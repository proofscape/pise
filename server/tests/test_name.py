# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2024 Proofscape Contributors                           #
#                                                                             #
#   Licensed under the Apache License, Version 2.0 (the "License");           #
#   you may not use this file except in compliance with the License.          #
#   You may obtain a copy of the License at                                   #
#                                                                             #
#       http://www.apache.org/licenses/LICENSE-2.0                            #
#                                                                             #
#   Unless required by applicable law or agreed to in writing, software       #
#   distributed under the License is distributed on an "AS IS" BASIS,         #
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  #
#   See the License for the specific language governing permissions and       #
#   limitations under the License.                                            #
# --------------------------------------------------------------------------- #

import json
import pathlib

import pytest

from tests import handleAsJson
from pfsc.constants import ISE_PREFIX, SYNC_JOB_RESPONSE_KEY
from pfsc.excep import PfscExcep, PECode
from pfsc.build.lib.libpath import PathInfo
from pfsc.lang.modules import build_module_from_text

err_lvl_key = 'err_lvl'


@pytest.mark.parametrize('parentpath, name, expected_code_1, expected_code_2', [
    # New module name needs .pfsc or .rst extension.
    ['test.spx.doc1.foo', 'bar', PECode.BAD_MODULE_FILENAME, 0],
    ['test.spx.doc1.foo', 'bar.spam', PECode.BAD_MODULE_FILENAME, 0],
    # User-supplied libpath segment cannot begin with reserved char.
    ['test.spx.doc1.foo', '_bar.pfsc', PECode.BAD_LIBPATH, 0],
    # Can't use a name that is an illegal libpath segment.
    ['test.spx.doc1.foo', 'true.pfsc', PECode.BAD_LIBPATH, 0],
    # Can't use a name whose stem is already taken.
    ['test.spx.doc1.foo', 'pageC.rst', 0, PECode.LIBSEG_UNAVAILABLE],
    ['test.spx.doc1.foo', 'pageC.pfsc', 0, PECode.LIBSEG_UNAVAILABLE],
    # Cannot make submodule under rst module.
    ['test.spx.doc1.pageA', 'foo.pfsc', 0, PECode.BAD_MODULE_FILENAME],
])
@pytest.mark.psm(True)
@pytest.mark.wip(True)
def test_new_submodule_fail(
        client, repos_ready,
        parentpath, name, expected_code_1, expected_code_2
):
    resp = client.put(f'{ISE_PREFIX}/makeNewSubmodule', data={
        'parentpath': parentpath,
        'name': name,
    })
    d = handleAsJson(resp)
    print(json.dumps(d, indent=4))
    assert d[err_lvl_key] == expected_code_1
    if expected_code_1 == 0:
        assert d[SYNC_JOB_RESPONSE_KEY][err_lvl_key] == expected_code_2


@pytest.mark.parametrize('parentpath, name', [
    # Parent is already a directory:
    ['test.spx.doc1.foo', 'pageOmega.rst'],
    ['test.spx.doc1.foo', 'pageOmega.pfsc'],
])
@pytest.mark.psm(True)
@pytest.mark.wip(True)
def test_new_submodule_under_dir(
        client, repos_ready, parentpath, name
):
    """
    Successfully make a new submodule under a parent that is already a dir.
    """
    resp = client.put(f'{ISE_PREFIX}/makeNewSubmodule', data={
        'parentpath': parentpath,
        'name': name,
    })
    d = handleAsJson(resp)
    print(json.dumps(d, indent=4))
    assert d[err_lvl_key] == 0
    s = d[SYNC_JOB_RESPONSE_KEY]
    assert s[err_lvl_key] == 0
    modpath = f'{parentpath}.{name.split(".")[0]}'
    assert s['modpath'] == modpath

    # Clean up:
    pi = PathInfo(modpath)
    p = pathlib.Path(pi.get_src_fs_path())
    assert p.name == name
    assert str(p.parent).endswith('/' + parentpath.replace('.', '/'))
    print(p)
    p.unlink()


@pytest.mark.parametrize('parentpath, name', [
    # Parent is a file, must be converted into a directory:
    ['test.spx.doc1.anno', 'bar.pfsc'],
])
@pytest.mark.psm(True)
@pytest.mark.wip(True)
def test_new_submodule_under_file(
        client, repos_ready, parentpath, name
):
    """
    Successfully make a new submodule under a parent that is a file, and must
    be converted into a dir.
    """
    resp = client.put(f'{ISE_PREFIX}/makeNewSubmodule', data={
        'parentpath': parentpath,
        'name': name,
    })
    d = handleAsJson(resp)
    print(json.dumps(d, indent=4))
    assert d[err_lvl_key] == 0
    s = d[SYNC_JOB_RESPONSE_KEY]
    assert s[err_lvl_key] == 0
    modpath = f'{parentpath}.{name.split(".")[0]}'
    assert s['modpath'] == modpath

    # Clean up:
    bar_pi = PathInfo(modpath)
    bar_p = pathlib.Path(bar_pi.get_src_fs_path())
    anno_pi = PathInfo(parentpath)
    anno_p = pathlib.Path(anno_pi.get_src_fs_path())
    anno_dir = anno_p.parent
    anno_file = pathlib.Path(f'{anno_dir}.pfsc')

    print(bar_p)
    print(anno_p)
    print(anno_file)
    print(anno_dir)
    assert bar_p.name == name
    assert str(bar_p.parent).endswith('/' + parentpath.replace('.', '/'))
    assert anno_p.name == '__.pfsc'
    assert str(anno_p.parent).endswith('/' + parentpath.replace('.', '/'))
    assert str(anno_dir).endswith('/' + parentpath.replace('.', '/'))

    bar_p.unlink()
    anno_p.replace(anno_file)
    anno_dir.rmdir()


@pytest.mark.parametrize('libpath, new_filename, new_dirname, expected_code_1, expected_code_2', [
    # If it's a file, it needs .pfsc or .rst extension.
    ['test.spx.doc1.foo.pageC', 'bar', None, PECode.BAD_MODULE_FILENAME, 0],
    ['test.spx.doc1.foo.pageC', 'bar.spam', None, PECode.BAD_MODULE_FILENAME, 0],
    # If it's a directory, it must not have an extension.
    ['test.spx.doc1.foo', None, 'bar.pfsc', PECode.BAD_LIBPATH, 0],
    # User-supplied libpath segment cannot begin with reserved char.
    ['test.spx.doc1.foo.pageC', '_bar.rst', None, PECode.BAD_LIBPATH, 0],
    # Can't use a name whose stem is already taken.
    ['test.spx.doc1.foo.pageC', 'pageC.rst', None, 0, PECode.LIBSEG_UNAVAILABLE],
    ['test.spx.doc1.foo.pageC', 'pageC.pfsc', None, 0, PECode.LIBSEG_UNAVAILABLE],
    # Cannot rename a whole repo.
    ['test.spx.doc1', None, 'foo', 0, PECode.LIBPATH_TOO_SHORT],
])
@pytest.mark.psm(True)
@pytest.mark.wip(True)
def test_rename_fail(
        client, repos_ready,
        libpath, new_filename, new_dirname, expected_code_1, expected_code_2
):
    data = {
        'libpath': libpath,
    }
    if new_filename is not None:
        data['newFilename'] = new_filename
    if new_dirname is not None:
        data['newDirname'] = new_dirname
    resp = client.patch(f'{ISE_PREFIX}/renameModule', data=data)
    d = handleAsJson(resp)
    print(json.dumps(d, indent=4))
    assert d[err_lvl_key] == expected_code_1
    if expected_code_1 == 0:
        assert d[SYNC_JOB_RESPONSE_KEY][err_lvl_key] == expected_code_2


@pytest.mark.parametrize('libpath, new_filename, new_dirname', [
    # Rename a file
    ['test.spx.doc1.foo.pageC', 'pageCC.rst', None],
    # Rename a dir
    ['test.spx.doc1.foo', None, 'bar'],
])
@pytest.mark.psm(True)
@pytest.mark.wip(True)
def test_rename(
        client, repos_ready,
        libpath, new_filename, new_dirname
):
    def get_path(pi):
        return pathlib.Path(pi.abs_fs_path_to_file if pi.is_file else pi.abs_fs_path_to_dir)

    old_libpath = libpath
    old_pi = PathInfo(old_libpath)
    old_path = get_path(old_pi)

    data = {
        'libpath': libpath,
    }
    new_segment = None
    if new_filename is not None:
        data['newFilename'] = new_filename
        new_segment = new_filename.split('.')[0]
    if new_dirname is not None:
        data['newDirname'] = new_dirname
        new_segment = new_dirname
    resp = client.patch(f'{ISE_PREFIX}/renameModule', data=data)
    d = handleAsJson(resp)
    print(json.dumps(d, indent=4))

    assert d[err_lvl_key] == 0
    s = d[SYNC_JOB_RESPONSE_KEY]
    assert s[err_lvl_key] == 0

    new_libpath = '.'.join(libpath.split('.')[:-1] + [new_segment])
    assert s['oldLibpath'] == old_libpath
    assert s['newLibpath'] == new_libpath

    # Clean up:
    new_pi = PathInfo(new_libpath)
    new_path = get_path(new_pi)
    print(new_path)
    print(old_path)
    new_path.replace(old_path)


DEF_TEXTS = {
    'deduc': """
    deduc %s {
            asrt C { sy = "C" }
            meson = "C"
        }
    """,
    'node': """
    deduc foo {
            asrt %s { sy = "C" }
            meson = "C"
        }
    """,
    'lhs': """
    %s = ['foo', 'bar']
    """,
    'anno': """
    anno %s @@@
    Blah blah blah.
    @@@
    """,
    'widget': """
    anno foo @@@
    Here's <chart:%s>[a chart widget]{coords: [0, 0, 1]}.
    @@@
    """,
}

def test_cannot_use_illegal_names(app):
    """
    Show that we cannot use illegal names for Proofscape entities.
    """
    print()
    with app.app_context():
        for place, pre_text in DEF_TEXTS.items():
            for name in ['true', 'false', 'null', 'foobar']:
                print(f'{place}: {name}')
                text = pre_text % name
                if name == 'foobar':
                    # No error
                    build_module_from_text(text, 'test._foo._bar')
                    print('  ok')
                else:
                    with pytest.raises(PfscExcep) as ei:
                        build_module_from_text(text, 'test._foo._bar')
                    assert ei.value.code() == PECode.BAD_LIBPATH
                    print('  raises')

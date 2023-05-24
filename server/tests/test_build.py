# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2023 Proofscape Contributors                           #
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

import pytest

from pfsc.build import Builder, build_module, build_release
from pfsc.build.manifest import load_manifest
from pfsc.build.products import load_annotation
from pfsc.build.repo import get_repo_info
from pfsc.gdb import get_graph_writer

from tests.util import clear_all_indexing, get_basic_repos, make_repos


# FIXME: How do we skip a test based on the app's configuration?
#   Want to skip this one if not app.config["BUILD_IN_GDB"].
@pytest.mark.parametrize('rec', [
    False,
    True,
])
@pytest.mark.psm
def test_partial_builds(app, rec):
    """
    Try building just test.moo.study.results@WIP, and then
    building test.moo.study.expansions@WIP. We want to check that the
    manifest for the repo _grows_ (i.e. the results of the first build
    are _not_ simply overwritten by the results of the second build).
    """
    with app.app_context():
        if not app.config["BUILD_IN_GDB"]:
            return
        repopath = 'test.moo.study'
        ri = get_repo_info(repopath)
        ri.checkout('v1.1.0')
        gw = get_graph_writer()
        modpath1 = f'{repopath}.results'
        modpath2 = f'{repopath}.expansions'

        gw.delete_full_wip_build(repopath)

        build_module(modpath1)
        m1 = load_manifest(repopath)
        print()
        print(json.dumps(m1.build_dict(), indent=4))

        build_module(modpath2, recursive=rec)
        m2 = load_manifest(repopath)
        d2 = m2.build_dict()
        print()
        print(json.dumps(d2, indent=4))

        ch = d2["tree_model"]["children"]
        assert len(ch) == 2
        assert {c["libpath"] for c in ch} == {modpath1, modpath2}


def test_chart_widget_versions_dict_in_release(app, repos_ready):
    """
    The JSON data for a Chart widget contains a "versions" dictionary, listing
    the version at which to take each repo from which it draws. Here we want
    to check that, in a numbered release, we say to take our _own_ repo at the
    same version number at which we were built.
    """
    with app.app_context():
        repopath = 'test.moo.study'
        annopath = f'{repopath}.expansions.Notes1'
        version = 'v1.1.0'
        _, j = load_annotation(annopath, version=version)
        d = json.loads(j)
        #print(json.dumps(d, indent=4))
        widgets = d["widgets"]
        w10 = widgets["test-moo-study-expansions-Notes1-w10_v1-1-0"]
        assert w10["versions"][repopath] == version


# Try calling Builder.build()
@pytest.mark.skip(reason="just for manual testing")
@pytest.mark.parametrize("libpath, rec", (
    ("test.foo.bar", False),
    #("test.foo.bar.expansions", False),
    #("test.hist.lit", False),
    #("test.hist.lit.H.ilbert.ZB.Thm168.notes", False),
))
def test_build(libpath, rec):
    b = Builder(libpath, recursive=rec)
    b.build()
    print(json.dumps(b.manifest.build_dict(), indent=4))
    print()
    d = b.manifest.build_dict()
    j = json.dumps(d, indent=4)
    print(j)

# Try full build, index, & write
# Here we use `build_module()`, hence build @WIP.
# To build at a numbered release, see `test_build_release()` below.
@pytest.mark.skip(reason="just for manual testing")
@pytest.mark.parametrize("libpath, rec", (
    ("test.spx.doc0", True),
    ("test.spx.doc1", True),
    #("test.moo.bar", True),
    #("test.foo.bar.expansions", False),
    #("test.hist.lit", True),
    #("test.hist.lit.G.alois", True),
    #("test.hist.lit.H.ilbert.ZB.rdefs", False),
    #("test.hist.lit.H.ilbert.ZB", False),
    #("test.hist.lit.H.ilbert.ZB.Thm168.notes", False),
    #("test.hist.lit.H.ilbert.ZB.Pg180L1", False),
    #("test.hist.lit.H.ilbert.ZB.Thm117", True),
    #("test.wid.get.notes", False),
    #("test.moo.study.expansions", False),
    #("test.moo.links.deducs1", False),
    #("test.comment.notes.H.ilbert.ZB.Thm17", False),
))
@pytest.mark.psm
def test_full_build(app, libpath, rec):
    with app.app_context():
        cb = Builder(libpath, recursive=rec, verbose=False)
        build_module(cb)


# Try full build on different branches.
@pytest.mark.skip(reason="just for manual testing")
@pytest.mark.parametrize("libpath, branch, rec", (
    ("test.foo.bar.results", "v16", False),
    #("test.foo.bar.expansions", "v2", True),
))
@pytest.mark.psm
def test_full_build_at_version(app, libpath, branch, rec):
    with app.app_context():
        ri = get_repo_info(libpath)
        ri.checkout(branch)
        cb = Builder(libpath, recursive=rec, verbose=False)
        build_module(cb)


# Handy for manually remaking a single test repo, when developing.
@pytest.mark.skip(reason="For manual testing only!")
@pytest.mark.parametrize('only', [
    [('spx', 'doc1')],
])
@pytest.mark.psm
def test_make_repos(app, only):
    print()
    make_repos(only=only)


# NOTE: Must skip this test during ordinary unit testing!
# This test clears test indexing, so if included in the overall test suite,
# will cause many tests to error out.
@pytest.mark.skip(reason="For manual testing only!")
@pytest.mark.parametrize('repopath, version', [
    #['test.alex.math', 'v3.0.0'],
    #['test.brook.math', 'v0.0.0'],
    #['test.moo.bar', 'v2.1.0'],
    #['test.moo.links', 'v0.1.0'],
    #['test.moo.bar', 'v0.3.4'],
    #['test.moo.study', 'v1.1.0'],
    #['test.hist.lit', 'v0.0.0'],
    #['test.comment.notes', 'v0.1.0'],
    #['test.wid.get', 'v0.1.0'],
    #['test.moo.beta', 'v0.1.1'],
    ['test.spx.doc0', 'v0.1.0'],
])
@pytest.mark.psm
def test_build_release(app, repopath, version):
    """
    Clear index of test junk, then build the desired repo at the desired
    version, first building any dependencies.
    """
    repos_built = set()
    clear_all_indexing()
    repos = get_basic_repos()
    repos = {r.libpath:r for r in repos}
    stack = []
    def request_version(rp, vers):
        repo = repos[rp]
        i0 = repo.tag_names.index(vers)
        versions = reversed(repo.tag_names[:i0+1])
        stack.extend([(rp, v) for v in versions])
    request_version(repopath, version)
    with app.app_context():
        # Setting ALLOW_WIP to False makes this serve as a test of the
        # `pfsc.lang.modules.inherit_release_build_signal()` function.
        app.config["ALLOW_WIP"] = False
        while stack:
            rp, vers = stack.pop()
            repo = repos[rp]
            repo.lookup_dependencies()
            deps = repo.deps[vers].rhs if vers in repo.deps else {}
            prereqs = []
            for k, v in deps.items():
                if f'{k}@{v}' not in repos_built:
                    prereqs.append((k, v))
            if prereqs:
                stack.append((rp, vers))
                for k, v in prereqs:
                    request_version(k, v)
            else:
                build_release(rp, version=vers, verbose=True)
                repos_built.add(f'{rp}@{vers}')

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

from pfsc.build import Builder, build_repo
from pfsc.build.products import load_annotation
from pfsc.build.repo import get_repo_info

from tests.util import clear_and_build_releases_with_deps_depth_first, make_repos


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
@pytest.mark.parametrize("libpath, clean", (
    ("test.foo.bar", False),
    #("test.foo.bar.expansions", False),
    #("test.hist.lit", False),
    #("test.hist.lit.H.ilbert.ZB.Thm168.notes", False),
))
def test_build(libpath, clean):
    b = Builder(libpath, make_clean=clean)
    b.build()
    print(json.dumps(b.manifest.build_dict(), indent=4))
    print()
    d = b.manifest.build_dict()
    j = json.dumps(d, indent=4)
    print(j)

# Try full build, index, & write
# Here we use `build_repo()`, hence build @WIP.
# To build at a numbered release, see `test_build_release()` below.
@pytest.mark.skip(reason="just for manual testing")
@pytest.mark.parametrize("libpath, clean", (
    #("test.spx.doc0", True),
    ("test.spx.doc1", True),
    #("test.moo.bar", True),
    #("test.foo.bar.expansions", True),
    #("test.hist.lit", True),
    #("test.hist.lit.G.alois", True),
    #("test.hist.lit.H.ilbert.ZB.rdefs", True),
    #("test.hist.lit.H.ilbert.ZB", True),
    #("test.hist.lit.H.ilbert.ZB.Thm168.notes", True),
    #("test.hist.lit.H.ilbert.ZB.Pg180L1", True),
    #("test.hist.lit.H.ilbert.ZB.Thm117", True),
    #("test.wid.get.notes", True),
    #("test.moo.study.expansions", True),
    #("test.moo.links.deducs1", True),
    #("test.comment.notes.H.ilbert.ZB.Thm17", True),
))
@pytest.mark.psm
def test_full_build(app, libpath, clean):
    with app.app_context():
        cb = Builder(libpath, verbose=False, make_clean=clean)
        build_repo(cb)


# Try full build on different branches.
@pytest.mark.skip(reason="just for manual testing")
@pytest.mark.parametrize("libpath, branch, clean", (
    ("test.foo.bar.results", "v16", True),
    #("test.foo.bar.expansions", "v2", True),
))
@pytest.mark.psm
def test_full_build_at_version(app, libpath, branch, clean):
    with app.app_context():
        ri = get_repo_info(libpath)
        ri.checkout(branch)
        cb = Builder(libpath, make_clean=clean, verbose=False)
        build_repo(cb)


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
    #['test.alex.math', 'v0.0.0'],
    #['test.brook.math', 'v0.0.0'],
    #['test.moo.bar', 'v2.1.0'],
    #['test.moo.links', 'v0.1.0'],
    #['test.moo.bar', 'v0.3.4'],
    #['test.moo.study', 'v1.1.0'],
    #['test.hist.lit', 'v0.0.0'],
    #['test.comment.notes', 'v0.1.0'],
    #['test.wid.get', 'v0.1.0'],
    #['test.moo.beta', 'v0.1.1'],
    #['test.spx.doc0', 'v0.1.0'],
    ['test.spx.doc1', 'v0.1.0'],
])
@pytest.mark.psm
def test_build_release(app, repopath, version):
    clear_and_build_releases_with_deps_depth_first(app, [(repopath, version)])

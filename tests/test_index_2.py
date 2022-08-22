# --------------------------------------------------------------------------- #
#   Proofscape Server                                                         #
#                                                                             #
#   Copyright (c) 2011-2022 Proofscape contributors                           #
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

import pfsc.constants
from pfsc.build import build_module, build_release
from pfsc.build.repo import get_repo_info
from pfsc.gdb import get_graph_reader, get_graph_writer
from pfsc.excep import PfscExcep, PECode

def test_get_versions(app, repos_ready):
    with app.app_context():
        gr = get_graph_reader()
        infos = gr.get_versions_indexed('test.moo.bar')
        full_versions = [info['version'] for info in infos]
        assert full_versions == ["v0.3.4", "v1.0.0", "v2.0.0", "v2.1.0"]


def test_is_version_indexed(app, repos_ready):
    with app.app_context():
        gr = get_graph_reader()
        assert gr.version_is_already_indexed('test.moo.bar', 'v0.3.4')
        assert not gr.version_is_already_indexed('test.moo.bar', 'v0.3.5')


def test_get_modpath(app, repos_ready):
    with app.app_context():
        gr = get_graph_reader()
        libpath = 'test.moo.bar.results.Pf.E'
        modpath = 'test.moo.bar.results'
        assert gr.get_modpath(libpath, 2) == modpath
        assert gr.get_modpath(libpath, 1) is None


@pytest.mark.parametrize('version, err_code', [
['v1.0.0', PECode.MISSING_REPO_CHANGE_LOG],
['v2.0.0', PECode.MISSING_REPO_CHANGE_LOG],
['v3.0.0', PECode.VERSION_NOT_BUILT_YET],
['v4.0.0', PECode.BAD_LIBPATH],
# The next one does raise an exception, but the point is to test that
# a warning is printed about the libpath that looks absolute when
# it's supposed to be relative.
['v5.0.0', PECode.INVALID_MOVE_MAPPING],
])
@pytest.mark.psm
def test_various_errors(app, version, err_code):
    """
    Test some of the exceptions that can be raised when attempting
    to do a release build.
    """
    with app.app_context():
        repopath = 'test.moo.err'
        with pytest.raises(PfscExcep) as ei:
            build_release(repopath, version)
        pe = ei.value
        print('\n', pe)
        assert pe.code() == err_code

@pytest.mark.parametrize('version, err_code', [
['v1.1.0', PECode.BUILD_MAKES_DISALLOWED_BREAKING_CHANGE],
['v2.0.0', PECode.MULTIPLE_EXPANSION_DEFINITION],
])
@pytest.mark.psm
def test_more_errors(app, version, err_code):
    """
    This time we test errors that require an attempt to do something
    mistaken, based on an existing successful build. So v1.0.0 of
    repo test.moo.err2 is designed to build correctly, but subsequent
    versions are designed to have errors.
    """
    with app.app_context():
        gw = get_graph_writer()
        gr = gw.reader
        repopath = 'test.moo.err2'
        # Ensure the initial (correct) version is built.
        if not gr.version_is_already_indexed(repopath, 'v1.0.0'):
            build_release(repopath, 'v1.0.0')
        # Now trigger errors with subsequent versions.
        with pytest.raises(PfscExcep) as ei:
            build_release(repopath, version)
        pe = ei.value
        print('\n', pe)
        assert pe.code() == err_code
        # Clean up
        gw.delete_everything_under_repo('test.moo.err2')


def check_everything_under_repo(repopath):
    gr = get_graph_reader()
    return gr.everything_under_repo(repopath)


# FIXME: maybe we can let indexing happen here under `test2.`?
@pytest.mark.skip("Doesn't work with our new system where all release builds are already done.")
def test_moo_bar(app):
    """
    This test examines the behavior of the index on alternating release
    and WIP builds. If we begin with a WIP build, we expect the index to
    make nodes and relns to represent it. If we then do a release build,
    we expect this too to make new nodes and relns, since the release
    build cannot rely on the WIP indexing to stay around. If we then go
    back and do another WIP build, this time we should be left with only
    the nodes from the indexed release
    """
    verbose = True
    print()
    with app.app_context():
        repopath = 'test.moo.bar'
        ri = get_repo_info(repopath)

        # Starting from a clean index, we make a
        # WIP build on a preliminary version.
        v = 'v0.3.4'
        print('=' * 50)
        print(v)
        ri.checkout(v)
        v034_hash = ri.get_current_commit_hash()
        build_module(repopath, recursive=True)
        g = check_everything_under_repo(repopath)
        if verbose:
            print(g)
            print(g.writeIndexInfo())
        assert len(g.nodes) == 8
        assert len(g.relns) == 12

        # Now do a release build.
        # This should duplicate all the nodes curently in the index.
        # This is the right behavior because currently all we have are WIP nodes,
        # and those cannot be counted on to stay around.
        v = 'v1.0.0'
        print('=' * 50)
        print(v)
        build_release(repopath, v)
        g = check_everything_under_repo(repopath)
        if verbose:
            print(g)
            print(g.writeIndexInfo())
        # Actually we did more than duplicate, since we also added the node `T`.
        # And it brings with it a new UNDER and a new IMPLIES relation. So...
        assert len(g.nodes) == 8 + (8 + 1)
        assert len(g.relns) == 12 + (12 + 2)

        # Check that the system restored us to the commit we were on before
        # the release build:
        assert ri.get_current_commit_hash() == v034_hash
        # Now, let's do another WIP build, this time at v2.0.0.
        # This time, the system should (a) start by clearing out all existin WIP
        # nodes (as always), and then (b) recognize that there are already stable
        # nodes that it can use, so it doesn't need to make most nodes this time.
        v = 'v2.0.0'
        print('=' * 50)
        print(v)
        ri.checkout(v)
        build_module(repopath, recursive=True)
        g = check_everything_under_repo(repopath)
        if verbose:
            print(g)
            print(g.writeIndexInfo())
        assert len(g.nodes) == 10
        assert len(g.relns) == 19
        # However, we're now working on a version where nodes `T` and `S` as well
        # are gone. So a few `cut: WIP` properties should have been set, on both
        # nodes and relns.
        cut_nodes = list(filter(lambda u: u.cut == pfsc.constants.WIP_TAG, g.nodes))
        cut_relns = list(filter(lambda r: r.cut == pfsc.constants.WIP_TAG, g.relns))
        if verbose:
            print('Cut:')
            print(cut_nodes)
            print(cut_relns)
        assert len(cut_nodes) == 2
        assert len(cut_relns) == 5
        # Check that we got two MOVE relations.
        mt = [r for r in g.relns if r.reln_type == pfsc.constants.IndexType.MOVE]
        assert len(mt) == 2
        if verbose:
            for r in mt:
                print('Moved:')
                print(r)
        node_pairs = [
            [str(r.tail_libpath).split('.')[-1], str(r.head_libpath).split('.')[-1]]
            for r in mt
        ]
        print(node_pairs)
        assert ["S", "None"] in node_pairs
        assert ["T", "U"] in node_pairs

def test_find_move_conjugate(app, repos_ready):
    """
    Try computing some move-conjugates.

    As we move from v2 to v3 of the test.moo.spam repo, our change log
    looks like this:

        change_log={
            moved: {
                "Ch1.Sec8": null,
                "Ch1.Sec8.Thm15": "Ch1.Sec7.Thm15",
                "Ch1.Sec8.Pf": "Ch1.Sec7.Pf15",
                "Ch1.Sec8.Pf.A50": null,
            }
        }

    Therefore:

      * Node `test.moo.spam.Ch1.Sec8.Pf.E20.A4` should have libpath
        `test.moo.spam.Ch1.Sec7.Pf15.E20.A4` for its move-conjugate;
      * Section `test.moo.spam.Ch1.Sec8` was deleted, so the move-conjugate
         should be `None`;
      * Anno `test.moo.spam.Ch1.Sec7.Notes` did not move at all, so
         we should get `False` when we ask for the move-conjugate;
      * Node `test.moo.spam.Ch1.Sec8.Pf.A50` was deleted, so we expect `None`.
    """
    print()
    with app.app_context():
        gr = get_graph_reader()
        mc = gr.find_move_conjugate("test.moo.spam.Ch1.Sec8.Pf.E20.A4", 2)
        print(mc)
        assert mc.libpath == "test.moo.spam.Ch1.Sec7.Pf15.E20.A4"
        assert mc.major == "000003"
        mc = gr.find_move_conjugate("test.moo.spam.Ch1.Sec8", 2)
        print(mc)
        assert mc == pfsc.constants.IndexType.VOID
        mc = gr.find_move_conjugate("test.moo.spam.Ch1.Sec7.Notes", 2)
        print(mc)
        assert mc is None
        mc = gr.find_move_conjugate("test.moo.spam.Ch1.Sec8.Pf.A50", 2)
        print(mc)
        assert mc == pfsc.constants.IndexType.VOID

def test_get_enrichment_no_wip(app, repos_ready):
    """
    Check a case where there should _not_ be any enrichments available
    at WIP.
    """
    print()
    with app.app_context():
        gr = get_graph_reader()
        E = gr.get_enrichment('test.moo.bar.results.Thm', 1)
        print(json.dumps(E, indent=4))
        assert E['test.moo.bar.results.Thm.C']["Deduc"][0][pfsc.constants.WIP_TAG] == False

def test_moo_comment_1(app, repos_ready):
    """
    Test the detection of enrichments.
    """
    print()
    with app.app_context():
        gr = get_graph_reader()
        E = gr.get_enrichment('test.moo.bar.results.Pf', 1, filter_by_repo_permission=False)
        print(json.dumps(E, indent=4))
        for name in ["S", "T"]:
            assert f"test.moo.bar.results.Pf.{name}" in E
            e = E[f"test.moo.bar.results.Pf.{name}"]
            d = e["Deduc"]
            a = e["Anno"]
            assert len(d) == 1 and d[0]["libpath"] == f"test.moo.comment.bar.xpan_{name}"
            assert len(a) == 1 and a[0]["libpath"] == f"test.moo.comment.bar.Notes{name}"
            assert d[0]["latest"] == "v0.2.0"
            assert d[0][pfsc.constants.WIP_TAG] == True
            assert a[0]["latest"] == "v0.2.0"
            assert a[0][pfsc.constants.WIP_TAG] == True

def test_moo_comment_2a(app, repos_ready):
    """
    Test the generation of RETARGETS edges.
    """
    print()
    with app.app_context():
        # We expect to find
        #  test.moo.comment.bar.xpan_T
        #  test.moo.comment.bar.NotesT
        # as enrichments on test.moo.bar.results.Pf.U
        gr = get_graph_reader()
        E = gr.get_enrichment('test.moo.bar.results.Pf', 2, filter_by_repo_permission=False)
        print(json.dumps(E, indent=4))
        assert "test.moo.bar.results.Pf.U" in E
        e = E["test.moo.bar.results.Pf.U"]
        d = e["Deduc"]
        a = e["Anno"]
        assert len(d) == 2 and "test.moo.comment.bar.xpan_T" in [d[i]["libpath"] for i in range(2)]
        assert len(a) == 1 and a[0]["libpath"] == "test.moo.comment.bar.NotesT"

@pytest.mark.skip("""This no longer does anything different from the last test.
We need to carefully design our set of test repos so that we can test generation
of RETARGETS edges for enrichments added _before_ their targets move, as well as
for enrichments added _after_ their targets have already moved.""")
def test_moo_comment_2b(app, repos_ready):
    """
    Test the generation of RETARGETS edges for enrichments added _before_ their
    targets move.
    """
    print()
    with app.app_context():
        # We expect to find
        #  test.moo.comment.bar.xpan_T
        #  test.moo.comment.bar.NotesT
        # as enrichments on test.moo.bar.results.Pf.U
        gr = get_graph_reader()
        E = gr.get_enrichment('test.moo.bar.results.Pf', 2, filter_by_repo_permission=False)
        print(json.dumps(E, indent=4))
        assert "test.moo.bar.results.Pf.U" in E
        e = E["test.moo.bar.results.Pf.U"]
        d = e["Deduc"]
        a = e["Anno"]
        assert len(d) == 1 and d[0]["libpath"] == "test.moo.comment.bar.xpan_T"
        assert len(a) == 1 and a[0]["libpath"] == "test.moo.comment.bar.NotesT"

def test_retarget_for_moves(app, repos_ready):
    """
    Test the generation of RETARGETS edges of the second kind, i.e. those
    for existing enrichments on entities that moved.
    """
    print()
    with app.app_context():
        lp7 = 'test.moo.spam.Ch1.Sec7.Thm15'
        lp8 = 'test.moo.spam.Ch1.Sec8.Thm15'
        gr = get_graph_reader()
        E1 = gr.get_enrichment(lp7, 1)
        E2 = gr.get_enrichment(lp8, 2)
        E3 = gr.get_enrichment(lp7, 3)
        print(json.dumps(E1, indent=4))
        print(json.dumps(E2, indent=4))
        print(json.dumps(E3, indent=4))

        lp7C = lp7 + ".C"
        lp8C = lp8 + ".C"

        def scan(E, lp):
            d = {}
            for i in E[lp]["Deduc"]:
                d[i["latest"]] = i["libpath"]
            return d

        assert scan(E1, lp7C) == {
            "v1.0.0": "test.moo.spam.Ch1.Sec7.Pf"
        }
        assert scan(E2, lp8C) == {
            "v1.0.0": "test.moo.spam.Ch1.Sec7.Pf",
            "v2.0.0": "test.moo.spam.Ch1.Sec8.Pf"
        }
        assert scan(E3, lp7C) == {
            "v1.0.0": "test.moo.spam.Ch1.Sec7.Pf",
            "v2.0.0": "test.moo.spam.Ch1.Sec8.Pf",
            "v3.0.1": "test.moo.spam.Ch1.Sec7.Pf15"
        }

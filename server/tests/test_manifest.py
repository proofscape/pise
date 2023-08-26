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

from pfsc.build.manifest import (
    build_manifest_from_dict,
    load_manifest,
    Manifest,
    ManifestTreeNode,
)


manifest_00 = {
    "build": {
        "a.b0": {
            "version": "WIP",
            "commit": "123412341234",
            "time": "Monday",
            "recursive": False,
        }
    },
    "doc_info": {},
    "tree_model": {
        "id": "a",
        "libpath": "a",
        "name": "a",
        "children": [
            {
                "id": "a.b0",
                "libpath": "a.b0",
                "name": "b0"
            }
        ]
    }
}


manifest_01 = {
    "build": {
        "a.b1": {
            "version": "WIP",
            "commit": "abcdabcdabcd",
            "time": "Tuesday",
            "recursive": False,
        }
    },
    "doc_info": {},
    "tree_model": {
        "id": "a",
        "libpath": "a",
        "name": "a",
        "children": [
            {
                "id": "a.b1",
                "libpath": "a.b1",
                "name": "b1",
                "type": "BAR",
            }
        ]
    }
}


manifest_01_c1 = {
    "build": {
        "a.b1": {
            "version": "WIP",
            "commit": "abcdabcdabcd",
            "time": "Tuesday",
            "recursive": False,
        },
        "a.b1.c1": {
            "version": "WIP",
            "commit": "a1b2c3d4",
            "time": "Wednesday",
            "recursive": False,
        },
    },
    "doc_info": {},
    "tree_model": {
        "id": "a",
        "libpath": "a",
        "name": "a",
        "children": [
            {
                "id": "a.b1",
                "libpath": "a.b1",
                "name": "b1",
                "type": "BAR",
                "children": [
                    {
                        "id": "a.b1.c1",
                        "libpath": "a.b1.c1",
                        "name": "c1"
                    }
                ]
            }
        ]
    }
}


manifest_01r = {
    "build": {
        "a.b1": {
            "version": "WIP",
            "commit": "abcdabcdabcd",
            "time": "Tuesday",
            "recursive": True,
        }
    },
    "doc_info": {},
    "tree_model": {
        "id": "a",
        "libpath": "a",
        "name": "a",
        "children": [
            {
                "id": "a.b1",
                "libpath": "a.b1",
                "name": "b1",
                "type": "BAR",
            }
        ]
    }
}


manifest_02_c_CAT = {
    "build": {
        "a.b1.c": {
            "recursive": False,
        }
    },
    "doc_info": {},
    "tree_model": {
        "id": "a",
        "libpath": "a",
        "name": "a",
        "children": [
            {
                "id": "a.b1",
                "libpath": "a.b1",
                "name": "b1",
                "type": "FOO",
                "children": [
                    {
                        "id": "a.b1.c",
                        "libpath": "a.b1.c",
                        "name": "c",
                        "type": "CAT",
                    }
                ]
            }
        ]
    }
}


manifest_02_c_MOD = {
    "build": {
        "a.b1.c": {
            "recursive": False,
        }
    },
    "doc_info": {},
    "tree_model": {
        "id": "a",
        "libpath": "a",
        "name": "a",
        "children": [
            {
                "id": "a.b1",
                "libpath": "a.b1",
                "name": "b1",
                "type": "FOO",
                "children": [
                    {
                        "id": "a.b1.c",
                        "libpath": "a.b1.c",
                        "name": "c",
                        "type": "MODULE",
                    }
                ]
            }
        ]
    }
}


manifest_03 = {
    "build": {
        "a.b1.c.d": {
            "recursive": False,
        }
    },
    "doc_info": {},
    "tree_model": {
        "id": "a",
        "libpath": "a",
        "name": "a",
        "children": [
            {
                "id": "a.b1",
                "libpath": "a.b1",
                "name": "b1",
                "type": "FOO",
                "children": [
                    {
                        "id": "a.b1.c",
                        "libpath": "a.b1.c",
                        "name": "c",
                        "type": "MODULE",
                        "children": [
                            {
                                "id": "a.b1.c.d",
                                "libpath": "a.b1.c.d",
                                "name": "d",
                                "type": "FOO",
                            }
                        ]
                    }
                ]
            }
        ]
    }
}


def make(m):
    m = json.loads(json.dumps(m))
    return build_manifest_from_dict(m)


def show(m):
    d = m.build_dict()
    j = json.dumps(d, indent=4)
    print("=" * 40)
    print(j)
    return d


def test_manifest_1():
    """Test that we can build a manifest manually. """
    root_node = ManifestTreeNode('a', name="a")
    manifest = Manifest(root_node)
    node1 = ManifestTreeNode('a.b0', name="b0")
    manifest.get('a').add_child(node1)
    manifest.set_build_info('a.b0', 'WIP', '123412341234', 'Monday', False)
    d = manifest.build_dict()
    j = json.dumps(d, indent=4)
    print(j)
    assert d == manifest_00


def test_merge_01():
    """Merge a pair of sibling builds. """
    m00 = make(manifest_00)
    m01 = make(manifest_01)
    m00.merge(m01)
    d = show(m00)
    assert set(d["build"].keys()) == {"a.b0", "a.b1"}
    assert set(c["id"] for c in d["tree_model"]["children"]) == {"a.b0", "a.b1"}


def test_merge_02():
    """Merge a new build of a parent module. """
    m01 = make(manifest_01)
    m01r = make(manifest_01r)

    # We merge a non-recursive build of our parent module.
    # We have a child of type "CAT". Only children of type
    # "MODULE" are preserved in such a case, so this child
    # vanishes.
    m02_cat = make(manifest_02_c_CAT)
    m02_cat.merge(m01)
    d = show(m02_cat)
    assert "a.b1.c" in d["build"]
    a_b1 = d["tree_model"]["children"][0]
    assert a_b1["type"] == "BAR"
    assert "children" not in a_b1

    # We merge a recursive build of our parent module.
    # Everything we had before is replaced completely.
    m02_cat = make(manifest_02_c_CAT)
    m02_cat.merge(m01r)
    d = show(m02_cat)
    assert d == manifest_01r

    # We merge a non-recursive build of our parent module.
    # This time we have a child that is of type "MODULE",
    # so it is preserved.
    m02_mod = make(manifest_02_c_MOD)
    m02_mod.merge(m01)
    d = show(m02_mod)
    a_b1 = d["tree_model"]["children"][0]
    assert a_b1["type"] == "BAR"
    a_b1_c = a_b1["children"][0]
    assert a_b1_c["id"] == "a.b1.c"
    assert a_b1_c["type"] == "MODULE"


def test_merge_03():
    """Merge submodule where first common ancestor is its grandparent. """
    m01_c1 = make(manifest_01_c1)
    m03 = make(manifest_03)
    m01_c1.merge(m03)
    d = show(m01_c1)
    a_b1 = d["tree_model"]["children"][0]
    assert set(c["id"] for c in a_b1["children"]) == {
        "a.b1.c1", "a.b1.c"
    }
    a_b1_c = a_b1["children"][1]
    assert a_b1_c["children"][0]["id"] == "a.b1.c.d"


def test_merge_04():
    """Replace the built module itself. """
    m02_cat = make(manifest_02_c_CAT)
    m02_mod = make(manifest_02_c_MOD)
    m02_cat.merge(m02_mod)
    d = show(m02_cat)
    assert d == manifest_02_c_MOD


def test_is_terminal(repos_ready):
    """Check the `isTerminal` property."""
    manifest = load_manifest('test.alex.math', version='v3.0.0')
    root = manifest.get_root_node()
    model = []
    root.build_relational_model(model)
    for info in model:
        lp = info['libpath']
        if lp == 'test.alex.math.thm1':
            # If terminal, then definitely has no submodules.
            assert info['isTerminal'] is True
            assert info['hasSubmodules'] is False
        if lp == 'test.alex.math':
            # If non-terminal, may have submodules, but also may not (see below).
            assert info['isTerminal'] is False
            assert info['hasSubmodules'] is True

    manifest = load_manifest('test.hist.lit', version='v0.0.0')
    root = manifest.get_root_node()
    model = []
    root.build_relational_model(model)
    for info in model:
        lp = info['libpath']
        if lp == 'test.hist.lit.H.ilbert.ZB.Thm9':
            # Here is a case where the module is non-terminal but (currently)
            # has no submodules.
            assert info['isTerminal'] is False
            assert info['hasSubmodules'] is False


def test_doc_info(repos_ready):
    """Check the `doc_info` field."""
    manifest = load_manifest('test.hist.lit', version='v0.0.0')
    d = manifest.build_dict()

    doc_ids = [
        "pdffp:73a76954e6a0db76a97e98bdac835811",
        "pdffp:f55073bb58f8823ebfa19482ab6fdabe"
    ]
    assert set(d["doc_info"].keys()) == set(doc_ids)

    Thm9 = manifest.lookup["test.hist.lit.H.ilbert.ZB.Thm9.Pf"]
    assert len(Thm9.build_dict()["docRefs"][doc_ids[1]]) == 4

    Thm117 = manifest.lookup["test.hist.lit.H.ilbert.ZB.Thm117.Pf"]
    assert len(Thm117.build_dict()["docRefs"][doc_ids[0]]) == 1

    Thm118 = manifest.lookup["test.hist.lit.H.ilbert.ZB.Thm118.Pf1"]
    assert len(Thm118.build_dict()["docRefs"][doc_ids[0]]) == 1

    manifest = load_manifest('test.comment.notes', version='v0.1.0')
    d = manifest.build_dict()

    doc_ids = [
        "pdffp:6318d851c27fc30fd97ac614cf747ac0"
    ]
    assert set(d["doc_info"].keys()) == set(doc_ids)

    wt = manifest.lookup["test.comment.notes.H.ilbert.ZB.Thm168.notes.Walkthrough"]
    assert len(wt.build_dict()["docRefs"][doc_ids[0]]) == 1

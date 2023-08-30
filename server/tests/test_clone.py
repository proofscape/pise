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

import pytest
import json

from pfsc.build.repo import get_repo_info
from pfsc.excep import PfscExcep, PECode
from pfsc.lang.modules import build_module_from_text


@pytest.mark.psm
def test_clone_00(app):
    """
    Show that we get the expected error if we try to clone a ghost node.
    """
    print()
    modtext = """
    from test.hist.lit.K.ummer.Cr040_08 import Pf

    deduc Foo {

        asrt A {
            sy = "A"
        }

        clone Pf.Thm.C

        meson = "A so C."
    }
    """
    with app.app_context():
        modpath = f'test.local.foo'
        with pytest.raises(PfscExcep) as ei:
            module = build_module_from_text(modtext, modpath, dependencies={
                'test.hist.lit': "WIP",
            })
            module.resolve()
        assert ei.value.code() == PECode.CANNOT_CLONE_NODE


@pytest.mark.psm
def test_clone_01(app):
    """
    Basic test of node cloning. Show that we can make a clone, which gets a
    'cloneOf' property pointing to the original, and gets the 'labelHTML' from
    the original. Show that non-clones have 'cloneOf' equal to `None`.
    Show that we can use an "as" clause to give a clone a different local name.
    """
    print()
    modtext = """
    from test.hist.lit.K.ummer.Cr040_08 import Pf

    deduc Foo {

        clone Pf.A10

        asrt A20 {
            sy = "A20"
        }
        
        clone Pf.A30 as A25

        meson = "A10 so A20, hence A25."
    }
    """
    with app.app_context():
        modpath = f'test.local.foo'
        module = build_module_from_text(modtext, modpath, dependencies={
            'test.hist.lit': "WIP",
        })
        module.resolve()
        name = 'Foo'
        deduc = module[name]
        dg = deduc.buildDashgraph()
        print(json.dumps(dg, indent=4))
        no = dg["nodeOrder"]
        assert no == [
            "test.local.foo.Foo.A10",
            "test.local.foo.Foo.A20",
            "test.local.foo.Foo.A25",
        ]
        ch = dg["children"]
        assert ch[no[0]]["cloneOf"] == "test.hist.lit.K.ummer.Cr040_08.Pf.A10@WIP"
        assert ch[no[0]]["labelHTML"] == "%3Cp%3EThe%20class%20number%20of%20%24%5Cmathbb%7BQ%7D(%5Calpha)%24%3Cbr%3E%0Ais%20not%20divisible%20by%20%24%5Clambda%24.%3C%2Fp%3E%0A"
        assert ch[no[1]]["cloneOf"] is None
        assert ch[no[2]]["cloneOf"] == "test.hist.lit.K.ummer.Cr040_08.Pf.A30@WIP"


@pytest.mark.psm
def test_clone_02a(app):
    """
    Show that we can clone both a `supp` node and a linked `flse` node, and
    that the `contra` in the cloned `flse` node makes it link to the cloned
    `supp` node.
    """
    print()
    modtext = """
    from test.foo.bar.results import Pf

    deduc Foo {

        clone Pf.S

        asrt A20 {
            sy = "A20"
        }
        
        clone Pf.F

        meson = "Suppose S. Then A20, so F."
    }
    """
    with app.app_context():
        repopath = 'test.foo.bar'
        ri = get_repo_info(repopath)
        ri.checkout('v7')
        modpath = f'test.local.foo'
        module = build_module_from_text(modtext, modpath, dependencies={
            'test.foo.bar': "WIP",
        })
        module.resolve()
        name = 'Foo'
        deduc = module[name]
        dg = deduc.buildDashgraph()
        print(json.dumps(dg, indent=4))
        no = dg["nodeOrder"]
        assert no == [
            "test.local.foo.Foo.S",
            "test.local.foo.Foo.A20",
            "test.local.foo.Foo.F"
        ]
        ch = dg["children"]
        assert ch[no[0]]["cloneOf"] == "test.foo.bar.results.Pf.S@WIP"
        assert ch[no[2]]["cloneOf"] == "test.foo.bar.results.Pf.F@WIP"
        assert ch[no[2]]["contra"] == [
            "test.local.foo.Foo.S"
        ]


@pytest.mark.psm
def test_clone_02b(app):
    """
    Show that we can clone just a `flse` node, and its `contra` will simply
    continue to link it to a node that's not present here.
    """
    print()
    modtext = """
    from test.foo.bar.results import Pf

    deduc Foo {

        asrt A20 {
            sy = "A20"
        }

        clone Pf.F

        meson = "A20, so F."
    }
    """
    with app.app_context():
        repopath = 'test.foo.bar'
        ri = get_repo_info(repopath)
        ri.checkout('v7')
        modpath = f'test.local.foo'
        module = build_module_from_text(modtext, modpath, dependencies={
            'test.foo.bar': "WIP",
        })
        module.resolve()
        name = 'Foo'
        deduc = module[name]
        dg = deduc.buildDashgraph()
        print(json.dumps(dg, indent=4))
        no = dg["nodeOrder"]
        assert no == [
            "test.local.foo.Foo.A20",
            "test.local.foo.Foo.F"
        ]
        ch = dg["children"]
        assert ch[no[1]]["cloneOf"] == "test.foo.bar.results.Pf.F@WIP"
        assert ch[no[1]]["contra"] == [
            "test.foo.bar.results.Pf.S"
        ]


@pytest.mark.psm
def test_clone_03a(app):
    """
    Show that we can clone:
     - a subdeduc
     - a single node out of a subdeduc

    In particular, even if the subdeduc contains outgoing links (via `contra`
    or `versus`) to nodes we do not clone, we are still okay.
    """
    print()
    modtext = """
    from test.hist.lit.K.ummer.Cr040_08 import Pf

    deduc Foo {

        clone Pf.S40
        clone Pf.Cs2.S as S10

        asrt A20 {
            sy = "A20"
        }

        meson = "Suppose S10. Then A20."
    }
    """
    with app.app_context():
        modpath = f'test.local.foo'
        module = build_module_from_text(modtext, modpath, dependencies={
            'test.hist.lit': "WIP",
        })
        module.resolve()
        name = 'Foo'
        deduc = module[name]
        dg = deduc.buildDashgraph()
        print(json.dumps(dg, indent=4))

        ch = dg["children"]
        assert ch["test.local.foo.Foo.S10"]["cloneOf"] == "test.hist.lit.K.ummer.Cr040_08.Pf.Cs2.S@WIP"
        assert ch["test.local.foo.Foo.S10"]["alternates"] == [
            "test.hist.lit.K.ummer.Cr040_08.Pf.Cs1.S"
        ]


@pytest.mark.psm
def test_clone_03b(app):
    """
    This time we clone *both* of a pair of linked alternative supp nodes, and
    we show that our two clones wind up linked to each other.
    """
    print()
    modtext = """
    from test.hist.lit.K.ummer.Cr040_08 import Pf

    deduc Foo {

        clone Pf.Cs1.S as S05
        clone Pf.Cs2.S as S10

        asrt A20 {
            sy = "A20"
        }

        meson = "Suppose S05. Suppose S10. Then A20."
    }
    """
    with app.app_context():
        modpath = f'test.local.foo'
        module = build_module_from_text(modtext, modpath, dependencies={
            'test.hist.lit': "WIP",
        })
        module.resolve()
        name = 'Foo'
        deduc = module[name]
        dg = deduc.buildDashgraph()
        print(json.dumps(dg, indent=4))

        ch = dg["children"]
        assert ch["test.local.foo.Foo.S05"]["cloneOf"] == "test.hist.lit.K.ummer.Cr040_08.Pf.Cs1.S@WIP"
        assert ch["test.local.foo.Foo.S05"]["alternates"] == [
            "test.local.foo.Foo.S10"
        ]
        assert ch["test.local.foo.Foo.S10"]["cloneOf"] == "test.hist.lit.K.ummer.Cr040_08.Pf.Cs2.S@WIP"
        assert ch["test.local.foo.Foo.S10"]["alternates"] == [
            "test.local.foo.Foo.S05"
        ]


@pytest.mark.psm
def test_clone_04a(app):
    """
    Show that we can clone a node whose label includes a nodelink.
    If we do not also clone the node to which it links, then the nodelink
    continues to link to the original.
    """
    print()
    modtext = """
    from test.wid.get.notes import Pf1

    deduc Foo {

        # This node makes a nodelink to `x1.E10`.
        clone Pf1.A10

        asrt A20 {
            sy = "A20"
        }

        meson = "Have A10. So A20."
    }
    """
    with app.app_context():
        modpath = f'test.local.foo'
        module = build_module_from_text(modtext, modpath, dependencies={
            'test.wid.get': "v0.1.0",
        })
        module.resolve()
        name = 'Foo'
        deduc = module[name]
        dg = deduc.buildDashgraph()
        print(json.dumps(dg, indent=4))

        ch = dg["children"]
        A10_label = ch["test.local.foo.Foo.A10"]["labelHTML"]
        assert "nodelink" in A10_label
        assert "test.wid.get.notes.x1.E10" in A10_label


@pytest.mark.psm
def test_clone_04b(app):
    """
    Again we clone a node whose label includes a nodelink, but this time we
    do also clone the node to which it links. Now the nodelink should point to
    our clone of the original target.
    """
    print()
    modtext = """
    from test.wid.get.notes import Pf1, x1

    deduc Foo {

        # This node makes a nodelink to `x1.E10`.
        clone Pf1.A10
        clone x1.E10

        asrt A20 {
            sy = "A20"
        }

        meson = "Have A10. So A20."
    }
    """
    with app.app_context():
        modpath = f'test.local.foo'
        module = build_module_from_text(modtext, modpath, dependencies={
            'test.wid.get': "v0.1.0",
        })
        module.resolve()
        name = 'Foo'
        deduc = module[name]
        dg = deduc.buildDashgraph()
        print(json.dumps(dg, indent=4))

        ch = dg["children"]
        A10_label = ch["test.local.foo.Foo.A10"]["labelHTML"]
        assert "nodelink" in A10_label
        assert "test.local.foo.Foo.E10" in A10_label

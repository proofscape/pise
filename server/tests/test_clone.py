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
            build_module_from_text(modtext, modpath, dependencies={
                'test.hist.lit': "WIP",
            })
        assert ei.value.code() == PECode.CANNOT_CLONE_NODE


@pytest.mark.psm
def test_clone_01(app):
    """
    Basic test of node cloning. Show that we can make a clone, which gets a
    'cloneOf' property pointing to the original, and gets the 'labelHTML' from
    the original. Show that non-clones have 'cloneOf' equal to `None`.
    """
    print()
    modtext = """
    from test.hist.lit.K.ummer.Cr040_08 import Pf

    deduc Foo {

        clone Pf.A10

        asrt A20 {
            sy = "A20"
        }

        meson = "A10 so A20."
    }
    """
    with app.app_context():
        modpath = f'test.local.foo'
        module = build_module_from_text(modtext, modpath, dependencies={
            'test.hist.lit': "WIP",
        })
        name = 'Foo'
        deduc = module[name]
        dg = deduc.buildDashgraph()
        print(json.dumps(dg, indent=4))
        no = dg["nodeOrder"]
        assert no == [
            "test.local.foo.Foo.A10",
            "test.local.foo.Foo.A20"
        ]
        ch = dg["children"]
        assert ch[no[0]]["cloneOf"] == "test.hist.lit.K.ummer.Cr040_08.Pf.A10"
        assert ch[no[0]]["labelHTML"] == "%3Cp%3EThe%20class%20number%20of%20%24%5Cmathbb%7BQ%7D(%5Calpha)%24%3Cbr%3E%0Ais%20not%20divisible%20by%20%24%5Clambda%24.%3C%2Fp%3E%0A"
        assert ch[no[1]]["cloneOf"] is None


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
        clone Pf.F

        asrt A20 {
            sy = "A20"
        }

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
        assert ch[no[0]]["cloneOf"] == "test.foo.bar.results.Pf.S"
        assert ch[no[2]]["cloneOf"] == "test.foo.bar.results.Pf.F"
        assert ch[no[2]]["contra"] == [
            "test.local.foo.Foo.S"
        ]


@pytest.mark.psm
def test_clone_02b(app):
    """
    Show that we can clone just a `flse` node, and its `contra` will link it to
    a locally-defined node, provided the latter has the right name.
    (Also show that clones don't have to happen before local node defs.)
    """
    print()
    modtext = """
    from test.foo.bar.results import Pf

    deduc Foo {

        supp S {
            sy = "S"
        }

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
        assert ch[no[0]]["cloneOf"] is None
        assert ch[no[2]]["cloneOf"] == "test.foo.bar.results.Pf.F"
        assert ch[no[2]]["contra"] == [
            "test.local.foo.Foo.S"
        ]


@pytest.mark.psm
def test_clone_03(app):
    """
    Show that:
     - We can clone a subdeduc, as long as we provide targets for any
       outgoing links it may define (via `contra`, `versus`, etc.)
     - We can clone a single node out of a subdeduc.
    """
    print()
    modtext = """
    from test.hist.lit.K.ummer.Cr040_08 import Pf

    deduc Foo {

        clone Pf.S40
        clone Pf.Cs1
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
        name = 'Foo'
        deduc = module[name]
        dg = deduc.buildDashgraph()
        print(json.dumps(dg, indent=4))

        ch = dg["children"]
        assert ch["test.local.foo.Foo.S10"]["cloneOf"] == "test.hist.lit.K.ummer.Cr040_08.Pf.Cs2.S"
        assert ch["test.local.foo.Foo.S10"]["alternates"] == [
            "test.local.foo.Foo.Cs1.S"
        ]
        assert ch["test.local.foo.Foo.Cs1"]["children"]["test.local.foo.Foo.Cs1.S"]["cloneOf"] == "test.hist.lit.K.ummer.Cr040_08.Pf.Cs1.S"
        assert ch["test.local.foo.Foo.Cs1"]["children"]["test.local.foo.Foo.Cs1.S"]["alternates"] == [
            "test.local.foo.Foo.S10"
        ]


@pytest.mark.psm
def test_clone_04(app):
    """
    Show that we can clone a node whose label includes a nodelink, as long as
    we provide a local name to which the link target can resolve.
    """
    print()
    modtext = """
    from test.wid.get.notes import Pf1

    deduc x1 {
    
        exis E10 {
            intr I {
                sy = "I"
            }
            asrt A {
                sy = "A"
            }
        }
    
        meson = "E10"
    }

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
        name = 'Foo'
        deduc = module[name]
        dg = deduc.buildDashgraph()
        print(json.dumps(dg, indent=4))
        ch = dg["children"]
        assert "%3Cspan%20class%3D%22nodelink%22%3E" in ch["test.local.foo.Foo.A10"]["labelHTML"]

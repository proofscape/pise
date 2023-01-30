# --------------------------------------------------------------------------- #
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

import pytest

from pfsc.build.repo import checkout, get_repo_info
from pfsc.excep import PfscExcep, PECode
from pfsc.lang.meson import build_graph_from_meson, build_graph_from_arcs
from pfsc.lang.modules import load_module


success = [
    # (0)
    ("A, so B.", """\
A
B
A --> B
"""),
    # (1)
    ("A10. Therefore A20, by A30 and A40, by A50.", """\
A10
A20
A30
A40
A50
A30 --> A20
A40 --> A20
A50 --> A30
A50 --> A40
A10 --> A20
"""),
    # (2)
    ("A10, so A20, via M30.", """\
A10
A20
M30
A10 --> M30
M30 --> A20
"""),
    # (3)
    ("A10. But suppose S20 and S30 and S40. Then A50.", """\
A10
S20
S30
S40
A50
S20 --> A50
S30 --> A50
S40 --> A50
"""),
    # (4)
    ("A10. Now suppose S20 and S30 and S40. Then A50.", """\
A10
S20
S30
S40
A50
S20 ..> S30
S30 ..> S40
A10 ..> S20
S40 --> A50
"""),
    # (5)
    ("A10. Suppose S20 and S30 and S40. Then A50.", """\
A10
S20
S30
S40
A50
S20 ..> S30
S30 ..> S40
A10 ..> S20
S40 --> A50
"""),
    # (6)
    ("""
A10 by D20.
Meanwhile A30 by Pf.S.
Let I60.
Then E70 by D40 and D50.
But A80 using A30 and Pf.Cs1.S, so E90.
Let I100.
Then A110 using E70.A20, so A120.
Meanwhile A130 by I100.
Let I140. Then A150 so A160 by A120 and Thm.I1.
Therefore E170 by A110 and ZB127.
From E180 get A190 using E170.A5.
Meanwhile let I200.
Then A220 by A190 and E170.A35, applying M210.
So A230 using A190.
But E240 since A10 and E90.A20,
hence A250 using A230.
Therefore A270 by A260.
From A130 get A280, so A290 using A270.
Therefore A310 using A230, applying M300, hence A320.
Now D330.
But A340 by D330.A70,
hence Pf.Cs1.Cs1C.F since A320 and Pf.Cs1.Cs1C.S.
""", """\
A10
D20
A30
Pf.S
I60
E70
D40
D50
A80
Pf.Cs1.S
E90
I100
A110
E70.A20
A120
A130
I140
A150
A160
Thm.I1
E170
ZB127
E180
A190
E170.A5
I200
A220
E170.A35
M210
A230
E240
E90.A20
A250
A270
A260
A280
A290
A310
M300
A320
D330
A340
D330.A70
Pf.Cs1.Cs1C.F
Pf.Cs1.Cs1C.S
D20 --> A10
Pf.S --> A30
D40 --> E70
D50 --> E70
A30 --> A80
Pf.Cs1.S --> A80
E70.A20 --> A110
I100 --> A130
A120 --> A160
Thm.I1 --> A160
A110 --> E170
ZB127 --> E170
E170.A5 --> A190
A190 --> A230
A10 --> E240
E90.A20 --> E240
A230 --> A250
A260 --> A270
A270 --> A290
D330.A70 --> A340
A320 --> Pf.Cs1.Cs1C.F
Pf.Cs1.Cs1C.S --> Pf.Cs1.Cs1C.F
A30 ..> I60
I60 --> E70
A80 --> E90
E90 ..> I100
I100 --> A110
A110 --> A120
A130 ..> I140
I140 --> A150
A150 --> A160
A160 --> E170
E180 --> A190
I200 --> M210
A190 --> M210
E170.A35 --> M210
M210 --> A220
A220 --> A230
E240 --> A250
A250 --> A270
A130 --> A280
A280 --> A290
A290 --> M300
A230 --> M300
M300 --> A310
A310 --> A320
A320 ..> D330
A340 --> Pf.Cs1.Cs1C.F
"""),
    # (7)
    ("A --> B", """\
A
B
A --> B
"""),
    # (8)
    ("B <-- A", """\
B
A
A --> B
"""),
    # (9)
    ("From A10 get A20 by !2 and ?1.", """\
A10
A20
!2
?1
!2 --> A20
?1 --> A20
A10 --> A20
"""),
    # (10)
    ("Let I10. ..> Suppose S20.", """\
I10
S20
I10 ..> S20
"""),
    # (11)
    ("Thm.C by A10 and A20 and A30.", """\
Thm.C
A10
A20
A30
A10 --> Thm.C
A20 --> Thm.C
A30 --> Thm.C
"""),
    # (12)
    ("Let I. Then C.", """\
I
C
I --> C
"""),
]

@pytest.mark.parametrize(['meson_script', 'graph_repr'], success)
def test_meson_success(meson_script, graph_repr):
    g = build_graph_from_meson(meson_script)
    r = repr(g)
    print(r)
    assert r == graph_repr


error = [
    # After first concluding A30, we later suppose it.
    ("Suppose S10. Then A20. So A30 by S10. Suppose A30. Then A40.", PECode.MESON_EXCESS_MODAL)
]

@pytest.mark.parametrize(['meson_script', 'err_code'], error)
def test_meson_error(meson_script, err_code):
    with pytest.raises(PfscExcep) as ei:
        build_graph_from_meson(meson_script)
    assert ei.value.code() == err_code


arc_success = [
    # (0)
    ("A10 --> A20 --> A30 ..> I40 --> A50 <-- A30", """\
A10
A20
A30
I40
A50
A10 --> A20
A20 --> A30
A30 ..> I40
I40 --> A50
A30 --> A50
"""),
    # (1)
    ("""
    A10 --> A20 --> A30 ..> I40 --> A50 <-- A30
    A50 ..> S60 --> A70 --> A80 <-- Pf100.E70
    A80 --> A90 <-- A50
    """, """\
A10
A20
A30
I40
A50
S60
A70
A80
Pf100.E70
A90
A10 --> A20
A20 --> A30
A30 ..> I40
I40 --> A50
A30 --> A50
A50 ..> S60
S60 --> A70
A70 --> A80
Pf100.E70 --> A80
A80 --> A90
A50 --> A90
""")
]
@pytest.mark.parametrize('arc_listing, graph_repr', arc_success)
def test_arclang_success(arc_listing, graph_repr):
    g = build_graph_from_arcs(arc_listing)
    r = repr(g)
    print(r)
    assert r == graph_repr

meson_arcwords_graph = """\
A10
I20
A30
A40
A50
A50 --> A40
A10 ..> I20
I20 ..> A30
A30 --> A40
"""

@pytest.mark.psm
def test_meson_arcwords(app):
    """
    Try loading a module containing a deduc with a meson script that
    uses "arcwords" i.e. keywords `..>`, `-->`, and `<--`.
    Since all freestrings in modules are escaped by default, this tests
    that we are properly _un_escaping the meson string before attempting
    to parse, so that we recover angle brackets.
    """
    with app.app_context():
        mod = load_module('test.moo.deducs.d1')
        foo = mod['foo']
        g = str(foo.graph)
        print()
        print(g)
        assert g == meson_arcwords_graph

arclist_with_intr_graph = """\
A10
I20
A30
A40
A50
A10 ..> I20
I20 ..> A30
A30 --> A40
A50 --> A40
"""

@pytest.mark.psm
def test_bar(app):
    """
    Check that we can load a module containing a deduc that using an
    arc listing. In particular, we want to see that we are able to flow
    to an `intr` node without raising the exception that we are missing
    a modal keyword. That test must only apply to Meson scripts!
    """
    with app.app_context():
        mod = load_module('test.moo.deducs.d2')
        bar = mod['bar']
        g = str(bar.graph)
        print()
        print(g)
        assert g == arclist_with_intr_graph


Pf2_edges = [
    {
        "tail": "test.foo.bar.results.Pf2.Thm2.S",
        "head": "test.foo.bar.results.Pf2.B",
        "style": "ded",
        "bridge": True
    },
    {
        "tail": "test.foo.bar.results.Pf2.B",
        "head": "test.foo.bar.results.Pf2.M",
        "style": "ded",
        "bridge": False
    },
    {
        "tail": "test.foo.bar.results.Pf2.M",
        "head": "test.foo.bar.results.Pf2.C",
        "style": "ded",
        "bridge": False
    },
    {
        "tail": "test.foo.bar.results.Pf2.C",
        "head": "test.foo.bar.results.Pf2.Thm2.A",
        "style": "ded",
        "bridge": True
    }
]


@pytest.mark.psm
def test_issue_7(app):
    """
    See https://github.com/proofscape/pfsc-server/issues/7
    """
    with app.app_context():
        libpath = "test.foo.bar.results"
        version = "v16.0.0"
        ri = get_repo_info(libpath)
        with checkout(ri, version):
            mod = load_module(libpath)
            dg = mod['Pf2'].buildDashgraph()
            #import json
            #print(json.dumps(dg['edges'], indent=4))
            assert dg['edges'] == Pf2_edges


@pytest.mark.psm
def test_issue_14(app):
    """
    See https://github.com/proofscape/pise/issues/14
    """
    with app.app_context():
        libpath = "test.foo.bar.expansions"
        version = "v17.0.0"
        ri = get_repo_info(libpath)
        with checkout(ri, version):
            with pytest.raises(PfscExcep) as ei:
                load_module(libpath)
            assert ei.value.code() == PECode.MESON_BAD_GHOST_NODE


######################################################################
# Manual testing

def run_success_case(n):
    p = success[n]
    test_meson_success(p[0], p[1])

def run_error_case(n):
    p = error[n]
    test_meson_error(p[0], p[1])

def run_arc_success_case(n):
    p = arc_success[n]
    test_arclang_success(p[0], p[1])

if __name__ == "__main__":
    try:
        run_success_case(12)
        #run_error_case(0)
        #run_arc_success_case(1)
    except AssertionError:
        pass

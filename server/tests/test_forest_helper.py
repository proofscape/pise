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

from pfsc.handlers.forest import ForestUpdateHelper

r"""
When we put the alex, brook, and casey test repos in versions 3, 2, and 2, resp., then
we get a nice forest of deducs, all with distinct "names" (i.e. final libseg), looking like this:

    Thm1 <-- Pf <-- X1 <-- W1
              \        \_ W2
               \ 
                \__ X2 <-- W3
                       \_ W4
                       \_ W5

    Thm2 <-- Pf13
         \__Pf2 <-- X3 <-- W6
                       \_ W7
"""

DEDUCS = {
    "Thm1": ('test.alex.math.thm1.Thm1', 3),
    "Pf": ('test.alex.math.thm1.Pf', 3),
    "Thm2": ('test.alex.math.thm2.Thm2', 3),
    "Pf13": ('test.alex.math.thm2.Pf13', 3),
    "Pf2": ('test.alex.math.thm2.Pf2', 3),
    "X1": ('test.brook.math.exp1.X1', 2),
    "X2": ('test.brook.math.exp1.X2', 2),
    "X3": ('test.brook.math.exp1.X3', 2),
    "W1": ('test.casey.math.expand.W1', 2),
    "W2": ('test.casey.math.expand.W2', 2),
    "W3": ('test.casey.math.expand2.W3', 2),
    "W4": ('test.casey.math.expand2.W4', 2),
    "W5": ('test.casey.math.expand2.W5', 2),
    "W6": ('test.casey.math.expand2.W6', 2),
    "W7": ('test.casey.math.expand2.W7', 2),
}


def names2lps(name_string):
    """
    Turn a string of space-separated names into the list of the libpaths of
    the deducs of those names.
    """
    return [DEDUCS[name][0] for name in name_string.split()]

def prepare_info_for_fuh(info):
    dv = {
        "test.alex.math": "v3.0.0",
        "test.brook.math": "v2.0.0",
        "test.casey.math": "v2.0.0",
    }
    d = {}
    for k, v in info.items():
        if k == 'dv':
            c = dv.copy()
            if v == 2:
                c["test.alex.math"] = "v2.0.0"
            d['desired_versions'] = c
        elif k == 'current_forest':
            d[k] = prepare_current_forest(v)
        elif v == 'all':
            d[k] = v
        elif isinstance(v, str):
            d[k] = names2lps(v)
        else:
            d[k] = v
    return json.dumps(d)

def prepare_current_forest(forest_of_names):
    full_forest = {}
    for name_at_vers, f in forest_of_names.items():
        name, vers = name_at_vers.split("@")
        g = prepare_current_forest(f)
        lp = DEDUCS[name][0]
        full_forest[f'{lp}@v{vers}.0.0'] = g
    return full_forest

def prepare_expected(expected):
    prepared = {}
    keys = 'to_open to_close'.split()
    for k in keys:
        prepared[k] = names2lps(expected.get(k, ""))
    return prepared

def lp2name(lp):
    """
    Return the final segment (the "name") off the end of a libpath.
    """
    return lp.split('.')[-1]

def examine_fuh_response(r):
    if r['err_lvl'] > 0:
        print(json.dumps(r, indent=4))
        print(r['err_msg'])
    if 'to_open' in r:
        print("to_open", json.dumps(r['to_open'], indent=4))
    if 'to_close' in r:
        print("to_close", json.dumps(r['to_close'], indent=4))
    if 'dashgraphs' in r:
        print("dashgraphs' deducInfos:")
        for dg in r['dashgraphs'].values():
            print(json.dumps(dg['deducInfo'], indent=4))

@pytest.mark.parametrize("info, expected", (
    # Things to be viewed need to be opened if not yet present.
    ({
        'to_view': 'Thm1',
        'dv': 2,
    }, {
        'to_open': 'Thm1'
    }),
    # If we want a deduc we need its ancestors.
    ({
        'on_board': 'W7',
        'dv': 2,
     }, {
        'to_open': 'Thm2 Pf2 X3 W7'
    }),
    # (a) we ask to close only a minimal pruning set, and (b) asking that something
    # be absent which was never there anyway, has no effects
    ({
        #'current_deducs': 'Thm1 Pf X2 W3 W4 W5',
        'current_forest': {
            'Thm1@2': {
                'Pf@2': {
                    'X2@2': {
                        'W3@2': {},
                        'W4@2': {},
                        'W5@2': {},
                    },
                },
            },
        },
        'dv': 2,
        'off_board': 'X2 W3 W6'
     }, {
        'to_close': 'X2'
    }),
    # If we ask to reload a deduc, we will reopen any and all of its descendants that
    # were on board, except for any the user has explicitly asked to be off board.
    ({
        #'current_deducs': "Thm1 Pf X1 W1 W2",
        'current_forest': {
            'Thm1@2': {
                'Pf@2': {
                    'X1@2': {
                        'W1@2': {},
                        'W2@2': {},
                    },
                },
            },
        },
        'dv': 2,
        'reload': "Pf",
        'off_board': "W1"
     }, {
        'to_close': "Pf",
        'to_open': "Pf X1 W2"
    }),
    # Try reloading "all".
    ({
        #'current_deducs': "Thm1 Pf X1 W1 W2",
        'current_forest': {
            'Thm1@2': {
                'Pf@2': {
                    'X1@2': {
                        'W1@2': {},
                        'W2@2': {},
                    },
                },
            },
        },
        'dv': 2,
        'reload': 'all'
     }, {
        'to_close': 'Thm1',
        'to_open': "Thm1 Pf X1 W1 W2"
    }),
    # Try clearing the board with "all", while also asking for certain deducs to be on board.
    ({
        #'current_deducs': 'Thm1 Pf Thm2 Pf13 Pf2',
        'current_forest': {
            'Thm1@3': {
                'Pf@3': {},
            },
            'Thm2@3': {
                'Pf13@3': {},
                'Pf2@3': {},
            },
        },
        'dv': 3,
        'off_board': 'all',
        'on_board': 'Pf2'
     },{
        'to_close': 'Thm1 Pf13'
    }),
))
@pytest.mark.req_csrf(False)
def test_forest_update_helper(app, info, expected):
    info = prepare_info_for_fuh(info)
    expected = prepare_expected(expected)
    with app.app_context():
        fuh = ForestUpdateHelper({'info': info})
        fuh.process()
        r = fuh.generate_response()
        print()
        examine_fuh_response(r)
        # Assertions:
        # (1) There was no error.
        assert r['err_lvl'] == 0
        # (2) There are as many dashgraphs as there are deducs to be opened.
        assert len(r['dashgraphs']) == len(r['to_open'])
        # (3) We got the right set of deducs to close.
        assert set(r['to_close']) == set(expected['to_close'])
        # (4) We got the right (ordered) list of deducs to open.
        assert r['to_open'] == expected['to_open']

# In this example, the `desired_versions` arg alone is not enough to speak
# for everything in `to_view`. So we need to fall back on `current_forest`
# to supply versions where `desired_versions` is silent.
req_01 = """
{
    "current_forest": {
        "test.moo.bar.results.Thm@v2.0.0": {}
    },
    "desired_versions": {
        "test.moo.bar.results.Pf": "v2.0.0"
    },
    "on_board": null,
    "off_board": null,
    "reload": null,
    "to_view": [
        "test.moo.bar.results.Thm.C",
        "test.moo.bar.results.Pf"
    ],
    "incl_nbhd_in_view": false,
    "known_dashgraphs": {}
}
"""
@pytest.mark.psm
@pytest.mark.req_csrf(False)
def test_fallback_on_current_versions(app, repos_ready):
    with app.app_context():
        fuh = ForestUpdateHelper({'info': req_01})
        fuh.process()
        r = fuh.generate_response()
        print()
        print(json.dumps(json.loads(req_01), indent=4))
        if r['err_lvl'] > 0:
            print(json.dumps(r, indent=4))
        assert r['err_lvl'] == 0
        assert len(r["to_open"]) == 1

req_02 = """
{
    "current_forest": {
        "test.moo.bar.results.Thm@v2.0.0": {
            "test.moo.bar.results.Pf@v2.0.0": {}
        }
    },
    "desired_versions": {
        "test.moo.bar": "v1.0.0"
    },
    "on_board": null,
    "off_board": null,
    "reload": null,
    "to_view": "test.moo.bar.results.Pf.T",
    "incl_nbhd_in_view": false,
    "known_dashgraphs": {}
}
"""
@pytest.mark.psm
@pytest.mark.req_csrf(False)
def test_fuh_02(app, repos_ready):
    with app.app_context():
        fuh = ForestUpdateHelper({'info': req_02})
        fuh.process()
        r = fuh.generate_response()
        print()
        print(json.dumps(json.loads(req_02), indent=4))
        print("\nResponse:")
        examine_fuh_response(r)
        assert r['to_close'] == ["test.moo.bar.results.Thm"]
        assert r['to_open'] == [
            "test.moo.bar.results.Thm",
            "test.moo.bar.results.Pf"
        ]

req_03 = """
{
    "current_forest": {
        "test.wid.get.notes.Prop1@WIP": {
            "test.wid.get.notes.Pf1@WIP": {}
        }
    },
    "desired_versions": {
        "test.wid.get.notes.x1.SD20": "WIP"
    },
    "on_board": null,
    "off_board": null,
    "reload": null,
    "to_view": [
        "test.wid.get.notes.x1.SD20"
    ],
    "incl_nbhd_in_view": false,
    "known_dashgraphs": {}
}
"""
@pytest.mark.psm
@pytest.mark.req_csrf(False)
def test_fuh_03(app, repos_ready):
    """
    Test the case where we are only interested in a node, and
    do not state any version info for any ancestor of it.
    This case requires the use of _reverse_ prefix matching, so that
    the desired version of the deduc to which this node belongs can
    be inferred from the desired version of the node.
    """
    with app.app_context():
        fuh = ForestUpdateHelper({'info': req_03})
        fuh.process()
        r = fuh.generate_response()
        print()
        print(json.dumps(json.loads(req_03), indent=4))
        print("\nResponse:")
        examine_fuh_response(r)
        assert r['dashgraphs']['test.wid.get.notes.x1']['deducInfo']['version'] == "WIP"

req_04 = """
{
    "current_forest": {
        "test.hist.lit.H.ilbert.ZB.Thm168.Thm@v0.0.0": {
            "test.hist.lit.H.ilbert.ZB.Thm168.Pf@v0.0.0": {}
        }
    },
    "desired_versions": {
        "test.hist.lit": "v0.0.0"
    },
    "on_board": null,
    "off_board": null,
    "reload": null,
    "to_view": [
        "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A",
        "test.hist.lit.H.ilbert.ZB.Thm168.Pf1B"
    ],
    "incl_nbhd_in_view": false,
    "known_dashgraphs": {}
}
"""

@pytest.mark.psm
@pytest.mark.req_csrf(False)
def test_fuh_04(app, repos_ready):
    """
    Makes a good check on ForestUpdateHelper.step_040_ancestors(), since,
    in order for that method to work right, the node for Pf must get added
    to the `opening_forest`, while the nodes for both Pf1A and Pf1B get added
    to that for Pf. (Full disclosure: this case arose from a bug where we
    were adding Pf1A to Pf, then adding Pf1B to a brand new node for Pf!
    This led to a KeyError triggered by the `L[vlp]` right at the end of
    the `step_050_open_and_close()` method.)
    """
    print()
    print(json.dumps(json.loads(req_04), indent=4))
    with app.app_context():
        fuh = ForestUpdateHelper({'info': req_04})
        fuh.process()
        r = fuh.generate_response()
        print("\nResponse:")
        examine_fuh_response(r)
        assert set(r['to_open']) == {
            "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A",
            "test.hist.lit.H.ilbert.ZB.Thm168.Pf1B"
        }

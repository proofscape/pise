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

import json
import pytest

from tests import parse_served_state_from_app_load_response
from pfsc.handlers.app import AppLoader, StateArgMaker, AugLpSeq

args_0 = {
    'th': 'd',
    'z': '120',
    'sd': 'c310',
    'sp': 'V40H',
    'c': 'test(comment.notes@W.H.ilbert.ZB.Thm168.notes.Walkthrough~a(g0t0)s(g1t0L100)b*hist.lit@1_2_3.H.ilbert.ZB(Thm168.Pf~c(g2t0)b*Thm9.Pf~c(0)b))',
    'a': '0,0,0;2',
    'wl': '0,0-CHART.-2,0'
}
state_0 = """\
{
    "autoSaveDelay": 30000,
    "reloadFromDisk": "auto",
    "saveAllOnAppBlur": true,
    "enablePdfProxy": false,
    "offerPdfLibrary": false,
    "allowWIP": true,
    "appUrlPrefix": "",
    "devMode": false,
    "personalServerMode": false,
    "ssnrAvailable": false,
    "hostingByRequest": true,
    "tosURL": null,
    "tosVersion": null,
    "prpoURL": null,
    "prpoVersion": null,
    "loginsPossible": true,
    "err_lvl": 0,
    "theme": "dark",
    "zoom": 120,
    "sidebar": {
        "isVisible": false,
        "width": 310
    },
    "content": {
        "tctStructure": [
            "V",
            "H",
            "L",
            "L",
            "L"
        ],
        "tctSizeFractions": [
            0.4,
            0.5
        ],
        "activeTcIndex": 2,
        "tcs": [
            {
                "tabs": [
                    {
                        "type": "NOTES",
                        "libpath": "test.comment.notes.H.ilbert.ZB.Thm168.notes.Walkthrough",
                        "version": "WIP",
                        "modpath": "test.comment.notes.H.ilbert.ZB.Thm168.notes"
                    }
                ],
                "activeTab": 0
            },
            {
                "tabs": [
                    {
                        "type": "SOURCE",
                        "libpath": "test.comment.notes.H.ilbert.ZB.Thm168.notes.Walkthrough",
                        "version": "WIP",
                        "modpath": "test.comment.notes.H.ilbert.ZB.Thm168.notes",
                        "sourceRow": 100
                    }
                ],
                "activeTab": 0
            },
            {
                "tabs": [
                    {
                        "type": "CHART",
                        "on_board": [
                            "test.hist.lit.H.ilbert.ZB.Thm168.Pf",
                            "test.hist.lit.H.ilbert.ZB.Thm9.Pf"
                        ],
                        "versions": {
                            "test.hist.lit.H.ilbert.ZB.Thm168.Pf": "v1.2.3",
                            "test.hist.lit.H.ilbert.ZB.Thm9.Pf": "v1.2.3"
                        },
                        "gid": "0"
                    }
                ],
                "activeTab": 0
            }
        ],
        "widgetPanes": {
            "test.comment.notes@WIP.H.ilbert.ZB.Thm168.notes.Walkthrough:CHART:": "2:0"
        }
    },
    "trees": {
        "trees": {
            "test.comment.notes@WIP": {
                "expand": {
                    "buildNodeIds": [
                        "test.comment.notes.H.ilbert.ZB.Thm168.notes.Walkthrough"
                    ]
                }
            },
            "test.hist.lit@v1.2.3": {
                "expand": {
                    "buildNodeIds": [
                        "test.hist.lit.H.ilbert.ZB.Thm168.Pf",
                        "test.hist.lit.H.ilbert.ZB.Thm9.Pf"
                    ]
                }
            }
        }
    }
}"""
gen_args_0 = {
    "sd": "c310",
    "sp": "V40H",
    "a": "0,0,0;2",
    'c': 'test(comment.notes@W.H.ilbert.ZB.Thm168.notes.Walkthrough~a(g0t0)s(g1t0L100)b*hist.lit@1_2_3.H.ilbert.ZB(Thm168.Pf~c(g2t0)b*Thm9.Pf~c(0)b))',
    "wl": "0,0-CHART.-2,0"
}

args_1 = {
    'c': 'test.hist.lit@3_1_4.H.ilbert.ZB.Thm8.Thm~c(g0t0x-32y99z1.3L1v3o5)'
}
state_1 = """\
{
    "autoSaveDelay": 30000,
    "reloadFromDisk": "auto",
    "saveAllOnAppBlur": true,
    "enablePdfProxy": false,
    "offerPdfLibrary": false,
    "allowWIP": true,
    "appUrlPrefix": "",
    "devMode": false,
    "personalServerMode": false,
    "ssnrAvailable": false,
    "hostingByRequest": true,
    "tosURL": null,
    "tosVersion": null,
    "prpoURL": null,
    "prpoVersion": null,
    "loginsPossible": true,
    "err_lvl": 0,
    "content": {
        "tctStructure": [
            "L"
        ],
        "tctSizeFractions": [],
        "activeTcIndex": 0,
        "tcs": [
            {
                "tabs": [
                    {
                        "type": "CHART",
                        "on_board": [
                            "test.hist.lit.H.ilbert.ZB.Thm8.Thm"
                        ],
                        "versions": {
                            "test.hist.lit.H.ilbert.ZB.Thm8.Thm": "v3.1.4"
                        },
                        "coords": [
                            -32,
                            99,
                            1.3
                        ],
                        "ordSel": 5,
                        "gid": "0",
                        "layout": "OrderedList1",
                        "forest": {
                            "overview": {
                                "position": "tl"
                            }
                        }
                    }
                ],
                "activeTab": 0
            }
        ]
    }
}"""
gen_args_1 = {
    "a": "0;0",
    "c": "test.hist.lit@3_1_4.H.ilbert.ZB.Thm8.Thm~c(g0t0x-32y99z1.3L1o5)"
}

state_2 = """\
{
    "autoSaveDelay": 30000,
    "reloadFromDisk": "auto",
    "saveAllOnAppBlur": true,
    "enablePdfProxy": false,
    "offerPdfLibrary": false,
    "allowWIP": true,
    "appUrlPrefix": "",
    "devMode": false,
    "personalServerMode": false,
    "ssnrAvailable": false,
    "hostingByRequest": true,
    "tosURL": null,
    "tosVersion": null,
    "prpoURL": null,
    "prpoVersion": null,
    "loginsPossible": true,
    "err_lvl": 0,
    "content": {
        "tctStructure": [
            "L"
        ],
        "tctSizeFractions": [],
        "activeTcIndex": 0,
        "tcs": [
            {
                "tabs": [
                    {
                        "type": "CHART",
                        "on_board": [
                            "test.hist.lit.H.ilbert.ZB.Thm9.Pf"
                        ],
                        "versions": {
                            "test.hist.lit.H.ilbert.ZB.Thm9.Pf": "v3.1.4"
                        },
                        "gid": "0"
                    }
                ],
                "activeTab": 0
            }
        ]
    },
    "trees": {
        "trees": {
            "test.hist.lit@v3.1.4": {
                "expand": {
                    "buildNodeIds": [
                        "test.hist.lit.H.ilbert.ZB"
                    ]
                }
            }
        }
    }
}"""
gen_args_2 = {
    "a": "0;0",
    "c": "test.hist.lit@3_1_4.H.ilbert.ZB~b.Thm9.Pf~c(g0t0)"
}


state_3 = """\
{
    "autoSaveDelay": 30000,
    "reloadFromDisk": "auto",
    "saveAllOnAppBlur": true,
    "enablePdfProxy": false,
    "offerPdfLibrary": false,
    "allowWIP": true,
    "appUrlPrefix": "",
    "devMode": false,
    "personalServerMode": false,
    "ssnrAvailable": false,
    "hostingByRequest": true,
    "tosURL": null,
    "tosVersion": null,
    "prpoURL": null,
    "prpoVersion": null,
    "loginsPossible": true,
    "err_lvl": 0,
    "content": {
        "tctStructure": [
            "L"
        ],
        "tctSizeFractions": [],
        "activeTcIndex": 0,
        "tcs": [
            {
                "tabs": [
                    {
                        "type": "CHART",
                        "on_board": [
                            "test.hist.lit.H.ilbert.ZB.Thm9.Pf"
                        ],
                        "versions": {
                            "test.hist.lit.H.ilbert.ZB.Thm9.Pf": "v3.1.4"
                        },
                        "gid": "16591218247960.7542378166739916"
                    }
                ],
                "activeTab": 0
            },
            {
                "tabs": [
                    {
                        "type": "CHART",
                        "on_board": [
                            "test.hist.lit.H.ilbert.ZB.Thm9.Pf"
                        ],
                        "versions": {
                            "test.hist.lit.H.ilbert.ZB.Thm9.Pf": "v3.1.4"
                        },
                        "gid": "16591218360040.8058427115456224"
                    },
                    {
                        "type": "CHART",
                        "on_board": [
                            "test.hist.lit.H.ilbert.ZB.Thm9.Pf"
                        ],
                        "versions": {
                            "test.hist.lit.H.ilbert.ZB.Thm9.Pf": "v3.1.4"
                        },
                        "gid": "16591218360040.8058427115456224"
                    }
                ],
                "activeTab": 0
            }
        ]
    },
    "trees": {
        "trees": {
            "test.hist.lit@v3.1.4": {
                "expand": {
                    "buildNodeIds": [
                        "test.hist.lit.H.ilbert.ZB"
                    ]
                }
            }
        }
    }
}"""
gen_args_3 = {
    "a": "0,0;0",
    "c": "test.hist.lit@3_1_4.H.ilbert.ZB~b.Thm9.Pf~c(g0t0*g1t0G1*g1t1G1)"
}

# This one is the same as state_2, except that the version is WIP.
# This is for testing that the default version will be provided if omitted in
# the original URL args. Note that in the generated version of the args, the
# `@W` version has been added for us.
args_4 = {
    "a": "0;0",
    "c": "test.hist.lit.H.ilbert.ZB~b.Thm9.Pf~c(g0t0)"
}
gen_args_4 = {
    "a": "0;0",
    "c": "test.hist.lit@W.H.ilbert.ZB~b.Thm9.Pf~c(g0t0)"
}
state_4 = """\
{
    "autoSaveDelay": 30000,
    "reloadFromDisk": "auto",
    "saveAllOnAppBlur": true,
    "enablePdfProxy": false,
    "offerPdfLibrary": false,
    "allowWIP": true,
    "appUrlPrefix": "",
    "devMode": false,
    "personalServerMode": false,
    "ssnrAvailable": false,
    "hostingByRequest": true,
    "tosURL": null,
    "tosVersion": null,
    "prpoURL": null,
    "prpoVersion": null,
    "loginsPossible": true,
    "err_lvl": 0,
    "content": {
        "tctStructure": [
            "L"
        ],
        "tctSizeFractions": [],
        "activeTcIndex": 0,
        "tcs": [
            {
                "tabs": [
                    {
                        "type": "CHART",
                        "on_board": [
                            "test.hist.lit.H.ilbert.ZB.Thm9.Pf"
                        ],
                        "versions": {
                            "test.hist.lit.H.ilbert.ZB.Thm9.Pf": "WIP"
                        },
                        "gid": "0"
                    }
                ],
                "activeTab": 0
            }
        ]
    },
    "trees": {
        "trees": {
            "test.hist.lit@WIP": {
                "expand": {
                    "buildNodeIds": [
                        "test.hist.lit.H.ilbert.ZB"
                    ]
                }
            }
        }
    }
}"""


def normalize_gids(state):
    gids = []
    for tc in state["content"]["tcs"]:
        for tab in tc["tabs"]:
            if "gid" in tab:
                gid = tab["gid"]
                if isinstance(gid, str):
                    p = gid.split('-')
                    if len(p) == 6:
                        # In this case we have the kind of gid generated by the
                        # server, which is an index, a hyphen, and a uuid4.
                        tab["gid"] = p[0]
                    else:
                        # In this case it is the kind of gid generated by the
                        # client.
                        if gid in gids:
                            tab["gid"] = str(gids.index(gid))
                        else:
                            tab["gid"] = str(len(gids))
                            gids.append(gid)


def normalize_served_state(state):
    del state['pdfjsURL']
    normalize_gids(state)


@pytest.mark.parametrize(['args', 'expected'], (
    (args_0, state_0),
    (args_1, state_1),
    (gen_args_2, state_2),
    (gen_args_3, state_3),
    (args_4, state_4),
))
def test_app_loader(app, args, expected):
    with app.app_context():
        with app.test_request_context():
            print()
            al = AppLoader(args)
            al.process()
            state = al.ISE_state

            assert "CSRF" in state
            del state["CSRF"]

            normalize_served_state(state)

            computed = json.dumps(state, indent=4)
            print(computed)

            expected = json.loads(expected)
            normalize_gids(expected)
            expected = json.dumps(expected, indent=4)

            assert computed == expected

def test_app_loader_2(app):
    print()
    with app.app_context():
        c = app.test_client()
        response = c.get('/?sp=V&c=test.hist.lit.H.ilbert.ZB.Thm8.Thm~c(g1t0)ps(g0t0)')
        #print(response.data)
        assert 'ISE split code V is malformed.' not in str(response.data)

@pytest.mark.parametrize(['state', 'expected'], (
    (state_0, gen_args_0),
    (state_1, gen_args_1),
    (state_2, gen_args_2),
    (state_3, gen_args_3),
    (state_4, gen_args_4),
))
def test_arg_maker(app, state, expected):
    print()
    with app.app_context():
        app.config["REQUIRE_CSRF_TOKEN"] = False
        sam = StateArgMaker({'state': state})
        sam.process()
        resp = sam.generate_response()
        if resp['err_lvl'] > 0:
            print(resp['err_msg'])
        else:
            args = json.loads(resp['args'])
            print(json.dumps(args, indent=4))
            assert args == expected

trees_1 = {
    "test.moo.comment@WIP": {
        "expand": {
            "fsNodeIds": [
                "."
            ],
            "buildNodeIds": [
                "test.moo.comment.bar"
            ]
        }
    },
    "test.wid.get@WIP": {
        "expand": {
            "fsNodeIds": [],
            "buildNodeIds": [
                "test.wid.get"
            ]
        }
    },
    "test.moo.links@v0.1.0": {
        "expand": {
            "buildNodeIds": []
        }
    },
    "test.moo.study@v1.0.0": {
        "expand": {
            "buildNodeIds": [
                "test.moo.study.results"
            ]
        }
    }
}

buildpaths_1 = {
    'test.wid.get@WIP',
    'test.moo.comment@WIP.bar',
    'test.moo.study@v1_0_0.results'
}

fspaths_1 = {'test.moo.comment@WIP'}

def test_arg_maker_2():
    print()
    #trees = json.loads(trees_1)
    #print(json.dumps(trees, indent=4))
    B, F = StateArgMaker.trees_to_rvlps(trees_1)
    print(B)
    print(F)
    assert B == buildpaths_1
    assert F == fspaths_1

def test_make_tree_info():
    print()
    a = AugLpSeq(None, None)
    a.fstree_paths = list(fspaths_1)
    a.buildtree_paths = list(buildpaths_1)
    info = a.get_tree_info()
    print(json.dumps(info, indent=4))

def test_demo_req(app, client):
    app.config["PROVIDE_DEMO_REPOS"] = True
    resp = client.get('/', query={
        'sp': "V",
        'c': 'demo._.workbook@W.foo~s(g0t0L1)a(g1t0)b',
    })
    #print(resp.data.decode())
    d = parse_served_state_from_app_load_response(resp)
    #print(json.dumps(d, indent=4))
    lp = d["content"]["tcs"][0]["tabs"][0]["libpath"]
    print()
    print(lp)
    parts = lp.split('.')
    demo_username = parts[1]
    assert len(demo_username) == 7

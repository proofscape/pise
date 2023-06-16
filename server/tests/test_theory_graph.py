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

from pfsc.gdb import get_graph_reader
from pfsc.lang.modules import build_module_from_text

@pytest.mark.psm
def test_lower_graph(app):
    print()
    deducpath = 'test.hist.lit.H.ilbert.ZB.Thm119.Thm'
    with app.app_context():
        graph = get_graph_reader().get_lower_theory_graph(deducpath, "WIP")
        name = '_map'
        modtext = graph.write_modtext(name)
        print(modtext)
        type_ = 'lower'
        modpath = f'special.theorymap.{type_}.{deducpath}'
        module = build_module_from_text(modtext, modpath, dependencies={
            'test.hist.lit': "WIP",
        })
        module.resolve()
        theorymap = module[name]
        dg = theorymap.buildDashgraph()
        print(json.dumps(dg, indent=4))
        assert {v["ghostOf"].split('.')[-2] for v in dg["children"].values()} == {
            "Thm119", "Thm24", "Thm31", "Thm118", "Thm26", "Pg180L1"
        }

@pytest.mark.psm
def test_upper_graph(app):
    print()
    deducpath = 'test.hist.lit.H.ilbert.ZB.Thm8.Thm'
    with app.app_context():
        graph = get_graph_reader().get_upper_theory_graph(deducpath, "WIP")
        name = '_map'
        modtext = graph.write_modtext(name)
        print(modtext)
        type_ = 'upper'
        modpath = f'special.theorymap.{type_}.{deducpath}'
        module = build_module_from_text(modtext, modpath, dependencies={
            'test.hist.lit': "WIP",
        })
        module.resolve()
        theorymap = module[name]
        dg = theorymap.buildDashgraph()
        print(json.dumps(dg, indent=4))
        assert {v["ghostOf"].split('.')[-2] for v in dg["children"].values()} == {
            "Thm8", "Thm9"
        }

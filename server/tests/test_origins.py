# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2024 Proofscape Contributors                           #
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

from pfsc.build.products import load_dashgraph, load_annotation


def test_origins_1(app, repos_ready):
    with app.app_context():
        j = load_dashgraph('test.moo.bar.results.Pf', version='v2.0.0')
        dg = json.loads(j)
        origin = dg["children"]["test.moo.bar.results.Pf.U"]["origin"]
        assert origin == "test.moo.bar.results.Pf.T@1"

def test_origins_2(app, repos_ready):
    with app.app_context():
        html, j = load_annotation('test.moo.study.expansions.Notes3', version='v1.0.0')
        data = json.loads(j)
        origin = data["widgets"]["test-moo-study-expansions-Notes3-w1_v1-0-0"]["origin"]
        assert origin == "test.moo.study.expansions.Notes3.w2@1"

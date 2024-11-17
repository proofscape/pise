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

import os
import json

import pytest

from tests import handleAsJson
from pfsc.constants import ISE_PREFIX, IndexType


cf_out_key = "cf_out"
children_key = "children"
enrichment_key = "enrichment"


def test_cf_out(client, repos_ready):
    libpath = 'test.hist.lit.H.ilbert.ZB.Thm168.Pf'
    vers = 'v0.0.0'
    resp = client.get(f'{ISE_PREFIX}/loadDashgraph?libpath={libpath}&vers={vers}')
    d = handleAsJson(resp)
    #print(json.dumps(d, indent=4))

    dg = d["dashgraph"]
    assert dg[cf_out_key] == [
        {
            "libpath": "test.hist.lit.K.ummer.Cr040_08.Pf",
            "version": "v0.0.0"
        }
    ]

    dg = dg[children_key][f'{libpath}.Cs1']
    assert dg[cf_out_key] == [
        {
            "libpath": "test.hist.lit.K.ummer.Cr040_08.Pf.Cs1",
            "version": "v0.0.0"
        }
    ]

    dg = dg[children_key][f'{libpath}.Cs1.S']
    assert dg[cf_out_key] == [
        {
            "libpath": "test.hist.lit.K.ummer.Cr040_08.Pf.Cs1.S",
            "version": "v0.0.0"
        }
    ]


# See `tests.util.gather_repo_info()` function, on the reason for the conditional skip here.
@pytest.mark.skipif(bool(int(os.getenv("DUPLICATE_TEST_HIST_LIT", 0))), reason="fails when test.hist.lit has a v1")
def test_cf_in(client, repos_ready):
    libpath = 'test.hist.lit.K.ummer.Cr040_08.Pf'
    vers = 'v0.0.0'
    resp = client.get(f'{ISE_PREFIX}/loadDashgraph?libpath={libpath}&vers={vers}')
    d = handleAsJson(resp)
    print(json.dumps(d, indent=4))

    dg = d["dashgraph"]
    e = dg[enrichment_key]
    cf = e[IndexType.CF][0]
    assert cf["libpath"] == "test.hist.lit.H.ilbert.ZB.Thm168.Pf"
    assert cf["versions"][-1] == "v0.0.0"

    dg = dg[children_key][f'{libpath}.Cs1']
    e = dg[enrichment_key]
    cf = e[IndexType.CF][0]
    assert cf["libpath"] == "test.hist.lit.H.ilbert.ZB.Thm168.Pf.Cs1"
    assert cf["versions"][-1] == "v0.0.0"

    dg = dg[children_key][f'{libpath}.Cs1.S']
    e = dg[enrichment_key]
    cf = e[IndexType.CF][0]
    assert cf["libpath"] == "test.hist.lit.H.ilbert.ZB.Thm168.Pf.Cs1.S"
    assert cf["versions"][-1] == "v0.0.0"

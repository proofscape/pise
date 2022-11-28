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

from pfsc.build.repo import get_repo_info
from pfsc.lang.modules import load_module
from pfsc.excep import PfscExcep, PECode

@pytest.mark.parametrize("mod, expected_code", [
    ["X0", PECode.MISSING_INPUT],
    ["X1", PECode.MALFORMED_PDF_FINGERPRINT],
    ["X2", PECode.BAD_URL],
    ["Y1", PECode.MALFORMED_COMBINER_CODE],
    ["Y2", PECode.PDF_COMBINER_CODE_UKNOWN_VERS],
    ["Y3", PECode.MALFORMED_COMBINER_CODE],
    ["Y4", PECode.MALFORMED_PDF_REF_CODE],
])
@pytest.mark.psm
def test_pdf_ref_validate_1(app, mod, expected_code):
    with app.app_context():
        ri = get_repo_info('test.foo.pdf')
        ri.checkout('v0')
        print()
        with pytest.raises(PfscExcep) as ei:
            load_module(f'test.foo.pdf.{mod}')
        pe = ei.value
        code = pe.code()
        print(pe, code)
        assert code == expected_code

@pytest.mark.psm
def test_pdf_ref_validate_2(app):
    with app.app_context():
        ri = get_repo_info('test.foo.pdf')
        ri.checkout('v0')
        mod = load_module('test.foo.pdf.Z1')
        print()
        dg = mod['Z1'].buildDashgraph()
        pdf_info = dg['deducInfo']['pdf']['pdf3']
        #import json
        #print(json.dumps(dg['deducInfo']['pdf'], indent=4))
        assert pdf_info['url'] == "https://example.org/pdf/foo.pdf"
        assert pdf_info['fingerprint'] == 'abcdef0123456789'

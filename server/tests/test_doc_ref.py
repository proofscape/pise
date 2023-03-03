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
    ["X0", PECode.MISSING_DOC_INFO],
    ["X1", PECode.MALFORMED_DOC_ID],
    ["X2", PECode.BAD_URL],
    ["Y1", PECode.MALFORMED_COMBINER_CODE],
    ["Y2", PECode.DOC_COMBINER_CODE_UKNOWN_VERS],
    ["Y3", PECode.MALFORMED_COMBINER_CODE],
    ["Y4", PECode.MALFORMED_DOC_REF_CODE],
])
@pytest.mark.psm
def test_doc_ref_validate_1(app, mod, expected_code):
    with app.app_context():
        ri = get_repo_info('test.foo.doc')
        ri.checkout('v0')
        print()
        with pytest.raises(PfscExcep) as ei:
            load_module(f'test.foo.doc.{mod}')
        pe = ei.value
        code = pe.code()
        print(pe, code)
        assert code == expected_code

Z1_docInfo = {
    "docs": {
        "pdffp:abcdef0123456789": {
            "url": "https://example.org/pdf/foo.pdf",
            "docId": "pdffp:abcdef0123456789"
        }
    },
    "refs": {
        "pdffp:abcdef0123456789": [
            {
                "ccode": "v2;s3;(146:1758:2666:814:390:279:45);n;x+35;y+4;(146:1758:2666:1095:386:205:49)",
                "siid": "test.foo.doc.Z1.Z1.A1",
                "slp": "test.foo.doc.Z1.Z1",
                "stype": "CHART"
            }
        ]
    }
}

@pytest.mark.psm
def test_doc_ref_assemble_1(app):
    with app.app_context():
        ri = get_repo_info('test.foo.doc')
        ri.checkout('v0')
        mod = load_module('test.foo.doc.Z1')
        print()
        dg = mod['Z1'].buildDashgraph()
        doc_info = dg['deducInfo']['docInfo']
        #import json
        #print(json.dumps(doc_info, indent=4))
        assert doc_info == Z1_docInfo


Pf_docInfo = {
    "docs": {
        "pdffp:fedcba9876543210": {
            "url": "https://example.org/pdf/foo1.pdf",
            "docId": "pdffp:fedcba9876543210"
        },
        "pdffp:0123456789abcdef": {
            "url": "https://example.org/pdf/foo2.pdf",
            "docId": "pdffp:0123456789abcdef"
        }
    },
    "refs": {
        "pdffp:fedcba9876543210": [
            {
                "ccode": "v2;s3;(1:1758:2666:400:200:100:50);n;x+35;y+4;(1:1758:2666:400:250:110:49)",
                "siid": "test.foo.doc.results.Pf.R",
                "slp": "test.foo.doc.results.Pf",
                "stype": "CHART"
            }
        ],
        "pdffp:0123456789abcdef": [
            {
                "ccode": "v2;s3;(146:1758:2666:210:450:90:46);",
                "siid": "test.foo.doc.results.Pf.S",
                "slp": "test.foo.doc.results.Pf",
                "stype": "CHART"
            }
        ]
    }
}


@pytest.mark.psm
def test_doc_ref_assemble_2(app):
    with app.app_context():
        ri = get_repo_info('test.foo.doc')
        ri.checkout('v1')
        mod = load_module('test.foo.doc.results')
        print()
        dg = mod['Pf'].buildDashgraph()
        doc_info = dg['deducInfo']['docInfo']
        #import json
        #print(json.dumps(doc_info, indent=4))
        assert doc_info == Pf_docInfo


@pytest.mark.psm
def test_doc_ref_formats_1(app):
    """
    Test that doc refs can be made in various formats, both on nodes,
    and in pdf widgets.
    """
    with app.app_context():
        ri = get_repo_info('test.foo.doc')
        ri.checkout('v2')
        mod = load_module('test.foo.doc.results')
        print()
        dg = mod['Pf'].buildDashgraph()
        pf_doc_info = dg['deducInfo']['docInfo']
        anno = mod['Discussion'].get_anno_data()

        verbose = False
        if verbose:
            import json
            print(json.dumps(pf_doc_info, indent=4))
            print('=' * 80)
            print(json.dumps(anno, indent=4))

        assert len(pf_doc_info['docs']) == 2 == len(pf_doc_info['refs'])
        assert pf_doc_info['refs']['pdffp:fedcba9876543210'][0]['siid'][-1] == 'R'
        assert pf_doc_info['refs']['pdffp:0123456789abcdef'][0]['siid'][-1] == 'S'

        widgets = anno['widgets']
        wk = list(widgets.keys())
        assert len(wk) == 4
        assert 'selection' not in widgets[wk[0]]
        assert all('selection' in widgets[wk[i]] for i in [1, 2, 3])
        assert all(widgets[wk[i]]['docId'] == 'pdffp:fedcba9876543210' for i in range(4))
        anno_doc_info = anno['docInfo']
        assert len(anno_doc_info['docs']) == 1
        assert len(anno_doc_info['refs']) == 1
        assert len(anno_doc_info['refs']['pdffp:fedcba9876543210']) == 3
        assert all(
            hld['ccode'] == 'v2;s3;(1:1758:2666:400:200:100:50);n;x+35;y+4;(1:1758:2666:400:250:110:49)'
            for hld in anno_doc_info['refs']['pdffp:fedcba9876543210']
        )

        # Getting widget uids for siids for pdf widgets:
        assert anno_doc_info['refs']['pdffp:fedcba9876543210'][0]["siid"] == "test-foo-doc-results-Discussion-w2_WIP"

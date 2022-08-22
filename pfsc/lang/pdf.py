# --------------------------------------------------------------------------- #
#   Proofscape Server                                                         #
#                                                                             #
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

from pfsc.checkinput import check_input, IType
from pfsc.excep import PfscExcep, PECode

def malformedReferenceCodeError(code, extra_msg=''):
    msg = f'Malformed PDF ref code: {code}'
    if extra_msg:
        msg += '. ' + extra_msg
    return PfscExcep(msg, PECode.MALFORMED_PDF_REF_CODE)

class PdfReference:

    def __init__(self, full_code, context):
        """
        :param full_code: a code such as may appear in a Node, as the
          value of its `pdfL` attribute.
        :param context: a PfscObj in which to search for referenced pdf info.
        """
        if not isinstance(full_code, str): raise malformedReferenceCodeError(full_code)
        parts = full_code.split("#")
        if not len(parts) == 2:
            e = 'Should be of the form `{ref}#{code}`.'
            raise malformedReferenceCodeError(full_code, extra_msg=e)
        pdf_info_name, combiner_code = parts

        # Validate the combiner code.
        check_input({'code': combiner_code}, {}, {
            "REQ": {
                'code': {
                    'type': IType.COMBINER_CODE,
                    'version': 2,
                },
            },
        })
        self.combiner_code = combiner_code

        # Try to find the referenced pdf info.
        pdf_info, libpath = context.getAsgnValueFromAncestor(pdf_info_name)
        if not isinstance(pdf_info, dict):
            msg = f'Could not find PDF info reference: {pdf_info_name}'
            raise PfscExcep(msg, PECode.MISSING_PDF_INFO)
        # Work with a copy, so that we don't modify the original.
        pdf_info = pdf_info.copy()

        # Validate the PDF info.
        possible_url_fields = [
            'url', 'aboutUrl'
        ]
        url_type = {
            'type': IType.URL,
            'allowed_schemes': ['http', 'https'],
            'unescape_first': True,
            'return': 'escaped_url',
        }
        check_input(pdf_info, pdf_info, {
            "REQ": {
                'fingerprint': {
                    'type': IType.PDF_FINGERPRINT
                },
            },
            "OPT": {f:url_type for f in possible_url_fields}
        }, reify_undefined=False)

        self.fingerprint = pdf_info['fingerprint']
        self.pdf_info = pdf_info
        self.pdf_info_name = pdf_info_name

    def write_pdf_render_div(self):
        return f'<div class="pdf-render" data-pdf-fingerprint="{self.fingerprint}" data-pdf-combinercode="{self.combiner_code}"></div>'

    def get_info_lookup(self):
        return {
            self.pdf_info_name: self.pdf_info
        }

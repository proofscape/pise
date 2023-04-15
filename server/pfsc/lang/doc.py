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

from pfsc.checkinput import check_input, IType
from pfsc.excep import PfscExcep, PECode

def malformedReferenceCodeError(code, extra_msg=''):
    msg = f'Malformed doc ref code: {code}'
    if extra_msg:
        msg += '. ' + extra_msg
    return PfscExcep(msg, PECode.MALFORMED_DOC_REF_CODE)

class DocReference:

    def __init__(self, full_code, context):
        """
        :param full_code: a code such as may appear in a Node, as the
          value of its `doc` attribute.
        :param context: a PfscObj in which to search for referenced doc info.
        """
        if not isinstance(full_code, str): raise malformedReferenceCodeError(full_code)
        parts = full_code.split("#")
        if not len(parts) == 2:
            e = 'Should be of the form `{ref}#{code}`.'
            raise malformedReferenceCodeError(full_code, extra_msg=e)
        doc_info_name, combiner_code = parts

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

        # Try to find the referenced doc info.
        doc_info, libpath = context.getAsgnValueFromAncestor(doc_info_name)
        if not isinstance(doc_info, dict):
            msg = f'Could not find doc info reference: {doc_info_name}'
            raise PfscExcep(msg, PECode.MISSING_DOC_INFO)
        # Work with a copy, so that we don't modify the original.
        doc_info = doc_info.copy()

        # Validate the doc info.
        possible_url_fields = [
            'url', 'aboutUrl'
        ]
        url_type = {
            'type': IType.URL,
            'allowed_schemes': ['http', 'https'],
            'unescape_first': True,
            'return': 'escaped_url',
        }
        check_input(doc_info, doc_info, {
            "REQ": {
                'docId': {
                    'type': IType.DOC_ID
                },
            },
            "OPT": {f:url_type for f in possible_url_fields}
        }, reify_undefined=False)

        checked_doc_id = doc_info['docId']
        doc_info['docId'] = checked_doc_id.full_id

        self.doc_id = checked_doc_id.full_id
        self.id_type = checked_doc_id.id_type
        self.id_code = checked_doc_id.id_code

        self.doc_info = doc_info
        self.doc_info_name = doc_info_name

    def write_doc_render_div(self):
        return f'<div class="doc-render" data-doc-id-type="{self.id_type}" data-doc-id-code="{self.id_code}" data-doc-combinercode="{self.combiner_code}"></div>'

    def write_highlight_descriptor(self, siid, slp, stype):
        """
        Assemble a dictionary that describes this reference as a "highlight".

        param siid: "supplier internal id": some id that the supplier of the
            highlight can interpret, in order to navigate in response to a
            click on this highlight.
        param slp: supplier libpath: the libpath of the supplier
        param stype: supplier type: the content type of the supplier

        Examples
        ========

        Suppose the doc ref was defined by a node ``u`` in a deduc ``D``.
        In this case, the deduction ``D`` is the supplier, and we would want:
            siid = u.libpath
            slp = D.libpath
            stype = "CHART"

        This would make it possible so that, when the highlight was clicked
        in a document panel, a chart panel containing deduction ``D`` could
        navigate to show node ``u`` (after first being opened, if not already).

        """
        return {
            'ccode': self.combiner_code,
            'siid': siid,
            'slp': slp,
            'stype': stype,
        }

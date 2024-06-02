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

import re

from lark import Lark
import lark.exceptions

from pfsc.excep import PfscExcep, PECode

NONEMPTY_HEXADECIMAL_PATTERN = re.compile(r'^[a-fA-F0-9]+$')

class DocIdType:
    PDF_FINGERPRINT_ID_TYPE = 'pdffp'


class CheckedDocId:

    def __init__(self, full_id, id_type, id_code):
        self.full_id = full_id
        self.id_type = id_type
        self.id_code = id_code


def check_doc_id(key, raw, typedef):
    """
    A doc id is a unique identifier for various types of documents such as
    PDFs, as well as other forms in which docs may be delivered.

    Every doc id has the form,

        type:code

    At present we recognize one type:

        pdffp: PDF fingerprint

    A PDF fingerprint is a hexadecimal hash computed by Mozilla's pdf.js
    in order to (probably uniquely) identify a PDF document. A full docId of
    this type might look like e.g.

        pdffp:ae4cc6056dbf2e389704cc8ef99f9720

    In PISE, you can obtain a PDF's fingerprint by opening it and then clicking
    the "fingerprint" icon in the viewer's toolbar.
    """
    def reject():
        raise PfscExcep('Malformed doc ID', PECode.MALFORMED_DOC_ID, bad_field=key)

    if not isinstance(raw, str):
        reject()

    first_colon = raw.find(":")
    if first_colon < 0:
        reject()

    id_type = raw[:first_colon]
    id_code = raw[first_colon + 1:]

    if id_type == DocIdType.PDF_FINGERPRINT_ID_TYPE:
        if not NONEMPTY_HEXADECIMAL_PATTERN.match(id_code):
            reject()
    else:
        reject()

    return CheckedDocId(raw, id_type, id_code)


combiner_code_grammar = r"""
    program: version scale depth? content_command+
    version: "v" (DECIMAL|INT) ("." INT)* ";"?
    scale: "s" (DECIMAL|INT) ";"?
    depth: "z" opt_signed_int ("," opt_signed_int)* ";"?
    ?content_command: box | x_shift | y_shift | newline
    box: "(" INT ":" INT ":" INT ":" INT ":" INT ":" INT ":" INT ")" ";"?
    x_shift: "x" SIGNED_INT ";"?
    y_shift: "y" SIGNED_INT ";"?
    newline: "n" ";"?
    SIGNED_INT: ("+"|"-") INT
    ?opt_signed_int: SIGNED_INT | INT
    
    %import common.INT
    %import common.DECIMAL
    %import common.WS
    %ignore WS
"""

combiner_code_parser = Lark(combiner_code_grammar, start='program', parser='lalr', lexer='standard')


def check_combiner_code(key, raw, typedef):
    """
    A combiner code is a little program used to indicate a way of selecting and
    combining boxes (from a document).

    typedef:
        opt:
            version: Which version of combiner code are we checking? Defaults to 2.

    Note: For now we are only capable of checking version 2.
    """
    desired_version = typedef.get('version', 2)
    if desired_version != 2:
        msg = f'Trying to check unknown combiner code version: {desired_version}'
        raise PfscExcep(msg, PECode.DOC_COMBINER_CODE_UKNOWN_VERS, bad_field=key)
    desired_v_code = f'v{desired_version}'

    try:
        combiner_code_parser.parse(raw)
    except lark.exceptions.LarkError as e:
        msg = f'Malformed combiner code: {e}'
        raise PfscExcep(msg, PECode.MALFORMED_COMBINER_CODE, bad_field=key)

    commands = raw.split(';')
    if commands[0] != desired_v_code:
        msg = f'Combiner code of unknown version: {commands[0]}'
        raise PfscExcep(msg, PECode.DOC_COMBINER_CODE_UKNOWN_VERS, bad_field=key)

    return raw

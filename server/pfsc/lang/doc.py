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

from pfsc.checkinput import check_input, IType
from pfsc.excep import PfscExcep, PECode


def malformedReferenceCodeError(code, extra_msg=''):
    msg = f'Malformed doc ref code: {code}'
    if extra_msg:
        msg += '. ' + extra_msg
    return PfscExcep(msg, PECode.MALFORMED_DOC_REF_CODE)


def doc_ref_factory(code=None, origin_node=None,
                    doc_info_obj=None, context=None, doc_info_libpath=None):
    """
    Supports various ways of constructing a DocReference instance.

    In all cases, a doc info object must somehow be obtained.
    A combiner code may or may not be supplied.

    An origin node may be supplied, in order to clone its doc ref.
    In this case, we copy all fields from this, and ignore all other args.

    The doc info object may be passed directly, under `doc_info_obj`.
    Otherwise, it will be resolved from a context. This means you pass some
    `PfscObj` (such as a module) under `context`, and then the doc info object
    will be located under some libpath, within this context.

    The libpath can either be passed directly, under `doc_info_libpath`, or
    parsed out of a passed `code`.

    Rules
    -----

    * If an `origin_node` is passed, we simply return a clone of its doc ref.

    * If we can attempt to resolve -- i.e. we have a `context` and a libpath,
      then we will attempt it, and raise an exception if the resolution fails.

    * Only if resolution cannot even be attempted will a passed `doc_info_obj`
      be used.

    * The `code` can be a pure combiner code, or a 2-part ref code of the form
      `{ref}#{combiner_code}`. If it is 2-part, then `ref` will override any
      passed `doc_info_libpath`.

    Note that, in particular, this allows you to treat the `doc_info_obj` as a
    default, to be used only if a ref is not defined in the code.
    """
    if origin_node is not None:
        return DocReference(origin_node=origin_node)

    combiner_code = None
    if code is not None:
        if not isinstance(code, str):
            raise malformedReferenceCodeError(code, extra_msg='Doc ref code must be string')
        parts = code.split("#")
        n = len(parts)
        if n < 1 or n > 2:
            e = 'Doc ref code should be either `combiner_code` or `{ref}#{combiner_code}`.'
            raise malformedReferenceCodeError(code, extra_msg=e)
        if n == 1:
            combiner_code = parts[0]
        else:
            doc_info_libpath, combiner_code = parts
            if len(doc_info_libpath) == 0:
                msg = f'Error: doc ref begins with "#": {code}'
                raise PfscExcep(msg, PECode.MALFORMED_DOC_REF_CODE)

    can_try_resolve = context is not None and doc_info_libpath is not None

    if doc_info_obj is None and not can_try_resolve:
        msg = "Need a context and a libpath to locate doc info object."
        raise PfscExcep(msg, PECode.MISSING_DOC_INFO)

    # If can try to resolve, will try. In particular, will ignore any
    # doc_info_obj that may have been provided.
    if can_try_resolve:
        doc_info_obj, _ = context.getAsgnValueFromAncestor(doc_info_libpath)
        if not isinstance(doc_info_obj, dict):
            msg = f'Could not find doc info reference: {doc_info_libpath}'
            raise PfscExcep(msg, PECode.MISSING_DOC_INFO)

    if not doc_info_obj:
        raise PfscExcep('Mising doc info', PECode.MISSING_DOC_INFO)

    # Work with a copy, so that we don't modify the original.
    doc_info = doc_info_obj.copy()
    return DocReference(doc_info, combiner_code=combiner_code)


def validate_doc_info(doc_info):
    """
    Validate a document descriptor object.

    * MUST supply a well-formatted `docId` field.
    * MAY supply URLs under the fields:
        - `url`
        - `aboutUrl`
      and we check the format of any that are supplied.

    """
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
        "OPT": {f: url_type for f in possible_url_fields}
    }, reify_undefined=False)
    checked_doc_id = doc_info['docId']
    doc_info['docId'] = checked_doc_id.full_id
    return checked_doc_id


class DocReference:

    def __init__(self, doc_info=None, combiner_code=None, origin_node=None):
        """
        :param doc_info: a dict giving the document descriptor for the referenced
            document
        :param combiner_code: (optional) a string of CombinerCode
        :param origin_node: (optional) Node that defines a doc ref of which we
            should be a clone. If given, overrides `doc_info` and `combiner_code`.
        """
        self.origin_node = origin_node
        if origin_node:
            ref = origin_node.getDocRef()
            doc_info = ref.doc_info
            combiner_code = ref.combiner_code

        self.doc_info = doc_info
        self.combiner_code = combiner_code

        if combiner_code:
            check_input({'code': combiner_code}, {}, {
                "REQ": {
                    'code': {
                        'type': IType.COMBINER_CODE,
                        'version': 2,
                    },
                },
            })

        checked_doc_id = validate_doc_info(doc_info)
        self.doc_id = checked_doc_id.full_id
        self.id_type = checked_doc_id.id_type
        self.id_code = checked_doc_id.id_code

    def write_doc_render_div(self):
        """
        Build a div that can be placed as the label HTML for a Moose node, in
        order to make the label be rendered, via combiner code, out of a doc.
        """
        return f'<div class="doc-render" data-doc-id-type="{self.id_type}" data-doc-id-code="{self.id_code}" data-doc-combinercode="{self.combiner_code}"></div>'

    def write_highlight_descriptor(self, siid, slp, stype):
        """
        If this doc ref defines a combiner code, build a highlight descriptor
        object to represent it. Otherwise return `None`.
        """
        if self.combiner_code is None:
            return None
        osiid, oslp = None, None
        if self.origin_node:
            osiid = self.origin_node.getDocRefInternalId()
            oslp = self.origin_node.getParent().getLibpath()
        return write_highlight_descriptor(
            self.combiner_code, siid, slp, stype, osiid=osiid, oslp=oslp)


def write_highlight_descriptor(ccode, siid, slp, stype, osiid=None, oslp=None):
    """
    Assemble a dictionary that describes a doc reference as a "highlight".

    param ccode: the combiner code that defines the highlight
    param siid: "supplier internal id": some id that the supplier of the
        highlight can interpret, in order to navigate in response to a
        click on this highlight.
    param slp: supplier libpath: the libpath of the supplier
    param stype: supplier type: the content type of the supplier
    param osiid: optional "original supplier internal id" for clone highlights
    param oslp: optional "original supplier libpath" for clone highlights

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
    d = {
        'ccode': ccode,
        'siid': siid,
        'slp': slp,
        'stype': stype,
    }
    if osiid:
        d['osiid'] = osiid
    if oslp:
        d['oslp'] = oslp
    return d

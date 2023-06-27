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

import json

from pfsc.excep import PfscExcep, PECode

from pfsc.checkinput.basic import (
    check_boolean,
    check_integer,
    check_string,
    check_simple_dict,
    check_json,
)
from pfsc.checkinput.url import (
    CheckedURL,
    check_url,
)
from pfsc.checkinput.libpath import (
    CheckedLibseg,
    EntityType,
    CheckedLibpath,
    check_boxlisting,
    check_libseg,
    check_content_forest,
    check_goal_id,
    check_versioned_libpath,
    check_versioned_forest,
    check_libpath,
)
from pfsc.checkinput.version import (
    check_major_version,
    check_full_version,
)
from pfsc.checkinput.doc import (
    check_doc_id,
    check_combiner_code,
)
from pfsc.checkinput.ise import (
    IseSideInfo,
    IseSplitInfo,
    IseActiveTabInfo,
    IseWidgetLinkInfo,
    check_ise_side,
    check_ise_split,
    check_ise_active,
    check_ise_widget_link,
)
from pfsc.checkinput.repo import (
    check_repo_dependencies_format,
)

def check_cdlist(key, raw, typedef):
    """
    'cdlist' stands for 'comma-delimited list'

    :param raw: a string, giving a comma-delimited list

    typedef is same as for `check_list` function.
    """
    inputs = raw.split(',')
    if len(inputs) == 1 and inputs[0] == '': inputs = []
    return check_list(key, inputs, typedef)

def check_dlist(key, raw, typedef):
    """
    'dlist' stands for 'delimited list'

    :param raw: a string, giving a delimited list

    typedef is same as for `check_list` function, plus the following:
        opt:
            delimiter: string that delimits the items of the list.
                Defaults to ',' if undefined.
    """
    d = typedef.get('delimiter', ',')
    inputs = raw.split(d)
    if len(inputs) == 1 and inputs[0] == '': inputs = []
    return check_list(key, inputs, typedef)

def check_list(key, raw, typedef):
    """
    :param raw: an actual list or a string rep thereof

    typedef:
        req:
            itemtype: typedef for the items of the list
        opt:
            max_num_items: maximum allowed number of items
            nonempty: bool
            flatten: bool; set true if the itemtype itself returns a list, and if
                you want to get a simple list, rather than a list of lists.
    :return: list of values
    """
    if isinstance(raw, str):
        try:
            L = json.loads(raw)
        except Exception:
            raise PfscExcep('Bad list', PECode.INPUT_WRONG_TYPE, bad_field=key)
    else:
        L = raw
    if not isinstance(L, list):
        raise PfscExcep('Bad list', PECode.INPUT_WRONG_TYPE, bad_field=key)
    M = typedef.get('max_num_items')
    if M is not None and len(L) > M:
        raise PfscExcep("List too long.", PECode.INPUT_TOO_LONG, bad_field=key)
    if typedef.get('nonempty', False) and len(L) == 0:
        raise PfscExcep("Empty list.", PECode.INPUT_EMPTY, bad_field=key)
    itemtypedef = typedef['itemtype']
    values = [check_type(key, raw_i, itemtypedef) for raw_i in L]
    # If the itemtype itself returns a list, then we have a list of lists, and
    # we need to flatten it if the user requested this.
    if typedef.get('flatten', False) and len(values) > 0 and isinstance(values[0], list):
        values = sum(values, [])
    return values

def check_dict(key, raw, typedef):
    """
    :param raw: an actual dictionary or a string rep thereof
    :param typedef:
        req:
            keytype: typedef for the keys in the dict. The return value
              of the corresonding check_... function must be hashable, so
              that we can build a dict of checked values.
            valtype: typedef for the values in the dict
    :return: dict
    """
    if isinstance(raw, str):
        try:
            d = json.loads(raw)
        except Exception:
            raise PfscExcep('Bad dictionary', PECode.INPUT_WRONG_TYPE, bad_field=key)
    else:
        d = raw
    if not isinstance(d, dict):
        raise PfscExcep('Bad dictionary', PECode.INPUT_WRONG_TYPE, bad_field=key)
    kt = typedef['keytype']
    vt = typedef['valtype']
    checked_dict = {}
    for raw_k, raw_v in d.items():
        k = check_type(key, raw_k, kt)
        v = check_type(key, raw_v, vt)
        checked_dict[k] = v
    return checked_dict

class IType:
    "Input Types"
    BOOLEAN = 'boolean'
    INTEGER = 'integer'
    SIMPLE_DICT = 'simple_dict'
    DICT = 'dict'
    LIST = 'list'
#    FLOAT = 'float'
    CDLIST = 'cdlist'
    DLIST = 'dlist'
#    CHECKBOX = 'checkbox'
    STR = 'str'
    JSON = 'json'
#    HASH = 'hash'
#    USERNAME_FORMAT = 'username_format'
#    PASSWORD_FORMAT = 'password_format'
#    EMAIL_FORMAT = 'email_format'
    MAJ_VERS = 'major_version'
    FULL_VERS = 'full_version'
    BOXLISTING = 'boxlisting'
    LIBSEG = 'libseg'
    LIBPATH = 'libpath'
    CONTENT_FOREST = 'content_forest'
    GOAL_ID = 'goal_id'
    VERSIONED_LIBPATH = 'versioned_libpath'
    VERSIONED_FOREST = 'versioned_forest'
#    REPOPATH = 'repopath'
#    MODPATH = 'modpath'
#    DEDUCPATH = 'deducpath'
#    NODEPATH = 'nodepath'
#    MODTEXT = 'modtext'
#    XPANTARGETLIST = 'xpantargetlist'
#    EDIT_ACTION_PARAM = 'edit_action_param'
#    DISCUSSION_NODE_ADDR = 'discussion_node_addr'
#    XPANREQID = 'xpanreqID'
#    RDEF_PAIRS = 'rdef_pairs'
#    FRIENDLY_RESULT_TYPE = 'friendly_result_type'
#    INPUT_RESULT_NUMBER = 'input_result_number'
#    INPUT_RESULT_PAGE_AND_LINE = 'input_result_page_and_line'
#    INPUT_RESULT_PAGE = 'input_result_page'
#    INPUT_RESULT_LINE = 'input_result_line'
#    ACCESS_TYPE = 'access_type'
#    WORK_TYPE = 'work_type'
    URL = 'url'
#    LIBSEG_FORMAT = 'libseg_format'
#    MSC_CODE = 'MSC_code'
#    MSC_TOP_LEVEL_CODE = 'MSC_top_level_code'
#    LIB_PAGE_TYPE = 'lib_page_type'
    ISE_SIDE = 'ise_side'
    ISE_SPLIT = 'ise_split'
    ISE_ACTIVE = 'ise_active'
    ISE_WIDGET_LINK = 'ise_widget_link'
    DOC_ID = 'doc_id'
    COMBINER_CODE = 'combiner_code'

TYPE_HANDLERS = {
    IType.BOOLEAN: check_boolean,
    IType.INTEGER: check_integer,
    IType.SIMPLE_DICT: check_simple_dict,
    IType.DICT: check_dict,
    IType.LIST: check_list,
#    IType.FLOAT: check_float,
    IType.CDLIST: check_cdlist,
    IType.DLIST: check_dlist,
#    IType.CHECKBOX: check_checkbox,
    IType.STR: check_string,
    IType.JSON: check_json,
#    IType.HASH: check_hash,
#    IType.USERNAME_FORMAT: check_username_format,
#    IType.PASSWORD_FORMAT: check_password_format,
#    IType.EMAIL_FORMAT: check_email_format,
    IType.MAJ_VERS: check_major_version,
    IType.FULL_VERS: check_full_version,
    IType.BOXLISTING: check_boxlisting,
    IType.LIBSEG: check_libseg,
    IType.LIBPATH: check_libpath,
    IType.CONTENT_FOREST: check_content_forest,
    IType.GOAL_ID: check_goal_id,
    IType.VERSIONED_LIBPATH: check_versioned_libpath,
    IType.VERSIONED_FOREST: check_versioned_forest,
#    IType.REPOPATH: check_libpath,
#    IType.MODPATH: check_libpath,
#    IType.DEDUCPATH: check_libpath,
#    IType.NODEPATH: check_libpath,
#    IType.MODTEXT: check_modtext,
#    IType.XPANTARGETLIST: check_xpantargetlist,
#    IType.EDIT_ACTION_PARAM: check_edit_action_param,
#    IType.DISCUSSION_NODE_ADDR: check_discussion_node_addr,
#    IType.XPANREQID: check_xpanreqID,
#    IType.RDEF_PAIRS: check_rdef_pairs,
#    IType.FRIENDLY_RESULT_TYPE: check_friendly_result_type,
#    IType.INPUT_RESULT_NUMBER: check_input_result_number,
#    IType.INPUT_RESULT_PAGE_AND_LINE: check_input_result_page_and_line,
#    IType.INPUT_RESULT_PAGE: check_input_result_page,
#    IType.INPUT_RESULT_LINE: check_input_result_line,
#    IType.ACCESS_TYPE: check_access_type,
#    IType.WORK_TYPE: check_work_type,
    IType.URL: check_url,
#    IType.LIBSEG_FORMAT: check_libseg_format,
#    IType.MSC_CODE: check_MSC_code,
#    IType.MSC_TOP_LEVEL_CODE: check_MSC_top_level_code,
#    IType.LIB_PAGE_TYPE: check_lib_page_type,
    IType.ISE_SIDE: check_ise_side,
    IType.ISE_SPLIT: check_ise_split,
    IType.ISE_ACTIVE: check_ise_active,
    IType.ISE_WIDGET_LINK: check_ise_widget_link,
    IType.DOC_ID: check_doc_id,
    IType.COMBINER_CODE: check_combiner_code,
}

def check_type(key, raw, typedef):
    """
    Check an individual input value against a typedef
    :param key: the key under which the input string was passed
    :param raw: input
    :param typedef: the typedef that the input should satisfy
    :return: an instance of whatever class we use for the specified type
    """
    typename = typedef['type']
    handler = TYPE_HANDLERS[typename]
    return handler(key, raw, typedef)

class UndefinedInput:
    """
    We use instances of this class to represent undefined input values.
    This is so that `None` can be reserved for other meanings.
    """
    pass

def is_undefined(thing):
    return isinstance(thing, UndefinedInput)

def is_defined(thing):
    return not is_undefined(thing)

def check_input(raw_dict, stash, types, reify_undefined=True):
    """
    We search for expected variables in a raw input dictionary,
    and perform type checking and other checks, stashing the
    results in the stash dictionary.

    :param raw_dict: dict {varname:value} giving the raw input
    :param stash: dict; a place to stash the results
    :param types: describes what you expect to find
    :param reify_undefined: see below
    :return: nothing

    Exceptions will be raised if anything is wrong with the input.
    This is the primary purpose of this function!

    If instead all goes well, then every variable named in types will be
    a key in stash, and will point either to an instance of UndefinedInput --if
    it was an optional variable that wasn't defined, or an alternative variable that wasn't
    chosen -- or to an instance of whatever class we use to represent data
    of the appropriate type.

    Alternatively, if you set keyword arg `reify_undefined` to False, then
    instead of storing instances of UndefinedInput in the stash, we simply
    store nothing in the stash under that key.

    Format of the 'types' argument:

    This is a dictionary, featuring any subset (including all) of
    the keys: REQ, REQ_ORDER, OPT, ALT_SETS, and CONF.

    REQ: A name:typedef dict. All these are required variables.

    REQ_ORDER: if defined, should be a list, giving an ordering on the
               keys in the REQ dict, so that they will be checked in this order.

    OPT: A name:typedef dict. All these are optional variables.

    ALT_SETS: A list of name:typedef dicts di. Each di represents a set of
              alternative variables, i.e. exactly one of these must be
              provided in the raw input, or else an exception will be raised.

    CONF: A name:typedef dict. All these are required, and must equal
          corresponding variables. See below.

    In a name:typedef dict, the names are strings, naming variables.
    The typedefs are themselves dicts, describing types.

    A typedef dict MUST have the key 'type', pointing to the name of the basic type.

    A typedef dict MAY have the key 'rename', giving an alternative name for this variable.
    If defined, the checked value will be stored in the stash under this name.

    Further keys in a typedef dict may specify subtypes or various options.

    In particular, recursive types like 'cdlist' will have a key 'itemtype'
    pointing to another typedef, defining the type of the elements of the list.

    Typedefs under the OPT group MAY have one of two special keys, 'default_raw'
    and 'default_cooked'. If the former is present and the user offered no value,
    then the given value is passed through as though it had been offered by the
    user. If the latter is present and the user offered no value, then the given
    value is simply recorded in the stash.

    The contemplated use case for the CONF group is the checking of "confirm" boxes
    in input forms, e.g. when users are asked to type their email address a second
    time as a confirmation.

    Type defs under the CONF group are in fact an exception to the rule about having
    a 'type' key; they do not have to have one. All they need is a 'primary' key, which
    points to the name of the variable that these vars are supposed to equal.
    On these vars, we do not store the value in the stash; we only check that they
    are present and that their raw value equals that of their nominated primary,
    otherwise raising an exception.
    """
    # Required arguments
    req = types.get("REQ")
    req_order = types.get("REQ_ORDER")
    if req is not None:
        if req_order is not None:
            varnames = req_order
        else:
            varnames = req.keys()
        for varname in varnames:
            typedef = req[varname]
            stashname = typedef.get('rename', varname)
            raw = raw_dict.get(varname)
            if raw is None:
                # These are required variables, so this is a problem.
                raise PfscExcep('var "%s" not supplied' % varname, PECode.MISSING_INPUT, bad_field=varname)
            stash[stashname] = check_type(varname, raw, typedef)
    # Optional arguments
    opt = types.get("OPT")
    if opt is not None:
        for varname, typedef in opt.items():
            stashname = typedef.get('rename', varname)
            raw = raw_dict.get(varname)
            if raw is None:
                # These are optional variables, so no worries.
                # Store a default value if one is given.
                # Otherwise store an instance of UndefinedInput.
                if 'default_cooked' in typedef:
                    # This is a default value that doesn't need to be built into
                    # any special kind of object; it already is the exact return
                    # value that we want.
                    stash[stashname] = typedef['default_cooked']
                elif 'default_raw' in typedef:
                    # This is a default value that should be run through the same
                    # process as an actual given input would be.
                    default_raw = typedef['default_raw']
                    stash[stashname] = check_type(varname, default_raw, typedef)
                elif reify_undefined:
                    stash[stashname] = UndefinedInput()
            else:
                stash[stashname] = check_type(varname, raw, typedef)
    # Sets of alternative arguments
    alt_sets = types.get("ALT_SETS")
    if alt_sets is not None:
        raw_key_set = set(raw_dict.keys())
        for alt_set in alt_sets:
            # Intersect the set of alternatives with the set of all
            # varnames provided in the raw_dict.
            # The size of the intersection should be exactly 1.
            alt_key_set = set(alt_set.keys())
            inter = alt_key_set & raw_key_set
            if len(inter) != 1:
                msg = 'Bad alternative args. For alternatives\n    %s' % alt_key_set
                msg += '\ngot\n    %s' % raw_key_set
                raise PfscExcep(msg, PECode.BAD_ALTERNATIVE_ARGS)
            # Check the chosen varname.
            varname = inter.pop()
            typedef = alt_set[varname]
            stashname = typedef.get('rename', varname)
            raw = raw_dict[varname]
            stash[stashname] = check_type(varname, raw, typedef)
            # Store an instance of UndefinedInput for all the other alternatives.
            unchosen = alt_key_set - set([varname])
            for u in unchosen:
                typedef = alt_set[u]
                stashname = typedef.get('rename', u)
                stash[stashname] = UndefinedInput()
    # Confirmation arguments
    conf = types.get("CONF")
    if conf is not None:
        for varname, typedef in conf.items():
            conf_raw = raw_dict.get(varname)
            if conf_raw is None:
                # These are required variables, so this is a problem.
                raise PfscExcep('var "%s" not supplied' % varname, PECode.MISSING_INPUT, bad_field=varname)
            primary_key = typedef['primary']
            primary_raw = raw_dict.get(primary_key)
            if primary_raw is None:
                raise PfscExcep('var "%s" not supplied' % primary_key, PECode.MISSING_INPUT, bad_field=primary_key)
            if conf_raw != primary_raw:
                raise PfscExcep(
                    'var "%s" does not match var "%s"' % (varname, primary_key),
                    PECode.CONF_ARG_DOES_NOT_MATCH,
                    bad_field=varname
                )

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
    check_any,
    check_boolean,
    check_integer,
    check_float,
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
    CheckedModuleFilename,
    EntityType,
    CheckedLibpath,
    check_boxlisting,
    check_relboxlisting,
    check_libseg,
    check_module_filename,
    check_content_forest,
    check_goal_id,
    check_versioned_libpath,
    check_versioned_forest,
    check_libpath,
    check_relpath,
    check_chart_color,
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

    :param typedef:
        alt sets:
            EITHER:
                req:
                    itemtype: typedef for the items of the list
                opt:
                    max_num_items: maximum allowed number of items
                    nonempty: bool
                    flatten: bool; set true if the itemtype itself returns a list, and if
                        you want to get a simple list, rather than a list of lists.
            OR:
                req:
                    spec: For a list of a fixed, expected length, provide a list
                        of typedef dictionaries, one for each expected entry.
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

    values = []
    if 'spec' in typedef:
        item_typedefs = typedef['spec']
        if len(L) != len(item_typedefs):
            msg = f'Wrong number of items passed. Expected {len(item_typedefs)}.'
            raise PfscExcep(msg, PECode.INPUT_WRONG_TYPE, bad_field=key)

        i = -1
        for item, item_typedef in zip(L, item_typedefs):
            i += 1
            try:
                value = check_type(f'{key}[{i}]', item, item_typedef)
            except PfscExcep as pe:
                pe.extendMsg(f'Error was on list item of index {i}: "{item}"')
                raise pe
            values.append(value)
    else:
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
        alt sets:
            EITHER:
                req:
                    keytype: typedef for the keys in the dict. The return value
                      of the corresponding `check_...()` function must be hashable, so
                      that we can build a dict of checked values.
                    valtype: typedef for the values in the dict
            OR:
                req:
                    spec: Provide precisely the same kind of dictionary you
                      would pass for the `types` arg to the `check_input()` function.
                      `check_input()` will be called with `raw` as its `raw_dict` arg,
                      (or the parsed version of `raw` if `raw` was a string)
                      and a fresh dictionary as its `stash` arg. That stash dictionary
                      will be the return value of this `check_dict()` call.
                opt:
                    reify_undefined: boolean, to be passed to `check_input()`. Default True.
    :return: dict
    """
    if isinstance(raw, str):
        try:
            raw_dict = json.loads(raw)
        except Exception:
            raise PfscExcep('Bad dictionary', PECode.INPUT_WRONG_TYPE, bad_field=key)
    else:
        raw_dict = raw
    if not isinstance(raw_dict, dict):
        raise PfscExcep('Bad dictionary', PECode.INPUT_WRONG_TYPE, bad_field=key)

    checked_dict = {}
    if 'spec' in typedef:
        types = typedef['spec']
        reify_undefined = typedef.get('reify_undefined', True)
        try:
            check_input(raw_dict, checked_dict, types, reify_undefined=reify_undefined)
        except PfscExcep as pe:
            pe.extendMsg(f'Error occurred in dictionary passed under key: "{key}"')
            raise pe
    else:
        kt = typedef['keytype']
        vt = typedef['valtype']
        for raw_k, raw_v in raw_dict.items():
            k = check_type(f'{key} key {raw_k}', raw_k, kt)
            v = check_type(f'{key}[{raw_k}]', raw_v, vt)
            checked_dict[k] = v

    return checked_dict


def check_disjunctive_type(key, raw, typedef):
    """
    Check the input against a set of alternative possible types.

    :param typedef:
        REQ:
            alts: list of alternative typedef dictionaries

                The alternatives are tried in the order given.
                Any `PfscExcep` raised is caught, and the next type is tried.
                If all alternatives fail, we raise a `PfscExcep` listing all
                the error messages.
    """
    alts = typedef['alts']
    err_msgs = []
    for alt_def in alts:
        try:
            value = check_type(key, raw, alt_def)
        except PfscExcep as pe:
            msg = f'Failed as {alt_def["type"]} due to:\n  ' + pe.public_msg()
            err_msgs.append(msg)
        else:
            return value
    msg = 'Input did not match any of the allowed types.\n'
    msg += '\n'.join(err_msgs)
    raise PfscExcep(msg, PECode.INPUT_WRONG_TYPE, bad_field=key)


class IType:
    """
    Input Types
    """
    ANY = 'any'
    DISJ = 'disj'
    BOOLEAN = 'boolean'
    INTEGER = 'integer'
    FLOAT = 'float'
    SIMPLE_DICT = 'simple_dict'
    DICT = 'dict'
    LIST = 'list'
    CDLIST = 'cdlist'
    DLIST = 'dlist'
    STR = 'str'
    JSON = 'json'
    MAJ_VERS = 'major_version'
    FULL_VERS = 'full_version'
    BOXLISTING = 'boxlisting'
    RELBOXLISTING = 'relboxlisting'
    LIBSEG = 'libseg'
    LIBPATH = 'libpath'
    RELPATH = 'relpath'
    MOD_FN = 'module_filename'
    CONTENT_FOREST = 'content_forest'
    GOAL_ID = 'goal_id'
    VERSIONED_LIBPATH = 'versioned_libpath'
    VERSIONED_FOREST = 'versioned_forest'
    URL = 'url'
    ISE_SIDE = 'ise_side'
    ISE_SPLIT = 'ise_split'
    ISE_ACTIVE = 'ise_active'
    ISE_WIDGET_LINK = 'ise_widget_link'
    DOC_ID = 'doc_id'
    COMBINER_CODE = 'combiner_code'
    CHART_COLOR = 'chart_color'


TYPE_HANDLERS = {
    IType.ANY: check_any,
    IType.DISJ: check_disjunctive_type,
    IType.BOOLEAN: check_boolean,
    IType.INTEGER: check_integer,
    IType.FLOAT: check_float,
    IType.SIMPLE_DICT: check_simple_dict,
    IType.DICT: check_dict,
    IType.LIST: check_list,
    IType.CDLIST: check_cdlist,
    IType.DLIST: check_dlist,
    IType.STR: check_string,
    IType.JSON: check_json,
    IType.MAJ_VERS: check_major_version,
    IType.FULL_VERS: check_full_version,
    IType.BOXLISTING: check_boxlisting,
    IType.RELBOXLISTING: check_relboxlisting,
    IType.LIBSEG: check_libseg,
    IType.LIBPATH: check_libpath,
    IType.RELPATH: check_relpath,
    IType.MOD_FN: check_module_filename,
    IType.CONTENT_FOREST: check_content_forest,
    IType.GOAL_ID: check_goal_id,
    IType.VERSIONED_LIBPATH: check_versioned_libpath,
    IType.VERSIONED_FOREST: check_versioned_forest,
    IType.URL: check_url,
    IType.ISE_SIDE: check_ise_side,
    IType.ISE_SPLIT: check_ise_split,
    IType.ISE_ACTIVE: check_ise_active,
    IType.ISE_WIDGET_LINK: check_ise_widget_link,
    IType.DOC_ID: check_doc_id,
    IType.COMBINER_CODE: check_combiner_code,
    IType.CHART_COLOR: check_chart_color,
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


def extract_full_key_set(types):
    """
    Pass the same `types` dict you would pass to the `check_input()` function; we extract
    and return the full set of key names that can possibly be passed, given this spec.
    """
    return check_input({}, {}, types, skip_reqs=True)


def check_input(raw_dict, stash, types, reify_undefined=True, err_on_unexpected=False, skip_reqs=False):
    """
    We search for expected variables in a raw input dictionary,
    and perform type checking and other checks, stashing the
    results in the stash dictionary.

    :param raw_dict: dict {varname:value} giving the raw input
    :param stash: dict; a place to stash the results
    :param types: describes what you expect to find
    :param reify_undefined: set False to record nothing, instead of an instance of `UndefinedInput`,
        for undefined input fields
    :param err_on_unexpected: set True if you want to raise an exception if
        any unexpected keys are received
    :param skip_reqs: set True if you don't want to actually require required args.
        Mainly intended for internal use.
    :return: the full set of arg names that could possibly be accepted, according to the given `types`

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

    This is a dictionary, featuring any subset of the keys: REQ, REQ_ORDER, OPT,
    ALT_SETS, and CONF.

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

    typedef dicts
    -------------

    Required keys:

        type

    Optional keys:

        rename
        keep_raw
        default_raw
        default_cooked

    Other keys:

        Further keys may be accepted, depending on the value of the `type`.
        See the specific type checker function for that type.

    'type': This is the only required key. It defines the basic type of the input.
        The value must be one of the values of the `IType` enum class.

    'rename': You can use this to give an alternative name for this variable.
        If defined, the checked value will be stored in the stash under this name.

    'keep_raw': If True, then the type checker function will still be called, but
        instead of stashing its return value, the raw value will be stashed.

    'default_raw': For use only in typedefs under the OPT group. If defined, and
        if no input was provided for this field, then this value is passed through
        the type checker as though it had been given as input.

    'default_cooked': For use only in typedefs under the OPT group. If defined, and
        if no input was provided for this field, then this value is recorded directly
        in the stash.

    Further keys in a typedef dict may specify subtypes or various options.
    In particular, recursive types like 'cdlist' will have a key 'itemtype'
    pointing to another typedef, defining the type of the elements of the list.

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
    raw_key_set = set(raw_dict.keys())
    expected_keys = set()

    # Required arguments
    req = types.get("REQ")
    req_order = types.get("REQ_ORDER")
    if req is not None:
        if req_order is not None:
            varnames = req_order
        else:
            varnames = req.keys()
        expected_keys.update(set(varnames))
        for varname in varnames:
            typedef = req[varname]
            stashname = typedef.get('rename', varname)
            keep_raw = typedef.get('keep_raw', False)
            raw = raw_dict.get(varname)
            if raw is None:
                if skip_reqs:
                    continue
                # These are required variables, so this is a problem.
                raise PfscExcep('var "%s" not supplied' % varname, PECode.MISSING_INPUT, bad_field=varname)
            checked_value = check_type(varname, raw, typedef)
            stash[stashname] = raw if keep_raw else checked_value

    # Optional arguments
    opt = types.get("OPT")
    if opt is not None:
        for varname, typedef in opt.items():
            expected_keys.add(varname)
            stashname = typedef.get('rename', varname)
            keep_raw = typedef.get('keep_raw', False)
            raw = raw_dict.get(varname)
            if raw is None:
                # These are optional variables, so no worries.
                # Store a default value if one is given.
                # Otherwise store an instance of `UndefinedInput` if reifying undefined.
                if 'default_cooked' in typedef:
                    # This is a default value that doesn't need to be built into
                    # any special kind of object; it already is the exact return
                    # value that we want.
                    stash[stashname] = typedef['default_cooked']
                elif 'default_raw' in typedef:
                    # This is a default value that should be run through the same
                    # process as an actual given input would be.
                    default_raw = typedef['default_raw']
                    checked_value = check_type(varname, default_raw, typedef)
                    stash[stashname] = default_raw if keep_raw else checked_value
                elif reify_undefined:
                    stash[stashname] = UndefinedInput()
            else:
                checked_value = check_type(varname, raw, typedef)
                stash[stashname] = raw if keep_raw else checked_value

    # Sets of alternative arguments
    alt_sets = types.get("ALT_SETS")
    if alt_sets is not None:
        for alt_set in alt_sets:
            # Intersect the set of alternatives with the set of all
            # varnames provided in the raw_dict.
            # The size of the intersection should be exactly 1.
            alt_key_set = set(alt_set.keys())
            expected_keys.update(alt_key_set)
            inter = alt_key_set & raw_key_set
            if len(inter) != 1:
                if skip_reqs:
                    continue
                msg = 'Bad alternative args. For alternatives\n    %s' % alt_key_set
                msg += '\ngot\n    %s' % raw_key_set
                raise PfscExcep(msg, PECode.BAD_ALTERNATIVE_ARGS)
            # Check the chosen varname.
            varname = inter.pop()
            typedef = alt_set[varname]
            stashname = typedef.get('rename', varname)
            keep_raw = typedef.get('keep_raw', False)
            raw = raw_dict[varname]
            checked_value = check_type(varname, raw, typedef)
            stash[stashname] = raw if keep_raw else checked_value
            # Store an instance of UndefinedInput for all the other alternatives.
            unchosen = alt_key_set - {varname}
            for u in unchosen:
                typedef = alt_set[u]
                stashname = typedef.get('rename', u)
                stash[stashname] = UndefinedInput()

    # Confirmation arguments
    conf = types.get("CONF")
    if conf is not None:
        for varname, typedef in conf.items():
            expected_keys.add(varname)
            conf_raw = raw_dict.get(varname)
            if conf_raw is None and not skip_reqs:
                # These are required variables, so this is a problem.
                raise PfscExcep('var "%s" not supplied' % varname, PECode.MISSING_INPUT, bad_field=varname)
            primary_key = typedef['primary']
            primary_raw = raw_dict.get(primary_key)
            if primary_raw is None and not skip_reqs:
                raise PfscExcep('var "%s" not supplied' % primary_key, PECode.MISSING_INPUT, bad_field=primary_key)
            if conf_raw != primary_raw and not skip_reqs:
                raise PfscExcep(
                    'var "%s" does not match var "%s"' % (varname, primary_key),
                    PECode.CONF_ARG_DOES_NOT_MATCH,
                    bad_field=varname
                )

    # Check for unexpected args
    if err_on_unexpected:
        unexpected = raw_key_set - expected_keys
        if unexpected:
            noun = 'key' if len(unexpected) == 1 else 'keys'
            msg = f'Received unexpected {noun}: ' + ', '.join(sorted(list(unexpected)))
            raise PfscExcep(msg, PECode.UNEXPECTED_INPUT)

    return expected_keys

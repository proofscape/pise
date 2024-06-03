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

from pfsc.excep import PfscExcep, PECode
from pfsc.lang.freestrings import Libpath


def check_any(key, raw, typedef):
    """
    This is useful in cases where the `check_input()` function has been called
    with `err_on_unexpected=True`. Then every legal field has to be "checked" in
    some way, lest an error be raised when it is defined. If no further checking
    is desired, then this is the "checker" function to use.
    """
    return raw


def check_boolean(key, raw, typedef):
    """
    :param raw: either an actual boolean, or potentially also int and/or str,
        depending on the typedef (see below).
    :param typedef:
        accept_int: boolean, default False
            If True, accept int or string that parses to int, and take 0 to
            mean False, and any other integer to mean True.
        accept_str: boolean, default True (for backwards compatibility reasons)
            If True, accept a string s, and map it to True if s.lower() == 'true',
            and to False otherwise.
    :return: an actual boolean
    """
    if raw is True or raw is False:
        return raw

    accept_int = typedef.get('accept_int', False)
    accept_str = typedef.get('accept_str', True)

    if accept_int:
        try:
            n = int(raw)
        except ValueError:
            pass
        else:
            return n != 0

    if accept_str and isinstance(raw, str):
        return raw.lower() == 'true'

    msg = 'Expecting boolean.'
    if accept_int or accept_str:
        alts = {'int' if accept_int else None, 'str' if accept_str else None} - {None}
        msg = msg[:-1] + f', optionally expressed as {" or ".join(sorted(alts))}.'
    raise PfscExcep(msg, PECode.INPUT_WRONG_TYPE)


def check_strict_boolean(key, raw, typedef):
    """
    Convenience function to call `check_boolean()` with settings to strictly
    accept only actual boolean input values.
    """
    td = typedef.copy()
    td.update({
        'accept_int': False,
        'accept_str': False,
    })
    return check_boolean(key, raw, td)


def check_integer(key, raw, typedef):
    """
    :param raw: either an actual integer, or a string rep of integer, base 10
    :param typedef:
        opt:
            min: minimum integer value accepted (inclusive)
            max: maximum integer value accepted (inclusive)
            default_on_empty: value to take as default in case of empty string input
            divisors: list of integers that must divide the given one
    :return: int
    """
    if not isinstance(raw, (str, int)):
        msg = 'Expecting int or string rep thereof.'
        raise PfscExcep(msg, PECode.INPUT_WRONG_TYPE)
    lb = typedef.get('min')
    ub = typedef.get('max')
    if 'default_on_empty' in typedef and raw == '':
        return typedef['default_on_empty']
    try:
        n = int(raw)
    except Exception:
        raise PfscExcep('Bad integer', PECode.BAD_INTEGER, bad_field=key)
    try:
        if lb is not None:
            assert n >= lb
        if ub is not None:
            assert n <= ub
    except Exception:
        raise PfscExcep('Integer out of range', PECode.BAD_INTEGER, bad_field=key)

    divisors = typedef.get('divisors', [])
    for d in divisors:
        if n % d != 0:
            raise PfscExcep(f'Integer must be divisible by {d}', PECode.BAD_INTEGER, bad_field=key)

    return n


def check_float(key, raw, typedef):
    """
    :param raw: either an actual float, or a string rep thereof
    :param typedef:
        opt:
            gte: must be greater than or equal to this
            lte: must be less than or equal to this
            gt: must be greater than this
            lt: must be less than this
    :return: float
    """
    gte = typedef.get('gte')
    lte = typedef.get('lte')
    gt = typedef.get('gt')
    lt = typedef.get('lt')

    try:
        f = float(raw)
    except Exception:
        raise PfscExcep('Bad float', PECode.BAD_FLOAT, bad_field=key)

    try:
        if gte is not None:
            assert f >= gte
        if lte is not None:
            assert f <= lte
        if gt is not None:
            assert f > gt
        if lt is not None:
            assert f < lt
    except Exception:
        raise PfscExcep('Float out of range', PECode.BAD_FLOAT, bad_field=key)

    return f


def check_simple_dict(key, raw, typedef):
    """
    The "simple" in the name of this function contrasts it with the `check_dict`
    function which requires a formal typedef for keys and for values. Here, you
    may provide a Python type for keys and for values, but each is optional.

    :param raw: an actual dictionary or a string rep thereof
    :param typedef:
        opt:
            keytype: a Python type of which all keys in the dict must be instances
            valtype: a Python type of which all values in the dict must be instances
    :return: dict
    """
    if isinstance(raw, str):
        try:
            d = dict(raw)
        except Exception:
            raise PfscExcep('Bad dictionary', PECode.INPUT_WRONG_TYPE, bad_field=key)
    else:
        d = raw
    if not isinstance(d, dict):
        raise PfscExcep('Bad dictionary', PECode.INPUT_WRONG_TYPE, bad_field=key)
    kt = typedef.get('keytype')
    vt = typedef.get('valtype')
    if kt is not None:
        for k in d.keys():
            if not isinstance(k, kt):
                raise PfscExcep('Key of wrong type in dictionary', PECode.INPUT_WRONG_TYPE, bad_field=key)
    if vt is not None:
        for v in d.values():
            if not isinstance(v, vt):
                raise PfscExcep('Value of wrong type in dictionary', PECode.INPUT_WRONG_TYPE, bad_field=key)
    return d


def check_string(key, raw, typedef):
    """
    Check that the input is a string.
    See Pfsc-7.1 for more sophisticated checks we might want here.

    :param typedef:
        optional:
            values: list of strings giving the only allowed values
            max_len: maximum allowable length of the string
            is_Libpath_instance: boolean, default False. Set True to require
                that this string actually be an instance of the
                `pfsc.lang.freestrings.Libpath` class.
    """
    if not isinstance(raw, str):
        raise PfscExcep('Expecting string', PECode.INPUT_WRONG_TYPE, bad_field=key)

    if typedef.get('is_Libpath_instance') and not isinstance(raw, Libpath):
        raise PfscExcep('Expecting Libpath', PECode.INPUT_WRONG_TYPE, bad_field=key)

    values = typedef.get('values')
    if values is not None:
        if raw not in values:
            raise PfscExcep('Param not among allowed values.', PECode.INPUT_WRONG_TYPE, bad_field=key)

    max_len = typedef.get('max_len')
    if isinstance(max_len, int):
        if len(raw) > max_len:
            raise PfscExcep('String too long.', PECode.INPUT_TOO_LONG, bad_field=key)

    return raw


def check_json(key, raw, typedef):
    """
    Check that the input parses as JSON.

    :param typedef: nothing special
    :return: the parsed object
    """
    import json
    try:
        obj = json.loads(raw)
    except json.decoder.JSONDecodeError:
        raise PfscExcep('Malformed JSON', PECode.MALFORMED_JSON, bad_field=key)
    return obj

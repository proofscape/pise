# --------------------------------------------------------------------------- #
#   Copyright (c) 2018-2023 Proofscape Contributors                           #
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

"""
Parsing for display widgets.

We use the `displaylang` library to build a DisplayLang processor that accepts
those SymPy callables for which we have so far defined `AllowedCallable`s.
The set is expected to grow over time in response to user demand.
"""

from displaylang.build import make_displaylang_processor
from sympy.core.function import UndefinedFunction
from sympy.core.relational import Relational

from pfsc_examp.config import config
from .excep import ParsingExcep

from .sympy_allowed import (
    sympy_basic_allowed_callables,
    generalized_builtin_allowed_callables,
    sympy_other_allowed_callables,
    sympy_available_constants,
)


# The "basic vars" are those that are available for all builds.
# Here we combine the constants we've made available, along with
# the "sympy basic" and "generalized builtin" allowed callables.
basic_vars = {**sympy_available_constants}
for c in sympy_basic_allowed_callables + generalized_builtin_allowed_callables:
    basic_vars[c.name] = c.callable

all_allowed_callables = (
    generalized_builtin_allowed_callables +
    sympy_basic_allowed_callables +
    sympy_other_allowed_callables
)

displaylang_processor = make_displaylang_processor(
    basic_vars, all_allowed_callables, add_builtins=True,
    allow_local_var_calls=False,
    abstract_function_classes=[UndefinedFunction],
    abstract_relation_classes=[Relational],
    max_len=config["MAX_DISPLAY_BUILD_LEN"],
    max_depth=config["MAX_DISPLAY_BUILD_DEPTH"],
)


###############################################################################
# Bounds on arithmetic operations
#
# For now none of this is doing anything.
# Keeping here for possible future use.

EXPONENT_CAP = 100
INT_DIGIT_CAP = 200


def pow_check(b, e):
    if isinstance(b, int) and isinstance(e, int):
        # There is a largest exponent that we will allow, regardless of the base:
        if abs(e) > EXPONENT_CAP:
            raise ParsingExcep(f'Exponent too large: {e}.')
        # For smaller exponents we allow larger bases, but we don't want the total
        # number of digits in the power to grow too large. We estimate this as the
        # number of decimal digits in the base, times the exponent itself.
        if len(str(b)) * abs(e) > INT_DIGIT_CAP:
            raise ParsingExcep(f'Power too large: {b}^{e}.')


def mult_check(a, b):
    if isinstance(a, int) and isinstance(b, int):
        if len(str(a)) + len(str(b)) > INT_DIGIT_CAP:
            raise ParsingExcep(f'Product too large: {a}*{b}.')

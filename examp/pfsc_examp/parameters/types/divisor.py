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

from sympy.core.numbers import Integer, NegativeOne, Zero, One
from sympy.ntheory.factor_ import divisors, divisor_count

from pfsc_examp.calculate import calculate
from pfsc_examp.parameters.base import (
    Parameter,
    write_radio_panel_chooser_widget
)
from pfsc_examp.excep import MalformedParamRawValue


class Divisor_Param(Parameter):
    """
    Represents a rational integer that is supposed to divide another.

    The reason for having a special Parameter class for this (instead of
    just using `Integer_Param`) is to supply the user with a radio panel
    where they are offered all the possible divisors. Remember that the
    purpose of a Parameter class is not just to represent a particular
    type of mathematical object, but to represent such an object _plus
    a way of choosing its values_.

    ptype: "Divisor"

    Value type: Integer

    Default: int

    Args:
        Required:
            dividing: int
                The number of which this is a divisor.
        Optional:
            sign: {-1, 0, 1}, default=1
                1 if you want only positive divisors
                -1 if you want only negative divisors
                0 if you allow both positive and negative divisors

    """

    arg_spec = {
        "REQ": {
            'dividing': {
                'type': Integer,
            },
        },
        "OPT": {
            'sign': {
                'type': (One, Zero, NegativeOne,),
                'default_cooked': Integer(1),
            },
        }
    }

    def __init__(self, parent, name=None,
                 default=None, tex=None, descrip=None, params=None,
                 args=None, last_raw=None, **other):
        super().__init__(parent, name, default, tex, descrip, params, args, last_raw)
        self.divisors = []
        self.dividing = None
        self.sign = None

    def prebuild(self):
        # Store args as attributes
        self.dividing = self.resolved_args['dividing']
        self.sign = self.resolved_args['sign']
        # Compute all the divisors.
        n = self.dividing.value
        c = calculate(divisor_count, n)
        if c > 200:  # FIXME: make such upper bounds configurable.
            msg = f'Parameter {self.name} has too many notes, er divisors.'
            raise MalformedParamRawValue(msg, self)
        self.divisors = calculate(divisors, n)
        s = self.sign.value
        if s == 0:
            self.divisors = list(reversed([-d for d in self.divisors])) + self.divisors
        elif s == -1:
            self.divisors = list(reversed([-d for d in self.divisors]))

    def auto_build(self):
        s = self.sign.value
        d = s if s != 0 else 1
        return self.build_from_raw(d)

    def build_from_raw(self, raw):
        d = self.check_int(raw)
        n = self.dividing.value
        if not n % d == 0:
            raise MalformedParamRawValue(f'Must divide ${n}$', self)
        return Integer(d)

    def auto_descrip(self, include_value=True, editable=True):
        return '%s a divisor of $%s$' % (
            self.write_name_and_value(include_value, editable),
            self.dividing
        )

    def write_chooser_widget(self):
        return write_radio_panel_chooser_widget(
            self.name, self.auto_descrip(), zip(self.divisors, self.divisors),
            self.value
        )

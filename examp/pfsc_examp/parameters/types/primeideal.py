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

from sympy import AlgebraicField, Integer, latex

from pfsc_examp.calculate import calculate
from pfsc_examp.parameters.base import (
    Parameter, DependencyType, ParametricValued,
    write_radio_panel_chooser_widget,
)
from pfsc_examp.excep import MalformedParamRawValue


class PrimeIdeal_Param(Parameter):
    """
    A prime ideal in a number field.

    The chooser HTML offers a radio panel, with which to select one
    of the prime ideals lying above a particular rational prime, in a
    particular number field.

    ptype: "PrimeIdeal"

    Value type: sympy.polys.numberfields.primes.PrimeIdeal

    Default: int
        Zero-based index into the list of PrimeIdeals computed by SymPy.

    Args:
        Required:
            k: Libpath
                Must point to a param widget of `NumberField` type.
            p: int
                The rational prime whose ideal divisors we are to represent.
    """

    arg_spec = {
        "REQ": {
            'k': {
                'type': AlgebraicField,
            },
            'p': {
                'type': Integer,
            }
        }
    }

    def __init__(self, parent, name=None,
                 default=None, tex=None, descrip=None, params=None,
                 args=None, last_raw=None, **other):
        super().__init__(parent, name, default, tex, descrip, params, args, last_raw)
        self.field = None
        self.prime = None
        self.prime_ideals = None
        self.display_values = None
        self.selected_index = None

        self.last_field_value = None
        self.last_prime_value = None

    def prebuild(self):
        K0 = self.last_field_value
        p0 = self.last_prime_value

        self.field = self.resolved_args['k']
        self.prime = self.resolved_args['p']
        K = self.field.value
        p = self.prime.value

        if K != K0 or p != p0:
            # `AlgebraicField.primes_above()` expects a raw `int`, not an `Integer`.
            self.prime_ideals = calculate(K.primes_above, int(p))
            self.display_values = [self.write_display_value_for_prime_ideal(P)
                                   for P in self.prime_ideals]
            self.last_attempted_raw_value = None
            #print(f'{self.name}: reset last to None')
            self.last_field_value = K
            self.last_prime_value = p

    def write_display_value_for_prime_ideal(self, P):
        field_gen = self.field.get_field_generator_symbol()
        alpha = P.alpha.poly(x=field_gen).as_expr()
        p = self.prime.value
        return f'({p}, {latex(alpha)})'

    def auto_build(self):
        return self.build_from_raw(0)

    def build_from_raw(self, raw):
        i = self.check_int(raw)
        if not 0 <= i < len(self.prime_ideals):
            raise MalformedParamRawValue(f'Bad index for prime ideal: {i}', self)
        self.selected_index = i
        return self.prime_ideals[i]

    def auto_descrip(self, include_value=True, editable=True):
        display_value = self.display_values[self.selected_index]
        return f'%s a prime ideal over $%s$ in $%s$' % (
            self.write_name_and_value(include_value, editable, display_value),
            self.prime.value, self.field.getTeX(as_name=True)
        )

    def write_chooser_widget(self):
        return write_radio_panel_chooser_widget(
            self.name, self.auto_descrip(),
            enumerate([f'${v}$' for v in self.display_values]),
            self.selected_index
        )

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

import re

from sympy import (
    AlgebraicNumber, QQ, Poly, cyclotomic_poly, Symbol, latex, CRootOf, Integer
)
import jinja2
from lark.exceptions import LarkError

from pfsc_examp.calculate import calculate, construct_instance
from pfsc_examp.parameters.base import Parameter
from pfsc_examp.parse.polynom import validate_univar_polynom_over_Z
from pfsc_examp.parse.excep import ParsingExcep
from pfsc_examp.excep import MalformedParamRawValue


CYC_POLY_RAW_PATTERN = re.compile(r'^cyc(lotomic_poly)?\((\d+)\)$')

class NumberField_Param(Parameter):
    """
    Number Field over the rationals.

    ptype: "NumberField"

    Value type: AlgebraicField

    Default: str
        accepts EITHER:
        - `cyc(n)` or `cyclotomic_poly(n)` for the nth cyclotomic field, OR
        - a string giving any irreducible univariate polynomial over Z

    Args:
        Required: None.
        Optional:
            gen: str
                Symbol name to use for a generator of the field.
                For example, 'theta'.
                If supplied, it will be included in the description of the
                field; otherwise, we only describe the field as a quotient
                mod a polynomial.
            var: str
                Symbol name to use for the variable in the field's defining,
                irreducible polynomial.
                If not supplied, we use `x` for `cyc(n)`, or the
                given variable for polynomials given explicitly.
            root_idx: int
                Root index, indicating which root of the minimal polynomial to
                use as primitive element for the field. This is passed to
                SymPy's `CRootOf`. Real roots come first, in increasing order,
                followed by complex roots, which are sorted first by real part
                (increasing) and then by imaginary part (increasing).
                If not supplied, we use -1.
    """

    arg_spec = {
        "OPT": {
            'gen': {
                'type': Symbol,
            },
            'var': {
                'type': Symbol,
            },
            'root_idx': {
                'type': Integer,
                'default_raw': -1,
            }
        }
    }

    def __init__(self, parent, name=None,
                 default=None, tex=None, descrip=None, params=None,
                 args=None, last_raw=None, **other):
        super().__init__(parent, name, default, tex, descrip, params, args, last_raw)
        self.explicit_cyclo = False
        self.cyc_num = None
        self.raw = None
        self.validated = None

    def get_poly(self):
        return self.value.ext.root.minpoly

    def get_field_generator_symbol(self):
        gen = self.resolved_args.get('gen')
        return gen.value if gen is not None else None

    def write_polynomial(self):
        if self.explicit_cyclo:
            pol = fr'\Phi_{self.cyc_num}({self.get_poly().gen})'
        else:
            pol = latex(self.get_poly().as_expr())
        return pol

    def write_as_quotient(self):
        var = self.get_poly().gen
        pol = self.write_polynomial()
        return fr'\mathbb{{Q}}[{var}]/({pol})'

    def auto_descrip(self, include_value=True, editable=True):
        display_value = self.write_as_quotient()
        gen = self.resolved_args.get('gen')
        if gen is not None:
            display_value = fr'\mathbb{{Q}}({gen}) \cong ' + display_value
        name_part = self.write_name_and_value(include_value, editable, display_value=display_value)
        noun_phrase = r'a number field over $\mathbb{Q}$'
        return f'{name_part} {noun_phrase}'

    def auto_build(self):
        raw = 'cyc(4)'
        return self.build_from_raw(raw)

    def build_from_raw(self, raw):
        """
        :return: AlgebraicField
        """
        raw = str(raw)  # Ensure that we have a string
        M = CYC_POLY_RAW_PATTERN.match(raw)
        if M:
            self.explicit_cyclo = True
            self.cyc_num = int(M.group(2))
            validated = raw
            sym = self.resolved_args.get('var', Symbol('x'))
            poly_expr = calculate(cyclotomic_poly, self.cyc_num, sym)
            poly_value = calculate(construct_instance, Poly, poly_expr)
        else:
            # Use `calculate` here in case the description is too long.
            try:
                v = calculate(validate_univar_polynom_over_Z, raw)
            except (LarkError, ParsingExcep) as e:
                raise MalformedParamRawValue(str(e), self)
            validated = v['poly']
            poly_value = calculate(construct_instance, Poly, validated)
            sym = self.resolved_args.get('var')
            if sym:
                poly_value = poly_value.subs(poly_value.gen, sym.value)
        self.validated = validated
        self.raw = raw

        # Check irreducible.
        if not self.explicit_cyclo:
            # Careful! `poly_value.is_irreducible` is a `@property` method,
            # so must use `getattr` here as the function:
            is_irred = calculate(getattr, poly_value, 'is_irreducible')
            if not is_irred:
                msg = r'Polynomial must be irreducible over $\mathbb{Q}$.'
                raise MalformedParamRawValue(msg, self)

        i = self.resolved_args['root_idx'].value
        root = calculate(construct_instance, CRootOf, poly_value, i)
        ext = calculate(construct_instance, AlgebraicNumber,
                        (poly_value, root),
                        alias=self.get_field_generator_symbol())
        field = calculate(QQ.algebraic_field, ext)

        return field

    def write_chooser_widget(self):
        context = {
            'name': self.name,
            'descrip': self.auto_descrip(),
            'current_value': self.raw,
        }
        return nf_chooser_widget_template.render(context)

nf_chooser_widget_template = jinja2.Template("""
<div class="chooser nf_chooser" name="{{ name }}">
    <div class="heading">{{ descrip }}</div>
    <div class="error_display"></div>
    <input class="textfield polynomial_field" type="text" placeholder="Irreducible polynomial" value="{{current_value}}"/>
</div>
""")

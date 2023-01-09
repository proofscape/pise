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


import dill
import pytest

from sympy import Expr, I

from pfsc_examp.parameters.types.numberfield import NumberField_Param
from pfsc_examp.excep import ExampError
from pfsc_examp.parse.excep import ParsingExcep
from pfsc_examp.parse.polynom import (
    validate_univar_polynom_over_Z
)
from pfsc_examp.parse.algebraic import (
    safe_algebraic_func_str_to_sympy,
)

@pytest.mark.parametrize('given, validated', [
    ["3", {'poly': '3', 'var': 'None'}],
    ["x", {'poly': 'x', 'var': 'x'}],
    ["T", {'poly': 'T', 'var': 'T'}],
    ["2*x + 7", {'poly': '2*x + 7', 'var': 'x'}],
    ["t^2 - t + 18", {'poly': 't**2 - t + 18', 'var': 't'}],
    ["t**2 - t + 18", {'poly': 't**2 - t + 18', 'var': 't'}],
    ["-3*u^17 - 5*u^2 + -2*u + 9", {'poly': '-3*u**17 - 5*u**2 + -2*u + 9', 'var': 'u'}],
])
def test_poly_parse_ok_1(given, validated):
    assert validate_univar_polynom_over_Z(given) == validated


@pytest.mark.parametrize('given', [
    'x^3 + u - 7',
    'x*2',
    'x^-3',
    '3.14*x',
    'x^2 + +x',
    'x^3 + -x',
    'foo',
    'os.system("malicious code")',
])
def test_poly_parse_fail_1(given):
    with pytest.raises(ExampError):
        validate_univar_polynom_over_Z(given)


@pytest.mark.parametrize('given', [
    'x',
    'theta',
    'x^3 + u - 7',
    'x*2',
    'x^-3',
    '3.14*x',
    'x^3 + -x',
    '(2*a^3 + b*c - 7)/(-r + s^(1/2))',
    '(2*a^3 + b*c - 7)/(-theta + s^(x - 1/2))',
    '2 + 3',
    '2 - 3',
    'x + 2',
    '(x - 2)*(y + 3)',
    'a*b + c*d',
    'a/b',
    'b^(-1)',
    '(x^2 - 3*x + 7)^(2*y - 1)',
    'a + b * c ^ d',
    'c ^ d * b + a',
    'a + b + c',
    'p*q*r*s',
    'a - -b',
    'a---b',
])
def test_alg_func_valid(given):
    f = safe_algebraic_func_str_to_sympy(given, max_len=1024, max_depth=32)
    #from sympy import latex
    #print(latex(f))
    assert isinstance(f, Expr)


@pytest.mark.parametrize('given', [
    "sin(x)",
    "x.n.__globals__['__builtins__']['exec']('''import os; os.system(\"echo 'arbitrary code execution...'\")''')",
])
def test_alg_func_invalid(given):
    with pytest.raises(ParsingExcep):
        safe_algebraic_func_str_to_sympy(given)


def test_nf_param_root_idx():
    # When we do not specify the root index, it defaults to -1, which in
    # this case means the cube root of 2 in the second quadrant:
    d = {
        'name': 'k',
        'default': 'x^3 - 2',
    }
    nfp = NumberField_Param(None, **d)
    nfp.build()
    k = nfp.value
    assert abs(k.ext.n(5) - (-0.62996 + 1.0911*I)) < 1e-4

    # Now we specify the real cube root of 2:
    d['args'] = {
        'root_idx': 0
    }
    nfp = NumberField_Param(None, **d)
    nfp.build()
    k = nfp.value
    assert abs(k.ext.n(5) - 1.2599) < 1e-4


def test_nf_pickle():
    d = {
        'name': 'k',
        'default': 'x^3 - 2',
    }
    nfp = NumberField_Param(None, **d)
    nfp.build()
    k1 = nfp.value
    k2 = dill.loads(dill.dumps(k1))
    assert k1.ext.minpoly == k2.ext.minpoly

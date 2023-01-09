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


import pytest

from sympy import Symbol

from displaylang.exceptions import CannotCall
from pfsc_examp.parse.display import displaylang_processor


build_01 = """
return str((Matrix([[2, 3], [5, 7]]) @ Matrix([[-7, 3], [5, -2]])).flat())
"""

build_02 = """
x, y, z = symbols('x, y, z')
return latex(Poly(x + y**2 + z**3).as_expr())
"""

@pytest.mark.parametrize('code, s_exp, d_exp', [
    [build_01, '[1, 0, 0, 1]', {}],
    [build_02, 'x + y^{2} + z^{3}', {'x': Symbol('x'), 'y': Symbol('y'), 'z': Symbol('z')}],
])
def test_builds(code, s_exp, d_exp):
    s, d = displaylang_processor.process(code, {})
    interactive = False
    if interactive:
        print()
        print(s)
        print(d)
    else:
        assert s == s_exp
        assert d == d_exp


@pytest.mark.parametrize('code', [
    'Poly("foo")',
    'Symbol("x[]")',
    'symbols("x, y, z()")',
])
def test_reject_str_args(code):
    code += '\nreturn "foo"'
    with pytest.raises(CannotCall) as e:
        displaylang_processor.process(code, {})
    #print(e.value)


@pytest.mark.parametrize('code', [
    'range(3)',
    'range(S(3))',
    'S(3)',
    'S(1)/2',
    'S(3.14)',
    'latex(S(3))',
    'Matrix([[1, 2], [3, 4]])',
    'mod_inverse(2, 7)',
    'x = Symbol("x"); Poly(x**2 - 2, x, modulus=7)',
    'Symbol("theta")',
    'Symbol("theta2")',
    'symbols("x, y0, z12")',
    'k = QQ.cyclotomic_field(7); B = k.integral_basis()',
    'k = QQ.cyclotomic_field(7); P = k.primes_above(11); a = 4*P[0].ZK.parent(3); P[0].reduce_element(a)',
    'k = QQ.cyclotomic_field(7); P = k.primes_above(11); a = k([1, 2, 3]); P[0].reduce_ANP(a)',
    'k = QQ.cyclotomic_field(7); P = k.primes_above(11); a = k.to_alg_num(k([1, 2, 3])); P[0].reduce_alg_num(a)',
    'k = QQ.cyclotomic_field(7); a = k.to_sympy(k.new([1, 2, 3]))',
    'k = QQ.cyclotomic_field(7); a = k.to_sympy(k([1, 2, 3]))',
    'Matrix([[1, 2], [3, 4]]).flat()',
    'x = Symbol("x"); Poly(x**2 - 2).as_expr()',
])
def test_allow_call(code):
    """
    Just testing that we can process these code strings without raising any
    exception.
    """
    code += '\nreturn "foo"'
    displaylang_processor.process(code, {})


@pytest.mark.parametrize('code', [
    'range("foo")',
    'S("3")',
    'S("zeta")',
    'latex(S(3), order="foo()")',
    'Matrix([["1", 2], [3, 4]])',
    'mod_inverse(2.1, 7)',
    'Poly("x**2 - 2")',
    'x = Symbol("x"); Poly(x**2 - 2, 5, modulus=7)',
    'x = Symbol("x"); Poly(x**2 - 2, x, modulus=7.3)',
    'Symbol("theta[x]")',
    'symbols("x, y0, z+")',
    'k = QQ.cyclotomic_field(7.5); B = k.integral_basis(fmt="foo.bar")',
    'k = QQ.cyclotomic_field(7); B = k.integral_basis(fmt="foo.bar")',
    'k = QQ.cyclotomic_field(7); P = k.primes_above("foo")',
    'k = QQ.cyclotomic_field(7); P = k.primes_above(11); P[0].reduce_element("foo")',
    'k = QQ.cyclotomic_field(7); P = k.primes_above(11); P[0].reduce_ANP("foo")',
    'k = QQ.cyclotomic_field(7); P = k.primes_above(11); P[0].reduce_alg_num("foo")',
    'k = QQ.cyclotomic_field(7); a = k.to_sympy(k.new("foo"))',
    'k = QQ.cyclotomic_field(7); a = k.to_sympy(k("foo"))',
    'k = QQ.cyclotomic_field(7); a = k.to_sympy("foo")',
    'Matrix([[1, 2], [3, 4]]).flat("foo")',
    'x = Symbol("x"); Poly(x**2 - 2).as_expr("foo")',
])
def test_disallow_call(code):
    with pytest.raises(CannotCall):
        code += '\nreturn "foo"'
        displaylang_processor.process(code, {})

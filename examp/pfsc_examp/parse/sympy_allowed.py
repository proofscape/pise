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
This module is where we define the set of allowed callables from SymPy.
The set is expected to grow over time, in response to user demand.
"""

from sympy import (
    AlgebraicField, AlgebraicNumber, Expr, Integer, latex, Matrix, mod_inverse,
    Poly, QQ, S, Symbol, symbols,
)
from sympy.logic.boolalg import Boolean
from sympy.polys.domains.domain import Domain
from sympy.polys.matrices import DomainMatrix
from sympy.polys.numberfields.modules import (
    ModuleElement, PowerBasis, Submodule
)
from sympy.polys.numberfields.primes import PrimeIdeal
from sympy.polys.polyclasses import ANP

from typing import List, Optional as o, Union as u

from displaylang.allow import (
    ArgSpec as a,
    AllowedCallable as c,
    StrPermType as s,
    Tail as t
)


Bool = u[Boolean, bool]
Int = u[Integer, int]
iExpr = u[Expr, int]
fExpr = u[Expr, float]
fiExpr = u[Expr, float, int]


sympy_available_constants = {
    'QQ': QQ,
}

# We need to override some of the built-ins defined in the `displaylang`
# library, to allow them to accept not just `int` but also `Integer`.
generalized_builtin_allowed_callables = [
    c(range, [t(Int)]),
]

# The "basic" callables are those that will be present in the namespace for all
# display code evaluations, under their `.__name__`, before defining any imported
# names from any other displays or parameters.
sympy_basic_allowed_callables = [

    # Note: We're supplying the `S` function only to provide an easy way to
    # construct a SymPy `Integer`, `Rational`, or `Float`.
    # If you want a `Symbol`, you should use either `symbols()` or `Symbol()`.
    # If we allowed `S` for this purpose, users would find it confusing, since
    # `beta`, `gamma`, `zeta` would be exceptions, being recognized instead as
    # special functions.
    c(S, [u[int, float]], name="S"),

    c(latex, [Expr], {'order': s.CNAME}, incomplete=True),
    c(Matrix, [List[List[fiExpr]]], name="Matrix"),
    c(mod_inverse, [Int, Int]),
    c(Poly, [Expr, t(Symbol)], {'modulus': Int}, incomplete=True),
    c(Symbol, [s.UWORD]),
    c(symbols, [s.UWORD_CDL]),
]

# These are callables not added to the namespace basis. Instead, we expect you
# to access them through other objects you define or import from other displays
# or parameters.
sympy_other_allowed_callables = [
    c(AlgebraicField.integral_basis, [], {'fmt': s.CNAME}, method_of=AlgebraicField),
    c(AlgebraicField.primes_above, [int], method_of=AlgebraicField),
    c(AlgebraicField.new, [List[iExpr]], method_of=AlgebraicField),
    c(AlgebraicField.__call__, [List[iExpr]], method_of=AlgebraicField),
    c(AlgebraicField.to_sympy, [ANP], method_of=AlgebraicField),
    c(AlgebraicField.to_alg_num, [ANP], method_of=AlgebraicField),
    c(Domain.cyclotomic_field, [int],
      {'ss': bool, 'alias': s.UWORD, 'gen': Symbol, 'root_index': int},
      method_of=Domain),
    c(Matrix.flat, [], method_of=Matrix),
    c(Poly.as_expr, [t(Symbol)], method_of=Poly),
    c(PowerBasis.__call__, [
        [DomainMatrix],
        [int]
    ], {'denom': int}, method_of=PowerBasis),
    c(PrimeIdeal.reduce_element, [ModuleElement], method_of=PrimeIdeal),
    c(PrimeIdeal.reduce_ANP, [ANP], method_of=PrimeIdeal),
    c(PrimeIdeal.reduce_alg_num, [AlgebraicNumber], method_of=PrimeIdeal),
    c(Submodule.__call__, [
        [DomainMatrix],
        [int]
    ], {'denom': int}, method_of=Submodule),
]

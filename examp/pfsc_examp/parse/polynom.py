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

from lark import Lark, Transformer
from lark.exceptions import LarkError, VisitError

from pfsc_examp.excep import ExampError, MalformedInput
from pfsc_examp.parse.excep import ParsingExcep

univar_polynom_over_Z_grammar = r"""
    poly: term (PM term)*
    PM: "+"|"-"
    ?term: var_term | coeff
    var_term: (coeff "*")? var (("^"|"**") power)?
    coeff: [PM] INT
    var: LETTER
    power: INT

    %import common.LETTER
    %import common.INT
    %import common.WS
    %ignore WS
"""

univar_polynom_over_Z_parser = Lark(
    univar_polynom_over_Z_grammar, start='poly', lexer='standard')

class UnivarPolynomOverZTransformer(Transformer):

    def __init__(self):
        self.var_letter = None

    def coeff(self, items):
        n = items[-1]
        # Regularize (e.g. 002 -> 2)
        n = int(n)
        s = str(n)
        if len(items) == 2:
            sign = items[0]
            assert sign in "+-"
            s = sign + s
        return s

    def var(self, items):
        letter = items[0]
        if self.var_letter is not None and letter != self.var_letter:
            msg = 'Univariate polynomial must only name one variable.'
            raise MalformedInput(msg)
        self.var_letter = letter
        return letter

    def power(self, items):
        # Validated polynomial expressions are intended for consumption by
        # the SymPy library, so exponentiation is given by `**`.
        return f'**{int(items[0])}'

    def var_term(self, items):
        k = len(items)
        if k == 1:
            return items[0]
        elif k == 2:
            a, b = items
            # Powers include their initial "**", but coeffs do NOT include their trailing "*".
            # This is important, so that we can have terms that are pure coeffs.
            if b.startswith("**"):
                return f'{a}{b}'
            else:
                return f'{a}*{b}'
        elif k == 3:
            c, v, p = items
            return f'{c}*{v}{p}'

    def poly(self, items):
        return ' '.join(items)

def validate_univar_polynom_over_Z(raw_text):
    """
    :param raw_text: a string which _is supposed to_ define a univariate polynomial
      with integer coefficients.
    :return: dict {
      poly: a string that _does_ define a univariate polynomial with int coeffs,
      var: the variable (str) or None if constant polynomial
    }
    :raises: ParsingExcep if anything goes wrong during parsing or transforming.
    """
    try:
        ast = univar_polynom_over_Z_parser.parse(raw_text)
        transformer = UnivarPolynomOverZTransformer()
        validated = transformer.transform(ast)
    except VisitError as v:
        # Lark traps our `ExampError`s, but we want to see them.
        if isinstance(v.orig_exc, ExampError):
            raise v.orig_exc from v
        else:
            raise ParsingExcep(f'Parsing error: {v}') from v
    except LarkError as e:
        raise ParsingExcep(f'Parsing error: {e}') from e
    return {
        'poly': validated,
        'var': str(transformer.var_letter),
    }

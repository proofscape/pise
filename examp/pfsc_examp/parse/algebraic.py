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

"""Parsing for algebraic functions. """

from sympy import Add, Mul, Pow, Symbol, Integer, Float
from lark import Lark, Transformer
from lark.exceptions import LarkError

from pfsc_examp.parse.util import check_expr_dims
from pfsc_examp.parse.excep import ParsingExcep


algebraic_grammar = r"""
    ?expr: add | mul | pow | atomic
    add: expr (plus | minus) expr
    mul: factor (times | dividedby) factor
    ?factor: mul | pow | atomic
    pow: atomic ("^"|"**") atomic
    ?atomic: "(" expr ")" | atom
    ?atom: pos | neg
    neg: "-" atom
    ?pos: var | int | float
    plus: "+"
    minus: "-"
    times: "*"
    dividedby: "/"
    var: CNAME
    int: INT
    float : FLOAT

    %import common.CNAME
    %import common.INT
    %import common.FLOAT
    %import common.WS
    %ignore WS
"""


algebraic_func_parser = Lark(
    algebraic_grammar, start='expr', lexer='standard')


class ExprBuilder(Transformer):

    def add(self, items):
        a, op, b = items
        if op.data == 'minus':
            b = -b
        return Add(a, b)

    def mul(self, items):
        a, op, b = items
        if op.data == 'dividedby':
            b = Pow(b, -1)
        return Mul(a, b)

    def pow(self, items):
        a, b = items
        return Pow(a, b)

    def neg(self, items):
        return -items[0]

    def var(self, items):
        return Symbol(items[0])

    def int(self, items):
        return Integer(items[0])

    def float(self, items):
        return Float(items[0])


def safe_algebraic_func_str_to_sympy(raw_text, max_len=None, max_depth=None):
    """
    Safely convert a string defining an algebraic function into a SymPy expression.

    @param raw_text: the string supposedly defining the algebraic function.
    @param max_len: maximum allowed length for the string. If `None`, we look
        for a value in the global config.
    @param max_depth: maximum allowed parenthesis depth for the string. If
        `None`, we look for a value in the global config.
    @return: SymPy Expr
    @raise: ParsingExcep if given text is too long, or has too deep parenthesis
      nesting (important to avoid exceeding recusion stack max depth), or if
      it simply doesn't parse as a valid algebraic function.
    """
    check_expr_dims(raw_text, max_len=max_len, max_depth=max_depth)
    try:
        tree = algebraic_func_parser.parse(raw_text)
    except LarkError as e:
        raise ParsingExcep("Expression not a valid algebraic function.\n" + str(e))
    builder = ExprBuilder()
    expr = builder.transform(tree)
    return expr

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

"""Utilities for parsing. """

from pfsc_examp.config import config
from pfsc_examp.parse.excep import ParsingExcep


def paren_depth(raw_text):
    """Compute the deepest parenthesis nesting depth in a string."""
    max_depth = 0
    cur_depth = 0
    for c in raw_text:
        if c == "(":
            cur_depth += 1
            max_depth = max(max_depth, cur_depth)
        elif c == ")":
            cur_depth = max(0, cur_depth - 1)
    return max_depth


def check_expr_dims(raw_text, max_len=None, max_depth=None):
    """
    Check that a string is not too long or too deep (in parenthesis nesting),
    for safe parsing as a mathematical expression.

    @param raw_text: the string to be checked.
    @param max_len: maximum allowed length for the string. If `None`, we look
        for a value in the global config.
    @param max_depth: maximum allowed parenthesis depth for the string. If
        `None`, we look for a value in the global config.
    @return: nothing
    @raise: ParsingExcep if given text is too long, or has too deep parenthesis
      nesting.
    """
    if max_len is None:
        max_len = config["MAX_SYMPY_EXPR_LEN"]
    if max_depth is None:
        max_depth = config["MAX_SYMPY_EXPR_DEPTH"]
    if len(raw_text) > max_len:
        raise ParsingExcep("Math expression too long.")
    if paren_depth(raw_text) > max_depth:
        raise ParsingExcep("Math expression too deep.")

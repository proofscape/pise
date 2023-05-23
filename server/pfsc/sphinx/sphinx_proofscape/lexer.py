# --------------------------------------------------------------------------- #
#   Sphinx-Proofscape                                                         #
#                                                                             #
#   Copyright (c) 2022-2023 Proofscape contributors                           #
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

from pygments.lexer import RegexLexer, bygroups, default, include, words, using
from pygments.token import *


IDENTIFIER = r'[_a-zA-Z]\w*'
PATH = r'[a-zA-Z_!?]\w*(?:\.[a-zA-Z_!?]\w*)*'
GEN_STR_TERM = r'\'\'\'|"""|\'|"'


# HINT for debugging a Pygments lexer:
#  Set a breakpoint in `pygments.lexer.RegexLexer.get_tokens_unprocessed()`, in
#  the `else` clause that catches the case where none of the regexes matched.


class MesonBnfGrammarLexer(RegexLexer):
    """
    This lexer will probably only be used once ever, namely on the Proofscape
    docs page that shows the BNF grammar for the Meson language.
    """

    tokens = {
        'root': [
            (r'\s+', Text),
            (words((
                'inf', 'sup', 'flow', 'roam', 'conj', 'modal', 'how', 'name',
            ), suffix=r'\b'), Keyword),
            (words((
                '::=', '?', '*', '|', '(', ')',
            )), Operator),
            (r'\w+', Name.Builtin),
        ]
    }


class MesonLexer(RegexLexer):
    """
    Lexer for the Meson language.
    """
    name = 'Meson'
    aliases = ['meson']

    tokens = {
        'root': [
            (r'\s+', Text),
            (words((
                'so', 'then', 'therefore', 'hence', 'thus', 'get', 'infer',
                'find', 'implies', 'whence', 'whereupon',
                'by', 'since', 'using', 'because', 'for',
                'now', 'next', 'claim',
                'but', 'meanwhile', 'note', 'have', 'from', 'observe', 'consider',
                'and', 'plus',
                'suppose', 'let',
                'applying',
                '-->', '..>'
            ), prefix=r'(?i)', suffix=r'\b'), Keyword),
            (PATH, Name),
            (r'[.,;]', Punctuation),
        ],
    }


class ProofscapeLexer(RegexLexer):
    """
    Lexer for Proofscape modules.

    FIXME:
      This is an initial approximation, to get us started. We're not yet supporting
      annos, and we could be much more careful about defining different states,
      and having certain keywords match only in certain states (e.g. deduc preamble,
      node contents, etc.).
    """

    name = 'Proofscape'
    aliases = ['proofscape']
    filenames = ['*.pfsc']

    def innerstring_rules(ttype):
        return [
            (r'[^\\\'"\n]+', ttype),
            (r'[\'"\\]', ttype),
            # Newlines are allowed in all string types
            (r'\n', ttype),
        ]

    tokens = {
        'root': [
            (r'\s+', Text),
            (r'#.*$', Comment.Single),
            (r'[{}\[\],:]', Punctuation),
            include('keywords'),
            (r'(from)((?:\s|\\\s)+)', bygroups(Keyword.Namespace, Text),
             'fromimport'),
            (r'(import)((?:\s|\\\s)+)', bygroups(Keyword.Namespace, Text),
             'import'),
            (r'(meson|arcs)(\s*)(=)(\s*)(\'\'\'|"""|\'|")', bygroups(
                Name.Builtin, Text, Operator, Text, String
            ), 'meson'),
            (r'=', Operator),
            ('"""', String.Double, 'tdqs'),
            ("'''", String.Single, 'tsqs'),
            ('"', String.Double, 'dqs'),
            ("'", String.Single, 'sqs'),
            include('nodetype'),
            include('known-fields'),
            include('json-constants'),
            include('numbers'),
            include('path'),
            include('name'),
        ],
        'keywords': [
            (words((
                'deduc', 'defn',
                'as', 'of', 'with',
                'versus', 'wolog', 'contra'), suffix=r'\b'),
             Keyword),
        ],
        'nodetype': [
            (words((
                'asrt', 'cite', 'exis', 'flse', 'intr', 'mthd', 'rels', 'supp',
                'univ', 'with', 'subdeduc'), suffix=r'\b'),
             Name.Builtin),
        ],
        'known-fields': [
            (words((
                'sy', 'en', 'fr', 'de', 'ru', 'lt',
                'sympy', 'cf'), suffix=r'\b'),
             Name.Builtin),
        ],
        'json-constants': [
            (words((
                'false', 'true', 'null',
                # Python equivalents are also accepted
                'False', 'True', 'None',
            ), suffix=r'\b'),
             Name.Builtin.Pseudo),
        ],
        'numbers': [
            (r'(\d+\.\d*|\d*\.\d+)([eE][+-]?[0-9]+)?j?', Number.Float),
            (r'\d+[eE][+-]?[0-9]+j?', Number.Float),
            (r'0[0-7]+j?', Number.Oct),
            (r'0[bB][01]+', Number.Bin),
            (r'0[xX][a-fA-F0-9]+', Number.Hex),
            (r'\d+L', Number.Integer.Long),
            (r'\d+j?', Number.Integer)
        ],
        'name': [
            (IDENTIFIER, Name),
        ],
        'path': [
            (PATH, Name),
        ],
        'import': [
            (r'(?:[ \t]|\\\n)+', Text),
            (r'as\b', Keyword.Namespace),
            (r',', Operator),
            (r'[a-zA-Z_][\w.]*', Name),
            default('#pop')
        ],
        'fromimport': [
            (r'(?:[ \t]|\\\n)+', Text),
            (r'import\b', Keyword.Namespace, '#pop'),
            (r'[a-zA-Z_.][\w.]*', Name),
            default('#pop'),
        ],
        'meson': [
            (r'(?s)(.+?)(\'\'\'|"""|\'|")', bygroups(
                using(MesonLexer), String
            ), '#pop'),
        ],
        'strings-single': innerstring_rules(String.Single),
        'strings-double': innerstring_rules(String.Double),
        'dqs': [
            (r'"', String.Double, '#pop'),
            include('strings-double')
        ],
        'sqs': [
            (r"'", String.Single, '#pop'),
            include('strings-single')
        ],
        'tdqs': [
            (r'"""', String.Double, '#pop'),
            include('strings-double'),
            (r'\n', String.Double)
        ],
        'tsqs': [
            (r"'''", String.Single, '#pop'),
            include('strings-single'),
            (r'\n', String.Single)
        ],
    }

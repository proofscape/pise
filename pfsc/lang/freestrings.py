# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2022 Proofscape contributors                           #
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
This module is intended to be the home of all code that is responsible for
safely handling "free strings" in pfsc modules.

By a "free string" we mean any place in the syntax where the module author is
free to write any string whatsoever. These are the places in pfsc modules where
we have to think about HTML escaping and XSS safety.

When pfsc modules are parsed, they are first chunked, and annotations are handled
separately. Thus, the question has two parts: (1) Where are free strings in annotations,
and (2) Where are free strings in the pfsc module syntax minus annotations. We
find the following answers:

  (1) Annotations: The entire _contents_ of an annotation is a free string.
  (2) pfsc syntax minus annos:
      (A) Assignments. These occur at the top level, in deducs, and in nodes.
          The right-hand side of an assignment is arbitrary JSON, and thus may
          either _be_ a free string, or _contain_ one or more free strings.
      (B) defn's. The definiens and definiendum are both free strings.
  
Our security model is to ensure that every free string is HTML-escaped,
and to make that happen in one, central location, namely within this module.

One peculiarity of pfsc modules is that, in many settings, free strings may be
expected to contain VerTeX syntax. Since this is so widespread, we bundle VerTeX
translation (into ordinary TeX) along with our HTML-escaping. The two operations
happen together in our `vertex_and_escape` function -- henceforth "V&E".

In theory, and hopefully this will be maintained going forward, a security
audit should be able to begin by asking your IDE to find all usages of the V&E
function. At time of writing, the plan is that there should be exactly _two_ usages
of V&E -- one to handle annotation contents, and one to handle all free strings
occuring in pfsc syntax minus annos.

Free strings in pfsc syntax minus annos
---------------------------------------

Here the key invocation of the V&E function is in `PfscJsonTransformer.ve_string`.

To begin with, this means that _every_ string occuring in any JSON anywhere in
any pfsc module passes through V&E. In particular, this covers all strings
occurring in any assignments.

As for `defn`s, the pfsc module syntax defined in `modules.py` uses the `ve_string`
nonterminal from our custom JSON grammar. This means that the strings received here
go through `PfscJsonTransformer.ve_string` too.

   !!! NOTE: Going forward, any time a string is needed in the pfsc module
       syntax, you must use the `ve_string` nonterminal! 

Remark on universal escaping of strings in JSON: It is anticipated that, for
some applications, it will be necessary to _un_escape to make the string
usable again. This is by design. Consider the case of a new developer (or an old one who has
forgotten about security), adding a brand new widget type. Maybe this new widget
type takes a data field that is ruined by HTML-escapes. Under our design, the
developer is forced to become aware of security implications, because the escaped
string becomes unavoidable.

The alternative would be to leave it up to the developer to just magically "remember",
_without any prompting_, that widget data fields may need to be escaped. In that case,
our security model would be open-ended: it would have to be revisited every time you
added a new widget type. Essentially, every new extension would be a security hole
until patched. We prefer that every new extension be secure by design, and sometimes
you have to unescape to do what you need to do.


Annotation contents
-------------------

Here the key invocation of the V&E function is in the `render_anno_markdown` function.

    !!! NOTE: You should never turn annotation markdown into HTML except through
        the `render_anno_markdown` function.

When we process an annotation, every widget, which is of the form:

    <type:name>[label]{data}

is replaced with a stub:

    [label]{name}

The resulting text is what is passed through V&E in `render_anno_markdown`, before
being passed onward to markdown rendering.

This means that the only free strings in annos that don't go through this particular
V&E invocation are those occurring within widget data parts. But a widget data part
is just JSON syntax, and we parse this using our custom JSON parser. Therefore any
free strings occuring in widget data go through `PfscJsonTransformer.ve_string`.
It follows that all free parts of annotations are escaped.

"""

import json, re
from collections import namedtuple
from itertools import chain

from flask import escape
from lark import Lark, Transformer, v_args
import vertex2tex
import mistletoe
from mistletoe.span_token import SpanToken
from mistletoe.latex_token import Math as MathToken
from mistletoe.html_renderer import HTMLRenderer

from pfsc import check_config
import pfsc.constants
from pfsc.excep import PfscExcep, PECode
from pfsc_util.scan import PfscModuleStringAwareScanner


def vertex_and_escape(s):
    s = vertex2tex.translate_document(s, keychar=pfsc.constants.VERTEX_KEY_CHAR)
    return escape(s)


##################################################################################
# JSON Parsing
#
# We use a custom json parser for several reasons:
#   * Allow mutli-line strings as values, i.e. strings where a linebreak in the
#     input does not terminate the string but is simply accepted as a \n char.
#   * Allow strings to be delimited by " or '. Whichever is used, it can occur
#     within the string if escaped (as \" or \'). No other escapes are
#     processed.
#   * Allow strings to be delimited by """ or '''. In such strings, no escapes
#     are processed. WYSIWYG.
#   * Allow an extra comma at the end of an array or object.
#   * Allow both Python (True, False, None) and Javascript (true, false, null)
#     constants.
#   * Allow identifiers (as well as strings) as object keys, like in Javascript.
#   * Allow libpaths as primitives (along with strings, ints, floats, booleans,
#     and null). This requires a "scope" (any PfscObj instance) as a place to
#     resolve the libpath to an object. If no scope is provided, we simply
#     convert the libpath directly into a `Libpath` instance (a subclass of
#     `str` -- see below). Otherwise we resolve to an object. If the resolution
#     fails, we raise an exception. If the object is a PfscAssignment, it is
#     replaced by its RHS. Otherwise we again convert to a `Libpath` instance.

# We use a `json_` prefix to put the grammar definition within a namespace, so
# that it can be included as a sub-grammar elsewhere.
json_grammar = r"""
    ?json_value: json_object
          | json_array
          | ve_string
          | SIGNED_INT         -> json_integer
          | SIGNED_FLOAT       -> json_number
          | ("true"|"True")    -> json_true
          | ("false"|"False")  -> json_false
          | ("null"|"None")    -> json_null
          | json_libpath
    json_array  : "[" [json_value ("," json_value)*] ","? "]"
    json_object : "{" [json_pair ("," json_pair)*] ","? "}"
    json_pair   : (json_cname|ve_string) ":" json_value
    ve_string : TRIPLE_QUOTE_STRING|TRIPLE_APOS_STRING|ESCAPED_STRING|APOS_STRING
    json_cname: CNAME
    json_libpath: CNAME ("." CNAME)*
"""

json_grammar_imports = """
    TRIPLE_APOS_STRING.2 : "'''" /'?'?[^']/* "'''"
    TRIPLE_QUOTE_STRING.2 : "\\"\\"\\"" /"?"?[^"]/* "\\"\\"\\""
    APOS_STRING : "'" ("\\'"|/[^']/)* "'"
    %import common.CNAME
    %import common.ESCAPED_STRING
    %import common.SIGNED_INT
    %import common.SIGNED_FLOAT
    %import common.WS
    %ignore WS
"""


class Libpath(str):
    """
    The purpose of this subclass of str is to make a formal record of the fact
    that a string returned after parsing our extended JSON syntax was
    originally given in the .pfsc module not as a literal string, but as a
    direct libpath reference.
    """

    def __new__(cls, value):
        self = str.__new__(cls, value)
        return self


class PfscJsonTransformer(Transformer):

    def __init__(self, scope=None):
        """
        :param scope: a PfscObj where libpaths can be resolved.
        """
        self.scope = scope

    @staticmethod
    def raise_libpath_resolution_excep(libpath):
        msg = 'Libpath %s could not be resolved.' % libpath
        raise PfscExcep(msg, PECode.RELATIVE_LIBPATH_CANNOT_BE_RESOLVED)

    def json_libpath(self, items):
        libpath = Libpath('.'.join(items))
        scope = self.scope
        if scope is None:
            return libpath
        obj, ancpath = scope.getAsgnValueFromAncestor(libpath)
        if obj is not None:
            # We got the RHS of a PfscAssignment
            return obj
        obj, ancpath = scope.getFromAncestor(libpath)
        if obj is None:
            # This means we couldn't resolve the libpath at all, which is an exception.
            self.raise_libpath_resolution_excep(libpath)
        # We can resolve the libpath, but it doesn't point to a PfscAssignment,
        # so we just return the libpath itself.
        return libpath

    @v_args(inline=True)
    def ve_string(self, s):
        """
        "VE-string" stands for "VerTeXed and Escaped string".
        This means that (1) VerTeX has been translated to ordinary TeX, and
        (2) HTML escaping has been applied (in that order).
        """
        # First we have to strip the delimiters, and replace escaped quotes
        # in single-quoted strings.
        lc = s[0]
        if lc == '"':
            n = 3 if s[:3] == '"""' else 1
        else:
            n = 3 if s[:3] == "'''" else 1
        s = s[n:-n]
        if n == 1:
            s = s.replace('\\'+lc, lc)
        return vertex_and_escape(s)

    json_array = list
    json_pair = tuple
    json_object = dict
    json_cname = v_args(inline=True)(str)
    json_integer = v_args(inline=True)(int)
    json_number = v_args(inline=True)(float)

    json_null = lambda self, _: None
    json_true = lambda self, _: True
    json_false = lambda self, _: False

json_parser = Lark(json_grammar + json_grammar_imports, start='json_value', parser='lalr', lexer='standard')


###############################################################################
# Widget parsing

# RawWidgetData is a simple named tuple for representing the raw data extracted from widget
# definitions in Proofscape-flavored Markdown.
#
# The fields in the RawWidgetData tuple are:
#   type :  the type given in the <type:name> part
#   name:  the name given in the <type:name> part
#   label: the text strictly between the square brackets
#   data:  the full JSON data, including the outside braces
#   lineno: the line number (within the given text) on which the widget defn starts
#
RawWidgetData = namedtuple("RawWidgetData", "type name label data lineno")


class WidgetDataScanner(PfscModuleStringAwareScanner):

    def __init__(self):
        super().__init__()
        self.brace_depth = 1
        self.data_part = None
        self.remainder = None
        self.num_newlines = None

    def state_0(self, c, i):
        if c == "{":
            self.brace_depth += 1
        elif c == "}":
            self.brace_depth -= 1
            if self.brace_depth == 0:
                self.data_part = "{" + self.code[:i+1]
                self.remainder = self.code[i+1:]
                self.num_newlines = self.code.count('\n')
                return self.BREAK, None
        return None, None


WIDGET_RE = re.compile(r'<( *\w+ *):( *[a-zA-Z]\w* *)?>\[([^]]*)\]{')


def split_on_widgets(text, supply_missing_names=True):
    """
    This function is for identifying the widget definitions in a Proofscape annotation.
    Annotations are written in "Proofscape-flavored Markdown", and a widget definition occurring
    in the midst of such will look like this:

        Blah blah, surrounding text <widget_type:widget_name>[label text for widget, *where markdown is okay too*]{
            "here": "you give the data",
            "that": [
                "defines", "the", "widget"
            ],
            "in": {
                "javascript": 1,
                "object": 2,
                "notation": 3
            }
        } and then some more surrounding text, blah blah blah.

    OR, it may begin merely with `<widget_type:>`, omitting the `widget_name`.

    In parsing, we use a depth counter to allow nested braces, and hence arbitrary
    JSON objects for the data part of each widget.

    However, in the name of simplicity we do not allow brackets within widget labels,
    so we do not do depth counting there.

    :param text: The full text of a Proofscape annotation.
    :param supply_missing_names: If True (the default), names are automatically generated and inserted
             for any widgets that lack them. If False, an exception is raised if any widget lacks a name.
    :return: The list of "parts." This is similar to what you would get from re.split, if you
             were able to split on widgets. Thus, the list will always be of odd length, beginning
             and ending with a string. The entries in the list alternate between strings, and
             RawWidgetData named tuples.
    """
    lineno = 1
    # We start by splitting on the `<widget_type:widget_name>[label_text]{` regex.
    chunks = WIDGET_RE.split(text)
    num_chunks = len(chunks)
    assert num_chunks % 4 == 1
    # Number of quadruples to be processed:
    Nquad = int((num_chunks - 1)/4)
    # Initialize return value.
    parts = [chunks[0]]
    lineno += chunks[0].count('\n')
    # Iterate over quadruples.
    names = []
    indices_of_missing_names = []
    for k in range(Nquad):
        a, b, c, remainder = chunks[4*k+1 : 4*k+5]
        widget_type = a.strip()
        widget_label = c.strip()
        widget_name = None
        widget_lineno = lineno
        if b is None:
            # Widget is unnamed.
            if not supply_missing_names:
                # If we're not meant to supply missing names, raise an exception.
                msg = 'Widget missing name: "<%s:>[%s]{..."' % (a, c)
                raise PfscExcep(msg, PECode.WIDGET_MISSING_NAME)
            else:
                # If we _are_ meant to supply missing names, note the index for later.
                indices_of_missing_names.append(k)
        else:
            # Widget is named.
            widget_name = b.strip()
            # Add to list of names.
            names.append(widget_name)
        wds = WidgetDataScanner()
        wds.scan(remainder)
        if wds.brace_depth != 0:
            msg = 'Unterminated widget: "<%s:>[%s]{..."' % (a, c)
            raise PfscExcep(msg)
        # Add the widget part.
        parts.append(RawWidgetData(widget_type, widget_name, widget_label,
                          wds.data_part, widget_lineno))
        # And the "remainder of the remainder" is the next non-widget part.
        parts.append(wds.remainder)
        lineno += wds.num_newlines

    # Do we need to supply missing names?
    if indices_of_missing_names:
        # Yes, there are names to be supplied.
        # All generated names will be of the form `w<n>` where n is a positive integer.
        # First we must determine which such names are already taken. And here we are
        # case-insensitive on the leading `w`.
        used_nums = set()
        for name in names:
            if len(name) >= 2 and name[0] in 'wW' and name[1] != '0':
                try:
                    n = int(name[1:])
                except ValueError:
                    pass
                else:
                    used_nums.add(n)
        def next_num(used):
            n = 1
            while True:
                while n in used: n += 1
                yield n
                n += 1
        for k, n in zip(indices_of_missing_names, next_num(used_nums)):
            rwd = parts[2*k+1]
            parts[2*k+1] = rwd._replace(name='w%s' % n)
    # Return the parts.
    return parts

###############################################################################
# Markdown processing

def render_markdown(text, trusted=False):
    """
    You can use this function to render markdown that doesn't necessarily come
    from an actual annotation, but using the process that is applied to annotation
    text. In this case, you pass no widget lookup since the text is not expected
    to contain any widget stubs. You do get to specify whether the "trusted" or
    "untrusted" policies should be applied while rendering.

    :param text: the markdown to be rendered
    :param trusted: boolean specifying how this text should be treated
    :return: rendered HTML
    """
    return render_anno_markdown(text, {}, trusted=trusted)

DOMAIN_LIST_PATTERN = re.compile(r'\w+\.\w+(\.\w+)*(, *\w+\.\w+(\.\w+)*)*$')

def process_domain_policy(policy):
    if policy in ['0', 0]:
        allow = False
    elif policy in ['1', 1]:
        allow = True
    elif not DOMAIN_LIST_PATTERN.match(policy):
        msg = f"Malformed policy: {policy}"
        raise PfscExcep(msg, PECode.MALFORMED_DOMAIN_POLICY)
    else:
        allow = [d.strip() for d in policy.split(',')]
    return allow

def lookup_link_and_img_policy(trusted):
    repo_type = "TRUSTED" if trusted else "UNTRUSTED"
    link_policy = check_config(f"PFSC_MD_LINKS_FOR_{repo_type}_REPOS")
    img_policy = check_config(f"PFSC_MD_IMGS_FOR_{repo_type}_REPOS")
    allow_links = process_domain_policy(link_policy)
    allow_images = process_domain_policy(img_policy)
    return allow_links, allow_images

def render_anno_markdown(annotext_with_widget_stubs, widget_lookup, trusted=False):
    """
    IMPORTANT: This is THE ONLY function you should use when it is time to turn
      annotation markdown into HTML.

    :param annotext_with_widget_stubs: (string) the annotation text after replacing
      widgets with widget stubs
    :param widget_lookup: (dict) the lookup where we can find the actual Widget
      instance for each stub
    :param trusted: boolean saying whether this text is being treated as coming
      from a trusted source or not. This controls (in combination with the app
      config) how links and images in the markdown will be treated.
    :return: the rendered HTML
    """
    allow_links, allow_images = lookup_link_and_img_policy(trusted)
    renderer = PfscRenderer(widget_lookup, allow_links=allow_links, allow_images=allow_images)
    ve_text = vertex_and_escape(annotext_with_widget_stubs)
    return mistletoe.markdown(ve_text, renderer)

MathToken.precedence = 100

class PfscWidgetStub(SpanToken):
    """
    A widget stub represents a widget with a small, inline element that just gives
    the label text of the widget, and the widget's name, in the form `[label]{name}`.

    This allows us to (1) apply ordinary Markdown rendering recursively on the label part,
    (2) look up a widget based on its name, and (3) pass the rendered label HTML to the
    widget, for it to compute the final HTML that will replace the stub.
    
    The [Mistletoe documentation](https://github.com/miyuchina/mistletoe#a-new-token)
    explains how to extend the lanaguage by defining a new span token, as we've done here.
    """
    # Widget stub format is `[label]{name}`:
    pattern = re.compile(r"\[([^]]*)\]{(\w+)}")
    # Apply markdown processing recursively to the _first_ matching group, i.e. the
    # label in `[label]{name}`:
    parse_inner = True
    parse_group = 1
    # Set high precedence, just under that of MathTokens.
    precedence = 90
    def __init__(self, match_obj):
        super().__init__(match_obj)
        self.widget_name = match_obj.group(2)

class SectionNumberRenderer(HTMLRenderer):
    """
    Automatically add section numbers to headings.

        self.sn_do_number: default False; set True to add section numbers.
        self.sn_top_level: default 1; start numbering on headings of
          this level; must be int from 1 to 6.
    """

    def __init__(self, *extras):
        super().__init__(*extras)
        self.sn_counters = [0] * 6
        self.sn_do_number = False
        self.sn_top_level = 1

    def render_heading(self, token):
        template = '<h{level}>{inner}</h{level}>'
        inner = self.render_inner(token)
        level = token.level
        self.sn_counters[level - 1] += 1
        for i in range(level, 6):
            self.sn_counters[i] = 0
        if self.sn_do_number and level >= self.sn_top_level:
            N = self.sn_counters[self.sn_top_level - 1 : level]
            number = '.'.join(map(str, N))
            inner = f'{number}&nbsp;&nbsp; {inner}'
        return template.format(level=level, inner=inner)


class MathRenderer(SectionNumberRenderer):
    """
    This is our base HTML renderer class. It correctly identifies TeX math modes,
    giving these higher precedence than anything else in Markdown. This is necessary,
    for example, to avoid applying <i> tags in

        foo $a_1, a_2$ bar

    around the text between the two underscore characters in the math mode, as in

        foo $a<i>1, a</i>2$ bar
    """

    def __init__(self, *extras):
        super().__init__(*chain((MathToken,), extras))

    @staticmethod
    def render_math(token):
        return token.content

class PfscRenderer(MathRenderer):
    """
    This class does rendering for Proofscape-flavored Markdown.
    Its extensions over the base HTMLRenderer are as follows:
    
    (1) Correctly identify TeX math modes, giving these higher precedence
    than anything else in Markdown. This is necessary, for example, to avoid
    applying <i> tags in

        foo $a_1, a_2$ bar

    around the text between the two underscore characters in the math mode, as in

        foo $a<i>1, a</i>2$ bar
        
    (2) Identify widget stubs, and replace these with the HTML for the named
    widget. The latter is obtained from a lookup, passed to our constructor.
    
    (3) Mark links with class "external" and target "_blank".
    
    (4) Accept configuration parameters saying whether links are allowed,
    and whether images are allowed.
    
    (5) Blocks all HTML pass-through. This is intended only as a backup, since
    we expect that this renderer will only ever be applied to markdown that has
    already been HTML escaped.
     Notes:
      * [HTML pass-through is part of the CommonMark spec](https://spec.commonmark.org/0.28/#html-blocks)
      * [Some wish it weren't](https://talk.commonmark.org/t/remove-html-passthru-pass-through/1869)

    (6) Since we anticipate receiving only HTML-escaped text, this text will not
    include any angle brackets. Therefore it is impossible for the user to use
    `<URL>` style links. To make up for this lack, we add a special rule (outside
    the MD spec): if you use a link of the form `[](URL)`, i.e. with empty label,
    then we automatically set the URL as the label.
    """

    def __init__(self, widget_lookup, allow_links=False, allow_images=False):
        """
        :param widget_lookup: dict mapping widget names to Widget objects
        :param allow_links: boolean (meaning all or nothing) or list of allowed domains
        :param allow_images: boolean (meaning all or nothing) or list of allowed domains
        """
        super().__init__(PfscWidgetStub)
        self.widget_lookup = widget_lookup
        self.allow_links = allow_links
        self.allow_images = allow_images
    
    def __call__(self, *args, **kwargs):
        """
        This allows us to pass an _instance_ of this class -- rather than the
        class itself -- to `mistletoe.markdown`.
        """
        return self
    
    def render_pfsc_widget_stub(self, token):
        from pfsc.lang.widgets import CtlWidget
        widget_name = token.widget_name
        widget = self.widget_lookup.get(widget_name)
        if widget:
            if isinstance(widget, CtlWidget):
                widget.configure(self)
                return ''
            else:
                inner = self.render_inner(token)
                return widget.writeHTML(label=inner)
        else:
            return f'MISSING_WIDGET:[...]{{{widget_name}}}'

    @staticmethod
    def make_link_external(a_tag):
        i0 = a_tag.find('<a') + 2
        e = ' target="_blank" class="external"'
        a_tag = a_tag[:i0] + e + a_tag[i0:]
        return a_tag

    def render_inline_code(self, token):
        """
        For some reason (maybe just an oversight), Mistletoe's `HTMLRenderer` base
        class uses straight `html.escape` here, like this:
            inner = html.escape(token.children[0].content)
        instead of using its `self.escape_html`. The purpose of the latter is to prevent
        double-escaping. For us, that case definitely arises, since we pre-escape code.
        So we have to override the base class method just to use the right `self.escape_html` here.
        """
        template = '<code>{}</code>'
        inner = self.escape_html(token.children[0].content)
        return template.format(inner)

    def render_block_code(self, token):
        """
        Our reason for overriding the base class's `render_block_code` is exactly the
        same as our reason for overriding `render_inline_code` -- see above. We just need
        to apply `self.escape_html` instead of `html.escape` to the inner content.
        """
        template = '<pre><code{attr}>{inner}</code></pre>'
        if token.language:
            attr = ' class="{}"'.format('language-{}'.format(self.escape_html(token.language)))
        else:
            attr = ''
        inner = self.escape_html(token.children[0].content)
        return template.format(attr=attr, inner=inner)

    # -----------------------------------------------------------------------
    # Block HTML pass-through
    
    def render_html_span(self, token):
        h = super().render_html_span(token)
        h = self.escape_html(h)
        return h

    def render_html_block(self, token):
        h = super().render_html_block(token)
        h = self.escape_html(h)
        return h

    # -----------------------------------------------------------------------
    # Enforce the configured policy.

    @staticmethod
    def url_is_okay(url, allow):
        """
        To be "okay" a URL not only has to match our policy, but also
        must use an accepted scheme, namely `http` or `https`.
        :param url: the URL to be checked
        :param allow: boolean (meaning all domains or none) or list of domain names
        :return: boolean
        """
        from pfsc.checkinput import check_url
        if allow is False:
            return False
        params = {
            'allowed_schemes': ['http', 'https'],
        }
        if isinstance(allow, list):
            params['allowed_netlocs'] = allow
        else:
            assert allow is True
        try:
            checked = check_url('', url, params)
        except PfscExcep as pe:
            if pe.code() == PECode.BAD_URL:
                return False
            else:
                raise pe
        if checked.scheme_ok and (checked.netloc_ok is True or allow is True):
            return True
        return False

    def render_image(self, token):
        h = super().render_image(token)
        url = token.src
        if not self.url_is_okay(url, self.allow_images):
            h = self.escape_html(h)
        return h

    def super_render_link_plus(self, token):
        """
        This is almost an exact copy of the `render_link` method from
        our superclass (hence "super_render_link"), plus a bit more
        (hence "_plus"). The bit more is where we implement our special
        rule that in links of the form `[](url)` i.e. with empty label,
        we automatically set the URL as the label text.
        """
        template = '<a href="{target}"{title}>{inner}</a>'
        target = self.escape_url(token.target)
        if token.title:
            title = ' title="{}"'.format(self.escape_html(token.title))
        else:
            title = ''
        inner = self.render_inner(token)
        if inner == '':
            inner = target
        return template.format(target=target, title=title, inner=inner)

    def render_link(self, token):
        h = self.super_render_link_plus(token)
        h = self.make_link_external(h)
        url = token.target
        if not self.url_is_okay(url, self.allow_links):
            h = self.escape_html(h)
        return h

    def render_auto_link(self, token):
        h = super().render_auto_link(token)
        h = self.make_link_external(h)
        url = token.target
        if not self.url_is_okay(url, self.allow_links):
            h = self.escape_html(h)
        return h

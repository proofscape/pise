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

"""
Language extensions (roles, directives, and node types)
"""

import re

from docutils import nodes
from docutils.parsers.rst.directives import unchanged
from sphinx.errors import SphinxError
from sphinx.util.docutils import SphinxRole, SphinxDirective

from pfsc.sphinx.sphinx_proofscape.chart_widget import SphinxChartWidget
from pfsc.sphinx.sphinx_proofscape.util import process_widget_label
from pfsc.checkinput import check_libpath
from pfsc.excep import PfscExcep


###############################################################################


class chartwidget(nodes.General, nodes.Inline, nodes.TextElement):
    """
    `chartwidget` node type:

    We could probably get away with just using the built-in `reference` node type,
    and either setting `refuri=''` or `refid=''`. However, this means we will get
    one of the classes 'external' or 'internal', and I think we might want to avoid
    possible confusion with actual links to pages.
    """
    pass


def visit_chartwidget_html(self, node):
    # We do want the 'reference' class, which eliminates the underscore text
    # decoration.
    atts = {
        'href': '#',
        'class': 'reference',
    }
    self.body.append(self.starttag(node, 'a', '', **atts))


def depart_chartwidget_html(self, node):
    self.body.append('</a>')


###############################################################################


class PfscDefnsDirective(SphinxDirective):
    """
    The pfsc-defns directive has no visual form; it is just a place to define
    things that control how pfsc widgets are processed.

    At this time there is only one option, `libpaths`, which accepts
    definitions of abbreviations for libpaths.

    Example:
        .. pfsc-defns::
            :libpaths:
                Pf:  gh.toepproj.lit.H.ilbert.ZB.Thm168.Pf
                Thm: gh.toepproj.lit.H.ilbert.ZB.Thm168.Thm
    """

    required_arguments = 0
    has_content = False
    option_spec = {
        "libpaths": unchanged,
    }

    def run(self):
        def parse_list_of_pairs(option_name, key_pattern, value_test):
            given = self.options.get(option_name)
            if not given:
                return {}
            lines = given.split('\n')
            pairs = [[p.strip() for p in line.split(":")] for line in lines]

            # Validate
            def fail(p):
                raise SphinxError(f'In pfsc-defns at {self.get_location()}, bad {option_name} pair: {p}')
            for p in pairs:
                if len(p) != 2:
                    fail(p)
                if not re.match(key_pattern, p[0]):
                    fail(p)
                if not value_test(p[1]):
                    fail(p)

            mapping = {name: value for name, value in pairs}
            return mapping

        def libpath_test(raw):
            try:
                check_libpath('', raw, {})
            except PfscExcep:
                return False
            return True

        lp_defns = parse_list_of_pairs('libpaths', r'\w+$', libpath_test)
        if not hasattr(self.env, 'pfsc_lp_defns_by_docname'):
            self.env.pfsc_lp_defns_by_docname = {}
        self.env.pfsc_lp_defns_by_docname[self.env.docname] = lp_defns

        return []


class PfscChartWidgetBuilder:
    """
    Base class providing functionality required by both the Role and the
    Directive classes for pfsc chart widgets.
    """

    # Making this method static is a way to make my IDE stop complaining about
    # attributes it doesn't think `self` has. When our subclasses invoke this
    # method, they just have to remember to pass `self` as first arg.
    #
    # Ideally, the Sphinx package would define a common superclass to its
    # `SphinxRole` and `SphinxDirective` classes, and then this class could
    # simply be a subclass of that.
    @staticmethod
    def finish_run(self, rawtext, label, widget_fields, widget_name=None):
        vers_defns = self.env.pfsc_vers_defns

        docname = self.env.docname

        if widget_name:
            # Do not allow user-supplied names to begin with underscore.
            if widget_name.startswith('_'):
                raise SphinxError(
                    f'{self.get_location()}: User-supplied widget name may not'
                    ' begin with underscore "_"'
                )
        else:
            # Make a new name of the form `_w\d+`
            wnum = self.env.new_serialno('widget')
            widget_name = f'_w{wnum}'

        lp_defns = getattr(self.env, 'pfsc_lp_defns_by_docname', {})

        src_file, lineno = self.get_source_info()

        widget = SphinxChartWidget(
            self.config, lp_defns, vers_defns,
            docname, src_file, lineno, widget_name,
            **widget_fields
        )

        if not hasattr(self.env, 'pfsc_all_widgets'):
            self.env.pfsc_all_widgets = []
        self.env.pfsc_all_widgets.append(widget)

        node = chartwidget(rawtext, label, classes=[
            'widget', 'chartWidget', widget.write_uid(),
        ])
        return node


class PfscChartRole(SphinxRole, PfscChartWidgetBuilder):
    """
    A simple, inline syntax for minimal chart widgets:
        - The label may optionally begin with a widget name.
        - Must define only a `view` field, in angle brackets.

    Example:

        Let's open :pfsc-chart:`the proof <libpath.of.some.proof>`.
    """

    def run(self):
        M = re.match(f'^(.+)<([^<>]+)>$', self.text)
        if not M:
            msg = self.inliner.reporter.error(
                'Inline Proofscape chart widgets must have the form `LABEL <VIEW>`.',
                line=self.lineno)
            prb = self.inliner.problematic(self.rawtext, self.rawtext, msg)
            return [prb], [msg]
        raw_label, view = [g.strip() for g in M.groups()]
        widget_name, final_label_text = process_widget_label(raw_label)
        node = self.finish_run(self, self.rawtext, final_label_text, {
            'view': view,
        }, widget_name=widget_name)
        return [node], []


class PfscChartDirective(SphinxDirective, PfscChartWidgetBuilder):
    r"""
    Full, directive syntax for chart widgets.

    Label text must be passed via exactly one of two ways: either as the one
    optional argument of the directive, or else via the 'alt' option.
    Note that, if we are defined under an rST substitution,
    (see https://docutils.sourceforge.io/docs/ref/rst/restructuredtext.html#substitution-definitions)
    then the 'alt' option will be automatically set equal to the inner text of
    the substitution.

    Label Rule
    ==========

    The label follows our general rule for widget labels, regarding optional
    definition of a widget name at the beginning. See the docs.

    Example: In

        Let's open the |w001: proof|.

        .. |w001: proof| pfsc-chart::
            :view: Pf
            :color:
                bgB: Pf.A03

    the widget name will be `w001`, while the label text will be "proof".

    Current support
    ===============

    The intention is to support the same options that are supported by chart
    widgets in the classic annotation syntax; however,
        * At this time, support is incomplete.
        * The syntax is somewhat different.
    See below.

    * Each of the `on_board`, `off_board`, `view`, and `select` fields
      can receive only a boxlisting. This means:
        - None of these fields can yet receive any keywords (e.g. "all" for `off_board`).
        - The `view` option cannot yet receive its more advanced format, where
          a whole dictionary is passed.
    * The `color` and `hovercolor` fields are fully supported.

    Syntax
    ======

    Generally, the goal is to take advantage of the possibilities of rST, to make
    a nicer, easier syntax than is available in annotations. In the latter, we
    are constrained by JSON format; here we are not.

    Boxlistings
    -----------

    There is no need for surrounding brackets to make a list, or
    for quotation marks to make a string. Thus, for example, you may write

        :view: Thm.A10, Pf.{A10,A20}

    which is equivalent to `view: ["Thm.A10", "Pf.{A10,A20}"]` in the old,
    annotation syntax.

    Color / Hovercolor
    ------------------

    In the old annotation syntax, this is defined by a dictionary
    of key-value pairs. Because keys must be unique there, we allowed the keys
    to be either color codes, or multipaths.

    Here, you should instead give a listing of `colorCodes: boxlisting` pairs,
    one per line.

    Because there is no unique-key constraint, there is no reason to allow
    multipaths on the left. (For annotations, we decided you might want to be
    able to use the same color spec twice, without having to make a giant RHS,
    so we allowed the option of putting the libpaths on the LHS.)
    Therefore color codes should always be on the left, boxlistings on the right.

    Since multipaths are no longer allowed on the left, there is no longer a
    need to disambiguate between color codes and libpaths, and therefore color
    codes no longer need to be preceded by colons. On the contrary, in rST we
    don't want color codes to begin and end with colons, since this would be
    recognized by syntax highlighters as being a part of rST.

    Therefore color codes should simply be separated by commas.

    As in the old annotation syntax, we support the special `update` color code,
    which applies to the whole directive, and therefore does not need any
    righthand side.

    Example:

        update
        push,bgR,olY,fi0,diGB: libpath.to.node1

    which means:

        Do not clear existing colors; simply add the given settings.
        For node1:
            - push current colors onto node1's color stack
            - set background red
            - set outline yellow
            - clear any existing colors from incoming flow edges
            - give incoming deduction edges a gradient from green to blue

    Note that `update` is meaningless in hovercolor, which is always done as
    an update.

    See the docstring for the ColorManager class in pfsc-moose for more info.

    """

    optional_arguments = 1
    final_argument_whitespace = True
    has_content = False
    option_spec = {
        "on_board": unchanged,
        "off_board": unchanged,
        "view": unchanged,
        "color": unchanged,
        "hovercolor": unchanged,
        "select": unchanged,
        "alt": unchanged,
    }

    def run(self):
        n = len(self.arguments)
        if n > 1:
            raise SphinxError(
                f'{self.get_location()}: too many args.'
                'Widget accepts at most one arg, being the label text.'
            )
        arg_raw = self.arguments[0] if n == 1 else None

        # If we're defined under an rST substitution, then we'll have an 'alt'
        # option, giving the alt text.
        alt_raw = self.options.get('alt')

        if arg_raw and alt_raw:
            raise SphinxError(
                f'{self.get_location()}: double label definition.'
                'Widget label should be defined either via directive argument, '
                'or via alt text, but not both.'
            )

        if not arg_raw and not alt_raw:
            raise SphinxError(
                f'{self.get_location()}: missing label definition.'
                'Widget label should be defined either via directive argument, '
                'or via alt text.'
            )

        raw_label = arg_raw or alt_raw

        widget_name, final_label_text = process_widget_label(raw_label)

        node = self.finish_run(
            self, raw_label, final_label_text, self.options,
            widget_name=widget_name
        )
        return [node]

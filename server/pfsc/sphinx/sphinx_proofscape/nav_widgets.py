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

import re

from docutils import nodes
from docutils.parsers.rst.directives import unchanged
from sphinx.errors import SphinxError
from sphinx.util.docutils import SphinxRole, SphinxDirective

from pfsc.sphinx.sphinx_proofscape.environment import get_pfsc_env
from pfsc.sphinx.sphinx_proofscape.util import process_widget_label
from pfsc.excep import PfscExcep


###############################################################################


class navwidget(nodes.General, nodes.Inline, nodes.TextElement):
    """
    `navwidget` node type: This is for use by any Proofscape widget type that
    wants a mere inline <a> tag as its visual representation.

    We could probably get away with just using the built-in `reference` node type,
    and either setting `refuri=''` or `refid=''`. However, this means we will get
    one of the classes 'external' or 'internal', and I think we might want to avoid
    possible confusion with actual links to pages.
    """
    pass


def visit_navwidget_html(self, node):
    # We do want Sphinx's 'reference' class, which eliminates the underscore
    # text decoration. We also set Proofscape's 'widget' class here.
    atts = {
        'href': '#',
        'class': 'widget reference',
    }
    self.body.append(self.starttag(node, 'a', '', **atts))


def depart_navwidget_html(self, node):
    self.body.append('</a>')


###############################################################################


def finish_run(self, widget_class, html_class, rawtext,
               label, widget_fields, widget_name=None):
    """
    Complete the `run()` method for both the Role and the Directive classes
    for pfsc nav widgets.

    :param self: the ``self`` instance for the calling Directive or Role
    :param widget_class: the widget class to instantiate, e.g. SphinxChartWidget
    :param html_class: string to appear as widget class in HTML, e.g. 'chartWidget'
    :param rawtext: the raw text of the widget
    :param label: the final (processed) label text
    :param widget_fields: dictionary of special fields for the widget type,
        e.g. for SphinxChartWidget this will include the 'view' field, among others
    :param widget_name: optional user-supplied name for the widget
    """
    pfsc_env = get_pfsc_env(self.env)
    vers_defns = pfsc_env.vers_defns

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

    lp_defns = pfsc_env.lp_defns_by_docname

    src_file, lineno = self.get_source_info()

    widget = widget_class(
        self.config, lp_defns, vers_defns,
        docname, src_file, lineno, widget_name,
        **widget_fields
    )

    pfsc_env.all_widgets.append(widget)

    classes = [widget.write_uid(), html_class]

    node = navwidget(rawtext, label, classes=classes)
    return node


class PfscNavWidgetRole(SphinxRole):
    """
    A simple, inline syntax for minimal nav widgets:
        - The label may optionally begin with a widget name.
        - Must define exactly one "target" field, which maps onto an
            appropriate field for each subclass (e.g. the `view` field
            for chart widgets).

    Subclasses must override:
        widget_class (e.g. SphinxChartWidget)
        html_class (e.g. 'chartWidget')
        widget_type_name (e.g. 'chart')
        target_field_name (e.g. 'view')
    """
    widget_class = None
    html_class = ''
    widget_type_name = 'nav'
    target_field_name = 'target'

    def write_error_return_values(self, msg_text):
        msg = self.inliner.reporter.error(msg_text, line=self.lineno)
        prb = self.inliner.problematic(self.rawtext, self.rawtext, msg)
        return [prb], [msg]

    def run(self):
        M = re.match(f'^(.+)<([^<>]+)>$', self.text)
        if not M:
            return self.write_error_return_values(
                f'Inline Proofscape {self.widget_type_name} widgets must have'
                f' the form `LABEL <{self.target_field_name.upper()}>`.'
            )
        raw_label, target = [g.strip() for g in M.groups()]

        try:
            widget_name, final_label_text = process_widget_label(raw_label)
        except PfscExcep:
            return self.write_error_return_values(
                'Widget name (text before colon) malformed.'
                ' Must be valid libpath segment, or empty.'
            )

        fields = {
            self.target_field_name: target,
        }

        node = finish_run(
            self, self.widget_class, self.html_class,
            self.rawtext, final_label_text, fields,
            widget_name=widget_name
        )
        return [node], []


class PfscNavWidgetDirective(SphinxDirective):
    """
    General directive superclass for all Proofscape nav widgets (e.g. chart, doc).
    (Possibly all widgets, not just nav?....)

    Implements processing of one optional arg, and the `alt` option, in order
    to process the widget *label*, including when used with the rST substitution
    pattern.

    Subclasses must override:
        widget_class (e.g. SphinxChartWidget)
        html_class (e.g. 'chartWidget')

    Subclasses should extend:
        option_spec
            For example:
                option_spec = {
                    **PfscNavWidgetDirective.option_spec,
                    "some_special_field_name": unchanged,
                }
    """
    optional_arguments = 1
    final_argument_whitespace = True
    has_content = False

    widget_class = None
    html_class = ''
    option_spec = {
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

        try:
            widget_name, final_label_text = process_widget_label(raw_label)
        except PfscExcep:
            raise SphinxError(
                f'{self.get_location()}: widget name (text before colon) malformed.'
                ' Must be valid libpath segment, or empty.'
            )

        node = finish_run(
            self, self.widget_class, self.html_class,
            raw_label, final_label_text, self.options,
            widget_name=widget_name
        )
        return [node]

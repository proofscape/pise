# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2023 Proofscape Contributors                           #
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

from docutils import nodes
from docutils.parsers.rst.directives import unchanged
from sphinx.util.docutils import SphinxDirective
from sphinx.errors import SphinxError

from pfsc.sphinx.sphinx_proofscape.pages import get_sphinx_page
from pfsc.sphinx.sphinx_proofscape.widgets.util import (
    process_widget_label, check_widget_name,
)
from pfsc.excep import PfscExcep


class pfsc_inline_widget(nodes.General, nodes.Inline, nodes.Element):
    """
    Proofscape widgets like Chart, Pdf, and others whose HTML form is
    an inline element.
    """

    def __init__(self, rawsource='', libpath='', *children, **attributes):
        nodes.Element.__init__(self, rawsource, *children, libpath=libpath, **attributes)


class pfsc_block_widget(nodes.General, nodes.Element):
    """
    Proofscape widgets like Param, Disp, and others whose HTML form is
    a block element.
    """

    def __init__(self, rawsource='', libpath='', *children, **attributes):
        nodes.Element.__init__(self, rawsource, *children, libpath=libpath, **attributes)


def visit_pfsc_widget_html(self, node):
    """
    Each pfsc widget doctree node carries the libpath of the widget. We can
    use this to look up the Widget instance itself, and ask it to generate
    the HTML.
    """
    widgetpath = node['libpath']
    segments = widgetpath.split('.')
    modpath = '.'.join(segments[:-2])
    intramodularpath = '.'.join(segments[-2:])
    module = self.builder.env.proofscape.pfsc_modules[modpath]
    widget = module.get(intramodularpath)
    html = widget.writeHTML(sphinx=True)
    self.body.append(html)


def depart_pfsc_widget_html(self, node):
    """
    Since our abstract pfsc widget doctree nodes don't have any children,
    there's no need to add anything more on departure.
    """
    pass


class PfscOneArgWidgetDirective(SphinxDirective):
    """
    Base class for Proofscape widget directives that accept a single argument,
    where the name, and possibly label, of the widget can be specified.

    Handles both the one optional arg, and the `alt` option, in order
    to process the name/label including when used with the rST substitution
    pattern.

    Subclasses must override:
        widget_class (e.g. ChartWidget -- which class from pfsc.lang.widgets to use)

    Subclasses may override:
        * has_content (set True if the directive has content)
        * content_field_name (string of widget data field under which content should
            be passed to the widget class, when `has_content` is `True`)
        * label_allowed (set False if only a name may be passed)
        * label_required (set True if a label must be given)

    Subclasses should extend:
        option_spec (defines the fields to be passed on to the widget instance)
            Can do it like this:
                option_spec = {
                    **PfscOneArgWidgetDirective.option_spec,
                    "some_special_field_name": unchanged,
                }
    """
    optional_arguments = 1
    final_argument_whitespace = False

    widget_class = None
    label_allowed = True
    label_required = False

    has_content = False
    content_field_name = ''

    option_spec = {
        "alt": unchanged,
    }

    def get_name_and_label(self, label_allowed=True, required=False):
        """
        Get the name/label from the one arg, or from the alt text.

        :param label_allowed: set False if only a name, not a label, may be
            given in this way.
        :param required: set True if a non-empty string must be provided
        """
        n = len(self.arguments)
        if n > 1:
            raise SphinxError(
                f'{self.get_location()}: too many args.'
                'Widget accepts at most one arg, being the name'
                f'{" and/or label text." if label_allowed else "."}'
            )
        arg_raw = self.arguments[0] if n == 1 else None

        # If we're defined under an rST substitution,
        # (see https://docutils.sourceforge.io/docs/ref/rst/restructuredtext.html#substitution-definitions)
        # then we'll have an 'alt' option, giving the alt text.
        alt_raw = self.options.get('alt')

        if arg_raw and alt_raw:
            raise SphinxError(
                f'{self.get_location()}: double label definition.'
                'Widget name/label should be defined either via directive argument, '
                'or via alt text, but not both.'
            )

        if not arg_raw and not alt_raw:
            if required:
                raise SphinxError(
                    f'{self.get_location()}: missing label definition.'
                    'Widget name/label should be defined either via directive argument, '
                    'or via alt text.'
                )
            else:
                return '', '', ''

        raw_text = arg_raw or alt_raw

        if label_allowed:
            try:
                widget_name, label_text = process_widget_label(raw_text)
            except PfscExcep:
                raise SphinxError(
                    f'{self.get_location()}: widget name (text before colon) malformed.'
                    ' Must be valid libpath segment, or empty.'
                )
        else:
            widget_name, label_text = raw_text, ''
            try:
                check_widget_name(widget_name)
            except PfscExcep:
                raise SphinxError(
                    f'{self.get_location()}: widget name malformed.'
                    ' Must be valid libpath segment, or empty.'
                )

        return raw_text, widget_name, label_text

    def run(self):
        raw_text, widget_name, label_text = self.get_name_and_label(
            label_allowed=self.label_allowed, required=self.label_required
        )

        opts = self.options.copy()
        if self.has_content:
            opts[self.content_field_name] = '\n'.join(self.content)

        node = finish_run(
            self, self.widget_class,
            raw_text, label_text, opts,
            widget_name=widget_name
        )
        return [node]


def finish_run(self, widget_class, rawtext,
               label, widget_fields, widget_name=None):
    """
    Complete the `run()` method for widget Role and Directive classes, by
    producing the necessary Widget instance, adding it to the SphinxPage, and
    returning a pfsc widget node for the doctree.

    :param self: the ``self`` instance for the calling Directive or Role
    :param widget_class: the widget class to instantiate, e.g. ChartWidget
    :param rawtext: the raw text of the widget
    :param label: the final (processed) label text
    :param widget_fields: dictionary of special fields for the widget type,
        e.g. for ChartWidget this will include the 'view' field, among others
    :param widget_name: optional user-supplied name for the widget
    """
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

    src_file, lineno = self.get_source_info()

    page = get_sphinx_page(self.env)
    widget = widget_class(widget_name, label, widget_fields, page, lineno)
    page.add_widget(widget)

    widgetpath = widget.getLibpath()
    node = (
        pfsc_inline_widget(rawtext, widgetpath)
        if widget.is_inline else
        pfsc_block_widget(rawtext, widgetpath)
    )

    return node

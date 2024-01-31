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

from pfsc.checkinput import extract_full_key_set
from pfsc.lang.freestrings import build_pfsc_json
from pfsc.sphinx.pages import get_sphinx_page
from pfsc.sphinx.widgets.util import process_widget_subtext
from pfsc.excep import PfscExcep


class pfsc_inline_widget(nodes.General, nodes.Inline, nodes.Element):
    """
    This is a doctree node class for Proofscape widgets like Chart, Doc,
    and others whose HTML form is an inline element.
    """

    def __init__(self, rawsource='', libpath='', *children, **attributes):
        nodes.Element.__init__(self, rawsource, *children, libpath=libpath, **attributes)


class pfsc_block_widget(nodes.General, nodes.Element):
    """
    This is a doctree node class for Proofscape widgets like Param, Disp,
    and others whose HTML form is a block element.
    """

    def __init__(self, rawsource='', libpath='', *children, **attributes):
        nodes.Element.__init__(self, rawsource, *children, libpath=libpath, **attributes)


def visit_pfsc_widget_html(self, node):
    """
    This is the visitor function for the doctree nodes of Proofscape widgets.

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
    Base class for Proofscape widget directives that accept a single argument, being
    the SUBTEXT, i.e. where the name, and possibly label, of the widget can be specified.

    Handles both the one optional arg, and the `alt` option, in order
    to process the SUBTEXT including when used with the rST substitution
    pattern.

    Subclasses must override:
        widget_class (e.g. ChartWidget -- which class from pfsc.lang.widgets to use)

    Subclasses may override:
        * has_content: set True if the directive has content.
        * content_field_name: the name of the widget data field under which content
            should be passed to the widget class, when `has_content` is `True`.
            The entire content value is interpreted as a string, i.e. it is *not*
            passed through the PF-JSON parser, and should *not* be surrounded by
            quotation marks.
        * label_allowed: default True. Set False if *only* a name may be passed.
        * label_required: default False. Set True if a label *must* be given.
    """
    optional_arguments = 1
    final_argument_whitespace = True

    widget_class = None
    label_allowed = True
    label_required = False

    has_content = False
    content_field_name = ''

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls, *args, **kwargs)

        spec = cls.widget_class.generate_arg_spec()
        field_names = extract_full_key_set(spec)
        option_spec = {fn: build_pfsc_json for fn in field_names}
        option_spec['alt'] = unchanged
        if cls.has_content:
            option_spec[cls.content_field_name] = unchanged
        instance.option_spec = option_spec

        return instance

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
                'Widget accepts at most one arg, being the SUBTEXT'
                ', which specifies NAME and/or LABEL.'
            )
        arg_raw = self.arguments[0] if n == 1 else None

        # If we're defined under an rST substitution,
        # (see https://docutils.sourceforge.io/docs/ref/rst/restructuredtext.html#substitution-definitions)
        # then we'll have an 'alt' option, giving the alt text.
        alt_raw = self.options.get('alt')

        if arg_raw and alt_raw:
            raise SphinxError(
                f'{self.get_location()}: double SUBTEXT definition.'
                'Widget SUBTEXT should be defined either via directive argument, '
                'or via alt text, but not both.'
            )

        if not arg_raw and not alt_raw:
            if required:
                raise SphinxError(
                    f'{self.get_location()}: missing SUBTEXT.'
                    'Widget SUBTEXT should be defined either via directive argument, '
                    'or via alt text.'
                )
            else:
                return '', '', ''

        raw_text = arg_raw or alt_raw

        try:
            widget_name, widget_label = process_widget_subtext(raw_text)
        except PfscExcep:
            raise SphinxError(
                f'{self.get_location()}: widget name (text before colon) malformed.'
                ' Must be valid libpath segment, or empty.'
            )

        if widget_label and not label_allowed:
            msg = f'{self.get_location()}: Widget does not accept label'
            if widget_name:
                msg += ', but both name and label were given.'
            else:
                msg += ', but label was given. To set a name, put colon after name.'

            raise SphinxError(msg)

        return raw_text, widget_name, widget_label

    def run(self):
        raw_text, widget_name, widget_label = self.get_name_and_label(
            label_allowed=self.label_allowed, required=self.label_required
        )

        opts = self.options.copy()
        if self.has_content:
            opts[self.content_field_name] = '\n'.join(self.content)

        node = finish_run(
            self, self.widget_class,
            raw_text, widget_label, opts,
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

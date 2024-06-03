# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2024 Proofscape Contributors                           #
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

from docutils.parsers.rst.directives import unchanged
from docutils.utils import ExtensionOptionError
from lark.exceptions import LarkError

from pfsc.checkinput import extract_full_key_set
from pfsc.lang.freestrings import build_pfsc_json
from pfsc.constants import PFSC_SPHINX_CRIT_ERR_MARKER

from .base import (
    pfsc_block_widget, pfsc_inline_widget,
    visit_pfsc_widget_html, depart_pfsc_widget_html,
)

from .widget_types import (
    PfscChartRole, PfscChartDirective,
    PfscCtlWidgetDirective,
    PfscDocWidgetRole, PfscDocWidgetDirective,
    PfscDispWidgetDirective, PfscParamWidgetDirective,
    PfscQnAWidgetDirective,
)


widget_types_and_classes = (
    ('chart', PfscChartRole, PfscChartDirective),
    ('ctl', None, PfscCtlWidgetDirective),
    ('doc', PfscDocWidgetRole, PfscDocWidgetDirective),
    ('disp', None, PfscDispWidgetDirective),
    ('param', None, PfscParamWidgetDirective),
    ('qna', None, PfscQnAWidgetDirective),
)


def generic_data_field_converter(text):
    """
    Generic converter function to be applied to the values of options in widget
    directives.

    This is applied by `docutils`, so we need to raise its `ExtensionOptionError`
    in case of any parsing problems, in order to get an informative error message,
    including the location (filename and lineno) where the error occurred.

    Note: This only results in a "warning" as Sphinx sees it, so, for the build
    to actually be interrupted and the user to see an error message through PISE,
    we have to add the `PFSC_SPHINX_CRIT_ERR_MARKER` to the error message.

    See also:
        pfsc.sphinx.errors.ProofscapeWarningIsErrorFilter
        pfsc.build.Builder.build_sphinx_doc()
        docutils.parsers.rst.states.Body.parse_extension_options()
    """
    try:
        pf_json = build_pfsc_json(text)
    except LarkError as e:
        msg = f'{PFSC_SPHINX_CRIT_ERR_MARKER}: Error parsing PF-JSON: {e}'
        raise ExtensionOptionError(msg)
    return pf_json


def monkey_patch_option_specs():
    """
    The classes we use to make widgets available as directives in Sphinx pages
    have to define all the data field names in their `option_spec` class property.

    But we want to define the data fields for each widget type in exactly one place,
    and that place is the `generate_arg_spec()` class method of each Widget subclass,
    as defined in `pfsc.lang.widgets`, not here under `pfsc.sphinx.widgets`.

    Therefore we use this function to monkey patch the definition of the
    `option_spec` property into each of our widget directive classes.

    Note: Unfortunately, alternative approaches such as attempting to
    define `option_spec` in `PfscOneArgWidgetDirective.__new__()` will not
    work, because `docutils` uses the directive class itself, not an instance
    thereof. See `docutils.parsers.rst.states.Body.parse_directive_block()`,
    which starts with:

        option_spec = directive.option_spec

    """
    for _, _, cls in widget_types_and_classes:
        spec = cls.widget_class.generate_arg_spec()
        field_names = extract_full_key_set(spec)

        # Because field names in rST are case-insensitive,
        #     https://docutils.sourceforge.io/docs/ref/rst/restructuredtext.html#field-lists
        # and because of the particular way in which they are checked (at least in docutils v0.19)
        #     See the `docutils.utils.extract_extension_options()` function.
        # we have to use `fn.lower()` for the keys in the `option_spec`.
        # In order to be able to reconstruct the desired casing later, we also build
        # and store a `proper_casing` dictionary.
        option_spec = {fn.lower(): generic_data_field_converter for fn in field_names}
        proper_casing = {fn.lower(): fn for fn in field_names}

        # The 'alt' option is a special one, where docutils hands us the value of
        # the substitution, when the substitution pattern was used.
        option_spec['alt'] = unchanged

        # For those directives that do have a content field, this is the one exception
        # to the rule that the value must be valid PF-JSON; in this case, we interpret
        # the whole thing as a string, and you do NOT put quotation marks around it.
        if cls.has_content:
            option_spec[cls.content_field_name] = unchanged

        cls.option_spec = option_spec
        cls.proper_casing = proper_casing


monkey_patch_option_specs()

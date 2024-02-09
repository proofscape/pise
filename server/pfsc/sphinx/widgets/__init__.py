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

from docutils.parsers.rst.directives import unchanged
from pfsc.checkinput import extract_full_key_set
from pfsc.lang.freestrings import build_pfsc_json

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
        option_spec = {fn: build_pfsc_json for fn in field_names}
        option_spec['alt'] = unchanged
        if cls.has_content:
            option_spec[cls.content_field_name] = unchanged
        cls.option_spec = option_spec


monkey_patch_option_specs()

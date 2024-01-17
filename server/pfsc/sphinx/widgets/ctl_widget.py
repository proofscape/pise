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

from pfsc.lang.freestrings import build_pfsc_json
from pfsc.lang.widgets import CtlWidget, SUPPORTED_CTL_WIDGET_DEFAULT_FIELDS
from pfsc.sphinx.widgets.base import PfscOneArgWidgetDirective


class PfscCtlWidgetDirective(PfscOneArgWidgetDirective):
    """
    Directive for Proofscape "Ctl" widgets

    Accepts one argument, of the form `NAME:` (SUBTEXT with no label).
    """
    widget_class = CtlWidget

    label_allowed = False

    option_spec = {
        **PfscOneArgWidgetDirective.option_spec,
        # Not declaring 'section_numbers' as a field, since (for now at least?) that is
        # only a way of controlling Markdown rendering in annotations.
        **{field_name: build_pfsc_json for field_name in SUPPORTED_CTL_WIDGET_DEFAULT_FIELDS}
    }

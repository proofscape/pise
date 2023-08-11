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

from sphinx.util.docutils import SphinxRole

from pfsc.sphinx.sphinx_proofscape.widgets.base import (
    finish_run, PfscOneArgWidgetDirective,
)
from pfsc.sphinx.sphinx_proofscape.widgets.util import process_widget_label
from pfsc.excep import PfscExcep


class PfscNavWidgetRole(SphinxRole):
    """
    A simple, inline syntax for minimal nav widgets:
        - The label may optionally begin with a widget name.
        - Must define exactly one "target" field, which maps onto an
            appropriate field for each subclass (e.g. the `view` field
            for chart widgets).

    Subclasses must override:
        widget_class (e.g. ChartWidget -- which class from pfsc.lang.widgets to use)
        widget_type_name (e.g. 'chart' -- appears in error messages)
        target_field_name (e.g. 'view' -- key under which target will be passed on to widget instance)
    """
    widget_class = None
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
            self, self.widget_class,
            self.rawtext, final_label_text, fields,
            widget_name=widget_name
        )
        return [node], []

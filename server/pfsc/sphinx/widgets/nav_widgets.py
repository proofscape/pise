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

import re

from lark.exceptions import LarkError
from sphinx.util.docutils import SphinxRole

from pfsc.lang.freestrings import build_pfsc_json
from pfsc.lang.widgets import WIDGET_TYPE_TO_CLASS
from pfsc.sphinx.widgets.base import finish_run
from pfsc.sphinx.widgets.util import process_widget_subtext
from pfsc.excep import PfscExcep


class PfscNavWidgetRole(SphinxRole):
    """
    A simple, inline syntax for minimal nav widgets:
        - The SUBTEXT may optionally begin with a widget NAME.
        - Must define exactly one "target" field, which maps onto an
            appropriate field for each subclass (e.g. the `view` field
            for chart widgets).

    Subclasses must override:
        widget_class (e.g. ChartWidget -- which class from pfsc.lang.widgets to use)
        target_field_name (e.g. 'view' -- key under which target will be passed on to widget instance)
    """
    widget_class = None
    target_field_name = 'target'

    @property
    def widget_type_name(self):
        name = 'nav'
        for uppercase_name, widget_class in WIDGET_TYPE_TO_CLASS.items():
            if widget_class is self.widget_class:
                name = uppercase_name.lower()
                break
        return name

    def write_error_return_values(self, msg_text):
        msg = self.inliner.reporter.error(msg_text, line=self.lineno)
        prb = self.inliner.problematic(self.rawtext, self.rawtext, msg)
        return [prb], [msg]

    def run(self):
        M = re.match(f'^(.+)<([^<>]+)>$', self.text)
        if not M:
            return self.write_error_return_values(
                f'Inline Proofscape {self.widget_type_name} widgets must have'
                f' the form `SUBTEXT <{self.target_field_name.upper()}>`.'
            )
        subtext, raw_target = [g.strip() for g in M.groups()]

        try:
            widget_name, widget_label = process_widget_subtext(subtext)
        except PfscExcep:
            return self.write_error_return_values(
                'Widget name (text before colon in subtext) malformed.'
                ' Must be valid libpath segment, or empty.'
            )

        try:
            target = build_pfsc_json(raw_target)
        except (PfscExcep, LarkError) as e:
            msg = f'The "{self.target_field_name}" field is malformed.\n{e}'
            return self.write_error_return_values(msg)

        fields = {
            self.target_field_name: target,
        }

        node = finish_run(
            self, self.widget_class,
            self.rawtext, widget_label, fields,
            widget_name=widget_name
        )
        return [node], []

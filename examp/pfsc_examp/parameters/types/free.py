# --------------------------------------------------------------------------- #
#   Copyright (c) 2018-2023 Proofscape Contributors                           #
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

import jinja2

from pfsc_examp.calculate import calculate
from pfsc_examp.parameters.base import Parameter
from pfsc_examp.parse.display import displaylang_processor


class Free_Param(Parameter):
    """
    Free parameter

    ptype: "Free"

    Value type: any

    Default: str
        Any (multi-line) DisplayLang code

    Descrip: str
        Any (multi-line) DisplayLang code, returning html

    Args:
        None
    """

    arg_spec = {}

    def __init__(self, parent, name=None,
                 default=None, tex=None, descrip=None, params=None,
                 args=None, last_raw=None, **other):
        super().__init__(parent, name, default, tex, descrip, params, args, last_raw)
        self.descrip_html = None

    def auto_descrip(self, include_value=True, editable=True):
        return self.descrip_html

    def auto_build(self):
        raw = self.default
        return self.build_from_raw(raw)

    def build_from_raw(self, raw):
        raw = str(raw)  # Ensure that we have a string
        code = '\n'.join([raw, self.descrip])
        # TODO:
        #  set up existing_values based on imported params
        existing_values = {}
        html, exports = calculate(
            displaylang_processor.process,
            code, existing_values
        )
        # TODO:
        #  use args to do sth smarter with the exports
        self.descrip_html = html
        return exports[0]

    def write_chooser_widget(self):
        context = {
            'name': self.name,
            'descrip': self.auto_descrip(),
            'current_value': self.raw,
        }
        return free_widget_template.render(context)


free_widget_template = jinja2.Template("""
<div class="chooser free_chooser" name="{{ name }}">
    <div class="heading">{{ descrip }}</div>
    <div class="error_display"></div>
    <code class="displayCode">{{ current_value }}</code>
</div>
""")

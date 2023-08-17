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

from pfsc.lang.widgets import QnAWidget
from pfsc.sphinx.sphinx_proofscape.widgets.base import PfscOneArgWidgetDirective


class PfscQnAWidgetDirective(PfscOneArgWidgetDirective):
    """
    Directive for Proofscape "Q&A" widgets

    Accepts one argument, which is the name of the widget.
    (It has no label, so you do not need a colon after the name.)
    """
    widget_class = QnAWidget

    label_allowed = False

    option_spec = {
        **PfscOneArgWidgetDirective.option_spec,
        'question': unchanged,
        'answer': unchanged,
    }

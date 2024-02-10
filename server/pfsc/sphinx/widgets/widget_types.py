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

from pfsc.lang.widgets import (
    ChartWidget, CtlWidget, DocWidget,
    ParamWidget, DispWidget, QnAWidget,
)
from pfsc.sphinx.widgets.nav_widgets import PfscNavWidgetRole
from pfsc.sphinx.widgets.base import PfscOneArgWidgetDirective


class PfscChartRole(PfscNavWidgetRole):
    widget_class = ChartWidget
    target_field_name = 'view'


class PfscChartDirective(PfscOneArgWidgetDirective):
    widget_class = ChartWidget
    label_required = True


class PfscCtlWidgetDirective(PfscOneArgWidgetDirective):
    widget_class = CtlWidget
    label_allowed = False


class PfscDocWidgetRole(PfscNavWidgetRole):
    widget_class = DocWidget
    target_field_name = 'sel'


class PfscDocWidgetDirective(PfscOneArgWidgetDirective):
    widget_class = DocWidget
    label_required = True


class PfscParamWidgetDirective(PfscOneArgWidgetDirective):
    widget_class = ParamWidget
    label_allowed = False


class PfscDispWidgetDirective(PfscOneArgWidgetDirective):
    widget_class = DispWidget
    label_allowed = False
    has_content = True
    content_field_name = 'build'


class PfscQnAWidgetDirective(PfscOneArgWidgetDirective):
    # No CONTENT_FIELD. It is tempting to make either the question or the answer the
    # CONTENT_FIELD, but I see no reason to prefer one of them. Sometimes you write a
    # long question that has a short answer; sometimes you write a short question that
    # has a long answer. Given this ambiguity, I feel the best design is the symmetrical
    # one. So, both question and answer are passed in the form of (required) "options".
    widget_class = QnAWidget
    label_allowed = False

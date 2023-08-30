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

from pfsc.checkinput import IType, check_cdlist, check_json
from pfsc.lang.widgets import ParamWidget, DispWidget
from pfsc.sphinx.widgets.base import PfscOneArgWidgetDirective
from pfsc.sphinx.widgets.util import parse_dict_lines


class PfscParamWidgetDirective(PfscOneArgWidgetDirective):
    """
    Directive for Proofscape parameter or "param" widgets.

    Accepts one argument, which is the name of the widget.
    (It has no label, so you do not need a colon after the name.)
    """
    widget_class = ParamWidget

    label_allowed = False

    option_spec = {
        **PfscOneArgWidgetDirective.option_spec,
        'ptype': unchanged,
        'context': unchanged,
        'name': unchanged,
        'tex': unchanged,
        'default': lambda t: check_json('default', t, {}),
        'args': lambda t: parse_dict_lines(
            t, {'type': IType.STR}, {'type': IType.JSON}, 'args'
        ),
        'import': lambda t: parse_dict_lines(
            t, {'type': IType.STR},
            {'type': IType.LIBPATH, 'short_okay': True},
            'import'
        ),
    }


class PfscDispWidgetDirective(PfscOneArgWidgetDirective):
    """
    Directive for Proofscape display or "disp" widgets.

    Accepts one argument, which is the name of the widget.
    (It has no label, so you do not need a colon after the name.)
    """
    widget_class = DispWidget

    label_allowed = False

    has_content = True
    content_field_name = 'build'

    option_spec = {
        **PfscOneArgWidgetDirective.option_spec,
        'import': lambda t: parse_dict_lines(
            t, {'type': IType.STR}, {'type': IType.STR}, 'import'
        ),
        'export': lambda t: check_cdlist('export', t, {
            'itemtype': {
                'type': IType.STR,
            },
        }),
    }

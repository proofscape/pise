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

from sympy import Integer
from sympy.ntheory import is_primitive_root, primitive_root
import jinja2

from pfsc_examp.calculate import calculate
from pfsc_examp.canon_arithmeticus import all_prim_res_under_100, one_prim_res_under_1000
from pfsc_examp.parameters.base import Parameter
from pfsc_examp.excep import MalformedParamRawValue


class PrimRes_Param(Parameter):
    """
    Primitive residue in elementary number theory

    ptype: "PrimRes"

    Value type: Integer

    Default: int

    Args:
        Required:
            m: int
                The modulus.
        Optional: None.
    """

    arg_spec = {
        "REQ": {
            'm': {
                'type': Integer,
            },
        },
    }

    def __init__(self, parent, name=None,
                 default=None, tex=None, descrip=None, params=None,
                 args=None, last_raw=None, **other):
        super().__init__(parent, name, default, tex, descrip, params, args, last_raw)
        self.m = None
        # Depending on how big the modulus m is, we might store a list of all
        # of its primitive residues, or we might just store one primitive residue;
        # we might not store either of these if m is too large.
        self.all_options = []
        self.one_option = None

    def prebuild(self):
        # Read args
        self.m = self.resolved_args['m']
        m = self.m.value
        # If the modulus m is < 100, we can supply the set of all possible values
        # for this primitive residue.
        # If 100 < m < 1000 we can offer one value, and give the user a text box
        # in which to set a different value.
        # Otherwise we offer no suggestion.
        if m < 100:
            self.all_options = all_prim_res_under_100.get(m, [])
        elif m < 1000:
            self.one_option = one_prim_res_under_1000.get(m, None)

    def auto_descrip(self, include_value=True, editable=True):
        return '%s a primitive residue mod $%s$' % (
            self.write_name_and_value(include_value, editable),
            self.m
        )

    def auto_build(self):
        if self.one_option:
            return self.one_option
        elif self.all_options:
            return self.all_options[0]
        else:
            return calculate(primitive_root, self.m.value)

    def build_from_raw(self, raw):
        n = Integer(self.check_int(raw))
        m = self.m.value
        def reject():
            msg = f'{n} is not a generator mod {m}.'
            raise MalformedParamRawValue(msg, self)
        # If m < 100 then we can check directly from the list of all generators.
        if m < 100:
            if n % m not in self.all_options:
                reject()
            return n
        else:
            if not calculate(is_primitive_root, n, m):
                reject()
            return n

    def write_chooser_widget(self):
        ready_options = []
        free_option = True
        if self.all_options:
            ready_options = self.all_options
            free_option = False
        elif self.one_option:
            ready_options = [self.one_option]
        context = {
            'name': self.name,
            'descrip': self.auto_descrip(),
            'selected_res': self.value,
            'ready_options': ready_options,
            'free_option': free_option,
        }
        return prim_res_chooser_widget_template.render(context)

prim_res_chooser_widget_template = jinja2.Template("""
<div class="chooser radio_panel_chooser prim_res_chooser" name="{{ name }}">
    <div class="heading">{{ descrip }}</div>
    <div class="error_display"></div>
    {# #}
    {% if ready_options %}
        {# Buttons for ready-made options #}
        <div class="radio_panel">
            {% for r in ready_options %}
                {% if r == selected_res %}
                    <div tabindex="0" value="{{ r }}" class="radio_panel_button rpb_selected">{{ r }}</div>
                {% else %}
                    <div tabindex="0" value="{{ r }}" class="radio_panel_button">{{ r }}</div>
                {% endif %}
            {% endfor %}
        </div>
    {% endif %}
    {# #}
    {% if free_option %}
        {# Text field for any other values #}
        {% if selected_res not in ready_options %}
            <input class="textfield" type="text" placeholder="Other" value="{{selected_res}}"/>
        {% else %}
            <input class="textfield" type="text" placeholder="Other"/>
        {% endif %}
    {% endif %}
</div>
""")

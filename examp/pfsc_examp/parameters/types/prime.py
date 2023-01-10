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

from sympy.core.numbers import Integer
from sympy.logic.boolalg import BooleanAtom
from sympy.ntheory.primetest import isprime
import jinja2

from pfsc_examp.calculate import calculate
from pfsc_examp.canon_arithmeticus import primes_under_100, three_digit_primes
from pfsc_examp.parameters.base import Parameter
from pfsc_examp.contexts import ContextNames
from pfsc_examp.excep import MalformedParamRawValue


class Prime_Param(Parameter):
    """
    Prime rational integer.

    ptype: "Prime"

    Value type: Integer

    Default: int

    Args:
      Required: None.
      Optional:
        odd: boolean, default=False
            True if you require that it be an odd prime
        chooser_upper_bound: int
            If positive, do not display primes larger than this in
            the chooser HTML. Note: This is not a *mathematical* constraint;
            you are not saying that the prime actually needs to be bounded
            for any mathematical reason. You are only saying that you want
            to limit the set of primes "on offer". So the reasons for the limit
            are practical ones, relating to computation time, or surveyability
            of displays.
    """

    arg_spec = {
        "OPT": {
            'odd': {
                'type': BooleanAtom,
                'default_raw': False,
            },
            'chooser_upper_bound': {
                'type': Integer,
                'default_raw': 0,
            },
        }
    }

    def __init__(self, parent, name=None,
                 default=None, tex=None, descrip=None, params=None,
                 args=None, last_raw=None, **other):
        super().__init__(parent, name, default, tex, descrip, params, args, last_raw)
        self.odd_only = None
        self.chooser_upper_bound = None

    def prebuild(self):
        self.odd_only = self.resolved_args['odd']
        self.chooser_upper_bound = self.resolved_args['chooser_upper_bound']

    def auto_build(self):
        raw = 3 if self.odd_only.value else 2
        return self.build_from_raw(raw)

    def build_from_raw(self, raw):
        n = self.check_int(raw)
        if not calculate(isprime, n):
            raise MalformedParamRawValue('Must be prime.', self)
        if self.odd_only.value and n in [2, -2]:
            raise MalformedParamRawValue('Prime must be odd.', self)
        return Integer(n)

    def auto_descrip(self, include_value=True, editable=True):
        symbolic = self.write_name_and_value(include_value, editable)
        noun = 'prime number'
        if self.parent.context == ContextNames.AlgNT:
            noun = 'rational prime'
        return f"{symbolic} a{'n odd' if self.odd_only.value else ''} {noun}"

    def write_chooser_widget(self):
        # Booleans to control display of widgets:
        show_three_digit_primes = True
        show_free_box = True
        # Prepare our list of primes under 100 (possibly modified):
        pu100 = primes_under_100[1 if self.odd_only.value else 0:]
        if 0 < self.chooser_upper_bound.value <= 100:
            show_three_digit_primes = False
            show_free_box = False
            pu100 = filter(lambda p: p <= self.chooser_upper_bound.value, pu100)
        # Prepare our list of three-digit primes (possibly modified):
        tdp = None
        if show_three_digit_primes:
            tdp = three_digit_primes[:]
            if 100 < self.chooser_upper_bound.value <= 1000:
                show_free_box = False
                tdp = filter(lambda p: p <= self.chooser_upper_bound.value, tdp)
        context = {
            'name': self.name,
            'selected_prime': self.value,
            'descrip': self.auto_descrip(),
            'primes_under_100': pu100,
            'three_digit_primes': tdp,
            'show_tdp': show_three_digit_primes,
            'show_free_box': show_free_box,
        }
        return prime_chooser_widget_template.render(context)


prime_chooser_widget_template = jinja2.Template("""
<div class="chooser radio_panel_chooser prime_chooser" name="{{ name }}">
    <div class="heading">{{ descrip }}</div>
    <div class="error_display"></div>
    {# #}
    {# Buttons for the primes under 100 #}
    <div class="radio_panel">
        {% for p in primes_under_100 %}
            {% if p == selected_prime %}
                <div tabindex="0" value="{{ p }}" class="radio_panel_button rpb_selected">{{ p }}</div>
            {% else %}
                <div tabindex="0" value="{{ p }}" class="radio_panel_button">{{ p }}</div>
            {% endif %}
        {% endfor %}
    </div>
    {# #}
    {% if show_tdp %}
        {# Dropdown for the three-digit primes #}
        <select class="dd">
            <option class="dd_null_opt" value="">3-digit primes</option>
            {% for p in three_digit_primes %}
                {% if p == selected_prime %}
                    <option class="dd_opt" value="{{p}}" selected="selected">{{p}}</option>
                {% else %}
                    <option class="dd_opt" value="{{p}}">{{p}}</option>
                {% endif %}
            {% endfor %}
        </select>
    {% endif %}
    {# #}
    {% if show_free_box %}
        {# Text field for anything larger #}
        {% if selected_prime > 1000 %}
            <input class="textfield" type="text" placeholder="Other prime" value="{{selected_prime}}"/>
        {% else %}
            <input class="textfield" type="text" placeholder="Other prime"/>
        {% endif %}
    {% endif %}
</div>
""")

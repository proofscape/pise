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

from sympy.core.numbers import igcd, Integer
import jinja2

from pfsc_examp.calculate import calculate
from pfsc_examp.parameters.base import Parameter, ParametricValued, DependencyType
from pfsc_examp.contexts import ContextNames
from pfsc_examp.excep import MalformedParamRawValue


class Integer_Param(Parameter):
    """
    Rational integer.

    ptype: "Integer"

    Value type: Integer

    Default: int

    Args:
      Required: None.
      Optional:
        coprime_to: int
            Must be coprime to this.
        dividing: int
            Must divide this.
        gt: int
            Must be greater than this.
        lt: int
            Must be less than this.
    """
    
    arg_spec = {
        "OPT": {
            'coprime_to': {
                'type': Integer,
            },
            'dividing': {
                'type': Integer,
            },
            'gt': {
                'type': Integer,
            },
            'lt': {
                'type': Integer,
            },
        }
    }

    def __init__(self, parent, name=None,
                 default=None, tex=None, descrip=None, params=None,
                 args=None, last_raw=None, **other):
        super().__init__(parent, name, default, tex, descrip, params, args, last_raw)

    def get_name_for_extra(self, predicate_name):
        a = self.resolved_args.get(predicate_name, None)
        if a is None:
            return None
        else:
            return str(a)

    def auto_build(self):
        # We're not writing a sat solver!
        # If you defined conditions, you should provide a default value that
        # satisfies them.
        return self.build_from_raw(0)

    def build_from_raw(self, raw):
        n = self.check_int(raw)

        # Note: when formatting error messages, we use the _name_ of the parameter
        # to which this one is supposed to relate in a given way; not the current
        # value. This is more informative for the user.

        D = self.get_arg_value('dividing')
        C = self.get_arg_value('coprime_to')
        G = self.get_arg_value('gt')
        L = self.get_arg_value('lt')

        D_name = self.get_name_for_extra('dividing')
        C_name = self.get_name_for_extra('coprime_to')
        G_name = self.get_name_for_extra('gt')
        L_name = self.get_name_for_extra('lt')

        if D is not None and D % n != 0:
            raise MalformedParamRawValue(f'Must divide ${D_name}$.', self)

        if C is not None and calculate(igcd, C, n) != 1:
            raise MalformedParamRawValue(f'Must be coprime to ${C_name}$.', self)

        if G is not None and not n > G:
            raise MalformedParamRawValue(f'Must be greater than ${G_name}$.', self)

        if L is not None and not n < L:
            raise MalformedParamRawValue(f'Must be less than ${L_name}$.', self)

        return Integer(n)

    def auto_descrip(self, include_value=True, editable=True):
        # Start by getting any optional, related parameters.
        dividing_str = self.get_name_for_extra('dividing')
        coprime_str = self.get_name_for_extra('coprime_to')
        lb_str = self.get_name_for_extra('gt')
        ub_str = self.get_name_for_extra('lt')

        # Build the symbolic part
        symbolic_part = self.write_name_and_value(include_value=include_value, editable=editable)
        if not include_value:
            # If we do not want to include the value, then the symbolic
            # section can look like one of the following:
            #   $n$
            #   $n > l$
            #   $n < u$
            #   $l < n < u$
            if lb_str and not ub_str:
                symbolic_part += f' &gt; {lb_str}'
            elif ub_str and not lb_str:
                symbolic_part += f' &lt; {ub_str}'
            elif lb_str and ub_str:
                symbolic_part = f'{lb_str} $lt; {symbolic_part} &lt; {ub_str}'
            symbolic_part = f'${symbolic_part}$'

        # Set noun phrase according to context.
        noun_phrase = ('a rational integer'
                       if self.parent.context == ContextNames.AlgNT
                       else 'an integer')

        # Prepositional phrases:
        prep = []
        if include_value:
            # If we included the value, then gt/lt expressions need to go here.
            if lb_str is not None:
                prep.append(f'greater than ${lb_str}$')
            if ub_str is not None:
                prep.append(f'less than ${ub_str}$')
        if coprime_str:
            prep.append(f'coprime to ${coprime_str}$')
        if dividing_str:
            prep.append(f'dividing ${dividing_str}$')

        # Build the final phrase
        final = symbolic_part + ' ' + noun_phrase
        N = len(prep)
        for i, p in enumerate(prep):
            final += ', '
            if 0 < i == N - 1:
                final += 'and '
            final += p
        return final

    def write_chooser_widget(self):
        return write_int_chooser_widget(
            self.name,
            self.auto_descrip(),
            current_value=self.value
        )


int_chooser_widget_template = jinja2.Template("""
<div class="chooser int_chooser" name="{{ name }}">
    <div class="heading">{{ descrip }}</div>
    <div class="error_display"></div>
    <input class="textfield" type="text" placeholder="Integer" value="{{current_value}}"/>
</div>
""")


def write_int_chooser_widget(name, descrip, current_value):
    context = {}
    context.update(locals())
    return int_chooser_widget_template.render(context)


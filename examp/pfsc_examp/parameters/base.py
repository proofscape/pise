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
from markupsafe import Markup

from sympy import S as SS
from sympy import Symbol, latex

from pfsc_examp.parse.algebraic import safe_algebraic_func_str_to_sympy
from pfsc_examp.parse.excep import ParsingExcep
from pfsc_examp.excep import (
    MissingParamArgError,
    MissingParameterError,
    MalformedParamRawValue,
    UnexpectedParamArgError,
    UnexpectedParamArgTypeError,
    MissingName,
    UnresolvedParamArgError,
    MissingParamArgType,
)
from pfsc_examp.util import adapt
from pfsc_util.imports import from_import


class DependencyType:
    """
    Dependency types let us classify the ways in which a parameter Q may
    depend on another parameter P.

    FUNC: ("functional"). This means that when P changes, then Q should request
      a whole new inner HTML, because the whole set of options has changed, and
      we want to present the options in a new way. For example, Q might be an
      ideal prime lying over the rational prime P.

    COND: ("conditional"). This means that when P changes, the current choice
      for Q may become invalid, since Q is supposed to satisfy a certain condition
      w.r.t. P (e.g. "greater than"). However, Q doesn't need to request a whole
      new inner HTML, because we do not want to change the way we represent or
      offer the set of possibilities. E.g. user may enter any integer, and they
      just need to choose one that is greater than P.

    INDIRECT: We use this in order to indicate, in a dependency closure, which
      params were included not as direct dependencies, but instead as a part of
      the recursive closure computation.
    """
    FUNC = "FUNC"
    COND = "COND"
    INDIRECT = "INDIRECT"


class Valued:
    """
    Abstract base class for objects with a `.value` proeprty.
    """

    @property
    def value(self):
        return self._value


class NonParamValue(Valued):
    """
    Simple wrapper class for values that are not dependent on `Parameter`s.
    The internal `self._value` should be an instance of some SymPy class.
    """

    def __init__(self, value):
        self._value = value

    def __str__(self):
        return latex(self._value)


class ParametricValued(Valued):
    """
    Superclass of any `Valued` that is parametric, i.e. whose value depends
    on the value(s) of one or more Parameters.
    """

    def get_libpaths(self):
        """
        @return: iterable of all libpaths of parameters involved in this object.
        """
        raise NotImplementedError


class ParametricExpression(ParametricValued):
    """
    For SymPy expressions containing symbols that stand for Parameters.
    """

    def __init__(self, expr, params, require_saturated=False):
        """
        @param expr: a SymPy Expr
        @param params: dict mapping names (strings) to Parameter instances.
          Each Symbol occuring in `expr` whose `.name` is a key in this dict
          will be replaced by the value of that Parameter, when the value of
          this ParametricExpression is requested.
        @param require_saturated: If True, and if not every symbol name occurs
          as a parameter name, then raise an exception.
        """
        self.expr = expr
        self.params = params

        self.symbols = {a for a in expr.atoms() if isinstance(a, Symbol)}
        self.names = [a.name for a in self.symbols]

        if require_saturated:
            for a in self.names:
                if a not in self.params:
                    msg = f'Expression contains symbol `{a}` corresp. to no parameter'
                    msg += ', but is required to be saturated.'
                    raise MissingParameterError(msg)

        self.orig_names = {s: self.params[s.name].getTeX(as_name=True)
                           for s in self.symbols if s.name in self.params}

    def __str__(self):
        return latex(self.expr, symbol_names=self.orig_names)

    @property
    def value(self):
        v = [(name, param.value) for name, param in self.params.items()]
        return self.expr.subs(v, simultaneous=True)

    def get_libpaths(self):
        return [param.getLibpath() for param in self.params.values()]


class Parameter(ParametricValued):
    """
    The abstract base class for all parameter types.
    """

    def __init__(self, parent, name,
                 default=None, tex=None, descrip=None, params=None,
                 args=None, last_raw=None):
        """
        :param parent: reference to a governing object. Could be a
          PyodideWidgetStandIn when operating in Pyodide, or a ParamWidget when
          operating in pfsc-server.

        :param name: (str) the name by which the parameter is known. Often
          coincident with the desired TeX string.

        :param default: some specification of a default value for this parameter.
          May be of various types; it is up to the subclass to interpret.
          If specified, will be passed through the same method (build_from_raw)
          as any user-selected value that may come down from the client side.

          May be left unspecified (None), and then the subclass's auto_build
          method will be engaged at build time.

        :param tex: string to be used in TeX representations; if left None,
          self.name will be used instead.

        :param descrip: optional string giving a textual description of this
          parameter, for the benefit of users; however, it is more common to
          let the description instead be generated by the subclass's
          auto_descrip method.

        :param params: dict mapping local names to libpaths of other parameters.
          The names appearing here may then occur within mathematical expressions
          appearing as values in the `args` dict (see below). The value of such
          expressions will then be obtained by substituting the values of these
          parameters.

          NOTE: As a convenience, if you import a param under the same name as
          one of the args (see below) this will set the value of the parameter
          as the value of the arg, unless you override it by defining the
          arg to have some other value.

        :param args: dict giving any arguments, required and/or optional, for
          defining this parameter. Keys are argument names (prescribed by the
          particular subclass); values are any raw JSON type that in some way
          specifies a value (to be interpreted by the particular subclass's
          `parse_raw_arg` method).

          Shortcut option: you may omit an arg definition if you have imported
          a parameter under the exact same name. By doing so, you imply that
          you want the value of that parameter as the value of this arg.

        :param last_raw: useful when rebuilding a parameter that has already
          been in use, in the ISE. You can pass the most recent raw value that
          this parameter has taken on, and it will be recorded as such here. In
          particular, it will take precedence over `self.default` when we build.
        """
        self.parent = parent
        if not name:
            raise MissingName
        self.name = name
        self.default = default
        self.last_attempted_raw_value = last_raw
        if tex is None:
            tex = name
        self.tex = tex
        self.descrip = descrip
        self.given_args = args or {}
        # Dict in which param name points to Parameter instance:
        self.resolved_params = {k: self.parent.get_generator(v)
                                for k, v in (params or {}).items()}
        # Dict in which arg name points to Valued instance:
        self.resolved_args = self.resolve_args(self.given_args)
        # Initialize value to None, so we know whether the parameter has been
        # built yet.
        self._value = None

    def resolve_args(self, args):
        """
        @param args: the raw `args` dict defined in a parameter widget's data.
        @return: dict mapping arg names to instances of `Valued`.
        """
        resolved = {}
        for mode in ["REQ", "OPT"]:
            items = self.arg_spec.get(mode, {}).items()
            for name, spec in items:
                value = None
                if name in args:
                    raw = args[name]
                elif name in self.resolved_params:
                    # Shortcut rule: if you didn't define an arg, but you did
                    # import a param under the exact same name, then you imply
                    # that you want this param as the value of this arg.
                    value = self.resolved_params[name]
                elif mode == "REQ":
                    raise MissingParamArgError(f"Required parameter arg `{name}` not supplied.")
                elif 'default_raw' in spec:
                    raw = spec['default_raw']
                elif 'default_cooked' in spec:
                    value = NonParamValue(spec['default_cooked'])
                else:
                    continue
                if value is None:
                    value = self.parse_raw_arg(name, raw)
                if not isinstance(value, Valued):
                    raise UnresolvedParamArgError(name)
                resolved[name] = value
        return resolved

    def check_value_types(self):
        """
        Check that each resolved arg has value of the required type.
        If not, raise an exception.

        This is invoked before `self.prebuild()`.
        """
        for mode in ["REQ", "OPT"]:
            items = self.arg_spec.get(mode, {}).items()
            for name, spec in items:
                if name in self.resolved_args:
                    a = self.resolved_args[name]
                    t = spec.get('type')
                    if t is None:
                        raise MissingParamArgType(name)
                    if not isinstance(a.value, t):
                        raise UnexpectedParamArgTypeError(f'Arg `{name}` has wrong type.')

    def get_arg_value(self, name, default=None):
        """
        Retrieve the value of a resolved arg, or return a default value if the
        arg was not defined.

        @param name: (str) the name of the arg
        @param default: (any) value to return if the name is not found
        @return: the value of the arg, or the default value
        """
        if not self.has_arg(name):
            return default
        return self.resolved_args[name].value

    def has_arg(self, name):
        return name in self.resolved_args

    def get_arg_mode_and_expected_type(self, name):
        """
        @param name: name of an arg defined in `self.arg_spec`
        @return: pair (m, t), where m is the arg mode "REQ" or "OPT",
          and t is a tuple listing all the allowed types for the value
          of the arg.
        """
        for mode in ["REQ", "OPT"]:
            t = self.arg_spec.get(mode, {}).get(name, {}).get('type')
            if t:
                if not isinstance(t, tuple):
                    t = (t,)
                return mode, t
        raise UnexpectedParamArgError

    def check_int(self, raw):
        try:
            n = int(raw)
        except Exception:
            raise MalformedParamRawValue(raw, self)
        return n

    @property
    def value(self):
        if self._value is None:
            self.build()
        return self._value

    def getTeX(self, as_name=True):
        return self.tex if as_name else latex(self.value)

    def __str__(self):
        return self.getTeX()

    def getUid(self):
        return self.parent.getUid()

    def getLibpath(self):
        return self.parent.getLibpath()

    def get_libpaths(self):
        return [self.getLibpath()]

    def write_name_and_value(self, include_value=True, editable=True, display_value=None):
        """
        A utility for use by subclasses' auto_descrip methods. Achieves a common
        pattern in which the value of the parameter is rendered according to the
        keyword args, which are the same as for the auto_descrip method, except that
        the additional arg display_value may be provided if something other than
        self.value should be shown.
        """
        s = f'${self}$'
        if include_value:
            if display_value is None:
                display_value = self.value
            if editable:
                v = f'<span class="param_val">&nbsp;$= {display_value}$</span>'
            else:
                v = f'&nbsp;$= {display_value}$'
            s += Markup(v)
        return s

    def write_html(self):
        """
        Note: It's important that this be a normal method, not a @property
        method. In Pyodide (as of v0.19.0), it seems that exceptions raised
        while executing property methods are silenced. But we need to see any
        exceptions, so we can debug.
        """
        return self.write_chooser_widget()

    def build(self, raw=None):
        """
        This is where `self._value` gets defined. This should be an instance of
        some class defined in SymPy. This includes things like a `Poly` or an
        `AlgebraicField`, but also basic types like `Integer`, `Rational`,
        `Float`, and `BooleanAtom` (for True and False). In other words,
        even Python primitives should be transformed into appropriate SymPy
        objects.

        If `self.default` has been provided, it should be some primitive
        value that somehow specifies the desired value for this parameter. For
        example, it might be an int, or a string describing a polynomial.
        It has to be something that could be written into a widget's data (i.e.
        a valid JSON type), but now it is to be transformed into an internal
        representation. It is passed to `self.build_from_raw()` in order to
        achieve this transformation.

        If `self.default` was not provided, then we "auto build", choosing a
        value perhaps based on optional args in the arg_sepc, perhaps based on
        prior parameters on which we depend, or perhaps based on nothing.
        Subclasses decide how this works in their `self.auto_build()` method.
        One common pattern is to pick a raw value, and pass it to
        `self.build_from_raw()`.

        There are optional prebuild and postbuild hooks that subclasses may
        override.
        """
        #print(f'{self.name}: raw: {raw}, last: {self.last_attempted_raw_value}, default: {self.default}')
        raw = adapt(raw)
        if raw is not None:
            self.last_attempted_raw_value = raw
        self._value = None

        self.check_value_types()
        self.prebuild()

        if raw is not None:
            # When attempting to build based on a user-supplied raw value, we do
            # NOT catch exceptions. The user has to know that their value was
            # attempted, and failed.
            self._value = self.build_from_raw(raw)
        else:
            # When attempting to build based on a previously attempted value,
            # or an author-supplied default, we DO catch exceptions.
            # In the case of previously attempted values, the user has not
            # actively entered a value, so should be happy to have the chooser
            # switch back to anything that works.
            # In the case of author-supplied defaults, we want authors to be
            # free to make defaults that work with the *initial* values of other
            # parameters, but not necessarily with other values those params
            # may take on later.
            raw = self.last_attempted_raw_value
            if raw is None:
                raw = self.default
            if raw is not None:
                try:
                    self._value = self.build_from_raw(raw)
                except MalformedParamRawValue:
                    pass
            if self._value is None:
                self._value = self.auto_build()

        self.postbuild()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # SUBCLASSES MAY OVERRIDE

    """
    `arg_spec` is where subclasses define their required and optional args.
    E.g. might look something like:
    
        arg_spec = {
            "REQ": {
                'dividing': {
                    'type': Integer,
                },
            },
            "OPT": {
                'sign': {
                    'type': (One, Zero, NegativeOne,),
                    'default_cooked': Integer(1),
                },
            }
        }
    
    In particular, each arg should define a 'type', whose value should be
    either a single SymPy type, or else a tuple thereof (serving as a
    disjunctive type, i.e. input may define any of these).
    
    Note that the 'type' is not the raw, JSON type of the input, but the
    eventual type of the internal SymPy object the raw input specifies in one
    way or another (it's up to the particular parameter subclass to interpret;
    see `parse_raw_arg()` method).
    
    Optional args may define a 'default_raw', or `default_cooked`, which
    supplies a value in case the user did not supply one. Neither is required.
    
    A 'default_raw' value will be passed through the same parsing process as a
    raw value supplied by the user, while a 'default_cooked' value is assumed
    to already be of the internal SymPy type resulting from that process, and
    is accepted as is.
    
    All types will be checked at the start of the `build()` process, and an
    exception raised if any check fails. 
    """
    arg_spec = {}

    def parse_raw_arg(self, name, raw):
        """
        Transform a raw parameter argument value (a JSON type) into its
        internal representation as some SymPy type.

        Subclasses that expect any of their args to be (even optionally) passed
        via raw JSON types (i.e. not by reference to other parameters) may need
        to override this method.

        A common pattern for subclasses should be to call this method (as a
        superclass method), and iff it returns `None`, then consider other
        possible cases.

        This method will return a `Valued` object on any raw arg of type
        `bool`, `int`, or `float`, and on _some_ raw args of type `str` (see
        below). Otherwise it returns `None`.

        This method will turn raw args of types `bool`, `int`, and `float` into
        their corresponding SymPy types, and wrap these in a `NonParamValue`.

        Raw args of type `str` it will attempt to parse as algebraic
        expressions. This includes anything as simple as a single symbol
        (like 'x' or 'theta') up to any expression built using symbol names,
        numbers (int and float), and the binary operations +, -, *, /, ^, **,
        where ^ is a synonym for **.

        When a `str` parses successfully as a Sympy `Expr`, we wrap it in a
        `ParametricExpression`.

        When a `str` does not parse successfully as a Sympy `Expr`, this method
        returns `None`.

        WARNING
        =======

        EDIT: This warning was originally written before we used a custom fork
        of SymPy. We now use a fork in which `parse_expr()` no longer calls
        `eval()`. Nevertheless, our policy is still to use custom parsers
        instead of `S` or `sympify`.

            Subclasses that do wish to do their own parsing
            MUST NOT use Sympy's `S` or `sympify` functions to parse strings!

            Similarly, DO NOT pass strings directly to constructors like `Poly`,
            which just uses `sympify` internally.

            Consider, for example,

            >>> S("x.n.__globals__['__builtins__']['exec']('''import os; os.system(\"echo 'arbitrary code execution...'\")''')")
            arbitrary code execution...

            (Explanation: `sympify` (which is called through `S`) turns `x` into a
            `Symbol`. The `Symbol` class has a method called `n`. Every method in
            Python has a `__globals__` attribute, through which all built-ins (incl
            `exec`) can be reached.)

            Instead, use the parsers defined under `pfsc.examp.parameters.parse`.
            If the parser you need isn't defined there yet, please consider writing
            it and contributing via pull request.

        @param name: the name of the argument
        @param raw: the raw value of the argument

        @return: an instance of `Valued`, or `None`
        """
        if isinstance(raw, (bool, int, float)):
            return NonParamValue(SS(raw))

        if isinstance(raw, str):
            try:
                expr = safe_algebraic_func_str_to_sympy(raw)
            except ParsingExcep:
                return None
            else:
                return ParametricExpression(expr, self.resolved_params)

        return None

    def prebuild(self):
        """
        Subclasses may assume that, when `prebuild` is called:
            * all prior parameters on which this one depends have already been
              built (i.e. they have defined their `self._value`).
            * all resolved args for this parameter have had their values
              type-checked.

        This is a good place to compute any values that may be used repeatedly
        in the "MUST OVERRIDE" methods below.

        It is also common to grab resolved args and store them under instance
        attributes here, so that they can be more easily referenced.
        Best practice is to store the args themselves, not their values.
        Then, where values are needed, just use `.value`.
        """
        pass

    def postbuild(self):
        pass

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # SUBCLASSES MUST OVERRIDE

    def auto_build(self):
        """
        Choose a value for this parameter. See doctext for self.build()

        :return: the value
        """
        raise NotImplementedError

    def build_from_raw(self, raw):
        """
        Build a value for this parameter from the given raw description.
        See doctext for self.build()

        :param raw: string/numerical description/specification of the desired
          parameter value
        :return: the value
        """
        raise NotImplementedError

    def auto_descrip(self, include_value=True, editable=True):
        """
        Write a string giving a verbal/symbolic description of this parameter.
        Should honor `self.parent.context` when choosing phraseology.

        :param include_value: e.g. "$p$ a prime" if False,
          but "$p = 7$ a prime" if True.
        :param editable: only meaningful if `include_value` is True.
          In that case, `editable` True should yield e.g.

            "$p$ <span class="edit_me">&nbsp;$= 7$</span> a prime"

          so that it's easy to edit the value on the client-side.

        :return: the description string
        """
        raise NotImplementedError

    def write_chooser_widget(self):
        """
        Write HTML to describe the client-side chooser widget with which users
        may choose new values for this parameter.

        This is not to be invoked until after `self.build()`.

        :return: HTML string
        """
        raise NotImplementedError

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def write_radio_panel_chooser_widget(name, descrip, code_and_text, selected=None):
    """
    :param name: the name of the parameter (e.g. 'frp')
    :param descrip: the parameter's description (e.g. '$\\mathfrak{p}$ a prime ideal')
    :param code_and_text: list of pairs (c, t) in which t is the text that should
      appear on the button, e.g. '$(13, x^2 + 3 x + 1)$' and c the code that
      should be passed to the server when this option is selected,
      e.g. '0'. They can be strings, or anything else that formats to the
      desired string.
    :param selected: the code of the selected button
    :return: HTML string for the chooser widget
    """
    context = {}
    context.update(locals())
    return radio_panel_chooser_widget_template.render(context)

radio_panel_chooser_widget_template = jinja2.Template("""
<div class="chooser radio_panel_chooser" name="{{ name }}">
    <div class="heading">{{ descrip }}</div>
    <div class="error_display"></div>
    <div class="radio_panel">
        {% for c, t in code_and_text %}
            {% if c == selected %}
                <div tabindex="0" value="{{ c }}" display="{{ t }}" class="radio_panel_button rpb_selected">{{ t }}</div>
            {% else %}
                <div tabindex="0" value="{{ c }}" display="{{ t }}" class="radio_panel_button">{{ t }}</div>
            {% endif %}
        {% endfor %}
    </div>
</div>
""")

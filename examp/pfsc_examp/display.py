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

from displaylang.exceptions import ControlledEvaluationException

from pfsc_examp.calculate import calculate
from pfsc_examp.excep import MalformedExampImport, MissingExport
from pfsc_examp.parse.display import displaylang_processor
from pfsc_examp.util import adapt


def parse_imports(s):
    """
    Parse an import string of the kind that appears as key in the `import`
    dictionary of a DispWidget.

    The format of this string is a comma-delimited list of imports, where each
    import at least gives the name of a variable as exported from the DispWidget
    in question, and may also give a local name we wish to use for it after
    importing, separated by keyword `as`.

    In other words, an import string matches this grammar:

        import_string := import ("," import)*
        import := CNAME ("as" CNAME)?
        %skip whitespace

    Thus, imports can be as simple as,

        import: {
            'f': some_disp
        }

    importing `f` as 'f' from `some_disp`, or as complex as,

        import: {
            'f as g, a, b, alpha as zeta': some_disp
        }

    importing `f` as 'g', `a` as 'a', `b` as 'b', and `alpha` as 'zeta'.

    Note that there is no risk of key collision in such an `import` dictionary,
    because it does not make sense to import more than one thing under the same
    local name.

    :param s: the import string to be parsed
    :return: list of ordered pairs (exported name, local name)
    """
    def err():
        msg = f'Malformed imports: {s}'
        raise MalformedExampImport(msg)
    imps = [p.strip() for p in s.split(',')]
    pairs = []
    for imp in imps:
        words = imp.split()
        n = len(words)
        if n == 1:
            w = words[0]
            pairs.append((w, w))
        elif n == 3:
            exp, prep, loc = words
            if prep != 'as':
                err()
            pairs.append((exp, loc))
        else:
            err()
    return pairs


def make_disp(parent, info):
    params = info.get('params', {})
    imports = info.get('imports', {})
    build_code = info['build']
    export_names = info.get('export', None)
    return ExampDisplay(parent, params, imports, build_code, export_names)


class ExampDisplay:

    def __init__(self, parent, params, imports, build_code, export_names=None):
        """
        Build an `ExampDisplay` instance based on a *built* display widget.
        In other words, the args passed here are not identical with those a
        user writes when defining a display in a pfsc module; they are instead
        as processed by a `pfsc.lang.widgets.DispWidget()` at build time.
        In particular, while users put all imports together in a single
        `imports` dictionary, in a built display widget these are separated
        into params, and imports from other displays.

        :param parent: DispWidget
            The widget that is constructing this display.
        :param params: dict
            Maps local param names we wish to use, to the absolute libpaths of
            ParamWidgets representing those parameters.
        :param imports: dict
            Specifies exports to import from DispWidgets.
            The values are absolute libpaths of DispWidgets. The keys are
            strings specifying vars to import, as defined in the
            `parse_imports()` function.
        :param build_code: str or list[str]
            Python code that builds (a) our HTML display, and (b) any values we
            want to export.
        :param export_names: None or list[str]
            Optional list of names of vars defined in the build_code. If given,
            then *only* these vars will be exported, i.e. made available for
            other displays to import. If ``None``, then *all* vars defined in
            the build_code will be exported.
        """
        self.parent = parent
        self.params = params
        self.imports = imports
        self.build_code = self.to_code_string(build_code)
        self.export_names = export_names

        self.param_values = {}
        self.import_values = {}

        self._exports = {}
        self._html = None

        self.last_attempted_raw_value = None

    def getUid(self):
        return self.parent.getUid()

    @staticmethod
    def to_code_string(code):
        """
        Convert what may be a string, or a list of strings, into a single code
        string.
        """
        return '\n'.join(code) if isinstance(code, list) else code

    def obtain_param_values(self):
        return {
            name: self.parent.get_generator(lp).value
            for name, lp in self.params.items()
        }

    def obtain_import_values(self):
        values = {}
        for imp_str, lp in self.imports.items():
            disp = self.parent.get_generator(lp)
            pairs = parse_imports(imp_str)
            for exp, loc in pairs:
                if exp not in disp.exports:
                    raise MissingExport(f'Display {lp} is missing export "{exp}".')
                values[loc] = disp.exports[exp]
        return values

    @property
    def exports(self):
        return self._exports

    @property
    def html(self):
        return self._html

    def write_html(self):
        """
        The reason for having this method (which duplicates the @property method
        `html`) is to have a uniform interface implemented by both `ExampDisplay`
        and `Parameter`. The reason `Parameter` needs this to be a true method
        instead of a property method is so that exceptions will not be silenced
        by Pyodide. See note in `Parameter.write_html()`.
        """
        return self._html

    def build(self, raw=None):
        raw = adapt(raw)
        if raw is not None:
            self.last_attempted_raw_value = raw = self.to_code_string(raw)

        self.param_values = self.obtain_param_values()
        self.import_values = self.obtain_import_values()
        existing_values = {**self.param_values, **self.import_values}

        html = None
        exports = {}
        if raw is None and self.last_attempted_raw_value is not None:
            # When attempting to build based on a previously attempted value,
            # we simply fail silently in case of a ControlledEvaluationException.
            # The user has not actively entered a value, so should be happy to
            # have the display switch back to anything that works.
            code = self.last_attempted_raw_value
            try:
                html, exports = calculate(
                    displaylang_processor.process,
                    code, existing_values
                )
            except ControlledEvaluationException:
                pass
        if html is None:
            # Here we are either attempting to build the value passed by the
            # user, or our default code. In either case, we do NOT catch
            # exceptions, because the user needs to know about any errors.
            code = self.build_code if raw is None else raw
            html, exports = calculate(
                displaylang_processor.process,
                code, existing_values
            )

        self._html = (
            f'<div class="display">\n{html}\n</div>\n'
        )
        if self.export_names is not None:
            exports = {k: v for k, v in exports.items() if k in self.export_names}
        self._exports = exports

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

from pfsc_examp.calculate import calculate
from pfsc_examp.excep import MalformedExampImport, MissingExport
from pfsc_examp.parse.display import displaylang_processor


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
    export_names = info.get('export', [])
    return ExampDisplay(parent, params, imports, build_code, export_names)


class ExampDisplay:

    def __init__(self, parent, params, imports, build_code, export_names):
        """
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
        :param build_code: str
            Python code that builds (a) our HTML display, and (b) any values we
            want to export.
        :param export_names: list[str]
            Names of vars defined in the build_code, which we want to export.
        """
        self.parent = parent
        self.params = params
        self.imports = imports
        self.build_code = build_code
        self.export_names = export_names

        self.param_values = {}
        self.import_values = {}

        self._exports = {}
        self._html = None

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

    def build(self):
        self.param_values = self.obtain_param_values()
        self.import_values = self.obtain_import_values()
        existing_values = {**self.param_values, **self.import_values}

        html, exports = calculate(
            displaylang_processor.process,
            self.build_code, existing_values
        )

        self._html = f'<div class="display">\n{html}\n</div>\n'
        self._exports = exports

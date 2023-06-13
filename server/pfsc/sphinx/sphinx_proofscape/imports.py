# --------------------------------------------------------------------------- #
#   Sphinx-Proofscape                                                         #
#                                                                             #
#   Copyright (c) 2022-2023 Proofscape contributors                           #
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

from sphinx.util.docutils import SphinxDirective
from lark import Tree
from lark.exceptions import VisitError

from pfsc.sphinx.sphinx_proofscape.environment import get_pfsc_env
from pfsc.sphinx.sphinx_proofscape.pages import build_libpath_for_rst
from pfsc.lang.modules import parse_module_text, PfscRelpath, PendingImport
from pfsc.lang.freestrings import PfscJsonTransformer
from pfsc.excep import PfscExcep, PECode


class ImportReader(PfscJsonTransformer):
    """
    Ultimately, should not need this class; if `pfsc.lang.modules.ModuleLoader`
    is redesigned to operate first in a pure READING phase, before a RESOLVING
    phase, then it should be usable. On the other hand, ultimately should not
    need the `pfsc-import::` directive at all, replacing it with `pfsc::`. (But
    then processing that directive's content will need the redesigned
    `ModuleLoader`, as just described.)
    """

    def __init__(self, home_module):
        """
        :param home_module: the PfscModule where the import happened
        """
        super().__init__()
        self.home_module = home_module
        self.homepath = home_module.libpath
        self.imports = []

    def module(self, items):
        # Each item should be a ``PendingImport`` instance.
        # If the user wrote anything other than an import, it will be received
        # here as an un-transformed AST node (a ``Tree`` instance).
        for item in items:
            if isinstance(item, Tree):
                raise PfscExcep(
                    f'`pfsc-import` directive tries to define'
                    f' `{item.data}`'
                    # line/col are within directive; maybe more confusing than helpful
                    # f' at line {item.line}, col {item.column}'
                    f'. Only imports are allowed.'
                )
            else:
                self.imports.append(item)
        return self.imports

    def fromimport(self, items):
        """
        Process line of the form:

            fromimport : "from" (relpath|libpath) "import" (STAR|identlist ("as" IDENTIFIER)?)

        :return: PendingImport instance
        """
        src_modpath = items[0]
        is_relative = isinstance(src_modpath, PfscRelpath)
        if is_relative:
            src_modpath = src_modpath.resolve(self.homepath)
        object_names = items[1]
        requested_local_name = items[2] if len(items) == 3 else None
        return PendingImport(
            self.home_module, PendingImport.FROM_IMPORT_FORMAT, src_modpath,
            object_names=object_names, local_path=requested_local_name
        )

    def plainimport(self, items):
        """
        :return: PendingImport instance
        """
        src_modpath = items[0]
        # Are we using a relative libpath or absolute one?
        is_relative = isinstance(src_modpath, PfscRelpath)
        if is_relative:
            src_modpath = src_modpath.resolve(self.homepath)
            # In this case the user _must_ provide an "as" clause.
            if len(items) < 2:
                msg = 'Plain import with relative libpath failed to provide "as" clause.'
                raise PfscExcep(msg, PECode.PLAIN_RELATIVE_IMPORT_MISSING_LOCAL_NAME)
            local_path = items[1]
        else:
            # In this case an "as" clause is optional.
            local_path = items[1] if len(items) == 2 else src_modpath
        return PendingImport(
            self.home_module, PendingImport.PLAIN_IMPORT_FORMAT, src_modpath,
            local_path=local_path
        )

    def relpath(self, items):
        num_dots = len(items[0])
        libpath = items[1] if len(items) == 2 else ''
        return PfscRelpath(num_dots, libpath)

    def identlist(self, items):
        return items

    def libpath(self, items):
        return '.'.join(items)


class PfscImportDirective(SphinxDirective):
    """
    Eventually we may have a `pfsc::` directive, under which you can put
    arbitrary pfsc module syntax. For now, we have a `pfsc-import::` directive,
    under which just `import` (and `from-import`) statements can go. The former
    will obviate the latter (if we get there).

    This directive has no visual form; it is just a place to do imports.

    Example:
        .. pfsc-import::

            import gh.toepproj.lit as tpl
            from gh.toepproj.lit.H.ilbert.ZB168 import Thm
    """

    required_arguments = 0
    has_content = True
    option_spec = {
    }

    def run(self):
        env = self.env
        config = env.config
        docname = env.docname
        modpath = build_libpath_for_rst(config, docname, within_page=False)
        pfsc_env = get_pfsc_env(env)
        module = pfsc_env.get_module(modpath)

        # self.content is an instance of `docutils.statemachine.StringList`.
        # It presents the lines of the content as a list, with left indent stripped.
        text = '\n'.join(self.content)
        tree, _ = parse_module_text(text)
        reader = ImportReader(module)
        try:
            imports = reader.transform(tree)
        except VisitError as v:
            # Lark traps our PfscExceps, re-raising them within a VisitError. We want to see the PfscExcep.
            raise v.orig_exc from v

        pfsc_env.imports_by_homepath[modpath] = imports

        # No presence in the final document.
        return []

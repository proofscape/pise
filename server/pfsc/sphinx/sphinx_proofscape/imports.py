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
from lark.exceptions import VisitError

from pfsc.sphinx.sphinx_proofscape.environment import get_pfsc_env
from pfsc.sphinx.sphinx_proofscape.pages import build_libpath_for_rst
from pfsc.build.lib.libpath import get_modpath
from pfsc.lang.modules import parse_module_text, PfscRelpath
from pfsc.lang.freestrings import PfscJsonTransformer
from pfsc.excep import PfscExcep, PECode


class PfscImport:
    """
    Represents a pfsc import (as achieved via `pfsc-import::` directive, before
    resolution.
    """
    PLAIN_IMPORT_FORMAT = 0
    FROM_IMPORT_FORMAT = 1

    def __init__(self, format, src, original_name=None, local_name=None, homepath=None):
        """
        :param format: one of PLAIN_IMPORT_FORMAT, FROM_IMPORT_FORMAT, indicating
            the format of the import statement
        :param src: the libpath named as the source in the import statement
        :param original_name: for FROM imports, the name of the imported object
            inside of ``src``
        :param local_name: optional local name given in an "as" clause in the import
        :param homepath: libpath of the module where the import happened. May
            be useful later for resolving ``src``, if relative.
        """
        self.format = format
        self.src = src
        self.original_name = original_name
        self.local_name = local_name
        self.homepath = homepath

    def resolve_src(self):
        """
        Resolve src if a relative path, otherwise return it as is (already resolved).
        """
        src = self.src
        if isinstance(src, PfscRelpath):
            return src.resolve(self.homepath)
        return src

    def get_module(self, modpath, version):
        """
        Get a PfscModule from the environment
        """
        ...  # TODO

    def carry_out_from_import(self, modpath, version):
        """
        Carry out (delayed) resolution of a FROM-IMPORT.

        Experimental.
        Based on `pfsc.lang.modules.ModuleLoader.fromimport()`.
        """
        # Now we have the module libpath and version from which we are attempting to import something.
        # What we're allowed to do depends on whether the modpath we've constructed is the
        # same as that of this module, or different.
        # Usually it will be different, and then we have these permissions:
        may_search_within_module = True

        if modpath == self.homepath:
            # The modpaths will be the same in the special case where we are attempting to
            # import a submodule via a relative path.
            # For example, if the module a.b.c.d features the import statement
            #     from . import e
            # where a.b.c.d.e is a submodule of a.b.c.d, then this case arises.
            # In this case, submodules are the _only_ thing we can try to import.
            may_search_within_module = False
            src_module = None
        else:
            # In all other cases, the modpath points to something other than this module.
            # We can now attempt to build it, in case it points to a module (receiving None if it does not).
            src_module = self.get_module(modpath, version)

        local_name = self.local_name
        object_name = self.original_name
        # Initialize imported object to None, so we can check for success.
        obj = None
        # Construct the full path to the object, and compute the longest initial segment
        # of it that points to a module.
        full_object_path = modpath + '.' + object_name
        object_modpath = get_modpath(full_object_path, version=version)
        # If the object_modpath equals the libpath of the module we're in, this is a cyclic import error.
        if object_modpath == self.homepath:
            if full_object_path == self.homepath:
                msg = f'Module {self.homepath} attempts to import itself from its ancestor.'
            else:
                msg = f'Module {self.homepath} attempts to import from within itself.'
            raise PfscExcep(msg, PECode.CYCLIC_IMPORT_ERROR)
        # The first attempt is to find the name in the source module, if any.
        if src_module and may_search_within_module:
            obj = src_module.get(object_name)
        # If that failed, try to import a submodule.
        if obj is None:
            obj = self.get_module(full_object_path, version)
        # If that failed too, it's an error.
        if obj is None:
            msg = 'Could not import %s from %s' % (object_name, modpath)
            raise PfscExcep(msg, PECode.MODULE_DOES_NOT_CONTAIN_OBJECT)

        return obj


class ImportReader(PfscJsonTransformer):
    """
    Ultimately, should not need this class; if `pfsc.lang.modules.ModuleLoader`
    is redesigned to operate first in a pure READING phase, before a RESOLVING
    phase, then it should be usable. On the other hand, ultimately should not
    need the `pfsc-import::` directive at all, replacing it with `pfsc::`. (But
    then processing that directive's content will need the redesigned
    `ModuleLoader`, as just described.)
    """

    def __init__(self, modpath):
        """
        :param modpath: The libpath of the module where the import happened.
        """
        super().__init__()
        self.modpath = modpath
        self.imports = []

    def module(self, items):
        # Each item should be a list of `PfscImport` objects.
        self.imports = sum(items, [])
        return self.imports

    def fromimport(self, items):
        """
        Process line of the form:

            fromimport : "from" (relpath|libpath) "import" (STAR|identlist ("as" IDENTIFIER)?)

        :return: list of PfscImport instances (one for each imported object)
        """
        src = items[0]
        object_names = items[1]
        requested_local_name = items[2] if len(items) == 3 else None

        if object_names == "*":
            raise PfscExcep('import "*" not allowed in this context')

        imports = []
        N = len(object_names)
        for i, object_name in enumerate(object_names):
            local_name = requested_local_name if requested_local_name and i == N - 1 else object_name
            imports.append(PfscImport(
                PfscImport.FROM_IMPORT_FORMAT, src, original_name=object_name,
                local_name=local_name, homepath=self.modpath
            ))
        return imports

    def plainimport(self, items):
        """
        :return: list of length 1, containing a single PfscImport instance
        """
        src = items[0]
        # Are we using a relative libpath or absolute one?
        is_relative = isinstance(items[0], PfscRelpath)
        if is_relative:
            # In this case the user _must_ provide an "as" clause.
            if len(items) < 2:
                msg = 'Plain import with relative libpath failed to provide "as" clause.'
                raise PfscExcep(msg, PECode.PLAIN_RELATIVE_IMPORT_MISSING_LOCAL_NAME)
            local_name = items[1]
        else:
            # In this case an "as" clause is optional.
            local_name = items[1] if len(items) == 2 else src
        return [PfscImport(
            PfscImport.PLAIN_IMPORT_FORMAT, src,
            local_name=local_name, homepath=self.modpath
        )]

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
        pfsc_env = get_pfsc_env(env)
        modpath = build_libpath_for_rst(config, docname, within_page=False)

        # self.content is an instance of `docutils.statemachine.StringList`.
        # It presents the lines of the content as a list, with left indent stripped.
        text = '\n'.join(self.content)
        tree, _ = parse_module_text(text)
        reader = ImportReader(modpath)
        try:
            imports = reader.transform(tree)
        except VisitError as v:
            # Lark traps our PfscExceps, re-raising them within a VisitError. We want to see the PfscExcep.
            raise v.orig_exc from v

        pfsc_env.imports_by_modpath[modpath] = imports

        # No presence in the final document.
        return []

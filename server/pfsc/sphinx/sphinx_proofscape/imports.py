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
from pfsc.build.lib.libpath import get_modpath
from pfsc.lang.modules import parse_module_text, PfscRelpath
from pfsc.lang.freestrings import PfscJsonTransformer
from pfsc.excep import PfscExcep, PECode


class PendingImport:
    """
    Represents a pfsc import (as achieved via `pfsc-import::` directive)
    that is pending, i.e. has not yet been resolved.

    NOTE: We're going to try to keep to a design where objects like this one,
    that will be stored in the Sphinx build environment, will *not* retain their
    own reference to the environment object. This is in order to try to keep the
    ``merge`` operation simple, and not have to change each object's env reference
    at that time. Thus, this class's ``__init__()`` method does *not* accept an
    ``env`` argument, but its ``resolve()`` method does.
    """
    PLAIN_IMPORT_FORMAT = 0
    FROM_IMPORT_FORMAT = 1

    def __init__(self, home_module, format, src_modpath, object_names=None, local_path=None):
        """
        :param home_module: the PfscModule where the import happened
        :param format: one of PLAIN_IMPORT_FORMAT, FROM_IMPORT_FORMAT, indicating
            the format of the import statement
        :param src_modpath: the libpath of the module named as the source in
            the import statement
        :param object_names: for FROM imports, the name or names (str or list of
            str) of the imported object or objects inside of the source module,
            or "*" if importing all from there
        :param local_path: dotted path or name under which the imported object
            (last imported object, if several) is to be stored in the home module
        """
        self.home_module = home_module
        self.format = format
        self.src_modpath = src_modpath
        self.object_names = object_names
        self.local_path = local_path
        self.homepath = self.home_module.libpath

    def get_desired_version_for_target(self, targetpath):
        """
        :param targetpath: The libpath of the target object.
        :return: the version at which we wish to take the repo to which the
          named target belongs.

        NOTE: Copied from `pfsc.lang.modules.ModuleLoader.get_desired_version_for_target()`
        """
        extra_msg = f' Required for import in module `{self.homepath}`.'
        return self.home_module.getRequiredVersionOfObject(targetpath, extra_err_msg=extra_msg)

    def resolve(self, pfsc_env):
        """
        Resolve this import, and store the result in the "home module," i.e.
        the module where this import statement occurred.

        :param pfsc_env: the SphinxPfscEnvironment object in place at the time
            that resolution needs to happen.
        """
        if self.format == self.PLAIN_IMPORT_FORMAT:
            self.resolve_plainimport(pfsc_env)
        elif self.format == self.FROM_IMPORT_FORMAT:
            self.resolve_fromimport(pfsc_env)

    def resolve_plainimport(self, pfsc_env):
        """
        Carry out (delayed) resolution of a PLAIN-IMPORT.

        Based on `pfsc.lang.modules.ModuleLoader.plainimport()`.
        """
        modpath = self.src_modpath
        version = self.get_desired_version_for_target(modpath)
        module = pfsc_env.get_module(modpath, version=version)
        self.home_module[self.local_path] = module

    def resolve_fromimport(self, pfsc_env):
        """
        Carry out (delayed) resolution of a FROM-IMPORT.

        Copied from `pfsc.lang.modules.ModuleLoader.fromimport()`.
        """
        modpath = self.src_modpath
        version = self.get_desired_version_for_target(modpath)

        # Now we have the module libpath and version from which we are attempting to import something.
        # What we're allowed to do depends on whether the modpath we've constructed is the
        # same as that of this module, or different.
        # Usually it will be different, and then we have these permissions:
        may_import_all = True
        may_search_within_module = True

        if modpath == self.homepath:
            # The modpaths will be the same in the special case where we are attempting to
            # import a submodule via a relative path.
            # For example, if the module a.b.c.d features the import statement
            #     from . import e
            # where a.b.c.d.e is a submodule of a.b.c.d, then this case arises.
            # In this case, submodules are the _only_ thing we can try to import.
            may_import_all = False
            may_search_within_module = False
            src_module = None
        else:
            # In all other cases, the modpath points to something other than this module.
            # We can now attempt to build it, in case it points to a module (receiving None if it does not).
            src_module = pfsc_env.get_module(modpath, version=version)

        object_names = self.object_names
        # Next behavior depends on whether we wanted to import "all", or named individual object(s).
        if object_names == "*":
            if not may_import_all:
                # Currently the only time when importing all is prohibited is when we are
                # trying to import from self.
                msg = 'Module %s is attempting to import * from itself.' % self.homepath
                raise PfscExcep(msg, PECode.CYCLIC_IMPORT_ERROR)
            # Importing "all".
            # In this case, the modpath must point to an actual module, or else it is an error.
            if src_module is None:
                msg = 'Attempting to import * from non-existent module: %s' % modpath
                raise PfscExcep(msg, PECode.MODULE_DOES_NOT_EXIST)
            all_names = src_module.listAllItems()
            for name in all_names:
                self.home_module[name] = src_module[name]
        else:
            # Importing individual name(s).
            N = len(object_names)
            requested_local_name = self.local_path
            for i, object_name in enumerate(object_names):
                # Set up the local name.
                local_name = requested_local_name if requested_local_name and i == N - 1 else object_name
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
                    obj = pfsc_env.get_module(full_object_path, version=version)
                # If that failed too, it's an error.
                if obj is None:
                    msg = 'Could not import %s from %s' % (object_name, modpath)
                    raise PfscExcep(msg, PECode.MODULE_DOES_NOT_CONTAIN_OBJECT)
                    # Otherwise, record the object.
                else:
                    self.home_module[local_name] = obj


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

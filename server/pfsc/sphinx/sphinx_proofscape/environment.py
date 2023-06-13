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

from pfsc.constants import WIP_TAG
from pfsc.build.versions import version_string_is_valid
from pfsc.lang.modules import load_module


class SphinxPfscEnvironment:
    """
    An instance of this class will be stored in the Sphinx BuildEnvironment,
    under the attribute 'proofscape'.

    It is designed to hold all of the environment data structures relevant to
    the sphinx-proofscape extension.

    It supports merge/purge operations, for Sphinx parallel builds.
    """

    def __init__(self, app):
        self.all_widgets = []
        self.vers_defns = regularize_version_dict(app)
        self.lp_defns_by_docname = {}
        self.imports_by_homepath = {}

        # Lookup for PfscModule instances, by libpath.
        # This will hold all modules, whether constructed from pfsc
        # files, or from rst files.
        self.pfsc_modules = {}

    def update_modules(self, modules):
        """
        Update our dict of pfsc modules with a given dict.

        :param modules: dict of modules by modpath
        """
        self.pfsc_modules.update(modules)

    def get_module(self, modpath, version=None):
        """
        Get a module, trying our catalog first, or resorting to loading from
        disk if need be.

        :param modpath: the libpath of the desired module
        :param version: if defined, and if we do not already have the module
             in our catalog, then we will attempt to load it from disk, at
             this version
        :return: PfscModule or None
        """
        module = self.pfsc_modules.get(modpath)
        if module is None and version is not None:
            module = load_module(modpath, version=version)
        return module

    def purge(self, docname):
        # See https://www.sphinx-doc.org/en/master/development/tutorials/
        # TODO: other things besides widgets?
        self.all_widgets = [
            w for w in self.all_widgets if w.docname != docname
        ]

    def merge(self, other):
        # TODO: other things besides widgets?
        other_pfsc_env = get_pfsc_env(other)
        self.all_widgets.extend(other_pfsc_env.all_widgets)

    def resolve(self):
        """
        Invoked after both the rst side and the pfsc side having finished
        their READING phase. It is time now to RESOLVE pending imports etc.
        """
        # Pending imports
        for pending_import_list in self.imports_by_homepath.values():
            for pending_import in pending_import_list:
                pending_import.resolve(self)
        # Anything else? ...


def setup_pfsc_env(app):
    """
    To be registered as a handler for the 'builder-inited' event.
    Puts a `SphinxPfscEnvironment` instance into the Sphinx BuildEnvironment.
    """
    pfsc_env = SphinxPfscEnvironment(app)
    app.env.proofscape = pfsc_env


def get_pfsc_env(sphinx_env) -> SphinxPfscEnvironment:
    """
    Accessor for the `SphinxPfscEnvironment` stored in a Sphinx
    BuildEnvironment.
    """
    return sphinx_env.proofscape


def purge_pfsc_env(app, env, docname):
    """
    Handler for the Sphinx 'env-purge-doc' event.
    Updates the `SphinxPfscEnvironment` accordingly.
    """
    get_pfsc_env(env).purge(docname)


def merge_pfsc_env(app, env, docnames, other):
    """
    Handler for the Sphinx 'env-merge-info' event.
    Updates the `SphinxPfscEnvironment` accordingly.
    """
    get_pfsc_env(env).merge(other)


def regularize_version_dict(app):
    """
    Read the version dictionary out of `config.pfsc_import_repos`, regularize
    it, meaning ensure that each value is either WIP or starts with a 'v', and
    then save the regularized version in the env.

    raises: ValueError if any version string is improperly formatted
    """
    vers_defns = app.config.pfsc_import_repos or {}
    r = {}
    for k, v in vers_defns.items():
        if v != WIP_TAG:
            if not v.startswith('v'):
                v = f'v{v}'
            if not version_string_is_valid(v):
                raise ValueError(v)
        r[k] = v
    return r

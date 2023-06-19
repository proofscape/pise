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

from pfsc.sphinx.sphinx_proofscape.environment import get_pfsc_env

from pfsc.lang.objects import PfscObj
from pfsc.lang.modules import PfscModule


# Since it seems most natural that rst files should correspond to modules,
# we need there to be an abstract entity *inside* the module, defined at the
# top level, that represents the page. This is especially true if we're going
# to have directives that allow you to use ordinary pfsc module syntax within
# an rst file, in order to define other top-level entities. Since it is a fixed
# given that each rst file defines exactly one Sphinx page, we're setting a
# fixed libpath segment of '_page' to be the name of that entity, and the final
# segment of its libpath.
#
# All widgets meanwhile, defined within the page, will always have this same
# segment as their next-to-last, since they are understood as defined within
# the page.
FIXED_PAGE_NAME = '_page'


class SphinxPage(PfscObj):

    def __init__(self, module, libpath):
        super().__init__()
        self.parent = module
        self.libpath = libpath
        self.name = FIXED_PAGE_NAME


def build_libpath_for_rst(
    config, sphinx_provided_pagename, within_page=False,
    extension=None, add_repo_version=False, add_tail_version=False
):
    """
    Build the libpath (possibly with version number) for a Proofscape entity
    defined in or by an rst file.

    :param config: the Sphinx app's ``config`` object
    :param sphinx_provided_pagename: the canonical pagename for the page,
        as provided by Sphinx, also sometimes known as "docname". This is
        the "/"-separated path, from the project root, down to and including
        the rst filename, WITHOUT the ``.rst`` extension.
    :param within_page: boolean, saying whether this Proofscape entity is
        equal to, or is regarded as belonging to, the ``SphinxPage`` defined by
        the rst file. For example, this should be ``True`` for the page and for
        any widgets defined in the page, but should be ``False`` for anything
        defined in pfsc module syntax under a ``pfsc::`` directive. In
        practical terms, this boolean simply controls whether we will attach
        the canonical '_page' path segment onto the module path, before any
        ``extension`` (see below).
    :param extension: str, optional extension to add onto end of path (should
        NOT begin with a dot). This will be attached to the module path if
        ``within_page`` is ``False``, or onto the page path if ``within_page``
        is ``True``.
    :param add_repo_version: set ``True`` to make it a repo-versioned libpath
    :param add_tail_version: set ``True`` to make it a tail-versioned libpath
    """
    libpath = sphinx_provided_pagename.replace("/", ".")
    if within_page:
        libpath += '.' + FIXED_PAGE_NAME
    if extension:
        libpath += '.' + extension

    prefix = config.pfsc_repopath
    if add_repo_version or add_tail_version:
        version_suffix = '@' + config.pfsc_repovers
        if add_repo_version:
            prefix += version_suffix
        else:
            libpath += version_suffix

    libpath = prefix + '.' + libpath
    return libpath


def form_pfsc_module_for_rst_file(app, docname, source):
    """
    Designed as a handler for the Sphinx 'source-read' event.

    It is when an rst source file has been read, that it is time
    to form a `PfscModule` and `SphinxPage`, to represent the module
    and page defined by that rst file.

    Either this is a "first run" (since last `make clean`), and this
    file does not yet have a `PfscModule` in the `env`; or it is not, in
    which case a `PfscModule` was already unpickled for this file, but
    we are re-reading the file since it has changed, in which case we
    just want to overwrite the existing `PfscModule` object. Either way,
    now is the time to form a `PfscModule` (and corresp. `SphinxPage`).
    """
    config = app.config
    modpath = build_libpath_for_rst(config, docname, within_page=False)
    pagepath = build_libpath_for_rst(config, docname, within_page=True)
    version = config.pfsc_repovers

    module = PfscModule(modpath)
    module.setRepresentedVersion(version)

    page = SphinxPage(module, pagepath)
    module[FIXED_PAGE_NAME] = page

    pfsc_env = get_pfsc_env(app.env)
    pfsc_env.pfsc_modules[modpath] = module

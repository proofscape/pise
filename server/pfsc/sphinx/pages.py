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

import json

from pfsc.lang.objects import EnrichmentPage, EnrichmentType
from pfsc.lang.modules import PfscModule, make_timestamp_for_module

import pfsc.constants


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


class SphinxPage(EnrichmentPage):
    """
    A SphinxPage does not have any "targets," like other Enrichments, but it
    does share the "page" behavior of Annotations, and it does need the
    `gather_doc_info()` method of the Enrichment class. It is therefore an
    EnrichmentPage.
    """

    def __init__(self, module, libpath):
        super().__init__(EnrichmentType.sphinxpage)
        self.parent = module
        self.libpath = libpath
        self.name = FIXED_PAGE_NAME
        self.widgets = []

    def get_index_type(self):
        return pfsc.constants.IndexType.SPHINX

    def get_proper_widgets(self):
        return self.widgets

    def add_widget(self, w):
        self.widgets.append(w)
        self[w.name] = w
        w.cascadeLibpaths()


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
    # I don't see any way to get the actual read time from Sphinx. Marking it
    # right now should be good enough.
    read_time = make_timestamp_for_module()

    config = app.config
    modpath = build_libpath_for_rst(config, docname, within_page=False)
    pagepath = build_libpath_for_rst(config, docname, within_page=True)
    version = config.pfsc_repovers

    module = PfscModule(modpath, version=version, read_time=read_time)
    module._rst_src = source[0]

    page = SphinxPage(module, pagepath)
    module[FIXED_PAGE_NAME] = page

    pfsc_env = get_pfsc_env(app.env)
    pfsc_env.add_module(modpath, module)


def get_sphinx_page(env, docname=None) -> SphinxPage:
    """
    Get a ``SphinxPage`` from the Sphinx environment.

    :param env: Sphinx ``BuildEnvironment``
    :param docname: the docname for the desired page. If not given, we will
        use ``env.docname``
    :return: ``SphinxPage`` or ``None``
    """
    pfsc_env = get_pfsc_env(env)
    docname = docname or env.docname
    config = env.config
    modpath = build_libpath_for_rst(config, docname, within_page=False)
    module = pfsc_env.get_module(modpath)
    return module[FIXED_PAGE_NAME] if module else None


SCRIPT_INTRO = 'window.pfsc_page_data = '
SCRIPT_ID = 'pfsc-page-data'


def inject_page_data(app, pagename, templatename, context, event_arg):
    """
    Handler for Sphinx 'html-page-context' event.

    Inject the necessary <script> tag into a document, recording the page data
    for that page (incl libpath, version, widget data, doc infos, etc.)
    """
    if app.builder.format != 'html':
        return
    page = get_sphinx_page(app.env, pagename)
    if not page:
        return
    page_data = page.get_page_data()
    body = f'\n{SCRIPT_INTRO}{json.dumps(page_data, indent=4)}\n'
    app.add_js_file(None, body=body, id=SCRIPT_ID)


class SphinxPfscEnvironment:
    """
    An instance of this class will be stored in the Sphinx BuildEnvironment,
    under the attribute 'proofscape'.

    It is designed to hold any and all data structures relevant to the
    sphinx-proofscape extension.

    It supports merge/purge operations, for Sphinx parallel builds.

    At this point, it is essentially just a wrapper around a dictionary of
    PfscModule instances, by libpath. Could just use a dictionary instead, but
    we keep this class in case useful in the future.
    """

    def __init__(self, app):
        # Lookup for PfscModule instances, by libpath.
        self.pfsc_modules = {}

    def update_modules(self, modules):
        """
        Update our dict of pfsc modules with a given dict.

        :param modules: dict of modules by modpath
        """
        self.pfsc_modules.update(modules)

    def get_modules(self):
        return self.pfsc_modules

    def add_module(self, modpath, module):
        self.pfsc_modules[modpath] = module

    def get_module(self, modpath):
        """
        Get a module from our lookup.
        """
        return self.pfsc_modules.get(modpath)

    def purge(self, app, docname):
        modpath = build_libpath_for_rst(app.config, docname, within_page=False)
        if modpath in self.pfsc_modules:
            del self.pfsc_modules[modpath]

    def merge(self, other):
        other_pfsc_env = get_pfsc_env(other)
        self.pfsc_modules.update(other_pfsc_env.pfsc_modules)


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
    get_pfsc_env(env).purge(app, docname)


def merge_pfsc_env(app, env, docnames, other):
    """
    Handler for the Sphinx 'env-merge-info' event.
    Updates the `SphinxPfscEnvironment` accordingly.
    """
    get_pfsc_env(env).merge(other)

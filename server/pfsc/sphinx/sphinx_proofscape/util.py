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

from sphinx.errors import SphinxError

from pfsc.excep import PfscExcep
from pfsc.checkinput import check_boxlisting


def build_intra_repo_libpath(pagename, extension=None):
    """
    Build the intra-repo libpath, i.e. the part coming after the repopath,
    for a Sphinx page, or for some item within a Sphinx page.

    :param pagename: the canonical pagename for the page, as provided by Sphinx
    :param extension: optional extension to add onto end of path (should NOT
        begin with a dot)
    """
    libpath = f'_sphinx.{pagename.replace("/", ".")}'
    if extension:
        libpath += '.' + extension
    return libpath


def build_libpath(config, pagename, extension=None,
                  add_repo_version=False, add_tail_version=False):
    """
    Build the libpath (possibly with version number) for a Sphinx page or for
    some item within a Sphinx page.

    :param config: the Sphinx app's `config` object
    :param pagename: the canonical pagename for the page, as provided by Sphinx
    :param extension: optional extension to add onto end of path (should NOT
        begin with a dot)
    :param add_repo_version: set True to make it a repo-versioned libpath
    :param add_tail_version: set True to make it a tail-versioned libpath
    """
    irl = build_intra_repo_libpath(pagename, extension=extension)
    prefix = config.pfsc_repopath
    if add_repo_version or add_tail_version:
        version_suffix = '@' + config.pfsc_repovers
        if add_repo_version:
            prefix += version_suffix
        else:
            irl += version_suffix
    libpath = prefix + '.' + irl
    return libpath


class ResolvedLibpath:

    def __init__(self, libpath, repopath, version):
        self.libpath = libpath
        self.repopath = repopath
        self.version = version


def find_lp_defn_for_docname(lp_defns, segment, docname, local_only=False):
    """
    Look for a libpath definition for a given segment, which pertains within
    a given document.

    If local_only is false, then we search definitions for the given document,
    as well as the index document of any directories above this one. If true,
    we search only defs for the given document.
    """
    lp = lp_defns.get(docname, {}).get(segment)
    if lp or local_only:
        return lp
    names = docname.split('/')
    for i in range(1, len(names) + 1):
        dn = '/'.join(names[:-i] + ['index'])
        lp = lp_defns.get(dn, {}).get(segment)
        if lp:
            return lp
    return None


def parse_box_listing(box_listing):
    """
    Return a list of libpath strings, or raise a SphinxError.

    Example:

        foo.bar, foo.{spam.baz, cat}

    is transformed into

        ['foo.bar', 'foo.spam.baz', foo.cat]
    """
    try:
        bl = check_boxlisting('', box_listing, {
            'libpath_type': {
                'short_okay': True,
            },
        })
    except PfscExcep as pe:
        raise SphinxError(str(pe))
    return bl.get_libpaths()

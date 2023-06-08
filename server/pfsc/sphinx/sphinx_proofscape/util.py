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
from pfsc.checkinput import check_boxlisting, check_libseg


def process_widget_label(raw_label):
    """
    Process a raw widget label, extracting an optional widget name, and
    stripping external whitespace.

    * If the raw label does not contain any colons, then the entire thing (stripped of external
        whitespace) is the final label, and the widget gets a system-supplied name.

    * If the raw label does contain one or more colons, then everything coming before the
        *first* one must be either a valid widget name, or empty (otherwise it's an error).

        In the first case, the widget takes the given name; in the second case, the system
        supplies one.

        In all cases, everything up to and including the first colon will be deleted, external
        whitespace will be stripped from what remains, and that will be the final label text.

    :returns: pair (name, text) being the widget name (possibly None),
        and final label text
    :raises: PfscExcep if the raw text contains a colon, but what comes before
        the first colon is neither empty nor a valid libpath segment.
    """
    name = None
    text = raw_label

    # If there is a colon...
    i0 = raw_label.find(":")
    if i0 >= 0:
        # ...and if the text up to the first colon is either empty or a valid libseg...
        prefix = raw_label[:i0]
        if i0 > 0:
            check_libseg('', prefix, {})
        # ...then that prefix is the widget name, while everything coming
        # *after* the colon is the text.
        name = prefix
        text = raw_label[i0 + 1:]

    # Strip external whitespace off the text.
    text = text.strip()

    return name, text


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

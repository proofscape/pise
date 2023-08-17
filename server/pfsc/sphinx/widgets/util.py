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

import re

from sphinx.errors import SphinxError

from pfsc.excep import PfscExcep, PECode
from pfsc.checkinput import check_boxlisting, check_libseg, check_dict


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

    :returns: pair (name, text) being the widget name (possibly None, possibly empty string),
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
            check_widget_name(prefix)
        # ...then that prefix is the widget name, while everything coming
        # *after* the colon, minus external whitespace, is the text.
        name = prefix
        text = raw_label[i0 + 1:]

    # Strip external whitespace off the text.
    text = text.strip()

    return name, text


def check_widget_name(raw):
    """
    Check that a string gives a valid widget name.
    """
    check_libseg('', raw, {})


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


def parse_dict_lines(text, keytype, valtype, key=None):
    """
    Parse the value of a single rST directive option, where the value is in a
    format we call "dictionary lines".

    Example:

        key1: single-line value
        key2: this is
            a multi-line
            value

    A new entry provides a key, followed by a colon, and then a value. The
    value may run over multiple lines, as long as subsequent lines are indented.
    External whitespace is stripped from final values (and keys).

    This function builds the dictionary, and checks the well-formedness of
    each key and value, using the given `keytype` and `valtype` specs.

    The checked dictionary is returned. In here, the keys and values are
    as returned by the type checker functions.

    :param text: (str) the raw text to be processed
    :param keytype: as in `pfsc.checkinput.check_dict()`
    :param valtype: as in `pfsc.checkinput.check_dict()`
    :param key: optionally pass the name of an input variable under which the
        raw text was received, for use in error message.

    :return: checked dict
    """
    lines = text.split('\n')

    entries = []
    entry = []
    for line in lines:
        if not line:
            continue
        if entry and not re.match(r'\s', line):
            entries.append(entry)
            entry = []
        entry.append(line)
    if entry:
        entries.append(entry)

    d = {}
    for entry in entries:
        line0 = entry[0]
        i0 = line0.find(":")
        if i0 <= 0:
            raise PfscExcep('Bad dictionary', PECode.INPUT_WRONG_TYPE, bad_field=key)
        key = line0[:i0].strip()
        value = line0[i0+1:]
        value = '\n'.join([value] + entry[1:])
        value = value.strip()
        d[key] = value

    cd = check_dict(key, d, {
        'keytype': keytype,
        'valtype': valtype,
    })
    return cd

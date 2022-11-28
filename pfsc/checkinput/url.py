# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2022 Proofscape contributors                           #
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

import urllib.parse as urlparse

from markupsafe import Markup

from pfsc.util import escape_url
from pfsc.excep import PfscExcep, PECode

class CheckedURL:

    def __init__(self, given, splitResult, escaped_url):
        self.given = given
        self.splitResult = splitResult
        self.escaped_url = escaped_url
        self.scheme_ok = None
        self.netloc_ok = None


def check_url(key, raw, typedef):
    """
    Check a URL:
        * well-formed, in that `urlparse.urlsplit` does not raise a ValueError.
        * scheme is not `javascript` (in any mixture of lower- and upper-case).
        * optional further checks defined by the typedef.

    typedef:
        opt:
            allowed_schemes: list of allowed schemes; if not provided, assume
              all schemes are ok, _except `javascript`_. The `javascript`
              scheme always raises an exception.
            allowed_netlocs: list of allowed notlocs; if not provided, assume
              all netlocs are ok
            unescape_first: boolean. Set True in order to indicate that the
              raw value is expected to be an instance of Markup, and that we
              should unescape it before attempting to parse it.
            return:
              undefined: a CheckedURL instance
              'escaped_url': just the `escaped_url` property of the CheckedURL
                instance

    :return: controlled by `return` option
    """
    unescape_first = typedef.get('unescape_first', False)
    if unescape_first:
        if not isinstance(raw, Markup):
            raise TypeError
        url_string = raw.unescape()
    else:
        url_string = raw

    try:
        splitResult = urlparse.urlsplit(url_string)
    except ValueError:
        raise PfscExcep('Malformed URL.', PECode.BAD_URL, bad_field=key)

    escaped_url_string = escape_url(url_string)

    checked = CheckedURL(raw, splitResult, escaped_url_string)

    if splitResult.scheme.lower() == 'javascript':
        raise PfscExcep('javascript URL', PECode.BAD_URL, bad_field=key)

    if 'allowed_schemes' in typedef:
        schemes = typedef['allowed_schemes']
        if splitResult.scheme not in schemes:
            checked.scheme_ok = False
            raise PfscExcep('Bad scheme', PECode.BAD_URL, bad_field=key)
        checked.scheme_ok = True

    if 'allowed_netlocs' in typedef:
        netlocs = typedef['allowed_netlocs']
        if splitResult.netloc not in netlocs:
            checked.netloc_ok = False
            raise PfscExcep('Bad netloc', PECode.BAD_URL, bad_field=key)
        checked.netloc_ok = True

    return_type = typedef.get('return')
    if return_type == 'escaped_url':
        return checked.escaped_url
    else:
        return checked

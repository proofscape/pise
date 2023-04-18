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

"""
Routes serving the OCA (One-Container App)
"""

import json
import re

from flask import Blueprint

from pfsc import check_config
from pfsc.methods import try_to_proxy


bp = Blueprint('oca', __name__)


@bp.route('/latestVersion', methods=["GET"])
def latest_version():
    """
    Check the latest version number for the OCA.

    The reason for supplying an endpoint for this, instead of simply letting
    the client-side code make the request directly, is that we expect the
    request to be one that goes outside the Content Security Policy we set for
    the app. In particular, if it is a request to raw.githubusercontent.com,
    that is probably a domain we want to exclude from our CSP.

    @return: Either the version number, if we managed to obtain it, or else
        an empty string.
    """
    if not check_config("IS_OCA"):
        return '', 403

    ns = check_config("OCA_DOCKERHUB_NAMESPACE")
    rp = check_config("OCA_DOCKERHUB_REPO")
    desired_url = f"https://hub.docker.com/v2/namespaces/{ns}/repositories/{rp}/tags"
    robots_url = f"https://hub.docker.com/robots.txt"
    RESULTS = 'results'
    sorry = ''

    j = try_to_proxy(desired_url, robots_url=robots_url)
    if j is None:
        return sorry
    try:
        d = json.loads(j)
    except json.decoder.JSONDecodeError:
        return sorry
    if RESULTS not in d:
        return sorry
    r = d[RESULTS]
    names = {result.get('name') for result in r} - {"latest", "edge", "testing", None}
    if not names:
        return sorry

    # NOTE: As long as images with old-style numbers exist on Docker Hub (i.e.
    # unless we at some point delete them from there), we have to have the code
    # here that makes old- and new-style numbers comparable.
    #
    # However, the final number we return, if new-style, will *not* have the
    # '26.0' padding at the front. This is because we're keeping the client-side
    # comparison code simple, and not bothering there with old-style numbers.

    # Old-style numbers were of the form
    #   CM.Cm-SM.Sm.Sp(-n)
    # while new-style numbers are of the form
    #   M.m.p(-n)
    # In the old-style numbers, the client numbers (CM.Cm) never got past 25.2,
    # so we can make all lists comparable by prepending [26, 0] to the new ones.
    string_parts = [(re.split(r'[.-]', n), n) for n in names]

    int_parts_padded = []
    for parts, name in string_parts:
        if len(parts) > 4:
            int_parts_padded.append(([int(n) for n in parts], name))
        else:
            # Is there a label (i.e. fourth part)?
            # New-style numbers may use a fourth part with an 'a' or 'b' for alpha
            # and beta releases. We turn such labels into two integers.
            if len(parts) == 4:
                n = parts[-1]
                if n[0] == 'a':
                    x, y = 1, n[1:]
                elif n[0] == 'b':
                    x, y = 2, n[1:]
                else:
                    x, y = 0, n
                parts[-1] = x
                parts.append(y)

            int_parts_padded.append(([26, 0] + [int(n) for n in parts], name))

    _, latest_name = list(sorted(int_parts_padded, key=lambda p: p[0]))[-1]
    return latest_name


@bp.route('/EULA', methods=["GET"])
def eula():
    """
    Load the text of the EULA.
    """
    if not check_config("IS_OCA"):
        return '', 403
    with open(check_config("EULA_FILE")) as f:
        text = f.read()
    return text


@bp.route('/extraAboutInfo', methods=["GET"])
def extra_about_info():
    """
    Load the extra info from `about.json` for the "About" dialog.
    """
    if not check_config("IS_OCA"):
        return '', 403
    with open(check_config("ABOUT_JSON_FILE")) as f:
        text = f.read()
    return text

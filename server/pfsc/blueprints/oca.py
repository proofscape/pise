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

"""
Routes serving the OCA (One-Container App)
"""

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
    vers = try_to_proxy(check_config("OCA_LATEST_VERSION_URL"))
    return vers.strip() if vers else ''


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

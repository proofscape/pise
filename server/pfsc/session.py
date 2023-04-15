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

import secrets

from flask import session, has_app_context, has_request_context

import pfsc.constants
from pfsc import check_config
from pfsc.build.repo import RepoInfo
from pfsc.util import short_unpronouncable_hash
from pfsc.excep import PfscExcep, PECode


def get_csrf_from_session(supply_if_absent=False):
    token = session.get("CSRF")
    if token is None:
        if supply_if_absent:
            token = secrets.token_urlsafe(32)
            session["CSRF"] = token
        else:
            raise PfscExcep('Session has no CSRF token.', PECode.SESSION_HAS_NO_CSRF_TOKEN)
    return token

def get_demo_username_from_session(supply_if_absent=False):
    demo_username = session.get(pfsc.constants.DEMO_USERNAME_SESSION_KEY)
    if demo_username is None and supply_if_absent:
        demo_username = short_unpronouncable_hash(length=7, start_with_letter=True)
        session[pfsc.constants.DEMO_USERNAME_SESSION_KEY] = demo_username
    return demo_username

def repopath_is_demo_for_session(repopath):
    ri = RepoInfo(repopath)
    if not ri.is_demo():
        return False
    demo_username = get_demo_username_from_session(supply_if_absent=True)
    return ri.user == demo_username

def make_demo_user_path():
    if has_app_context() and check_config("PROVIDE_DEMO_REPOS"):
        if has_request_context():
            demo_username = get_demo_username_from_session(supply_if_absent=True)
            return f'demo.{demo_username}'
    return None

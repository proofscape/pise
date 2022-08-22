# --------------------------------------------------------------------------- #
#   Proofscape Server                                                         #
#                                                                             #
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

import json

from flask import (
    Blueprint, flash, get_flashed_messages,
    redirect, render_template, request, url_for
)
from flask_login import current_user

from pfsc import check_config
from pfsc.methods import handle_and_redirect, handle_and_jsonify
from pfsc.handlers.auth import (
    LogoutHandler,
    TestRepoLoginHandler,
    OAuthStep1_SendUserAway,
    OAuthStep2_ReceiveRedirect,
)


bp = Blueprint('auth', __name__)


@bp.route('/login')
def login_page():
    """
    Serve a login page.
    """
    if current_user.is_authenticated:
        flash(json.dumps({
            'type': 'auto_close',
            'delay': 0,
        }), category='control')
        return redirect(url_for('auth.login_success'))
    if check_config("PRE_APPROVED_LOGINS_ONLY"):
        flash(PRE_APPROVED_LOGINS_ONLY_MESSAGE, category='warning')

    tos_url = check_config("TOS_URL")
    tos_js = f"window.open('{tos_url}', 'tos', 'width=700,height=740,left=22,top=22')" if tos_url else None
    prpo_url = check_config("PRPO_URL")
    prpo_js = f"window.open('{prpo_url}', 'prpo', 'width=700,height=740,left=44,top=44')" if prpo_url else None

    return render_template(
        "login.html",
        title="Proofscape Sign in",
        branding_img_url=check_config("LOGIN_PAGE_BRANDING_IMG_URL"),
        tos_js=tos_js,
        prpo_js=prpo_js,
        use_checkboxes=check_config("LOGIN_PAGE_USE_AGREEMENT_CHECKBOXES"),
        allow_test_repo_logins=check_config("ALLOW_TEST_REPO_LOGINS"),
        allow_github_logins=check_config("ALLOW_GITHUB_LOGINS"),
        allow_bitbucket_logins=check_config("ALLOW_BITBUCKET_LOGINS"),
        css=[
            url_for('static', filename='css/login.css'),
        ]
    )


PRE_APPROVED_LOGINS_ONLY_MESSAGE = """
<strong>Invitation only!</strong>
At this time only pre-approved users are able to sign in.
If you have received an invitation, please sign in below.
"""


@bp.route('/login_success')
def login_success():
    messages = get_flashed_messages(with_categories=True)
    auto_close = False
    auto_close_delay = None
    for mtype, msg in messages:
        if mtype == 'control':
            try:
                d = json.loads(msg)
                if d['type'] == 'auto_close':
                    auto_close_delay = max(0, int(d['delay']))
            except (json.decoder.JSONDecodeError, ValueError):
                pass
            else:
                auto_close = True
    return render_template(
        "login_success.html",
        title="Proofscape Sign in",
        branding_img_url=check_config("LOGIN_PAGE_BRANDING_IMG_URL"),
        auto_close=auto_close,
        auto_close_delay=auto_close_delay,
        css=[
            url_for('static', filename='css/login.css'),
        ]
    )


@bp.route('/logout')
def logout():
    return handle_and_jsonify(LogoutHandler, request.args)


@bp.route('/testRepoLogin', methods=["POST"])
def login_as_test_repo_owner():
    return handle_and_redirect(TestRepoLoginHandler, request.form)


@bp.route('/loginWith/<prov>/<level>')
def login_with_provider(prov, level):
    info = {'prov': prov, 'level': level}
    return handle_and_redirect(OAuthStep1_SendUserAway, info)


@bp.route('/redirFrom/<prov>')
def redir_from_provider(prov):
    info = {'prov': prov}
    info.update(request.args)
    return handle_and_redirect(OAuthStep2_ReceiveRedirect, info)

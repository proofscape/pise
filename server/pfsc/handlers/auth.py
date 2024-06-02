# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2024 Proofscape Contributors                           #
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

from urllib.parse import urlencode, quote
import json
import secrets

from flask import session, flash, abort, url_for
from flask_login import current_user, login_user, logout_user
from markupsafe import Markup
import requests

from pfsc import check_config
from pfsc.gdb import get_graph_writer
from pfsc.handlers import Handler
from pfsc.checkinput import IType
from pfsc.excep import PfscExcep, PECode
from pfsc.permissions import check_is_psm
import pfsc.constants
from pfsc.constants import UserProps


OAUTH_GH_ID = check_config("OAUTH_GH_ID")
OAUTH_BB_ID = check_config("OAUTH_BB_ID")
OAUTH_GH_SECRET = check_config("OAUTH_GH_SECRET")
OAUTH_BB_SECRET = check_config("OAUTH_BB_SECRET")


class LogoutHandler(Handler):
    """
    Logout is handled by a Handler class just to check the CSRF token.
    """

    def check_permissions(self):
        pass

    def go_ahead(self):
        logout_user()


class LoginHandler(Handler):

    def __init__(self, request_info):
        super().__init__(request_info)
        self.flash_err_msg = True
        self.redir_by_err_code = {
            0: url_for('auth.login_success'),
            Handler.DEFAULT_ERR_CODE: url_for('auth.login_page')
        }
        # By definition, a CSRF attack is one in which you are _already_ logged
        # in, and the request has some potentially harmful side-effects. Therefore
        # there's no reason to require a CSRF token when the request itself is a
        # login request. Furthermore, OAuth providers aren't going to send our
        # CSRF token (they do bounce back our `state` token, which plays a
        # similar role).
        self.do_require_csrf = False

    def check_permissions(self):
        # Everyone has permission to _try_ to log in.
        pass

    def give_up(self, msg='Failed login'):
        raise PfscExcep(msg, PECode.LOGIN_INCORRECT)


class TestRepoLoginHandler(LoginHandler):
    """
    Handles logins as owner of one of the `test.` repos
    i.e. repos of path `test.user.repo`.

    Env var "ALLOW_TEST_REPO_LOGINS" must be truthy to get
    anything other than a 403. Then password must equal username
    for a successful login. This allows to test both successful
    and failed logins.
    """

    def check_enabled(self):
        if not check_config("ALLOW_TEST_REPO_LOGINS"):
            abort(403)

    def check_input(self):
        self.check({
            "REQ": {
                'username': {
                    'type': IType.LIBSEG,
                },
                'password': {
                    'type': IType.STR,
                },
            },
            "OPT": {
                'orgs': {
                    'type': IType.CDLIST,
                    'itemtype': {
                        'type': IType.STR
                    },
                    'default_cooked': [],
                },
            },
        })

    def go_ahead(self, username, password, orgs):
        username = username.value
        if password == username:
            pfsc_username = f'test.{username}'
            email = f'{pfsc_username}@{check_config("EMAIL_DOMAIN_FOR_TEST_USERS")}'
            orgs_owned_by_user = orgs
            _actually_log_in_after_checks(pfsc_username, email, orgs_owned_by_user,
                                          login_checks_have_been_performed=True)
        else:
            msg = 'Username or password is incorrect.'
            raise PfscExcep(msg, PECode.LOGIN_INCORRECT)



class OAuthStep1_SendUserAway(LoginHandler):
    """
    Perform Step 1 of an OAuth login: sending the user to
    the identity provider, to login there, and grant us access.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'prov': {
                    'type': IType.STR,
                    'values': ['gh', 'bb'],
                },
                'level': {
                    'type': IType.STR,
                    'values': [
                        # Just verify your identity as a user:
                        'user',
                        # Also verify your organization ownership:
                        'owner',
                    ]
                },
            },
        })

    def check_permissions(self, prov):
        if prov == 'gh' and not check_config("ALLOW_GITHUB_LOGINS"):
            raise PfscExcep('Not accepting logins via GitHub', PECode.OAUTH_PROVIDER_NOT_ACCEPTED)
        if prov == 'bb' and not check_config("ALLOW_BITBUCKET_LOGINS"):
            raise PfscExcep('Not accepting logins via BitBucket', PECode.OAUTH_PROVIDER_NOT_ACCEPTED)

    def go_ahead(self, prov, level):
        if current_user.is_authenticated:
            return

        state = secrets.token_urlsafe(32)
        session['oauth_state'] = state

        check_orgs = (level == 'owner')
        session['check_orgs'] = check_orgs

        base = {
            'gh': 'https://github.com/login/oauth/authorize?',
            'bb': 'https://bitbucket.org/site/oauth2/authorize?'
        }[prov]
        a = {
            'gh': {
                "client_id": OAUTH_GH_ID,
                "state": state,
                "scope": "user:email read:org" if check_orgs else "user:email",
            },
            # TODO:
            #   Support org ownership checks for BitBucket.
            #   (In BitBucket they're called "workspaces".)
            'bb': {
                "client_id": OAUTH_BB_ID,
                "state": state,
                "response_type": "code",
            }
        }[prov]
        # Default quoting is via the `quote_plus` func, but that turns spaces
        # into `+` signs; we want them to become `%20`. GitHub requires
        # multiple scopes to be separated by this.
        args = urlencode(a, quote_via=quote)
        url = base + args
        assert url[:6] == "https:"
        self.set_response_field('redirect', url)

class OAuthStep2_ReceiveRedirect(LoginHandler):
    """
    Perform Step 2 of an OAuth login: receive the redirect from
    the identity provider.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'prov': {
                    'type': IType.STR,
                    'values': ['gh', 'bb'],
                },
            },
            "OPT": {
                # BitBucket offers the user a "cancel" button, which will redirect
                # them here, but with an "error" arg.
                'error': {
                    'type': IType.STR,
                    'default_cooked': None,
                },
                # The state should be bounced back, to prevent CSRF.
                'state': {
                    'type': IType.STR,
                    'default_cooked': None,
                },
                # If all went well, we should be given a code with which we can now
                # request our access token.
                'code': {
                    'type': IType.STR,
                    'default_cooked': None,
                },
            }
        })
        self.force_input_field('check_orgs', bool(session.get('check_orgs')))

    def check_permissions(self, prov):
        if prov == 'gh' and not check_config("ALLOW_GITHUB_LOGINS"):
            raise PfscExcep('Not accepting logins via GitHub', PECode.OAUTH_PROVIDER_NOT_ACCEPTED)
        if prov == 'bb' and not check_config("ALLOW_BITBUCKET_LOGINS"):
            raise PfscExcep('Not accepting logins via BitBucket', PECode.OAUTH_PROVIDER_NOT_ACCEPTED)

    def confirm(self, prov, error, state, code):
        if error == "access_denied":
            # This happens when the user clicks "Cancel" at BitBucket.
            self.give_up("Login canceled.")
        if (
            error is not None or
            state is None or state != session.get('oauth_state') or
            code is None
        ):
            self.give_up("Something went wrong. Please try again.")
        assert error is None
        assert state == session.get('oauth_state')
        assert code is not None

    def go_ahead(self, prov, state, code, check_orgs):
        token = self.request_access_token(prov, state, code, check_orgs)
        username, email, orgs_owned_by_user = self.make_info_requests(prov, token, check_orgs)
        self.complete_login(prov, username, email, orgs_owned_by_user, check_orgs)

    def request_access_token(self, prov, state, code, check_orgs):
        # Step 2: Obtain access token.
        client_id = {
            'gh': OAUTH_GH_ID,
            'bb': OAUTH_BB_ID
        }[prov]
        client_secret = {
            'gh': OAUTH_GH_SECRET,
            'bb': OAUTH_BB_SECRET
        }[prov]
        headers = {
            "Accept": "application/json"
        }
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "state": state,
        }
        if prov == 'bb':
            payload["grant_type"] = "authorization_code"
        url = {
            'gh': 'https://github.com/login/oauth/access_token',
            'bb': 'https://bitbucket.org/site/oauth2/access_token'
        }[prov]
        assert url[:6] == "https:"
        r = requests.post(url, headers=headers, data=payload)
        j = r.content.decode("utf-8")
        d = json.loads(j)

        # Check that the required access scope was granted.
        granted = False
        if prov == 'gh':
            granted_scope_set = set(d.get("scope").split(','))
            granted = "user:email" in granted_scope_set
            if check_orgs:
                granted &= "read:org" in granted_scope_set
        elif prov == 'bb':
            if check_orgs:
                pass  # TODO
            else:
                granted = (d.get("scopes") == "account")

        token = d.get("access_token")
        if not granted:
            self.give_up("Insufficient permissions granted. Please try again.")
        if not token:
            self.give_up("Something went wrong. Please try again.")
        assert granted
        return token

    def make_info_requests(self, prov, token, check_orgs):
        # Step 3: Obtain info using the API
        assert token is not None
        headers = {
            'gh': {
                "Authorization": "token " + token,
                "Accept": "application/vnd.github.v3+json",
            },
            'bb': {
                "Authorization": "Bearer " + token,
            }
        }[prov]

        # Get username
        url = {
            'gh': 'https://api.github.com/user',
            'bb': 'https://api.bitbucket.org/2.0/user'
        }[prov]
        assert url[:6] == "https:"
        r = requests.get(url, headers=headers)
        j = r.content.decode("utf-8")
        d = json.loads(j)
        #print("*"*80)
        #print('user info:', json.dumps(d, indent=4))
        #print("*" * 80)
        username_key = {
            'gh': 'login',
            'bb': 'username'
        }[prov]
        username = d.get(username_key)

        # Get email
        url = {
            'gh': 'https://api.github.com/user/emails',
            'bb': 'https://api.bitbucket.org/2.0/user/emails'
        }[prov]
        assert url[:6] == "https:"
        r = requests.get(url, headers=headers)
        j = r.content.decode("utf-8")
        d = json.loads(j)
        #print("@" * 80)
        #print('email info:', json.dumps(d, indent=4))
        #print("@" * 80)
        email = None
        if prov == 'gh':
            # d is a list
            for info in d:
                if info.get("primary") and info.get("verified"):
                    email = info.get("email")
        elif prov == 'bb':
            # d is dict; list of addresses at "values" key
            values = d.get("values", [])
            for info in values:
                if info.get("is_primary") and info.get("is_confirmed"):
                    email = info.get("email")

        orgs_owned_by_user = []
        if check_orgs:
            if prov == 'gh':
                url = 'https://api.github.com/user/memberships/orgs?state=active'
                assert url[:6] == "https:"
                r = requests.get(url, headers=headers)
                j = r.content.decode("utf-8")
                d = json.loads(j)
                #print("&" * 80)
                #print('user orgs:', json.dumps(d, indent=4))
                #print("&" * 80)
                for org in d:
                    if org.get("role") == "admin":
                        org_name = org.get("organization", {}).get("login")
                        if org_name:
                            orgs_owned_by_user.append(org_name)
            elif prov == 'bb':
                # TODO:
                #   Handle 'check_orgs' for prov == 'bb'
                pass

        # Check
        if email is None:
            self.give_up("Your account does not seem to have a verified, primary email address.")
        if username is None:
            self.give_up("Unable to obtain username. Please try again.")

        return username, email, orgs_owned_by_user

    def complete_login(self, prov, username, email, orgs_owned_by_user, check_orgs):
        # Step 4: Complete the login.
        assert email is not None
        assert username is not None
        assert isinstance(orgs_owned_by_user, list)
        # The Proofscape username is obtained by joining the provider abbreviation,
        # and the username at that provider, with a dot. Thus, it is equal to the
        # first two segments of the libpath of any repo owned by that user.
        # E.g. if you sign in with GitHub and you username there is foo, then your
        # username here will be `gh.foo`.
        pfsc_username = f'{prov}.{username}'
        pre_approved_only = check_config("PRE_APPROVED_LOGINS_ONLY")
        if pre_approved_only:
            approved_logins = check_config("APPROVED_LOGINS")
            admin_users = check_config("ADMIN_USERS")
            if pfsc_username not in approved_logins + admin_users:
                msg = f'Sorry, the server is accepting only pre-approved log-ins,'
                msg += f' and username `{pfsc_username}` has not been pre-approved.'
                self.give_up(msg)
        _actually_log_in_after_checks(pfsc_username, email, orgs_owned_by_user,
                                      org_ownership_check_was_requested=check_orgs,
                                      login_checks_have_been_performed=True)


def _actually_log_in_after_checks(pfsc_username, email, orgs_owned_by_user,
                                  org_ownership_check_was_requested=False,
                                  login_checks_have_been_performed=False):
    """
    !!! WARNING WARNING WARNING WARNING WARNING !!!

    This signs a user in (or up) without any checks!
    For use only by handlers that have already verified
    a login!

    * Handles existing OR brand new logins (in the latter
      case email must be provided).
    * Flashes a standard "welcome" or "welcome back" message.
    * Actually marks the session so the user is logged in.

    :param pfsc_username: a full, Proofscape username, i.e.
      a name of the form `host.user`.
    :param email: the user's email address
    :param orgs_owned_by_user: list of strings, being the names of organizations
        at `host` that are owned by `user`. E.g. `example_org` if `gh.example_org`
        is an org owned by `gh.user`.
    :param org_ownership_check_was_requested: boolean, saying whether the user
        wanted us to check for org ownership. Helps us produce a helpful message.
    :return: nothing
    """
    if not login_checks_have_been_performed:
        return

    gw = get_graph_writer()

    user, is_new = gw.merge_user(
        pfsc_username, UserProps.V_USERTYPE.USER, email, orgs_owned_by_user)

    prov, prov_username = pfsc_username.split('.')
    full_prov_name = {'gh': 'GitHub', 'bb': 'BitBucket', 'test': 'test'}[prov]

    for org_name in orgs_owned_by_user:
        org_path = f'{prov}.{org_name}'
        gw.merge_user(org_path, UserProps.V_USERTYPE.ORG, None, [])

    msg = ''
    msg += '<h2>Sign in successful</h2>'
    msg += f'<p>You signed in as <strong>{full_prov_name}</strong> user <strong>{prov_username}</strong>.'
    msg += f' Your username in PISE is <strong>{pfsc_username}</strong>.</p>'
    msg += f'<p>Email: {email}</p>'
    if orgs_owned_by_user:
        msg += '<p>You were recognized as an owner of the following organizations:</p>'
        msg += '<ul>'
        for org_name in orgs_owned_by_user:
            msg += f'<li>{prov}.{org_name}</li>'
        msg += '</ul>'
    elif org_ownership_check_was_requested:
        msg += '<p>We did not find any organizations of which you are an owner.</p>'
    msg += '<p>You can close this window now.</p>'
    msg = Markup(msg)
    flash(msg)

    # Keeping the auto_close business here to document how it's done; but
    # I now think closing this window is a bad user experience (taking away
    # text before the user has a chance to read it).
    do_auto_close = False
    if not is_new:
        if do_auto_close:
            flash(json.dumps({
                'type': 'auto_close',
                'delay': 2000,
            }), category='control')

    # Now can log the user in, whether newly created or existing.
    login_user(user)


def _log_in_as_default_user_in_psm():
    """
    Log in as the default user, when configured in personal server mode.
    """
    if check_is_psm():
        default_username = pfsc.constants.DEFAULT_USER_NAME
        default_email = pfsc.constants.DEFAULT_USER_EMAIL
        orgs_owned_by_user = []
        gw = get_graph_writer()
        user, _ = gw.merge_user(
            default_username, UserProps.V_USERTYPE.USER,
            default_email, orgs_owned_by_user
        )
        login_user(user)

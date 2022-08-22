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

from flask_login import current_user

from tests import login_context, user_context, handleAsJson
from config import HostingStance
from pfsc.gdb import get_graph_writer, get_graph_reader
from pfsc.gdb.user import HostingStatus
from pfsc.constants import UserProps, WIP_TAG
from pfsc.excep import PECode


def test_user_hosting_status_00(client):
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.UNAVAILABLE
    with login_context(client, 'moo'):
        with client.test_request_context():
            status, _ = current_user.hosting_status('test.moo.bar', 'v2.0.0')
            assert status == HostingStatus.MAY_NOT_REQUEST


def test_user_hosting_status_01(client):
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.BY_REQUEST
    with login_context(client, 'moo'):
        with client.test_request_context():
            status, _ = current_user.hosting_status('test.moo.bar', 'v2.0.0')
            assert status == HostingStatus.MAY_REQUEST


def test_user_hosting_status_02(client):
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.FREE
    with login_context(client, 'moo'):
        with client.test_request_context():
            status, _ = current_user.hosting_status('test.moo.bar', 'v2.0.0')
            assert status == HostingStatus.GRANTED


def test_user_hosting_status_03(client):
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.BY_REQUEST
    with login_context(client, 'moo'):
        with client.test_request_context():
            current_user.set_hosting(UserProps.V_HOSTING.GRANTED, 'test.moo')
            current_user.commit_properties()

            d = current_user.get_hosting_settings()
            print('\n', json.dumps(d, indent=4))

            status, _ = current_user.hosting_status('test.moo.bar', 'v2.0.0')
            assert status == HostingStatus.GRANTED


def test_user_hosting_status_04(client):
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.BY_REQUEST
    with login_context(client, 'moo'):
        with client.test_request_context():
            current_user.set_hosting(UserProps.V_HOSTING.GRANTED, 'test.moo.bar')
            current_user.set_hosting(UserProps.V_HOSTING.DENIED, 'test.moo.foo')
            current_user.set_hosting(UserProps.V_HOSTING.PENDING, 'test.moo.foo', version='v3.1.4')
            current_user.commit_properties()

            d = current_user.get_hosting_settings()
            print('\n', json.dumps(d, indent=4))

            status, _ = current_user.hosting_status('test.moo.bar', 'v2.0.0')
            assert status == HostingStatus.GRANTED

            status, _ = current_user.hosting_status('test.moo.foo', 'v2.0.0')
            assert status == HostingStatus.MAY_NOT_REQUEST

            status, _ = current_user.hosting_status('test.moo.foo', 'v3.1.4')
            assert status == HostingStatus.PENDING

            status, _ = current_user.hosting_status('test.moo.spam', 'v1.0.0')
            assert status == HostingStatus.MAY_REQUEST


def test_user_hosting_status_05(client):
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.BY_REQUEST
    with login_context(client, 'moo'):
        with client.test_request_context():
            current_user.set_hosting(
                UserProps.V_HOSTING.GRANTED, 'test.moo.bar', version='v2.0.0',
                hash='deadbea7'
            )
            current_user.set_hosting(
                UserProps.V_HOSTING.PENDING, 'test.moo.bar', version='v2.1.0'
            )
            current_user.set_hosting(
                UserProps.V_HOSTING.DENIED, 'test.moo.bar', version='v2.1.1'
            )
            current_user.commit_properties()

            d = current_user.get_hosting_settings()
            print('\n', json.dumps(d, indent=4))

            status, hash = current_user.hosting_status('test.moo.bar', 'v2.0.0')
            assert status == HostingStatus.GRANTED
            assert hash == 'deadbea7'

            status, _ = current_user.hosting_status('test.moo.bar', 'v2.1.0')
            assert status == HostingStatus.PENDING

            status, _ = current_user.hosting_status('test.moo.bar', 'v2.1.1')
            assert status == HostingStatus.DENIED

            status, _ = current_user.hosting_status('test.moo.bar', 'v2.2.0')
            assert status == HostingStatus.MAY_REQUEST

            # Try unsetting denial; should go back to option to request
            current_user.set_hosting(
                None, 'test.moo.bar', version='v2.1.1'
            )
            current_user.commit_properties()

            d = current_user.get_hosting_settings()
            print('\n', json.dumps(d, indent=4))

            status, _ = current_user.hosting_status('test.moo.bar', 'v2.1.1')
            assert status == HostingStatus.MAY_REQUEST


def test_user_hosting_status_06(client):
    with login_context(client, 'moo'):
        with client.test_request_context():
            status, _ = current_user.hosting_status('test.moo.bar', WIP_TAG)
            assert status == HostingStatus.NA


def test_user_hosting_status_07(client):
    with login_context(client, 'moo'):
        with client.test_request_context():
            status, _ = current_user.hosting_status('test.foo.bar', 'v2.0.0')
            assert status == HostingStatus.DOES_NOT_OWN


lorem_ipsum_446 = """\
Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis
nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore
eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt
in culpa qui officia deserunt mollit anim id est laborum.
"""

def test_request_hosting_00(client):
    """
    Repo is owned directly by the user.
    Hosting request is successful.
    """
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.BY_REQUEST
    with login_context(client, 'moo'):
        resp = client.post('/ise/requestHosting', data={
            'repopath': 'test.moo.bar', 'vers': 'v2.0.0',
            'comment': lorem_ipsum_446
        })
        d = handleAsJson(resp)
        print('\n', json.dumps(d, indent=4))
        assert d["err_lvl"] == 0
        assert d["new_hosting_status"] == HostingStatus.PENDING
        assert d["rev_msg_len"] == 6255
        assert d["usr_msg_len"] == 5989


def test_request_hosting_00b(client):
    """
    This time, comment string is empty.
    """
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.BY_REQUEST
    with login_context(client, 'moo'):
        resp = client.post('/ise/requestHosting', data={
            'repopath': 'test.moo.bar', 'vers': 'v2.0.0',
            'comment': '',
        })
        d = handleAsJson(resp)
        print('\n', json.dumps(d, indent=4))
        assert d["err_lvl"] == 0
        assert d["new_hosting_status"] == HostingStatus.PENDING
        assert d["rev_msg_len"] == 5387
        assert d["usr_msg_len"] == 5121


def test_request_hosting_01(client):
    """
    Hosting request fails because user does not own repo.
    """
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.BY_REQUEST
    with login_context(client, 'foo'):
        resp = client.post('/ise/requestHosting', data={
            'repopath': 'test.moo.bar', 'vers': 'v2.0.0'
        })
        d = handleAsJson(resp)
        print('\n', json.dumps(d, indent=4))
        assert d["err_lvl"] == PECode.HOSTING_REQUEST_REJECTED
        assert d["err_msg"].find("owner") > 0


def test_request_hosting_02(client):
    """
    Repo is owned directly by the user.
    Hosting request fails because request is already pending.
    """
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.BY_REQUEST
    with login_context(client, 'moo'):

        with client.test_request_context():
            current_user.set_hosting(UserProps.V_HOSTING.PENDING, 'test.moo.bar', version='v2.0.0')
            current_user.commit_properties()

        resp = client.post('/ise/requestHosting', data={
            'repopath': 'test.moo.bar', 'vers': 'v2.0.0'
        })
        d = handleAsJson(resp)
        print('\n', json.dumps(d, indent=4))
        assert d["err_lvl"] == PECode.HOSTING_REQUEST_UNNECESSARY
        assert d["err_msg"].find("already been requested") > 0


def test_request_hosting_03(client):
    """
    Repo is owned directly by the user.
    Hosting request fails because request has already been granted.
    """
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.BY_REQUEST
    with login_context(client, 'moo'):

        with client.test_request_context():
            current_user.set_hosting(UserProps.V_HOSTING.GRANTED, 'test.moo.bar')
            current_user.commit_properties()

        resp = client.post('/ise/requestHosting', data={
            'repopath': 'test.moo.bar', 'vers': 'v2.0.0'
        })
        d = handleAsJson(resp)
        print('\n', json.dumps(d, indent=4))
        assert d["err_lvl"] == PECode.HOSTING_REQUEST_UNNECESSARY
        assert d["err_msg"].find("already been granted") > 0


def test_request_hosting_10(client):
    """
    Repo is owned by on org the user owns.
    Hosting request is successful.
    """
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.BY_REQUEST
    with login_context(client, 'moo', owned_orgs=['bar']):
        resp = client.post('/ise/requestHosting', data={
            'repopath': 'test.bar.foo', 'vers': 'v2.0.0'
        })
        d = handleAsJson(resp)
        print('\n', json.dumps(d, indent=4))
        assert d["err_lvl"] == 0
        assert d["new_hosting_status"] == HostingStatus.PENDING
        assert d["rev_msg_len"] == 5387
        assert d["usr_msg_len"] == 5121


def test_request_hosting_12(client):
    """
    Repo is owned by on org the user owns.
    Hosting request fails because request is already pending.
    """
    client.app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.BY_REQUEST
    with login_context(client, 'moo', owned_orgs=['bar']):
        repopath = 'test.bar.foo'

        with client.app.app_context():
            owner = get_graph_reader().load_owner(repopath)
            owner.set_hosting(UserProps.V_HOSTING.PENDING, repopath, version='v2.0.0')
            owner.commit_properties()

        resp = client.post('/ise/requestHosting', data={
            'repopath': repopath, 'vers': 'v2.0.0'
        })
        d = handleAsJson(resp)
        print('\n', json.dumps(d, indent=4))
        assert d["err_lvl"] == PECode.HOSTING_REQUEST_UNNECESSARY
        assert d["err_msg"].find("already been requested") > 0


def test_update_on_merge(app):
    """
    Show that, if we merge a user with a new email address and/or new
    org ownerships, these data are updated.
    """
    with user_context(app, 'test.foo', 'foo@localhost', ['bar']) as u:
        user, is_new = u[0]
        assert is_new is True
        assert user.userpath == 'test.foo'
        assert user.email_addr == 'foo@localhost'
        assert user.owned_orgs == ['bar']

        gw = get_graph_writer()
        user, is_new = gw.merge_user('test.foo', UserProps.V_USERTYPE.USER, 'foo@example.com', [])
        assert is_new is False
        assert user.userpath == 'test.foo'
        assert user.email_addr == 'foo@example.com'
        assert user.owned_orgs == []


def test_ownership_00(app):
    """
    A user who owns no orgs, owns only repos under their username.
    """
    with user_context(app, 'test.foo', 'foo@localhost', []) as u:
        user, _ = u[0]
        assert user.owns_repo('test.foo.bar') is True
        assert user.owns_repo('test.bar.foo') is False


def test_ownership_01(app):
    """
    A user who owns an org, owns repos under their username, as well as under
    that org, but not under any un-owned org.
    """
    with user_context(app, 'test.foo', 'foo@localhost', ['bar']) as u:
        user, _ = u[0]
        assert user.owns_repo('test.foo.bar') is True
        assert user.owns_repo('test.bar.foo') is True
        assert user.owns_repo('test.spam.foo') is False

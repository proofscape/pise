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

import pytest

from tests import handleAsJson, login_context
from config import HostingStance
from pfsc.constants import ISE_PREFIX, WIP_TAG, SYNC_JOB_RESPONSE_KEY
from pfsc.gdb import get_graph_writer
from pfsc.permissions import have_repo_permission, ActionType
from pfsc.session import get_demo_username_from_session
from pfsc.excep import PfscExcep, PECode

source_key = 'source'
err_lvl_key = 'err_lvl'


###############################################################################
# READ tests

@pytest.mark.psm(False)
@pytest.mark.wip(False)
def test_repo_permission_00(app, client, repos_ready):
    """
    READ, not WIP = ok.

    Our various request handler classes that perform READ operations always do
    their own filtering during permission checking, not bothering to check for
    reads at non-WIP versions.

    One could argue that this is not the right design, since, instead of letting
    the policy (that anyone can read any hosted repo @ non-WIP) be encoded in just
    one place (in the low-level `have_repo_permission()` function), it is encoded in
    many places. For now, we call this good enough.

    Therefore for this unit test we can't make an actual request, but have to
    simulate a low-level call.
    """
    with app.app_context():
        with app.test_request_context():
            assert have_repo_permission(ActionType.READ, 'test.moo.bar', 1) is True


@pytest.mark.psm(False)
@pytest.mark.wip(False)
def test_repo_permission_01(app, repos_ready):
    """READ, WIP, demo = ok"""
    with app.app_context():
        with app.test_request_context():
            demo_username = get_demo_username_from_session(supply_if_absent=True)
            repopath = f'demo.{demo_username}.workbook'
            assert have_repo_permission(ActionType.READ, repopath, WIP_TAG) is True


@pytest.mark.psm(True)
@pytest.mark.wip(True)
def test_repo_permission_02(app, client, repos_ready):
    """READ, WIP, allowed, PSM = ok"""
    libpaths = 'test.moo.bar.results'
    versions = 'WIP'
    resp = client.get(f'{ISE_PREFIX}/loadSource?libpaths={libpaths}&versions={versions}')
    d = handleAsJson(resp)
    print(json.dumps(d, indent=4))
    assert source_key in d


@pytest.mark.parametrize('username, ok', [
    # Non owner cannot access
    ['foo', False],
    # User whose name is a prefix -- but _not_ segment-wise -- cannot access
    ['mo', False],
    # Owner can access
    ['moo', True],
    # Admin cannot access
    ['admin', False],
])
@pytest.mark.psm(False)
@pytest.mark.wip(True)
def test_repo_permission_03(app, client, repos_ready, username, ok):
    """READ, WIP, allowed, not PSM, logged in. Result depends on identity. """
    app.config["ADMIN_USERS"] = ['test.admin']
    libpaths = 'test.moo.bar.results'
    versions = 'WIP'
    with login_context(client, username):
        resp = client.get(f'{ISE_PREFIX}/loadSource?libpaths={libpaths}&versions={versions}')
        d = handleAsJson(resp)
        print(json.dumps(d, indent=4))
        if ok:
            assert source_key in d
        else:
            assert source_key not in d


@pytest.mark.psm(False)
@pytest.mark.wip(True)
def test_repo_permission_04(app, client, repos_ready):
    """READ, WIP, allowed, neither PSM nor logged in = rejected"""
    libpaths = 'test.moo.bar.results'
    versions = 'WIP'
    resp = client.get(f'{ISE_PREFIX}/loadSource?libpaths={libpaths}&versions={versions}')
    d = handleAsJson(resp)
    print(json.dumps(d, indent=4))
    assert source_key not in d


@pytest.mark.psm(True)
@pytest.mark.wip(False)
def test_repo_permission_05(app, client, repos_ready):
    """READ, WIP, not allowed = rejected (despite PSM and owner)"""
    libpaths = 'test.moo.bar.results'
    versions = 'WIP'
    with login_context(client, 'moo'):
        resp = client.get(f'{ISE_PREFIX}/loadSource?libpaths={libpaths}&versions={versions}')
        d = handleAsJson(resp)
        print(json.dumps(d, indent=4))
        assert source_key not in d

###############################################################################
# WRITE tests
#
# Here we exploit the behavior of the `NewSubmoduleHandler`, which first
# checks for write permission, and later raises a PfscExcep if the desired
# name proves to be unavailable. By requesting an unavailable name, this lets
# us check write permissions without actually doing anything.


@pytest.mark.psm(False)
@pytest.mark.wip(False)
def test_repo_permission_10(app, repos_ready):
    """
    WRITE, not WIP = rejected.
    This is a weird case which should never arise in practice, but we check it
    here just for good test coverage.
    """
    with app.app_context():
        with app.test_request_context():
            assert have_repo_permission(ActionType.WRITE, 'test.moo.bar', 1) is False


@pytest.mark.psm(False)
@pytest.mark.wip(False)
def test_repo_permission_11(app, repos_ready):
    """WRITE, WIP, demo = ok"""
    with app.app_context():
        with app.test_request_context():
            demo_username = get_demo_username_from_session(supply_if_absent=True)
            repopath = f'demo.{demo_username}.workbook'
            assert have_repo_permission(ActionType.WRITE, repopath, WIP_TAG) is True


@pytest.mark.psm(True)
@pytest.mark.wip(True)
def test_repo_permission_12(client, repos_ready):
    """WRITE, WIP, allowed, PSM = ok"""
    parentpath = 'test.moo.bar'
    name = 'results'
    resp = client.put(f'{ISE_PREFIX}/makeNewSubmodule', data={
        'parentpath': parentpath,
        'name': name,
    })
    d = handleAsJson(resp)
    print(json.dumps(d, indent=4))
    assert d[err_lvl_key] == 0
    assert d[SYNC_JOB_RESPONSE_KEY][err_lvl_key] == PECode.LIBSEG_UNAVAILABLE


@pytest.mark.parametrize('username, ok', [
    # Non owner cannot access
    ['foo', False],
    # User whose name is a prefix -- but _not_ segment-wise -- cannot access
    ['mo', False],
    # Owner can access
    ['moo', True],
    # Admin cannot access
    ['admin', False],
])
@pytest.mark.psm(False)
@pytest.mark.wip(True)
def test_repo_permission_13(app, client, repos_ready, username, ok):
    """WRITE, WIP, allowed, not PSM, logged in. Result depends on identity. """
    app.config["ADMIN_USERS"] = ['test.admin']
    parentpath = 'test.moo.bar'
    name = 'results'
    with login_context(client, username):
        resp = client.put(f'{ISE_PREFIX}/makeNewSubmodule', data={
            'parentpath': parentpath,
            'name': name,
        })
        d = handleAsJson(resp)
        print(json.dumps(d, indent=4))
        if ok:
            assert d[err_lvl_key] == 0
            assert d[SYNC_JOB_RESPONSE_KEY][err_lvl_key] == PECode.LIBSEG_UNAVAILABLE
        else:
            assert d[err_lvl_key] == PECode.INADEQUATE_PERMISSIONS


@pytest.mark.psm(False)
@pytest.mark.wip(True)
def test_repo_permission_14(app, client, repos_ready):
    """WRITE, WIP, allowed, neither PSM nor logged in = rejected"""
    parentpath = 'test.moo.bar'
    name = 'results'
    resp = client.put(f'{ISE_PREFIX}/makeNewSubmodule', data={
        'parentpath': parentpath,
        'name': name,
    })
    d = handleAsJson(resp)
    print(json.dumps(d, indent=4))
    assert d[err_lvl_key] == PECode.INADEQUATE_PERMISSIONS


@pytest.mark.psm(True)
@pytest.mark.wip(False)
def test_repo_permission_15(app, client, repos_ready):
    """WRITE, WIP, not allowed = rejected (despite PSM and owner)"""
    parentpath = 'test.moo.bar'
    name = 'results'
    with login_context(client, 'moo'):
        resp = client.put(f'{ISE_PREFIX}/makeNewSubmodule', data={
            'parentpath': parentpath,
            'name': name,
        })
        d = handleAsJson(resp)
        print(json.dumps(d, indent=4))
        assert d[err_lvl_key] == PECode.INADEQUATE_PERMISSIONS

###############################################################################
# BUILD tests


@pytest.mark.psm(False)
@pytest.mark.wip(False)
def test_repo_permission_200(app, repos_ready):
    """BUILD, demo, WIP = ok"""
    with app.app_context():
        with app.test_request_context():
            demo_username = get_demo_username_from_session(supply_if_absent=True)
            repopath = f'demo.{demo_username}.workbook'
            assert have_repo_permission(ActionType.BUILD, repopath, WIP_TAG) is True


@pytest.mark.psm(False)
@pytest.mark.wip(False)
def test_repo_permission_201(app, repos_ready):
    """BUILD, non-demo, WIP, not allowed = reject"""
    with app.app_context():
        with app.test_request_context():
            repopath = 'test.moo.bar'
            assert have_repo_permission(ActionType.BUILD, repopath, WIP_TAG) is False


@pytest.mark.psm(False)
@pytest.mark.wip(True)
def test_repo_permission_202(app, repos_ready):
    """BUILD, non-demo, WIP, allowed, not PSM, not owner = reject"""
    with app.app_context():
        with app.test_request_context():
            repopath = 'test.moo.bar'
            assert have_repo_permission(ActionType.BUILD, repopath, WIP_TAG) is False


@pytest.mark.psm(True)
@pytest.mark.wip(True)
def test_repo_permission_203(app, repos_ready):
    """BUILD, non-demo, WIP, allowed, PSM = ok"""
    with app.app_context():
        with app.test_request_context():
            repopath = 'test.moo.bar'
            assert have_repo_permission(ActionType.BUILD, repopath, WIP_TAG) is True


@pytest.mark.psm(False)
@pytest.mark.wip(True)
def test_repo_permission_204(client, repos_ready):
    """BUILD, non-demo, WIP, allowed, not PSM, owner = ok"""
    with login_context(client, 'moo'):
        with client.test_request_context():
            repopath = 'test.moo.bar'
            assert have_repo_permission(ActionType.BUILD, repopath, WIP_TAG) is True


@pytest.mark.psm(True)
def test_repo_permission_205(app, repos_ready):
    """BUILD, non-demo, non-WIP, PSM = ok"""
    with app.app_context():
        with app.test_request_context():
            assert have_repo_permission(ActionType.BUILD, 'test.moo.bar', 'v2.0.0') is True


@pytest.mark.psm(False)
def test_repo_permission_206(app, client, repos_ready):
    """BUILD, non-demo, non-WIP, not PSM, admin with permission = ok"""
    app.config["ADMIN_USERS"] = ['test.admin']
    app.config["ADMINS_CAN_BUILD_RELEASES"] = True
    with login_context(client, 'admin'):
        with client.test_request_context():
            assert have_repo_permission(ActionType.BUILD, 'test.moo.bar', 'v2.0.0') is True


@pytest.mark.psm(False)
def test_repo_permission_207(app, client, repos_ready):
    """BUILD, non-demo, non-WIP, not PSM, owner, hosting not granted = rejected"""
    app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.UNAVAILABLE
    with login_context(client, 'moo'):
        with client.test_request_context():
            assert have_repo_permission(ActionType.BUILD, 'test.moo.bar', 'v2.0.0') is False


@pytest.mark.psm(False)
def test_repo_permission_208(app, client, repos_ready):
    """BUILD, non-demo, non-WIP, not PSM, owner, hosting is granted = ok"""
    app.config["DEFAULT_HOSTING_STANCE"] = HostingStance.FREE
    with login_context(client, 'moo'):
        with client.test_request_context():
            assert have_repo_permission(ActionType.BUILD, 'test.moo.bar', 'v2.0.0') is True


@pytest.mark.psm(False)
def test_repo_permission_209(client, repos_ready):
    """BUILD, non-demo, non-WIP, not PSM, not owner = rejected"""
    with login_context(client, 'foo'):
        with client.test_request_context():
            assert have_repo_permission(ActionType.BUILD, 'test.moo.bar', 'v2.0.0') is False


###############################################################################

from pfsc.build import build_module, build_release

@pytest.mark.psm
def test_load_module_at_wip_fail(app, repos_ready):
    """
    test.moo.err3 imports from test.moo.bar@WIP.
    If we try to build it as a release, it should therefore fail.
    """
    with app.app_context():
        with pytest.raises(PfscExcep) as ei:
            build_release('test.moo.err3', 'v1.0.0')
        print(ei.value)
        assert ei.value.code() == PECode.NO_WIP_IMPORTS_IN_NUMBERED_RELEASES

@pytest.mark.psm
def test_load_module_at_wip_succeed(app, repos_ready):
    """
    test.moo.err3 imports from test.moo.bar@WIP.
    Importing at WIP is allowed if your own repo is being built at WIP too.
    So there should be no error here.
    """
    with app.app_context():
        build_module('test.moo.err3', recursive=True)
        # Clean up
        get_graph_writer().delete_everything_under_repo('test.moo.err3')

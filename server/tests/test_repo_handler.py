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

import os
import json

import pytest
from flask_login import current_user

from tests import handleAsJson, login_context, logout
from pfsc import get_build_dir
from pfsc.build.repo import get_repo_info
from pfsc.gdb import get_graph_writer, building_in_gdb
from pfsc.gdb.user import HostingStatus
from pfsc.constants import ISE_PREFIX, UserProps, SYNC_JOB_RESPONSE_KEY
from pfsc.excep import PECode


model_key = "model"
priv_key = "privileged"
hosting_key = "hosting"
built_key = "built"
present_key = "present"
err_lvl_key = "err_lvl"
version_key = "version"


def test_repo_loader_01(client, repos_ready):
    """
    Not logged in, request a numbered release that has already been built.
    Should get the repo model.
    """
    repopath = 'test.moo.bar'
    version = 'v2.0.0'
    resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}')
    d = handleAsJson(resp)
    print()
    print(json.dumps(d, indent=4))
    assert model_key in d
    model = d[model_key]
    assert len(model) == 4
    assert len([item for item in model if item["type"] == "MODULE"]) == 2
    assert len([item for item in model if item["type"] == "CHART"]) == 2


def test_repo_loader_02(client, repos_ready):
    """
    Not logged in, request a numbered release that has not been built.
    Response shows we lack privilege on that repo.
    """
    repopath = 'test.moo.bar'
    version = 'v8.8.8'
    resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}')
    d = handleAsJson(resp)
    print()
    print(json.dumps(d, indent=4))
    assert model_key not in d
    assert d[priv_key] == False


def test_repo_loader_03(app, client, repos_ready):
    """
    Log in as owner, and request a numbered release that has already been built.
    """
    repopath = 'test.moo.bar'
    version = 'v2.0.0'
    with login_context(client, 'moo'):
        resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}')
        d = handleAsJson(resp)
        print()
        print(json.dumps(d, indent=4))
        assert model_key in d


def test_repo_loader_04(client, repos_ready):
    """
    Log in as owner, and request a numbered release that has not been built,
    but do not request that it be built.
    """
    repopath = 'test.moo.bar'
    version = 'v8.8.8'
    with login_context(client, 'moo'):
        resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}')
        d = handleAsJson(resp)
        print()
        print(json.dumps(d, indent=4))
        assert model_key not in d
        assert d[hosting_key] == "MAY_REQUEST"
        assert d[present_key]
        assert not d[built_key]


def test_repo_loader_10(client, repos_ready):
    """
    App in "default latest" mode.
    Not logged in, request a repo for which some numbered release has already
    been built, and omit version in request.
    Should get the repo model at latest release.
    """
    client.app.config["DEFAULT_REPO_VERSION_IS_LATEST_RELEASE"] = True
    repopath = 'test.moo.bar'
    resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}')
    d = handleAsJson(resp)
    print()
    print(json.dumps(d, indent=4))
    assert d[version_key] == "v2.1.0"
    assert model_key in d
    model = d[model_key]
    assert len(model) == 4
    assert len([item for item in model if item["type"] == "MODULE"]) == 2
    assert len([item for item in model if item["type"] == "CHART"]) == 2


def test_repo_loader_11(client, repos_ready):
    """
    App NOT in "default latest" mode.
    Not logged in, request a repo, omitting version in request.
    Should be denied.
    """
    client.app.config["DEFAULT_REPO_VERSION_IS_LATEST_RELEASE"] = False
    repopath = 'test.moo.bar'
    resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}')
    d = handleAsJson(resp)
    print()
    print(json.dumps(d, indent=4))
    assert d[version_key] == "WIP"
    assert model_key not in d
    assert not d[priv_key]


@pytest.mark.wip
def test_repo_loader_21(client, repos_ready):
    """
    Not logged in, request WIP version.
    """
    repopath = 'test.moo.comment'
    version = 'WIP'
    logout(client)
    resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}')
    d = handleAsJson(resp)
    print()
    print(json.dumps(d, indent=4))
    assert model_key not in d
    assert not d[priv_key]


@pytest.mark.wip
def test_repo_loader_23(app, client, repos_ready):
    """
    Log in as owner, request WIP version, which has already been built.
    """
    repopath = 'test.moo.comment'
    version = 'WIP'
    with login_context(client, 'moo'):
        resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}')
        d = handleAsJson(resp)
        print()
        print(json.dumps(d, indent=4))
        assert model_key in d


def test_repo_loader_24(app, client, repos_ready):
    """
    Log in as owner, request WIP version, which has not been built, but do not
    request to build it.
    """
    repopath = 'test.moo.bar'
    version = 'WIP'
    with login_context(client, 'moo'):
        resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}')
        d = handleAsJson(resp)
        print()
        print(json.dumps(d, indent=4))
        assert model_key not in d
        assert d[priv_key]
        assert d[present_key]
        assert not d[built_key]


@pytest.mark.wip
def test_repo_loader_44(app, client, repos_ready):
    """
    Log in as owner, and request a WIP version that has not been built,
    and do request that it be built.

    NOTE: This unit tests replaces the existing `Version` node in the GDB for
    repo 'test.moo.comment' @ WIP with a new node. (For future reference, in
    case examining the GDB manually, and wondering why sth changed after
    running unit tests.)
    """
    with app.app_context():
        repopath = 'test.moo.comment'
        version = 'WIP'
        base_tag = 'v0.1.0'
        tag_for_wip = 'v0.2.0'

        ri = get_repo_info(repopath)

        # First delete the existing build:

        if building_in_gdb():
            get_graph_writer().delete_full_wip_build(repopath)
        else:
            build_dir = ri.get_build_dir(version=version)

            # Sanity check:
            build_root = get_build_dir()
            test_build = build_root / 'test'
            # That this does not raise `ValueError`, is our sanity check.
            # From Python 3.9 onward, we could call `is_relative_to()`, but
            # we're still on 3.8.
            build_dir.relative_to(test_build)

            cmd = f'rm -rf {build_dir}'
            os.system(cmd)

        # Now rebuild:

        # Checkout right version
        ri.checkout(tag_for_wip)

        with login_context(client, 'moo'):
            resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}&doBuild=true')
            d = handleAsJson(resp)
            print()
            print(json.dumps(d, indent=4))

        # Checkout base version
        ri.checkout(base_tag)


def test_repo_loader_101(app, client, repos_ready):
    """
    Not logged in, request a numbered release that has not been built.
    """
    repopath = 'test.moo.bar'
    version = 'v8.8.8'
    resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}')
    d = handleAsJson(resp)
    print()
    print(json.dumps(d, indent=4))
    assert hosting_key not in d


def test_repo_loader_102(client, repos_ready):
    """
    Log in as non-owner, and request a numbered release that has not been built.
    """
    repopath = 'test.moo.bar'
    version = 'v8.8.8'
    with login_context(client, 'foo'):
        resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}')
        d = handleAsJson(resp)
        print()
        print(json.dumps(d, indent=4))
        assert d[hosting_key] == HostingStatus.DOES_NOT_OWN


def test_repo_loader_300(client):
    """
    Log in as owner, request a numbered release that has not been built, and do
    request that it be built.
    Hosting permission has been granted for this version, but an incorrect
    commit hash has been recorded. The system should refuse to build.
    """
    repopath = 'test.moo.err'
    version = 'v1.0.0'
    with login_context(client, 'moo'):
        ri = get_repo_info(repopath)
        actual_hash = ri.get_hash_of_ref(version)
        wrong_char = '1' if actual_hash[0] == '0' else '0'
        wrong_hash = wrong_char + actual_hash[1:7]

        with client.test_request_context():
            current_user.set_hosting(
                UserProps.V_HOSTING.GRANTED, repopath, version=version,
                hash=wrong_hash
            )
            current_user.commit_properties()

        resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}&doBuild=true')
        d = handleAsJson(resp)
        print()
        print(json.dumps(d, indent=4))
        assert d[SYNC_JOB_RESPONSE_KEY][err_lvl_key] == PECode.BAD_HASH


def test_repo_loader_301(client):
    """
    Log in as owner, request a numbered release that has not been built, and do
    request that it be built.
    Hosting permission has been granted for this version, and this time the
    correct commit hash has been recorded. The system should attempt to build.
    However, we have deliberately chosen a repo version with an error, so that
    the build doesn't succeed.
    """
    repopath = 'test.moo.err'
    version = 'v1.0.0'
    with login_context(client, 'moo'):
        ri = get_repo_info(repopath)
        actual_hash = ri.get_hash_of_ref(version)

        with client.test_request_context():
            current_user.set_hosting(
                UserProps.V_HOSTING.GRANTED, repopath, version=version,
                hash=actual_hash
            )
            current_user.commit_properties()

        resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}&doBuild=true')
        d = handleAsJson(resp)
        print()
        print(json.dumps(d, indent=4))
        assert d[SYNC_JOB_RESPONSE_KEY][err_lvl_key] == PECode.MISSING_REPO_CHANGE_LOG

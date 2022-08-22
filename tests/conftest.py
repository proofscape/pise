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

import os
import re

import pytest
from werkzeug.test import Client as WzClient

from pfsc.constants import WEBSOCKET_NAMESPACE, WIP_TAG, ISE_PREFIX
from pfsc import make_app, socketio
from pfsc.build.lib.addresses import ForestAddress
from pfsc.gdb import get_graph_reader
from config import ConfigName
from tests.util import get_basic_repos, get_tags_to_build_as_wip
from tests import loginAsTestUser

testing_config = ConfigName.LOCALDEV

os.environ["FLASK_CONFIG"] = testing_config


def make_test_app():
    return make_app(testing_config)


@pytest.fixture
def app(request):
    """
    Optional marks:

        @pytest.mark.psm(True/False)
            Argless: @pytest.mark.psm == @pytest.mark.psm(True)
            Effect: set app.config["PERSONAL_SERVER_MODE"]

        @pytest.mark.wip(True/False)
            Argless: @pytest.mark.wip == @pytest.mark.wip(True)
            Effect: set app.config["ALLOW_WIP"]

        @pytest.mark.req_csrf(True/False)
            Argless: @pytest.mark.req_csrf == @pytest.mark.req_csrf(True)
            Effect: set app.config["REQUIRE_CSRF_TOKEN"]
    """
    app = make_test_app()

    psm = request.node.get_closest_marker("psm")
    if psm:
        val = psm.args[0] if psm.args else True
        app.config["PERSONAL_SERVER_MODE"] = val

    wip = request.node.get_closest_marker("wip")
    if wip:
        val = wip.args[0] if wip.args else True
        app.config["ALLOW_WIP"] = val

    csrf = request.node.get_closest_marker("req_csrf")
    if csrf:
        val = csrf.args[0] if csrf.args else True
        app.config["REQUIRE_CSRF_TOKEN"] = val

    return app


@pytest.fixture
def repos_ready(app):
    """
    This fixture just checks that the "error-free repos" are built and indexed.
    If not, it's an error, and assertion will fail.

    :return: True
    """
    repos = get_basic_repos()
    built_at_wip = [p[0] for p in get_tags_to_build_as_wip()]
    with app.app_context():
        gr = get_graph_reader()
        for repo in repos:
            versions = gr.get_versions_indexed(repo.libpath)
            tags = set(info['version'] for info in versions)
            if not set(repo.tag_names).issubset(tags):
                print(repo.libpath)
                assert 0
        for repopath in built_at_wip:
            versions = gr.get_versions_indexed(repopath, include_wip=True)
            if not versions[-1]['version'] == WIP_TAG:
                print(repopath)
                assert 0
    return True


class ClientWrapper(WzClient):
    """
    Wrapper for the basic Werkzeug test client.
    Ensures we (a) obtain a CSRF token, and (b) supply it with every
    subsequent request.

    Also provides a test request context that includes any cookies currently
    held by the client. This means that if you have previously used the client
    to do a login, you'll get a request context in which the Flask Login
    `current_user` represents the logged in user.
    """

    def __init__(self, app):
        self.client = app.test_client()
        # Need to initialize our csrf_token to None so we can get through
        # the request whereby we obtain a token.
        self.csrf_token = None
        self.csrf_token = self.obtain_csrf_token()

    def obtain_csrf_token(self):
        response = self.get('/')
        html = response.data.decode()
        m = re.search('"CSRF": "([^"]+)"', html)
        return m.group(1)

    @property
    def app(self):
        return self.client.application

    def test_request_context(self):
        """
        Return a request context that includes any cookies currently
        held by the client.
        """
        headers = {}
        cj = self.client.cookie_jar
        if cj is not None:
            environ = {}
            cj.inject_wsgi(environ)
            cookie = environ.get("HTTP_COOKIE")
            if cookie:
                headers["COOKIE"] = cookie
        ctx = self.app.test_request_context(headers=headers)
        return ctx

    def open(self, path, query=None, method="GET", data=None):
        """
        :param path: at least the requested path; _may_ include query args
        :param query: optional dict of query args
        :param method: duh
        :param data: optional dict of form args
        :return: same as `open()` method in Flask test client
          (which appears to be a `flask.wrappers.Response`).
        """
        # If query args given within path, put into dict form.
        if path.find("?") >= 0:
            path, qs = path.split("?")
            qd = {k:v for k, v in [kv.split('=') for kv in qs.split("&")]}
            # If query was given, it overrides anything in the path.
            if query is not None:
                qd.update(query)
            query = qd
        if self.csrf_token:
            # Add CSRF token.
            if query is not None:
                query["CSRF"] = self.csrf_token
            elif data is not None:
                data["CSRF"] = self.csrf_token
            else:
                query = {"CSRF": self.csrf_token}
        return self.client.open(path, query_string=query, method=method, data=data)


@pytest.fixture
def client(app, request):
    """
    Unit tests employing this fixture may use

        @pytest.mark.asTestUser(username)

    in order to say that the client should log in as the named test user.
    This means the user whose full Proofscape username is `test.username`.
    """
    cl = ClientWrapper(app)
    marker = request.node.get_closest_marker("asTestUser")
    if marker:
        username = marker.args[0]
        app.config["ALLOW_TEST_REPO_LOGINS"] = True
        loginAsTestUser(cl, username)
    return cl


@pytest.fixture
def sio_client(client):
    return socketio.test_client(
        client.app,
        namespace=WEBSOCKET_NAMESPACE,
        flask_test_client=client.client
    )


def make_forest_addresses(app):
    r"""
    When we put the alex, brook, and casey test repos in versions 3, 2, and 2, resp., then
    we get a nice forest of deducs, all with distinct "names" (i.e. final libseg), looking like this:

        Thm1 <-- Pf <-- X1 <-- W1
                  \        \_ W2
                   \
                    \__ X2 <-- W3
                           \_ W4
                           \_ W5

        Thm2 <-- Pf13
             \__Pf2 <-- X3 <-- W6
                           \_ W7

    """
    # FIXME: do we need an app context here?
    with app.app_context():
        fa = {
            "Thm1": ForestAddress('test.alex.math.thm1.Thm1', 3),
            "Pf": ForestAddress('test.alex.math.thm1.Pf', 3),
            "Thm2": ForestAddress('test.alex.math.thm2.Thm2', 3),
            "Pf13": ForestAddress('test.alex.math.thm2.Pf13', 3),
            "Pf2": ForestAddress('test.alex.math.thm2.Pf2', 3),
            "X1": ForestAddress('test.brook.math.exp1.X1', 2),
            "X2": ForestAddress('test.brook.math.exp1.X2', 2),
            "X3": ForestAddress('test.brook.math.exp1.X3', 2),
            "W1": ForestAddress('test.casey.math.expand.W1', 2),
            "W2": ForestAddress('test.casey.math.expand.W2', 2),
            "W3": ForestAddress('test.casey.math.expand2.W3', 2),
            "W4": ForestAddress('test.casey.math.expand2.W4', 2),
            "W5": ForestAddress('test.casey.math.expand2.W5', 2),
            "W6": ForestAddress('test.casey.math.expand2.W6', 2),
            "W7": ForestAddress('test.casey.math.expand2.W7', 2),
        }
        return fa


@pytest.fixture
def forest_addresses(app, repos_ready):
    return make_forest_addresses(app)

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

import json
from contextlib import contextmanager
import cProfile
import pstats, io

from pfsc.constants import UserProps


def profile_call(func, args, kwargs, print_top=50):
    with cProfile.Profile() as pr:
        ret_val = func(*args, **kwargs)
    s = io.StringIO()
    sortby = pstats.SortKey.CUMULATIVE
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(print_top)
    print(s.getvalue())
    return ret_val


def handleAsJson(response):
    return json.loads(response.data.decode())


def loginAsTestUser(client, username, owned_orgs=None):
    owned_orgs = owned_orgs or []
    d = {
        'username': username,
        'password': username
    }
    if owned_orgs:
        d['orgs'] = ','.join(owned_orgs)
    return client.post('/auth/testRepoLogin', data=d)


def logout(client):
    return client.get('/auth/logout')


@contextmanager
def login_context(client, username, owned_orgs=None):
    """
    Open a context manager within which we have logged in as test user
    f'test.{username}'.
    """
    owned_orgs = owned_orgs or []
    from pfsc.gdb import get_graph_writer
    yield loginAsTestUser(client, username, owned_orgs)
    with client.client.application.app_context():
        for name in [username] + owned_orgs:
            get_graph_writer().delete_user(f'test.{name}',
                                           definitely_want_to_delete_this_user=True)

@contextmanager
def user_context(app, username, email, owned_orgs, usertype=UserProps.V_USERTYPE.USER):
    """
    Make a context in which a user exists in the GDB.

    Unlike `login_context()`, here we do not use the '/auth/testRepoLogin'
    endpoint, but instead use `GraphWriter.merge_user()` directly.
    This means we can set any combination of username, email, and owned_orgs
    we want.

    We also merge org User nodes for any owned orgs, and delete these upon
    exit.

    :yields: list [(user, is_new), (org1, is_new1), ... (orgN, is_newN)]
    """
    from pfsc.gdb import get_graph_writer
    with app.app_context():
        gw = get_graph_writer()
        host, user = username.split('.')
        orgpaths = [f'{host}.{org}' for org in owned_orgs]

        results = [gw.merge_user(username, usertype, email, owned_orgs)]
        for orgpath in orgpaths:
            results.append(gw.merge_user(orgpath, UserProps.V_USERTYPE.ORG, None, []))

        yield results

        gw.delete_user(username, definitely_want_to_delete_this_user=True)
        for orgpath in orgpaths:
            gw.delete_user(orgpath, definitely_want_to_delete_this_user=True)


def parse_served_state_from_app_load_response(resp):
    """
    :param resp: the response from a call (via test client) to
      the app loader endpoint
    :return: dictionary representing the served ISE state
    """
    html = resp.data.decode()
    lines = html.split('\n')
    json_lines = []
    mode = 0
    for line in lines:
        if mode == 0:
            if line == '  pfsc_ISE_state = {':
                json_lines.append('{')
                mode = 1
        elif mode == 1:
            if line == '};':
                json_lines.append('}')
                break
            else:
                json_lines.append(line)
    j = '\n'.join(json_lines)
    d = json.loads(j)
    return d

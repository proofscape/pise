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

import json

import pytest

#import eventlet
#eventlet.monkey_patch()

from tests import handleAsJson, login_context
from pfsc.constants import WEBSOCKET_NAMESPACE, ISE_PREFIX, UserProps
from pfsc.gdb import get_graph_writer, get_graph_reader
from pfsc.excep import PECode

"""
For now, skipping all tests involving sockets.
Have not yet figured out how to get the socketio test client working.
"""

###############################################################################
# UPDATE: Currently, the sio_client does say it's connected, but we still can't
# get any tests to work in which we want the sio_client to receive emitted
# messages.
# UPDATE (230829): After package upgrades from today's rebase of sphinx topic
# onto main (resulting in regenerating requirements.txt from scratch), this test
# works when run in isolation, but not when running our entire suite of unit
# tests. It is somehow history-dependent.
@pytest.mark.skip(reason="sio_client still not working for us...")
def test_connect(sio_client):
    assert sio_client.is_connected(namespace=WEBSOCKET_NAMESPACE)


@pytest.mark.skip(reason="sio_client still not working for us...")
def test_subscribe(sio_client):
    resource = 'test.hist.lit.H.ilbert.ZB.Thm168.notes.Notes'
    sio_client.emit('subscribe', {
        'resource': resource,
        'product': "HTML",
        'sid': 3
    }, namespace=WEBSOCKET_NAMESPACE)
    received = sio_client.get_received(WEBSOCKET_NAMESPACE)
    print(received)
###############################################################################


def test_load_dashgraph(app, client, repos_ready):
    with app.app_context():
        print()
        app.config["ALLOW_TEST_REPO_LOGINS"] = True
        app.config["OFFER_SERVER_SIDE_NOTE_RECORDING"] = True
        libpath = 'test.moo.bar.results.Pf'
        vers = 'v2.0.0'

        with login_context(client, 'moo'):
            resp = client.post(f'/ise/requestSsnr', data={'activate': 1, 'confirm': 1})
            d = handleAsJson(resp)
            print(json.dumps(d, indent=4))
            resp = client.post(f'{ISE_PREFIX}/recordNotes', data={
                'goal_id': f'{libpath}.R@0', 'state': 'checked', 'notes': 'foo',
            })
            d = handleAsJson(resp)
            print(json.dumps(d, indent=4))

            resp = client.get(f'{ISE_PREFIX}/loadDashgraph?libpath={libpath}&vers={vers}')
            d = handleAsJson(resp)
            print(json.dumps(d, indent=4))

            di = d["dashgraph"]["deducInfo"]
            assert di["version"] == vers

            e = d["dashgraph"]["children"]["test.moo.bar.results.Pf.U"]["enrichment"]
            deducs = e["Deduc"]
            annos = e["Anno"]
            assert len(deducs) == 3 and "test.moo.comment.bar.xpan_T" in [deducs[i]["libpath"] for i in range(2)]
            assert len(annos) == 2 and annos[0]["libpath"] == "test.moo.comment.bar.NotesT"

            u = d["dashgraph"]["children"]["test.moo.bar.results.Pf.R"]["user_notes"]
            assert u == {
                "notes": "foo",
                "state": "checked"
            }


def test_load_enrichment(app, client, repos_ready):
    with app.app_context():
        libpath = 'test.moo.bar.results.Pf'
        major = 2
        resp = client.get(f'{ISE_PREFIX}/getEnrichment?libpath={libpath}&vers={major}')
        d = handleAsJson(resp)
        # Check that full version is also accepted:
        full = 'v2.0.0'
        resp2 = client.get(f'{ISE_PREFIX}/getEnrichment?libpath={libpath}&vers={full}')
        d2 = handleAsJson(resp2)
        del d['orig_req']
        del d2['orig_req']
        assert d2 == d
        print(json.dumps(d, indent=4))
        e = d["enrichment"]["test.moo.bar.results.Pf.U"]
        d = e["Deduc"]
        a = e["Anno"]
        assert len(d) == 2 and "test.moo.comment.bar.xpan_T" in [d[i]["libpath"] for i in range(2)]
        assert len(a) == 1 and a[0]["libpath"] == "test.moo.comment.bar.NotesT"


def test_load_annotation(app, client, repos_ready):
    """Test loading of user notes & trust along with an annotation. """
    with app.app_context():
        app.config["ALLOW_TEST_REPO_LOGINS"] = True
        app.config["OFFER_SERVER_SIDE_NOTE_RECORDING"] = True
        app.config["RECORD_PER_USER_TRUST_SETTINGS"] = True
        repopath = 'test.wid.get'
        libpath = f'{repopath}.notes.Notes'
        vers = 'v0.2.0'

        def get_anno_data(dump=False):
            response = client.post(f'{ISE_PREFIX}/loadAnnotation?libpath={libpath}&vers={vers}')
            d = handleAsJson(response)
            # print(json.dumps(d, indent=4))
            data_str = d['data_json']
            data = json.loads(data_str)
            if dump:
                print(json.dumps(data, indent=4))
            return data

        def check_trust():
            res = client.get(f'/ise/checkUserTrust?repopath={repopath}&vers={vers}')
            d = handleAsJson(res)
            return d['user_trust_setting']

        with login_context(client, 'moo'):
            client.post(f'/ise/requestSsnr', data={'activate': 1, 'confirm': 1})
            client.post(f'{ISE_PREFIX}/recordNotes', data={
                'goal_id': f'{libpath}.w2@0', 'state': 'checked', 'notes': 'bar',
            })

            data = get_anno_data()

            # Test that a widget gets the correct auto-generated pane_group field:
            pg = "test.wid.get@v0_2_0.notes.Notes:CHART:"
            assert data['widgets']['test-wid-get-notes-Notes-w1_v0-2-0']['pane_group'] == pg

            # Test that notes were recorded and loaded:
            u = data['widgets']['test-wid-get-notes-Notes-w2_v0-2-0']['user_notes']
            assert u == {
                "state": "checked",
                "notes": "bar"
            }

            # Initially, repo is not trusted:
            w1_uid = 'test-wid-get-notes-Notes-w1_v0-2-0'
            assert data['widgets'][w1_uid]['trusted'] is False

            # User sets trust:
            client.get(f'/ise/setUserTrust?repopath={repopath}&vers={vers}&trust=true')
            data = get_anno_data()
            assert data['widgets'][w1_uid]['trusted'] is True
            assert check_trust() is True

            # User revokes trust:
            client.get(f'/ise/setUserTrust?repopath={repopath}&vers={vers}&trust=false')
            data = get_anno_data()
            assert data['widgets'][w1_uid]['trusted'] is False
            assert check_trust() is None

            # User sets trust, but at a different version:
            other_vers = 'v0.3.0'
            client.get(f'/ise/setUserTrust?repopath={repopath}&vers={other_vers}&trust=true')
            data = get_anno_data()
            assert data['widgets'][w1_uid]['trusted'] is False
            assert check_trust() is None


def test_load_annotation_02(app, client, repos_ready):
    """Test loading of trust and approvals along with an annotation. """
    with app.app_context():
        annopath = 'test.comment.notes.H.ilbert.ZB.Thm17.Notes'
        version = 'v0.1.0'
        widgetpath1 = annopath + '.eg1_disp1'
        widgetpath2 = annopath + '.eg1_disp2'

        uid1 = f'{widgetpath1}_{version}'.replace('.', '-')
        uid2 = f'{widgetpath2}_{version}'.replace('.', '-')

        def get_widget_data():
            response = client.post(f'{ISE_PREFIX}/loadAnnotation?libpath={annopath}&vers={version}')
            d = handleAsJson(response)
            data_str = d['data_json']
            data = json.loads(data_str)
            #print(json.dumps(data, indent=4))
            wd = data['widgets']
            w1 = wd[uid1]
            w2 = wd[uid2]
            return w1, w2

        gw = get_graph_writer()

        tpm = app.config["trusted_prefix_mapping"]

        tpm.clear()
        for wp in [widgetpath1, widgetpath2]:
            gw.set_approval(wp, version, False)

        w1, w2 = get_widget_data()
        assert w1['trusted'] is False
        assert w1.get('approved') is None
        assert w2['trusted'] is False
        assert w2.get('approved') is None

        gw.set_approval(widgetpath1, version, True)

        w1, w2 = get_widget_data()
        assert w1['trusted'] is False
        assert w1.get('approved') is True
        assert w2['trusted'] is False
        assert w2.get('approved') is None

        gw.set_approval(widgetpath1, version, False)
        w1, w2 = get_widget_data()
        assert w1.get('approved') is None

        tpm.add_heading(annopath, True)

        w1, w2 = get_widget_data()
        assert w1['trusted'] is True
        assert w1.get('approved') is None
        assert w2['trusted'] is True
        assert w2.get('approved') is None


def test_user_trust_setting_rejected(app, client, repos_ready):
    """
    Check that requests to user trust setting endpoint are rejected
    when not configured to be accepted.
    """
    with app.app_context():
        app.config["ALLOW_TEST_REPO_LOGINS"] = True
        # NOTE: We are deliberately *not* making any setting on the
        # 'RECORD_PER_USER_TRUST_SETTINGS' config var. We want to test that
        # the default mode is to reject.
        repopath = 'test.wid.get'
        vers = 'v0.2.0'

        with login_context(client, 'moo'):
            response = client.get(f'/ise/setUserTrust?repopath={repopath}&vers={vers}&trust=true')
            d = handleAsJson(response)
            print(json.dumps(d, indent=4))
            assert d['err_lvl'] == PECode.SERVICE_DISABLED


def test_user_trust_check_rejected(app, client, repos_ready):
    """
    Check that requests to user trust checker endpoint are rejected
    when not configured to be accepted.
    """
    with app.app_context():
        app.config["ALLOW_TEST_REPO_LOGINS"] = True
        # NOTE: We are deliberately *not* making any setting on the
        # 'RECORD_PER_USER_TRUST_SETTINGS' config var. We want to test that
        # the default mode is to reject.
        repopath = 'test.wid.get'
        vers = 'v0.2.0'

        with login_context(client, 'moo'):
            response = client.get(f'/ise/checkUserTrust?repopath={repopath}&vers={vers}')
            d = handleAsJson(response)
            print(json.dumps(d, indent=4))
            assert d['err_lvl'] == PECode.SERVICE_DISABLED


def test_load_source(app, client, repos_ready):
    with app.app_context():
        libpaths = [
            'test.wid.get.notes.Notes',
            'test.wid.get.notes2',
        ]
        vers = 'v0.1.0'
        versions = [vers] * 2
        r = client.get(f'{ISE_PREFIX}/loadSource?libpaths={",".join(libpaths)}&versions={",".join(versions)}')
        d = handleAsJson(r)
        print()
        print(json.dumps(d, indent=4))
        #return
        source = d["source"]
        text1 = source['test.wid.get.notes']
        text2 = source['test.wid.get.notes2']
        #print(len(text1))
        #print(len(text2))
        assert len(text1) == 1000
        assert len(text2) == 118

def test_lookup_goals(app, client, repos_ready):
    with app.app_context():
        libpath = 'test.moo.bar.results.Pf'
        vers = 'v2.0.0'
        response = client.get(f'{ISE_PREFIX}/lookupGoals?libpath={libpath}&vers={vers}')
        d = handleAsJson(response)
        print()
        print(json.dumps(d, indent=4))
        assert d["origins"] == [
            "test.moo.bar.results.Pf@0",
            "test.moo.bar.results.Pf.R@0",
            "test.moo.bar.results.Pf.T@1"
        ]

@pytest.mark.parametrize('studypath, vers, expected', [
    ['test.moo.study.expansions', 'v1.0.0', ("special-studypage-test-moo-study-expansions-studyPage-_w14_v1-0-0", "target_type", "WIDG")],
    ['test.moo.bar.results.Pf', 'v2.0.0', ("special-studypage-test-moo-bar-results-Pf-studyPage-_w4_v2-0-0", "origin", "test.moo.bar.results.Pf.T@1")],
    ['test.moo.bar.results.Pf', 'v2.1.0', ("special-studypage-test-moo-bar-results-Pf-studyPage-_w12_v2-1-0", "origin", "test.moo.bar.results.Pf.E.A1@2")],
])
def test_load_study_page(app, client, repos_ready, studypath, vers, expected):
    with app.app_context():
        response = client.post(f'{ISE_PREFIX}/loadAnnotation?special=studypage&libpath=special.studypage.{studypath}.studyPage&vers={vers}&studyData={{}}')
        d = handleAsJson(response)
        print()
        print(json.dumps(d, indent=4))
        #return
        print(d['html'])
        data_str = d['data_json']
        data = json.loads(data_str)
        print(json.dumps(data, indent=4))
        x = data['widgets']
        for k in expected[:-1]:
            x = x[k]
        assert x == expected[-1]

def test_get_theory_map_lower(app, client, repos_ready):
    with app.app_context():
        deducpath = 'test.hist.lit.H.ilbert.ZB.Thm119.Thm'
        vers = "v0.0.0"
        type_ = 'lower'
        resp = client.get(f'{ISE_PREFIX}/getTheoryMap?deducpath={deducpath}&vers={vers}&type={type_}')
        d = handleAsJson(resp)
        print()
        print(json.dumps(d, indent=4))
        #return
        dg = d["dashgraph"]
        assert {v["ghostOf"].split('.')[-2] for v in dg["children"].values()} == {
            "Thm119", "Thm24", "Thm31", "Thm118", "Thm26", "Pg180L1"
        }

def test_get_theory_map_upper(app, client, repos_ready):
    with app.app_context():
        deducpath = 'test.hist.lit.H.ilbert.ZB.Thm8.Thm'
        vers = "v0.0.0"
        type_ = 'upper'
        resp = client.get(f'{ISE_PREFIX}/getTheoryMap?deducpath={deducpath}&vers={vers}&type={type_}')
        d = handleAsJson(resp)
        print()
        print(json.dumps(d, indent=4))
        dg = d["dashgraph"]
        assert {v["ghostOf"].split('.')[-2] for v in dg["children"].values()} == {
            "Thm8", "Thm9"
        }

def test_get_deduction_closure(app, client, repos_ready):
    with app.app_context():
        vers = 'v3.0.0'
        libpaths = ['test.moo.spam.Ch1.Sec7.Pf15.A30', 'test.moo.spam.Ch1.Sec7.Pf15.E20.I2', 'test.moo.spam.Ch1.Sec7.Thm15']
        versions = [vers] * 3
        lps = ','.join(libpaths)
        vs = ','.join(versions)
        resp = client.get(f'{ISE_PREFIX}/getDeductionClosure?libpaths={lps}&versions={vs}')
        d = handleAsJson(resp)
        print()
        print(json.dumps(d, indent=4))
        assert set(d["closure"]) == {
            "test.moo.spam.Ch1.Sec7.Thm15",
            "test.moo.spam.Ch1.Sec7.Pf15"
        }

def test_get_modpath(app, client, repos_ready):
    with app.app_context():
        vers = 'v3.0.0'
        libpath = 'test.moo.spam.Ch1.Sec7.Pf15.A30'
        resp = client.get(f'{ISE_PREFIX}/getModpath?libpath={libpath}&vers={vers}')
        d = handleAsJson(resp)
        print()
        print(json.dumps(d, indent=4))
        assert d["modpath"] == 'test.moo.spam.Ch1.Sec7'

def test_forest_update_helper_0(app, client, repos_ready):
    """
    This request should fail since we did not provide a version number mapping.
    """
    with app.app_context():
        info = {
            "current_forest": {},
            #"on_board": [],
            "off_board": "<all>",
            "to_view": [
                "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A.D330.A10",
                "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A.D330.A20"
            ],
            "incl_nbhd_in_view": True
        }
        response = client.post(f'{ISE_PREFIX}/forestUpdateHelper', data={
            "info": json.dumps(info)
        })
        d = handleAsJson(response)
        print()
        print(json.dumps(d, indent=4))
        assert d["err_lvl"] == 257

def test_forest_update_helper_1(app, client, repos_ready):
    """
    This time we provide the version number mapping, and the
    request should succeed.
    """
    with app.app_context():
        info = {
            "current_forest": {},
            #"on_board": [],
            "off_board": "<all>",
            "to_view": [
                "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A.A10",
                "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A.A20"
            ],
            "desired_versions": {
                "test.hist.lit": "v0.0.0",
            },
            "incl_nbhd_in_view": True
        }
        response = client.post(f'{ISE_PREFIX}/forestUpdateHelper', data={
            "info": json.dumps(info)
        })
        d = handleAsJson(response)
        print()
        #print(json.dumps(d, indent=4))
        #return
        to_open = d["to_open"]
        view_closure = d["view_closure"]
        print(json.dumps(to_open, indent=4))
        assert set(to_open) == {
            "test.hist.lit.H.ilbert.ZB.Thm168.Thm",
            "test.hist.lit.H.ilbert.ZB.Thm168.Pf",
            "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A"
        }
        print(json.dumps(view_closure, indent=4))
        assert set(view_closure) == {
            "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A.Pf.Cs1.S",
            "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A.Pf.Cs1.Cs1A.S",
            "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A.A20",
            "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A.A30",
            "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A.A10"
        }

def test_release_loader(client, repos_ready):
    repopath = 'test.moo.bar'
    version = 'v2.0.0'
    resp = client.get(f'{ISE_PREFIX}/loadRepoTree?repopath={repopath}&vers={version}')
    d = handleAsJson(resp)
    print()
    print(json.dumps(d, indent=4))
    model = d["model"]
    assert len(model) == 4
    assert len([item for item in model if item["type"] == "MODULE"]) == 2
    assert len([item for item in model if item["type"] == "CHART"]) == 2


@pytest.mark.parametrize('url', [
'/loadDashgraph?libpath=test.moo.bar.results.Pf&vers=WIP',
'/getEnrichment?libpath=test.moo.bar.results.Pf&vers=WIP',
'/loadSource?libpaths=test.wid.get.notes2&versions=WIP',
'/lookupGoals?libpath=test.moo.bar.results.Pf&vers=WIP',
'/getTheoryMap?deducpath=%s&vers=WIP&type=lower' % 'test.hist.lit.H.ilbert.ZB.Thm119.Thm',
'/getTheoryMap?deducpath=%s&vers=WIP&type=upper' % 'test.hist.lit.H.ilbert.ZB.Thm8.Thm',
'/getDeductionClosure?libpaths=test.moo.spam.Ch1.Sec7.Pf15.A30&versions=WIP',
'/getModpath?libpath=test.moo.spam.Ch1.Sec7.Pf15.A30&vers=WIP'
])
@pytest.mark.psm(False)
def test_permission_rejections_GET(app, client, repos_ready, url):
    with app.app_context():
        resp = client.get(ISE_PREFIX + url)
        print()
        print(resp)
        d = handleAsJson(resp)
        #print(json.dumps(d, indent=4))
        assert d["err_lvl"] == PECode.INADEQUATE_PERMISSIONS


@pytest.mark.parametrize('url', [
'/loadAnnotation?libpath=%s&vers=WIP' % 'test.hist.lit.H.ilbert.ZB.Thm168.notes.Notes',
'/loadAnnotation?special=studypage&libpath=special.studypage.%s.studyPage&vers=WIP&studyData={}' % 'test.moo.bar.results.Pf',
])
@pytest.mark.psm(False)
def test_permission_rejections_POST(app, client, repos_ready, url):
    with app.app_context():
        resp = client.post(ISE_PREFIX + url)
        print()
        print(resp)
        d = handleAsJson(resp)
        #print(json.dumps(d, indent=4))
        assert d["err_lvl"] == PECode.INADEQUATE_PERMISSIONS

@pytest.mark.parametrize('info', [
{
    "current_forest": {},
    "off_board": "<all>",
    "to_view": [
        "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A.A10",
        "test.hist.lit.H.ilbert.ZB.Thm168.Pf1A.A20"
    ],
    "desired_versions": {
        "test.hist.lit": "WIP",
    },
    "incl_nbhd_in_view": True
},
{
    "current_forest": {"test.hist.lit.H.ilbert.ZB.Thm168.Pf1A@WIP":{}},
    "reload": "<all>",
    "incl_nbhd_in_view": True
}
])
def test_permission_rejection_fuh(app, client, repos_ready, info):
    with app.app_context():
        response = client.post(f'{ISE_PREFIX}/forestUpdateHelper', data={
            "info": json.dumps(info)
        })
        d = handleAsJson(response)
        #print()
        #print(json.dumps(d, indent=4))
        assert d["err_lvl"] == PECode.INADEQUATE_PERMISSIONS

@pytest.mark.parametrize('url, exp_err_code', [
    # In RepoLoader, we have retained an old check in the `self.confirm()` method,
    # where we make a call to `self.check_wip_mode()`. That method raises the `NO_WIP_MODE`
    # error.
    ('/loadRepoTree?repopath=test.moo.links&vers=WIP', PECode.NO_WIP_MODE),
    # The SourceLoader is the only other place where we ever used `self.check_wip_mode()`,
    # but this time it comes after the call to `self.check_repo_read_permission()`, so we
    # get a more generic error code. In Handlers, `self.check_permissions()` always comes
    # before `self.confirm()`, but in RepoLoader the repo permissions are not checked there;
    # they are checked later.
    ('/loadSource?libpaths=test.moo.links.deducs1&versions=WIP', PECode.INADEQUATE_PERMISSIONS),
])
@pytest.mark.asTestUser('moo')
@pytest.mark.wip(False)
def test_wip_rejection(client, repos_ready, url, exp_err_code):
    """
    Test that we get the expected rejections when the app
    is configured with ALLOW_WIP False.
    """
    response = client.get(ISE_PREFIX + url)
    d = handleAsJson(response)
    #print()
    #print(json.dumps(d, indent=4))
    assert d["err_lvl"] == exp_err_code


def test_request_ssnr(app, client):
    with app.app_context():
        app.config["OFFER_SERVER_SIDE_NOTE_RECORDING"] = True
        with login_context(client, 'moo'):
            resp = client.post(f'/ise/requestSsnr', data={'activate': 1, 'confirm': 0})
            d = handleAsJson(resp)
            assert 'conf_dialog_html' in d

            resp = client.post(f'/ise/requestSsnr', data={'activate': 1, 'confirm': 1})
            d = handleAsJson(resp)
            assert d['new_setting'] == UserProps.V_NOTES_STORAGE.BROWSER_AND_SERVER

            resp = client.post(f'/ise/requestSsnr', data={'activate': 0, 'confirm': 0})
            d = handleAsJson(resp)
            assert 'conf_dialog_html' in d

            resp = client.post(f'/ise/requestSsnr', data={'activate': 0, 'confirm': 1})
            d = handleAsJson(resp)
            assert d['new_setting'] == UserProps.V_NOTES_STORAGE.BROWSER_ONLY


def test_cannot_record_notes(app, client):
    with app.app_context():
        app.config["OFFER_SERVER_SIDE_NOTE_RECORDING"] = False
        goal_id = 'test.moo.spam.Ch1.Sec7.Pf.A10@1'
        state = 'checked'
        notes = 'easy!'
        resp = client.post(f'{ISE_PREFIX}/recordNotes', data={
            'goal_id': goal_id, 'state': state, 'notes': notes,
        })
        d = handleAsJson(resp)
        assert d["err_lvl"] == PECode.SSNR_SERVICE_DISABLED


def test_record_notes(app, client, repos_ready):
    """
    Test that a user can record server-side notes.
    """
    with app.app_context():
        app.config["ALLOW_TEST_REPO_LOGINS"] = True
        app.config["OFFER_SERVER_SIDE_NOTE_RECORDING"] = True
        goal_id = 'test.moo.spam.Ch1.Sec7.Pf.A10@1'
        state = 'checked'
        notes = 'easy!'

        # Before we log in, we can't make user settings, or record notes.
        resp = client.post(f'/ise/requestSsnr', data={'activate': 1, 'confirm': 1})
        d = handleAsJson(resp)
        assert d["err_lvl"] == PECode.USER_NOT_LOGGED_IN
        resp = client.post(f'{ISE_PREFIX}/recordNotes', data={
            'goal_id': goal_id, 'state': state, 'notes': notes,
        })
        d = handleAsJson(resp)
        assert d["err_lvl"] == PECode.USER_NOT_LOGGED_IN

        # Now log in, but try again to record notes, before updating the
        # notes storage setting.
        with login_context(client, 'moo'):
            resp = client.post(f'{ISE_PREFIX}/recordNotes', data={
                'goal_id': goal_id, 'state': state, 'notes': notes,
            })
            d = handleAsJson(resp)
            assert d["err_lvl"] == PECode.ACTION_PROHIBITED_BY_USER_SETTINGS

            # Finally we update our notes storage setting, and then record notes.
            resp = client.post(f'/ise/requestSsnr', data={'activate': 1, 'confirm': 1})
            d = handleAsJson(resp)
            #print()
            #print(json.dumps(d, indent=4))
            assert d["err_lvl"] == 0
            resp = client.post(f'{ISE_PREFIX}/recordNotes', data={
                'goal_id': goal_id, 'state': state, 'notes': notes,
            })
            d = handleAsJson(resp)
            assert d["err_lvl"] == 0
            assert d["notes_successfully_recorded"] is True

            # Now blank out these notes:
            resp = client.post(f'{ISE_PREFIX}/recordNotes', data={
                'goal_id': goal_id, 'state': 'unchecked', 'notes': '',
            })
            d = handleAsJson(resp)
            assert d["err_lvl"] == 0
            assert d["notes_successfully_recorded"] is True


def test_load_and_purge_notes(app, client):
    with app.app_context():
        app.config["ALLOW_TEST_REPO_LOGINS"] = True
        app.config["OFFER_SERVER_SIDE_NOTE_RECORDING"] = True
        with login_context(client, 'moo'):
            client.post(f'/ise/requestSsnr', data={'activate': 1, 'confirm': 1})
            notes = {
                'test.moo.study.expansions.Notes3.w2@1': {
                    'checked': True,
                    'notes': 'Some notes on goal w2...',
                },
                'test.moo.study.expansions.X.A1@1': {
                    'checked': False,
                    'notes': 'Some notes on node A1...',
                }
            }
            for goal_id, info in notes.items():
                client.post(f'{ISE_PREFIX}/recordNotes', data={
                    'goal_id': goal_id,
                    'state': 'checked' if info['checked'] else 'unchecked',
                    'notes': info['notes'],
                })

            # Show that it doesn't hurt to request our notes on a goal for which
            # we have none. We simply get nothing back under that key in the
            # response.
            extra = 'test.moo.study.expansions.X.A2@1'
            goal_ids = ','.join(list(notes.keys()) + [extra])
            resp = client.post(f'{ISE_PREFIX}/loadNotes', data={'goal_ids': goal_ids})
            d = handleAsJson(resp)
            goal_info = d['goal_info']
            assert extra not in goal_info
            assert goal_info == notes

            # Try requesting _all_ notes.
            resp = client.post(f'{ISE_PREFIX}/loadNotes', data={'goal_ids': '', 'load_all': 'true'})
            d = handleAsJson(resp)
            goal_info = d['goal_info']
            assert goal_info == notes

            # Attempt purge, but with missing confirmation string.
            resp = client.post(f'{ISE_PREFIX}/purgeNotes', data={})
            d = handleAsJson(resp)
            print(json.dumps(d, indent=4))
            assert d["err_lvl"] == PECode.MISSING_INPUT

            # Attempt purge, but with unknown confirmation string.
            resp = client.post(f'{ISE_PREFIX}/purgeNotes', data={'confirmation': 'ImNotSoSure'})
            d = handleAsJson(resp)
            print(json.dumps(d, indent=4))
            assert d["err_lvl"] == PECode.INPUT_WRONG_TYPE

            # Attempt purge, but with alternate conf string which, for testing purposes,
            # will get past the input check, but will not confirm the purge.
            resp = client.post(f'{ISE_PREFIX}/purgeNotes', data={'confirmation': 'DELETEALLMYNOTES'})
            d = handleAsJson(resp)
            print(json.dumps(d, indent=4))
            assert d["err_lvl"] == 0
            assert d["num_remaining_notes"] == 2

            # This time purge should succeed.
            resp = client.post(f'{ISE_PREFIX}/purgeNotes', data={'confirmation': 'DeleteAllMyNotes'})
            d = handleAsJson(resp)
            print(json.dumps(d, indent=4))
            assert d["err_lvl"] == 0
            assert d["num_remaining_notes"] == 0


user_info_01 = {
    "username": "test.moo",
    "properties": {
        "USERTYPE": "USER",
        "EMAIL": "test.moo@localhost",
        "OWNED_ORGS": [],
        "TRUST": {},
        "NOTES_STORAGE": "BROWSER_AND_SERVER",
        "HOSTING": {}
    },
    "study_notes": {
        "test.moo.study.expansions.X.A1@1": {
            "checked": False,
            "notes": "Some notes on node A1..."
        },
        "test.moo.study.expansions.Notes3.w2@1": {
            "checked": True,
            "notes": "Some notes on goal w2..."
        }
    }
}

def test_export_user_info(app, client):
    with app.app_context():
        app.config["ALLOW_TEST_REPO_LOGINS"] = True
        app.config["OFFER_SERVER_SIDE_NOTE_RECORDING"] = True
        with login_context(client, 'moo'):
            client.post(f'/ise/requestSsnr', data={'activate': 1, 'confirm': 1})
            notes = {
                'test.moo.study.expansions.Notes3.w2@1': {
                    'checked': True,
                    'notes': 'Some notes on goal w2...',
                },
                'test.moo.study.expansions.X.A1@1': {
                    'checked': False,
                    'notes': 'Some notes on node A1...',
                }
            }
            for goal_id, info in notes.items():
                client.post(f'{ISE_PREFIX}/recordNotes', data={
                    'goal_id': goal_id,
                    'state': 'checked' if info['checked'] else 'unchecked',
                    'notes': info['notes'],
                })

            resp = client.get(f'{ISE_PREFIX}/exportUserInfo?target=all&mode=download')
            info = handleAsJson(resp)
            print(json.dumps(info, indent=4))
            del info['properties']['CTIME']
            assert info == user_info_01


def test_purge_acct(app, client):
    with app.app_context():
        app.config["ALLOW_TEST_REPO_LOGINS"] = True
        app.config["OFFER_SERVER_SIDE_NOTE_RECORDING"] = True

        gr = get_graph_reader()
        Nv0 = gr.num_nodes_in_db()
        Ne0 = gr.num_edges_in_db()

        with login_context(client, 'moo'):

            # User node has been added. No new edges.
            assert gr.num_nodes_in_db() == Nv0 + 1
            assert gr.num_edges_in_db() == Ne0
            assert gr.load_user('test.moo') is not None

            client.post(f'/ise/requestSsnr', data={'activate': 1, 'confirm': 1})
            notes = {
                'test.moo.study.expansions.Notes3.w2@1': {
                    'checked': True,
                    'notes': 'Some notes on goal w2...',
                },
                'test.moo.study.expansions.X.A1@1': {
                    'checked': False,
                    'notes': 'Some notes on node A1...',
                }
            }
            for goal_id, info in notes.items():
                client.post(f'{ISE_PREFIX}/recordNotes', data={
                    'goal_id': goal_id,
                    'state': 'checked' if info['checked'] else 'unchecked',
                    'notes': info['notes'],
                })

            # Two new edges, for the user's notes:
            assert gr.num_edges_in_db() == Ne0 + 2

            # Attempt purge, but with missing confirmation string.
            resp = client.post(f'{ISE_PREFIX}/purgeUserAcct', data={})
            d = handleAsJson(resp)
            print(json.dumps(d, indent=4))
            assert d["err_lvl"] == PECode.MISSING_INPUT

            # Attempt purge, but with unknown confirmation string.
            resp = client.post(f'{ISE_PREFIX}/purgeUserAcct', data={'confirmation': 'ImNotSoSure'})
            d = handleAsJson(resp)
            print(json.dumps(d, indent=4))
            assert d["err_lvl"] == PECode.INPUT_WRONG_TYPE

            # Attempt purge, but with alternate conf string which, for testing purposes,
            # will get past the input check, but will not confirm the purge.
            resp = client.post(f'{ISE_PREFIX}/purgeUserAcct', data={'confirmation': 'DELETEMYACCOUNT'})
            d = handleAsJson(resp)
            print(json.dumps(d, indent=4))
            assert d["err_lvl"] == 0
            assert d["user_nodes_deleted"] == 0

            # This time purge should succeed.
            resp = client.post(f'{ISE_PREFIX}/purgeUserAcct', data={'confirmation': 'DeleteMyAccount'})
            d = handleAsJson(resp)
            print(json.dumps(d, indent=4))
            assert d["err_lvl"] == 0
            assert d["user_nodes_deleted"] == 1

            # User node, and notes edges, are gone:
            assert gr.num_nodes_in_db() == Nv0
            assert gr.num_edges_in_db() == Ne0
            assert gr.load_user('test.moo') is None


def test_whoami(app, client):
    with app.app_context():
        app.config["ALLOW_TEST_REPO_LOGINS"] = True

        resp = client.get(f'{ISE_PREFIX}/whoAmI')
        d = handleAsJson(resp)
        print()
        print(json.dumps(d, indent=4))
        assert d["username"] is None
        assert d["props"] is None

        with login_context(client, 'moo'):
            resp = client.get(f'{ISE_PREFIX}/whoAmI')
            d = handleAsJson(resp)
            print(json.dumps(d, indent=4))

            assert d["username"] == "test.moo"

            props = d["props"]
            assert UserProps.K_CREATION_TIME in props

            del props[UserProps.K_CREATION_TIME]
            assert props == {
                UserProps.K_USERTYPE: UserProps.V_USERTYPE.USER,
                UserProps.K_EMAIL: "test.moo@localhost",
                UserProps.K_HOSTING: {},
                UserProps.K_NOTES_STORAGE: UserProps.V_NOTES_STORAGE.BROWSER_ONLY,
                UserProps.K_OWNED_ORGS: [],
                UserProps.K_TRUST: {},
            }

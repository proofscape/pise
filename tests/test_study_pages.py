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

from tests import handleAsJson, loginAsTestUser
from pfsc.gdb import get_graph_writer
from pfsc.constants import ISE_PREFIX
from pfsc.handlers.study import (
    StudyPageBuilder,
    GoalOriginFinder,
    GoalDataLoadMethod,
    DEFAULT_GOAL_DATA_LOAD_METHOD,
)

exp0 = """\
<h1>Study Notes</h1>
<hr />
<h2>Page</h2>
<p><a class="widget linkWidget special-studypage-test-moo-study-expansions-Notes3-studyPage-w1_v1-0-0" href="#"><code>Notes3</code></a></p>
<h2>Goals</h2>
<p><span class="widget goalWidget special-studypage-test-moo-study-expansions-Notes3-studyPage-w2_v1-0-0"><span class="graphics"></span></span> <a class="widget linkWidget special-studypage-test-moo-study-expansions-Notes3-studyPage-w3_v1-0-0" href="#"><code>w1</code></a></p>
<p>Some notes on goal w2...</p>
<p><span class="widget goalWidget special-studypage-test-moo-study-expansions-Notes3-studyPage-w4_v1-0-0"><span class="graphics"></span></span> <a class="widget linkWidget special-studypage-test-moo-study-expansions-Notes3-studyPage-w5_v1-0-0" href="#"><code>w2</code></a></p>
<p>Some notes on goal w2...</p>
<p><span class="widget goalWidget special-studypage-test-moo-study-expansions-Notes3-studyPage-w6_v1-0-0"><span class="graphics"></span></span> <a class="widget linkWidget special-studypage-test-moo-study-expansions-Notes3-studyPage-w7_v1-0-0" href="#"><code>w3</code></a></p>
<hr />
"""

exp1 = """\
<h1>Study Notes</h1>
<hr />
<h2>Deduction</h2>
<p><span class="widget goalWidget special-studypage-test-moo-study-expansions-X-studyPage-w1_v1-0-0"><span class="graphics"></span></span> <a class="widget chartWidget special-studypage-test-moo-study-expansions-X-studyPage-w2_v1-0-0" href="#"><code>X</code></a></p>
<h2>Goals</h2>
<p><span class="widget goalWidget special-studypage-test-moo-study-expansions-X-studyPage-w3_v1-0-0"><span class="graphics"></span></span> <a class="widget chartWidget special-studypage-test-moo-study-expansions-X-studyPage-w4_v1-0-0" href="#"><code>A1</code></a></p>
<p>Some notes on node A1...</p>
<p><span class="widget goalWidget special-studypage-test-moo-study-expansions-X-studyPage-w5_v1-0-0"><span class="graphics"></span></span> <a class="widget chartWidget special-studypage-test-moo-study-expansions-X-studyPage-w6_v1-0-0" href="#"><code>A2</code></a></p>
<hr />
"""
exp2 = """\
<h1>Study Notes</h1>
<hr />
<h2>Deduction</h2>
<p><span class="widget goalWidget special-studypage-test-moo-study-expansions-studyPage-w1_v1-0-0"><span class="graphics"></span></span> <a class="widget chartWidget special-studypage-test-moo-study-expansions-studyPage-w2_v1-0-0" href="#"><code>X</code></a></p>
<h2>Goals</h2>
<p><span class="widget goalWidget special-studypage-test-moo-study-expansions-studyPage-w3_v1-0-0"><span class="graphics"></span></span> <a class="widget chartWidget special-studypage-test-moo-study-expansions-studyPage-w4_v1-0-0" href="#"><code>A1</code></a></p>
<p>Some notes on node A1...</p>
<p><span class="widget goalWidget special-studypage-test-moo-study-expansions-studyPage-w5_v1-0-0"><span class="graphics"></span></span> <a class="widget chartWidget special-studypage-test-moo-study-expansions-studyPage-w6_v1-0-0" href="#"><code>A2</code></a></p>
<hr />
<h2>Page</h2>
<p><a class="widget linkWidget special-studypage-test-moo-study-expansions-studyPage-w7_v1-0-0" href="#"><code>Notes1</code></a></p>
<h2>Goals</h2>
<hr />
<h2>Page</h2>
<p><a class="widget linkWidget special-studypage-test-moo-study-expansions-studyPage-w8_v1-0-0" href="#"><code>Notes2</code></a></p>
<h2>Goals</h2>
<hr />
<h2>Page</h2>
<p><a class="widget linkWidget special-studypage-test-moo-study-expansions-studyPage-w9_v1-0-0" href="#"><code>Notes3</code></a></p>
<h2>Goals</h2>
<p><span class="widget goalWidget special-studypage-test-moo-study-expansions-studyPage-w10_v1-0-0"><span class="graphics"></span></span> <a class="widget linkWidget special-studypage-test-moo-study-expansions-studyPage-w11_v1-0-0" href="#"><code>w1</code></a></p>
<p>Some notes on goal w2...</p>
<p><span class="widget goalWidget special-studypage-test-moo-study-expansions-studyPage-w12_v1-0-0"><span class="graphics"></span></span> <a class="widget linkWidget special-studypage-test-moo-study-expansions-studyPage-w13_v1-0-0" href="#"><code>w2</code></a></p>
<p>Some notes on goal w2...</p>
<p><span class="widget goalWidget special-studypage-test-moo-study-expansions-studyPage-w14_v1-0-0"><span class="graphics"></span></span> <a class="widget linkWidget special-studypage-test-moo-study-expansions-studyPage-w15_v1-0-0" href="#"><code>w3</code></a></p>
<hr />
"""

@pytest.mark.parametrize(['studypath', 'expected'], [
    ['test.moo.study.expansions.Notes3', exp0],
    ['test.moo.study.expansions.X', exp1],
    ['test.moo.study.expansions', exp2]
])
@pytest.mark.req_csrf(False)
def test_study_page_builder(app, repos_ready, studypath, expected):
    print()
    studyData = {
        'test.moo.study.expansions.Notes3.w2@1': {
            'checked': True,
            'notes': 'Some notes on goal w2...',
        },
        'test.moo.study.expansions.X.A1@1': {
            'checked': False,
            'notes': 'Some notes on node A1...',
        }
    }
    with app.app_context():
        vers = 'v1.0.0'
        with app.test_request_context():
            args = {
                'libpath': f'special.studypage.{studypath}.studyPage',
                'vers': vers,
                'studyData': json.dumps(studyData),
            }
            spb = StudyPageBuilder(args)
            spb.process()
            resp = spb.generate_response()
            html = resp['html']
            print(html)
            if expected is not None:
                assert html == expected


@pytest.mark.parametrize(['studypath', 'expected'], [
    ['test.moo.study.expansions.Notes3', exp0],
    ['test.moo.study.expansions.X', exp1],
    ['test.moo.study.expansions', exp2]
])
def test_study_page_builder_with_SSNR(app, repos_ready, client, studypath, expected):
    """
    This time we test the study page builder with server-side notes.
    """
    studyData = {
        'test.moo.study.expansions.Notes3.w2@1': {
            'checked': True,
            'notes': 'Some notes on goal w2...',
        },
        'test.moo.study.expansions.X.A1@1': {
            'checked': False,
            'notes': 'Some notes on node A1...',
        }
    }
    with app.app_context():
        app.config["ALLOW_TEST_REPO_LOGINS"] = True
        app.config["OFFER_SERVER_SIDE_NOTE_RECORDING"] = True
        loginAsTestUser(client, 'moo')
        client.post(f'/ise/requestSsnr', data={'activate': 1, 'confirm': 1})
        for goal_id, info in studyData.items():
            client.post(f'{ISE_PREFIX}/recordNotes', data={
                'goal_id': goal_id,
                'state': 'checked' if info['checked'] else 'unchecked',
                'notes': info['notes'],
            })

        args = {
            'special': 'studypage',
            'libpath': f'special.studypage.{studypath}.studyPage',
            'vers': 'v1.0.0',
            'studyData': '{}',
        }
        resp = client.post(f'{ISE_PREFIX}/loadAnnotation', data=args)
        d = handleAsJson(resp)
        #print(json.dumps(d, indent=4))

        html = d['html']
        print(html)
        if expected is not None:
            assert html == expected

        get_graph_writer().delete_user('test.moo', definitely_want_to_delete_this_user=True)


@pytest.mark.req_csrf(False)
def test_goal_origin_finder(app, repos_ready):
    libpath = 'test.moo.bar.results.Pf'
    vers = 'v2.0.0'
    args = {
        'libpath': libpath,
        'vers': vers,
    }
    with app.app_context():
        method = DEFAULT_GOAL_DATA_LOAD_METHOD
        #method = GoalDataLoadMethod.MOD_LOAD
        h = GoalOriginFinder(args, method=method)
        h.process()
        resp = h.generate_response()
        print()
        print(json.dumps(resp, indent=4))
        assert resp["origins"] == [
            "test.moo.bar.results.Pf@0",
            "test.moo.bar.results.Pf.R@0",
            "test.moo.bar.results.Pf.T@1"
        ]

@pytest.mark.req_csrf(False)
def test_study_page_builder_2(app, repos_ready):
    libpath = 'test.moo.bar.results.Pf'
    vers = 'v2.0.0'
    args = {
        'libpath': f'special.studypage.{libpath}.studyPage',
        'vers': vers,
        'studyData': '{}',
    }
    with app.app_context():
        h = StudyPageBuilder(args)
        h.process()
        resp = h.generate_response()
        print()
        #print(json.dumps(resp, indent=4))
        print(resp["html"])
        j = resp["data_json"]
        data = json.loads(j)
        print(json.dumps(data, indent=4))
        assert data["widgets"]["special-studypage-test-moo-bar-results-Pf-studyPage-w5_v2-0-0"]["origin"] == "test.moo.bar.results.Pf.T@1"

import cProfile, pstats, io
"""
For timings with StudyPageBuilder, whichever method you employ first operates
at an enormous disadvantage, since it has to load all the imported modules.
Thereafter these modules remain in the cache, and all subsequent runs get to
load them for free.

Therefore the first run is really a throwaway, as far as _comparison_ is
concerned. However, the first run gives the only meaningful representation of
the full cost of loading a study page.

Still, I actually do not yet understand the results.
The timings depend in a weird way on _which_ method goes first.
Obviously, since the MOD_LOAD method does need to load one more module,
it's conceivable this could make a difference; but I'm not yet seeing
the explanation for the times I'm getting.

Three runs each, on
    test.hist.lit.H.ilbert.ZB.Thm168.notes @ v0.0.0
using Neo4j, and on 2019 MacBook Pro:

BUILD-MOD-BUILD:
    1.5s, 0.18s, 0.15s
    1.5s, 0.19s, 0.18s
    1.5s, 0.19s, 0.14s
    
MOD-BUILD-MOD:
    1.4s, 0.32s, 0.22s
    1.4s, 0.32s, 0.19s
    1.4s, 0.32s, 0.19s

Did further testing after _partially_ implementing the GDB method.
(It is only partial because it does not handle goal widgets with altpaths.)
But that class does not show any significant speed up.
Therefore I see no reason to finish implementing it (which would require
sth like noting altpaths on widget j-nodes in the graph databse).

GDB-MOD-BUILD-GDB:
    1.4s, 0.19s, 0.33s, 0.23s
    1.4s, 0.21s, 0.31s, 0.23s
    1.4s, 0.18s, 0.30s, 0.24s

BUILD-MOD-BUILD-GDB:
    1.5s, 0.20s, 0.16s, 0.24s
    1.6s, 0.19s, 0.14s, 0.24s
    1.5s, 0.20s, 0.15s, 0.24s

"""
@pytest.mark.parametrize('method', [
    #GoalDataLoadMethod.GDB,
    GoalDataLoadMethod.BUILD_DIR,
    GoalDataLoadMethod.MOD_LOAD,
    GoalDataLoadMethod.BUILD_DIR,
    #GoalDataLoadMethod.MOD_LOAD,
    #GoalDataLoadMethod.GDB,
])
@pytest.mark.parametrize('handler', [
    StudyPageBuilder,
    GoalOriginFinder,
])
def test_timings_1(app, repos_ready, handler, method):
    print()
    print('=' * 50)
    print(f'{handler.__name__}, {method}\n')
    libpath = 'test.hist.lit.H.ilbert.ZB.Thm168.notes'
    vers = 'v0.0.0'
    args = {
        'libpath': f'special.studypage.{libpath}.studyPage',
        'vers': vers,
        'studyData': '{}',
    }
    with app.app_context():
        h = handler(args, method=method)
        #h = GoalOriginFinder(args, method=method)
        with cProfile.Profile() as pr:
            h.process()
        s = io.StringIO()
        sortby = pstats.SortKey.CUMULATIVE
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats(10)
        print(s.getvalue())

# --------------------------------------------------------------------------- #
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

import pytest

from pfsc.constants import UserProps
from pfsc.gdb import get_gdb, get_graph_reader, get_graph_writer
from pfsc.gdb.user import UserNotes

from tests import user_context


def test_get_db(app):
    with app.app_context():
        gdb = get_gdb()
        reader = get_graph_reader()
        writer = get_graph_writer()
        # Getting again should return the same object.
        assert gdb is get_gdb()
        assert reader is get_graph_reader()
        assert writer is get_graph_writer()

def test_get_ancestor_chain(app, repos_ready):
    with app.app_context():
        deducpath = 'test.casey.math.expand2.W7'
        chain = get_graph_reader().get_ancestor_chain(deducpath, 2)
        print()
        for link in chain:
            print(link)
        assert chain == [
            ['test.alex.math.thm2.Thm2', 'v2.0.0', 'inf'],
            ['test.alex.math.thm2.Pf2', 'v2.0.0', 'inf'],
            ['test.brook.math.exp1.X3', 'v2.0.0', 'inf'],
        ]

def test_get_deduc_closure(app, repos_ready):
    with app.app_context():
        libpaths = ['test.alex.math.thm1.Pf.A2', 'test.alex.math.thm2.Thm2.C2', 'test.alex.math.thm2.Thm2.C3', 'test.alex.math.thm2.Thm2', 'test.alex.math.thm2.Pf13']
        libpaths_by_major = {
            3: libpaths,
        }
        expected_closure = {'test.alex.math.thm1.Pf', 'test.alex.math.thm2.Thm2', 'test.alex.math.thm2.Pf13'}
        computed_closure1 = get_graph_reader().get_deduction_closure(libpaths_by_major)
        assert computed_closure1 == expected_closure
        # FIXME: This one needs to be updated to accept version numbers:
        #computed_closure2 = lp_get_deduc_closure(libpaths)
        #assert computed_closure2 == expected_closure

def test_get_deductive_nbrs(app, repos_ready):
    print()
    with app.app_context():
        lp_by_maj_1 = {
            1: ['test.moo.spam.Ch1.Sec7.Pf.A60']
        }
        computed_nbrs_1 = get_graph_reader().get_deductive_nbrs(lp_by_maj_1)
        expected_nbrs_1 = {
            'test.moo.spam.Ch1.Sec7.Pf.A40',
            'test.moo.spam.Ch1.Sec7.Pf.A50',
            'test.moo.spam.Ch1.Sec7.Pf.Thm15.C'
        }
        print(computed_nbrs_1)
        assert computed_nbrs_1 == expected_nbrs_1
        lp_by_maj_3 = {
            3: ['test.moo.spam.Ch1.Sec7.Pf15.A60']
        }
        computed_nbrs_3 = get_graph_reader().get_deductive_nbrs(lp_by_maj_3)
        expected_nbrs_3 = {
            'test.moo.spam.Ch1.Sec7.Pf15.A40',
            'test.moo.spam.Ch1.Sec7.Pf15.A70',
            'test.moo.spam.Ch1.Sec7.Pf15.A80',
            'test.moo.spam.Ch1.Sec7.Pf15.Thm15.C'
        }
        print(computed_nbrs_3)
        assert computed_nbrs_3 == expected_nbrs_3

@pytest.mark.parametrize(['libpath', 'major', 'expected'], [
('test.alex.math.thm1.Pf.A2', 3, False),
('test.alex.math.thm1.Pf', 3, True),
])
def test_is_deduc(app, repos_ready, libpath, major, expected):
    with app.app_context():
        assert get_graph_reader().is_deduc(libpath, major) == expected

@pytest.mark.parametrize(['libpath', 'major', 'expected'], [
('test.moo.comment.bar.NotesS.w1', 0, False),
('test.moo.comment.bar.NotesS', 0, True),
])
def test_is_anno(app, repos_ready, libpath, major, expected):
    with app.app_context():
        assert get_graph_reader().is_anno(libpath, major) == expected


def test_user_update(app):
    with app.app_context():
        gw = get_graph_writer()
        username = 'test.foo'
        with user_context(app, username, 'foo@localhost', []) as u:
            user, _ = u[0]
            assert not user.wants_server_side_note_recording()
            user.prop(UserProps.K_NOTES_STORAGE, UserProps.V_NOTES_STORAGE.BROWSER_AND_SERVER)
            gw.update_user(user)
            user1 = gw.reader.load_user(username)
            assert user1.wants_server_side_note_recording()


def test_load_user_notes(app, repos_ready):
    with app.app_context():
        gw = get_graph_writer()
        username = 'test.foo'
        with user_context(app, username, 'foo@localhost', []):
            goalpath = 'test.moo.spam.Ch1.Sec7.Pf.A10'
            goal_major = 1
            # Round I:
            state = 'unchecked'
            notes = 'interesting...'
            user_notes0 = UserNotes(goalpath, goal_major, state, notes)
            gw.record_user_notes(username, user_notes0)
            user_notes1 = gw.reader.load_user_notes(username, [(goalpath, goal_major)])[0]
            assert user_notes1 == user_notes0
            # Round II:
            state = 'checked'
            notes = 'Apply Lemma 5!'
            user_notes0 = UserNotes(goalpath, goal_major, state, notes)
            gw.record_user_notes(username, user_notes0)
            user_notes1 = gw.reader.load_user_notes(username, [(goalpath, goal_major)])[0]
            assert user_notes1 == user_notes0
            # Round III: Record blank notes. NOTES edge should be deleted.
            state = 'unchecked'
            notes = ''
            user_notes0 = UserNotes(goalpath, goal_major, state, notes)
            assert user_notes0.is_blank()
            gw.record_user_notes(username, user_notes0)
            result = gw.reader.load_user_notes(username, [(goalpath, goal_major)])
            assert len(result) == 0


def test_actions_on_all_of_one_users_notes(app, repos_ready):
    """
    Test actions on all of a user's notes; namely:
    * load all of a user's notes,
    * delete all of a user's notes.
    """
    with app.app_context():
        gw = get_graph_writer()
        username1 = 'test.foo'
        username2 = 'test.bar'

        def record_some_notes(username):
            original_notes = set()
            goal_major = 1
            nodes = """
            A10
            E20
              E20.I1 E20.I2 E20.A3 E20.A4
            A30
            A40
            """.split()
            for i, node in enumerate(nodes):
                state = 'checked' if i % 2 == 0 else 'unchecked'
                notes = f'{username} says: Node {node} is interesting...'
                goalpath = f'test.moo.spam.Ch1.Sec7.Pf.{node}'
                user_notes = UserNotes(goalpath, goal_major, state, notes)
                original_notes.add(user_notes)
                gw.record_user_notes(username, user_notes)
            return original_notes

        with user_context(app, username1, 'foo@localhost', []):
            with user_context(app, username2, 'bar@localhost', []):
                # Each user records some notes.
                original_notes1 = record_some_notes(username1)
                original_notes2 = record_some_notes(username2)

                # Load all of first user's notes. Should equal original set.
                loaded_notes = gw.reader.load_user_notes(username1, None)
                assert set(loaded_notes) == original_notes1

                # Delete all of first user's notes.
                Nv0 = gw.reader.num_nodes_in_db()
                Ne0 = gw.reader.num_edges_in_db()
                gw.delete_all_notes_of_one_user(username1, definitely_want_to_delete_all_notes=True)
                Nv1 = gw.reader.num_nodes_in_db()
                Ne1 = gw.reader.num_edges_in_db()
                loaded_notes1 = gw.reader.load_user_notes(username1, None)
                loaded_notes2 = gw.reader.load_user_notes(username2, None)
                # First user's notes are all gone:
                assert len(loaded_notes1) == 0
                # Second user's notes are unaffected:
                assert set(loaded_notes2) == original_notes2
                # Number of nodes in db is unaffected:
                assert Nv1 == Nv0
                # Number of edges in db should go down by number of notes taken
                # by first user:
                assert Ne0 - Ne1 == len(original_notes1)


def test_load_user_notes_on_deduc(app, repos_ready):
    with app.app_context():
        gw = get_graph_writer()
        username = 'test.foo'
        with user_context(app, username, 'foo@localhost', []):
            notes0 = [
                UserNotes('test.moo.spam.Ch1.Sec7.Pf.A10', 1, 'checked', 'foo'),
                UserNotes('test.moo.spam.Ch1.Sec7.Pf15.A80', 3, 'checked', 'bar'),
            ]
            for un in notes0:
                gw.record_user_notes(username, un)

            notes1 = gw.reader.load_user_notes_on_deduc(
                username, 'test.moo.spam.Ch1.Sec7.Pf15', 3)

            assert set(notes1) == set(notes0)

        #gw.delete_user(username, definitely_want_to_delete_this_user=True)


def test_load_user_notes_on_anno(app, repos_ready):
    with app.app_context():
        gw = get_graph_writer()
        username = 'test.foo'
        with user_context(app, username, 'foo@localhost', []):
            notes0 = [
                UserNotes('test.moo.study.expansions.Notes3.w1', 1, 'checked', 'foo'),
                UserNotes('test.moo.study.expansions.Notes3.w2', 1, 'checked', 'bar'),
            ]
            for un in notes0:
                gw.record_user_notes(username, un)

            notes1 = gw.reader.load_user_notes_on_anno(
                username, 'test.moo.study.expansions.Notes3', 1)

            assert set(notes1) == set(notes0)


def test_load_user_notes_on_module(app, repos_ready):
    with app.app_context():
        gw = get_graph_writer()
        username = 'test.foo'
        with user_context(app, username, 'foo@localhost', []):
            notes0 = [
                UserNotes('test.moo.study.expansions.X.A2', 1, 'unchecked', 'foo'),
                UserNotes('test.moo.study.expansions.Notes3.w2', 1, 'checked', 'bar'),
            ]
            for un in notes0:
                gw.record_user_notes(username, un)

            notes1 = gw.reader.load_user_notes_on_module(
                username, 'test.moo.study.expansions', 1)

            assert set(notes1) == set(notes0)


def test_set_approvals(app, repos_ready):
    with app.app_context():
        gw = get_graph_writer()
        annopath = 'test.comment.notes.H.ilbert.ZB.Thm17.Notes'
        version = 'v0.1.0'
        other_version = 'v0.2.0'
        widgetpath1 = annopath + '.eg1_disp1'
        widgetpath2 = annopath + '.eg1_disp2'

        # Start clean:
        for wp in [widgetpath1, widgetpath2]:
            gw.set_approval(wp, version, False)

        gw.set_approval(widgetpath1, version, True)
        approvals = gw.reader.check_approvals_under_anno(annopath, version)
        assert approvals == [widgetpath1]

        gw.set_approval(widgetpath2, version, True)
        approvals = gw.reader.check_approvals_under_anno(annopath, version)
        assert set(approvals) == {widgetpath1, widgetpath2}
        approvals = gw.reader.check_approvals_under_anno(annopath, other_version)
        assert approvals == []

        gw.set_approval(widgetpath1, version, False)
        approvals = gw.reader.check_approvals_under_anno(annopath, version)
        assert approvals == [widgetpath2]

        gw.set_approval(widgetpath2, version, False)
        approvals = gw.reader.check_approvals_under_anno(annopath, version)
        assert approvals == []

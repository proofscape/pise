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

from flask import g as flask_g
from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import TextP
from gremlite import SQLiteConnection

from pfsc.constants import WIP_TAG, IndexType
from pfsc.gdb.writer import GraphWriter
from pfsc.gdb.k import make_kNode_from_jNode, make_kReln_from_jReln
import pfsc.gdb.gremlin.indexing as indexing
from pfsc.gdb.gremlin.util import (
    GTX, lp_covers, merge_node, is_user, lp_maj,
    set_kReln_reln_props,
)
from pfsc.build.versions import get_padded_components
from pfsc.excep import PfscExcep


GREMLIN_REMOTE_NAME = "gremlin_remote"


def using_sqlite():
    """
    Check whether we are using SQLite.
    """
    remote = getattr(flask_g, GREMLIN_REMOTE_NAME)
    return isinstance(remote, SQLiteConnection)


class GremlinGraphWriter(GraphWriter):
    """
    GraphWriter that speaks Gremlin.

    This subclass takes a kwarg indicating whether to use transactions or not.
    """

    def __init__(self, reader, use_transactions=True):
        super().__init__(reader)

        # If we are using an SQLiteConnection, then we force use of transactions, since
        # it supports them and they are to be preferred (both for atomicity and increased speed).

        # DEBUG
        self.use_transactions = True if using_sqlite() else use_transactions
        #self.use_transactions = False if using_sqlite() else use_transactions
        # ... ...

        self._tx = None

    @property
    def g(self) -> GTX:
        return self._tx if self._tx is not None else self.gdb

    def new_transaction(self):
        return self.g.tx().begin() if self.use_transactions else self.g

    def commit_transaction(self, gtx):
        if self.use_transactions:
            gtx.commit()

    def rollback_transaction(self, gtx):
        if self.use_transactions:
            gtx.rollback()

    def _drop_wip_nodes_under_module(self, modpath, gtx):
        gtx.V().has('modpath', modpath).has('major', WIP_TAG).union(
            __.identity(),
            __.out(IndexType.BUILD),
        ).barrier().drop().iterate()

    def ix0200(self, mii, gtx):
        if mii.V_cut:
            mii.note_begin_indexing_phase(220)
            ids = [mii.existing_k_nodes[uid].db_uid for uid in mii.V_cut]
            gtx.V(*ids).union(
                __.properties('cut').drop(),
                __.property('cut', mii.major)
            ).iterate()
            mii.note_task_element_completed(220, len(ids))
        if mii.E_cut:
            mii.note_begin_indexing_phase(240)
            ids = [mii.existing_k_relns[uid].db_uid for uid in mii.E_cut]
            gtx.E(*ids).union(
                __.properties('cut').drop(),
                __.property('cut', mii.major)
            ).iterate()
            mii.note_task_element_completed(240, len(ids))
        #return indexing.ix002682(mii, gtx)
        # For now we're sticking with method 2681 since we're getting weird,
        # unpredictable memory errors for 2682. The process of building all
        # test repos hangs at random points.
        return indexing.ix002681(mii, gtx)

    def ix0330(self, mii, gtx, verbose=False):
        items = mii.move_mapping.items()
        if verbose:
            print(f'Adding {len(items)} new moves.')
        move_counter, void_counter = 0, 0
        mii.note_begin_indexing_phase(330)
        for src, dst in items:
            tr = gtx
            if dst is None:
                void_counter += 1
                tr = merge_node(tr.V(), IndexType.VOID, {})
            else:
                move_counter += 1
                tr = lp_covers(dst, mii.major, tr.V())
            tr = tr.as_('d')
            tr = lp_covers(src, mii.current_maj_vers, tr.V())
            tr.add_e(IndexType.MOVE).to('d').iterate()
            mii.note_task_element_completed(330)
        if verbose:
            print(f'  ({move_counter}) ?:{IndexType.MOVE}:?')
            print(f'  ({void_counter}) ?:{IndexType.MOVE}:{IndexType.VOID}')

    def ix0360(self, mii, gtx, new_targeting_relns, verbose=False):
        if verbose:
            print('Searching for retargeting relations...')
        mii.note_begin_indexing_phase(360)
        retarget_counter = 0
        # (1) Enrichments we have added:
        for k in new_targeting_relns:
            mcs = self.reader.find_move_conjugate_chain(k.head_libpath, k.head_major)
            if mcs:
                retarget_counter += len(mcs)
                mc_ids = [mc.db_uid for mc in mcs]
                tr = lp_covers(k.tail_libpath, k.tail_major, gtx.V()).as_('e')
                tr = tr.V(mc_ids).add_e(IndexType.RETARGETS).from_('e')
                tr = set_kReln_reln_props(k, tr)
                tr.iterate()
            mii.note_task_element_completed(361)
        # (2) Existing enrichments on anything we moved:
        ids = [mii.existing_k_nodes[a].db_uid for a, b in
               mii.mm_closure.items() if b is not None]
        res = [] if not ids else gtx.V(ids).as_('t') \
            .in_e(IndexType.TARGETS, IndexType.RETARGETS).as_('r').out_v().as_('e') \
            .select('e', 'r', 't') \
            .by(__.element_map()).by(__.element_map()).by(__.element_map()).to_list()
        triples = [
            [
                make_kNode_from_jNode(d['e']).db_uid,
                make_kReln_from_jReln((d['e'], d['r'], d['t'])),
                mii.mm_closure[make_kNode_from_jNode(d['t']).libpath]
            ]
            for d in res
        ]
        if triples:
            retarget_counter += len(triples)
            tr = gtx
            for eid, k_reln, tlp in triples:
                tr = lp_covers(tlp, mii.major, tr.V()).as_('t'). \
                    V(eid).add_e(IndexType.RETARGETS).to('t')
                tr = set_kReln_reln_props(k_reln, tr)
            tr.iterate()
        mii.note_task_element_completed(362, len(ids))
        if verbose:
            print(f'  ({retarget_counter}) ?:{IndexType.RETARGETS}:?')

    def ix0400(self, mii, gtx):
        merge_node(gtx.V(), IndexType.VERSION, {
            'repopath': mii.repopath,
            'version': mii.version
        }, mii.write_version_node_props()).iterate()

    def _clear_test_indexing(self):
        self.g.V().has('repopath', TextP.starting_with('test.')).union(
            __.identity(),
            __.out(IndexType.BUILD),
        ).barrier().drop().iterate()
        self.g.V().has('username', TextP.starting_with('test.')).drop().iterate()

    def _do_delete_all_under_repo(self, repopath):
        self.g.V().has('repopath', repopath).union(
            __.identity(),
            __.out(IndexType.BUILD),
        ).barrier().drop().iterate()

    def _delete_full_build_at_version(self, repopath, version=WIP_TAG):
        M, m, p = get_padded_components(version)
        self.g.V().has('repopath', repopath).or_(
            __.has('version', version),
            __.and_(
                __.has('major', M), __.has('minor', m), __.has('patch', p),
            )
        ).union(
            __.identity(),
            __.out(IndexType.BUILD),
        ).barrier().drop().iterate()

    # ----------------------------------------------------------------------

    def _add_user(self, username, j_props):
        merge_node(self.g.V(), IndexType.USER, {
            'username': username
        }, {
            'properties': j_props
        }, label_order=1).iterate()

    def _delete_user(self, username, *,
                    definitely_want_to_delete_this_user=False):
        if not definitely_want_to_delete_this_user:
            return 0
        c0 = is_user(username, self.g.V()).count().next()
        if c0 == 0:
            return 0
        is_user(username, self.g.V()).drop().iterate()
        c1 = is_user(username, self.g.V()).count().next()
        return c0 - c1

    def _delete_all_notes_of_one_user(self, username, *,
                    definitely_want_to_delete_all_notes=False):
        if not definitely_want_to_delete_all_notes:
            return
        is_user(username, self.g.V()).out_e(IndexType.NOTES).drop().iterate()

    def _update_user(self, username, j_props):
        is_user(username, self.g.V()).union(
            __.properties('properties').drop(),
            __.property('properties', j_props)
        ).iterate()

    def _record_user_notes(self, username, user_notes):
        major0 = self.reader.adaptall(user_notes.goal_major)

        is_goal = lambda tr: lp_maj(user_notes.goalpath, major0, tr)

        # Retrieve a path of IDs, which will be of length 3, 2, or 1:
        # 3: we found user-[NOTES]->goal
        # 2: we found user, goal, but NOTES edge doesn't exist yet
        # 1: the goal node doesn't exist
        p = is_user(username, self.g.V()).coalesce(
            is_goal(__.out_e(IndexType.NOTES).in_v()).path().by(__.id_()),
            is_goal(__.V()).path().by(__.id_()),
            __.path().by(__.id_())
        ).next()

        n = len(p)
        if n == 1:
            raise PfscExcep(f'Cannot record notes. Origin {user_notes.write_origin()} does not exist.')
        elif n == 2:
            if not user_notes.is_blank():
                self.g.V(p[0]).as_('u').V(p[1]).add_e(IndexType.NOTES).from_('u') \
                    .property('state', user_notes.state).property('notes', user_notes.notes).iterate()
        else:
            assert n == 3
            tr = self.g.E(p[1])
            if user_notes.is_blank():
                tr.drop().iterate()
            else:
                tr.union(
                    __.properties('state', 'notes').drop(),
                    __.property('state', user_notes.state).property('notes', user_notes.notes)
                ).iterate()

    # ----------------------------------------------------------------------

    def _record_module_source(self, modpath, version, modtext):
        major0 = self.reader.adaptall(version)
        lp_covers(modpath, major0, self.g.V()).as_('m') \
            .add_v(IndexType.MOD_SRC) \
            .property('pfsc', modtext) \
            .add_e(IndexType.BUILD).from_('m') \
            .property(IndexType.P_BUILD_VERS, version).iterate()

    def _record_repo_manifest(self, repopath, version, manifest_json):
        self.g.V().has_label(IndexType.VERSION) \
            .has('repopath', repopath).has('version', version).union(
                __.properties('manifest').drop(),
                __.property('manifest', manifest_json)
            ).iterate()

    def _record_dashgraph(self, deducpath, version, dg_json):
        major0 = self.reader.adaptall(version)
        lp_covers(deducpath, major0, self.g.V()).as_('d') \
            .add_v(IndexType.DEDUC_BUILD) \
            .property('json', dg_json) \
            .add_e(IndexType.BUILD).from_('d') \
            .property(IndexType.P_BUILD_VERS, version).iterate()

    def _record_annobuild(self, annopath, version, anno_html, anno_json):
        major0 = self.reader.adaptall(version)
        lp_covers(annopath, major0, self.g.V()).as_('a') \
            .add_v(IndexType.ANNO_BUILD) \
            .property('html', anno_html) \
            .property('json', anno_json) \
            .add_e(IndexType.BUILD).from_('a') \
            .property(IndexType.P_BUILD_VERS, version).iterate()

    def _delete_builds_under_module(self, modpath, version):
        self.g.V().has('modpath', modpath) \
            .out_e(IndexType.BUILD).has(IndexType.P_BUILD_VERS, version) \
            .in_v().drop().iterate()

    # ----------------------------------------------------------------------

    def _set_approvals_dict_json(self, widgetpath, version, j):
        major0 = self.reader.adaptall(version)
        lp_covers(
            widgetpath, major0, self.g.V().has_label(IndexType.WIDGET)
        ).union(
            __.properties(IndexType.P_APPROVALS).drop(),
            __.property(IndexType.P_APPROVALS, j)
        ).iterate()

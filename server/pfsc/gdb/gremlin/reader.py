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
import time

from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import TextP, P

from pfsc.constants import IndexType, WIP_TAG
from pfsc.gdb.k import make_kNode_from_jNode, make_kReln_from_jReln
from pfsc.gdb.reader import GraphReader
from pfsc.gdb.gremlin.util import (
    among_lps, covers, lp_covers, lps_covers, edge_info, is_user)
from pfsc.gdb.user import UserNotes


class GremlinGraphReader(GraphReader):

    @property
    def g(self):
        # We use `writer.g` if possible, since that might be a transaction,
        # in which case we should participate in it.
        return self.writer.g if self.writer is not None else self.gdb

    def num_nodes_in_db(self):
        return self.g.V().count().next()

    def num_edges_in_db(self):
        return self.g.E().count().next()

    def all_nodes_under_repo(self, repopath):
        j_nodes = self.g.V().has('repopath', repopath).element_map().to_list()
        return [make_kNode_from_jNode(j) for j in j_nodes]

    def all_relns_under_repo(self, repopath):
        j_relns = edge_info(self.g.E().has('repopath', repopath)).to_list()
        return [make_kReln_from_jReln(j) for j in j_relns]

    def get_versions_indexed(self, repopath, include_wip=False):
        infos = self.g.V().has_label(IndexType.VERSION). \
            has('repopath', repopath).order().by('full'). \
            element_map().to_list()
        if infos and (not include_wip) and infos[-1]['major'] == WIP_TAG:
            infos = infos[:-1]
        return infos

    def version_is_already_indexed(self, repopath, version):
        n = self.g.V().has_label(IndexType.VERSION). \
            has('repopath', repopath).has('version', version).count().next()
        assert n < 2
        return n == 1

    def find_move_conjugate(self, libpath, major):
        major = self.adaptall(major)

        tr1 = lp_covers(libpath, major, self.g.V())
        if not tr1.has_next():
            # The node in question could not be found.
            return None

        # Note: the usages here of `.out_e().in_v()` are deliberate, and can *not*
        # be simplified to `out()`. The reason for this is that we need both edges and
        # vertices to be reported by the `path()` step.
        #
        # Note 2: Because the `repeat()` step is following outgoing UNDER edges, there
        # is no need for a `limit(1)`. No vertex in our database can ever have more than
        # one outgoing `UNDER` edge, so the BFS conducted by `repeat()` has nowhere else
        # to go, no other paths to explore. Once we hit the `until()` condition, the search
        # will stop, without need of a `limit(1)` to make it stop.
        tr2 = self.g.V(tr1.next()) \
            .until(__.out_e(IndexType.MOVE)) \
            .repeat(__.out_e(IndexType.UNDER).in_v()) \
            .out_e(IndexType.MOVE).in_v() \
            .union(
                __.path() \
                    .by(__.id_()) \
                    # The UNDER relns have a 'segment' property, but the MOVE
                    # relns do not, so we need a coalesce. (A path step returns no
                    # result at all if any of its `by()` modulators is non-productive.)
                    .by(__.coalesce(
                        __.values('segment'),
                        __.constant(0)
                    )),
                __.label()
            )

        if not tr2.has_next():
            # The node neither moved nor died.
            return None

        # Get a path of alternating node IDs and edge segment properties,
        # plus the label of the final node reached.
        p, label = tr2.to_list()
        if label == IndexType.VOID:
            # The node died.
            return IndexType.VOID

        # If we get this far, then the node moved, and should have a move-conjugate.
        sp = p[-1]
        n = len(p)
        assert n >= 3
        assert n % 2 == 1

        if n == 3:
            props = self.g.V(sp).element_map().next()
            return make_kNode_from_jNode(props)

        # `Path` instances do not accept slices, so we slice the `objects` attr, which is a list.
        segments = p.objects[-4::-2]

        tr = self.g.V(sp)
        for seg in segments:
            tr = tr.in_e(IndexType.UNDER).has('segment', seg).out_v()
        props = tr.element_map().next()
        return make_kNode_from_jNode(props)

    ################################################################################
    # Get existing objects

    """
    What is the most efficient way to query the database for all existing objects (both
    vertices and edges) at and under a given modpath, and for a given major version?
    
    At this time we have written two different methods, which are implemented in the
    `get_existing_j_objects_0()` and `get_existing_j_objects_1()` methods below.
    
    For now, we are simply using method 0, but I'm not convinced we really know which
    method (one of these, or perhaps another we haven't thought of yet) is really best.
    
    If you want to experiment with these methods again, here is how to do it:
    
        * In `get_existing_objects()`, pass `[0, 1]` to the `methods` kwarg of
            the `get_existing_objects_MULTI()` method. The latter tries both methods
            and compares their results.
        
        * In your `instance/.env`, set
            
                DUPLICATE_TEST_HIST_LIT=1
        
            which will cause there to be a `v1.0.0` of the `test.hist.lit` repo. This is
            important so that we can see, for a fairly large repo, how long it takes to
            fetch all existing objects for the previous version.
            See also the `tests.util.gather_repo_info()` function on this.
    """

    def get_existing_objects(self, modpath, major, recursive):
        # For now we're sticking with method 0.
        # Tests showed that both methods were taking about the same time.
        # I do wonder which one might scale better, but for now we leave this question for future work.
        methods = [0]
        # methods = [0, 1]
        return self.get_existing_objects_MULTI(modpath, major, recursive, methods=methods)

    def get_existing_objects_MULTI(self, modpath, major, recursive, methods=None):
        """
        All args are as for the `get_existing_objects()` method, except for `methods`,
        where you can pass a list of integers, being the numbers of the methods you
        want to employ. If more than one, we will compare their results.
        """
        if methods is None:
            methods = [0, 1]
        comparing = len(methods) > 1

        N, R = [], []
        for m in methods:
            get_existing_j_objects = getattr(self, f'get_existing_j_objects_{m}')

            existing_j_nodes, existing_j_relns = get_existing_j_objects(
                modpath, major, recursive, print_times=comparing)

            # Convert from j-nodes to k-nodes.
            existing_k_nodes = {}
            for j in existing_j_nodes:
                k = make_kNode_from_jNode(j)
                existing_k_nodes[k.uid] = k

            # Convert from j-relns to k-relns.
            existing_k_relns = {}
            for j in existing_j_relns:
                k = make_kReln_from_jReln(j)
                # Reject inferred relations.
                if k.reln_type in IndexType.INFERRED_RELNS:
                    continue
                existing_k_relns[k.uid] = k

            N.append(existing_k_nodes)
            R.append(existing_k_relns)

        N0, R0 = N[0], R[0]

        if comparing:
            # Did we get the same results?
            for m in methods[1:]:
                print(f'\nComparing method {m}')
                N, R = N[m], R[m]
                k1 = set(N.keys())
                k0 = set(N0.keys())
                if k1 != k0:
                    print('  Got different set of node keys.')
                else:
                    print('  Got same set of node keys.')
                if set(R.keys()) != set(R0.keys()):
                    print('  Got different set of reln keys.')
                else:
                    print('  Got same set of reln keys.')

        return N0, R0

    def get_existing_j_objects_0(self, modpath, major, recursive, print_times=False):
        """
        Use `starting_with()` to locate all objects having modpath with the right prefix.
        """

        t0 = time.time()

        existing_j_nodes = covers(
            major, self.g.V().has('modpath', modpath)
        ).element_map().to_list()
        # For a recursive build we also need nodes defined _under_ this module.
        if recursive:
            basepath = modpath + '.'
            existing_j_nodes_under_module = covers(
                major,
                self.g.V().has('modpath', TextP.starting_with(basepath))
            ).element_map().to_list()
            existing_j_nodes += existing_j_nodes_under_module

        t1 = time.time()

        existing_j_relns = edge_info(covers(
            major, self.g.E().has('modpath', modpath)
        )).to_list()
        if recursive:
            basepath = modpath + '.'
            existing_j_relns_under_module = edge_info(covers(
                major,
                self.g.E().has('modpath', TextP.starting_with(basepath))
            )).to_list()
            existing_j_relns += existing_j_relns_under_module

        t2 = time.time()

        if print_times:
            print('get_existing_j_objects_0 internal times:')
            print(f'  {t1 - t0}')
            print(f'  {t2 - t1}')

        return existing_j_nodes, existing_j_relns

    def get_existing_j_objects_1(self, modpath, major, recursive, print_times=False):
        """
        First do a BFS with `repeat()` to determine all the modpaths that begin with the
        right prefix, and then return all objects having any of these modpaths.
        """
        t0 = time.time()

        if not recursive:
            modpaths = [modpath]
        else:
            modpaths = covers(
                major,
                covers(
                    major, self.g.V().has('libpath', modpath)
                ).emit().repeat(__.in_(IndexType.UNDER).has_label(IndexType.MODULE))
            ).values('modpath').to_list()

        t1 = time.time()

        existing_j_nodes = covers(
            major, self.g.V().has('modpath', P.within(modpaths))
        ).element_map().to_list()

        t2 = time.time()

        existing_j_relns = edge_info(covers(
            major, self.g.E().has('modpath', P.within(modpaths))
        )).to_list()

        t3 = time.time()

        if print_times:
            print('get_existing_j_objects_1 internal times:')
            print(f'  {t1 - t0} ({len(modpaths)} modpaths)')
            print(f'  {t2 - t1} ({len(existing_j_nodes)} nodes)')
            print(f'  {t3 - t2} ({len(existing_j_relns)} relns)')

        return existing_j_nodes, existing_j_relns

    ################################################################################

    def _get_origins_internal(self, label, libpaths, major0):
        M = lps_covers(libpaths, major0, self.g.V().has_label(label)). \
            element_map('libpath', 'major', 'origin').to_list()
        return [(m['libpath'], m['major'], m.get('origin')) for m in M]

    def _find_enrichments_internal(self, deducpath, major0):
        tr = lp_covers(deducpath, major0, self.g.V()).union(
            __.identity().as_('t'),
            __.repeat(covers(major0, __.in_e(IndexType.UNDER)).out_v()).emit().as_('t')
        ).in_e(IndexType.TARGETS, IndexType.RETARGETS, IndexType.CF).as_('r').out_v().as_('e') \
                .select('e', 'r', 't') \
                .by(__.element_map()).by(__.element_map()).by(__.element_map()).to_list()
        return [make_kReln_from_jReln((i['e'], i['r'], i['t'])) for i in tr]

    def get_modpath(self, libpath, major):
        major0 = self.adaptall(major)
        tr = lp_covers(libpath, major0, self.g.V()).values('modpath')
        return None if not tr.has_next() else tr.next()

    def get_ancestor_chain(self, deducpath, major):
        major0 = self.adaptall(major)
        tr = lp_covers(deducpath, major0, self.g.V())
        tr = tr.repeat(__.out_e(IndexType.EXPANDS).as_('e').in_v().as_('d')).emit()
        tr = tr.select('e', 'd'). \
            by(IndexType.EP_TAKEN_AT). \
            by(__.value_map('libpath', 'cut'))
        res = tr.to_list()
        return [
            [r['d']['libpath'][0], r['e'], r['d']['cut'][0]]
            for r in reversed(res)
        ]

    def _get_deductive_nbrs_internal(self, libpaths, major0):
        return among_lps(libpaths, self.g.V()).union(
            covers(major0, __.out_e(IndexType.IMPLIES)).in_v(),
            covers(major0, __.in_e(IndexType.IMPLIES)).out_v(),
        ).values('libpath').to_set()

    def _get_deduction_closure_internal(self, libpaths, major0):
        # Note: As noted earlier in this module, a `repeat()` that only follows
        # outgoing UNDER edges has no need of a `limit(1)`, since there can be
        # no branching on such paths.
        res = among_lps(libpaths, self.g.V()).as_('u') \
            .repeat(
                covers(major0, __.out_e(IndexType.UNDER)).in_v()
            ).until(__.has_label(IndexType.DEDUC)).as_('d') \
            .select('u', 'd').by('libpath').to_list()
        return {r['u']: r['d'] for r in res}

    def is_deduc(self, libpath, major):
        return self._is_type(libpath, major, IndexType.DEDUC)

    def is_anno(self, libpath, major):
        return self._is_type(libpath, major, IndexType.ANNO)

    def _is_type(self, libpath, major, index_type):
        major0 = self.adaptall(major)
        c = lp_covers(libpath, major0, self.g.V()) \
            .has_label(index_type).count().next()
        return c > 0

    def get_results_relied_upon_by(self, deducpath, major, realm=None):
        major0 = self.adaptall(major)
        if realm is None:
            realm = '.'.join(deducpath.split('.')[:3])
        realmbase = realm + '.'
        return lp_covers(deducpath, major0, self.g.V()) \
            .repeat(
                covers(major0, __.in_e(IndexType.EXPANDS)) \
                    .out_v().has('modpath', TextP.starting_with(realmbase))
            ).emit() \
            .repeat(
                covers(
                    major0,
                    covers(major0, __.in_e(IndexType.UNDER)) \
                        .out_v().has_label(IndexType.GHOST) \
                        .out_e(IndexType.GHOSTOF)
                ).in_v().has_label(IndexType.DEDUC)
            ).emit().values('libpath').to_set()

    def get_results_relying_upon(self, deducpath, major, realm=None):
        major0 = self.adaptall(major)
        if realm is None:
            realm = '.'.join(deducpath.split('.')[:3])
        realmbase = realm + '.'
        # Note: As noted earlier in this module, a `repeat()` that only follows
        # outgoing UNDER edges has no need of a `limit(1)`, since there can be
        # no branching on such paths.
        return covers(
            major0,
            lp_covers(deducpath, major0, self.g.V()).in_e(IndexType.GHOSTOF)
        ).out_v().has('modpath', TextP.starting_with(realmbase)) \
            .repeat(
                covers(major0, __.out_e(IndexType.UNDER)).in_v()
            ).until(__.has_label(IndexType.DEDUC)) \
            .repeat(
                covers(major0, __.out_e(IndexType.EXPANDS)).in_v()
            ).emit().values('libpath').to_set()

    def _load_user(self, username):
        tr = is_user(username, self.g.V()).values('properties')
        return tr.next() if tr.has_next() else None

    def load_user_notes(self, username, goal_infos):
        tr = is_user(username, self.g.V())

        if goal_infos is None:
            tr = tr.out_e(IndexType.NOTES).as_('h').in_v().as_('g')
        else:
            tr = tr.as_('u').union(*[
                __.V().has('libpath', g[0]).has('major', self.adaptall(g[1])).as_('g')
                for g in goal_infos
            ]).in_e(IndexType.NOTES).where(
                __.out_v().as_('u')
            ).as_('h')

        infos = tr.select('g', 'h') \
            .by(__.value_map('libpath', 'major').by(__.unfold())) \
            .by(__.value_map('state', 'notes').by(__.unfold())) \
            .to_list()
        notes = []
        for info in infos:
            g, h = info['g'], info['h']
            notes.append(UserNotes(g['libpath'], g['major'], h['state'], h['notes']))
        return notes

    def load_user_notes_on_deduc(self, username, deducpath, major):
        major0 = self.adaptall(major)

        tr = is_user(username, self.g.V()).as_('u')
        tr = lp_covers(deducpath, major0, tr.V())

        # Consider anything at or under the deduc:
        tr = tr.union(
            __.identity().as_('g'),
            __.repeat(covers(major0, __.in_e(IndexType.UNDER)).out_v()).emit().as_('g')
        )

        return self._extract_goal_infos_and_load_user_notes(username, tr)

    def load_user_notes_on_anno(self, username, annopath, major):
        major0 = self.adaptall(major)

        tr = is_user(username, self.g.V()).as_('u')
        tr = lp_covers(annopath, major0, tr.V())

        # Consider anything under the anno, having a "widget type" property
        # equal to "GOAL":
        tr = tr.repeat(covers(major0, __.in_e(IndexType.UNDER)).out_v()).emit() \
                .has(IndexType.EP_WTYPE, "GOAL").as_('g')

        return self._extract_goal_infos_and_load_user_notes(username, tr)

    def load_user_notes_on_module(self, username, modpath, major):
        major0 = self.adaptall(major)

        tr = is_user(username, self.g.V()).as_('u')
        tr = covers(major0, tr.V().has('modpath', modpath))

        # Consider anything with the right modpath and major, which is a deduc,
        # or node, or goal widget.
        tr = tr.or_(
            __.has_label(IndexType.DEDUC, IndexType.NODE),
            __.has(IndexType.EP_WTYPE, "GOAL")
        ).as_('g')

        return self._extract_goal_infos_and_load_user_notes(username, tr)

    def _extract_goal_infos_and_load_user_notes(self, username, tr):

        infos = tr.coalesce(
            __.has('origin'),
            # Note: Here we are using pattern matching using a `where()` step.
            #  https://kelvinlawrence.net/book/Gremlin-Graph-Guide.html#patternwhere
            # This means the `as_()` step inside the `where()` does not assign a
            # label, but instead requires the object to equal the one that previously
            # received that label, outside of the `where()` step.
            __.in_e(IndexType.NOTES).where(
                __.out_v().as_('u')
            )
        ).as_('h').select('g', 'h') \
            .by(__.value_map('libpath', 'major').by(__.unfold())) \
            .by(__.value_map('origin', 'state', 'notes').by(__.unfold())) \
            .to_list()

        notes = []
        goal_infos = []
        for info in infos:
            if 'origin' in info['h']:
                goal_info = info['h']['origin'].split("@")
                goal_infos.append(goal_info)
            else:
                g, h = info['g'], info['h']
                notes.append(UserNotes(g['libpath'], g['major'], h['state'], h['notes']))

        notes.extend(self.load_user_notes(username, goal_infos))

        return notes

    # ----------------------------------------------------------------------

    def has_manifest(self, libpath, version):
        tr = self.g.V().has_label(IndexType.VERSION) \
            .has('repopath', libpath).has('version', version) \
            .values('manifest')
        return tr.has_next()

    def load_manifest(self, libpath, version):
        tr = self.g.V().has_label(IndexType.VERSION) \
            .has('repopath', libpath).has('version', version) \
            .values('manifest')
        # As opposed to the corresponding Cypher query, if the Version node
        # exists but does not yet have a `manifest` property, then `has_next()`
        # will simply be False. So the test here is simple.
        if not tr.has_next():
            raise FileNotFoundError
        return tr.next()

    def dashgraph_is_built(self, libpath, version):
        return self._object_is_built(libpath, version)

    def load_dashgraph(self, libpath, version):
        major0 = self.adaptall(version)
        tr = lp_covers(libpath, major0, self.g.V()) \
            .out_e(IndexType.BUILD) \
            .has(IndexType.P_BUILD_VERS, version) \
            .in_v().values('json')
        if not tr.has_next():
            raise FileNotFoundError
        return tr.next()

    def annotation_is_built(self, libpath, version):
        return self._object_is_built(libpath, version)

    def _load_annotation(self, libpath, version, fields):
        major0 = self.adaptall(version)
        tr = lp_covers(libpath, major0, self.g.V()) \
            .out_e(IndexType.BUILD) \
            .has(IndexType.P_BUILD_VERS, version) \
            .in_v().value_map(*fields) \
            .by(__.unfold())
        if not tr.has_next():
            raise FileNotFoundError
        d = tr.next()
        return tuple(d.get(f) for f in ['html', 'json'])

    def module_is_built(self, libpath, version):
        return self._object_is_built(libpath, version)

    def load_module_src(self, libpath, version):
        major0 = self.adaptall(version)
        tr = lp_covers(libpath, major0, self.g.V()) \
            .out_e(IndexType.BUILD) \
            .has(IndexType.P_BUILD_VERS, version) \
            .in_v().values('pfsc')
        if not tr.has_next():
            raise FileNotFoundError
        return tr.next()

    def _object_is_built(self, libpath, version):
        major0 = self.adaptall(version)
        tr = lp_covers(libpath, major0, self.g.V()) \
            .out_e(IndexType.BUILD) \
            .has(IndexType.P_BUILD_VERS, version)
        return tr.has_next()

    # ----------------------------------------------------------------------

    def check_approvals_under_anno(self, annopath, version):
        major0 = self.adaptall(version)
        # Note: Here our goal is to find *all* widgets under a given annotation,
        # so we do *not* want a `limit(1)` on this `repeat()`.
        elt_maps = covers(
            major0,
            lp_covers(
                annopath, major0, self.g.V()
            ).repeat(__.in_(IndexType.UNDER))
             .until(__.has_label(IndexType.WIDGET))
        ).element_map('libpath', IndexType.P_APPROVALS).to_list()
        approved = []
        for elt_map in elt_maps:
            j = elt_map.get(IndexType.P_APPROVALS)
            if j is not None:
                approvals = json.loads(j)
                if approvals.get(version, False):
                    libpath = elt_map['libpath']
                    approved.append(libpath)
        return approved

    def _load_approvals_dict_json(self, widgetpath, version):
        major0 = self.adaptall(version)
        tr = lp_covers(
            widgetpath, major0, self.g.V().has_label(IndexType.WIDGET)
        ).values(IndexType.P_APPROVALS)
        return tr.next() if tr.has_next() else None

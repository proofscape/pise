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

import json

from pfsc.constants import IndexType, WIP_TAG
from pfsc.gdb.k import make_kNode_from_jNode, make_kReln_from_jReln
from pfsc.gdb.reader import GraphReader
from pfsc.gdb.cypher.rg import check_count, get_node_label, RedisGraphWrapper
from pfsc.gdb.user import UserNotes


class CypherGraphReader(GraphReader):

    def __init__(self, gdb):
        super().__init__(gdb)
        self.session = self.gdb.session()
        # TODO: Maybe the gdb teardown needs to close the session?

    # FIXME:
    #  Maybe instead of using this method, all special functionality can be
    #  moved to the `RedisGraphReader` subclass?
    def using_rg(self):
        return isinstance(self.gdb, RedisGraphWrapper)

    def num_nodes_in_db(self):
        res = self.session.run("MATCH (v) RETURN count(v)")
        return check_count(res)

    def num_edges_in_db(self):
        res = self.session.run("MATCH ()-[e]-() RETURN count(e)")
        return check_count(res)

    def all_nodes_under_repo(self, repopath):
        res = self.session.run("""
            MATCH (u {repopath: $repopath}) RETURN u
        """, repopath=repopath)
        j_nodes = [rec.value() for rec in res]
        return [make_kNode_from_jNode(j) for j in j_nodes]

    def all_relns_under_repo(self, repopath):
        res = self.session.run("""
            MATCH (u)-[r {repopath: $repopath}]->(v) RETURN u, r, v
        """, repopath=repopath)
        j_relns = [rec for rec in res]
        return [make_kReln_from_jReln(j) for j in j_relns]

    def get_versions_indexed(self, repopath, include_wip=False):
        # As of v2.4.7, RG does not support the `properties()` function, so
        # with RG we return full nodes, and grab their properties manually.
        rg = self.using_rg()
        res = self.session.run(
            f"""
            MATCH (v:{IndexType.VERSION} {{repopath: $repopath}})
            WITH v
            ORDER BY v.full
            RETURN {'v' if rg else 'properties(v)'}
            """, repopath=repopath
        )
        infos = [record[0] for record in res]
        if rg:
            infos = [node.properties for node in infos]
        if infos and (not include_wip) and infos[-1]['major'] == WIP_TAG:
            infos = infos[:-1]
        return infos

    def version_is_already_indexed(self, repopath, version):
        res = self.session.run(
            f"""
            MATCH (v:{IndexType.VERSION} {{repopath: $repopath, version: $version}})
            RETURN count(v)
            """, repopath=repopath, version=version
        )
        n = check_count(res)
        assert n < 2
        return n == 1

    def find_move_conjugate(self, libpath, major):
        major = self.adaptall(major)
        res = self.session.run(
            f"""
                MATCH p = (t {{libpath: $libpath}})-[:{IndexType.UNDER}*0..]->(s)-[:{IndexType.MOVE}]->(r)
                WHERE t.major <= $major < t.cut
                WITH length(p) as n, relationships(p)[..-1] as U1, r
                ORDER BY n LIMIT 1
                MATCH p2 = (q)-[:{IndexType.UNDER}*0..]->(r)
                WHERE r.libpath is null OR [e IN relationships(p2) | e.segment] = [e IN U1 | e.segment]
                RETURN q
                """,
            libpath=libpath, major=major
        )
        record = res.single()
        if record is None:
            return None
        j = record.value()
        node_type = get_node_label(j)
        if node_type == IndexType.VOID:
            return IndexType.VOID
        return make_kNode_from_jNode(j)

    def get_existing_objects(self, modpath, major, recursive):
        # Nodes
        res = self.session.run("""
            MATCH (u {modpath: $modpath}) WHERE u.major <= $major < u.cut RETURN u
        """, modpath=modpath, major=major)
        existing_j_nodes = [v[0] for v in res]
        # For a recursive build we also need nodes defined _under_ this module.
        if recursive:
            basepath = modpath + '.'
            res = self.session.run("""
                MATCH (u) WHERE u.modpath STARTS WITH $basepath AND u.major <= $major < u.cut RETURN u
            """, basepath=basepath, major=major)
            existing_j_nodes_under_module = [v[0] for v in res]
            existing_j_nodes += existing_j_nodes_under_module
        # Convert from j-nodes to k-nodes.
        existing_k_nodes = {}
        for j in existing_j_nodes:
            k = make_kNode_from_jNode(j)
            existing_k_nodes[k.uid] = k
        # Relations
        # Due to the way Neo4j works, we have to ask the database to return the
        # endnodes of the relation, not just the relation itself. Otherwise
        # the relation won't know any of the info about the nodes (e.g. libpaths).
        res = self.session.run("""
            MATCH (u)-[r {modpath: $modpath}]->(v) WHERE r.major <= $major < r.cut RETURN u, r, v
        """, modpath=modpath, major=major)
        existing_j_relns = [v for v in res]
        if recursive:
            basepath = modpath + '.'
            res = self.session.run("""
                MATCH (u)-[r]->(v) WHERE r.modpath STARTS WITH $basepath AND r.major <= $major < r.cut RETURN u, r, v
            """, basepath=basepath, major=major)
            existing_j_relns_under_module = [v for v in res]
            existing_j_relns += existing_j_relns_under_module
        # Convert from j-relns to k-relns.
        existing_k_relns = {}
        for j in existing_j_relns:
            k = make_kReln_from_jReln(j)
            # Reject inferred relations.
            if k.reln_type in IndexType.INFERRED_RELNS:
                continue
            existing_k_relns[k.uid] = k
        return existing_k_nodes, existing_k_relns
    
    def _get_origins_internal(self, label, libpaths, major0):
        return self.session.run(
            f"""
            MATCH (u:{label})
            WHERE u.libpath in $libpaths AND u.major <= $major < u.cut
            RETURN u.libpath, u.major, u.origin
            """, libpaths=libpaths, major=major0
        )

    def _find_enrichments_internal(self, deducpath, major0):
        return self.session.run(
            f"""
            MATCH p = (e)-[e_reln:{IndexType.TARGETS}|{IndexType.RETARGETS}|{IndexType.CF}]->(t)-[:{IndexType.UNDER}*0..]->(d:{IndexType.DEDUC} {{libpath: $deducpath}})
            WHERE d.major <= $major < d.cut AND all(r IN relationships(p)[1..] WHERE r.major <= $major < r.cut)
            WITH e, type(e_reln) as e_reln_type, t.libpath as t_lp
            MATCH (v:{IndexType.VERSION}) WHERE v.repopath = e.repopath AND e.major <= v.major < e.cut
            RETURN e, e_reln_type, collect(v.full), t_lp
            """,
            deducpath=deducpath, major=major0
        )

    def get_modpath(self, libpath, major):
        major = self.adaptall(major)
        res = self.session.run(
            f"""
            MATCH (v {{libpath: $libpath}}) WHERE v.major <= $major < v.cut RETURN v.modpath
            """, libpath=libpath, major=major
        )
        record = res.single()
        return None if record is None else record.value()

    def get_ancestor_chain(self, deducpath, major):
        major = self.adaptall(major)
        # Note that we do not need to check the major intervals of the EXPANDS
        # relations. This is because any given j-node can have at most one
        # EXPANDS relation leaving it.
        res = self.session.run(f"""
        MATCH p = (d:{IndexType.DEDUC} {{libpath: $deducpath}})-[:{IndexType.EXPANDS}*1..]->(e:{IndexType.DEDUC})
        WHERE d.major <= $major < d.cut
        RETURN e.libpath, relationships(p)[-1].{IndexType.EP_TAKEN_AT}, e.cut, length(p) AS n
        ORDER BY n DESC
        """, deducpath=deducpath, major=major)
        # Unlike NJ, RG seems to need values to be RETURNED in order to be able
        # to work properly with them in a subsequent ORDER BY clause. If you do not
        # include `p` or `length(p)` in the RETURN, then RG can't do the ORDER BY
        # at all. If you include `p` in the RETURN, and then try  `ORDER BY length(p)`,
        # it does not reliably sort according to length. (Seems to be a bug.)
        # So we return `length(p)`, and then sort by that. But then we need to
        # slice this off the data we return, since our caller doesn't want it.
        chain = [list(v)[:-1] for v in res]
        return chain

    def _get_deductive_nbrs_internal(self, libpaths, major0):
        res = self.session.run(f"""
        MATCH (u)-[r:{IndexType.IMPLIES}]-(c)
        WHERE c.libpath in $libpaths AND r.major <= $major < r.cut
        RETURN u.libpath
        """, libpaths=libpaths, major=major0)
        return {v[0] for v in res}

    def _get_deduction_closure_internal(self, libpaths, major0):
        # Note: we match no label on node (u) in the query below, since we want
        # to catch anything under a deduc, including j-nodes of label `Ghost` and
        # even `Special`, along with (of course) `Node`.
        res = self.session.run(f"""
        MATCH p = (u)-[:{IndexType.UNDER}*1..]->(D:{IndexType.DEDUC})
        WHERE u.libpath in $libpaths AND all(r IN relationships(p) WHERE r.major <= $major < r.cut)
        RETURN u.libpath, D.libpath
        """, libpaths=list(libpaths), major=major0)
        return {v[0]: v[1] for v in res}

    def is_deduc(self, libpath, major):
        major = self.adaptall(major)
        res = self.session.run(f"""
        MATCH (d:{IndexType.DEDUC} {{libpath: $libpath}})
        WHERE d.major <= $major < d.cut
        RETURN count(*)
        """, libpath=libpath, major=major)
        c = check_count(res)
        return c > 0

    def is_anno(self, libpath, major):
        major = self.adaptall(major)
        res = self.session.run(f"""
        MATCH (a:{IndexType.ANNO} {{libpath: $libpath}})
        WHERE a.major <= $major < a.cut
        RETURN count(*)
        """, libpath=libpath, major=major)
        c = check_count(res)
        return c > 0

    def get_results_relied_upon_by(self, deducpath, major, realm=None):
        major = self.adaptall(major)
        if realm is None:
            realm = '.'.join(deducpath.split('.')[:3])
        # Since all var-length paths have length at least 1, we don't need to
        # check major interval for any nodes; relns are enough.
        res = self.session.run(f"""
        MATCH p = (:{IndexType.DEDUC} {{libpath: $deducpath}}) <-[:{IndexType.EXPANDS}*1..]- (E:{IndexType.DEDUC})
            <-[:{IndexType.UNDER}*1..]- (:{IndexType.GHOST}) -[:{IndexType.GHOSTOF}]-> (D:{IndexType.DEDUC})
        WHERE E.modpath STARTS WITH $realmbase AND all(r IN relationships(p) WHERE r.major <= $major < r.cut)
        RETURN D.libpath
        """, deducpath=deducpath, major=major, realmbase=realm + '.')
        return [v[0] for v in res]

    def get_results_relying_upon(self, deducpath, major, realm=None):
        major = self.adaptall(major)
        if realm is None:
            realm = '.'.join(deducpath.split('.')[:3])
        # Since all var-length paths have length at least 1, we don't need to
        # check major interval for any nodes; relns are enough.
        res = self.session.run(f"""
        MATCH p = (D:{IndexType.DEDUC}) <-[:{IndexType.EXPANDS}*1..]- (:{IndexType.DEDUC})
            <-[:{IndexType.UNDER}*1..]- (g:{IndexType.GHOST}) -[:{IndexType.GHOSTOF}]-> (:{IndexType.DEDUC} {{libpath: $deducpath}})
        WHERE g.modpath STARTS WITH $realmbase AND all(r IN relationships(p) WHERE r.major <= $major < r.cut)
        RETURN D.libpath
        """, deducpath=deducpath, major=major, realmbase=realm + '.')
        return [v[0] for v in res]

    def _load_user(self, username):
        res = self.session.run(f"""
        MATCH (u:{IndexType.USER} {{username: $username}}) RETURN u.properties
        """, username=username)
        record = res.single()
        return None if record is None else record.value()

    def load_user_notes(self, username, goal_infos):
        if goal_infos is None:
            res = self.session.run(f"""
            MATCH (u:{IndexType.USER} {{username: $username}})-[e:{IndexType.NOTES}]->(g)
            RETURN g.libpath, g.major, e.state, e.notes
            """, username=username)
        else:
            goal_infos = [[g[0], self.adaptall(g[1])] for g in goal_infos]
            res = self.session.run(f"""
            UNWIND $goal_infos AS goal
            MATCH (u:{IndexType.USER} {{username: $username}})-[e:{IndexType.NOTES}]->(g)
            WHERE g.libpath = goal[0] AND g.major = goal[1]
            RETURN goal[0], goal[1], e.state, e.notes
            """, goal_infos=goal_infos, username=username)
        return [UserNotes(r[0], r[1], r[2], r[3]) for r in res]

    def load_user_notes_on_deduc(self, username, deducpath, major):
        major0 = self.adaptall(major)
        res = self.session.run(f"""
        MATCH p = (u:{IndexType.USER} {{username: $username}})-[n:{IndexType.NOTES}]->(g)-[:{IndexType.UNDER}*0..]->(d:{IndexType.DEDUC} {{libpath: $deducpath}})
        WHERE d.major <= $major < d.cut AND all(r IN relationships(p)[1..] WHERE r.major <= $major < r.cut)
        AND NOT exists(g.origin)
        RETURN g.libpath, g.major, n.state, n.notes
        """, username=username, deducpath=deducpath, major=major0)
        notes = [UserNotes(r[0], r[1], r[2], r[3]) for r in res]
        res = self.session.run(f"""
        MATCH p = (g)-[:{IndexType.UNDER}*0..]->(d:{IndexType.DEDUC} {{libpath: $deducpath}})
        WHERE d.major <= $major < d.cut AND all(r IN relationships(p) WHERE r.major <= $major < r.cut)
        AND exists(g.origin)
        RETURN g.origin
        """, deducpath=deducpath, major=major0)
        goal_infos = [r[0].split("@") for r in res]
        notes.extend(self.load_user_notes(username, goal_infos))
        return notes

    def load_user_notes_on_anno(self, username, annopath, major):
        major0 = self.adaptall(major)
        res = self.session.run(f"""
        MATCH p = (u:{IndexType.USER} {{username: $username}})-[n:{IndexType.NOTES}]->
            (g:{IndexType.WIDGET} {{{IndexType.EP_WTYPE}: "GOAL"}})-[:{IndexType.UNDER}*1..]->(a:{IndexType.ANNO} {{libpath: $annopath}})
        WHERE a.major <= $major < a.cut AND all(r IN relationships(p)[1..] WHERE r.major <= $major < r.cut)
        AND NOT exists(g.origin)
        RETURN g.libpath, g.major, n.state, n.notes
        """, username=username, annopath=annopath, major=major0)
        notes = [UserNotes(r[0], r[1], r[2], r[3]) for r in res]
        res = self.session.run(f"""
        MATCH p = (g:{IndexType.WIDGET} {{{IndexType.EP_WTYPE}: "GOAL"}})-[:{IndexType.UNDER}*1..]->(a:{IndexType.ANNO} {{libpath: $annopath}})
        WHERE a.major <= $major < a.cut AND all(r IN relationships(p) WHERE r.major <= $major < r.cut)
        AND exists(g.origin)
        RETURN g.origin
        """, annopath=annopath, major=major0)
        goal_infos = [r[0].split("@") for r in res]
        notes.extend(self.load_user_notes(username, goal_infos))
        return notes

    def load_user_notes_on_module(self, username, modpath, major):
        major0 = self.adaptall(major)
        res = self.session.run(f"""
        MATCH (u:{IndexType.USER} {{username: $username}})-[n:{IndexType.NOTES}]->(g {{modpath: $modpath}})
        WHERE g.major <= $major < g.cut
        AND (g:{IndexType.DEDUC} OR g:{IndexType.NODE} OR g.{IndexType.EP_WTYPE} = "GOAL")
        AND NOT exists(g.origin)
        RETURN g.libpath, g.major, n.state, n.notes
        """, username=username, modpath=modpath, major=major0)
        notes = [UserNotes(r[0], r[1], r[2], r[3]) for r in res]
        res = self.session.run(f"""
        MATCH (g {{modpath: $modpath}})
        WHERE g.major <= $major < g.cut
        AND (g:{IndexType.DEDUC} OR g:{IndexType.NODE} OR g.{IndexType.EP_WTYPE} = "GOAL")
        AND exists(g.origin)
        RETURN g.origin
        """, modpath=modpath, major=major0)
        goal_infos = [r[0].split("@") for r in res]
        notes.extend(self.load_user_notes(username, goal_infos))
        return notes

    # ----------------------------------------------------------------------

    def has_manifest(self, libpath, version):
        res = self.session.run(f"""
        MATCH (v:{IndexType.VERSION} {{repopath: $repopath, version: $version}})
        WHERE exists(v.manifest)
        RETURN count(v)
        """, repopath=libpath, version=version)
        n = check_count(res)
        assert n < 2
        return n == 1

    def load_manifest(self, libpath, version):
        res = self.session.run(f"""
        MATCH (v:{IndexType.VERSION} {{repopath: $repopath, version: $version}})
        RETURN v.manifest
        """, repopath=libpath, version=version)
        rec = res.single()
        if rec is None:
            raise FileNotFoundError
        m = rec.value()
        # Unlike the build nodes for modules, annos, and deducs, a Version node
        # can exist but not yet have a `manifest` property. So we have to check
        # to see if that happened:
        if m is None:
            raise FileNotFoundError
        return m

    def dashgraph_is_built(self, libpath, version):
        return self._object_is_built(libpath, version, IndexType.DEDUC)

    def load_dashgraph(self, libpath, version):
        major0 = self.adaptall(version)
        res = self.session.run(f"""
        MATCH (u:{IndexType.DEDUC} {{libpath: $libpath}})-[b:{IndexType.BUILD}]->(t)
        WHERE u.major <= $major < u.cut
        AND b.{IndexType.P_BUILD_VERS} = $version
        RETURN t.json
        """, libpath=libpath, version=version, major=major0)
        rec = res.single()
        if rec is None:
            raise FileNotFoundError
        return rec.value()

    def annotation_is_built(self, libpath, version):
        return self._object_is_built(libpath, version, IndexType.ANNO)

    def _load_annotation(self, libpath, version, fields):
        major0 = self.adaptall(version)
        res = self.session.run(f"""
        MATCH (u:{IndexType.ANNO} {{libpath: $libpath}})-[b:{IndexType.BUILD}]->(t)
        WHERE u.major <= $major < u.cut
        AND b.{IndexType.P_BUILD_VERS} = $version
        RETURN {', '.join(['t.%s' % f for f in fields])}
        """, libpath=libpath, version=version, major=major0)
        rec = res.single()
        if rec is None:
            raise FileNotFoundError
        if len(fields) == 2:
            return rec.values()
        elif fields[0] == 'html':
            return rec.value(), None
        else:
            return None, rec.value()

    def module_is_built(self, libpath, version):
        return self._object_is_built(libpath, version, IndexType.MODULE)

    def load_module_src(self, libpath, version):
        major0 = self.adaptall(version)
        res = self.session.run(f"""
        MATCH (u:{IndexType.MODULE} {{libpath: $libpath}})-[b:{IndexType.BUILD}]->(t)
        WHERE u.major <= $major < u.cut
        AND b.{IndexType.P_BUILD_VERS} = $version
        RETURN t.pfsc
        """, libpath=libpath, version=version, major=major0)
        rec = res.single()
        if rec is None:
            raise FileNotFoundError
        return rec.value()

    def _object_is_built(self, libpath, version, node_type):
        major0 = self.adaptall(version)
        res = self.session.run(f"""
        MATCH (u:{node_type} {{libpath: $libpath}})-[b:{IndexType.BUILD}]->(t)
        WHERE u.major <= $major < u.cut
        AND b.{IndexType.P_BUILD_VERS} = $version
        RETURN count(b)
        """, libpath=libpath, version=version, major=major0)
        n = check_count(res)
        assert n < 2
        return n == 1

    # ----------------------------------------------------------------------

    def check_approvals_under_anno(self, annopath, version):
        major0 = self.adaptall(version)
        basepath = annopath + '.'
        res = self.session.run(f"""
        MATCH (w:{IndexType.WIDGET}) WHERE w.major <= $major < w.cut
        AND w.libpath STARTS WITH $basepath
        RETURN w.libpath, w.{IndexType.P_APPROVALS}
        """, basepath=basepath, major=major0)
        approved = []
        for libpath, j in res:
            if j is not None:
                approvals = json.loads(j)
                if approvals.get(version, False):
                    approved.append(libpath)
        return approved

    def _load_approvals_dict_json(self, widgetpath, version):
        major0 = self.adaptall(version)
        res = self.session.run(f"""
        MATCH (w:{IndexType.WIDGET} {{libpath: $widgetpath}})
        WHERE w.major <= $major < w.cut
        RETURN w.{IndexType.P_APPROVALS}
        """, widgetpath=widgetpath, major=major0)
        record = res.single()
        return None if record is None else record.value()


# ----------------------------------------------------------------------------

class RedisGraphReader(CypherGraphReader):
    """
    Accommodates differences or limitations of RedisGraph.
    Currently (RedisGraph 2.4.13, redisgraph-py 2.4.2):

    * No support for "has label" query

    """

    def load_user_notes_on_module(self, username, modpath, major):
        """
        The difference between this method and that of the superclass is that
        we simply omit the "has label" parts of the queries. Those were only
        meant to filter out nodes that are not goals (are not Deduc, Node, or
        Widget with wtype = GOAL). The query still works without the filtering;
        we just waste time checking to see if the user has any notes on the
        nodes we couldn't filter out.
        """
        major0 = self.adaptall(major)
        res = self.session.run(f"""
        MATCH (u:{IndexType.USER} {{username: $username}})-[n:{IndexType.NOTES}]->(g {{modpath: $modpath}})
        WHERE g.major <= $major < g.cut
        AND NOT exists(g.origin)
        RETURN g.libpath, g.major, n.state, n.notes
        """, username=username, modpath=modpath, major=major0)
        notes = [UserNotes(r[0], r[1], r[2], r[3]) for r in res]
        res = self.session.run(f"""
        MATCH (g {{modpath: $modpath}})
        WHERE g.major <= $major < g.cut
        AND exists(g.origin)
        RETURN g.origin
        """, modpath=modpath, major=major0)
        goal_infos = [r[0].split("@") for r in res]
        notes.extend(self.load_user_notes(username, goal_infos))
        return notes

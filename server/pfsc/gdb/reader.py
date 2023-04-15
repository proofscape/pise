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

from collections import deque, defaultdict
import json

from pfsc import check_config
from pfsc.build.repo import get_repo_info
from pfsc.build.versions import (
    collapse_major_string, collapse_padded_full_version,
    adapt_gen_version_to_major_index_prop)
from pfsc.constants import WIP_TAG, IndexType
from pfsc.excep import PfscExcep, PECode
from pfsc.gdb.k import make_kNode_from_jNode, kNode
from pfsc.gdb.user import User
from pfsc.gdb.util import SimpleGraph
from pfsc.lang.theorygraph import TheoryNode, TheoryEdge, TheoryGraph
from pfsc.permissions import have_repo_permission, ActionType


class GraphReader:
    """Abstract base class for graph database readers. """

    def __init__(self, gdb):
        self.gdb = gdb

    @staticmethod
    def adaptall(version):
        return adapt_gen_version_to_major_index_prop(version)

    def num_nodes_in_db(self):
        """
        Get the total number of nodes in the database.
        Mostly useful for testing.

        @return: int
        """
        raise NotImplementedError

    def num_edges_in_db(self):
        """
        Get the total number of edges in the database.
        Mostly useful for testing.

        @return: int
        """
        raise NotImplementedError

    def everything_under_repo(self, repopath):
        k_nodes = self.all_nodes_under_repo(repopath)
        k_relns = self.all_relns_under_repo(repopath)
        index_info = self.get_versions_indexed(repopath, include_wip=True)
        return SimpleGraph(k_nodes, k_relns, index_info=index_info)

    def all_nodes_under_repo(self, repopath):
        raise NotImplementedError

    def all_relns_under_repo(self, repopath):
        raise NotImplementedError

    def get_versions_indexed(self, repopath, include_wip=False):
        """
        Say which versions of a given repo have so far been indexed.

        :param repopath: the libpath of a repo.
        :param include_wip: if True, and if the repo has been indexed at WIP,
            then the WIP version will be included at the end of the list.
        :return: list of property dicts for those versions of the repo that
            have so far been indexed, listed in order of increasing version.
            For the list of properties in each dict, see
            `ModuleIndexInfo.write_version_node_props()`.
        """
        raise NotImplementedError

    def version_is_already_indexed(self, repopath, version):
        """
        Say whether a repo has already been indexed at a given version.

        :param repopath: the libpath of a repo.
        :param version: a version tag of the form `vM.m.p`
        :return: boolean saying whether this repo at this version has
          already been indexed.
        """
        raise NotImplementedError

    def find_move_conjugate(self, libpath, major):
        """
        In our GDB, only those MOVE relations are formed that correspond to
        mappings explicitly noted in a change log. Therefore most movements
        are implicit, and must be computed, essentially as an algebraic
        conjugate, of one of the explicit MOVE relations.

                (s) --[:MOVE]--> (s')
                 | UNDER          | UNDER
                ...              ...
                 | UNDER          | UNDER
                (t)              (t')

        In the diagram above, (s) is a node that received an explicit MOVE
        relation, carrying it to a node (s'). A node (t) under (s) did not,
        since it was intended to undergo the corresponding move. To be precise,
        if libpath(s) = a, then, since t is under s, we should have libpath(t) = a.b
        for some b. If libpath(s') = a', then the implication is that t moved
        to a node t' with libpath(t') = a'.b.

        In this situation, we say that t' is the "move-conjugate" of t.
        This is because t' is obtained from t by conjugating the nearest MOVE
        relation by the chain of UNDER relations that separates it from t.

        Meanwhile there are always two other possibilities. One is that t did
        not move but "died". This is the case when the nearest MOVE relation
        to t points to the (:Void) node:

                (s) --[:MOVE]--> (:Void)
                 | UNDER
                ...
                 | UNDER
                (t)

        The final possibility is that t neither moved nor died. This is the
        case when there is no MOVE relation leaving t or any of t's ancestors.

        :param libpath: the libpath of the node whose move-conjugate is to
          be computed (t in the discussion above).
        :param major: the major version of the node whose move-conjugate is
          to be computed. We accept anything accepted by `adaptall`.
        :return: kNode, str, None
            If node t moved, return a kNode representing its move-conjugate.
            If t died, return the string constant `IndexType.VOID`.
            If t neither moved nor died, return None.
            WARNING: We also return None if t simply isn't found in the index.
        """
        raise NotImplementedError

    def find_move_conjugate_chain(self, libpath, major):
        """
        Repeatedly apply `find_move_conjugate`, starting with the given
        libpath, major.

        :param libpath: as for `find_move_conjugate`
        :param major: as for `find_move_conjugate`
        :return: list of move conjugates, but representing only actual moves,
          never Void or None.
        """
        mcs = []
        mc = self.find_move_conjugate(libpath, major)
        while isinstance(mc, kNode):
            # Sanity check: This case should never arise, but if it did it
            # would result in an infinite loop:
            if mc.major <= major:
                msg = f'Found retro move-conjugate `{mc.libpath}@{mc.major}`'
                msg += f' for `{libpath}@{major}`.'
                raise PfscExcep(msg, PECode.RETRO_MOVE_CONJUGATE)
            mcs.append(mc)
            libpath, major = mc.libpath, mc.major
            mc = self.find_move_conjugate(libpath, major)
        return mcs

    def get_existing_objects(self, modpath, major, recursive):
        """
        Get k-representations of all existing j-objects under a given module,
        and covering a given major version.

        :param modpath: the libpath of the module in question.
        :param major: the major version in question.
        :param recursive: boolean saying whether we want all objects under the
            given module _and_ all its submodules.
        :return: pair of dicts `existing_k_nodes, existing_k_relns` mapping
            k-node UIDs to k-nodes, and k-reln UIDs to k-relns.
        """
        # Note that, throughout this function, we must search not for objects _having_
        # the desired major version, but _covering_ the desired major version in their
        # clopen interval. The point is to find the j-objects that serve to represent
        # certain Proofscape entities in certain versions of the repo in question.
        # Those j-objects may have first appeared many versions ago; if they are not
        # _cut_ yet, then they still represent the same entities.
        raise NotImplementedError

    def get_origins(self, libpaths_by_label, major):
        """
        Look up the origins of a collection of nodes.

        :param libpaths_by_label: dict mapping node labels ("types") to
            lists of libpaths to search for under that label.
        :param major: the desired major version.
        :return: dict mapping those libpaths for which a matching j-node is
            found, to the origin of that j-node, in the form `libpath@major`.
        """
        major0 = self.adaptall(major)
        origins = {}
        for label, libpaths in libpaths_by_label.items():
            res = self._get_origins_internal(label, libpaths, major0)
            for libpath, maj, origin in res:
                origins[
                    libpath] = origin or f'{libpath}@{collapse_major_string(maj)}'
        return origins

    def _get_origins_internal(self, label, libpaths, major0):
        raise NotImplementedError

    def get_enrichment(self, deducpath, major, filter_by_repo_permission=True):
        """
        List available enrichment (expansions, annotations, comparisons) for
        any nodes in a given deduction, or for the deduction itself.

        :param deducpath: the libpath of the deduction.
        :param major: the major version of interest for this deduction. We
            accept anything accepted by `adaptall`.
        :param filter_by_repo_permission: if True, we will not report any
            enrichments as available at WIP unless we have permission for the
            repo where they are defined.
        :return: dict of the form:

            {
                targetpath_1: {
                    'Deduc': [info, ..., info],
                    'Anno':  [info, ..., info],
                    'CF':    [info, ..., info],
                },
                ...
                targetpath_m: {
                    'Deduc': [info, ..., info],
                    'Anno':  [info, ..., info],
                    'CF':    [info, ..., info],
                }
            }

        where:
          - Every targetpath either denotes a node defined under deducpath, or
            equals deducpath itself;
          - Enrichments under 'Deduc' are expansions; those under 'Anno' are
            annotations; those under 'CF' are comparisons, i.e. nodes or deducs
            whose 'cf' field points to the target.
          - Each `info` is a dict of properties of an enrichment node, as returned
            by `kNode.get_property_dict()`, PLUS the following additional properties:
              `WIP`: true if this enrichment is available at WIP version, false otherwise.
              `latest`: the latest indexed _numerical_ version of this enrichment,
                or null if there isn't any (meaning it is only available at WIP).
        """
        major0 = self.adaptall(major)
        enrichment = defaultdict(lambda: defaultdict(list))
        show_demo = check_config("SHOW_DEMO_ENRICHMENTS")
        target_is_demo = get_repo_info(deducpath).is_demo()
        res = self._find_enrichments_internal(deducpath, major0)
        for e, e_reln_type, padded_full_versions, t_libpath in res:
            k = make_kNode_from_jNode(e)

            # If config says not to show demo enrichments on non-demo objects, and
            # this is a demo enrichment, then skip this one.
            if not show_demo and not target_is_demo and get_repo_info(
                    k.libpath).is_demo():
                continue

            info = k.get_property_dict()
            versions = [collapse_padded_full_version(pfv) for pfv in
                        sorted(padded_full_versions)]
            n = len(versions)
            assert n > 0
            if versions[-1] == WIP_TAG:
                info[WIP_TAG] = True
                info['latest'] = versions[-2] if n > 1 else None
                if filter_by_repo_permission and not have_repo_permission(
                        ActionType.READ, k.repopath, WIP_TAG):
                    if info['latest'] is None:
                        continue
                    info[WIP_TAG] = False
            else:
                info[WIP_TAG] = False
                info['latest'] = versions[-1]

            e_type = (
                IndexType.CF
                if e_reln_type == IndexType.CF else
                k.node_type
            )

            enrichment[t_libpath][e_type].append(info)

        return enrichment

    def _find_enrichments_internal(self, deducpath, major0):
        raise NotImplementedError

    def get_modpath(self, libpath, major):
        """
        Get the libpath of the lowest module in which a given libpath is
        found, at a given major version.

        :param libpath: the libpath in question
        :param major: the major version in question; anything accepted by `adaptall`.
        :return: the libpath of the lowest module in which this libpath is
          found, at this major version; or None if we could not match this
          pattern.
        """
        raise NotImplementedError

    def get_ancestor_chain(self, deducpath, major):
        """
        Suppose, for a given major version of a deduction d, the chain of ancestors
        of d is z < y < x < ... < e < d, with z being a TLD or "root" deduction (i.e.
        it has no parent). Then this function returns the list, [
            [ libpath(z), taken_at, cut ],
            [ libpath(y), taken_at, cut ],
            [ libpath(x), taken_at, cut ],
            ...,
            [ libpath(e), taken_at, cut ]
        ]
        where, in each triple, you get the libpath of a deduction, the (full) version
        at which its child takes it, and the (padded) major version (possibly `"inf"`)
        at which its j-node is cut.

        This means the child deduc should be able to take the parent at any version
        that is both >= `taken_at`, and strictly < `cut`; in other words, any version
        of the parent deduc's repo from the time the expansion was written, to the
        time (if any) at which a breaking change was made that affected the parent deduc.
        """
        raise NotImplementedError

    def get_deductive_nbrs(self, libpaths_by_major):
        """
        Find all nodes one IMPLIES edge away from the given ones, in either direction.

        Note: we do not filter out nodes that are already in the given set.
        Thus, for example, if A -> B -> C -> D and you pass the set {B, C},
        you will get the set {A, B, C, D} as return value.

        :param libpaths_by_major: dict in which major version numbers map to
          iterables of libpaths of nodes and/or deducs that are desired at that version.
        :return: set of libpaths of nodes one IMPLIES edge away from anything in
            the given set, where the edges must be valid at the corresponding versions.
        """
        nbrs = set()
        for major, libpaths in libpaths_by_major.items():
            major0 = self.adaptall(major)
            s = self._get_deductive_nbrs_internal(libpaths, major0)
            nbrs.update(s)
        return nbrs

    def _get_deductive_nbrs_internal(self, libpaths, major0):
        raise NotImplementedError

    def get_deduction_closure(self, libpaths_by_major):
        """
        Given the libpaths of deducs and/or nodes, compute the "deduction closure"
        thereof. This is the smallest set of deductions that contains all the items named.

        :param libpaths_by_major: dict mapping major version numbers to iterables of
          libpaths of deducs and/or nodes that are to be examined at that version.
        :return: set of libpaths of the deduction closure thereof.

        Note: In its current implementation, all this function actually does is replace
        those libpaths that do point to nodes by the libpaths of the deducs to which
        those nodes belong. Therefore it is very much a "garbage in, garbage out" situation.
        Buyer beware.
        """
        closure = set()
        for major, libpaths in libpaths_by_major.items():
            major0 = self.adaptall(major)
            node2deduc = self._get_deduction_closure_internal(libpaths, major0)
            closure.update({node2deduc.get(lp, lp) for lp in libpaths})
        return closure

    def _get_deduction_closure_internal(self, libpaths, major0):
        raise NotImplementedError

    def is_deduc(self, libpath, major):
        """
        Check whether a libpath points to a deduction, at a given major version.
        :param libpath: the libpath in question
        :param major: the major version in question
        :return: boolean
        """
        raise NotImplementedError

    def is_anno(self, libpath, major):
        """
        Check whether a libpath points to an annotation, at a given major version.
        :param libpath: the libpath in question
        :param major: the major version in question
        :return: boolean
        """
        raise NotImplementedError

    # ----------------------------------------------------------------------
    # The following methods are concerned with computing theory graphs.
    #
    # NOTE:
    # All these functions use a `realm` argument, which limits the scope of the graph.
    # They also accept a `major` version number.
    # For now we assume the realm contains only one repo -- and it is to that
    # that the given major version number applies. In future we may wish to generalize,
    # accepting a full dependencies lookup from repopaths to major versions.

    def get_results_relied_upon_by(self, deducpath, major, realm=None):
        """
        Essentially this function answers the question, "Which theorems did we use in order to prove this one?"

        :param deducpath: the libpath of the deduction for which you want to know the supporting results.
        :param major: the desired major version. (See NOTE above.)
        :param realm: a libpath under which supporting results are required to live. If undefined, we will
          use the repopath for the deduction in question. The idea is to filter out extraneous expansions,
          and note only the results belonging to a given theoretical development.
        :return: list of libpaths of deducs cited in the proof(s) of the given one.
        """
        raise NotImplementedError

    def get_results_relying_upon(self, deducpath, major, realm=None):
        """
        This is the companion method to `get_results_relied_upon_by`. This time, we're looking upward
        in the theory, and asking which results rely on this one.

        :param deducpath: the libpath of the deduction for which you want to know the results that rely on it.
        :param major: the desired major version. (See NOTE above.)
        :param realm: same idea as in `get_results_relied_upon_by`. We will only return deducs defined under this libpath.
        :return: list of libpaths of deducs in whose proof(s) the given one is cited.
        """
        raise NotImplementedError

    def get_lower_theory_graph(self, deducpath, major, realm=None):
        """
        Compute the graph of all results on which a given one relies, recursively.

        :param deducpath: the libpath of the deduction in question.
        :param major: the desired major version. (See NOTE above.)
        :param realm: same as in `get_results_relied_upon_by`; constrains to a given set of deducs.
        :return: a TheoryGraph instance

        Think of directed edges as indicating deduction. I.e. they point from (src) the result
        cited, to (tgt) the result that uses the prior one.

        If you care about order, note that we do breadth-first search. This seems more appropriate
        for a lower graph.

        See also `get_upper_theory_graph`.
        """
        major = self.adaptall(major)
        if realm is None:
            realm = '.'.join(deducpath.split('.')[:3])
        nodes = {deducpath: TheoryNode(deducpath)}
        edges = []
        q = deque(nodes.values())
        while q:
            d = q.popleft()
            cited_libpaths = self.get_results_relied_upon_by(d.label, major,
                                                        realm=realm)
            for lp in cited_libpaths:
                if lp in nodes:
                    c = nodes[lp]
                else:
                    c = TheoryNode(lp)
                    nodes[lp] = c
                    q.append(c)
                edges.append(TheoryEdge(c, d))
        graph = TheoryGraph(nodes.values(), edges)
        return graph

    def get_upper_theory_graph(self, deducpath, major, realm=None):
        """
        Compute the graph of all results which rely on a given one, recursively.

        :param deducpath: the libpath of the deduction in question.
        :param major: the desired major version. (See NOTE above.)
        :param realm: same as in `get_results_relied_upon_by`; constrains to a given set of deducs.
        :return: a TheoryGraph instance

        Think of directed edges as indicating deduction. I.e. they point from (src) the result
        cited, to (tgt) the result that uses the prior one.

        If you care about order, note that we do depth-first search. This seems more appropriate
        for an upper graph.

        See also `get_lower_theory_graph`.
        """
        major = self.adaptall(major)
        if realm is None:
            realm = '.'.join(deducpath.split('.')[:3])
        nodes = {deducpath: TheoryNode(deducpath)}
        edges = []
        q = deque(nodes.values())
        while q:
            d = q.pop()
            libpaths_using = self.get_results_relying_upon(d.label, major,
                                                      realm=realm)
            for lp in libpaths_using:
                if lp in nodes:
                    u = nodes[lp]
                else:
                    u = TheoryNode(lp)
                    nodes[lp] = u
                    q.append(u)
                edges.append(TheoryEdge(d, u))
        graph = TheoryGraph(nodes.values(), edges)
        return graph

    # ----------------------------------------------------------------------

    def load_user(self, username):
        """
        Find the existing user by a given username, or return None.

        @param username: Full proofscape username in the form `host.user`
        @return: User or None
        """
        j_props = self._load_user(username)
        if j_props is None:
            return None
        props = json.loads(j_props)
        return User(username, props)

    def _load_user(self, username):
        raise NotImplementedError

    def load_owner(self, libpath):
        """
        Find the existing user who owns a given libpath, or return None.

        @param libpath: the libpath is question
        @return: User or None
        """
        p = libpath.split('.')
        if len(p) < 2:
            return None
        username = '.'.join(p[:2])
        return self.load_user(username)

    def load_user_notes(self, username, goal_infos):
        """
        Load a user's notes, either on a given set of goals, or else on
        all goals whatsoever.

        @param username: full username of the form 'host.user'
        @param goal_infos: either a list of pairs (libpath, major) giving the
            libpaths and major versions of the goals of interest, or else
            None, indicating that you want to load all the user's notes, on
            all goals whatsoever.
        @return: list of UserNotes objects
        """
        raise NotImplementedError

    def load_user_notes_on_deduc(self, username, deducpath, major):
        """
        Load a user's notes on all goals at or under a given deduction.

        @param username: full username of the form 'host.user'
        @param deducpath: the libpath of the deduction
        @param major: the major version of the deduction
        @return: list of UserNotes objects
        """
        raise NotImplementedError

    def load_user_notes_on_anno(self, username, annopath, major):
        """
        Load a user's notes on all goals under a given annotation.

        @param username: full username of the form 'host.user'
        @param annopath: the libpath of the annotation
        @param major: the major version of the annotation
        @return: list of UserNotes objects
        """
        raise NotImplementedError

    def load_user_notes_on_module(self, username, modpath, major):
        """
        Load a user's notes on all goals under a given module.

        @param username: full username of the form 'host.user'
        @param modpath: the libpath of the module
        @param major: the major version of the module
        @return: list of UserNotes objects
        """
        raise NotImplementedError

    # ----------------------------------------------------------------------

    def has_manifest(self, libpath, version):
        """
        Say whether a given repo at a given version has a built manifest.

        @param libpath: the libpath of the repo
        @param version: the version of the repo
        @return: boolean
        """
        raise NotImplementedError

    def load_manifest(self, libpath, version):
        """
        Load the manifest for a given repo at a given version.

        @param libpath: the libpath of the repo
        @param version: the version of the repo
        @return: JSON string
        """
        raise NotImplementedError

    def dashgraph_is_built(self, libpath, version):
        """
        Say whether the dashgraph for a given deduc has been built at a given
        version.

        @param libpath: the libpath of the deduc
        @param version: the version of the deduc
        @return: boolean
        """
        raise NotImplementedError

    def load_dashgraph(self, libpath, version):
        """
        Load the dashgraph for a given deduc at a given version.

        @param libpath: the libpath of the deduc
        @param version: the version of the deduc
        @return: JSON string
        """
        raise NotImplementedError

    def annotation_is_built(self, libpath, version):
        """
        Say whether the html and json for a given anno have been built at a
        given version.

        @param libpath: the libpath of the deduc
        @param version: the version of the deduc
        @return: boolean
        """
        raise NotImplementedError

    def load_annotation(self, libpath, version, load_html=True, load_json=True):
        """
        Load the html and/or json for a given anno at a given version.

        @param libpath: the libpath of the anno
        @param version: the version of the anno
        @param load_html: boolean, whether to load the html or not
        @param load_json: boolean, whether to load the json or not
        @return: pair (h, j) where h is either an HTML string or None,
            and j is either a JSON string or None, according to what
            was requested.
        """
        fields = []
        if load_html:
            fields.append('html')
        if load_json:
            fields.append('json')
        if not fields:
            return None, None
        return self._load_annotation(libpath, version, fields)

    def _load_annotation(self, libpath, version, fields):
        raise NotImplementedError

    def module_is_built(self, libpath, version):
        """
        Say whether a given module has been built at a given version.

        @param libpath: the libpath of the module
        @param version: the version of the module
        @return: boolean
        """
        raise NotImplementedError

    def load_module_src(self, libpath, version):
        """
        Load the source code for a given module at a given version.

        @param libpath: the libpath of the module
        @param version: the version of the module
        @return: string of pfsc code
        """
        raise NotImplementedError

    # ----------------------------------------------------------------------

    def check_approvals_under_anno(self, annopath, version):
        """
        Check all the approvals for display widgets in a given annotation,
        at a given full version.

        @param annopath: the libpath of the annotation
        @param version: the full version of the annotation
        @return: list of libpaths that have been approved under this annotation
            at this exact full version.
        """
        raise NotImplementedError

    def _load_approvals_dict_json(self, widgetpath, version):
        """
        Load the approvals dictionary JSON for a given widget.

        @param widgetpath: the libpath of the widget.
        @param version: the version of the widget.
        @return: None if no approvals property defined yet for this widget,
            else the current JSON string value.
        """
        raise NotImplementedError

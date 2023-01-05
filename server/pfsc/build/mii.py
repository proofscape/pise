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

from collections import defaultdict
from time import time as unixtime

import pfsc.constants
from pfsc.build.repo import get_repo_info
from pfsc.build.lib.prefix import LibpathPrefixMapping
from pfsc.build.versions import VersionTag, collapse_major_string
from pfsc.checkinput import check_libpath
from pfsc.constants import IndexType
from pfsc.gdb.k import kNode, kReln
from pfsc.excep import PfscExcep, PECode


class ModuleIndexInfo:
    """
    Keeps track of all the necessary info about things defined in
    a module, in order to do indexing.
    """

    def __init__(self, monitor, modpath, version, commit_hash, recursive=False):
        """
        :param monitor: a BuildMonitor, for registering progress
        :param modpath: The libpath of the module that is to be indexed.
        :param version: The version that is being indexed.
        :param commit_hash: The commit hash of the version that is being indexed.
        :param recursive: Says whether the indexing is to be recursive or not.

        Apart from the passed data, we maintain two data structures, a set of nodes
        and a set of relations.
        """
        self.monitor = monitor
        self.modpath = modpath
        self.repo_info = get_repo_info(modpath)
        self.repopath = self.repo_info.libpath
        self.version = version
        self.commit_hash = commit_hash
        self.major, self.minor, self.patch = self.compute_major_minor_patch(version)
        self.recursive = recursive
        self.change_log = {}
        self.exceptional_libpaths = self.prepare_exceptional_libpaths()
        self.node_lookup = {}
        self.reln_lookup = {}
        self.submodules = []
        self.add_kNode(IndexType.MODULE, self.modpath, self.modpath)

        # Slots:
        self.current_maj_vers = None
        self.existing_k_nodes = None
        self.existing_k_relns = None
        self.move_mapping = None
        self.mm_closure = None
        self.M = None
        self.Rbar = None
        self.V_cut = None
        self.E_cut = None
        self.V_add = None
        self.E_add = None
        self.here = None
        self.elsewhere = None
        self.nowhere = None
        self.origins = None

        # TODO:
        #  These weights should be based on empirical observation.
        #  (And even tailored to the specific GDB we're using?)
        #  For now, just guesses.
        self.monitor_task_weights = {
            # one call to writer._drop_wip_nodes_under_module():
            111: 40,
            # call to writer._undo_wip_cut_nodes() PER NODE:
            112: 10,
            # call to writer._undo_wip_cut_relns() PER RELN:
            113: 10,
            # cut one vertex:
            220: 5,
            # cut one edge:
            240: 5,
            # add one vertex:
            260: 10,
            # add one edge:
            280: 20,
            # record one move (should be same as add one edge):
            330: 20,
            # retarget for one new enrichment:
            361: 23,
            # retarget for one existing enrichment:
            362: 23,
        }

    def setup_monitor(self):
        w = self.monitor_task_weights

        # 100
        n100 = 0
        if self.is_WIP():
            n100 += w[111] * len(self.all_modules())
            n100 += w[112] * len(self.existing_k_nodes)
            n100 += w[113] * len(self.existing_k_relns)

        # 200
        n200 = 0
        n200 += w[220] * len(self.V_cut)
        n200 += w[240] * len(self.E_cut)
        n200 += w[260] * len(self.V_add)
        n200 += w[280] * len(self.E_add)

        # 300
        n300 = 0
        n300 += w[330] * len(self.move_mapping)
        n300 += w[361] * len([uid for uid in self.E_add if self.get_kReln(uid).reln_type == IndexType.TARGETS])
        n300 += w[362] * len([b for b in self.mm_closure.values() if b is not None])

        n = n100 + n200 + n300

        self.monitor.begin_phase(n, 'Indexing...')

    def note_begin_indexing_phase(self, phase_code):
        phase_name = {
            110: 'clear previous WIP indexing',
            220: 'cutting vertices',
            240: 'cutting edges',
            260: 'adding vertices',
            280: 'adding edges',
            330: 'recording move mappings',
            360: 'recording retargeting relations',
        }[phase_code]
        message = 'Indexing: %s...' % phase_name
        self.monitor.set_message(message)

    def note_task_element_completed(self, task_code, count=1):
        w = self.monitor_task_weights[task_code]
        n = w * count
        self.monitor.inc_count(n)

    def all_modules(self):
        return [self.modpath] + self.submodules

    def prepare_exceptional_libpaths(self):
        return {
            f'{self.repopath}.{pfsc.constants.CHANGE_LOG_LHS}',
            f'{self.repopath}.{pfsc.constants.DEPENDENCIES_LHS}',
            f'{self.repopath}.{pfsc.constants.VERSION_NUMBER_LHS}',
        }

    def do_not_index(self, libpath):
        """
        Certain libpaths are not to be indexed.
        This method says whether a given one is of that kind.
        """
        # For now we just have a finite set of exceptional libpaths.
        # In the future we may decide there are whole classes of libpaths
        # that should be skipped.
        return libpath in self.exceptional_libpaths

    def set_change_log(self, cl):
        self.change_log = cl

    def is_major_version_increment(self):
        return int(self.minor) == 0 == int(self.patch)

    def is_major_zero(self):
        return not self.is_WIP() and int(self.major) == 0

    def is_building_off_major_zero(self):
        return int(self.current_maj_vers) == 0

    def is_WIP(self):
        return self.version == pfsc.constants.WIP_TAG

    def write_padded_full_version(self):
        return ''.join([self.major, self.minor, self.patch])

    def may_make_breaking_changes(self):
        return self.is_WIP() or self.is_major_version_increment() or self.is_building_off_major_zero()

    def write_version_node_props(self):
        """
        Write relevant info for this indexing operation in a dictionary,
        to be set as properties on a j-node representing the version.
        """
        return {
            'repopath': self.repopath,
            'version': self.version,
            'full': self.write_padded_full_version(),
            'major': self.major,
            'minor': self.minor,
            'patch': self.patch,
            'commit': self.commit_hash,
            'time': unixtime(),
        }

    @staticmethod
    def compute_major_minor_patch(version):
        f = pfsc.constants.PADDED_VERSION_COMPONENT_FORMAT
        if version == pfsc.constants.WIP_TAG:
            return version, f % 0, f % 0
        vt = VersionTag(version)
        return map(lambda n: f % n, vt.get_components())

    def get_padded_major_from_pfsc_obj(self, obj):
        version = obj.getVersion()
        M, m, p = self.compute_major_minor_patch(version)
        return M

    def get_padded_current_major_version(self, graph_reader):
        """
        By the "current major version" (CMV) we mean the major version that
        the present indexing job can be understood as building off of.

        If the present job is a WIP index, the CMV is the latest major
        version that has been indexed so far, or 0 if none has yet been indexed.

        For a numbered release M.m.p, the CMV is M - 1 (or 0, whichever is
        larger) when m == 0 == p; otherwise it is M.

        :param graph_reader: GraphReader we can use to run queries.
        :return: the current major version as a 0-padded string.
        """
        current_maj_vers_int = 0
        if self.is_WIP():
            versions = graph_reader.get_versions_indexed(self.repopath)
            if versions:
                latest_info = versions[-1]
                current_maj_vers_int = int(latest_info['major'])
        else:
            M = int(self.major)
            current_maj_vers_int = max(0, M - 1) if self.is_major_version_increment() else M
        f = pfsc.constants.PADDED_VERSION_COMPONENT_FORMAT
        return f % current_maj_vers_int

    # ------------------------------------------------------------------------

    def compute_mm_closure(self, graph_reader):
        current_maj_vers = self.get_padded_current_major_version(graph_reader)
        existing_k_nodes, existing_k_relns = graph_reader.get_existing_objects(
            self.modpath, current_maj_vers, self.recursive)
        move_mapping = self.change_log.get(pfsc.constants.MOVE_MAPPING_NAME, {})
        # In the change log, all libpaths are to be relative to the repo.
        # Now we make them absolute, by prefixing the repopath.
        # We also validate libpath format here.
        mm = {}
        basepath = self.repopath + '.'
        n = len(basepath)
        for a, b in move_mapping.items():
            rel_lps = [a] if b is None else [a, b]
            for lp in rel_lps:
                if lp.startswith(basepath):
                    # Record a warning if any libpath begins with the repopath. It's
                    # not _necessarily_ an error, but it's _almost definitely_ an error.
                    msg = f'WARNING: your move mapping contains the libpath `{lp}`'
                    msg += ', which begins with the repopath. In a move mapping all libpaths'
                    msg += ' must be _relative_ to the repopath.'
                    msg += f" Are you sure you don't want `{lp[n:]}` instead?"
                    print(msg)
            A = f'{self.repopath}.{a}'
            if b is None:
                B = b
                abs_lps = [A]
            else:
                B = f'{self.repopath}.{b}'
                abs_lps = [A, B]
            for lp in abs_lps:
                check_libpath('move mapping', lp, {'value_only': True})
            mm[A] = B
        self.current_maj_vers = current_maj_vers
        self.existing_k_nodes = existing_k_nodes
        self.existing_k_relns = existing_k_relns
        self.move_mapping = mm
        self.mm_closure = compute_movemapping_closure(mm, set(existing_k_nodes.keys()))

    def cut_add_validate(self):
        """
        Compute the sets of j-vertices and j-edges to be cut and to be added,
        and also perform various validation checks.

        We work with quite a few different sets:

        L           all libpaths in the current major version
        M           all libpaths in the version being indexed
        V- = L - M  (vertex uids that are going away)
        V0 = L ^ M  (vertex uids that are staying)
        V+ = M - L  (vertex uids that are being added)
        I           immediately reused libpaths (as far as we can tell)
        D           stated domain of the move mapping
        R           stated range of the move mapping
        Dbar        computed closure of D
        Rbar        computed closure of R (not including null)
        E-          edge uids that are going away
        E0          edge uids that are staying
        E+          edge uids that are being added
        I_reln      immediately reused edge uids
        V_cut       uids of vertices that are to be cut
        V_add       uids of vertices that are to be added
        E_cut       uids of edges that are to be cut
        E_add       uids of edges that are to be added
        """

        L = set(self.existing_k_nodes.keys())
        M = set(self.get_kNode_uids())
        existing_k_reln_uids = set(self.existing_k_relns.keys())
        desired_k_reln_uids = set(self.get_kReln_uids())

        # V-: Vertex UIDs (which equal libpaths) that are going away:
        V_minus = L - M
        # V0: Vertex UIDs that are staying:
        V0 = L & M
        # V+: New Vertex UIDs:
        V_plus = M - L

        # E-: Edge UIDs (taillibpath:relntype:headlibpath) that are going away:
        E_minus = existing_k_reln_uids - desired_k_reln_uids
        # E0: Edge UIDs that are staying:
        E0 = existing_k_reln_uids & desired_k_reln_uids
        # E+: New Edge UIDs:
        E_plus = desired_k_reln_uids - existing_k_reln_uids

        Dbar = set(self.mm_closure.keys())
        Rbar = set(self.mm_closure.values()) - { None }
        # We also want the domain before closure:
        D = set(self.move_mapping.keys())

        # Correctness checks:
        # We want to check that certain sets are subsets of others.
        # The set class has a nice method for that (`issubset`), but we can't
        # use it because in the event of failure we want to be able to report
        # the witnesses. So we compute set differences instead.
        # Rbar.issubset(M):
        X = Rbar - M
        if X:
            msg = f'Change log for repo `{self.repopath}` implies the following libpaths should'
            msg += ' occur in the new version, but they cannot be found: '
            msg += str(list(X))
            raise PfscExcep(msg, PECode.INVALID_MOVE_MAPPING)
        # D.issubset(L):
        X = D - L
        if X:
            msg = f'Change log for repo `{self.repopath}` says the entities at the following'
            msg += ' libpaths move, but these libpaths cannot be found in the existing version: '
            msg += str(list(X))
            raise PfscExcep(msg, PECode.INVALID_MOVE_MAPPING)
        # V_minus.issubset(Dbar):
        X = V_minus - Dbar
        if X:
            msg = f'The following libpaths go away in the new build of repo `{self.repopath}`,'
            msg += ' but the change log is silent on them.'
            msg += f' Did you define a `{pfsc.constants.MOVE_MAPPING_NAME}` property? '
            msg += str(list(X))
            raise PfscExcep(msg, PECode.INVALID_MOVE_MAPPING)

        # We will compute the set of Immediately Reused Libpaths.
        # This is a subset of V0, and consists of all those libpaths for which
        # we are able to determine that they now point to something different
        # from what they pointed to before.
        I = set()
        I.update(Dbar & M)
        I.update(Rbar & L)
        # Examine the set V0 for any detectible changes, which will also indicate reused libpaths.
        for uid in V0:
            e = self.existing_k_nodes[uid]
            d = self.get_kNode(uid)
            if d.node_type != e.node_type or d.modpath != e.modpath:
                I.add(e.libpath)

        """
        Thm: I subset Dbar.

        Pf: If a libpath is in I, that means it's being reused.
        That means it's no longer going to point to the entity it used to point to.
        That means that entity has to have either moved or died.
        That means that entity's old libpath (the one that's being reused) should be in Dbar. [ ]
        """
        # Check:
        # if not I.issubset(Dbar):
        X = I - Dbar
        if X:
            msg = 'The following libpaths appear to be recycled (point to new entities) in the'
            msg += f' new build of repo `{self.repopath}`, but the change log is silent on them.'
            msg += f' Did you put mappings under the `{pfsc.constants.MOVE_MAPPING_NAME}` key? '
            msg += str(list(X))
            raise PfscExcep(msg, PECode.INVALID_MOVE_MAPPING)

        r"""
        Thm: V_cut = Dbar.

        Pf: Let a \in V_cut. This means a \in L and the existing j-node u_a for a is one on which
        we intend to set u_a.cut = M. But we have the rule that any j-node with finite cut property
        must have a move, i.e. a MOVE edge leaving it or one of its ancestors. But the latter can
        only happen if we know which is the _right_ move, i.e. if the change log said sth about this.
        But that's the case iff a is in Dbar.

        Conversely, let b \in Dbar. Then the entity living at libpath b in major version L is either
        moving or dying. That means the j-node representing libpath b for major version L must receive
        cut = M. That means b \in V_cut. [ ]
        """
        V_cut = Dbar

        r"""
        Thm: V_add = V+ U I.

        Pf: Let a \in V_add. This means we need to add a j-node to represent the entity that lives
        at libpath a in version M. There are two cases: either a \in L or not. If a \in L, then a
        is an immediately reused libpath, so a \in I. Otherwise a is not in L. But we said that in
        version M there is an entity that lives at a, which means a \in M. So a \in M - L = V+.

        Conversely, suppose b \in V+ U I. If b \in V+, then by definition b is not in L. That means
        there is currently no j-node for this libpath, so b \in V_add. Otherwise b \in I. In that case,
        in verion M the libpath b is to represent a different entity from the one it represented in
        version L; so the existing j-node must get cut = M, and we must add a new j-node to cover the
        libpath, i.e. we must have b \in V_add.
        """
        V_add = V_plus | I

        # A relation UID must be considered "immediately reused" if either or both of
        # its endpoint libpaths are immediately reused.
        I_reln = set()
        for uid in E0:
            tlp, kind, hlp = uid.split(":")
            if tlp in I or hlp in I:
                I_reln.add(uid)
        # Where a relation UID has been immediately reused, the old edge under that UID
        # must be marked as cut, and we must add a new edge to represent this reln in the new version.
        E_cut = E_minus | I_reln
        E_add = E_plus | I_reln

        # Check: No j-node should have more than one EXPANDS relation leaving it.
        # This means that if we're going to add an EXPANDS edge where the tail libpath
        # already exists in the index, then this libpath should be among the immediately reused.
        for uid in E_add:
            tlp, kind, hlp = uid.split(":")
            if kind == IndexType.EXPANDS and tlp in L and not tlp in I:
                msg = f'Attempting to add relation `{uid}`, but tailpath `{tlp}` already exists'
                msg += ', and does not appear to be recycled.'
                msg += f' No node can have multiple `{IndexType.EXPANDS}` relations leaving it.'
                raise PfscExcep(msg, PECode.MULTIPLE_EXPANSION_DEFINITION)

        # Note: It's always possible there be breaking changes that we _can't_ detect automatically,
        # but we do the best we can.
        there_are_detectible_breaking_changes = (
                V_cut or E_cut or self.move_mapping
        )
        if there_are_detectible_breaking_changes and not self.may_make_breaking_changes():
            msg = f'Release `{self.version}` of repo `{self.repopath}` makes disallowed breaking changes.'
            for uid in list(V_cut) + list(E_cut):
                msg += f'\nCuts: {uid}'
            for src, dst in self.move_mapping.items():
                msg += f'\nMoves: {src} --> {dst}'
            for uid in I:
                msg += f'\nReuses: {uid}'
            raise PfscExcep(msg, PECode.BUILD_MAKES_DISALLOWED_BREAKING_CHANGE)

        self.M = M
        self.Rbar = Rbar
        self.V_cut = V_cut
        self.E_cut = E_cut
        self.V_add = V_add
        self.E_add = E_add

    def here_elsewhere_nowhere(self):
        """
        For an indexing operation, we speak of "time" and "place". There are two times: now, and before.
        By "now" we mean the version being indexed, and by "before" we mean what exists in the index already.
        Meanwhile, by "place" we mean libpath.

        For any entity that's going to exist _here_ at libpath `lp`, and _now_, we can ask: Where was it before?
        And there are three possible answers: here, elsewhere, or nowhere.

        Accordingly, if `M` is the set of all libpaths in use _now_, we partition `M` into three disjoint sets:

                M = H U E U N

            "Here":      H = {lp in M : the entity living at lp now also lived at lp before}
            "Elsewhere": E = {lp in M : the entity living at lp now lived at a different libpath before}
            "Nowhere":   N = {lp in M : the entity living at lp now is being born now, i.e. did not live anywhere before}

        This method computes the three sets H, E, N.
        """
        ...
        r"""
        Thm: E = Rbar
        
        Pf:
        This is essentially just by definition. If we write it out, it goes like this:
        
        Suppose b \in E, and let e be the entity that will be living at b now. By def of E, e lived somewhere
        else before, say at libpath a. So e is moving in this build, and so the mapping a |--> b is to be implied
        by the change log. But that just means that a \in Dbar and b \in Rbar.
        
        Conversely, suppose b \in Rbar. Then there must be some a \in Dbar such that a |--> b is implied by the
        change log. This means there is an entity e that lived at a before, and will be living at b now.
        Then b \in E by definition of E. [ ]
        """
        self.elsewhere = self.Rbar

        r"""
        Thm: N = V_add - Rbar
        
        Pf:
        Using the previous theorem, and the key theorem about V_add (that it equals V_plus U I -- see `cut_add_validate()`),
        this is equivalent to: N = (V_plus U I) - E.
        
        Suppose a \in N, and let e be the entity that will be living at a now. Since N and E are by defn disjoint,
        it is enough to show that a \in I or a \in V_plus.
        
        Since e is just being born now, that means that either something else lived at a before, or nothing did.
        If something else lived at a before, then a \in I. If nothing lived at a before, then a \not\in L,
        so a \in M - L = V_plus.
        
        Conversely, suppose b \in V_add - Rbar. Since V_add \subseteq M, we can let f be the entity that will be
        living at b now. We want to show that f is being born now. Suppose not. If f is not just being born now,
        then it lived before. And if it lived before, then it lived either at b, or not at b. If it lived somewhere
        other than b before, and will live at b now, then b \in Rbar, which is a contradiction. The only remaining
        possibility is that f lived at b before and will continue to do so now, and for this last case we will derive
        our contradiction by showing that b could not be in V_add. This means showing that b could be neither in V_plus
        nor in I. Well, to say that _anything_ was at b before says that b \in L, which means b \not\in M - L = V_plus.
        And finally, to say that the _same_ thing (f) was at b before and now as well, is to say that b \not\in I. [ ]
        """
        self.nowhere = self.V_add - self.Rbar

        r"""
        Cor: H = M - (V_add U Rbar)
        
        Pf:
        
        H = M - (N U E) = M - ((V_add - Rbar) U Rbar)
        
        but in general
        
        (X - Y) U Y  =  (X ^ ~Y) U Y
                     =  (X U Y) ^ (~Y U Y)
                     =  X U Y
        
        [ ]
        """
        self.here = self.M - (self.V_add | self.Rbar)

    def compute_origins(self, graph_reader):
        """
        We need to do two things with origin properties:
        (1) Set them on the new j-nodes that will represent libpaths in E.
        (2) Prepare a lookup giving the origin for _every_ libpath in M,
          so that the Builder can set these into certain `PfscObj`s.
        """
        # We need to query the graph database for origins for E and H.
        # To be precise, we want origins for existing j-nodes at the
        # current major version and with libpaths a such that either a in H
        # or a |--> b in E according to the mm_closure.
        libpaths_by_node_type = defaultdict(list)
        mm_closure_inverse = {}
        # E:
        for a, b in self.mm_closure.items():
            if b is not None:
                k = self.existing_k_nodes[a]
                libpaths_by_node_type[k.node_type].append(a)
                mm_closure_inverse[b] = a
        # H:
        for a in self.here:
            k = self.existing_k_nodes[a]
            libpaths_by_node_type[k.node_type].append(a)
        M0 = int(self.current_maj_vers)
        M1 = collapse_major_string(self.major)
        existing_origins = graph_reader.get_origins(libpaths_by_node_type, M0)
        # Now we can build a lookup giving the origin for every libpath in M.
        new_origins = {}
        # E:
        for b in self.elsewhere:
            a = mm_closure_inverse[b]
            new_origins[b] = existing_origins[a]
        # H:
        for a in self.here:
            new_origins[a] = existing_origins[a]
        # N:
        for a in self.nowhere:
            new_origins[a] = f'{a}@{M1}'
        # We want the kNodes for E to have `origin` properties.
        for b in self.elsewhere:
            k = self.get_kNode(b)
            k.set_extra_prop('origin', new_origins[b])
        # Store the origins lookup so the Builder can use it to set origin
        # properties in certain PfscObjs before writing their products to disk.
        self.origins = new_origins

    # ------------------------------------------------------------------------

    def get_kNode_uids(self):
        return self.node_lookup.keys()

    def get_kReln_uids(self):
        return self.reln_lookup.keys()

    def get_kNode(self, uid):
        return self.node_lookup[uid]

    def get_kReln(self, uid):
        return self.reln_lookup[uid]

    # ------------------------------------------------------------------------
    # Low-level methods.
    #   Use these methods to add kNodes and kRelns directly.

    def add_kNode(self, node_type, libpath, modpath, extra_props=None):
        """
        Add a kNode.

        Args are the same as those to the kNode initializer.
        """
        k = kNode(node_type, libpath, modpath,
                  self.repopath, self.major, self.minor, self.patch, extra_props=extra_props)
        self.node_lookup[k.uid] = k
        return k

    def add_kReln(self,
                  tail_type, tail_libpath, tail_major,
                  reln_type,
                  head_type, head_libpath, head_major,
                  modpath, extra_props=None):
        """
        Add a kReln.

        Args are the same as those to the kReln initializer.
        """
        k = kReln(
            tail_type, tail_libpath, tail_major,
            reln_type,
            head_type, head_libpath, head_major,
            modpath,
            self.repopath, self.major, self.minor, self.patch,
            extra_props=extra_props
        )
        self.reln_lookup[k.uid] = k
        return k

    # ------------------------------------------------------------------------
    # High-level methods.
    #   Use these methods to add various pfsc entity types, and let the system
    #   figure out for you which kNodes and kRelns are to be recorded.

    def add_under_reln(self, child_type, childpath, parent_type, parentpath, modpath):
        i = childpath.rfind('.')
        segment = childpath[i+1:]
        self.add_kReln(child_type, childpath, self.major, IndexType.UNDER, parent_type, parentpath, self.major, modpath,
                       extra_props={"segment": segment})

    def add_submodule(self, modpath, parentpath):
        self.submodules.append(modpath)
        self.add_kNode(IndexType.MODULE, modpath, modpath)
        self.add_under_reln(IndexType.MODULE, modpath, IndexType.MODULE, parentpath, modpath)

    def add_comparisons(self, object, modpath):
        itype = object.get_index_type()
        libpath = object.getLibpath()
        cfs = object.getComparisons()
        for cf in cfs:
            self.add_kReln(
                itype, libpath, self.major,
                IndexType.CF,
                cf.target_index_type, cf.target_libpath, self.major,
                modpath
            )

    def add_pfsc_node(self, module, node):
        """
        The name of this method is meant to clearly disambiguate between "nodes" in
        the Proofscape system, and "nodes" in the GDB. Use this method when you want
        to add one of the former.

        :param module: a PfscModule
        :param node: a (proofscape) Node belonging to this PfscModule
        """
        libpath = node.getLibpath()
        modpath = module.getLibpath()
        nodetype = node.get_index_type()
        self.add_kNode(nodetype, libpath, modpath)
        children = node.getChildrenForIndex()
        for child in children:
            self.add_pfsc_node(module, child)
            child_type = child.get_index_type()
            childpath = child.getLibpath()
            self.add_under_reln(child_type, childpath, nodetype, libpath, modpath)
        self.add_comparisons(node, modpath)

    def add_enrichment(self, module, eobj):
        """
        :param module: a PfscModule
        :param eobj: an enrichment object (Deduction, Examplorer, or Annotation) belonging to this PfscModule
        """
        libpath = eobj.getLibpath()
        modpath = module.getLibpath()
        itype = eobj.get_index_type()
        self.add_generic(itype, libpath, module)
        # Targets
        targets = eobj.getTargets()
        for target in targets:
            t_type = target.get_index_type()
            t_libpath = target.getLibpath()
            t_major = self.get_padded_major_from_pfsc_obj(target)
            self.add_kReln(itype, libpath, self.major, IndexType.TARGETS, t_type, t_libpath, t_major, modpath)

    def add_generic(self, itype, libpath, module):
        if self.do_not_index(libpath):
            return
        modpath = module.getLibpath()
        self.add_kNode(itype, libpath, modpath)
        self.add_under_reln(itype, libpath, IndexType.MODULE, modpath, modpath)

    def add_anno(self, module, anno):
        modpath = module.getLibpath()
        annopath = anno.getLibpath()
        self.add_enrichment(module, anno)
        widgets = anno.get_proper_widgets()
        for widget in widgets:
            widgetpath = widget.getLibpath()
            self.add_kNode(IndexType.WIDGET, widgetpath, modpath, extra_props={IndexType.EP_WTYPE: widget.get_type()})
            self.add_under_reln(IndexType.WIDGET, widgetpath, IndexType.ANNO, annopath, modpath)

    def add_deduc(self, module, deduc):
        """
        While a deduction _is_ a particular type of enrichment, there is enough
        special processing for a deduc that we have a dedicated method for it.

        :param module: a PfscModule
        :param deduc: a Deduction belonging to this PfscModule
        """
        modpath = module.getLibpath()
        deducpath = deduc.getLibpath()
        self.add_enrichment(module, deduc)
        self.add_comparisons(deduc, modpath)

        # Add UNDER relations for nodes (of all types, incl special,
        # ghost, and subdeduc) that live inside this deduction.
        all_children = deduc.getChildren()
        for node in all_children:
            self.add_pfsc_node(module, node)
            child_type = node.get_index_type()
            childpath = node.getLibpath()
            self.add_under_reln(child_type, childpath, IndexType.DEDUC, deducpath, modpath)

        # Add special nodes.
        special_nodes = deduc.getSpecialNodes()
        for node in special_nodes:
            libpath = node.getLibpath()
            self.add_kNode(IndexType.SPECIAL, libpath, modpath)

        # Add ghost nodes and GHOSTOF relations
        ghost_nodes = deduc.getGhostNodes()
        for gn in ghost_nodes:
            ghostpath = gn.getLibpath()
            real_obj = gn.realObj()
            real_type = real_obj.get_index_type()
            realpath = real_obj.getLibpath()
            real_major = self.get_padded_major_from_pfsc_obj(real_obj)
            self.add_kNode(IndexType.GHOST, ghostpath, modpath)
            self.add_kReln(IndexType.GHOST, ghostpath, self.major, IndexType.GHOSTOF, real_type, realpath, real_major, modpath)

        # Add IMPLIES and FLOWSTO relations
        edges = deduc.getGraph().getEdges()
        for edge in edges.values():
            tail = edge.getSrcActualNode()
            t_type = tail.get_index_type()
            tailpath = tail.getLibpath()
            t_major = self.get_padded_major_from_pfsc_obj(tail)
            head = edge.getTgtActualNode()
            h_type = head.get_index_type()
            headpath = head.getLibpath()
            h_major = self.get_padded_major_from_pfsc_obj(head)
            reln_type = IndexType.IMPLIES if edge.isDeduc() else IndexType.FLOWSTO
            self.add_kReln(t_type, tailpath, t_major, reln_type, h_type, headpath, h_major, modpath)

        # Is this deduc an expansion?
        parent = deduc.getTargetDeduc()
        if parent is not None:
            p_libpath = parent.getLibpath()
            p_vers = parent.getVersion()
            p_major = self.get_padded_major_from_pfsc_obj(parent)
            self.add_kReln(
                IndexType.DEDUC, deducpath, self.major, IndexType.EXPANDS,
                IndexType.DEDUC, p_libpath, p_major, modpath, extra_props={IndexType.EP_TAKEN_AT: p_vers})


def compute_movemapping_closure(mm, L):
    """
    The move mapping in a repo change log is largely implicit: when it states
    that libpath `a` maps to libpath `b`, this means that any libpath _starting
    with_ `a` (in whole segments) should have that part replaced by `b`.
    This holds, up until any more specific key in the mapping overrides it.

    So, given the set of all libpaths currently present in the repo, we may wish
    to compute the "closure" of both the domain and range of the given move mapping.
    This means we want to know the set of all libpaths to which the mapping actually
    applies (the domain closure), and we want to know where each of these libpaths
    gets mapped to (the range closure).

    :param mm: The move mapping (dict) provided in a repo's change log.
    :param L:  The set of all libpaths present in the current version of the repo.
    :return: dict representing the mapping from domain closure to range closure.
    """
    matches = LibpathPrefixMapping(mm)(L)
    return {lp: m.substitute() for lp, m in matches.items()}

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

from collections import defaultdict

import pfsc.constants
from pfsc.handlers import Handler
from pfsc.handlers.load import DashgraphLoader
from pfsc.checkinput import IType, check_versioned_libpath
from pfsc.gdb import get_graph_reader
from pfsc.lang.modules import build_module_from_text
from pfsc.build.repo import get_repo_part
from pfsc.build.lib.addresses import (
    VersionedLibpathNode,
    ForestAddressList,
    find_oldest_elements,
)
from pfsc.build.lib.prefix import LibpathPrefixMapping
from pfsc.excep import PfscExcep, PECode


class VersionMappings:
    """
    Generate various types of mapping associating libpaths with (major or full)
    version numbers.
    """

    def __init__(self, given_mapping):
        """
        :param given_mapping: dict mapping libpaths (strings) to CheckedVersion
          instances.
        """
        self.given_mapping = given_mapping
        # We use reversible prefix mappings because if a node is desired at a given
        # version, this implies that its deduc must be desired at that version as well.
        self.prefix2full = LibpathPrefixMapping({k:v.full for k, v in given_mapping.items()}, reversible=True)
        self.prefix2major = LibpathPrefixMapping({k:v.major for k, v in given_mapping.items()}, reversible=True)
        self.fallbacks = []

    def add_fallback(self, other):
        """
        Supply another instance of this class, which we are allowed to fall back on
        when computing mappings.
        :param other: another VersionMappings instance
        :return: nothing
        """
        self.fallbacks.append(other)

    @staticmethod
    def raise_no_def_excep(libpath):
        msg = f'Failed to define version number for `{libpath}` in ForestUpdateHelper request.'
        raise PfscExcep(msg, PECode.MISSING_REPO_DEPENDENCY_INFO)

    def get_source_stack(self):
        return list(reversed([self] + self.fallbacks))

    def make_libpaths_by_major_mapping(self, libpaths, tolerant=False):
        """
        :param libpaths: iterable of libpaths
        :param tolerant: if False, raise an exception for any libpath that
          doesn't match.
        :return: dict mapping major version numbers to lists of libpaths
          that fall under that number.
        """
        sources = self.get_source_stack()
        lbm = defaultdict(list)
        while sources and libpaths:
            source = sources.pop()
            unmatched = []
            matches = source.prefix2major(libpaths)
            for libpath in libpaths:
                match = matches.get(libpath)
                if match is None:
                    unmatched.append(libpath)
                else:
                    lbm[match.value()].append(libpath)
            libpaths = unmatched
        if libpaths and not tolerant:
            self.raise_no_def_excep(libpaths.pop())
        return lbm

    def make_libpath_to_full_mapping(self, libpaths, tolerant=False):
        """
        :param libpaths: iterable of libpaths
        :param tolerant: if False, raise an exception for any libpath that
          doesn't match.
        :return: dict mapping each libpath to its full version
        """
        sources = self.get_source_stack()
        ltf = {}
        while sources and libpaths:
            source = sources.pop()
            unmatched = []
            matches = source.prefix2full(libpaths)
            for libpath in libpaths:
                match = matches.get(libpath)
                if match is None:
                    unmatched.append(libpath)
                else:
                    ltf[libpath] = match.value()
            libpaths = unmatched
        if libpaths and not tolerant:
            self.raise_no_def_excep(libpaths.pop())
        return ltf

    def make_fvlps(self, libpaths, tolerant=False):
        """
        Make "full versioned libpaths".

        :param libpaths: iterable of libpaths
        :param tolerant: same as in `make_libpath_to_full_mapping` method.
        :return: set of strings of the form `libpath@fullversion`
        """
        m = self.make_libpath_to_full_mapping(libpaths, tolerant=tolerant)
        return set(f'{libpath}@{vers}' for libpath, vers in m.items())


class DeducClosureFinder(Handler):
    """
    Usage:

    Under the arg 'libpaths', pass a list of libpaths [p1, p2, ..., pn] (as a comma-delimited
    string) which may point to any mixture of deductions, subdeductions, nodes, and subnodes.

    Under the arg 'versions', pass the corresponding list of desired version numbers.
    These may be full version strings `vM.m.p`, or mere major version numbers `M`.

    If for each i, qi is the libpath of the nearest ancestor of pi that is a deduction, then we
    return the set {q1, q2, ..., qn}. (We return it as a list, but there are no repeats.)
    Thus, you get the smallest set of deductions containing all the things you named.

    The list will be under the `closure` property of the returned JSON.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'libpaths': {
                    'type': IType.CDLIST,
                    'itemtype': {
                        'type': IType.LIBPATH,
                        'formally_within_module': True
                    }
                },
                'versions': {
                    'type': IType.CDLIST,
                    'itemtype': {
                        'type': IType.MAJ_VERS,
                    }
                },
            }
        })

    def check_permissions(self, libpaths, versions):
        repos = set([
            get_repo_part(lp.value)
            for lp, v in zip(libpaths, versions)
            if v == pfsc.constants.WIP_TAG
        ])
        for rp in repos:
            self.check_repo_read_permission(
                rp, pfsc.constants.WIP_TAG, action='access work in progress from')

    def go_ahead(self, libpaths, versions):
        libpaths = [lp.value for lp in libpaths]
        libpaths_by_major = defaultdict(list)
        for lp, vers in zip(libpaths, versions):
            libpaths_by_major[vers].append(lp)
        closure = list(get_graph_reader().get_deduction_closure(libpaths_by_major))
        self.set_response_field('closure', closure)


class TheoryMapBuilder(Handler):
    """
    Builds dashgraphs for drawing the "upper and lower theory maps" for deductions
    in the library.

    The "lower theory map" for a given deduction is the graph of all deducs on which
    the given one relies, recursively, plus itself. We search only within the repo to
    which the given deduc belongs.

    The "upper theory map" is the same idea, only this time we are looking for all
    deducs that rely on the given one, (again, recursively).
    """

    def check_input(self):
        self.check({
            "REQ": {
                'deducpath': {
                    'type': IType.LIBPATH,
                },
                'vers': {
                    'type': IType.FULL_VERS,
                },
                'type': {
                    'type': IType.STR,
                    'values': ['lower', 'upper']
                }
            }
        })

    def check_permissions(self, deducpath, vers):
        """
        NOTE: This is the correct check as long as we're searching only within
        the repo to which the given deduc belongs. If we ever generalize that,
        we'll have to review this check as well.
        """
        if vers.isWIP:
            self.check_repo_read_permission(deducpath, vers, action='load work in progress from')

    def go_ahead(self, deducpath, vers, type):
        deducpath = deducpath.value
        if type == 'lower':
            graph = get_graph_reader().get_lower_theory_graph(deducpath, vers.major)
        else:
            graph = get_graph_reader().get_upper_theory_graph(deducpath, vers.major)
        # Now build a dashgraph.
        name = '_map'
        modtext = graph.write_modtext(name)
        modpath = f'special.theorymap.{type}.{deducpath}'
        repopath = get_repo_part(deducpath)
        module = build_module_from_text(modtext, modpath, dependencies={
            repopath: vers.full,
        })
        theorymap = module[name]
        dg = theorymap.buildDashgraph()
        self.set_response_field('dashgraph', dg)

def vlpStr2Node(vlpStr):
    """
    Convenience function to turn a "versioned libpath string" into a VersionedLibpathNode.
    """
    return check_versioned_libpath('', vlpStr, {})

class ForestUpdateHelper(Handler):
    """
    When the Forest is handling a request to update the state in a chart panel, this handler helps
    it figure out what it needs to do, and supplies all the data necessary to do it, in convenient format.

    NOTE: All the input for this handler is expected to come under a single JSON serialized object.
    Accordingly, in our `check_input` method we use `self.check_jsa`.

    INPUT:

        current_forest: dict representing the entire forest of deducs currently on board, including the libpath and
          version of each, and showing the expansion structure. It looks sth like this:

            {
                libpath.of.a.Thm@vers: {
                    libpath.of.Pf.of.Thm@vers: {
                        libpath.of.an.expansion.on.Pf@vers: {},
                        libpath.of.another.expansion.on.Pf@vers: {}
                    }
                },
                libpath.of.another.Thm@vers: {}
            }

          and it can be obtained as the return value of `Floor.writeVersionedForestRepn()` in Moose.

        on_board: boxlisting indicating any elements (nodes and/or deducs), all of which you want to be on the
          board (and some of which may already be there).

        reload: boxlisting indicating elements -- presumably already on the board -- which you want reloaded/refreshed;
          if an element is in fact absent, it is no error, it just means the same thing as `on_board`;
          keyword 'all' is permitted, meaning everything on board is to be reloaded.

        to_view: boxlisting indicating elements that are to be viewed; keyword 'all' is permitted, meaning you
          want an overview of all elements.

        desired_versions: dict, mapping libpaths to full version strings, indicating the versions at which
          you want deducs to be loaded.

          For every libpath listed in any of the three above arguments (`on_board`, `reload`, and `to_view`) either this
          dict, or the `current_forest` dict, must supply a version number. We check `desired_versions` first, and go to
          `current_forest` only if necessary.

          Note that both lookups will be interpreted as "reversible prefix mappings."
          This means that not every libpath needing a version has to be a key, but if not then either some proper
          segmentwise prefix or extension of it must be, in order to find a match. Prefixes are allowed because these
          are, by definition, prefix mappings. Extensions are allowed (and this is what makes them "reversible") because
          it makes sense: if a node is desired at a certain version, that implies that so is its deduc.

        off_board: boxlisting indicating any elements you do _not_ want on the board (and may not be there already);
          keyword 'all' is permitted, meaning the board should be cleared of existing deducs. Here the version numbers
          are those implied by `current_forest`.

        incl_nbhd_in_view: boolean; if true, (and if to_view is not 'all') it means that you want to augment `to_view`
          by including the deductive neighborhood of each object in that list -- i.e. all nodes one deduction arc away.

        known_dashgraphs: dict, in which the keys are the libpaths of deductions whose dashgraphs need not be
          loaded from disk, since for whatever reason the ISE already has them, or does not need them. For each
          key `k` in this dict, let `D` be the deduction of which `k` is the libpath. If `D` is a top-level deduction
          (i.e. has no parent, or expands on nothing), then `k` must point to `null`. Otherwise, suppose
          `D` expands on deduc `C` at version `V`. Then `k` must point to the string `C@V`.

        NOTE: It can be tricky to understand what `reload` means w.r.t. versions. The rule is: these are libpaths
        which will be closed if present -- at whatever version they are present -- and will be opened at the version
        indicated in `desired_versions`, again, _regardless of the version that is currently present_. So, reloading
        can be a way to change the version of a deduc on board.

    OUTPUT:

        to_close: list of libpaths of deductions presently on the board, that should be closed.

                 You might think this list should be in reverse-topological order, but instead this list will
                 have the property that if it contains deductions C and D, then neither C nor D is ancestor of
                 the other.

                 A list with this property can do the job because whenever the ISE removes a deduction
                 from the board, it also removes any and all descendants along with it.

        to_open: list of libpaths of deductions that should be opened. If a deduction D appears in this list,
                then either it is not presently on the board, or it is but the user has requested it be reloaded
                (or has requested it at a different version than currently present).

                This list of libpaths is guaranteed to have two properties: (1) it is sorted in _topological
                order_. (2) If united with the set of deducs that will remain on board after the close operation
                indicated by the `to_close` list, you get an ancestrally closed set.

                This means that after performing the close operation, you can open these deducs in the order
                given, and each deduc's ancestors will already be present at the time that it is opened.

        dashgraphs: a lookup, in which the libpaths in the `to_open` list point to the dashgraphs for
                    these deducs, loaded freshly from disk, except that any libpaths that were named in the
                    `known_dashgraphs` input field will not have an entry here.

        view_closure: equal to `to_view` if `incl_nbhd_in_view` was `False` or if `to_view` was `'all'`; otherwise
            equal to the neighborhood-closure of `to_view`, i.e. `to_view` plus all nodes one arc away from nodes therein.

        NOTE: We need not return version numbers for the libpaths in `to_open`, because that information is available
        in the returned `dashgraphs` lookup (or in any known dashgraphs you already had on the client side).

    NOTE: If an impossible state is requested, behavior is undefined. (It is deterministic, but we make no claim
    about what it will be.) For example, if D <-- E and you ask that E be on board but D be off board, you are
    requesting an impossible state. We will return something, but of course it will not achieve what you asked for.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gr = None

    def check_input(self):
        self.check_jsa('info', {
            "OPT": {
                'on_board': {
                    'type': IType.BOXLISTING,
                    'default_raw': None,
                    'libpath_type': {'formally_within_module': True}
                },
                'reload': {
                    'type': IType.BOXLISTING,
                    'allowed_keywords': ['all'],
                    'default_raw': None,
                    'libpath_type': {'formally_within_module': True}
                },
                'to_view': {
                    'type': IType.BOXLISTING,
                    'allowed_keywords': ['all'],
                    'default_raw': None,
                    'libpath_type': {'formally_within_module': True}
                },
                'desired_versions': {
                    'type': IType.DICT,
                    'keytype': {
                        'type': IType.LIBPATH,
                        'value_only': True,
                    },
                    'valtype': {
                        'type': IType.FULL_VERS,
                    },
                    'default_cooked': {},
                },
                'current_forest': {
                    'type': IType.VERSIONED_FOREST,
                    'default_raw': {},
                },
                'off_board': {
                    'type': IType.BOXLISTING,
                    'allowed_keywords': ['all'],
                    'default_raw': None,
                    'libpath_type': {'formally_within_module': True}
                },
                'incl_nbhd_in_view': {
                    'type': IType.BOOLEAN,
                    'default_cooked': False
                },
                'known_dashgraphs': {
                    'type': IType.DICT,
                    'keytype': {
                        'type': IType.LIBPATH,
                        'value_only': True,
                    },
                    'valtype': {
                        'type': IType.VERSIONED_LIBPATH,
                        'null_okay': True,
                    },
                    'default_cooked': {},
                }
            },
        })

    def check_permissions(self, current_forest, desired_versions):
        """
        FIXME
        This is a tricky one. To really do it right, we probably can't do a preliminary
        check here at all; we probably have to just `pass` here, and perform checks at
        several different places in the methods that follow.

        If we didn't care about "libpath espionage" (i.e. learning things about the
        set of libpaths present in a repo you do not own), then this would be very easy.
        We wouldn't need to do any check at all. Where we load dashgraphs in our
        `step_040_ancestors` method, we rely on a DashgraphLoader, and the latter would do
        all the necessary permission checking for us.

        But since we do care about libpath espionage, we have to be careful about what
        we return in `to_open` and `view_closure` too. For example, Let R be a repo you
        do not own. If in `to_view` you named a node v belonging to R, and in `desired_versions`
        you said you wanted repo R at WIP, then in the `view_closure` part of the response
        you could learn:

            * that libpath(v) is indeed present in R@WIP
            * the libpaths of all nodes one deduction arc away from v in R@WIP

        Or again, suppose in `on_board` you named a deduc d belonging to R. Then from `to_open`
        you could learn:

            * that libpath(d) is indeed present in R@WIP
            * the libpaths of all ancestors of d in R@WIP

        To prevent this, it would again be easy if only `desired_versions` could come to bear.
        But in fact `current_forest` has to be checked too, since we have the mechanism where we
        fall back on `current_forest` when `desired_versions` is silent.

        This means if we want to do a _preliminary_ check, i.e. one happening right here,
        before we get into the thick of computing various sets in the methods below, we have
        to check permissions on _all_ repos named at WIP in `current_forest`.

        But this has the unintended consequence that we might refuse to help
        a user update the state in a chart in which a deduc is _already open_ at WIP from a repo
        they don't own, even if their request does not involve learning anything new about that
        repo. That is odd behavior.

        Admittedly, this should be an edge case in practice. It could arise if you were logged
        in, opened a deduc from a repo you own at WIP, then logged out while that chart was still
        open, then attempted to open something else in that chart.

        Arguably, having WIP that you don't own open in a chart in your app is a weird state
        that we don't really need to support smoothly, at least in beta. So for now I'm going
        to err on the safe side and just do a preliminary check on all repos named in both
        `current_forest` and in `desired_versions`. Later, we may wish to refine this a bit.
        """
        current_versions = current_forest.get_implied_version_mapping()
        repos = set()
        repos.update(set([get_repo_part(k) for k, v in desired_versions.items() if v.isWIP]))
        repos.update(set([get_repo_part(k) for k, v in current_versions.items() if v.isWIP]))
        for rp in repos:
            self.check_repo_read_permission(rp, pfsc.constants.WIP_TAG,
                                            action='access work in progress from')

    def go_ahead(self, on_board, reload, to_view, current_forest, desired_versions, off_board, incl_nbhd_in_view, known_dashgraphs):
        self.gr = get_graph_reader()
        # Throughout this process, we make use of sets of "versioned deducpaths", by which
        # we mean strings of the form `deducpath@version`. We give most of these sets names
        # beginning with `d` for "deductions".
        # We begin with d0: the set of all deducs currently on board
        assert isinstance(current_forest, VersionedLibpathNode)
        d0 = set(current_forest.get_all_versioned_libpath_strings())

        cvm = VersionMappings(current_forest.get_implied_version_mapping())
        dvm = VersionMappings(desired_versions)
        dvm.add_fallback(cvm)

        view_closure, d_v = self.step_010_view(to_view, incl_nbhd_in_view, d0, dvm)

        d_re, d_fake_re, d_re_desc = self.step_020_reload(reload, d0, dvm, current_forest)

        d_need_ancestors, d_implied_really_want_removed = self.step_030_on_and_off(
            dvm, on_board, d_v, d_re, d_fake_re, d_re_desc, d0, current_forest, off_board, cvm)

        dashgraphs, opening_forest, d_implied_want_opened = self.step_040_ancestors(
            d_need_ancestors, known_dashgraphs, d0)

        to_open, to_close = self.step_050_open_and_close(
            d_implied_want_opened, d_re, d_implied_really_want_removed, current_forest, opening_forest)

        # Record the results.
        self.set_response_field('to_close', to_close)
        self.set_response_field('to_open', to_open)
        self.set_response_field('dashgraphs', dashgraphs)
        self.set_response_field('view_closure', view_closure)

    def step_010_view(self, to_view, incl_nbhd_in_view, d0, dvm):
        if to_view.is_keyword('all'):
            # When the user asks to view 'all' (meaning an overview), then `to_view` does not name any
            # additional nodes or deducs that are to be viewed, beyond what is already specified by
            # other parameters.
            # For `view_closure` we can just return the same keyword 'all'.
            view_closure = 'all'
            # For `d_v`, which we use locally to represent the set of deducs we want to view, we
            # take a copy of the set of all deducs currently on board.
            d_v = set(d0)
        else:
            # When the user has listed libpaths of nodes and deducs to be viewed, then we must first
            # adjoin neighboring nodes, if that has been requested.
            # Make a copy of the list, so that we can modify it without affecting anything else.
            view_closure = to_view.get_libpaths()[:]
            if incl_nbhd_in_view:
                libpaths_by_major = dvm.make_libpaths_by_major_mapping(view_closure)
                nbrs = self.gr.get_deductive_nbrs(libpaths_by_major)
                view_closure = list(set(view_closure) | nbrs)
            # And now we must compute the deduction closure, in order to get the set of deducs that
            # must be on board in order to satisfy the requested view.
            libpaths_by_major = dvm.make_libpaths_by_major_mapping(view_closure)
            dc = self.gr.get_deduction_closure(libpaths_by_major)
            d_v = dvm.make_fvlps(dc)
        return view_closure, d_v

    def step_020_reload(self, reload, d0, dvm, current_forest):
        if reload.is_keyword('all'):
            libpaths_to_reload = current_forest.get_implied_version_mapping().keys()
        else:
            libpaths_to_reload = reload.get_libpaths()
        libpaths_by_major = dvm.make_libpaths_by_major_mapping(libpaths_to_reload)
        dc = self.gr.get_deduction_closure(libpaths_by_major)
        # Deducs for which a reload was requested:
        d_requested_re = dvm.make_fvlps(dc)
        # Deducs that are actually to be reloaded, i.e. closed and then opened again:
        d_re = d_requested_re & d0
        # Deducs that we said we wanted to reload, but actually they're not present,
        # so really it's just more deducs that we want to open:
        d_fake_re = d_requested_re - d0
        # Proper descendants, among d0, of the deducs that are actually to be
        # reloaded, i.e. closed and then opened again:
        if d_re != set():
            # If d_re is nonempty, we
            # compute its proper descendants among d0.
            # Note: d_re is the set of versioned libpaths that we want to reload, and that are already
            # present _at the desired version_. This means that, if any descendants
            # (i.e. expansions, recursively) are already present as well, then these too are
            # already known to apply to the desired version.
            d_re_desc = set(current_forest.get_descendants_of_vlps(d_re).keys())
            # But we only want _proper_ descendants:
            d_re_desc -= d_re
        else:
            d_re_desc = set()
        return d_re, d_fake_re, d_re_desc

    def step_030_on_and_off(self, dvm, on_board, d_v, d_re, d_fake_re, d_re_desc, d0, current_forest, off_board, cvm):
        # d_on: set of deducs the user has explicitly requested be on board
        libpaths_by_major = dvm.make_libpaths_by_major_mapping(on_board.get_libpaths())
        dc = self.gr.get_deduction_closure(libpaths_by_major)
        d_on = dvm.make_fvlps(dc)
        # Altogether the user has, in effect, said that certain deductions should be present:
        d_said_want_present = d_on | d_v | d_re | d_fake_re
        # Some of these already may be present, others not.
        d_said_want_kept = d_said_want_present & d0
        # We want to open a deduc if (a) we want it present and it is not, or (b) it is present but
        # want to reload it.
        d_said_want_opened = (d_said_want_present - d0) | d_re
        # The deducs we implied we want kept are those we said we want kept, plus their ancestors.
        d_implied_want_kept = set(current_forest.get_ancestors_of_vlps(d_said_want_kept).keys())
        # Which deducs did the user say should be removed?
        if off_board.is_keyword('all'):
            d_said_want_removed = d0 - d_implied_want_kept
        else:
            libpaths_by_major = cvm.make_libpaths_by_major_mapping(off_board.get_libpaths(), tolerant=True)
            dc = self.gr.get_deduction_closure(libpaths_by_major)
            d_off = cvm.make_fvlps(dc)
            d_said_want_removed = d_off & d0
        # The deducs that we _imply_ we want removed, are those we _said_ we want removed, plus the
        # descendants of these, among d0.
        d_implied_want_removed = set(current_forest.get_descendants_of_vlps(d_said_want_removed).keys())
        # But "on" overrides "off", so...
        d_implied_really_want_removed = d_implied_want_removed - d_implied_want_kept
        # And for which deducs do we need ancestors? (1) whatever we said we wanted to be opened.
        # Meanwhile (2) there is a by-product of reloading the deducs in d_re: their on-board proper
        # descendants will get closed. The question is which, among these, should then be reopened.
        # And the answer is: any that we didn't really want to remove.
        d_need_ancestors = d_said_want_opened | (d_re_desc - d_implied_really_want_removed)
        return d_need_ancestors, d_implied_really_want_removed

    def step_040_ancestors(self, d_need_ancestors, known_dashgraphs, d0):
        # We do a DFS to compute the set of all deducs which the user "implied" they want opened,
        # meaning either the deduc was named, or is an ancestor of one that was named.
        dashgraphs = {}
        nodes = {}
        opening_forest = VersionedLibpathNode(None, None)
        d_implied_want_opened = set()
        stack = [vlpStr2Node(s) for s in d_need_ancestors]
        while stack:
            node = stack.pop()
            rep = repr(node)
            if rep in d_implied_want_opened:
                # This is a deduc that we have already explored.
                continue
            d_implied_want_opened.add(rep)
            nodes[rep] = node
            next_vlp = None
            if node.libpath in known_dashgraphs:
                n = known_dashgraphs[node.libpath]
                if n:
                    next_vlp = repr(n)
            else:
                loader = DashgraphLoader({'libpath': node.libpath, 'vers': node.version.full})
                loader.do_require_csrf = False
                loader.process(raise_anticipated=True)
                dg = loader.get_response_field('dashgraph')
                dashgraphs[node.libpath] = dg
                di = dg["deducInfo"]
                parentpath = di["target_deduc"]
                if parentpath:
                    version = di["target_version"]
                    next_vlp = "@".join([parentpath, version])
            if next_vlp:
                next_node = nodes.get(next_vlp, vlpStr2Node(next_vlp))
                nodes[next_vlp] = next_node
                next_node.add_child(node)
                if next_vlp in d0:
                    # This is a deduc which is already present, hence so are all of its
                    # ancestors, so we need explore no further based on it, and do not add
                    # it to the stack. But we do want to record it under our root node.
                    opening_forest.add_child(next_node)
                else:
                    stack.append(next_node)
            else:
                # We hit a TLD, so there is no next node, but we do want a record
                # under our root node.
                opening_forest.add_child(node)
        return dashgraphs, opening_forest, d_implied_want_opened

    def step_050_open_and_close(self, d_implied_want_opened, d_re, d_implied_really_want_removed, current_forest, opening_forest):
        # We need to check whether `d_implied_want_opened` yields a well-defined mapping
        # from libpaths to version numbers. This can fail if it asks that a single
        # deduc be opened at more than one version, in which case we raise an exception.
        opening_pairs = [vlp.split("@") for vlp in d_implied_want_opened]
        opening_mapping = {}
        for lp, v in opening_pairs:
            if lp in opening_mapping:
                msg = f'Attempting to open deduc `{lp}` simulataneously at versions `{v}`'
                msg += f' and `{opening_mapping[lp]}`.'
                raise PfscExcep(msg, PECode.CONFLICTING_DEDUC_VERSIONS)
            opening_mapping[lp] = v
        # Are any deducs currently on board at the wrong version?
        existing_versions = current_forest.get_implied_full_version_mapping()
        wrong_version = {f'{k}@{v}' for k, v in existing_versions.items() if k in opening_mapping and v != opening_mapping[k]}
        # Now, there are three reasons to close something: (a) because we really do want to remove it,
        # (b) because we want to reload it and it is indeed currently present, or (c) because it is present
        # at the wrong version.
        to_close = d_implied_really_want_removed | d_re | wrong_version
        # But when the ISE removes any deduction, this also causes all descendant deducs to be removed.
        # Therefore we can minimize the set of deducs on which a decay operation actually need be performed.
        # We also transform it from a set into a list, for use by the ISE.
        L = current_forest.get_full_tree_lookup()
        fal = ForestAddressList(L[vlp] for vlp in to_close)
        to_close = [e.libpath for e in find_oldest_elements(fal)]
        # And finally we need to turn `d_implied_want_opened` into a list, sorted in topological order.
        # The next step is necessary because the `opening_forest` root node may have some children
        # representing deducs that are already on board. It needs their correct addresses.
        opening_forest.read_child_addresses_from_other_node(current_forest)
        # Really should make a copy of `L` and `update` _that_ (since otherwise we actually pollute
        # `current_forest`'s lookup) -- but this is the last use we make of it, so it doesn't matter.
        L.update(opening_forest.get_full_tree_lookup())
        nodes = sorted([L[vlp] for vlp in d_implied_want_opened], key=lambda node: node.address)
        to_open = [node.libpath for node in nodes]
        return to_open, to_close

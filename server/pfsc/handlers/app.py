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

import traceback
import json
from collections import defaultdict
from uuid import uuid4

from flask import render_template, url_for, current_app
from flask_login import current_user, logout_user

from config import HostingStance
from pfsc import check_config
import pfsc.constants
from pfsc.handlers import Handler
from pfsc.handlers.auth import _log_in_as_default_user_in_psm
from pfsc.session import get_csrf_from_session
from pfsc.build.repo import make_repo_versioned_libpath, parse_repo_versioned_libpath
from pfsc.permissions import check_is_psm
from pfsc.excep import PfscExcep, PECode
from pfsc.checkinput import (
    IType,
    is_defined,
    IseSideInfo,
    IseSplitInfo,
    IseActiveTabInfo,
    IseWidgetLinkInfo
)

from pfsc.contenttree import (
    AugmentedLibpath,
    TypeRequest,
    AnnoRequest,
    ChartRequest,
    SourceRequest,
    LocDesc,
    LocRef,
    TreeCode,
    build_forest_for_content,
    write_forest
)

class AugLpSeq:
    """
    Augmented Libpath Sequence

    Accepts a list of AugmentedLibpaths, as returned by the contenttree module.
    Processes this in order to compute the values for the `tcs` and `trees.trees`
    properties of an ISE state description.
    """

    def __init__(self, auglps, ati):
        """
        :param auglps: list of AugmentedLibpath instances
        :param ati: an IseActiveTabInfo instance
        """
        self.auglps = auglps
        self.active_tab_info = ati
        self.tc_lookup = {}
        self.tcs = []
        self.fstree_paths = []
        self.buildtree_paths = []

    def get_tcs(self):
        return self.tcs

    def get_tree_info(self):
        """
        Based on self.fstree_paths and self.buildtree_paths, describe all
          the tree nodes that are to be expanded.
        :return: a dictionary of the format of `trees.trees` in
          an ISE state description.
        """
        info = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        def make_rv_lp_p(rvlp):
            lp, v = parse_repo_versioned_libpath(rvlp)
            p = lp.split('.')
            rp = '.'.join(p[:3])
            rv = f'{rp}@{v}'
            return rv, lp, p
        for fp in self.fstree_paths:
            rv, lp, p = make_rv_lp_p(fp)
            nodeId = '/'.join(['.'] + p[3:])
            info[rv]['expand']['fsNodeIds'].append(nodeId)
        for bp in self.buildtree_paths:
            rv, lp, p = make_rv_lp_p(bp)
            info[rv]['expand']['buildNodeIds'].append(lp)
        return info

    def compute_content(self):
        tcs = defaultdict(lambda: defaultdict(list))

        # Record chart requests here iff they define their own location
        # (i.e. they do _not_ make a back ref).
        located_chart_reqs = []

        def record_request_info(req):
            g = req.group_num
            t = req.tab_num
            tcs[g][t] = req.type_descrip

        for alp in self.auglps:
            assert isinstance(alp, AugmentedLibpath)

            # Record tree requests
            if alp.makes_fstree_request():
                self.fstree_paths.append(alp.libpath)
            if alp.makes_buildtree_request():
                self.buildtree_paths.append(alp.libpath)

            # Any source requests?
            src_reqs = alp.get_source_requests()
            for req in src_reqs:
                assert isinstance(req, TypeRequest)
                record_request_info(req)

            # Any content requests?
            con_reqs = alp.get_content_requests()
            for req in con_reqs:
                if isinstance(req, ChartRequest):
                    n = req.get_back_ref()
                    if n is None:
                        # If a ChartRequest does _not_ make a backref, that means it
                        # is supposed to have defined its own location. That means it's
                        # to be recorded in our list of "located" chart requests.
                        located_chart_reqs.append(req)
                    else:
                        # If a ChartRequest _does_ make a backref, this reference should
                        # be a zero-based index into the list of "located" chart requests
                        # made so far.
                        try:
                            snowball = located_chart_reqs[n]
                        except IndexError:
                            msg = 'Bad chart request backref.'
                            raise PfscExcep(msg, PECode.BAD_CHART_REQ_BACKREF)
                        else:
                            snowball.add_copath(make_repo_versioned_libpath(req.libpath, req.version))
                else:
                    # For now at least, ChartRequests are the only kind of
                    # TypeRequests that can use back-references; all other
                    # types (at the moment, just AnnoRequest), must specify
                    # group and tab numbers, so are ready to be recorded.
                    record_request_info(req)

        # Finalize chart requests.
        gid_salt = f'-{uuid4()}'
        for req in located_chart_reqs:
            # Forest group ids are salted so that if the app is loaded in two
            # different windows, using the exact same URL args, corresponding
            # forests in those windows do not wind up unintentionally linked.
            req.extend_gid(gid_salt)
            req.finalize_libpaths()
            record_request_info(req)

        self.tc_lookup = tcs

    def compute_tcs_array(self):
        """
        This method should be called only after calling `self.compute_content()`.
        It transforms the tc_lookup into the tcs array, whose format is:

            [
                {
                    tabs: <object[]>,
                    activeTab: <int>
                }
            ]

        In the process, it checks that the array is well-formed, in the sense that
        there are no "missing" indices.
        """
        def raiseExcep():
            msg = 'Content descrip involves gaps in tab or group indices.'
            raise PfscExcep(msg, PECode.MALFORMED_CONTENT_FOREST_DESCRIP)

        tc_indices = sorted(self.tc_lookup.keys())
        if tc_indices != list(range(len(tc_indices))): raiseExcep()

        tcs = []
        for i in tc_indices:
            tabs = self.tc_lookup[i]
            tab_indices = sorted(tabs.keys())
            if tab_indices != list(range(len(tab_indices))): raiseExcep()

            tab_infos = [tabs[j] for j in tab_indices]

            tcs.append({
                'tabs': tab_infos,
                'activeTab': self.active_tab_info.get_active_tab_for_group(i)
            })

        self.tcs = tcs

def make_notes_vlp(tab):
    return make_repo_versioned_libpath(tab['libpath'], tab['version'])

def make_source_vmp(tab):
    # The `EditManager.writeStateInfo()` method in pfsc-ise returns an object
    # that defines a `libpath` field, not a `modpath` field; however, the code
    # here (as late as 220625) was expecting a `modpath` field. Rather than try
    # to track down right now whether there are any lingering cases where
    # `modpath` is given instead of `libpath`, we accept both. No harm.
    libpath = tab.get('modpath') or tab.get('libpath')
    return make_repo_versioned_libpath(libpath, tab['version'])

def make_chart_vlps(tab):
    versions = tab['versions']
    deducs = tab['on_board']
    return [make_repo_versioned_libpath(lp, versions[lp]) for lp in deducs]

class StateArgMaker(Handler):
    """
    Transform an ISE state description into a set of URL args that can be used
    upon app load to restore that state.

    This handler is not going to do much input checking at all. There is no reason
    for the user to be manually supplying any values, so there is no reason to
    respond with helpful error messages. If anything is malformed, we're simply
    going to fail.

    And even if we don't fail, we may return a set of inconsistent URL args.
    Garbage in, garbage out.
    We leave it to the AppLoader class to detect and respond to such inconsistencies
    at app load time. Again, since this handler is only intended for internal use,
    there is no reason to check consistency here as well as there.

    Another way to think about this is that really the operation performed by
    this handler could have just been done on the client side. Maybe at some
    some point we should be doing it that way. But we wanted to reuse all the
    infrastructure existing here on the server side, which we use to go in the
    opposite direction, i.e. to parse URL args and turn them into a state description.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'state': {
                    'type': IType.STR
                }
            }
        })

    def check_permissions(self):
        pass

    @staticmethod
    def give_up(extra_msg=None):
        msg = 'Malformed state description'
        if extra_msg is not None:
            msg += f'\n{extra_msg}'
        msg += f'\n{traceback.format_exc()}'
        raise PfscExcep(msg, PECode.MALFORMED_ISE_STATE)

    def confirm(self, state):
        try:
            assert len(state) < 16384  # arbitrary limit to prevent abuse
            state = json.loads(state)
        except (AssertionError, json.decoder.JSONDecodeError) as e:
            self.give_up(e)
        else:
            self.fields['state'] = state

    @staticmethod
    def trees_to_rvlps(trees):
        """
        :param trees: The `trees.trees` value in an ISE state description.
        :return: Two sets B and F of repo-versioned libpaths, naming the nodes
          we want expanded in the build, resp. filesystem trees.
        """
        B, F = set(), set()
        for repopathv, info in trees.items():
            p = repopathv.split("@")
            rvrp = f'{p[0]}@{p[1].replace(".", "_")}'
            expand = info.get('expand', {})
            for nodeId in expand.get('fsNodeIds', []):
                f = nodeId.split('/')
                f[0] = rvrp
                F.add('.'.join(f))
            for nodeId in expand.get('buildNodeIds', []):
                b = nodeId.split('.')
                b[2] = rvrp
                B.add('.'.join(b[2:]))
        return B, F

    def process_tcs(self, args, trees, tcs, activeTcIndex, widgetPanes):
        """
        This method is responsible for setting the 'a' and 'c' properties
        of the args dict.

        :param args: the dictionary of URL args it is this class's purpose to build
        :param trees: as in the given state description
        :param tcs: as in the given state description
        :param activeTcIndex: as in the given state description
        :param widgetPanes: as in the given state description
        :return: nothing; args is modified in-place
        """
        # We want the sets A, C, and P of all versioned libpaths for which annotations,
        # charts, and paths are requested; and we want the set S of all versioned _module_
        # paths for which sources are requested. Here we work with "repo-versioned" libpaths,
        # i.e. those of the form `host.user.repo@version.remainder`.
        A, C, S = set(), set(), set()
        B, F = self.trees_to_rvlps(trees)
        for tc in tcs:
            for tab in tc['tabs']:
                ty = tab['type']
                if ty == "NOTES":
                    A.add(make_notes_vlp(tab))
                elif ty == "SOURCE":
                    S.add(make_source_vmp(tab))
                elif ty == "CHART":
                    C.update(set(make_chart_vlps(tab)))

        # L will be the set of all versioned libpaths for which we must make some request.
        # It starts out as this:
        L = A | C | B | F
        # However, for source modpaths we also need a mapping to some libpath
        # in L for which this source can be requested, and we enlarge L as necessary.
        src_vmp2vlp = {}
        sortedL = sorted(L)
        i, N = 0, len(sortedL)
        for vmp in sorted(S):
            # A versioned libpath vlp will suffice if it either equals vmp or has vmp as
            # a proper prefix. Since the lists are sorted lexicographically,
            # there is a libpath with this property iff the first one not less
            # than vmp has this property. This is so because '.' comes before any
            # of the alphanumeric or underscore chars that may occur in the middle
            # of a libpath segment.
            while i < N and sortedL[i] < vmp:
                i += 1
            vlp = sortedL[i] if i < N else ''
            if vlp == vmp or vlp.startswith(vmp + '.'):
                src_vmp2vlp[vmp] = vlp
            else:
                L.add(vmp)
                src_vmp2vlp[vmp] = vmp

        alps = {}
        for vlp in L:
            alps[vlp] = AugmentedLibpath(vlp, [])

        active_tabs = []
        vlp2chartLocs = defaultdict(list)
        # In order to set up widget group control mappings later, we'll need a
        # lookup where we can obtain one (g, t) location where a given annotation,
        # identified by its repo-versioned libpath, can be found.
        anno_panes = {}
        forest_groups = []
        total_tab_count = 0
        for g, tc in enumerate(tcs):
            active_tabs.append(tc.get('activeTab', 0))
            for t, tab in enumerate(tc['tabs']):
                total_tab_count += 1
                ty = tab['type']

                if ty == "NOTES":
                    vlp = make_notes_vlp(tab)
                    # Again, the annotation for a given vlp may indeed be open in more
                    # than one (g, t) location, but it doesn't matter here; we just need
                    # _one_ location where that anno can be found.
                    anno_panes[vlp] = (g, t)
                    loc = LocDesc('a', {'g': g, 't': t})
                    alp = alps[vlp]
                    alp.content_reqs.append(AnnoRequest(vlp, loc))

                elif ty == "SOURCE":
                    vmp = make_source_vmp(tab)
                    codes = {'g': g, 't': t}

                    sr = tab.get('sourceRow')
                    fvr = tab.get('firstVisibleRow')
                    L = sr if sr is not None else fvr + 1 if fvr is not None else None
                    if L is not None:
                        codes["L"] = L

                    loc = LocDesc('s', codes)
                    vlp = src_vmp2vlp[vmp]
                    alp = alps[vlp]
                    alp.source_reqs.append(SourceRequest(vlp, loc))

                elif ty == "CHART":
                    codes = {'g': g, 't': t}

                    coords = tab.get('coords')
                    if coords is not None:
                        for i, c in enumerate('xyz'):
                            codes[c] = coords[i]

                    layout_method_name = tab.get('layout')
                    if layout_method_name is not None:
                        layout_method_code = ChartRequest.get_layout_method_code(layout_method_name)
                        # If `None`, method name was unknown.
                        # If 0, this is the default value, and we omit the code for sake of brevity.
                        if layout_method_code not in {None, 0}:
                            codes["L"] = layout_method_code

                    ordSel = tab.get('ordSel')
                    if ordSel is not None:
                        codes['o'] = ordSel

                    forest_gid = tab.get('gid')
                    if forest_gid is None or forest_gid not in forest_groups:
                        G = len(forest_groups)
                        forest_groups.append(forest_gid)
                    else:
                        G = forest_groups.index(forest_gid)
                    # For compression, we omit group #0. It is implied.
                    if G > 0:
                        codes['G'] = G

                    loc = LocDesc('c', codes)
                    for vlp in make_chart_vlps(tab):
                        vlp2chartLocs[vlp].append(loc)

        if total_tab_count > 0:
            args['a'] = f'{",".join(map(str,active_tabs))};{activeTcIndex}'

        next_index = 0
        # We go in lexicographic order through the versioned libpaths for which charts
        # are requested. The first versioned libpath to lie at any location will include
        # that location's full description among its codes; subsequent versioned libpaths
        # lying at this location will use backrefs.
        # Later, when we finally build a forest out of all of our augmented
        # libpaths, we will again go in lexicographic order, and this will ensure
        # that the chart requests in particular occur in the intended order, so
        # that all backrefs make sense.
        for vlp in sorted(vlp2chartLocs.keys()):
            alp = alps[vlp]
            locs = vlp2chartLocs[vlp]
            for loc in locs:
                if loc.index is None:
                    loc.index = next_index
                    next_index += 1
                else:
                    loc = LocRef(loc.index)
                alp.content_reqs.append(ChartRequest(vlp, loc))

        for vlp in F:
            alp = alps[vlp]
            alp.fstree_code = TreeCode('f', None)
        for vlp in B:
            alp = alps[vlp]
            alp.buildtree_code = TreeCode('b', None)

        built_alps = []
        for vlp in sorted(alps.keys()):
            alp = alps[vlp]
            alp.build_codes()
            built_alps.append(alp)

        forest = build_forest_for_content(built_alps)
        args['c'] = write_forest(forest)

        widget_link_codes = []
        for k, v in widgetPanes.items():
            vlp, widget_type, group_name = k.split(":")
            sg, st = anno_panes[vlp]
            tg, tt = v.split(":")
            widget_link_codes.append(f'{sg},{st}-{widget_type}.{group_name}-{tg},{tt}')
        if widget_link_codes:
            args['wl'] = ';'.join(widget_link_codes)

    def process_content(self, args, trees, content):
        """
        This method is responsible for setting the 'sp' and 'wl' properties
        of the args dict; it also initiates the call to the method that handles
        the 'a' and 'c' properties.

        :param args: the dictionary of URL args it is this class's purpose to build
        :param trees: as in the given state description
        :param content: as in the given state description
        :return: nothing; args is modified in-place
        """
        struct = content.get('tctStructure')
        sizes = content.get('tctSizeFractions')
        if struct is not None and sizes is not None:
            assert(len(struct) < 128)  # arbitrary limit to prevent abuse
            sizes = [round(100*s) for s in sizes]
            struct.reverse()  # reverse for popping off back
            sizes.reverse()
            sp = ''
            while struct:
                c = struct.pop()
                sp += c
                if c in "VH":
                    p = sizes.pop()
                    # For brevity, omit size if it is the default value of 50.
                    if p != 50:
                        sp += str(p)
            # If sp is just "L", we don't need an 'sp' arg at all.
            if sp != "L":
                # If sp is different from "L", we can trim trailing L's:
                sp = sp.strip("L")
                args['sp'] = sp

        tcs = content.get('tcs')
        if tcs is not None:
            activeTcIndex = content.get('activeTcIndex', 0)
            widgetPanes = content.get('widgetPanes', {})
            self.process_tcs(args, trees, tcs, activeTcIndex, widgetPanes)

    def go_ahead(self, state):
        """
        Here we handle the 'sd' property of the args dict.
        We also initiate the call to the `process_content` method that
        handles other properties.
        """
        args = {}
        try:
            sidebar = state.get('sidebar')
            if sidebar is not None:
                w = sidebar.get('width', 200)
                v = sidebar.get('isVisible', True)
                sd = str(w)
                if not v:
                    sd = 'c' + sd
                args['sd'] = sd

            repos = state.get('trees', {})
            tree_tab = repos.get('tab')
            if tree_tab in ['fs', 'build']:
                args['tt'] = tree_tab[0]
            trees = repos.get('trees', {})

            content = state.get('content', {})
            self.process_content(args, trees, content)
            j_args = json.dumps(args)
        except (ValueError, TypeError, IndexError, AttributeError, AssertionError) as e:
            self.give_up(e)
        else:
            self.set_response_field('args', j_args)


def logins_are_possible():
    """
    Say whether there is any way to log in, under the current configuration.
    """
    return any(
        current_app.config[v] for v in [
            "ALLOW_GITHUB_LOGINS",
            "ALLOW_BITBUCKET_LOGINS",
            "ALLOW_TEST_REPO_LOGINS",
        ]
    )


class AppLoader(Handler):
    """
    Load the one-page ISE app.
    """

    def __init__(self, request_info):
        Handler.__init__(self, request_info)
        # Mustn't require a CSRF check when loading the app, since it's the
        # app load that sets it in the first place!
        self.do_require_csrf = False
        # We will record the ISE state that we compute.
        # This is useful for testing.
        self.ISE_state = {}

    def check_input(self):
        # At present this Handler class does not accept any arguments in which
        # errors should derail the entire process. We want the app to load,
        # whether or not any optional arguments are malformed.
        pass

    def secondary_check_input(self):
        # We will check for optional arguments, but will do so in a controlled
        # manner, so that errors are reported to the client side, but so that the
        # app still loads.
        self.check({
            "OPT": {
                # theme
                'th': {
                    'type': IType.STR,
                    'values': ['l', 'd']
                },
                # zoom
                'z': {
                    'type': IType.INTEGER,
                    'min': 50,
                    'max': 200,
                    'divisors': [10]
                },
                # sidebar
                'sd': {
                    'type': IType.ISE_SIDE
                },
                # tree tab
                'tt': {
                    'type': IType.STR,
                    'values': ['f', 'b']
                },
                # splits
                'sp': {
                    'type': IType.ISE_SPLIT
                },
                # content
                'c': {
                    'type': IType.CONTENT_FOREST
                },
                # active tabs
                'a': {
                    'type': IType.ISE_ACTIVE
                },
                # widget links
                'wl': {
                    'type': IType.DLIST,
                    'delimiter': ';',
                    'itemtype': {
                        'type': IType.ISE_WIDGET_LINK
                    }
                }
            }
        })

    def check_permissions(self):
        pass

    def confirm(self):
        pass

    def go_ahead(self):
        self.ISE_state = self.compute_ISE_state()
        html = self.write_html(self.ISE_state)
        self.set_response_field('html', html)
        self.handle_psm_user_state()

    @staticmethod
    def handle_psm_user_state():
        """
        When the app is configured in personal server mode, the client side
        offers no "User" menu with which to log in/out. Instead, the user
        should always be logged in as the "default user". (While much of the
        app's functionality checks the PSM setting directly, some things do
        require that the user actually be logged in as a user, e.g. recording
        of NOTES edges in the GDB.)

        Besides ensuring the user is logged _in_ as the default user when
        configured in PSM, this method also handles the unusual case that can
        arise during development, in which the server _was_ configured in PSM
        but is no more, and there is still a valid, signed Flask session cookie
        in the browser saying the user is the default user.
        """
        if check_is_psm():
            _log_in_as_default_user_in_psm()
        elif current_user.is_authenticated and current_user.is_the_default_user():
            logout_user()

    @staticmethod
    def compute_content(auglps, sp, a, wl, tree_info):
        """
        Compute the `content` part of the ISE state description.

        :param auglps: list of AugmentedLibpaths
        :param sp: an IseSplitInfo or undefined
        :param a: an IseActiveTabInfo or undefined
        :param wl: a list of IseWidgetLinkInfos or undefined
        :param tree_info: a dict which we will populate as a side-effect, with
            all node IDs requested to be expanded in the fs and build tree views
        :return: dict that can be set as the value of the `content` property in
          the ISE state description.
        """
        content = {}

        if is_defined(sp):
            assert isinstance(sp, IseSplitInfo)
            content['tctStructure'] = sp.structure
            content['tctSizeFractions'] = sp.size_fracs
        else:
            content['tctStructure'] = ["L"]
            content['tctSizeFractions'] = []

        numTCs = content['tctStructure'].count("L")

        ati = a if is_defined(a) else IseActiveTabInfo()

        n = ati.get_active_group()
        content['activeTcIndex'] = n if 0 <= n < numTCs else 0

        alp_seq = AugLpSeq(auglps, ati)
        alp_seq.compute_content()
        alp_seq.compute_tcs_array()
        tcs = alp_seq.get_tcs()
        # If there is more than one tab container, then it's an error for any
        # of them to be empty. (When exactly 1, it's okay.)
        if len(tcs) != numTCs > 1:
            msg = 'There is an empty split.'
            raise PfscExcep(msg, PECode.MALFORMED_CONTENT_FOREST_DESCRIP)
        content['tcs'] = tcs

        tree_info.update(alp_seq.get_tree_info())

        if is_defined(wl):
            widgetPanes = {}
            for link in wl:
                assert isinstance(link, IseWidgetLinkInfo)
                try:
                    sg, st = link.source
                    source_content = tcs[sg]['tabs'][st]
                    notes_vlp = make_notes_vlp(source_content)
                    tg, tt = link.target
                    # Access the target content just to test that the indices are valid.
                    target_content = tcs[tg]['tabs'][tt]
                except (IndexError, KeyError):
                    msg = f'Bad widget link: "{link}"'
                    raise PfscExcep(msg, PECode.MALFORMED_ISE_WIDGET_LINK_CODE)
                else:
                    k = f"{notes_vlp}:{link.type_}:{link.group}"
                    widgetPanes[k] = f"{tg}:{tt}"
            content['widgetPanes'] = widgetPanes

        return content

    def compute_ISE_state(self):
        # These properties are defined, regardless of any optional arguments
        # that may have been passed.
        state = {
            'CSRF': get_csrf_from_session(supply_if_absent=True),
            'autoSaveDelay': current_app.config["PFSC_AUTOSAVEDELAY"],
            'reloadFromDisk': current_app.config["PFSC_RELOADFROMDISK"],
            'saveAllOnAppBlur': bool(current_app.config["PFSC_SAVEALLONAPPBLUR"]),
            'enablePdfProxy': bool(current_app.config["PFSC_ENABLE_PDF_PROXY"]),
            'offerPdfLibrary': bool(current_app.config["ISE_OFFER_PDFLIB"]),
            'allowWIP': bool(current_app.config["ALLOW_WIP"]),
            'appUrlPrefix': current_app.config["APP_URL_PREFIX"],
            # `devMode` used to just control whether `window.pfscisehub` would be defined, but
            # now we always do that, since it is needed by code running under Pyodide.
            # We keep `devMode` in case it is useful.
            'devMode': bool(current_app.config["ISE_DEV_MODE"]),
            'personalServerMode': check_is_psm(),
            'ssnrAvailable': current_app.config["OFFER_SERVER_SIDE_NOTE_RECORDING"],
            'hostingByRequest': current_app.config["DEFAULT_HOSTING_STANCE"] == HostingStance.BY_REQUEST,
            'tosURL': current_app.config.get("TOS_URL"),
            'tosVersion': current_app.config.get("TOS_VERSION"),
            'prpoURL': current_app.config.get("PRPO_URL"),
            'prpoVersion': current_app.config.get("PRPO_VERSION"),
            'loginsPossible': logins_are_possible(),
            'pdfjsURL': url_for('static', filename='pdfjs/vVERSION/web/viewer.html'),
        }

        if current_app.config["IS_OCA"]:
            with open(current_app.config["OCA_VERSION_FILE"]) as f:
                v = f.read().strip()
            state['OCA_version'] = v

        # We make an attempt to process optional arguments.
        # If there are any errors, we simply give up on that part of the
        # state definition process, and record an error report that the
        # ISE can find after the app loads.
        try:
            self.secondary_check_input()
            requested_state = self.withfields(self.compute_requested_ISE_state)
        except PfscExcep as pe:
            state['err_lvl'] = pe.code()
            state['err_msg'] = pe.public_msg()
        else:
            state['err_lvl'] = 0
            state.update(requested_state)

        return state

    def compute_requested_ISE_state(self, th, z, sd, tt, sp, c, a, wl):
        state = {}

        if is_defined(th):
            state['theme'] = {'l': 'light', 'd': 'dark'}[th]

        if is_defined(z):
            state['zoom'] = z

        if is_defined(sd):
            assert isinstance(sd, IseSideInfo)
            state['sidebar'] = {
                'isVisible': not sd.collapsed,
                'width': sd.width
            }

        trees = {}
        if is_defined(tt):
            trees['tab'] = {
                'f': 'fs', 'b': 'build',
            }[tt]
        tree_info = {}
        if is_defined(c):
            state['content'] = self.compute_content(c, sp, a, wl, tree_info)
        if tree_info:
            trees['trees'] = tree_info
        if trees:
            state['trees'] = trees

        return state

    @staticmethod
    def write_html(ISE_state):
        css = []

        ise_bundle_filename = f'ise.bundle{".min." if check_config("ISE_SERVE_MINIFIED") else "."}js'
        ise_vers = check_config("ISE_VERSION")

        js = [
            # the ISE bundle
            (
                url_for('static', filename=f'ise/v{ise_vers}/{ise_bundle_filename}')
                if check_config("ISE_SERVE_LOCALLY") else
                f'https://cdn.jsdelivr.net/npm/@proofscape/pise-client@{ise_vers}/dist/ise/{ise_bundle_filename}'
            ),

            # If we want to use pdfjs outside of iframes, might need sth like this:
            # url_for('static', filename='pdfjs/build/pdf.js'),
            # url_for('static', filename='pdfjs/web/pdf_viewer.js'),
        ]

        other_scripts = {
            'mathjax': (
                url_for('static', filename='mathjax/vVERSION/tex-svg.js')
                if check_config("MATHJAX_SERVE_LOCALLY") else
                'https://cdn.jsdelivr.net/npm/mathjax@VERSION/es5/tex-svg.js'
            ),
            'elkjs': (
                url_for(
                    'static',
                    filename=f'elk/vVERSION/elk{"-api" if check_config("ELK_DEBUG") else ".bundled"}.js'
                )
                if check_config("ELKJS_SERVE_LOCALLY") else
                'https://cdn.jsdelivr.net/npm/elkjs@VERSION/lib/elk.bundled.js'
            ),
            # If using KLay instead of ELK:
            # url_for('static', filename='klay/klay.js'),
        }

        local_whl_filenames = {
            "pfsc-util": "pfsc_util-VERSION-py3-none-any.whl",
            "typeguard": "typeguard-VERSION-py3-none-any.whl",
            "displaylang": "displaylang-VERSION-py3-none-any.whl",
            "displaylang-sympy": "displaylang_sympy-VERSION-py3-none-any.whl",
            "lark": "lark067-VERSION-py2.py3-none-any.whl",
            "pfsc-examp": "pfsc_examp-VERSION-py3-none-any.whl",
        }

        pyodide_serve_locally = check_config("PYODIDE_SERVE_LOCALLY")
        mathworker_bundle_filename = f'mathworker.bundle{".min." if check_config("MATHWORKER_SERVE_MINIFIED") else "."}js'

        examp_config = {
            "vars": {
                "MAX_SYMPY_EXPR_LEN": check_config("MAX_SYMPY_EXPR_LEN"),
                "MAX_SYMPY_EXPR_DEPTH": check_config("MAX_SYMPY_EXPR_DEPTH"),
                "MAX_DISPLAY_BUILD_LEN": check_config("MAX_DISPLAY_BUILD_LEN"),
                "MAX_DISPLAY_BUILD_DEPTH": check_config("MAX_DISPLAY_BUILD_DEPTH"),
            },

            "mathworkerURL": url_for('static', filename=f'ise/v{ise_vers}/{mathworker_bundle_filename}'),

            "pyodideIndexURL": (
                url_for('static', filename='pyodide/vVERSION')
                if pyodide_serve_locally else
                'https://cdn.jsdelivr.net/pyodide/vVERSION/full/'
            ),

            "micropipInstallTargets": {
                k: url_for('static', filename=f'whl/{v}') for k, v in local_whl_filenames.items()
            } if pyodide_serve_locally else {
                'pfsc-examp': 'pfsc-examp==VERSION'
            },

            "micropipNoDeps": pyodide_serve_locally,
        }

        html = render_template(
            'ise.html',
            css=css,
            js=js,
            title="Proofscape ISE",
            ISE_state=json.dumps(ISE_state, indent=4),
            examp_config=json.dumps(examp_config, indent=4),
            other_scripts=json.dumps(other_scripts, indent=4),
        )
        return html

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

"""
These classes form the internal representation of a proofscape
module, as defined in a .pfsc file.
"""

import re, traceback
from collections import defaultdict

import mistletoe
from markupsafe import Markup

import pfsc.util
from pfsc.excep import PfscExcep, PECode
from pfsc.lang import meson as meson
from pfsc.build.repo import get_repo_part
from pfsc.build.lib.libpath import libpath_is_trusted
from pfsc.gdb import get_graph_reader
from pfsc.lang.objects import PfscObj, Enrichment, PfscDefn
from pfsc import util
from pfsc.constants import IndexType
from pfsc.lang.comparisons import Comparison
from pfsc.lang.doc import doc_ref_factory
from pfsc.lang.nodelabels import NodeLabelRenderer, ll, writeNodelinkHTML


class NodeLikeObj(PfscObj):
    """
    On one level, we make a distinction between Deductions, SubDeductions, and
    Nodes. On another level -- the level seen by Meson scripts, dashgraphs, and
    by the pfsc-moose project -- all these things are just different types of
    "nodes", i.e. things that are the endpoints of edges.

    The `NodeLikeObj` class is a place to define functionality that is common
    to all these "node-like objects".

    (Note: This class was introduced relatively late, so there may still be
    some common functionality that should be refactored and put here.)
    """

    def __init__(self):
        # Some subclasses (like `Deduction`) have multiple inheritance; others
        # (like `Node`) do not. So we take care to do our superclass init only
        # if it hasn't been done already.
        if not hasattr(self, 'items'):
            PfscObj.__init__(self)
        self.comparisons = []

    def getComparisons(self):
        return self.comparisons

    def resolveComparisons(self):
        def visit(item):
            if isinstance(item, NodeLikeObj):
                item._resolveOwnComparisons()
        self.recursiveItemVisit(visit)

    def _resolveOwnComparisons(self):
        cf_list = self.get('cf')
        if cf_list:
            if not isinstance(cf_list, list):
                msg = f'The `cf` field for {self.libpath} is malformed.'
                msg += ' Should be a list.'
                raise PfscExcep(msg, PECode.MALFORMED_CF)
            self.comparisons.extend([
                Comparison(self, cf_raw) for cf_raw in cf_list
            ])

    def add_comparisons_to_dashgraph(self, dg):
        if self.comparisons:
            dg['cf_out'] = [{
                'libpath': cf.target_libpath,
                'version': cf.target_version,
            } for cf in self.comparisons]


class Deduction(Enrichment, NodeLikeObj):

    def __init__(self, name, target_paths, rdef_paths, module=None):
        """
        name:            str     e.g. 'Thm' or 'Pf'
        target_paths:    list(str)   target paths from deduc preamble
        rdef_paths:      list(str)   rdef paths from deduc preamble
        module:          PfscModule object to which this deduc belongs
        """
        Enrichment.__init__(self, 'deduction')
        NodeLikeObj.__init__(self)
        self.parent = module
        self.name = name
        self.hname = None # "human-readable name"
        self.targets = []
        self.targetDeduc = None
        self.graph = None
        self.nodeSeq = []
        self.subdeducSeq = []
        self.ghostNodes = []
        self.specialNodes = []
        self._trusted = None
        self.cloneOf = None

        self.rdef_paths = rdef_paths
        self.runningDefs = []

        if not module: return
        self.find_and_store_targets(target_paths, module, all_nodes=True, common_deduc=True)

        # FIXME: isn't this redundant?
        #   Ans: It appears not, because when we call `buildGraph` these nodes appear
        #   as if they were "declared locally", and so we do not make ghost nodes for
        #   them there. But this seems like the wrong approach. Why not just let all ghost
        #   nodes be made during `buildGraph`?
        #   I am tentatively commenting this out (30 May 2019) and we'll see how we do...
        # Create GhostNodes for targets.
        #for ts in target_paths:
        #    G = self.createGhosts(ts)
        #    self.ghostNodes.append(G)

    @property
    def trusted(self):
        if self._trusted is None:
            assert (libpath := self.getLibpath()) is not None
            self._trusted = libpath_is_trusted(libpath)
        return self._trusted

    def getGhostNodes(self):
        return self.ghostNodes

    def getSpecialNodes(self):
        return self.specialNodes

    def getNodesAndSubdeducs(self):
        return self.nodeSeq + self.subdeducSeq

    def getChildren(self):
        return self.getNodesAndSubdeducs() + self.getGhostNodes() + self.getSpecialNodes()

    def getGraph(self):
        return self.graph

    def getFirstRowNum(self):
        return None if self.textRange is None else self.textRange[0]

    def get_index_type(self):
        return IndexType.DEDUC

    def listNativeNodesByLibpath(self, nodelist):
        """
        Populate a list with the libpath of every node and/or subdeduc contained
        under this deduction, recursively.
        :param nodelist: the list you want populated
        :return: nothing
        """
        items = self.nodeSeq + self.subdeducSeq
        for item in items:
            item.listNativeNodesByLibpath(nodelist)

    def getAllNativeNodes(self, nodelist):
        """
        Populate a list with every node and/or subdeduc contained
        under this deduction, recursively.
        :param nodelist: the list you want populated
        :return: nothing
        """
        items = self.nodeSeq + self.subdeducSeq
        for item in items:
            item.getAllNativeNodes(nodelist)

    def createGhosts(self, dotpath):
        """
        dotpath: a string such as gives a target in a deduc
                 preamble, or refers to an outside node in
                 a Meson script, e.g. 'Thm.C'

        We create a ghost node for each part of the dotpath.
        They are nested under this deduction automatically
        by the GhostNode.__init__ method.

        Return the /last/ GhostNode created.
        """
        module = self.getModule()
        parts = dotpath.split('.')
        path = ''
        parent = self
        G = None
        for name in parts:
            if path: path += '.' 
            path += name
            # Does the parent already have a GhostNode by this name?
            # This case can arise e.g. when a proof cites two results from a single module.
            # Then, when making a ghost for the second result, we already have a ghost
            # representing the module (and within it, a ghost representing the first result).
            # We don't want to now overwrite the module ghost, since then we will lose our
            # ghost of the first result!
            G = parent.get(name)
            if G is None:
                # No ghost yet. So need to make one.
                R = module[path]
                if not R:
                    # This case should never arise.
                    msg = 'Named object %s '%path
                    msg += 'in module %s not defined.'%module.libpath
                    raise PfscExcep(msg, PECode.MODULE_DOES_NOT_CONTAIN_OBJECT)
                G = GhostNode(R, parent, name)
            # Now the GhostNode becomes the parent object, for the next iteration.
            parent = G
        # After the final iteration, the deepest GhostNode (the one for the full dotpath given)
        # is the one we now want to return.
        return G

    def getXpansAvailPresentationInfo(self, major, filter_by_repo_permission=True):
        infos = get_graph_reader().get_enrichment(
            self.getLibpath(),
            major,
            filter_by_repo_permission=filter_by_repo_permission
        )
        return infos

    def getNodeType(self):
        return 'deduc'

    def getDeductionLibpath(self):
        """
        Intended for use by Subdeducs, to determine the libpath of
        the Deduction to which they belong, but we need this method
        to be defined for Deductions too, so declare it here.
        """
        return self.getDeduction().getLibpath()

    def getTargetDeduction(self):
        """
        :rtype : Deduction
        """
        return self.targetDeduc

    def getTargetDeductionLibpath(self):
        """
        Convenience method. Returns libpath to target deduction,
        or None if none.
        """
        td = self.getTargetDeduction()
        if td:
            libpath = td.getLibpath()
        else:
            libpath = None
        return libpath

    def getTargetVersion(self):
        """
        Return the version string for the targeted deduc, or None if none.
        """
        td = self.getTargetDeduction()
        if td is None:
            return None
        target_repo = get_repo_part(td.libpath)
        if target_repo == get_repo_part(self.libpath):
            return self.getVersion()
        return self.getDependencies()[target_repo]

    def getTargetSubdeduc(self):
        """
        The purpose here is to figure out inside what box this
        deduction's graph should be drawn.
        The "target subdeduction" is the NCA (nearest common ancestor)
        of all the targets of this deduction, within the target
        deduction.
        """
        ts = None
        if self.targets:
            SAS = [t.getSubdeducAncestorSeq() for t in self.targets]
            ts = SAS[0][0]
            ptr = 0
            m = min([len(sas) for sas in SAS])
            while ptr + 1 < m:
                ptr += 1
                s = SAS[0][ptr]
                allsame = True
                for sas in SAS[1:]:
                    allsame &= sas[ptr] == s
                    if not allsame: break
                if allsame: ts = s
                else: break
        return ts

    def getTargetSubdeducLibpath(self):
        ts = self.getTargetSubdeduc()
        if ts:
            libpath = ts.getLibpath()
        else:
            libpath = None
        return libpath

    def resolve_objects(self):
        """
        This is a place to do anything that has to do with resolving libpaths to
        actual objects, and which should be carried out after the whole deduc definition
        has been parsed.
        """
        self.find_rdefs()
        self.resolve_node_targets()
        self.link_cases()
        self.resolveDocRefs()
        self.resolveComparisons()

    def resolveDocRefs(self):
        default_doc_info = self.get('docInfo', lazy_load=False)
        if default_doc_info is not None and not isinstance(default_doc_info, dict):
            # It will be a common error to pass a string here, instead of a libpath,
            # which would resolve to an actual doc info dictionary.
            msg = f'docInfo in deduc "{self.libpath}" should be a dictionary'
            raise PfscExcep(msg, PECode.INPUT_WRONG_TYPE)

        def visit(item):
            if isinstance(item, Node):
                item.resolveDocRefs(default_doc_info)

        self.recursiveItemVisit(visit)

    def find_rdefs(self):
        """
        Find and resolve any running definitions named in the preamble of this deduction.

        @return: nothing. We just store the rdefs (i.e. the resolved PfscDefn objects)
                 under our self.runningDefs field.
        """
        for path in self.rdef_paths:
            rdef = self.resolve_object(
                path, self.parent,
                self_typename=self.typename, obj_descrip='rdef', allowed_types=[PfscDefn]
            )
            self.runningDefs.append(rdef)

    def link_cases(self):
        """
        This method partitions all supp nodes declared within this deduction (or any of
        its subdeductions) into sets of alternative cases.

        The result is that each Supp instance is informed of its own set of alternatives.

        A step like this is necessary so that we can allow the
        user to declare the alternatives in just one of the case declarations for each
        set of alternatives (i.e. so that the user need not repeat the same information
        in multiple places).
        """
        # That the supp nodes are to be _partitioned_ means that we are dealing with
        # an _equivalence relation_, i.e. one which is reflexive, symmetric, and transitive.
        # The work we have to do here consists of two main parts, the first of which
        # deals with symmetry, and the second of which deals with transitivity.

        # In the first part, we must represent the set of all supp nodes as a graph, with each
        # node represented by its absolute libpath, and where two nodes are neighbors iff they
        # are alternatives of one another.
        #
        # Because of the way users are expected to use the
        # pfsc syntax, however, it will generally be the case that among a set of alternatives,
        # only one of them knows about the others. In other words, we must account for the
        # _symmetry_ of this relation, which generally is _not_ made explicit in the text
        # of a given module.
        #
        # For example, two supp nodes may be defined as:
        #
        #   supp R versus S { ... }
        #   supp S { ... }
        #
        # so that R knows about S, but S does not yet know about R. We must correct for that
        # here.

        # Represent the graph as a lookup, in which each node (represented by its abs libpath)
        # points to the set of all of its neighbors.
        g = defaultdict(set)
        # Make a lookup for all supp nodes (in this deduc or any subdeduc, recursively), by libpath.
        s = {}
        self.get_all_supp_nodes_rec(s)
        # Iterate over all supp nodes.
        for lp, node in s.items():
            # Get the supp node's set of alternatives (which are other supp nodes)
            alts = node.get_alternates()
            # Iterate over the alternatives.
            for alt in alts:
                alt_lp = alt.getLibpath()
                # Let each node know that it has the other as a neighbor.
                g[lp].add(alt_lp)
                g[alt_lp].add(lp)

        # In the second part, we must account for _transitivity_. For example, three supp nodes
        # could be defined as:
        #
        #   supp R versus S { ... }
        #   supp S versus T { ... }
        #   supp T { ... }
        #
        # in which case R would not know it is connected to T. In order to catch such cases,
        # we now compute the connected components of the graph.

        # Compute the connected components, with each node represented by its libpath.
        lp_comps = util.connected_components(g)
        # Convert into components with actual Supp node instances.
        node_comps = [set([s[lp] for lp in comp]) for comp in lp_comps]
        # Inform each Supp node of its component.
        for comp in node_comps:
            for supp in comp:
                # Here we deliberately _suppress_ the reflexive property of the equivalence,
                # removing the supp node itself from the component that it records.
                supp.set_alternates(comp - {supp})

    def get_all_supp_nodes_rec(self, lookup):
        """
        Compute a lookup, recording Supp nodes by their absolute libpaths, and in which
        _all_ Supp nodes either in this Deduc or any of its SubDeducs, should appear.
        @param lookup: Users should pass an empty dictionary, to be populated.
        @return: nothing. The given dictionary is populated.
        """
        for node in self.nodeSeq:
            if isinstance(node, Supp):
                lp = node.getLibpath()
                lookup[lp] = node
        for sd in self.subdeducSeq:
            assert isinstance(sd, Deduction)
            sd.get_all_supp_nodes_rec(lookup)

    def resolve_node_targets(self):
        """
        Certain node types may have "targets" (e.g. `supp` nodes may name alternative cases;
        and `flse` nodes may name the `supp` nodes whose rejection they signal).
        This is a place to resolve any such targets.
        """
        for node in self.nodeSeq:
            node.resolve_targets()
        for subded in self.subdeducSeq:
            assert isinstance(subded, Deduction)
            subded.resolve_node_targets()

    def writeRunningDefsObject(self):
        """
        Write a simple JSON-serializable object in which to represent any and all running defs,
        for use by the front-end.
        @return: the object
        """
        d = []
        for rdef in self.runningDefs:
            lhs = rdef.lhs
            rhs = ll(rdef.rhs)
            d.append([lhs, rhs])
        return d

    def isDeduc(self):
        return True

    def getHname(self):
        return self.hname

    def addNode(self, node):
        self.nodeSeq.append(node)
        name = node.getName()
        self[name] = node
        node.setParent(self)

    def addSubDeduc(self, subdeduc):
        self.subdeducSeq.append(subdeduc)
        name = subdeduc.getName()
        self[name] = subdeduc
        subdeduc.setParent(self)

    def writeXpanSeq(self):
        seq = []
        td = self.getTargetDeduction()
        if td:
            seq = td.writeXpanSeq()
        seq.append( self.writePresentationInfo() )
        return seq

    def getTargetDeducLibpath(self):
        td = self.getTargetDeduction()
        lp = td.getLibpath() if td else None
        return lp

    def writeTargetsToGhostsDict(self):
        t2g = {}
        # Do we have any targets?
        if len(self.targets) > 0:
            targetpaths = [t.getLibpath() for t in self.targets]
            # The way things currently work (not sure this is the best design),
            # ghost nodes aren't built until self.buildDashgraph has been called
            # at least once.
            if len(self.ghostNodes) == 0:
                self.buildDashgraph()
            # Now we should have a ghost node for each target node.
            # Build a dictionary mapping libpaths of real nodes to libpaths
            # of ghost nodes.
            for gn in self.ghostNodes:
                libpath = gn.realObj().getLibpath()
                # We only want the ones that are targets:
                if libpath in targetpaths:
                    ghostpath = gn.getLibpath()
                    t2g[libpath] = ghostpath
        return t2g

    def writePresentationInfo(self):
        info = {}
        info['libpath'] = self.libpath
        info['friendly_name'] = self.generateFriendlyName()
        info['target_deduc'] = self.getTargetDeducLibpath()
        info['targets_to_ghosts'] = self.writeTargetsToGhostsDict()
        return info 

    def generateFriendlyName(self):
        fn = self.name
        if self.hname:
            # If a human-readable name was provided, use it.
            fn = self.hname
        elif self.name in ['Thm', 'Lem', 'Prop', 'Rem']:
            # In this case build the friendly name from the name of the module.
            # E.g. for module Thm168 produce "Theorem 168".
            modname = self.getModuleName()
            resultType = re.match(
                'Thm|Lem|Prop|Rem',
                modname
            )
            if resultType:
                t = resultType.group()
                rem = modname[len(t):]
                T = {
                    'Thm':'Theorem',
                    'Lem':'Lemma',
                    'Prop':'Proposition',
                    'Rem':'Remark'
                }[t]
                fn = '%s %s'%(T,rem)
            else:
                # Otherwise it should be a page/line reference.
                # Format of module name should be Pg#.#
                m = re.match(r'Pg(\d+).(\d+)', modname)
                if m:
                    page = m.group(1)
                    line = m.group(2)
                    fn = 'Page %s, line %s' % (page, line)
                else:
                    # Fail silently.
                    pass
        elif len(self.name) >= 2 and self.name[:2]=='Pf':
            # In this case it is a proof.
            fn = 'Proof'
            # Add the remainder of the name, after replacing
            # underscores with spaces.
            rem = self.name[2:].replace("_", ' ').strip()
            if rem:
                fn += ' ' + rem
            """
            # Add e.g. "of C1" if there is more than one proof
            # of this deduction's target deduction.
            td = self.getTargetDeduction()
            if not td:
                msg = 'Deduction called %s begins with "Pf" '%(
                    self.name
                )
                msg += 'but has no target deduction.'
                raise PfscExcep(msg)
            mod = self.parent
            allDeds = mod.getAllDeductionsOfDeduction(td)
            if len(allDeds) > 1:
                # There's more than one proof, so augment the name.
                targetNames = [t.name for t in self.targets]
                fn += ' of '
                s = ''
                for tn in targetNames:
                    s += ', %s'%tn
                fn += s[2:]
            """
        elif self.name == 'Xpan':
            libpath = self.getLibpath()
            S = re.search(r'([XYZ]\d+(\.[A-Z]\d+)*)\.Xpan$', libpath)
            if S is None:
                raise PfscExcep('Bad xpanpath: "%s"' % libpath, PECode.MALFORMED_XPANMOD_PATH)
            fn = S.groups()[0]
        return fn

    def canAppearAsGhostInMesonScript(self):
        return True

    def generateGhostName(self):
        gn = self.generateFriendlyName()
        if len(gn) >= 5 and gn[:5] == 'Proof':
            gn = 'Proof of '
            td = self.getTargetDeduction()
            gn += td.generateFriendlyName()
        return gn

    def getModuleName(self):
        """
        self is a Deduction, so might have a libpath like
            lit.h.Hilbert.ZB.P1.C2.S5.Thm8.Thm
        in which case the /name/ (not libpath) of the module
        would be 'Thm8'. Return that.
        """
        parts = self.libpath.split('.')
        return parts[-2]

    def buildGraph(self):
        # Every deduc must define either a Meson Script, or an Arc Listing.
        meson_script = self.get('meson', '').strip()
        arc_listing  = self.get('arcs', '').strip()
        # All free strings in pfsc modules are HTML-escaped at parse time,
        # and come to us as instances of the `Markdown` class. Arc listings
        # use angle brackets, and even Meson scripts now allow arrows as
        # keywords, so we need to unescape.
        if meson_script:
            meson_script = meson_script.unescape()
            try:
                graph = meson.build_graph_from_meson(meson_script)
            except PfscExcep as e:
                msg = 'Problem with Meson script is '
                msg += 'for deduction %s'%self.libpath
                e.extendMsg(msg)
                raise e
        elif arc_listing:
            arc_listing = arc_listing.unescape()
            try:
                graph = meson.build_graph_from_arcs(arc_listing)
            except PfscExcep as e:
                msg = 'Problem with arc listing is '
                msg += 'for deduction %s'%self.libpath
                e.extendMsg(msg)
                raise e
        else:
            msg = 'Deduction `%s` defines no graph!' % self.libpath
            msg += '\n\nDid you define a meson or arc script?'
            raise PfscExcep(msg, PECode.DEDUCTION_DEFINES_NO_GRAPH)
        # Go through all the nodes in the returned graph, and, based on their names, figure out
        # which actual library node they refer to, if any, or else build a ghost node or special
        # node, as appropriate. Ghost nodes will be stored under self.ghostNodes; any other nodes
        # built here will be stored under self.specialNodes. Finally, pass to each dummy node
        # the actual node that it represents.
        dummyNodes = graph.getNodes()
        self.specialNodes = []
        for name in dummyNodes:
            dn = dummyNodes[name]
            obj = None
            # If the name begins with a '?' then it is a question node;
            # if it begins with a '!' then it is an "under construction" node.
            # Such nodes need to be created right now and stored as special nodes.
            if name[0] == '?':
                obj = QuestionNode(name, self)
                self.specialNodes.append(obj)
            elif name[0] == '!':
                obj = UnconNode(name, self)
                self.specialNodes.append(obj)
            else:
                # Otherwise retrieve the actual PfscObj refered to by the name,
                # raising an informative exception if it cannot be found.
                desc = 'named in Meson script in deduction %s' % self.libpath
                obj, libpath = self.getFromAncestor(name, missing_obj_descrip=desc)
                # Check where it came from, and act accordingly.
                if libpath == self.libpath:
                    # In this case the item was declared within this
                    # deduction itself, so we mark it as declared locally.
                    dn.declaredLocally = True
                elif libpath == self.getDeductionLibpath():
                    # In this case this deduction must be a subdeduc of the deduction where the item is declared.
                    dn.declaredLocally = False
                else:
                    # The item lives somewhere else, so we need to construct a ghost node.
                    obj = self.createGhosts(name)
                    self.ghostNodes.append(obj)
                    dn.declaredLocally = False
            dn.setActualNode(obj)
        # Now that each dummy node has a reference to the actual node that it represents,
        # we can ask the graph to do a final semantic check.
        try:
            graph.semanticCheck(self.targets)
        except PfscExcep as e:
            traceback.print_exc()
            msg = 'Problem with Meson script is for deduction %s' % self.libpath
            e.extendMsg(msg)
            raise e
        self.graph = graph
        # Build subdeducs' graphs too.
        for subded in self.subdeducSeq:
            subded.buildGraph()
        # Mark bridge edges.
        graph.findAndMarkBridges()
        graph.markFlowLinkOutsAsBridges()

    def buildDashgraph(self, lang='en'):
        """
        Produce a dashgraph for this deduction in the form of
        a JSON-serializable dict.
        """
        # Get node and edge lists from the graph.
        # The node list is logically ordered for the sake of outline view:
        nodesInOrder = self.graph.listNodesInLogicalOrder()
        edges = self.graph.buildEdgeListForDashgraph()
        # Put together the dashgraph for this deduction.
        dg = {}
        dg['edges'] = edges
        dg['libpath'] = self.libpath
        dg['nodetype'] = 'subded' if isinstance(self, SubDeduc) else 'ded'
        dg['origin'] = self.origin
        dg['textRange'] = self.textRange
        dg['labelHTML'] = ''
        dg['isAssertoric'] = False
        dg['nodeOrder'] = [u.actualNode.getLibpath() for u in nodesInOrder]
        dg['cloneOf'] = self.cloneOf.libpath if self.cloneOf else None

        self.add_comparisons_to_dashgraph(dg)

        # Children:
        dg['children'] = {}
        items = (self.nodeSeq + self.subdeducSeq + self.ghostNodes + self.specialNodes)
        for item in items:
            idg = item.buildDashgraph(lang=lang)
            lp = item.getLibpath()
            dg['children'][lp] = idg

        # deducInfo -------------------
        if not self.isSubDeduc():
            di = {}
            di['libpath'] = self.libpath
            di['version'] = self.getVersion()
            di['dependencies'] = self.getDependencies()
            di['deduction'] = self.name
            di['friendly_name'] = self.generateFriendlyName()
            if hasattr(self, 'author'):
                di['author'] = self.author
            if hasattr(self, 'workinfo'):
                di['work'] = self.workinfo
            if hasattr(self, 'runningDefs'):
                di['runningDefs'] = self.writeRunningDefsObject()
            di['targets'] = self.getTargetLibpaths()
            di['xpans_avail'] = []
            di['target_deduc'] = self.getTargetDeductionLibpath()
            di['target_version'] = self.getTargetVersion()
            di['target_subdeduc'] = self.getTargetSubdeducLibpath()
            di['docInfo'] = self.gather_doc_info()
            di['textRange'] = self.textRange
            # Finally:
            dg['deducInfo'] = di

        return dg


class SubDeduc(Deduction):

    def __init__(self, name):
        Deduction.__init__(self, name, [], [])

    def makeClone(self, name=None):
        """
        Make a clone of this subdeduc. You can pass a name if you want to specify
        that; otherwise, it gets the same name as this subdeduc.
        """
        clone = SubDeduc(name or self.name)
        self.populateClone(clone)
        return clone

    def populateClone(self, clone):
        clone.cloneOf = self
        # This list of cloned properties can grow in future versions, as we
        # learn what it is that we want...
        cloned_props = [
            'meson',
        ]
        for prop_name in cloned_props:
            if (value := self.get(prop_name)) is not None:
                clone[prop_name] = value
        # Recurse on nodes and subdeducs
        for node in self.nodeSeq:
            c = node.makeClone()
            clone.addNode(c)
        for subdeduc in self.subdeducSeq:
            c = subdeduc.makeClone()
            clone.addSubDeduc(c)

    def isDeduc(self):
        return False

    def isSubDeduc(self):
        return True

    def get_index_type(self):
        """
        A SubDeduc is really a hybrid between a Deduction and a Node.
        While we make it a subclass of Deduction, in some cases we need it
        to behave more like a Node.
        """
        return IndexType.NODE

    def getAllNativeNodes(self, nodelist):
        nodelist.append(self)
        Deduction.getAllNativeNodes(self, nodelist)

    def getChildrenForIndex(self):
        return self.getChildren()


class NodeType:
    ASRT = "asrt"
    CITE = "cite"
    EXIS = "exis"
    FLSE = "flse"
    INTR = "intr"
    MTHD = "mthd"
    RELS = "rels"
    SUPP = "supp"
    UNIV = "univ"
    WITH = "with"

    GHOST = "ghost"
    QSTN = "qstn"
    UCON = "ucon"

    assertoric_types = [ASRT, EXIS, FLSE, RELS, UNIV, WITH]

    compound_w_intro_types = [EXIS, RELS, UNIV, WITH]

    @classmethod
    def isAssertoric(cls, t):
        return t in cls.assertoric_types

    @classmethod
    def isCompoundNodeWithIntro(cls, t):
        return t in cls.compound_w_intro_types


class Node(NodeLikeObj):

    def __init__(self, nodeType, name):
        NodeLikeObj.__init__(self)
        self.nodeType = nodeType
        self.name = name
        self.subnodeSeq = []
        self.docReference = None
        self.cloneOf = None

    def makeClone(self, name=None):
        """
        Make a clone of this node. You can pass a name if you want to specify
        that; otherwise, it gets the same name as this node.
        """
        if self.nodeType in [NodeType.GHOST, NodeType.QSTN, NodeType.UCON]:
            # At the moment, I don't know what it would mean to clone ghost or
            # special nodes. It sounds like sth we shouldn't be doing, but I
            # haven't thought about it a lot either.
            msg = (
                f'Nodes of type `{self.nodeType}` cannot be cloned.'
                f' (Trying to clone `{self.libpath}`.)'
            )
            raise PfscExcep(msg, PECode.CANNOT_CLONE_NODE)

        clone = node_factory(self.nodeType, name or self.name)
        self.populateClone(clone)
        return clone

    def populateClone(self, clone):
        clone.cloneOf = self
        # This list of cloned properties can grow in future versions, as we
        # learn what it is that we want...
        cloned_props = [
            'en', 'sy', 'de', 'fr', 'ru',
            'doc',
        ]
        for prop_name in cloned_props:
            if (value := self.get(prop_name)) is not None:
                clone[prop_name] = value
        # Recurse on subnodes
        for subnode in self.subnodeSeq:
            sc = subnode.makeClone()
            clone.addNode(sc)

    def getChildren(self):
        return self.subnodeSeq

    def getChildrenForIndex(self):
        return list(filter(lambda u: u.nodeType != 'dummy', self.getChildren()))

    def get_index_type(self):
        return IndexType.NODE

    def resolve_targets(self):
        "Should be overridden by any special node types that may have targets to be resolved."
        pass

    def resolveDocRefs(self, default_doc_info):
        ref_text = self.get('doc')
        if ref_text:
            mod = self.getModule()
            self.docReference = doc_ref_factory(
                code=ref_text, doc_info_obj=default_doc_info, context=mod)

    def getDocRef(self):
        return self.docReference or None

    def listNativeNodesByLibpath(self, nodelist):
        nodelist.append(self.getLibpath())
        # And recurse on subnodes.
        for subnode in self.subnodeSeq:
            subnode.listNativeNodesByLibpath(nodelist)

    def getAllNativeNodes(self, nodelist):
        nodelist.append(self)
        # And recurse on subnodes.
        for subnode in self.subnodeSeq:
            subnode.getAllNativeNodes(nodelist)

    def getNodeType(self):
        return self.nodeType

    def isNode(self):
        return True

    def isSubNode(self):
        return (self.parent and self.parent.isNode())

    def isModal(self):
        t = self.nodeType
        if t == NodeType.SUPP:
            return True
        elif t == NodeType.INTR:
            p = self.parent
            if p is not None and p.isNode() and p.isCompoundNodeWithIntro():
                return False
            else:
                return True
        else:
            return False

    def isAssertoric(self):
        if self.isGhostNode():
            node = self.realObj()
        else:
            node = self
        t = node.getNodeType()
        return NodeType.isAssertoric(t)

    def isCompoundNodeWithIntro(self):
        t = self.nodeType
        return NodeType.isCompoundNodeWithIntro(t)

    def addNode(self, node):
        name = node.getName()
        self[name] = node
        node.setParent(self)
        # We also keep track of the order in which nodes were added.
        self.subnodeSeq.append(node)

    def buildDashgraph(self, lang='en', debug=False):
        dg = {}
        dg['libpath'] = self.libpath
        dg['nodetype'] = self.nodeType
        dg['origin'] = self.origin
        label = self.writeLabelHTML(lang)
        dg['labelHTML'] = pfsc.util.jsonSafe(label)
        dg['isAssertoric'] = self.isAssertoric()
        dg['intraDeducPath'] = self.getIntradeducPath()
        dg['textRange'] = self.textRange
        dg['cloneOf'] = self.cloneOf.libpath if self.cloneOf else None

        if self.docReference:
            dg['docRef'] = self.docReference.combiner_code
            dg['docId'] = self.docReference.doc_id

        self.add_comparisons_to_dashgraph(dg)

        optional = [
            # Prescribed size for the node:
            'size',
            # Formal representation using SymPy:
            'sympy',
            # Formal representation using Lean:
            'lean',
        ]
        for k in optional:
            v = self.get(k)
            if v is not None:
                dg[k] = v

        # Children (subnodes):
        dg['children'] = {}
        for subnode in self.subnodeSeq:
            lp = subnode.getLibpath()
            sndg = subnode.buildDashgraph()
            dg['children'][lp] = sndg
        return dg

    def addChildNodesToDashgraph(self, dg, lang='en', debug=False):
        """
        For use by compound node types.
        Pass an exiting dashgraph. We augment it with a 'children'
        field.
        """
        chil = {}
        for item in self.items.values():
            if hasattr(item,'isNode') and item.isNode():
                lp = item.getLibpath()
                cdg = item.buildDashgraph(lang=lang)
                chil[lp] = cdg
        dg['children'] = chil

    def writeLabelPrefix(self):
        """
        Subclasses may override, in order to set a label prefix.
        """
        return ''

    def writeLabelHTML(self, lang):
        # Look for a latex label, based on language.
        latex_label = self.get(lang, '')
        if not latex_label:
            # If text for the specified language was not defined,
            # then try the 'sy' or "symbolic" field.
            latex_label = self.get('sy', '')
        if not latex_label and lang != 'en':
            # Last ditch: try English, if haven't already.
            latex_label = self.get('en', '')

        # Handle multiline formatting.
        text = ll(latex_label)

        # Add prefix, if any.
        prefix = self.writeLabelPrefix()
        if prefix:
            # Wrap in appropriate tag.
            prefix = '<span class="mooseNode-prefix">%s</span>' % prefix
            prefix = Markup(prefix)
            # Prepend to text.
            text = prefix + text

        # Markdown processing
        renderer = NodeLabelRenderer(self)
        text = mistletoe.markdown(text, renderer)

        # Add a doc label if defined, and if no latex label.
        if self.docReference and not latex_label:
            text += self.docReference.write_doc_render_div()

        return text

    def canAppearAsGhostInMesonScript(self):
        return True

    def generateGhostName(self):
        home = self.getDeduction()
        hgn = home.generateGhostName()
        gn = 'Node %s in %s'%(self.name, hgn)
        return gn


class GhostNode(Node):

    def __init__(self, referent, parent, name):
        Node.__init__(self, NodeType.GHOST, name)
        self.referent = referent
        self.parent = parent
        self.cascadeLibpaths()
        parent[name] = self

    def get_index_type(self):
        return IndexType.GHOST

    def isGhostNode(self):
        return True

    def realObj(self):
        return self.referent.realObj()

    def ghostOf(self):
        return self.referent.getLibpath()

    def fwdRelPath(self):
        return self.get_fwd_rel_libpath(self.referent)

    def writeLabelHTML(self, lang):
        text = self.generateFriendlyName()
        #text = self.fwdRelPath()
        text = '<span class="mooseMonospace">'+text+'</span>'
        # Sanitisation should have already been performed before the
        # module was even recorded.
        return text

    def generateFriendlyName(self):
        fn = self.realObj().generateGhostName()
        return fn

    def writeXpanSeq(self):
        d = self.referent.getDeduction()
        return d.writeXpanSeq()

    def buildDashgraph(self, lang='en', debug=False):
        dg = Node.buildDashgraph(self, lang=lang, debug=debug)
        realObj = self.realObj()
        realDeduc = realObj.getDeduction()
        dg['xpanSeq'] = self.writeXpanSeq()
        dg['ghostOf'] = self.ghostOf()
        dg['fwdRelPath'] = self.fwdRelPath()
        dg['realObj'] = realObj.getLibpath()
        dg['realVersion'] = realObj.getVersion()
        dg['realOrigin'] = realObj.getOrigin()
        dg['realDeduc'] = realDeduc.getLibpath()
        return dg


class SpecialNode(Node):

    def get_index_type(self):
        return IndexType.SPECIAL


class QuestionNode(SpecialNode):

    def __init__(self, name, parent):
        Node.__init__(self, NodeType.QSTN, name)
        self.parent = parent
        self.cascadeLibpaths()

    def writeLabelHTML(self, lang):
        return '?'


class UnconNode(SpecialNode):

    def __init__(self, name, parent):
        Node.__init__(self, NodeType.UCON, name)
        self.parent = parent
        self.cascadeLibpaths()

    def writeLabelHTML(self, lang):
        return '<div class="mooseUnderConstructionNode" title="Under Construction"></div>'


class Flse(Node):

    def __init__(self, name):
        Node.__init__(self, NodeType.FLSE, name)
        # list of relative libpaths (local names) of contradicted supp nodes:
        self.contra_lps = []
        # list of contradicted `Supp` instances themselves:
        self.contra_supps = []

    def populateClone(self, clone):
        super().populateClone(clone)
        clone.contra_lps = self.contra_lps[:]

    def set_contra(self, contra_lps):
        """
        Set the list of libpaths of supposition nodes that are contradicted.
        @param contra: List of (abs or rel) libpaths of contradicted supp nodes.
        """
        self.contra_lps = contra_lps

    def get_contras(self):
        return self.contra_supps

    def writeLabelHTML(self, lang):
        text = '$\\bot$'
        if self.contra_supps:
            versions = {s.getLibpath():s.getVersion() for s in self.contra_supps}
            libpaths = list(versions.keys())
            text = writeNodelinkHTML(text, libpaths, versions)
        return text

    def buildDashgraph(self, lang='en', debug=False):
        dg = Node.buildDashgraph(self,lang=lang,debug=debug)
        dg['contra'] = [node.getLibpath() for node in self.contra_supps]
        return dg

    def resolve_targets(self):
        desc = 'named as contra for node %s' % self.getLibpath()
        for lp in self.contra_lps:
            node = self.parent.getFromAncestor(lp, missing_obj_descrip=desc)[0]
            if not isinstance(node, Supp):
                msg = 'Node %s named as contra for node %s is of wrong type.' % (lp, self.getLibpath())
                msg += ' Only `supp` nodes may be named.'
                raise PfscExcep(msg, PECode.TARGET_OF_WRONG_TYPE)
            self.contra_supps.append(node)


class WologNode(Node):

    def __init__(self, type_, name):
        Node.__init__(self, type_, name)
        # boolean to mark whether this step is "wolog":
        self.wolog = False

    def populateClone(self, clone):
        super().populateClone(clone)
        clone.wolog = self.wolog

    def set_wolog(self, b):
        """
        Say whether this step is to be regarded as taken
        "wolog" i.e. "without loss of generality". What this really means is
        that there are actually several possible cases, but all cases can
        be reduced to this one.
        @param b: boolean
        """
        self.wolog = b

    def writeLabelPrefix(self):
        prefix = ''
        if self.wolog:
            prefix = 'Wolog'
        return prefix


class Mthd(WologNode):

    def __init__(self, name):
        WologNode.__init__(self, NodeType.MTHD, name)


class Supp(WologNode):

    def __init__(self, name):
        WologNode.__init__(self, NodeType.SUPP, name)
        # list of relative libpaths (local names) of alternates:
        self.alternate_lps = []
        # set of actual alternates (i.e. instances of `Supp` class):
        self.alternates = set()

    def populateClone(self, clone):
        super().populateClone(clone)
        clone.alternate_lps = self.alternate_lps[:]

    def set_alternate_lps(self, alts):
        """
        Set the list of alternate_lps for this supposition.
        @param alts: List of (abs or rel) libpaths of other supp nodes that
                     are to be regarded as alternative cases with this one.
        """
        self.alternate_lps = alts

    def buildDashgraph(self, lang='en', debug=False):
        dg = Node.buildDashgraph(self,lang=lang,debug=debug)
        dg['alternates'] = [alt.getLibpath() for alt in self.alternates]
        dg['wolog'] = self.wolog
        return dg

    def writeLabelPrefix(self):
        if self.alternates:
            label = "Case"
            all_cases = self.alternates | {self}
            versions = {c.getLibpath():c.getVersion() for c in all_cases}
            libpaths = list(versions.keys())
            prefix = writeNodelinkHTML(label, libpaths, versions)
        else:
            prefix = WologNode.writeLabelPrefix(self)
        return prefix

    def get_alternates(self):
        return self.alternates

    def set_alternates(self, alts):
        self.alternates = alts

    def resolve_targets(self):
        # It is already enforced syntactically that a supp node can never be
        # declared wolog and also name alternates. So we do not need to check that here.
        desc = 'named as alternate to node %s' % self.getLibpath()
        for alt_lp in self.alternate_lps:
            alt = self.parent.getFromAncestor(alt_lp, missing_obj_descrip=desc)[0]
            if not isinstance(alt, Supp):
                msg = 'Node %s named as alternate for node %s is of wrong type.' % (alt_lp, self.getLibpath())
                msg += ' Only `supp` nodes may be named.'
                raise PfscExcep(msg, PECode.TARGET_OF_WRONG_TYPE)
            # We also check that the alternative is not identical with this one.
            # Supp nodes should not be named as alternates of themselves.
            if alt is self:
                msg = 'Supp node %s should not name self as alternate.' % self.getLibpath()
                raise PfscExcep(msg, PECode.SUPP_NODE_NAMES_SELF_AS_ALTERNATE)
            self.alternates.add(alt)


class CompoundNode(Node):
    pass


class QuantifierNode(CompoundNode):

    def __init__(self, nodetype, name):
        Node.__init__(self, nodetype, name)
        self.defaultText = ''

    def populateClone(self, clone):
        super().populateClone(clone)
        clone.defaultText = self.defaultText

    def writeLabelHTML(self, lang):
        return ''

    def buildDashgraph(self, lang='en', debug=False):
        dg = Node.buildDashgraph(self,lang=lang,debug=debug)
        # List the type nodes and property nodes.
        typenodeUIDs = []
        propnodeUIDs = []
        for node in self.subnodeSeq:
            nt = node.nodeType
            if nt == NodeType.INTR:
                typenodeUIDs.append(node.getLibpath())
            elif node.isAssertoric():
                propnodeUIDs.append(node.getLibpath())
            else:
                pass
                """
                msg = 'There cannot be nodes of type "%s" '%nt
                msg += 'directly inside a "%s" node.\n'%self.nodeType
                msg += 'Node %s '%node.getLibpath()
                msg += 'appears to violate this.'
                raise PfscExcep(msg)
                """
        dg['typenodeUIDs'] = typenodeUIDs
        dg['propnodeUIDs'] = propnodeUIDs
        # Create the pre- and post- nodes.
        text = self.get(lang)
        if not text: text = self.get('sy')
        if not text: text = self.defaultText
        try:
            preText, postText = [t.strip() for t in text.split('%')]
        except:
            msg = 'Text for %s node '%self.nodetype
            msg += 'is supposed to have two parts, '
            msg += 'separated by a "%" character.\n'
            msg += 'Node %s appears to violate this.'%self.libpath
            raise PfscExcep(msg, PECode.MALFORMED_QUANTIFIER_NODE_LABEL)
        pre = Node('dummy','_pre')
        self.addNode(pre)
        pre.cascadeLibpaths()
        pre[lang] = preText
        post = Node('dummy','_post')
        self.addNode(post)
        post.cascadeLibpaths()
        post[lang] = postText
        # Now can add children.
        self.addChildNodesToDashgraph(dg, lang=lang, debug=debug)
        return dg


class Exis(QuantifierNode):

    def __init__(self, name):
        QuantifierNode.__init__(self, NodeType.EXIS, name)
        self.defaultText = 'There exists % such that'


class Univ(QuantifierNode):

    def __init__(self, name):
        QuantifierNode.__init__(self, NodeType.UNIV, name)
        self.defaultText = 'For all % we have'


class With(CompoundNode):

    def __init__(self, name):
        Node.__init__(self, NodeType.WITH, name)

    def writeLabelHTML(self, lang):
        return ''

    def buildDashgraph(self, lang='en', debug=False):
        dg = Node.buildDashgraph(self,lang=lang,debug=debug)
        # List the type nodes and property nodes.
        defnodeUIDs = []
        claimnodeUIDs = []
        for node in self.subnodeSeq:
            nt = node.nodeType
            if nt == NodeType.INTR:
                defnodeUIDs.append(node.getLibpath())
            elif node.isAssertoric():
                claimnodeUIDs.append(node.getLibpath())
            else:
                msg = 'There cannot be nodes of type "%s" '%nt
                msg += 'directly inside a "where" node.\n'
                msg += 'Node %s '%node.getLibpath()
                msg += 'appears to violate this.'
                raise PfscExcep(msg, PECode.BAD_SUBNODE_TYPE)
        dg['defnodeUIDs'] = defnodeUIDs
        dg['claimnodeUIDs'] = claimnodeUIDs
        # Create the pre- and post- nodes.
        text = self.get(lang)
        if not text: text = self.get('sy')
        if not text: text = 'Have % with'
        try:
            preText, postText = [t.strip() for t in text.split('%')]
        except:
            msg = 'Text for "with" node is supposed to have '
            msg += 'two parts, separated by a "%" character.\n'
            msg += 'Node %s appears to violate this.' % self.libpath
            raise PfscExcep(msg, PECode.MALFORMED_WHERE_NODE_LABEL)
        pre = Node('dummy','_pre')
        self.addNode(pre)
        pre.cascadeLibpaths()
        pre[lang] = preText
        post = Node('dummy','_post')
        self.addNode(post)
        post.cascadeLibpaths()
        post[lang] = postText
        # Now can add children.
        self.addChildNodesToDashgraph(dg, lang=lang, debug=debug)
        return dg


class Rels(CompoundNode):

    def __init__(self, name):
        Node.__init__(self, NodeType.RELS, name)

    def writeLabelHTML(self, lang):
        return ''

    def buildDashgraph(self, lang='en', debug=False):
        dg = Node.buildDashgraph(self,lang=lang,debug=debug)
        # List the nodes in the order they should appear.
        chainUIDs = [n.getLibpath() for n in self.subnodeSeq]
        dg['chainUIDs'] = chainUIDs
        # Now can add children.
        self.addChildNodesToDashgraph(dg, lang=lang, debug=debug)
        return dg


# Lookup for special Node subclasses, by their type name:
SPECIAL_NODE_CLASS_LOOKUP = {
    NodeType.EXIS: Exis,
    NodeType.FLSE: Flse,
    NodeType.MTHD: Mthd,
    NodeType.RELS: Rels,
    NodeType.SUPP: Supp,
    NodeType.UNIV: Univ,
    NodeType.WITH: With
}


def node_factory(type_, name):
    """
    Given the desired type for a new node, and its desired name, construct
    an instance of the right class.

    param type_: element of the NodeType enum class
    param name: string

    return: instance of some subclass of Node
    """
    cls = SPECIAL_NODE_CLASS_LOOKUP.get(type_)
    if cls is None:
        node = Node(type_, name)
    else:
        node = cls(name)
    return node

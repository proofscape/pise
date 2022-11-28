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

"""
Parse meson scripts, and build Graph objects to represent them.
"""
import sys
from collections import defaultdict

from lark import Lark, Transformer
from lark.exceptions import VisitError, LarkError

from pfsc.excep import PfscExcep, PECode

######################################################################
# At one time these were viewed as settings. But as libraries grow,
# these must be viewed as fixed rules.

# Flow arrows for sentences without prefix?
MESON_FLOW_UNPREFIXED = True

# As a semantic check, we check that all target nodes of a deduction
# lie at the head of at least one arrow. If you want to also demand
# that they lie at the head of at least one _deduction_ arrow, then
# set this option to True.
TARGET_NODES_STRICTLY_DEDUCED = False

######################################################################
# Graph, Node, Edge classes

class EdgeType:
    DED = 'ded'
    FLOW = 'flow'

class GraphSource:
    MESON = 'meson'
    ARCS = 'arcs'

class Graph:

    def __init__(self, src_type=None):
        """
        :param src_type: a value of the GraphSource enum class, indicating the
          type of script that gave rise to this Graph.
        """
        self.src_type = src_type
        self.nodes = {}
        self.edges = {}
        # We build a lookup in which you can find an edge by passing the names
        # of its endpoint nodes, in either order.
        self.edgesByEndpts = defaultdict(dict)
        # Write debug info to stderr?
        self.debug = False
        # For numbering nodes in order of original occurrence in Meson script:
        self.nodeSeqNum = 0

    def __repr__(self):
        r = ''
        for name in self.nodes:
            r += '%s\n'%name
        for desc in self.edges:
            r += '%s\n'%desc
        return r

    def listNodesInLogicalOrder(self):
        """
        This is for the Lamport/outline view.
        We simply define a __lt__ method in the Node class (see below) and then
        return a sorted version of our list of Nodes.
        """
        return sorted(self.nodes.values())

    def listEdges(self):
        r = ''
        for desc in self.edges:
            r += '%s\n'%desc
        return r

    def getNodes(self):
        return self.nodes

    def getNode(self, name):
        return self.nodes.get(name, None)

    def getEdges(self):
        return self.edges

    def createNode(self, name):
        # Create node
        node = Node(name)
        # Assign next sequence number
        node.seqNum = self.nodeSeqNum
        self.nodeSeqNum += 1
        # Record
        self.nodes[name] = node
        if self.debug:
            sys.stderr.write('Created node: %s\n'%name)
        return node

    def createEdge(self, Pn, Qn, kind=EdgeType.DED):
        """
        Create an edge from node of name Pn to node of name Qn,
        creating also the nodes if they do not already exist.

        :param kind: an EdgeType
        """
        if not self.getNode(Pn): self.createNode(Pn)
        if not self.getNode(Qn): self.createNode(Qn)
        E = Edge(self, Pn, Qn, kind = kind)
        P = self.getNode(Pn)
        P.addEdge(E)
        Q = self.getNode(Qn)
        Q.addEdge(E)
        d = repr(E)
        self.edges[d] = E
        self.edgesByEndpts[Pn][Qn] = E
        self.edgesByEndpts[Qn][Pn] = E
        if self.debug:
            sys.stderr.write('Created edge: %s\n' % d)
        return E

    def deleteEdge(self, e):
        """
        Delete an edge from the graph.
        Fail silently if edge is not found.

        e: the Edge instance to be deleted
        """
        d = repr(e)
        if d in self.edges:
            del self.edges[d]
        Pn = e.getSrcName()
        Qn = e.getTgtName()
        if Qn in self.edgesByEndpts[Pn]:
            del self.edgesByEndpts[Pn][Qn]
        if Pn in self.edgesByEndpts[Qn]:
            del self.edgesByEndpts[Qn][Pn]
        if self.debug:
            sys.stderr.write('Deleted edge: %s\n' % d)

    def factorEdgesThroughMethod(self, E, Mn):
        """
        E: a list of actual edge objects, each of which
               should already be in self.edges
        Mn: the name of a method node

        Create node M if it does not already exist.
        Then node M is to be inserted as method for all the
        edges in the list E. This means that all edges in E
        are to be deleted, while if S and T are the sets of
        all sources and targets in E, then we are to form
        the edges (s, M) for all s in S and (M, t) for all
        t in T.
        """
        if not self.getNode(Mn):
            self.createNode(Mn)
        # We use dicts, not sets, not because the order actually matters,
        # but just to make the output deterministic, and make it easier
        # to write unit tests.
        S, T = {}, {}
        for e in E:
            s = e.getSrcName()
            t = e.getTgtName()
            S[s] = 1
            T[t] = 1
            self.deleteEdge(e)
        for s in S:
            self.createEdge(s, Mn)
        for t in T:
            self.createEdge(Mn, t)

    def semanticCheck(self, targets):
        """
        Perform semantic checks which are possible only after each (dummy) node
        in this Graph  has been passed a reference to the actual (Proofscape) Node
        that it represents. (So this method is not to be called until after that
        has happened!)

        Checks on nodes:

            (N1) All supp and intr nodes are first named inside a supposition, unless
                they are contained in a compound node such as `exis`. However, we apply
                this rule only if this Graph's `src_type` is MESON (not ARCS).

            (N2) A non-modal node never occurs inside a supposition.

        Checks on the endpoints of arrows (edges):

            (E1) A deduction arrow may not have a subdeduction or a
                modal (supp or intr) node at its head.

            (E2) There is at most one flow arrow leaving any single node,
                and at most one entering it.

            (E3) There is at most one arrow between any two nodes.

            (E4) A node which is a target of a deduction may not lie at the
                tail of any arrow with head in that same deduction.

            (E5) Every target node must lie at the head of at least one
                (deduction) arrow.

        We raise an exception if any check fails.

        :param targets: list of Proofscape `Node` instances representing the
          targets of this deduction.
        """

        # (I) Check supp and intr nodes.
        for node in self.nodes.values():
            node_is_modal = node.actualNode.isModal()
            if (self.src_type == GraphSource.MESON and node_is_modal
                    and node.declaredLocally and not node.firstOccursInSupposition):
                msg = 'Modal nodes must first occur after a modal keyword'
                msg += ', but node "%s" breaks this rule.' % node.name
                raise PfscExcep(msg, PECode.MESON_MODAL_WORD_MISSING)
            elif node.firstOccursInSupposition and not node_is_modal:
                msg = 'Only modal nodes may occur after modal keywords'
                msg += ', but node "%s" breaks this rule.' % node.name
                raise PfscExcep(msg, PECode.MESON_MODAL_MISMATCH)

        # (II) Check edges.
        # Get the list of libpaths of the targets.
        targetLibpaths = [t.getLibpath() for t in targets]
        # Prepare a set of libpaths of "undeduced targets," i.e. target
        # nodes which were not found to be at the head of any deduction arrow.
        # It starts off as the set of all target libpaths.
        # After we have iterated over all edges, it should be empty.
        undeducedTargetLibpaths = set(targetLibpaths)
        # Prepare a set of ordered pairs of edge endpts.
        # We will record these as strings, with the endpts
        # sorted alphabetically.
        endpairs = set([])
        # Prepare a set of nodes having an outgoing flow edge,
        # and a set of nodes having an incoming flow edge.
        outflow = set([])
        inflow = set([])
        # Now iterate over edges.
        for desc in self.edges:
            e = self.edges[desc]
            sn = e.getSrcName()
            tn = e.getTgtName()
            # Check (1)
            if e.isDeduc():
                t = self.getNode(tn).getActualNode()
                if t.isSubDeduc() or t.isModal():
                    msg = 'Deduction arrows may not terminate '
                    msg += 'at subdeductions or modal nodes.\n'
                    msg += 'Deduction arrow terminates at %s.\n'%tn
                    msg += self.listEdges()
                    raise PfscExcep(msg, PECode.MESON_DEDUC_ARROW_BAD_TARGET)
            # Check (2)
            if e.isFlow():
                if sn in outflow or tn in inflow:
                    prob = sn if sn in outflow else tn
                    msg = 'No node may have more than one '
                    msg += 'incoming flow arrow or more than one '
                    msg += 'outgoing flow arrow.\n'
                    msg += 'Node %s appears to violate this.\n'%prob
                    msg += self.listEdges()
                    raise PfscExcep(msg, PECode.MESON_EXCESS_FLOW)
                else:
                    outflow.add(sn)
                    inflow.add(tn)
            # Check (3)
            pair = ','.join(sorted([sn,tn]))
            if pair in endpairs:
                msg = 'There may be at most one arrow between'
                msg += ' any two nodes.\n'
                msg += 'There appear to be two arrows between'
                msg += ' the nodes %s and %s.\n'%(sn,tn)
                msg += self.listEdges()
                raise PfscExcep(msg, PECode.MESON_EXCESS_ARROW)
            else:
                endpairs.add(pair)
            # Check (4)
            s = self.getNode(sn).getActualNode()
            t = self.getNode(tn).getActualNode()
            # There's a problem only if the source node lies outside
            # the present deduction, and is a target of this
            # deduction, AND the target node is IN the deduction, i.e.
            # is NOT a ghost node.
            if (
                s.isGhostNode() and
                (not t.isGhostNode()) and
                (s.ghostOf() in targetLibpaths)
            ):
                msg = 'A node which is a target of a '
                msg += 'deduction may not lie at the tail of any '
                msg += 'arrow with head in that deduction.\n'
                msg += 'Node %s appears to violate this.\n'%sn
                msg += self.listEdges()
                raise PfscExcep(msg, PECode.MESON_DOWNWARD_FLOW_ERROR)
            # Prepare for Check (5):
            if e.isDeduc() or (e.isFlow and not TARGET_NODES_STRICTLY_DEDUCED):
                if t.isGhostNode():
                    tlp = t.ghostOf()
                else:
                    tlp = t.getLibpath()
                if tlp in undeducedTargetLibpaths:
                    undeducedTargetLibpaths.remove(tlp)
        # Check (5)
        numUndeducedTargets = len(undeducedTargetLibpaths)
        if numUndeducedTargets > 0:
            msg = 'Deduction declared\n'
            for utl in undeducedTargetLibpaths:
                msg += '    %s\n' % utl
            msg += 'as target%s, but %s not deduced.' % (
                '' if numUndeducedTargets == 1 else 's',
                'this node was' if numUndeducedTargets == 1 else 'these nodes were'
            )
            raise PfscExcep(msg, PECode.MESON_DID_NOT_DELIVER)

    def buildEdgeListForDashgraph(self, suppress_flow=False):
        es = []
        for desc in self.edges:
            E = self.edges[desc]
            if suppress_flow and E.isFlow(): continue
            e = E.buildDashgraphRep()
            es.append(e)
        return es

    def computeContainmentNbrs(self):
        """
        After each dummy node's actual node has been set, we can compute the adjacencies
        w.r.t. imaginary "containment edges".

        :return: dict in which node name maps to set of names of that node's containment nbrs.
        """
        containment_nbrs = defaultdict(set)
        all_names = set(self.nodes.keys())
        for name, node in self.nodes.items():
            parent = node.getActualNode().getParent()
            parentName = parent.getName()
            if parentName in all_names:
                containment_nbrs[name].add(parentName)
                containment_nbrs[parentName].add(name)
        return containment_nbrs

    def findAndMarkBridges(self):
        """
        Locate all bridges in the graph -- i.e. edges whose deletion would increase
        the number of connected components -- and mark them as such, i.e. record the
        fact in each Edge instance.

        The idea is: we traverse each connected component of the graph via DFS, enumerating
        the nodes in the order in which they are first encountered. As we go,
        we also work out the minimum index that can be reached from each node, _without traversing
        the edge along which we first came to that node_. In this process, the bridges
        are precisely those edges that lead us to a node from which it is "impossible to retreat",
        i.e. a node whose minimum reachable index equals its index as first encountered.

        :return: the set of bridges located.
        """
        bridges = set()
        all_nodes = self.nodes
        edge_lookup = self.edgesByEndpts
        unvisited_names = set(all_nodes.keys())
        c_nbrs = self.computeContainmentNbrs()

        count = 0
        min_reach = {name:-1 for name in all_nodes}
        first_enc = min_reach.copy()

        def bridge_search(a, b, count):
            count += 1
            min_reach[b] = first_enc[b] = count

            all_nbrs = all_nodes[b].nbrNames | c_nbrs[b]
            for c in all_nbrs:
                if first_enc[c] < 0:
                    unvisited_names.remove(c)
                    bridge_search(b, c, count)
                    min_reach[b] = min(min_reach[b], min_reach[c])
                    if min_reach[c] == first_enc[c]:
                        e = edge_lookup[b].get(c)
                        if e is not None:
                            e.isBridge(True)
                            bridges.add(e)
                elif a != c:
                    min_reach[b] = min(min_reach[b], first_enc[c])

        while unvisited_names:
            a = unvisited_names.pop()
            bridge_search(a, a, count)

        return bridges

    def markFlowLinkOutsAsBridges(self):
        """
        A "link" is a degree-2 node; a "flow-link" is a link both of whose incident edges
        are flow edges, one incoming, one outgoing. The "out" edge of a flow-link is the
        outgoing flow edge. It may be useful to mark such edges as being bridges; even if
        they are not actually bridges, our goal may be simply to prevent these edges from
        being suppressed.

        :return: set of edges marked
        """
        marked = set()
        for node in self.nodes.values():
            if node.isFlowLink():
                e = node.outflowEdge
                e.isBridge(True)
                marked.add(e)
        return marked

class Node:

    def __init__(self, name):
        self.name = name
        self.seqNum = None
        self.actualNode = None
        self.firstOccursInSupposition = False
        self.declaredLocally = False
        self.nbrNames = set()
        # Besides just knowing all our neighbor nodes, it is useful to us to
        # know which of them lies at the target end of the edge:
        self.targetNames = set()
        # Each node can have at most one incoming flow edge, and at most
        # one outgoing flow edge. If they exist, we record them here:
        self.inflowEdge = None
        self.outflowEdge = None

    def addEdge(self, edge):
        if edge.tgtName != self.name:
            # The edge target is our neighbor.
            self.nbrNames.add(edge.tgtName)
            if edge.isFlow():
                self.outflowEdge = edge
            self.targetNames.add(edge.tgtName)
        else:
            # The edge source is our neighbor.
            self.nbrNames.add(edge.srcName)
            if edge.isFlow():
                self.inflowEdge = edge

    def isFlowLink(self):
        """
        Is this a degree-2 node (a "link") both of whose incident edges are flow edges?
        :return: boolean
        """
        return (len(self.nbrNames) == 2) and (self.inflowEdge is not None) and (self.outflowEdge is not None)

    def __lt__(self, other):
        # This is for listing the nodes named in a Meson script
        # in a logical order, for the "outline view".
        # Primarily, if A --> B (i.e. there is a deduction arrow from
        # node A to node B) then A should come before B in the list.
        # Secondarily, when neither node points to the other, we go
        # according to the order named in the Meson script.

        # (1a) If other is target of self, then self is less than other.
        if other.name in self.targetNames:
            return True
        # (1b) Vice versa
        elif self.name in other.targetNames:
            return False
        # (2) Otherwise go according to order named in the Meson script.
        else:
            return self.seqNum < other.seqNum

    def getName(self):
        return self.name

    def setActualNode(self, node):
        self.actualNode = node

    def getActualNode(self):
        return self.actualNode

class Edge:

    def __init__(self, graph, srcName, tgtName, kind=EdgeType.DED):
        self.graph = graph
        self.srcName = srcName
        self.tgtName = tgtName
        self.kind = kind
        self._isBridge = False

    def getSrcName(self):
        return self.srcName

    def getTgtName(self):
        return self.tgtName

    def getOtherName(self, name):
        return self.srcName if name == self.tgtName else self.tgtName

    def getSrcLibpath(self):
        return self.graph.getNode(self.srcName).getActualNode().getLibpath()

    def getTgtLibpath(self):
        return self.graph.getNode(self.tgtName).getActualNode().getLibpath()

    def getSrcActualNode(self):
        return self.graph.getNode(self.srcName).getActualNode()

    def getTgtActualNode(self):
        return self.graph.getNode(self.tgtName).getActualNode()

    def getKind(self):
        return self.kind

    def isFlow(self):
        return self.kind == EdgeType.FLOW

    def isDeduc(self):
        return self.kind == EdgeType.DED

    def isBridge(self, *args):
        if args:
            self._isBridge = args[0]
        else:
            return self._isBridge

    def __repr__(self):
        s = ''
        e = {
            EdgeType.DED:'-->', EdgeType.FLOW:'..>'
        }[self.kind]
        s += '%s %s %s'%(self.srcName, e, self.tgtName)
        return s

    def buildDashgraphRep(self):
        r = {}
        r['tail'] = self.getSrcLibpath()
        r['head'] = self.getTgtLibpath()
        r['style'] = self.kind
        r['bridge'] = self.isBridge()
        return r

######################################################################
# Parsing

arc_parser = Lark(r'''
    arclisting : chain+
    chain : NAME (ARC NAME)+
    ARC  : "-->"|"<--"|"..>"
    NAME : /[A-Za-z\?!]([A-Za-z0-9_.]*[A-Za-z0-9_])?/
    %import common.WS
    %ignore WS
''', start='arclisting')


class ArcLangTransformer(Transformer):

    def __init__(self):
        # Build a Graph
        self.graph = Graph(src_type=GraphSource.ARCS)

    def arclisting(self, items):
        return self.graph

    def chain(self, items):
        m = len(items)
        n = int((m - 1)/2)
        for k in range(n):
            p, a, q = items[2*k : 2*k+3]
            t = EdgeType.FLOW if a[0] == '.' else EdgeType.DED
            if a[0] == "<": p, q = q, p
            self.graph.createEdge(p, q, t)



meson_parser = Lark(r'''
    mesonscript : ROAM? initialphrase phrase*
    ?initialphrase : supposition | assertion
    phrase : conclusion | (ROAM|FLOW)? initialphrase
    conclusion : INF assertion method?
    assertion : nodes reason*
    supposition : MODAL nodes
    reason : SUP nodes
    method : HOW node
    nodes : node (_CONJ node)*
    node : NAME

    // We make the keyword terminals prority 2, and use a standard lexer, so that keywords
    // cannot match as NAMEs.
    INF.2   : /so|then|therefore|hence|thus|get|infer|find|implies|whence|whereupon|-->/i
    SUP.2   : /by|since|using|because|for|<--/i
    FLOW.2  : /now|next|claim|\.\.>/i
    ROAM.2  : /but|meanwhile|note|have|from|observe|consider/i
    HOW.2   : /applying|via/i
    MODAL.2 : /let|suppose/i
    _CONJ.2  : /and|plus/i

    NAME : /[A-Za-z\?!]([A-Za-z0-9_.]*[A-Za-z0-9_])?/

    %import common.WS
    %ignore WS
    %ignore /[,;.]/

''', start='mesonscript', lexer='standard')

class MesonNode:

    def __init__(self, token):
        self.token = token
        self.name = str(token)
        self.pos = token.pos_in_stream

    def __str__(self):
        return self.name

class MesonMethod:

    def __init__(self, node):
        self.node = node

    def __str__(self):
        return 'method: ' + ' '.join([str(node) for node in self.nodes])

class MesonReason:

    def __init__(self, nodes):
        self.nodes = nodes

    def __str__(self):
        return 'reason: ' + ' '.join([str(node) for node in self.nodes])

class MesonPrefix:
    NONE = None
    ROAM = "ROAM"
    FLOW = "FLOW"
    INF  = "INF"

# We make a lookup, mapping MesonPrefixes to Edge types.
EDGE_TYPE_BY_PREFIX = {
    MesonPrefix.NONE: EdgeType.FLOW if MESON_FLOW_UNPREFIXED else None,
    MesonPrefix.ROAM: None,
    MesonPrefix.FLOW: EdgeType.FLOW,
    MesonPrefix.INF:  EdgeType.DED
}

class MesonPhrase:

    def __init__(self):
        self.prefix = MesonPrefix.NONE
        self.first_nodes = []
        self.last_nodes = []

class MesonSupposition(MesonPhrase):

    def __init__(self, nodes):
        super().__init__()
        self.nodes = nodes
        self.first_nodes = nodes
        self.last_nodes = nodes

    def __str__(self):
        return 'suppose: ' + ' '.join([str(node) for node in self.nodes])

class MesonAssertion(MesonPhrase):

    def __init__(self, targets):
        super().__init__()
        self.targets = targets
        self.first_nodes = targets
        self.last_nodes = targets
        self.factorable_edges = []

class MesonConclusion(MesonPhrase):

    def __init__(self, assertion):
        super().__init__()
        self.prefix = MesonPrefix.INF
        self.assertion = assertion
        # Lift first and last nodes up, from the assertion.
        self.first_nodes = assertion.first_nodes
        self.last_nodes = assertion.last_nodes
        self.method = None
        # List factorable edges.
        self.factorable_edges = assertion.factorable_edges



class MesonTransformer(Transformer):

    def __init__(self):
        # Build a Graph
        self.graph = Graph(src_type=GraphSource.MESON)
        # Map names to the positions (in the stream) at which they first occur.
        self.name_first_pos = {}

    def is_first_occurrence(self, node):
        """
        Say whether a given MesonNode is the _first_ occurrence of that name.
        :param node: The MesonNode in question.
        :return: Boolean
        """
        return node.pos == self.name_first_pos[node.name]

    def mesonscript(self, items):
        """
        Make inter-phrase edges.
        """
        N = len(items)
        if N == 0: return
        # We want to scan the list of all phrases, with a sliding window of width 2.
        i0 = 1
        # If the script began with the optinoal ROAM keyword, then we need to skip that.
        if not isinstance(items[0], MesonPhrase): i0 = 2
        # Scan:
        for i in range(i0, N):
            # Grab pair of adjacent phrases.
            P, Q = items[i-1: i+1]
            # The kind of inter-phrase edges we make depends on the prefix of the
            # second phrase.
            k = EDGE_TYPE_BY_PREFIX[Q.prefix]
            # If none, move on.
            if k is None: continue
            # Otherwise make edges.
            sources = P.last_nodes
            targets = Q.first_nodes
            # We never want to flow from more than just one
            # of the final names of the previous sentence.
            # Namely, we take the last one. Likewise, we never
            # flow /to/ more than just one node.
            if k == EdgeType.FLOW:
                sources = sources[-1:]
                targets = targets[:1]
            edges = []
            for src in sources:
                for tgt in targets:
                    e = self.graph.createEdge(src.name, tgt.name, kind=k)
                    edges.append(e)
            # If Q is a conclusion and has a method, then factor edges.
            if isinstance(Q, MesonConclusion) and Q.method is not None:
                edges.extend(Q.factorable_edges)
                self.graph.factorEdgesThroughMethod(edges, Q.method.node.name)
        return self.graph
    
    def phrase(self, items):
        """
        For assertions and suppositions, we set the prefix.

        For suppositions we also set up the first and last nodes for the formation of inter-phrase edges.
        For conclusions and assertions this is already set. We only need to do anything for suppositions.
        We do this at this level since it depends on whether the we have a FLOW prefix.
        In that case we also make internal flow arrows here.
        """
        mp = items[-1]
        # If it is a conclusion, we have nothing to do at this stage.
        if isinstance(mp, MesonConclusion):
            return mp
        # Otherwise we need to set the prefix.
        N = len(items)
        mp.prefix = MesonPrefix.NONE if N == 1 else items[0].type
        # If it is a supposition, then we need to set up the first and last nodes,
        # and maybe make flow edges.
        if isinstance(mp, MesonSupposition):
            nodes = mp.nodes
            n = len(items)
            no_prefix = mp.prefix == MesonPrefix.NONE
            flow_prefix = mp.prefix == MesonPrefix.FLOW
            if flow_prefix or (no_prefix and MESON_FLOW_UNPREFIXED):
                # In this case we want to chain the nodes
                # together with flow arrows, and set just the first
                # and last of these as this phrase's first and last nodes.
                mp.first_nodes = [nodes[0]]
                mp.last_nodes = [nodes[-1]]
                if len(nodes) >= 2:
                    for S, T in zip( nodes[:-1], nodes[1:] ):
                        e = self.graph.createEdge(S.name, T.name, kind=EdgeType.FLOW)
        return mp

    def conclusion(self, items):
        # Grab the assertion, and use it to form a conclusion object.
        ma = items[1]
        mc = MesonConclusion(ma)
        # Set the method node, if any.
        if len(items) == 3:
            mc.method = items[2]
        return mc

    def assertion(self, items):
        """
        For an assertion, we make arrows only if there are any `reason` clauses.
        If there are any `reason` clauses, then we record the arrows for the only
        the _first_ such clause as "factorable edges" i.e. edges that may be
        factored through a `method`, if one should be given higher up.
        """
        targets = items[0]
        ma = MesonAssertion(targets)
        # Any reasons?
        first_reason_set = True
        for reason in items[1:]:
            sources = reason.nodes
            for src in sources:
                for tgt in targets:
                    e = self.graph.createEdge(src.name, tgt.name)
                    if first_reason_set:
                        ma.factorable_edges.append(e)
            targets = sources
            first_reason_set = False
        return ma

    def reason(self, items):
        nodes = items[1]
        return MesonReason(nodes)

    def method(self, items):
        nodes = items[1]
        return MesonMethod(nodes)

    def supposition(self, items):
        nodes = items[1]
        for node in nodes:
            if self.is_first_occurrence(node):
                # Record the fact.
                # Note: `node` is a `MesonNode` instance. We need the `Node` instance.
                graph_node = self.graph.getNode(node.name)
                graph_node.firstOccursInSupposition = True
            else:
                # In this case we have a second or later mention of a node
                # occurring inside a supposition, and that is never okay.
                msg = 'Only the first mention of a node may occur after a'
                msg += ' modal keyword, but node "%s" breaks this rule.' % node.name
                raise PfscExcep(msg, PECode.MESON_EXCESS_MODAL)
        return MesonSupposition(nodes)

    def nodes(self, items):
        return items

    def node(self, items):
        mn = MesonNode(items[0])
        name = mn.name
        # If we have not yet encountered this name...
        if name not in self.name_first_pos:
            # ...then note the position of the first occurrence...
            self.name_first_pos[name] = mn.pos
            # ...and make a Node in the Graph if it has not been made already.
            if not self.graph.getNode(name):
                self.graph.createNode(name)
        return mn


######################################################################
# API

def build_graph_from_arcs(arc_listing):
    """
    Take a listing in the "arc lang", and return a Graph object for it.
    """
    try:
        tree = arc_parser.parse(arc_listing)
        alt = ArcLangTransformer()
        graph = alt.transform(tree)
    except VisitError as v:
        # Lark traps our PfscExceps, re-raising them within a VisitError.
        # We want to see the PfscExcep.
        raise v.orig_exc from v
    except LarkError as e:
        msg = 'Arclang parsing error: ' + str(e)
        raise PfscExcep(msg, PECode.ARCLANG_ERROR) from e
    return graph

def build_graph_from_meson(meson_script):
    """
    Take a meson script, and return a Graph object for it.
    """
    try:
        tree = meson_parser.parse(meson_script)
        mt = MesonTransformer()
        graph = mt.transform(tree)
    except VisitError as v:
        # Lark traps our PfscExceps, re-raising them within a VisitError.
        # We want to see the PfscExcep.
        raise v.orig_exc from v
    except LarkError as e:
        msg = 'Meson parsing error: ' + str(e)
        raise PfscExcep(msg, PECode.MESON_ERROR) from e
    return graph

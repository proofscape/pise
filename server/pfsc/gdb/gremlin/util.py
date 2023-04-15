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

from gremlin_python.process.graph_traversal import (
    GraphTraversalSource, Transaction, __)
from gremlin_python.process.traversal import TextP, P

from pfsc.constants import IndexType


def covers(major, tr):
    return tr.has('cut', TextP.gt(major)).has('major', TextP.lte(major))


def among_lps(libpaths, tr):
    return tr.has('libpath', P.within(libpaths))


def lp_covers(libpath, major, tr):
    return covers(major, tr.has('libpath', libpath))


def lps_covers(libpaths, major, tr):
    return covers(major, among_lps(libpaths, tr))


def lp_maj(libpath, major, tr):
    return tr.has('libpath', libpath).has('major', major)


def is_user(username, tr):
    return tr.has('username', username).has_label(IndexType.USER)


def edge_info(tr):
    return tr.project('u', 'e', 'v'). \
                by(__.out_v().element_map()). \
                by(__.element_map()). \
                by(__.in_v().element_map())


def merge_node(tr, label, ip, op=None, label_order=0):
    """
    Extend a traversal with a "merge" operation for a node.

    @param tr: GraphTraversal onto which to add this merge op.
    @param label: str, the label of the node
    @param ip: dict, "identifying properties", i.e. a set of properties which,
      together with the label, should uniquely identify the node.
    @param op: dict, optional, "other properties", properties which should not
      take part in identifying the node, but should be set on the node.
    @param label_order: int, optional, defines where in the sequence of
      identifying properties the label should be invoked. Set negative to not
      use it at all.
    @return: the augmented traversal
    """
    add_tr = __.add_v(label)
    i = -1
    for i, (k, v) in enumerate(ip.items()):
        if i == label_order:
            tr = tr.has_label(label)
        tr = tr.has(k, v)
        add_tr = add_tr.property(k, v)
    if i < label_order:
        tr = tr.has_label(label)
    tr = tr.fold().coalesce(
        __.unfold(),
        add_tr
    )
    if op:
        set_props = __
        for k, v in op.items():
            set_props = set_props.property(k, v)
        tr = tr.union(
            __.properties(*list(op.keys())).drop(),
            set_props
        )
    return tr


class GtxTx_Gts(GraphTraversalSource):
    """
    A GraphTraversalSource whose `tx()` method makes a GtxTransation.
    """

    def tx(self):
        tx = super().tx()
        return GtxTransaction(tx)


class GTX(GraphTraversalSource):
    """
    The purpose of this class is to be "a GraphTraversalSource that was spawned
    by a Transaction". It retains a reference to the tx that spawned it, so
    that `commit()` and `rollback()` can be called here, instead of having to
    separately keep track of the tx.
    """

    def __init__(self, gts, tx):
        """
        @param gts: a GraphTraversalSource
        @param tx: a Transaction
        """
        super().__init__(gts.graph, gts.traversal_strategies, gts.bytecode)
        self.tx = tx

    def commit(self):
        return self.tx.commit()

    def rollback(self):
        return self.tx.rollback()


class GtxTransaction(Transaction):
    """
    The purpose of this class is to be "a Transaction that spawns a GTX".
    See above.
    """

    def __init__(self, tx):
        """
        @param tx: a Transaction
        """
        super().__init__(tx._g, tx._remote_connection)

    def begin(self):
        gts = super().begin()
        return GTX(gts, self)

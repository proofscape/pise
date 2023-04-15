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

import math
from itertools import count

from gremlin_python.process.graph_traversal import __

from pfsc.constants import IndexType
from pfsc.gdb.gremlin.util import lp_covers


def ix002682(mii, gtx, N=12):
    """
    Bundle N new nodes or edges into each traversal.

    Note, the N==1 case is equivalent to the ix002681 function.

    Ran tests on the 'test.hist.lit' repo, on 18 Dec 2021, on a t2.micro EC2
    instance (Ubuntu 20.04), connecting to Neptune on a db.t3.medium (2 vCPU,
    4 GB RAM):

     N     Runtime for this function (s)
    ---    -----------------------------
      1     22.086
      5     10.147
      8      8.763
     10      8.506
     12      8.165
     15      8.537
     20      8.975
     50     14.947
    100     (raised MemoryLimitExceededException)

    The error for N==100 was raised inside a GremlinServerError,
    at gremlin_python/driver/protocol.py", line 142.

    EDIT: In subsequent testing, I started seeing more weird hangs and errors
    even on much smaller values of N, including the optimal 12. Would be nice
    to get to the bottom of this, and see if we can use this function somehow.
    """
    lp_maj_to_db_uid = {}
    if mii.V_add:
        mii.note_begin_indexing_phase(260)
        kNodes = [mii.get_kNode(uid) for uid in mii.V_add]
        G = math.ceil(len(kNodes) / N)
        b = 0
        lp_maj = []
        for _ in range(G):
            tr = gtx
            a, b = b, b + N
            for u in kNodes[a:b]:
                tr = tr.add_v(u.node_type)
                for k, v in u.get_property_dict().items():
                    tr = tr.property(k, v)
                tr.store('ids').by(__.id_())
                lp_maj.append((u.libpath, u.major))
                mii.note_task_element_completed(260)
            ids = tr.cap('ids').next()
            for k, v in zip(lp_maj, ids):
                lp_maj_to_db_uid[k] = v

    new_targeting_relns = []
    if mii.E_add:
        mii.note_begin_indexing_phase(280)
        kRelns = [mii.get_kReln(uid) for uid in mii.E_add]
        G = math.ceil(len(kRelns) / N)
        b = 0
        for _ in range(G):
            tr = gtx
            a, b = b, b + N
            for r in kRelns[a:b]:
                if r.reln_type == IndexType.TARGETS:
                    new_targeting_relns.append(r)
                head_id = lp_maj_to_db_uid.get((r.head_libpath, r.head_major))
                if head_id is None:
                    tr = lp_covers(r.head_libpath, r.head_major,
                                   tr.V().has_label(r.head_type))
                else:
                    tr = tr.V(head_id)
                tr = tr.as_('head')
                tail_id = lp_maj_to_db_uid.get((r.tail_libpath, r.tail_major))
                if tail_id is None:
                    tr = lp_covers(r.tail_libpath, r.tail_major,
                                   tr.V().has_label(r.tail_type))
                else:
                    tr = tr.V(tail_id)
                tr = tr.add_e(r.reln_type).to('head')
                for k, v in r.get_structured_property_dict()['reln'].items():
                    tr = tr.property(k, v)
                mii.note_task_element_completed(280)
            tr.iterate()
    return new_targeting_relns


def ix002681(mii, gtx):
    """
    Make a separate traversal for each new node and edge.
    """
    lp_maj_to_db_uid = {}
    if mii.V_add:
        mii.note_begin_indexing_phase(260)
        kNodes = [mii.get_kNode(uid) for uid in mii.V_add]
        for u in kNodes:
            tr = gtx.add_v(u.node_type).as_('v')
            for k, v in u.get_property_dict().items():
                tr = tr.property(k, v)
            db_uid = tr.select('v').by(__.id_()).next()
            lp_maj_to_db_uid[(u.libpath, u.major)] = db_uid
            mii.note_task_element_completed(260)
    new_targeting_relns = []
    if mii.E_add:
        mii.note_begin_indexing_phase(280)
        kRelns = [mii.get_kReln(uid) for uid in mii.E_add]
        for r in kRelns:
            if r.reln_type == IndexType.TARGETS:
                new_targeting_relns.append(r)
            head_id = lp_maj_to_db_uid.get((r.head_libpath, r.head_major))
            if head_id is None:
                tr = lp_covers(r.head_libpath, r.head_major,
                               gtx.V().has_label(r.head_type))
            else:
                tr = gtx.V(head_id)
            tr = tr.as_('head')
            tail_id = lp_maj_to_db_uid.get((r.tail_libpath, r.tail_major))
            if tail_id is None:
                tr = lp_covers(r.tail_libpath, r.tail_major,
                               tr.V().has_label(r.tail_type))
            else:
                tr = tr.V(tail_id)
            tr = tr.add_e(r.reln_type).to('head')
            for k, v in r.get_structured_property_dict()['reln'].items():
                tr = tr.property(k, v)
            tr.iterate()
            mii.note_task_element_completed(280)
    return new_targeting_relns


def ix002680(mii, gtx):
    """
    Try forming all new nodes and edges in a single traversal.

    DON'T USE.

    Doesn't work in practice, because even `test.hist.lit` is already too big.
    The connection is closed because we tried to pass a message that was too
    large. (True on both gremlin-server (TinkerGraph) and JanusGraph 0.6.0
    default config.)
    """
    tr = None
    lp_maj_to_name = {}
    next_index = 0
    if mii.V_add:
        tr = gtx  # .with_('evaluationTimeout', 20000)
        kNodes = [mii.get_kNode(uid) for uid in mii.V_add]
        for i, u in enumerate(kNodes):
            name = str(i)
            lp_maj_to_name[(u.libpath, u.major)] = name
            tr = tr.add_v(u.node_type)
            for k, v in u.get_property_dict().items():
                tr = tr.property(k, v)
            tr = tr.as_(name)
        next_index = i + 1

    new_targeting_relns = []
    if mii.E_add:
        tr = tr or gtx  # .with_('evaluationTimeout', 20000)
        kRelns = [mii.get_kReln(uid) for uid in mii.E_add]
        counter = count(next_index)
        for r in kRelns:
            head_name = lp_maj_to_name.get((r.head_libpath, r.head_major))
            if head_name is None:
                head_name = str(next(counter))
                tr = lp_covers(r.head_libpath, r.head_major,
                               tr.V().has_label(r.head_type)).as_(head_name)
            tail_name = lp_maj_to_name.get((r.tail_libpath, r.tail_major))
            if tail_name is None:
                tr = lp_covers(r.tail_libpath, r.tail_major,
                               tr.V().has_label(r.tail_type))
                tr = tr.add_e(r.reln_type)
            else:
                tr = tr.add_e(r.reln_type).from_(tail_name)
            tr = tr.to(head_name)
            for k, v in r.get_structured_property_dict()['reln'].items():
                tr = tr.property(k, v)
        new_targeting_relns = [k for k in kRelns if
                               k.reln_type == IndexType.TARGETS]
    if tr:
        tr.iterate()
    return new_targeting_relns

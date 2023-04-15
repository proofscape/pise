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
Indexing functions for Cypher.

Here we experiment with various ways of implementing the various indexing
operations.
"""

from collections import defaultdict

from pfsc.constants import IndexType
from pfsc.gdb.k import make_kNode_from_jNode


def ix00220(mii, tx, verbose=False):
    if mii.V_cut:
        mii.note_begin_indexing_phase(220)
        ids = [mii.existing_k_nodes[uid].db_uid for uid in mii.V_cut]
        if verbose:
            print(f'Marking {len(ids)} j-nodes as cut.')
        tx.run("""
            MATCH (u {repopath: $repopath}) WHERE id(u) IN $ids SET u.cut = $cut
        """, repopath=mii.repopath, ids=ids, cut=mii.major)
        mii.note_task_element_completed(220, len(ids))


def ix00240(mii, tx, verbose=False):
    if mii.E_cut:
        mii.note_begin_indexing_phase(240)
        ids = [mii.existing_k_relns[uid].db_uid for uid in mii.E_cut]
        if verbose:
            print(f'Marking {len(ids)} j-relns as cut.')
        tx.run("""
            MATCH ()-[r {repopath: $repopath}]->() WHERE id(r) IN $ids SET r.cut = $cut
        """, repopath=mii.repopath, ids=ids, cut=mii.major)
        mii.note_task_element_completed(240, len(ids))


def ix00260(mii, tx):
    if mii.V_add:
        mii.note_begin_indexing_phase(260)
        kNodes = [mii.get_kNode(uid) for uid in mii.V_add]
        print(f'Adding {len(kNodes)} new j-nodes.')
        for k in kNodes:
            res = tx.run(f"""
                CREATE (:{k.node_type} {{
                  libpath: $libpath, modpath: $modpath, repopath: $repopath,
                  major: $major, minor: $minor, patch: $patch, cut: $cut
                  {k.write_extra_props_internal_pairs(initialComma=True)}
                }})
                """, libpath=k.libpath, modpath=k.modpath, repopath=k.repopath,
                         major=k.major, minor=k.minor, patch=k.patch, cut=k.cut, **k.extra_props
                         )
            #report.add_step(get_counters(res), add_nodes=kNodes)
            mii.note_task_element_completed(260)


def ix00261(mii, tx, verbose=False):
    """
    We create all nodes with one Cypher query, using UNWIND.
    """
    if mii.V_add:
        mii.note_begin_indexing_phase(260)
        kNodes = [mii.get_kNode(uid) for uid in mii.V_add]
        if verbose:
            print(f'Adding {len(kNodes)} new j-nodes.')
        props_by_node_type = defaultdict(list)
        for k in kNodes:
            props_by_node_type[k.node_type].append(k.get_property_dict())
        for node_type, props in props_by_node_type.items():
            if verbose:
                print(f'  ({len(props)}) {node_type}')
            # On use of SET to set a whole dictionary of properties:
            #   <https://neo4j.com/docs/cypher-manual/4.0/clauses/create/#create-create-multiple-nodes-with-a-parameter-for-their-properties>
            tx.run(
                f"""
                UNWIND $props as prop
                CREATE (u:{node_type})
                SET u = prop
                """,
                props=props
            )
        mii.note_task_element_completed(260, len(kNodes))


def ix00280(mii, tx, diagnostics=False):
    new_targeting_relns = []
    if mii.E_add:
        kRelns = [mii.get_kReln(uid) for uid in mii.E_add]
        print(f'Adding {len(kRelns)} new j-relns.')
        for k in kRelns:
            # ------------------------------------------
            if diagnostics:
                # This allows us to see the node pairs that are being matched,
                # and on which relations are to be added.
                res = tx.run(f"""
                    MATCH (t {{libpath: $tail_libpath}}), (h {{libpath: $head_libpath}})
                    WHERE t.major <= $tail_major < t.cut AND h.major <= $head_major < h.cut
                    RETURN t, h
                    """, tail_libpath=k.tail_libpath, tail_major=k.tail_major,
                             head_libpath=k.head_libpath, head_major=k.head_major
                             )
                print(f'Matched node pairs for {k.reln_type} from {k.tail_major} to {k.head_major}:')
                for t, h in res:
                    kt, kh = map(make_kNode_from_jNode, [t, h])
                    print(f'{kt} {kh}')
            # ------------------------------------------
            res = tx.run(f"""
                MATCH (t {{libpath: $tail_libpath}}), (h {{libpath: $head_libpath}})
                WHERE t.major <= $tail_major < t.cut AND h.major <= $head_major < h.cut
                CREATE (t)-[:{k.reln_type} {{
                  modpath: $modpath, repopath: $repopath,
                  major: $major, minor: $minor, patch: $patch, cut: $cut
                  {k.write_extra_props_internal_pairs(initialComma=True)}
                }}]->(h)
                """, tail_libpath=k.tail_libpath, tail_major=k.tail_major,
                         head_libpath=k.head_libpath, head_major=k.head_major,
                         modpath=k.modpath, repopath=k.repopath,
                         major=k.major, minor=k.minor, patch=k.patch, cut=k.cut, **k.extra_props
                         )
            #report.add_step(get_counters(res), add_relns=kRelns)
            if k.reln_type == IndexType.TARGETS:
                new_targeting_relns.append(k)
    return new_targeting_relns


def ix00281(mii, tx, diagnostics=False):
    new_targeting_relns = []
    if mii.E_add:
        kRelns = [mii.get_kReln(uid) for uid in mii.E_add]
        print(f'Adding {len(kRelns)} new j-relns.')
        props_by_reln_type = defaultdict(list)
        for k in kRelns:
            props_by_reln_type[k.reln_type].append(k.get_property_dict())
        # TODO: {k.write_extra_props_internal_pairs(initialComma=True)}
        for reln_type, props in props_by_reln_type.items():
            ix00281c(tx, props, reln_type)
        new_targeting_relns = [k for k in kRelns if k.reln_type == IndexType.TARGETS]
    return new_targeting_relns


def ix00281c(tx, props, reln_type):
    tx.run(
        f"""
        UNWIND $props as prop
        MATCH (t {{libpath: prop.tail_libpath}}), (h {{libpath: prop.head_libpath}})
        WHERE t.major <= prop.tail_major < t.cut AND h.major <= prop.head_major < h.cut
        CREATE (t)-[:{reln_type} {{
          modpath: prop.modpath, repopath: prop.repopath,
          major: prop.major, minor: prop.minor, patch: prop.patch, cut: prop.cut
        }}]->(h)
        """, props=props
    )


def ix00282s(mii, tx, diagnostics=False):
    """
    This time we divide the relations up according to "composite type",
    which means tail type + reln type + head type.

    282s uses structured property dicts
    """
    new_targeting_relns = []
    if mii.E_add:
        mii.note_begin_indexing_phase(280)
        kRelns = [mii.get_kReln(uid) for uid in mii.E_add]
        if diagnostics:
            print(f'Adding {len(kRelns)} new j-relns.')
        props_by_composite_type = defaultdict(list)
        for k in kRelns:
            comp_type = f'{k.tail_type}:{k.reln_type}:{k.head_type}'
            props_by_composite_type[comp_type].append(k.get_structured_property_dict())
        for comp_type, props in props_by_composite_type.items():
            if diagnostics:
                print(f'  ({len(props)}) {comp_type}')
            tail_type, reln_type, head_type = comp_type.split(":")
            ix00282c03s(tx, props, tail_type, reln_type, head_type)
        new_targeting_relns = [k for k in kRelns if k.reln_type == IndexType.TARGETS]
        mii.note_task_element_completed(280, len(kRelns))
    return new_targeting_relns


def ix00282f(mii, tx, diagnostics=False):
    """
    This time we divide the relations up according to "composite type",
    which means tail type + reln type + head type.

    282f uses flat property dicts
    """
    new_targeting_relns = []
    if mii.E_add:
        kRelns = [mii.get_kReln(uid) for uid in mii.E_add]
        if diagnostics:
            print(f'Adding {len(kRelns)} new j-relns.')
        props_by_composite_type = defaultdict(list)
        for k in kRelns:
            comp_type = f'{k.tail_type}:{k.reln_type}:{k.head_type}'
            props_by_composite_type[comp_type].append(k.get_property_dict())
        for comp_type, props in props_by_composite_type.items():
            if diagnostics:
                print(f'  ({len(props)}) {comp_type}')
            tail_type, reln_type, head_type = comp_type.split(":")
            ix00282c03f(tx, props, tail_type, reln_type, head_type)
        new_targeting_relns = [k for k in kRelns if k.reln_type == IndexType.TARGETS]
    return new_targeting_relns

# ----------------------------------------------------------------------
# NOTE: In timing tests, I observed _no_ significant difference
# between methods 01, 02, and 03 below. Perhaps internally they are all the same?
#
# NOTE: Do not actually _use_ method 01, 02, or 03, since they miss extra_props.
# Only 03s or 03f may actually be used in production.
#
# In timings, 03s seems to be a bit faster than 03f. On repo `test.hist.lit` I was
# getting ~3s for 03f and ~2.5s for 03s.
#
# In terms of implementation, 03s is certainly more elegant as well.

def ix00282c01(tx, props, tail_type, reln_type, head_type):
    """
    Name libpath as property on node; put major ranges afterward.
    """
    tx.run(
        f"""
        UNWIND $props as prop
        MATCH (t:{tail_type} {{libpath: prop.tail_libpath}}), (h:{head_type} {{libpath: prop.head_libpath}})
        WHERE t.major <= prop.tail_major < t.cut AND h.major <= prop.head_major < h.cut
        CREATE (t)-[:{reln_type} {{
          modpath: prop.modpath, repopath: prop.repopath,
          major: prop.major, minor: prop.minor, patch: prop.patch, cut: prop.cut
        }}]->(h)
        """, props=props
    )


def ix00282c02(tx, props, tail_type, reln_type, head_type):
    """
    Put major ranges and libpaths as conditions outside node patterns.
    Major ranges come first.
    """
    tx.run(
        f"""
        UNWIND $props as prop
        MATCH (t:{tail_type}), (h:{head_type})
        WHERE t.major <= prop.tail_major < t.cut AND t.libpath = prop.tail_libpath
          AND h.major <= prop.head_major < h.cut AND h.libpath = prop.head_libpath
        CREATE (t)-[:{reln_type} {{
          modpath: prop.modpath, repopath: prop.repopath,
          major: prop.major, minor: prop.minor, patch: prop.patch, cut: prop.cut
        }}]->(h)
        """, props=props
    )


def ix00282c03(tx, props, tail_type, reln_type, head_type):
    """
    Put major ranges and libpaths as conditions outside node patterns.
    Libpaths come first.
    """
    tx.run(
        f"""
        UNWIND $props as prop
        MATCH (t:{tail_type}), (h:{head_type})
        WHERE t.libpath = prop.tail_libpath AND t.major <= prop.tail_major < t.cut 
          AND h.libpath = prop.head_libpath AND h.major <= prop.head_major < h.cut
        CREATE (t)-[:{reln_type} {{
          modpath: prop.modpath, repopath: prop.repopath,
          major: prop.major, minor: prop.minor, patch: prop.patch, cut: prop.cut
        }}]->(h)
        """, props=props
    )


def ix00282c03s(tx, props, tail_type, reln_type, head_type):
    """
    This one uses the structured props lookup.
    """
    tx.run(
        f"""
        UNWIND $props as prop
        MATCH (t:{tail_type}), (h:{head_type})
        WHERE t.libpath = prop.tail.libpath AND t.major <= prop.tail.major < t.cut 
          AND h.libpath = prop.head.libpath AND h.major <= prop.head.major < h.cut
        CREATE (t)-[r:{reln_type}]->(h)
        SET r = prop.reln
        """, props=props
    )


def ix00282c03f(tx, props, tail_type, reln_type, head_type):
    """
    This one uses the flat props lookup.

    ** NOTE **  We assume that, for a given reln_type, the set of extra_props
      will always be the same!
    """
    reln_prop_names = set(props[0].keys()) - {'tail_libpath', 'tail_major', 'head_libpath', 'head_major'}
    eqns = ', '.join(f'{k}: prop.{k}' for k in reln_prop_names)
    query = f"""
    UNWIND $props as prop
    MATCH (t:{tail_type}), (h:{head_type})
    WHERE t.libpath = prop.tail_libpath AND t.major <= prop.tail_major < t.cut 
      AND h.libpath = prop.head_libpath AND h.major <= prop.head_major < h.cut
    CREATE (t)-[:{reln_type} {{{eqns}}}]->(h)
    """
    #print(query)
    tx.run(query, props=props)

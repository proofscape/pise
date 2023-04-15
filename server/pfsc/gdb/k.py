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

"""k-Nodes and k-Relns. """

from gremlin_python.process.traversal import (
    T as gremlin_T,
    Direction as gremlin_Direction
)
import neo4j.graph
import redisgraph

import pfsc.constants


class Versioned:
    """
    Currently just a superclass for kObj; potentially for anything that
    is versioned.
    """

    def __init__(self, major, minor, patch, cut):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.cut = cut

    def __str__(self):
        if self.major == pfsc.constants.WIP_TAG:
            s = self.major
        elif self.major is None:
            # This case arises if we form a kNode on the (:Void) node.
            s = 'None'
        else:
            s = f'v{int(self.major)}.{int(self.minor)}.{int(self.patch)}'
        s += f'/{self.cut}'
        return s


class kObj(Versioned):
    """
    Superclass for kNodes and kRelns.
    """

    def __init__(self, modpath, repopath,
                 major, minor, patch, cut,
                 db_uid=None, extra_props=None):
        super().__init__(major, minor, patch, cut)
        self.modpath = modpath
        self.repopath = repopath
        self.db_uid = db_uid
        self.extra_props = extra_props or {}

    def update_extra_props(self, d):
        self.extra_props.update(d)

    def set_extra_prop(self, k, v):
        self.extra_props[k] = v

    def write_extra_props_internal_pairs(self, initialComma=False, finalComma=False):
        s = ', '.join([f'{k}: ${k}' for k in self.extra_props])
        t = ', ' + s if s and initialComma else s
        t = t + ', ' if s and finalComma else t
        return t


class kNode(kObj):
    """
    This class provides an alternative representation of graph database nodes.
    """

    def __init__(self, node_type, libpath, modpath, repopath,
                 major, minor, patch, cut=pfsc.constants.INF_TAG,
                 db_uid=None, extra_props=None):
        """
        :param node_type: a value of the IndexType enum
        :param libpath: the libpath of the entity represented by this node
        :param modpath: the libpath of the module in which this entity is defined
        :param repopath: the libpath of the repo to which this entity belongs
        :param major: the major version string for the build in which this
          entity first appeared
        :param minor: the minor version string for the build in which this
          entity first appeared
        :param patch: the patch version string for the build in which this
          entity first appeared
        :param cut: the major version string for the build in which this
          entity first disappeared
        :param db_uid: the id assigned to the node within the graph database
        :param extra_props: optional place to pass a dictionary of extra properties
          to be set on the resulting j-object.
        """
        super().__init__(modpath, repopath, major, minor, patch, cut,
                         db_uid=db_uid, extra_props=extra_props)
        self.node_type = node_type
        self.libpath = libpath
        self.uid = libpath

    def __eq__(self, other):
        return (
            self.node_type == other.node_type and
            self.libpath == other.libpath and
            self.modpath == other.modpath and
            self.repopath == other.repopath and
            self.major == other.major and
            self.minor == other.minor and
            self.patch == other.patch and
            self.cut == other.cut
        )

    def __str__(self):
        return f'{self.node_type}:{self.libpath}@{super().__str__()}'

    def __repr__(self):
        return str(self)

    def get_property_dict(self):
        basic = {
            'libpath': self.libpath,
            'modpath': self.modpath,
            'repopath': self.repopath,
            'major': self.major,
            'minor': self.minor,
            'patch': self.patch,
            'cut': self.cut,
        }
        basic.update(self.extra_props)
        return basic


class kReln(kObj):
    """
    This class provides an alternative representation of edges/relationships
    from our graph database.
    """

    def __init__(self, tail_type, tail_libpath, tail_major, reln_type, head_type, head_libpath, head_major,
                 modpath, repopath,
                 major, minor, patch, cut=pfsc.constants.INF_TAG, db_uid=None, extra_props=None):
        """
        To be clear, a relation goes _from_ tail _to_ head:

                             tail -[relation]-> head

        :param tail_libpath: the libpath of the entity represented by the tail
          end of this relation
        :param tail_major: the major version number of the entity represented
          by the tail end of this relation
        :param reln_type: a value of the IndexType enum
        :param head_libpath: the libpath of the entity represented by the head
          end of this relation
        :param head_major: the major version number of the entity represented
          by the head end of this relation
        :param modpath: the libpath of the module in which this relation is defined
        :param repopath: the libpath of the repo in which this relation is defined
        :param major: the major version string for the build in which this
          relation first appeared
        :param minor: the minor version string for the build in which this
          relation first appeared
        :param patch: the patch version string for the build in which this
          relation first appeared
        :param cut: the major version string for the build in which this
          relation first disappeared
        :param db_uid: the id assigned to the reln within the graph database
        :param extra_props: optional place to pass a dictionary of extra properties
          to be set on the resulting j-object.
        """
        super().__init__(modpath, repopath, major, minor, patch, cut,
                         db_uid=db_uid, extra_props=extra_props)
        self.tail_type = tail_type
        self.tail_libpath = tail_libpath
        self.tail_major = tail_major
        self.reln_type = reln_type
        self.head_type = head_type
        self.head_libpath = head_libpath
        self.head_major = head_major
        self.uid = f'{self.tail_libpath}:{self.reln_type}:{self.head_libpath}'

    def __str__(self):
        return f'{self.uid}@{super().__str__()}'

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return (
            self.uid == other.uid and
            self.modpath == other.modpath and
            self.repopath == other.repopath and
            self.major == other.major and
            self.minor == other.minor and
            self.patch == other.patch and
            self.cut == other.cut
        )

    def get_property_dict(self):
        basic = {
            'tail_libpath': self.tail_libpath,
            'tail_major': self.tail_major,
            'head_libpath': self.head_libpath,
            'head_major': self.head_major,
            'modpath': self.modpath,
            'repopath': self.repopath,
            'major': self.major,
            'minor': self.minor,
            'patch': self.patch,
            'cut': self.cut,
        }
        basic.update(self.extra_props)
        return basic

    def get_structured_property_dict(self):
        basic = {
            'modpath': self.modpath,
            'repopath': self.repopath,
            'major': self.major,
            'minor': self.minor,
            'patch': self.patch,
            'cut': self.cut,
        }
        basic.update(self.extra_props)
        return {
            'reln': basic,
            'tail': {
                'libpath': self.tail_libpath,
                'major': self.tail_major,
            },
            'head': {
                'libpath': self.head_libpath,
                'major': self.head_major,
            }
        }


def make_kNode_from_jNode(j):
    """
    Factory function to make a kNode from a node instance coming from the graph
    database driver.
    :param j: a node instance from the graph database driver
    :return: an instance of our `kNode` class representing the same info
    """
    # NB: we have made a design choice _not_ to take advantage of the ability of
    # j-nodes to carry multiple labels. For us, a node has a single "type", be it
    # `Node`, `Deduc`, `Anno`, what have you.
    # EDIT: What was a design choice when working with Neo4j is actually a
    # _necessity_ now that we also work with RedisGraph, where only a single
    # node label is supported.
    # See <https://oss.redis.com/redisgraph/cypher_support/#structural-types>
    if isinstance(j, redisgraph.node.Node):
        node_type = j.label
        p = j.properties
        db_uid = j.id
    elif isinstance(j, neo4j.graph.Node):
        assert len(j.labels) == 1
        node_type = list(j.labels)[0]
        p = j
        db_uid = j.id
    else:
        # Otherwise we should be using Gremlin, in which case `j` should just
        # be a plain dictionary, representing an `elementMap()`.
        assert isinstance(j, dict)
        node_type = j[gremlin_T.label]
        p = j
        db_uid = j[gremlin_T.id]
    libpath = p.get('libpath')
    modpath = p.get('modpath')
    repopath = p.get('repopath')
    major = p.get('major')
    minor = p.get('minor')
    patch = p.get('patch')
    cut = p.get('cut')
    return kNode(node_type, libpath, modpath, repopath, major, minor, patch, cut, db_uid)


def make_kReln_from_jReln(j):
    """
    Factory function to make a kReln from an edge/relationship from the gdb driver.
    :param j: either a triple u, e, v, or a dictionary with keys 'u', 'e', 'v',
        consisting of an edge/relationship e and its two endpoint nodes u and v.
    :return: an instance of our `kReln` class representing the same info as the edge/relationship.
    """
    if isinstance(j, dict):
        u, e, v = j['u'], j['e'], j['v']
    else:
        u, e, v = j
    if isinstance(e, redisgraph.edge.Edge):
        # We don't know which of u and v is src node and dst node
        # (aka tail and head) of the relation. We have to find out
        # by consulting the `e.src_node` and `e.dest_node` properties.
        nodes = {u.id: u, v.id: v}
        tail_type = nodes[e.src_node].label
        head_type = nodes[e.dest_node].label
        tail_props = nodes[e.src_node].properties
        head_props = nodes[e.dest_node].properties
        reln_type = e.relation
        p = e.properties
        db_uid = e.id
    elif isinstance(e, neo4j.graph.Relationship):
        tail_type = list(e.start_node.labels)[0]
        head_type = list(e.end_node.labels)[0]
        tail_props = e.start_node
        head_props = e.end_node
        reln_type = e.type
        p = e
        db_uid = e.id
    else:
        # Otherwise we should be using Gremlin, in which case `u`, `e`, and `v`
        # should just be plain dictionaries, representing `elementMap()`s.
        assert all(isinstance(x, dict) for x in [u, e, v])
        nodes = {u[gremlin_T.id]: u, v[gremlin_T.id]: v}
        out_info = e[gremlin_Direction.OUT]
        in_info = e[gremlin_Direction.IN]
        tail_type = out_info[gremlin_T.label]
        head_type = in_info[gremlin_T.label]
        tail_props = nodes[out_info[gremlin_T.id]]
        head_props = nodes[in_info[gremlin_T.id]]
        reln_type = e[gremlin_T.label]
        p = e
        db_uid = e[gremlin_T.id]
        # Special handling for reln IDs in JanusGraph: These look like, e.g.,
        #   {'@type': 'janusgraph:RelationIdentifier', '@value': {'relationId': '3zf6-2t8w-9hx-2q4g'}}
        # when returned, but you need to use the inner 'relationId' part if you
        # want to locate relations by their ID.
        if isinstance(db_uid, dict) and db_uid.get('@type') == 'janusgraph:RelationIdentifier':
            db_uid = db_uid['@value']['relationId']
    # Must take care and use `get` in case the desired properties are
    # undefined. For example, this allows us to seamlessly handle the case
    # with a MOVE reln, where the head node is the (:Void) node (which has
    # no properties). Neo4j's client library actually gracefully returns
    # `None` even if you use `head_props['libpath']`, but RedisGraph's does not.
    tail_libpath = tail_props.get('libpath')
    tail_major = tail_props.get('major')
    head_libpath = head_props.get('libpath')
    head_major = head_props.get('major')
    modpath = p.get('modpath')
    repopath = p.get('repopath')
    major = p.get('major')
    minor = p.get('minor')
    patch = p.get('patch')
    cut = p.get('cut')
    return kReln(tail_type, tail_libpath, tail_major, reln_type, head_type, head_libpath, head_major,
                 modpath, repopath, major, minor, patch, cut, db_uid)

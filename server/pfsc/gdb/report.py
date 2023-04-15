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
Old index report classes. For now defunct. Might want to revive later.
"""

import json


class IndexReport:

    def __init__(self):
        self.steps = []

    def __str__(self):
        return '\n'.join(str(step) for step in self.steps)

    def get_full_summary(self):
        fs = IndexFullSummary()
        fs.init_with_index_report(self)
        return fs

    def add_step(
            self,
            counters,
            intention=None,
            remove_nodes=None,
            update_nodes=None,
            add_nodes=None,
            detach_relns=None,
            remove_relns=None,
            update_relns=None,
            add_relns=None
    ):
        """
        Convenience method for forming an IndexStep and recording it.

        A `counters` arg must be passed. This should be an instance of
        the neo4j.SummaryCounters class. It serves as a record of what actually
        took place, at the level of number of nodes/relationships added/deleted, etc.

        Apart from the counters, you should indicate the _intention_.
        Here it is possible to record more detailed information.
        You may either pass an IndexIntention object under the `intention` kwarg, or
        you may pass any data to the other various kwargs in order to record the intention
        of the transaction.

        For example, if adding three nodes, the libpaths of the three nodes may be
        recorded under `add_nodes`. Meanwhile, the counters will show whether three
        nodes actually were successfully added or not.
        """
        intention = intention or IndexIntention(
            remove_nodes=remove_nodes, update_nodes=update_nodes, add_nodes=add_nodes,
            detach_relns=detach_relns,
            remove_relns=remove_relns, update_relns=update_relns, add_relns=add_relns
        )
        step = IndexStep(intention, counters)
        self.steps.append(step)

class IndexFullSummary:

    def __init__(self):
        self.intention = IndexIntention()
        self.nodes_created = 0
        self.nodes_deleted = 0
        self.relationships_created = 0
        self.relationships_deleted = 0

    def init_with_index_report(self, index_report):
        self.intention = sum([s.intention for s in index_report.steps], IndexIntention())
        self.nodes_created = sum([s.counters.nodes_created for s in index_report.steps])
        self.nodes_deleted = sum([s.counters.nodes_deleted for s in index_report.steps])
        self.relationships_created = sum([s.counters.relationships_created for s in index_report.steps])
        self.relationships_deleted = sum([s.counters.relationships_deleted for s in index_report.steps])

    def __repr__(self):
        return json.dumps(self.serializable_rep(), indent=4)

    def serializable_rep(self):
        return {
            'intention': self.intention.serializable_rep(),
            'nodes_created': self.nodes_created,
            'nodes_deleted': self.nodes_deleted,
            'relationships_created': self.relationships_created,
            'relationships_deleted': self.relationships_deleted
        }

class IndexStep:

    def __init__(self, intention, counters):
        self.intention = intention
        self.counters = counters

    def __str__(self):
        return f'Intention:\n{self.intention}\nResults:\n{self.counters}'


class IndexIntention:

    def __init__(
            self,
            remove_nodes=None,
            update_nodes=None,
            add_nodes=None,
            detach_relns=None,
            remove_relns=None,
            update_relns=None,
            add_relns=None
    ):
        """
        :param remove_nodes: set of kNode UIDs
        :param update_nodes: list of kNodes
        :param add_nodes: list of kNodes
        :param detach_relns: set of kReln UIDs
        :param remove_relns: set of kReln UIDs
        :param update_relns: list of kRelns
        :param add_relns: list of kRelns
        """
        self.remove_nodes = remove_nodes
        self.update_nodes = self.listToLookup(update_nodes)
        self.add_nodes = self.listToLookup(add_nodes)
        # Note: to "detach" relationships does not, in the final result, mean
        # anything other than to remove them; the purpose of recording relationships
        # here is to indicate the _way_ in which they were removed, namely, by
        # detaching some nodes.
        self.detach_relns = detach_relns
        self.remove_relns = remove_relns
        self.update_relns = self.listToLookup(update_relns)
        self.add_relns = self.listToLookup(add_relns)

    @staticmethod
    def listToLookup(L):
        """
        Turn a list of kNodes or kRelns into a dict of the form:

            {
                uid: {
                    properties
                }
            }

        with the properties being determined by the class's `get_property_dict` method.

        If a dict is passed, return it unchanged.
        If None is passed, return it unchanged.

        :param L: the list to be converted, or a dict, or None
        :return: dict, or None
        """
        if L is None: return None
        if isinstance(L, dict): return L
        return {k.uid:k.get_property_dict() for k in L}

    @staticmethod
    def merge_lookups(a, b):
        """
        a and b can be sets or dicts
        Either can be None
        We return the result of combining them.
        Return value will not be identical with either a or b, i.e. we make copies.
        Note however that we do _not_ make _deep_ copies.
        """
        if a is None and b is None:
            return None
        elif a is None:
            return b.copy()
        elif b is None:
            return a.copy()
        else:
            c = a.copy()
            c.update(b)
            return c

    def __add__(self, other):
        assert isinstance(other, IndexIntention)
        return IndexIntention(
            remove_nodes=self.merge_lookups(self.remove_nodes, other.remove_nodes),
            update_nodes=self.merge_lookups(self.update_nodes, other.update_nodes),
            add_nodes=self.merge_lookups(self.add_nodes, other.add_nodes),
            detach_relns=self.merge_lookups(self.detach_relns, other.detach_relns),
            remove_relns=self.merge_lookups(self.remove_relns, other.remove_relns),
            update_relns=self.merge_lookups(self.update_relns, other.update_relns),
            add_relns=self.merge_lookups(self.add_relns, other.add_relns),
        )

    @staticmethod
    def make_serializable(A):
        """
        Make sets serializable by converting them into dicts.
        Leave dicts unchanged.
        """
        if isinstance(A, set):
            return {a:1 for a in A}
        else:
            return A

    def serializable_rep(self):
        d = {}
        if self.remove_nodes is not None:
            d['remove_nodes'] = self.make_serializable(self.remove_nodes)
        if self.update_nodes is not None:
            d['update_nodes'] = self.make_serializable(self.update_nodes)
        if self.add_nodes is not None:
            d['add_nodes'] = self.make_serializable(self.add_nodes)
        if self.detach_relns is not None:
            d['detach_relns'] = self.make_serializable(self.detach_relns)
        if self.remove_relns is not None:
            d['remove_relns'] = self.make_serializable(self.remove_relns)
        if self.update_relns is not None:
            d['update_relns'] = self.make_serializable(self.update_relns)
        if self.add_relns is not None:
            d['add_relns'] = self.make_serializable(self.add_relns)
        return d

    def __repr__(self):
        d = self.serializable_rep()
        return json.dumps(d, indent=4)

    def __str__(self):
        d = self.serializable_rep()
        return json.dumps(d, indent=4)

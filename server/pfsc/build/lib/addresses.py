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

from pfsc.gdb import get_graph_reader


class ForestAddress:
    """
    In a given version, every deduction has a unique "forest address", a string
    equal to the ":"-join of the libpaths of all its ancestors, from TLD down
    to (and including) itself.

    Think of it as being like a postal address, only written backwards, i.e.
    starting with the broadest, most general element, and proceeding toward the
    most specific.

    In the forest of all deductions, this address would tell you how to get from
    the forest floor, all the way up to the deduction in question.
    """

    def __init__(self, libpath, tol_maj):
        """
        :param libpath: the libpath of the deduction of interest.
        :param tol_maj: "tolerant major version number": this means what we
          actually want is a major version number, but you can pass a full
          version string if you wish.
        """
        self.libpath = libpath
        self.version = tol_maj
        gr = get_graph_reader()
        self.ancestors = list(gr.get_ancestor_chain(libpath, tol_maj))
        self.address = ":".join(self.ancestors)
        self.n = len(self.ancestors)

    def __hash__(self):
        return hash(self.libpath)

    def __repr__(self):
        return self.address

    def __len__(self):
        """
        The length of an address is the number of libpaths of which it is made up.
        """
        return self.n

    def __eq__(self, other):
        return self.address == other.address

    def __lt__(self, other):
        """
        For ForestAddresses, "<" will mean "is an ancestor of".

        IMPORTANT: For the very common operation of sorting ForestAddresses by
        lexicographic ordering on their string representations, this is _not_ the
        right operator! But it is still very easy to do: `addresses.sort(key=repr)`
        """
        return self.n < other.n and other.ancestors[:self.n] == self.ancestors


class VersionedLibpathNode:

    def __init__(self, libpath, version):
        """
        :param libpath: string
        :param version: CheckedVersion instance
        """
        self.libpath = libpath
        self.version = version
        self.parent = None
        self.children = {}
        self.full_tree_lookup = None
        self.address = None

    def __repr__(self):
        if self.libpath is None:
            return ''
        return f'{self.libpath}@{self.version.full}'

    def __hash__(self):
        return hash(repr(self))

    def write_as_origin(self):
        return f'{self.libpath}@{self.version.major}'

    def add_child(self, vln):
        """
        Add another VersionedLibpathNode as child.
        """
        self.children[repr(vln)] = vln
        vln.parent = self

    def read_child_addresses_from_other_node(self, other):
        L = other.get_full_tree_lookup()
        for rep, child in self.children.items():
            node = L.get(rep)
            if node:
                child.address = node.address

    def get_full_tree_lookup(self, force=False, parent_address=''):
        """
        Compute the full lookup from versioned libpath strings
        to VersionedLibpathNodes, for all nodes below this one,
        recursively.
        """
        if force or self.full_tree_lookup is None:
            if self.address is None:
                self.address = f'{parent_address}:{repr(self)}'
            L = {}
            for vlp, vln in self.children.items():
                L[vlp] = vln
                L.update(vln.get_full_tree_lookup(force=force, parent_address=self.address))
            self.full_tree_lookup = L
        return self.full_tree_lookup

    def get_all_versioned_libpath_strings(self):
        L = self.get_full_tree_lookup()
        return L.keys()

    def get_implied_version_mapping(self):
        """
        :return: dict mapping (unversioned) libpaths to CheckedVersion instances.
        """
        return {v.libpath:v.version for v in self.get_full_tree_lookup().values()}

    def get_implied_full_version_mapping(self):
        """
        :return: dict mapping (unversioned) libpaths to full version strings.
        """
        return {v.libpath:v.version.full for v in self.get_full_tree_lookup().values()}

    def make_stack_from_vlps(self, vlps):
        """
        Utility method used by search procedures.
        """
        L = self.get_full_tree_lookup()
        stack = []
        for vlp in vlps:
            vln = L.get(vlp)
            if vln:
                stack.append(vln)
        return stack

    def get_descendants_of_vlps(self, ancestor_vlps):
        """
        :param ancestor_vlps: iterable of versioned libpath strings
        :return: a lookup of all nodes at or below self, which are
            _also_ at or below _at least one_ of the given ancestors.
        """
        stack = self.make_stack_from_vlps(ancestor_vlps)
        visited = {}
        while stack:
            v = stack.pop()
            if repr(v) in visited: continue
            visited[repr(v)] = v
            stack.extend(v.children.values())
        return visited

    def get_ancestors_of_vlps(self, descendant_vlps):
        """
        :param descendant_vlps: iterable of versioned libpath strings
        :return: a lookup of all nodes at or below self, which are
            _also_ at or above _at least one_ of the given descendants.
        """
        stack = self.make_stack_from_vlps(descendant_vlps)
        visited = {}
        while stack:
            v = stack.pop()
            if repr(v) in visited: continue
            visited[repr(v)] = v
            if v.parent and v.parent.libpath:
                stack.append(v.parent)
        return visited

class ForestAddressList(list):
    """
    Many operations on lists of ForestAddresses require that they be sorted
    lexicographically. This is a list-like class that lets us carry around a
    record as to whether that sorting has been done yet or not.
    """

    def __init__(self, _collection):
        super(ForestAddressList, self).__init__(_collection)
        self._is_sorted = False

    def is_sorted(self):
        return self._is_sorted

    def lex_sort(self):
        """
        Sort the ForestAddresses lexicographically, according to their string
        representations.

        But only do the sorting if it has not already been done! Preventing such
        duplication of effort is this class's raison d'etre.
        """
        if not self._is_sorted:
            self.sort(key=lambda u: u.address)
            self._is_sorted = True

def get_ancestral_closure(deducpaths, topo_sort=False, ancestor_chains=None, exclude=None):
    """
    Given a dict mapping deducpaths (libpaths of deductions) to (major) versions, compute
    the "ancestral closure" thereof. This is the smallest set of deducpaths that contains
    the given set, and is closed under the operation of passing from a deducpath to the
    libpath of that deduction's parent, within the given (major) version.

    (To be clear, to say that deduction D is _parent_ of deduction E is the same as saying
    that E is an expansion on D, or that E's targets lie in D.)

    :param deducpaths: dict mapping the deduction libpaths whose closure is desired, to
      the (major) version at which each one should be taken.
    :param topo_sort: if True we return a list (not a set), sorted in topological order, i.e.
      so that if deduc C is an ancestor of deduc E then C's libpath comes before that of E.
    :param ancestor_chains: Optionally, you may provide a dictionary of pre-computed ancestor
      chains (with deducpaths as keys), to speed things up. It needn't be complete.
    :param exclude: Optional set of libpaths that should be excluded from the final closure.

    :return: The ancestral closure of the given iterable of deducpaths. If topo_sort was True,
      then it is a list, and the deducpaths are in topological order. Otherwise it is a set.
    """
    if ancestor_chains is None: ancestor_chains = {}
    gr = get_graph_reader()
    if topo_sort:
        addresses = set()
        for d, vers in deducpaths.items():
            chain = ancestor_chains.get(d, gr.get_ancestor_chain(d, vers))
            a = ''
            for p in chain:
                a += ":" + p
                if exclude is None or p not in exclude:
                    addresses.add(a)
        addresses = sorted(list(addresses))
        lps = [a[a.rindex(":") + 1:] for a in addresses]
        return lps
    else:
        closure = set(deducpaths)
        for d, vers in deducpaths.items():
            chain = ancestor_chains.get(d, gr.get_ancestor_chain(d, vers))
            closure.update(chain)
        if exclude is not None:
            closure -= exclude
        return closure

def find_oldest_elements(fal):
    """
    Given a ForestAddressList, return the subset consisting of those elements
    that are "oldest" in the sense that they have no ancestor in the given list.

    :param fal: the ForestAddressList in which to search
    :return: the set of all "oldest" elements of the given list
    """
    oldest = set()
    fal.lex_sort()
    cur = None
    for a in fal:
        if cur is None or not a.address.startswith(cur.address):
            oldest.add(a)
            cur = a
    return oldest

def find_descendants_of(ancestors, pool):
    """
    Suppose you have a pool of forest addresses, and you have a set of addresses
    to be regarded as  "ancestors". You want to find the set of all elements of
    the pool that are descendants of any of these potential ancestors.

    :param ancestors: a ForestAddressList giving the set of potential ancestors
    :param pool: a ForestAddressList giving the pool in which to search

    :return: the set of all descendants of the ancestors, in the pool
    """
    desc = set()
    pool.lex_sort()
    ancestors.lex_sort()
    pool_iter = iter(pool)
    anc_iter  = iter(ancestors)
    try:
        anc = next(anc_iter)
        candidate = next(pool_iter)
        while True:
            # Test lex ordering on addresses. That the potential ancestor's
            # address come before that of the potential descendant lexicographically
            # is a necessary but not sufficient condition for an actual ancestral
            # relationship.
            if candidate.address <= anc.address:
                candidate = next(pool_iter)
            # Test the actual ancestral relationship. See defn of __lt__ relation
            # on ForestAddress class.
            elif anc < candidate:
                desc.add(candidate)
                candidate = next(pool_iter)
            else:
                anc = next(anc_iter)
    except StopIteration:
        pass
    return desc

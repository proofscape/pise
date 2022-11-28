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
Utility classes to support the common operation where you have a dict D
mapping libpaths to something, and you want to apply that mapping to
any given libpath L, with the rule that a pair K:V in D applies to L if
K is either equal to L or is a proper, segmentwise prefix of L.

We also support the "reversible" case. The application is said to be reversible
if the pair K:V _also_ applies to L when K is a proper, segmentwise _extension_
of L.
"""

class SortableLibpath:
    """
    Supports sorting libpaths lexicographically, and thereby determining
    which ones fall under those that have been marked as "headings".
    """

    HEADING = 0
    SUBJECT = 1

    def __init__(self, kind, libpath, mapsto=True):
        self.kind = kind
        self.libpath = libpath
        self.mapsto = mapsto
        self.n = len(self.libpath)

    def __lt__(self, other):
        """
        We make it so that a sorted list of SortableLibpaths has the property
        that, if S is any subject in the list, and if H_0 is the longest heading
        in the list that applies to S, then:
          - H_0 comes before S.
          - If H' is a heading that comes between H_0 and S, then H' is a
            segment-wise extension of H_0; in particular, H' does not apply
            to S.
        """
        return self.libpath < other.libpath or (
                self.libpath == other.libpath and self.kind < other.kind
        )

    def __call__(self, subject):
        """
        Attempt to apply a heading to a subject.
        :param subject: the potential subject
        :return: a PrefixMatch if this heading is a prefix of the subject, else None
        """
        match = None
        prefix = subject.libpath[:self.n]
        if prefix == self.libpath:
            suffix = subject.libpath[self.n:]
            if suffix == '':
                match = PrefixMatch(PrefixMatch.IDENTICAL, self, subject, suffix)
            elif suffix[0] == '.':
                if subject.kind == SortableLibpath.HEADING and self.kind == SortableLibpath.SUBJECT:
                    match = PrefixMatch(PrefixMatch.REVERSE, subject, self, suffix)
                else:
                    match = PrefixMatch(PrefixMatch.PROPER, self, subject, suffix)
        return match

class PrefixMatch:
    """
    Represents a match of a subject under a heading, in terms of SortableLibpaths.
    """

    IDENTICAL = 0
    PROPER = 1
    REVERSE = 2

    def __init__(self, kind, heading, subject, suffix):
        """
        :param kind: is it an IDENTICAL match, a PROPER prefix, or a REVERSE match?
        :param heading: the SortableLibpath of HEADING type that matched as prefix
        :param subject: the SortableLibpath of SUBJECT type that had the prefix
        :param suffix: the suffix of the subject following the heading
        """
        self.kind = kind
        self.heading = heading
        self.subject = subject
        self.suffix = suffix

    def substitute(self):
        """
        Sometimes (but not always), the `mapsto` property of the heading is
        another libpath prefix that is meant to be substituted for the prefix
        that matched. In those cases, this method returns the result of that
        substitution.
        """
        m = self.heading.mapsto
        return None if m is None else m + self.suffix

    def value(self):
        return self.heading.mapsto

    def is_proper(self):
        return self.kind == PrefixMatch.PROPER

    def is_reverse(self):
        return self.kind == PrefixMatch.REVERSE


class LibpathPrefixMapping:
    """
    Given a mapping in the form of a dict with libpaths (strings) as keys, and
    anything as values, this class supports the application of that mapping to
    _any_ given libpath, via (optionally reversible) prefix matching.
    """

    def __init__(self, given_mapping, reversible=False):
        self.headings = [
            SortableLibpath(SortableLibpath.HEADING, k, v)
            for k, v in given_mapping.items()
        ]
        self.reversible = reversible

    def add_heading(self, libpath, value):
        self.headings.append(
            SortableLibpath(SortableLibpath.HEADING, libpath, value)
        )

    def clear(self):
        self.headings = []

    def __call__(self, libpaths):
        """
        :param libpaths: an iterable of libpaths
        :return: dict mapping just those libpaths that matched to their PrefixMatch
        """
        A = self.headings + [
            SortableLibpath(SortableLibpath.SUBJECT, lp)
            for lp in libpaths
        ]
        A.sort()
        matches = {}
        # We need a stack of headings.
        # Why? Consider the following example:
        #     H1: xy.foo.bar.Pf
        #     S1: xy.foo.bar.Pf.A10
        #     H2: xy.foo.bar.Pf.A20
        #     S2: xy.foo.bar.Pf.A20
        #     S3: xy.foo.bar.Pf.A30
        # We hit heading H1, and then it applies to subject S1. Fine.
        # Now we hit heading H2. What do we do? Throw away H1 entirely?
        # Suppose so. Then H2 applies to S2, which is great, but then we hit S3.
        # What happens? Well, H2 doesn't apply, so now we have no heading.
        # This is an error. H1 was meant to apply to S3.
        # This is why, instead of throwing H1 away, we just let H2 push it down
        # on the stack of headings. As soon as H2 fails to apply, we go back to
        # trying to apply H1.
        heading_stack = []
        heading = None
        last_chance = []
        for x in A:
            if x.kind == SortableLibpath.HEADING:
                if self.reversible and not heading_stack:
                    # Empty heading stack means this is the _first_ heading since
                    # the elements of the last_chance list were put in there. This is
                    # their chance to make a reverse match, if we're allowing that.
                    # See theory discussion below.
                    while last_chance:
                        subject = last_chance.pop()
                        y = subject(x)
                        if y:
                            matches[subject.libpath] = y
                heading_stack.append(heading)
                heading = x
            else:
                while heading is not None:
                    y = heading(x)
                    if y is None:
                        # As soon as we hit a libpath to which a heading does not
                        # apply, this heading will never apply again (due to sorting).
                        heading = heading_stack.pop()
                    else:
                        matches[x.libpath] = y
                        break
                else:
                    last_chance.append(x)
        return matches

r"""
# Theory of reversible prefix matching

We establish in Theorem 4 that, in a sorted list of SortableLibpaths, if p is any subject
in that list, then we have a heading that is a segmentwise extension of p iff the _first_ heading
coming after p is such a one.

**Defn:** Let p and q be libpaths. We say q is an _extension_ of p if len(q) >= len(p) and q[:len(p)] == p.
The extension is said to be _proper_ if len(q) > len(p).

**Defn:** If q is a proper extension of p, then q is said to be a _segmentwise_ or _true_ extension of
p if q[len(p)] == '.'. Otherwise it is called a _false_ extension of p.


**Lemma 1:** Let p, q, r be libpaths with q an extension of p and r not an extension of p.
If p < r, then q < r.

**Proof:** Let n = len(p). Since r > p but r is not an extension of p, there must be some 0 <= k < n such
that r[k] > p[k]. Let k0 be the least such k. So we have

    r[i] == p[i] for 0 <= i < k0

    r[k0] > p[k0].

Since q is an extension of p, we have q[:n] == p. In particular, k0 < n implies

    r[i] == q[i] for 0 <= i < k0

    r[k0] > q[k0],

which means r > q. [ ]


**Lemma 2:** Let p be a libpath, q a true extension of p, and q' a false extension of p. Then q < q'.

**Proof:** Let n = len(p). Since q and q' are both extensions of p, we have q[:n] == q'[:n].
Since they are both _proper_ extensions of p, both q[n] and q'[n] are defined.
Furthermore, since q' is a false extension, we have q'[n] = c for some letter c.
Finally, since q is segmentwise, we have q[n] == '.' < c == q'[n].
It follows that q < q'. [ ]


**Corollary 3:** Let L be any nonempty, sorted list of libpaths, with p = L[0].
Partition the remainder R = L[1:] into three disjoint sets:
    S = the segmentwise extensions of p among R
    F = the false extensions of p among R
    N = the non-extensions of p among R
Then S < F < N, elementwise.

**Proof:** Follows from Lemmas 1 and 2. [ ]

Let's clarify this a bit. Fixing any libpath p, consider any other libpath q != p whatsoever.
Either q is an extension of p, or it is not. If it is, then (being different from p and hence proper)
it is either segmentwise or false.
What Cor 3 is saying is simply that, among q > p, these three types are not mixed up, but neatly
stratified: the segmentwise extensions come first, then the false extensions, and finally the
non-extensions. (Meanwhile on the other side, where q < p, the story is even simpler: all such
q are non-extensions of p.)


**Theorem 4:** Let L be a set of SortableLibpaths. Let p be a subject in L. Let S be
the set of headings in L that are segmentwise extensions of p. Let A be the set of headings
in L that come after p. If S is nonempty, then A is nonempty, and the _first_ element of A
is in S.

**Proof:** S is a subset of A, because all extensions of p come after p. So if S is nonempty,
so is A. So A has a first element a0. According to Cor 3, stratify A into A_S < A_F < A_N.
We have A_S = A ^ S by definition. But S \subseteq A, so A ^ S = S. Then S nonempty says A_S
is nonempty. Then we must have a0 \in A_S. But then a0 \in S. [ ]
"""

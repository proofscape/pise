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
This module supports linear descriptions of content forests.

For example, the string

    "foo.bar(cat~s(g1t2*g2t0)p*cat2(foo2*bar2~c(0)))"

can be passed to the `parse` function to get the forest consisting of
just one tree,

    foo
        bar
            cat~s(g=1,t=2; g=2,t=0)p()
            cat2
                foo2
                bar2~c(ref:0)

If you call `expand` on this tree's root Node you will get the list

    foo.bar.cat~s(g=1,t=2; g=2,t=0)p()
    foo.bar.cat2.foo2
    foo.bar.cat2.bar2~c(ref:0)

of augmented libpaths represented by the tree's leaves.

Going in the other direction, you can pass this list of AugmentedLibpaths
to the `build_forest_for_content` function in order to get a forest, as
a list of root Nodes. In this case, there is just one root.

Finally, you can call the `linearlize` method of that root Node and it will
spit out exactly the string

    "foo.bar(cat~s(g1t2*g2t0)p*cat2(foo2*bar2~c(0)))"

with which we began.

The language is a simple way of linearizing trees, with decorations on their
leaves.

Every node must have a name, like this:
    foo
If a node has exactly one child, the child is separated by a dot, like this:
    foo.bar
If a node has two or more children, they are put in parentheses, and separated by stars:
    foo.bar(cat*baz*spam)
Nodes may have "decorations" set off by a tilde:
    foo.bar(cat~decorationGoesHere*baz~orHere*spam~orHere)
A decoration is a series of "codes" which consist of a single letter, optionally
followed by a parenthesized argument block. Examples:
    c(1)
    s(g1t2)
    a(g0t0*g1t1)
The argument block may be in any of the following forms:
    (I) an integer
    (II) a list of key-value pairs
    (III) a star-delimited list of chunks of forms (I) or (II)
In the key-value pairs in form (II) the keys are alphabetical, the values are
numerical, and there is no space in between.

The reason for using the characters `().*~` is that according to RFC 3986
<https://www.ietf.org/rfc/rfc3986.txt> these are "sub-delims" and may be used
_unescaped_ in the path part of a URI. This is desirable since this tree notation
is intended to be used in URLs, and we are trying to keep these as short and
compact -- and even human-readable -- as possible.
"""

import re

from lark import Lark, Transformer

import pfsc.constants
from pfsc.build.versions import VersionTag
from pfsc.build.lib.libpath import get_modpath
from pfsc.build.repo import parse_repo_versioned_libpath, make_repo_versioned_libpath
from pfsc.excep import PfscExcep, PECode
from pfsc.session import make_demo_user_path

forest_grammar = r'''
    forest : tree | children
    tree : segment ("." segment)* children?
    segment : CNAME ("@" version)? ("~" codes)?
    version : "W" "IP"? | "v"? INT "_" INT "_" INT
    children : "(" tree ("*" tree)+ ")"
    codes : code+
    code : CNAME ("(" CODE_ARGS ")")?
    CODE_ARGS : /[^)]/+
    %import common.CNAME
    %import common.INT
'''

class DecoratedSegment:

    def __init__(self, name, version, codes):
        self.name = name
        self.version = version
        self.codes = codes

class Version:

    def __init__(self, is_WIP=False, major=None, minor=None, patch=None):
        self.is_WIP = is_WIP
        self.major = major
        self.minor = minor
        self.patch = patch

    def __str__(self):
        if self.is_WIP:
            return "WIP"
        else:
            return f'v{self.major}_{self.minor}_{self.patch}'

    def write_compact(self):
        if self.is_WIP:
            return "W"
        else:
            return f'{self.major}_{self.minor}_{self.patch}'

STANDARD_CODES = ['a', 'c', 's', 'f', 'b']

class ForestBuilder(Transformer):

    def __init__(self, allowed_codes=None):
        super().__init__()
        self.allowed_codes = allowed_codes or STANDARD_CODES

    def forest(self, items):
        """
        :return: list of root Nodes
        """
        if isinstance(items[0], list):
            return items[0]
        else:
            return items

    def tree(self, items):
        if isinstance(items[-1], list):
            segments, children = items[:-1], items[-1]
        else:
            segments, children = items, []
        root = None
        prev = None
        for segment in segments:
            u = Node(segment.name, version=segment.version)
            for code in segment.codes:
                u.add_code(code)
            if root is None: root = u
            if prev is not None: prev.add_child(u)
            prev = u
        for child in children:
            prev.add_child(child)
        return root

    def segment(self, items):
        name = items[0]
        version = None
        codes = []
        n = len(items)
        if n == 2:
            if isinstance(items[1], Version):
                version = items[1]
            else:
                codes = items[1]
        elif n == 3:
            version, codes = items[1:]
        return DecoratedSegment(name, version, codes)

    def version(self, items):
        if len(items) == 0:
            return Version(is_WIP=True)
        else:
            assert len(items) == 3
            M, m, p = map(int, items)
            return Version(major=M, minor=m, patch=p)

    def children(self, items):
        return items

    def codes(self, items):
        return items

    def code(self, items):
        type_ = items[0]
        if type_ not in self.allowed_codes:
            msg = f'Content forest uses disallowed code `{type_}`.'
            raise PfscExcep(msg, PECode.MALFORMED_CONTENT_FOREST_DESCRIP)
        if len(items) == 2:
            arg_block = items[1]
        else:
            arg_block = ''
        return TreeCode(type_, arg_block)

forest_parser = Lark(forest_grammar, start='forest')

class TypeRequest:
    """
    Any request for a thing that has a type, e.g. CHART or NOTES or SOURCE,
    and is supposed to go in a place (specified by group number g, tab number t).
    """

    def __init__(self, g, t, type_):
        self.group_num = g
        self.tab_num = t
        self.type_descrip = {
            'type': type_
        }

class LibpathRequest(TypeRequest):
    """
    Many type requests are for things that are specified by a repo-versioned libpath.
    This is for those kinds of requests.
    """

    def __init__(self, g, t, type_, rvlp):
        TypeRequest.__init__(self, g, t, type_)
        libpath, version = parse_repo_versioned_libpath(rvlp)
        self.type_descrip['libpath'] = libpath
        self.type_descrip['version'] = version
        # For the sake of unit tests and demo repos, we tolerate libpaths for
        # which modpath will be reported as not existing.
        try:
            modpath = get_modpath(libpath)
        except PfscExcep as pe:
            # Re-raise anything other than the module failing to exist.
            if pe.code() != PECode.MODULE_DOES_NOT_EXIST:
                raise pe
        else:
            self.type_descrip['modpath'] = modpath

class SourceRequest(LibpathRequest):

    def __init__(self, rvlp, loc):
        self.loc = loc
        g = loc.get('group')
        t = loc.get('tab')
        L = loc.get('line')
        if g is None or t is None:
            raise ValueError
        LibpathRequest.__init__(self, g, t, "SOURCE", rvlp)
        if L is not None:
            self.type_descrip['sourceRow'] = L

class AnnoRequest(LibpathRequest):

    def __init__(self, rvlp, loc):
        self.loc = loc
        g = loc.get('group')
        t = loc.get('tab')
        if g is None or t is None:
            raise ValueError
        LibpathRequest.__init__(self, g, t, "NOTES", rvlp)

class ChartRequest(TypeRequest):

    layout_method_lookup = {
        0: 'KLayDown',
        1: 'OrderedList1',
        2: 'KLayUp',
    }

    overview_pos_lookup = {
        0: 'bl', 1: 'br', 2: 'tr', 3: 'tl'
    }

    @classmethod
    def get_layout_method_code(cls, method_name):
        for k, v in cls.layout_method_lookup.items():
            if v == method_name:
                return k
        return None

    def __init__(self, rvlp, loc):
        # For a ChartRequest, the group and tab numbers may well be
        # undefined; namely, this is the case if our location is given
        # by a back-reference.
        # In such a case, we are happy to record `None` for group and
        # tab for now. They will be filled in later.
        g = loc.get('group')
        t = loc.get('tab')
        TypeRequest.__init__(self, g, t, "CHART")

        libpath, version = parse_repo_versioned_libpath(rvlp)
        # We start by recording just the one libpath and version in the type description.
        # If you are planning to add "copaths" later, you just need to call the
        # `finalize_libpaths` method when you are done, in order to override this.
        self.type_descrip['on_board'] = [libpath]
        self.type_descrip['versions'] = {libpath: version}

        self.libpath = libpath
        self.version = version
        self.loc = loc
        self.back_ref = None

        # Repo-versioned libpaths of other deducs that are to be opened in the same pane
        # as this one may be added later. They'll be recorded here:
        self.copaths = []

        # Set up back-ref or other args.
        if g is None or t is None:
            n = loc.get_back_ref()
            if n is None:
                raise ValueError
            self.back_ref = n
        else:
            x = loc.get('x-coord')
            y = loc.get('y-coord')
            z = loc.get('zoom')
            # If _any_ of these is defined...
            if {x, y, z} != {None}:
                # ...then they _all_ need values (default if not as given)
                x = 0 if x is None else x
                y = 0 if y is None else y
                z = 1 if z is None else z
                self.type_descrip['coords'] = [x, y, z]

            o = loc.get('ordSel')
            if o is not None:
                self.type_descrip['ordSel'] = o

            G = loc.get('gid', 0)
            self.type_descrip['gid'] = str(G)

            L = loc.get('layout_method')
            if L is not None:
                L = self.coerce_key(L, ChartRequest.layout_method_lookup)
                self.type_descrip['layout'] = ChartRequest.layout_method_lookup[L]

            # Forest settings:
            # The typedescrip is allowed to have a `forest` subnamespace, in which
            # we may make any settings that pertain not to the desired content but
            # to the configuration of the forest itself, in which the content is to
            # be loaded.
            # At present we only have one such optional setting: the overview panel.
            # So we make a `forest` property iff this setting is defined.
            v = loc.get('overview_panel')
            if v is not None:
                v = self.coerce_key(v, ChartRequest.overview_pos_lookup)
                self.type_descrip['forest'] = {
                    'overview': {
                        'position': ChartRequest.overview_pos_lookup[v]
                    }
                }

    @staticmethod
    def coerce_key(key, lookup, default=0):
        """
        Check whether a key is among the keys of a lookup. If so, return
        it unchanged; if not, return a default value instead.
        :param key: the key to be coerced
        :param lookup: the lookup
        :param default: the default value in case the given key value is not present
        :return: coerced key value
        """
        return default if key not in lookup.keys() else key

    def get_back_ref(self):
        return self.back_ref

    def get_location(self):
        return self.loc

    def add_copath(self, copath):
        self.copaths.append(copath)

    def extend_gid(self, salt):
        if 'gid' in self.type_descrip:
            self.type_descrip['gid'] += salt

    def finalize_libpaths(self):
        """
        If any copaths have been added, this method should be called
        when that process is all done, in order to update the type description.
        """
        if self.copaths:
            versions = {k:v for k, v in [parse_repo_versioned_libpath(rvlp) for rvlp in self.copaths]}
            self.type_descrip['versions'].update(versions)
            self.type_descrip['on_board'].extend(list(versions.keys()))

class AugmentedLibpath:

    def __init__(self, libpath, codes):
        """
        :param libpath: str
        :param codes: list of TreeCode instances
        """
        # Ensure that we have a version, using default for repo if necessary.
        libpath, version = parse_repo_versioned_libpath(libpath, provide_default=True)
        libpath = make_repo_versioned_libpath(libpath, version)

        self.libpath = libpath
        self.codes = codes

        self.fstree_code = None
        self.buildtree_code = None

        self.source_code = None
        self.content_code = None
        self.source_reqs = []
        self.content_reqs = []
        # Populate
        self.find_codes()
        self.extract_requests()

    def find_codes(self):
        # There should be _at most one_ code of each of the "build," "fs," "source," and
        # "content" types. Therefore the following method of extraction is correct.
        for code in self.codes:
            if code.type == 'f':
                self.fstree_code = code
            elif code.type == 'b':
                self.buildtree_code = code
            elif code.type == 's':
                self.source_code = code
            elif code.type in 'ac':
                self.content_code = code

    def raise_malformed_code_excep(self, code):
        msg = f'Malformed code "{code.linearize()}" for libpath "{self.libpath}".'
        raise PfscExcep(msg, PECode.MALFORMED_AUGLP_CODE)

    def extract_requests(self):
        jobs = []
        if self.source_code is not None:
            jobs.append((self.source_code, SourceRequest, self.source_reqs))
        if self.content_code is not None:
            ReqType = {
                'a': AnnoRequest,
                'c': ChartRequest,
            }[self.content_code.type]
            jobs.append((self.content_code, ReqType, self.content_reqs))

        for code, ReqType, storage in jobs:
            locs = code.locations
            for loc in locs:
                try:
                    req = ReqType(self.libpath, loc)
                except ValueError:
                    self.raise_malformed_code_excep(code)
                else:
                    storage.append(req)

    def __str__(self):
        s = self.libpath
        if self.codes:
            s += "~" + ''.join(str(c) for c in self.codes)
        return s

    def makes_fstree_request(self):
        return self.fstree_code is not None

    def makes_buildtree_request(self):
        return self.buildtree_code is not None

    def get_source_requests(self):
        return self.source_reqs

    def get_content_requests(self):
        return self.content_reqs

    def build_codes(self):
        """
        Sometimes we use instances of this class in reverse: we add source
        and content requests (and even a path code) to them manually, and
        then we want them to assemble all this into a `self.codes` list.
        """
        self.codes = []

        if self.content_reqs:
            req0 = self.content_reqs[0]
            if isinstance(req0, AnnoRequest):
                type_ = 'a'
            elif isinstance(req0, ChartRequest):
                type_ = 'c'
            else:
                raise ValueError
            self.content_code = TreeCode(type_, '')
            self.content_code.locations = [req.loc for req in self.content_reqs]
            self.codes.append(self.content_code)

        if self.source_reqs:
            self.source_code = TreeCode('s', '')
            self.source_code.locations = [req.loc for req in self.source_reqs]
            self.codes.append(self.source_code)

        if self.fstree_code:
            self.codes.append(self.fstree_code)

        if self.buildtree_code:
            self.codes.append(self.buildtree_code)


class Node:
    """
    Represents a node in a content tree.
    """

    def __init__(self, name, version=None):
        """
        Every node must have a name, which is the libseg that it repreents.
        It _may_ have version, codes and/or children.
        """
        self.name = name
        self.version = version
        self.codes = []
        self.children = []

    def add_child(self, child):
        self.children.append(child)

    def add_code(self, code):
        self.codes.append(code)

    def write_versioned_segment(self, compact=False):
        s = self.name
        if self.version is not None:
            s += f'@{self.version.write_compact()}' if compact else f'@{self.version}'
        return s

    def write(self, indent=4):
        """
        Write a text description of the tree rooted at this node.
        :param indent: desired indent in number of spaces
        :return: string description
        """
        r = self.write_versioned_segment()
        if self.codes:
            r += "~" + ''.join(str(c) for c in self.codes)
        r += '\n'
        for ch in self.children:
            r += (' ' * indent) + ch.write(indent=indent+4)
        return r

    def expand(self, rootpath=''):
        """
        Expand the tree rooted at this node, into the full list of
        augmented libpaths that it represents, in depth-first order
        of traversal.

        To be precise, there is one augmented libpath for each node
        which either (a) has codes, or (b) is a leaf.

        :param rootpath: the libpath up to this node. When calling on
          a root node, you should simply leave this empty.
        :return: list of AugmentedLibpaths
        """
        vseg = self.write_versioned_segment()
        selfpath = vseg if rootpath == '' else f'{rootpath}.{vseg}'
        if selfpath == 'demo._':
            selfpath = make_demo_user_path() or selfpath
        alps = []
        # If this node has codes or is a leaf, we want to represent it.
        if self.codes or not self.children:
            alps.append(AugmentedLibpath(selfpath, self.codes))
        # Recurse.
        if self.children:
            alps += sum([ch.expand(rootpath=selfpath) for ch in self.children], [])
        return alps

    def linearize(self):
        """
        Write a linear description of the tree rooted at this node.
        :return: str
        """
        d = self.write_versioned_segment(compact=True)
        if self.codes:
            d += "~" + ''.join(c.linearize() for c in self.codes)
        n = len(self.children)
        if n == 1:
            ch = self.children[0]
            d += f'.{ch.linearize()}'
        elif n > 1:
            d += f'({"*".join(ch.linearize() for ch in self.children)})'
        return d

CODE_ARG = re.compile(r'([A-Za-z]+)(-?[0-9.]+)')

CODE_LOOKUP = {
    # annotation
    'a': {
        'g': 'group',
        't': 'tab',
    },
    # chart
    'c': {
        # gid means forest group id
        "G": 'gid',
        # group means tab group
        'g': 'group',
        "L": 'layout_method',
        'o': 'ordSel',
        't': 'tab',
        'v': 'overview_panel',
        'x': 'x-coord',
        'y': 'y-coord',
        'z': 'zoom'
    },
    # source
    's': {
        'g': 'group',
        "L": 'line',
        't': 'tab',
    },
}

CODE_REV_LOOKUP = {
    # annotation
    'a': {
        'group': 'g',
        'tab': 't',
    },
    # chart
    'c': {
        'gid': "G",
        'group': 'g',
        'layout_method': "L",
        'ordSel': 'o',
        'tab': 't',
        'overview_panel': 'v',
        'x-coord': 'x',
        'y-coord': 'y',
        'zoom': 'z',
    },
    # source
    's': {
        'group': 'g',
        'line': "L",
        'tab': 't',
    },
}

class Location:
    """
    Abstract class representing a location, as given within a TreeCode.
    """

    def get(self, param, default=None):
        """
        Look up the value of a parameter, by name (e.g. `group`, `tab`, etc.)
        :param param: (str) the name of the parameter
        :param default: default value to return if parameter is undefined
        :return: the numerical (int or float) value of the parameter, or the default
        """
        return default

    def get_back_ref(self):
        """
        :return: int if this location is a back-ref; else None
        """
        return None

class LocDesc(Location):
    """
    Location description.

    A location is described by a set of key-value pairs.
    """

    def __init__(self, type_, args):
        self.type = type_
        self.args = args
        # Sometimes it is useful to have a place to record an index:
        self.index = None

    def __str__(self):
        return ','.join(f'{k}={v}' for k, v in self.args.items())

    def linearize(self):
        return ''.join(f'{k}{v}' for k, v in self.args.items())

    def get(self, param, default=None):
        L = CODE_REV_LOOKUP[self.type]
        param_code = L.get(param)
        s = self.args.get(param_code)
        if s is None:
            return default
        try:
            v = int(s)
        except ValueError:
            try:
                v = float(s)
            except ValueError:
                v = s
        return v

class LocRef(Location):
    """
    Location reference.

    This is a zero-based index referring to a previously given location description.
    """

    def __init__(self, n):
        self.n = n

    def __str__(self):
        return f"ref:{self.n}"

    def linearize(self):
        return str(self.n)

    def get_back_ref(self):
        return self.n

class TreeCode:

    def __init__(self, type_, arg_block):
        self.type = type_
        # The argument block consists of chunks delimited by "*" chars.
        arg_chunks = arg_block.split("*") if arg_block else []
        locs = []
        for ch in arg_chunks:
            try:
                # First we check if the chunk is a simple integer.
                n = int(ch)
            except ValueError:
                # If that fails, the chunk must be a sequence of key-value pairs.
                # We will record it as an instance of `LocDesc`
                pairs = CODE_ARG.findall(ch)
                args = {k: v for k, v in pairs}
                locs.append(LocDesc(self.type, args))
            else:
                # When the chunk _was_ an integer, we record it as an
                # instance of `LocRef`.
                locs.append(LocRef(n))
        self.locations = locs

    def __str__(self):
        args = '; '.join([str(loc) for loc in self.locations])
        return f'{self.type}({args})'

    def linearize(self):
        """
        Write a linear description of this code.
        :return: str
        """
        d = self.type
        if self.locations:
            d += f'({"*".join(loc.linearize() for loc in self.locations)})'
        return d

def parse(text, allowed_codes=None):
    """
    Parse a linear, textual description of a forest of content trees.
    :param text: (str) the description.
    :param allowed_codes: list of allowed decoration codes
    :return: list of Nodes, being the roots of the trees in the forest.
    """
    ast = forest_parser.parse(text)
    allowed_codes = allowed_codes or STANDARD_CODES
    builder = ForestBuilder(allowed_codes)
    forest = builder.transform(ast)
    return forest

def build_node_on_segment(segment):
    parts = segment.split("@")
    if len(parts) == 1:
        name, version = parts[0], None
    else:
        assert len(parts) == 2
        name, raw_vers = parts
        if raw_vers == pfsc.constants.WIP_TAG:
            version = Version(is_WIP=True)
        else:
            vt = VersionTag(raw_vers.replace("_", '.'))
            version = Version(major=vt.major, minor=vt.minor, patch=vt.patch)
    return Node(name, version=version)

def build_forest_for_content(auglps):
    """
    Given a list of AugmentedLibpaths, build a forest to represent it,
    in the form of a list of Nodes.

    :param auglps: list of AugmentedLibpaths
    :return: list of Nodes
    """
    forest = []
    lp2node = {}
    for alp in auglps:
        segments = alp.libpath.split('.')
        lp = ''
        prev = None
        for segment in segments:
            if prev: lp += '.'
            lp += segment
            u = lp2node.get(lp)
            if u is None:
                u = build_node_on_segment(segment)
                lp2node[lp] = u
                if prev is None:
                    forest.append(u)
                else:
                    prev.add_child(u)
            prev = u
        # The code list (possibly empty) goes to the final node.
        prev.codes = alp.codes
    return forest

def write_forest(forest):
    """
    Write the linearized string representation of a forest.
    :param forest: list of one or more root Nodes
    :return: str
    """
    n = len(forest)
    if n == 0:
        return ''
    elif n == 1:
        root = forest[0]
        return root.linearize()
    else:
        f = "*".join([r.linearize() for r in forest])
        return f'({f})'

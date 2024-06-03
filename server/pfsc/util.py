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

import os
import re
import urllib.parse
import random
import datetime
from collections import defaultdict
import subprocess

from mistletoe import HTMLRenderer

from pfsc import check_config
from pfsc.excep import PfscExcep, PECode

numbered_name_re = re.compile(r'^(.*?)((\d+)([-._](\d+))*)$')

class NumberedName:
    """
    A class to make names comparable based on numbers occurring within them.
    E.g. this is so `Thm90` comes before `Thm100`.
    Or, e.g., `Prop_2.5.7` comes before `Prop_2.5.10`.
    """

    def __init__(self, name):
        self.name = name
        m = numbered_name_re.match(name)
        if m:
            self.prefix = m.group(1)
            suffix = m.group(2)
            # The suffix will be the longest final segment that matches the regex `(\d+)([-._](\d+))*`
            # In other words, groups of one or more digits, delimited by any of the chars "-._".
            # The prefix will be whatever comes before that.
            # Now split the suffix, and convert the digits to integers.
            self.nums = list(map(int, suffix.replace('-', '.').replace("_", '.').split('.')))
        else:
            self.prefix = self.name
            self.nums = []

    def __lt__(self, other):
        if self.prefix != other.prefix:
            # If the prefixes are not the same, then compare the names as strings.
            return self.name < other.name
        else:
            # If the prefixes _are_ the same, then it is a lexicographic comparison on
            # the number sequences. But corresponding numbers are compared _as numbers_,
            # not as strings!
            A, B = self.nums, other.nums
            # Begin by comparing corresponding numbers, as long as neither sequence has ended.
            for a, b in zip(A, B):
                if a < b:
                    return True
                elif b < a:
                    return False
            # If all corresonding numbers were equal, then it comes down to the question of
            # whether one sequence was shorter.
            L, M = len(A), len(B)
            return L < M

def topological_sort(graph, reversed=False, secondary_key=None):
    """
    :param graph: a directed graph (see format below)
    :param secondary_key: if defined, should be a key function with which to perform
                          additional sorting, secondary to the topological ordering condition
    :return: a list of the nodes in the graph, in a topological ordering,
             i.e. such that whenever a --> b you are assured that:
                a comes before b in the list if 'reversed' is False
             OR
                b comes before a in the list if 'reversed' is True
    Raises an exception if the graph has any directed cycles.

    Graph format:
    Dictionary in which node name points to list of _outneighbours_ of that node.
    ALL nodes in the graph MUST be present as keys, even if they have no outneighbours.
    E.g.
    { 1: [2, 4],
      2: [3, 4],
      3: [4],
      4: []
    }
    for the graph with directed edges (1, 2), (1, 4), (2, 3), (2, 4), (3, 4).
    """
    # We are going to need the in-degree of each node.
    indeg = defaultdict(int)
    for W in graph.values():
        for w in W:
            indeg[w] += 1
    # We need a stack.
    stack = []
    # Determine the initial order in which we will scan through the keys of the graph.
    initial_order = list(graph.keys())
    # Is there a secondary key?
    if secondary_key is not None:
        # If there is a secondary key then we apply it to the initial order.
        # Whether this needs to be reversed is opposite to whether the overall
        # toposort is to be reversed. This is because our use of a stack in the
        # procedure below is already going to introduce one reversal.
        initial_order.sort(key=secondary_key, reverse=not reversed)
        # We also need to sort each entry in the graph in the same way.
        for L in graph.values():
            L.sort(key=secondary_key, reverse=not reversed)
    # Initialise the "in-count" of each node to equal its in-degree,
    # and push the nodes with zero in-degree onto the stack.
    incount = {}
    for u in initial_order:
        incount[u] = indeg[u]
        if indeg[u] == 0:
            stack.append(u)
    # Prepare the list in which a comes before b whenever a --> b.
    top_order = []
    # While there is anything on the stack, pop the top element, add it to
    # the list, and decrement the in-count of all its forward neighbours,
    # pushing these neighbours onto the stack if their in-count has dropped to 0.
    while stack:
        u = stack.pop()
        top_order.append(u)
        for w in graph[u]:
            incount[w] -= 1
            if incount[w] == 0:
                stack.append(w)
    # Check for cycles.
    if len(top_order) < len(graph.keys()):
        msg = 'Graph has cycle. Cannot compute topological order.'
        raise PfscExcep(msg, PECode.DAG_HAS_CYCLE)
    # Reverse?
    if reversed:
        top_order.reverse()
    return top_order

def connected_components(graph):
    """
    @param graph: dict in which node points to _set_ of node's nbrs
    @return: generator of generators of components. Thus, if C is the return
             value, then [list(c) for c in C] will get you a list of components,
             each one spelled out as a list of nodes.
    """
    def next_chunk(u):
        U = set([u])
        while U:
            u = U.pop()
            visited.add(u)
            U |= graph[u] - visited
            yield u
    visited = set()
    for u in graph:
        if u not in visited:
            yield next_chunk(u)


def jsonSafe(text):
    """
    Encodes text so as to be decoded by JavaScript's
    decodeURIComponent function.

    Note that single quote characters ' are NOT encoded.
    But double quote " are encoded, so for JSON purposes just
    be sure to use double quotes around this string.
    """
    return urllib.parse.quote(text, safe='~()*!.\'')


def escape_url(raw):
    return HTMLRenderer.escape_url(raw)

class DoublyLinkedListNode:
    def __init__(self, data, prev=None, next=None):
        self.data = data
        self.prev = prev
        self.next = next

    def extract(self):
        if self.prev is not None:
            self.prev.next = self.next
        if self.next is not None:
            self.next.prev = self.prev

    def set_next(self, next):
        if next is not None:
            next.next = self.next
            next.prev = self
        if self.next is not None:
            self.next.prev = next
        self.next = next

def short_unpronouncable_hash(length=6, start_with_letter=False):
    """
    Produce a random string of digits and (selected) consonants.

    We use a stock of 30 possible characters (10 digits and 20 (upper and lowercase)
    consonants). So the number of possible strings of some reasonable lengths are:

        5:     24,300,000
        6:    729,000,000
        7: 21,870,000,000

    :param length: the desired length of the string
    :param start_with_letter: True to require the string begin with a letter
    :return: the string
    """
    h = ''
    letters = 'MmNnXxTtDdPpZzQqBbGg'
    digits = '1234567890'
    if start_with_letter:
        length -= 1
        h = random.choice(letters)
    # Want digits to be as common as letters so include digit list twice:
    h += ''.join(random.choices(digits+digits+letters, k=length))
    return h

def casual_time_delta(delta):
    """
    Express a time difference in casual English language.

    :param delta: a timedelta instance
    :return: string expressing the time difference
    """
    s = delta.total_seconds()
    h = s // 3600
    s %= 3600
    if h == 0:
        m = s // 60
        return 'about %d minute%s' % (m, '' if m == 1 else 's')
    return '%s%d hour%s' % (
        '' if s == 0 else 'about ',
        h,
        '' if h == 1 else 's'
    )

def recycle(fs_path):
    """
    Move a file or directory to the recycling bin.

    :param fs_path: filesystem path (string or pathlib.Path) pointing
      to the file or directory that is to be recycled.
    :return: the name to which the file or directory was moved, within
      the recycling bin. This is essentially the given path, plus a
      timestamp, plus a random number.
    """
    recyc_bin_dir = check_config("RECYCLING_BIN")
    os.makedirs(recyc_bin_dir, exist_ok=True)
    now = datetime.datetime.utcnow()
    dst_name = "_".join([
        str(fs_path).replace(os.sep, "_"),
        str(now).replace(' ', "_"),
        str(random.random())
    ])
    dst_path = os.path.join(recyc_bin_dir, dst_name)
    cmd = f'mv {fs_path} {dst_path}'
    os.system(cmd)
    return dst_name

def count_pfsc_modules(fs_path):
    """
    Count the .pfsc modules under a given directory.

    :param fs_path: filesystem path (string) to a directory
    :return: number (int) of .pfsc modules living in or under the
      named directory, at any depth.
    """
    if not os.path.exists(fs_path):
        return 0
    p = subprocess.run(
        f"find {fs_path} -name '*.pfsc' | wc -l",
        shell=True, stdout=subprocess.PIPE, text=True
    )
    return int(p.stdout)

def run_cmd_in_dir(cmd, dir_path, silence=False):
    full_cmd = f'cd {dir_path}; {cmd}'
    if silence:
        full_cmd += ' > /dev/null 2>&1'
    os.system(full_cmd)


def unindent(text, space=' ', newline='\n', tabwidth=4, cut_inner_blank_lines=True):
    """
    Normalize whitespace and unindent so first non-blank line has zero indent.

    Definitions:
        * A blank line is one consisting only of whitespace, i.e. \n, \r, \t or ' ' chars.
        * "Normalize" means:
          - Strip any and all outer blank lines. Outer means initial or final.
          - Remove any and all \r chars.
          - Optionally, expand tabs to spaces.

    @param text: The text (string) to be processed.
    @param space: String to use for creating each "space" at the beginning of those lines
        that are indented beyond the "basic" indentation (i.e. the indentation that is removed
        from all lines). Default: ' '. Useful e.g. if set to '&nbsp;' when generating HTML.
    @param newline: String to use for creating line breaks in the final text.
        Default: '\n'. Useful e.g. if set to '<br>\n' when generating HTML.
    @param tabwidth: If a positive integer (default 4), all tab chars will be expanded
        to this many spaces.
    @param cut_inner_blank_lines: If True (the default), then eliminate any *inner* blank
        lines too, i.e. blank lines that would still remain after all outer ones had been stripped.

    @return: The processed string.
    """
    # Expand tabs
    if isinstance(tabwidth, int) and tabwidth > 0:
        text = text.replace('\t', ' ' * tabwidth)
    # Remove carriage returns
    text = text.replace('\r', '')
    # Strip outer empty lines.
    text = text.strip('\n')

    if not text:
        return ''

    lines = text.split('\n')

    # Strip outer blank lines
    num_trailing_blank_lines = 0
    for line in lines[::-1]:
        if not line.strip():
            num_trailing_blank_lines += 1
        else:
            break
    if num_trailing_blank_lines > 0:
        lines = lines[0:-num_trailing_blank_lines]

    num_leading_blank_lines = 0
    for line in lines:
        if not line.strip():
            num_leading_blank_lines += 1
        else:
            break
    else:
        return ''

    core = lines[num_leading_blank_lines:]

    # Determine basic indentation.
    top = core[0]
    basic = 0
    while top[basic] == ' ':
        basic += 1

    # Initialize the unindented text:
    u = ''

    first = True
    for line in core:
        st = line.strip()
        if cut_inner_blank_lines and (not st):
            continue
        if first:
            first = False
        else:
            u += newline
        sp = 0
        if st:
            while line[sp] == ' ':
                sp += 1
        else:
            sp = len(line)
        if sp > basic:
            u += space * (sp - basic)
        u += st

    return u


def dict_to_url_args(d):
    return "&".join([f'{k}={v}' for k, v in d.items()])


def conditionally_unlink_files(dir_path, condition, recursive=False, rmdirs=False):
    """
    Unlink any and all files satisfying a given condition, in (and optionally under)
    a given directory.

    :param dir_path: pathlib.Path specifying the directory under which to search.
    :param condition: a unary callable, accepting a pathlib.Path pointing to a file,
        and returning boolean True iff that file should be unlinked.
    :param recursive: set True if you want to recurse on all nested directories.
    :param rmdirs: set True if you also want to remove directories that are or
        become empty.

    :return: the total number of files and directories unlinked
    """
    if not dir_path.exists():
        return 0

    count_total = 0
    count_this_dir = 0
    # Don't want to use an iterator while unlinking files under it, so convert
    # to a list. This also lets us get the total number of subpaths.
    subpaths = list(dir_path.iterdir())
    N = len(subpaths)
    for path in subpaths:
        if recursive and path.is_dir():
            count_total += conditionally_unlink_files(path, condition, recursive=True, rmdirs=rmdirs)
            # If we're trying to remove directories, and if the subdir has ceased to exist,
            # then count it as one deletion from this dir.
            if rmdirs and not path.exists():
                count_this_dir += 1
        if path.is_file() and condition(path):
            path.unlink()
            count_this_dir += 1
            count_total += 1
    if rmdirs and count_this_dir == N:
        dir_path.rmdir()
        count_total += 1
    return count_total

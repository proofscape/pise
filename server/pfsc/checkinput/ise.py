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

import re

from pfsc.excep import PfscExcep, PECode

class IseSideInfo:
    """
    Represents settings for the sidebar in the ISE.

        width: (int) the width in pixels that the sidebar should occupy
        collapsed: (bool) true iff the sidebar should be in its collapsed or closed state
    """

    def __init__(self, width, collapsed):
        self.width = width
        self.collapsed = collapsed

def check_ise_side(key, raw, typedef):
    """
    :param raw: a code string. Format: integer, optionally prefixed
        with a `c`. The number means the width in pixels that the
        sidebar should occupy; the `c` means it should be collapsed.

        Alternatively, you may simply provide a `c`, and then the width will
        be set at a default value of 200.

        Examples:
            250: visible, 250 pixels wide
	        c90: collapsed, 90 pixels wide
    :param typedef: nothing special
    :return: a IseSideInfo
    """
    collapsed = raw[:1] == 'c'
    width_str = raw[1:] if collapsed else raw
    if collapsed and width_str == '':
        width_str = 200
    try:
        width = int(width_str)
    except ValueError:
        msg = f'ISE sidebar code {raw} is malformed'
        raise PfscExcep(msg, PECode.MALFORMED_ISE_SIDEBAR_CODE, bad_field=key)
    if width < 1 or width > 2000:
        msg = f'ISE sidebar width must be between 1 and 2000, inclusive'
        raise PfscExcep(msg, PECode.MALFORMED_ISE_SIDEBAR_CODE, bad_field=key)
    return IseSideInfo(width, collapsed)

class IseSplitInfo:
    """
    Represents a way of setting up the tab container splits in the ISE.

        structure: list of "V", "H", "L" chars indicating vertical, horizontal,
            and leaf nodes in the split structure.
        size_fracs: list of fractions (floats between 0 and 1), one for
            each "V" or "H", giving the desired fraction of space occupied
            by the left/top half of the split.
    """

    def __init__(self, structure, size_fracs):
        self.structure = structure
        self.size_fracs = size_fracs

SPLIT_CODE_PATTERN = re.compile(r'[VHL]|\d+')

def check_ise_split(key, raw, typedef):
    """
    :param raw: a split code. This should be a sequence of "V", "H", and "L"
        characters,(giving the desired vertical and horizontal splits, and leaf
        nodes, in Polish notation) plus integers between 1 and 99.

        There may be one integer after each "V" or "H", indicating what percentage
        of space is to be occupied by the left/top half of the split.

        Integers may be omitted, in which case we assume that 50 was intended.

        To have a well-formed split tree, the number of leaf nodes must be exactly
        one greater than the number of splits; however, you may omit trailing "L"s,
        and they will be supplied automatically to reach the necessary count.

        Examples:

            V30LH50LL   Start with a vertical split, in which the left side gets 30%
                        of the space. Then split the right-hand side horizontally 50/50.

            V30LH       Same. 50/50 is implied for the H; trailing L's are omitted.

            V30H        Same except the left side is split horizontally instead of the right.

    :param typedef: nothing special
    :return: a IseSplitInfo
    """

    def raiseExcep(extra_msg=None):
        msg = f'ISE split code {raw} is malformed.'
        if extra_msg is not None:
            msg += ' ' + extra_msg
        raise PfscExcep(msg, PECode.MALFORMED_ISE_SPLIT_CODE, bad_field=key)

    words = SPLIT_CODE_PATTERN.findall(raw)
    if ''.join(words) != raw:
        raiseExcep()

    structure = []
    size_fracs = []
    num_splits = 0
    num_leaves = 0
    last_was_split = False

    for word in words:
        if word in "VHL" and last_was_split:
            # No size for last split so assume 50%
            size_fracs.append(0.5)
        if word in "VH":
            structure.append(word)
            num_splits += 1
            last_was_split = True
        elif word == "L":
            structure.append(word)
            num_leaves += 1
            last_was_split = False
        else:
            try:
                p = int(word)
            except ValueError:
                raiseExcep()
            if p < 1 or p > 99:
                extra = 'ISE split code percentages must be between 1 and 99 inclusive.'
                raiseExcep(extra)
            f = p/100
            size_fracs.append(f)
            last_was_split = False
    if last_was_split:
        # No size for last split so assume 50%
        size_fracs.append(0.5)

    # There must be one size per split.
    if len(size_fracs) != num_splits:
        raiseExcep()
    # The number of leaves must be exactly one more than the number of splits.
    # Let d be the deficit.
    d = (num_splits + 1) - num_leaves
    if d < 0:
        # Too many leaves is an error.
        raiseExcep()
    elif d > 0:
        # If not enough leaves were supplied, we assume they are meant to be
        # filled in at the end.
        structure.extend(["L"] * d)

    return IseSplitInfo(structure, size_fracs)

class IseActiveTabInfo:

    def __init__(self, active_tabs=None, active_group=None):
        self.active_tabs = active_tabs or []
        self.active_group = active_group or 0
        self.num_groups = len(self.active_tabs)

    def get_active_tab_for_group(self, n):
        if n < self.num_groups:
            return self.active_tabs[n]
        else:
            return 0

    def get_active_group(self):
        return self.active_group

def check_ise_active(key, raw, typedef):
    """
    :param raw: code representing the active tabs in the ISE.

        Example:

            3,2,0;1

        This means that there are three tab groups, and that:
            group 0: tab 3 is active
            group 1: tab 2 is active
            group 2: tab 0 is active
        and finally that group 1 is the active group.

        Thus, the indices before the semicolon say which of the (0-based)
        tabs in each group should be active within that group.
        The index after the semicolon says which of the (0-based) groups
        is the active one.

    :param typedef: nothing special
    :return: an IseActiveTabInfo instance
    """

    def raiseExcep():
        msg = f'Active tab code {raw} is malformed.'
        raise PfscExcep(msg, PECode.MALFORMED_ISE_ACTIVE_TAB_CODE, bad_field=key)

    parts = raw.split(';')
    if len(parts) != 2:
        raiseExcep()

    tabs, group_str = parts

    tab_str_list = tabs.split(',')
    try:
        tab_int_list = list(map(int, tab_str_list))
        group_num = int(group_str)
    except ValueError:
        raiseExcep()

    for n in tab_int_list + [group_num]:
        if n < 0:
            raiseExcep()

    return IseActiveTabInfo(tab_int_list, group_num)

class IseWidgetLinkInfo:

    def __init__(self, source, type_, group, target):
        """
        :param source: pair [g, t] giving the group and tab indices of the
            pane where the controlling widget group lives
        :param type_: (str) the widget's type
        :param group: (str) the name of the widget group
        :param target: pair [g, t] giving the group and tab indices of the
            pane where teh controlled content lives
        """
        self.source = source
        self.type_ = type_
        self.group = group
        self.target = target

    def __str__(self):
        sg, st = self.source
        t = self.type_
        g = self.group
        tg, tt = self.target
        return f'{sg},{st}-{t}.{g}-{tg},{tt}'

def check_ise_widget_link(key, raw, typedef):
    """
    :param raw: code defining a widget link.
        Example:

            2,4-foo.bar-3,1

        This means that the widget group of type "foo" and name "bar" in the
        annotation displayed in TabContainer 2, Tab 4, is to be linked to the
        content displayed in TabContainer 3, Tab 1.

    :param typedef: nothing special
    :return: an IseWidgetLinkInfo instance
    """

    def raiseExcep():
        msg = f'Widget link code {raw} is malformed.'
        raise PfscExcep(msg, PECode.MALFORMED_ISE_WIDGET_LINK_CODE, bad_field=key)

    parts = raw.split('-')
    if len(parts) != 3:
        raiseExcep()

    T = [parts[0], parts[2]]
    coords = []
    for t in T:
        N = t.split(',')
        try:
            C = list(map(int, N))
        except ValueError:
            raiseExcep()
        coords.append(C)

    source, target = coords
    center_parts = parts[1].split('.')
    if len(center_parts) != 2:
        raiseExcep()
    type_, group = center_parts

    return IseWidgetLinkInfo(source, type_, group, target)

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

import json
import re

import lark.exceptions

import pfsc.constants
from pfsc.excep import PfscExcep, PECode
from pfsc.build.lib.addresses import VersionedLibpathNode
from pfsc.build.lib.libpath import expand_multipath, PathInfo, get_modpath
from pfsc.build.repo import RepoFamily, RepoInfo, parse_repo_versioned_libpath
import pfsc.contenttree as contenttree
from pfsc.checkinput.version import (
    check_full_version, check_major_version, CheckedVersion)


class BoxListing:
    """
    Represents a "listing of boxes". The name of this class, and more generally the term "box",
    comes from the Moose forest browser, where nodes and deductions are referred to uniformly
    as "boxes".

    In working with Moose, (which includes writing chart widgets, in pfsc annotations) there are
    many places where users have the option to name zero or more boxes.

    Such a listing may be given in many ways:
      * It may not be defined at all, in the case of optional fields (so we get None when we look for it);
      * It may be a string giving either a single libpath or multipath, or a comma-delimited
        list of libpaths and multipaths;
      * It may be a list of strings giving a mixture of libpaths and multipaths;
      * Sometimes, it may be a string of the form `<...>`, i.e. beginning and
        ending with angle brackets, giving a special keyword.

    The purpose of this class is to accept such a value, and uniformize it.
    """

    def __init__(self, raw_value, allowed_keywords=None):
        """
        :param raw_value: the raw value of the box listing
        :param allowed_keywords: optional list of keywords allowed for this
            particular box listing. Keywords should be listed here *without*
            angle brackets.

        Our aim is to uniformize the input by storing either a list of
        libpaths, or a keyword value.
        """
        self.allowed_keywords = allowed_keywords or []

        # We record a keyword, which will remain `None` if the user did not provide one.
        self.keyword = None
        # All libpaths are initially considered to be (potential) multipaths, until expanded.
        self.multipaths = []
        # After expanding (potential) multipaths, we store them here as plain libpaths.
        self.libpaths = []
        # We may also want to check the libpaths, and so we can store CheckedLibpath instances as well.
        self.checked_libpaths = []

        # If no raw value was given, there is nothing for us to do.
        if raw_value is None:
            return
        # If a string was given...
        if isinstance(raw_value, str):
            # ...Is it an angle-bracketed keyword?
            if keyword := self.extract_keyword(raw_value):
                self.keyword = keyword
            # ...otherwise we parse it into a list of multipaths.
            else:
                self.multipaths = self.parse_raw_string_as_multipaths(raw_value)
        # If a list was given, we assume it is a list of multipaths.
        elif isinstance(raw_value, list):
            self.multipaths = raw_value
        # Otherwise it's an error.
        else:
            msg = 'Bad box listing: %s' % raw_value
            raise PfscExcep(msg, PECode.BAD_BOX_LISTING)

        # Finally, expand multipaths into plain libpaths.
        for mp in self.multipaths:
            self.libpaths.extend(expand_multipath(mp))

    def extract_keyword(self, raw_string):
        """
        Given a raw input string, determine whether it is an angle-bracketed
        one of our allowed keywwords.

        :return: the inner, unbracketed keyword, if it is one; else None
        """
        if raw_string.startswith("<") and raw_string.endswith(">"):
            if (inner := raw_string[1:-1]) in self.allowed_keywords:
                return inner
        return None

    @staticmethod
    def parse_raw_string_as_multipaths(raw_string):
        """
        Parse a string as a comma-delimited list of multipaths, with skipped
        whitespace.

        :return: list of strings, believed to be multipaths
        """
        mps = []
        mp = ''
        depth = 0
        for c in raw_string:
            if c in ' \t\r\n':
                continue
            if c == ',' and depth == 0:
                mps.append(mp)
                mp = ''
                continue

            if c == '{':
                depth += 1
                if depth > 1:
                    raise PfscExcep(f'Boxlisting contains nested braces: {raw_string}')
            elif c == '}':
                depth -= 1
                if depth < 0:
                    raise PfscExcep(f'Boxlisting contains unmatched braces: {raw_string}')

            mp += c
        if mp:
            mps.append(mp)
        return mps

    def is_keyword(self, *args):
        """
        Pass zero args to simply check whether this box listing is given by a keyword.
        Pass one arg (string) to check whether it is a certain keyword.
        """
        if len(args) == 1:
            return self.keyword == args[0]
        else:
            return self.keyword is not None

    def get_keyword(self):
        return self.keyword

    def get_libpaths(self):
        return self.libpaths

    def set_checked_libpaths(self, clps):
        self.checked_libpaths = clps

    def get_checked_libpaths(self):
        return self.checked_libpaths

def check_boxlisting(key, raw, typedef):
    """
    :param raw: The raw value of the boxlisting. May be None, str, or list.
    :param typedef:
        opt:
            allowed_keywords: list of keywords allowed for this box listing;
                see doctext for `BoxListing` class

            libpath_type: a typedef dict d. If given, we will pass this
                dictionary d to the check_libpath function when we check all
                libpaths in the boxlisting. CheckedLibpath instances will be
                stored in the BoxListing.

    :return: a BoxListing instance
    """
    # Form the BoxListing instance.
    ak = typedef.get('allowed_keywords', [])
    bl = BoxListing(raw, ak)
    # Check libpaths.
    lp_typedef = typedef.get('libpath_type', {})
    raw_libpaths = bl.get_libpaths()
    clps = []
    for lp in raw_libpaths:
        clp = check_libpath(key, lp, lp_typedef)
        clps.append(clp)
    bl.set_checked_libpaths(clps)
    return bl

LIBSEG_PATTERN = re.compile(r'^[a-zA-Z_!?]\w*$')

class CheckedLibseg:

    def __init__(self):
        # Checks:
        self.length_in_bounds = None
        self.valid_format = None
        # Data
        self.value = None

def check_libseg(key, raw, typedef):
    """
    Check a single segment in (or for) a libpath

    :param typedef: no special options
    :return: a CheckedLibseg object
    """
    checked = CheckedLibseg()
    # Legnth check:
    if len(raw) == 0:
        raise PfscExcep('Empty libseg', PECode.INPUT_EMPTY, bad_field=key)
    if len(raw) > pfsc.constants.MAX_LIBSEG_LEN:
        trunc = raw[:32]
        raise PfscExcep('libseg too long: "%s..."' % trunc, PECode.INPUT_TOO_LONG, bad_field=key)
    checked.value = raw
    checked.length_in_bounds = True
    # Format check:
    M = LIBSEG_PATTERN.match(raw)
    if M is None or M.group() != raw:
        msg = 'Segment %s is of bad format.' % raw
        raise PfscExcep(msg, PECode.BAD_LIBPATH, bad_field=key)
    checked.valid_format = True
    return checked

class EntityType:
    REPO = 'repo'
    MODULE = 'module'
    DEDUC = 'deduc'
    ANNO = 'anno'
    EXAMP = 'examp'
    NODE = 'node'
    WIDGET = 'widget'


def check_content_forest(key, raw, typedef):
    """
    :param raw: a "content forest" description, of the kind that can be parsed
        by the contenttree.py module.
    :param typedef: nothing special
    :return: list of AugmenetedLibpath instances
    """
    try:
        forest = contenttree.parse(raw)
    except lark.exceptions.LarkError as e:
        msg = f'Error while parsing content description "{raw}":\n  {e}'
        raise PfscExcep(msg, PECode.MALFORMED_CONTENT_FOREST_DESCRIP, bad_field=key)
    auglps = sum( [root.expand() for root in forest], [] )
    for alp in auglps:
        check_versioned_libpath(key, alp.libpath, {'form': 'repo'})
    return auglps


def check_goal_id(key, raw, typedef):
    """
    @param raw: a string representing a goal id, i.e. of the form
        {libpath}@{major}, where major is either an `int` or "WIP". Since
        numerical version numbers are `int`s, they are _not_ zero-padded.
    @param typedef: {
      OPT:
        allow_WIP: boolean, default True
    }
    @return: VersionedLibpathNode instance
    """
    td = typedef.copy()
    td['form'] = 'tail'
    td['version'] = 'major'
    td['allow_WIP'] = typedef.get('allow_WIP', True)
    return check_versioned_libpath(key, raw, td)


def check_versioned_libpath(key, raw, typedef):
    """
    :param raw: a string representing a versioned libpath. This should be of one
      of the known forms:
        tail-versioned: libpath@version
        repo-versioned: host.user.repo@version.remainder
      and the form should be noted in the typedef (see below).
      Whether the version part is full or just major, and whether "WIP" is
      allowed, is controlled by options (see below).
    :param typedef: {
      OPT:
        form: 'tail' or 'repo' (see above), default 'tail'
        version: 'full' or 'major', default 'full'
        allow_WIP: boolean, default True
        null_okay: set True to accept None, and return None in that case
    }
    :return: VersionedLibpathNode instance
    """
    def basic_err():
        msg = f'Malformed versioned libpath `{raw}`.'
        raise PfscExcep(msg, PECode.MALFORMED_VERSIONED_LIBPATH, bad_field=key)
    if raw is None:
        if typedef.get('null_okay'):
            return None
        else:
            basic_err()
    if not isinstance(raw, str):
        basic_err()
    form = typedef.get('form', 'tail')
    if form == 'repo':
        parts = parse_repo_versioned_libpath(raw)
    else:
        assert form == 'tail'
        parts = raw.split("@")
        if len(parts) != 2:
            basic_err()
    libpath = check_libpath(key, parts[0], {'value_only': True})

    version_type = typedef.get('version', 'full')
    if version_type == 'full':
        version = check_full_version(key, parts[1], typedef)
    else:
        td  = typedef.copy()
        td['tolerant'] = False
        maj = check_major_version(key, parts[1], td)
        version = CheckedVersion(None, maj, maj=="WIP")

    return VersionedLibpathNode(libpath, version)

def check_versioned_forest(key, raw, typedef, node=None, depth=0):
    """
    :param raw: Either a versioned forest representation itself -- which looks like

        {
            libpath.of.a.Thm@vers: {
                libpath.of.Pf.of.Thm@vers: {
                    libpath.of.an.expansion.on.Pf@vers: {},
                    libpath.of.another.expansion.on.Pf@vers: {}
                }
            },
            libpath.of.another.Thm@vers: {}
        }

      and can be obtained as the return value of `Floor.writeVersionedForestRepn()`
      in Moose -- or the JSON serialization thereof.

    :param typedef: nothing special
    :param node: optional VersionedLibpathNode for use with recursion
    :param depth: for use with recursion
    :return: a VersionedForest instance, representing the entire forest; it itself
        has `None` for both libpath and version, and it only serves to collect all
        the trees, as its children.
    """
    if depth > pfsc.constants.MAX_FOREST_EXPANSION_DEPTH:
        raise PfscExcep('Exceeded max forest expansion depth.', PECode.EXCEEDED_MAX_FOREST_EXPANSION_DEPTH)
    if isinstance(raw, str):
        try:
            d = json.loads(raw)
        except Exception:
            raise PfscExcep('Bad dictionary', PECode.INPUT_WRONG_TYPE, bad_field=key)
    else:
        d = raw
    if not isinstance(d, dict):
        raise PfscExcep('Bad dictionary', PECode.INPUT_WRONG_TYPE, bad_field=key)
    if node is None:
        node = VersionedLibpathNode(None, None)
    for k, v in d.items():
        child = check_versioned_libpath(key, k, {})
        check_versioned_forest(key, v, {}, node=child, depth=depth + 1)
        node.add_child(child)
    return node

class CheckedLibpath:

    def __init__(self):
        # Checks:
        self.length_in_bounds = None
        self.valid_format = None
        self.valid_repo_format = None
        self.is_repo = None
        self.is_module = None
        self.is_deduc = None
        self.is_node = None
        self.is_anno = None
        self.is_widget = None
        self.has_built_dashgraph = None
        self.has_built_annotation = None
        self.formally_within_module = None
        # Data
        self.value = None
        # Optionally loaded, depending on checks performed; see below
        self.pathInfo = None
        self.repoInfo = None

def check_libpath(key, raw, typedef):
    """
    :param typedef:
        optional:

            entity: the type of entity this libpath should point to. Should be a value of
                    the `EntityType` enum class. Raise an exception if the libpath does not
                    appear to point to an entity of this type.

            check_entity_type: boolean. If True, we check _all_ entity types, and no exceptions will be
                raised in these checks; we merely set the booleans (self.is_...) based on the results.
                So if True, this overrides the `entity` property.

            repo_format: boolean. If True, we check that the libpath is of valid format to
                         name a repo. This means that it is exactly three segments long, and
                         that the initial segment names a known repo family.

            formally_within_module: check that this libpath appears (formally) to name something within
                                    a module. This simply means that the libpath is at least one segment
                                    longer than the longest prefix that names a module. NB: the "formal"
                                    aspect of the check means that we do _not_ confirm whether there is
                                    actually any entity with this libpath.

            value_only: boolean. Default False, in which case we return a CheckedLibpath instance.
              Set True if instead you only want the `value` property thereof to be returned.

            short_okay: boolean. Default False, in which case libpath is expected to
                contain at least three segments (being the repopath).
                Set True to allow libpaths shorter than three segments.

    :return: a CheckedLibpath object, or just its `value` property (see above).
    """
    checked = CheckedLibpath()

    # Basic length checks.
    if len(raw) == 0:
        raise PfscExcep('Empty libpath', PECode.INPUT_EMPTY, bad_field=key)
    if len(raw) > pfsc.constants.MAX_LIBPATH_LEN:
        trunc = raw[:64]
        raise PfscExcep('libpath too long: "%s..."' % trunc, PECode.INPUT_TOO_LONG, bad_field=key)
    checked.value = raw
    checked.length_in_bounds = True

    # Check proper dotted path format
    parts = raw.split('.')
    # Need at least three parts to name a repo.
    if len(parts) < 3 and not typedef.get('short_okay'):
        msg = 'Libpath %s is too short.' % raw
        raise PfscExcep(msg, PECode.BAD_LIBPATH, bad_field=key)
    # Check format of each part.
    for part in parts:
        check_libseg(key, part, {})
    checked.valid_format = True

    # OPTIONAL CHECKS

    # Repo format?
    if typedef.get('repo_format'):
        if len(parts) != 3 or parts[0] not in RepoFamily.all_families:
            msg = 'Libpath %s is not of valid format to name a repo.' % checked.value
            raise PfscExcep(msg, PECode.MALFORMED_LIBPATH, bad_field=key)
        else:
            checked.valid_repo_format = True

    # Formally within module?
    if typedef.get('formally_within_module'):
        deepest_modpath = get_modpath(checked.value)
        if len(deepest_modpath.split('.')) == len(parts):
            msg = 'Libpath does not appear to lie within a module: %s' % checked.value
            raise PfscExcep(msg, PECode.LIBPATH_IS_NOT_WITHIN_MODULE)
        else:
            checked.formally_within_module = True

    # Do specific checks for special entity types.
    entity_type = typedef.get('entity')
    check_all = typedef.get('check_entity_type')

    if check_all or entity_type == EntityType.REPO:
        ri = RepoInfo(checked.value)
        checked.is_repo = len(parts) == 3 and ri.is_git_repo
        checked.repoInfo = ri
        if not check_all and not checked.is_repo:
            msg = 'Libpath %s does not point to a repo.' % ri.libpath
            raise PfscExcep(msg, PECode.LIBPATH_IS_NOT_REPO, bad_field=key)

    if check_all or entity_type == EntityType.MODULE:
        pi = PathInfo(checked.value)
        checked.pathInfo = pi
        checked.is_module = pi.is_module(strict=False)
        if not check_all and not checked.is_module:
            msg = 'Libpath %s does not point to a module.' % pi.libpath
            raise PfscExcep(msg, PECode.MODULE_DOES_NOT_EXIST, bad_field=key)

    if check_all or entity_type == EntityType.DEDUC:
        # FIXME: need to pass a major vers to `is_deduc()`:
        from pfsc.gdb import get_graph_reader
        checked.is_deduc = get_graph_reader().is_deduc(checked.value)
        if not check_all and not checked.is_deduc:
            msg = 'Libpath %s does not point to a deduction.' % checked.value
            raise PfscExcep(msg, PECode.DEDUC_NOT_FOUND, bad_field=key)

    if check_all or entity_type == EntityType.ANNO:
        # FIXME: need to pass a major vers to `is_anno()`:
        from pfsc.gdb import get_graph_reader
        checked.is_anno = get_graph_reader().is_anno(checked.value)
        if not check_all and not checked.is_anno:
            msg = 'Libpath %s does not point to an annotation.' % checked.value
            raise PfscExcep(msg, PECode.ANNO_NOT_FOUND, bad_field=key)

    if entity_type == EntityType.EXAMP:
        # TODO: implement the check
        raise Exception("Check not yet implemented for entity type: " + entity_type)

    if entity_type == EntityType.NODE:
        # TODO: implement the check
        raise Exception("Check not yet implemented for entity type: " + entity_type)

    if entity_type == EntityType.WIDGET:
        # TODO: implement the check
        raise Exception("Check not yet implemented for entity type: " + entity_type)

    if typedef.get('value_only'):
        return checked.value
    return checked

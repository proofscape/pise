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

from collections import defaultdict
import json
import re

import lark.exceptions

import pfsc.constants
from pfsc.constants import PFSC_EXT, RST_EXT
from pfsc.excep import PfscExcep, PECode
from pfsc.build.lib.addresses import VersionedLibpathNode
from pfsc.build.lib.libpath import expand_multipath, PathInfo, get_modpath
from pfsc.build.repo import RepoFamily, RepoInfo, parse_repo_versioned_libpath
import pfsc.contenttree as contenttree
from pfsc.checkinput.version import (
    check_full_version, check_major_version, CheckedVersion)
from pfsc.lang.freestrings import Libpath


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

    @classmethod
    def make_union(cls, bls):
        """
        Pass a list of `BoxListing` instances. We return a new one, in which the `self.libpaths`
        and `self.checked_libpaths` lists have been combined, with no repeats. A "repeat" in
        the latter list means that the two have the same raw string value, and in that case
        the earlier one is retained.

        If any given `BoxListing` has a keyword value, an exception is raised.

        Sets are used for the calculation, so, for deterministic output, the lists are sorted
        lexicographically by libpath, before returning.
        """
        if any(bl.keyword for bl in bls):
            raise PfscExcep(
                'Cannot unite boxlistings in which any has a keyword value.',
                PECode.CANNOT_UNITE_BOXLISTINGS
            )

        bl0 = cls(None)

        # Reverse list of inputs so that earlier ones control.
        inputs = list(reversed(bls))

        libpaths = set()
        for bl in inputs:
            libpaths.update(set(bl.libpaths))
        bl0.libpaths = sorted(libpaths)

        checked = {}
        for bl in inputs:
            checked.update({cl.value: cl for cl in bl.checked_libpaths})
        bl0.checked_libpaths = [
            checked[lp] for lp in sorted(checked.keys())
        ]

        return bl0

    def union(self, *others):
        bls = [self] + others
        return self.make_union(bls)

    @property
    def bracketed_keyword(self):
        if self.keyword:
            return f'<{self.keyword}>'
        return None

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
        Pass one arg (string) to check whether it is a certain keyword. In this case,
        pass the keyword *without* angle brackets, e.g. 'all'.
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


def check_relboxlisting(key, raw, typedef):
    """
    Check a boxlisting, where libpaths are allowed to be relative.

    This is a convenience function that calls `check_boxlisting()` after first
    setting the `short_okay` option to `True` in the `libpath_type` in the `typedef`.
    """
    enriched_typedef = typedef.copy()
    libpath_type_field_name = 'libpath_type'
    libpath_type_dict = enriched_typedef.get(libpath_type_field_name, {})
    libpath_type_dict['short_okay'] = True
    enriched_typedef[libpath_type_field_name] = libpath_type_dict
    return check_boxlisting(key, raw, enriched_typedef)


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
PROHIBITED_LIBSEGS = {'true', 'false', 'null'}


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

    :param typedef:
        opt:
            user_supplied: boolean, saying whether this name was supplied
                by a user. If so, it is not allowed to begin with underscore,
                exclamation point, or question mark.
                Default: False

    :return: a CheckedLibseg object
    """
    checked = CheckedLibseg()

    # Prohibited values check:
    if raw in PROHIBITED_LIBSEGS:
        raise PfscExcep(f'Illegal libpath segment: "{raw}"', PECode.BAD_LIBPATH, bad_field=key)

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

    if typedef.get('user_supplied'):
        if raw[0] in '_!?':
            msg = f'User supplied libpath segment `{raw}` cannot begin with `{raw[0]}`.'
            raise PfscExcep(msg, PECode.BAD_LIBPATH, bad_field=key)

    checked.valid_format = True
    return checked


class CheckedModuleFilename:

    def __init__(self, stem_segment, extension):
        """
        :param stem_segment: CheckedLibseg
        :param extension: string
        """
        self.checked_stem_segment = stem_segment
        self.extension = extension

    def __str__(self):
        return f'{self.checked_stem_segment.value}.{self.extension}'


def check_module_filename(key, raw, typedef):
    """
    :param raw: str, giving a proposed full filename for a module file.
        Should be of the form STEM.EXTENSION.
    :param typedef:
        opt:
            segment: a typedef dict that will be forwarded to the `check_libseg()`
                function, for checking the stem.
            allow_pfsc: boolean, saying whether the `pfsc` extension is allowed.
                Default: True.
            allow_rst: boolean, saying whether the `rst` extension is allowed.
                Default: True.

    :return: CheckedModuleFilename
    """

    allow_pfsc = typedef.get('allow_pfsc', True)
    allow_rst = typedef.get('allow_rst', True)
    allowed_exts = []
    if allow_pfsc:
        allowed_exts.append(PFSC_EXT)
    if allow_rst:
        allowed_exts.append(RST_EXT)
    expected_ext = ' or '.join([f'"{ext}"' for ext in allowed_exts])

    parts = raw.split('.')
    if len(parts) != 2:
        msg = f'Bad filename "{raw}".'
        if expected_ext:
            msg += f' Should have extension {expected_ext}.'
        raise PfscExcep(msg, PECode.BAD_MODULE_FILENAME, bad_field=key)

    stem, pure_ext = parts

    dotted_ext = f'.{pure_ext}'
    if dotted_ext not in allowed_exts:
        msg = f'File name "{raw}" has bad extension.'
        if expected_ext:
            msg += f' Expected {expected_ext}.'
        raise PfscExcep(msg, PECode.BAD_MODULE_FILENAME, bad_field=key)

    segment_typedef = typedef.get('segment', {})
    checked_stem = check_libseg(key, stem, segment_typedef)

    return CheckedModuleFilename(checked_stem, pure_ext)


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


def check_relpath(key, raw, typedef):
    """
    Check a relative libpath.

    Actually just a convenience function to call `check_libpath()` after first setting
    the `short_okay` option to `True` in the `typedef`.
    """
    enriched_typedef = typedef.copy()
    enriched_typedef['short_okay'] = True
    return check_libpath(key, raw, enriched_typedef)


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

            is_Libpath_instance: boolean, default False. Set True to require
                that the given raw string actually be an instance of the
                `pfsc.lang.freestrings.Libpath` class.

    :return: a CheckedLibpath object, or just its `value` property (see above).
    """
    if not isinstance(raw, str):
        raise PfscExcep('Expecting string', PECode.INPUT_WRONG_TYPE, bad_field=key)

    if typedef.get('is_Libpath_instance') and not isinstance(raw, Libpath):
        raise PfscExcep('Expecting Libpath', PECode.INPUT_WRONG_TYPE, bad_field=key)

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


def check_chart_color(key, raw, typedef):
    """
    Check the value of a specification for one of the color options ('color' or 'hoverColor')
    for chart widgets.

    Accepts both the newer string format and the older dictionary format.
    Normalizes the output so that:
        - it is in the old, dictionary format
        - keys are color codes, values are `BoxListing` instances

    :param typedef:
        optional:
            update_allowed: boolean, default False. If True, allow the 'update' color command
                to be accepted. Otherwise, raise an exception if it is encountered.

    Note: At this time, we are not checking that the color codes are well-formed.
    Might want to add that check in the future.

    Explanation of new, string format:

        In the old format, a color field is given by a dictionary
        of key-value pairs. Because keys must be unique there, we allowed the keys
        to be either color codes, or multipaths.

        Here, you should instead give a listing of `colorCodes: boxlisting` pairs,
        one per line, where the color codes are comma separated.

        In the boxlistings, there is no need for surrounding brackets to make a list,
        or for quotation marks to make a string. Thus, for example, you may write

            Thm.A10, Pf.{A10,A20}

        which is equivalent to ["Thm.A10", "Pf.{A10,A20}"]` in the dictionary format.

        Because there is no unique-key constraint, there is no reason to allow
        multipaths on the left. (For dictionaries, we decided you might want to be
        able to use the same color spec twice, without having to make a giant RHS,
        so we allowed the option of putting the libpaths on the LHS.)
        Therefore color codes should always be on the left, boxlistings on the right.

        Since multipaths are no longer allowed on the left, there is no longer a
        need to disambiguate between color codes and libpaths, and therefore color
        codes no longer need to be preceded by colons. Therefore color codes should
        simply be separated by commas.

        As in the dictionary format, we support the special `update` color code,
        which applies to the whole directive, and therefore does not need any
        righthand side. Just write the word 'update', by itself, on a line (no quotation
        marks).

        Example:

            update
            push,bgR,olY,fi0,diGB: libpath.to.node1

        which means:

            Do not clear existing colors; simply add the given settings.
            For node1:
                - push current colors onto node1's color stack
                - set background red
                - set outline yellow
                - clear any existing colors from incoming flow edges
                - give incoming deduction edges a gradient from green to blue

        Note that `update` is meaningless in hoverColor, which is always done as
        an update.

        See the docstring for the ColorManager class in pfsc-moose for more info.


    :return: dict with string keys and `BoxListing` values
    """
    update = False
    color_to_raw = defaultdict(list)

    if isinstance(raw, str):
        lines = [L.strip() for L in raw.split('\n')]
        for line in lines:
            if not line:
                continue
            if line == 'update':
                update = True
                continue
            parts = [p.strip() for p in line.split(":")]
            if len(parts) != 2:
                raise PfscExcep(f'Each line in the "{key}" string format'
                                ' should have a single colon (:), with a comma-separated list'
                                ' of color codes on the left, and a boxlisting on the right.',
                                PECode.MALFORMED_COLOR_CODE)
            comma_sep_color_codes, raw_box_listing = parts
            color_codes = [c.strip() for c in comma_sep_color_codes.split(',')]
            # Restore the leading colons expected in the old format.
            color_spec = ":" + ":".join(color_codes)
            color_to_raw[color_spec].append(raw_box_listing)

    elif isinstance(raw, dict):
        for k, v in raw.items():
            if not isinstance(k, str):
                raise PfscExcep('Keys in color option dictionaries must be strings.',
                                PECode.INPUT_WRONG_TYPE)
            if not k:
                raise PfscExcep('Keys in color option dictionaries must be nonempty strings.',
                                PECode.INPUT_WRONG_TYPE)
            if v and k == ':update':
                update = True
                continue
            color_spec, raw_box_listing = (k, v) if k[0] == ":" else (v, k)
            color_to_raw[color_spec].append(raw_box_listing)

    else:
        raise PfscExcep('Color spec should be dict or string', PECode.INPUT_WRONG_TYPE)

    # Note: At this time, we are not checking that the color codes are well-formed.
    # Might want to add that check in the future.

    normalized = {}

    if update:
        update_allowed = typedef.get('update_allowed', False)
        if not update_allowed:
            raise PfscExcep(f'Color spec for "{key}" cannot use "update" command.', PECode.MALFORMED_COLOR_CODE)
        normalized[':update'] = True

    for color_spec, raw_box_listings in color_to_raw.items():
        bls = [check_relboxlisting(key, rbl, {}) for rbl in raw_box_listings]
        normalized[color_spec] = BoxListing.make_union(bls)

    return normalized

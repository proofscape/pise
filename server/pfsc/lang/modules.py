# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2024 Proofscape Contributors                           #
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
Parse .pfsc modules, and build internal representations of the objects
they declare, using the classes in the deductions and annotations (python) modules.
"""

import datetime
import pickle
import re

from lark import Lark, v_args
from lark.exceptions import VisitError, LarkError

from pfsc.lang.annotations import Annotation
from pfsc.lang.freestrings import (
    PfscJsonTransformer, json_grammar, json_grammar_imports, Libpath
)
from pfsc.lang.deductions import (
    PfscObj, Deduction, SubDeduc, Node, Supp, Flse, node_factory,
)
from pfsc.lang.objects import PfscDefn
from pfsc.lang.widgets import Widget
from pfsc.excep import PfscExcep, PECode
from pfsc.build.lib.libpath import PathInfo, get_modpath
from pfsc.build.repo import get_repo_part, get_repo_info
from pfsc.build.versions import version_string_is_valid
from pfsc.permissions import have_repo_permission, ActionType
from pfsc_util.scan import PfscModuleStringAwareScanner
import pfsc.util as util
import pfsc.constants


class PfscModule(PfscObj):
    """
    Represents a whole Proofscape Module.
    """

    def __init__(
            self, libpath, version=pfsc.constants.WIP_TAG,
            given_dependencies=None, read_time=None
    ):
        """
        :param libpath: the libpath of this module.
        :param version: the version of this module.
        :param given_dependencies: a dependencies lookup which, if given, will
          override that which we obtain from our root module.
        """
        PfscObj.__init__(self)
        self.libpath = libpath
        self.read_time = read_time
        self.repopath = get_repo_part(libpath)
        self.version = version
        self._modtext = None  # place to stash the original text of the module
        self._bc = None  # place to stash the BlockChunker that processed this module's text
        self.dependencies = None
        if given_dependencies is not None:
            self.load_and_validate_dependency_info()
            assert isinstance(self.dependencies, dict)
            self.dependencies.update(given_dependencies)
        self.pending_imports = []
        self.resolving = False
        self.resolved = False

    def add_pending_import(self, pi):
        self.pending_imports.append(pi)

    def list_modules_imported_from(self):
        return [pi.src_modpath for pi in self.pending_imports]

    def get_oldest_built_product_timestamp(self):
        """
        Get the oldest timestamp on any of this module's existing built
        products in the build dir, if any, else -1.
        """
        pi = PathInfo(self.libpath)
        times = pi.get_built_product_modification_times(version=self.version)
        return max([-1] + list(times.values()))

    def partial_resolve_external_at_wip(self, cache=None, prog_mon=None):
        """
        If this module has any imports of external modules @WIP, do a partial
        resolution on them now, i.e. just load all the modules, recursively.

        :return: the latest timestamp for the resolved modules, or any modules
            resolved recursively under them, else -1 if no such modules.
        """
        latest_read_time = -1
        for pi in self.pending_imports:
            if pi.is_external_at_wip():
                lrt = pi.resolve(cache=cache, prog_mon=prog_mon, load_only=True)
                latest_read_time = max(latest_read_time, lrt)
        return latest_read_time

    def resolve(self, cache=None, prog_mon=None, load_only=False):
        """
        RESOLUTION steps that are delayed so that we can have a pure READ phase,
        when initially building modules.

        :return: the latest read time (Unix time stamp) of this module, or any
            module imported under it, recursively.
        """
        latest_read_time = self.read_time or 0
        if not self.resolved and not self.resolving:
            self.resolving = True

            if cache is None:
                cache = {}

            if prog_mon:
                prog_mon.set_message(f'Resolving imports from {self.libpath}...')

            for pi in self.pending_imports:
                lrt = pi.resolve(cache=cache, prog_mon=prog_mon, load_only=load_only)
                latest_read_time = max(latest_read_time, lrt)

            if not load_only:
                if prog_mon:
                    prog_mon.set_message(f'Resolving {self.libpath}...')

                self.resolve_libpaths_to_rhses()

                native = self.getNativeItemsInDefOrder()
                for item in native.values():
                    if isinstance(item, PfscObj):
                        item.resolve()

                self.resolved = True

            self.resolving = False

        return latest_read_time

    def isRepo(self):
        return self.libpath == self.repopath

    def isSpecial(self):
        return self.libpath.startswith('special.')

    def isTerminal(self):
        pi = PathInfo(self.libpath)
        return pi.is_file

    def getDependencies(self):
        return self.dependencies or {}

    def resolve_libpaths_to_rhses(self):
        """
        Visit all items recursively, and replace `Libpath` instances with
        RHSes of `PfscAssigment`s in those cases where they point to them.

        This takes over, in the READ/RESOLVE design, for the resolution that
        used to take place in `PfscJsonTransformer.json_libpath()`.
        """
        def replace_or_replace_within(item, scope):
            """
            If item is a `Libpath`, then resolve to RHS or not at all; if it
            is a list or dict, resolve recursively within.

            Return the given item itself unless it was a `Libpath` that
            resolved to an RHS, in which case return the RHS.
            """
            if isinstance(item, Libpath):
                return item.resolve_to_rhs_or_not_at_all(scope)
            elif isinstance(item, list):
                for i, list_item in enumerate(item):
                    item[i] = replace_or_replace_within(list_item, scope)
            elif isinstance(item, dict):
                for k, v in item.items():
                    item[k] = replace_or_replace_within(v, scope)
            return item

        def visit(obj):
            """
            An `assignment` in a pfsc module can occur only at the top level
            (i.e. as a `tla`), or else among `nodecontents` or `deduccontents`.

            At the top level, a `PfscAssignment` is stored as the value.
            In node or deduc contents, the RHS value is stored instead.

            Therefore we need only consider `Node`, `Deduction`, and
            `PfscAssignment` items here.
            """
            if isinstance(obj, (Node, Deduction)):
                native = obj.getNativeItemsInDefOrder(accept_primitive=True)
                for name, item in native.items():
                    obj[name] = replace_or_replace_within(item, obj)
            elif isinstance(obj, PfscAssignment):
                obj.rhs = replace_or_replace_within(obj.rhs, obj)
            elif isinstance(obj, Widget):
                replace_or_replace_within(obj.raw_data, obj)

        self.recursiveItemVisit(visit)

    def load_and_validate_dependency_info(self):
        if self.dependencies is None:
            deps = {}
            if not self.isSpecial():
                root_module = self if self.isRepo() else load_module(
                    self.repopath, version=self.version, fail_gracefully=True, history=[]
                )
                if root_module:
                    # No need to call root_module.resolve(), since we are only interested in
                    # an assignment made in this module (which needs no resolution).
                    deps = root_module.getAsgnValue(pfsc.constants.DEPENDENCIES_LHS, default={})

            checked_deps = {}
            for r, v in deps.items():
                # Being drawn from a parsed module, the keys and values in the `deps` dict will be
                # not pure strings but `Markup` instances. We convert them into pure strings now,
                # to avoid potential trouble. In particular, the version will wind up being a parameter
                # in Cypher queries. In RedisGraph this used to lead to trouble when `Graph.build_params_header()`
                # (in redisgraph-py v2.4.0) added quotation marks to param values. The problem then was that, e.g.
                # `Markup('foo') + '"' --> Markup('foo&#34;')` and we got unwanted HTML escapes.
                # This has since been repaired, but I'm keeping the string conversion here just
                # to be on the safe side.
                r, v = str(r), str(v)
                if not version_string_is_valid(v, allow_WIP=True):
                    msg = f'Repo `{self.repopath}` defines invalid version `{v}` for dependency `{r}`.'
                    raise PfscExcep(msg, PECode.MALFORMED_VERSION_TAG)
                checked_deps[r] = v

            self.dependencies = checked_deps

    def getRequiredVersionOfObject(self, libpath, extra_err_msg=''):
        """
        Determine, according to the dependencies declaration for the repo to which
        this module belongs, what is the required version of a given object.

        :param libpath: the libpath of the object whose required version we want.
        :param extra_err_msg: extra string to be added onto the error message, in
            case the version number is unavailable. This can provide helpful info
            about where/why the version number is needed.
        :return: the required version string.
        """
        self.load_and_validate_dependency_info()
        repopath = get_repo_part(libpath)
        if repopath == self.repopath:
            return self.version
        if repopath not in self.dependencies:
            msg = f'Repo `{self.repopath}` failed to define required version of `{repopath}`.'
            msg += f' Check "{pfsc.constants.DEPENDENCIES_LHS}" declaration in root module.'
            msg += extra_err_msg
            raise PfscExcep(msg, PECode.MISSING_REPO_DEPENDENCY_INFO)
        return self.dependencies[repopath]

    def getVersion(self):
        return self.version

    def setBlockChunker(self, bc):
        self._bc = bc

    def getBlockChunker(self):
        return self._bc

    def modtext(self, *args):
        if len(args) == 0:
            return self._modtext
        else:
            self._modtext = args[0]

    def get_build_dir_src_code_path(self, version=pfsc.constants.WIP_TAG):
        pi = PathInfo(self.libpath)
        return pi.get_build_dir_src_code_path(version=version)

    def list_existing_built_product_paths(self, version=pfsc.constants.WIP_TAG):
        pi = PathInfo(self.libpath)
        return pi.list_existing_built_product_paths(version=version)
                
    def getBuiltVersion(self):
        if rst_src := getattr(self, '_rst_src', None):
            return rst_src
        return self._bc.write_module_text()

    def writeBuiltVersionToDisk(self, writeOnlyIfDifferent=True, makeTildeBackup=True):
        """
        Since the build process can supply missing widget names, it can be useful
        to write the built version to disk.

        :param writeOnlyIfDifferent: True means we will write to disk only if the text has changed.
        :param makeTildeBackup: True means that before writing the current version to disk, we rename
                                the existing version with a tilde at the end of the filename.
        :return: number of bytes written
        """
        text = self.getBuiltVersion()
        n = 0
        if (not writeOnlyIfDifferent) or text != self._modtext:
            pi = PathInfo(self.libpath)
            if makeTildeBackup:
                pi.make_tilde_backup()
            n = pi.write_module(text)
        return n

    def lazyLoadSubmodule(self, name):
        """
        Attempt to load a submodule.
        If we succeed, we both store the submodule in this module under its name,
        and return the submodule.

        @param name: the name of the supposed submodule
        @return: the loaded submodule, if found, else None
        """
        possible_submodule_path = '.'.join([self.libpath, name])
        sub = load_module(possible_submodule_path, version=self.version, fail_gracefully=True)
        if sub is not None:
            sub.resolve()
            self[name] = sub
        return sub

    def isModule(self):
        return True

    def getNativeItemsInDefOrder(self, hoist_expansions=False):
        """
        Get an ordered dict of all native items in definition order.

        :param hoist_expansions: if True, we start with definition order, but then
          "hoist expansions," so that, if E --> D then E comes immediately after D.
        :return: ordered dict of native items
        """
        native = PfscObj.getNativeItemsInDefOrder(self)

        if hoist_expansions:
            nodes = {}  # lookup of DoublyLinkedListNodes by libpath of item
            start_node = util.DoublyLinkedListNode(None)
            prev = start_node
            for name, item in native.items():
                node = util.DoublyLinkedListNode((name, item), prev=prev)
                nodes[item.getLibpath()] = node
                if prev is not None:
                    prev.next = node
                prev = node
            for node in nodes.values():
                name, item = node.data
                if isinstance(item, Deduction):
                    tdlp = item.getTargetDeducLibpath()
                    if tdlp in nodes:
                        parent = nodes[tdlp]
                        node.extract()
                        parent.set_next(node)
            native = {}
            node = start_node.next
            seen = set()
            while node is not None:
                name, item = node.data
                native[name] = item
                node = node.next
                # There shouldn't be any cycles, but just in case...
                libpath = item.getLibpath()
                if libpath in seen:
                    raise PfscExcep(f'Cycle detected among expansions in module {self.libpath}', PECode.DAG_HAS_CYCLE)
                seen.add(libpath)

        return native

    def listNativeNodesByLibpath(self):
        nodelist = []
        deducs = self.getAllNativeDeductions()
        for deduc in deducs:
            deduc.listNativeNodesByLibpath(nodelist)
        return nodelist

    def getAllNativeNodes(self):
        nodelist = []
        deducs = self.getAllNativeDeductions()
        for deduc in deducs:
            deduc.getAllNativeNodes(nodelist)
        return nodelist

    def getAllNativeDeductions(self, toposort=True, numberednames=True):
        names = self.listNativeDeducsByName(toposort=toposort, numberednames=numberednames)
        deducs = [self[name] for name in names]
        return deducs

    def getAllDeductionsOfDeduction(self, T):
        """
        T an instance of the Deduction class, belonging to
        this module.
        Return a list of all Deductions declared in this module
        having T as target.
        """
        deds = []
        for item in self.items.values():
            if callable(getattr(item, 'getTargetDeduction', None)):
                S = item.getTargetDeduction()
                if S == T:
                    deds.append(item)
        return deds

    def buildAllDashgraphs(
            self,
            lang='en',
            nativeOnly=False,
            skiplist=None
    ):
        if skiplist is None: skiplist=[]
        dashgraphs = {}
        for item in self.items.values():
            if (
                callable(getattr(item, 'buildDashgraph', None)) and
                callable(getattr(item, 'getName', None))
            ):
                name = item.getName()
                if name in skiplist:
                    continue
                if nativeOnly:
                    # Build dg only for deducs native to this module.
                    ilp = item.getLibpath()
                    slp = self.libpath
                    m = len(ilp)
                    n = len(slp)
                    if ilp[:n] != slp or m <= n or ilp[n] != '.':
                        continue
                dg = item.buildDashgraph(lang=lang)
                dashgraphs[name] = dg
        return dashgraphs

    def listNativeDeducsByName(self, toposort=True, numberednames=True):
        """
        Return a list of the local names (e.g. "Thm", "Pf", "Xpan") of the
        deductions defined in this module.
        :param toposort: If True (the default) then the deduction names are
                         sorted in topological order, so that if E --> D then
                         D comes before E in the list.

                         This is useful e.g. for adding all the deducs to the
                         index, where D should have a row before we try to say
                         that E expands on D.
        :param numberednames: If True then, secondary to topological ordering,
                              names are sorted according to numerical suffixes.
                              E.g. this is so `Thm9` comes before `Thm10`.
                              See `NumberedName` class in util module.
        """
        # First find the names of all the native deductions.
        names = []
        slp = self.libpath
        n = len(slp)
        for name, item in self.items.items():
            # Is item a Deduction?
            if not isinstance(item, Deduction): continue
            # Is item native?
            ilp = item.getLibpath()
            m = len(ilp)
            if ilp[:n] != slp or m <= n or ilp[n] != '.':
                continue
            # Add name.
            names.append(name)
        # Now do topological sort, if requested.
        if toposort:
            # First must build digraph representation.
            graph = {}
            for E_name in names:
                E = self[E_name]
                D = E.getTargetDeduction()
                outnbrs = []
                if D is not None:
                    # D only belongs in the digraph if it is also native.
                    ilp = D.getLibpath()
                    m = len(ilp)
                    if ilp[:n] == slp and m > n and ilp[n] == '.':
                        D_name = D.getName()
                        outnbrs.append(D_name)
                graph[E_name] = outnbrs
            # Want e.g. Thm to come before Pf, so set reversed=True in topo sort.
            secondary_key = util.NumberedName if numberednames else None
            names = util.topological_sort(graph, reversed=True, secondary_key=secondary_key)
        return names


# TODO: "take REPO_PATH at COMMIT_HASH" ???
# Do we want to support a
#
#     take REPO_PATH at COMMIT_HASH
#
# statement? It would be kind of like explicitly noting, in any software project, the
# version number you require for any of your dependencies.

pfsc_grammar = r'''
    module : (import|deduc|anno|defn|tla)*

    ?import : plainimport
            | fromimport
    plainimport : "import" (relpath|libpath) ("as" IDENTIFIER)?
    fromimport : "from" (relpath|libpath) "import" (STAR|identlist ("as" IDENTIFIER)?)

    relpath : RELPREFIX libpath?
    libpath : IDENTIFIER ("." IDENTIFIER)*
    identlist : IDENTIFIER ("," IDENTIFIER)*

    deduc : deducpreamble "{" deduccontents "}"
    deducpreamble : "deduc" IDENTIFIER (OF targets)? (WITH targets)?
    targets : libpath ("," libpath)*

    deduccontents : (subdeduc|node|clone|assignment)*

    subdeduc : "subdeduc" IDENTIFIER "{" deduccontents "}"

    ?node : basicnode
          | suppnode
          | wolognode
          | flsenode

    basicnode : NODETYPE IDENTIFIER "{" nodecontents "}"

    suppnode : "supp" IDENTIFIER ("versus" targets)? "{" nodecontents "}"

    wolognode : WOLOGTYPE IDENTIFIER "wolog" "{" nodecontents "}"

    flsenode : "flse" IDENTIFIER ("contra" targets)? "{" nodecontents "}"

    nodecontents : (node|assignment)*

    clone : "clone" libpath ("as" IDENTIFIER)?

    anno: "anno" IDENTIFIER ("on" targets)?

    defn: "defn" IDENTIFIER ve_string ve_string

    tla : assignment

    assignment : IDENTIFIER "=" json_value

    STAR : "*"

    OF: "of"

    WITH: "with"

    IDENTIFIER : CNAME

    RELPREFIX : "."+

    NODETYPE : "asrt"|"cite"|"exis"|"intr"|"mthd"|"rels"|"univ"|"with"

    WOLOGTYPE : "mthd"|"supp"
'''

# We don't actually need any further imports beyond the json_grammar_imports.
pfsc_grammar_imports = '''
'''

# Pass `propagate_positions=True` so that non-terminal handlers in the `ModuleLoader`
# can use `@v_args` to get a `meta` arg containing line and column numbers.
pfsc_parser = Lark(
    pfsc_grammar + json_grammar + pfsc_grammar_imports + json_grammar_imports,
    start='module',
    propagate_positions=True
)

BLOCK_RE = re.compile(r'(anno +([a-zA-Z]\w*)[^@]*?)@@@(\w{,8})(\s.*?)@@@\3', flags=re.S)


class BlockChunker:
    '''
    Contrary to the appearance of the pfsc_parser definition in EBNF above, "annotation blocks"
    in actual pfsc modules should look like this:

        anno <NameOfBlock> <targets>? """
            ...pfsc-flavored markdown...
        """

    However, it does not make sense to pass all of this directly to the Earley-algorithm parser
    we build using Lark.

    Furthermore, the markdown in the anno block is apt to contain many `#` chars (for headings),
    which we need to protect from the step that strips comments out of the module.

    Therefore we have this class to perform a pre-processing step in which we:
      (a) simplify the module before passing to Earley algorithm, and
      (b) protect `#` chars in anno blocks

    We locate all anno blocks, and take away the interior text and bracketing quotes, leaving
    just the `anno` keyword, the name of the block, and the targets (if any).

    We store the text so modified, along with dicts mapping the block names to the original
    text (minus bracketing quotes).
    '''
    def __init__(self, text, base_line_num=0):
        """
        :param text: the original text of a pfsc module
        :param base_line_num: optionally pass an integer, in order to offset
            all line numbers by this amount
        """
        self.text = text
        chunks = BLOCK_RE.split(text)
        self.chunks = chunks
        self.n = int((len(chunks)-1)/5)

        # We will record data in order to achieve a "line mapping". This is so that line numbers in
        # the modified text we are going to produce can be mapped back to their correct values in the original text.
        # This is useful in reporting parsing errors or seeking a definition in a module.
        # Note: since mapping list will be reversed later, the entry added here
        # will come last.
        self.line_mapping = [(-1, base_line_num)]
        self.line_no = 1
        self.lines_cut = 0

        def keep_lines(chunk):
            n = chunk.count('\n')
            self.line_no += n

        def cut_lines(chunk):
            n = chunk.count('\n')
            self.lines_cut += n
            self.line_mapping.append((self.line_no, self.lines_cut + base_line_num))

        # Record the first text chunk.
        c0 = chunks[0]
        mod_text_parts = [c0]
        keep_lines(c0)

        # anno_lookup maps the identifiers of anno blocks (their "names", in other words)
        # to the original text of those blocks (sans bracketing triple-quotes)
        self.anno_lookup = {}
        for k in range(self.n):
            # a : anno preamble
            # an: ANNONAME
            # ad: anno delimiter code
            # ac: ANNOCONTENTS
            # t : TEXT
            a, an, ad, ac, t = chunks[5*k+1:5*k+6]
            mod_text_parts.append(a)
            self.anno_lookup[an] = ac
            cut_lines(ac)
            mod_text_parts.append(t)
            keep_lines(t)

        # For use in computing line mappings, the list we recorded needs to be reversed.
        self.line_mapping.reverse()
        # Build the modified text.
        self.modified_text = ''.join(mod_text_parts)
        # annotations_by_name will map the names of Annotation instances to those instances;
        # these names are the same as the identifiers of the original anno blocks.
        self.annotations_by_name = {}

    def map_line_num_to_orig(self, n):
        for lb, a in self.line_mapping:
            if n > lb:
                n += a
                break
        return n

    def get_modified_text(self):
        return self.modified_text

    def add_annotation(self, a):
        """
        :param a: an Annotation instance
        """
        self.annotations_by_name[a.name] = a

    def write_module_text(self, widget_data=None):
        """
        Write the text for the module, after substituting new widget data.
        :param widget_data: dict mapping widget libpaths to new data for those widgets.
                            See the `Annotation` class's `write_anno_text` method for format.
        :return: the module text, with substitutions
        """
        if widget_data is None: widget_data = {}
        chunks = self.chunks
        mod_text_parts = [chunks[0]]
        for k in range(self.n):
            a, an, ad, ac, t = chunks[5*k+1:5*k+6]
            anno_obj = self.annotations_by_name[an]
            anno_text = anno_obj.write_anno_text(widget_data)
            anno_block = '%s@@@%s%s@@@%s' % (a, ad, anno_text, ad)
            mod_text_parts.append(anno_block)
            mod_text_parts.append(t)
        module_text = ''.join(mod_text_parts)
        return module_text


class CommentStripper(PfscModuleStringAwareScanner):

    def __init__(self):
        super().__init__()
        self.stripped_text = ''

    def state_0(self, c, i):
        next_state = None
        if c == "#":
            next_state = 'inside_comment'
        else:
            self.stripped_text += c
            if self.planned_next_state == 'd3':
                self.stripped_text += '""'
            elif self.planned_next_state == 's3':
                self.stripped_text += "''"
        return next_state, None

    def state_inside_comment(self, c, i):
        next_state = None
        if c == '\n':
            # Comment ends.
            # We keep the \n char in the output so that line numbering
            # is not altered by the comment stripping operation.
            self.stripped_text += c
            next_state = 0
        return next_state, None

    def state_d1(self, c, i):
        self.stripped_text += c
        return None, None

    state_s1 = state_d1

    def state_d3(self, c, i):
        self.stripped_text += c
        if self.planned_next_state == 0:
            self.stripped_text += '""'
        return None, None

    def state_s3(self, c, i):
        self.stripped_text += c
        if self.planned_next_state == 0:
            self.stripped_text += "''"
        return None, None


def strip_comments(text):
    """
    Strip all comments (full-line, or end-line) out of a given text.
    :param text: The text to be purged of comments.
    :return: The purged text.
    """
    cs = CommentStripper()
    cs.scan(text)
    return cs.stripped_text


def parse_module_text(text, base_line_num=0):
    """
    Parse a .pfsc module.
    :param text: The text of a .pfsc module.
    :param base_line_num: optional integer by which to shift line numbers
        recorded by entities in the module as their place of definition
    :return: (Lark Tree instance, BlockChunker instance)
    """
    # Simplify anno blocks.
    bc = BlockChunker(text, base_line_num=base_line_num)
    mtext = bc.get_modified_text()
    # Strip out all comments.
    mmtext = strip_comments(mtext)
    # Now parse, and return.
    try:
        tree = pfsc_parser.parse(mmtext)
    except LarkError as e:
        # Parsing error.
        # Restore original line numbers in error message.
        parse_msg = re.sub(r'at line (\d+)', lambda m: ('at line %s' % bc.map_line_num_to_orig(int(m.group(1)))), str(e))
        raise PfscExcep(parse_msg, PECode.PARSING_ERROR)
    return tree, bc


class PendingClone(PfscObj):
    """
    Represents an intention to make a clone of a node or subdeduc.
    """

    def __init__(self, orig_libpath, local_name):
        PfscObj.__init__(self)
        self.orig_libpath = orig_libpath
        self.local_name = local_name

    def add_as_content(self, owner):
        owner.add_pending_clone(self)

    def make_clone(self, owner):
        orig_obj, _ = owner.getFromAncestor(
            self.orig_libpath,
            missing_obj_descrip=f'cloned in {owner.name}'
        )
        if isinstance(orig_obj, Node):
            # Asking the node to write its label causes it to resolve any
            # nodelinks therein, populating its `self.relpathResolutions`
            # accordingly, which will then be copied into the clone.
            orig_obj.buildDashgraph()
        clone = orig_obj.makeClone(name=self.local_name)
        clone.textRange = self.textRange
        return clone


class PfscAssignment(PfscObj):

    def __init__(self, lhs, rhs, module=None):
        PfscObj.__init__(self)
        self.parent = module
        self.name = lhs
        self.lhs = lhs
        self.rhs = rhs

    def __str__(self):
        return "%s := %s" % (self.lhs, self.rhs)

    def get_rhs(self):
        return self.rhs

    def add_as_content(self, owner):
        owner[self.lhs] = self.rhs


class PfscDeducPreamble:

    def __init__(self, name, targets, rdefs):
        self.name = name
        self.targets = targets
        self.rdefs = rdefs


class PfscRelpath:

    def __init__(self, num_dots, libpath):
        self.num_dots = num_dots
        self.libpath = libpath

    def __str__(self):
        return '.'*self.num_dots + self.libpath

    def resolve(self, home_path):
        """
        Resolve this relative path to an absolute one, given the absolute path
        of the module in which this relative one was invoked.
        @param home_path: the aboslute libpath of the module in which this was invoked
        @return: the absolute libpath to which this relative one resolves
        """
        # First dot means "this module", second dot means "the module above this one", and so on.
        # So the number of segments to be chopped is one less than the number of leading dots.
        chop_count = self.num_dots - 1
        assert chop_count >= 0
        home_parts = home_path.split('.')
        if chop_count > len(home_parts):
            msg = 'Malformed relative path: %s attempts to go above top of hierarchy.' % self
            raise PfscExcep(msg, PECode.MALFORMED_LIBPATH)
        # Subtlety: unfortunately slicing up to "negative 0" doesn't get you the whole list, so...
        keep_parts = home_parts[:-chop_count] if chop_count > 0 else home_parts[:]
        # The extension, i.e. the part that comes after the leading dots, may be empty.
        # But if it's not...
        if self.libpath:
            # ...then append it.
            keep_parts.append(self.libpath)
        # Now can join, to make the full absolute libpath.
        abspath = '.'.join(keep_parts)
        return abspath


class CachePolicy:
    """
    Enum class for ways of using the module cache.

    NEVER: Do not use the cache. Reload the module.
    ALWAYS: If the module is in the cache, use it. Don't worry about timestamps.
    TIME: Base use of the cache on timestamps. Let t_m be the modification time of the module on disk.
          Let t_r be the "read time" for the cached module (i.e. the time that it was read off disk).
          If t_m is later than t_r (i.e. the module has been modified since the last time it was
          read), then reload the module from disk; else, use the cache.
    """
    NEVER=0
    ALWAYS=1
    TIME=2


class PendingImport:
    """
    Represents an import that is pending, i.e. has not yet been resolved.
    """
    PLAIN_IMPORT_FORMAT = 0
    FROM_IMPORT_FORMAT = 1

    def __init__(self, home_module, format,
                 src_modpath, object_names=None, local_path=None):
        """
        :param home_module: the PfscModule where the import happened
        :param format: one of PLAIN_IMPORT_FORMAT, FROM_IMPORT_FORMAT, indicating
            the format of the import statement
        :param src_modpath: the libpath of the module named as the source in
            the import statement
        :param object_names: for FROM imports, the name or names (str or list of
            str) of the imported object or objects inside of the source module,
            or "*" if importing all from there
        :param local_path: dotted path or name under which the imported object
            (last imported object, if several) is to be stored in the home module
        """
        self.home_module = home_module
        self.format = format
        self.src_modpath = src_modpath
        self.object_names = object_names
        self.local_path = local_path
        self.homepath = self.home_module.libpath
        self._src_version = None

    @property
    def src_version(self):
        if self._src_version is None:
            self._src_version = self.get_desired_version_for_target(self.src_modpath)
        return self._src_version

    def is_external_at_wip(self):
        """
        Say whether this is an external import (the source module belongs to a
        different repo than the one where the import happened) of a module
        taken @WIP version.
        """
        return (
            get_repo_part(self.src_modpath) != get_repo_part(self.homepath)
            and self.src_version == pfsc.constants.WIP_TAG
        )

    def get_desired_version_for_target(self, targetpath):
        """
        :param targetpath: The libpath of the target object.
        :return: the version at which we wish to take the repo to which the
          named target belongs.
        """
        extra_msg = f' Required for import in module `{self.homepath}`.'
        return self.home_module.getRequiredVersionOfObject(targetpath, extra_err_msg=extra_msg)

    def resolve(self, cache=None, prog_mon=None, load_only=False):
        """
        Resolve this import, and store the result in the "home module," i.e.
        the module where this import statement occurred.
        """
        if cache is None:
            cache = {}
        if self.format == self.PLAIN_IMPORT_FORMAT:
            return self.resolve_plainimport(cache=cache, prog_mon=prog_mon, load_only=load_only)
        elif self.format == self.FROM_IMPORT_FORMAT:
            return self.resolve_fromimport(cache=cache, prog_mon=prog_mon, load_only=load_only)

    def resolve_plainimport(self, cache=None, prog_mon=None, load_only=False):
        """
        Carry out (delayed) resolution of a PLAIN-IMPORT.
        """
        if cache is None:
            cache = {}
        modpath = self.src_modpath
        if modpath == self.homepath:
            msg = 'Module %s is attempting to import itself.' % self.homepath
            raise PfscExcep(msg, PECode.CYCLIC_IMPORT_ERROR)
        version = self.src_version
        module = load_module(
            modpath, version=version, fail_gracefully=False,
            caching=CachePolicy.TIME, cache=cache
        )
        if not load_only:
            self.home_module[self.local_path] = module
        # Depth-first resolution:
        return module.resolve(cache=cache, prog_mon=prog_mon, load_only=load_only)

    def resolve_fromimport(self, cache=None, prog_mon=None, load_only=False):
        """
        Carry out (delayed) resolution of a FROM-IMPORT.
        """
        lrt = 0
        if cache is None:
            cache = {}
        modpath = self.src_modpath
        version = self.src_version

        # Now we have the module libpath and version from which we are attempting to import something.
        # What we're allowed to do depends on whether the modpath we've constructed is the
        # same as that of this module, or different.
        # Usually it will be different, and then we have these permissions:
        may_import_all = True
        may_search_within_module = True

        if modpath == self.homepath:
            # The modpaths will be the same in the special case where we are attempting to
            # import a submodule via a relative path.
            # For example, if the module a.b.c.d features the import statement
            #     from . import e
            # where a.b.c.d.e is a submodule of a.b.c.d, then this case arises.
            # In this case, submodules are the _only_ thing we can try to import.
            may_import_all = False
            may_search_within_module = False
            src_module = None
        else:
            # In all other cases, the modpath points to something other than this module.
            # We can now attempt to build it, in case it points to a module (receiving None if it does not).
            src_module = load_module(
                modpath, version=version, fail_gracefully=True,
                caching=CachePolicy.TIME, cache=cache
            )
            if src_module:
                # Depth-first resolution:
                lrt = src_module.resolve(cache=cache, prog_mon=prog_mon, load_only=load_only)

        object_names = self.object_names
        # Next behavior depends on whether we wanted to import "all", or named individual object(s).
        if object_names == "*":
            if not may_import_all:
                # Currently the only time when importing all is prohibited is when we are
                # trying to import from self.
                msg = 'Module %s is attempting to import * from itself.' % self.homepath
                raise PfscExcep(msg, PECode.CYCLIC_IMPORT_ERROR)
            # Importing "all".
            # In this case, the modpath must point to an actual module, or else it is an error.
            if src_module is None:
                msg = 'Attempting to import * from non-existent module: %s' % modpath
                raise PfscExcep(msg, PECode.MODULE_DOES_NOT_EXIST)
            if not load_only:
                all_names = src_module.listAllItems()
                for name in all_names:
                    self.home_module[name] = src_module[name]
        else:
            # Importing individual name(s).
            N = len(object_names)
            requested_local_name = self.local_path
            for i, object_name in enumerate(object_names):
                # Set up the local name.
                local_name = requested_local_name if requested_local_name and i == N - 1 else object_name
                # Initialize imported object to None, so we can check for success.
                obj = None
                # Construct the full path to the object, and compute the longest initial segment
                # of it that points to a module.
                full_object_path = modpath + '.' + object_name
                object_modpath = get_modpath(full_object_path, version=version)
                # If the object_modpath equals the libpath of the module we're in, this is a cyclic import error.
                if object_modpath == self.homepath:
                    if full_object_path == self.homepath:
                        msg = f'Module {self.homepath} attempts to import itself from its ancestor.'
                    else:
                        msg = f'Module {self.homepath} attempts to import from within itself.'
                    raise PfscExcep(msg, PECode.CYCLIC_IMPORT_ERROR)
                # The first attempt is to find the name in the source module, if any.
                if src_module and may_search_within_module:
                    obj = src_module.get(object_name)
                # If that failed, try to import a submodule.
                if obj is None:
                    obj = load_module(
                        full_object_path, version=version, fail_gracefully=True,
                        caching=CachePolicy.TIME, cache=cache
                    )
                    if obj:
                        # Depth-first resolution:
                        lrt = obj.resolve(cache=cache, prog_mon=prog_mon, load_only=load_only)
                # If that failed too, it's an error.
                if obj is None:
                    msg = 'Could not import %s from %s' % (object_name, modpath)
                    raise PfscExcep(msg, PECode.MODULE_DOES_NOT_CONTAIN_OBJECT)
                    # Otherwise, record the object.
                elif not load_only:
                    self.home_module[local_name] = obj

        return lrt


class ModuleLoader(PfscJsonTransformer):

    def __init__(
            self, modpath, bc,
            version=pfsc.constants.WIP_TAG, existing_module=None,
            history=None, caching=CachePolicy.TIME,
            dependencies=None, read_time=None, do_imports=True
    ):
        """
        :param modpath: The libpath of this module
        :param bc: The BlockChunker that performed the first chunking pass on this module's text
        :param version: The version being loaded
        :param existing_module: optional existing `PfscModule` instance to be extended
        :param history: a list of libpaths we have already imported; helps detect cyclic import errors
        :param caching: set the cache policy.
        :param dependencies: optionally pass a dict mapping repopaths to required versions. If provided,
          these will override what we would have determined by checking dependencies declared in the repo root module.
        :param read_time: Unix time stamp for when the file was read from disk
        :param do_imports: Set False if you don't actually want to perform imports. May be useful for testing.
        """
        # Since we are subclassing Transformer, and since our grammar has a nonterminal
        # named `module` (namely, the start symbol for our grammar), we use `self._module`
        # to store the PfscModule object we are building.
        self.modpath = modpath
        self.version = version
        self._module = existing_module or PfscModule(
            modpath, version=version, given_dependencies=dependencies,
            read_time=read_time
        )

        # For delayed resolution, we dot NOT want our `PfscJsonTransformer`
        # superclass to do any resolving of `Libpath` instances. Therefore
        # set `scope` to `None`.
        scope = None
        super().__init__(scope=scope)

        self.bc = bc
        self._module.setBlockChunker(bc)
        self.do_imports = do_imports
        self.caching = caching
        self.history = history

    def fromimport(self, items):
        """
        Process line of the form:
            fromimport : "from" (relpath|libpath) "import" (STAR|identlist ("as" IDENTIFIER)?)
        """
        if self.do_imports:
            src_modpath = items[0]
            is_relative = isinstance(src_modpath, PfscRelpath)
            if is_relative:
                src_modpath = src_modpath.resolve(self.modpath)
            object_names = items[1]
            requested_local_name = items[2] if len(items) == 3 else None
            pi = PendingImport(
                self._module, PendingImport.FROM_IMPORT_FORMAT,
                src_modpath, object_names=object_names, local_path=requested_local_name
            )
            self._module.add_pending_import(pi)

    def plainimport(self, items):
        if self.do_imports:
            src_modpath = items[0]
            # Are we using a relative libpath or absolute one?
            is_relative = isinstance(src_modpath, PfscRelpath)
            if is_relative:
                src_modpath = src_modpath.resolve(self.modpath)
                # In this case the user _must_ provide an "as" clause.
                if len(items) < 2:
                    msg = 'Plain import with relative libpath failed to provide "as" clause.'
                    raise PfscExcep(msg, PECode.PLAIN_RELATIVE_IMPORT_MISSING_LOCAL_NAME)
                local_path = items[1]
            else:
                # In this case an "as" clause is optional.
                local_path = items[1] if len(items) == 2 else src_modpath
            pi = PendingImport(
                self._module, PendingImport.PLAIN_IMPORT_FORMAT,
                src_modpath, local_path=local_path
            )
            self._module.add_pending_import(pi)

    @staticmethod
    def ban_duplicates(names_encountered, next_name):
        """
        Raise an appropriate exception in case of duplicate definition.
        Otherwise, add name to set.

        :param names_encountered: Set of names encountered so far, within a
                                  context, such as a Node or Deduc defn.
        :param next_name: The next name to be considered. Should be a Lark Token,
                          from the original parsing process. This is because we want
                          to know the position where it occurred.
        :return: nothing
        :raises: PfscExcep

        :side-effect: the name will be added to the set, unless an exception is raised.
        """
        if next_name in names_encountered:
            msg = "Duplicate definition of %s at line %s, column %s" % (
                next_name, next_name.line, next_name.column
            )
            raise PfscExcep(msg, PECode.DUPLICATE_DEFINITION_IN_PFSC_MODULE)
        else:
            names_encountered.add(next_name)

    def set_first_line(self, obj, postchunk_lineno):
        """
        Tell an object the line number on which it begins.
        :param obj: the object whose line number is to be recorded. Must have a `setTextRange` method.
        :param postchunk_lineno: the line number where we "think" this object's definition begins,
            in the post-chunking universe. In other words, this is the line number that can be read
            off of the `line` attribute of a token occuring in the line in question. We will use our
            BlockChunker to restore this to the _actual_ line number in the original module text, and
            that is the number that will be recorded.
        :return: the _actual_ line number, as adjusted by the BlockChunker
        """
        actual_lineno = self.bc.map_line_num_to_orig(postchunk_lineno)
        obj.setTextRange(actual_lineno, None, None, None)
        return actual_lineno

    def module(self, items):
        # In our handlers for top-level nonterminals (deduc, anno, etc.), we
        # are already recording the item in the module, so there is nothing
        # left to do here.
        return self._module

    def anno(self, items):
        name = items[0]
        targets = items[1] if len(items) == 2 else []
        text = self.bc.anno_lookup[name]
        pa = Annotation(name, targets, text, self._module)
        # Add to module now. We do this here in this method so that objects
        # defined later in the same module can refer to this one. Furthermore,
        # we do it before the call to cascade libpaths so that relative libpaths
        # being resolved in widgets defined in this annotation can refer to this
        # annotation itself.
        self._module[name] = pa
        self.bc.add_annotation(pa)
        self.set_first_line(pa, name.line)
        # Ask the Annotation to build itself. This means it parses the pfsc-flavored markdown, builds widgets etc.
        pa.build()
        # Now that it has built its widgets, we can cascade and resolve libpaths.
        pa.cascadeLibpaths()
        return pa

    def deduc(self, items):
        preamble, contents = items
        ded = Deduction(preamble.name, preamble.targets, preamble.rdefs, module=self._module)
        self.set_first_line(ded, preamble.name.line)
        self._module[ded.name] = ded
        for item in contents:
            item.add_as_content(ded)
        ded.cascadeLibpaths()
        return ded

    def subdeduc(self, items):
        name, contents = items
        subdeduc = SubDeduc(name)
        self.set_first_line(subdeduc, name.line)
        for item in contents:
            item.add_as_content(subdeduc)
        return subdeduc

    def defn(self, items):
        name, lhs, rhs = items
        defn = PfscDefn(name, lhs, rhs, module=self._module)
        # Add to module now, so later defs can reference.
        self._module[name] = defn
        defn.cascadeLibpaths()
        return defn

    def basicnode(self, items):
        type_, name, contents = items
        node = node_factory(type_, name)
        for item in contents:
            item.add_as_content(node)
        self.set_first_line(node, name.line)
        return node

    def suppnode(self, items):
        name = items[0]
        contents = items[-1]
        alternate_lps = items[1] if len(items) == 3 else []
        node = Supp(name)
        node.set_alternate_lps(alternate_lps)
        for item in contents:
            item.add_as_content(node)
        self.set_first_line(node, name.line)
        return node

    def wolognode(self, items):
        type_, name, contents = items
        node = node_factory(type_, name)
        node.set_wolog(True)
        for item in contents:
            item.add_as_content(node)
        self.set_first_line(node, name.line)
        return node

    def flsenode(self, items):
        name = items[0]
        contents = items[-1]
        contra = items[1] if len(items) == 3 else []
        node = Flse(name)
        node.set_contra(contra)
        for item in contents:
            item.add_as_content(node)
        self.set_first_line(node, name.line)
        return node

    # This is the first non-terminal where we've wanted to know the line num on
    # which it was defined, but don't have any `Token` instances to consult for
    # that. So we need Lark's `meta` arg to be passed.
    @v_args(meta=True)
    def clone(self, items, meta):
        libpath = items[0]
        local_name = items[1] if len(items) == 2 else None
        pc = PendingClone(libpath, local_name)
        self.set_first_line(pc, meta.line)
        return pc

    def deducpreamble(self, items):
        name = items[0]
        targets = []
        rdefs = []
        n = len(items)
        for i in range(int((n-1)/2)):
            prep, paths = items[2*i+1:2*i+3]
            if prep == "of": targets = paths
            elif prep == "with": rdefs = paths
        return PfscDeducPreamble(name, targets, rdefs)

    def deduccontents(self, items):
        return items

    def nodecontents(self, items):
        return items

    def targets(self, items):
        return items

    def relpath(self, items):
        num_dots = len(items[0])
        libpath = items[1] if len(items) == 2 else ''
        return PfscRelpath(num_dots, libpath)

    def identlist(self, items):
        return items

    def libpath(self, items):
        return '.'.join(items)

    def assignment(self, items):
        lhs, rhs = items[:2]
        pa = PfscAssignment(lhs, rhs, module=self._module)
        return pa

    def tla(self, items):
        """
        "tla" = "top-level assignment". We use this syntactic distinction
        to let us know when we need to add an assignment to the module.
        """
        pa = items[0]
        self._module[pa.name] = pa
        pa.cascadeLibpaths()
        return pa


def make_timestamp_for_module():
    return datetime.datetime.now().timestamp()


class TimestampedText:

    def __init__(self, read_time, text):
        """
        @param read_time: a Unix timestamp for the time at which the text was read off disk.
        @param text: the text that was read
        """
        self.read_time = read_time
        self.text = text


def remove_modules_from_disk_cache(modpaths, version=pfsc.constants.WIP_TAG):
    """
    Purge any pickle files that may be present on disk, for the named modules.

    :param modpaths: iterable of module libpaths (strings)
    :param version: the version at which these module pickle files should be purged
    """
    for modpath in modpaths:
        path_info = PathInfo(modpath)
        pickle_path = path_info.get_pickle_path(version=version)
        if pickle_path.exists():
            # Double check:
            if pickle_path.suffix == pfsc.constants.PICKLE_EXT:
                pickle_path.unlink()


def remove_all_pickles_from_dir(dir_path, recursive=False):
    """
    Purge any and all pickle files in (and optionally under) a directory.

    :param dir_path: pathlib.Path
    :param recursive: set True if you want to recurse on all nested directories
    """
    util.conditionally_unlink_files(
        dir_path,
        lambda path: path.suffix == pfsc.constants.PICKLE_EXT,
        recursive=recursive,
        rmdirs=False
    )


def remove_all_pickles_for_repo(repopath, version=pfsc.constants.WIP_TAG):
    """
    Purge any and all pickle files for a given repo, at a given version.
    """
    ri = get_repo_info(repopath)
    dir_path = ri.get_build_dir(version=version, cache_dir=True)
    if dir_path.exists():
        remove_all_pickles_from_dir(dir_path, recursive=True)


def pickle_module(module, path_info=None):
    """
    Save a pickled representation of a `PfscModule` at its correct location in
    the build directory for the repo and version to which the module belongs.

    :param module: the PfscModule
    :param path_info: optional PathInfo object for this module. If not given,
        we construct it here.
    :return: the path of the pickle file
    """
    if path_info is None:
        path_info = PathInfo(module.libpath)
    pickle_path = path_info.get_pickle_path(version=module.version)
    if not pickle_path.parent.exists():
        pickle_path.parent.mkdir(parents=True)
    with open(pickle_path, 'wb') as f:
        pickle.dump(module, f, pickle.HIGHEST_PROTOCOL)
    return pickle_path


def unpickle_module(path_spec, version):
    """
    Try to load a module from its pickle file.

    :param path_spec: libpath (str), or PathInfo object for the module
    :param version: the version at which you are trying to load the module
    :return: PfscModule, or None if pickle file doesn't exist or is malformed
    """
    module = None
    path_info = path_spec if isinstance(path_spec, PathInfo) else PathInfo(path_spec)
    pickle_path = path_info.get_pickle_path(version=version)
    if pickle_path.exists():
        with open(pickle_path, 'rb') as f:
            try:
                module = pickle.load(f)
            except Exception as e:
                # TODO: log the exception
                pass
    return module


class LoadingResult:

    def __init__(self, rebuilt):
        self.rebuilt = rebuilt


def load_module(
        path_spec, version=pfsc.constants.WIP_TAG,
        text=None, fail_gracefully=False, history=None,
        caching=CachePolicy.TIME, cache=None,
        current_builds=None, loading_results=None,
):
    """
    This is how you get a PfscModule object, i.e. an internal representation of a pfsc module.
    You can call it directly, or you can call it through a PathInfo object's own `load_module` method.
    If you do call it directly, you can pass a mere modpath string, or a PathInfo object built on such a string.

    @param path_spec: Either a string, being the libpath of the module you want to load, or else
                      a PathInfo object built on such a libpath. If you pass the string, we're
                      just going to start by constructing the PathInfo on it.

    @param version: The version of this module that you wish to load.

    @param text: If you happen to already have the text of the module, you can pass it here.
                 Note that when you provide the text we will definitely bypass the cache _for this module_;
                 meanwhile, cache use for any imports taking place _within_ the module will be controlled as
                 usual; see below.

                 The text can be passed either as a string, or as an instance of TimestampedText.
                 If the former, then we will _not_ cache the PfscModule object we construct on the given
                 text (because we cannot give it a timestamp). If the latter, we will cache it.

    @param fail_gracefully: What should happen if the libpath fails to point to a .pfsc file? If you just
                            want us to return `None`, then set this to `True`. Else we will raise an
                            appropriate `PfscException`.

    @param history: This is used for detecting cyclic import errors. Generally, you don't have to use this
                    yourself; it is already used appropriately by the system.

    @param caching: Cache policy controlling how we use the on-disk cache (i.e. pickle files).
        See `CachePolicy` enum class. Note that we always use the in-mem cache, when it's a hit.

    @param cache: The in-mem module cache.

    @param current_builds: Like the `history` kwarg, this is here to catch cyclic errors, in this case
        cyclic builds. These *shouldn't* arise anyway, but we have this kwarg as an extra safety net,
        to prevent infinite recursion. This pertains only to the special case where an rst module is loaded
        @WIP, and is *not* being loaded from cache. In a build scenario, this should only happen when the
        module belongs to another repo than the one(s) already being built.

    @param loading_results: Optional dict in which information about the loading process will be recorded.
        Info will be recorded as an instance of the `LoadingResult` class, under the
        tail-versioned modpath as key, but not if that key is already present in the dict.

    @return: If successful, the loaded PfscModule instance is returned. If unsuccessful, then behavior depends
             on the `fail_gracefully` kwarg. If that is `True`, we will return `None`; otherwise, nothing will
             be returned, as a `PfscException` will be raised instead.
    """
    path_info = path_spec if isinstance(path_spec, PathInfo) else PathInfo(path_spec)

    modpath = path_info.libpath
    repopath = get_repo_part(modpath)
    verspath = f'{modpath}@{version}'

    if version == pfsc.constants.WIP_TAG and not have_repo_permission(
        ActionType.READ, repopath, pfsc.constants.WIP_TAG
    ):
        msg = f'Insufficient permission to load `{modpath}` at WIP.'
        raise PfscExcep(msg, PECode.INADEQUATE_PERMISSIONS)

    def fail(msg=None, pe_code=None):
        if fail_gracefully:
            return None
        else:
            msg = msg or f'Could not find source code for module `{modpath}` at version `{version}`.'
            if pe_code is None:
                pe_code = PECode.MODULE_HAS_NO_CONTENTS
            e = PfscExcep(msg, pe_code)
            e.extra_data({
                'repopath': repopath,
                'version': version,
                'modpath': modpath,
            })
            raise e

    if cache is None:
        cache = {}

    # Decide whether we will rebuild the module (i.e. *not* use the cache).
    will_rebuild = False
    text_given = (text is not None)
    mem_cache_hit = (verspath in cache)
    never_use_disk_cache = (caching == CachePolicy.NEVER)
    if text_given:
        # If module text was passed, this is always to be used to construct the module.
        will_rebuild = True
    elif mem_cache_hit:
        # The cache policy only controls how we use the on-disk cache (i.e.
        # pickle files). If we have a cache hit in the in-mem cache, we always use it.
        will_rebuild = False
    elif never_use_disk_cache:
        # At this point, it's at best an on-disk cache hit. If we're told not
        # to use that, then we should rebuild.
        will_rebuild = True
    else:
        # In this case, we *want* to use the on-disk cache, provided it is both
        # *possible* (module is available) and *appropriate* (i.e. time stamps
        # check out, if using time-based policy).
        unpickled_module = unpickle_module(path_info, version)
        if not unpickled_module:
            will_rebuild = True
        elif caching == CachePolicy.ALWAYS:
            will_rebuild = False
        # Otherwise, the module was found in the on-disk cache, and we're using time-based policy.
        else:
            assert caching == CachePolicy.TIME
            # We need to compare the modification time to the read time.
            t_r = unpickled_module.read_time
            t_m = path_info.get_src_file_modification_time(version=version)
            if t_m is None:
                return fail()
            # We should rebuild the module if it has been modified since it was last read.
            if isinstance(t_m, int):
                # At one time (I think I was using a MacBook Pro, in summer 2019, with up-to-date
                # OS -- not sure which Python version, probably 3.5 - 3.7?), I seem to have observed
                # that the Unix mtime timestamps were being truncated to next lowest integer.
                # It's also possible I was working on an Ubuntu server at the time.
                # At any rate, now (230624, macOS 10.14.6, Python 3.8) they seem to be floats, with
                # microsecond accuracy. *In case* we get an integer, we give the mod time a +1
                # boost, to be on the safe side. ("Safe" meaning: err on the side of reloading
                # the module even if unnecessary.)
                # I note that coarse filesystem time resolution is a phenomenon acknowledged e.g. by Sphinx:
                # https://github.com/sphinx-doc/sphinx/blob/d3c91f951255c6729a53e38c895ddc0af036b5b9/sphinx/builders/__init__.py#L498-L501
                t_m += 1
            will_rebuild = t_m >= t_r
        # If it was an on-disk cache hit, and we're going to use it, then elevate
        # it to the in-mem cache.
        if unpickled_module and not will_rebuild:
            cache[verspath] = unpickled_module

    if isinstance(loading_results, dict) and verspath not in loading_results:
        loading_results[verspath] = LoadingResult(will_rebuild)

    if not will_rebuild:
        module = cache[verspath]
        return module
    else:
        # Only when we have to rebuild does history become relevant, so we deal with it now.
        if history is None:
            history = []
        # If the module we're trying to build is already in the history of imports that have
        # led us to this point, then we raise a cyclic import error.
        if modpath in history:
            msg = 'Cyclic import error: \n    ' + (' -->\n    '.join(history + [modpath]))
            raise PfscExcep(msg, PECode.CYCLIC_IMPORT_ERROR)
        # Otherwise, add this modpath to the history.
        history.append(modpath)

        is_rst = path_info.is_rst_file(version=version)
        if is_rst:
            if version != pfsc.constants.WIP_TAG:
                msg = (
                    f'Cannot build rst module `{modpath}` at version `{version}`.'
                    ' May need to build its repo at that version first.'
                )
                fail(msg=msg, pe_code=PECode.VERSION_NOT_BUILT_YET)

            if current_builds is None:
                current_builds = set()
            if repopath in current_builds:
                msg = f'Cyclic build error. Trying to build rst module {modpath}@WIP'
                msg += ' while already building:\n'
                for rp in current_builds:
                    msg += f'  {rp}\n'
                fail(msg=msg, pe_code=PECode.CYCLIC_IMPORT_ERROR)
            current_builds.add(repopath)

            from pfsc.build import Builder
            b = Builder(
                repopath, version=pfsc.constants.WIP_TAG,
                current_builds=current_builds
            )
            b.build(
                force_reread_rst_paths=[path_info.abs_fs_path_to_file],
                no_sphinx_write=True
            )
            module = b.module_cache[verspath]
        else:
            # We need an instance of TimestampedText.
            if text_given:
                # Text was given.
                if not isinstance(text, TimestampedText):
                    # If text was provided but is not already an instance of TimestampedText, then it must be a string.
                    assert isinstance(text, str)
                    # We set `None` as timestamp, to ensure the module will not be cached.
                    ts_text = TimestampedText(None, text)
                else:
                    ts_text = text
            else:
                # To be on the safe side, make timestamp just _before_ performing the read operation.
                # (This is "safe" in the sense that the read operation looks older, so we will be more
                # likely to rebuild in the future, i.e. to catch updates.)
                read_time = make_timestamp_for_module()
                try:
                    module_contents = path_info.read_module(version=version)
                except FileNotFoundError:
                    return fail()
                ts_text = TimestampedText(read_time, module_contents)
            # Construct a PfscModule.
            module = build_module_from_text(
                ts_text.text, modpath, version=version, history=history,
                caching=caching, read_time=ts_text.read_time
            )

        # If everything is working correctly, then now is the time to "forget" this
        # module, i.e. to erase its record from the history list; it should be the last record.
        to_forget = history.pop()
        assert to_forget == modpath

        if module.read_time is not None:
            cache[verspath] = module
            pickle_module(module, path_info)

        return module


def build_module_from_text(
        text, modpath,
        version=pfsc.constants.WIP_TAG, existing_module=None,
        history=None, caching=CachePolicy.TIME,
        dependencies=None, read_time=None,
        base_line_num=0
):
    """
    Build a module, given its text, and its libpath.
    :param text: (str) the text of the module
    :param modpath: (str) the libpath of the module
    :param version: (str) the version being built
    :param existing_module: optional existing `PfscModule` instance to be extended
    :param history: (list) optional history of modules built; useful for
      detecting cyclic import errors
    :param caching: the desired CachePolicy
    :param dependencies: optionally pass a dict mapping repopaths to required versions.
    :param read_time: Unix time stamp for when the file was read from disk
    :param base_line_num: optional integer by which to shift line numbers
        recorded by entities in the module as their place of definition
    :return: the PfscModule instance constructed
    """
    tree, bc = parse_module_text(text, base_line_num=base_line_num)
    loader = ModuleLoader(
        modpath, bc,
        version=version, existing_module=existing_module,
        history=history, caching=caching, dependencies=dependencies,
        read_time=read_time
    )
    try:
        module = loader.transform(tree)
    except VisitError as v:
        # Lark traps our PfscExceps, re-raising them within a VisitError. We want to see the PfscExcep.
        raise v.orig_exc from v
    return module

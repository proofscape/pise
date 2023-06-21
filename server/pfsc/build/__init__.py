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
Utilities for building Proofscape modules.

Building may be thought of as analogous to compiling and linking a C++ project. Here, the
"compiling" means writing dashgraph and annotation files, while the "linking"
means updating targeting/expansion relationships in the graph database.

More specifically, building a module entails the following operations:

    - The module is parsed and an internal representation is formed.
      In particular this means that any syntactic errors will be discovered and an
      exception will be raised.

    - The `manifest.json` file for the repo to which the module belongs is updated.

    - For every deduction defined in the module, a dashgraph is built and written to disk
      in the installation's BUILD_ROOT as a .dg.json file. This also means that any semantic
      errors in deduction definitions will be caught, and exceptions raised.

    - For every annotation defined in the module, the notes page data are built and written to
      disk, again under the BUILD_ROOT, as a pair of .anno.html and .anno.json files.

    - The graph database in which all targeting relations are indexed is updated.

Any module can be built either recursively or not. To build recursively means to
act on the module itself as well as any and all submodules (and submodules thereof, and so on).
To build non-recursively means to act on only the module itself.
"""

import os, json, math, re
from collections import deque
from datetime import datetime
import logging
import pathlib
import pickle
import traceback

from sphinx.cmd import make_mode
from sphinx.application import Sphinx
from sphinx.errors import SphinxError
from sphinx.util.console import strip_colors
from sphinx.util.docutils import patch_docutils, docutils_namespace

from pfsc.build.mii import ModuleIndexInfo
from pfsc.build.manifest import (
    build_manifest_tree_from_dict,
    build_manifest_from_dict,
    load_manifest,
    Manifest,
    ManifestTreeNode
)
from pfsc.excep import PfscExcep, PECode
from pfsc.build.lib.libpath import PathInfo
from pfsc.build.products import get_dashgraph_dir_and_filename, get_annotation_dir_and_filenames
from pfsc.build.repo import RepoInfo, checkout, get_repo_info
from pfsc.build.versions import version_string_is_valid
from pfsc.gdb import get_graph_writer, get_graph_reader, building_in_gdb
from pfsc.constants import IndexType
from pfsc.lang.modules import (
    CachePolicy, load_module, PfscDefn, PfscAssignment,
    cache_module,
)
from pfsc.lang.annotations import Annotation
from pfsc.lang.deductions import Deduction, Node, GhostNode
from pfsc.lang.widgets import GoalWidget

import pfsc.util
import pfsc.constants


def build_module(
        target, recursive=False, caching=CachePolicy.TIME,
        verbose=False, progress=None,
        clean_sphinx=False
):
    """
    Build a module.

    :param target: Either the libpath (str) of the module that is to be built,
                      or a Builder instance representing that module.
    :param recursive: as for the Builder class.
    :param caching: as for the Builder class.
    :param verbose: as for the Builder class.
    :param progress: as for the Builder class.
    :param clean_sphinx: as for the Builder class.
    :return: the Builder instance that built the module.
    """
    if not isinstance(target, Builder):
        b = Builder(
            target, version=pfsc.constants.WIP_TAG, recursive=recursive,
            caching=caching, verbose=verbose, progress=progress,
            clean_sphinx=clean_sphinx
        )
    else:
        b = target
    if verbose:
        profile_build_write_index(b)
    else:
        b.build_write_index()
    return b


def build_release(
        repopath, version, caching=CachePolicy.TIME, verbose=False,
        progress=None, clean_sphinx=False
):
    """
    Build a release.

    :param repopath: the libpath of the repo for which you wish to build a release.
    :param version: the number of the release to be built.
    :param caching: as for the Builder class.
    :param verbose: as for the Builder class.
    :param progress: as for the Builder class.
    :param clean_sphinx: as for the Builder class.
    :return: the Builder instance we use to do the build.
    """
    b = Builder(
        repopath, version=version, recursive=True, caching=caching,
        verbose=verbose, progress=progress, clean_sphinx=clean_sphinx
    )
    if verbose:
        profile_build_write_index(b)
    else:
        b.build_write_index()
    return b


def profile_build_write_index(builder):
    import cProfile
    with cProfile.Profile() as pr:
        builder.build_write_index()
    import pstats, io
    s = io.StringIO()
    # sortby = pstats.SortKey.TIME
    sortby = pstats.SortKey.CUMULATIVE
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)

    # Use these, to focus on indexing:
    #ps.print_stats('pfsc/build/__init__.py', 12)
    #ps.print_stats('ix0')

    # Use this instead, to just see the 50 slowest things:
    ps.print_stats(50)

    r = s.getvalue()

    # printing to stdout is fine for local unit testing, and working with the OCA
    print(r)

    # When working with the MCA, long-running tasks tend to be carried out by
    # the RQ worker, so you need to uncomment these lines to see what's going
    # on in there:
    #from pfsc.methods import log_within_rq
    #log_within_rq(r)


class BuildMonitor:
    """
    Manages monitoring of the build process.

    This class is designed to be flexible, and support different usage patterns.

    In some cases, your build process may be "distributed," in the sense that
    many different bits of code are responsible for advancing the process, one
    piece at a time. In such cases, it is handy to use this class's
    `begin_phase()`, `inc_count()`, and `set_message()` methods.

    In other cases, you may have a centralized process that keeps track of its
    own progress. Then it may be easier to use this class's `set_state()`
    method directly.
    """

    def __init__(self, external):
        """
        :param external: A function to which progress information is to be passed when available.
                         Should accept four args: (op_code, cur_count, max_count, message)
        """
        self.external = external

        self.op_code = None
        # cur_count may be integer or float
        self.cur_count = 0
        # max_count must be an integer
        self.max_count = 100
        self.message = ''

    def pub(self):
        """
        Publish the current state to the external monitor.
        """
        # In some build scenarios, we don't use an external monitor, so we
        # do have to check here.
        if self.external:
            c = min(self.max_count, math.floor(self.cur_count))
            self.external(self.op_code, c, self.max_count, self.message)

    def set_message(self, message):
        """
        Set the message.
        """
        self.message = message
        self.pub()

    def begin_phase(self, max_count, message):
        """
        Start a new phase. Indicate the total number of steps it will involve,
        and set an initial message.
        """
        self.cur_count = 0
        self.max_count = max_count
        self.message = message
        self.pub()

    def inc_count(self, f=1.0):
        """
        Increase the current count. Say by how much, or default to 1.

        f: int or float
        """
        self.cur_count += f
        self.pub()

    def set_count(self, f):
        """
        Set the current count directly, instead of by differential.

        f: int or float
        """
        self.cur_count = f
        self.pub()

    def set_state(self, cur_count, max_count, message):
        """
        Set the complete state.
        """
        self.cur_count = cur_count
        self.max_count = max_count
        self.message = message
        self.pub()

    def declare_complete(self):
        """
        Call this method when the entire build process is complete.
        """
        self.message = 'Done'
        self.cur_count = self.max_count
        self.pub()


class SphinxBuildLogStream:
    """
    Allows us to monitor the build progress of the Sphinx build (if any)
    contained within a repo build.

    Construct a logging.StreamHandler with this as stream, and then add the
    handler to the logger named 'sphinx.sphinx.util'.

    Note that Sphinx prepends the namespace prefix 'sphinx.' onto the usual
    `__name__`. This therefore is the logger defined in sphinx/util/__init__.py.

    See also sphinx/util/logging.py for the `SphinxLoggerAdapter` class that wraps
    Python's built-in logger.

    See also `sphinx.util.status_iterator()` for the code that generates the
    log messages that do contain percentages.

    """

    def __init__(self, monitor):
        """
        monitor: an instance of the BuildMonitor class
        """
        self.monitor = monitor
        self.percentage_pattern = re.compile(r'\[\s*(\d+)%\]')
        # We use a "real" counter for steps where Sphinx gives a percentage.
        self.last_real_count = 0
        # We use a "fake" counter for sequences of steps that have no percentage.
        self.last_fake_count = 0
        # These are depicted as being out of a fake denominator, which is
        # always at least a certain way away.
        # Example: with basic denom of 10, and min remainder of 3, the fractions
        # will go: 1/10, 2/10, ..., 7/10, 8/11, 9/12, 10/13, ...
        self.min_fake_rem = 3
        self.basic_fake_denom = 10

    def write(self, record):
        message = strip_colors(record.strip())
        if message == 'done':
            # Sphinx ends each of its steps with a 'done' message.
            # We're not going to display these.
            pass
        else:
            parts = self.percentage_pattern.split(message)
            if len(parts) == 3:
                # It's a percentage message
                try:
                    count = int(parts[1])
                except ValueError:
                    count = self.last_real_count
                denom = 100
                self.last_real_count = count
                message = parts[0] + parts[2].strip()
                # Reset fake counter, for next fake phase (if any)
                self.last_fake_count = 0
            else:
                # It's a step that has no percentage
                count = self.last_fake_count + 1
                self.last_fake_count = count
                denom = max(self.basic_fake_denom, count + self.min_fake_rem)
            message = 'Sphinx: ' + message
            self.monitor.set_state(count, denom, message)

    def flush(self):
        """
        Just implementing the `stream` interface so that an instance of this
        class can be passed when constructing a `logging.StreamHandler()`.
        """
        pass


class OriginInjectionVisitor:

    def __init__(self, lp2origin):
        """
        :param lp2origin: dict mapping libpaths to origins
        """
        self.lp2origin = lp2origin
        self.graph_reader = get_graph_reader()

    @staticmethod
    def takes_origin(item):
        return isinstance(item, (Deduction, Node, GoalWidget))

    def __call__(self, item):
        if self.takes_origin(item):
            lp = item.getLibpath()
            if lp in self.lp2origin:
                item.setOrigin(self.lp2origin[lp])

        if isinstance(item, GhostNode):
            real_obj = item.realObj()
            if not real_obj.getOrigin():
                realpath = real_obj.getLibpath()
                if realpath in self.lp2origin:
                    real_obj.setOrigin(self.lp2origin[realpath])
                else:
                    # This case arises if e.g. the repo X being built cites a theorem
                    # in repo Y. Since repo Y is not being built at this time, we
                    # have no origin data for its nodes, and need to consult the GDB.
                    #
                    # What we're trying to do here is ensure that the `realOrigin`
                    # property in the dashgraph for a GhostNode (see the
                    # `pfsc.lang.deductions.GhostNode.buildDashgraph()` method) has
                    # a value.
                    #
                    # This only matters if we want goal boxes to be able to appear
                    # on ghost nodes for cited theorems and lemmas. For now at least,
                    # we think we do want this. E.g. it lets the user know, without
                    # opening a theorem, whether they have already studied it and
                    # put a checkmark on it.
                    #
                    # TODO: Could we make this more efficient by noting all ghost
                    #  nodes to external repos during the build process, and then
                    #  making a single query to the GDB for all the origin info at once?
                    vers = real_obj.getVersion()
                    label = real_obj.get_index_type()
                    origins = self.graph_reader.get_origins({label: [realpath]}, vers)
                    if realpath in origins:
                        real_obj.setOrigin(origins[realpath])


class Builder:
    """
    Builds Proofscape modules.
    """

    def __init__(
            self, modpath, version=pfsc.constants.WIP_TAG, recursive=False,
            caching=CachePolicy.TIME, verbose=False, progress=None,
            clean_sphinx=False
    ):
        """
        :param modpath: libpath of the module to be built.
        :param version: the version we are building. Must be either "WIP", meaning we want
          to build our work-in-progress, or else a valid release tag `vM.m.p`.
        :param recursive: If False, build only the module itself; if True, also build all submodules.
        :param caching: set the cache policy
        :param verbose: control printing
        :param progress: a function to which to pass progress updates
        :param clean_sphinx: set True to `make clean` the Sphinx doc before
            building it, if a part of the build
        """
        self.module_path = modpath
        self.version = version
        self.path_parts = self.module_path.split('.')
        self.recursive = recursive
        self.caching = caching
        self.verbose = verbose
        self.clean_sphinx = clean_sphinx
        self.monitor = BuildMonitor(progress)
        self.graph_writer = get_graph_writer()
        self.build_in_gdb = building_in_gdb()

        if not version_string_is_valid(version, allow_WIP=True):
            raise PfscExcep(f'Invalid version string: {version}', PECode.MALFORMED_VERSION_TAG)

        # We set a couple of arbitrary counts for progress monitoring.
        self.prog_count_per_module = 100
        self.prog_count_for_parsing = 10

        # Keep track of whether we have built yet.
        self.have_built = False
        self.timestamp = None

        # We need to know in which repo this module lives.
        self.repo_info = get_repo_info(self.module_path)
        self.commit_hash = self.repo_info.get_current_commit_hash()
        # It's useful to know if we're building a (whole) repo.
        self.build_target_is_repo = self.repo_info.libpath == self.module_path
        self.build_target_is_whole_repo = self.build_target_is_repo and self.recursive

        # Sanity check: release builds can only be on whole repos:
        if self.is_release_build() and not self.build_target_is_whole_repo:
            msg = 'Release builds can only be on whole repos.'
            raise PfscExcep(msg, PECode.ATTEMPTED_RELEASE_BUILD_ON_SUB_REPO)

        # Prepare build data stores.

        # We keep track of any directories scanned that turn out not to contain a single pfsc module.
        # TODO: Report to the user after the build operation completes.
        #   Any such dirs ought to be noted in a .pfscignore file (_and_ we need to support that!)
        self.useless_dirs = []

        self.module_cache = {}

        # a ModuleIndexInfo
        self.mii = ModuleIndexInfo(
            self.monitor,
            self.module_path,
            self.version,
            self.commit_hash,
            recursive=self.recursive
        )
        # a lookup of Deductions by their libpaths
        self.deductions = {}
        # a lookup of Annotations by their libpaths
        self.annotations = {}
        # a lookup of PfscModules by their libpaths
        self.modules = {}
        # a manifest
        path = self.repo_info.libpath
        self.repo_node = ManifestTreeNode(path, type="MODULE", name=path)
        self.manifest = Manifest(self.repo_node)
        node = self.repo_node
        for segment in self.path_parts[3:]:
            path += '.' + segment
            child_node = ManifestTreeNode(path, type="MODULE", name=segment)
            node.add_child(child_node)
            node = child_node
        self.root_node = node
        
        # A "scan job" is a pair (PfscModule, ManifestTreeNode), representing
        # a module that we have loaded from disk, but have not yet analyzed its
        # contents.
        self.scan_jobs = deque()

        # A place to store a copy of the dependencies declared by the repo being built:
        self.repo_dependencies = {}

        # Set up items to be skipped.
        # For now we automatically skip any directory or file beginning with a dot '.'
        # TODO:
        # In the future, we may want to allow repos to define a `.pfscignore` file where they can specify more skip-paths.
        # Format:
        #   path-within-repo points to dict optionally defining 'dirs' and 'files' keys, under each of which is
        #   a list of dirnames or filenames to be skipped under this path.
        self.skip_items = {
        }

    def is_release_build(self):
        return self.version != pfsc.constants.WIP_TAG

    def building_a_release_of(self):
        """
        Report the repopath of the repo of which we are building a release, or
        None if we are not doing a release build.
        """
        return self.repo_info.libpath if self.is_release_build() else None

    def has_sphinx_doc(self):
        p = pathlib.Path(self.repo_info.abs_fs_path_to_dir) / 'index.rst'
        return p.exists()

    def raise_missing_change_log_excep(self):
        msg = f'Repo `{self.module_path}` failed to declare a change log for release `{self.version}`'
        msg += ', which is a major version increment.'
        raise PfscExcep(msg, PECode.MISSING_REPO_CHANGE_LOG)

    def build_write_index(self, force=False):
        """
        Conduct the entire process of three phrases: (1) Build, (2) Write, and (3) Index
        :param force: True to force rebuild
        :return: nothing
        """
        self.build(force=force)
        self.update_index()
        self.write_all()
        self.monitor.declare_complete()

    def build(self, force=False):
        """
        Here is where we do the actual building operations.
        :param force: Must set True if you want to build again, after already building once.
        :return: nothing
        """
        # Build only if have not yet built, or if forcing.
        if force or not self.have_built:
            self.monitor.set_message('Starting...')
            with checkout(self.repo_info, self.version):
                # Set signal visible below this frame by inspecting the stack.
                building_a_release_of = self.building_a_release_of()

                self.check_root_declarations()
                self.mii.compute_mm_closure(self.graph_writer.reader)

                # Sphinx build.
                # If you want a Sphinx build to take place, you have to have an `index.rst` file
                # in the repo root dir.
                if self.build_target_is_whole_repo and self.has_sphinx_doc() and not self.build_in_gdb:
                    self.build_sphinx_doc(do_clean=self.clean_sphinx)
                else:
                    self.reading_phase()
                    self.resolving_phase()

                self.have_built = True

    def reading_phase(self):
        """
        Form modules by READING pfsc files, but do not yet RESOLVE them.

        In cases where we're going to do a Sphinx build, this function
        should be carried out after the Sphinx build has
        finished its READING phase, but before it begins its RESOLVING phase.
        """
        # Note: It is critical that this method be invoked only within the
        # context provided by the `checkout()` context manager, which is invoked
        # in our `build()` method. In particular,
        # it was not until we checked out the intended version that we could construct
        # our PathInfo object, and examine the filesystem structures representing our root module.
        # It's easy to think some of this stuff may belong in our __init__ method, but for
        # this reason it has to wait until now.
        path_info = PathInfo(self.module_path)

        pickle_path = self.repo_info.get_modules_pickle_path(version=self.version)

        if os.path.exists(pickle_path):
            with open(pickle_path, 'rb') as f:
                try:
                    self.module_cache = pickle.load(f)
                except EOFError:
                    # If the pickle file is malformed, just give up. It's the
                    # same as if we didn't have one at all. We'll overwrite it
                    # with a good one later.
                    pass

        if self.verbose:
            print(f"Building {self.module_path}@{self.version}...")
        self.walk(path_info.abs_fs_path_to_dir)

        build_dir = self.repo_info.get_build_dir(version=self.version)
        os.makedirs(build_dir, exist_ok=True)
        with open(pickle_path, 'wb') as f:
            # Store only the pfsc modules (not rst modules) belonging to
            # *this* repo, and which the `walk()` has determined *still* belong
            # to this repo.
            local_pfsc_mod_cache = {
                verspath: cm for verspath, cm in self.module_cache.items()
                if cm.module.libpath in self.modules
            }
            pickle.dump(local_pfsc_mod_cache, f, pickle.HIGHEST_PROTOCOL)

    def resolving_phase(self):
        """
        RESOLVE the pfsc modules formed in the READING phase.
        """
        modules = [cm.module for cm in self.module_cache.values()]
        for module in modules:
            module.resolve()

        while self.scan_jobs:
            module, manifest_node = self.scan_jobs.popleft()
            self.scan_pfsc_module(module, manifest_node)

        self.mii.cut_add_validate()
        self.mii.here_elsewhere_nowhere()
        self.mii.compute_origins(self.graph_writer.reader)
        self.inject_origins()
        self.timestamp = datetime.now()
        self.manifest.set_build_info(self.module_path, self.version, self.repo_info.git_hash, self.timestamp, self.recursive)
        self.merge_manifests()

    def build_sphinx_doc(self, do_clean=False, force_all=False, filenames=None):
        """
        do_clean: Set True to do a `make clean` before building
        force_all: write all files, instead of just for new or changed source
            files. Same as `-a` siwtch to commandline Sphinx.
        filenames: try to build only these output files. Same as passing filenames
            to commandline Sphinx.

        See:
            https://www.sphinx-doc.org/en/master/man/sphinx-build.html#cmdoption-sphinx-build-a
            https://www.sphinx-doc.org/en/master/man/sphinx-build.html#synopsis
        """
        sourcedir = self.repo_info.abs_fs_path_to_dir
        confdir = sourcedir
        outputdir = self.repo_info.get_sphinx_build_dir(version=self.version)
        doctreedir = os.path.join(outputdir, '.doctrees')

        p = pathlib.Path(outputdir)
        p.mkdir(parents=True, exist_ok=True)

        if do_clean:
            args = ['clean', sourcedir, outputdir]
            make_mode.run_make_mode(args)

        # Conf overrides
        required_extensions = [
            'sphinx_math_dollar',
            # We use the separate extension for the lexers:
            'sphinx_proofscape',
            # We use the local extension for everything else:
            'pfsc.sphinx.sphinx_proofscape',
        ]
        confoverrides = {
            'pfsc_repopath': self.repo_info.libpath,
            'pfsc_repovers': self.version,
            'html_theme': 'furo',
            # Note: this does not extend, but overwrites completely any 'extensions' list
            # the user may have specified in their conf.py. This is fine for now since we
            # are not yet supporting any way of adding extensions to the Proofscape build
            # system.
            'extensions': required_extensions,
        }

        stream = SphinxBuildLogStream(self.monitor)
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger('sphinx.sphinx.util')
        logger.addHandler(handler)

        def env_updated_handler(app, env):
            """
            This handler is called when Sphinx has finished its READING phase,
            but has not yet begun its RESOLVING phase. We do our own READING
            and RESOLVING, and we also in a sense begin the Sphinx RESOLVING
            phase, by resolving all pfsc modules formed from rst files.
            """
            self.reading_phase()

            pfsc_env = env.proofscape
            for rst_module in pfsc_env.pfsc_modules.values():
                cache_module(rst_module, self.module_cache)

            self.resolving_phase()

        try:
            with patch_docutils(confdir), docutils_namespace():
                app = Sphinx(sourcedir, confdir, outputdir, doctreedir,
                             'html', confoverrides=confoverrides)
                app.connect('env-updated', env_updated_handler)
                app.build(force_all=force_all, filenames=filenames)
        except (SphinxError, Exception) as e:
            traceback.print_exc()
            raise PfscExcep(f'Sphinx error: {e}', PECode.SPHINX_ERROR) from e

        self.manifest.set_has_sphinx_doc()

    def inject_origins(self):
        visitor = OriginInjectionVisitor(self.mii.origins)
        for module in self.modules.values():
            module.recursiveItemVisit(visitor)

    def merge_manifests(self):
        if not self.build_target_is_whole_repo:
            # If we are not rebuilding an entire repo recursively, then we need
            # to check for an existing manifest, and merge with it.
            try:
                manifest = load_manifest(self.repo_info.libpath, version=self.version)
            except PfscExcep as e:
                if e.code() != PECode.MISSING_MANIFEST:
                    raise e from None
            else:
                manifest.merge(self.manifest)
                self.manifest = manifest

    def check_root_declarations(self):
        """
        This is where we load and perform checks on any of the things that are
        to be declared in repo root modules, like the change log and the
        dependencies.
        """
        is_release = self.is_release_build()
        is_major_inc = self.mii.is_major_version_increment()
        is_major_zero = self.mii.is_major_zero()
        repopath = self.repo_info.libpath
        pi = PathInfo(repopath)
        module_has_contents = pi.get_pfsc_fs_path() is not None
        if not module_has_contents:
            # If it's a release build for a major version increment, there must be a
            # repo root module (so that it can declare a change log).
            if is_release and is_major_inc:
                self.raise_missing_change_log_excep()
            else:
                return
        module = load_module(
            self.repo_info.libpath, version=pfsc.constants.WIP_TAG,
            fail_gracefully=False, caching=self.caching, cache=self.module_cache
        )
        # Change log
        cl = module.getAsgnValue(pfsc.constants.CHANGE_LOG_LHS)
        if is_release and not is_major_zero:
            if is_major_inc:
                # In this case a change log is required.
                if cl is None:
                    self.raise_missing_change_log_excep()
            else:
                # In this case print a warning if a change log _is_ defined.
                if cl is not None:
                    msg = f'Repo `{repopath}` defines a change log for release `{self.version}`'
                    msg += ', but this is not a major version increment.'
                    # This used to be an exception, as follows:
                    #   raise PfscExcep(msg, PECode.DISALLOWED_REPO_CHANGE_LOG)
                    # but for now we are just printing a warning. We'll see how it goes.
                    print(f'WARNING: {msg}')
        self.mii.set_change_log(cl or {})
        # Dependencies
        deps = module.getAsgnValue(pfsc.constants.DEPENDENCIES_LHS, default={})
        self.repo_dependencies = deps
        if is_release:
            if pfsc.constants.WIP_TAG in deps.values():
                msg = f'Repo `{repopath}` imports from one or more other repos at WIP,'
                msg += ' but this is not allowed in a release build.'
                raise PfscExcep(msg, PECode.NO_WIP_IMPORTS_IN_NUMBERED_RELEASES)

    def walk(self, root_fs_path):
        """
        When building recursively, this method manages the walking of the filesystem hierarchy.
        :param root_fs_path: The filesystem path to the directory we want to walk.
        :return: nothing
        """
        # We will build a list of "jobs," being pairs (modpath, tree_node), to be passed to
        # our `read_pfsc_module` method.
        jobs = []
        walk_list = list(os.walk(root_fs_path))
        self.monitor.begin_phase(len(walk_list), 'Scanning...')
        for P, D, F in walk_list:
            self.monitor.inc_count()

            # FIXME: really should check first whether we're under a skip dir, and skip immediately.
            #   Wasting lots of cycles walking all through .git!
            #   Might be worth just implementing our own custom "walk" iterator.
            # For now, just a simple check that the path does not contain a hidden dir or file:
            if P.find(os.sep+'.') >= 0: continue

            # What is the ID of the manifest tree node representing the directory we are now in?
            internal_fs_path = os.path.relpath(P, root_fs_path)
            if internal_fs_path == '.':
                parent_node_id = self.module_path
            else:
                parent_node_id = self.module_path + '.' + internal_fs_path.replace(os.sep, '.')
            # Check for a parent node with this ID.
            parent_node = self.manifest.get(parent_node_id)
            # If None, this is because we are in or under a directory that was marked as to be skipped.
            if parent_node is None: continue

            # We'll build a list of child nodes to be added to the parent node.
            child_nodes = []

            # Check for lists of items to be skipped.
            skip_dirs = []
            skip_files = []
            if internal_fs_path in self.skip_items:
                skip_info = self.skip_items[internal_fs_path]
                skip_dirs = skip_info.get('dirs', [])
                skip_files = skip_info.get('files', [])

            # Scan the nested directories.
            for d in D:
                # Skip?
                if d[0] == '.' or d in skip_dirs: continue
                # If not skipping, we add a node to the tree for this directory.
                dir_id = parent_node_id + '.' + d
                # TODO: allow user to define name of directory.
                #   This could be done by defining the name within a special file in the directory.
                #   Maybe just define a "dirname" string in the __.pfsc file in the dir?
                dir_node = ManifestTreeNode(dir_id, type="MODULE", name=d)
                # Record this directory's tree node as one of the parent's children
                child_nodes.append(dir_node)
                self.mii.add_submodule(dir_id, parent_node_id)

            # Now scan the files under this path.
            # FIXME: it would be cool if we could do local depths for _all_ deducs defined in a whole directory.
            # Right now we only do this within each module. The result is that if you define expansions in a
            # separate module from literature deducs, say, then the expans are all shown at level 0, instead of
            # being nicely nested under the deducs they target, as we'd like.
            num_pfsc_modules_in_this_dir = 0
            for f in F:
                # Skip?
                if f[0] == '.' or f in skip_files: continue
                # Is it a pfsc module?
                if f[-5:] == '.pfsc':
                    name = f[:-5]
                    if (pathlib.Path(P) / f'{name}.rst').exists():
                        msg = (
                            f'Module name `{name}` occurs with both .pfsc and'
                            f' .rst extension in dir `{P}`.'
                        )
                        raise PfscExcep(msg, PECode.MODULE_NAME_USED_WITH_MULTIPLE_EXTENSIONS)
                    # Reconstruct the module's abs libpath.
                    modpath = parent_node_id if name == "__" else parent_node_id + '.' + name
                    if name == "__":
                        # Contents of "dunder module" will be added directly to the parent node.
                        mod_node = parent_node
                    else:
                        # For "terminal modules", add a manifest node to represent the module itself.
                        mod_node = ManifestTreeNode(modpath, type="MODULE", name=name)
                        child_nodes.append(mod_node)
                        self.mii.add_submodule(modpath, parent_node_id)
                    # Record the job.
                    jobs.append((modpath, mod_node))
                    # Count it.
                    num_pfsc_modules_in_this_dir += 1

            # Sort child nodes, then add to parent node.
            child_nodes.sort(key=lambda n: pfsc.util.NumberedName(n.data.get('name', '')))
            for n in child_nodes:
                parent_node.add_child(n)

            # Mark dir as useless if there were no pfsc modules in it.
            if num_pfsc_modules_in_this_dir == 0: self.useless_dirs.append(P)

        self.monitor.begin_phase(self.prog_count_per_module * len(jobs), 'Building...')
        for modpath, mod_node in jobs:
            self.read_pfsc_module(modpath, mod_node)

    def read_pfsc_module(self, module_path, manifest_node):
        """
        Read a proofscape module, and record it as a scan job.

        :param module_path: the libpath of the module to be processed
        :param manifest_node: a ManifestTreeNode representing this module, and to which
                              nodes representing its items are to be added
        """
        self.monitor.set_message('Reading %s...' % module_path)
        if self.verbose: print("  ", module_path)

        try:
            # Tricky couple of steps here: We are currently working in a context where the
            # desired version of the repo being built has been checked out. So we can get
            # the module source code we need from the WIP version, i.e. from the lib dir;
            # in fact, we can _only_ get it from there, since it's not yet available in the
            # build dir, as we are right now in the process of making that very build. So
            # we must pass WIP as version to the load_module function.
            module = load_module(
                module_path, version=pfsc.constants.WIP_TAG,
                fail_gracefully=False, caching=CachePolicy.TIME, cache=self.module_cache
            )
            # On the other hand, if we are doing a release build, then this module actually
            # represents a non-WIP version. We must set the represented version now, so that
            # as we add kNodes and kRelns to self.mii, they record the right version numbers.
            module.setRepresentedVersion(self.version)
        except PfscExcep as e:
            if e.code() == PECode.PARSING_ERROR:
                msg = 'Error while parsing module `%s`.' % module_path
                msg += '\n\nDetails:\n\n%s' % e.public_msg()
                raise PfscExcep(msg, PECode.PARSING_ERROR)
            else:
                e.msg = f'While loading module `{module_path}`:\n\n' + e.msg
                raise e

        self.monitor.inc_count(self.prog_count_for_parsing)
        self.scan_jobs.append((module, manifest_node))
        self.modules[module.libpath] = module

    def scan_pfsc_module(self, module, manifest_node):
        """
        Process a single proofscape module. This means recording dashgraphs and annotations,
        adding manifest tree nodes, and recording indexing info, for the contents of this module.

        :param module: the PfscModule to be scanned
        :param manifest_node: a ManifestTreeNode representing this module, and to which
                              nodes representing its items are to be added
        """
        module_path = module.libpath
        self.monitor.set_message('Scanning %s...' % module_path)

        manifest_node.update_data({'isTerminal': module.isTerminal()})

        # Grab all the items.
        all_items = module.getNativeItemsInDefOrder(hoist_expansions=True)
        num_items = len(all_items)
        remaining_count = self.prog_count_per_module - self.prog_count_for_parsing
        prog_count_per_item = 0
        if num_items == 0:
            self.monitor.inc_count(remaining_count)
        else:
            prog_count_per_item = remaining_count / num_items

        annos = []
        defns = {}
        asgns = {}
        for name, item in all_items.items():
            if isinstance(item, Annotation):
                annos.append(item)
            elif isinstance(item, PfscDefn):
                defns[name] = item
            elif isinstance(item, Deduction):
                pass
            elif isinstance(item, PfscAssignment):
                asgns[name] = item

        # For the list of all deductions defined within the module, we do request toposort, to help us
        # list the deducs in a nice order for the tree view.
        deducs = module.getAllNativeDeductions(toposort=True, numberednames=True)

        mtns_by_name = {}

        for anno in annos:
            # Record for indexing
            self.mii.add_anno(module, anno)
            # Record the Annotation itself.
            annopath = anno.getLibpath()
            self.annotations[annopath] = anno
            # Doc refs
            # Note: It's not enough to call `anno.gather_doc_info()` here, since
            # it's not until `enrich_data()` has been called on each widget that
            # doc infos will be available. But `anno.get_anno_data()` is caching,
            # so this is not wasted effort.
            doc_info = anno.get_anno_data()['docInfo']
            self.manifest.update_doc_info(doc_info['docs'])
            # Add a tree node.
            name = anno.getName()
            mtns_by_name[name] = ManifestTreeNode(
                annopath, type="NOTES", name=name,
                modpath=module_path, sourceRow=anno.getFirstRowNum(),
                docRefs=doc_info['refs']
            )
            self.monitor.inc_count(prog_count_per_item)

        for name in defns:
            libpath = f'{module.libpath}.{name}'
            self.mii.add_generic(IndexType.DEFN, libpath, module)
            self.monitor.inc_count(prog_count_per_item)

        for name in asgns:
            libpath = f'{module.libpath}.{name}'
            self.mii.add_generic(IndexType.ASGN, libpath, module)
            self.monitor.inc_count(prog_count_per_item)

        # For each deduc in this module, we will map its libpath to its "depth within the module".
        # Depth within the module is defined as follows:
        #   Any TLD has depth 0, and so does any deduc whose target deduc lies outside this module.
        #   Any deduc E whose target deduc D is defined within this module satisfies depth(E) = depth(D) + 1.
        deduc_depth_within_module = {}

        # Iterate over the deductions defined in this module, in topo-order.
        for deduc in deducs:
            dlp = deduc.getLibpath()
            self.deductions[dlp] = deduc
            # Record deduc for indexing.
            self.mii.add_deduc(module, deduc)
            # Compute and record depth within module.
            # First get the libpath of the "target deduction", i.e. the deduc to which all the target nodes belong.
            tdlp = deduc.getTargetDeducLibpath()
            # (Because we process deducs in topo-order, it follows that tdlp is defined within this module
            #  and is not None IFF it is already a key in the depth lookup.)
            depth = 1 + deduc_depth_within_module.get(tdlp, -1)
            deduc_depth_within_module[dlp] = depth
            # Doc refs
            doc_info = deduc.gather_doc_info()
            self.manifest.update_doc_info(doc_info['docs'])
            # Add a tree node.
            name = deduc.getName()
            mtns_by_name[name] = ManifestTreeNode(
                dlp, type="CHART", name=name, modpath=module_path,
                sourceRow=deduc.getFirstRowNum(), docRefs=doc_info['refs'],
                # target deduc libpath
                tdlp=tdlp,
                # depth
                depth=depth
            )
            self.monitor.inc_count(prog_count_per_item)

        # Add the manifest tree nodes in definition order.
        for name, item in all_items.items():
            mtn = mtns_by_name.get(name)
            if mtn:
                manifest_node.add_child(mtn)

    def write_all(self):
        # Some operations during the write-phase do require that the desired version
        # of the repo be checked out. For example, the call to `module.getBuildDirAndFilename`
        # in `clear_build_dirs`. Since we still have some places in the code base where we
        # invoke Builder.build outside of Builder.write_build_index, we cannot just put a
        # single checkout context in the latter. So we keep one checkout in Builder.build,
        # and put another one here.
        with checkout(self.repo_info, self.version):
            # Set signal visible below this frame by inspecting the stack.
            building_a_release_of = self.building_a_release_of()
            # How many writes do we have to do?
            n = len(self.modules) + len(self.deductions) + len(self.annotations)
            self.monitor.begin_phase(n, 'Writing...')
            self.clear_build_dirs()
            self.write_built_modules_to_build_dir()
            self.write_manifest()
            self.write_dashgraphs()
            self.write_notespages()

    def write_manifest(self):
        d = self.manifest.build_dict()
        j = json.dumps(d, indent=4)
        if self.build_in_gdb:
            self.graph_writer.record_repo_manifest(self.repo_info.libpath, self.version, j)
        else:
            build_dir = self.repo_info.get_build_dir(version=self.version)
            manifest_json_path = self.repo_info.get_manifest_json_path(version=self.version)
            os.makedirs(build_dir, exist_ok=True)
            with open(manifest_json_path, 'w') as f:
                f.write(j)

    def write_built_modules_to_build_dir(self):
        """
        We need copies of the pfsc modules in the build dir for each built release.
        These are needed so that another repo can import them during its own build.
        They are also needed so that non-owning users can browse the source at a
        given release.
        """
        for module in self.modules.values():
            text = module.getBuiltVersion()
            if self.build_in_gdb:
                modpath = module.getLibpath()
                self.graph_writer.record_module_source(modpath, self.version, text)
            else:
                build_dir, filename = module.getBuildDirAndFilename(version=self.version)
                os.makedirs(build_dir, exist_ok=True)
                path = os.path.join(build_dir, filename)
                with open(path, 'w') as f:
                    f.write(text)
            self.monitor.inc_count()

    def clear_build_dirs(self):
        """
        Clean out the build directory for each built module. This eliminates old built
        products for any entities that used to be defined in these modules, but no
        longer are.
        """
        for module in self.modules.values():
            if self.build_in_gdb:
                modpath = module.getLibpath()
                self.graph_writer.delete_builds_under_module(modpath, self.version)
            else:
                build_dir, filename = module.getBuildDirAndFilename(version=self.version)
                if os.path.exists(build_dir):
                    for ext in [
                        'src', 'anno.html', 'anno.json', 'dg.json'
                    ]:
                        cmd = f'rm {build_dir}/*.{ext} 2> /dev/null'
                        os.system(cmd)

    def write_dashgraphs(self):
        """
        Write the dashgraphs to disk.
        """
        for deducpath, deduc in self.deductions.items():
            dashgraph = deduc.buildDashgraph()
            dg_json = json.dumps(dashgraph, indent=4)
            if self.build_in_gdb:
                self.graph_writer.record_dashgraph(deducpath, self.version, dg_json)
            else:
                dest_dir, filename = get_dashgraph_dir_and_filename(deducpath, version=self.version)
                os.makedirs(dest_dir, exist_ok=True)
                dg_json_path = os.path.join(dest_dir, filename)
                with open(dg_json_path, 'w') as f:
                    f.write(dg_json)
            self.monitor.inc_count()

    def write_notespages(self):
        """
        Write the annotations to disk.
        """
        for annopath, annotation in self.annotations.items():
            anno_html = annotation.get_escaped_html()
            anno_json = json.dumps(annotation.get_anno_data(), indent=4)
            if self.build_in_gdb:
                self.graph_writer.record_annobuild(annopath, self.version, anno_html, anno_json)
            else:
                dest_dir, html_filename, json_filename = get_annotation_dir_and_filenames(annopath, version=self.version)
                os.makedirs(dest_dir, exist_ok=True)
                anno_html_path = os.path.join(dest_dir, html_filename)
                anno_json_path = os.path.join(dest_dir, json_filename)
                with open(anno_html_path, 'w') as f:
                    f.write(anno_html)
                with open(anno_json_path, 'w') as f:
                    f.write(anno_json)
            self.monitor.inc_count()

    def update_index(self):
        """
        Update the graph database.
        """
        self.mii.setup_monitor()
        self.graph_writer.index_module(self.mii)


def index(obj, recursive=False, caching=CachePolicy.TIME):
    """
    Convenience function to accept a variety of arguments, and perform just the indexing operation
    on the appropriate module.

    :param obj: Can be a variety of argument types:

                libpath (str): we construct a Builder on this libpath, and ask it to index.
                RepoInfo: we construct a Builder on this RepoInfo's libpath, and ask it to index.
                Builder: we ask it to index.

    :param recursive: same as in Builder.__init__; we just forward it.
    :param caching: same as in Builder.__init__; we just forward it.

    :return: The report from the indexing operation.
    """
    if isinstance(obj, str):
        b = Builder(obj, recursive=recursive, caching=caching)
    elif isinstance(obj, RepoInfo):
        b = Builder(obj.libpath, recursive=recursive, caching=caching)
    elif isinstance(obj, Builder):
        b = obj
    else:
        raise PfscExcep("Unrecognized type.")
    # Build.
    b.build()
    # And index.
    return b.update_index()

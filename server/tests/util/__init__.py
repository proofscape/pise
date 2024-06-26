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

import os
import re
import tempfile

import pfsc.constants
from pfsc import make_app
from pfsc.constants import TEST_RESOURCE_DIR
from pfsc.build import build_repo
from pfsc.build.versions import VersionTag
from pfsc.build.repo import get_repo_info
from pfsc.gdb import get_graph_writer
from pfsc.lang.modules import build_module_from_text
from config import LocalDevConfig, ConfigName

REPO_SRC_DIR = os.path.join(TEST_RESOURCE_DIR, 'repo')


class Repo:

    def __init__(self, root_dir, user, proj, vers_dirs, tag_names):
        self.user = user
        self.proj = proj
        self.libpath = f'test.{user}.{proj}'
        self.src_dir = os.path.join(root_dir, user, proj)
        self.vers_dirs = vers_dirs
        self.tag_names = tag_names
        self.deps = None

    def lookup_dependencies(self):
        if self.deps is None:
            deps = {}
            for vers, tag in zip(self.vers_dirs, self.tag_names):
                root_module_path = os.path.join(self.src_dir, vers, "__.pfsc")
                if os.path.exists(root_module_path):
                    with open(root_module_path) as f:
                        text = f.read()
                    mod = build_module_from_text(text, self.libpath, version=tag)
                    d = mod.get('dependencies', lazy_load=False)
                    if d:
                        deps[tag] = d
            self.deps = deps


def gather_repo_info():
    # Discover user/proj/version by scanning directories.
    from pfsc_test_modules import get_repo_src_dir_path
    extra_repos = get_repo_src_dir_path()
    REPOS = []
    for root_dir in [REPO_SRC_DIR, extra_repos]:
        USERS = sorted(os.listdir(root_dir))
        for user in USERS:
            if user[0] == '.': continue  # skip hidden dirs
            for proj in sorted(os.listdir(os.path.join(root_dir, user))):
                if proj[0] == '.': continue
                SRC = os.path.join(root_dir, user, proj)
                # Before we implemented multi-versioning support, in our test repos
                # we used version dirs with names of the form `v\d+`.
                # Post-multi-versioning, we use names that look like full version
                # tags, vM.m.p. For backwards-compatibility, we accept both formats.
                vers_dirs = [d for d in os.listdir(SRC) if re.match(r'v\d+', d)]
                if 'v0' in vers_dirs:
                    vers_dirs.sort(key=lambda d: int(d[1:]))
                else:
                    vers_dirs.sort(key=lambda d: VersionTag(d))
                # For tag names, pad pre-multi-versioning names with zeros.
                tag_names = [f'{vers}.0.0' if vers.find('.') < 0 else vers for vers in vers_dirs]
                REPOS.append(Repo(root_dir, user, proj, vers_dirs, tag_names))
    return REPOS


def make_repos(config=LocalDevConfig, verbose=True, cautious=False, only=None):
    """
    Set up for unit tests by building all the "test" repos.
    :param config: a Config subclass. This is needed for the PFSC_LIB_ROOT.
    :param verbose: control verbosity
    :param cautious: control whether we ask before rebuilding existing repos
    :param only: if None, simply make *all* the test repos. If not None,
        should be a list of ordered pairs (user, proj) giving those user/project
        pairs that are the only repos you want to make.
    :return: nothing
    """
    # Ensure the `test` folder exists.
    LIB_TEST_DIR = os.path.join(config.PFSC_LIB_ROOT, 'test')
    if not os.path.exists(LIB_TEST_DIR):
        os.makedirs(LIB_TEST_DIR)
    REPOS = gather_repo_info()
    for repo in REPOS:
        user_proj_pair = (repo.user, repo.proj)
        if only is not None and user_proj_pair not in only:
            continue
        if verbose: print("Repo test.%s.%s..." % user_proj_pair)
        USER_DIR = os.path.join(LIB_TEST_DIR, repo.user)
        PROJ_DIR = os.path.join(USER_DIR, repo.proj)
        # Make user dir if does not exist already.
        if not os.path.exists(USER_DIR):
            os.makedirs(USER_DIR)
        # If the project directory already exists...
        if os.path.exists(PROJ_DIR):
            if verbose: print("    already exists!")
            # Are we being cautious?
            # If so, ask before deleting and rebuilding; else just go ahead and delete and rebuild.
            if cautious:
                del_existing = input('    Delete existing test repo under %s and rebuild? (Y/n)> ' % PROJ_DIR) == "Y"
            else:
                del_existing = True
            if del_existing:
                if verbose: print('    Rebuilding...')
                cmd = 'rm -rf %s' % PROJ_DIR
                DRY = False
                if DRY:
                    print(cmd)
                else:
                    print('    '+cmd)
                    os.system(cmd)
            else:
                if verbose: print('    Doing nothing...')
                continue
        # Otherwise we proceed to make the repo.
        with tempfile.TemporaryDirectory() as TMP_DIR:
            GIT_DIR = None
            for vers, tag_name in zip(repo.vers_dirs, repo.tag_names):
                # Make tmp copy of version dir.
                if verbose: print("    Make version %s..." % vers)
                SRC_VERS = os.path.join(repo.src_dir, vers)
                assert os.path.isdir(SRC_VERS)
                TMP_VERS = os.path.join(TMP_DIR, vers)
                os.system('cp -r %s %s' % (SRC_VERS, TMP_VERS))
                # Initialize git repo if first version, or else copy existing .git dir from previous version.
                if GIT_DIR is None:
                    # Initialize
                    if verbose: print("      Initializing git repo...")
                    os.system(f'cd {TMP_VERS}; git init > /dev/null 2>&1')
                else:
                    # Take .git dir from last repo.
                    os.system('mv %s %s' % (GIT_DIR, TMP_VERS))
                # Commit all, and make a version branch.
                os.system(f'cd {TMP_VERS}; git add . > /dev/null 2>&1')
                os.system(f'cd {TMP_VERS}; git commit -m "{vers}" > /dev/null 2>&1')
                os.system(f'cd {TMP_VERS}; git branch {vers} > /dev/null 2>&1')
                # Tag it.
                os.system(f'cd {TMP_VERS}; git tag {tag_name} > /dev/null 2>&1')
                # Set the GIT_DIR.
                GIT_DIR = os.path.join(TMP_VERS, '.git')
            # Leave on initial version branch.
            init_vers = repo.vers_dirs[0]
            if verbose: print("    Resetting to initial version %s." % init_vers)
            os.system(f'cd {TMP_VERS}; git checkout {init_vers} > /dev/null 2>&1')
            if verbose: print("    Done.")
            # Move into place.
            os.system('mv %s %s' % (TMP_VERS, PROJ_DIR))


def get_basic_repos():
    """
    List the test repos that are meant to be built as a basic setup for all
    unit tests.

    Some repos are not meant to be pre-built; others are designed to have
    errors. For this reason, not all test repos are meant to be built before
    running unit tests.

    :return: list of Repo instances
    """
    return list(filter(
        lambda repo: not (
            repo.libpath.startswith('test.foo.') or
            repo.libpath.startswith('test.moo.err') or
            repo.libpath.startswith('test.spx.err') or
            repo.libpath in [
                #'test.hist.lit',
            ]
        ),
        gather_repo_info()
    ))


def clear_indexing(repopath=None, version=None):
    """
    if repopath is None:
        Clear all indexing under `test` host segment.
    else:
        if version is None:
            Clear indexing for repopath@WIP
        else:
            Clear indexing for repopath@version
    """
    app = make_app(ConfigName.LOCALDEV)
    with app.app_context():
        gw = get_graph_writer()
        if repopath is None:
            gw.clear_test_indexing()
        else:
            version = version or pfsc.constants.WIP_TAG
            gw.delete_full_build_at_version(repopath, version)


def build_big(verbose=True):
    clear_indexing()
    repopath = 'test.hist.lit'
    version = 'v0.0.0'
    app = make_app(ConfigName.LOCALDEV)
    # Ensure we are able to build:
    app.config["PERSONAL_SERVER_MODE"] = True
    with app.app_context():
        build_repo(
            repopath, version=version, verbose=verbose, make_clean=True
        )


def clear_and_build_releases_with_deps_depth_first(
        app, repopath_version_pairs, verbose=False
):
    """
    Clear index of test junk, then build the desired repos at the desired
    versions, first building any dependencies, in topological order ("depth first").

    :param app: Flask app
    :param repopath_version_pairs: iterable of pairs (repopath, version)
    """
    repos_built = set()
    clear_indexing()
    repos = get_basic_repos()
    repos = {r.libpath: r for r in repos}
    stack = []

    def request_version(rp, vers):
        repo = repos[rp]
        i0 = repo.tag_names.index(vers)
        versions = reversed(repo.tag_names[:i0 + 1])
        stack.extend([(rp, v) for v in versions])

    with app.app_context():
        for repopath, version in repopath_version_pairs:
            request_version(repopath, version)
            while stack:
                rp, vers = stack.pop()
                if f'{rp}@{vers}' in repos_built:
                    continue
                repo = repos[rp]
                repo.lookup_dependencies()
                deps = repo.deps[vers].rhs if vers in repo.deps else {}
                prereqs = []
                for k, v in deps.items():
                    if f'{k}@{v}' not in repos_built:
                        prereqs.append((k, v))
                if prereqs:
                    stack.append((rp, vers))
                    for k, v in prereqs:
                        request_version(k, v)
                else:
                    verspath = f'{rp}@{vers}'
                    print(f'\nBuilding {verspath}...')
                    build_repo(rp, version=vers, verbose=verbose, make_clean=True)
                    repos_built.add(verspath)


def build_all(verbose=True):
    repos = get_basic_repos()
    app = make_app(ConfigName.LOCALDEV)
    # Ensure we are able to build:
    app.config["PERSONAL_SERVER_MODE"] = True
    repopath_version_pairs = []
    for repo in repos:
        for version in repo.tag_names:
            repopath_version_pairs.append((repo.libpath, version))
    clear_and_build_releases_with_deps_depth_first(
        app, repopath_version_pairs, verbose=verbose
    )


def get_tags_to_build_as_wip():
    return [
        ['test.moo.comment', 'v0.2.0'],
        ['test.wid.get', 'v0.2.0'],
    ]


def build_at_wip(verbose=True):
    """
    We might want at least a few test repos to be built at WIP, for testing purposes.
    """
    tags_to_build_as_wip = get_tags_to_build_as_wip()
    app = make_app(ConfigName.LOCALDEV)
    # Ensure we are able to build:
    app.config["PERSONAL_SERVER_MODE"] = True
    with app.app_context():
        for repopath, tag in tags_to_build_as_wip:
            ri = get_repo_info(repopath)
            ri.checkout(tag)
            print(f'\nBuilding {repopath}@WIP...')
            build_repo(repopath, verbose=verbose, make_clean=True)
            ri.clean()

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

import os
from pathlib import Path
from contextlib import contextmanager

from pygit2 import (
    Repository, discover_repository, GitError, GIT_STATUS_IGNORED,
    Signature,
)

import pfsc.constants
from pfsc import check_config
from pfsc.build.versions import VersionTag, VERSION_TAG_REGEX
from pfsc.excep import PfscExcep, PECode
from pfsc.util import run_cmd_in_dir


class RepoInfo:

    def __init__(self, libpath):

        # What libpath do we represent?
        self.libpath = libpath
        self.userpath = None

        # Parts of the libpath:
        self.family = None
        self.user = None
        self.project = None

        # Does the path refer to an existing directory?
        self.is_dir = None
        # If so, record the absolute filesystem path to the directory.
        self.abs_fs_path_to_dir = None
        # Also record the absolute filesystem path to the user directory.
        self.abs_fs_path_to_user_dir = None

        # If (and only if) is_dir is True, we check whether this is a git repo.
        # Does the path refer to a git repo?
        self.is_git_repo = None
        # If so, store its current commit hash.
        self.git_hash = None

        # Now check the given path, populating the info fields.
        self.check_libpath()

        self.version_tags = None
        self.version_tag_names = None

    @property
    def git_repo(self):
        """
        The pygit2 class `Repository` is not picklable.
        Therefore we do not store one as an attribute. Instead, we form one
        each time it is needed.
        This allows e.g. the `RepoLoader` handler class to be pickled by RQ,
        since it has a `RepoInfo` attribute.
        """
        if self.is_git_repo:
            return Repository(self.abs_fs_path_to_dir)
        else:
            return None

    def __repr__(self):
        fields = ['libpath', 'userpath', 'family', 'user', 'project',
                  'is_dir', 'abs_fs_path_to_dir', 'abs_fs_path_to_user_dir',
                  'is_git_repo', 'git_repo', 'git_hash']
        r = ''
        for f in fields:
            v = getattr(self, f)
            r += '%s: %s\n' % (f, v)
        return r

    def write_url(self):
        if not self.is_remote():
            msg = 'Cannot write URL for local repo %s' % self.libpath
            raise PfscExcep(msg, PECode.REPO_HAS_NO_URL)
        fmt = {
            RepoFamily.GITHUB: 'https://github.com/%(user)s/%(repo)s',
            RepoFamily.BITBUCKET: 'https://bitbucket.org/%(user)s/%(repo)s'
        }[self.family]
        url = fmt % {
            'user': self.user,
            'repo': self.project
        }
        return url

    def is_remote(self):
        return self.family in RepoFamily.remote_families

    def is_demo(self):
        return self.family == RepoFamily.DEMO

    def rebuild_libpath(self):
        return '.'.join([self.family, self.user, self.project])

    def get_shadow_repo_path(self):
        return os.path.join(
            self.abs_fs_path_to_user_dir,
            pfsc.constants.SHADOW_PREFIX + self.project
        )

    def get_default_version(self):
        """
        Determine the default version for this repo (which means the version to
        be loaded/opened if the user failed to specify a version).

        :return: full version string
        """
        vers_str = pfsc.constants.WIP_TAG
        if self.is_demo():
            # Default version is always WIP, for a demo repo.
            pass
        elif check_config("DEFAULT_REPO_VERSION_IS_LATEST_RELEASE"):
            from pfsc.gdb import get_graph_reader
            vi = get_graph_reader().get_versions_indexed(self.libpath, include_wip=False)
            if len(vi) > 0:
                vers_str = vi[-1].get('version', pfsc.constants.WIP_TAG)
        return vers_str

    def clean(self):
        # Note: This is only used by testing code (not in production), so it is
        # okay to use CLI git here.
        run_cmd_in_dir('git restore .', self.abs_fs_path_to_dir)

    def get_hash_of_ref(self, ref_name):
        """
        If a reference name resolves and points to a commit, we return the
        hex hash of that commit.

        :@param ref_name: (str) the name of the ref to be checked out
        :@raise: PfscExcep if the name does not resolve
        :@return: str
        """
        try:
            commit, ref = self.git_repo.resolve_refish(ref_name)
        except (TypeError, KeyError):
            raise PfscExcep('Unknown git reference', PECode.UNKNOWN_GIT_REF)
        return commit.hex

    def checkout(self, ref_name):
        """
        Convenience function to checkout a branch or tag.

        Note: Checking out a commit hash is not supported.

        :param ref_name: (str) the name of the ref to be checked out
        """
        try:
            commit, ref = self.git_repo.resolve_refish(ref_name)
        except (TypeError, KeyError):
            raise PfscExcep('Unknown git reference', PECode.UNKNOWN_GIT_REF)
        if ref is None:
            raise PfscExcep('Cannot checkout commit', PECode.UNKNOWN_GIT_REF)
        self.git_repo.checkout(ref)

    def checkout_tag(self, tagname):
        """
        Like `checkout`, but this time we check first to make sure the named
        tag exists.
        :param tagname: the name of the tag to be checked out
        """
        self.get_all_version_tags_in_increasing_order()
        if not tagname in self.version_tag_names:
            msg = f'Tried to check out non-existent tag `{tagname}` for repo `{self.libpath}`.'
            raise PfscExcep(msg, PECode.VERSION_TAG_DOES_NOT_EXIST)
        self.checkout(tagname)

    def is_clean(self):
        repo = self.git_repo
        return set(repo.status().values()).issubset({GIT_STATUS_IGNORED})

    def is_detached(self):
        return self.git_repo.head_is_detached

    def find_a_tag(self):
        """
        Try to find an existing tag that points to the current head.

        This is useful when in detached head state, and wanting to have a tag we
        can use to get back here, after checking out some other ref in the
        meantime.

        @return: a full ref string if found, else None
        """
        repo = self.git_repo
        commit = repo.head.peel()
        for ref in repo.references:
            if ref.startswith('refs/tags/'):
                c, r = repo.resolve_refish(ref)
                if c == commit:
                    return ref
        return None

    def get_active_branch_name(self):
        def fail():
            raise PfscExcep('Repo is in detached state.', PECode.REPO_IN_DETACHED_STATE)
        if self.is_detached():
            fail()
        repo = self.git_repo
        sh = repo.head.resolve().shorthand
        # Confirm that it's a branch:
        b = repo.lookup_branch(sh)
        if b is None:
            fail()
        return b.shorthand

    def get_current_commit_hash(self, strict=True):
        try:
            commit_hash = str(self.git_repo.head.resolve().target)
        except GitError:
            if strict:
                msg = f'Cannot get current commit hash for repo `{self.libpath}`. Have you done an initial commit yet?'
                raise PfscExcep(msg, PECode.REPO_HAS_NO_HASH)
            else:
                return None
        return commit_hash

    def get_all_version_tags_in_increasing_order(self, force=False):
        """
        :return: list of VersionTag instances, properly sorted in increasing order.
        """
        tags = self.version_tags
        if force or tags is None:
            # Note: We do need to use our VersionTag class for proper sorting,
            # since plain alphabetical order puts e.g. version 10 before version 2.
            all_tag_names = [r[10:] for r in self.git_repo.references if r.startswith('refs/tags/')]
            tags = sorted([
                VersionTag(name) for name in all_tag_names
                if VERSION_TAG_REGEX.match(name)
            ])
            self.version_tags = tags
            self.version_tag_names = [tag.get_name() for tag in tags]
        return tags

    def has_version_tag(self, tag_name):
        """
        Pass a string, e.g. 'v1.2.3', to check whether this currently exists as
        a version tag in the repo.
        """
        return tag_name in [t.name for t in self.get_all_version_tags_in_increasing_order()]

    def get_build_dir(self, version=pfsc.constants.WIP_TAG):
        build_root = check_config("PFSC_BUILD_ROOT")
        build_dir = os.path.join(
            build_root, self.family, self.user, self.project, version
        )
        return build_dir

    def get_repo_build_dir(self):
        """
        Like `get_build_dir`, but omits the version dir at the end.
        """
        build_root = check_config("PFSC_BUILD_ROOT")
        build_dir = os.path.join(
            build_root, self.family, self.user, self.project
        )
        return build_dir

    def get_user_build_dir(self):
        """
        Like `get_build_dir`, but omits the repo dir and version dir at the end.
        """
        build_root = check_config("PFSC_BUILD_ROOT")
        build_dir = os.path.join(
            build_root, self.family, self.user
        )
        return build_dir

    def get_manifest_json_path(self, version=pfsc.constants.WIP_TAG):
        build_dir = self.get_build_dir(version=version)
        return os.path.join(build_dir, 'manifest.json')

    def has_manifest_json_file(self, version=pfsc.constants.WIP_TAG):
        path = self.get_manifest_json_path(version=version)
        return os.path.exists(path)

    def get_hash_or_none(self):
        return self.git_hash

    def check_libpath(self):
        """
        Check the given libpath, populating all info fields to describe what we learn.
        """
        from pfsc.build.lib.libpath import libpathToAbsFSPath
        parts = self.libpath.split('.')
        try:
            assert len(parts) == 3
            assert parts[0] in RepoFamily.all_families
            assert len(parts[1]) > 0
            assert len(parts[2]) > 0
        except AssertionError:
            self.is_git_repo = False
            return
        self.family = parts[0]
        self.user = parts[1]
        self.project = parts[2]
        self.userpath = '.'.join(parts[:2])

        fs_path = libpathToAbsFSPath(self.libpath)
        user_fs_path = libpathToAbsFSPath(self.userpath)
        # Store these paths. They can be useful even if either directory does not exist.
        self.abs_fs_path_to_dir = fs_path
        self.abs_fs_path_to_user_dir = user_fs_path
        # Does the path name a directory?
        self.is_dir = os.path.isdir(fs_path)
        if self.is_dir:
            # We only want to call it a git repo if the given path points to
            # the root dir of the repo, not to any path properly inside it.
            # The `discover_repository()` function maps any path at or under the
            # repo root dir to the path of the repo's `.git` dir, and any other
            # path to `None`.
            dot_git_path = discover_repository(fs_path)
            # Subtle point: in a Docker image, `fs_path` may be a symlink, like
            # `/home/pfsc/proofscape/lib/...`, while `dot_git_path` will be the resolved
            # version thereof, like `/proofscape/lib/...`. So we need to call `.resolve()`
            # here. Probably should redo whole system, using resolved `Path` instances
            # throughout, instead of strings.
            if dot_git_path and Path(dot_git_path).resolve() == (Path(fs_path) / '.git').resolve():
                self.is_git_repo = True
                # When checking for current commit hash, set `strict=False` to
                # allow for the case of a brand-new repo in which not even an
                # initial commit has yet been made.
                self.git_hash = self.get_current_commit_hash(strict=False)
            else:
                self.is_git_repo = False

    def load_fs_model(self):
        if not self.is_dir:
            return []
        root_node = FilesystemNode(self.libpath, '.', self.libpath, FilesystemNode.DIR)
        root_node.explore(self.abs_fs_path_to_dir)
        items = []
        root_node.build_relational_model(items)
        return items


class FilesystemNode:
    DIR = "DIR"
    FILE = "FILE"

    def __init__(self, name, id, libpath, kind):
        self.name = name
        self.id = id
        self.libpath = libpath
        self.kind = kind
        self.parent = None
        self.children = []
        self.num_files = 0

    def explore(self, fspath, omit_fileless_dirs=True, cur_depth=0):
        if cur_depth > pfsc.constants.MAX_REPO_DIR_DEPTH:
            raise PfscExcep('Exceeded max repo directory depth.', PECode.REPO_DIR_NESTING_DEPTH_EXCEEDED)
        child_dirs = []
        with os.scandir(fspath) as it:
            for entry in it:
                name = entry.name
                if entry.is_file() and name.endswith('.pfsc'):
                    libpath = self.libpath if name == '__.pfsc' else f'{self.libpath}.{name[:-5]}'
                    node = FilesystemNode(name, f'{self.id}/{name}', libpath, FilesystemNode.FILE)
                    self.add_child(node)
                # For dirs, definitely want to skip `.git`. We'll skip all hidden dirs.
                elif entry.is_dir() and not name.startswith('.'):
                    node = FilesystemNode(name, f'{self.id}/{name}', f'{self.libpath}.{name}', FilesystemNode.DIR)
                    self.add_child(node)
                    path = os.path.join(fspath, name)
                    #node.explore(path)
                    child_dirs.append((node, path))
        if omit_fileless_dirs and self.num_files == 0:
            # Don't bother recursing.
            return
        for node, path in child_dirs:
            node.explore(path, cur_depth=cur_depth + 1)

    def add_child(self, child):
        child.parent = self
        if child.kind == FilesystemNode.FILE:
            self.num_files += 1
        self.children.append(child)

    def build_relational_model(self, items, siblingOrder=0, omit_fileless_dirs=True):
        """
        Build a list of items in the tree rooted at this node.
        Compare: pfsc.build.manifest.ManifestTreeNode.build_relational_model().

        It is a "relational model" in that items are _not_ nested. Instead, each item has a `parent`
        attribute, giving either the id of the parent item, or None if no parent.

        Each item also gets a "sibling" attribute, giving its order among its siblings.

        :param items: Pass the list you want to be populated with all the items.
        :param siblingOrder: Value for the `sibling` attribute.
        :return: nothing. The `items` list you pass is modified in-place.
        """
        items.append({
            "id": self.id,
            "name": self.name,
            "libpath": self.libpath,
            "parent": self.parent.id if self.parent else None,
            "type": self.kind,
            "sibling": siblingOrder,
        })
        self.children.sort(key=lambda u: u.name)
        for i, child in enumerate(self.children):
            if omit_fileless_dirs and child.kind == FilesystemNode.DIR and child.num_files == 0: continue
            child.build_relational_model(items, siblingOrder=i)


class RepoFamily:
    """
    Enum class for the names used for the different families of content repositories.
    """
    DEMO = 'demo'
    TEST = 'test'
    LOCAL = 'lh'
    GITHUB = 'gh'
    BITBUCKET = 'bb'

    all_families = [DEMO, TEST, LOCAL, GITHUB, BITBUCKET]
    local_families = [DEMO, TEST, LOCAL]
    remote_families = [GITHUB, BITBUCKET]


@contextmanager
def checkout(repo_info, tag_name=None):
    """
    Open a context in which you have checked out a repo at a certain tag.
    When the context manager closes, the repo is restored to the state it
    was in before the checkout: if you were on a branch, it goes back to
    that branch; if you were in detached state, it goes back to the commit
    you were on.

    :param repo_info: a RepoInfo instance for the repo you are interested in.
    :param tag_name: string, giving the tag you want to check out. As a convenience,
      you may also pass `None` or the "WIP" constant for the tag_name, in which case
      we don't actually do anything.
    :yield: the same repo_info object given.
    """
    if tag_name is None or tag_name == pfsc.constants.WIP_TAG:
        # In this case we're not actually meant to do anything.
        yield repo_info
    else:
        assert isinstance(repo_info, RepoInfo)
        if not repo_info.is_clean():
            msg = f'Cannot checkout `{tag_name}` for repo `{repo_info.libpath}` while working directory is not clean.'
            raise PfscExcep(msg, PECode.REPO_NOT_CLEAN)
        if repo_info.is_detached():
            final_checkout = repo_info.find_a_tag()
            if final_checkout is None:
                msg = f'Cannot checkout `{tag_name}` for repo `{repo_info.libpath}` since current commit lacks any tag.'
                raise PfscExcep(msg, PECode.REPO_IN_DETACHED_STATE)
        else:
            final_checkout = repo_info.get_active_branch_name()
        try:
            repo_info.checkout_tag(tag_name)
            yield repo_info
        finally:
            repo_info.checkout(final_checkout)


def add_all_and_commit(repo, message):
    """
    Add everything in the work space of a repo and commit.

    @param repo: pygit2 Repository
    @param message: the commit message
    @return: the Oid of the new commit
    """
    repo.index.add_all()
    repo.index.write()
    tree = repo.index.write_tree()

    s = Signature(
        pfsc.constants.PROGRAMMATIC_COMMIT_USER_NAME,
        pfsc.constants.PROGRAMMATIC_COMMIT_USER_EMAIL
    )

    h = repo.references.get("HEAD")
    if h.target in repo.references:
        ref = repo.head.name
        parents = [repo.head.target]
    else:
        # This happens with new repos that don't have any commits yet.
        ref = "HEAD"
        parents = []

    return repo.create_commit(ref, s, s, message, tree, parents)


def get_repo_info(libpath):
    """
    :param libpath: a libpath pointing either to a repo itself or to anything inside a repo
    :return: a RepoInfo object representing the containing repo
    """
    potential_repo_path = get_repo_part(libpath)
    ri = RepoInfo(potential_repo_path)
    if not ri.is_git_repo:
        raise PfscExcep("invalid repo (sub)path in %s" % libpath, PECode.INVALID_REPO)
    return ri


def get_repo_part(libpath):
    parts = libpath.split('.')
    if len(parts) < 3:
        raise PfscExcep("libpath %s does not lie within a repo" % libpath, PECode.LIBPATH_TOO_SHORT)
    potential_repo_path = '.'.join(parts[:3])
    return potential_repo_path


def make_repo_versioned_libpath(libpath, version):
    """
    One way of representing a libpath at a given version is with a
    "repo-versioned" libpath: this means we put the "@version" part
    on the repo (i.e. third) segment of the libpath, like this:

        host.user.repo@version.remainder

    While this may be a somewhat costlier operation than simply tacking
    the "@version" onto the end of the libpath, it is "truer" in that the
    version really does apply to the repo. For some applications it may
    be important to represent things this way.

    :param libpath: the libpath
    :param version: the version string. Should be either "WIP" or of the
      form `vM.m.p`. Should NOT include the "@" symbol.
    :return: the repo-versioned libpath
    """
    repo_part = get_repo_part(libpath)
    return f'{repo_part}@{version.replace(".", "_")}{libpath[len(repo_part):]}'


def parse_repo_versioned_libpath(rvlp, provide_default=False):
    """
    :param rvlp: a repo-versioned libpath
    :param provide_default: if True, and the supposed repo-versioned libpath
        in fact fails to include a version, then we provide the default version
        for this repo; if False, we instead raise an exception.
    :return: pair libpath, version
    """
    versioned_repo_part = get_repo_part(rvlp)
    p = versioned_repo_part.split("@")
    if len(p) != 2:
        if len(p) == 1 and provide_default:
            ri = RepoInfo(p[0])
            p.append(ri.get_default_version())
        else:
            raise PfscExcep(f"Malformed versioned segment: `{versioned_repo_part}`", PECode.MALFORMED_VERSIONED_LIBPATH)
    repo_part, underscore_version = p
    remainder = rvlp[len(versioned_repo_part):]
    libpath = repo_part + remainder
    version = underscore_version.replace("_", '.')
    return libpath, version

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
Tools for handling libpaths.
"""

import os
import pathlib
import re
import tempfile
from functools import lru_cache

from flask import current_app
from pygit2 import init_repository

from pfsc import check_config
import pfsc.constants
from pfsc.excep import PfscExcep, PECode
from pfsc.build.repo import RepoFamily, RepoInfo, get_repo_part, add_all_and_commit
from pfsc.gdb import get_graph_reader, building_in_gdb


def libpath_is_trusted(libpath):
    """
    Check whether a libpath is considered to be trusted, according to
    the current configuration.
    @param libpath: the libpath to be tested
    @return: boolean: True if libpath is trusted, False if not.
    """
    tpm = current_app.config['trusted_prefix_mapping']
    return libpath in tpm([libpath])


@lru_cache(maxsize=32)
def read_file_with_cache(fs_path, control_code):
    """
    :raises: FileNotFoundError
    """
    with open(fs_path) as f:
        contents = f.read()
    return contents


def libpathToAbsFSPath(libpath):
    """
    :param libpath: a dotted libpath
    :return: the corresponding absolute filesystem path

    NB: This is a purely syntactic operation, not semantic. It is up to
    you to decide if '.pfsc', '.rst', or '/__.pfsc' needs to be tacked onto
    the end. If you need help with this, you should probably be using
    the `PathInfo` class. See in particular `PathInfo.get_src_fs_path()`.
    """
    parts = libpath.split('.')
    lib_root = check_config("PFSC_LIB_ROOT")
    abs_path = os.path.join(lib_root, *parts)
    return abs_path

def absFSPathToLibpath(abs_fs_path):
    """
    Turn a filesystem path into a libpath.
    :param abs_fs_path: The given filesystem path.
    :return: The corresponding libpath.

    Note: You may include in the filesystem path the name of a .pfsc module (including __.pfsc), or not.
    """
    lib_root = check_config("PFSC_LIB_ROOT")
    path = os.path.relpath(abs_fs_path, lib_root)
    if path[-5:] == '.pfsc':
        path = path[:-5]
        if path[-2:] == "__":
            path = path[:-3]
    elif path[-4:] == '.rst':
        path = path[:-4]
    libpath = path.replace(os.sep, '.')
    return libpath

def libpath_is_absolute(libpath):
    """
    Analogous to filesystem paths, libpaths can be either absolute or relative.
    They are absolute when they begin with a valid three-part repo path, of the form
    host.user.repo. This function says whether a libpath is absolute.
    """
    parts = libpath.split('.')
    if len(parts) < 3: return False
    if parts[0] not in RepoFamily.all_families: return False
    potential_repo_path = '.'.join(parts[:3])
    ri = RepoInfo(potential_repo_path)
    return ri.is_git_repo

def isInitialPathSeg(p, P):
    """
    Say whether libpath p is an initial segment of libpath P.
    For example, if
        p == lit.h.Hilbert.ZB.P1.C1.S3.Thm5.Pf,
    and
        P == lit.h.Hilbert.ZB.P1.C1.S3.Thm5.Pf.SbPf
    then we will return True.

    We require p to be strictly shorter than P.
    """
    n = len(p); N = len(P)
    if N <= n: return False
    if not p == P[:n]: return False
    if not P[n] == '.': return False
    return True

def expand_multipath(mp):
    """
    A _multipath_ is a libpath in which at most one libseg may be replaced by
    an expression of the form `{lp1,lp2,...,lpn}`, where each lpi itself has the
    form of a libpath. The multipath thereby indicates multiple libpaths.

    For example, the multipath

                    foo.bar.{spam.baz, cat}.boo

    indicates the two libpaths,

                    foo.bar.spam.baz.boo
                    foo.bar.cat.boo

    @param mp: a multipath
    @return: list of libpaths represented by the multipath
    """
    i0 = mp.find("{")
    if i0 < 0:
        # No opening brace. In this case we assume it is just an ordinary libpath.
        return [mp]
    i1 = mp.find("}")
    if i1 <= i0:
        # If closing brace is missing, or does not come after opening brace, then malformed.
        msg = 'Malformed multipath: %s' % mp
        raise PfscExcep(msg, PECode.MALFORMED_MULTIPATH)
    # Now we have 0 <= i0 < i1, and the two indices i0, i1 point to "{" and "}" chars, resp.
    prefix = mp[:i0]
    suffix = mp[i1+1:]
    multi = mp[i0+1:i1].split(',')
    return [prefix + m.strip() + suffix for m in multi]


class PathInfo:
    """
    Gathers filesystem info about a libpath, such as whether it corresponds to a file,
    or to a directory.
    """

    def __init__(self, libpath):

        # What libpath do we represent?
        self.libpath = libpath

        # Before populating our info fields, we define them all here:

        # Does the path refer to an existing file?
        self.is_file = None
        # If so, record the absolute filesystem path to the file.
        self.abs_fs_path_to_file = None
        # Does the path refer to an existing directory?
        self.is_dir = None
        # If so, record the absolute filesystem path to the directory.
        self.abs_fs_path_to_dir = None
        # If (and only if) is_dir is True, this field will say whether that
        # directory contains a __.pfsc module.
        self.dir_has_default_module = None
        # If we do have a default module, record the abs fs path to it.
        self.abs_fs_path_to_default_module = None
        # If the path refers to a file, or to a dir that has a __.pfsc file,
        # record the modification time of that file, as a Unix timestamp.
        self.src_file_modification_time = None

        # Now check the given path, populating the info fields.
        self.check_libpath()

    def check_libpath(self):
        """
        Check the given libpath, populating all info fields to describe what we learn.
        """
        fs_path = libpathToAbsFSPath(self.libpath)

        # Is there a .pfsc or .rst file under this name?
        for ext in ['.pfsc', '.rst']:
            modpath = fs_path + ext
            self.is_file = os.path.exists(modpath)
            if self.is_file:
                self.abs_fs_path_to_file = modpath
                break

        # Does the path name a directory?
        self.is_dir = os.path.isdir(fs_path)
        # If so, is there a default module within the directory?
        if self.is_dir:
            self.abs_fs_path_to_dir = fs_path
            default_modpath = os.path.join(fs_path, '__.pfsc')
            self.dir_has_default_module  = os.path.exists(default_modpath)
            if self.dir_has_default_module:
                self.abs_fs_path_to_default_module = default_modpath

        # If there is a module file, get its modification time.
        src_fs_path = self.get_src_fs_path()
        if src_fs_path is not None:
            self.src_file_modification_time = os.path.getmtime(src_fs_path)

    def get_formal_parent_path(self):
        """
        Convenience method to get the libpath that results from deleting the final
        segment of this one. This is a purely syntactic operation (hence "formal" in the
        method name), and gives _no_ guarantee that the resulting libpath refers to
        anything real.

        :return: The formal parent path, as described above.
        :raises: AssertionError if our libpath has no dots.
        """
        k = self.libpath.rfind('.')
        assert k > 0
        return self.libpath[:k]

    def is_module(self, strict=False):
        """
        Say whether this path points to a module.
        :param strict: set True if you require directories to contain a `__.pfsc` file in order
                   to be considered a module.
        :return: boolean
        """
        return self.is_file or (self.is_dir and (self.dir_has_default_module or not strict))

    def get_build_dir_and_filename(self, version=pfsc.constants.WIP_TAG):
        """
        Get the directory to which this module's source code should be saved
        when building, and the filename to use.

        :param version: which version we are building.
        :return: Pair (build_dir, filename) giving the absolute filesystem path
            to the build dir for this module, and the filename to use.
        """
        parts = self.libpath.split('.')
        build_root = check_config("PFSC_BUILD_ROOT")
        fs_dir_parts = [build_root] + parts[:3] + [version] + parts[3:]
        filename = '__.src'
        return os.path.join(*fs_dir_parts), filename

    def get_pickle_path(self, version=pfsc.constants.WIP_TAG):
        """
        Get the path for this module's pickle file.

        :param version: which version we are building.
        :return: The absolute filesystem path to the pickle file for this
            module.
        """
        build_dir, _ = self.get_build_dir_and_filename(version=version)
        return os.path.join(build_dir, 'module.pickle')

    def is_rst_file(self):
        """
        Say whether the file representing this module is an `.rst` file.
        """
        p = self.abs_fs_path_to_file
        return p and p.endswith('.rst')

    def name_is_available(self, proposed_name):
        """
        If this path points to a directory, say whether a certain name is still available
        for a file within this directory.

        :param proposed_name: The name whose availability is to be checked.
          _Must not_ include the `.pfsc` or `.rst` file extension.
        :return: boolean
        :raises: PfscExcep if this path does not point to a directory.
        """
        if not self.is_dir:
            msg = 'Path %s is not a directory.' % self.libpath
            raise PfscExcep(msg, PECode.LIBPATH_IS_NOT_DIR)
        existing_names = []
        with os.scandir(self.abs_fs_path_to_dir) as it:
            for entry in it:
                name = entry.name
                if entry.is_file():
                    if name.endswith('.pfsc'):
                        existing_names.append(name[:-5])
                    elif name.endswith('.rst'):
                        existing_names.append(name[:-4])
                # For dirs, definitely want to skip `.git`. We'll skip all hidden dirs.
                elif entry.is_dir() and not name.startswith('.'):
                    if '__.pfsc' in os.listdir(entry.path):
                        existing_names.append(name)
        available = proposed_name not in existing_names
        return available

    def get_src_fs_path(self):
        """
        :return: If this libpath points to a file, return the absolute filesystem
                 path to that file. Otherwise return None.
        """
        if self.is_dir and self.dir_has_default_module:
            fs_path = self.abs_fs_path_to_default_module
        elif self.is_file:
            fs_path = self.abs_fs_path_to_file
        else:
            fs_path = None
        return fs_path

    def make_tilde_backup(self):
        """
        Make a backup copy of the WIP version of the module on disk (if it exists
        yet), appending a tilde character "~" to the end of the filename.
        """
        try:
            text = self.read_module(version=pfsc.constants.WIP_TAG)
        except FileNotFoundError:
            pass
        else:
            self.write_module(text, appendTilde=True)

    def check_shadow_policy(self):
        """
        Determine whether we should do a shadow write for this module.
        :return: boolean
        """
        shadow_policy = check_config("PFSC_SHADOWSAVE")
        if 'all' in shadow_policy:
            return True
        repopart = get_repo_part(self.libpath)
        return repopart in shadow_policy

    def write_module(self, text, appendTilde=False):
        """
        Write the given text to disk in the file for this module, if any.
        :param text: The fulltext of the module to be written.
        :param appendTilde: If True, append a tilde "~" to the end of the filename.
        :return: number of bytes written
        :raises: PfscExcep if no such file exists
        """
        fs_path = self.get_src_fs_path()
        if fs_path is None:
            msg = 'Libpath %s does not point to a file.' % self.libpath
            raise PfscExcep(msg, PECode.MODULE_DOES_NOT_EXIST)
        if appendTilde:
            fs_path += "~"
        with open(fs_path, 'w') as f:
            n = f.write(text)
        return n

    def read_module(self, version=pfsc.constants.WIP_TAG, cache_control_code=None):
        """
        Attempt to read the contents of the module indicated by this path, at the
        desired version.

        :param version: the version of this module to be loaded.
        :param cache_control_code: just here to control lru caching.
          Pass `None` to force a cache miss.
        :return: the contents of the module at the desired version.
        :raises: FileNotFoundError if there is no file for the desired version.
        """
        if version == pfsc.constants.WIP_TAG:
            fs_path = self.get_src_fs_path()
            if fs_path is None:
                raise FileNotFoundError
        elif building_in_gdb():
            return get_graph_reader().load_module_src(self.libpath, version)
        else:
            build_dir, filename = self.get_build_dir_and_filename(version=version)
            fs_path = os.path.join(build_dir, filename)
        if cache_control_code is None:
            return read_file_with_cache.__wrapped__(fs_path, None)
        else:
            return read_file_with_cache(fs_path, cache_control_code)

def get_modpath(libpath, version=pfsc.constants.WIP_TAG, strict=False):
    """
    Compute the libpath of the deepest module named in a given libpath.

    :param libpath: any valid absolute libpath
    :param version: the version at which this relation should obtain.
    :param strict: set True if you require directories to contain a `__.pfsc` file in order
                   to be considered a module.
    :return: the longest initial segment of this path that points to a module
    """
    if version != pfsc.constants.WIP_TAG:
        modpath = get_graph_reader().get_modpath(libpath, version)
        if modpath is None:
            msg = f'Cannot find module for `{libpath}` at version `{version}`.'
            raise PfscExcep(msg, PECode.MODULE_DOES_NOT_EXIST)
        return modpath
    parts = libpath.split('.')
    if len(parts) < 3:
        msg = 'Libpath too short: %s' % libpath
        raise PfscExcep(msg, PECode.LIBPATH_TOO_SHORT)
    p = parts[:2]
    for part in parts[2:]:
        p.append(part)
        lp = '.'.join(p)
        pi = PathInfo(lp)
        if not pi.is_module(strict=strict):
            p.pop()
            break
    if len(p) < 3:
        msg = 'Module does not exist: %s' % libpath
        raise PfscExcep(msg, PECode.MODULE_DOES_NOT_EXIST)
    modpath = '.'.join(p)
    return modpath

def get_formal_moditempath(libpath, strict=False):
    """
    Like `get_modpath`, only we try to extend the modpath one segment more, to
    a libpath denoting a "module item" (i.e. an item defined at the top level of a
    proofscape module).

    We do _not_ check whether the resulting path is valid, hence the `formal` in the name
    of this function.

    :param libpath: any valid absolute libpath
    :param strict: see `get_modpath` function.

    :raises: PfscExcep if the given libpath is too short to point to a module item, i.e. if it
             points to a module.
    """
    modpath = get_modpath(libpath, strict=strict)
    remainder = libpath[len(modpath)+1:]
    rem_parts = remainder.split('.')
    next_seg = rem_parts[0]
    if not next_seg:
        msg = 'libpath %s too short too point to module item' % libpath
        raise PfscExcep(msg)
    moditempath = modpath + '.' + next_seg
    return moditempath

def get_deduction_closure(libpaths):
    """
    Given an iterable of libpaths of deducs and/or nodes, compute the "deduction closure"
    thereof. This is the smallest set of deductions that contains all the items named.

    :param libpaths: list of libpaths of deducs and/or nodes.
    :return: set of libpaths of the deduction closure thereof
    """
    closure = set()
    for libpath in libpaths:
        closure.add(get_formal_moditempath(libpath))
    return closure

def git_style_merge_conflict_file(modpath, yourtext, your_label="YOURS", disk_label="DISK"):
    """
    Compare a given text to the contents of a certain module on disk.
    Return a merged version of the two, showing git-style merge conflicts:

        ...
        <<<<<<< YOURS
        ...
        =======
        ...
        >> >>>> DISK
        ...

    (Note: a ">" is omitted from the illustration above to avoid matching as
     Python REPL text in IDEs.)

    :param modpath: the libpath of the module to which you want to compare.
    :param yourtext: the text (string) you want to compare with the version on disk.
    :param your_label: the label you want after "<<<<<<<<"
    :param disk_label: the label you want after ">>>>>>>>"
    :return: Git-style "merge conflict" text (string) combining the two versions.
    """
    pi = PathInfo(modpath)
    fs_path = pi.get_src_fs_path()
    if fs_path is None:
        msg = f'Module {modpath} does not exist.'
        raise PfscExcep(msg, PECode.MODULE_DOES_NOT_EXIST)
    disktext = pi.read_module()
    with tempfile.TemporaryDirectory() as tmp_path_str:
        repo_dir = pathlib.Path(tmp_path_str)
        filename = repo_dir / 'contested'

        repo = init_repository(repo_dir)
        initial_id = add_all_and_commit(repo, "Initial commit")
        initial_commit = repo.get(initial_id)

        disk_branch = repo.branches.local.create('disk_version', initial_commit)
        your_branch = repo.branches.local.create('your_version', initial_commit)

        repo.checkout(disk_branch)
        with open(filename, 'w') as f:
            f.write(disktext)
        disk_latest_id = add_all_and_commit(repo, "disk version")

        repo.checkout(your_branch)
        with open(filename, 'w') as f:
            f.write(yourtext)
        add_all_and_commit(repo, "your version")

        repo.merge(disk_latest_id)

        with open(filename, 'r') as f:
            mergetext = f.read()

        mergetext = re.sub(
            '^<<<<<<< HEAD', f'<<<<<<< {your_label}',
            mergetext, flags=re.MULTILINE)
        mergetext = re.sub(
            f'^>>>>>>> {disk_latest_id.hex}', f'>>>>>>> {disk_label}',
            mergetext, flags=re.MULTILINE)

    return mergetext

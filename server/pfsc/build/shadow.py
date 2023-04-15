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
Tools for saving and committing to shadow repos.
"""

import os

from pygit2 import Repository, init_repository

from pfsc.excep import PfscExcep, PECode
from pfsc.build.lib.libpath import PathInfo
from pfsc.build.repo import RepoInfo, get_repo_info, add_all_and_commit


class ShadowInfo:

    def __init__(self):
        self.num_bytes_written = 0
        self.commit = None

    def num_tree_objects(self):
        """Provides some rough measure of what happened. """
        return len(self.commit.tree)

    def __str__(self):
        r = ''
        c = self.commit
        if c is None:
            r = 'No changes detected. No commit.\n'
        else:
            r += f'commit {c.oid}\n'
            r += f'Author:  {c.author.name} <{c.author.email}>\n'
            r += f'Time:    {c.commit_time}\n'
            r += f'Objects: {self.num_tree_objects()}\n'
        return r


def shadow_save_and_commit(true_path_info, fulltext):
    """
    Save a copy of a module in a shadow repo.

    :param true_path_info: PathInfo for the true (not shadow) module
    :param fulltext: the full text (str) of the module
    :return: ShadowInfo instance
    """
    shadow_info = ShadowInfo()

    assert isinstance(true_path_info, PathInfo)
    true_repo_info = get_repo_info(true_path_info.libpath)
    assert isinstance(true_repo_info, RepoInfo)

    shadow_repo_path = true_repo_info.get_shadow_repo_path()

    # Make sure we have a shadow repo.
    if not os.path.exists(shadow_repo_path):
        shadow_repo = init_repository(shadow_repo_path)
    else:
        shadow_repo = Repository(shadow_repo_path)

    mod_fs_path = true_path_info.get_pfsc_fs_path()
    if mod_fs_path is None:
        msg = 'Module must have a true filesystem path to be shadow saved.'
        raise PfscExcep(msg, PECode.MODULE_DOES_NOT_EXIST)

    repo_fs_path = true_repo_info.abs_fs_path_to_dir
    intra_repo_mod_fs_path = mod_fs_path[len(repo_fs_path):]

    # Make sure intra repo path is relative.
    if intra_repo_mod_fs_path[0] == '/':
        intra_repo_mod_fs_path = intra_repo_mod_fs_path[1:]

    shadow_mod_fs_path = os.path.join(
        shadow_repo_path,
        intra_repo_mod_fs_path
    )

    # Make sure the directory within the shadow repo exists, where the shadow
    # module is supposed to live.
    shadow_mod_dir_fs_path = os.path.dirname(shadow_mod_fs_path)
    os.makedirs(shadow_mod_dir_fs_path, exist_ok=True)

    # Write the shadow module.
    with open(shadow_mod_fs_path, 'w') as f:
        n = f.write(fulltext)
        shadow_info.num_bytes_written = n

    # Commit if any diff.
    if shadow_repo.status():
        oid = add_all_and_commit(shadow_repo, "...")
        shadow_info.commit = shadow_repo.get(oid)

    return shadow_info

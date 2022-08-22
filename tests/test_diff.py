# --------------------------------------------------------------------------- #
#   Proofscape Server                                                         #
#                                                                             #
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

import pytest

from pfsc.build.lib.libpath import PathInfo, git_style_merge_conflict_file
from pfsc.build.repo import get_repo_info

expected_diff = """
<<<<<<<< YOURS
# We also need to test whether we correctly ignore # chars occurring within
# strings (i.e. do _not_ strip them out as comments).
# Also in this version I moved some words around in the last two comment lines,
# so we can test out our Git-style merge conflict function, by comparing v11
# and v12.
========
# We also need to test whether we correctly ignore # chars
# occurring within strings (i.e. do _not_ strip them out as comments).
>>>>>>>> DISK
"""

@pytest.mark.parametrize("repo, branch1, branch2, modpath", (
    ("test.foo.bar", "v11", "v12", "test.foo.bar.expansions"),
))
def test_git_style_merge(app, repo, modpath, branch1, branch2):
    with app.app_context():
        ri = get_repo_info(repo)
        ri.checkout(branch2)
        pi = PathInfo(modpath)
        fs_path = pi.get_pfsc_fs_path()
        with open(fs_path) as f:
            yourtext = f.read()
        ri.checkout(branch1)
        mergetext = git_style_merge_conflict_file(modpath, yourtext)
        #print(mergetext)
        lines = mergetext.split('\n')
        #print(len(lines))
        assert len(lines) == 114
        #print(mergetext.find(expected_diff))
        assert mergetext.find(expected_diff) == 1921

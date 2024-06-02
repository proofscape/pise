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

from pfsc.build.repo import get_repo_info
from pfsc.build.lib.libpath import PathInfo
from pfsc.build.shadow import shadow_save_and_commit

def test_shadow_00(app):
    print()
    with app.app_context():
        #modpath = 'test.alex.math.thm1'
        modpath = 'test.hist.lit.G.auss.DA'
        ri = get_repo_info(modpath)
        ri.checkout('v0')
        pi = PathInfo(modpath)
        modtext_0 = pi.read_module()
        modtext_1 = "# Add some comments at the top...\n" + modtext_0
        modtext_2 = "# Add more comments above those...\n# And still more...\n" + modtext_1

        si_0 = shadow_save_and_commit(pi, modtext_0)
        print(si_0)
        assert si_0.commit is not None

        si_1 = shadow_save_and_commit(pi, modtext_1)
        print(si_1)
        assert si_1.num_tree_objects() == 1

        si_2 = shadow_save_and_commit(pi, modtext_2)
        print(si_2)
        assert si_2.num_tree_objects() == 1

        # Now try writing the last version again.
        # Should show no change, no commit.
        si_3 = shadow_save_and_commit(pi, modtext_2)
        print(si_3)
        assert si_3.commit is None

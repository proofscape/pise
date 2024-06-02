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
Turn the resources in our `repo` directory into actual git repositories
under LIB_ROOT/test.
"""

import sys

from tests.util import make_repos

if __name__ == "__main__":
    only = None
    """
    One optional CLI arg may be passed, of the form 'user.proj', in order to
    make *only* the repo 'test.user.proj'. Otherwise, *all* repos are made.
    """
    if len(sys.argv) > 1:
        only_repo = sys.argv[1]
        user, proj = only_repo.split('.')
        only = [(user, proj)]
    make_repos(only=only)

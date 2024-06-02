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
Clear all indexing of test repos.
"""

import argparse

from tests.util import clear_indexing

from pfsc.excep import PfscExcep

descrip="""
Clear existing indexing.

If no args are passed: clear all test indexing (i.e. under host segment `test`).
If -r/--repo is given: clear indexing just for this repo (need not be under `test`).
If -v/--vers is given: clear the named repo at this version (else under WIP).
"""

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description=descrip)
        parser.add_argument('-r', '--repo', help='repopath')
        parser.add_argument('-v', '--vers', help='version')
        args = parser.parse_args()
        clear_indexing(repopath=args.repo, version=args.vers)
    except PfscExcep as e:
        print(e)

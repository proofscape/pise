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
Utility script for updating all import statements in a Proofscape repo, following
the (hopefully rare) change in the way import statements work in .pfsc modules.

Most recent usaage (17 Jul 2019): We are making it so the first dot in a relative
 import means "this module". Therefore, at this time, all existing relative import
 paths need to be extended by one dot.
"""

import sys, os

def update(repopath, dry=False):
    for P, D, F in os.walk(repopath):
        for fn in F:
            if fn[-5:] == '.pfsc':
                path = os.path.join(P, fn)
                with open(path) as f:
                    lines = f.readlines()
                out = ''
                for line in lines:
                    if line.startswith('from .'):
                        print("Change %s:" % path)
                        print('    ', line[:-1])
                        line = 'from ..' + line[6:]
                        print('    ', line[:-1])
                    out += line
                if dry:
                    #print("%"*80)
                    #print(path+'\n')
                    #print(out)
                    pass
                else:
                    with open(path, 'w') as f:
                        f.write(out)

def test1():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests/resources/repo')
    print()
    #path = '/usr/local/share/proofscape/lib/gh/rrmath/lit'
    #path = '/usr/local/share/proofscape/lib/gh/skieffer/mathnotes'
    update(path, dry=False)

def cli():
    try:
        repopath = sys.argv[1]
        assert os.path.exists(repopath)
    except:
        print("Pass one arg, being the abs filesystem path to the repo to be updated.")
        sys.exit(1)
    update(repopath)

if __name__ == "__main__":
    test1()

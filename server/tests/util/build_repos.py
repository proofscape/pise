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
Build and index the test repos.
"""

import sqlite3

from tests.util import build_all, build_at_wip, build_big

from gremlite.logging import print_open_cursor_traces

if __name__ == "__main__":

    # The try-except was added in order to help diagnose issues with transactions
    # when first adding support for gremlite. I leave it in case it is useful for
    # future debugging.
    try:
        # Uncomment to record logs:
        #import logging
        #logging.basicConfig(filename='build_repos.log', level=logging.INFO)

        #build_big()

        build_all()
        # To show timings:
        #build_all(verbose=2)

        build_at_wip()

    except sqlite3.OperationalError:
        print_open_cursor_traces()
        raise

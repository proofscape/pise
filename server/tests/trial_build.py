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
During development, use this script in order to test/debug a complete build
of any repo.

Define the build job by setting env vars in `instance/.env`:

    TRIAL_BUILD_LIBPATH=repo.to.build
    TRIAL_BUILD_VERSION=WIP
    TRIAL_BUILD_CLEAN=1

When TRIAL_BUILD_VERSION is any numbered version, e.g. v0.1.0, then we use the
`clear_and_build_releases_with_deps_depth_first()` function, which clears all
existing indexing of test repos, and then builds the desired version plus all
its dependencies, in topological order.

We use a script instead of a unit test because sometimes these builds can mess up
other unit tests. In particular, our procedure when building at a numbered version
messes them up by clearing indexing, and you must do

    $ inv btr

again, before you can run the unit tests.

We use environment variables to control the build so that these settings are
not seen as "changes" by git.
"""

import os
import sys

from pfsc import make_app
from pfsc.build import build_repo
from pfsc.constants import WIP_TAG
from config import ConfigName

from tests.util import clear_and_build_releases_with_deps_depth_first

testing_config = ConfigName.LOCALDEV

os.environ["FLASK_CONFIG"] = testing_config


def main():
    app = make_app(testing_config)
    app.config["PERSONAL_SERVER_MODE"] = True

    repopath = os.getenv("TRIAL_BUILD_LIBPATH")
    version = os.getenv("TRIAL_BUILD_VERSION", WIP_TAG)
    make_clean = bool(int(os.getenv("TRIAL_BUILD_CLEAN", 1)))

    print('-' * 50)
    print('Trial build')
    print('  repo:', repopath)
    print('  version:', version)
    if version == WIP_TAG:
        print('  clean:', make_clean)
    print()

    if not repopath:
        print('Did you forget to define `TRIAL_BUILD_LIBPATH` in `instance/.env`?')
        sys.exit(1)

    if version == WIP_TAG:
        with app.app_context():
            build_repo(repopath, make_clean=make_clean)
    else:
        clear_and_build_releases_with_deps_depth_first(app, [(repopath, version)])


if __name__ == "__main__":
    main()

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

import pytest

import pfsc.constants as pfsc_constants
from pfsc.build.repo import get_repo_info
from pfsc.lang.modules import (
    load_module, remove_modules_from_disk_cache, unpickle_module
)


@pytest.mark.psm
def test_purge(app):
    """
    Test the ability to purge pickle files from on-disk cache.
    """
    with app.app_context():
        ri = get_repo_info('test.foo.bar')
        ri.checkout('v0')

        modpath = 'test.foo.bar.results'
        version = pfsc_constants.WIP_TAG

        remove_modules_from_disk_cache([modpath], version=version)
        u = unpickle_module(modpath, version)
        assert u is None

        load_module(modpath, version=version)
        u = unpickle_module(modpath, version)
        assert u is not None

        remove_modules_from_disk_cache([modpath], version=version)
        u = unpickle_module(modpath, version)
        assert u is None

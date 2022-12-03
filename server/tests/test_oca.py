# --------------------------------------------------------------------------- #
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

import config


@pytest.mark.skip(reason="for manual testing only")
def test_latest_version(client):
    # First try when it's not under OcaConfig:
    resp = client.get(f'/oca/latestVersion')
    assert resp.status_code == 403
    # Now force it to be an OcaConfig-ed app.
    # This time should get the actual latest version number.
    client.app.config.from_object(config.OcaConfig)
    resp = client.get(f'/oca/latestVersion')
    print(f'\nObtained latest version: {resp.data.decode()}')

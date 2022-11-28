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

import pfsc.constants
from pfsc.checkinput import check_input
from pfsc.excep import PfscExcep, PECode


@pytest.mark.parametrize(('pathtype', 'path', 'err_code'), (
    ('libpath', '', PECode.INPUT_EMPTY),
    ('libpath', 'a' * (pfsc.constants.MAX_LIBPATH_LEN + 1), PECode.INPUT_TOO_LONG)
))
def test_check_libpath_exceps(pathtype, path, err_code):
    """
    Show that when we try to check a libpath of a certain type, we get a certain error code.
    :param pathtype: the type of the path (libpath, repopath, etc.)
    :param path: the path to be checked
    :param err_code: the PECode we should get
    :return: nothing
    """
    with pytest.raises(PfscExcep) as e:
        check_input({'libpath': path}, {}, {
            "REQ": {
                'libpath': {
                    'type': pathtype
                }
            }
        })
    assert e.value.code() == err_code

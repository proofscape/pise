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

import pfsc.constants
from pfsc.build.versions import get_major_version_part, adapt_gen_version_to_major_index_prop
from pfsc.excep import PfscExcep, PECode

def check_major_version(key, raw, typedef):
    """
    :param raw: either an actual non-negative integer, or a string rep of non-negative
      integer, base 10, or the string "WIP".
    :param typedef:
        OPT:
            tolerant: default is True; set False to disallow input in the form of
                a full version tag `vM.m.p`. (When tolerant, we extract the `M` part.
                and return as int.)
            allow_WIP: default is True; set False to disallow "WIP"
    :return: int or "WIP" string
    """
    if not isinstance(raw, (str, int)):
        raise PfscExcep('Major version must be int or string.', PECode.INPUT_WRONG_TYPE)
    tolerant = typedef.get('tolerant', True)
    allow_WIP = typedef.get('allow_WIP', True)
    if tolerant:
        raw = adapt_gen_version_to_major_index_prop(raw)
    if raw == pfsc.constants.WIP_TAG:
        if not allow_WIP:
            raise PfscExcep('Disallowed version tag.', PECode.DISALLOWED_VERSION_TAG, bad_field=key)
        return raw
    try:
        n = int(raw)
    except Exception:
        raise PfscExcep('Bad major version number', PECode.BAD_INTEGER, bad_field=key)
    if n < 0:
        raise PfscExcep('Bad major version number', PECode.BAD_INTEGER, bad_field=key)
    return n

class CheckedVersion:

    def __init__(self, full, major, isWIP):
        self.full = full
        self.major = major
        self.isWIP = isWIP

def check_full_version(key, raw, typedef):
    """
    :param raw: a string that should represent a full version, so either "WIP" or
      of the form vM.m.p
    :param typedef:
        OPT:
            allow_WIP: default is True; set False to disallow "WIP"

    :return: CheckedVersion instance
    """
    if not isinstance(raw, str):
        raise PfscExcep('Full version must be string.', PECode.INPUT_WRONG_TYPE)
    allow_WIP = typedef.get('allow_WIP', True)
    # This function raises exactly the exceptions we want:
    M = get_major_version_part(raw, allow_WIP=allow_WIP)
    # If didn't raise an exception, raw input is okay.
    return CheckedVersion(raw, M, raw==pfsc.constants.WIP_TAG)

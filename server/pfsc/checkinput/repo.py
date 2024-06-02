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

from pfsc.checkinput.libpath import check_libpath
from pfsc.checkinput.version import check_full_version
from pfsc.excep import PfscExcep


def check_repo_dependencies_format(deps, home_repopath):
    """
    Check the dependencies dictionary for a repo.

    :param deps: dictionary, in which keys should be repopaths (strings), and
        values should be versions (strings)
    :param home_repopath: the libpath of the repo from which this dependency
        declaration was taken. This is just for enriching the error message.

    :return: dictionary of checked repopaths and versions. Still just mapping
        strings to strings.
    """
    checked_deps = {}
    try:
        for rp, vers in deps.items():
            cl = check_libpath('', rp, {'repo_format': True})
            cv = check_full_version('', vers, {})
            checked_deps[cl.value] = cv.full
    except PfscExcep as pe:
        pe.extendMsg(
            f'Problem is with dependencies declared in root module of {home_repopath}.'
        )
        raise pe
    return checked_deps

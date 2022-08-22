# --------------------------------------------------------------------------- #
#   Proofscape Server                                                         #
#                                                                             #
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

import re

import pfsc.constants
from pfsc.excep import PfscExcep, PECode


# Each component of a version number tag must either equal "0" or else start
# with a non-zero digit. In other words, we want it to represent a non-negative
# integer, and we want there to be only one way to do that (i.e. you can't start
# with an arbitrary number of leading zeros).
VERSION_TAG_REGEX = re.compile(r'^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')


def adapt_gen_version_to_major_index_prop(version):
    """
    This function aims to be a sort of "universal adapter," accepting nearly
    anything you can throw at it under the name of "version", and producing
    a string of the kind our indexing system uses as the `major` property
    of j-nodes and j-relns.

    :param version: Accepted values are:
        * the "WIP" string
        * a non-negative integer (as an actual int)
        * a non-negative integer as a base-10 string
        * a release tag string of the form `vM.m.p`

    :return: a string, which will be either "WIP" or else a 0-padded integer
      of the correct length. (The latter will be the given integer, or int(M).)
    :raises: PfscExcep
    """
    if version == pfsc.constants.WIP_TAG:
        return version
    try:
        n = int(version)
    except ValueError:
        n = get_major_version_part(version)
    assert isinstance(n, int)
    if n < 0 or n > pfsc.constants.MAX_NUMERICAL_VERSION_COMPONENT:
        msg = f'Version number component `{n}` out of range.'
        raise PfscExcep(msg, PECode.MALFORMED_VERSION_TAG)
    return pfsc.constants.PADDED_VERSION_COMPONENT_FORMAT % n

def collapse_padded_full_version(pfv):
    """
    :param pfv: a string giving a padded version, such as
      `000003000014000159` or `WIP000000000000`.
    :return: the corresponding ordinary version tag, such as `v3.14.159` or `WIP`.
    """
    assert isinstance(pfv, str)
    if pfv.startswith(pfsc.constants.WIP_TAG):
        return pfsc.constants.WIP_TAG
    n = pfsc.constants.PADDED_VERSION_COMPONENT_LENGTH
    assert len(pfv) == 3 * n
    M, m, p = [int(k) for k in [pfv[n*i : n*i + n] for i in range(3)]]
    return f'v{M}.{m}.{p}'

def collapse_major_string(ms):
    """
    :param ms: a string giving a major version, as obtained from a j-node's
      `major` property. Thus, either "WIP" or a padded integer "00000n".
    :return: int or the string "WIP"
    """
    try:
        # Want to collapse padded numerical major versions.
        major = int(ms)
    except ValueError:
        # This case should arise only if major == "WIP", in which
        # case we're happy to leave it as it is.
        major = ms
    return major

def version_string_is_valid(vs, allow_WIP=True):
    """
    Say whether a version string is of valid form.
    :param vs: the string to be tested.
    :param allow_WIP: set True to allow version string "WIP", False to disallow it.
    :return: boolean True if the given version string is valid, False otherwise.
    """
    if allow_WIP and vs == pfsc.constants.WIP_TAG:
        return True
    return VERSION_TAG_REGEX.match(vs) is not None


def get_major_version_part(vs, allow_WIP=True):
    """
    Extract the "major part" from a version string.
    If the string is invalid, we raise an exception.
    If it's a WIP version and we allow that, we return that string itself.
    If it's a WIP version and we don't allow that, we raise an exception.
    Otherwise it must be of the form vM.m.p, and we return M as an integer.

    :param vs: the version string.
    :param allow_WIP: set True to allow version string "WIP", False to disallow it.
    :return: the major part of the version string, as WIP string or int.
    """
    is_WIP = vs == pfsc.constants.WIP_TAG
    if not version_string_is_valid(vs, allow_WIP=allow_WIP):
        if is_WIP and not allow_WIP:
            raise PfscExcep(f'Disallowed version tag `{vs}`.', PECode.DISALLOWED_VERSION_TAG)
        else:
            raise PfscExcep(f'Malformed version tag `{vs}`.', PECode.MALFORMED_VERSION_TAG)
    return vs if is_WIP else int(vs.split('.')[0][1:])


class VersionTag:

    def __init__(self, name):
        """
        :param name: the text of the version name, e.g. "v3.0.2"
        """
        self.name = name
        M = VERSION_TAG_REGEX.match(self.name)
        if not M:
            raise PfscExcep(f'Malformed version tag: {self.name}', PECode.MALFORMED_VERSION_TAG)
        self.major, self.minor, self.patch = [int(g) for g in M.groups()]

    def get_name(self):
        """
        :return: the full text of the version tag, such as "v3.0.2"
        """
        return self.name

    def get_components(self):
        """
        :return: triple (M, m, p) of the major, minor, and patch numbers as ints.
        """
        return self.major, self.minor, self.patch

    def __lt__(self, other):
        """
        Support proper sorting of version tags. This is necessary since
        lexicographic ordering on strings will produce wrong results such
        as putting "v10.0.1" before "v2.1.8".
        """
        return self.major < other.major or (
            self.major == other.major and (
                self.minor < other.minor or (
                    self.minor == other.minor and self.patch < other.patch
                )
            )
        )
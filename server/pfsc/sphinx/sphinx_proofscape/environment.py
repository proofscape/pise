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

from pfsc.constants import WIP_TAG
from pfsc.build.versions import version_string_is_valid


class SphinxPfscEnvironment:
    """
    An instance of this class will be stored in the Sphinx BuildEnvironment,
    under the attribute 'proofscape'.

    It is designed to hold all of the environment data structures relevant to
    the sphinx-proofscape extension, such as Widget instances, etc.

    It supports merge/purge operations, for Sphinx parallel builds.
    """

    def __init__(self, app):
        self.all_widgets = []
        self.vers_defns = regularize_version_dict(app)
        self.lp_defns_by_docname = {}

    def purge(self, docname):
        # See https://www.sphinx-doc.org/en/master/development/tutorials/
        # TODO: other things besides widgets?
        self.all_widgets = [
            w for w in self.all_widgets if w.docname != docname
        ]

    def merge(self, other):
        # TODO: other things besides widgets?
        self.all_widgets.extend(other.all_widgets)


def regularize_version_dict(app):
    """
    Read the version dictionary out of `config.pfsc_import_repos`, regularize
    it, meaning ensure that each value is either WIP or starts with a 'v', and
    then save the regularized version in the env.

    raises: ValueError if any version string is improperly formatted
    """
    vers_defns = app.config.pfsc_import_repos or {}
    r = {}
    for k, v in vers_defns.items():
        if v != WIP_TAG:
            if not v.startswith('v'):
                v = f'v{v}'
            if not version_string_is_valid(v):
                raise ValueError(v)
        r[k] = v
    return r

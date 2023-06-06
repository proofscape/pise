# --------------------------------------------------------------------------- #
#   Sphinx-Proofscape                                                         #
#                                                                             #
#   Copyright (c) 2022-2023 Proofscape contributors                           #
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

from docutils.parsers.rst.directives import unchanged
from sphinx.errors import SphinxError
from sphinx.util.docutils import SphinxDirective

from pfsc.sphinx.sphinx_proofscape.environment import SphinxPfscEnvironment
from pfsc.checkinput import check_libpath
from pfsc.excep import PfscExcep


class PfscDefnsDirective(SphinxDirective):
    """
    The pfsc-defns directive has no visual form; it is just a place to define
    things that control how pfsc widgets are processed.

    At this time there is only one option, `libpaths`, which accepts
    definitions of abbreviations for libpaths.

    Example:
        .. pfsc-defns::
            :libpaths:
                Pf:  gh.toepproj.lit.H.ilbert.ZB.Thm168.Pf
                Thm: gh.toepproj.lit.H.ilbert.ZB.Thm168.Thm
    """

    required_arguments = 0
    has_content = False
    option_spec = {
        "libpaths": unchanged,
    }

    def run(self):
        def parse_list_of_pairs(option_name, key_pattern, value_test):
            given = self.options.get(option_name)
            if not given:
                return {}
            lines = given.split('\n')
            pairs = [[p.strip() for p in line.split(":")] for line in lines]

            # Validate
            def fail(p):
                raise SphinxError(f'In pfsc-defns at {self.get_location()}, bad {option_name} pair: {p}')
            for p in pairs:
                if len(p) != 2:
                    fail(p)
                if not re.match(key_pattern, p[0]):
                    fail(p)
                if not value_test(p[1]):
                    fail(p)

            mapping = {name: value for name, value in pairs}
            return mapping

        def libpath_test(raw):
            try:
                check_libpath('', raw, {})
            except PfscExcep:
                return False
            return True

        lp_defns = parse_list_of_pairs('libpaths', r'\w+$', libpath_test)
        pfsc_env = self.env.proofscape
        assert isinstance(pfsc_env, SphinxPfscEnvironment)
        pfsc_env.lp_defns_by_docname[self.env.docname] = lp_defns

        return []

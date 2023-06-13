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

from sphinx.util.docutils import SphinxDirective

from pfsc.sphinx.sphinx_proofscape.environment import get_pfsc_env
from pfsc.sphinx.sphinx_proofscape.pages import build_libpath_for_rst
from pfsc.lang.modules import build_module_from_text, CachePolicy


class PfscEmbedDirective(SphinxDirective):
    """
    Directive under which you can put arbitrary pfsc module syntax.

    This directive has no visual form, i.e. adds nothing to the Sphinx doctree.
    It can be used as many times as desired, in an rst file. Each time, its
    text is simply parsed as if a pfsc file, and its imports and definitions
    affect the Proofscape module being built by the rst file, in the normal
    way.
    """

    required_arguments = 0
    has_content = True
    option_spec = {
    }

    def run(self):
        env = self.env
        config = env.config
        docname = env.docname
        modpath = build_libpath_for_rst(config, docname, within_page=False)
        pfsc_env = get_pfsc_env(env)
        module = pfsc_env.get_module(modpath)
        version = module.represented_version

        # self.content is an instance of `docutils.statemachine.StringList`.
        # It presents the lines of the content as a list, with left indent stripped.
        text = '\n'.join(self.content)
        build_module_from_text(
            text, modpath,
            version=version, existing_module=module,
            caching=CachePolicy.ALWAYS
        )

        # No presence in the final document.
        return []

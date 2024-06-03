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

from docutils import nodes
from docutils.transforms import Transform


class ExternalLinks(Transform):
    """
    Give all external links the attribute, `target="_blank"`.
    """

    # Put at end of post-processing phase.
    # https://www.sphinx-doc.org/en/master/extdev/appapi.html#sphinx.application.Sphinx.add_transform
    default_priority = 799

    def apply(self):
        for node in self.document.findall(nodes.reference):
            # See sphinx.writers.html5.HTML5Translator.visit_reference().
            # We want to act in exactly the case where that method adds the
            # 'external' class to the <a> tag.
            if node.get('internal') or 'refuri' not in node:
                continue
            else:
                node['target'] = '_blank'

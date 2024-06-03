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

import vertex2tex

from pfsc.constants import VERTEX_KEY_CHAR


def any_math_node(node):
    return isinstance(node, (nodes.math, nodes.math_block))


class VerTeX2TeX(Transform):
    """
    Apply VerTeX --> TeX translation to any and all math and math_block nodes
    that begin or end with the VerTeX keychar "@".

    Authors are advised to put the "@" only at the end, not the start of the
    math mode, as this will almost always avoid rST matching an "email address"
    and turning it into a `mailto`. (Putting it at the start is far more likely
    to trigger this.) In the rare case where you still get a `mailto`, just put
    a space in front of the final "@" to stop this (or use a double "@@").

    If you want a simple rule that will always work, you can always end the
    math mode with ` @$` or `@@$`.
    """

    # Put just after sphinx-math-dollar, which uses priority 500.
    default_priority = 510

    def apply(self):
        all_math = self.document.findall(any_math_node)
        for math_node in all_math:
            text_child = math_node[0]
            t = vertex2tex.translate_snippet(text_child, keychar=VERTEX_KEY_CHAR)
            if t != text_child:
                new_text_child = nodes.Text(t)
                math_node.replace(text_child, new_text_child)

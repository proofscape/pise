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

import pytest

from pfsc.build.repo import RepoInfo
from pfsc.lang.modules import load_module


disp1 = r"""<div class="display">
An integral basis for $k$:

$\{1,\zeta,\zeta^{2},\zeta^{3},\zeta^{4},\zeta^{5}\}$
</div>
"""

disp2 = r"""<div class="display">
Reducing the elements of the integral basis mod $\mathfrak{p}$:

$$\begin{array}{rcl}
1 & \mapsto & 1 \\
\zeta & \mapsto & \zeta \\
\zeta^{2} & \mapsto & \zeta^{2} \\
\zeta^{3} & \mapsto & 1 + 7 \zeta + 6 \zeta^{2} \\
\zeta^{4} & \mapsto & 6 + 10 \zeta + 10 \zeta^{2} \\
\zeta^{5} & \mapsto & 10 + 10 \zeta + 4 \zeta^{2} \\
\end{array}$$

</div>
"""

@pytest.mark.psm
def test_disps_01(app):
    with app.app_context():
        ri = RepoInfo('test.comment.notes')
        ri.checkout('v0.1.0')
        modpath = 'test.comment.notes.H.ilbert.ZB.Thm17'
        mod = load_module(modpath, caching=0)
        anno = mod['Notes']
        anno.get_anno_data()
        wl = anno.get_widget_lookup()

        cases = [
            ('disp1', disp1),
            ('disp2', disp2),
        ]
        for name, expected_html in cases:
            w = wl[f'eg1_{name}']
            d = w.generator
            d.build()
            h = d.html
            assert h == expected_html

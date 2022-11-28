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

from pfsc.handlers.examp import ExampReevaluator
from pfsc.excep import PECode

request_1 = {
    "libpath": "test.foo.bar.expansions.Notes4.eg1_disp2",
    "vers": "v14.0.0",
    "params": {
        "test.foo.bar.expansions.Notes4.eg1_p": "19",
        "test.foo.bar.expansions.Notes4.eg1_frp": "0",
        "test.foo.bar.expansions.Notes4.eg1_k": "cyc(7)"
    }
}

request_2 = {
    "libpath": "test.comment.notes.H.ilbert.ZB.Thm17.Notes.eg1_disp2",
    "vers": "v0.1.0",
    "params": {
        "test.comment.notes.H.ilbert.ZB.Thm17.Notes.eg1_p": "19",
        "test.comment.notes.H.ilbert.ZB.Thm17.Notes.eg1_frp": "0",
        "test.comment.notes.H.ilbert.ZB.Thm17.Notes.eg1_k": "cyc(7)"
    }
}

html_2 = r"""<div class="display">
Reducing the elements of the integral basis mod $\mathfrak{p}$:

$$\begin{array}{rcl}
1 & \mapsto & 1 \\
\zeta & \mapsto & \zeta \\
\zeta^{2} & \mapsto & \zeta^{2} \\
\zeta^{3} & \mapsto & \zeta^{3} \\
\zeta^{4} & \mapsto & \zeta^{4} \\
\zeta^{5} & \mapsto & \zeta^{5} \\
\end{array}$$

</div>
"""


@pytest.mark.skip('For now the ExampReevaluator is a disabled part of the library.')
@pytest.mark.psm
@pytest.mark.req_csrf(False)
def test_reeval_2(app):
    """
    Successful reeval of examp widget.
    """
    with app.app_context():
        er = ExampReevaluator(request_2, 0)
        er.process()
        resp = er.generate_response()
        html = resp['innerHtml']
        assert html == html_2

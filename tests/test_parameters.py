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


import pytest

from pfsc.lang.modules import load_module
from pfsc.build.repo import RepoInfo


@pytest.mark.psm
def test_string_arg_escape(app):
    with app.app_context():
        ri = RepoInfo('test.foo.eg')
        ri.checkout('v3')
        mod = load_module('test.foo.eg.notes', caching=0)
        anno = mod['Notes']
        data = anno.get_anno_data()
        wl = anno.get_widget_lookup()
        import json
        print(json.dumps(data, indent=4))
        W = data["widgets"]
        uid_fmt = 'test-foo-eg-notes-Notes-eg1_%s_WIP'
        cases = (
            # name, num dependencies, strings present in html, strings absent
            ('d', 1, ['a divisor of $n$'], []),
            ('K', 0, ['\\mathbb{Q}(\\theta)'], []),
        )
        for name, num_dep, present, absent in cases:
            w = W[uid_fmt % name]
            deps = w["dependencies"]
            assert len(deps) == num_dep

            widget = wl[f'eg1_{name}']
            p = widget.generator
            p.build()
            html = p.write_chooser_widget()

            for s in present:
                assert html.find(s) >= 0
            for t in absent:
                assert html.find(t) < 0


@pytest.mark.psm
def test_params_01(app):
    """Test Integer and Divisor parameters."""
    with app.app_context():
        ri = RepoInfo('test.foo.eg')
        ri.checkout('v2')
        mod = load_module('test.foo.eg.notes', caching=0)
        anno = mod['Notes']
        #html = anno.get_escaped_html()
        # print(html)
        data = anno.get_anno_data()
        wl = anno.get_widget_lookup()
        #import json
        #print(json.dumps(data, indent=4))
        W = data["widgets"]

        uid_fmt = 'test-foo-eg-notes-Notes-eg1_%s_WIP'

        for name in ['n', 'd1', 'd2', 'd3']:
            widget = wl[f'eg1_{name}']
            p = widget.generator
            p.build()
            html = p.write_chooser_widget()
            W[uid_fmt % name]["chooser_html"] = html

        wn = W["test-foo-eg-notes-Notes-eg1_n_WIP"]
        assert wn["chooser_html"].find("an integer, greater than $5$") > 0

        wd1 = W["test-foo-eg-notes-Notes-eg1_d1_WIP"]
        assert wd1["chooser_html"].find("a divisor of $n$") > 0
        wd1_deps = wd1["dependencies"]
        assert len(wd1_deps) == 1
        assert wd1_deps[0]["libpath"] == "test.foo.eg.notes.Notes.eg1_n"
        assert wd1_deps[0]["direct"] == True

        wd2 = W["test-foo-eg-notes-Notes-eg1_d2_WIP"]
        assert wd2["chooser_html"].find("-9") > 0
        wd2_deps = wd2["dependencies"]
        assert len(wd2_deps) == 0

        wd3 = W["test-foo-eg-notes-Notes-eg1_d3_WIP"]
        assert wd3["chooser_html"].find("a divisor of $n + 2$") > 0
        wd3_deps = wd3["dependencies"]
        assert len(wd3_deps) == 1
        assert wd3_deps[0]["libpath"] == "test.foo.eg.notes.Notes.eg1_n"
        assert wd3_deps[0]["direct"] == True


@pytest.mark.psm
def test_params_02(app):
    """Test Prime parameters."""
    with app.app_context():
        ri = RepoInfo('test.foo.eg')
        ri.checkout('v2')
        mod = load_module('test.foo.eg.notes', caching=0)
        anno = mod['Notes']
        data = anno.get_anno_data()
        wl = anno.get_widget_lookup()
        #import json
        #print(json.dumps(data, indent=4))
        W = data["widgets"]

        uid_fmt = 'test-foo-eg-notes-Notes-eg1_%s_WIP'

        cases = (
            # name, num dependencies, strings present in html, strings absent
            ('p1', 0, ['$= 11$'], []),
            ('p2', 0, ['$= 2$'], []),
            ('p3', 0, ['$= 3$'], []),
            ('p4', 0, ['$= 13$'], ['select class="dd"', 'input class="textfield"']),
            ('p5', 0, ['$= 17$'], ['option class="dd_opt" value="173"', 'input class="textfield"']),
            ('p6', 0, ['$= 101$', 'option class="dd_opt" value="101" selected="selected"'], []),
            ('p7', 1, ['$= 23$', 'option class="dd_opt" value="109"'], ['option class="dd_opt" value="113"']),
        )
        for name, num_dep, present, absent in cases:
            w = W[uid_fmt % name]
            deps = w["dependencies"]
            assert len(deps) == num_dep

            widget = wl[f'eg1_{name}']
            p = widget.generator
            p.build()
            html = p.write_chooser_widget()

            for s in present:
                assert html.find(s) >= 0
            for t in absent:
                assert html.find(t) < 0


@pytest.mark.psm
def test_params_03(app):
    """Test PrimRes parameters."""
    with app.app_context():
        ri = RepoInfo('test.foo.eg')
        ri.checkout('v2')
        mod = load_module('test.foo.eg.notes', caching=0)
        anno = mod['Notes']
        data = anno.get_anno_data()
        wl = anno.get_widget_lookup()
        #import json
        #print(json.dumps(data, indent=4))
        W = data["widgets"]

        uid_fmt = 'test-foo-eg-notes-Notes-eg1_%s_WIP'

        cases = (
            # name, num dependencies, strings present in html, strings absent
            ('r1', 0, ['value="33" class="radio_panel_button"'], []),
            ('r2', 0, ['a primitive residue mod $343$'], []),
            ('r3', 0, ['value="3"'], []),
            ('r4', 1, ['a primitive residue mod $2 p_1^{2}$'], []),
        )
        for name, num_dep, present, absent in cases:
            w = W[uid_fmt % name]
            deps = w["dependencies"]
            assert len(deps) == num_dep

            widget = wl[f'eg1_{name}']
            p = widget.generator
            p.build()
            html = p.write_chooser_widget()

            for s in present:
                assert html.find(s) >= 0
            for t in absent:
                assert html.find(t) < 0


@pytest.mark.psm
def test_params_04(app):
    """Test NumberField parameters."""
    with app.app_context():
        ri = RepoInfo('test.foo.eg')
        ri.checkout('v2')
        mod = load_module('test.foo.eg.notes', caching=0)
        anno = mod['Notes']
        data = anno.get_anno_data()
        wl = anno.get_widget_lookup()
        W = data["widgets"]

        uid_fmt = 'test-foo-eg-notes-Notes-eg1_%s_WIP'

        cases = (
            # name, num dependencies, strings present in html, strings absent
            ('K1', 0, [r'$= \mathbb{Q}(\zeta) \cong \mathbb{Q}[x]/(\Phi_7(x))$'], []),
            ('K2', 0, [r'$= \mathbb{Q}(\zeta) \cong \mathbb{Q}[x]/(\Phi_7(x))$'], []),
            ('K3', 0, [r'$= \mathbb{Q}(\alpha) \cong \mathbb{Q}[t]/(t^{2} + 5)$'], []),
            ('K4', 0, [r'$= \mathbb{Q}[u]/(u^{3} + 4 u - 7)$'], []),
        )
        for name, num_dep, present, absent in cases:
            w = W[uid_fmt % name]
            #import json
            #print(json.dumps(w, indent=4))
            deps = w["dependencies"]
            assert len(deps) == num_dep

            widget = wl[f'eg1_{name}']
            p = widget.generator
            p.build()
            html = p.write_chooser_widget()

            #print(html)
            for s in present:
                assert html.find(s) >= 0
            for t in absent:
                assert html.find(t) < 0


@pytest.mark.psm
def test_params_05(app):
    """Test PrimeIdeal parameters."""
    with app.app_context():
        ri = RepoInfo('test.foo.eg')
        ri.checkout('v2')
        mod = load_module('test.foo.eg.notes', caching=0)
        anno = mod['Notes']
        data = anno.get_anno_data()
        wl = anno.get_widget_lookup()
        W = data["widgets"]

        uid_fmt = 'test-foo-eg-notes-Notes-eg1_%s_WIP'

        cases = (
            # name, num dependencies, strings present in html, strings absent
            ('P1', 1, [r'value="1" display="$(11, \zeta^{3} - 4 \zeta^{2} - 5 \zeta - 1)$"'], []),
            ('P2', 2, [r'value="2" display="$(13, \zeta^{2} + 6 \zeta + 1)$"',
                       r'rpb_selected">$(13, \zeta^{2} + 6 \zeta + 1)$'], []),
        )
        for name, num_dep, present, absent in cases:
            w = W[uid_fmt % name]
            #import json
            #print(json.dumps(w, indent=4))
            deps = w["dependencies"]
            assert len(deps) == num_dep

            widget = wl[f'eg1_{name}']
            p = widget.generator
            p.build()
            html = p.write_chooser_widget()

            #print(html)
            for s in present:
                assert html.find(s) >= 0
            for t in absent:
                assert html.find(t) < 0

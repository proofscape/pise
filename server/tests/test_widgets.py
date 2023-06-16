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

import json

import pytest

from pfsc.excep import PfscExcep, PECode
from pfsc.lang.modules import load_module
from pfsc.build.repo import RepoInfo

widget_data_1 = {
    "test-foo-bar-expansions-Notes1-w10_WIP": {
        "view": "test.foo.bar.results.Pf",
        "type": "CHART",
        'uid': 'test-foo-bar-expansions-Notes1-w10_WIP',
        "src_line": 22,
        "pane_group": "test.foo.bar@WIP.expansions.Notes1:CHART:",
        "versions": {
            "test.foo.bar": "WIP"
        },
        "title_libpath": "test.foo.bar.expansions.Notes1",
        "widget_libpath": "test.foo.bar.expansions.Notes1.w10",
        "icon_type": "nav",
        "version": "WIP"
    },
    "test-foo-bar-expansions-Notes1-w20_WIP": {
        "view": "test.foo.bar.expansions.X",
        "group": 2,
        "type": "CHART",
        'uid': 'test-foo-bar-expansions-Notes1-w20_WIP',
        "src_line": 26,
        "pane_group": "test.foo.bar@WIP.expansions.Notes1:CHART:2",
        "versions": {
            "test.foo.bar": "WIP"
        },
        "title_libpath": "test.foo.bar.expansions.Notes1",
        "widget_libpath": "test.foo.bar.expansions.Notes1.w20",
        "icon_type": "nav",
        "version": "WIP"
    }
}

html_1 = r"""<p>Some enlightening notes...
with a <a class="widget chartWidget test-foo-bar-expansions-Notes1-w10_WIP" href="#">chart widget with <em>cool equation</em> $e^{ i\pi}+1=0$ in the label</a>
This time we give it its own name, and even put it in a different pane group.
<a class="widget chartWidget test-foo-bar-expansions-Notes1-w20_WIP" href="#"></a></p>
"""

# Here we want to see that duplicate widget names are detected.
@pytest.mark.psm
def test_dup_names(app):
    with app.app_context():
        # First advance to v1, where there is a duplicate widget name.
        ri = RepoInfo('test.foo.bar')
        ri.checkout('v1')
        with pytest.raises(PfscExcep) as ei:
            mod = load_module('test.foo.bar.expansions', caching=0)
        assert ei.value.code() == PECode.DUPLICATE_DEFINITION_IN_PFSC_MODULE
        # Now advance to v2, where the error is corrected.
        ri.checkout('v2')
        mod = load_module('test.foo.bar.expansions', caching=0)
        anno = mod['Notes1']
        html = anno.get_escaped_html()
        wd = anno.get_anno_data()["widgets"]
        j = json.dumps(wd, indent=4)
        print(j)
        print(html)
        assert wd == widget_data_1
        assert html == html_1

mod_text_fragment_2 = """\
<chart:w20>[]{
    "this_is": "some",
    "replacement": "data"
}"""

# Try substituting new data for entire original widget data.
@pytest.mark.psm
def test_widget_data_sub(app):
    with app.app_context():
        ri = RepoInfo('test.foo.bar')
        ri.checkout('v2')
        mod = load_module('test.foo.bar.expansions', caching=0)
        bc = mod.getBlockChunker()
        text = bc.write_module_text({
            "test.foo.bar.expansions.Notes1.w20": {
                '': {
                    "this_is": "some",
                    "replacement": "data"
                }
            }
        })
        print()
        print(text)
        assert text.find(mod_text_fragment_2) > 0

mod_text_fragment_3 = """\
<chart:w20>[]{
    "view": "X",
    "group": 3
}"""

# Try substituting new data for part of original widget data.
@pytest.mark.psm
def test_widget_data_sub_3(app):
    with app.app_context():
        ri = RepoInfo('test.foo.bar')
        ri.checkout('v2')
        mod = load_module('test.foo.bar.expansions', caching=0)
        bc = mod.getBlockChunker()
        text = bc.write_module_text({
            "test.foo.bar.expansions.Notes1.w20": {
                "group": 3
            }
        })
        print()
        print(text)
        assert text.find(mod_text_fragment_3) > 0

mod_text_fragment_4 = """\
<chart:w20>[]{
    "view": "X",
    "group": 2,
    "checkboxes": {
        "deducs": "Pf",
        "checked": [
            "Pf.S",
            "Pf.R"
        ]
    }
}"""

# Try a substitution with datapath of length two.
@pytest.mark.psm
def test_widget_data_sub_4(app):
    with app.app_context():
        ri = RepoInfo('test.foo.bar')
        ri.checkout('v3')
        mod = load_module('test.foo.bar.expansions', caching=0)
        bc = mod.getBlockChunker()
        text = bc.write_module_text({
            "test.foo.bar.expansions.Notes1.w20": {
                "checkboxes.checked": ["Pf.S", "Pf.R"]
            }
        })
        print()
        print(text)
        assert text.find(mod_text_fragment_4) > 0

# Try substituting new data for part of original widget data, where thing
# to be replaced is not yet defined at all.
@pytest.mark.psm
def test_widget_data_sub_5(app):
    with app.app_context():
        ri = RepoInfo('test.foo.bar')
        # Move to version 4, where we don't define checkboxes.checked at all.
        ri.checkout('v4')
        mod = load_module('test.foo.bar.expansions', caching=0)
        bc = mod.getBlockChunker()
        text = bc.write_module_text({
            "test.foo.bar.expansions.Notes1.w20": {
                "checkboxes.checked": ["Pf.S", "Pf.R"]
            }
        })
        print()
        print(text)
        assert text.find(mod_text_fragment_4) > 0

@pytest.mark.psm
def test_libpath_resolve(app):
    with app.app_context():
        ri = RepoInfo('test.moo.links')
        ri.checkout('v0.1.0')
        mod = load_module('test.moo.links.anno1', caching=0)
        mod.resolve()
        assert mod['Notes'].widget_seq[0].data['ref'] == 'test.moo.links.deducs1.Foo'


@pytest.mark.psm
def test_local_libpath_resolve(app):
    """
    This time we test relative libpath resolution in cases where we are dereferencing
    from the anno itself, or even just naming a widget defined within the anno directly.
    """
    with app.app_context():
        ri = RepoInfo('test.foo.bar')
        ri.checkout('v10')
        mod = load_module('test.foo.bar.expansions', caching=0)
        mod.resolve()
        assert mod['Notes3'].widget_seq[0].data['altpath'] == 'test.foo.bar.expansions.Notes3.w2'
        assert mod['Notes3'].widget_seq[1].data['altpath'] == 'test.foo.bar.expansions.Notes3.w2'


@pytest.mark.psm
def test_param_widget_1(app):
    with app.app_context():
        ri = RepoInfo('test.foo.eg')
        ri.checkout('v0')
        mod = load_module('test.foo.eg.notes', caching=0)
        mod.resolve()

        # In Notes1, the widgets try to import each other, cyclically.
        with pytest.raises(PfscExcep) as ei:
            anno = mod['Notes1']
            anno.get_anno_data()
        assert ei.value.code() == PECode.DAG_HAS_CYCLE

        # In Notes2, the widgets build okay.
        anno = mod['Notes2']
        data = anno.get_anno_data()
        assert len(data['widgets']) == 2


@pytest.mark.psm
def test_param_widget_2(app):
    """
    Check widget dependencies
    """
    with app.app_context():
        ri = RepoInfo('test.comment.notes')
        ri.checkout('v0.1.0')
        mod = load_module('test.comment.notes.H.ilbert.ZB.Thm17', caching=0)
        mod.resolve()
        anno = mod['Notes']
        html = anno.get_escaped_html()
        data = anno.get_anno_data()
        #print()
        #print(html)
        #print(json.dumps(data, indent=4))

        widget_data = data["widgets"]
        info = [
            ('k', set()),
            ("F", set()),
            ("disp1", {('k', True)}),
            ('p', set()),
            ('frp', {('k', True), ('p', True)}),
            ('disp2', {('k', False), ('p', False), ('frp', True), ('disp1', True)}),
            ('n', {('p', True)}),
            ('m', {('p', True)}),
            ('disp3', {('p', False), ('n', True), ('m', True)}),
            ('disp4', {('p', True), ('n', True), ('m', True)}),
            ('r', {('p', False), ('m', True)}),
        ]
        for name, expected_dep_set in info:
            d = widget_data[f'test-comment-notes-H-ilbert-ZB-Thm17-Notes-eg1_{name}_WIP']
            deps = d["dependencies"]
            actual_dep_set = {(p["libpath"].split("_")[-1], p["direct"]) for p in deps}
            assert actual_dep_set == expected_dep_set


@pytest.mark.psm
def test_disp_widget_1(app):
    """
    Check parsing of display widget build code
    """
    with app.app_context():
        ri = RepoInfo('test.comment.notes')
        ri.checkout('v0.1.0')
        mod = load_module('test.comment.notes.H.ilbert.ZB.Thm17', caching=0)
        mod.resolve()
        anno = mod['Notes']
        data = anno.get_anno_data()
        widget_data = data["widgets"]
        info = [
            ("disp1", 3),
            ('disp2', 1),
            ('disp3', 1),
            ('disp4', 5),
        ]
        for name, expected_num_sections in info:
            d = widget_data[f'test-comment-notes-H-ilbert-ZB-Thm17-Notes-eg1_{name}_WIP']
            assert len(d['build']) == expected_num_sections

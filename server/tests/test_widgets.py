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
from pfsc.lang.modules import load_module, build_module_from_text
from pfsc.build.repo import RepoInfo

widget_data_1 = """{
    "test-foo-bar-expansions-Notes1-w10_WIP": {
        "view": "test.foo.bar.results.Pf",
        "type": "CHART",
        "src_line": 22,
        "widget_libpath": "test.foo.bar.expansions.Notes1.w10",
        "uid": "test-foo-bar-expansions-Notes1-w10_WIP",
        "pane_group": "test.foo.bar@WIP.expansions.Notes1:CHART:",
        "versions": {
            "test.foo.bar": "WIP"
        },
        "title_libpath": "test.foo.bar.expansions.Notes1",
        "icon_type": "nav",
        "version": "WIP"
    },
    "test-foo-bar-expansions-Notes1-w20_WIP": {
        "view": "test.foo.bar.expansions.X",
        "group": 2,
        "type": "CHART",
        "src_line": 26,
        "widget_libpath": "test.foo.bar.expansions.Notes1.w20",
        "uid": "test-foo-bar-expansions-Notes1-w20_WIP",
        "pane_group": "test.foo.bar@WIP.expansions.Notes1:CHART:2",
        "versions": {
            "test.foo.bar": "WIP"
        },
        "title_libpath": "test.foo.bar.expansions.Notes1",
        "icon_type": "nav",
        "version": "WIP"
    }
}"""

html_1 = r"""<p>Some enlightening notes...
with a <a class="widget chartWidget test-foo-bar-expansions-Notes1-w10_WIP" href="#">chart widget with <em>cool equation</em> $e^{ i\pi}+1=0$ in the label</a>
This time we give it its own name, and even put it in a different pane group.
<a class="widget chartWidget test-foo-bar-expansions-Notes1-w20_WIP" href="#"></a></p>
"""

@pytest.mark.psm
def test_dup_names(app):
    with app.app_context():
        ri = RepoInfo('test.foo.bar')
        ri.checkout('v2')
        mod = load_module('test.foo.bar.expansions', caching=0)
        mod.resolve()
        anno = mod['Notes1']
        html = anno.get_escaped_html()
        wd = anno.get_page_data()["widgets"]
        j = json.dumps(wd, indent=4)
        print(html)
        print(j)
        assert html == html_1
        assert j == widget_data_1

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

        # In Notes1, the widgets try to import each other, cyclically.
        with pytest.raises(PfscExcep) as ei:
            anno = mod['Notes1']
            anno.resolve()
        assert ei.value.code() == PECode.DAG_HAS_CYCLE

        # In Notes2, the widgets build okay.
        anno = mod['Notes2']
        anno.resolve()
        data = anno.get_page_data()
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
        data = anno.get_page_data()
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
        data = anno.get_page_data()
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


@pytest.mark.psm
def test_doc_ref_malformed(app):
    """
    Catch error where docref begins with "#" char.
    """
    with app.app_context():
        text = """
        docInfo = {docId: "pdffp:0123456789abcdef"}
        anno Notes @@@
        Here is <doc:>[a widget]{
            doc: docInfo,
            sel: "#v2;s3;(1:1758:2666:400:200:100:50)"
        }
        @@@
        """
        with pytest.raises(PfscExcep) as ei:
            mod = build_module_from_text(text, 'test._foo._bar')
            mod.resolve()
        assert ei.value.code() == PECode.MALFORMED_DOC_REF_CODE


test_widget_group_spec_module_template = """
anno Notes @@@
Here is <chart:>[a widget]{
    "group": %s,
}
@@@
"""


@pytest.mark.psm
@pytest.mark.parametrize("group_spec, expected_err_code", [
    ['"this_spec_is_too_long_this_spec_is_too_long_this_spec_is_too_long_this_spec_is_too_long"',
     PECode.WIDGET_GROUP_NAME_TOO_LONG],
    ['"...this_has_too_many_dots"',
     PECode.PARENT_DOES_NOT_EXIST],
])
def test_widget_group_spec_err(app, group_spec, expected_err_code):
    """
    Check various errors in widget group spec formats.
    """
    with app.app_context():
        text = test_widget_group_spec_module_template % group_spec
        with pytest.raises(PfscExcep) as ei:
            mod = build_module_from_text(text, 'test._foo._bar')
            mod.resolve()
        assert ei.value.code() == expected_err_code


@pytest.mark.psm
@pytest.mark.parametrize("group_spec, expected_group_id", [
    # No leading dots. Namespace is the anno.
    ['"foo"', 'test._foo._bar@WIP.Notes:CHART:foo'],
    # One leading dot. Namespace is the module; dot is pruned from name.
    ['".foo"', 'test._foo._bar@WIP:CHART:foo'],
])
def test_widget_group_spec(app, group_spec, expected_group_id):
    """
    Check valid formats for widget group spec.
    """
    with app.app_context():
        text = test_widget_group_spec_module_template % group_spec
        mod = build_module_from_text(text, 'test._foo._bar')
        mod.resolve()  # This is where widget data gets enriched.
        anno = mod['Notes']
        widget = anno.widget_seq[0]
        group_id = widget.data['pane_group']
        assert group_id == expected_group_id

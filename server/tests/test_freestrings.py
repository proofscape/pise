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

import json, os

import pytest

from pfsc.lang.freestrings import (
    render_markdown,
    json_parser,
    PfscJsonTransformer,
    split_on_widgets,
    render_anno_markdown,
)
from pfsc.build.repo import RepoInfo
from pfsc.lang.modules import load_module
from pfsc.lang.annotations import Annotation
from pfsc.constants import TEST_RESOURCE_DIR
from pfsc.excep import PfscExcep, PECode

# ----------------------------------------------------------------------

md_input_1 = "foo $a_1, a_2$ bar _emphasis_"
html_output_1 = "<p>foo $a_1, a_2$ bar <em>emphasis</em></p>\n"

def test_md_1():
    """
    Test that math mode takes precedence over italics.
    In particular, on the input,
         foo $a_1, a_2$ bar
    we should _not_ get
         foo $a<i>1, a</i>2$ bar
    """
    h = render_markdown(md_input_1)
    print()
    print(h)
    assert h == html_output_1

# ----------------------------------------------------------------------

md_input_2 = """
![image?](https://example.org/img/Euclid.png)

![image?](https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Mandel_zoom_00_mandelbrot_set.jpg/320px-Mandel_zoom_00_mandelbrot_set.jpg)

[link](https://proofscape.org)

[link](http://proofscape.org)

[link](javascript:alert('Bar!');)
"""

html_output_2a = """\
<p><img src="https://example.org/img/Euclid.png" alt="image?" /></p>
<p><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Mandel_zoom_00_mandelbrot_set.jpg/320px-Mandel_zoom_00_mandelbrot_set.jpg" alt="image?" /></p>
<p><a target="_blank" class="external" href="https://proofscape.org">link</a></p>
<p><a target="_blank" class="external" href="http://proofscape.org">link</a></p>
<p>&lt;a target=&quot;_blank&quot; class=&quot;external&quot; href=&quot;javascript:alert(%27Bar%21%27)%3B&quot;&gt;link&lt;/a&gt;</p>
"""

html_output_2b = """\
<p>&lt;img src=&quot;https://example.org/img/Euclid.png&quot; alt=&quot;image?&quot; /&gt;</p>
<p><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Mandel_zoom_00_mandelbrot_set.jpg/320px-Mandel_zoom_00_mandelbrot_set.jpg" alt="image?" /></p>
<p><a target="_blank" class="external" href="https://proofscape.org">link</a></p>
<p><a target="_blank" class="external" href="http://proofscape.org">link</a></p>
<p>&lt;a target=&quot;_blank&quot; class=&quot;external&quot; href=&quot;javascript:alert(%27Bar%21%27)%3B&quot;&gt;link&lt;/a&gt;</p>
"""

@pytest.mark.parametrize("T, E", [
    [True, html_output_2a],
    [False, html_output_2b],
])
def test_md_2(T, E):
    """
    Test our default link and image policies for trusted/untrusted repos.

    At present this means:
      - links to anywhere are allowed in any repo, as long as they use an approved
        protocol, namely http or https
      - images are allowed from anywhere in trusted repos, but only from wikimedia.org
        in untrusted repos
    """
    h = render_markdown(md_input_2, trusted=T)
    print()
    print(h)
    print(E)
    assert h == E

# ----------------------------------------------------------------------

md_input_3 = """
Is this text <b>bold</b> via passthrough?

<script>alert('Foo!');</script>
"""

html_output_3 = """\
<p>Is this text &lt;b&gt;bold&lt;/b&gt; via passthrough?</p>
<p>&lt;script&gt;alert('Foo!');&lt;/script&gt;</p>
"""

def test_md_3():
    """
    Test that HTML does NOT pass through.
    """
    h = render_markdown(md_input_3)
    print()
    print(h)
    assert h == html_output_3

# ----------------------------------------------------------------------

md_input_4 = """
<https://proofscape.org>

[](http://proofscape.org)
"""

html_output_4 = """\
<p>&lt;https://proofscape.org&gt;</p>
<p><a target="_blank" class="external" href="http://proofscape.org">http://proofscape.org</a></p>
"""

def test_md_4():
    """
    Test that <URL> links don't work, but that [](URL) works as a replacement.
    """
    h = render_markdown(md_input_4)
    print()
    print(h)
    assert h == html_output_4

# ----------------------------------------------------------------------

def text_2_anno(text):
    return Annotation('foo', [], text, None)

widget_attacks = [
"""
This widget is malformed: <chart:>[bad label: <script>alert('foo');</script>]{
    <script>alert('bar');</script>
}
""",
"""
This widget is of unknown type: <foo:>[bad label: <script>alert('foo');</script>]{
    "name": "foo",
    "bad-script": "<script>alert('bar');</script>"
}
""",
"""
This widget is of known type: <chart:>[<script>alert('foo');</script>]{
    "name": "foo",
    "bad-script": "<script>alert('bar');</script>"
}
"""
]
@pytest.mark.parametrize('md', widget_attacks)
def test_widget_attacks(app, md):
    """
    Test that widgets cannot be used as attack vectors.
    """
    with app.app_context():
        anno = text_2_anno(md)
        anno.build()
        anno.cascadeLibpaths()
        out = anno.get_escaped_html()
        print()
        print(out)
        # Assert that a fully-formed script tag did _not_ survive:
        assert out.find('<script>') == -1

# ----------------------------------------------------------------------

transformer = PfscJsonTransformer()

def build_json(text):
    tree = json_parser.parse(text)
    return transformer.transform(tree)

@pytest.mark.parametrize("j, p", [
    [r"'Foo\'s bar'", "Foo&#39;s bar"],
    [r'"\"Foo\" bar"', '&#34;Foo&#34; bar'],
    [r"""'''bar'''""", 'bar'],
    [r"""'''bar's cat'''""", 'bar&#39;s cat'],
    [r"""'''bar's cat ''foo'''""", 'bar&#39;s cat &#39;&#39;foo'],
    [r'''"""bar"""''', 'bar'],
    [r'''"""bar "cat" meow"""''', 'bar &#34;cat&#34; meow'],
    [r'''"""bar "cat" meow ""foo"""''', 'bar &#34;cat&#34; meow &#34;&#34;foo'],
])
def test_json_1(j, p):
    """
    Test basic string handling:
        * delimiters are stripped;
        * escaped delimiters inside are replaced (first by taking away
          the backslash, and then by HTML escaping).
    """
    data = build_json(j)
    print()
    print(data)
    print(p)
    assert data == p

# ----------------------------------------------------------------------

json_input_2 = """{
    foo: "<script>alert('Bar!');</script> &c.",
    ineq: '$@alp < bet$'
}"""

json_output_2 = r"""{
    "foo": "&lt;script&gt;alert(&#39;Bar!&#39;);&lt;/script&gt; &amp;c.",
    "ineq": "$\\alpha&lt;\\beta$"
}"""

def test_json_2():
    """
    Test VerTeX translation and HTML escaping in strings occurring
    within a JSON object.
    """
    data = build_json(json_input_2)
    d = json.dumps(data, indent=4)
    print()
    print(d)
    assert d == json_output_2

# ----------------------------------------------------------------------

anno_text_1 = """
Blah blah, surrounding text <widget_type:widget_name>[label text for widget, *where markdown is okay too*]{
    "here": "you give the data",
    "that": [
        "defines", "the", "widget"
    ],
    "in": {
        "javascript": 1,
        "object": 2,
        "notation": 3
    }
} and then some more surrounding text, blah blah blah.
"""

def test_widget_split_1():
    """
    Test splitting on our basic example from the doctext
    of the split_on_widgets function.
    """
    A, B, C = split_on_widgets(anno_text_1)
    print()
    print(A)
    print(B.data)
    print(C)
    data = build_json(B.data)
    assert data['in']['object'] == 2
    assert data['that'][1] == 'the'
    assert A.split()[1] == 'blah,'
    assert C.split()[2] == 'some'

# ----------------------------------------------------------------------

anno_text_2 = """
This <time:>[we have]{
    some: 'extra } tricky',
    strings: "that have open { and close } braces"
} in them.
"""

def test_widget_split_2():
    """
    Test that (a) braces occurring in strings (of either delimiter) do not
    trick us into thinking that the widget data part is over; and (b) that
    we generate a name for a widget that lacks one.
    """
    A, B, C = split_on_widgets(anno_text_2)
    print()
    print(A)
    print(B.data)
    print(C)
    data = build_json(B.data)
    assert B.name == 'w1'
    assert len(data.keys()) == 2

# ----------------------------------------------------------------------

def test_supply_names():
    """
    Test that we supply missing widget names.
    """
    with open(os.path.join(TEST_RESOURCE_DIR, 'md', 'missing_names.md')) as f:
        md = f.read()
    parts = split_on_widgets(md)
    # Should be eight widgets, so 17 parts.
    assert len(parts) == 17
    # Let's see the widget names:
    names = []
    print()
    for k in range(8):
        rwd = parts[2*k+1]
        print(rwd.name)
        names.append(rwd.name)
    expected = [2, 1, 3, 4, 6, 5, 7, 8]
    for name, n in zip(names, expected):
        assert name == 'w%s' % n

def test_no_supply_names():
    """
    Test requirement that all widgets have names
    """
    with open(os.path.join(TEST_RESOURCE_DIR, 'md', 'missing_names.md')) as f:
        md = f.read()
    with pytest.raises(PfscExcep) as ei:
        split_on_widgets(md, supply_missing_names=False)
    pe = ei.value
    print('\n', pe)
    assert pe.code() == PECode.WIDGET_MISSING_NAME


# ----------------------------------------------------------------------

class MockWidget:

    def __init__(self, template):
        self.template = template

    def writeHTML(self, label=''):
        return self.template.format(label)

anno_stub_text_1 = """
This simulates some anno text after widgets have been
replaced with [**stub**]{w1} widgets.

It also tries to use <b>HTML pass-through</b>, but that
should not work.

It also names a widget [hello?]{noSuchWidget} that does
not exist.
"""

mock_widgets_1 = {
    'w1': MockWidget('<span class="fancyWidgetClass">{}</span>')
}

render_anno_output_1 = """\
<p>This simulates some anno text after widgets have been
replaced with <span class="fancyWidgetClass"><strong>stub</strong></span> widgets.</p>
<p>It also tries to use &lt;b&gt;HTML pass-through&lt;/b&gt;, but that
should not work.</p>
<p>It also names a widget MISSING_WIDGET:[...]{noSuchWidget} that does
not exist.</p>
"""

def test_render_anno_md_1():
    h = render_anno_markdown(anno_stub_text_1, mock_widgets_1)
    print()
    print(h)
    assert h == render_anno_output_1

# ----------------------------------------------------------------------

# An example with a widget, and with both VerTeX and Markdown within the widget label:
foo_bar_widget_html = r"""<p>Some enlightening notes...
with a <a class="widget chartWidget test-foo-bar-expansions-Notes1-w10_WIP" href="#">chart widget with <em>cool equation</em> $e^{ i\pi}+1=0$ in the label</a></p>
"""

foo_bar_widget_data = {
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
    }
}

@pytest.mark.psm
def test_full_compile_1(app):
    with app.app_context():
        # First make sure the repo is on v0
        ri = RepoInfo('test.foo.bar')
        ri.checkout('v0')
        # See that we correctly build a module with an annotation containing a widget.
        mod = load_module('test.foo.bar.expansions', caching=0)
        anno = mod['Notes1']
        html = anno.get_escaped_html()
        wd = anno.get_anno_data()['widgets']
        j = json.dumps(wd, indent=4)
        print(j)
        print(html)
        assert j == json.dumps(foo_bar_widget_data, indent=4)
        assert html == foo_bar_widget_html

# ----------------------------------------------------------------------

anno_text_ctl_0 = ""

anno_text_ctl_1 = """
<ctl:>[]{
    section_numbers: {
        top_level: 1,
    }
}
"""

anno_text_ctl_2 = """
<ctl:>[]{
    section_numbers: {
        top_level: 2,
    }
}
"""
anno_text_section_numbers_1 = """
# H1
## H1.1
### H1.1.1
### H1.1.2
## H1.2
### H1.2.1
## H1.3
# H2
## H2.1
"""

@pytest.mark.parametrize('ctl_text, depth', [
    [anno_text_ctl_0, 999],
    [anno_text_ctl_1, 1],
    [anno_text_ctl_2, 2],
])
def test_section_numbers_1(app, ctl_text, depth):
    with app.app_context():
        anno = Annotation('foo', [], ctl_text + anno_text_section_numbers_1, None)
        anno.build()
        anno.cascadeLibpaths()
        h = anno.get_escaped_html()
        print()
        print(h)
        sep = '&nbsp;&nbsp; H'
        lines = h.split('\n')
        for line in lines:
            assert isinstance(line, str)
            if line.startswith('<h'):
                inner = line[4:-5]
                d = int(line[2:3])
                if d < depth:
                    # No section number
                    assert inner.startswith("H")
                else:
                    p = inner.split(sep)
                    # Section number has right number e of parts.
                    # E.g. if depth == 2, then
                    #   <h3>1.2&nbsp;...
                    # is correct because d = 3 and e = 2
                    e = len(p[0].split('.'))
                    assert e == d - (depth - 1)
                    assert p[1].endswith(p[0])

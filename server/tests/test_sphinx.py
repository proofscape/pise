# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2023 Proofscape contributors                           #
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

"""Tests of sphinx builds. """

import json
import pathlib

from bs4 import BeautifulSoup
from flask import Flask
import pytest

from pfsc.build.repo import get_repo_info
from pfsc.build.manifest import load_manifest
from pfsc.build.products import load_annotation, load_dashgraph
from pfsc.sphinx.sphinx_proofscape.pages import SCRIPT_INTRO, SCRIPT_ID
from pfsc.sphinx.sphinx_proofscape.widgets.util import process_widget_label
from pfsc.excep import PfscExcep


def get_chart_widget_anchors(soup):
    """
    Get the list of any and all <a> tags having class `chartWidget`.
    """
    return list(soup.find_all('a', class_='chartWidget'))


def get_examp_widget_divs(soup):
    """
    Get the list of any and all <div> tags having class `exampWidget`.
    """
    return list(soup.find_all('div', class_='exampWidget'))


def get_qna_widget_divs(soup):
    """
    Get the list of any and all <div> tags having class `qna_widget`.
    """
    return list(soup.find_all('div', class_='qna_widget'))


def get_external_anchors(soup):
    """
    Get the list of any and all <a> tags having class `external`.
    """
    return list(soup.find_all('a', class_='external'))


def get_page_data_from_script_tag(soup):
    """
    If the HTML contains a <script> tag defining pfsc page data, then parse
    the JSON and return the data itself.

    Otherwise return None.
    """
    script = soup.find('script', id=SCRIPT_ID)
    if script:
        text = script.text.strip()
        intro = SCRIPT_INTRO
        if text.startswith(intro):
            rem = text[len(intro):]
            data = json.loads(rem)
            return data
    return None


def get_mathjax_script_tags(soup):
    """
    Find <script> tags, if any, that have 'mathjax' in their `src` attribute.
    """
    return [
        script for script in soup.find_all('script')
        if script.get('src', '').find('mathjax') >= 0
    ]


def get_math_spans(soup):
    """
    Find <span> tags with 'math' class.
    """
    return list(soup.find_all('span', class_='math'))


def get_math_divs(soup):
    """
    Find <div> tags with 'math' class.
    """
    return list(soup.find_all('div', class_='math'))


def get_highlights(soup, language):
    """
    Grab all the highlight divs, for a given language.
    """
    return list(soup.find_all('div', class_=f'highlight-{language}'))


@pytest.mark.parametrize('raw_label, name0, text0', [
    ['foo bar ', None, 'foo bar'],
    ['foo: bar ', 'foo', 'bar'],
    ['myGreatWidget: foo: bar', 'myGreatWidget', 'foo: bar'],
    [': foo: bar', '', 'foo: bar'],
    [':foo: bar', '', 'foo: bar'],

])
def test_process_widget_label(raw_label, name0, text0):
    name1, text1 = process_widget_label(raw_label)
    assert name1 == name0
    assert text1 == text0


@pytest.mark.parametrize('raw_label', [
    '23w: the proof',
])
def test_process_widget_label_exception(raw_label):
    with pytest.raises(PfscExcep):
        process_widget_label(raw_label)


expected_widget_data_spx_doc0 = json.loads("""
{
    "libpath": "test.spx.doc0.index._page",
    "version": "v0.1.0",
    "widgets": {
        "test-spx-doc0-index-_page-w0_v0-1-0": {
            "view": "test.moo.bar.results.Pf",
            "type": "CHART",
            "src_line": 14,
            "widget_libpath": "test.spx.doc0.index._page.w0",
            "uid": "test-spx-doc0-index-_page-w0_v0-1-0",
            "pane_group": "test.spx.doc0@v0_1_0.index._page:CHART:",
            "versions": {
                "test.moo.bar": "v1.0.0"
            },
            "title_libpath": "test.spx.doc0.index._page",
            "icon_type": "nav",
            "version": "v0.1.0"
        }
    },
    "docInfo": {"docs": {}, "refs": {}}
}
""")


def test_generated_pfsc_widget_data_script_tag(app):
    """
    Test that we get the expected widget data script tag.
    """
    # PyCharm seems to be confused, and thinks `app` is a `SphinxTestApp`.
    # So we give it an assertion to convince it that this is our Flask app
    # test fixture.
    assert isinstance(app, Flask)
    with app.app_context():
        libpath = 'test.spx.doc0'
        version = 'v0.1.0'
        ri = get_repo_info(libpath)
        build_dir = ri.get_sphinx_build_dir(version)
        with open(pathlib.Path(build_dir) / 'index.html') as f:
            html = f.read()
        soup = BeautifulSoup(html, 'html.parser')
        widget_data = get_page_data_from_script_tag(soup)
        #print(json.dumps(widget_data, indent=4))
        assert widget_data == expected_widget_data_spx_doc0


def test_manifest(app):
    """
    Test that we get the expected structure in the build manifest
    relational model.
    """
    with app.app_context():
        libpath = 'test.spx.doc1'
        version = 'v0.1.0'
        manifest = load_manifest(libpath, version=version)
        root = manifest.get_root_node()

        model = []
        root.build_relational_model(model)
        sphinx_indices = [i for i, item in enumerate(model) if item['type'] == "SPHINX"]
        assert sphinx_indices == [5, 7, 11, 13, 15, 17]


def test_spx_doc1(app):
    """
    Cf `test_sphinx_build()` in the `sphinx-proofscape` project.
    This test now takes over testing on Pages A and C, while Page B is still
    tested there.
    """
    with app.app_context():
        libpath = 'test.spx.doc1'
        version = 'v0.1.0'
        ri = get_repo_info(libpath)
        build_dir = pathlib.Path(ri.get_sphinx_build_dir(version))

        # Page A
        # ======
        html = (build_dir / 'pageA.html').read_text()
        soup = BeautifulSoup(html, 'html.parser')
    
        # Have exactly one chart widget anchor tag, and it has a class encoding its UID.
        A = get_chart_widget_anchors(soup)
        assert len(A) == 1
        assert 'test-spx-doc1-pageA-_page-proof1_v0-1-0' in A[0].get('class')

        D = get_qna_widget_divs(soup)
        assert len(D) == 1
        assert f'test-spx-doc1-pageA-_page-ultimateQuestion_v0-1-0' in D[0].get('class')
    
        # Defines the expected pfsc_page_data
        page_data = get_page_data_from_script_tag(soup)
        # print('\n', json.dumps(page_data, indent=4))
        assert page_data == PAGE_A_PAGE_DATA

        mjs = get_mathjax_script_tags(soup)
        assert len(mjs) == 1
        ms = get_math_spans(soup)
        assert len(ms) == 9
        md = get_math_divs(soup)
        assert len(md) == 4

        # Page B
        # ======
        # We don't check much: just confirm that syntax highlighting is indeed
        # happening (which proves we're using the external sphinx-proofscape
        # pkg for this, since we don't define lexers locally).
        html = (build_dir / 'pageB.html').read_text()
        soup = BeautifulSoup(html, 'html.parser')
        hl = get_highlights(soup, 'proofscape')
        assert len(hl) == 1

        mjs = get_mathjax_script_tags(soup)
        assert len(mjs) == 0
        
        # Page C
        # ======
        html = (build_dir / 'foo/pageC.html').read_text()
        soup = BeautifulSoup(html, 'html.parser')
    
        # Get the expected anchor tags:
        A = get_chart_widget_anchors(soup)
        for a, expected_name, expected_label in zip(A, PAGE_C_WIDGET_NAMES, PAGE_C_WIDGET_LABELS):
            assert f'test-spx-doc1-foo-pageC-_page-{expected_name}_v0-1-0' in a.get('class')
            assert a.text == expected_label
    
        # Get the expected pfsc_page_data:
        page_data = get_page_data_from_script_tag(soup)
        #print('\n', json.dumps(page_data, indent=4))
        assert page_data == PAGE_C_PAGE_DATA

        # Page D
        # ======
        html = (build_dir / 'foo/pageD.html').read_text()
        soup = BeautifulSoup(html, 'html.parser')

        # Get the expected anchor tags:
        A = get_chart_widget_anchors(soup)
        for a, expected_name, expected_label in zip(A, PAGE_D_WIDGET_NAMES, PAGE_D_WIDGET_LABELS):
            assert f'test-spx-doc1-foo-pageD-_page-{expected_name}_v0-1-0' in a.get('class')
            assert a.text == expected_label

        # Get the expected pfsc_page_data:
        page_data = get_page_data_from_script_tag(soup)
        # print('\n', json.dumps(page_data, indent=4))
        assert page_data == PAGE_D_PAGE_DATA

        # Page E
        # ======
        html = (build_dir / 'foo/pageE.html').read_text()
        soup = BeautifulSoup(html, 'html.parser')

        A = get_external_anchors(soup)
        assert len(A) == 2
        for a in A:
            assert a['target'] == '_blank'

        D = get_examp_widget_divs(soup)
        for d, expected_name in zip(D, PAGE_E_WIDGET_NAMES):
            assert f'test-spx-doc1-foo-pageE-_page-{expected_name}_v0-1-0' in d.get('class')

        # Get the expected pfsc_page_data:
        page_data = get_page_data_from_script_tag(soup)
        # print('\n', json.dumps(page_data, indent=4))
        assert page_data == PAGE_E_PAGE_DATA


PAGE_A_PAGE_DATA = {
    "libpath": "test.spx.doc1.pageA._page",
    "version": "v0.1.0",
    "widgets": {
        "test-spx-doc1-pageA-_page-proof1_v0-1-0": {
            "view": "test.moo.bar.results.Pf",
            "type": "CHART",
            "src_line": 11,
            "widget_libpath": "test.spx.doc1.pageA._page.proof1",
            "uid": "test-spx-doc1-pageA-_page-proof1_v0-1-0",
            "pane_group": "test.spx.doc1@v0_1_0.pageA._page:CHART:",
            "versions": {
                "test.moo.bar": "v1.0.0"
            },
            "title_libpath": "test.spx.doc1.pageA._page",
            "icon_type": "nav",
            "version": "v0.1.0"
        },
        "test-spx-doc1-pageA-_page-ultimateQuestion_v0-1-0": {
            "question": "What is the answer?",
            "answer": "42",
            "type": "QNA",
            "src_line": 15,
            "widget_libpath": "test.spx.doc1.pageA._page.ultimateQuestion",
            "uid": "test-spx-doc1-pageA-_page-ultimateQuestion_v0-1-0",
            "version": "v0.1.0"
        }
    },
    "docInfo": {
        "docs": {},
        "refs": {}
    }
}

PAGE_C_WIDGET_NAMES = [
    '_w0', '_w1', 'w000', '_w2', 'w001', 'w002'
]

PAGE_C_WIDGET_LABELS = [
    'chart widget',
    'chart widgets',
    'substitutions',
    'like: this one',
    'one-line color definition',
    'color defn with: repeated LHS, plus use of update',
]

PAGE_C_PAGE_DATA = {
    "libpath": "test.spx.doc1.foo.pageC._page",
    "version": "v0.1.0",
    "widgets": {
        "test-spx-doc1-foo-pageC-_page-_w0_v0-1-0": {
            "view": "test.moo.bar.results.Pf",
            "type": "CHART",
            "src_line": 13,
            "widget_libpath": "test.spx.doc1.foo.pageC._page._w0",
            "uid": "test-spx-doc1-foo-pageC-_page-_w0_v0-1-0",
            "pane_group": "test.spx.doc1@v0_1_0.foo.pageC._page:CHART:",
            "versions": {
                "test.moo.bar": "v1.0.0"
            },
            "title_libpath": "test.spx.doc1.foo.pageC._page",
            "icon_type": "nav",
            "version": "v0.1.0"
        },
        "test-spx-doc1-foo-pageC-_page-_w1_v0-1-0": {
            "view": "test.moo.bar.results.Thm",
            "type": "CHART",
            "src_line": 15,
            "widget_libpath": "test.spx.doc1.foo.pageC._page._w1",
            "uid": "test-spx-doc1-foo-pageC-_page-_w1_v0-1-0",
            "pane_group": "test.spx.doc1@v0_1_0.foo.pageC._page:CHART:",
            "versions": {
                "test.moo.bar": "v1.0.0"
            },
            "title_libpath": "test.spx.doc1.foo.pageC._page",
            "icon_type": "nav",
            "version": "v0.1.0"
        },
        "test-spx-doc1-foo-pageC-_page-_w2_v0-1-0": {
            "alt": ": like: this one",
            "view": [
                "test.moo.bar.results.Pf"
            ],
            "type": "CHART",
            "src_line": 38,
            "widget_libpath": "test.spx.doc1.foo.pageC._page._w2",
            "uid": "test-spx-doc1-foo-pageC-_page-_w2_v0-1-0",
            "pane_group": "test.spx.doc1@v0_1_0.foo.pageC._page:CHART:",
            "versions": {
                "test.moo.bar": "v1.0.0"
            },
            "title_libpath": "test.spx.doc1.foo.pageC._page",
            "icon_type": "nav",
            "version": "v0.1.0"
        },
        "test-spx-doc1-foo-pageC-_page-w000_v0-1-0": {
            "alt": "w000: substitutions",
            "view": [
                "test.moo.bar.results.Thm.C",
                "test.moo.bar.results.Pf.R",
                "test.moo.bar.results.Pf.S"
            ],
            "on_board": "test.moo.comment.bar.xpan_S",
            "off_board": "test.moo.comment.bar.xpan_T",
            "color": {
                ":olB": [
                    "test.moo.bar.results.Pf.R",
                    "test.moo.bar.results.Pf.S"
                ],
                ":bgG": [
                    "test.moo.bar.results.Thm.C"
                ]
            },
            "type": "CHART",
            "src_line": 41,
            "widget_libpath": "test.spx.doc1.foo.pageC._page.w000",
            "uid": "test-spx-doc1-foo-pageC-_page-w000_v0-1-0",
            "pane_group": "test.spx.doc1@v0_1_0.foo.pageC._page:CHART:",
            "versions": {
                "test.moo.comment": "v0.1.0",
                "test.moo.bar": "v1.0.0"
            },
            "title_libpath": "test.spx.doc1.foo.pageC._page",
            "icon_type": "nav",
            "version": "v0.1.0"
        },
        "test-spx-doc1-foo-pageC-_page-w001_v0-1-0": {
            "alt": "w001: one-line color definition",
            "view": [
                "test.moo.bar.results.Pf"
            ],
            "color": {
                ":olB": [
                    "test.moo.bar.results.Pf.R",
                    "test.moo.bar.results.Pf.S"
                ]
            },
            "type": "CHART",
            "src_line": 49,
            "widget_libpath": "test.spx.doc1.foo.pageC._page.w001",
            "uid": "test-spx-doc1-foo-pageC-_page-w001_v0-1-0",
            "pane_group": "test.spx.doc1@v0_1_0.foo.pageC._page:CHART:",
            "versions": {
                "test.moo.bar": "v1.0.0"
            },
            "title_libpath": "test.spx.doc1.foo.pageC._page",
            "icon_type": "nav",
            "version": "v0.1.0"
        },
        "test-spx-doc1-foo-pageC-_page-w002_v0-1-0": {
            "alt": "w002: color defn with: repeated LHS, plus use of update",
            "color": {
                ":bgG": [
                    "test.moo.bar.results.Pf.R",
                    "test.moo.bar.results.Pf.S",
                    "test.moo.bar.results.Thm.C"
                ],
                ":update": True
            },
            "type": "CHART",
            "src_line": 53,
            "widget_libpath": "test.spx.doc1.foo.pageC._page.w002",
            "uid": "test-spx-doc1-foo-pageC-_page-w002_v0-1-0",
            "pane_group": "test.spx.doc1@v0_1_0.foo.pageC._page:CHART:",
            "versions": {
                "test.moo.bar": "v1.0.0"
            },
            "title_libpath": "test.spx.doc1.foo.pageC._page",
            "icon_type": "nav",
            "version": "v0.1.0"
        }
    },
    "docInfo": {'docs': {}, 'refs': {}}
}

PAGE_D_WIDGET_NAMES = [
    '_w0', 'wDirPdf1',
]

PAGE_D_WIDGET_LABELS = [
    'an inline PDF widget',
    'a directive PDF widget',
]

PAGE_D_PAGE_DATA = {
    "libpath": "test.spx.doc1.foo.pageD._page",
    "version": "v0.1.0",
    "widgets": {
        "test-spx-doc1-foo-pageD-_page-_w0_v0-1-0": {
            "sel": "v2;s3;(1:1758:2666:400:200:100:50);n;x+35;y+4;(1:1758:2666:400:250:110:49)",
            "type": "PDF",
            "src_line": 35,
            "widget_libpath": "test.spx.doc1.foo.pageD._page._w0",
            "uid": "test-spx-doc1-foo-pageD-_page-_w0_v0-1-0",
            "docId": "pdffp:fedcba9876543210",
            "pane_group": "test.spx.doc1@v0_1_0.foo.pageD._page:PDF:pdffp:fedcba9876543210:",
            "highlightId": "test.spx.doc1.foo.pageD._page:test-spx-doc1-foo-pageD-_page-_w0_v0-1-0",
            "url": "https://example.org/pdf/foo1.pdf",
            "version": "v0.1.0"
        },
        "test-spx-doc1-foo-pageD-_page-wDirPdf1_v0-1-0": {
            "alt": "wDirPdf1: a directive PDF widget",
            "sel": "v2;s3;(1:1758:2666:400:200:100:50);n;x+35;y+4;(1:1758:2666:400:250:110:49)",
            "type": "PDF",
            "src_line": 40,
            "widget_libpath": "test.spx.doc1.foo.pageD._page.wDirPdf1",
            "uid": "test-spx-doc1-foo-pageD-_page-wDirPdf1_v0-1-0",
            "docId": "pdffp:fedcba9876543210",
            "pane_group": "test.spx.doc1@v0_1_0.foo.pageD._page:PDF:pdffp:fedcba9876543210:",
            "highlightId": "test.spx.doc1.foo.pageD._page:test-spx-doc1-foo-pageD-_page-wDirPdf1_v0-1-0",
            "url": "https://example.org/pdf/foo1.pdf",
            "version": "v0.1.0"
        }
    },
    "docInfo": {
        "docs": {
            "pdffp:fedcba9876543210": {
                "url": "https://example.org/pdf/foo1.pdf",
                "docId": "pdffp:fedcba9876543210"
            }
        },
        "refs": {
            "pdffp:fedcba9876543210": [
                {
                    "ccode": "v2;s3;(1:1758:2666:400:200:100:50);n;x+35;y+4;(1:1758:2666:400:250:110:49)",
                    "siid": "test-spx-doc1-foo-pageD-_page-_w0_v0-1-0",
                    "slp": "test.spx.doc1.foo.pageD._page",
                    "stype": "SPHINX"
                },
                {
                    "ccode": "v2;s3;(1:1758:2666:400:200:100:50);n;x+35;y+4;(1:1758:2666:400:250:110:49)",
                    "siid": "test-spx-doc1-foo-pageD-_page-wDirPdf1_v0-1-0",
                    "slp": "test.spx.doc1.foo.pageD._page",
                    "stype": "SPHINX"
                }
            ]
        }
    }
}

PAGE_E_WIDGET_NAMES = [
    'eg1_k', 'eg1_disp1',
]

PAGE_E_PAGE_DATA = {
    "libpath": "test.spx.doc1.foo.pageE._page",
    "version": "v0.1.0",
    "widgets": {
        "test-spx-doc1-foo-pageE-_page-eg1_k_v0-1-0": {
            "ptype": "NumberField",
            "name": "k",
            "default": "cyc(7)",
            "args": {
                "gen": "zeta",
                "foo": [
                    1,
                    2,
                    3,
                    4
                ],
                "bar": False
            },
            "type": "PARAM",
            "src_line": 15,
            "trusted": False,
            "widget_libpath": "test.spx.doc1.foo.pageE._page.eg1_k",
            "uid": "test-spx-doc1-foo-pageE-_page-eg1_k_v0-1-0",
            "dependencies": [],
            "params": {},
            "version": "v0.1.0"
        },
        "test-spx-doc1-foo-pageE-_page-eg1_disp1_v0-1-0": {
            "export": [
                "B"
            ],
            "build": [
                "",
                "# You can choose the printing format for the elements of the basis.\nfmt = 'alg'\n",
                "B = k.integral_basis(fmt=fmt)\nhtml = \"An integral basis for $k$:\\n\\n\"\nhtml += r\"$\\{\" + ','.join([latex(b, order='old') for b in B]) + r\"\\}$\"\nreturn html"
            ],
            "type": "DISP",
            "src_line": 26,
            "trusted": False,
            "widget_libpath": "test.spx.doc1.foo.pageE._page.eg1_disp1",
            "uid": "test-spx-doc1-foo-pageE-_page-eg1_disp1_v0-1-0",
            "dependencies": [
                {
                    "libpath": "test.spx.doc1.foo.pageE._page.eg1_k",
                    "uid": "test-spx-doc1-foo-pageE-_page-eg1_k_v0-1-0",
                    "type": "PARAM",
                    "direct": True
                }
            ],
            "params": {
                "k": "test.spx.doc1.foo.pageE._page.eg1_k"
            },
            "imports": {},
            "version": "v0.1.0"
        }
    },
    "docInfo": {
        "docs": {},
        "refs": {}
    }
}


def test_import_rst_into_pfsc(app):
    """
    Check that we can import from an rst module into a pfsc module.
    """
    with app.app_context():
        _, j = load_annotation('test.spx.doc1.anno.Notes', version='v0.1.0')
        d = json.loads(j)
        #print(json.dumps(d, indent=4))
        W = d['widgets']
        link_w1 = W["test-spx-doc1-anno-Notes-w1_v0-1-0"]
        assert link_w1["type"] == "LINK"
        assert link_w1["ref"] == "test.spx.doc1.foo.pageC._page.w000"


def test_repeated_pfsc_directives(app):
    """
    Check that, in an rst module with two or more `pfsc::` directives,
    the entities defined therein accumulate. I.e., we wind up with built
    products for everything defined in all of these directives.
    """
    with app.app_context():
        _, j_a = load_annotation('test.spx.doc1.foo.pageD.Notes1', version='v0.1.0')
        d_a = json.loads(j_a)
        #print(json.dumps(d_a, indent=4))
        assert d_a['libpath'] == 'test.spx.doc1.foo.pageD.Notes1'

        j_d = load_dashgraph('test.spx.doc1.foo.pageD.Thm', version='v0.1.0')
        d_d = json.loads(j_d)
        #print(json.dumps(d_d, indent=4))
        assert d_d['libpath'] == 'test.spx.doc1.foo.pageD.Thm'

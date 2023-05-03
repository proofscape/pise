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

from pfsc.build.repo import get_repo_info
from pfsc.build.manifest import load_manifest


def get_widget_data_from_script_tag(soup):
    """
    If the HTML contains a <script> tag defining pfsc_widget_data, then parse
    the JSON and return the widget data itself.

    Otherwise return None.
    """
    intro = '\nconst pfsc_widget_data = '
    for s in soup.find_all('script'):
        if s.text.startswith(intro):
            rem = s.text[len(intro):]
            data = json.loads(rem)
            return data
    return None


expected_widget_data = json.loads("""
[
    {
        "view": [
            "test.moo.bar.results.Pf"
        ],
        "versions": {
            "test.moo.bar": "v0.3.4"
        },
        "pane_group": "test.spx.doc1@v0.1.0._sphinx.index:CHART:",
        "src_line": 13,
        "type": "CHART",
        "uid": "test-spx-doc1-_sphinx-index-w0_v0.1.0",
        "version": "v0.1.0",
        "widget_libpath": "test.spx.doc1._sphinx.index.w0"
    }
]
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
        libpath = 'test.spx.doc1'
        version = 'v0.1.0'
        ri = get_repo_info(libpath)
        build_dir = ri.get_sphinx_build_dir(version)
        with open(pathlib.Path(build_dir) / 'index.html') as f:
            html = f.read()
        soup = BeautifulSoup(html, 'html.parser')
        widget_data = get_widget_data_from_script_tag(soup)
        assert widget_data == expected_widget_data


def test_manifest(app):
    """
    Test that we get the expected structure in the build manifest,
    and in the relational model.
    """
    with app.app_context():
        libpath = 'test.spx.doc1'
        version = 'v0.1.0'
        manifest = load_manifest(libpath, version=version)
        assert manifest.has_sphinx_doc is True

        root = manifest.get_root_node()
        s = root.children[0]
        assert s.id == f'{libpath}._sphinx'
        assert s.data['type'] == "SPHINX"
        assert s.data['name'] == "Sphinx"

        model = []
        root.build_relational_model(model)
        # Should have exactly one node of type "SPHINX", and it should be the
        # second model element, as the first child of the root node.
        sphinx_indices = [i for i, item in enumerate(model) if item['type'] == "SPHINX"]
        assert sphinx_indices == [1]

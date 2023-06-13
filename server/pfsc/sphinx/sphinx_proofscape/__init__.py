# --------------------------------------------------------------------------- #
#   Sphinx-Proofscape                                                         #
#                                                                             #
#   Copyright (c) 2022-2023 Proofscape contributors                           #
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

from config import PISE_VERSION

from pfsc.sphinx.sphinx_proofscape.environment import (
    setup_pfsc_env, get_pfsc_env, purge_pfsc_env, merge_pfsc_env,
)
from pfsc.sphinx.sphinx_proofscape.pages import (
    form_pfsc_module_for_rst_file, build_libpath_for_rst,
)
from pfsc.sphinx.sphinx_proofscape.nav_widgets import (
    navwidget, visit_navwidget_html, depart_navwidget_html,
)
from pfsc.sphinx.sphinx_proofscape.chart_widget import (
    PfscChartRole, PfscChartDirective,
)
from pfsc.sphinx.sphinx_proofscape.doc_widget import (
    PfscDocRole, PfscDocDirective,
)
# FIXME: delete
from pfsc.sphinx.sphinx_proofscape.defns import PfscDefnsDirective
from pfsc.sphinx.sphinx_proofscape.embed import PfscEmbedDirective

from pfsc.lang.annotations import format_page_data


SCRIPT_INTRO = 'window.pfsc_page_data = '


def write_page_data(app, pagename, templatename, context, event_arg):
    """
    Inject the necessary <script> tag into a document, recording the data for
    any pfsc widgets defined on the page.
    """
    if app.builder.format != 'html':
        return
    pfsc_env = get_pfsc_env(app.env)

    tvl = build_libpath_for_rst(
        app.config, pagename, within_page=True, add_tail_version=True
    )
    libpath, version = tvl.split('@')

    docInfo = None  # TODO

    widgets = {}

    for w in pfsc_env.all_widgets:
        if w.docname == pagename:
            uid = w.write_uid()
            widgets[uid] = w.write_info_dict()

    page_data = format_page_data(libpath, version, widgets, docInfo)
    body = f'\n{SCRIPT_INTRO}{json.dumps(page_data, indent=4)}\n'
    app.add_js_file(None, body=body, id='pfsc-page-data')


def setup(app):
    app.add_config_value('pfsc_repopath', None, 'html')
    app.add_config_value('pfsc_repovers', None, 'html')
    app.add_config_value('pfsc_import_repos', None, 'html')

    app.add_node(navwidget,
                 html=(visit_navwidget_html, depart_navwidget_html))

    app.add_directive('pfsc-defns', PfscDefnsDirective)
    app.add_directive('pfsc', PfscEmbedDirective)

    app.add_role('pfsc-chart', PfscChartRole())
    app.add_directive('pfsc-chart', PfscChartDirective)

    app.add_role('pfsc-doc', PfscDocRole())
    app.add_directive('pfsc-doc', PfscDocDirective)

    app.connect('builder-inited', setup_pfsc_env)
    app.connect('env-purge-doc', purge_pfsc_env)
    app.connect('env-merge-info', merge_pfsc_env)
    app.connect('source-read', form_pfsc_module_for_rst_file)
    app.connect('html-page-context', write_page_data)

    return {
        'version': PISE_VERSION,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }

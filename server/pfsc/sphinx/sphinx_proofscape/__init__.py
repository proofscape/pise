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

from config import PISE_VERSION

from pfsc.sphinx.sphinx_proofscape.pages import (
    form_pfsc_module_for_rst_file,
    setup_pfsc_env, purge_pfsc_env, merge_pfsc_env,
    write_page_data,
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
from pfsc.sphinx.sphinx_proofscape.embed import PfscEmbedDirective


def setup(app):
    app.add_config_value('pfsc_repopath', None, 'html')
    app.add_config_value('pfsc_repovers', None, 'html')

    app.add_node(navwidget,
                 html=(visit_navwidget_html, depart_navwidget_html))

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

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

from config import PISE_VERSION

from pfsc.sphinx.pages import (
    form_pfsc_module_for_rst_file,
    setup_pfsc_env, purge_pfsc_env, merge_pfsc_env,
    inject_page_data,
)
from pfsc.sphinx.widgets import (
    pfsc_block_widget, pfsc_inline_widget,
    visit_pfsc_widget_html, depart_pfsc_widget_html,
    widget_types_and_classes,
)
from pfsc.sphinx.embed import PfscEmbedDirective
from pfsc.sphinx.links import ExternalLinks
from pfsc.sphinx.vertex import VerTeX2TeX


def setup(app):
    app.add_config_value('pfsc_repopath', None, 'html')
    app.add_config_value('pfsc_repovers', None, 'html')

    app.add_node(pfsc_block_widget,
                 html=(visit_pfsc_widget_html, depart_pfsc_widget_html))
    app.add_node(pfsc_inline_widget,
                 html=(visit_pfsc_widget_html, depart_pfsc_widget_html))

    app.add_transform(VerTeX2TeX)
    app.add_post_transform(ExternalLinks)

    app.add_directive('pfsc', PfscEmbedDirective)

    for name, role_class, directive_class in widget_types_and_classes:
        full_name = f'pfsc-{name}'
        if role_class:
            role_instance = role_class()
            app.add_role(full_name, role_instance)
        if directive_class:
            app.add_directive(full_name, directive_class)

    app.connect('builder-inited', setup_pfsc_env)
    app.connect('env-purge-doc', purge_pfsc_env)
    app.connect('env-merge-info', merge_pfsc_env)
    app.connect('source-read', form_pfsc_module_for_rst_file)
    app.connect('html-page-context', inject_page_data)

    return {
        'version': PISE_VERSION,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }

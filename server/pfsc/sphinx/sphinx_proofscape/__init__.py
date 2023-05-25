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
from pfsc.sphinx.sphinx_proofscape.lang_exts import (
    chartwidget, visit_chartwidget_html, depart_chartwidget_html,
    PfscChartRole,
    PfscChartDirective,
    PfscDefnsDirective,
)

from pfsc.constants import WIP_TAG
from pfsc.lang.annotations import format_page_data
from pfsc.sphinx.sphinx_proofscape.util import build_libpath
from pfsc.build.versions import version_string_is_valid


###############################################################################
# Standard purge & merge
# See e.g. https://www.sphinx-doc.org/en/master/development/tutorials/todo.html


def purge_pfsc_widgets(app, env, docname):
    if not hasattr(env, 'pfsc_all_widgets'):
        return
    env.pfsc_all_widgets = [w for w in env.pfsc_all_widgets
                                  if w.docname != docname]


def merge_pfsc_widgets(app, env, docnames, other):
    if not hasattr(env, 'pfsc_all_widgets'):
        env.pfsc_all_widgets = []
    if hasattr(other, 'pfsc_all_widgets'):
        env.pfsc_all_widgets.extend(other.pfsc_all_widgets)


###############################################################################


def regularize_version_dict(app):
    """
    Read the version dictionary out of `config.pfsc_import_repos`, regularize
    it, meaning ensure that each value is either WIP or starts with a 'v', and
    then save the regularized version in the env.

    raises: ValueError if any version string is improperly formatted
    """
    vers_defns = app.config.pfsc_import_repos or {}
    r = {}
    for k, v in vers_defns.items():
        if v != WIP_TAG:
            if not v.startswith('v'):
                v = f'v{v}'
            if not version_string_is_valid(v):
                raise ValueError(v)
        r[k] = v
    app.builder.env.pfsc_vers_defns = r


SCRIPT_INTRO = 'window.pfsc_page_data = '


def write_page_data(app, pagename, templatename, context, event_arg):
    """
    Inject the necessary <script> tag into a document, recording the data for
    any pfsc widgets defined on the page.
    """
    if app.builder.format != 'html':
        return
    env = app.builder.env

    tvl = build_libpath(app.config, pagename, add_tail_version=True)
    libpath, version = tvl.split('@')

    docInfo = None  # TODO

    widgets = {}

    if not hasattr(env, 'pfsc_all_widgets'):
        env.pfsc_all_widgets = []

    for w in env.pfsc_all_widgets:
        if w.docname == pagename:
            uid = w.write_uid()
            widgets[uid] = w.write_info_dict()

    page_data = format_page_data(libpath, version, widgets, docInfo)
    body = f'\n{SCRIPT_INTRO}{json.dumps(page_data, indent=4)}\n'
    app.add_js_file(None, body=body, id='pfsc-page-data')


###############################################################################


def setup(app):

    app.add_config_value('pfsc_repopath', None, 'html')
    app.add_config_value('pfsc_repovers', None, 'html')
    app.add_config_value('pfsc_import_repos', None, 'html')

    app.add_node(chartwidget,
                 html=(visit_chartwidget_html, depart_chartwidget_html))

    app.add_role('pfsc-chart', PfscChartRole())
    app.add_directive('pfsc-chart', PfscChartDirective)
    app.add_directive('pfsc-defns', PfscDefnsDirective)

    app.connect('env-purge-doc', purge_pfsc_widgets)
    app.connect('env-merge-info', merge_pfsc_widgets)
    app.connect('builder-inited', regularize_version_dict)
    app.connect('html-page-context', write_page_data)

    return {
        'version': PISE_VERSION,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }

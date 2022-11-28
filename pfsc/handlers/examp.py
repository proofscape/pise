# --------------------------------------------------------------------------- #
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

import json

from pfsc import check_config
from pfsc.handlers import SocketHandler
from pfsc.excep import PfscExcep, PECode
from pfsc.checkinput import IType
from pfsc.build.lib.libpath import libpath_is_trusted
from pfsc.build.products import load_annotation
from pfsc.lang.widgets import make_widget_uid, WidgetTypes, WIDGET_TYPE_TO_CLASS


class WidgetReconstructor:
    """
    For rebuilding Widgets based on their built data.
    """

    def __init__(self, anno_json):
        all_data = json.loads(anno_json)
        self.annopath = all_data["libpath"]
        self.version = all_data["version"]
        self.widget_data = all_data["widgets"]

        self.made_widgets = {}

    # ------------------------------------------------------------
    # Dummy methods to let widgets' `getVersion()` method work:
    def getModule(self):
        return self

    def getVersion(self):
        return self.version
    # ------------------------------------------------------------

    def getFromAncestor(self, path, proper=False, missing_obj_descrip=None):
        # Last ditch attempt to find a widget by a relative libpath from args_lp
        # (See Parameter.resolve_args.)
        for abslp, w in self.made_widgets.items():
            if abslp.endswith(path):
                prefix = abslp[:-len(path)]
                if len(prefix) == 0 or prefix[-1] == '.':
                    return w, self.annopath
        return None, None

    def get_widget_data(self, libpath):
        uid = make_widget_uid(libpath, self.version)
        widget_data = self.widget_data.get(uid)
        if widget_data is None:
            msg = f'Could not find widget `{libpath}`'
            raise PfscExcep(msg, PECode.MODULE_DOES_NOT_CONTAIN_OBJECT)
        return widget_data

    def make_widget(self, data, label='', lineno=0):
        """
        Make a widget based on any data you supply.
        """
        type_ = data['type']
        libpath = data['widget_libpath']
        name = libpath.split('.')[-1]
        ClassName = WIDGET_TYPE_TO_CLASS[type_]
        parent = self
        widget = ClassName(name, label, data, parent, lineno)
        widget.libpath = f'{self.annopath}.{name}'
        self.made_widgets[libpath] = widget
        return widget

    def get_widget(self, libpath, subs=None):
        """
        Make a widget formed from some data that we already have, but with
        optional substitutions.
        """
        data = self.get_widget_data(libpath)
        data.update(subs or {})
        return self.make_widget(data)

    def link_all(self):
        """
        Give all made widgets links to one another, by setting their
        `self.objects_by_abspath` dicts equal to a copy of our own
        `self.made_widgets` dict.
        """
        for widget in self.made_widgets.values():
            widget.objects_by_abspath = self.made_widgets.copy()


class ExampHandler(SocketHandler):
    """
    Server-side examp re-eval is disabled, at least for now (maybe for good?).
    We have moved to using Pyodide in the browser for this.

    Here was the old config var and explanatory text from config.py, which is checked here:

    # Evaluating examp widgets (i.e. param and disp widgets) means passing jobs
    # to the math queue workers based on "moderately freeform" input.
    # Much has been done in the design of the param and disp widgets to try to
    # gracefully handle "bad code"; however, it is the nature of such a system
    # that we will never be able to call it more than "maybe safe". For this
    # reason, the math queue workers are containerized, and there is a strict,
    # short timeout before these jobs are terminated, completed or not. Use
    # this setting to decide whether to evaluate examp widgets from untrusted
    # repos.
    EVAL_EXAMP_WIDGETS_IN_UNTRUSTED_REPOS = bool(int(os.getenv("EVAL_EXAMP_WIDGETS_IN_UNTRUSTED_REPOS", 0)))
    """

    def check_libpath_trusted(self):
        if not check_config("EVAL_EXAMP_WIDGETS_IN_UNTRUSTED_REPOS"):
            checked_libpath = self.fields['libpath']
            lp = checked_libpath.value
            is_trusted = libpath_is_trusted(lp)
            if not is_trusted:
                msg = 'Sorry, cannot evaluate examplorer widget %s from untrusted repo.' % lp
                raise PfscExcep(msg, PECode.LIBPATH_NOT_ALLOWED)
            checked_libpath.is_trusted = is_trusted


class ExampReevaluator(ExampHandler):
    """
    Reevaluate an examp widget.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'libpath': {
                    'type': IType.LIBPATH,
                },
                'vers': {
                    'type': IType.FULL_VERS,
                },
                'params': {
                    'type': IType.DICT,
                    'keytype': {
                        'type': IType.LIBPATH,
                        'value_only': True,
                    },
                    'valtype': {
                        'type': IType.STR,
                    },
                    'default_cooked': {},
                }
            },
            "OPT": {
                'cache_code': {
                    'type': IType.STR,
                    'default_cooked': None,
                }
            }
        })
        self.check_libpath_trusted()

    def check_permissions(self, libpath, vers):
        if vers.isWIP:
            self.check_repo_read_permission(libpath, vers, action='evaluate WIP examp widgets from')

    def go_ahead(self, libpath, vers, params, cache_code):
        widgetpath = libpath.value
        parts = widgetpath.split('.')
        annopath = '.'.join(parts[:-1])
        _, data_json = load_annotation(annopath, cache_code, version=vers.full)

        wr = WidgetReconstructor(data_json)
        target_widget = wr.get_widget(widgetpath)
        required_widgets = []
        deps = target_widget.data["dependencies"]
        for dep in deps:
            lp = dep["libpath"]
            if dep["type"] == WidgetTypes.PARAM:
                if lp not in params:
                    msg = f'Missing required parameter choice for `{lp}`'
                    raise PfscExcep(msg, PECode.MISSING_EXAMPLORE_PARAM)
                subs = {"default": params[lp]}
            else:
                subs = None
            required_widgets.append(wr.get_widget(lp, subs=subs))

        wr.link_all()

        for w in required_widgets:
            w.enrich_data()

        target_widget.enrich_data()

        self.set_response_field('innerHtml', target_widget.innerHtml)

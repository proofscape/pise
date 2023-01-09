# --------------------------------------------------------------------------- #
#   Copyright (c) 2018-2023 Proofscape Contributors                           #
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

import traceback
from markupsafe import escape

from pfsc_examp.contexts import ContextNames
from pfsc_examp.parameters import make_param
from pfsc_examp.parameters.base import Parameter
from pfsc_examp.display import make_disp
from pfsc_examp.excep import ExampError, MalformedParamRawValue
from pfsc_examp.util import adapt
from pfsc_util.imports import from_import


def make_examp_generator_obj_from_js(info, pane_id):
    """
    This is the factory function for Parameters and ExampDisplays, which is
    intended to be invoked from the JS side, in pfsc-ise.

    Note that we deliberately do not call `to_js()` on the return value, because
    we want a PyProxy on the JS side. When one param or display needs to get
    ahold of another, it will be through `PyodideWidgetStandIn.get_generator()`,
    and will be a "round trip conversion" of a Python object
    (see <https://pyodide.org/en/stable/usage/type-conversions.html#round-trip-conversions>)
    which means this PyProxy will simply be unwrapped to recover the original
    object itself.
    """
    info = adapt(info)
    parent = PyodideWidgetStandIn(info, pane_id)
    wtype = info.get('type')
    if wtype == "PARAM":
        obj = make_param(parent, info)
    elif wtype == "DISP":
        obj = make_disp(parent, info)
    else:
        raise ExampError(f"Invalid widget type {wtype}")
    # NOTE: Tried using `create_proxy()` to ensure persistence on the JS side,
    # like this,
    #   create_proxy = from_import('pyodide', 'create_proxy')
    #   proxy = create_proxy(obj)
    #   return proxy
    # but it didn't work. We still got the,
    #   "This borrowed proxy was automatically destroyed at the end of a function call."
    # error when we tried to use `PyodideWidgetStandIn.get_generator()` more than
    # once on the same widget.
    # This is why the `ExampWidget` class in pfsc-ise offers
    # the `getPyProxyCopy()` method, which returns a *copy* of the proxy, so
    # that the original will not be destroyed.
    # The docs,
    #   https://pyodide.org/en/stable/usage/type-conversions.html#calling-javascript-functions-from-python
    # say that either method should work, but for us only making the copy on the
    # JS side worked. This was with Pyodide v0.19.0.
    # See also:
    #   https://github.com/pyodide/pyodide/issues/1607
    return obj


class ErrCode:
    OK = 0
    UNKNOWN = 1
    UNEXPECTED = 2
    # For historical reasons (original error codes in pfsc-server), we're using
    # the original number 193 for this error:
    MALFORMED_PARAM_RAW_VALUE = 193
    EXAMP_ERROR = 4


def rebuild_examp_generator_from_js(obj, value=None, write_html=False):
    to_js = from_import('pyodide', 'to_js')
    d = {
        'err_lvl': ErrCode.UNKNOWN,
        'err_msg': 'unknown error',
    }
    try:
        obj.build(raw=value)
        html = obj.write_html() if write_html else None
    except MalformedParamRawValue as e:
        d['err_lvl'] = ErrCode.MALFORMED_PARAM_RAW_VALUE
        d['err_msg'] = str(e)
        d['blame_widget_uid'] = e.param.getUid()
        d['trace'] = '\n'.join(traceback.format_stack())
    except ExampError as e:
        d['err_lvl'] = ErrCode.EXAMP_ERROR
        d['err_msg'] = str(e)
        d['trace'] = '\n'.join(traceback.format_stack())
    except Exception as e:
        d['err_lvl'] = ErrCode.UNEXPECTED
        d['err_msg'] = str(e)
        d['trace'] = '\n'.join(traceback.format_stack())
    else:
        d['err_lvl'] = 0
        d['err_msg'] = ''
        if write_html:
            d['html'] = html
    # Error messages may contain angle brackets (e.g. when reporting expected
    # type for an argument to an allowed callable), and we want these to
    # display correctly in the browser, so we escape:
    d['err_msg'] = escape(d.get('err_msg', ''))
    return to_js(d)


class PyodideWidgetStandIn:
    """
    For execution in Pyodide, plays the role of a Widget, in its capacity as
    the parent object to a Parameter or ExampDisplay.
    """

    def __init__(self, info, pane_id):
        """
        info: (dict) the widget info, as loaded from the anno JSON
        pane_id: (str) the pane Id where we'll look for sibling examp widgets
        """
        self.info = info
        self.pane_id = pane_id

        self.uid = info['uid']
        self.libpath = info['widget_libpath']
        self.dependencies = info['dependencies']
        self.context = info.get('context', ContextNames.Basic)

        self.lp2uid = {
            d["libpath"] : d["uid"] for d in self.dependencies
        }

        hub = from_import('js', 'pfscisehub')
        self.nm = hub.notesManager

    def get_examp_widget(self, lp):
        uid = self.lp2uid[lp]
        return self.nm.getWidget(uid)

    def get_generator(self, lp):
        w = self.get_examp_widget(lp)
        return w.getPyProxyCopy(self.pane_id)

    def getLibpath(self):
        return self.libpath

    def getUid(self):
        return self.uid

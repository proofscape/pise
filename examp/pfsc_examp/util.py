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

import sys


PYODIDE = ('pyodide' in sys.modules)
PFSCSERVER = ('pfsc' in sys.modules)


def adapt(x):
    """
    Adapt an incoming argument if we're running in Pyodide, and the arg is
    given as a JsProxy. Otherwise leave it unchanged.
    """
    if PYODIDE and hasattr(x, 'to_py'):
        x = x.to_py()
    return x

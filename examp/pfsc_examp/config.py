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

from pfsc_examp.util import (
    PYODIDE,
    PFSCSERVER,
)
from pfsc_util.imports import from_import

# Default values
config = {
    "MAX_SYMPY_EXPR_LEN": 1024,
    "MAX_SYMPY_EXPR_DEPTH": 32,
    "MAX_DISPLAY_BUILD_LEN": 4096,
    "MAX_DISPLAY_BUILD_DEPTH": 32,
}

# Override default values, depending on context
if PFSCSERVER:
    has_app_context, current_app = from_import('flask', ['has_app_context', 'current_app'])
    if has_app_context():
        config = current_app.config
elif PYODIDE:
    pfscExampConfig = from_import('js', 'pfscExampConfig')
    config = pfscExampConfig.to_py()

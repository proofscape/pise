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

"""
This blueprint provides an easy way to generate URLs for static assets defined
here in the pfsc-server project (as opposed to linked from other projects) so
that they include pfsc-server's version number.

For example,

    url_for('vstat.static', filename='css/base.css')

will generate a URL like

    /static/v0.23.6/css/base.css
"""

from flask import Blueprint

from pfsc import __version__


bp = Blueprint(
    'vstat', __name__,
    static_folder='../../static',
    static_url_path=f'static/v{__version__}',
)

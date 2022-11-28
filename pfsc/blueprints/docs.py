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
Routes into the doc modules

For now at least, this is just a place to provide URL-shortening, and
suppression of version numbers, for locations in the docs to which we might
commonly want to link.
"""

from flask import Blueprint, redirect



bp = Blueprint('docs', __name__)


@bp.route('/Tutorial', methods=["GET"])
def zb119_tutorial():
    return redirect('/?sd=c289&tt=b&a=0;0&c=gh.proofscape.docs.pise.tutorial.zb119~b.tutorial~a(g0t0)')

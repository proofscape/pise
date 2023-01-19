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

from pfsc_examp.util import PFSCSERVER
from pfsc_util.imports import from_import


def simple_calc(f, *args, **kwargs):
    return f(*args, **kwargs)


"""
By default, to calculate is simply to apply a function to arguments.
"""
calculate = simple_calc


"""
If we're running in pfsc-server, then we want to use controlled calculation.

EDIT (230119): For now we're disabling this. Server side math jobs are no
longer being used, and now the use of RQ in pise/server unit tests has begun
to cause issues with pickling of certain SymPy types. Probably this old feature
should just be removed.

TODO: Remove support for server-side math jobs.
"""
if PFSCSERVER and False:  # Disabled. See note above.
    calculate = from_import('pfsc_examp.calculate.server_calc', 'calculate')


"""
RQ jobs will not accept a class as the callable. So we need a function we
can call, in order to construct class instances within `calculate`.

E.g.

    f = construct_instance(Poly, x**2 + 1, domain=QQ)

This is only needed when using server_calc, but since we want to write code
that works in any setting, parameter classes should always use it.
"""
construct_instance = simple_calc

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
High-level installation routines.

Sometimes installing a project involves several steps, beyond merely cloning a
single repo. For example, a Python project might depend on a library which
cannot currently be obtained from PyPI, since we require a development branch
which has not yet been released.

Other times the procedure is not complex, but does differ from merely cloning
a repo. For example, a Javascript library may need to be obtained from npm,
instead of cloning and building.

The functions defined here are meant to carry out the steps that may sometimes
be involved in installing a project, in such cases.

UPDATE: At present we have no need of any such commands. The old ones are now
inaccurate, so have been removed.
"""

import os

import click

from manage import cli, PFSC_ROOT

SRC_DIR = os.path.join(PFSC_ROOT, 'src')
STATIC_DIR = os.path.join(PFSC_ROOT, 'static')


@cli.group()
def install():
    """
    Utilities for installing projects.
    """
    pass

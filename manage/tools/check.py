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

import sys

import click

from manage import cli
from tools.util import get_version_numbers


@cli.group()
def check():
    """
    Commands for checking information like version numbers
    """
    pass


@check.command()
@click.argument('project')
def version(project):
    """
    Check the version of a project, by name
    """
    nums = get_version_numbers()
    if project not in nums:
        raise click.UsageError(f'Unknown project: {project}')
    sys.stdout.write(nums[project])

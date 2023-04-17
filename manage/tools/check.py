# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2023 Proofscape Contributors                           #
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
@click.option('-l', is_flag=True, help="List known projects.")
@click.argument('projects', nargs=-1)
def version(l, projects):
    """
    Check the version of one or more projects, by name.

    Result is printed without leading or trailing whitespace.
    If multiple projects are named, versions are comma-separated.
    """
    nums = get_version_numbers(include_tags=True, include_other=True)
    if l:
        print('Projects:')
        for k in sorted(nums.keys()):
            print(f'  {k}')
        return
    versions = []
    for project in projects:
        if project not in nums:
            raise click.UsageError(f'Unknown project: {project}')
        versions.append(nums[project])
    sys.stdout.write(','.join(versions))

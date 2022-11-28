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

import re

import click

from manage import cli
from tools.update import COPYRIGHT_INFO_PER_REPO, LicensableFiles

@cli.command()
@click.argument('repo')
@click.argument('pattern')
def grep(repo, pattern):
    """
    Grep the licensable files of projects.
    """
    if repo == "ALL":
        repos = COPYRIGHT_INFO_PER_REPO.keys()
    elif repo not in COPYRIGHT_INFO_PER_REPO:
        raise click.UsageError(f'Unknown repo {repo}')
    else:
        repos = [repo]

    for repo in repos:
        lf = LicensableFiles(repo)
        for path in lf.paths():
            with open(path) as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                if re.search(pattern, line):
                    line = line.strip('\n')
                    print(f'{path}:{i + 1}: {line}')

# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2024 Proofscape Contributors                           #
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

import os
import pathlib

import click

from manage import cli, PFSC_ROOT, PISE_ROOT
from tools.util import trymakedirs

log = click.echo

@cli.command()
@click.option('-y', '--yes', is_flag=True, help="Proceed without confirmation.")
def makestruct(yes):
    """
    Build the directory structure for Proofscape.

    In order to build the directory structure for Proofscape, `pfsc-manage` needs
    to know where the root directory is to be located.

    If you want to override the default behavior, you may set the location of the
    root directory in the variable `PFSC_ROOT` in your `conf.py`.
    """
    if PFSC_ROOT is None or (isinstance(PFSC_ROOT, str) and len(PFSC_ROOT) == 0):
        raise click.UsageError('PFSC_ROOT undefined.')

    if not yes:
        click.confirm(f'Do you want to install Proofscape in {PFSC_ROOT}?', abort=True)

    if os.path.exists(PFSC_ROOT):
        log(f'Found existing directory {PFSC_ROOT}.')
    else:
        log(f'Making directory {PFSC_ROOT}.')
        trymakedirs(PFSC_ROOT)

    for name in "lib build/cache build/html PDFLibrary graphdb deploy/.ssl src/tmp".split():
        path = os.path.join(PFSC_ROOT, name)
        if os.path.exists(path):
            log(f'Directory {path} already exists.')
        else:
            log(f'Making directory {path}.')
            trymakedirs(path, exist_ok=True)

    links = [
        ('pfsc-server', 'server'),
        ('pfsc-ise', 'client'),
    ]
    for name, target in links:
        p = pathlib.Path(f'{PFSC_ROOT}/src/{name}')
        if p.exists():
            log(f'Found existing link {p}')
        else:
            p.symlink_to(
                pathlib.Path(f'{PISE_ROOT}/{target}'),
                target_is_directory=True
            )
            log(f'Made link {p}')

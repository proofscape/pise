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

import os
import pathlib

import click

import conf
from manage import cli, PFSC_ROOT
from tools.util import do_commands_in_directory, get_version_numbers

SRC_DIR = os.path.join(PFSC_ROOT, 'src')


@cli.group()
def get():
    """
    Utilities for downloading various resources.
    """
    pass


@get.command()
@click.option('-v', '--version', help="Desired version number. Defaults to setting in client/other-versions.json.")
@click.option('--dry-run', is_flag=True, help="Do not actually download; just print commands.")
def pyodide(version, dry_run):
    """
    Download a complete build of Pyodide, at a particular version.
    """
    p_path = pathlib.Path(PFSC_ROOT) / 'src' / 'pyodide'

    versions = get_version_numbers()
    version = version or versions['pyodide']
    v_path = p_path / f'v{version}'
    if v_path.exists():
        raise click.UsageError(f'{v_path} already exists!')

    if not p_path.exists():
        print(f'mkdir -p {p_path}')
        if not dry_run:
            p_path.mkdir(parents=True, exist_ok=True)

    fn = f'pyodide-build-{version}.tar.bz2'
    url = f'https://github.com/pyodide/pyodide/releases/download/{version}/{fn}'
    cmds = [
        f'wget {url}',
        f'tar -xjvf {fn}',
        f'mv pyodide {v_path.name}',
        f'rm {fn}',
    ]
    do_commands_in_directory(cmds, p_path, dry_run=dry_run)


@get.command()
@click.option('-v', '--version', help="Desired version number for pfsc-examp. Defaults to setting in client/other-versions.json.")
@click.option('--release', is_flag=True, help="Set true to save to the whl/release directory.")
@click.option('--dry-run', is_flag=True, help="Do not actually download; just print commands.")
def wheels(version, release, dry_run):
    """
    Download all the whl files needed for the current version of pfsc-examp.
    """
    versions = get_version_numbers()
    version = version or versions['pfsc-examp']
    path = pathlib.Path(PFSC_ROOT) / 'src' / 'whl'
    if release:
        path /= 'release'
    if not path.exists():
        print(f'mkdir -p {path}')
        if not dry_run:
            path.mkdir(parents=True, exist_ok=True)
    cmds = [
        f'pip download pfsc-examp=={version}'
    ]
    do_commands_in_directory(cmds, path, dry_run=dry_run)

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

import json
import os
import re

import click

import conf
from manage import cli, PFSC_ROOT, PFSC_MANAGE_ROOT
import tools.build
from tools.util import (
    get_version_numbers,
    get_server_version,
)

SRC_ROOT = os.path.join(PFSC_ROOT, 'src')


@cli.group()
def release():
    """
    Tools for building docker images for release.
    """
    pass


@release.command()
@click.option(
    '-n', '--seq-num', default=0, type=int,
    help="Sequence number. If positive n, will be appended on tag as `-n`."
)
@click.option(
    '-y', '--skip-check', is_flag=True,
    help="Skip tag check."
)
@click.option('--dump', is_flag=True, help="Dump Dockerfile to stdout before building.")
@click.option('--dry-run', is_flag=True, help="Do not actually build; just print docker command.")
def oca(seq_num, skip_check, dump, dry_run):
    """
    Build a `pise` (one-container app) docker image, for release.

    The tag is generated from the current version number of pfsc-ise, the
    current version number of pfsc-server, and any sequence number you may
    supply. The "current" versions are those currently checked out in the
    repos in the `src` directory.

    Unless you say to skip it, there will be a prompt to check if the tag is
    correct.

    The oca_version.txt file in pfsc-manage will also be updated. This should
    be pushed to GitHub after the new docker image has been pushed to Docker
    Hub. The oca_version.txt file can be checked by existing OCA containers
    so that they know a new version has been released.
    """
    # This ensures the pfsc-ise and pfsc-server repos exist:
    tools.build.oca_readiness_checks(release=True)

    versions = get_version_numbers()

    with open(os.path.join(SRC_ROOT, 'pfsc-pdf', 'package.json')) as f:
        d = json.load(f)
        pdf_checked_out_vers = d["version"]

    pfsc_pdf_vers = versions['pfsc-pdf']
    if pdf_checked_out_vers != pfsc_pdf_vers:
        raise click.UsageError(
            f'Version of pfsc-pdf checked out under `src` ({pdf_checked_out_vers}) does not match'
            f' version ({pfsc_pdf_vers}) named by pfsc-ise.'
        )

    ise_vers = versions['pfsc-ise']
    server_vers = get_server_version()
    seq_num_suffix = f'-{seq_num}' if seq_num > 0 else ''
    oca_tag = f'{ise_vers}-{server_vers}{seq_num_suffix}'

    print('Building with versions:')
    print(f'  server: {server_vers}')
    print(f'  ise: {ise_vers}')
    print('If any of the above is incorrect, use `git checkout` in the repo in the `src` dir.')
    print()

    if skip_check:
        print(f'Using tag "{oca_tag}".')
    else:
        ok = input(f'Will use tag: "{oca_tag}". Okay? [y/N] ')
        if ok != 'y':
            print('Aborting')
            return

    vers_file = os.path.join(PFSC_MANAGE_ROOT, 'topics', 'pfsc', 'oca_version.txt')
    if not dry_run:
        with open(vers_file, 'w') as f:
            f.write(oca_tag)
        print(f'Wrote tag to {vers_file}')

    tools.build.oca.callback(True, dump, dry_run, oca_tag)


@release.command()
@click.option(
    '-y', '--skip-check', is_flag=True,
    help="Skip tag check."
)
@click.option('--demos', is_flag=True, help="Include demo repos.")
@click.option('--dump', is_flag=True, help="Dump Dockerfile to stdout before building.")
@click.option('--dry-run', is_flag=True, help="Do not actually build; just print docker command.")
def server(skip_check, demos, dump, dry_run):
    """
    Build a `pfsc-server` docker image, for release.

    The tag is generated from the current version number of pfsc-server.

    Unless you say to skip it, there will be a prompt to check if the tag is
    correct.
    """
    venv_path = os.path.join(SRC_ROOT, 'pfsc-server/venv')
    if not os.path.exists(venv_path):
        raise click.FileError(f'Could not find {venv_path}. Have you installed pfsc-server yet?')

    server_vers = get_server_version()

    tag = server_vers

    if skip_check:
        print(f'Using tag "{tag}".')
    else:
        ok = input(f'Will use tag: "{tag}". Okay? [y/N] ')
        if ok != 'y':
            print('Aborting')
            return

    tools.build.server.callback(demos, dump, dry_run, tag)

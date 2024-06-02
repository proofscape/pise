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
@click.option('--tar-path', help="Instead of building, save the context tar file to this path.")
def oca(seq_num, skip_check, dump, dry_run, tar_path):
    """
    Build a `pise` (one-container app) docker image, for release.

    The tag is generated from the current version number of pise,
    plus any sequence number you may supply.
    The "current" version is the one currently checked out.

    Unless you say to skip it, there will be a prompt to check if the tag is
    correct.
    """
    # This ensures the client and server code is ready:
    tools.build.oca_readiness_checks(release=True)

    versions = get_version_numbers()

    with open(os.path.join(SRC_ROOT, 'pfsc-pdf', 'package.json')) as f:
        d = json.load(f)
        pdf_checked_out_vers = d["version"]

    pfsc_pdf_vers = versions['pfsc-pdf']
    if pdf_checked_out_vers != pfsc_pdf_vers:
        raise click.UsageError(
            f'Version of pfsc-pdf checked out under `src` ({pdf_checked_out_vers}) does not match'
            f' version ({pfsc_pdf_vers}) named by pise.'
        )

    pise_vers = versions['pise']
    seq_num_suffix = f'-{seq_num}' if seq_num > 0 else ''
    oca_tag = f'{pise_vers}{seq_num_suffix}'

    print(f'Building with pise version: {pise_vers}')
    print('If this is incorrect, use `git checkout` in the pise repo.')
    print()

    if skip_check:
        print(f'Using tag "{oca_tag}".')
    else:
        ok = input(f'Will use tag: "{oca_tag}". Okay? [y/N] ')
        if ok != 'y':
            print('Aborting')
            return

    tools.build.oca.callback(dump, dry_run, tar_path, oca_tag)


@release.command()
@click.option(
    '-y', '--skip-check', is_flag=True,
    help="Skip tag check."
)
@click.option('--demos/--no-demos', default=True, help="Include demo repos.")
@click.option('--dump', is_flag=True, help="Dump Dockerfile to stdout before building.")
@click.option('--dry-run', is_flag=True, help="Do not actually build; just print docker command.")
@click.option('--tar-path', help="Instead of building, save the context tar file to this path.")
def server(skip_check, demos, dump, dry_run, tar_path):
    """
    Build a `pise-server` docker image, for release.

    The tag is generated from the current version number of pise (i.e. the one
    that is checked out).

    Unless you say to skip it, there will be a prompt to check if the tag is
    correct.
    """
    server_vers = get_server_version()

    tag = server_vers

    if skip_check:
        print(f'Using tag "{tag}".')
    else:
        ok = input(f'Will use tag: "{tag}". Okay? [y/N] ')
        if ok != 'y':
            print('Aborting')
            return

    tools.build.server.callback(demos, dump, dry_run, tar_path, tag)

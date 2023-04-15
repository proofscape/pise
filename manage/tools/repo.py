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

import os

import click

from manage import cli, PFSC_ROOT

SRC_DIR = os.path.join(PFSC_ROOT, 'src')

KNOWN_REPOS = {
    'moose': 'github.com/proofscape/pfsc-moose',
}

# Repo name may be mapped to an alternative name that should be used for it
# locally. keys: repo names as in KNOWN_REPOS; values: desired local names.
LOCAL_NAMES = {
    #'foo': 'bar',
}

# If a particular branch, tag, or commit needs to be checked out, you can set
# that here. keys: repo names as in KNOWN_REPOS; values: ref to be checked out.
REQUIRED_CHECKOUTS = {
    #'foo': 'topic_branch_x',
}

@cli.group()
def repo():
    """
    Utilities for cloning source repos.
    """
    pass

@repo.command()
def known():
    """
    List known source repos.
    """
    N = max(len(k) for k in KNOWN_REPOS)
    f = f'%{N + 4}s %s'
    print(f % ('Name', 'Repo'))
    print(f % ('-' * N, '-' * N))
    print('\n'.join(f % I for I in KNOWN_REPOS.items()))


def normalize_repo_name(name):
    if name.startswith('pfsc-'):
        name = name[5:]
    return name


def make_repo_url(normalized_repo_name):
    base = KNOWN_REPOS[normalized_repo_name]
    prefix = ''
    if base.startswith('github.com/'):
        # Read GitHub username and personal access token from environment, if defined:
        GH_USER = os.getenv('GH_USER')
        GH_PAT  = os.getenv('GH_PAT')
        if GH_USER and GH_PAT:
            prefix = f'{GH_USER}:{GH_PAT}@'
    url = f'https://{prefix}{base}.git'
    return url


@repo.command()
@click.option('--dry-run', is_flag=True, help="Do not actually clone; just print the clone command.")
@click.argument('repo')
def clone(dry_run, repo):
    """
    Clone source repo REPO into the src dir.

    REPO should be a repo name (without .git), such as "server" or "ise".

    See `pfsc repo known` command, to list all known names.
    """
    repo = normalize_repo_name(repo)
    if not repo in KNOWN_REPOS:
        raise click.UsageError(f'Unknown repo {repo}')
    url = make_repo_url(repo)
    clone_cmd = f'git clone {url}'
    full_cmd = f'cd {SRC_DIR}; {clone_cmd}'

    local_name = url.split('/')[0][:-4]
    if repo in LOCAL_NAMES:
        local_name = LOCAL_NAMES[repo]
        full_cmd += f' {local_name}'

    ref = REQUIRED_CHECKOUTS.get(repo, 'main')
    full_cmd += f'; cd {local_name}; git fetch; git checkout {ref}'

    if dry_run:
        print(full_cmd)
    else:
        print(clone_cmd)
        os.system(full_cmd)

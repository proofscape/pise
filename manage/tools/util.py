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
import json
import re
import pathlib
from configparser import ConfigParser
from datetime import datetime
import subprocess

import click

import conf as pfsc_conf
from manage import PFSC_ROOT, PISE_ROOT

def simple_timestamp():
    return datetime.now().strftime('%y%m%d_%H%M%S')

def trymakedirs(path, exist_ok=False):
    """
    Try to use os.makedirs(), and raise a click.UsageError if
    anything goes wrong.

    :param path: the desired new directory path
    :param exist_ok: as in os.makedirs
    :return: nothing
    """
    try:
        os.makedirs(path, exist_ok=exist_ok)
    except Exception as e:
        msg = f'Could not make directory {path}.\n{e}\n'
        raise click.UsageError(msg)

def check_app_url_prefix():
    """
    The APP_URL_PREFIX config var lets you add an optional prefix before
    all URLs in the Proofscape ISE.

    Working with the prefix is a little tricky. What you get depends on two
    questions: (1) is the prefix empty or not, and (2) are you trying to modify
    the root URL or some extended path?

    As you can see:

        Empty prefix:
            / --> /
            /some/path --> /some/path

        /my/prefix:
            / --> /my/prefix
            /some/path --> /my/prefix/some/path

    there is no single string that we can prepend to all existing paths (root
    or extended) that will work in all cases. Therefore this function checks
    the APP_URL_PREFIX and returns _two_ strings: one to use as the root URL,
    and one to prepend to extended paths.
    """
    raw_prefix = getattr(pfsc_conf, 'APP_URL_PREFIX', None) or ''
    if not isinstance(raw_prefix, str):
        msg = 'APP_URL_PREFIX must be string or undefined.'
        msg += ' Please correct your conf.py.'
        raise click.UsageError(msg)
    pre = raw_prefix.strip('/')
    app_url_prefix = f'/{pre}' if pre else ''
    root_url = f'/{pre}' if pre else '/'
    return root_url, app_url_prefix

def squash(text):
    """
    Jinja templates with conditional sections tend to wind up
    with lots of excess newlines. To "squash" is to replace any blocks of
    whitespace beginning and ending with newlines, with exactly two newlines.
    In other words, a single blank line is okay, but two or more is not.
    """
    import re
    return re.sub(r'\n\s*\n', '\n\n', text)

def resolve_fs_path(var_name):
    """
    Generally, when vars defined in conf.py define filesystem paths, they are
    interpreted as relative to `PFSC_ROOT`, unless they begin with a slash.
    This function performs that interpretation.

    :param var_name: (string) the name of the variable to be resolved.
    :return: `None` if the desired variable is undefined or set equal to `None`;
      otherwise the resolved path.
    :raises: ValueError if the desired variable is defined but equal to neither
      a string nor `None`.
    """
    raw = getattr(pfsc_conf, var_name)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError
    if len(raw) == 0:
        path = PFSC_ROOT
    elif raw[0] == '/':
        path = raw
    else:
        path = os.path.join(PFSC_ROOT, raw)
    # Do a resolve, in case there are symlinks.
    return pathlib.Path(path).resolve()


def do_commands_in_directory(cmds, path, dry_run=True, quiet=False):
    for cmd in cmds:
        full_cmd = f'cd {path}; {cmd}'
        if not quiet:
            print(full_cmd)
        if not dry_run:
            os.system(full_cmd)


def get_version_numbers(include_tags=False, include_other=False):
    """
    Read package.json, package-lock.json, and other-versions.json in the
    client code, in order to determine the version numbers for the
    projects:
        pise, mathjax, elkjs,
    and all projects named in other-versions.json, which at this time includes:
        pfsc-pdf, pyodide, pfsc-examp, pfsc-util, dislaylang,
        displaylang-sympy, lark, typeguard, mpmath, Jinja2, MarkupSafe

    include_tags: set True to supply also some of the configured image tags
    include_other: set True to supply also some other version numbers
    """
    client_path = pathlib.Path(PISE_ROOT) / 'client'
    with open(client_path / 'package.json') as f:
        pj = json.load(f)
    with open(client_path / 'package-lock.json') as f:
        plj = json.load(f)
    with open(client_path / 'other-versions.json') as f:
        ovj = json.load(f)
    nums = {
        'pise': pj['version'],
        'mathjax': plj["dependencies"]["mathjax"]["version"],
        'elkjs': plj["dependencies"]["elkjs"]["version"],
    }
    nums.update(ovj)

    if include_tags:
        # Could add others; atm this is all we need
        nums['redis-tag'] = pfsc_conf.REDIS_IMAGE_TAG
        nums['redisgraph-tag'] = pfsc_conf.REDISGRAPH_IMAGE_TAG
        nums['nginx-tag'] = pfsc_conf.NGINX_IMAGE_TAG

    if include_other:
        nums['demo-repos'] = pfsc_conf.PFSC_DEMO_REPOS

        server_path = pathlib.Path(PISE_ROOT) / 'server'
        with open(server_path / 'req/test-requirements.hashless') as f:
            trh = f.read()
        nums['pfsc-test-modules'] = re.search(r'pfsc-test-modules\.git@v(.+)$', trh).group(1)

    return nums


def get_server_version():
    """
    Get the version number of pfsc-server
    """
    return get_version_numbers()['pise']


def get_redis_server_version_for_oca():
    """
    Get the version number of redis-server that is installed in the OCA image.
    """
    cmd = f'docker run --rm --entrypoint=bash redis/redis-stack-server:{pfsc_conf.REDISGRAPH_IMAGE_TAG} -c "redis-server --version"'
    out = subprocess.check_output(cmd, shell=True)
    text = out.decode()

    def problem():
        raise Exception(f'Unexpected redis server version output: {text}')

    # Expect sth like this:
    #   Redis server v=6.2.4 sha=00000000:0 malloc=jemalloc-5.1.0 bits=64 build=72b794ea2901b8e1
    parts = text.split()
    if len(parts) < 3:
        problem()
    m = re.match(r'v=(\d+\.\d+\.\d+)$', parts[2])
    if not m:
        problem()
    return m.group(1)


def get_python_version_for_images():
    """
    Get the version number of Python being used in the pise and pise-server images.
    """
    return pfsc_conf.PYTHON_IMAGE_TAG.split('-')[0]

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
import jinja2

from manage import cli, PFSC_ROOT
from conf import DOCKER_CMD
from tools.util import do_commands_in_directory


@cli.group()
def make():
    """
    Make/build/compile for various projects.
    """
    pass

WHL_PROJECTS = {
    'examp': 'pfsc-examp',
    'displaylang': 'displaylang',
    'sympy': 'sympy',
    'util': 'pfsc-util',
}

@make.command()
@click.option('--dry-run', is_flag=True, help="Do nothing; just print commands.")
@click.argument('project')
def whl(dry_run, project):
    """
    Rebuild the whl file for PROJECT, and copy it into PFSC_ROOT/src/whl.

    Known projects: examp, displaylang, sympy, util
    """
    if not project in WHL_PROJECTS:
        raise click.UsageError('Unknown project.')
    repo_dir_name = WHL_PROJECTS[project]
    src_dir = pathlib.Path(PFSC_ROOT) / 'src'
    proj_dir = src_dir / repo_dir_name
    whl_dir = src_dir / 'whl'
    cmds = [
        f'source venv/bin/activate; python setup.py bdist_wheel',
        f'cp ./dist/*.whl {whl_dir}',
    ]
    do_commands_in_directory(cmds, proj_dir, dry_run=dry_run)


elkjs_static_path = os.path.join(PFSC_ROOT, 'static', 'elkjs')

MAKE_ELKJS_TPLT = jinja2.Template("""\
{{docker_cmd}} run --rm \\
    -v {{static_dir}}:/usr/local/lib/elkjs:rw \\
    elkjs-build-env:{{existing_elkjs_build_env_image_tag}} \\
    npm run build; npm run build; cp -r lib /usr/local/lib/elkjs
""")

@make.command()
@click.option('--dry-run', is_flag=True, help="Print but do not execute the `docker run` command.")
@click.argument('tag')
def elkjs(dry_run, tag):
    """
    Rebuild the elkjs library, using an _existing_ `elkjs-build-env` docker
    image of a given TAG.
    """
    cmd = MAKE_ELKJS_TPLT.render(
        docker_cmd=DOCKER_CMD,
        static_dir=elkjs_static_path,
        existing_elkjs_build_env_image_tag=tag,
    )
    click.echo(cmd)
    if not dry_run:
        os.system(cmd)

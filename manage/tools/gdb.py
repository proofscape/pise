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

@cli.group()
def gdb():
    """
    Utilities for the graph database.
    """
    pass


@gdb.command()
@click.option('--flask-config',
              type=click.Choice(['localdev', 'dockerdev', 'production']),
              default='localdev',
              help='Set the FLASK_CONFIG env var for the call to `flask pfsc gdb_setup`.')
def setup(flask_config):
    """
    Set up the graph database.
    """
    server_dir = os.path.join(PFSC_ROOT, 'src', 'pfsc-server')
    cmd = f'cd {server_dir}'
    cmd += f'; export FLASK_APP=web; export FLASK_CONFIG={flask_config}'
    cmd += f'; ./venv/bin/flask pfsc gdb_setup'
    os.system(cmd)

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
import re
import secrets
import copy
import pathlib

import click
import jinja2

import conf
from manage import cli, PFSC_ROOT
import tools.deploy.services as services
from tools.deploy.services import GdbCode
from tools import simple_yaml
from tools.util import (
    simple_timestamp, trymakedirs, check_app_url_prefix,
    resolve_fs_path, get_version_numbers
)
from topics.nginx import write_nginx_conf, write_maintenance_nginx_conf
import conf as pfsc_conf


@cli.group()
def deploy():
    """
    Utilities for deploying docker containers.
    """
    pass


@deploy.command()
@click.option('--gdb',
              type=click.Choice(['re', 'nj', 'tk', 'ja', 'np']),
              prompt='Graph database',
              help='The graph DB you are using. re=RedisGraph, nj=Neo4j, tk=TinkerGraph, ja=JanusGraph, np=Neptune')
@click.option('-n', '--workers', type=int, default=1, prompt='How many RQ workers', help='Number of worker containers you want to run')
@click.option('--demos/--no-demos', default=False, prompt='Serving demo repos', help="Are you serving demo repos?")
@click.option('--dump-dc', is_flag=True,
              help='Print the generated docker-compose YAML to stdout.')
@click.option('--dirname',
              help='Directory name under which to save. Use "production_" + random word/name + timestamp if unspecified.')
@click.option('--official', is_flag=True, help='Use official docker images under "proofscape/"')
@click.argument('pfsc-tag')
def production(gdb, workers, demos, dump_dc, dirname, official, pfsc_tag):
    """
    Generate a deployment directory for a production MCA deployment, using
    pise-server image of tag PFSC_TAG.

    This command is a front-end for the `pfsc deploy generate` command,
    offering a much more restricted set of options and output.

    In particular:

    * Only one GDB must be chosen

    * The tag for the pise-server docker image is passed as an argument,
      and must be a numerical tag of the form M.m.p

    * flask_config is always 'production'

    * Generates no OCA deployment, no local.env, and no layered deployment
    """
    if pfsc_tag in ["latest", "testing"]:
        raise click.UsageError('You cannot use the "latest" or "testing" pise-server docker image.')
    if not re.match(r'\d+\.\d+\.\d+$', pfsc_tag):
        raise click.UsageError('You must specify a tag of the form "M.m.p" for the pise-server docker image.')
    frontend_tag = pfsc_tag
    oca_tag = None
    mount_code = False
    mount_pkg = None
    no_local = True
    flask_config = 'production'
    static_redir = None
    static_acao = False
    dummy = False
    lib_vol, build_vol, gdb_vol = None, None, None
    generate.callback(gdb, pfsc_tag, frontend_tag, oca_tag, official, workers, demos, mount_code, mount_pkg, dump_dc,
             dirname, no_local, flask_config, static_redir, static_acao, dummy,
             lib_vol, build_vol, gdb_vol,
             production_mode=True)


@deploy.command()
@click.option('--gdb',
              default=GdbCode.RE, prompt='Graph database (re, nj, tk, ja, np)',
              help='List one or more graph DBs. re=RedisGraph, nj=Neo4j, tk=TinkerGraph, ja=JanusGraph, np=Neptune')
@click.option('--pfsc-tag', default='testing', prompt='pise-server image tag',
              help='Use `pise-server:TEXT` docker image.')
@click.option('--frontend-tag',
              help='Use `pise-frontend:TEXT` docker image. If undefined, use same tag as for pise-server.')
@click.option('--oca-tag', default='testing', prompt='pise (OCA) image tag',
              help='Use `pise:TEXT` docker image.')
@click.option('--official', is_flag=True, help='Use official docker images under "proofscape/"')
@click.option('-n', '--workers', type=int, default=1, prompt='How many RQ workers', help='Number of worker containers you want to run')
@click.option('--demos/--no-demos', default=True, prompt='Serve demo repos', help="Serve demo repos.")
@click.option('--mount-code/--no-mount-code', default=True, prompt='Volume-mount code for development',
              help='Volume-mount code (server,client,pdf,pyodide,whl) for live updates during development.')
@click.option('--mount-pkg', default=None,
              help='Volume-mount pkg dir TEXT from local venv, e.g. for testing upgrade before docker rebuild. May be comma-delimited list.')
@click.option('--dump-dc', is_flag=True,
              help='Print the generated docker-compose YAML to stdout.')
@click.option('--dirname',
              help='Directory name under which to save. Use random words + timestamp if unspecified.')
@click.option('-L', '--no-local', is_flag=True, help="Do NOT activate local.env by generating a symlink.")
@click.option('--flask-config',
              type=click.Choice(['dockerdev', 'production']),
              default='dockerdev', prompt='Flask config',
              help='Set the FLASK_CONFIG env var for the websrv and worker docker containers.')
@click.option('--per-deploy-dirs/--no-per-deploy-dirs', default=True,
              prompt='Use build,lib,graphdb dirs local to the deployment directory',
              help='Use build,lib,graphdb dirs local to the deployment directory')
@click.option('--static-redir', default=None, help='Redirect all static requests to domain TEXT.')
@click.option('--static-acao', is_flag=True, help='Serve all static assets with `Access-Control-Allow-Origin *` header.')
@click.option('--dummy', is_flag=True, help='Write a docker compose yml for a dummy deployment (Hello World web app).')
@click.option('--lib-vol', help="A pre-existing docker volume to be mounted to /proofscape/lib")
@click.option('--build-vol', help="A pre-existing docker volume to be mounted to /proofscape/build")
@click.option('--gdb-vol', help="A pre-existing docker volume for the graph db. Only RedisGraph currently supported.")
@click.option('--no-redis', is_flag=True, help='Only allowed when RedisGraph is sole GDB, which is then used in place of Redis.')
def generate(gdb, pfsc_tag, frontend_tag, oca_tag, official, workers, demos, mount_code, mount_pkg, dump_dc,
             dirname, no_local, flask_config, per_deploy_dirs, static_redir, static_acao, dummy,
             lib_vol, build_vol, gdb_vol, no_redis=False,
             production_mode=False):
    """
    Generate a new deployment dir containing files for deploying a full Proofscape system.

    The new directory lives under PFSC_ROOT/deploy, and generated files include:

      * docker-compose.yml

      * nginx.conf

      * local.env

      * docker.env

      * conf.py (a copy of the conf.py you used when you ran this command)

      * layers (a directory of docker-compose ymls to deploy by layers)

    Many (but not all) options will be determined by interactive prompt if not
    already supplied on the command line.
    """
    # It is typical to use this command interactively, i.e. to answer a bunch
    # of prompts. We want a blank line to separate those from the output.
    click.echo('')

    frontend_tag = frontend_tag or pfsc_tag

    if not gdb:
        raise click.UsageError('Must select at least one graph database.')
    gdb = re.split(r'[,\s]+', gdb)
    s = set(gdb)
    if not s.issubset(set(GdbCode.all)):
        raise click.UsageError(f'Legal GDB codes are: {", ".join(GdbCode.all)}')
    if len(gdb) > len(s):
        raise click.UsageError('Cannot repeat graph database selections.')
    if no_redis and s != {'re'}:
        raise click.UsageError('RedisGraph must be sole GDB selection, when using --no-redis.')

    dirname_prefix = 'production_' if production_mode else None
    new_dir_name, new_dir_path = make_new_deployment_dir(
        desired_name=dirname, prefix=dirname_prefix)
    click.echo(f'Made new deployment dir {new_dir_path}')

    # admin shell script
    admin_sh_script = write_admin_sh_script(
        new_dir_name, new_dir_path, pfsc_tag, flask_config,
        demos=demos, mount_code=mount_code, mount_pkg=mount_pkg,
        official=official, no_redis=no_redis
    )
    admin_script_path = os.path.join(new_dir_path, 'admin.sh')
    with open(admin_script_path, 'w') as f:
        f.write(admin_sh_script)
    os.chmod(admin_script_path, 0o755)
    click.echo(f'Wrote admin.sh')

    # mca-docker-compose.yml
    y = write_docker_compose_yaml(new_dir_name, new_dir_path,
                                  gdb, pfsc_tag, frontend_tag, official, workers, demos,
                                  mount_code, mount_pkg, per_deploy_dirs, flask_config,
                                  lib_vol, build_vol, gdb_vol, no_redis)
    y_full = y['full']
    y_layers = y['layers']

    if dump_dc:
        click.echo(y_full)
    dc_path = os.path.join(new_dir_path, 'mca-docker-compose.yml')
    with open(dc_path, 'w') as f:
        f.write(y_full)
    click.echo('Wrote mca-docker-compose.yml')

    if not production_mode:
        layers_dir = os.path.join(new_dir_path, 'layers')
        trymakedirs(layers_dir)
        for name, text in y_layers.items():
            filename = f'{name}.yml'
            dc_path = os.path.join(layers_dir, filename)
            with open(dc_path, 'w') as f:
                f.write(text)
            click.echo(f'Wrote layers/{filename}')

        dc_script_path = os.path.join(layers_dir, 'dc')
        with open(dc_script_path, 'w') as f:
            f.write(write_dc_script(new_dir_name))
        os.chmod(dc_script_path, 0o755)
        click.echo(f'Wrote layers/dc script')

    # oca-docker-compose.yml and run script
    if not production_mode:
        y_oca = write_oca_docker_compose_yaml(new_dir_name, new_dir_path, oca_tag,
                                              mount_code, mount_pkg, per_deploy_dirs,
                                              lib_vol=lib_vol, build_vol=build_vol, gdb_vol=gdb_vol)
        if dump_dc:
            click.echo(y_oca)
        oca_dc_path = os.path.join(new_dir_path, 'oca-docker-compose.yml')
        with open(oca_dc_path, 'w') as f:
            f.write(y_oca)
        click.echo('Wrote oca-docker-compose.yml')

        run_oca_sh_script = write_run_oca_sh_script(oca_tag)
        run_oca_script_path = os.path.join(new_dir_path, 'run_oca.sh')
        with open(run_oca_script_path, 'w') as f:
            f.write(run_oca_sh_script)
        os.chmod(run_oca_script_path, 0o755)
        click.echo(f'Wrote run_oca.sh')

    # dummy-docker-compose.yml
    if dummy:
        y_dummy = write_dummy_docker_compose_yaml(new_dir_name, new_dir_path, pfsc_tag, frontend_tag, flask_config, mount_code)
        if dump_dc:
            click.echo(y_dummy)
        dummy_dc_path = os.path.join(new_dir_path, 'dummy-docker-compose.yml')
        with open(dummy_dc_path, 'w') as f:
            f.write(y_dummy)
        click.echo('Wrote dummy-docker-compose.yml')

    # maintenance site
    if pfsc_conf.MAINTENANCE_SITE_DIR:
        m_nginx_conf = write_maintenance_nginx_conf(
            listen_on=443 if pfsc_conf.SSL else 80,
            ssl=pfsc_conf.SSL,
            basic_auth_title=pfsc_conf.AUTH_BASIC_TITLE if pfsc_conf.AUTH_BASIC_PASSWORD else None,
            redir_http=(pfsc_conf.REDIRECT_HTTP_FROM is not None),
        )
        mnc_path = os.path.join(new_dir_path, 'maintenance_nginx.conf')
        with open(mnc_path, 'w') as f:
            f.write(m_nginx_conf)
        click.echo('Wrote maintenance_nginx.conf')

        y_mn = write_maintenance_docker_compose_yaml(new_dir_name, new_dir_path)
        if dump_dc:
            click.echo(y_mn)
        mn_dc_path = os.path.join(new_dir_path, 'maintenance-docker-compose.yml')
        with open(mn_dc_path, 'w') as f:
            f.write(y_mn)
        click.echo('Wrote maintenance-docker-compose.yml')

    # nginx.conf
    root_url, app_url_prefix = check_app_url_prefix()
    nginx_conf = write_nginx_conf(
        listen_on=443 if pfsc_conf.SSL else 80,
        server_name=pfsc_conf.SERVER_NAME,
        ssl=pfsc_conf.SSL,
        basic_auth_title=pfsc_conf.AUTH_BASIC_TITLE if pfsc_conf.AUTH_BASIC_PASSWORD else None,
        static_redir=static_redir, static_acao=static_acao,
        redir_http=(pfsc_conf.REDIRECT_HTTP_FROM is not None),
        twin_server_name=pfsc_conf.TWIN_SERVER_NAME,
        hsts_seconds=pfsc_conf.HSTS_SECONDS,
        app_url_prefix=app_url_prefix, root_url=root_url,
        use_docker_ns=True,
        pfsc_web_hostname='pfscweb'
    )
    nc_path = os.path.join(new_dir_path, 'nginx.conf')
    with open(nc_path, 'w') as f:
        f.write(nginx_conf)
    click.echo('Wrote nginx.conf')

    # htpasswd file
    if pfsc_conf.AUTH_BASIC_PASSWORD:
        htpasswd_path = os.path.join(new_dir_path, 'htpasswd')
        gen_hash_cmd = f'openssl passwd -apr1 {pfsc_conf.AUTH_BASIC_PASSWORD}'
        os.system(f'echo "{pfsc_conf.AUTH_BASIC_USERNAME}:$( {gen_hash_cmd} )" > {htpasswd_path}')
        click.echo('Wrote htpasswd')

    # .env files
    local_dot_env, docker_dot_env = write_dot_env_files(app_url_prefix, gdb, demos, no_redis)

    if not production_mode:
        lde_path = os.path.join(new_dir_path, 'local.env')
        with open(lde_path, 'w') as f:
            f.write(local_dot_env)
        click.echo('Wrote local.env')

    dde_path = os.path.join(new_dir_path, 'docker.env')
    with open(dde_path, 'w') as f:
        f.write(docker_dot_env)
    click.echo('Wrote docker.env')

    # conf.py
    with open(pfsc_conf.__file__) as f:
        conf_py_text = f.read()
    conf_py_text = CONF_PY_COPY_HEADER + conf_py_text
    conf_py_out_path = os.path.join(new_dir_path, 'conf.py')
    with open(conf_py_out_path, 'w') as f:
        f.write(conf_py_text)
    click.echo('Copied conf.py')

    if not no_local:
        try:
            activate_local_dot_env(new_dir_path)
        except FileExistsError:
            msg = 'ERROR: Could not activate local.env since'
            msg += ' pfsc-server/instance/.env already exists and is not a symlink.'
            click.echo(msg)
        else:
            click.echo('Activated local.env')

CONF_PY_COPY_HEADER = """\
##############################################################################
# This deployment dir was generated with the pfsc-manage `pfsc deploy generate`
# command, using the following `conf.py` module.
##############################################################################

"""

@deploy.command()
@click.argument('dirname')
def local(dirname):
    """
    Configure the local deployment by making pfsc-server/instance/.env
    a symlink pointing to DIRNAME/local.env.

    You do not have to spell out DIRNAME completely, but may supply any prefix
    that uniquely determines it among all existing dirs under PFSC_ROOT/deploy.
    """
    deploy_dir_path = os.path.join(PFSC_ROOT, 'deploy')
    existing_names = os.listdir(deploy_dir_path)
    full_dirname = None
    count = 0
    for name in existing_names:
        if name.startswith(dirname):
            full_dirname = name
            count += 1
            if count > 1:
                break
    if count == 0:
        raise click.UsageError(f'Could not find any existing deployment dir with "{dirname}" as prefix.')
    elif count > 1:
        raise click.UsageError(f'Found multiple existing deployment dirs with "{dirname}" as prefix.')
    assert full_dirname in existing_names
    full_deploy_path = os.path.join(deploy_dir_path, full_dirname)
    try:
        activate_local_dot_env(full_deploy_path)
    except FileExistsError:
        msg = 'ERROR: Could not activate local.env since'
        msg += ' pfsc-server/instance/.env already exists and is not a symlink.'
        click.echo(msg)
    else:
        click.echo(f'Activated {full_deploy_path}')

##############################################################################

def activate_local_dot_env(full_deploy_path):
    """
    Activate a local.env by making a symlink to it from pfsc-server/instance/.env.

    :param full_deploy_path: Full path to the dir where the desired local.env lives.
    :return: nothing
    :raises: FileExistsError if pfsc-server/instance/.env already exists AND is NOT a symlink.
    """
    instance_dir_path = f'{PFSC_ROOT}/src/pfsc-server/instance'
    trymakedirs(instance_dir_path, exist_ok=True)
    instance_dot_env = os.path.join(instance_dir_path, '.env')
    if os.path.exists(instance_dot_env) and not os.path.islink(instance_dot_env):
        raise FileExistsError
    cmd = f'ln -sf {full_deploy_path}/local.env {instance_dot_env}'
    os.system(cmd)


def write_dot_env_files(app_url_prefix, gdb, demos, no_redis):
    secret = secrets.token_urlsafe(32)
    local_dot_env = write_local_dot_env(app_url_prefix, gdb, demos, no_redis, secret=secret)
    docker_dot_env = write_docker_dot_env(app_url_prefix, gdb, demos, no_redis, secret=secret)
    return local_dot_env, docker_dot_env


def update_with_class_vars(d, cls):
    c = {a: getattr(cls, a) for a in dir(cls) if not a.startswith("__")}
    d.update(c)


def dict_to_dot_env(d):
    """
    Build a .env file based on a dictionary `d`.

    For each `k:v` in `d`:
    If `v` is a string, then we record the line `k=v`.
    Otherwise `v` should be a dictionary in which the allowed entries are:
        comment: a string that will be recorded verbatim
        name: a string to be used as the name of the env var, instead of the key `k`
        value: a string that will be set as the value of this env var
        out: if truthy, the k=v line will be commented out
    If both a comment and a value are given, the comment comes first.
    """
    lines = []
    for k, v in d.items():
        if not isinstance(v, dict):
            v = {'value': v}
        if 'comment' in v:
            c = v['comment']
            if c and c[0] != "#":
                c = "#" + c
            lines.append(c)
        if 'value' in v:
            name = v.get('name', k)
            line = f'{name}={v["value"]}'
            if v.get('out'):
                line = "#" + line
            lines.append(line)
    return '\n'.join(lines) + '\n'


def write_local_dot_env(app_url_prefix, gdb, demos, no_redis, secret=None):
    d = {
        "SECRET_KEY": secret or secrets.token_urlsafe(32),
        "PFSC_LIB_ROOT": f'{PFSC_ROOT}/lib',
        "PFSC_BUILD_ROOT": f'{PFSC_ROOT}/build',
        "PFSC_PDFLIB_ROOT": f'{PFSC_ROOT}/PDFLibrary',
        "REDIS_URI": f'redis://localhost:{pfsc_conf.REDISGRAPH_MCA_PORT if no_redis else pfsc_conf.REDIS_PORT}',
    }

    if app_url_prefix:
        d["APP_URL_PREFIX"] = app_url_prefix

    write_gdb_dot_env(d, gdb, GdbCode.localhost_URI, comment=True)

    demo_path = f'{PFSC_ROOT}/src/pfsc-demo-repos'
    if demos and os.path.exists(demo_path):
        d["PFSC_DEMO_ROOT"] = demo_path
        d["PROVIDE_DEMO_REPOS"] = 1
    elif demos:
        print(f'WARNING: Asked to serve demo repos, but `{demo_path}` not found.')

    if conf.EMAIL_TEMPLATE_DIR:
        d["EMAIL_TEMPLATE_DIR"] = resolve_fs_path("EMAIL_TEMPLATE_DIR")

    update_with_class_vars(d, pfsc_conf.CommonVars)
    update_with_class_vars(d, pfsc_conf.LocalVars)

    return dict_to_dot_env(d)


def write_docker_dot_env(app_url_prefix, gdb, demos, no_redis, secret=None):
    d = {
        "SECRET_KEY": secret or secrets.token_urlsafe(32),
    }

    if no_redis:
        d["REDIS_URI"] = 'redis://redisgraph:6379'

    if app_url_prefix:
        d["APP_URL_PREFIX"] = app_url_prefix

    write_gdb_dot_env(d, gdb, GdbCode.docker_URI)

    if demos:
        d["PROVIDE_DEMO_REPOS"] = 1

    if conf.EMAIL_TEMPLATE_DIR:
        d["EMAIL_TEMPLATE_DIR"] = "/home/pfsc/proofscape/src/_email_templates"

    update_with_class_vars(d, pfsc_conf.CommonVars)
    update_with_class_vars(d, pfsc_conf.DockerVars)

    return dict_to_dot_env(d)


# These are the names we need to find among wheel files when serving wheels
# locally, and they're listed in topological order.
REQUIRED_WHEEL_PROJECTS = [
    "pfsc_util",
    "typeguard",
    "displaylang",
    "displaylang_sympy",
    "lark067",
    "pfsc_examp",
]


class WheelFile:
    """
    Simple class for sorting version numbers in wheel file names.

    We support the following forms of version numbers, and ordering rules:
    * version numbers can be 3 or 4 segments (dot separated)
    * the first two segments must parse as integers
    * the third segment can be an integer, or an integer followed by any
      alphanumeric string
    * the fourth segment, if present, can be any alphanumeric string
    * we interpret any extension of the third segment as being an earlier
      version than the pure, ingegral third segment
    * for the optional fourth segment we're currently only expecting 'dev0',
      which means a version that comes before the one obtained by omitting
      this segment.
    """

    def __init__(self, filename):
        self.filename = filename
        self.parts = filename.split('-')
        self.project_name = self.parts[0]
        self.version_number = self.parts[1]

        plus_infinity = 'zzzzzzzzzzzzzzzz'
        parts = self.version_number.split('.')
        if len(parts) == 3:
            parts.append(plus_infinity)
        M, m, p, f = parts
        p, suffix = re.match(r'^(\d+)(.*)$', p).groups()
        M, m, p = int(M), int(m), int(p)
        if not suffix:
            # Pure numerical versions should come after the same number with
            # a suffix, so make an artificial suffix designed to come last.
            suffix = plus_infinity
        self.version_tuple = (M, m, p, suffix, f)

    def __hash__(self):
        return hash(self.filename)

    def __lt__(self, other):
        if self.project_name == other.project_name:
            return self.version_tuple < other.version_tuple
        return NotImplemented


def list_wheel_filenames():
    """
    Return a list, in topological order, with an exact filename for each of the
    projects, from the PFSC_ROOT/src/whl directory. For each project, we select
    the filename with the latest version number.
    """
    def raise_missing_wheels():
        raise click.UsageError("Asked for local wheels, but they're not all present. Did you use `pfsc get wheels` yet?")

    path = pathlib.Path(PFSC_ROOT) / 'src' / 'whl'
    if not path.exists():
        raise_missing_wheels()

    wheel_files = [WheelFile(p.name) for p in path.glob("*.whl")]
    present_project_names = set(w.project_name for w in wheel_files)
    if set(REQUIRED_WHEEL_PROJECTS) - present_project_names:
        raise_missing_wheels()

    # For each project, we take the filename with the latest version.
    # If you have downloaded existing versions, and are now developing new
    # versions, you'll want to mount the new ones, so this should be what
    # you want.
    selected_filenames = []
    for proj in REQUIRED_WHEEL_PROJECTS:
        files = set(w for w in wheel_files if w.project_name == proj)
        latest = max(files)
        selected_filenames.append(latest.filename)
    return selected_filenames


def write_gdb_dot_env(d, gdb, uri_lookup_method, comment=False):
    if len(gdb) == 1:
        code = gdb[0]
        d["GRAPHDB_URI"] = {
            'value': uri_lookup_method(code),
            'out': GdbCode.requires_manual_URI(code),
        }
    else:
        d['pre-gdb-block'] = {'comment': ''}
        for i, code in enumerate(gdb):
            v = {
                'value': uri_lookup_method(code),
                'name': "GRAPHDB_URI",
                'out': i > 0 or GdbCode.requires_manual_URI(code),
            }
            if comment:
                v['comment'] = GdbCode.service_name(code) + ":"
            d[f"GRAPHDB_URI_{i}"] = v
        d['post-gdb-block'] = {'comment': ''}


DC_SCRIPT_TPLT = jinja2.Template("""\
#!/bin/sh

# Use this script instead of docker-compose to take the various layers
# up and down. For example, use
#
#   $ ./dc 100_db.yml up
#
# to bring up the database layer, and
#
#   $ ./dc 100_db.yml down
#
# to bring it down.

if [ -z $1 ]; then
    echo "Missing filename."
else
    if [ -f $1 ]; then
        NAME=$(echo $1| cut -d'.' -f 1)
        PROJ="layer-$NAME-{{deploy_dir_name}}"
        if [ -z $2 ]; then
            echo "Missing command [up/down]."
        else
            if test $2 = "up"; then
                docker-compose -f $1 -p $PROJ up -d
            else
                if test $2 = "down"; then
                    docker-compose -f $1 -p $PROJ down
                else
                    echo "Unknown command: $2"
                fi
            fi
        fi
    else
        echo "File not found: $1"
    fi
fi
""")


def write_dc_script(deploy_dir_name):
    return DC_SCRIPT_TPLT.render(deploy_dir_name=deploy_dir_name)


ADMIN_SH_SCRIPT_TPLT = jinja2.Template(r"""#!/usr/bin/env sh

# Run this script in order to enter a Docker container where you can use
#
#   $ flask pfsc
#
# to conduct admin tasks w the MCA's gdb & build dir. This ensures you have the
# expected combination of python version and python package versions, even when
# operating the MCA on a host that doesn't necessarily use the same python
# version.
#
# Use
#
#   $ flask pfsc --help
#
# for a list of commands.

{{docker_command}} run --rm -it --entrypoint=bash \
  --network="mca-{{deploy_dir_name}}" \
{{bind_mounts}}
  -e FLASK_CONFIG={{flask_config}} \
  -e FLASK_APP=web \
  {{"proofscape/" if official else ""}}pise-server:{{pfsc_tag}}
""")


def write_admin_sh_script(
        deploy_dir_name, deploy_dir_path, pfsc_tag, flask_config,
        demos=False, mount_code=False, mount_pkg=None,
        official=False, no_redis=False
    ):
    # Want all the same bind mounts that are used in a pfsc worker container,
    # so that admin can do anything a worker can do.
    d = services.pise_server(
        deploy_dir_path, 'worker', flask_config, tag=pfsc_tag,
        demos=demos, mount_code=mount_code, mount_pkg=mount_pkg,
        official=official, no_redis=no_redis
    )
    bind_mounts = '\n'.join([
        f'  -v "{v}" \\' for v in d['volumes']
    ])
    return ADMIN_SH_SCRIPT_TPLT.render(
        deploy_dir_name=deploy_dir_name,
        bind_mounts=bind_mounts,
        pfsc_tag=pfsc_tag,
        flask_config=flask_config,
        docker_command=pfsc_conf.DOCKER_CMD,
        official=official,
    ) + '\n'


RUN_OCA_SH_SCRIPT_TPLT = jinja2.Template(r"""#!/usr/bin/env sh

# Run this script in order to test the OCA without any bind
# mounts, i.e. to verify that it actually runs properly on its own.

{{docker_command}} run --rm \
  -p {{oca_port}}:7372 \
  -v "{{oca_home_dir}}:/proofscape" \
  pise:{{image_tag}}

""")


def write_run_oca_sh_script(oca_tag):
    return RUN_OCA_SH_SCRIPT_TPLT.render(
        docker_command=pfsc_conf.DOCKER_CMD,
        oca_home_dir=f'{PFSC_ROOT}/oca',
        oca_port=pfsc_conf.PFSC_ISE_OCA_PORT,
        image_tag=oca_tag,
    )


def write_docker_compose_yaml(deploy_dir_name, deploy_dir_path, gdb, pfsc_tag, frontend_tag, official,
                              workers, demos, mount_code, mount_pkg, per_deploy_dirs, flask_config,
                              lib_vol, build_vol, gdb_vol, no_redis):
    s_full, s_db = {}, {}
    if not no_redis:
        svc_redis = services.redis()
        s_full = {
            'redis': svc_redis,
        }
        s_db = {
            'redis': copy.deepcopy(svc_redis),
        }

    altdir = f'{deploy_dir_path}/mca' if per_deploy_dirs else None

    for code in gdb:
        if code not in GdbCode.via_container:
            continue
        name = GdbCode.service_name(code)
        writer = GdbCode.service_defn_writer(code)
        svc_defn = writer(altdir=altdir)

        if gdb_vol:
            # TODO: Provide support for use of named volumes with other GDBs besides RedisGraph
            if code == GdbCode.RE:
                svc_defn['volumes'] = [
                    f'{gdb_vol}:/data'
                ]

        s_full[name] = svc_defn
        s_db[name] = copy.deepcopy(svc_defn)

    if GdbCode.RE in gdb and pfsc_conf.REDISINSIGHT_IMAGE_TAG:
        svc_ri = services.redisinsight()
        s_full['redisinsight'] = svc_ri
        s_db['redisinsight'] = copy.deepcopy(svc_ri)

    s_aux = {}
    # If we had any auxiliary services:
    #if aux1:
    #    svc_aux1 = services.aux1()
    #    s_full['aux1'] = svc_aux1
    #    s_aux['aux1'] = copy.deepcopy(svc_aux1)

    s_app = {}
    def write_pfsc_service(cmd):
        return services.pise_server(deploy_dir_path, cmd, flask_config,
            tag=pfsc_tag, gdb=gdb, workers=workers, demos=demos,
            mount_code=mount_code, mount_pkg=mount_pkg, official=official, altdir=altdir,
            lib_vol=lib_vol, build_vol=build_vol, no_redis=no_redis)

    for n in range(workers):
        svc_pfscwork = write_pfsc_service('worker')
        s_full[f'pfscwork{n}'] = svc_pfscwork
        s_app[f'pfscwork{n}'] = copy.deepcopy(svc_pfscwork)
        del s_app[f'pfscwork{n}']['depends_on']

    svc_pfscweb = write_pfsc_service('websrv')
    s_full['pfscweb'] = svc_pfscweb
    s_app['pfscweb'] = copy.deepcopy(svc_pfscweb)
    s_app['pfscweb']['depends_on'] = [
        d for d in s_app['pfscweb']['depends_on'] if d.startswith('pfscwork')
    ]

    s_front = {}
    svc_nginx = services.nginx(deploy_dir_path, frontend_tag,
                               mount_code=mount_code, official=official)
    s_full['nginx'] = svc_nginx
    s_front['nginx'] = copy.deepcopy(svc_nginx)
    del s_front['nginx']['depends_on']

    network_name = f'layers-{deploy_dir_name}'
    make_network = {
        'default': {
            'name': network_name
        }
    }
    join_network = {
        'default': {
            'external': {
                'name': network_name
            }
        }
    }

    d_full = {
        'version': '3.5',
        'services': s_full,
        'networks': {
            'default': {
                'name': f'mca-{deploy_dir_name}',
            }
        },
    }

    vol_names = {lib_vol, build_vol, gdb_vol} - {None}
    if vol_names:
        vol_names = sorted(list(vol_names))  # for deterministic results
        volumes = {}
        for vol_name in vol_names:
            volumes[vol_name] = {'external': True}
        d_full['volumes'] = volumes

    y = {
        'full': simple_yaml.dumps(d_full, indent=2) + '\n',
        'layers': {
            '100_db': "# Database layer\n" + simple_yaml.dumps({
                'version': '3.5', 'services': s_db, 'networks': make_network
            }, indent=2) + '\n',
            '150_aux': "# Auxiliary services\n" + simple_yaml.dumps({
                'version': '3.5', 'services': s_aux, 'networks': join_network
            }, indent=2) + '\n',
            '200_app': "# Application layer\n" + simple_yaml.dumps({
                'version': '3.5', 'services': s_app, 'networks': join_network
            }, indent=2) + '\n',
            '300_front': "# Front end\n" + simple_yaml.dumps({
                'version': '3.5', 'services': s_front, 'networks': join_network
            }, indent=2) + '\n',
        }
    }
    if not s_aux:
        del y['layers']['150_aux']
    return y


def write_oca_docker_compose_yaml(deploy_dir_name, deploy_dir_path, oca_tag,
                                  mount_code, mount_pkg, per_deploy_dirs=False,
                                  lib_vol=None, build_vol=None, gdb_vol=None):
    altdir = f'{deploy_dir_path}/oca' if per_deploy_dirs else None
    d = {
        'version': '3.5',
        'services': {
            'pise': services.proofscape_oca(
                deploy_dir_path, tag=oca_tag,
                mount_code=mount_code, mount_pkg=mount_pkg, altdir=altdir,
                lib_vol=lib_vol, build_vol=build_vol, gdb_vol=gdb_vol
            ),
        },
        'networks': {
            'default': {
                'name': f'oca-{deploy_dir_name}',
            }
        },
    }

    vol_names = {lib_vol, build_vol, gdb_vol} - {None}
    if vol_names:
        vol_names = sorted(list(vol_names))  # for deterministic results
        volumes = {}
        for vol_name in vol_names:
            volumes[vol_name] = {'external': True}
        d['volumes'] = volumes

    y = simple_yaml.dumps(d, indent=2) + '\n'
    return y


def write_dummy_docker_compose_yaml(deploy_dir_name, deploy_dir_path,
                                    pfsc_tag, frontend_tag, flask_config, mount_code):
    d = {
        'version': '3.5',
        'services': {
            'pfscweb': services.pfsc_dummy_server(
                deploy_dir_path, flask_config, tag=pfsc_tag
            ),
            'nginx': services.nginx(deploy_dir_path, frontend_tag, dummy=True, mount_code=mount_code)
        },
        'networks': {
            'default': {
                'name': f'dummy-{deploy_dir_name}',
            }
        },
    }
    y = simple_yaml.dumps(d, indent=2) + '\n'
    return y


def write_maintenance_docker_compose_yaml(deploy_dir_name, deploy_dir_path):
    d = {
        'version': '3.5',
        'services': {
            'nginx': services.maintenance_nginx(deploy_dir_path)
        },
        'networks': {
            'default': {
                'name': f'maintenance-{deploy_dir_name}',
            }
        },
    }
    y = simple_yaml.dumps(d, indent=2) + '\n'
    return y


def make_new_deployment_dir(desired_name=None, prefix=None):
    """
    Make a new directory under `PFSC_ROOT/deploy`.

    :param desired_name: Optional name to be used for the new directory.
      If not supplied, we generate a name consisting of a random adjective
      and name, followed by a timestamp.
    :param prefix: If specified, while desired_name is None, we prepend this
      prefix on the randomly generated name.

    :return: Pair (new dir name, full path to new dir).
    :raises: `click.UsageError` if desired name is supplied but already exists,
      or if for any reason we cannot make the new directory.
    """
    deploy_dir_path = os.path.join(PFSC_ROOT, 'deploy')
    existing_names = os.listdir(deploy_dir_path)
    if desired_name in existing_names:
        msg = f'The deployment dir `{desired_name}` already exists.'
        raise click.UsageError(msg)
    elif desired_name is None:
        from tools.word import random_adj_and_name
        adj, name = random_adj_and_name(dodge_prefixes=existing_names)
        new_dir_name = f'{adj}_{name}_{simple_timestamp()}'
        if prefix:
            new_dir_name = prefix + new_dir_name
    else:
        new_dir_name = desired_name
    new_dir_path = os.path.join(deploy_dir_path, new_dir_name)
    trymakedirs(new_dir_path)
    return new_dir_name, new_dir_path

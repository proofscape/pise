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
import jinja2

import conf
from manage import PFSC_ROOT
from tools.util import squash
from tools.deploy import list_wheel_filenames
from tools.util import get_version_numbers, get_server_version


this_dir = os.path.dirname(__file__)
templates_dir = os.path.join(this_dir, 'templates')
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))


##############################################################################
# Components

def write_startup_system(
        dir_where_startup_system_lives,
        numbered_inis=None, tmp_dir_name=None):
    numbered_inis = numbered_inis or {}
    template = jinja_env.get_template(f'Dockerfile.startup_system')
    return template.render(
        dir_where_startup_system_lives=dir_where_startup_system_lives,
        numbered_inis=numbered_inis,
        tmp_dir_name=tmp_dir_name,
        ensure_dirs=True,
    )


def write_oca_eula_file(version):
    template = jinja_env.get_template('EULA.txt')
    return template.render(
        version=version,
    )


def write_pfsc_installation(
        python_cmd='python',
        ubuntu=True, demos=False, use_venv=False,
        oca_version_file=None, eula_file=None):

    # At this time, we have no python packages to be installed locally.
    # If this once again becomes necessary, the 'Dockerfile.localreqs' file
    # in topics/pfsc/templates shows how we used to handle this with the
    # pfsc-util package. Modify that file as needed, and then set the
    # `local_reqs` variable here equal to its rendered contents.
    local_reqs = ''

    template = jinja_env.get_template(f'Dockerfile.pfsc')
    return template.render(
        python_cmd=python_cmd,
        ubuntu=ubuntu,
        demos=demos,
        use_venv=use_venv,
        oca_version_file=oca_version_file,
        eula_file=eula_file,
        local_reqs=local_reqs,
    )


def get_pyodide_major_minor_as_ints():
    versions = get_version_numbers()
    M, m, p = versions['pyodide'].split('.')
    return int(M), int(m)


def write_oca_static_setup(tmp_dir_name):
    template = jinja_env.get_template('Dockerfile.oca_static')

    pyodide_files = """
    pyodide.js pyodide_py.tar pyodide.asm.js pyodide.asm.data pyodide.asm.wasm
    """.split()

    project_names = """
    micropip pyparsing packaging Jinja2 MarkupSafe mpmath
    """.split()

    versions = get_version_numbers()
    server_vers = get_server_version()

    M, m = get_pyodide_major_minor_as_ints()
    if (M, m) < (0, 20):
        pyodide_files.extend(['packages.json', 'distutils.js', 'distutils.data'])
        for name in project_names:
            pyodide_files.extend([f'{name}.js', f'{name}.data'])
    else:
        pyodide_files.append('distutils.tar')
        if (M, m) == (0, 20):
            pyodide_files.append('packages.json')
        else:
            pyodide_files.append('repodata.json')
        vers_path = pathlib.Path(PFSC_ROOT) / 'src' / 'pyodide' / f'v{versions["pyodide"]}'
        for name in project_names:
            paths = list(vers_path.glob(f'{name}-*.whl'))
            # There should be exactly one wheel file for each project
            assert len(paths) == 1
            path = paths[0]
            pyodide_files.append(path.name)

    return template.render(
        tmp_dir_name=tmp_dir_name,
        versions=versions,
        server_vers=server_vers,
        pyodide_files=pyodide_files,
        wheels=list_wheel_filenames(),
    )


def write_oca_final_setup(tmp_dir_name, final_workdir='/home/pfsc'):
    template = jinja_env.get_template('Dockerfile.oca_final_setup')
    versions = get_version_numbers()
    return template.render(
        tmp_dir_name=tmp_dir_name,
        final_workdir=final_workdir,
    )


def write_oca_nginx_conf():
    """
    Write an nginx.conf for use in the OCA. (Currently not used, but we keep
    this around for reference.)
    """
    from topics.nginx import write_nginx_conf
    return write_nginx_conf(
        listen_on='0.0.0.0:7372',
        app_url_prefix='', root_url='/',
        use_docker_ns=False,
        pfsc_web_hostname='localhost'
    )


def write_worker_and_web_supervisor_ini(worker=True, web=True, use_venv=True, oca=False):
    template = jinja_env.get_template('pfsc.ini')
    return template.render(
        use_venv=use_venv,
        worker=worker,
        web=web,
        oca=oca,
    )

##############################################################################
# Whole Dockerfiles

def write_single_service_dockerfile(demos=False):
    pfsc_install = write_pfsc_installation(
        ubuntu=True, demos=demos, use_venv=False
    )
    template = jinja_env.get_template('Dockerfile.single_service')
    df = template.render(
        pfsc_install=pfsc_install,
    )
    return squash(df)


def write_proofscape_oca_dockerfile(tmp_dir_name, demos=False):
    pfsc_install = write_pfsc_installation(
        ubuntu=True, demos=demos, use_venv=False,
        oca_version_file=f'{tmp_dir_name}/oca_version.txt',
        eula_file=f'{tmp_dir_name}/eula.txt',
    )
    startup_system = write_startup_system(
        '/home/pfsc', numbered_inis={
            100: 'redisgraph',
            200: 'pfsc',
        }, tmp_dir_name=tmp_dir_name
    )
    static_setup = write_oca_static_setup(
        tmp_dir_name
    )
    final_setup = write_oca_final_setup(
        tmp_dir_name, final_workdir='/home/pfsc'
    )
    template = jinja_env.get_template('Dockerfile.oca')
    df = template.render(
        redisgraph_image_tag=conf.REDISGRAPH_IMAGE_TAG,
        pfsc_install=pfsc_install,
        startup_system=startup_system,
        static_setup=static_setup,
        final_setup=final_setup,
    )
    return squash(df)


##############################################################################
def test01():
    import sys
    n = int(sys.argv[1])
    demos = bool(n & 1)
    vim = bool(n & 4)
    w3m = bool(n & 8)

    df = write_single_service_dockerfile(demos=demos, vim=vim, w3m=w3m)
    sys.stdout.write(df)

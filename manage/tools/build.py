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

import subprocess
import tempfile
import os
import re
import pathlib
import sys
import json

import click

import conf
from manage import cli, PFSC_ROOT, PFSC_MANAGE_ROOT
from conf import DOCKER_CMD
import tools.license
from tools.util import get_version_numbers
import topics.pfsc.write_license_files as write_license_files

SRC_ROOT = os.path.join(PFSC_ROOT, 'src')
SRC_TMP_ROOT = os.path.join(SRC_ROOT, 'tmp')


@cli.group()
def build():
    """
    Tools for building docker images for development.
    """
    pass


def dump_text_with_title(text, title):
    print('=' * 79 + f'\n|| {title}:\n' + '=' * 79 + '\n' + text + '\n' + '=' * 79)


LICENSE_HEADER_PATTERN = re.compile("""\
# --------------------------------------------------------------------------- #
#   Copyright .+?
# --------------------------------------------------------------------------- #
""", re.S)


def strip_headers(text):
    return LICENSE_HEADER_PATTERN.sub('', text)


def finalize(df, image_name, tag, dump, dry_run, tar_path=None):
    """
    Finish a build process by actually carrying out the `docker build` command.

    df: the text of the Dockerfile
    image_name: the name for the image
    tag: the tag for the image
    dump: boolean, whether you want to dump the Dockerfile contents to stdout
    dry_run: boolean, whether to actually do anything
    tar_path: If given, then instead of carrying out the `docker build` command,
        we will write the tar file to this path. It can then be passed as the
        context to a `docker build` carried out at a later time. Tildes (~) are
        expanded.
    """
    df = strip_headers(df)
    if dump:
        dump_text_with_title(df, 'Dockerfile')

    # We build a temporary context for the build, using symlinks and
    # the tar trick to dereference the links and pass everything to Docker.
    # This is what allows source repos to live anywhere in your filessytem,
    # and simply be symlinked from PFSC_ROOT/src. It also makes builds much
    # faster on Ubuntu nodes, since the context is much smaller.
    with tempfile.TemporaryDirectory(dir=SRC_TMP_ROOT) as context_dir:
        # Get an alphabetical list without repeats, of the resources that
        # are copied into the image with the COPY command.
        copied = list(sorted({
            line.split()[1] for line in df.split('\n')
            if line.startswith("COPY")
            and not line.startswith("COPY --from")
        }))

        # Make a symlink for each desired resource.
        src_dir = pathlib.Path(SRC_ROOT)
        for resource in copied:
            res_path = pathlib.Path(resource)
            dirs = res_path.parts[:-1]
            c = pathlib.Path(context_dir)
            skip = False
            for d in dirs:
                c /= d
                if not c.exists():
                    c.mkdir()
                elif c.is_symlink():
                    # Because the resource paths are sorted alphabetically,
                    # and there are no repeats, it's okay if one is a prefix
                    # of another. We just skip the longer one entirely.
                    skip = True
                    break
            if not skip:
                r = src_dir / res_path
                cmd = f'ln -s {r} {c}'
                os.system(cmd)

        with open(pathlib.Path(context_dir) / 'Dockerfile', 'w') as f:
            f.write(df)

        ignore_file_path = src_dir / '.dockerignore'
        if ignore_file_path.exists():
            cmd = f'ln -s {ignore_file_path} {context_dir}'
            os.system(cmd)

        """
        On macOS, I found that if you gzip the tarfile (bzip produces similar
        error), you get:
                    
            failed to solve with frontend dockerfile.v0: failed to read dockerfile: Error processing tar file(gzip: invalid header):
        
        so we gzip iff the platform is NOT darwin.
        """
        do_zip = (sys.platform != 'darwin')
        zip = 'z' if do_zip else ''
        if tar_path:
            cmd = f'cd {context_dir}; tar -c{zip}h -f {os.path.expanduser(tar_path)} .'
        else:
            cmd = f'cd {context_dir}; tar -c{zip}h . | {DOCKER_CMD} build -t {image_name}:{tag} -'

        print(cmd)
        if not dry_run:
            os.system(cmd)


PYC_DOCKERIGNORE = """\
**/__pycache__
**/*.pyc
"""


def write_dockerignore_for_pyc():
    with open(os.path.join(SRC_ROOT, '.dockerignore'), 'w') as f:
        f.write(PYC_DOCKERIGNORE)


@build.command()
@click.option('--demos', is_flag=True, help="Include demo repos.")
@click.option('--dump', is_flag=True, help="Dump Dockerfile to stdout before building.")
@click.option('--dry-run', is_flag=True, help="Do not actually build; just print docker command.")
@click.option('--tar-path', help="Instead of building, save the context tar file to this path.")
@click.argument('tag')
def server(demos, dump, dry_run, tar_path, tag):
    """
    Build a `pise-server` docker image, and give it a TAG.
    """
    license_info = tools.license.gather_licensing_info()
    pfsc_topics = pathlib.Path(PFSC_MANAGE_ROOT) / 'topics' / 'pfsc'
    with open(pfsc_topics / 'templates' / 'combined_license_file_server.txt') as f:
        license_template = f.read()
    with open(pfsc_topics / 'write_license_files.py') as f:
        wlf_script = f.read()

    from topics.pfsc import write_single_service_dockerfile
    with tempfile.TemporaryDirectory(dir=SRC_TMP_ROOT) as tmp_dir_name:
        with open(os.path.join(tmp_dir_name, 'license_info.json'), 'w') as f:
            f.write(json.dumps(license_info, indent=4))
        with open(os.path.join(tmp_dir_name, 'license_template.txt'), 'w') as f:
            f.write(license_template)
        with open(os.path.join(tmp_dir_name, 'write_license_files.py'), 'w') as f:
            f.write(wlf_script)
        tmp_dir_rel_path = os.path.relpath(tmp_dir_name, start=SRC_ROOT)
        df = write_single_service_dockerfile(tmp_dir_rel_path, demos=demos)
        finalize(df, 'pise-server', tag, dump, dry_run, tar_path=tar_path)


@build.command()
@click.option('--dump', is_flag=True, help="Dump Dockerfile to stdout before building.")
@click.option('--dry-run', is_flag=True, help="Do not actually build; just print docker command.")
@click.option('--tar-path', help="Instead of building, save the context tar file to this path.")
@click.argument('tag')
def frontend(dump, dry_run, tar_path, tag):
    """
    Build a `pise-frontend` docker image, and give it a TAG.
    """
    if not dry_run:
        oca_readiness_checks(client=True, client_min=True, pdf=True, pyodide=True, whl=True)

    license_info = tools.license.gather_licensing_info()
    licenses_txt, notice_txt = write_license_files.build_frontend_files(license_info)

    from topics.pfsc import write_frontend_dockerfile
    with tempfile.TemporaryDirectory(dir=SRC_TMP_ROOT) as tmp_dir_name:
        with open(os.path.join(tmp_dir_name, 'LICENSES.txt'), 'w') as f:
            f.write(licenses_txt)
        with open(os.path.join(tmp_dir_name, 'NOTICE.txt'), 'w') as f:
            f.write(notice_txt)
        tmp_dir_rel_path = os.path.relpath(tmp_dir_name, start=SRC_ROOT)
        df = write_frontend_dockerfile(tmp_dir_rel_path)
        finalize(df, 'pise-frontend', tag, dump, dry_run, tar_path=tar_path)


def oca_readiness_checks(release=False, client=True, client_min=False, pdf=True, pyodide=True, whl=True):
    if client:
        ise_path = os.path.join(SRC_ROOT, 'pfsc-ise/dist')
        if not os.path.exists(ise_path):
            raise click.UsageError(f'Could not find {ise_path}. Have you built pfsc-ise yet?')
        if client_min:
            min_path = os.path.join(SRC_ROOT, 'pfsc-ise/dist/ise/ise.bundle.min.js')
            if not os.path.exists(min_path):
                raise click.UsageError(f'Could not find {min_path}. Did you build pfsc-ise for production yet?')

    if pdf:
        pdf_path = os.path.join(SRC_ROOT, 'pfsc-pdf/build/generic')
        if not os.path.exists(pdf_path):
            raise click.UsageError(f'Could not find {pdf_path}. Have you built pfsc-pdf yet?')

    #demo_path = os.path.join(SRC_ROOT, 'pfsc-demo-repos')
    #if not os.path.exists(demo_path):
    #    raise click.UsageError(f'Could not find {demo_path}. Have you cloned it?')

    versions = get_version_numbers()

    if pyodide:
        pyodide_version = versions["pyodide"]
        pyodide_path = os.path.join(SRC_ROOT, 'pyodide', f'v{pyodide_version}')
        if not os.path.exists(pyodide_path):
            raise click.UsageError(f'Could not find pyodide at expected version {pyodide_version}')

    if whl:
        whl_path = os.path.join(SRC_ROOT, 'whl')
        if release:
            whl_path = os.path.join(whl_path, 'release')
        if not os.path.exists(whl_path):
            advice = f'pfsc get wheels{" --release" if release else ""}'
            raise click.UsageError(f'Could not find wheels. Did you run `{advice}`?')
        pfsc_examp_version = versions['pfsc-examp']
        if not os.path.exists(os.path.join(whl_path, f'pfsc_examp-{pfsc_examp_version}-py3-none-any.whl')):
            raise click.UsageError(f'Did not find wheel for expected version {pfsc_examp_version} of pfsc-examp.')


@build.command()
@click.option('--dump', is_flag=True, help="Dump Dockerfile to stdout before building.")
@click.option('--dry-run', is_flag=True, help="Do not actually build; just print docker command.")
@click.option('--tar-path', help="Instead of building, save the context tar file to this path.")
@click.argument('tag')
def oca(dump, dry_run, tar_path, tag):
    """
    Build a `pise` (one-container app) docker image, and give it a TAG.

    This image is intended for casual users to run on their own machine.
    This is the full app, for anyone who simply wants to author Proofscape
    content repos. It is configured in "personal server mode" and comes with
    RedisGraph as the GDB.
    """
    if not dry_run:
        oca_readiness_checks(client=True, client_min=False, pdf=True, pyodide=True, whl=True)

    license_info = tools.license.gather_licensing_info()
    pfsc_topics = pathlib.Path(PFSC_MANAGE_ROOT) / 'topics' / 'pfsc'
    with open(pfsc_topics / 'templates' / 'combined_license_file_oca.txt') as f:
        license_template = f.read()
    with open(pfsc_topics / 'write_license_files.py') as f:
        wlf_script = f.read()

    from topics.pfsc import write_oca_eula_file
    from topics.pfsc import write_worker_and_web_supervisor_ini
    from topics.pfsc import write_proofscape_oca_dockerfile
    from topics.redis import write_redisgraph_ini
    with tempfile.TemporaryDirectory(dir=SRC_TMP_ROOT) as tmp_dir_name:
        with open(os.path.join(tmp_dir_name, 'license_info.json'), 'w') as f:
            f.write(json.dumps(license_info, indent=4))
        with open(os.path.join(tmp_dir_name, 'license_template.txt'), 'w') as f:
            f.write(license_template)
        with open(os.path.join(tmp_dir_name, 'write_license_files.py'), 'w') as f:
            f.write(wlf_script)
        with open(os.path.join(tmp_dir_name, 'eula.txt'), 'w') as f:
            eula = write_oca_eula_file(tag)
            f.write(eula)
        with open(os.path.join(tmp_dir_name, 'pfsc.ini'), 'w') as f:
            ini = write_worker_and_web_supervisor_ini(
                worker=False, web=True, use_venv=False, oca=True)
            f.write(ini)
        with open(os.path.join(tmp_dir_name, 'redisgraph.ini'), 'w') as f:
            ini = write_redisgraph_ini(use_conf_file=True)
            f.write(ini)
        with open(os.path.join(tmp_dir_name, 'oca_version.txt'), 'w') as f:
            f.write(tag)
        tmp_dir_rel_path = os.path.relpath(tmp_dir_name, start=SRC_ROOT)
        write_dockerignore_for_pyc()
        df = write_proofscape_oca_dockerfile(tmp_dir_rel_path)
        finalize(df, 'pise', tag, dump, dry_run, tar_path=tar_path)


@build.command()
@click.option('--dump', is_flag=True, help="Dump Dockerfile to stdout before building.")
@click.option('--dry-run', is_flag=True, help="Do not actually build; just print docker command.")
@click.argument('tag')
def dummy(dump, dry_run, tag):
    """
    Build a `pfsc-dummy-server` docker image, and give it a TAG.

    This image runs a Hello World flask app on port 7372, and is useful for
    testing the front-end (nginx) + web app combination (e.g. just testing
    SSL and basic auth, without putting a real app behind it).

    See also: `--dummy` switch to `pfsc deploy generate`.
    """
    from topics.dummy import write_web_py, write_dummy_server_dockerfile
    with tempfile.TemporaryDirectory(dir=SRC_TMP_ROOT) as tmp_dir_name:
        with open(os.path.join(tmp_dir_name, 'web.py'), 'w') as f:
            py = write_web_py()
            f.write(py)
        tmp_dir_rel_path = os.path.relpath(tmp_dir_name, start=SRC_ROOT)
        df = write_dummy_server_dockerfile(tmp_dir_rel_path)
        df = strip_headers(df)
        if dump:
            dump_text_with_title(df, 'Dockerfile')
        cmd = f'{DOCKER_CMD} build -f- -t pfsc-dummy-server:{tag} {SRC_ROOT}'
        print(cmd)
        if not dry_run:
            args = cmd.split()
            subprocess.run(args, input=df, text=True)


@build.command()
@click.option('--dump', is_flag=True, help="Dump Dockerfile and nginx.conf to stdout before building.")
@click.option('--dry-run', is_flag=True, help="Do not actually build; just print docker command.")
@click.argument('tag')
def static(dump, dry_run, tag):
    """
    Build a `pfsc-static-nginx` docker image, and give it a TAG.

    This image runs an Nginx web server that serves all static assets for a
    production deployment of the Proofscape ISE.
    """
    from topics.static import write_static_nginx_dockerfile, write_nginx_conf
    with tempfile.TemporaryDirectory(dir=SRC_TMP_ROOT) as tmp_dir_name:
        nc = write_nginx_conf()
        nc_path = os.path.join(tmp_dir_name, 'nginx.conf')
        with open(nc_path, 'w') as f:
            f.write(nc)
        tmp_dir_rel_path = os.path.relpath(tmp_dir_name, start=SRC_ROOT)
        df = write_static_nginx_dockerfile(tmp_dir_rel_path)
        df = strip_headers(df)
        if dump:
            dump_text_with_title(df, 'Dockerfile')
            dump_text_with_title(nc, nc_path)
        cmd = f'{DOCKER_CMD} build -f- -t pfsc-static-nginx:{tag} {SRC_ROOT}'
        print(cmd)
        if not dry_run:
            args = cmd.split()
            subprocess.run(args, input=df, text=True)


#@build.command()
# No longer making this a command, since we're now beyond v3.5.1.
# For the moment, keeping this here for historical purposes.
def gremlin():
    """
    Build a `gremlinserver:10mb` docker image.

    This image is the same as `tinkerpop/gremlin-server:3.5.1`, except
    configured so that TinkerGraph has max content length of 10 MB.

    When Apache Tinkerpop 3.5.2 is released, this should no longer be necessary.
    """
    from topics.gremlin import write_gremlin_dockerfile
    df = write_gremlin_dockerfile()
    cmd = f'{DOCKER_CMD} build -f- -t gremlinserver:10mb {SRC_ROOT}'
    print(cmd)
    args = cmd.split()
    subprocess.run(args, input=df, text=True)


@build.command()
@click.option('--dump', is_flag=True, help="Dump Dockerfile to stdout before building.")
@click.option('--dry-run', is_flag=True, help="Do not actually build; just print docker command.")
@click.argument('tag')
def elkjs_builder(dump, dry_run, tag):
    """
    Build a `elkjs-build-env` docker image, and give it a TAG.

    This image can be used to build elkjs, based on our custom ELK code.
    """
    from topics.elk import write_elk_build_env_dockerfile
    with tempfile.TemporaryDirectory(dir=SRC_TMP_ROOT) as tmp_dir_name:
        tmp_dir_rel_path = os.path.relpath(tmp_dir_name, start=SRC_ROOT)
        df = write_elk_build_env_dockerfile(tmp_dir_rel_path)
        df = strip_headers(df)
        if dump:
            dump_text_with_title(df, 'Dockerfile')
        cmd = f'{DOCKER_CMD} build -f- -t elkjs-build-env:{tag} {SRC_ROOT}'
        print(cmd)
        if not dry_run:
            args = cmd.split()
            subprocess.run(args, input=df, text=True)


@build.command()
@click.option('--dump', is_flag=True, help="Dump Dockerfile to stdout before building.")
@click.option('--dry-run', is_flag=True, help="Do not actually build; just print docker command.")
@click.argument('tag')
def redis(dump, dry_run, tag):
    """
    Build a `pfsc-redis` docker image, and give it a TAG.

    This image runs Redis with our custom redis.conf.
    """
    from topics.redis import write_redis_conf, write_pfsc_redis_dockerfile
    with tempfile.TemporaryDirectory(dir=SRC_TMP_ROOT) as tmp_dir_name:
        rc = write_redis_conf()
        rc_path = os.path.join(tmp_dir_name, 'redis.conf')
        with open(rc_path, 'w') as f:
            f.write(rc)
        tmp_dir_rel_path = os.path.relpath(tmp_dir_name, start=SRC_ROOT)
        df = write_pfsc_redis_dockerfile(tmp_dir_rel_path)
        df = strip_headers(df)
        if dump:
            dump_text_with_title(df, 'Dockerfile')
        cmd = f'{DOCKER_CMD} build -f- -t pfsc-redis:{tag} {SRC_ROOT}'
        print(cmd)
        if not dry_run:
            args = cmd.split()
            subprocess.run(args, input=df, text=True)

@build.command()
@click.option('--dump', is_flag=True, help="Dump Dockerfile to stdout before building.")
@click.option('--dry-run', is_flag=True, help="Do not actually build; just print docker command.")
@click.argument('tag')
def redisgraph(dump, dry_run, tag):
    """
    Build a `pfsc-redisgraph` docker image, and give it a TAG.

    This image is based on a redislabs/redisgraph image, and runs Redis with
    the RedisGraph module and with a custom redis.conf, which does frequent
    background dumps of the database.
    """
    from topics.redis import write_redisgraph_conf, write_pfsc_redisgraph_dockerfile
    with tempfile.TemporaryDirectory(dir=SRC_TMP_ROOT) as tmp_dir_name:
        rc = write_redisgraph_conf()
        rc_path = os.path.join(tmp_dir_name, 'redisgraph.conf')
        with open(rc_path, 'w') as f:
            f.write(rc)
        tmp_dir_rel_path = os.path.relpath(tmp_dir_name, start=SRC_ROOT)
        df = write_pfsc_redisgraph_dockerfile(tmp_dir_rel_path)
        df = strip_headers(df)
        if dump:
            dump_text_with_title(df, 'Dockerfile')
        cmd = f'{DOCKER_CMD} build -f- -t pfsc-redisgraph:{tag} {SRC_ROOT}'
        print(cmd)
        if not dry_run:
            args = cmd.split()
            subprocess.run(args, input=df, text=True)

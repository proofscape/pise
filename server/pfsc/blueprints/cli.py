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

"""
CLI commands
"""

import json
import pathlib

import click
from flask.cli import with_appcontext
from pygit2 import clone_repository, GitError, RemoteCallbacks

import pfsc.constants
from pfsc.constants import UserProps
from pfsc import pfsc_cli, make_app
from pfsc.build.lib.libpath import get_modpath
from pfsc.build import build_module, build_release
from pfsc.build.repo import RepoInfo
from pfsc.checkinput import check_type, IType
from pfsc.gdb import get_gdb, get_graph_writer, get_graph_reader
from pfsc.excep import PfscExcep, PECode


@pfsc_cli.command('build')
@click.argument('libpath')
@click.option('-t', '--tag', default="WIP",
              help='Build the module at version TEXT. Default: "WIP".')
@click.option('-r', '--recursive', is_flag=True, default=False,
              help='Also build all submodules, recursively.')
@click.option('-v', '--verbose', is_flag=True, default=False)
@click.option('--auto-deps', is_flag=True, default=False,
              help='Automatically clone and build missing dependencies, recursively.')
@with_appcontext
def build(libpath, tag, recursive, verbose=False, auto_deps=False):
    """
    Build the proofscape module at LIBPATH.

    Note: To build requires a configuration, since we need to know where are the
    `lib` and `build` dirs, and what is our graph database URI.
    To set the configuration, set the FLASK_CONFIG environment variable.

    So, for example, you might use

        $ export FLASK_APP=web
        $ export FLASK_CONFIG=localdev

    before attempting to build from the commandline.
    """
    # By invoking the `make_app` function with no arguments, we allow it to
    # determine the configuration based on the FLASK_CONFIG environment variable.
    app = make_app()
    # However we force PSM, since when you are working from the CLI you should
    # be able to do whatever you want.
    app.config["PERSONAL_SERVER_MODE"] = True
    with app.app_context():
        if auto_deps:
            auto_deps_build(libpath, tag, recursive, verbose=verbose)
        else:
            failfast_build(libpath, tag, recursive, verbose=verbose)


def failfast_build(libpath, tag, recursive, verbose=False):
    """
    This is the regular type of build, which simply fails if the repo is not
    present, or has a dependency that has not yet been built.
    """
    try:
        if tag != pfsc.constants.WIP_TAG:
            build_release(libpath, tag, verbose=verbose)
        else:
            modpath = get_modpath(libpath)
            build_module(modpath, recursive=recursive, verbose=verbose)
    except PfscExcep as e:
        code = e.code()
        data = e.extra_data()
        if code == PECode.INVALID_REPO:
            raise click.UsageError(f'The repo {data["repopath"]} does not appear to be present.')
        elif code == PECode.VERSION_NOT_BUILT_YET:
            raise click.UsageError(str(e))
        raise


MAX_AUTO_DEPS_RECURSION_DEPTH = 32


def auto_deps_build(libpath, tag, recursive, verbose=False):
    """
    Do a build with the "auto dependencies" feature enabled.
    This means that when dependencies have not been built yet, we try to build
    them, and when repos aren't present at all, we try to clone them.
    We keep trying until either the initial build request succeeds, we
    exceep the maximum allowed recursion depth set by the
    `MAX_AUTO_DEPS_RECUSION_DEPTH` variable, or some other error occurs.
    """
    jobs = [(libpath, tag, recursive, verbose)]
    while 0 < len(jobs) <= MAX_AUTO_DEPS_RECURSION_DEPTH:
        job = jobs.pop()
        libpath, tag, recursive, verbose = job
        print('-'*80)
        print(f'Building {libpath}@{tag}...')
        try:
            if tag != pfsc.constants.WIP_TAG:
                build_release(libpath, tag, verbose=verbose)
            else:
                modpath = get_modpath(libpath)
                build_module(modpath, recursive=recursive, verbose=verbose)
        except PfscExcep as e:
            code = e.code()
            data = e.extra_data()
            if code == PECode.INVALID_REPO:
                # The repo we tried to build is not present at all.
                # Clone and retry.
                repopath = data["repopath"]
                print(f'The repo {repopath} does not appear to be present.')
                print('Cloning...')
                clone(repopath, verbose=verbose)
                # Retry
                jobs.append(job)
            elif code == PECode.VERSION_NOT_BUILT_YET:
                # We have a dependency that hasn't been built yet. Try to build it.
                repopath = data["repopath"]
                version = data["version"]
                print(f'Dependency {repopath}@{version} has not been built yet.')
                print('Attempting to build...')
                # First requeue the job that failed.
                jobs.append(job)
                # Now add a job on top of it, for the dependency.
                jobs.append((repopath, version, True, verbose))
            else:
                raise
    if len(jobs) > MAX_AUTO_DEPS_RECURSION_DEPTH:
        raise PfscExcep('Exceeded max recursion depth.', PECode.AUTO_DEPS_RECUSION_DEPTH_EXCEEDED)


class ProgMon(RemoteCallbacks):

    def __init__(self, verbose=True, credentials=None, certificate=None):
        super().__init__(credentials=credentials, certificate=certificate)
        self.verbose = verbose

    def transfer_progress(self, stats):
        if self.verbose:
            print(f'Indexing objects: ({stats.indexed_objects}/{stats.total_objects})')


def clone(repopath, verbose=False):
    ri = RepoInfo(repopath)
    src_url = ri.write_url()
    dst_dir = ri.abs_fs_path_to_dir
    pathlib.Path(dst_dir).mkdir(parents=True, exist_ok=True)
    pm = ProgMon(verbose=verbose)
    try:
        result = clone_repository(src_url, dst_dir, callbacks=pm)
    except GitError as e:
        msg = 'Error while attempting to clone remote repo:\n%s' % e
        raise PfscExcep(msg, PECode.REMOTE_REPO_ERROR)
    return result


###############################################################################

@pfsc_cli.group('approval')
def approval():
    """
    Manage approvals of display widgets.
    """
    pass


@approval.command('set')
@click.argument('widgetpath')
@click.argument('version')
def set_approval(widgetpath, version):
    """
    Mark a display widget as approved at a particular (full) version.
    """
    gw = get_graph_writer()
    gw.set_approval(widgetpath, version, True)


@approval.command('unset')
@click.argument('widgetpath')
@click.argument('version')
def unset_approval(widgetpath, version):
    """
    Mark a display widget as NOT approved at a particular (full) version.
    """
    gw = get_graph_writer()
    gw.set_approval(widgetpath, version, False)


@approval.command('list')
@click.argument('annopath')
@click.argument('version')
def list_approvals(annopath, version):
    """
    List all approved widgets under a given annotation,
    at a particular (full) version.
    """
    gr = get_graph_reader()
    approvals = gr.check_approvals_under_anno(annopath, version)
    if approvals:
        for lp in sorted(approvals):
            print(lp)
    else:
        print(f'No widgets have been approved under {annopath} at {version}.')

###############################################################################

@pfsc_cli.group('hosting')
def hosting():
    """
    Manage hosting permissions.
    """
    pass


def get_owner(libpath):
    gr = get_graph_reader()
    user = gr.load_owner(libpath)
    if user is None:
        msg = f'Owner of {libpath} does not exist as a user on this server.'
        raise click.UsageError(msg)
    return user


def commit_user_changes(user, changed):
    if changed:
        user.commit_properties()


@hosting.command('list')
@click.argument('libpath')
def list_hosting(libpath):
    """
    List the current hosting settings for a given user (true or org) or repo.
    """
    user = get_owner(libpath)
    p = libpath.split('.')
    n = len(p)
    settings = user.prop(UserProps.K_HOSTING)
    if n > 2:
        _, repo_name = user.split_owned_repopath(libpath)
        if repo_name is None:
            raise click.UsageError('Pass a userpath or repopath.')
        settings = settings.get(repo_name)
    print(json.dumps(settings, indent=4))


@hosting.command('set')
@click.option('-s', '--status', required=True, type=click.Choice([
    'G', 'P', 'D', 'U',
    UserProps.V_HOSTING.GRANTED, UserProps.V_HOSTING.PENDING, UserProps.V_HOSTING.DENIED,
    "UNSET"
], case_sensitive=False), help="The desired hosting status. Use 'U' or 'UNSET' to remove any existing notation.")
@click.option('-v', '--version', help="Set the permission for a particular version of one repo.")
@click.option('-h', '--hash', help="When granting permission, set the accepted Git commit hash. At least 7 chars.")
@click.argument('libpath')
def set_hosting(status, version, hash, libpath):
    """
    Make a hosting setting for a user (true or org), repo, or version.

    User: To make a hosting setting for a user, pass the userpath (host.user)
    as the libpath. This works for both true users, and org users.
    It makes a default setting for this user, for all repos,
    at all versions, and overrides the default hosting stance of the server.
    For example, on a server with BY_REQUEST as the default stance, set a
    particular user to GRANTED to give this user total freedom. Passing 'U'
    or 'UNSET' removes only this default setting, not any more specific
    settings that may have been made.

    Repo: To make a hosting setting for a repo, pass the repopath as the
    libpath. This makes a default setting for this repo, at all versions, and
    overrides any default setting for the user, and the default hosting stance
    of the server. For example, on a server with BY_REQUEST as the default
    stance, set a particular repo to GRANTED to say this user may host this
    repo at any version. Passing 'U' or 'UNSET' removes only this default
    setting, not any more specific settings that may have been made.

    Version: To make a hosting setting for a repo at a particular version,
    pass the repopath as the libpath, and set the version using the -v or
    --version option. This overrides any default settings (for the repo, the
    user, or the server as a whole).

    When making a setting of GRANTED for a particular version, you must
    use the -h or --hash option to record the Git commit hash of the version
    that has been approved. (Pass at least seven characters, up to the whole
    hash.) The system will refuse to build the repo at this version unless the
    hash matches.
    """
    p = libpath.split('.')
    n = len(p)
    if n < 2 or n > 3:
        raise click.UsageError("Libpath should be userpath or repopath.")

    if version:
        if n == 2:
            raise click.UsageError("Version can only be specified for a repo, not a user.")
        try:
            check_type('version', version, {
                'type': IType.FULL_VERS,
                'allow_WIP': False,
            })
        except PfscExcep as e:
            raise click.UsageError(str(e))

    status = {
        "G": UserProps.V_HOSTING.GRANTED,
        "P": UserProps.V_HOSTING.PENDING,
        "D": UserProps.V_HOSTING.DENIED,
        "U": None,
        "UNSET": None,
    }.get(status, status)

    if version and status == UserProps.V_HOSTING.GRANTED and not hash:
        raise click.UsageError("Hash must be provided when granting hosting at a version.")

    if hash:
        if (not version) or status != UserProps.V_HOSTING.GRANTED:
            raise click.UsageError("Hash can only be provided when granting hosting at a version.")
        hash = hash.lower()
        try:
            int(hash, 16)
        except ValueError:
            raise click.UsageError("Invalid hash")
        if len(hash) < 7:
            raise click.UsageError("Hash must be at least 7 chars long.")

    user = get_owner(libpath)
    try:
        changed = user.set_hosting(status, libpath, version, hash)
        commit_user_changes(user, changed)
    except PfscExcep as e:
        print(e)

###############################################################################

# TODO: Make "setup index" commands for other GDB systems

@pfsc_cli.command('setup_indexes_neo4j')
def setup_indexes_neo4j():
    """
    Set up indexes if using Neo4j.

    Neo4j server must be accessible for this command to work.
    """
    app = make_app()
    with app.app_context():
        ML_types = """
        Module
        Deduc
        Anno
        Node
        Ghost
        Special
        Widget
        """.split()
        MR_types = """
        Version
        """.split()
        gdb = get_gdb()
        with gdb.session() as sesh:
            # For Neo4j v4.0.x we need to use `CALL db.indexes()`.
            # When we upgrade to v4.2.x we can use `SHOW INDEXES` instead.
            res = sesh.run('CALL db.indexes()')
            existing_names = [r['name'] for r in res]

            for t in ML_types:
                name = f'{t}ML'
                if name in existing_names:
                    print(f'{name} already exists')
                else:
                    cmd = f'CREATE INDEX {name} FOR (u:{t}) ON (u.major, u.libpath)'
                    print(cmd)
                    sesh.run(cmd)

            for t in MR_types:
                name = f'{t}MR'
                if name in existing_names:
                    print(f'{name} already exists')
                else:
                    cmd = f'CREATE INDEX {name} FOR (u:{t}) ON (u.major, u.repopath)'
                    print(cmd)
                    sesh.run(cmd)

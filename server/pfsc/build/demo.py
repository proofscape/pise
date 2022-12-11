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
import re
from datetime import datetime, timedelta, timezone

from pygit2 import init_repository
from rq.registry import ScheduledJobRegistry
from rq.exceptions import NoSuchJobError

import pfsc.constants
from pfsc import check_config, get_app
from pfsc.rq import get_rqueue
from pfsc.util import (
    casual_time_delta,
    recycle,
    count_pfsc_modules,
)
from pfsc.build.repo import get_repo_part, RepoInfo, RepoFamily, add_all_and_commit
from pfsc.gdb import get_graph_writer, building_in_gdb
from pfsc.excep import PfscExcep, PECode


demo_repo_lead_comment_template = """\
# NOTE: This module is part of a demo repo that is scheduled to be
# DELETED at or around %(deleted_at)s, i.e.
# %(delta)s from the time this module was created.
# Please plan accordingly!
#
# Also, if you close your browser (or delete your cookies) you will not be able
# to access this copy of the demo repo again, even if it has not been deleted yet.
#
# Tips:
#   * Right-click tree items for many options
#   * Ctrl-B to build, Ctrl-S to save in editor (or right-click background)

"""


license_header_pattern = re.compile('(# --------.+Copyright.+?-------- #\n)', re.S)


def make_demo_repo_lead_comment(libpath=None):
    """
    Write the comment text to go at the top of each module in a demo repo.

    :param libpath: Optionally, you may pass any libpath belonging to the
      repo. If so, we look for an existing scheduled job to delete the demo
      repo to which this libpath belongs. If we find such a job, we write the
      text accordingly; if not, we return an empty string.

      If instead you leave `libpath` equal to `None` then we assume you want
      text appropriate for a demo repo being built right now, and we base the
      deletion time on the configured hours to live for demo repos.

    :return: comment text, possibly empty (see above)
    """
    now = datetime.utcnow()
    now = now.replace(tzinfo=timezone.utc)
    if libpath is None:
        delta = timedelta(hours=check_config("DEMO_REPO_HOURS_TO_LIVE"))
        deletion_time = now + delta
    else:
        repopath = get_repo_part(libpath)
        deletion_time = check_demo_repo_deletion_time(repopath)
        if deletion_time is None:
            return ''
        delta = deletion_time - now
        if delta.total_seconds() < 0:
            return ''
    return demo_repo_lead_comment_template % {
        'deleted_at': deletion_time.strftime('%H:%M:%S UTC on %a %b %d'),
        'delta': casual_time_delta(delta),
    }

def demo_repo_deletion_job_id(repopath):
    return f'{pfsc.constants.DELETE_DEMO_REPO_JOB_PREFIX}:{repopath}'

def schedule_demo_repo_for_deletion(repopath, delta=None):
    if delta is None:
        delta = timedelta(hours=check_config("DEMO_REPO_HOURS_TO_LIVE"))
    job_id = demo_repo_deletion_job_id(repopath)
    get_rqueue(pfsc.constants.MAIN_TASK_QUEUE_NAME).enqueue_in(
        delta, delete_demo_repo_with_app, args=[repopath], job_id=job_id)

def cancel_scheduled_demo_repo_deletion(repopath):
    job_id = demo_repo_deletion_job_id(repopath)
    registry = ScheduledJobRegistry(queue=get_rqueue(pfsc.constants.MAIN_TASK_QUEUE_NAME))
    return registry.remove(job_id, delete_job=True)

def check_demo_repo_deletion_time(repopath):
    """
    :param repopath: the libpath of an existing demo repo
    :return: the datetime (in UTC) at which this repo is scheduled
      to be deleted, or None if we find no such deletion job.
    """
    job_id = demo_repo_deletion_job_id(repopath)
    registry = ScheduledJobRegistry(queue=get_rqueue(pfsc.constants.MAIN_TASK_QUEUE_NAME))
    try:
        deletion_time = registry.get_scheduled_time(job_id)
    except NoSuchJobError:
        return None
    return deletion_time

def make_demo_repo(repo_info, progress=None, dry_run=False):
    """
    Make a new demo repo.

    :param repo_info: RepoInfo for the desired demo repopath.
    :param progress: optional progress monitor function
    :param dry_run: set True to only print indications of actions, but not do anything.
    :return: nothing
    :raises: FileExistsError if the desired repo already exists
    """
    assert isinstance(repo_info, RepoInfo)
    assert repo_info.is_demo()
    assert repo_info.user != "_"

    dst_dir = repo_info.abs_fs_path_to_dir
    if dry_run:
        print(f'Make dirs: {dst_dir}')
    else:
        os.makedirs(dst_dir, exist_ok=False)

    demo_root = check_config("PFSC_DEMO_ROOT")
    src_dir = os.path.join(demo_root, repo_info.project)
    N = count_pfsc_modules(src_dir)

    if N == 0:
        msg = f'Demo repo template `{repo_info.project}` not found.'
        raise PfscExcep(msg, PECode.DEMO_REPO_TEMPLATE_NOT_FOUND)

    comment = make_demo_repo_lead_comment()
    cur_count = 0
    for P, D, F in os.walk(src_dir):
        for filename in F:
            if filename.endswith('.pfsc'):
                src = os.path.join(P, filename)
                rel = os.path.relpath(src, start=src_dir)
                dst = os.path.join(dst_dir, rel)
                if dry_run:
                    print(f'Copy {src} {dst}')
                else:
                    with open(src, 'r') as f:
                        text = f.read()
                    # Put the deletion comment after the license header, if present.
                    text, c = license_header_pattern.subn(
                        '\\1\n' + comment, text, count=1
                    )
                    if c == 0:
                        text = comment + text
                    with open(dst, 'w') as f:
                        f.write(text)
                    cur_count += 1
                    if progress:
                        progress(None, cur_count, N)
        for dirname in D:
            src = os.path.join(P, dirname)
            rel = os.path.relpath(src, start=src_dir)
            dst = os.path.join(dst_dir, rel)
            if dry_run:
                print(f'Make dir {dst}')
            else:
                os.mkdir(dst)
    if not dry_run:
        repo = init_repository(dst_dir)
        add_all_and_commit(repo, "Initial commit")


def delete_demo_repo_with_app(repopath, dry_run=False):
    """
    Run `delete_demo_repo` after ensuring we have an app context.
    Use this when asking an RQ worker to delete a demo repo.
    """
    app, _ = get_app()
    with app.app_context():
        delete_demo_repo(repopath, dry_run=dry_run)

def delete_demo_repo(repopath, dry_run=False):
    """
    Delete a demo repo completely:
        * move LIB repo dir to recycling bin
        * remove LIB user dir if now empty
        * move BUILD repo dir to recycling bin
        * remove BUILD user dir if now empty
        * detach & delete any j-nodes for this repo in the index

    Can safely be called if repo has already been completely or partially
    deleted; will do only those steps left to be done.

    :param repopath: the libpath of the demo repo to be deleted.
    :param dry_run: set True to only print indications of actions, but not do anything.
    :return: nothing
    :raises: AssertionError if given repopath does not point into the DEMO family.
    """
    ri = RepoInfo(repopath)
    assert ri.is_demo()

    # Clean up LIB dir:
    lib_root = check_config("PFSC_LIB_ROOT")
    expected_prefix = os.path.join(lib_root, RepoFamily.DEMO)
    repo_dir = ri.abs_fs_path_to_dir
    shadow_repo_dir = ri.get_shadow_repo_path()
    user_dir = ri.abs_fs_path_to_user_dir
    assert user_dir.startswith(expected_prefix)
    assert repo_dir.startswith(expected_prefix)
    assert shadow_repo_dir.startswith(expected_prefix)
    if os.path.exists(repo_dir):
        if dry_run:
            print(f'Recycle {repo_dir}')
        else:
            recycle(repo_dir)
    if os.path.exists(shadow_repo_dir):
        if dry_run:
            print(f'Recycle {shadow_repo_dir}')
        else:
            recycle(shadow_repo_dir)
    if os.path.exists(user_dir):
        # Was it the last repo for this user?
        remaining = os.listdir(user_dir)
        if not remaining:
            cmd = f'rmdir {user_dir}'
            if dry_run:
                print(cmd)
            else:
                os.system(cmd)

    # If we're not building in the GDB, then we need to clean up the BUILD dir.
    # If we are, then there's nothing to do here, since all build products will
    # be cleaned up when we clean up the index, below.
    if not building_in_gdb():
        build_root = check_config("PFSC_BUILD_ROOT")
        expected_prefix = os.path.join(build_root, RepoFamily.DEMO)
        user_build_dir = ri.get_user_build_dir()
        repo_build_dir = ri.get_repo_build_dir()
        assert user_build_dir.startswith(expected_prefix)
        assert repo_build_dir.startswith(expected_prefix)
        if os.path.exists(repo_build_dir):
            if dry_run:
                print(f'Recycle {repo_build_dir}')
            else:
                recycle(repo_build_dir)
        if os.path.exists(user_build_dir):
            # Was it the last repo for this user?
            remaining = os.listdir(user_build_dir)
            if not remaining:
                cmd = f'rmdir {user_build_dir}'
                if dry_run:
                    print(cmd)
                else:
                    os.system(cmd)

    # Clean up the INDEX:
    gw = get_graph_writer()
    if dry_run:
        infos = gw.reader.get_versions_indexed(repopath, include_wip=True)
        if infos:
            print('Found indexed versions. Will clear index.')
    else:
        gw.delete_everything_under_repo(repopath)

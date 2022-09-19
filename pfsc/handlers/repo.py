# --------------------------------------------------------------------------- #
#   Proofscape Server                                                         #
#                                                                             #
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

from flask_login import current_user
from pygit2 import clone_repository, GitError, RemoteCallbacks

from pfsc import check_config
import pfsc.constants
from pfsc.permissions import have_repo_permission, ActionType
from pfsc.excep import PfscExcep, PECode
from pfsc.handlers import RepoTaskHandler
from pfsc.checkinput import IType
from pfsc.checkinput.version import check_full_version
from pfsc.build import build_module, build_release
from pfsc.build.manifest import has_manifest, load_manifest
from pfsc.build.repo import RepoInfo
from pfsc.build.demo import (
    make_demo_repo,
    schedule_demo_repo_for_deletion,
    delete_demo_repo
)
from pfsc.session import get_demo_username_from_session


class ProgMon(RemoteCallbacks):

    def __init__(self, updater, credentials=None, certificate=None):
        super().__init__(credentials=credentials, certificate=certificate)
        self.updater = updater

    def transfer_progress(self, stats):
        self.updater.update(None, stats.indexed_objects, stats.total_objects)


class RepoLoader(RepoTaskHandler):
    """
    Supplies the manifest for a repo, at a given version.
    Supports optionally building and even cloning the repo, as needed.
    """

    def __init__(self, request_info, room):
        RepoTaskHandler.__init__(self, request_info, room)
        self.repo_info = None
        self.will_return_model_immediately = False
        self.will_scan = False
        self.will_build = False
        self.will_clone = False
        self.will_make_demo = False
        self.version = None
        self.is_wip = None
        self.action = ''
        self.required_hash = None

    def check_input(self):
        self.check({
            "REQ": {
                'repopath': {
                    'type': IType.LIBPATH,
                    'repo_format': True
                },
            },
            "OPT": {
                'vers': {
                    'type': IType.FULL_VERS,
                    'default_cooked': None,
                },
                'doBuild': {
                    'type': IType.BOOLEAN,
                    'default_cooked': False
                },
                'doClone': {
                    'type': IType.BOOLEAN,
                    'default_cooked': False
                },
            }
        })

    def check_permissions(self, repopath, vers):
        # We're going to do a more complicated set of tests when we compute
        # the set of implicated repopaths, so we just pass here.
        pass

    def confirm(self, repopath, vers):
        self.repo_info = ri = RepoInfo(repopath.value)

        if vers is None:
            vers_str = ri.get_default_version()
            vers = check_full_version('', vers_str, {})
        self.version = vers.full
        self.is_wip = vers.isWIP

        if ri.is_demo():
            msg = None
            if not check_config("PROVIDE_DEMO_REPOS"):
                msg = 'Demo repos cannot be loaded on this server.'
            elif not vers.isWIP:
                msg = 'Demo repos can only be loaded @WIP.'
            if msg:
                raise PfscExcep(msg, PECode.DEMO_REPO_NOT_ALLOWED)
            demo_username = get_demo_username_from_session(supply_if_absent=True)
            ri.user = demo_username
            true_repopath = ri.rebuild_libpath()
            self.repo_info = RepoInfo(true_repopath)
        else:
            self.check_wip_mode(vers, subject='Repos', verb='opened')

        # Both the repopath and the version we're finally ready to try to load
        # can be different from the values the user passed. The repopath can
        # change in the case of a demo repo, and the version can change if the
        # user omitted it, and we had to choose the default version.
        # Therefore we set both values as response fields.
        self.set_response_field('repopath', self.repo_info.libpath)
        self.set_response_field('version', vers.full)

    def compute_implicated_repopaths(self, doBuild, doClone):
        repopath = self.repo_info.libpath

        is_privileged = have_repo_permission(ActionType.BUILD, repopath, self.version)
        is_wip = self.is_wip
        is_present = self.repo_info.is_dir
        is_clonable = self.repo_info.is_remote()
        is_built = is_present and has_manifest(repopath, version=self.version)

        self.set_response_field('privileged', is_privileged)

        is_owner = False
        if current_user.is_authenticated:
            # If client is logged in, it will be helpful to report the hosting
            # status. (If the client is not the repo owner, the status will
            # just be "DOES_NOT_OWN".)
            status, hash = current_user.hosting_status(repopath, self.version)
            self.required_hash = hash
            self.set_response_field('hosting', status)
            if current_user.owns_repo(repopath):
                is_owner = True

        if is_privileged or is_owner:
            # In this case it's okay to learn things like whether the repo has
            # been built yet or not, so now we can record that response field.
            self.set_response_field('built', is_built)
            self.set_response_field('present', is_present)
            self.set_response_field('clonable', is_clonable)

        if is_privileged:
            if is_built:
                if is_wip:
                    self.will_scan = True
                # The model is built, and, since you are privileged, it doesn't matter whether it's WIP
                # or not; we can provide the model to you.
                self.will_return_model_immediately = True
            else:
                # The model is not built yet, but you are privileged, so building and/or cloning may be afoot.
                self.maybe_take_async_action(repopath, is_wip, doBuild, doClone)
        elif is_wip:
            # You're not privileged, and you're asking for WIP. Complete non-starter.
            return
        elif is_built:
            # You're not privileged, but you're asking for a numbered release that has been built
            # at this server. We can provide that for you.
            self.will_return_model_immediately = True
        else:
            # You asked for a numbered release. Sorry, it's not built yet, and you're not privileged.
            return

    def maybe_take_async_action(self, repopath, is_wip, doBuild, doClone):
        is_present = self.repo_info.is_dir
        is_clonable = self.repo_info.is_remote()
        is_demo = self.repo_info.is_demo()
        if is_present:
            if is_wip:
                self.will_scan = True
            if doBuild:
                self.will_build = True
        elif is_demo:
            self.will_make_demo = True
            self.will_build = True
            self.require_in_session(
                pfsc.constants.DEMO_USERNAME_SESSION_KEY,
                self.repo_info.user
            )
        elif is_clonable and doClone:
            self.will_clone = True
            if doBuild:
                self.will_build = True
        if self.need_lock():
            self.implicated_repopaths = {repopath}
        for plan in ['will_build', 'will_clone', 'will_make_demo']:
            self.set_response_field(plan, getattr(self, plan))

    def need_lock(self):
        return self.will_build or self.will_clone or self.will_make_demo

    def load_model(self):
        # The manifest for a numbered release never changes, so we can use a
        # constant cache control code for that case.
        ccc = None if self.version == pfsc.constants.WIP_TAG or check_config("BYPASS_CACHE_FOR_REPO_MODEL_LOAD") else 1
        repopath = self.repo_info.libpath
        manifest = load_manifest(repopath, cache_control_code=ccc, version=self.version)
        root = manifest.get_root_node()
        model = []
        root.build_relational_model(model)
        return model

    def emit_repo_built_event(self):
        # As a part of our security model, we employ the "notice and pickup" pattern.
        # That means that at the end of a long-running task, we do not assume that we
        # can emit the result to an authenticated user. Instead, we emit a notice.
        # The user must then make another https request to retrieve the result.
        self.emit("listenable", {
            'type': 'repoIsBuilt',
            'repopath': self.repo_info.libpath,
            'version': self.version,
        })

    def emit_repo_present_event(self):
        self.emit("listenable", {
            'type': 'repoIsPresent',
            'repopath': self.repo_info.libpath,
        })

    def go_ahead(self):
        if self.will_scan:
            fs_model = self.repo_info.load_fs_model()
            self.set_response_field('fs_model', fs_model)
        if self.will_return_model_immediately:
            model = self.load_model()
            self.set_response_field('model', model)
        else:
            cloned = False
            built = False
            if self.will_clone:
                self.clone()
                # Our RepoInfo currently thinks the directory is not a git repo,
                # since, until now, there was nothing there. We need it to recognize
                # that there is now a repo there, so we ask it to check the libpath again.
                self.repo_info.check_libpath()
                cloned = True
                self.set_response_field('cloned', True)
            if self.will_make_demo:
                self.make_demo_repo()
                self.set_response_field('made_demo', True)
            if self.will_build:
                self.rebuild()
                self.set_response_field('built', True)
                built = True
            self.emit_progress_complete()
            # To make things simpler for the client, we only emit one
            # event: "present" OR "built", but not both.
            if cloned and not built:
                self.emit_repo_present_event()
            if built:
                self.emit_repo_built_event()

    def clone(self):
        src_url = self.repo_info.write_url()
        dst_dir = self.repo_info.abs_fs_path_to_dir
        os.makedirs(os.path.dirname(dst_dir), exist_ok=True)
        self.action = 'Cloning... '
        pm =  ProgMon(self)
        try:
            clone = clone_repository(src_url, dst_dir, callbacks=pm)
        except GitError as e:
            msg = 'Error while attempting to clone remote repo:\n%s' % e
            raise PfscExcep(msg, PECode.REMOTE_REPO_ERROR)
        return clone

    def fetch(self, remote_name='origin'):
        try:
            remote = self.repo_info.git_repo.remotes[remote_name]
        except KeyError:
            msg = f'Repo {self.repo_info.libpath} has no remote "{remote_name}"'
            raise PfscExcep(msg, PECode.REMOTE_REPO_ERROR)

        self.action = 'Fetching... '
        pm = ProgMon(self)
        # In testing, found it could take two attempts for fetch to work. On
        # first attempt, get "_pygit2.GitError: SecureTransport error: connection closed via error",
        # then second attempt works. This was in manual testing, and only after waiting
        # several minutes between forming the Repository object, and calling fetch.
        # So we might not encounter it in practice, but to be on the safe side
        # we give it several tries before actually calling it an error.
        for i in range(5):
            try:
                t_prog = remote.fetch(callbacks=pm)
            except GitError as e:
                pass
            else:
                break
        else:
            msg = f'Error while attempting to fetch from remote repo:\n{e}'
            raise PfscExcep(msg, PECode.REMOTE_REPO_ERROR)
        return t_prog

    def check_hash(self):
        if self.required_hash:
            actual_hash = self.repo_info.get_hash_of_ref(self.version)
            if not actual_hash.lower().startswith(self.required_hash.lower()):
                msg = (
                    f'The Git commit {actual_hash} for {self.version}'
                    f' does not match the expected commit {self.required_hash}.'
                )
                raise PfscExcep(msg, PECode.BAD_HASH)

    def rebuild(self):
        self.action = ''
        if self.version == pfsc.constants.WIP_TAG:
            return build_module(self.repo_info.libpath, recursive=True, progress=self.update)
        else:
            if not self.repo_info.has_version_tag(self.version):
                self.fetch()
                self.action = ''
            self.check_hash()
            return build_release(self.repo_info.libpath, self.version, progress=self.update)

    def make_demo_repo(self):
        self.action = 'Make demo repo...'
        try:
            make_demo_repo(self.repo_info, progress=self.update)
        except Exception as e:
            # The delete operation works even on partially-built demo repos,
            # so should serve as a good cleanup here.
            delete_demo_repo(self.repo_info.libpath)
            self.emit_progress_crashed()
            raise e
        else:
            # For testing:
            #from datetime import timedelta
            #delta = timedelta(seconds=60)
            delta = None
            schedule_demo_repo_for_deletion(self.repo_info.libpath, delta=delta)

    def update(self, op_code, cur_count, max_count=None, message=''):
        """
        Implements GitPython's `RemoteProgress` interface.
        Now that we are using pygit2 instead of GitPython, maybe this could
        be revised.
        """
        if self.action:
            message = self.action + message
        self.emit("progress", {
            'job': self.job_id,
            'action': self.action,
            'fraction_complete': cur_count / (max_count or 100.0),
            'message': message
        })

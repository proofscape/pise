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

from flask import has_request_context
from flask_login import current_user

from pfsc import check_config, get_config_class
from pfsc.constants import WIP_TAG
from pfsc.session import repopath_is_demo_for_session
from config import ProductionConfig


def check_is_psm():
    """
    Check safely whether we are currently configured in personal server mode.

    The "safe" check means that, if we are using the `ProductionConfig`, then
    having PERSONAL_SERVER_MODE set is not enough; we must also find that
    IS_PFSC_RQ_WORKER is set. This is so that PSM can still be used to grant
    RQ workers the power to carry out their jobs, while in production, but so
    that the PSM setting is not, itself, a single point of failure.

    The env var IS_PFSC_RQ_WORKER is set by the worker.py script that starts
    up an RQ worker, and should never be set under any other circumstances.
    """
    config_class = get_config_class()
    in_production = (config_class == ProductionConfig)
    psm_is_set = check_config("PERSONAL_SERVER_MODE")
    is_rq_worker = os.getenv("IS_PFSC_RQ_WORKER", False)
    if in_production:
        return is_rq_worker and psm_is_set
    else:
        return psm_is_set


class ActionType:
    """
    Actions on repos:

    READ includes:
        - Load the contents of a source module belonging to the repo
        - Load a built product (dashgraph or annotation) from the repo
        - Get indexing information about the repo, such as enrichments
            it defines (which may come up in a query on any object, belonging
            to this repo or another)

    WRITE includes:
        - Alter the contents of any source module in the working copy
        - Add a new module
        - Rename a module

    BUILD means:
        - Load modules and record their built products (in NFS or GDB),
          and record indexing information (in GDB)
    """
    READ = "READ"
    WRITE = "WRITE"
    BUILD = "BUILD"


def have_repo_permission(action, repopath, version):
    """
    Say whether we have permission to "work with" a given repo, at a given
    version. This means actions such as:
        * loading source or products at WIP
        * writing
        * building
        * adding a module
        * renaming a module

    :param action: a value of the ActionType enum class, stating which type
        of action you are trying to take.
    :param repopath: the libpath of the repo.
    :param version: the version (string) of the repo. Only when attempting to
        build a release as the repo owner is a full version required;
        otherwise, all that matters is whether it is equal to WIP or not.
    :return: boolean
    """
    is_wip = (version == WIP_TAG)
    allow_wip = check_config("ALLOW_WIP")
    is_psm = check_is_psm()
    admins_can_release = check_config("ADMINS_CAN_BUILD_RELEASES")

    is_demo_for_session = False
    is_admin = False
    is_owner = False
    if has_request_context():
        is_demo_for_session = repopath_is_demo_for_session(repopath)
        if current_user.is_authenticated:
            is_admin = current_user.is_admin()
            is_owner = current_user.owns_repo(repopath)

    if action == ActionType.READ:
        if not is_wip:
            return True
        if is_demo_for_session:
            return True
        if allow_wip:
            # Blocking WIP _reads_ on no-WIP servers may seem extreme, but it's
            # designed to avoid weird, inconsistent states, like having a module
            # open for editing in the client, while the server continually
            # refuses to record changes.
            if is_psm or is_owner:
                return True
        return False

    if action == ActionType.WRITE:
        if not is_wip:
            # You shouldn't even be requesting this, as it makes no sense to
            # try to write to a repo except @WIP!
            return False
        if is_demo_for_session:
            return True
        if allow_wip:
            if is_psm or is_owner:
                return True
        return False

    if action == ActionType.BUILD:
        if is_demo_for_session:
            return True
        if is_wip:
            if not allow_wip:
                return False
            if is_psm or is_owner:
                return True
        else:
            if is_psm:
                return True
            if is_admin and admins_can_release:
                return True
            if is_owner and current_user.hosting_granted(repopath, version):
                # Note: both per-repo decisions, and the DEFAULT_HOSTING_STANCE
                # config var are accounted for in the call to `hosting_granted()`.
                return True
        return False

    return False

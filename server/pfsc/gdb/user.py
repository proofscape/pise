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

from datetime import datetime

from flask_login import UserMixin, current_user

from config import HostingStance
from pfsc import check_config
from pfsc.constants import UserProps
import pfsc.constants
from pfsc.permissions import check_is_psm
from pfsc.excep import PfscExcep, PECode


def should_load_user_notes_from_gdb():
    """
    Useful in many contexts in which we want to check whether we are supposed
    to load user notes from the GDB.
    """
    return (
        check_config("OFFER_SERVER_SIDE_NOTE_RECORDING") and
        # To allow testing outside of a request context, we first check whether
        # current_user is defined at all:
        current_user and
        current_user.is_authenticated and
        current_user.wants_server_side_note_recording()
    )


def make_new_user_properties_dict(usertype, email, orgs_owned_by_user):
    """
    This function is the source of truth for the schema of the `properties`
    field on a `User` node in the GDB.

    This function defines the initial set of properties for a new user.
    Various other functions and methods may later update property values.

    WARNING: The default assumption is that all of these properties will be
    served to the client by the `pfsc.blueprints.ise.who_am_i()` endpoint, i.e.
    they will be visible to any logged-in user who cares to go poking around
    in their browser's console. We assume that in many cases this info can be
    useful for the pfsc-ise client software, e.g. to prevent its having to
    make an additional request.

    If we decide that anything recorded here is info that the server operator
    may not want to share with the user, we'll have to implement code to do
    some filtering. Currently we are not doing any such filtering.

    @param usertype: a value of `UserProps.V_USERTYPE`, telling us whether this
        is a true user, or an organization.
    @param email: the user's email address. For a true user, should be a string,
        giving the user's primary, verified email address (as provided by the
        OAuth log-in). For an org, just pass `None`.
    @param orgs_owned_by_user: names of orgs owned by the user (list of strings).
    @return: dictionary whose JSON string should be recorded as the
        `properties` field for the `User` node of a new user.
    """
    initial_notes_storage = (
        UserProps.V_NOTES_STORAGE.BROWSER_AND_SERVER if check_is_psm()
        else UserProps.V_NOTES_STORAGE.BROWSER_ONLY
    )

    props = {
        UserProps.K_CREATION_TIME: str(datetime.now()),
        UserProps.K_USERTYPE: usertype,
        UserProps.K_EMAIL: email,
        UserProps.K_OWNED_ORGS: orgs_owned_by_user,
        UserProps.K_NOTES_STORAGE: initial_notes_storage,
        UserProps.K_HOSTING: {},
    }

    return props


class HostingStatus:
    """
    These are the possible return values for the `User.hosting_status()`
    method.
    """
    # By definition, a repo cannot be "hosted @WIP". It is a contradiction
    # in terms. For such a request, the status is "not applicable".
    NA = "NA"

    # In case the user does not own the repo:
    DOES_NOT_OWN = "DOES_NOT_OWN"

    # Corresponds to a server configured with HostingStance.UNAVAILABLE, but
    # also considers any pre-existing decision:
    MAY_NOT_REQUEST = "MAY_NOT_REQUEST"

    # Corresponds to a server configured with HostingStance.BY_REQUEST, but
    # also considers any pre-existing decision:
    MAY_REQUEST = "MAY_REQUEST"

    # Reflects that the user has made a request, but admins have not made
    # a decision yet:
    PENDING = "PENDING"

    # Reflects a default stance (FREE hosting) or an admin decision to
    # allow hosting:
    GRANTED = "GRANTED"

    # Reflects an admin decision not to allow hosting:
    DENIED = "DENIED"


class User(UserMixin):
    """A user of the site. """

    def __init__(self, username, props):
        self.username = username
        self.props = props

    @property
    def id(self):
        return self.username

    @property
    def userpath(self):
        return self.username

    @property
    def email_addr(self):
        return self.prop(UserProps.K_EMAIL)

    @property
    def owned_orgs(self):
        return self.prop(UserProps.K_OWNED_ORGS)

    def __eq__(self, other):
        return other.username == self.username

    def __repr__(self):
        return f'<User {self.username}>'

    def prop(self, *args):
        if len(args) == 1:
            return self.props[args[0]]
        elif len(args) == 2:
            k, v = args
            self.props[k] = v

    def commit_properties(self):
        from pfsc.gdb import get_graph_writer
        gw = get_graph_writer()
        gw.update_user(self)

    def is_admin(self):
        return self.username in check_config("ADMIN_USERS")

    def is_the_default_user(self):
        return self.username == pfsc.constants.DEFAULT_USER_NAME

    def update_email(self, email_addr):
        self.prop(UserProps.K_EMAIL, email_addr)
        self.commit_properties()

    def update_owned_orgs(self, orgs_owned_by_user):
        self.prop(UserProps.K_OWNED_ORGS, orgs_owned_by_user)
        self.commit_properties()

    def owns_orgpath(self, libpath):
        """
        Determine whether a given libpath is that of an org this user owns.
        """
        p = libpath.split('.')
        if len(p) != 2:
            return False
        host, _ = self.username.split('.')
        if p[0] != host:
            return False
        return p[1] in self.owned_orgs

    def makeTrustSetting(self, libpath, version, trusted):
        """
        Make a trust setting, for a repo at a version.

        @param libpath: any libpath at or under the repopath.
        @param version: full version string.
        @param trusted: `True` if repo@version should be marked as trusted;
            `False` if not.
        """
        ...  # TODO
        self.commit_properties()

    def trusts(self, libpath, version):
        """
        Check whether the user has marked a repo@version as trusted.

        @param libpath: any libpath at or under the repopath.
        @param version: full version string.

        @return: `True` if user has trusted this repo at this version;
            `None` if user has not made such a setting.
            Note: We return `None` instead of `False`, since the user
            does not explicitly say "do not trust;" the user simply
            has not said "trust."
        """
        ...  # TODO
        return False

    def split_owned_repopath(self, repopath):
        """
        Determine whether this user owns (personally, or through an owned org)
        this repo, and if so, split the repopath into ownerpath, reponame.

        @param repopath: the libpath of a repo
        @return: pair (ownerpath, reponame) if the user owns the repo,
            otherwise pair (None, None). In particular, (None, None) is
            returned if the given path is not a repopath at all (i.e. fails to
            have exactly three segments).
        """
        fail = (None, None)
        host, user = self.username.split('.')
        r = repopath.split('.')
        if len(r) != 3:
            return fail
        if r[0] != host:
            return fail
        owner, name = r[1:]
        if owner == user or owner in self.owned_orgs:
            return f'{host}.{owner}', name
        return fail

    def owns_repo(self, repopath, directly=None):
        """
        Say whether the user owns a repo or not.

        This can mean that the repo belongs to the user directly, or to an org
        that the user owns, or both.

        @param repopath: the libpath of the repo
        @param directly: say whether the ownership should be direct (i.e. not
            through an owned org).
                None: we don't care
                True: ownership must be direct
                False: ownership must be indirect
        @return: boolean
        """
        ownerpath, _ = self.split_owned_repopath(repopath)
        if ownerpath is None:
            return False
        if directly is None:
            return True
        elif directly is True:
            return ownerpath == self.userpath
        else:
            return ownerpath != self.userpath

    def wants_server_side_note_recording(self):
        return self.props.get(UserProps.K_NOTES_STORAGE) in \
               UserProps.V_NOTES_STORAGE.INCLUDES_SERVER

    def get_hosting_settings(self):
        return self.prop(UserProps.K_HOSTING)

    def hosting_status(self, repopath, version):
        """
        Determine the current status for hosting a particular repo, at a
        particular version, for this user.

        @param repopath: the libpath of the repo
        @param version: the full version (string)
        @return: pair (HostingStatus, hash), where the hash is either None,
            or a string giving a Git commit hash that has been approved.
        """
        hash = None

        # By definition, you can't "host @WIP". To say a PISE server is hosting
        # a repo at a given version is to say that that version has been built,
        # once and for all, and is publicly available. Hosting is like what
        # PyPI does with Python packages. Each package has a version number,
        # and doesn't change, once built.
        if version == pfsc.constants.WIP_TAG:
            return HostingStatus.NA, hash

        ownerpath, repo_name = self.split_owned_repopath(repopath)
        if repo_name is None:
            return HostingStatus.DOES_NOT_OWN, hash

        if ownerpath == self.userpath:
            owner = self
        else:
            from pfsc.gdb import get_graph_reader
            owner = get_graph_reader().load_owner(ownerpath)

        owner_hosting_settings = owner.prop(UserProps.K_HOSTING)
        repo_hosting_settings = owner_hosting_settings.get(repo_name, {})

        version_setting = repo_hosting_settings.get(version)
        if version_setting is not None:
            p = version_setting.split(":")
            status = {
                UserProps.V_HOSTING.DENIED:  HostingStatus.DENIED,
                UserProps.V_HOSTING.PENDING: HostingStatus.PENDING,
                UserProps.V_HOSTING.GRANTED: HostingStatus.GRANTED,
            }[p[0]]
            if len(p) == 2:
                hash = p[1]
        else:
            # No particular setting was made, so we take the most specific
            # default we can find.
            default = (
                repo_hosting_settings.get(UserProps.K_DEFAULT) or
                owner_hosting_settings.get(UserProps.K_DEFAULT) or
                check_config("DEFAULT_HOSTING_STANCE")
            )
            status = {
                UserProps.V_HOSTING.DENIED:  HostingStatus.MAY_NOT_REQUEST,
                UserProps.V_HOSTING.PENDING: HostingStatus.MAY_REQUEST,
                UserProps.V_HOSTING.GRANTED: HostingStatus.GRANTED,
                HostingStance.UNAVAILABLE:   HostingStatus.MAY_NOT_REQUEST,
                HostingStance.BY_REQUEST:    HostingStatus.MAY_REQUEST,
                HostingStance.FREE:          HostingStatus.GRANTED
            }[default]
        return status, hash

    def hosting_granted(self, repopath, version):
        return self.hosting_status(repopath, version)[0] == HostingStatus.GRANTED

    def set_hosting(self, status, libpath, version=None, hash=None):
        """
        Set the hosting status for this User itself, or a repo owned _directly_
        by this user (not indirectly through an owned org).

        See pfsc.blueprints.cli.set_hosting(). This function carries out the
        actual making of the desired settings.

        Note: We don't do much checking here for valid arguments. Most of that
        is done in pfsc.blueprints.cli.set_hosting(). For programmatic calls,
        we expect validation to happen elsewhere.

        We do raise an exception if the status is GRANTED while the version is
        given but hash is not, or if this user does not own the hosting target
        directly.

        @param status: a value of UserProps.V_HOSTING, or else None,
            where None means to delete any existing notation
        @param libpath: string, pointing either to this user, or to a repo this
            user owns _directly_ (not through an owned org).
        @param version: full version string or None
        @param hash: string or None
        @raise: PfscExcep if:
            * this User does not own the target directly, or
            * status is GRANTED, version is given, but hash is not given
        @return: boolean saying whether anything was actually changed
        """
        changed = False
        user_hosting_settings = self.prop(UserProps.K_HOSTING)
        if libpath == self.userpath:
            # Making a default setting for the user.
            current = user_hosting_settings.get(UserProps.K_DEFAULT)
            if status != current:
                user_hosting_settings[UserProps.K_DEFAULT] = status
                changed = True
        else:
            # Making a per-repo setting.
            ownerpath, repo_name = self.split_owned_repopath(libpath)
            if ownerpath is None:
                # User does not own repo at all (directly or indirectly).
                msg = f'User {self.userpath} does not own {libpath}.'
                raise PfscExcep(msg, PECode.USER_LACKS_OWNERSHIP)
            elif ownerpath != self.userpath:
                # User owns repo, but not directly.
                msg = (
                    f'User {self.userpath} does not own {libpath} directly.'
                    ' Settings for any repo must be made through the user'
                    ' (true or org) that owns the repo directly.'
                )
                raise PfscExcep(msg, PECode.USER_LACKS_DIRECT_OWNERSHIP)

            repo_hosting_settings = user_hosting_settings.get(repo_name, {})
            if version is None:
                # Making a default setting for the repo.
                current = repo_hosting_settings.get(UserProps.K_DEFAULT)
                if status != current:
                    repo_hosting_settings[UserProps.K_DEFAULT] = status
                    changed = True
            else:
                # Making a setting for a particular version.
                if status == UserProps.V_HOSTING.GRANTED:
                    if hash is None:
                        msg = 'Must set a hash when granting hosting for a particular version.'
                        raise PfscExcep(msg, PECode.BAD_HASH)
                    status = f'{status}:{hash}'
                current = repo_hosting_settings.get(version)
                if status != current:
                    repo_hosting_settings[version] = status
                    changed = True

            if changed:
                user_hosting_settings[repo_name] = repo_hosting_settings

        if changed:
            self.prop(UserProps.K_HOSTING, user_hosting_settings)
        return changed


class UserNotes:
    """A user's notes on a given goal. """

    def __init__(self, goalpath, goal_major, state, notes):
        self.goalpath = goalpath
        self.goal_major = (
            goal_major if goal_major == pfsc.constants.WIP_TAG
            else int(goal_major)
        )
        self.state = state
        self.notes = notes

    def __eq__(self, other):
        return all(
            getattr(self, name) == getattr(other, name)
            for name in ['goalpath', 'goal_major', 'state', 'notes']
        )

    def __str__(self):
        return f'{self.write_origin()}:{self.state}\n{self.notes}'

    def __hash__(self):
        return hash(str(self))

    def write_origin(self):
        return f'{self.goalpath}@{self.goal_major}'

    def write_dict(self):
        return {
            'state': self.state,
            'notes': self.notes,
        }

    def write_old_style_dict(self):
        return {
            'checked': self.state == 'checked',
            'notes': self.notes,
        }

    def is_blank(self):
        return self.state == 'unchecked' and len(self.notes) == 0

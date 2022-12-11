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

import json

from flask import url_for, render_template
from flask_login import current_user, logout_user

from pfsc import check_config
from pfsc.checkinput import IType
import pfsc.constants
from pfsc.constants import UserProps
from pfsc.email import (
    send_hosting_request_recd_mail_to_user,
    send_hosting_request_mail_to_reviewers,
)
from pfsc.excep import PfscExcep, PECode
from pfsc.gdb import get_graph_writer, get_graph_reader
from pfsc.gdb.user import UserNotes, HostingStatus
from pfsc.handlers import Handler
from pfsc.methods import proxy_or_render
from pfsc.session import get_csrf_from_session
from pfsc.util import dict_to_url_args


class UserInfoLoader(Handler):
    """
    Load basic info about the current user.
    """

    def check_permissions(self):
        pass

    def go_ahead(self):
        anon = current_user.is_anonymous
        self.set_response_field('username', None if anon else current_user.username)
        self.set_response_field('props', None if anon else current_user.props)


class UserHandler(Handler):
    """
    Superclass for any handler where the user must be logged in for the
    operation to make sense.
    """

    def check_enabled(self):
        if current_user.is_anonymous:
            raise PfscExcep('User not logged in.', PECode.USER_NOT_LOGGED_IN)

    def check_permissions(self):
        if not current_user.is_authenticated:
            super().check_permissions()


class UserNotesHandler(UserHandler):
    """
    Superclass for any handler where (a) the user must be logged in,
    and (b) server-side note recording must be an available service,
    though not necessarily activated yet for this user.
    """

    def check_enabled(self):
        if not check_config("OFFER_SERVER_SIDE_NOTE_RECORDING"):
            raise PfscExcep('Server-side note recording not enabled.',
                            PECode.SSNR_SERVICE_DISABLED)
        super().check_enabled()


class UserActiveNotesHandler(UserNotesHandler):
    """
    Superclass for any handler where (a) the user must be logged in,
    and (b) the user must have already activated server-side note recording.
    """

    def check_enabled(self):
        super().check_enabled()
        if not current_user.wants_server_side_note_recording():
            raise PfscExcep('Server-side note recording not enabled for user.',
                            PECode.ACTION_PROHIBITED_BY_USER_SETTINGS)


USER_SETTINGS_INPUT_TYPES = {}
def build_user_settings_input_types_dict():
    for k in UserProps.FREELY_SETTABLE_BY_USER:
        value_class = getattr(UserProps, f'V_{k}')
        values = value_class.ALL_
        USER_SETTINGS_INPUT_TYPES[k] = {
            'type': IType.STR,
            'values': values,
        }
# Define once upon module load:
build_user_settings_input_types_dict()


class UserSettingsUpdater(UserHandler):
    """
    Update a user's settings.
    """

    def check_input(self):
        self.check({
            "OPT": USER_SETTINGS_INPUT_TYPES,
        }, reify_undefined=False)
        self.reject_prohibited_changes()

    def reject_prohibited_changes(self):
        # The "default user" is the user's identity when the app is configured
        # in personal server mode. In this mode, you can't change the way notes
        # are recorded.
        if current_user.is_the_default_user():
            if UserProps.K_NOTES_STORAGE in self.fields:
                del self.fields[UserProps.K_NOTES_STORAGE]

    def go_ahead(self):
        if self.fields:
            for k, v in self.fields.items():
                current_user.prop(k, v)
            get_graph_writer().update_user(current_user)


class UserInfoExporter(UserHandler):
    """
    Handle requests from the user to export all their data, in machine-readable
    format.

    Depending on the 'mode' argument we receive, we either serve the HTML for
    a page prompting the user to click and begin the download, or we serve the
    download itself.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'target': {
                    'type': IType.STR,
                    'values': [
                        'all', 'notes',
                    ],
                }
            },
            "OPT": {
                'mode': {
                    'type': IType.STR,
                    'values': [
                        'page', 'download',
                    ],
                    'default_cooked': 'page',
                }
            }
        })

    def build_page(self, target):
        base_url = url_for('ise.export_user_info')
        token = get_csrf_from_session(supply_if_absent=False)
        params = {'target': target, 'mode': 'download', 'CSRF': token}
        download_url = f'{base_url}?{dict_to_url_args(params)}'
        thing_to_export = {
            'all': 'all your user account information',
            'notes': 'all of your server-side study notes',
        }[target]
        html = render_template(
            "user_exports_page.html",
            title="PISE Data Export",
            thing_to_export=thing_to_export,
            download_url=download_url,
            css=[
                url_for('vstat.static', filename='css/centered_justified.css'),
            ],
        )
        self.set_response_field('html', html)

    def do_download(self, target):
        uns = get_graph_reader().load_user_notes(current_user.username, None)
        study_notes = {un.write_origin(): un.write_old_style_dict() for un in uns}

        if target == 'all':
            info = {
                'username': current_user.username,
                'properties': current_user.props,
                'study_notes': study_notes,
            }
        else:
            info = study_notes

        info_json = json.dumps(info)
        info_json_bytes = info_json.encode()
        self.set_response_field('download', info_json_bytes)

    def go_ahead(self, target, mode):
        if mode == 'download':
            self.do_download(target)
        else:
            self.build_page(target)


class UserAcctPurgeHandler(UserHandler):
    """
    Handle a request from the user to purge their entire account.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'confirmation': {
                    'type': IType.STR,
                    # We accept the second string here, for testing purposes.
                    'values': ['DeleteMyAccount', 'DELETEMYACCOUNT'],
                }
            }
        })

    def go_ahead(self, confirmation):
        username = current_user.username
        gw = get_graph_writer()
        n = gw.delete_user(
            username,
            definitely_want_to_delete_this_user=(confirmation=='DeleteMyAccount')
        )
        self.set_response_field('username', username)
        self.set_response_field('user_nodes_deleted', n)
        if n > 0:
            logout_user()


class SsnrRequestHandler(UserNotesHandler):
    """
    Handle requests to activate/deactivate server-side note recording.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'activate': {
                    'type': IType.BOOLEAN,
                    'accept_int': True,
                },
                'confirm': {
                    'type': IType.BOOLEAN,
                    'accept_int': True,
                },
            }
        })

    def go_ahead(self, activate, confirm):
        if confirm:
            val = {
                True: UserProps.V_NOTES_STORAGE.BROWSER_AND_SERVER,
                False: UserProps.V_NOTES_STORAGE.BROWSER_ONLY
            }[activate]
            current_user.prop(UserProps.K_NOTES_STORAGE, val)
            get_graph_writer().update_user(current_user)
            self.set_response_field('new_setting', val)
        else:
            conf_var = {
                True: "SSNR_ACTIVATION_DIALOG_PROXY_URL",
                False: "SSNR_DEACTIVATION_DIALOG_PROXY_URL"
            }[activate]
            fn = {
                True: "ssnr_on_conf.html",
                False: "ssnr_off_conf.html"
            }[activate]
            html = proxy_or_render(
                conf_var, fn,
                branding_img_url=check_config("LOGIN_PAGE_BRANDING_IMG_URL"),
                tos_url=check_config("TOS_URL"),
                prpo_url=check_config("PRPO_URL"),
            )
            self.set_response_field('conf_dialog_html', html)


class NotesRecorder(UserActiveNotesHandler):
    """
    Record the user's notes on a goal.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'goal_id': {
                    'type': IType.GOAL_ID,
                    'allow_WIP': not check_config("REFUSE_SSNR_AT_WIP"),
                },
                'state': {
                    'type': IType.STR,
                    'values': [
                        'checked', 'unchecked',
                    ],
                },
                'notes':  {
                    'type':  IType.STR,
                    'max_len': pfsc.constants.MAX_NOTES_MARKDOWN_LENGTH,
                },
            },
        })

    def go_ahead(self, goal_id, state, notes):
        goalpath = goal_id.libpath
        goal_major = goal_id.version.major
        user_notes = UserNotes(goalpath, goal_major, state, notes)
        username = current_user.username
        gw = get_graph_writer()
        gw.record_user_notes(username, user_notes)
        # Check:
        uns = gw.reader.load_user_notes(username, [(goalpath, goal_major)])
        blank = user_notes.is_blank()
        success = (
            (blank and len(uns) == 0)
            or
            (not blank and len(uns) == 1 and uns[0] == user_notes)
        )
        self.set_response_field('notes_successfully_recorded', success)


class NotesLoader(UserNotesHandler):
    """
    Direct loading of user notes by goalId.

    Cf DashgraphLoader, AnnotationLoader, StudyPageBuilder, which also load
    user notes, but for more specialized purposes.

    Input Fields:
        REQ:
            goal_ids: comma-delimited list of goalIds to be looked up.
                May be empty string.
        OPT:
            load_all: boolean. If true, while goal_ids is empty, then we
                load *all* of this user's notes.

    Response Fields:
        goal_info: dict in which goalIds point to user's notes,
            in the form {
                checked: bool,
                notes: str
            }

    Note: While goal_ids being empty could have been taken, alone, as the
    signal to load all notes, we wanted to prevent unintentional cases, and
    so we require the `load_all` boolean. Consider client-side code that
    computes a list of goal_ids to be checked, but fails to check whether it's
    empty before making the request.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'goal_ids': {
                    'type': IType.CDLIST,
                    'itemtype': {
                        'type': IType.GOAL_ID,
                    },
                    'max_num_items': 1024,
                }
            },
            "OPT": {
                'load_all': {
                    'type': IType.BOOLEAN,
                    'default_cooked': False,
                },
            },
        })

    def go_ahead(self, goal_ids, load_all):
        if load_all and not goal_ids:
            goal_infos = None
        else:
            goal_infos = [(gid.libpath, gid.version.major) for gid in goal_ids]

        uns = get_graph_reader().load_user_notes(current_user.username, goal_infos)
        goal_info = {un.write_origin(): un.write_old_style_dict() for un in uns}

        self.set_response_field('goal_info', goal_info)


class NotesPurgeHandler(UserActiveNotesHandler):
    """
    Handle a request to purge all recorded notes, for a given user.

    As an added safety, we make this a `UserActiveNotesHandler`, meaning
    SSNR has to be currently activated.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'confirmation': {
                    'type': IType.STR,
                    # We accept the second string here, for testing purposes.
                    'values': ['DeleteAllMyNotes', 'DELETEALLMYNOTES'],
                }
            }
        })

    def go_ahead(self, confirmation):
        username = current_user.username
        gw = get_graph_writer()
        gw.delete_all_notes_of_one_user(
            username,
            definitely_want_to_delete_all_notes=(confirmation=='DeleteAllMyNotes')
        )
        # Check:
        all_notes = get_graph_reader().load_user_notes(username, None)
        num_remaining_notes = len(all_notes)
        self.set_response_field('num_remaining_notes', num_remaining_notes)


class HostingRequestHandler(UserHandler):
    """
    Handle requests to host repos (at particular versions) on this server.
    """

    no_comment_placeholder = '[no comment]'

    def check_input(self):
        self.check({
            "REQ": {
                'repopath': {
                    'type': IType.LIBPATH,
                    'repo_format': True
                },
                'vers': {
                    'type': IType.FULL_VERS,
                }
            },
            "OPT": {
                'comment': {
                    'type': IType.STR,
                    'max_len': 512,
                    'default_cooked': self.no_comment_placeholder,
                },
            },
        })

    def go_ahead(self, repopath, vers, comment):
        repopath = repopath.value
        version = vers.full
        comment = comment or self.no_comment_placeholder
        status, _ = current_user.hosting_status(repopath, version)
        if status == HostingStatus.MAY_REQUEST:
            self.make_request(repopath, version, comment)
        else:
            # In all other cases, the request is rejected.
            msg = f'Sorry, cannot request hosting for {repopath} at {version}.'
            code = PECode.HOSTING_REQUEST_REJECTED
            # In some of these cases we can provide a more helpful message.
            if status == HostingStatus.DOES_NOT_OWN:
                msg = (
                    f"You don't appear to be an owner of {repopath}."
                    f" Only owners can request hosting for a repo."
                )
            elif status == HostingStatus.PENDING:
                msg = (
                    "It looks like hosting has already been requested"
                    f" for {repopath} at {version}."
                    " We'll try to get back to you as soon as possible!"
                )
                code = PECode.HOSTING_REQUEST_UNNECESSARY
            elif status == HostingStatus.GRANTED:
                msg = (
                    "It looks like hosting has already been granted"
                    f" for {repopath} at {version}!"
                    " Did you try building yet?"
                )
                code = PECode.HOSTING_REQUEST_UNNECESSARY
            raise PfscExcep(msg, code)

    def make_request(self, repopath, version, comment):
        owner = get_graph_reader().load_owner(repopath)
        owner.set_hosting(
            UserProps.V_HOSTING.PENDING,
            repopath,
            version=version
        )
        owner.commit_properties()

        userpath = current_user.userpath
        user_email_addr = current_user.email_addr

        rev_msg = send_hosting_request_mail_to_reviewers(
            user_email_addr,
            userpath, repopath, version, comment
        )
        usr_msg = send_hosting_request_recd_mail_to_user(
            user_email_addr,
            userpath, repopath, version, comment
        )

        if check_config("TESTING"):
            self.set_response_field('rev_msg_len', len(str(rev_msg)))
            self.set_response_field('usr_msg_len', len(str(usr_msg)))

        status, _ = owner.hosting_status(repopath, version)
        self.set_response_field('new_hosting_status', status)

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

from contextlib import nullcontext
import json
from json.decoder import JSONDecodeError
import inspect
from uuid import uuid4

from rq import get_current_job
from flask import redirect, flash, has_request_context, session
from flask_socketio import SocketIO
from pottery import Redlock

import pfsc.constants
from pfsc.constants import (
    WEBSOCKET_NAMESPACE,
    REDIS_CHANNEL,
    ISE_EVENT_NAME,
    WIP_TAG,
    MAIN_TASK_QUEUE_NAME,
)
from pfsc import check_config, get_app
from pfsc.excep import *
import pfsc.checkinput as checkinput
from pfsc.checkinput.libpath import CheckedLibpath
from pfsc.checkinput.version import CheckedVersion
from pfsc.permissions import have_repo_permission, ActionType
from pfsc.build.repo import get_repo_part
from pfsc.rq import get_rqueue, get_redis_connection
from pfsc.session import get_csrf_from_session


# By setting the right message queue and channel, we can emit events from
# a process outside the web server.
# See https://flask-socketio.readthedocs.io/en/latest/deployment.html#emitting-from-an-external-process
redis_uri = check_config("REDIS_URI")
async_mode = check_config("SOCKETIO_ASYNC_MODE")
socketio_path = check_config("SOCKETIO_PATH")

socketio = SocketIO(
    path=socketio_path,
    async_mode=async_mode,
    message_queue=redis_uri,
    channel=REDIS_CHANNEL,
    #logger=True,
    #engineio_logger=True
)


def emit_ise_event(room, event_type, recipSID, event_message, namespace=WEBSOCKET_NAMESPACE):
    """
    Emit an ISE event. This function helps us stick to a standard format.

    :param room: the socket room to which the event will be emitted. Usually this
      will be the CSRF room to which all and only a single user's sockets belong.
    :param event_type: the type of event, for interpretation by the client.
    :param recipSID: a socket ID that may have been nominated as the intended recipient
      of the message. This helps the client decide which windows should pay attention,
      and which should simply drop the message.
    :param event_message: the message that is to be communicated.
    :param namespace: as usual, the websocket namespace to be used for sending.
    :return: nothing
    """
    wrapper = {
        'type': event_type,
        'recipSID': recipSID,
        'msg': event_message,
    }
    socketio.emit(ISE_EVENT_NAME, wrapper, room=room, namespace=namespace)


class Handler:
    """
    An abstract class for handling requests.

    You override:

        * the check_input method to check the input and stash the values
            globally;

        * the go_ahead method to do the processing that should happen iff all
            the input was good;

    In your check_input method, you should use self.check() as a convenience,
    since you only need to pass it a types dictionary. Input is read from the
    passed request_info, and checked values are stashed in self.fields.

    Your subclass should accept some kind of request info from the app routes, and
    should pass this on to the __init__ method of this abstract class.

    The 'process' method should then be called.

    If any PfscExceps are raised during processing, they will be stored under
    `self.anticipated_pfsc_excep`, and `success` will be `False`.

    As a convenience, you can override the public error message of any PfscExcep using the
    self.pub_err_msg_overrides dictionary, where keys are PECodes and values are
    error messages to replace the default ones belonging to PfscExceps of that PECode.
    """

    DEFAULT_ERR_CODE = "<DEFAULT>"

    def __init__(self, request_info, csrf_from_session=None):
        # SHOULD NOT OVERRIDE:
        self.request_info = request_info
        self.csrf_from_session = csrf_from_session
        self.fields = {}
        self.anticipated_pfsc_excep = None
        self.raise_anticipated = False
        self.err_lvl = 0
        self.err_msg = ''
        self.err_info = None
        self.is_prepared = False
        self.success = False
        self.reserved_response_fields = ['err_lvl', 'err_msg', 'err_info', 'orig_req']
        # MAY OVERRIDE:
        self.post_preparation_hooks = []
        self.success_response = {}
        self.pub_err_msg_overrides = {}
        self.flash_err_msg = False
        self.redir_by_err_code = {}
        self.do_require_csrf = check_config("REQUIRE_CSRF_TOKEN")

    # ---------------------------------------------------------------
    # SHOULD NOT OVERRIDE

    def set_response_field(self, k, v):
        """
        Subclasses should use this method to set key-value pairs in the success response.
        """
        assert k not in self.reserved_response_fields
        self.success_response[k] = v

    def get_response_field(self, k):
        """
        May be useful e.g. when one Handler type makes use of another.
        """
        return self.success_response[k]

    def adopt_response(self, other):
        """
        This is useful if you are passing the job to an instance of another Handler class.
        After running its `process` method (be sure to set `raise_anticipated=True`), pass
        it here, so that we can return its response.

        :param other: instance of another Handler class
        """
        self.success_response = other.success_response

    def set_anticipated_pfsc_excep(self, pfsc_excep):
        """
        Used internally to record any PfscExcep that was raised during the process.
        """
        if self.raise_anticipated:
            raise pfsc_excep
        self.anticipated_pfsc_excep = pfsc_excep

    def get_request_info(self):
        return self.request_info

    def generate_error_message(self):
        """
        Generate the error message in case of failure.
        Clients should call `generate_response` instead.
        """
        pe = self.anticipated_pfsc_excep
        if pe is None:
            pe = PfscExcep('', PECode.UNKNOWN)
        self.err_lvl = pe.code()
        self.err_info = pe.extra_data()
        if self.err_lvl in self.pub_err_msg_overrides:
            self.err_msg = self.pub_err_msg_overrides[self.err_lvl]
        else:
            self.err_msg = pe.public_msg()
        if self.flash_err_msg:
            flash(self.err_msg, category='error')

    def generate_response(self):
        """
        Automatically generate a response message, based on success or failure.

        In case of success, uses self.success_response, adding `err_lvl` field equal to 0.

        In case of error, generates standard error response with `err_lvl` and `err_msg`.

        In all cases, there is an `orig_req` field, equal to the original request object.

        :return: The response object.
        """
        # Get base response.
        if self.success:
            self.err_lvl = 0
            response = self.success_response
        else:
            self.generate_error_message()
            response = {
                'err_msg': self.err_msg,
                'err_info': self.err_info
            }
        # Redirect?
        if 'redirect' not in response:
            redir = self.redir_by_err_code.get(self.err_lvl)
            if redir is None and self.err_lvl > 0:
                redir = self.redir_by_err_code.get(Handler.DEFAULT_ERR_CODE)
            if redir is not None:
                response['redirect'] = redir
        # Add original request.
        response['orig_req'] = self.request_info
        # Set error level.
        response['err_lvl'] = self.err_lvl
        return response

    def generate_html_response(self):
        """
        Start with the dictionary generated by our `generate_response` method.
        We expect this dictionary to have an `html` field.
        If that field is absent, or if the dictionary reports a positive `err_lvl`, then
        we simply return an error message string.
        Otherwise we return the value of the `html` field.
        """
        d = self.generate_response()
        if d['err_lvl'] > 0 or 'html' not in d:
            r = d.get('err_msg', 'Could not generate HTML.')
        else:
            r = d['html']
        return r

    def generate_redirect_or_html(self):
        """
        If our standard response has a `redirect` field, return a redirect
        to the value of this field.
        Otherwise, return an HTML response.
        """
        d = self.generate_response()
        url = d.get('redirect')
        if url is not None:
            return redirect(url)
        return self.generate_html_response()

    @staticmethod
    def check_repo_permission(action_type, libpath, version, action='do that with', msg=None):
        """
        Check whether, in the current request context, we have "repo permissions"
        for a given repo.

        :param action_type: a value of the ActionType enum, indicating what
            type of action you are trying to take.
        :param libpath: string or CheckedLibpath, representing any libpath
          equal to either the repopath in question itself, or any proper
          extension thereof.
        :param version: string, CheckedVersion, None, or int.
            If int n (representing a major version), we convert to the
            string '{n}.0.0'. If None, forwarded as is.
        :param action: optional string describing the action the request is
          attempting to do. Should fit in, "You can't ______ that repo."
        :param msg: optional error message to completely override the one we
          otherwise would generate, using the `action` phrase.
        :return: nothing.
        :raises: PfscExcep if we lack the requisite permission.
        """
        if isinstance(libpath, CheckedLibpath):
            libpath = libpath.value

        if isinstance(version, CheckedVersion):
            version = version.full
        elif isinstance(version, int):
            version = f'{version}.0.0'

        repopath = get_repo_part(libpath)

        if not have_repo_permission(action_type, repopath, version):
            if msg is None:
                msg = f'You do not have permission to {action} repo `{repopath}`.'
            raise PfscExcep(msg, PECode.INADEQUATE_PERMISSIONS)

    @staticmethod
    def check_repo_read_permission(libpath, version, *, action='do that with', msg=None):
        """
        Convenience method, to call `check_repo_permission()` with ActionType.READ.
        """
        Handler.check_repo_permission(ActionType.READ, libpath, version, action, msg)

    @staticmethod
    def check_repo_write_permission(libpath, *, action='do that with', msg=None):
        """
        Convenience method, to call `check_repo_permission()` with ActionType.WRITE.

        There is no version arg, because you can only write @WIP.
        """
        Handler.check_repo_permission(ActionType.WRITE, libpath, WIP_TAG, action, msg)

    @staticmethod
    def check_repo_build_permission(libpath, version, *, action='do that with', msg=None):
        """
        Convenience method, to call `check_repo_permission()` with ActionType.BUILD.
        """
        Handler.check_repo_permission(ActionType.BUILD, libpath, version, action, msg)

    @staticmethod
    def check_wip_mode(version, subject='That', verb='done', first_para=None, advice=None):
        """
        If attempting to do something with WIP, raise an exception if the current
        app is configured with ALLOW_WIP False.

        :param version: version string or CheckedVersion we're trying to work with.
        :param subject: optional plug-in for canned message (see code below).
        :param verb: optional plug-in for canned message (see code below).
        :param first_para: optional override for first paragraph of message. This replaces
          completely the part that would have used the subject and verb kwargs.
        :param advice: optional override for second paragraph of message (see code below).
          Here you may provide an alternative string to be used as second para, or you
          may pass `False` to indicate that you don't want any second para at all, or you
          may leave at `None` to accept the canned message.
        :return: nothing.
        :raises: PfscExcep if appropriate.
        """
        if isinstance(version, CheckedVersion):
            version = version.full
        assert isinstance(version, str)
        if version == WIP_TAG and not check_config("ALLOW_WIP"):
            if first_para:
                msg = first_para
            else:
                msg = f'{subject} cannot be {verb} at work-in-progress on this server.'
                msg += ' You must supply a version number.'
            if advice:
                msg += advice
            elif advice is not False:
                msg += '\n\nIf you want to develop Proofscape modules you can run the ISE'
                msg += ' locally on your own computer.'
            raise PfscExcep(msg, PECode.NO_WIP_MODE)

    def check_csrf(self):
        token_from_args = self.request_info.get("CSRF")
        if not token_from_args:
            raise PfscExcep('CSRF token not supplied with request', PECode.BAD_OR_MISSING_CSRF_TOKEN)
        token_from_session = self.csrf_from_session or get_csrf_from_session(supply_if_absent=False)
        if token_from_args != token_from_session:
            raise PfscExcep('Incorrect CSRF token supplied with request', PECode.BAD_OR_MISSING_CSRF_TOKEN)

    def check(self, types, raw=None, reify_undefined=True):
        """
        Convenience method for checking the given args in self.request_info and stashing the
        results in self.fields.
        :param types: the definition of the arg types to be checked. See doctext for
                      the `check_input` function.
        :param raw: optional dictionary to check instead of self.request_info.
        :param reify_undefined: forwarded to the `check_input` function.
        :return: nothing
        """
        if raw is None:
            raw = self.request_info
        checkinput.check_input(raw, self.fields, types, reify_undefined=reify_undefined)

    def force_input_field(self, key, value):
        """
        Sometimes you want to put a key-value pair into self.fields, without
        actually drawing this from the raw input args. E.g. this can be useful
        in any of our methods that are invoked under our `withfields` method.
        """
        self.fields[key] = value

    def check_jsa(self, name_of_args_dict, types, lift_in_stash=True):
        """
        The name of this method stands for "check JSON-serialized args".
        This is for cases where a single argument `a` in `self.request_info` is supposed to have as
        value the JSON-serialization of a whole dictionary `d` and we want to:
            (1) check that arg `a`
                  (i) is present,
                 (ii) successfully parses as JSON, and
                (iii) produces a dictionary `d` after parsing
            (2) proceed to check dictionary `d` for args of types specified by `types`
            (3) optionally "lift" the args so checked, stashing them in `self.fields` under
                their names within dictionary `d`.

        :param name_of_args_dict: This is `a` in the explanation above. In other words, this is
                                  the name under which the JSON-serialization of `d` should be
                                  found in `self.request_info`.
        :param types: Just like the `types` argument to the ordinary `check` method, only this time
                      it's going to be applied to the parsed dictionary `d`.
        :param lift_in_stash: Leave True if you want the args found in `d` to be stashed in
                              `self.fields` under their names in `d`; set False if instead you
                              want a "checked dictionary" to be stashed in `self.fields[name_of_args_dict]`.
                              This "checked dictionary" is a dict in which the names in `d` point to the
                              results of checking the corresponding values.
        :return: nothing
        """
        # Attempt to find and parse the dictionary.
        j = self.request_info.get(name_of_args_dict)
        if j is None:
            msg = 'Missing argument "%s"' % name_of_args_dict
            raise PfscExcep(msg, PECode.MISSING_INPUT)
        try:
            d = json.loads(j)
        except JSONDecodeError:
            msg = 'Malformed JSON: %s' % j
            raise PfscExcep(msg, PECode.MALFORMED_JSON)
        if not isinstance(d, dict):
            msg = 'Was expecting a JSON-serialized dictionary under argument "%s"' % name_of_args_dict
            raise PfscExcep(msg, PECode.INPUT_WRONG_TYPE)
        # Check within the parsed dictionary.
        if lift_in_stash:
            stash = self.fields
        else:
            stash = {}
            self.fields[name_of_args_dict] = stash
        checkinput.check_input(d, stash, types)

    def withfields(self, func, include_self=False):
        """
        Execute a function, automatically passing those of its args whose names coincide
        with the names of checked input fields.
        :param func: The function to be executed.
        :return: The return value of the function.
        """
        field_names = inspect.getfullargspec(func).args
        arg_list = []
        for name in field_names:
            if name == 'self':
                if include_self:
                    arg_list.append(self)
            else:
                if name not in self.fields:
                    msg = 'Handler calls for missing arg: ' + name
                    raise Exception(msg)
                else:
                    arg = self.fields.get(name)
                    arg_list.append(arg)
        return func(*arg_list)

    @pfsc_anticipate_all()
    def prepare(self, raise_anticipated=False):
        """
        The `prepare` and `proceed` methods together provide an alternative
        to the `process` method. When called in succession they achieve the
        exact same effect. However, by calling them one at a time, you have
        a chance to inspect the results of the preliminary checks (i.e. the
        results of `prepare`) before completing the operation (with `proceed`).

        :param raise_anticipated: see `process` method
        :return: nothing
        """
        self.raise_anticipated = raise_anticipated
        if self.anticipated_pfsc_excep is not None:
            # There was already an error, so do nothing more.
            return
        if self.do_require_csrf:
            self.check_csrf()
        self.check_enabled()
        self.check_input()
        self.withfields(self.check_permissions)
        self.withfields(self.confirm)
        for hook in self.post_preparation_hooks:
            self.withfields(hook)
        self.is_prepared = True

    @pfsc_anticipate_all()
    def proceed(self, raise_anticipated=False):
        """
        The `prepare` and `proceed` methods together provide an alternative
        to the `process` method. When called in succession they achieve the
        exact same effect. However, by calling them one at a time, you have
        a chance to inspect the results of the preliminary checks (i.e. the
        results of `prepare`) before completing the operation (with `proceed`).

        :param raise_anticipated: see `process` method
        :return: nothing
        """
        assert self.is_prepared
        self.raise_anticipated = raise_anticipated
        if self.anticipated_pfsc_excep is not None:
            # There was already an error, so do nothing more.
            return
        self.withfields(self.go_ahead)
        self.success = True

    def process(self, raise_anticipated=False):
        """
        This is the main method where the Handler does its job.

        :param raise_anticipated: Set True if you want any caught ("anticipated")
          PfscExceps to actually be re-raised, instead of simply being recorded
          and reported in the final, generated response. This is useful when one
          handler H wants to use another handler K as a part of its own process.
          In such a case, H should call K's `process` method with `raise_anticipated`
          set to True. That way, any errors occurring during K's process are actually
          visible to H.
        """
        self.prepare(raise_anticipated=raise_anticipated)
        if self.is_prepared:
            self.proceed(raise_anticipated=raise_anticipated)

    @pfsc_anticipate_all()
    def super_process(self, cls):
        """
        If one type of Handler subclasses another, it can call this method, passing the
        superclass as argument, in order to do the superclass's processing on itself.
        :param cls: the superclass
        """
        cls.check_enabled(self)
        cls.check_input(self)
        cls.withfields(self, cls.check_permissions, include_self=True)
        cls.withfields(self, cls.confirm, include_self=True)
        cls.withfields(self, cls.go_ahead, include_self=True)

    # ---------------------------------------------------------------
    # MAY OVERRIDE

    def check_enabled(self):
        """
        This is a chance to check whether we are enabled or should abort
        immediately, before even doing input checking.
        """
        pass

    def confirm(self):
        """
        This is a place to make assertions on checked input fields, or perform
        any other additional checks, if desired.

        **WF** This method is invoked using "withfields": this means you may supply
        extra argument names identical to checked input fields, and they will
        be automatically supplied.
        """
        pass

    # ---------------------------------------------------------------
    # MUST OVERRIDE

    def check_input(self):
        """
        Use the `checkinput` module (or `self.check`) to check the input,
        and stash checked values in `self.fields`.
        """
        pass

    def check_permissions(self):
        """
        In order to be secure by design, the default is to assume that the
        user does _not_ have permission to do whatever this handler is
        supposed to do.

        Subclasses therefore must override this method if they actually want
        to do anything. It could be as simple as `pass`.

        **WF** This method is invoked using "withfields": this means you may supply
        extra argument names identical to checked input fields, and they will
        be automatically supplied.
        """
        raise PfscExcep('Permission denied', PECode.INADEQUATE_PERMISSIONS)

    def go_ahead(self):
        """
        Do the processing that should happen iff all the input was good.

        **WF** This method is invoked using "withfields": this means you may supply
        extra argument names identical to checked input fields, and they will
        be automatically supplied.
        """
        pass


class SocketHandler(Handler):
    """
    Handler for SocketIO events.
    """

    def __init__(self, request_info, room,
                 recipSID=None, namespace=WEBSOCKET_NAMESPACE, csrf_from_session=None):
        """
        :param request_info: Info describing the request.
        :param room: The SocketIO "room" to which emits should be directed.
        :param recipSID: A nominated socket ID that should be noted as the intended recipient
          of messages emitted by this handler. We will actually emit messages to the given `room`,
          but they will contain the `recipSID` to help the client sort out whether or not to listen.
        :param csrf_from_session: If the handler is going to do its processing outside of a
          request context (such as when carried out as an external job), you may need to supply the
          CSRF token as read from the session at job enqueing time. You can do that here.
        :param namespace: The SocketIO namespace to which emits should be directed.
        """
        Handler.__init__(self, request_info, csrf_from_session=csrf_from_session)
        self.reserved_response_fields.extend(['job_id', 'cookie'])
        self.room = room
        self.namespace = namespace
        # Look for a cookie dictionary.
        self.cookie = request_info.get('cookie', {})
        if not isinstance(self.cookie, dict):
            raise PfscExcep('Malformed socketio cookie', PECode.MALFORMED_SOCKETIO_COOKIE)
        # Look for a recipient SID
        self.recipSID = recipSID or request_info.get('SID')
        self.success_response = {}
        # Are we running inside an RQ job?
        self.job = get_current_job()
        self.job_id = self.job.id if self.job else None

    def check_cookie(self, types, lift_in_stash=True):
        """
        Check input given in the cookie.
        :param types: as in the ordinary `check` method (see `Handler` class)
        :param lift_in_stash: as in the `check_jsa` method (see `Handler` class). If False, the
                              "checked dictionary" will be stored under `self.fields['cookie']`.
        :return: nothing
        """
        if lift_in_stash:
            stash = self.fields
        else:
            stash = {}
            self.fields['cookie'] = stash
        checkinput.check_input(self.cookie, stash, types)

    def set_cookie(self, k, v):
        """
        Set a key-value pair in the socketio cookie.
        """
        self.cookie[k] = v

    def emit(self, event, message, groupcast=False):
        """
        Convenience method for emitting a message, automatically supplying the `namespace`
        and `room` parameters.

        :param event: The name (str) of the event to be emitted.
        :param message: The message to be sent.
        :param groupcast: Set true in order to specify `None` as the recipSID, which
          will encourage _all_ windows in the client group to listen to the message.
        :return: nothing
        """
        recipSID = None if groupcast else self.recipSID
        emit_ise_event(self.room, event, recipSID, message, namespace=self.namespace)

    def emit_progress_complete(self):
        self.emit("progress", {'complete': True})

    def emit_progress_crashed(self):
        self.emit("progress", {'crashed': True})

    def generate_response(self):
        """
        Add `job_id` to basic response, if we have one.

        :return: The response object.
        """
        # Get base response.
        response = Handler.generate_response(self)
        # Set job id if we have one.
        if self.job_id:
            response['job_id'] = self.job_id
        # Set cookie.
        response['cookie'] = self.cookie
        return response

    def emit_standard_response(self):
        """
        Emits the response generated by the `generate_response` method, under either of two
        event names, `success` and `error`, as appropriate.
        :return: the response object
        """
        event = 'success' if self.success else 'error'
        message = self.generate_response()
        self.emit(event, message)


def finish_socket_handler_process_with_app(handler):
    # If we're operating in RQ synchronous mode, then we'll still have the
    # existing app context under which the handler process began. Forming
    # a new one doesn't just waste time; in early experiments with the one-
    # container app image, it blocked the original app from hearing any
    # socket emits through Redis. Only the new app heard them, and it of
    # course did not have any of the sockets on which the user was connected,
    # so no emits were being sent to the client.
    app, new = get_app()
    if new:
        # RQ workers need to be able to do whatever we ask them to do.
        # By the time a job reaches them, we are past all questions of permissions.
        app.config["PERSONAL_SERVER_MODE"] = True
    with app.app_context():
        d = getattr(handler, 'required_phony_session_dict', {})
        need_rc = d and not has_request_context()
        ctx_mgr = app.test_request_context() if need_rc else nullcontext()
        with ctx_mgr:
            for k, v in d.items():
                session[k] = v
            handler.proceed()
            handler.emit_standard_response()


class RepoTaskHandler(SocketHandler):
    """
    Handler for long-running, exclusive repo tasks.

    Certain tasks, usually involving writing, buliding, or changing a repo
    in some way, are such that we must be sure that two such tasks are never
    running simultaneously, for a given repo. It is fine however to run such
    tasks simultaneously for different repos. We refer to tasks of this kind
    as "exclusive repo tasks".
    """

    def __init__(self, request_info, room, recipSID=None, namespace=WEBSOCKET_NAMESPACE):
        SocketHandler.__init__(self, request_info, room, recipSID=recipSID, namespace=namespace)
        self.implicated_repopaths = set()
        self.post_preparation_hooks.append(self.compute_implicated_repopaths)
        self.required_phony_session_dict = {}

    def require_in_session(self, *args):
        """
        If the handler is going to do delayed processing in a worker, that
        processing will take place outside of a true Flask request context.
        However, some handlers may need session variables, despite the lack of
        a true request context. They can use this method to set session
        variables they will require, and then the delayed processing will be
        given a phony request context, in which these session vars are set.

        :param args: Pass key and value, or just key. If just key, we read the
            value from the current session.
        """
        if len(args) == 2:
            k, v = args
        elif len(args) == 1:
            k = args[0]
            v = session.get(k)
        else:
            raise ValueError('Must pass one or two args')
        self.required_phony_session_dict[k] = v

    def get_implicated_repopaths(self):
        return self.implicated_repopaths

    def compute_implicated_repopaths(self):
        """
        This will be called at the end of `self.prepare()`, and will be
        dispatched by `self.withfields()`. That means you can list any checked
        input fields as args, and they will be automatically supplied.

        This method should make `self.implicated_repopaths` equal to the set of
        libpaths of all repos "implicated in" this Handler's action -- i.e.
        all the ones for which we want to act exclusively.
        """
        raise NotImplementedError

    def process(self, raise_anticipated=False):
        self.prepare(raise_anticipated=raise_anticipated)
        if self.is_prepared:
            repos = self.get_implicated_repopaths()
            if repos:
                pfsc_task_queue = get_rqueue(MAIN_TASK_QUEUE_NAME)
                next_job_id = str(uuid4())
                redis = get_redis_connection()
                is_async = pfsc_task_queue.is_async

                # Whether we are in async mode or not, we ensure that the
                # Handler instance that carries out the job will not be the
                # present one.
                #
                # This ensures uniformity of behavior across our various
                # execution contexts:
                #   * unit tests: sync
                #   * OCA (one-container app): sync (might revise some day?)
                #   * MCA (multi-container app): async
                # and, in sync mode, prevents the present handler from becoming
                # cluttered with the results of the job handler's work.
                #
                # In async mode, RQ will serialize the handler, and an RQ worker
                # process will deserialize it. In sync mode, RQ does not do any
                # ser./deser. and executes the job with the exact same objects
                # it was passed. So in this case we do the ser./deser. ourselves,
                # in order to make a copy.
                handler_to_enqueue = self
                if not is_async:
                    # Watch this line. `self.serializer` is not explicitly a
                    # part of the `Queue` class's API, so this could change.
                    ser = pfsc_task_queue.serializer
                    handler_to_enqueue = ser.loads(ser.dumps(handler_to_enqueue))

                # If we're operating with RQ in synchronous mode, as in the OCA,
                # then we don't use Redlock. It shouldn't be necessary in such a
                # setting. Also, since the whole job would be carried out while
                # holding the lock, this would go against the intended usage pattern
                # of acquiring, quickly doing something, and releasing. Redlock uses
                # a default expiration of 10s on the lock, and some jobs, e.g. large
                # repo builds, may take much, much longer than that. If the lock does
                # expire, Redlock raises a `ReleaseUnlockedLock` exception on exit.
                ctx_mgr = (Redlock(key=f'pfsc:repo_job_queue_lock', masters={redis})
                           if is_async else nullcontext())
                with ctx_mgr:
                    last_job_ids = [
                        redis.getset(f'pfsc:last_repo_job:{repopath}', next_job_id)
                        for repopath in repos
                    ]
                    # Some last job ids may be None, and we want to filter these out;
                    # the others will be bytes (since retrieved from Redis), and we
                    # must convert these to strings.
                    dependencies = [str(job_id) for job_id in last_job_ids if job_id]
                    pfsc_task_queue.enqueue_call(
                        finish_socket_handler_process_with_app, args=[handler_to_enqueue],
                        job_id=next_job_id, depends_on=dependencies
                    )
                self.job_id = next_job_id
                # At this point, the present handler instance has done all it wants to
                # do, so we count this much as a success.
                self.success = True
                # Meanwhile, when operating asynchronously, an RQ worker will have
                # its own handler instance, after unpickling, and that one will emit
                # its standard response when it finishes.

                if not is_async and check_config("TESTING"):
                    # In our unit tests, we operate synchronously, and have still
                    # not managed to get the Flask-SocketIO test client to receive
                    # emitted messages. (TO DO!) Therefore, in order to be able to
                    # see the emitted response of the job handler, we stash it here
                    # in our own response.
                    resp = handler_to_enqueue.generate_response()
                    self.set_response_field(
                        pfsc.constants.SYNC_JOB_RESPONSE_KEY, resp)

            else:
                self.proceed(raise_anticipated=raise_anticipated)

    def emit_standard_response(self):
        """
        RepoTaskHandler operates outside the standard 'success'/'error' response
        system. Instead, we emit the standard response as a `delayed` event.
        """
        message = self.generate_response()
        self.emit('delayed', message)

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
import inspect
import json
import datetime
import functools
import traceback

from flask import escape, current_app, has_app_context
import werkzeug.exceptions
import mistletoe

from config import ConfigName


class PECode:

    # -- All codes must be positive integers --
    # (Code zero is reserved to mean "no error")

    # basic
    LOCKFILE_TIMEOUT = 10
    MUST_BE_LOGGED_IN = 20
    INADEQUATE_PERMISSIONS = 21
    UNKNOWN_TARGET_RESOURCE_TYPE = 22
    BANNED_USER = 23
    RESOURCE_IS_CLOSED = 24
    USER_LACKS_OWNERSHIP = 25
    ACTION_EXCEEDS_RATE_LIMIT = 26
    EMAIL_ADDR_ALREADY_CONFIRMED = 27
    EMAIL_CONF_CODE_INCORRECT = 28
    BAD_OR_MISSING_CSRF_TOKEN = 29
    USR_LIT_MOD_NOT_IMPORTABLE = 30
    MUST_BE_IN_TESTING_MODE = 31
    LOGIN_INCORRECT = 32
    EXPIRED_TEMPORARY_PASSWORD = 33
    NO_RECORD_OF_PW_RESET_CODE = 34
    DAG_HAS_CYCLE = 35
    MATH_TIMEOUT_EXPIRED = 36
    DOWNLOAD_FAILED = 37
    PDF_PROXY_SERVICE_DISABLED = 38
    MISSING_REQUEST_CONTEXT = 39
    SESSION_HAS_NO_CSRF_TOKEN = 40
    NO_WIP_MODE = 41
    DEMO_REPO_NOT_ALLOWED = 42
    DEMO_REPO_TEMPLATE_NOT_FOUND = 43
    UNTRUSTED_REPO = 44
    ESSENTIAL_CONFIG_VAR_UNDEFINED = 45
    MATH_CALCULATION_FAILED = 46
    SSNR_SERVICE_DISABLED = 47
    REPO_DIR_NESTING_DEPTH_EXCEEDED = 48
    UNKNOWN_GIT_REF = 49
    MALFORMED_CONFIG_VAR = 50
    OAUTH_PROVIDER_NOT_ACCEPTED = 51
    HOSTING_REQUEST_REJECTED = 52
    USER_LACKS_DIRECT_OWNERSHIP = 53
    HOSTING_REQUEST_UNNECESSARY = 54
    AUTO_DEPS_RECUSION_DEPTH_EXCEEDED = 55

    # input checking
    MISSING_INPUT = 100
    INPUT_WRONG_TYPE = 101
    INPUT_TOO_LONG = 102
    INPUT_EMPTY = 103
    BAD_ALTERNATIVE_ARGS = 104
    BAD_EDIT_ACTION_PARAM = 105
    BAD_XPANREQID = 106
    BAD_LIBPATH = 107
    WRONG_LIBPATH_TYPE = 108
    MALFORMED_JSON = 109
    MALFORMED_RDEF_PAIRS_LIST = 110
    MISMATCHED_XPAN_AND_XPANREQ = 111
    BAD_MOOSE_ACTION = 112
    BAD_RESULT_TYPE = 113
    BAD_RESULT_NUMBER = 114
    BAD_INTEGER = 115
    REPEATED_ARGS = 116
    RAW_ARG_IS_NOT_STRING = 117
    BAD_STAR_STATE = 118
    BAD_HASH = 119
    BAD_DISC_NODE_ADDR = 120
    BAD_PASSWORD_FORMAT = 121
    WRONG_PASSWORD = 122
    BAD_ACCT_CREATION_FIELDS = 123
    CONF_ARG_DOES_NOT_MATCH = 124
    BAD_USERNAME_FORMAT = 125
    USERNAME_ALREADY_IN_USE = 126
    USERNAME_DOES_NOT_EXIST = 127
    BAD_EMAIL_ADDR_FORMAT = 128
    EMAIL_ADDR_ALREADY_IN_USE = 129
    EMAIL_ADDR_DOES_NOT_EXIST = 130
    CAPTCHA_INCORRECT = 131
    BAD_FLOAT = 132
    USERNAME_TOO_SIMILAR_TO_EXISTING_ONE = 133
    USERNAME_PROHIBITED = 134
    MODULE_CONTENTS_UNCHANGED = 135
    TARGETED_DEDUC_DOES_NOT_EXIST = 136
    BAD_URL = 137
    MISSING_LEGAL_AGREEMENT = 138
    BAD_REVISION_HASH = 139
    MISSING_EDIT_SUMMARY = 140
    BAD_LINE_REF = 141
    REF_WORK_MISSING_LINE_REF = 142
    BAD_AUTHOR = 143
    BAD_ACCESS_TYPE = 144
    BAD_WORK_TYPE = 145
    DATES_BAD_FOR_PUBLIC_DOMAIN = 146
    UNKNOWN_BOOK_SERIES_CODE = 147
    UNKNOWN_JOURNAL_CODE = 148
    LIBSEG_UNAVAILABLE = 149
    WORK_ALREADY_IN_LIBRARY = 150
    AUTHOR_ALREADY_IN_LIBRARY = 151
    SERIES_ALREADY_IN_LIBRARY = 152
    JOURNAL_ALREADY_IN_LIBRARY = 153
    CUSTOM_LIBSEG_COLLIDES_WITH_AUTO_FORMAT = 154
    MALFORMED_DATE = 156
    BAD_TRANSLITERATION = 157
    BAD_LIBSEG_FORMAT = 158
    MALFORMED_MSC_CODE = 159
    EMPTY_MSC_CODE = 160
    NONEXISTENT_MSC_CODE = 161
    UNKNOWN_LIB_PAGE_TYPE = 162

    MISSING_EXAMPLORE_STEP = 163
    MISSING_EXAMPLORE_PARAM = 164
    MALFORMED_EXAMPLORE_STEP_NUM = 165
    PARAMETER_HAS_NO_TYPE_CHECKING = 166
    MALFORMED_PARAMETER_TYPE = 167
    PARAMETER_HAS_NO_DEFAULT = 168
    BAD_LINE_COUNT = 169
    BAD_PARAMETER_RAW_VALUE = 170
    INCOMPLETE_PARAMETER_DEFN = 171

    NO_LIBPATH_FOR_FS_PATH = 172
    BAD_BOX_LISTING = 173
    MISMATCHED_PATHS_AND_TEXTS = 174
    MISMATCHED_BUILDS_AND_RECS = 175
    UNKNOWN_AUTOWRITE_TYPE = 176
    MISSING_SOCKET_ROOM_NAME = 177
    MALFORMED_PDF_REF_CODE = 178
    PDF_COMBINER_CODE_UKNOWN_VERS = 179
    MISSING_PDF_INFO = 180
    CANNOT_RESOLVE_NODE_LINK_TARGET = 181
    MALFORMED_DOMAIN_POLICY = 182
    MALFORMED_PDF_FINGERPRINT = 183
    MALFORMED_COMBINER_CODE = 184
    CYCLIC_EXAMP_WIDGET_DEPENDENCY = 185
    EXAMP_WIDGET_WRONG_DEPENDENCY_TYPE = 186
    UNKNOWN_PTYPE = 187
    UNBUILT_PARAMETER = 190
    MISSING_EXPORTED_VAR_NAME = 191
    MALFORMED_EXAMP_IMPORT = 192
    BAD_PARAMETER_RAW_VALUE_WITH_BLAME = 193
    EXAMP_WIDGET_DEPENDENCY_MISSING = 194
    MALFORMED_CF = 195

    # pfsc module parsing, VerTeX processing, repo handling
    MODULE_DOES_NOT_EXIST = 200
    MODULE_DECLARES_WRONG_DEDUC_NAMES = 201
    MALFORMED_XPANMOD_PATH = 202
    WRONG_CREATOR_FOR_DEDUCTION = 203
    ILLEGAL_ASSIGNMENT = 204
    DEDUC_NAME_TOO_LONG = 205
    VERTEX_ERROR = 206
    PFSC_PARSE_UNFINISHED_BLOCK = 207
    PFSC_PARSE_UNKNOWN_TOKEN = 208
    MODULE_DOES_NOT_CONTAIN_OBJECT = 209
    SUBOBJECT_NOT_FOUND = 210
    DUPLICATE_DEFINITION_IN_PFSC_MODULE = 211
    TARGET_DOES_NOT_EXIST = 212
    TARGET_OF_WRONG_TYPE = 213
    TARGETS_BELONG_TO_DIFFERENT_DEDUCS = 214
    MALFORMED_QUANTIFIER_NODE_LABEL = 215
    BAD_SUBNODE_TYPE = 216
    MALFORMED_WHERE_NODE_LABEL = 217
    DEDUCTION_DEFINES_NO_GRAPH = 218
    MALFORMED_LIBPATH = 219
    REPO_NOT_CLEAN = 220
    LIBPATH_IS_NOT_REPO = 221
    RELATIVE_LIBPATH_CANNOT_BE_RESOLVED = 222
    BAD_WIDGET_DATAPATH = 223
    LIBPATH_IS_NOT_DIR = 224
    WIDGET_MISSING_NAME = 225
    REPO_HAS_NO_URL = 226
    MANIFEST_TREE_NODE_PARENT_MISSING = 227
    REPO_HAS_NO_REMOTE = 228
    MISSING_DASHGRAPH = 229
    MISSING_ANNOTATION = 230
    MISSING_EXAMPLORER = 231
    LIBPATH_TOO_SHORT = 232
    LIBPATH_IS_NOT_WITHIN_MODULE = 233
    LIBPATH_NOT_ALLOWED = 234
    PARSING_ERROR = 235
    MALFORMED_SOCKETIO_COOKIE = 236
    ACTION_PROHIBITED_IN_READ_ONLY_MODE = 237
    REMOTE_REPO_ERROR = 238
    CYCLIC_IMPORT_ERROR = 239
    MODULE_HAS_NO_CONTENTS = 240
    WIDGET_MISSING_REQUIRED_FIELD = 241
    PLAIN_RELATIVE_IMPORT_MISSING_LOCAL_NAME = 242
    SUPP_NODE_NAMES_SELF_AS_ALTERNATE = 243
    MALFORMED_MULTIPATH = 244
    INVALID_REPO = 245
    MALFORMED_AUGLP = 246
    MALFORMED_AUGLP_CODE = 247
    MALFORMED_ISE_SIDEBAR_CODE = 248
    MALFORMED_ISE_SPLIT_CODE = 249
    MALFORMED_ISE_ACTIVE_TAB_CODE = 250
    MALFORMED_ISE_WIDGET_LINK_CODE = 251
    MALFORMED_CONTENT_FOREST_DESCRIP = 252
    BAD_CHART_REQ_BACKREF = 253
    MALFORMED_ISE_STATE = 254
    MALFORMED_VERSION_TAG = 255
    REPO_IN_DETACHED_STATE = 256
    MISSING_REPO_DEPENDENCY_INFO = 257
    DISALLOWED_VERSION_TAG = 258
    MISSING_REPO_CHANGE_LOG = 259
    DISALLOWED_REPO_CHANGE_LOG = 260
    BUILD_MAKES_DISALLOWED_BREAKING_CHANGE = 261
    ATTEMPTED_RELEASE_BUILD_ON_SUB_REPO = 262
    INVALID_OBIT_LISTING = 263
    INVALID_MOVE_MAPPING = 264
    VERSION_TAG_DOES_NOT_EXIST = 265
    RETRO_MOVE_CONJUGATE = 266
    ATTEMPTED_RELEASE_REINDEX = 267
    VERSION_NOT_BUILT_YET = 268
    MALFORMED_VERSIONED_LIBPATH = 269
    EXCEEDED_MAX_FOREST_EXPANSION_DEPTH = 270
    CONFLICTING_DEDUC_VERSIONS = 271
    MULTIPLE_EXPANSION_DEFINITION = 272
    NO_WIP_IMPORTS_IN_NUMBERED_RELEASES = 273
    REPO_HAS_NO_HASH = 274
    MALFORMED_CONTROL_WIDGET = 275
    MISSING_MANIFEST = 276
    MANIFEST_BAD_FORM = 277
    MISSING_ORIGIN = 278
    CONTROLLED_EVALUATION_EXCEPTION = 279

    # meson/arclang parsing
    MESON_ERROR = 300
    MESON_START_WITH_INF = 301
    MESON_MODAL_WORD_MISSING = 302
    MESON_MODAL_MISMATCH = 303
    MESON_DEDUC_ARROW_BAD_TARGET = 304
    MESON_EXCESS_FLOW = 305
    MESON_EXCESS_ARROW = 306
    MESON_DOWNWARD_FLOW_ERROR = 307
    MESON_DID_NOT_DELIVER = 308
    MESON_EXCESS_METHOD = 309
    MESON_EXCESS_MODAL = 310
    MESON_EMPTY = 311
    MESON_UNKNOWN_TOKEN = 312
    ARCLANG_ERROR = 350

    # writer stuff
    WRITER_DID_NOTHING = 400

    # dbfuncs stuff
    XPAN_NOT_FOUND = 501
    XPAN_REQ_NOT_FOUND = 511
    DEDUC_NOT_FOUND = 520
    DISCUSSION_NODE_NOT_FOUND = 521
    ANNO_NOT_FOUND = 522

    # user stuff
    USER_NOT_LOGGED_IN = 600
    ACTION_PROHIBITED_BY_USER_SETTINGS = 601

    # deep utils stuff
    GIT_HAD_NOTHING_TO_COMMIT = 900

    # A code to mean "unknown". This is the default code in a PfscExcep.
    # No, there's no reason not to exceed 2^16; but this seems large enough.
    UNKNOWN = 65535


class PEBlame:
    UNKNOWN = 0
    SYSTEM = 1
    USER = 2


class PfscExcep(Exception):

    def __init__(self, msg, code=PECode.UNKNOWN, blame=PEBlame.UNKNOWN, bad_field=None, msgIsXSSSafe=False, no_markdown=False):
        # Error messages often get rendered on a page, so let's make sure right here
        # that the message is sanitised. Even though I construct these messages myself,
        # I sometimes put content into them which may have something to do with something
        # user-generated. So, just to be on the safe side...
        if msgIsXSSSafe:
            self.msg = msg
        else:
            self.msg = escape(msg)

        self._code = code
        self._blame = blame
        self._bad_field = bad_field
        self._trace = None
        self._raw_kwargs = None
        self._extended_report = None
        self._extra_data = {}

        # Record the line and file where the exception was raised.
        self._lineno = None
        self._filename = None
        s = inspect.stack()
        if len(s) > 1:
            prev_frame = s[1][0]
            info = inspect.getframeinfo(prev_frame)
            self._lineno = info.lineno
            self._filename = info.filename

        self.no_markdown = no_markdown

    def __str__(self):
        return self.public_msg()

    def public_msg(self):
        msg = self.msg
        if has_app_context() and current_app.config.get('PFSC_ADD_ERR_NUM_TO_MSG'):
            msg = f'Error {self.code()}: ' + msg
        # In development mode it may be useful to also see the private message.
        try:
            mode = os.getenv('FLASK_CONFIG') or ConfigName.PRODUCTION
            if mode in [ConfigName.DOCKERDEV, ConfigName.LOCALDEV] and current_app.config.get('PFSC_SHOW_PRIVATE_ERR_MSGS_IN_DEVEL') == 1:
                msg = self.private_msg()
        except Exception as e:
            msg += '\nError while adding extra err info.'
        if (not self.no_markdown) and has_app_context() and current_app.config.get('PFSC_MARKDOWN_ERR_MSG'):
            msg = mistletoe.markdown(msg)
        return msg

    def set_multiline_msg(self, msg_lines):
        """
        Since we XSS sanitise all messages at construction time, we need a way to
        get some HTML formatting when we want it. In particular, you can pass a
        list of strings to this method, and it will set the public message to be
        those lines joined by '<br>', but it will still sanitise each line individually.
        """
        safe_lines = map(escape, msg_lines)
        self.msg = '<br>'.join(safe_lines)

    def set_msg_for_whose_XSS_safety_I_wholeheartedly_vouch(self, msg):
        """
        Use this one only if you're really sure that you have a safe message,
        and you want HTML formatting to be preserved.
        """
        self.msg = msg

    def bad_field(self):
        return self._bad_field

    def extra_data(self, *args):
        if len(args) == 0:
            return self._extra_data
        else:
            self._extra_data = args[0]

    def private_msg(self):
        s = ''
        s += self.msg
        if self._lineno is not None and self._filename is not None:
            s += '\nPfscExcep occurred at line %s in file "%s".\n' % (
                self._lineno, self._filename
            )
        if self._trace is not None:
            s += '%'*80 + '\n'
            s += 'TRACEBACK:\n'
            s += self._trace
            s += '\n'
        if self._raw_kwargs is not None:
            s += '%'*80 + '\n'
            s += 'RAW KWARGS:\n'
            s += json.dumps(self._raw_kwargs, indent=4)
            s += '\n'
        if self._extended_report is not None:
            s += '%'*80 + '\n'
            s += 'REPORT:\n'
            s += self._extended_report
            s += '\n'
        return s

    def code(self):
        return self._code

    def blame(self):
        return self._blame

    def extendMsg(self, ext):
        self.msg += '\n' + ext

    def setTrace(self, trace):
        self._trace = trace

    def setExtendedReport(self, r):
        self._extended_report = r

    def setRawKwargs(self, d):
        self._raw_kwargs = d


class PfscUnanticipated(Exception):

    def __init__(self, exc, trace, request_info):
        self.time = datetime.datetime.now()
        self.exc = exc
        self.trace = trace
        self.request_info = request_info

    def write_str(self, omitted_req_fields=None):
        omitted_req_fields = omitted_req_fields or []
        req = {k:v for k, v in self.request_info.items() if k not in omitted_req_fields}
        s = ''
        s += '\n' + '~'*50 + '\n'
        s += 'PFSC UNANTICIPATED ERROR:\n\n'
        s += 'Time: %s\n\n' % self.time
        s += 'Request info:\n%s\n' % repr(req)
        s += '-'*50 + '\n'
        s += 'Exception:\n%s\n\n' % repr(self.exc)
        s += '-'*50 + '\n'
        s += 'Stack trace:\n%s\n' % self.trace
        return s

    def __str__(self):
        # Omit CSRF token in case sending err report by email.
        return self.write_str(omitted_req_fields=["CSRF"])

def pfsc_anticipated(anticipated):
    """
    Function decorator to systematise error handling.
    Can ONLY decorate a method in a "Handler" class that implements the interface:
        set_anticipated_pfsc_excep(pfsc_excep)
        get_request_info()
    since it expects the first positional arg to be the 'self' reference to a class instance,
    and it will use these two methods of that instance.

    :param anticipated: list of PECodes

    Let the decorated function be F.

    If no exceptions are raised during execution of F,
    then we simply return the return value of F, if any.

    If a PfscExcep pe is raised during execution of F, then we check whether its
    code c is among the listed 'anticipated' codes. If so then we simply record
    the exception pe using the Handler's set_anticipated_pfsc_excep method.

    If however c is not among the anticipated codes, or if instead another type
    of Exception which is not a PfscExcep was raised, then we wrap the exception
    in an instance of PfscUnanticipated, stash the proper stack trace in there as
    well, and then raise that. We also use the Handler object's get_request_info
    method to stash info about the original request in the PfscUnanticipated object,
    so that in theory it should contain all the info you would need to debug the
    problem (or so we hope).
    """
    def decor(func):
        @functools.wraps(func)
        def pfsc_err_handling_wrapper(handler, *args, **kwargs):
            trace = None
            try:
                return func(handler, *args, **kwargs)
            except PfscExcep as pe:
                code = pe.code()
                # On anticipated error codes, simply record the exception.
                if code in anticipated:
                    handler.set_anticipated_pfsc_excep(pe)
                # Otherwise something unanticipated has happened, so we wrap it and raise it.
                else:
                    # Grab the proper stack trace now, and then re-raise the PfscExcep.
                    trace = traceback.format_exc()
                    raise pe
            except Exception as exc:
                # Here we catch any PfscExceps that were re-raised, as well as any
                # other kind of Exception whatsoever.
                # Grab the stack trace only if we don't already have it.
                if trace is None:
                    trace = traceback.format_exc()
                # Wrap the exception and re-raise it.
                raise PfscUnanticipated(exc, trace, handler.get_request_info())
        return pfsc_err_handling_wrapper
    return decor

def pfsc_anticipate_all_known():
    """
    Just like pfssc_anticipated, except that we automatically consider all
    PfscExceps as anticipated, unless their code is UNKNOWN (the default).
    """
    def decor(func):
        @functools.wraps(func)
        def pfsc_err_handling_wrapper(handler, *args, **kwargs):
            trace = None
            try:
                return func(handler, *args, **kwargs)
            except PfscExcep as pe:
                code = pe.code()
                # On anticipated error codes, simply record the exception.
                if code != PECode.UNKNOWN:
                    handler.set_anticipated_pfsc_excep(pe)
                # Otherwise something unanticipated has happened, so we wrap it and raise it.
                else:
                    # Grab the proper stack trace now, and then re-raise the PfscExcep.
                    trace = traceback.format_exc()
                    raise pe
            except Exception as exc:
                # Here we catch any PfscExceps that were re-raised, as well as any
                # other kind of Exception whatsoever.
                # Grab the stack trace only if we don't already have it.
                if trace is None:
                    trace = traceback.format_exc()
                # Wrap the exception and re-raise it.
                raise PfscUnanticipated(exc, trace, handler.get_request_info())
        return pfsc_err_handling_wrapper
    return decor

def pfsc_anticipate_all():
    """
    This time we consider ALL PfscExceps to be "anticipated," even if
    their code is UNKNOWN (the default).
    """
    def decor(func):
        @functools.wraps(func)
        def pfsc_err_handling_wrapper(handler, *args, **kwargs):
            try:
                return func(handler, *args, **kwargs)
            except PfscExcep as pe:
                pe.setTrace(traceback.format_exc())
                # Record the anticipated exception.
                handler.set_anticipated_pfsc_excep(pe)
                # If the handler is emitting progress events, emit a "crashed" event,
                # so the front-end can react accordingly.
                if hasattr(handler, 'emit_progress_crashed'):
                    handler.emit_progress_crashed()
            except werkzeug.exceptions.HTTPException as http_exc:
                raise http_exc
            except Exception as exc:
                # Here we catch any other kind of Exception whatsoever.
                trace = traceback.format_exc()
                # Wrap the exception and re-raise it.
                raise PfscUnanticipated(exc, trace, handler.get_request_info())
        return pfsc_err_handling_wrapper
    return decor

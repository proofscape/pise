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
Routes for the ISE
"""

from flask import Blueprint, request

from pfsc.constants import WEBSOCKET_NAMESPACE
from pfsc import socketio
from pfsc.methods import (
    enqueue_handler_job,
    handle_and_jsonify,
    handle_and_emit,
    handle_and_download,
)
from pfsc.session import get_csrf_from_session
from pfsc.handlers.app       import StateArgMaker
from pfsc.handlers.write     import WriteHandler, DiffHandler
from pfsc.handlers.repo      import RepoLoader
from pfsc.handlers.name      import NewSubmoduleHandler, RenameModuleHandler
from pfsc.handlers.load      import (
    DashgraphLoader,
    GeneralizedAnnotationLoader,
    SourceLoader,
    EnrichmentLoader,
    ModpathFinder,
)
from pfsc.handlers.study     import GoalOriginFinder
from pfsc.handlers.forest    import (
    ForestUpdateHelper,
    DeducClosureFinder,
    TheoryMapBuilder,
)
from pfsc.handlers.process   import MarkdownHandler
from pfsc.handlers.proxy     import ProxyPdfHandler

# Disabled for now.
# from pfsc.handlers.examp     import ExampReevaluator

from pfsc.handlers.user      import (
    UserInfoLoader,
    UserSettingsUpdater,
    UserInfoExporter,
    SsnrRequestHandler,
    NotesRecorder,
    NotesLoader,
    NotesPurgeHandler,
    HostingRequestHandler,
    UserAcctPurgeHandler,
)

bp = Blueprint('ise', __name__)

# ----------------------------------------------------------------------------
# HTTP Routes

@bp.route('/whoAmI', methods=["GET"])
def who_am_i():
    return handle_and_jsonify(UserInfoLoader, request.args)

@bp.route('/makeIseStateUrlArgs', methods=["POST"])
def make_state_args():
    return handle_and_jsonify(StateArgMaker, request.form)

@bp.route('/loadDashgraph', methods=["GET"])
def load_dashgraph():
    return handle_and_jsonify(DashgraphLoader, request.args)

@bp.route('/lookupGoals', methods=["GET"])
def lookup_goals():
    return handle_and_jsonify(GoalOriginFinder, request.args)

@bp.route('/loadAnnotation', methods=["POST"])
def load_annotation():
    # request.values combines request.args and request.form
    return handle_and_jsonify(GeneralizedAnnotationLoader, request.values)

@bp.route('/loadSource', methods=["GET"])
def load_source():
    return handle_and_jsonify(SourceLoader, request.args)

@bp.route('/getEnrichment', methods=["GET"])
def get_enrichment():
    return handle_and_jsonify(EnrichmentLoader, request.args)

@bp.route('/getModpath', methods=["GET"])
# Note: underscore at end of this function's name is to distinguish it from
# the get_modpath function that we have imported from elsewhere.
def get_modpath_():
    return handle_and_jsonify(ModpathFinder, request.args)

@bp.route('/forestUpdateHelper', methods=["POST"])
def forest_update_helper():
    return handle_and_jsonify(ForestUpdateHelper, request.form)

@bp.route('/getDeductionClosure', methods=["GET"])
def get_deduction_closure_handler():
    return handle_and_jsonify(DeducClosureFinder, request.args)

@bp.route('/getTheoryMap', methods=["GET"])
def get_theory_map():
    return handle_and_jsonify(TheoryMapBuilder, request.args)

@bp.route('/modDiff', methods=["POST"])
def compute_diffs():
    return handle_and_jsonify(DiffHandler, request.form)

@bp.route('/makeNewSubmodule', methods=["PUT"])
def make_new_submodule():
    room = get_csrf_from_session()
    return handle_and_jsonify(NewSubmoduleHandler, request.form, room=room)

@bp.route('/renameModule', methods=["PATCH"])
def rename_module():
    room = get_csrf_from_session()
    return handle_and_jsonify(RenameModuleHandler, request.form, room=room)

@bp.route('/loadRepoTree', methods=["GET"])
def load_repo_tree():
    room = get_csrf_from_session()
    return handle_and_jsonify(RepoLoader, request.args, room=room)

@bp.route('/writeAndBuild', methods=["POST"])
def write_and_build():
    room = get_csrf_from_session()
    return handle_and_jsonify(WriteHandler, request.form, room=room)


@bp.route('/userUpdate', methods=["POST"])
def user_update():
    return handle_and_jsonify(UserSettingsUpdater, request.form)

@bp.route('/requestSsnr', methods=["POST"])
def request_ssnr():
    return handle_and_jsonify(SsnrRequestHandler, request.form)

@bp.route('/recordNotes', methods=["POST"])
def record_notes():
    return handle_and_jsonify(NotesRecorder, request.form)

@bp.route('/loadNotes', methods=["POST"])
def load_notes():
    return handle_and_jsonify(NotesLoader, request.form)

@bp.route('/purgeNotes', methods=["POST"])
def purge_notes():
    return handle_and_jsonify(NotesPurgeHandler, request.form)

@bp.route('/requestHosting', methods=["POST"])
def request_hosting():
    return handle_and_jsonify(HostingRequestHandler, request.form)

@bp.route('/exportUserInfo', methods=["GET"])
def export_user_info():
    return handle_and_download(
        UserInfoExporter, request.args,
        download_name='pise_user_acct_info.json',
    )

@bp.route('/purgeUserAcct', methods=["POST"])
def purge_user_acct():
    return handle_and_jsonify(UserAcctPurgeHandler, request.form)

# ----------------------------------------------------------------------------
# Sometimes useful in development:

#@bp.route('/info')
def info():
    return bp.root_path

#@bp.route('/oops')
def oops():
    assert 0

# ----------------------------------------------------------------------------
# Synchronous SocketIO Events

# For now we don't have any synchronous SocketIO event handlers -- i.e. handlers
# in which the web server proecess itself computes the desired result, instead
# of handing off the job to an RQ worker process. But we keep the old endpoint
# below commented out, as an example.

#@socketio.on('markdown', namespace=WEBSOCKET_NAMESPACE)
#def render_markdown(message):
#    handle_and_emit(MarkdownHandler, message, request.sid)

# ----------------------------------------------------------------------------
# Asynchronous SocketIO Events

@socketio.on('markdown', namespace=WEBSOCKET_NAMESPACE)
def render_markdown(message):
    enqueue_handler_job(MarkdownHandler, message, request.sid)

# For now we've moved exclusively to client-side examp eval, with Pyodide.
# May want to reinstate server-side eval as a configurable option at some
# point, so we're keeping this here, commented out.
#@socketio.on('examp_eval', namespace=WEBSOCKET_NAMESPACE)
#def examp_eval(message):
#    enqueue_handler_job(ExampReevaluator, message, request.sid)

@socketio.on('proxy_get_pdf', namespace=WEBSOCKET_NAMESPACE)
def proxy_get_pdf(message):
    message['UserAgent'] = request.headers.get('User-Agent', '')
    message['AcceptLanguage'] = request.headers.get('Accept-Language', 'en-US,en;q=0.9')
    enqueue_handler_job(ProxyPdfHandler, message, request.sid)

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

"""
Methods of handling requests.
"""

import logging
from io import BytesIO

from flask import jsonify, render_template, send_file, url_for
import requests

from pfsc import get_app, check_config
from pfsc.rq import get_rqueue
from pfsc.constants import MAIN_TASK_QUEUE_NAME
from pfsc.handlers import emit_ise_event
from pfsc.session import get_csrf_from_session

def enqueue_handler_job(handler_class, message, request_id):
    """
    Convenience method to be used by socketio event handlers. Enqueues an RQ job, and
    emits the original message, with added job_id field, under the `job_enqueued` event.

    :param handler_class: the class that's going to handle the job
    :param message: The original message received by the socketio event handler.
    :param request_id: the ID of the socketio client

    :return: the job id
    """
    pfsc_task_queue = get_rqueue(MAIN_TASK_QUEUE_NAME)
    job = pfsc_task_queue.enqueue(
        handler_job, handler_class, message, request_id, get_csrf_from_session()
    )
    job_id = job.get_id()
    message['job_id'] = job_id
    # Here setting the room equal to the sid is not strictly necessary, since we should be
    # inside of an event context anyway.
    emit_ise_event(request_id, 'job_enqueued', request_id, message)
    return job_id

def bypass_queue(handler_class, message, request_id):
    """
    Possibly useful during testing? Would take same args as `enqueue_handler_job`.
    Haven't made it work yet, but keeping it around anyway...
    """
    handler_job(handler_class, message, request_id)

def log_within_rq(msg, level=logging.INFO):
    """
    Add a message to your RQ worker's logs.

    :param msg: The message (string) you want to log.
    :param level: The desired logging level. Level INFO should be enough,
      provided we are still starting our workers with that logging level.
      See the `worker.py` startup script at top level of this repo.
    :return: nothing
    """
    logger = logging.getLogger('rq.worker')
    logger.log(level, msg)

def handler_job(handler_class, message, request_id, csrf_from_session=None):
    """
    This function is only intended to be enqueued in an RQ task queue.
    That is why it begins by making an app and opening the app context.
    Otherwise the RQ worker will try to carry out the task without any app context,
    and then anything that requires configuration info (e.g. writing or building
    a module) will fail.
    """
    #log_within_rq('START HANDLER...')
    app, _ = get_app()
    with app.app_context():
        request_info = message.copy()
        handler = handler_class(request_info, request_id, csrf_from_session=csrf_from_session)
        # ~~~~~~~~~~~~~~~~
        # Tried some profiling...
        PROFILE = False
        if PROFILE:
            # Profiling (see stdout from RQ worker) confirms suspicion that Earley alg parsing is the time hog.
            import cProfile
            cProfile.runctx('handler.process()', globals(), locals())
        else:
            handler.process()
        # ~~~~~~~~~~~~~~~~
        handler.emit_standard_response()

def handle_and_jsonify(handler_class, info_dict, room=None):
    """
    Convenience method for handling a request with a handler class, and returning the
    jsonification of that handler's standard response.

    :param handler_class: the class to be used to handle the request
    :param info_dict: the dictionary of input fields for the handler
    :param room: optional socket room, in case the handler_class is a SocketHandler
    :return: the jsonification of the handler's standard response
    """
    h = handler_class(info_dict) if room is None else handler_class(info_dict, room)
    h.process()
    r = h.generate_response()
    return jsonify(r)


def handle_and_download(handler_class, info_dict, room=None,
                        download_field='download', html_field='html',
                        **send_file_kwargs):
    """
    Convenience method for handling a request with a handler class, and either
    instructing the user's browser to download as a file the value of a
    particular field in the handler's standard response, or else serving some
    HTML.

    The behavior depends on the handler's standard response `r`. If `r` reports
    a positive error level, then we serve a standard "download error" page as
    HTML, reporting the error to the user.

    Else we consult `r[download_field]`. If this is defined, its value
    should be a bytes object, and this is what will be downloaded as a file.

    Else we consult `r[html_field]`. If this is defined, its value should be
    an HTML string, which we serve as HTML.

    Else we again serve the "download error" page, this time constructing a
    canned error message.

    The client should call endpoints that use this handling method by opening
    a small popup window. In cases of success, the file will download, and the
    user can close the popup. In cases of error, the error HTML will be displayed
    in the popup, which again the user can close. Either way, you avoid
    disrupting or navigating away from the page you were on when you requested
    the download.

    :param handler_class: the class to be used to handle the request
    :param info_dict: the dictionary of input fields for the handler
    :param room: optional socket room, in case the handler_class is a SocketHandler
    :param download_field: string, naming the result field whose value is
        to be downloaded.
    :param html_field: string, naming the result field whose value is to be
        served as HTML, if no download was provided.
    :param send_file_kwargs: forwarded to the `send_file()` function.
        See https://werkzeug.palletsprojects.com/en/2.1.x/utils/#werkzeug.utils.send_file
    :return: the result of the call to `send_file()`, or some HTML.
    """
    h = handler_class(info_dict) if room is None else handler_class(info_dict, room)
    h.process()
    r = h.generate_response()

    def write_standard_download_error_page(err_msg):
        return render_template(
            "download_error.html",
            err_msg=err_msg,
            css=[
                url_for('vstat.static', filename='css/base.css'),
            ],
        )

    if r['err_lvl'] > 0:
        err_msg = f'{r["err_lvl"]}: {r["err_msg"]}'
        return write_standard_download_error_page(err_msg)
    elif download_field in r:
        f = BytesIO(r[download_field])
        return send_file(f, as_attachment=True, **send_file_kwargs)
    elif html_field in r:
        return r[html_field]
    else:
        err_msg = 'An unknown error occurred.'
        return write_standard_download_error_page(err_msg)


def handle_and_serve_html(handler_class, info_dict):
    """
    Convenience method for handling a request with a handler class, and returning the
    HTML that that handler is supposed to generate, or an error message string.

    :param handler_class: the class to be used to handle the request
    :param info_dict: the dictionary of input fields for the handler
    :return: HTML or an error message string
    """
    h = handler_class(info_dict)
    h.process()
    r = h.generate_html_response()
    return r

def handle_and_redirect(handler_class, info_dict):
    """
    Convenience method for handling a request with a handler class, and then
    either following the redirect generated by it, or else returning the
    HTML that the handler generates, or an error message string.

    :param handler_class: the class to be used to handle the request
    :param info_dict: the dictionary of input fields for the handler
    :return: a redirect, some HTML, or an error message string
    """
    h = handler_class(info_dict)
    h.process()
    r = h.generate_redirect_or_html()
    return r

def handle_and_emit(socket_handler_class, info_dict, room):
    """
    Convenience method for handling a request with a socket handler class, and emitting
    the standard response upon completion.

    :param socket_handler_class: the class to be used to handle the request
    :param info_dict: the dictionary of input fields for the handler
    :param room: The SocketIO "room" to which emits should be directed. Usually this will
                 be equal to the `request.sid` supplied by Flask-SocketIO, so that our
                 responses can be directed just to the client whose request we are handling.
    :return: nothing
    """
    s = socket_handler_class(info_dict, room)
    s.process()
    s.emit_standard_response()


def try_to_proxy(url):
    response = requests.get(url)
    return response.content if response.status_code == 200 else None


def proxy_or_render(proxy_config_var_name, template_filename, **context_kwargs):
    """
    This supports a common pattern where the goal is to generate some HTML, and
    there is an optional config var where a proxy URL may be provided, or else
    we default to rendering a certain template.

    @param proxy_config_var_name: the name (str) of the config var to check
        for a proxy URL.
    @param template_filename: the filename of the template to be rendered if
        the proxy fails.
    @param context_kwargs: kwargs to be passed as context for rendering
        the template.
    @return: HTML string
    """
    html = None
    url = check_config(proxy_config_var_name)
    if url:
        html = try_to_proxy(url)
    return html or render_template(template_filename, **context_kwargs)

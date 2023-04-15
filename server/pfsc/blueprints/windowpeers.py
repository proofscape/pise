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

from flask import request
from flask_socketio import emit, disconnect, join_room
from flask_socketio import rooms as get_current_rooms

from pfsc import socketio
from pfsc.session import get_csrf_from_session

NAMESPACE = '/pfsc-ise'
PREFIX = 'windowPeers'

###########################################################################
# Connect handler

# The connect handler is not purely a part of the Window Peers Protocol,
# but we define it here in this module anyway. It _supports_ our implementation
# of the protocol. But it also serves another purpose: generally speaking,
# Handlers that handle long-running tasks may wish to groupcast a socket event
# as notification when the task is completed, and they can send this event to
# the "CSRF Room," which is established by the connect handler.

@socketio.on('connect', namespace=NAMESPACE)
def on_connect():
    """
    We add all of a user's socket connections to a common room. We want this room
    to have a unique, unguessable name, and we want that name to be recorded in
    the user's Flask session. The existing CSRF token in the user's session fits
    the bill perfectly, so we use it as the name of the room.

    This provides a trustworthy way of groupcasting an event to all of a user's
    sockets in response to an HTTPS request, without the user having to nominate
    a recipient socket ID as an arg in that request.

    Note that with Flask-SocketIO, socket handlers always see the Flask session
    as it was at the time the connect event occurred, which is why it is possible
    for us to read the existing CSRF token here in this handler.

    See <https://flask-socketio.readthedocs.io/en/latest/implementation_notes.html#access-to-flask-s-context-globals>
    """
    token = get_csrf_from_session()
    join_room(token, sid=request.sid, namespace=NAMESPACE)

###########################################################################
# Window Peers Protocol

@socketio.on('disconnect', namespace=NAMESPACE)
def on_disconnect():
    sid = request.sid
    # Fortunately, during disconnect handling, the disconnecting client is
    # still in any rooms that it belonged to. So we can use this to roomcast
    # the fact of this client's departure, allowing the remaining members of
    # the group to update their records accordingly.
    current_rooms = get_current_rooms(sid, namespace=NAMESPACE)
    for r in current_rooms:
        #print(f'Final roomcast to {r} for disconnect of {sid}.')
        emit(PREFIX+'observeDeparture', {'name': sid}, namespace=NAMESPACE, room=r)

@socketio.on(PREFIX+'join', namespace=NAMESPACE)
def join(msg):
    token = get_csrf_from_session()
    birthday = msg.get('birthday')
    response = {
        "windowGroupId": token,
        "name": request.sid,
        "birthday": birthday,
    }
    socketio.emit(PREFIX+'hello', response, namespace=NAMESPACE, room=token)

@socketio.on(PREFIX+'depart', namespace=NAMESPACE)
def disconnect_request(msg=None):
    # Note: The window-peers protocol does not require that any `msg` be sent
    # along with a `depart` event, but Flask-SocketIO seems to want to provide
    # `None` as the msg anyway, when none is sent. Therefore this function has
    # to accept an argument, or else we get an error.
    # (Namely, you'll see
    #    TypeError: disconnect_request() takes 0 positional arguments but 1 was given
    # along with a traceback citing only the `socketio` and `flask_socketio`
    # Python packages, in the console for the web server.)
    disconnect()

@socketio.on(PREFIX+'welcome', namespace=NAMESPACE)
def welcome(msg):
    room = msg.get('to', request.sid)
    emit(PREFIX+'welcome', msg, room=room)

@socketio.on(PREFIX+'postWindowMessage', namespace=NAMESPACE)
def postWindowMessage(msg):
    room = msg.get('room', request.sid)
    emit(PREFIX+'handleWindowMessage', msg, room=room)

@socketio.on(PREFIX+'sendWindowEvent', namespace=NAMESPACE)
def sendWindowEvent(wrapper):
    event = wrapper.get('event', {})
    room = wrapper.get('room', request.sid)
    include_self = wrapper.get('includeSelf', True)
    emit(PREFIX+'genericWindowEvent', event, room=room, include_self=include_self)

###########################################################################

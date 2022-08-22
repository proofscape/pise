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

# See https://flask-socketio.readthedocs.io/en/latest/#emitting-from-an-external-process
# regarding necessity of monkey patching. Testing showed that this is indeed required for
# our setup, using RQ.
import eventlet
eventlet.monkey_patch()

import sys
from pfsc import socketio, make_app


def start_web_server(app):
    is_dev = app.config.get("IS_DEV", False)
    socketio.run(app, host='0.0.0.0', port=7372, debug=is_dev, use_reloader=is_dev)


def main():
    """
    Start up the web server.

    If "oca" was passed as command line arg, then we understand that we are
    running in the one-container app, and that we should act accordingly.
    """
    app = make_app()
    if len(sys.argv) >=2 and sys.argv[1] == "oca":
        # In the OCA, we use a single instance of Redis both to support
        # RedisGraph as our GDB, and for all its other functions such as recording
        # RQ jobs, and supporting SocketIO emit. Therefore the BGSAVEs that record
        # the GDB on disk also record all that other stuff. The question is: on
        # startup, should we delete all other Redis keys outside the GDB? We have
        # a function, `prepare_redis_for_oca()` that does this. For now, we are
        # not using it.
        #from pfsc.gdb.cypher.rg import prepare_redis_for_oca
        #okay = prepare_redis_for_oca(app)
        okay = True
    else:
        okay = True
    if okay:
        start_web_server(app)


if __name__ == "__main__":
    main()

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

import os

import dill
from flask import current_app, g
from redis import Redis
import rq

from config import ConfigName
from pfsc import check_config
from pfsc.constants import RQ_QUEUE_NAMES

def get_redis_connection():
    return Redis.from_url(current_app.config["REDIS_URI"])

def get_rqueue(queue_name):
    """
    :param: the name of the queue you want
    :return: an RQ queue
    """
    if queue_name not in g:
        server_mode = os.getenv('FLASK_CONFIG')
        is_local_dev = server_mode == ConfigName.LOCALDEV
        force_sync = check_config("FORCE_RQ_SYNCHRONOUS")
        q = rq.Queue(
            queue_name,
            is_async=(not is_local_dev and not force_sync),
            connection=get_redis_connection(),
            serializer=dill,
        )
        setattr(g, queue_name, q)
    return getattr(g, queue_name)

def close_rqueues(e=None):
    for name in RQ_QUEUE_NAMES:
        q = g.pop(name, None)
        if q is not None:
            pass # Do we need to tell the queue that it is closing?

def init_app(app):
    """
    Inform the Flask app that during teardown, the queue should be closed.
    """
    app.teardown_appcontext(close_rqueues)

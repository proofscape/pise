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
We follow the advice given [here](https://python-rq.org/docs/workers/#performance-notes),
and preload libraries in order to improve RQ worker performance.

In tests performed on a 2019 MacBook Pro, in Chrome 86.0.4240.111,
saving a 3866-byte pfsc module took about 1400ms without preloading libraries,
but took only about 350ms with preloading. In terms of user experience, this
is a very perceptible latency difference!
"""

import sys
import os

import dill
from redis import Redis
from rq import Connection, Worker

from pfsc import make_app
from pfsc.email import send_error_report_mail

# Set a signal that this is an RQ worker.
# This is checked by the `pfsc.permissions.check_is_psm()` function, to
# determine whether it will say we're in PSM, when in production.
os.environ["IS_PFSC_RQ_WORKER"] = "1"

app = make_app()
worker = None

def need_scheduler():
    # For now there is only one reason why we might need a scheduler,
    # namely to clean up demo repos. This function may evolve as new
    # reasons arise.
    return app.config.get("PROVIDE_DEMO_REPOS")

def email_exc_handler(job, *exc_info):
    worker.log.info('Sending email notification of exception.')
    send_error_report_mail(exc_info=exc_info, asyncr=False)

# Preload libraries.
# These lines may be grayed-out in your IDE, but don't delete them! They have a
# definite impact, improving performance of the worker by loading libraries
# once now, instead of repeatedly on each job.
from pfsc.blueprints.ise import *
# However, the following lines are deliberately commented out now, since we
# are not currently supporting server-side math eval.
#from pfsc_examp.parameters.types import *
#from pfsc_examp.parse.display import *

with Connection(connection=Redis.from_url(app.config.get("REDIS_URI"))):
    qs = sys.argv[1:] or ['pfsc-tasks']
    worker = Worker(
        qs, log_job_description=False,
        exception_handlers=[email_exc_handler],
        serializer=dill,
    )
    worker.work(with_scheduler=need_scheduler(), logging_level="INFO")

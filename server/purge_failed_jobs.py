#!/usr/bin/env python
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

"""
Purge all jobs from the failed job registries.
"""

from pfsc import make_app
from pfsc.rq import get_rqueue
from pfsc.constants import RQ_QUEUE_NAMES

dry_run = False

app = make_app()
with app.app_context():
    for queue_name in RQ_QUEUE_NAMES:
        print('-' * 40)
        print(f'Queue: {queue_name}:')
        q = get_rqueue(queue_name)
        reg = q.failed_job_registry
        jobs = reg.get_job_ids()
        print(f'  Purging {len(jobs)} failed jobs...')
        for job in jobs:
            print(f'    {job}...')
            if not dry_run:
                reg.remove(job, delete_job=True)
        jobs = reg.get_job_ids()
        n = len(jobs)
        if not n == 0:
            print(f'  Error: {n} jobs remain:')
            for job in jobs:
                print(f'    {job}')
        else:
            print('  Success. All failed jobs were purged.')

# --------------------------------------------------------------------------- #
#   Copyright (c) 2018-2023 Proofscape Contributors                           #
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
Controlled calculation for the server environment.
"""

from pfsc_util.imports import from_import

current_app = from_import('flask', 'current_app')

retry = from_import('tenacity', 'retry')
RetryError = from_import('tenacity', 'RetryError')
wait_exponential = from_import('tenacity', 'wait_exponential')
retry_if_result = from_import('tenacity', 'retry_if_result')
stop_after_delay = from_import('tenacity', 'stop_after_delay')

get_rqueue = from_import('pfsc.rq', 'get_rqueue')
MATH_CALC_QUEUE_NAME = from_import('pfsc.constants', 'MATH_CALC_QUEUE_NAME')
PfscExcep, PECode = from_import('pfsc.excep', ['PfscExcep', 'PECode'])


# Some calculations may return `None` as their legitimate result
# (e.g. `primitive_root(8)`), so we need a special object type to
# represent "no result":
class NoResult:
    pass


def calculate(f, *args, **kwargs):
    """
    Use this function to wait for a calculation to be carried out by an RQ worker,
    with a timeout, i.e. maximum execution time before the job is halted and marked
    as failed.

    Note that this function blocks: it won't return until the job is either
    completed or timed out. Thus, the purpose of using a worker here is not to make
    the job asynchronous, but to have the job carried out in a separate process,
    which can be timed out, and which can be containerized.
    """
    def give_up(due_to_timeout=False):
        msg = f'Math calc job failed for {f}'
        code = PECode.MATH_TIMEOUT_EXPIRED if due_to_timeout else PECode.MATH_CALCULATION_FAILED
        return PfscExcep(msg, code)

    overall_timeout = current_app.config.get("MATH_JOB_QUEUE_TIMEOUT", 180)

    @retry(
        retry=retry_if_result(lambda r: isinstance(r, NoResult)),
        wait=wait_exponential(multiplier=0.02, exp_base=1.4, max=1),
        stop=stop_after_delay(overall_timeout),
    )
    def check_job(job):
        job.get_status(refresh=True)
        if job.is_finished:
            return job.result
        # When jobs time out, RQ marks them as failed.
        # (See `rq.registry.StartedJobRegistry.cleanup()`.)
        # However, to be safe we also catch stopped jobs.
        elif job.is_failed or job.is_stopped:
            raise give_up()
        return NoResult()

    q = get_rqueue(MATH_CALC_QUEUE_NAME)
    calc_timeout = current_app.config.get("MATH_CALCULATION_TIMEOUT", 3)
    job = q.enqueue_call(f, args=args, kwargs=kwargs, timeout=calc_timeout)
    try:
        result = check_job(job)
    except RetryError:
        result = NoResult()
    if isinstance(result, NoResult):
        raise give_up(due_to_timeout=True)
    else:
        return result

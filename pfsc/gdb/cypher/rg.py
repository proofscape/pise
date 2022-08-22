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

"""Utilities for RedisGraph. """

from flask import has_app_context
import neo4j
from redis import Redis
import redis.exceptions
import redisgraph
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception_message
)

from pfsc import check_config
from pfsc.constants import MAIN_TASK_QUEUE_NAME
from pfsc.rq import get_rqueue


class RedisGraphWrapper:
    """
    In order to allow the same code to work both with Neo4j and
    with RedisGraph, this class acts as an adapter, wrapping a RedisGraph
    `Graph` instance, and serving to stand in where any of a Neo4j database,
    session, or transaction would have been used.

    It also ensures that after a transaction is committed, we initiate a
    background save to write dump.rdb to disk.

    Note: An attempt was made to achieve an actual notion of transaction, using
    Redis's MULTI/EXEC/DISCARD commands, and at this time the remnants of that
    code are left commented out below.

    It doesn't work for us because our code (originally written
    to work with Neo4j transactions) expects the sophisticated behavior wherein
    a read following a write shows the results of the write, even before the
    transaction has been committed. Redis doesn't provide that, so our code
    fails. We try to build up all our writes in a single MULTI before finally
    hitting EXEC to run them all, and meanwhile our reads see the wrong things.
    """

    GRAPH_NAME = 'pfscidx'
    BGSAVE_RETRIES = 10 # attempts

    def __init__(self, uri):
        self.uri = uri
        r = Redis.from_url(uri)
        self.graph = redisgraph.graph.Graph(RedisGraphWrapper.GRAPH_NAME, r)
        self.rqueue = get_rqueue(MAIN_TASK_QUEUE_NAME)
        #self.has_open_transaction = False

    def execute_command(self, *args, **kwargs):
        self.graph.redis_con.execute_command(*args, **kwargs)

    # ------------------------------------------------
    # Act as database

    def session(self):
        # Return self to act as a session.
        return self

    def close(self):
        pass

    # ------------------------------------------------
    # Act as session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # If user started a transaction but didn't deliberately commit it, we discard it.
        #if self.has_open_transaction:
        #    self.discard()
        pass

    def begin_transaction(self):
        # See <https://redis.io/topics/transactions>
        #self.execute_command("MULTI")
        #self.has_open_transaction = True
        return self

    # ------------------------------------------------
    # Act as transaction

    def run(self, query, **params):
        res = self.graph.query(query, params)
        return RedisGraphResultWrapper(res)

    def commit(self):
        #self.execute_command("EXEC")
        #self.has_open_transaction = False
        # Save to disk.
        # FIXME:
        #  Probably the attempt to bg save should be done inside a try-block,
        #  excepting `tenacity`'s `RetryError`. The question is: what's the
        #  right behavior in that case? For now, we just let the pfsc-server
        #  stop altogether. If we're not saving our graphdb data to disk, it
        #  could be considered reason to stop everything. Send an email? ???
        self.rqueue.enqueue(redis_bg_save, self.uri)
        #redis_bg_save(self.graph.redis_con)

    def rollback(self):
        pass

    #def discard(self):
        #self.execute_command("DISCARD")
        #self.has_open_transaction = False

BGSAVE_IN_PROG = "Background save already in progress"

@retry(
    stop=stop_after_attempt(RedisGraphWrapper.BGSAVE_RETRIES),
    wait=wait_exponential(multiplier=0.5, min=1, max=16),
    retry=(
        retry_if_exception_type(redis.exceptions.ResponseError) &
        retry_if_exception_message(BGSAVE_IN_PROG)
    )
)
def redis_bg_save(redis_uri):
    r = Redis.from_url(redis_uri)
    try:
        r.execute_command("BGSAVE")
    except redis.exceptions.ResponseError as e:
        if str(e) == BGSAVE_IN_PROG and has_app_context() and check_config("TESTING"):
            pass
        else:
            raise


def prepare_redis_for_oca(app):
    """
    In the one-container app, we want to clear everything out of Redis except
    for the GDB at startup time.

    @return: True if we successfully made a connection to Redis and cleared all
        keys except that under which the GDB is stored; False otherwise.
    """
    import time

    def log(m, debug=False):
        msg = f'[proofscape startup] {m}\n'
        if debug:
            app.logger.debug(msg)
        else:
            app.logger.info(msg)

    MAX_TRIES = 5
    r = Redis.from_url(app.config["REDIS_URI"])
    c = 0
    while c < MAX_TRIES:
        try:
            result = r.ping()
        except redis.exceptions.RedisError:
            log('Waiting for Redis...')
            time.sleep(1)
            c += 1
        else:
            if result:
                log('Connected to Redis.')
                break
    else:
        log('No Redis connection. Gave up.')
        return False

    keys = r.keys("*")
    gdb_key = RedisGraphWrapper.GRAPH_NAME.encode()
    keys.remove(gdb_key)
    assert gdb_key not in keys
    n_keys = len(keys)
    log(f'Found {n_keys} keys outside the GDB.')
    if n_keys:
        log(str(keys), debug=True)
        n_removed = r.delete(*keys)
        log(f'Removed {n_removed} keys.')
        if n_removed != n_keys:
            log(f'Could not remove all keys outide the GDB.')
            return False
    return True


class RedisGraphResultWrapper:
    """
    We wrap a redisgraph.query_result.QueryResult to make it behave
    sufficiently like a neo4j.work.result.Result.
    In particular, we ensure that (a) it is directly iterable, and
    that (b) it has a `consume()` method that returns an object having
    a `counters` attribute that is a neo4j.SummaryCounters.
    """

    def __init__(self, res):
        self.raw_res = res
        self.stats = {
            k.replace(' ', '-').lower() : int(v) for k, v in res.statistics.items()
        }
        self.counters = neo4j.SummaryCounters(self.stats)

    def __iter__(self):
        return iter(map(RedisGraphRecordWrapper, self.raw_res.result_set))

    def consume(self):
        return self

    def report_count(self):
        """
        Report the count from a graph database query that returns `count(*)`.

        RedisGraph seems to exhibit some odd behavior wherein it returns an
        empty result set in the case where the count is zero.
        (Still true as of v2.4.7.)

        Thus, e.g., if the count is say 4, you will get [[4]] as expected; but
        if the count is zero you will get [] instead of the [[0]] you would want.

        :return: int
        """
        r = self.raw_res.result_set
        return 0 if len(r) == 0 else r[0][0]

    def single(self):
        if len(self.raw_res.result_set) == 0:
            return None
        return RedisGraphRecordWrapper(self.raw_res.result_set[0])


class RedisGraphRecordWrapper:

    def __init__(self, rec):
        self.rec = rec

    def __getitem__(self, item):
        return self.rec[item]

    def value(self, key=0):
        return self.rec[key]

    def values(self):
        return list(self.rec)


def check_count(result):
    """
    Read the count out of the result of a graph database query
    that returns `count(*)`.

    We need a special function for this because of peculiarities of RedisGraph.
    See RedisGraphResultWrapper.report_count

    :param result: the result object (from Neo4j or from RedisGraph)
    :return: the count
    """
    if isinstance(result, neo4j.Result):
        return result.single().value()
    else:
        assert isinstance(result, RedisGraphResultWrapper)
        return result.report_count()

def get_node_label(j):
    """
    When a node has been returned by a Cypher query, read the label of the
    node.
    """
    if isinstance(j, redisgraph.node.Node):
        return j.label
    else:
        # Should be an instance of neo4j.graph.Node
        assert len(j.labels) == 1
        return list(j.labels)[0]

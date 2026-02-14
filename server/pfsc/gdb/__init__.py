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

import pathlib

from flask import current_app
from flask import g as flask_g
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import GraphTraversalSource
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.driver.serializer import GraphSONSerializersV3d0
from gremlite import SQLiteConnection, GremliteConfig
from wsc_grempy_transport.transport import websocket_client_transport_factory
import neo4j

from pfsc import check_config
from pfsc.gdb.reader import GraphReader
from pfsc.gdb.writer import GraphWriter

from pfsc.gdb.cypher.reader import CypherGraphReader, RedisGraphReader
from pfsc.gdb.cypher.writer import CypherGraphWriter
from pfsc.gdb.cypher.rg import RedisGraphWrapper

from pfsc.gdb.gremlin.reader import GremlinGraphReader
from pfsc.gdb.gremlin.writer import GremlinGraphWriter, GREMLIN_REMOTE_NAME
from pfsc.gdb.gremlin.util import GtxTx_Gts


GDB_OBJECT_NAME = "gdb"
GRAPH_READER_NAME = "graph_reader"
GRAPH_WRITER_NAME = "graph_writer"


def get_gdb():
    """
    Get a driver object for interacting with the graph database.
    """
    if GDB_OBJECT_NAME not in flask_g:
        uri = current_app.config["GRAPHDB_URI"]
        # Decide by the form of the URI which graph database system we are using.
        protocol = uri.split(":")[0]
        if protocol == 'file' or (protocol in ['ws', 'wss'] and uri.endswith('/gremlin')):
            # It looks like you are using Gremlin.
            if protocol == 'file':
                # We assume you want to use GremLite.
                path = pathlib.Path(uri[7:])
                # We ensure the named directory and any missing parent dirs exist.
                path_dir = path.parent
                if not path_dir.exists():
                    path_dir.mkdir(parents=True)
                # Set these True to log low level SQLite usage:
                log_plans = False
                check_qqc_patterns = False
                # Experimentally trying the read-all-at-once setting:
                glconf = GremliteConfig()
                glconf.read_all_at_once = True
                # As can be seen in the `GremlinGraphWriter.__init__()` method, we will
                # ignore pise/server's `USE_TRANSACTIONS` config var and will always use
                # transactions with GremLite. Therefore here we want to turn off its autocommit mode.
                remote = SQLiteConnection(path, autocommit=False,
                                          timeout=5,
                                          log_plans=log_plans, check_qqc_patterns=check_qqc_patterns,
                                          log_open_close=True,
                                          config=glconf)
            else:
                # We assume you are connecting to a Gremlin server.
                #
                # Starting with gremlinpython==3.6.1, we have to explicitly request the
                # `GraphSONSerializersV3d0` message serializer. This was the default in 3.6.0,
                # but in 3.6.1 they changed the default to `GraphBinarySerializersV1`.
                # See https://tinkerpop.apache.org/docs/current/upgrade/#_tinkerpop_3_6_1
                #
                # One consequence of the change is that, while TinkerGraph still uses longs (not ints)
                # as edge IDs, so that the `E()` step still requires IDs to be passed as instances
                # of `gremlin_python.statics.long`, the 3.6.1 serializer *reports* edge IDs to you
                # as `int` (whereas 3.6.0 reported them as `long`).
                #
                # Our code sometimes stores edge IDs as returned from certain Gremlin queries, and
                # then attempts to pass these same objects right back as arguments to `E()` steps.
                # (For example this happens in `pfsc.gdb.gremlin.writer.GremlinGraphWriter.ix0200()`.)
                # In order for this to work with TinkerGraph from gremlinpython 3.6.1 and onward,
                # without having to explicitly recast the IDs as longs, we need to use the old serializer.
                remote = DriverRemoteConnection(
                    uri, transport_factory=websocket_client_transport_factory,
                    message_serializer=GraphSONSerializersV3d0()
                )
            # Store the remote so it can be closed later.
            setattr(flask_g, GREMLIN_REMOTE_NAME, remote)
            gdb = traversal(GtxTx_Gts).with_remote(remote)
        else:
            if protocol in ['redis', 'rediss']:
                gdb = RedisGraphWrapper(uri)
            elif protocol in ['bolt', 'neo4j']:
                username = current_app.config.get('GDB_USERNAME', '')
                password = current_app.config.get('GDB_PASSWORD', '')
                gdb = neo4j.GraphDatabase.driver(uri, auth=(username, password))
            else:
                raise Exception(f"Unknown GDB URI format: {uri}")
        setattr(flask_g, GDB_OBJECT_NAME, gdb)
    return getattr(flask_g, GDB_OBJECT_NAME)


def get_graph_reader() -> GraphReader:
    """
    Get the GraphReader.
    """
    if GRAPH_READER_NAME not in flask_g:
        gdb = get_gdb()
        if using_gremlin(gdb):
            reader = GremlinGraphReader(gdb)
        elif using_RedisGraph(gdb):
            reader = RedisGraphReader(gdb)
        else:
            reader = CypherGraphReader(gdb)
        setattr(flask_g, GRAPH_READER_NAME, reader)
    return getattr(flask_g, GRAPH_READER_NAME)


def get_graph_writer() -> GraphWriter:
    """
    Get the GraphWriter.
    """
    if GRAPH_WRITER_NAME not in flask_g:
        reader = get_graph_reader()
        if isinstance(reader, GremlinGraphReader):
            use_transactions = current_app.config["USE_TRANSACTIONS"]
            writer = GremlinGraphWriter(reader, use_transactions)
        else:
            # Here we're not consulting the USE_TRANSACTIONS config var at all,
            # because we've only contemplated two GDBs that use Cypher, namely,
            # Neo4j and RedisGraph. With the former we automatically use transactions (since
            # it supports them), and with the latter we do not (because it doesn't).
            writer = CypherGraphWriter(reader)
        setattr(flask_g, GRAPH_WRITER_NAME, writer)
    return getattr(flask_g, GRAPH_WRITER_NAME)


def using_RedisGraph(gdb=None):
    """
    Check whether we are using RedisGraph
    """
    gdb = gdb or get_gdb()
    return isinstance(gdb, RedisGraphWrapper)


def using_gremlin(gdb=None):
    """
    Check whether we are using Gremlin.
    """
    gdb = gdb or get_gdb()
    return isinstance(gdb, GraphTraversalSource)


def building_in_gdb():
    return check_config("BUILD_IN_GDB")


def close_gdb(e=None):
    gdb = flask_g.pop(GDB_OBJECT_NAME, None)
    if gdb is not None:
        if using_gremlin(gdb):
            if remote := getattr(flask_g, GREMLIN_REMOTE_NAME):
                remote.close()
            # Alternatively:
            '''
            for strat in gdb.traversal_strategies.traversal_strategies:
                if rc := getattr(strat, 'remote_connection'):
                    rc.close()
            '''
        else:
            gdb.close()


def init_app(app):
    """
    Inform the Flask app that during teardown, the graph database driver
    should be closed.
    """
    app.teardown_appcontext(close_gdb)

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

from flask import current_app
from flask import g as flask_g
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import GraphTraversalSource
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from wsc_grempy_transport.transport import websocket_client_transport_factory
import neo4j

from pfsc import check_config
from pfsc.gdb.reader import GraphReader
from pfsc.gdb.writer import GraphWriter

from pfsc.gdb.cypher.reader import CypherGraphReader, RedisGraphReader
from pfsc.gdb.cypher.writer import CypherGraphWriter
from pfsc.gdb.cypher.rg import RedisGraphWrapper

from pfsc.gdb.gremlin.reader import GremlinGraphReader
from pfsc.gdb.gremlin.writer import GremlinGraphWriter
from pfsc.gdb.gremlin.util import GtxTx_Gts


GDB_OBJECT_NAME = "gdb"
GRAPH_READER_NAME = "graph_reader"
GRAPH_WRITER_NAME = "graph_writer"
GREMLIN_REMOTE_NAME = "gremlin_remote"


def get_gdb():
    """
    Get a driver object for interacting with the graph database.
    """
    if GDB_OBJECT_NAME not in flask_g:
        uri = current_app.config["GRAPHDB_URI"]
        # Decide by the form of the URI which graph database system we are using.
        if uri.endswith('/gremlin'):
            remote = DriverRemoteConnection(
                uri, transport_factory=websocket_client_transport_factory)
            # Store the remote so it can be closed later.
            setattr(flask_g, GREMLIN_REMOTE_NAME, remote)
            gdb = traversal(GtxTx_Gts).with_remote(remote)
        else:
            protocol = uri.split(":")[0]
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

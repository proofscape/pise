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
Occasionally, for admin or diagnostics, you want a Gremlin traversal (a "g") in
the Python interactive shell. This module provides a convenience function for
getting one.
"""

import os

from dotenv import load_dotenv
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from wsc_grempy_transport.transport import websocket_client_transport_factory


# Load pfsc-server/instance/.env
# In particular, this gives us the same GRAPHDB_URI the server sees.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOTENV_PATH = os.path.join(BASE_DIR, 'instance', '.env')
load_dotenv(DOTENV_PATH)


def getg(uri=None, lh=False, npp=None):
    """
    Get a traversal.

    @param uri: string, None, optional. If a string, we try to connect to
        a Gremlin server of this exact URI.
    @param lh: boolean. If True, we use ws://localhost:8182/gremlin as the URI.
    @param npp: string, None, optional. Stands for "Neptune prefix." If a
        string, we use f'wss://{npp}.neptune.amazonaws.com:8182/gremlin' as URI.

    If none of the kwargs is supplied, we use os.getenv("GRAPHDB_URI") as URI.
    """
    if uri is None:
        if lh:
            uri = 'ws://localhost:8182/gremlin'
        elif npp is not None:
            uri = f'wss://{npp}.neptune.amazonaws.com:8182/gremlin'
        else:
            uri = os.getenv("GRAPHDB_URI")

    remote = DriverRemoteConnection(uri, transport_factory=websocket_client_transport_factory)
    g = traversal().with_remote(remote)
    return g

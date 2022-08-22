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

"""
Currently we don't actually include any of the tests here in our normal testing
of pfsc-server. Their purpose instead is to encode oddities I have discovered
in gremlin-python, or in the behavior of various GDB systems.

NOTE: It is _important_ not to include these tests in ordinary testing, since
they wipe out all nodes, in order to start with a fresh database.
"""

import pytest

from gremlin_python.process.graph_traversal import __
#from gremlin_python.process.traversal import P, T, TextP

from pfsc.gdb import get_gdb


def get_conn():
    return get_gdb()

@pytest.mark.skip('Just for manual testing.')
def test_V_empty_list(app):
    """
    Seems V([]) matches all vertices, whereas I'd expect it to match none.
    """
    with app.app_context():
        print()
        g = get_conn()
        g.V().drop().iterate()
        g.add_v('Foo').add_v('Foo').add_v('Foo').iterate()
        print(g.V([]).count().next())

@pytest.mark.skip('Just for manual testing.')
def test_Neptune_union_as(app):
    """
    On TinkerGraph, you can use `union().as()` and the `as` name gets applied
    to every result of the union, which is what I'd expect.
    On Neptune, the name is only applied to the results of the first traversal
    in the union. If you want it to apply to all, you have to put the `as`
    inside the union, on the end of every traversal.

    UPDATE (06Jan22): Remarks above were based on commit f413bc3, from 18Dec21.
    However, just ran this test on Neptune, and it prints "2" in all three cases.
    In other words, it now does seem to work?
    """
    with app.app_context():
        print()
        g = get_conn()

        # Make a graph with three Nodes: S1, S2, T:
        g.V().drop().iterate()
        g.add_v('Node').property('name', 'S1').iterate()
        g.add_v('Node').property('name', 'S2').iterate()
        g.add_v('Node').property('name', 'T').iterate()

        # Now we try three different ways of connecting each "source" node (Si)
        # to the "target" node (T).

        # Note: None of these queries is how I would really do this; I just want
        # to demonstrate the issue.

        # Put the `as` OUTSIDE the `union`:
        g.V().union(
            __.has('name', 'S1'),
            __.has('name', 'S2'),
        ).as_('S').V().has('name', 'T').add_e('OUTSIDE').from_('S').iterate()

        # Repeat the `as` INSIDE the `union`:
        g.V().union(
            __.has('name', 'S1').as_('S'),
            __.has('name', 'S2').as_('S'),
        ).V().has('name', 'T').add_e('INSIDE').from_('S').iterate()

        # Put the `as` outside the `union` after a BARRIER step:
        g.V().union(
            __.has('name', 'S1'),
            __.has('name', 'S2'),
        ).barrier().as_('S').V().has('name', 'T').add_e('BARRIER').from_('S').iterate()

        for method in ["OUTSIDE", "INSIDE", "BARRIER"]:
            print(method, g.E().hasLabel(method).count().next())

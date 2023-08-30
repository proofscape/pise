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

import json

import pytest

from pfsc.build import index
from pfsc.build.repo import RepoInfo
from pfsc.excep import PfscExcep, PECode

alex_v1_summary="""
{
    "intention": {
        "add_nodes": {
            "test.alex.math.thm2.Pf.A3": {
                "libpath": "test.alex.math.thm2.Pf.A3",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Thm2.C3": {
                "libpath": "test.alex.math.thm2.Thm2.C3",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Thm2.C2": {
                "libpath": "test.alex.math.thm2.Thm2.C2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Thm2.C1": {
                "libpath": "test.alex.math.thm2.Thm2.C1",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Thm2.I": {
                "libpath": "test.alex.math.thm2.Thm2.I",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf": {
                "libpath": "test.alex.math.thm2.Pf",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Thm2": {
                "libpath": "test.alex.math.thm2.Thm2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf.Thm2.C1": {
                "libpath": "test.alex.math.thm2.Pf.Thm2.C1",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf.Thm2.C2": {
                "libpath": "test.alex.math.thm2.Pf.Thm2.C2",
                "modpath": "test.alex.math.thm2"
            }
        },
        "add_relns": {
            "test.alex.math.thm2.Pf.A3:BELONGSTO:test.alex.math.thm2.Pf": {
                "tail_libpath": "test.alex.math.thm2.Pf.A3",
                "head_libpath": "test.alex.math.thm2.Pf",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Thm2.C2:BELONGSTO:test.alex.math.thm2.Thm2": {
                "tail_libpath": "test.alex.math.thm2.Thm2.C2",
                "head_libpath": "test.alex.math.thm2.Thm2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf.Thm2.C2:BELONGSTO:test.alex.math.thm2.Pf": {
                "tail_libpath": "test.alex.math.thm2.Pf.Thm2.C2",
                "head_libpath": "test.alex.math.thm2.Pf",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Thm2.C3:BELONGSTO:test.alex.math.thm2.Thm2": {
                "tail_libpath": "test.alex.math.thm2.Thm2.C3",
                "head_libpath": "test.alex.math.thm2.Thm2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Thm2.I:BELONGSTO:test.alex.math.thm2.Thm2": {
                "tail_libpath": "test.alex.math.thm2.Thm2.I",
                "head_libpath": "test.alex.math.thm2.Thm2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf.Thm2.C1:BELONGSTO:test.alex.math.thm2.Pf": {
                "tail_libpath": "test.alex.math.thm2.Pf.Thm2.C1",
                "head_libpath": "test.alex.math.thm2.Pf",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Thm2.C1:BELONGSTO:test.alex.math.thm2.Thm2": {
                "tail_libpath": "test.alex.math.thm2.Thm2.C1",
                "head_libpath": "test.alex.math.thm2.Thm2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf.A3:IMPLIES:test.alex.math.thm2.Pf.Thm2.C1": {
                "tail_libpath": "test.alex.math.thm2.Pf.A3",
                "head_libpath": "test.alex.math.thm2.Pf.Thm2.C1",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Thm2.I:IMPLIES:test.alex.math.thm2.Thm2.C3": {
                "tail_libpath": "test.alex.math.thm2.Thm2.I",
                "head_libpath": "test.alex.math.thm2.Thm2.C3",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Thm2.I:IMPLIES:test.alex.math.thm2.Thm2.C1": {
                "tail_libpath": "test.alex.math.thm2.Thm2.I",
                "head_libpath": "test.alex.math.thm2.Thm2.C1",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf.A3:IMPLIES:test.alex.math.thm2.Pf.Thm2.C2": {
                "tail_libpath": "test.alex.math.thm2.Pf.A3",
                "head_libpath": "test.alex.math.thm2.Pf.Thm2.C2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Thm2.I:IMPLIES:test.alex.math.thm2.Thm2.C2": {
                "tail_libpath": "test.alex.math.thm2.Thm2.I",
                "head_libpath": "test.alex.math.thm2.Thm2.C2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf.Thm2.C2:GHOSTOF:test.alex.math.thm2.Thm2.C2": {
                "tail_libpath": "test.alex.math.thm2.Pf.Thm2.C2",
                "head_libpath": "test.alex.math.thm2.Thm2.C2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf.Thm2.C1:GHOSTOF:test.alex.math.thm2.Thm2.C1": {
                "tail_libpath": "test.alex.math.thm2.Pf.Thm2.C1",
                "head_libpath": "test.alex.math.thm2.Thm2.C1",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf:TARGETS:test.alex.math.thm2.Thm2.C2": {
                "tail_libpath": "test.alex.math.thm2.Pf",
                "head_libpath": "test.alex.math.thm2.Thm2.C2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf:TARGETS:test.alex.math.thm2.Thm2.C1": {
                "tail_libpath": "test.alex.math.thm2.Pf",
                "head_libpath": "test.alex.math.thm2.Thm2.C1",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf:EXPANDS:test.alex.math.thm2.Thm2": {
                "tail_libpath": "test.alex.math.thm2.Pf",
                "head_libpath": "test.alex.math.thm2.Thm2",
                "modpath": "test.alex.math.thm2"
            }
        }
    },
    "nodes_created": 9,
    "nodes_deleted": 0,
    "relationships_created": 17,
    "relationships_deleted": 0
}
"""

alex_v2_summary="""
{
    "intention": {
        "remove_nodes": {
            "test.alex.math.thm2.Pf.Thm2.C2": 1
        },
        "add_nodes": {
            "test.alex.math.thm2.Pf2.Thm2.C2": {
                "libpath": "test.alex.math.thm2.Pf2.Thm2.C2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf.Thm2.C3": {
                "libpath": "test.alex.math.thm2.Pf.Thm2.C3",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf2.A4": {
                "libpath": "test.alex.math.thm2.Pf2.A4",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf2": {
                "libpath": "test.alex.math.thm2.Pf2",
                "modpath": "test.alex.math.thm2"
            }
        },
        "detach_relns": {
            "test.alex.math.thm2.Pf.A3:IMPLIES:test.alex.math.thm2.Pf.Thm2.C2": 1,
            "test.alex.math.thm2.Pf.Thm2.C2:GHOSTOF:test.alex.math.thm2.Thm2.C2": 1,
            "test.alex.math.thm2.Pf.Thm2.C2:BELONGSTO:test.alex.math.thm2.Pf": 1
        },
        "remove_relns": {
            "test.alex.math.thm2.Pf:TARGETS:test.alex.math.thm2.Thm2.C2": 1
        },
        "add_relns": {
            "test.alex.math.thm2.Pf.A3:IMPLIES:test.alex.math.thm2.Pf.Thm2.C3": {
                "tail_libpath": "test.alex.math.thm2.Pf.A3",
                "head_libpath": "test.alex.math.thm2.Pf.Thm2.C3",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf2.A4:IMPLIES:test.alex.math.thm2.Pf2.Thm2.C2": {
                "tail_libpath": "test.alex.math.thm2.Pf2.A4",
                "head_libpath": "test.alex.math.thm2.Pf2.Thm2.C2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf.Thm2.C3:GHOSTOF:test.alex.math.thm2.Thm2.C3": {
                "tail_libpath": "test.alex.math.thm2.Pf.Thm2.C3",
                "head_libpath": "test.alex.math.thm2.Thm2.C3",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf2.Thm2.C2:GHOSTOF:test.alex.math.thm2.Thm2.C2": {
                "tail_libpath": "test.alex.math.thm2.Pf2.Thm2.C2",
                "head_libpath": "test.alex.math.thm2.Thm2.C2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf2.Thm2.C2:BELONGSTO:test.alex.math.thm2.Pf2": {
                "tail_libpath": "test.alex.math.thm2.Pf2.Thm2.C2",
                "head_libpath": "test.alex.math.thm2.Pf2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf.Thm2.C3:BELONGSTO:test.alex.math.thm2.Pf": {
                "tail_libpath": "test.alex.math.thm2.Pf.Thm2.C3",
                "head_libpath": "test.alex.math.thm2.Pf",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf2.A4:BELONGSTO:test.alex.math.thm2.Pf2": {
                "tail_libpath": "test.alex.math.thm2.Pf2.A4",
                "head_libpath": "test.alex.math.thm2.Pf2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf2:EXPANDS:test.alex.math.thm2.Thm2": {
                "tail_libpath": "test.alex.math.thm2.Pf2",
                "head_libpath": "test.alex.math.thm2.Thm2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf2:TARGETS:test.alex.math.thm2.Thm2.C2": {
                "tail_libpath": "test.alex.math.thm2.Pf2",
                "head_libpath": "test.alex.math.thm2.Thm2.C2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf:TARGETS:test.alex.math.thm2.Thm2.C3": {
                "tail_libpath": "test.alex.math.thm2.Pf",
                "head_libpath": "test.alex.math.thm2.Thm2.C3",
                "modpath": "test.alex.math.thm2"
            }
        }
    },
    "nodes_created": 4,
    "nodes_deleted": 1,
    "relationships_created": 10,
    "relationships_deleted": 4
}
"""

alex_v3_summary="""
{
    "intention": {
        "remove_nodes": {
            "test.alex.math.thm2.Pf.Thm2.C3": 1,
            "test.alex.math.thm2.Pf.Thm2.C1": 1,
            "test.alex.math.thm2.Pf.A3": 1,
            "test.alex.math.thm2.Pf": 1
        },
        "add_nodes": {
            "test.alex.math.thm2.Pf13.Thm2.C1": {
                "libpath": "test.alex.math.thm2.Pf13.Thm2.C1",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf13.Thm2.C3": {
                "libpath": "test.alex.math.thm2.Pf13.Thm2.C3",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf13": {
                "libpath": "test.alex.math.thm2.Pf13",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf13.A3": {
                "libpath": "test.alex.math.thm2.Pf13.A3",
                "modpath": "test.alex.math.thm2"
            }
        },
        "detach_relns": {
            "test.alex.math.thm2.Pf.Thm2.C3:BELONGSTO:test.alex.math.thm2.Pf": 1,
            "test.alex.math.thm2.Pf.A3:IMPLIES:test.alex.math.thm2.Pf.Thm2.C3": 1,
            "test.alex.math.thm2.Pf.A3:BELONGSTO:test.alex.math.thm2.Pf": 1,
            "test.alex.math.thm2.Pf.A3:IMPLIES:test.alex.math.thm2.Pf.Thm2.C1": 1,
            "test.alex.math.thm2.Pf:EXPANDS:test.alex.math.thm2.Thm2": 1,
            "test.alex.math.thm2.Pf.Thm2.C3:GHOSTOF:test.alex.math.thm2.Thm2.C3": 1,
            "test.alex.math.thm2.Pf.Thm2.C1:BELONGSTO:test.alex.math.thm2.Pf": 1,
            "test.alex.math.thm2.Pf:TARGETS:test.alex.math.thm2.Thm2.C1": 1,
            "test.alex.math.thm2.Pf:TARGETS:test.alex.math.thm2.Thm2.C3": 1,
            "test.alex.math.thm2.Pf.Thm2.C1:GHOSTOF:test.alex.math.thm2.Thm2.C1": 1
        },
        "add_relns": {
            "test.alex.math.thm2.Pf13.Thm2.C3:GHOSTOF:test.alex.math.thm2.Thm2.C3": {
                "tail_libpath": "test.alex.math.thm2.Pf13.Thm2.C3",
                "head_libpath": "test.alex.math.thm2.Thm2.C3",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf13.Thm2.C1:GHOSTOF:test.alex.math.thm2.Thm2.C1": {
                "tail_libpath": "test.alex.math.thm2.Pf13.Thm2.C1",
                "head_libpath": "test.alex.math.thm2.Thm2.C1",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf13:EXPANDS:test.alex.math.thm2.Thm2": {
                "tail_libpath": "test.alex.math.thm2.Pf13",
                "head_libpath": "test.alex.math.thm2.Thm2",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf13.A3:IMPLIES:test.alex.math.thm2.Pf13.Thm2.C1": {
                "tail_libpath": "test.alex.math.thm2.Pf13.A3",
                "head_libpath": "test.alex.math.thm2.Pf13.Thm2.C1",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf13.A3:IMPLIES:test.alex.math.thm2.Pf13.Thm2.C3": {
                "tail_libpath": "test.alex.math.thm2.Pf13.A3",
                "head_libpath": "test.alex.math.thm2.Pf13.Thm2.C3",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf13:TARGETS:test.alex.math.thm2.Thm2.C3": {
                "tail_libpath": "test.alex.math.thm2.Pf13",
                "head_libpath": "test.alex.math.thm2.Thm2.C3",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf13:TARGETS:test.alex.math.thm2.Thm2.C1": {
                "tail_libpath": "test.alex.math.thm2.Pf13",
                "head_libpath": "test.alex.math.thm2.Thm2.C1",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf13.A3:BELONGSTO:test.alex.math.thm2.Pf13": {
                "tail_libpath": "test.alex.math.thm2.Pf13.A3",
                "head_libpath": "test.alex.math.thm2.Pf13",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf13.Thm2.C3:BELONGSTO:test.alex.math.thm2.Pf13": {
                "tail_libpath": "test.alex.math.thm2.Pf13.Thm2.C3",
                "head_libpath": "test.alex.math.thm2.Pf13",
                "modpath": "test.alex.math.thm2"
            },
            "test.alex.math.thm2.Pf13.Thm2.C1:BELONGSTO:test.alex.math.thm2.Pf13": {
                "tail_libpath": "test.alex.math.thm2.Pf13.Thm2.C1",
                "head_libpath": "test.alex.math.thm2.Pf13",
                "modpath": "test.alex.math.thm2"
            }
        }
    },
    "nodes_created": 4,
    "nodes_deleted": 4,
    "relationships_created": 10,
    "relationships_deleted": 10
}
"""

@pytest.mark.skip('Does this test still make sense with multi-version indexing?')
def test_index_1(app):
    print()
    with app.app_context():
        # Index the Alex, Brook, and Casey "math" repos, ensuring each is on its v0 branch.
        ri = {}
        for name in 'alex brook casey'.split():
            # Form the libpath to the repo.
            repo_path = 'test.%s.math' % name
            # Form a RepoInfo object on this path. This helps us validate and work with repos.
            repo_info = RepoInfo(repo_path)
            # Store it for use later, in advancing to later branches.
            ri[name] = repo_info
            # Make sure we're on the initial version.
            repo_info.checkout('v0')
            # Index recursively.
            rep = index(repo_info)
            print("\nIndex %s:" % repo_path)
            print(rep)

        # Brook advances to v1.
        print("\nBrook advances to v1.")
        brook_ri = ri['brook']
        brook_ri.checkout('v1')
        rep = index(brook_ri)
        print("\nIndex %s:" % brook_ri.libpath)
        print(rep)
        assert rep.steps[0].intention.remove_nodes == {'test.brook.math.exp1.X1.B2'}
        assert rep.steps[0].counters.nodes_deleted == 1
        assert rep.steps[0].intention.detach_relns == {'test.brook.math.exp1.X1.B2:IMPLIES:test.brook.math.exp1.X1.Pf.A2',
                                                'test.casey.math.expand.W2.X1.B2:GHOSTOF:test.brook.math.exp1.X1.B2',
                                                'test.brook.math.exp1.X1.B2:BELONGSTO:test.brook.math.exp1.X1',
                                                'test.casey.math.expand.W2:TARGETS:test.brook.math.exp1.X1.B2'}
        assert rep.steps[0].counters.relationships_deleted == 4

        # Attempt to reindex Casey, without advancing.
        # Should raise exception for missing deduc target.
        print("\nAttempt to reindex Casey, without advancing.")
        casey_ri = ri['casey']
        with pytest.raises(PfscExcep) as ei:
            index(casey_ri)
        pe = ei.value
        print(pe)
        assert pe.code() == PECode.TARGET_DOES_NOT_EXIST

        # Now we do advance Casey to v1, and again try to reindex.
        # This time it should work.
        print("\nCasey advances to v1.")
        casey_ri.checkout('v1')
        rep = index(casey_ri)
        print("\nIndex %s:" % casey_ri.libpath)
        print(rep)

        assert rep.steps[0].intention.detach_relns == {'test.casey.math.expand.W2.C2:BELONGSTO:test.casey.math.expand.W2',
                                                       'test.casey.math.expand.W2:EXPANDS:test.brook.math.exp1.X1',
                                                       'test.casey.math.expand.W2.X1.B2:BELONGSTO:test.casey.math.expand.W2',
                                                       'test.casey.math.expand.W2.C2:IMPLIES:test.casey.math.expand.W2.X1.B2'}
        assert rep.steps[0].counters.relationships_deleted == 4
        assert rep.steps[0].intention.remove_nodes == {'test.casey.math.expand.W2.C2',
                                                       'test.casey.math.expand.W2.X1.B2',
                                                       'test.casey.math.expand.W2'}
        assert rep.steps[0].counters.nodes_deleted == 3

        # Next advance Alex's repo to later versions.
        print("\nAlex advances to v1.")
        alex_ri = ri['alex']
        alex_ri.checkout('v1')
        rep = index(alex_ri)
        print("\nIndex %s:" % alex_ri.libpath)
        ifs = rep.get_full_summary()
        print(repr(ifs))
        assert json.loads(alex_v1_summary) == ifs.serializable_rep()

        print("\nAlex advances to v2.")
        alex_ri.checkout('v2')
        rep = index(alex_ri)
        print("\nIndex %s:" % alex_ri.libpath)
        ifs = rep.get_full_summary()
        print(repr(ifs))
        assert json.loads(alex_v2_summary) == ifs.serializable_rep()

        print("\nAlex advances to v3.")
        alex_ri.checkout('v3')
        rep = index(alex_ri)
        print("\nIndex %s:" % alex_ri.libpath)
        ifs = rep.get_full_summary()
        print(repr(ifs))
        assert json.loads(alex_v3_summary) == ifs.serializable_rep()

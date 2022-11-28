# --------------------------------------------------------------------------- #
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

import pytest

# ------------------------------------------------------------------------
# TODO: adapt these old tests to multi-versioning:

from pfsc.build.lib.addresses import (
    ForestAddressList,
    find_descendants_of,
    find_oldest_elements,
    get_ancestral_closure,
)

@pytest.mark.skip('Not yet adapted from pre-multi-versioning')
@pytest.mark.parametrize("deducs, expected_oldest", (
("W1 W2 W3 W4 W5 W6 W7", "W1 W2 W3 W4 W5 W6 W7"),
("W1 W2 W3 W4 W5 W6 W7 X2", "W1 W2 X2 W6 W7"),
("W1 W2 W3 W4 W5 W6 W7 X2 Pf", "Pf W6 W7"),
("W1 W2 W3 W4 W5 W6 W7 Thm1 Thm2", "Thm1 Thm2"),
))
def test_find_oldest_elements(forest_addresses, deducs, expected_oldest):
    print()
    fal = ForestAddressList([forest_addresses[name] for name in deducs.split()])
    computed_oldest = find_oldest_elements(fal)
    expected_oldest_name_set = set(expected_oldest.split())
    computed_oldest_name_set = set([a.libpath.split('.')[-1] for a in computed_oldest])
    print(sorted(list(computed_oldest_name_set)))
    assert computed_oldest_name_set == expected_oldest_name_set

@pytest.mark.skip('Not yet adapted from pre-multi-versioning')
@pytest.mark.parametrize("pool_minus, ancestors, expected_desc", (
("", "X1", "W1 W2"),
("W1", "X1", "W2"),
("", "Pf2", "X3 W6 W7"),
("", "Thm2", "Pf13 Pf2 X3 W6 W7"),
))
def test_find_descendants_of(forest_addresses, pool_minus, ancestors, expected_desc):
    print()
    ancestors = ForestAddressList([forest_addresses[name] for name in ancestors.split()])
    pool = ForestAddressList([
        forest_addresses[name] for name in (set(forest_addresses.keys()) - set(pool_minus.split()))
    ])
    expected_desc_name_set = set(expected_desc.split())
    computed_desc = find_descendants_of(ancestors, pool)
    computed_desc_name_set = set([a.libpath.split('.')[-1] for a in computed_desc])
    print(sorted(list(computed_desc_name_set)))
    assert computed_desc_name_set == expected_desc_name_set

@pytest.mark.skip('Not yet adapted from pre-multi-versioning')
@pytest.mark.parametrize("deducs, expected_seqs", (
("W1", ["Thm1 Pf X1 W1"]),
("W1 W2", ["Thm1 Pf X1 W1", "X1 W2"]),
("W1 W3", ["Thm1 Pf X1 W1", "Pf X2 W3"]),
("W1 W3 W6", ["Thm1 Pf X1 W1", "Pf X2 W3", "Thm2 Pf2 X3 W6"]),
))
def test_ancestral_closure(app, forest_addresses, deducs, expected_seqs):
    print()
    with app.app_context():
        deducpaths = {
            forest_addresses[name].libpath:forest_addresses[name].version
            for name in deducs.split()
        }
        computed_closure = get_ancestral_closure(deducpaths, topo_sort=True)
        computed_closure_name_list = [libpath.split('.')[-1] for libpath in computed_closure]
        print(computed_closure_name_list)
        # Check that we got the right _set_ of deducs.
        expected_closure_name_set = set()
        for seq in expected_seqs:
            expected_closure_name_set |= set(seq.split())
        assert expected_closure_name_set == set(computed_closure_name_list)
        # Check that the order in each sequence is as expected.
        for seq in expected_seqs:
            seq = seq.split()
            for D, E in zip(seq[:-1], seq[1:]):
                i = computed_closure_name_list.index(D)
                j = computed_closure_name_list.index(E)
                assert i < j

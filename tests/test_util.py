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

from datetime import timedelta

import pytest

from pfsc.excep import PfscExcep, PECode
from pfsc import util
from pfsc.build.repo import get_repo_info

def test_topo_sort_1():
    """
    Simple test of a topo sort that works.
    """
    graph = {
        6: [1, 3],
        3: [5],
        1: [5, 7],
        5: [4],
        7: [2],
        4: [2],
        2: []
    }
    ts = util.topological_sort(graph)
    print(ts)
    assert ts == [6, 3, 1, 7, 5, 4, 2]

def test_topo_sort_2():
    """
    This time we expect an error, due to the given graph containing a cycle.
    """
    with pytest.raises(PfscExcep) as ei:
        graph = {
            6: [1, 3],
            3: [5],
            1: [5, 7],
            5: [4],
            7: [2],
            4: [2],
            2: [5]
        }
        util.topological_sort(graph)
    assert ei.value.code() == PECode.DAG_HAS_CYCLE

def test_suh():
    h = util.short_unpronouncable_hash(length=7, start_with_letter=True)
    assert len(h) == 7
    assert h[0].isalpha()
    assert h.isalnum()

@pytest.mark.parametrize('s, e', [
    [59, 'about 0 minutes'],
    [78, 'about 1 minute'],
    [2067, 'about 34 minutes'],
    [3600, '1 hour'],
    [4000, 'about 1 hour'],
    [10800, '3 hours'],
    [11000, 'about 3 hours'],
    [24*3600, '24 hours'],
])
def test_ctd(s, e):
    delta = timedelta(seconds=s)
    assert util.casual_time_delta(delta) == e

@pytest.mark.parametrize('repopath, n', [
    ['test.moo.links', 2],
    ['test.wid.get', 3],
])
def test_count_pfsc_modules(repopath, n, app, repos_ready):
    with app.app_context():
        ri = get_repo_info(repopath)
        assert util.count_pfsc_modules(ri.abs_fs_path_to_dir) == n

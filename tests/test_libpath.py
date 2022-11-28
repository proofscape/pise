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

from pfsc.build.lib.libpath import get_formal_moditempath
from pfsc.lang.modules import get_modpath
from pfsc.excep import PfscExcep


@pytest.mark.parametrize("libpath, modpath", (
    ("test.hist.lit", "test.hist.lit"),
    ("test.hist.lit.H.ilbert.ZB.Thm168", "test.hist.lit.H.ilbert.ZB.Thm168"),
    ("test.hist.lit.H.ilbert.ZB.Thm168.Thm", "test.hist.lit.H.ilbert.ZB.Thm168"),
    ("test.hist.lit.H.ilbert.ZB.Thm168.Pf.Cs1.Cs1A.S", "test.hist.lit.H.ilbert.ZB.Thm168"),
))
def test_get_modpath(libpath, modpath):
    assert get_modpath(libpath) == modpath


@pytest.mark.parametrize("libpath, moditempath", (
    ("test.hist.lit", False),
    ("test.hist.lit.H.ilbert.ZB.Thm168", False),
    ("test.hist.lit.H.ilbert.ZB.Thm168.Thm", "test.hist.lit.H.ilbert.ZB.Thm168.Thm"),
    ("test.hist.lit.H.ilbert.ZB.Thm168.Pf.Cs1.Cs1A.S", "test.hist.lit.H.ilbert.ZB.Thm168.Pf"),
))
def test_get_formal_moditempath(libpath, moditempath):
    if moditempath:
        assert get_formal_moditempath(libpath) == moditempath
    else:
        with pytest.raises(PfscExcep) as ei:
            get_formal_moditempath(libpath)
        assert str(ei.value).find('too short') >= 0

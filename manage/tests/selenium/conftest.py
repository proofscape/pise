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

import logging

import pytest

import conf as pfsc_conf
from tests.selenium.util import make_driver, get_pise_url, check_pise_server


@pytest.fixture
def pise_url():
    return get_pise_url()


@pytest.fixture
def pise_server_status(pise_url):
    return check_pise_server()


@pytest.fixture
def pise_server_ready(pise_server_status):
    """
    Require a ready server, raising an exception otherwise.
    """
    code, message = pise_server_status
    if code < 4:
        raise Exception('PISE Server not ready: ' + message)
    return pise_server_status


@pytest.fixture
def driver():
    return make_driver()


@pytest.fixture
def selenium_logging_level():
    return getattr(logging, pfsc_conf.SEL_LOG_LEVEL)

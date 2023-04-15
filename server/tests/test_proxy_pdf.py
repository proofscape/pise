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

import pytest

from pfsc.handlers.proxy import ProxyPdfHandler
from pfsc.excep import PECode


@pytest.mark.req_csrf(False)
def test_proxy_10(app):
    """
    Try downloading PDF from disallowed domain.
    """
    print()
    with app.app_context():
        app.config["PFSC_ENABLE_PDF_PROXY"] = 1
        h = ProxyPdfHandler({
            'url': 'http://example.com/foo.pdf',
            'UserAgent': 'Mozilla/5.0',
            'AcceptLanguage': 'en-US,en;q=0.9',
        }, 0)
        h.process()
        r = h.generate_response()
        print(r)
        assert r['err_lvl'] == PECode.BAD_URL


def connection_available(hostname):
    """
    Test whether we can make a connection to a given hostname.
    :param hostname: the host to which we want to be able to connect
    :return: boolean
    """
    import socket
    try:
        # see if we can resolve the host name -- tells us if there is
        # a DNS listening
        host = socket.gethostbyname(hostname)
        # connect to the host -- tells us if the host is actually
        # reachable
        s = socket.create_connection((host, 80), 2)
        s.close()
        return True
    except:
        pass
    return False

def pdf_server_available():
    from pfsc import make_app
    from config import ConfigName
    app = make_app(ConfigName.LOCALDEV)
    PDF_TEST_HOSTNAME = app.config.get("PDF_TEST_HOSTNAME")
    if not PDF_TEST_HOSTNAME:
        return False
    return connection_available(PDF_TEST_HOSTNAME)

@pytest.mark.skipif(not pdf_server_available(), reason='no pdf server')
@pytest.mark.req_csrf(False)
def test_proxy_11(app):
    """
    Try downloading PDF that will not be found (404).
    """
    print()
    with app.app_context():
        for c in range(2):
            app.config["PFSC_ENABLE_PDF_PROXY"] = c
            h = ProxyPdfHandler({
                'url': app.config["PDF_TEST_MISSING"],
                'UserAgent': 'Mozilla/5.0',
                'AcceptLanguage': 'en-US,en;q=0.9',
            }, 0)
            h.process()
            r = h.generate_response()
            print(r)
            if c:
                assert r['err_lvl'] == PECode.DOWNLOAD_FAILED
            else:
                assert r['err_lvl'] == PECode.PDF_PROXY_SERVICE_DISABLED

@pytest.mark.skipif(not pdf_server_available(), reason='no pdf server')
@pytest.mark.req_csrf(False)
def test_proxy_20(app):
    """
    Try a successful download.
    """
    print()
    with app.app_context():
        for c in range(2):
            app.config["PFSC_ENABLE_PDF_PROXY"] = c
            h = ProxyPdfHandler({
                'url': app.config["PDF_TEST_PRESENT"],
                'UserAgent': 'Mozilla/5.0',
                'AcceptLanguage': 'en-US,en;q=0.9',
            }, 0)
            h.process()
            r = h.generate_response()
            print(r)
            uuid = app.config["PDF_TEST_PRESENT_UUID3"]
            if c:
                assert r['uuid'] == uuid
            else:
                # This time the outcome depends on whether the PDF was already
                # in the local library. Could maybe improve this unit test by
                # programmatically deleting the PDF before beginning....
                assert r.get('uuid') == uuid or r.get('err_lvl') == PECode.PDF_PROXY_SERVICE_DISABLED

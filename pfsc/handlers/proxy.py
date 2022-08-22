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

import os
import re
import urllib.parse as urlparse
import uuid as uuidlib

from flask import current_app
import requests

import pfsc.constants
from pfsc import check_config
from pfsc.handlers import SocketHandler
from pfsc.checkinput import IType
from pfsc.excep import PfscExcep, PECode


def make_pdf_file_path(uuid):
    """
    Given the UUID for a PDF file, construct its absolute filesystem path.
    :param uuid: the UUID for the PDF
    :return: The absolute filesystem path for this file (whether or not the file exists).
    """
    lib_dir = current_app.config["PFSC_PDFLIB_ROOT"]
    cache_subdir = current_app.config["PFSC_PDFLIB_CACHE_SUBDIR"]
    filename = uuid + '.pdf'
    return os.path.join(lib_dir, cache_subdir, filename)

def make_pdf_local_url(uuid):
    """
    Given the UUID for a PDF file, construct its local URL, i.e. the URL that
    points into the configured PDFLibrary.
    :param uuid: the UUID for the PDF
    :return: The local URL.
    """
    cache_subdir = current_app.config["PFSC_PDFLIB_CACHE_SUBDIR"]
    app_url_prefix = current_app.config["APP_URL_PREFIX"]
    local_url = f'{app_url_prefix}/static/PDFLibrary/{cache_subdir}/{uuid}.pdf'
    return local_url

KNOWN_PDF_ACCESS_PATTERNS = [
]

def compute_access_url(pdf_url):
    """
    Given the URL of a PDF, attempt to determine, based on recognized hosts,
    the URL of a page from which this PDF can be accessed.
    :param pdf_url: the URL of the PDF
    :return: the access URL if it could be determiend; else None
    """
    access_url = None
    for P, U in KNOWN_PDF_ACCESS_PATTERNS:
        M = P.match(pdf_url)
        if M:
            access_url = U % M.groupdict()
            break
    return access_url

class ProxyPdfHandler(SocketHandler):
    """
    Make a PDF from anywhere on the web locally available.
    """

    def check_enabled(self):
        if not bool(check_config("PFSC_ENABLE_PDF_PROXY")):
            raise PfscExcep('PDF proxy service disabled', PECode.PDF_PROXY_SERVICE_DISABLED)

    def pad_url(self):
        """
        Eventually we may want to do something more sophisticated (if,
        say, we have some known source domains where the PDF URLs actually
        do not end in `.pdf`), but for now we force all URLs to end in
        `.pdf`.

        This is mainly intended to catch a common error case: If you right-click
        and copy the URL from the "PDF" link on an arXiv abstract page, the URL
        you get is missing the `.pdf` at the end.
        """
        if 'url' in self.request_info:
            raw_url = self.request_info['url']
            if raw_url[-4:] != '.pdf':
                amended_url = raw_url + '.pdf'
                self.request_info['url'] = amended_url

    def check_input(self):
        self.pad_url()
        self.check({
            "REQ": {
                'url': {
                    'type': IType.URL
                },
                'UserAgent': {
                    'type': IType.STR
                },
                'AcceptLanguage': {
                    'type': IType.STR
                },
            }
        })

    def check_permissions(self):
        pass

    def confirm(self, url, UserAgent, AcceptLanguage):
        """
        Check the URL:
            * Must use either http or https scheme (so e.g. no FTP)
            * Path must end with `.pdf`
            * We do not allow a query (?...) or fragment (#...)
            * If approved netlocs are configured, then the location
              i.e. (domain + port) must be matched by the approvals regex.
            * If banned netlocs are configured, then the location
              i.e. (domain + port) must not match the bans regex.
        """
        sr = url.splitResult
        assert isinstance(sr, urlparse.SplitResult)

        # Legal scheme
        if sr.scheme not in ['http', 'https']:
            msg = 'Proxy service does not allow URL scheme: ' + sr.scheme
            raise PfscExcep(msg, PECode.BAD_URL)

        # Path ends in '.pdf'
        if sr.path[-4:] != '.pdf':
            msg = 'Proxy service: PDF URL should end in ".pdf": ' + sr.path
            raise PfscExcep(msg, PECode.BAD_URL)

        # No query or fragment part
        if len(sr.query) > 0 or len(sr.fragment) > 0:
            msg = 'Proxy service: PDF URL should have no query or fragment part'
            raise PfscExcep(msg, PECode.BAD_URL)

        # Netloc approvals?
        approval_pattern = check_config("PFSC_PDF_NETLOC_APPROVED")
        if approval_pattern and not re.match(approval_pattern, sr.netloc):
            msg = 'Proxy service does not allow PDF domain: ' + sr.netloc
            raise PfscExcep(msg, PECode.BAD_URL)

        # Netloc bans?
        ban_pattern = check_config("PFSC_PDF_NETLOC_BANNED")
        if ban_pattern and re.match(ban_pattern, sr.netloc):
            msg = 'Proxy service does not allow PDF domain: ' + sr.netloc
            raise PfscExcep(msg, PECode.BAD_URL)

    def download(self, headers, url, filepath):
        """
        Download a URL to a file path, emitting progress updates.
        """
        self.check_enabled()  # (double check)
        response = requests.get(url, headers=headers, stream=True)
        self.set_response_field('sent_headers', {**response.request.headers})
        if response.status_code != 200:
            msg = f'Error downloading {url}: {response.status_code} {response.reason}'
            raise PfscExcep(msg, PECode.DOWNLOAD_FAILED)
        total_length = response.headers.get('content-length')
        with open(filepath, "wb") as f:
            #print("Downloading %s --> %s" % (url, filepath))
            if total_length is None:  # no content length header
                f.write(response.content)
            else:
                dl = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=4096):
                    dl += len(data)
                    f.write(data)
                    self.update(dl, total_length, 'Downloading...')

    def update(self, cur_count, max_count=None, message=''):
        self.emit("progress", {
            'job': self.job_id,
            'action': 'Downloading...',
            'fraction_complete': cur_count / (max_count or 100.0),
            'message': message
        })

    def go_ahead(self, url, UserAgent, AcceptLanguage):
        sr = url.splitResult
        assert isinstance(sr, urlparse.SplitResult)

        # We do not include the scheme in the URL to be hashed, i.e. on which
        # the UUID is to be based. This is because we do not want to download
        # duplicate PDFs just because the scheme was changed from http to https
        # or vice versa.
        hashed_url = sr.netloc + sr.path

        # Make UUID and filepath for the PDF
        uuid = str(uuidlib.uuid3(uuidlib.NAMESPACE_URL, hashed_url))
        filepath = make_pdf_file_path(uuid)

        self.set_response_field('orig_url', url.given)
        self.set_response_field('hashed_url', hashed_url)
        self.set_response_field('uuid', uuid)

        # Build the URL we will actually request if we download. It's possible this may differ
        # slightly from the original (see <https://docs.python.org/3.6/library/urllib.parse.html#urllib.parse.urlunsplit>).
        pdf_url = urlparse.urlunsplit(sr)
        # Try to compute the "access URL", which should be the address of a web page
        # from which the PDF can be accessed manually.
        access_url = compute_access_url(pdf_url)
        self.set_response_field('pdf_url', pdf_url)
        self.set_response_field('access_url', access_url)

        # Since we use the uuid3 algorithm, which is deterministic, we will always
        # get the same UUID for a given URL. So we can check whether we already have
        # this one, in which case we can skip the download.
        must_download = not os.path.exists(filepath)

        if must_download:
            # Make sure the directory exists.
            dirpath = os.path.dirname(filepath)
            os.makedirs(dirpath, exist_ok=True)
            # Download the PDF
            headers = {
                'Host': sr.netloc,
                'User-Agent': UserAgent,
                'Accept-Language': AcceptLanguage,
                'Accept-Encoding': 'gzip, deflate',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
            }
            self.download(headers, pdf_url, filepath)
            self.emit_progress_complete()

        local_url = make_pdf_local_url(uuid)
        self.set_response_field('download', must_download)
        self.set_response_field('local_url', local_url)

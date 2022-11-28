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

import json

import pytest

from pfsc.build.repo import get_repo_info
from pfsc.lang.modules import PathInfo
from pfsc.handlers.write import WriteHandler


@pytest.mark.psm
@pytest.mark.req_csrf(False)
def test_write_1(app):
    with app.app_context():
        # Reset repo to v0.
        ri = get_repo_info('test.foo.bar')
        ri.checkout('v0')
        # Read the text of a module.
        modpath = 'test.foo.bar.results'
        pi = PathInfo(modpath)
        text = pi.read_module()
        # Alter the text and write it to disk, using the WriteHandler.
        text2 = text[:46] + 'really ' + text[46:]
        #print(text2)
        args = {
            'writepaths': [modpath],
            'writetexts': [text2]
        }
        wh = WriteHandler({'info': json.dumps(args)}, 0)
        wh.process()
        resp = wh.generate_response()
        #print(resp)
        #return
        # Read again, from disk.
        text2b = pi.read_module()
        # Assert that what was found on disk this time is equal to
        # the new text. (I.e. we successfully wrote.)
        assert text2b == text2
        # Clean up.
        ri.clean()

@pytest.mark.psm
@pytest.mark.req_csrf(False)
def test_autowrite_1(app):
    with app.app_context():
        # Reset repo to v0.
        ri = get_repo_info('test.foo.bar')
        ri.checkout('v0')
        wpath = 'test.foo.bar.expansions.Notes1.w10'
        args = {
            'autowrites': [{
                'type': 'widget_data',
                'widgetpath': wpath,
                'data': {
                    wpath: {
                        'view': 'Pf.S'
                    }
                }
            }]
        }
        wh = WriteHandler({'info': json.dumps(args)}, 0)
        wh.process()
        resp = wh.generate_response()
        print()
        print(json.dumps(resp, indent=4))
        #print(resp.get('err_msg'))
        #return
        modpath = 'test.foo.bar.expansions'
        pi = PathInfo(modpath)
        text = pi.read_module()
        #print(text)
        #return
        i0 = text.find('"view": "Pf.S"')
        #print('i0=', i0)
        assert i0 == 355
        # Clean up.
        ri.clean()

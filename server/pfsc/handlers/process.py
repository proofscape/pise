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

from pfsc.handlers import SocketHandler
from pfsc.checkinput import IType
from pfsc.lang.freestrings import render_markdown
from pfsc.constants import MAX_NOTES_MARKDOWN_LENGTH

class MarkdownHandler(SocketHandler):
    """
    Format some markdown and return HTML.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'md': {
                    'type': IType.STR,
                    'max_len': MAX_NOTES_MARKDOWN_LENGTH,
                }
            }
        })

    def check_permissions(self):
        pass

    def go_ahead(self, md):
        # TODO: thorough review to decide if we can consider this markdown trusted.
        #  Any possibility of reflected XSS attack?
        #  For now we mark it as untrusted.
        html = render_markdown(md, trusted=False)
        self.set_response_field('html', html)

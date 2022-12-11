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


class SimpleGraph:

    def __init__(self, nodes, relns, index_info=None):
        self.nodes = nodes
        self.relns = relns
        self.index_info = index_info

    def __str__(self):
        d = {
            'nodes': list(map(str, self.nodes)),
            'relns': list(map(str, self.relns)),
        }
        s = f'{len(self.nodes)} Nodes, {len(self.relns)} Relns.'
        s += '\n' + json.dumps(d, indent=4)
        return s

    def write_index_info(self):
        return json.dumps(self.index_info, indent=4) if self.index_info else str(None)

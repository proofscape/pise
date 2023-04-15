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

from pfsc.lang.objects import Enrichment


class Comparison:
    """
    This is our internal representation for a comparison recorded in a node's
    `cf` field.

    For now, we are only accepting very simple raw values: they must be a
    libpath, which resolves to some object that is available in the module,
    i.e. that was imported or defined there.

    In the future, we may consider broadening the set of accepted values:
    * We could accept string libpaths, which needn't resolve. This could
      help with cyclic import issues.
    * We could accept dictionaries, so that besides just a libpath, other info
      could also be supplied, such as a comment, or some categorization tags.
    """

    def __init__(self, node, raw):
        """
        :param node: the Node that is being compared to something.
        :param raw: a single element from the list that makes the right-hand
            side of the `cf=` assignment in the node.
        """
        module = node.getModule()
        targets, _ = Enrichment.find_targets(
            [raw], module, typename='node', name=node.name
        )
        self.source = node
        self.target = targets[0]

    @property
    def target_libpath(self):
        return self.target.getLibpath()

    @property
    def target_version(self):
        return self.target.getVersion()

    @property
    def target_index_type(self):
        return self.target.get_index_type()

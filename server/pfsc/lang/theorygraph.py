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

class TheoryNode:

    def __init__(self, label):
        """
        :param label: string
        """
        self.label = label

class TheoryEdge:

    def __init__(self, src, tgt):
        """
        :param src: a TheoryNode
        :param tgt: a TheoryNode
        """
        self.src = src
        self.tgt = tgt

class TheoryGraph:

    def __init__(self, nodes, edges):
        """
        :param nodes: list of Nodes
        :param edges: list of Edges
        """
        self.nodes = nodes
        self.edges = edges

    def write_modtext(self, name):
        """
        Write module text that can be used to build a dashgraph to represent
        this theory graph.

        :param name: the desired name of the deduction we write.
        :return: the module text (string).
        """
        text = ''
        label2idx = {}
        for i, node in enumerate(self.nodes):
            parts = node.label.split('.')
            modpath = '.'.join(parts[:-1])
            deducname = parts[-1]
            text += f'from {modpath} import {deducname} as d{i}\n'
            label2idx[node.label] = i
        text += f"deduc {name} {{\n"
        if len(self.edges) > 0:
            text += 'arcs="\n'
            for edge in self.edges:
                text += f'd{label2idx[edge.src.label]} --> d{label2idx[edge.tgt.label]}\n'
            text += '"\n'
        else:
            text += 'meson="\n'
            for node in self.nodes:
                text += f' d{label2idx[node.label]}'
            text += '\n"\n'
        text += "}\n"
        return text

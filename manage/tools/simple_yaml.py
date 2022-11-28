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

import re

def dumps(obj, indent=0, current_indent='', top_level=True):
    """
    Dump an object to a yaml string.
    :param obj: The object to be dumped. Should be composed entirely of dicts,
      lists, strings, ints, and floats.
    :param indent: desired number of spaces for indentation
    :param current_indent: (internal use only)
    :param top_level: (internal use only)
    :return: yaml string
    :raises: Exception if the object contains anything of a type we do not know
      how to write as yaml.
    """
    if isinstance(obj, str):
        if re.match(r'^[a-zA-Z]\w*$', obj):
            return obj
        esc = obj.replace('"', r'\"')
        return f'"{esc}"'
    elif isinstance(obj, (int, float)):
        return str(obj)
    elif isinstance(obj, list):
        new_indent = current_indent if top_level else current_indent + ' '*indent
        y = '' if top_level else '\n'
        for elt in obj:
            y += f'{new_indent}- {dumps(elt, indent=indent, current_indent=new_indent, top_level=False)}\n'
        return y[:-1]
    elif isinstance(obj, dict):
        new_indent = current_indent if top_level else current_indent + ' ' * indent
        y = '' if top_level else '\n'
        for k, v in obj.items():
            y += f'{new_indent}{k}: {dumps(v, indent=indent, current_indent=new_indent, top_level=False)}\n'
        return y[:-1]
    else:
        raise Exception(f'YAML writer cannot process object: {obj}')

test_input_01 = {
    'version': '3',
    'services': {
        'redis': {
            'image': 'redis:6.2.1',
        },
        'neo4j': {
            'image': 'neo4j:4.0.6',
            'depends_on': [
                'redis',
            ],
            'ports': [
                '7474:7474',
                '7687:7687',
            ],
            'volumes': [
                '/home/foo/graphdb/data:/data',
                '/home/foo/graphdb/logs:/logs',
            ],
            'environment': {
                'NEO4J_AUTH': 'none',
                'FOO': '"bar"',
            }
        }
    },
    'foo': 42,
    'bar': 3.14,
}

expected_output_01 = """\
version: "3"
services: 
  redis: 
    image: "redis:6.2.1"
  neo4j: 
    image: "neo4j:4.0.6"
    depends_on: 
      - redis
    ports: 
      - "7474:7474"
      - "7687:7687"
    volumes: 
      - "/home/foo/graphdb/data:/data"
      - "/home/foo/graphdb/logs:/logs"
    environment: 
      NEO4J_AUTH: none
      FOO: "\\"bar\\""
foo: 42
bar: 3.14\
"""

def test01():
    y = dumps(test_input_01, indent=2)
    print(y)
    assert y == expected_output_01

if __name__ == "__main__":
    test01()

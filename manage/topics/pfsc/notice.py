# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2024 Proofscape Contributors                           #
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

PISE_notice = """\
Proofscape Integrated Study Environment (PISE)
Copyright (c) 2011-2023 Proofscape Contributors
"""

moose_notice = """\
Proofscape Moose
Copyright (c) 2011-2023 Proofscape Contributors
"""

displaylang_notice = """\
DisplayLang
Copyright (c) 2020-2022 DisplayLang contributors
"""

tinkerpop_notice = """\
Apache TinkerPop
Copyright 2015-2021 The Apache Software Foundation.

This product includes software developed at
The Apache Software Foundation (http://www.apache.org/).
"""

neo4j_notice = """\
Neo4j
Copyright (c) Neo4j Sweden AB (referred to in this notice as "Neo4j") [http://neo4j.com]

This product includes software ("Software") developed by Neo4j
"""

requests_notice = """\
Requests
Copyright 2019 Kenneth Reitz
"""

RSAL_notice = """\
This software is subject to the terms of the Redis Source Available License Agreement.
"""

notices = [
    {
        'name': 'PISE',
        'usage': ['oca', 'server', 'frontend'],
        'text': PISE_notice,
    },
    {
        'name': 'moose',
        'usage': ['oca', 'frontend'],
        'text': moose_notice,
    },
    {
        'name': 'displaylang',
        'usage': ['oca', 'frontend'],
        'text': displaylang_notice,
    },
    {
        'name': 'tinkerpop',
        'usage': ['oca', 'server'],
        'text': tinkerpop_notice,
    },
    {
        'name': 'neo4j',
        'usage': ['oca', 'server'],
        'text': neo4j_notice,
    },
    {
        'name': 'requests',
        'usage': ['oca', 'server'],
        'text': requests_notice,
    },
    {
        'name': 'RSAL',
        'usage': ['oca'],
        'text': RSAL_notice,
    },
]

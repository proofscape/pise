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

# Until Apache Tinkerpop 3.5.2 is released, we need to copy the latest
# `gremlin-server.yaml` so that the max content length is set to 10MB (not 64KB).
FROM tinkerpop/gremlin-server:3.5.1
COPY pfsc-server/venv/src/gremlinpython/gremlin-server/conf/gremlin-server.yaml \
        /opt/gremlin-server/conf

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

import os
import jinja2

import conf as pfsc_conf

this_dir = os.path.dirname(__file__)
templates_dir = os.path.join(this_dir, 'templates')
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))


def write_redisgraph_ini(use_conf_file=True):
    template = jinja_env.get_template('redisgraph.ini')
    return template.render(
        use_conf_file=use_conf_file,
    )


REDIS_DOCKERFILE_TPLT = jinja2.Template("""\
FROM redis:{{redis_image_tag}}
COPY {{tmp_dir_name}}/redis.conf /usr/local/etc/redis/redis.conf
CMD [ "redis-server", "/usr/local/etc/redis/redis.conf" ]
""")

REDISGRAPH_DOCKERFILE_TPLT = jinja2.Template("""\
FROM redislabs/redisgraph:{{redisgraph_image_tag}}
COPY {{tmp_dir_name}}/redisgraph.conf /usr/local/etc/redis/redisgraph.conf
CMD [ "redis-server", "/usr/local/etc/redis/redisgraph.conf", "--loadmodule", "/usr/lib/redis/modules/redisgraph.so" ]
""")

def write_pfsc_redis_dockerfile(tmp_dir_name):
    return REDIS_DOCKERFILE_TPLT.render(
        redis_image_tag=pfsc_conf.REDIS_IMAGE_TAG,
        tmp_dir_name=tmp_dir_name,
    )

def write_pfsc_redisgraph_dockerfile(tmp_dir_name):
    return REDISGRAPH_DOCKERFILE_TPLT.render(
        redisgraph_image_tag=pfsc_conf.REDISGRAPH_IMAGE_TAG,
        tmp_dir_name=tmp_dir_name,
    )

##############################################################################

def write_redis_conf():
    """
    Since Redis is going to be running inside a Docker container, it needs
    to accept connections from other hosts besides localhost. Therefore we
    set the bind address to 0.0.0.0.

    As for the TCP backlog, the default value of 511 results in a complaint
    in the logs when Redis starts up. We reduce it to the recommended value of 128.

    The save rules are just the default ones.
    """
    template = jinja_env.get_template('redis.conf')
    return template.render(
        ipv4_bind_addr='0.0.0.0',
        tcp_backlog=128,
        save_rules=[
            [900, 1],
            [300, 10],
            [60, 10000],
        ]
    )

def write_redisgraph_conf():
    """
    We use the same settings as for Redis, except that we save once a minute,
    if anything at all has changed.
    """
    template = jinja_env.get_template('redis.conf')
    return template.render(
        ipv4_bind_addr='0.0.0.0',
        tcp_backlog=128,
        save_rules=[
            [60, 1],
        ]
    )

##############################################################################
"""
Before we used Jinja, we used `patch` to apply diffs to an unaltered default
redis.conf. In Python it would be sth like this:

    subprocess.run(
        ['patch', '-o', tmp_redis_conf_path, default_conf_path],
        input=diff_text, text=True
    )

The diffs were as follows. We keep them here in case we want to
use this method again.
"""

REDIS_CONF_DIFF = """\
69c69
< bind 127.0.0.1
---
> bind 0.0.0.0
101c101
< tcp-backlog 511
---
> tcp-backlog 128
"""


REDISGRAPH_CONF_DIFF = """\
69c69
< bind 127.0.0.1
---
> bind 0.0.0.0
101c101
< tcp-backlog 511
---
> tcp-backlog 128
317,319c317
< save 900 1
< save 300 10
< save 60 10000
---
> save 60 1
"""

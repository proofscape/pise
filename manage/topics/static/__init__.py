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

from tools.util import check_app_url_prefix
import conf

this_dir = os.path.dirname(__file__)
templates_dir = os.path.join(this_dir, 'templates')
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))

def write_static_nginx_dockerfile(tmp_dir_name):
    template = jinja_env.get_template('Dockerfile')
    return template.render(
        nginx_image_tag=conf.NGINX_IMAGE_TAG,
        tmp_dir_name=tmp_dir_name,
    )

def write_nginx_conf():
    root_url, app_url_prefix = check_app_url_prefix()
    template = jinja_env.get_template('nginx.conf')
    return template.render(app_url_prefix=app_url_prefix)

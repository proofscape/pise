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

FROM python:{{python_image_tag}}
ARG DEBIAN_FRONTEND=noninteractive
# The rm command in /tmp is to clean up a cert file that is left there for some
# reason; see <https://github.com/docker-library/python/issues/609>
RUN rm /tmp/*

RUN adduser --disabled-password --gecos "" pfsc \
 && sed -i -e "s/#alias ll=/alias ll=/" /home/pfsc/.bashrc \
 && sed -i -e "s%# \(export\|eval\|alias l\)%\1%" /root/.bashrc \
 && bash -c "mkdir -p /proofscape/{lib,build,graphdb/re,deploy,PDFLibrary}"

RUN chown -R pfsc:pfsc /proofscape/ \
 && mkdir /home/pfsc/proofscape

WORKDIR /home/pfsc/proofscape
RUN ln -s /proofscape/lib \
 && ln -s /proofscape/build \
 && ln -s /proofscape/graphdb \
 && ln -s /proofscape/deploy \
 && ln -s /proofscape/PDFLibrary \
 && mkdir -p src/pfsc-server

WORKDIR /home/pfsc/proofscape/src/pfsc-server

RUN pip install Flask==2.1.2 python-dotenv==0.17.0 \
 && find / -name "*.pyc" | xargs -I % rm %

COPY {{tmp_dir_name}}/web.py ./

RUN chown -R pfsc:pfsc /home/pfsc
EXPOSE 7372

WORKDIR /home/pfsc/proofscape/src/pfsc-server
COPY pfsc-server/startup.sh ./
RUN chmod +x startup.sh

USER pfsc

# For continuous logging from the Flask web app:
ENV PYTHONUNBUFFERED 1
ENV PFSC_RUN_AS_WEB_SERVER 1
ENTRYPOINT ["./startup.sh"]

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

import json

from flask_login import current_user

import pfsc.constants
from pfsc.handlers import Handler
from pfsc.checkinput import CheckedLibpath, IType
import pfsc.build.products as products
from pfsc.build.lib.libpath import get_modpath, libpath_is_trusted
from pfsc.build.repo import get_repo_part
from pfsc.gdb import get_graph_reader
from pfsc.gdb.user import should_load_user_notes_from_gdb
from pfsc.handlers.study import StudyPageBuilder


def inject_enrichment_and_notes_in_dashgraph(enrichment, user_notes, node):
    """
    Recursive function to walk a dashgraph and inject info on available
    enrichments, and user notes.

    The info will be stored under the keys 'enrichment' and 'user_notes", and
    on a per-node basis, i.e. each node gets its own info.

    Important: even nodes that do not have any available enrichment will get
    these fields, pointing to empty dicts.

    :param enrichment: dict of the form {
            targetpath_1: {
                'Deduc': [info, ..., info],
                'Anno':  [info, ..., info],
            },
            ...
            targetpath_m: {
                'Deduc': [info, ..., info],
                'Anno':  [info, ..., info],
            }
        } as returned by `GraphReader.get_enrichment()`
    :param user_notes: dict of the form {
            origin_1: {
                'state': str,
                'notes': str,
            },
            ...
            origin_n: {
                'state': str,
                'notes': str,
            },
        }
    :param node: a node in a dashgraph. This includes the top-level one, i.e. you can just pass a whole
                 dashgraph for this argument. In fact, that's probably the only way you'll use this
                 function. The argument gets a more generic name ("node") because this function is going
                 to call itself recursively.
    :return: nothing. The passed node (dashgraph) is modified in-place.
    """
    libpath = node.get('libpath')
    if libpath:
        node['enrichment'] = enrichment.get(libpath, {})
    origin = node.get('origin')
    if origin:
        node['user_notes'] = user_notes.get(origin, {})
    children = node.get('children')
    if children:
        for child in children.values():
            inject_enrichment_and_notes_in_dashgraph(enrichment, user_notes, child)


def inject_info_in_widget_data(data, trusted, approvals, user_notes):
    """
    Similar to the `inject_enrichment_and_notes_in_dashgraph()` function, only
    this time we inject info into widget data.
    """
    widgets = data['widgets']
    for wd in widgets.values():
        wd['trusted'] = trusted

        if wd['widget_libpath'] in approvals:
            wd['approved'] = True

        if wd["type"] == "GOAL":
            origin = wd.get('origin')
            wd['user_notes'] = user_notes.get(origin, {})


class DashgraphLoader(Handler):
    """
    Load a dashgraph, injecting available enrichment info in the process.
    """

    def check_input(self):
        """
        libpath: the libpath of the deduction whose dashgraph you want to load.
        vers: the desired version of the deduction.
        cache_code: If you know that loads are likely to come in bursts, you can
          pass a fixed value here for each load in a burst. Then the first load
          will be a cache miss, but the others will be hits.
        """
        self.check({
            "REQ": {
                'libpath': {
                    'type': IType.LIBPATH,
                },
                'vers': {
                    'type': IType.FULL_VERS,
                },
            },
            "OPT": {
                'cache_code': {
                    'type': IType.STR,
                    'default_cooked': None,
                }
            }
        })

    def check_permissions(self, libpath, vers):
        if vers.isWIP:
            self.check_repo_read_permission(libpath, vers, action='load work in progress from')

    def confirm(self, libpath):
        assert isinstance(libpath, CheckedLibpath)
        assert libpath.length_in_bounds
        assert libpath.valid_format

    def go_ahead(self, libpath, vers, cache_code):
        h0 = products.load_dashgraph_with_cache.cache_info().hits
        dgj = products.load_dashgraph(libpath.value, cache_code, version=vers.full)
        h1 = products.load_dashgraph_with_cache.cache_info().hits
        dg = json.loads(dgj)

        gr = get_graph_reader()
        enrichment = gr.get_enrichment(
            libpath.value, vers.major, filter_by_repo_permission=True)
        user_notes = {}
        if should_load_user_notes_from_gdb():
            un_list = gr.load_user_notes_on_deduc(
                current_user.username, libpath.value, vers.major)
            for un in un_list:
                user_notes[un.write_origin()] = un.write_dict()
        inject_enrichment_and_notes_in_dashgraph(enrichment, user_notes, dg)

        self.set_response_field('dashgraph', dg)
        self.set_response_field('definite_cache_miss', h1 == h0)


class GeneralizedAnnotationLoader(Handler):
    """
    Load both ordinary and special types of annotations.
    """

    def check_input(self):
        self.check({
            "OPT": {
                'special': {
                    'type': IType.STR,
                    'default_cooked': ''
                }
            }
        })

    def check_permissions(self):
        # We'll be using either a StudyPageBuilder or an AnnotationLoader
        # to process the request. We let them decide about permissions.
        pass

    def go_ahead(self, special):
        handlerClass = {
            'studypage': StudyPageBuilder
        }.get(special, AnnotationLoader)
        handler = handlerClass(self.request_info)
        handler.process(raise_anticipated=True)
        self.adopt_response(handler)


class AnnotationLoader(Handler):
    """
    Load an annotation.
    """

    def check_input(self):
        """
        libpath: the libpath of the annotation whose html/json you want to load.
        cache_code: If you know that loads are likely to come in bursts, you can
          pass a fixed value here for each load in a burst. Then the first load
          will be a cache miss, but the others will be hits.
        """
        self.check({
            "REQ": {
                'libpath': {
                    'type': IType.LIBPATH,
                },
                'vers': {
                    'type': IType.FULL_VERS,
                },
            },
            "OPT": {
                'cache_code': {
                    'type': IType.STR,
                    'default_cooked': None,
                }
            }
        })

    def check_permissions(self, libpath, vers):
        if vers.isWIP:
            self.check_repo_read_permission(libpath, vers, action='load work in progress from')

    def confirm(self, libpath):
        assert isinstance(libpath, CheckedLibpath)
        assert libpath.length_in_bounds
        assert libpath.valid_format

    def go_ahead(self, libpath, vers, cache_code):
        annopath = libpath.value

        h0 = products.load_annotation_with_cache.cache_info().hits
        html, data_json = products.load_annotation(annopath, cache_code, version=vers.full)
        h1 = products.load_annotation_with_cache.cache_info().hits

        # Load and inject extra info
        anno_trusted = libpath_is_trusted(annopath)

        approvals = set()
        if not anno_trusted:
            gr = get_graph_reader()
            approvals = set(gr.check_approvals_under_anno(annopath, vers.full))

        user_notes = {}
        if should_load_user_notes_from_gdb():
            gr = get_graph_reader()
            un_list = gr.load_user_notes_on_anno(
                current_user.username, annopath, vers.major)
            for un in un_list:
                user_notes[un.write_origin()] = un.write_dict()

        data = json.loads(data_json)
        inject_info_in_widget_data(data, anno_trusted, approvals, user_notes)
        data_json = json.dumps(data)

        self.set_response_field('html', html)
        self.set_response_field('data_json', data_json)
        self.set_response_field('definite_cache_miss', h1 == h0)


class SourceLoader(Handler):
    """
    Load the source code of one or more proofscape modules.

    Desired libpaths are passed as a comma-delimited list, under the field `libpaths`.

    Each of the given libpaths may point either to a module itself, or to anything
    defined within that module.

    Under the field `versions` you must pass the corresponding list of desired full
    version numbers.

    In all cases the response will include a `source` field whose value is a dictionary
    in which module paths point to source text. Note that these will always be module
    paths, even if libpaths pointing within modules were given.

    If precisely one libpath was requested, then the response will also include a `modpath`
    field giving the modpath that was obtained, and a `text` field, giving the text of
    that module.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'libpaths': {
                    'type': IType.CDLIST,
                    'itemtype': {
                        'type': IType.LIBPATH
                    }
                },
                'versions': {
                    'type': IType.CDLIST,
                    'itemtype': {
                        'type': IType.FULL_VERS,
                    }
                },
            },
            "OPT": {
                'cache_code': {
                    'type': IType.STR,
                    'default_cooked': None,
                }
            }
        })

    def check_permissions(self, libpaths, versions):
        repos = set([
            get_repo_part(lp.value)
            for lp, v in zip(libpaths, versions)
            if v.isWIP
        ])
        for rp in repos:
            self.check_repo_read_permission(rp, pfsc.constants.WIP_TAG,
                                            action='load work in progress from')

    def go_ahead(self, libpaths, versions, cache_code):
        source_lookup = {}
        for libpath, vers in zip(libpaths, versions):
            modpath = get_modpath(libpath.value, version=vers.major)
            text = products.load_source(modpath, cache_control_code=cache_code, version=vers.full)
            source_lookup[modpath] = text
        self.set_response_field('source', source_lookup)
        if len(source_lookup) == 1:
            for modpath in source_lookup:
                text = source_lookup[modpath]
            self.set_response_field('modpath', modpath)
            self.set_response_field('text', text)


class EnrichmentLoader(Handler):
    """
    Load the enrichment available for a given libpath.

    In theory the given libpath could point to anything in the library, and we would then
    retrieve a lookup of enrichment available for any node whose libpath started with the given one.

    However this runs the risk of retrieving too large a response, if too short a libpath were given.

    Therefore the expectation is that you pass the libpath of a _deduction_, and we retrieve the
    enrichment info for all nodes therein, and for the deduction itself.

    In fact, all we will check is that the given libpath be longer than the longest modpath contained
    within it. In other words, it must point to a top-level content declaration within a module, or else
    to something contained within such.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'libpath': {
                    'type': IType.LIBPATH,
                    'formally_within_module': True
                },
                # We call it "vers" to be nice for the client side;
                # but since we only need a major version, we use the
                # more tolerant IType.
                'vers': {
                    'type': IType.MAJ_VERS,
                },
            }
        })

    def check_permissions(self, libpath, vers):
        if vers == pfsc.constants.WIP_TAG:
            self.check_repo_read_permission(libpath, vers, action='load work in progress from')

    def confirm(self, libpath):
        assert isinstance(libpath, CheckedLibpath)
        assert libpath.length_in_bounds
        assert libpath.valid_format
        assert libpath.formally_within_module

    def go_ahead(self, libpath, vers):
        enrichment = get_graph_reader().get_enrichment(
            libpath.value, vers, filter_by_repo_permission=True)
        self.set_response_field('enrichment', enrichment)


class ModpathFinder(Handler):
    """
    Find the modpath for a given libpath, at a given major version.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'libpath': {
                    'type': IType.LIBPATH
                },
                # We call it "vers" to be nice for the client side;
                # but since we only need a major version, we use the
                # more tolerant IType.
                'vers': {
                    'type': IType.MAJ_VERS,
                },
            }
        })

    def check_permissions(self, libpath, vers):
        # Just determining the modpath for a libpath is arguably no great
        # intrusion into a repo you do not own, but still it would go against
        # our general policy. If you don't own a repo, you can't acess anything
        # about it at its WIP version.
        if vers == pfsc.constants.WIP_TAG:
            self.check_repo_read_permission(libpath, vers, action='access work in progress from')

    def confirm(self, libpath):
        assert isinstance(libpath, CheckedLibpath)
        assert libpath.length_in_bounds
        assert libpath.valid_format

    def go_ahead(self, libpath, vers):
        modpath = get_modpath(libpath.value, version=vers)
        self.set_response_field('modpath', modpath)

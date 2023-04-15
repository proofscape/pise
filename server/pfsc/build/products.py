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

"""
Loading/managing built products.
"""

import os
from functools import lru_cache

import pfsc.constants
from pfsc import check_config
from pfsc.excep import PfscExcep, PECode
from pfsc.build.lib.libpath import PathInfo
from pfsc.gdb import building_in_gdb, get_graph_reader


class BuiltObjType:
    DASHGRAPH = 'dashgraph'
    ANNOTATION = 'annotation'


def object_is_built(built_obj_type, libpath, version=pfsc.constants.WIP_TAG):
    use_gdb = building_in_gdb()
    if built_obj_type == BuiltObjType.DASHGRAPH:
        if use_gdb:
            is_built = get_graph_reader().dashgraph_is_built(libpath, version)
        else:
            d, fn = get_dashgraph_dir_and_filename(libpath, version)
            p = os.path.join(d, fn)
            is_built = os.path.exists(p)
        return is_built
    elif built_obj_type == BuiltObjType.ANNOTATION:
        if use_gdb:
            is_built = get_graph_reader().annotation_is_built(libpath, version)
        else:
            d, hf, jf = get_annotation_dir_and_filenames(libpath)
            ph = os.path.join(d, hf)
            pj = os.path.join(d, jf)
            is_built = os.path.exists(ph) and os.path.exists(pj)
        return is_built
    elif built_obj_type is not None:
        # If we intended to specify some built object type, but it is not a known one, then
        # we were probably expecting some check to be performed. So this is a raw exception.
        raise Exception("Unknown built object type: " + built_obj_type)


def get_dashgraph_dir_and_filename(deducpath, version=pfsc.constants.WIP_TAG):
    """
    :param deducpath: The libpath of a deduction.
    :param version: The desired build version.
    :return: Ordered pair (d, f) giving the directory and filename for this
        deduction's dashgraph.
    """
    dp_parts = deducpath.split('.')
    deduc_name = dp_parts[-1]
    build_root = check_config("PFSC_BUILD_ROOT")
    fs_dir_parts = [build_root] + dp_parts[:3] + [version] + dp_parts[3:-1]
    dg_dir = os.path.join(*fs_dir_parts)
    dg_filename = '%s.dg.json' % deduc_name
    return dg_dir, dg_filename


@lru_cache(maxsize=32)
def load_dashgraph_with_cache(libpath, control_code, version=pfsc.constants.WIP_TAG):
    """
    Load the compiled json for a deduction.
    :param libpath: The libpath to the deduction.
    :param control_code: Just here so callers can encourage a cache hit
        (successive callers should pass the same value) or force a cache
        miss (pass a unique value like a Unix timestamp).
    :param version: The desired build version.
    :return: The compiled json (string).

    WARNING: This method just loads the dashgraph itself. Many applications may
    expect the dashgraph to come loaded with up-to-date _enrichments_. For that,
    you should not use this method directly; instead, use the DashgraphLoader
    class from the handlers/load.py module.
    """
    try:
        if building_in_gdb():
            j = get_graph_reader().load_dashgraph(libpath, version)
        else:
            d, fn = get_dashgraph_dir_and_filename(libpath, version=version)
            p = os.path.join(d, fn)
            with open(p) as f:
                j = f.read()
    except FileNotFoundError:
        msg = f'Dashgraph not found for {libpath} at version {version}.'
        raise PfscExcep(msg, PECode.MISSING_DASHGRAPH)
    return j


def load_dashgraph(libpath, cache_control_code=None, version=pfsc.constants.WIP_TAG):
    """
    See the corresponding "...with_cache" function.
    Leave `cache_control_code` as `None` to force read from disk; otherwise
        this is forwarded as the control code.
    """
    if cache_control_code is None:
        return load_dashgraph_with_cache.__wrapped__(libpath, None, version=version)
    else:
        return load_dashgraph_with_cache(libpath, cache_control_code, version=version)


def get_annotation_dir_and_filenames(annopath, version=pfsc.constants.WIP_TAG):
    """
    :param annopath: The libpath of an annotation.
    :param version: The desired build version.
    :return: Ordered triple (d, hf, jf) giving the directory and filenames for this annotation's
             html and json, respectively.
    """
    libpath_parts = annopath.split('.')
    anno_name = libpath_parts[-1]
    build_root = check_config("PFSC_BUILD_ROOT")
    fs_dir_parts = [build_root] + libpath_parts[:3] + [version] + libpath_parts[3:-1]
    dest_dir = os.path.join(*fs_dir_parts)
    html_filename = '%s.anno.html' % anno_name
    json_filename = '%s.anno.json' % anno_name
    return dest_dir, html_filename, json_filename


@lru_cache(maxsize=32)
def load_annotation_with_cache(libpath, control_code, version=pfsc.constants.WIP_TAG):
    """
    Load the compiled data for an annotation.
    :param libpath: The libpath to the annotation.
    :param control_code: Just here so callers can encourage a cache hit
        (successive callers should pass the same value) or force a cache
        miss (pass a unique value like a Unix timestamp).
    :param version: The desired build version.
    :return: Pair of strings (html, json).
    """
    try:
        if building_in_gdb():
            html, j = get_graph_reader().load_annotation(libpath, version)
        else:
            d, hf, jf = get_annotation_dir_and_filenames(libpath, version=version)
            ph = os.path.join(d, hf)
            pj = os.path.join(d, jf)
            with open(ph) as f:
                html = f.read()
            with open(pj) as f:
                j = f.read()
    except FileNotFoundError:
        msg = f'Annotation not found for {libpath} at version {version}.'
        raise PfscExcep(msg, PECode.MISSING_ANNOTATION)
    return html, j


def load_annotation(libpath, cache_control_code=None, version=pfsc.constants.WIP_TAG):
    """
    See the corresponding "...with_cache" function.
    Leave `cache_control_code` as `None` to force read from disk; otherwise
        this is forwarded as the control code.
    """
    if cache_control_code is None:
        return load_annotation_with_cache.__wrapped__(libpath, None, version=version)
    else:
        return load_annotation_with_cache(libpath, cache_control_code, version=version)


def load_source(modpath, cache_control_code=None, version=pfsc.constants.WIP_TAG):
    """
    Load the source code for a module.
    :param modpath: the libpath of the desired module.
    :param cache_control_code: as `None` to force read from disk; otherwise
        this is forwarded as the control code.
    :param version: the desired version of the module.
    :return: the contents of the module (as string)
    """
    pi = PathInfo(modpath)
    try:
        text = pi.read_module(version=version, cache_control_code=cache_control_code)
    except FileNotFoundError:
        msg = f'Could not find source code for module `{modpath}` at version `{version}`.'
        raise PfscExcep(msg, PECode.MODULE_HAS_NO_CONTENTS)
    return text

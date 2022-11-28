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

import os

from pfsc.handlers import RepoTaskHandler
from pfsc.build.lib.libpath import PathInfo
from pfsc.build.repo import get_repo_part, get_repo_info, FilesystemNode
from pfsc.build.demo import make_demo_repo_lead_comment
from pfsc.excep import PfscExcep, PECode
from pfsc.checkinput import CheckedLibpath, CheckedLibseg, IType, EntityType


class NewSubmoduleHandler(RepoTaskHandler):
    """
    Handle the process of adding a new submodule to a content repo.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'parentpath': {
                    'type': IType.LIBPATH,
                    'entity': EntityType.MODULE
                },
                'name': {
                    'type': IType.LIBSEG
                }
            }
        })

    def confirm(self, parentpath, name):
        assert isinstance(parentpath, CheckedLibpath)
        assert isinstance(name, CheckedLibseg)
        assert parentpath.length_in_bounds
        assert parentpath.valid_format
        assert parentpath.is_module
        assert name.length_in_bounds
        assert name.valid_format

    def check_permissions(self, parentpath):
        self.check_repo_write_permission(parentpath, action='edit')

    def compute_implicated_repopaths(self, parentpath):
        self.implicated_repopaths = {get_repo_part(parentpath.value)}

    def go_ahead(self, parentpath, name):
        # In what form does the parent module exist?
        pi = parentpath.pathInfo
        oldFiletype = FilesystemNode.FILE if pi.is_file else FilesystemNode.DIR
        self.set_response_field('parentpath', parentpath.value)
        self.set_response_field('oldFiletype', oldFiletype)
        dest_dir = None
        if pi.is_dir:
            # The parent is already represented by a directory.
            # Check if the proposed name is available.
            if not pi.name_is_available(name.value):
                msg = 'Name "%s" is unavailable under module %s.' % (name.value, parentpath.value)
                raise PfscExcep(msg, PECode.LIBSEG_UNAVAILABLE)
            # Set the destination directory for the new module.
            dest_dir = pi.abs_fs_path_to_dir
        else:
            # The parent module is represented only by a file, not a directory.
            # So we need to convert it from a terminal module to a non-terminal module.
            grandparent_dir = os.path.dirname(pi.abs_fs_path_to_file)
            new_parent_dir = pi.abs_fs_path_to_file[:-5]
            new_dunder_path = os.path.join(new_parent_dir, '__.pfsc')
            os.mkdir(new_parent_dir)
            os.rename(pi.abs_fs_path_to_file, new_dunder_path)
            # Set the destination directory for the new module.
            dest_dir = new_parent_dir
        # At this point we should have a directory in which to write the new file.
        assert os.path.exists(dest_dir)
        # Form the path to the new file.
        new_filename = name.value + '.pfsc'
        new_module_path = os.path.join(dest_dir, new_filename)
        # Write the new file.
        modtext = self.write_module_text(parentpath.value)
        with open(new_module_path, 'w') as f:
            f.write(modtext)
        # Check new libpath.
        new_libpath = '.'.join([parentpath.value, name.value])
        new_pi = PathInfo(new_libpath)
        assert new_pi.is_file
        self.set_response_field('modpath', new_pi.libpath)

    @staticmethod
    def write_module_text(libpath):
        ri = get_repo_info(libpath)
        if ri.is_demo():
            return make_demo_repo_lead_comment(libpath)
        else:
            return ''


class RenameModuleHandler(RepoTaskHandler):
    """
    Handle the process of renaming an existing module.
    """

    def check_input(self):
        self.check({
            "REQ": {
                'libpath': {
                    'type': IType.LIBPATH,
                    'entity': EntityType.MODULE
                },
                'newName': {
                    'type': IType.LIBSEG
                }
            }
        })

    def confirm(self, libpath, newName):
        assert isinstance(libpath, CheckedLibpath)
        assert isinstance(newName, CheckedLibseg)
        assert libpath.length_in_bounds
        assert libpath.valid_format
        assert libpath.is_module
        assert newName.length_in_bounds
        assert newName.valid_format

    def check_permissions(self, libpath):
        self.check_repo_write_permission(libpath, action='edit')

    def compute_implicated_repopaths(self, libpath):
        self.implicated_repopaths = {get_repo_part(libpath.value)}

    def go_ahead(self, libpath, newName):
        # In order to be able to rename the module in question, it has to have
        # a parent module. In other words, we can't rename repos through this method.
        pi = libpath.pathInfo
        filetype = FilesystemNode.FILE if pi.is_file else FilesystemNode.DIR
        self.set_response_field('oldLibpath', libpath.value)
        self.set_response_field('filetype', filetype)
        formal_parentpath = libpath.pathInfo.get_formal_parent_path()
        parentpathinfo = PathInfo(formal_parentpath)
        assert parentpathinfo.is_dir
        # Check if the proposed name is available.
        theNewName = newName.value
        if not parentpathinfo.name_is_available(theNewName):
            msg = 'Name %s is unavailable under module %s.' % (theNewName, formal_parentpath)
            raise PfscExcep(msg, PECode.LIBSEG_UNAVAILABLE)
        # Everything looks good. Rename the module.
        parent_dir = parentpathinfo.abs_fs_path_to_dir
        if pi.is_file:
            src = pi.abs_fs_path_to_file
            dst = os.path.join(parent_dir, theNewName + '.pfsc')
        else:
            assert pi.is_dir
            src = pi.abs_fs_path_to_dir
            dst = os.path.join(parent_dir, theNewName)
        os.rename(src, dst)
        # Check new libpath.
        new_libpath = '.'.join([formal_parentpath, theNewName])
        new_pi = PathInfo(new_libpath)
        assert new_pi.is_module(strict=False)
        self.set_response_field('newLibpath', new_pi.libpath)

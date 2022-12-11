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

import time

from flask import has_request_context

import pfsc.constants
from pfsc.excep import PfscExcep, PECode
from pfsc.handlers import RepoTaskHandler, SocketHandler, Handler
from pfsc.build import build_module
from pfsc.lang.modules import remove_modules_from_cache, load_module
from pfsc.checkinput import IType, EntityType
from pfsc.build.shadow import shadow_save_and_commit
from pfsc.build.lib.libpath import git_style_merge_conflict_file, PathInfo, get_modpath
from pfsc.build.repo import get_repo_part

class TestHandler(SocketHandler):

    def check_permissions(self):
        pass

    def go_ahead(self):

        import random
        if random.randrange(2) == 1:
            raise PfscExcep('dummy error')

        self.success_response = {
            'did': 'something useful'
        }

class AutoWriter(RepoTaskHandler):

    def __init__(self, request_info, room, writepaths, buildpaths, recursives):
        """
        @param request_info: dict defining the task, as in the Handler class
        @param writepaths: list to which we MUST append any modpaths to which we write
        @param buildpaths: list to which we MUST append any modpaths that need to be built
        @param recursives: list to which we MUST append booleans saying which corresp.
                            builds should be recursive
        """
        RepoTaskHandler.__init__(self, request_info, room)
        self.writepaths = writepaths
        self.buildpaths = buildpaths
        self.recursives = recursives

    def compute_implicated_repopaths(self):
        raise NotImplementedError

    def addWritepath(self, modpath):
        self.writepaths.append(modpath)

    def addBuildJob(self, modpath, recursive):
        self.buildpaths.append(modpath)
        self.recursives.append(recursive)

class WidgetDataWriter(AutoWriter):
    """
    Handles the WIDGET_DATA autowrite action.

    This is used by widget classes at the front-end when they want to update the data portion
    of their definition.

    Input should look like:

        {
            'type': AutowriteType.WIDGET_DATA,
            'widgetpath': <the widget path>,
            'data': <the data for updating the widget>
        }
    """

    def check_input(self):
        self.check({
            "REQ": {
                'widgetpath': {
                    'type': IType.LIBPATH
                },
                'data': {
                    'type': IType.SIMPLE_DICT
                }
            }
        })

    def check_permissions(self, widgetpath):
        self.check_repo_write_permission(widgetpath, action='write to')

    def compute_implicated_repopaths(self, widgetpath):
        self.implicated_repopaths = {get_repo_part(widgetpath.value)}

    def go_ahead(self, widgetpath, data):
        widget_data = data
        # Determine the libpath of the module in which the widget lives.
        modpath = get_modpath(widgetpath.value)
        # Load the module
        pi = PathInfo(modpath)
        module = load_module(pi, fail_gracefully=False)
        # Rewrite the text of the module, after substituting the given widget data.
        bc = module.getBlockChunker()
        text = bc.write_module_text(widget_data)
        # Write to disk.
        n = pi.write_module(text)
        self.set_response_field('write', 'Wrote %s, %s bytes' % (modpath, n))
        # Extend the lists:
        self.addWritepath(modpath)
        self.addBuildJob(modpath, False)

class AutowriteType:
    WIDGET_DATA='widget_data'

    all_types = [WIDGET_DATA]

# Lookup mapping AutowriteTypes to handler classes:
AUTOWRITE_HANDLERS = {
    AutowriteType.WIDGET_DATA: WidgetDataWriter
}

class WriteHandler(RepoTaskHandler):
    """
    Handles everything to do with writing and building modules.

    INPUT:
        OPT:
            writepaths: list of libpaths of modules to be written to disk before any building occurs
            writetexts: list of texts of modules to be written, corresp. to the writepaths
            shadowonly: boolean, saying whether writes should be shadow only; default False
            buildpaths: list of libpaths of modules to be built
            recursives: list of booleans, saying whether corresp. builds should be recursive
            autowrites: list of dictionaries, each describing an "autowrite" that is to be performed
				after writing all the writetexts to disk, but before doing the build

				The format of an autowrite dictionary may be quite variable, with the one fixed
				requirement being that it feature a `type` field, whose value is taken from the
				AutowriteType enum class.
    """

    def __init__(self, request_info, room):
        RepoTaskHandler.__init__(self, request_info, room)
        self.post_preparation_hooks.insert(0, self.prepare_autowriters)
        self.writerepos = set()
        self.buildrepos = set()
        self.autowriters = None

    def check_input(self):
        self.check_jsa('info', {
            "OPT": {
                'writepaths': {
                    'type': IType.LIST,
                    'itemtype': {
                        'type': IType.LIBPATH,
                        'entity': EntityType.MODULE
                    },
                    'default_cooked': []
                },
                'writetexts': {
                    'type': IType.LIST,
                    'itemtype': {
                        'type': IType.STR
                    },
                    'default_cooked': []
                },
                'shadowonly': {
                    'type': IType.BOOLEAN,
                    'default_cooked': False
                },
                'buildpaths': {
                    'type': IType.LIST,
                    'itemtype': {
                        'type': IType.LIBPATH,
                        'entity': EntityType.MODULE
                    },
                    'default_cooked': []
                },
                'recursives': {
                    'type': IType.LIST,
                    'itemtype': {
                        'type': IType.BOOLEAN
                    },
                    'default_cooked': []
                },
                'autowrites': {
                    'type': IType.LIST,
                    'itemtype': {
                        'type': IType.SIMPLE_DICT,
                        'keytype': str
                    },
                    'default_cooked': []
                }
            }
        })

    def check_permissions(self, writepaths, buildpaths):
        writerepos = set([get_repo_part(lp.value) for lp in writepaths])
        buildrepos = set([get_repo_part(lp.value) for lp in buildpaths])
        for rp in writerepos:
            self.check_repo_write_permission(rp, action='write to')
        for rp in buildrepos:
            self.check_repo_build_permission(rp, pfsc.constants.WIP_TAG, action='build')
        self.writerepos = writerepos
        self.buildrepos = buildrepos

    def confirm(self, writepaths, writetexts, shadowonly, buildpaths, recursives, autowrites):
        n_p = len(writepaths)
        n_t = len(writetexts)
        if not n_p == n_t:
            msg = 'Matching lists of writepaths and texts not provided.'
            raise PfscExcep(msg, PECode.MISMATCHED_PATHS_AND_TEXTS)
        n_b = len(buildpaths)
        n_r = len(recursives)
        if not n_b == n_r:
            msg = 'Matching lists of buildpaths and recursives not provided.'
            raise PfscExcep(msg, PECode.MISMATCHED_BUILDS_AND_RECS)
        for aw in autowrites:
            t = aw.get('type')
            if t not in AutowriteType.all_types:
                msg = 'Unknown autowrite type: %s' % t
                raise PfscExcep(msg, PECode.UNKNOWN_AUTOWRITE_TYPE)

    def prepare_autowriters(self, autowrites, writepaths, buildpaths, recursives):
        self.autowriters = []
        for i, req in enumerate(autowrites):
            t = req['type']
            cls = AUTOWRITE_HANDLERS[t]
            aw = cls(req, self.room, writepaths, buildpaths, recursives)
            assert isinstance(aw, AutoWriter)
            aw.do_require_csrf = False
            aw.prepare(raise_anticipated=True)
            assert aw.is_prepared
            self.autowriters.append(aw)

    def compute_implicated_repopaths(self):
        ir = self.writerepos | self.buildrepos
        for aw in self.autowriters:
            ir |= aw.get_implicated_repopaths()
        if ir and has_request_context():
            # Only need this for demo repos, but doesn't hurt in other cases,
            # so don't waste time checking if any repo is a demo repo.
            self.require_in_session(
                pfsc.constants.DEMO_USERNAME_SESSION_KEY
            )
        self.implicated_repopaths = ir

    def go_ahead(self, writepaths, writetexts, shadowonly, buildpaths, recursives, autowrites):
        # Replace CheckedLibpaths with their values.
        writepaths = [p.value for p in writepaths]
        buildpaths = [p.value for p in buildpaths]
        # Write modules to disk.
        self.step_write(writepaths, writetexts, shadowonly)
        # Remove any modules we have just written from the loader cache, to ensure
        # that as we proceed we load the versions that have just been
        # written to disk. While timestamp-based caching _should_ already achieve what we
        # want here, we choose not to rely on it because (a) there is the timestamp rounding
        # subtlety noted in the comments in the `load_module` function, and (b) we are talking
        # about a trade-off between saving some build time on the one hand, versus the
        # cardinal error of application development (overwriting the user's work) on the other.
        # Not a tough decision.
        remove_modules_from_cache(writepaths)
        # Do any autowrites.
        if self.autowriters:
            self.step_autowrite()
            # Again purge from cache, for the same reason. (AutoWriters are required
            # to extend the `writepaths` list with the libpaths of any modules they write.)
            remove_modules_from_cache(writepaths)
        if writepaths:
            # Let the client know immediately when the writes are done.
            self.emit('listenable', {
                "type": 'writeComplete',
                "libpathsWritten": writepaths,
            })
        # Process any build jobs.
        self.step_build(buildpaths, recursives)
        if buildpaths:
            # Let the client know that the builds are done.
            self.emit('listenable', {
                "type": 'buildComplete',
                "libpathsBuilt": buildpaths,
            })
        self.step_tree_items()
        # Mark the process as complete.
        self.emit_progress_complete()

    def step_write(self, writepaths, writetexts, shadowonly):
        results = []
        do_basic_write = not shadowonly
        for modpath, modtext in zip(writepaths, writetexts):
            pi = PathInfo(modpath)
            do_shadow_write = pi.check_shadow_policy()

            if do_basic_write:
                n = pi.write_module(modtext)
                results.append(f'Wrote {modpath}, {n} bytes')

            if do_shadow_write:
                shadow_save_and_commit(pi, modtext)
                results.append(f'Shadow wrote {modpath}')

        self.set_response_field('write', results)

    def step_autowrite(self):
        for i, aw in enumerate(self.autowriters):
            aw.proceed(raise_anticipated=True)
            k = 'autowrite_%2d' % i
            self.set_response_field(k, aw.generate_response())

    def step_build(self, buildpaths, recursives):
        results = []
        for buildpath, recursive in zip(buildpaths, recursives):
            build_module(buildpath, recursive=recursive, progress=self.update)
            results.append(f'Built {buildpath}')
            self.emit('listenable', {
                'type': 'moduleBuilt',
                'modpath': buildpath,
                'recursive': recursive,
                'timestamp': time.time(),
            }, groupcast=True)
        self.set_response_field('build', results)

    def step_tree_items(self):
        """
        We need to let the client know about rebuilt trees.

        For now we keep this extremely simple by just prompting the client to reload
        the tree for each repo in which any rebuilding took place.

        If we wanted to make the job more targeted, we could for each repo:
            * Compute the parent of each built module (or the repo itself if the repo was rebuilt).
              We move to parents in case a module was renamed or just introduced, since that affects that
              module's parent's subtree.
            * Compute the least common ancestor LCA of all these parents.
            * Get the manifest tree node for this LCA, ask it to build_relational_model with recursive=True,
              and emit just these items under the `rebuiltTreeItems` event for that repo.
        but we save that for future work.
        """
        for repopath in self.buildrepos:
            self.emit("listenable", {
                'type': 'repoIsBuilt',
                'repopath': repopath,
                'version': pfsc.constants.WIP_TAG,
            })
            # Here would be another simple approach, but one that involves the client updating an
            # existing tree, instead of reloading completely. For now that seems buggy,
            # so we don't do it that way.
            #from pfsc.build.manifest import load_manifest
            #model = []
            #load_manifest(repopath).get_root_node().build_relational_model(model)
            #self.emit('listenable', {
            #    'type': 'rebuiltTreeItems',
            #    'items': model,
            #}, groupcast=True)

    def update(self, op_code, cur_count, max_count=None, message=''):
        self.emit("progress", {
            'job': self.job_id,
            'action': 'Building...',
            'fraction_complete': cur_count / (max_count or 100.0),
            'message': message
        })


class DiffHandler(Handler):
    """
    For each in a list of pfsc modules, compute the diff between the
    existing WIP contents of that module on disk, and a given fulltext.
    """

    def check_input(self):
        self.check_jsa('info', {
            "REQ": {
                'modpaths': {
                    'type': IType.LIST,
                    'itemtype': {
                        'type': IType.LIBPATH,
                        'entity': EntityType.MODULE
                    },
                    'default_cooked': []
                },
                'modtexts': {
                    'type': IType.LIST,
                    'itemtype': {
                        'type': IType.STR
                    },
                    'default_cooked': []
                }
            }
        })

    def check_permissions(self, modpaths):
        # By definition this is a request regarding WIP, and, by passing
        # empty modtexts, would be a way to access fulltexts! So this is
        # definitely only allowed with repo permissions.
        for modpath in modpaths:
            self.check_repo_read_permission(modpath, pfsc.constants.WIP_TAG,
                                            action='load work in progress from')

    def go_ahead(self, modpaths, modtexts):
        modpaths = [p.value for p in modpaths]
        mergetexts = {
            modpath: git_style_merge_conflict_file(modpath, modtext)
            for modpath, modtext in zip(modpaths, modtexts)
        }
        self.set_response_field('mergetexts', mergetexts)

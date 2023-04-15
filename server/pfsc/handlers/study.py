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
import os

from flask_login import current_user
import jinja2

from pfsc.constants import IndexType
from pfsc.handlers import Handler
from pfsc.excep import PfscExcep, PECode
from pfsc.checkinput import IType
from pfsc.build.lib.libpath import get_modpath, PathInfo
from pfsc.build.products import load_dashgraph, load_annotation
from pfsc.build.repo import get_repo_part
from pfsc.lang.modules import load_module, build_module_from_text
from pfsc.lang.annotations import Annotation
from pfsc.lang.widgets import GoalWidget, WidgetTypes
from pfsc.lang.deductions import Deduction
from pfsc.build.versions import collapse_major_string, adapt_gen_version_to_major_index_prop as adapt_maj
from pfsc.gdb import get_gdb, get_graph_reader, building_in_gdb
from pfsc.gdb.user import should_load_user_notes_from_gdb
from pfsc.build.manifest import load_manifest
import pfsc.constants

class GoalInfo:

    def name(self):
        return ''

    def get_origins(self):
        """
        Subclasses should override.
        :return: list of origins (strings) of all goals represented
          by this info object.
        """
        return []

    def write_pfsc(self, studyData):
        """
        Subclasses should override.
        :param studyData: lookup giving goal notes by origin.
        :return: string representing a section of a study page,
          in pfsc syntax.
        """
        return ''

class AnnoInfo(GoalInfo):

    def __init__(self, anno_name):
        """
        :param anno_name: the name of the annotation, i.e. final segment
          in its libpath
        """
        self.anno_name = anno_name
        self.goal_widgets = []

    def name(self):
        return self.anno_name

    def add_goal_widget(self, name, origin):
        """
        :param name: the name of the GoalWidget, i.e. final segment
          in its libpath
        :param origin: the origin of the GoalWidget
        """
        self.goal_widgets.append((name, origin))

    def get_origins(self):
        return [p[1] for p in self.goal_widgets]

    def write_pfsc(self, studyData):
        notes = {g[1]: studyData.get(g[1], {}).get('notes') for g in self.goal_widgets}
        context = {
            'ai': self,
            'notes': notes,
        }
        return study_page_anno_section_template.render(context)

class DeducInfo(GoalInfo):

    def __init__(self, deduc_name, deduc_origin):
        """
        :param deduc_name: the name of the deduc, i.e. final segment
          in its libpath
        :param deduc_origin: the origin of the deduc
        """
        self.deduc_name = deduc_name
        self.deduc_origin = deduc_origin
        self.nodes = []

    def name(self):
        return self.deduc_name

    def add_node(self, idp, origin):
        """
        :param idp: intra-deduc path to this node (string)
        :param origin: the origin of the node
        """
        self.nodes.append((idp, origin))

    def get_origins(self):
        return [self.deduc_origin] + [p[1] for p in self.nodes]

    def write_pfsc(self, studyData):
        notes = {u[1]: studyData.get(u[1], {}).get('notes') for u in self.nodes}
        context = {
            'di': self,
            'deduc_notes': studyData.get(self.deduc_origin, {}).get('notes'),
            'notes': notes,
        }
        return study_page_deduc_section_template.render(context)


study_page_basic_template = jinja2.Template('''
{% for name in names %}
from {{modpath}} import {{name}}
{% endfor %}
anno {{pagename}} @@@
# Study Notes
----------------------------------------------------------------------
{% for section in sections %}
{{section}}
----------------------------------------------------------------------
{% endfor %}
@@@
''')

study_page_anno_section_template = jinja2.Template('''
## Page

<link:>[`{{ai.anno_name}}`]{tab:"other", ref:"{{ai.anno_name}}"}

## Goals
{% for goal_name, origin in ai.goal_widgets %}
<goal:>[]{altpath:"{{ai.anno_name}}.{{goal_name}}", origin:"{{origin}}"} <link:>[`{{goal_name}}`]{tab:"other", ref:"{{ai.anno_name}}.{{goal_name}}"}
{% if notes[origin] %}
{{notes[origin]}}
{% endif %}
{% endfor %}
''')

study_page_deduc_section_template = jinja2.Template('''
## Deduction

<goal:>[]{altpath:"{{di.deduc_name}}"} <chart:>[`{{di.deduc_name}}`]{view:"{{di.deduc_name}}"}
{% if deduc_notes %}{{deduc_notes}}{% endif %}

## Goals
{% for idp, origin in di.nodes %}
<goal:>[]{altpath:"{{di.deduc_name}}.{{idp}}"} <chart:>[`{{idp}}`]{view:"{{di.deduc_name}}.{{idp}}"}
{% if notes[origin] %}
{{notes[origin]}}
{% endif %}
{% endfor %}
''')


class GoalDataLoadMethod:
    MOD_LOAD = 'mod_load'
    BUILD_DIR = 'build_dir'
    # Commenting out the GDB method, since it cannot be completed unless
    # we augment the database in some way, e.g. by putting `altpath` properties
    # on widget j-nodes.
    #GDB = 'gdb'

#DEFAULT_GOAL_DATA_LOAD_METHOD = GoalDataLoadMethod.MOD_LOAD
DEFAULT_GOAL_DATA_LOAD_METHOD = GoalDataLoadMethod.BUILD_DIR

class GoalDataHandler(Handler):
    """
    A Handler that will need to use a GoalDataLoader.
    Takes an extra `method` kwarg, whose value should be a value of the
    GoalDataLoadMethod enum class. This indicates which type of loader
    you want to use.

    The `make_loader` method can then be invoked when you are ready to use
    a loader.
    """

    def __init__(self, request_info, method=DEFAULT_GOAL_DATA_LOAD_METHOD):
        Handler.__init__(self, request_info)
        self.method = method

    def make_loader(self, libpath, version):
        LoaderClass = {
            GoalDataLoadMethod.BUILD_DIR: BuildDir_GoalDataLoader,
            #GoalDataLoadMethod.GDB: Gdb_GoalDataLoader,
            GoalDataLoadMethod.MOD_LOAD: ModuleLoad_GoalDataLoader,
        }[self.method]
        loader = LoaderClass(libpath, version)
        loader.check()
        return loader


class StudyPageBuilder(GoalDataHandler):
    """
    Build study pages.

    Required input:

        libpath: Special libpath of the form 'special.studypage.ENTITY' where the
            ENTITY should be the libpath of any annotation, deduction, or module.

        vers: Full version number indicating the desired version of the named entity.

    Optional input:

        studyData: string of JSON for a lookup in which goal IDs point to dicts
            of the form {
                checked: boolean,
                notes: string
            }
            If the user is logged in and has activated server-side note recording,
            then this studyData lookup is actually ignored, and we instead simply
            load the user's notes from the GDB.
    """

    PREFIX = 'special.studypage.'
    SUFFIX = f'.{pfsc.constants.STUDYPAGE_ANNO_NAME}'

    def check_input(self):
        self.check({
            "REQ": {
                'libpath': {
                    'type': IType.LIBPATH
                },
                'vers': {
                    'type': IType.FULL_VERS,
                },
            },
            "OPT": {
                'studyData': {
                    'type': IType.JSON,
                    'default_cooked': {},
                },
            },
        })
        libpath = self.fields['libpath'].value
        n0 = len(StudyPageBuilder.PREFIX)
        n1 = len(StudyPageBuilder.SUFFIX)
        prefix = libpath[:n0]
        modpath_str = libpath[:-n1]
        studypath_str = libpath[n0:-n1]
        suffix = libpath[-n1:]
        if prefix != StudyPageBuilder.PREFIX or suffix != StudyPageBuilder.SUFFIX:
            msg = f'Study page libpath must begin with {StudyPageBuilder.PREFIX}'
            msg += f' and end with {StudyPageBuilder.SUFFIX}.'
            raise PfscExcep(msg, PECode.WRONG_LIBPATH_TYPE)
        self.check({
            "REQ": {
                'studypath': {
                    'type': IType.LIBPATH,
                },
                'modpath': {
                    'type': IType.LIBPATH,
                }
            }
        }, raw={
            'studypath': studypath_str,
            'modpath': modpath_str,
        })

    def check_permissions(self, studypath, vers):
        if vers.isWIP:
            self.check_repo_read_permission(studypath, vers, action='load work in progress from')

    def write_pfsc(self, pagename, modpath, infos, studyData):
        context = {
            'pagename': pagename,
            'modpath': modpath,
            'names': [info.name() for info in infos],
            'sections': [info.write_pfsc(studyData) for info in infos]
        }
        return study_page_basic_template.render(context)

    def go_ahead(self, modpath, vers, studypath, studyData):
        loader = self.make_loader(studypath.value, vers)
        infos = loader.load_goal_data()
        if should_load_user_notes_from_gdb():
            studyData = loader.load_user_notes()
        pagename = pfsc.constants.STUDYPAGE_ANNO_NAME
        pfsc_text = self.write_pfsc(pagename, loader.modpath, infos, studyData)
        # Now build a module on the fly, and return the built annotation assets.
        repopath = get_repo_part(studypath.value)
        modpath = modpath.value
        module = build_module_from_text(pfsc_text, modpath, dependencies={
            repopath: vers.full,
        })
        # Hack: Before writing the data for the page, tell this PfscModule
        # that it represents the same version as that of the subject matter
        # the study page is about. The study page itself was built at "WIP"
        # version, but we want a distinct version number to appear in widget
        # IDs and pane group IDs. This helps keep things distinct if the user
        # simultaneously loads the study page for a given entity at two or
        # more different versions.
        module.setRepresentedVersion(vers.full)
        page = module[pagename]
        html = page.get_escaped_html()
        data = page.get_anno_data()
        data_json = json.dumps(data)
        self.set_response_field('html', html)
        self.set_response_field('data_json', data_json)


class GoalOriginFinder(GoalDataHandler):
    """
    Look up goal origins.

    Given the libpath of a module, deduction, or annotation, and the full
    version at which to take it, we return the list of origin strings for
    all goals found therein (deducs, nodes, or goal widgets).
    """

    def check_input(self):
        self.check({
            "REQ": {
                'libpath': {
                    'type': IType.LIBPATH,
                },
                'vers': {
                    'type': IType.FULL_VERS,
                },
            },
        })

    def check_permissions(self, libpath, vers):
        if vers.isWIP:
            self.check_repo_read_permission(libpath, vers, action='load work in progress from')

    def go_ahead(self, libpath, vers):
        loader = self.make_loader(libpath.value, vers)
        infos = loader.load_goal_data()
        all_origins = sum([info.get_origins() for info in infos], [])
        self.set_response_field('origins', all_origins)


class GoalDataLoader:
    """
    There are a number of different approaches we can take to loading the
    info on the existing goals under a given libpath (and at a given version),
    be it for a single annotation or deduction, or for a whole module.

    We can read built products from the build dir, we can query the graph
    database, or we can build a module. It's not obvious, a priori, which of
    these approaches is going to be the most efficient.

    Therefore we have here an abstract class representing the job of loading
    data on existing goals. We will design various subclasses to implement the
    different approaches to getting this job done. Then they can be tested, and
    a best approach selected.

    MEANWHILE, it is also convenient to give this class the job of loading a
    user's server-side notes, in the case that the user has enabled this. This
    class will already have determined the type of the entity (module, anno, or
    deduc) and we need that in order to load the user's notes.
    """

    def __init__(self, libpath, version):
        """
        :param libpath: the libpath of the entity under which we want to read
          existing goal data. Must point either to an anno, a deduc, or a module.
        :param version: CheckedVersion representing the desired version of the
          entity in question.
        """
        self.libpath = libpath
        self.version = version
        self.modpath = None
        self.type_ = None
        self.determine_modpath()
        self.determine_type()

    def determine_modpath(self):
        self.modpath = get_modpath(self.libpath, version=self.version.major)

    def determine_type(self):
        gr = get_graph_reader()
        if gr.is_anno(self.libpath, self.version.major):
            self.type_ = IndexType.ANNO
        elif gr.is_deduc(self.libpath, self.version.major):
            self.type_ = IndexType.DEDUC
        else:
            if self.modpath is None:
                self.determine_modpath()
            if self.modpath == self.libpath:
                self.type_ = IndexType.MODULE
            else:
                msg = 'Study page libpaths must point to a module, an annotation, or a deduction,'
                msg += f' but given path `{self.libpath}` does not.'
                raise PfscExcep(msg, PECode.WRONG_LIBPATH_TYPE)

    def check(self):
        """
        Subclasses may override.
        This is a chance to check anything, before this loader is asked to load
        goal data.

        For now it seems we have here a good universal check for any of our loader
        classes. Even the ModLoad one -- and even when applied to WIP -- requires
        that the version in question be already built, since it needs to look up
        deduc & node origins in the GDB.

        :return: nothing, but may raise PfscExceps
        """
        if building_in_gdb():
            built = get_graph_reader().module_is_built(self.modpath, self.version.full)
        else:
            pi = PathInfo(self.modpath)
            build_dir, fn = pi.get_build_dir_and_filename(version=self.version.full)
            built = os.path.exists(build_dir)
        if not built:
            msg = f'Cannot load study data for `{self.libpath}@{self.version.full}`'
            msg += ' since it has not been built yet.'
            raise PfscExcep(msg, PECode.VERSION_NOT_BUILT_YET)

    def load_user_notes(self):
        """
        Load the current user's server-side notes on the entity in question.

        :@return: dict in which goal IDs point to dicts of the form {
            checked: boolean,
            notes: string
        }
        """
        gr = get_graph_reader()
        if self.type_ == IndexType.ANNO:
            method = gr.load_user_notes_on_anno
        elif self.type_ == IndexType.DEDUC:
            method = gr.load_user_notes_on_deduc
        else:
            assert self.type_ == IndexType.MODULE
            method = gr.load_user_notes_on_module
        uns = method(current_user.username, self.libpath, self.version.major)
        return {un.write_origin():un.write_old_style_dict() for un in uns}

    def load_goal_data(self):
        """
        Subclasses should override.

        :return: list of `GoalInfo` instances describing the existing goal data.
        """
        return []


class BuildDir_GoalDataLoader(GoalDataLoader):
    """
    This is a GoalDataLoader that reads from the build directory in order
    to obtain the required information.
    """

    @staticmethod
    def read_info_from_anno_data_json(anno_name, j):
        """
        :param anno_name: name of the annotation
        :param j: JSON (string) for anno data
        :return: an AnnoInfo, or None if this anno defines no GoalWidgets
        """
        data = json.loads(j)
        widget_data = data["widgets"]
        ai = AnnoInfo(anno_name)
        for widget_info in widget_data.values():
            if widget_info["type"] == "GOAL":
                widgetpath = widget_info["widget_libpath"]
                parts = widgetpath.split('.')
                origin = widget_info["origin"]
                if ai is None:
                    ai = AnnoInfo(parts[-2])
                ai.add_goal_widget(parts[-1], origin)
        return ai

    @staticmethod
    def read_info_from_dashgraph_json(deduc_name, j):
        """
        :param deduc_name: name of the deduction
        :param j: JSON (string) for a dashgraph
        :return: a DeducInfo
        """
        dg = json.loads(j)
        deducpath = dg["libpath"]
        deduc_origin = dg["origin"]
        di = DeducInfo(deduc_name, deduc_origin)
        N = len(deducpath) + 1
        skip_types = ["ghost", "dummy"]
        def processNode(node):
            if "origin" in node and node["libpath"] != deducpath and node["nodetype"] not in skip_types:
                idp = node["libpath"][N:]
                origin = node["origin"]
                di.add_node(idp, origin)
            if "children" in node:
                children = node["children"]
                for child in children.values():
                    processNode(child)
        processNode(dg)
        return di

    def load_module_data(self):
        # We use the manifest, so that we can load files in definition order.
        manifest = load_manifest(self.modpath, version=self.version.full)
        module_node = manifest.get(self.modpath)
        contents = module_node.get_contents()

        infos = []
        if building_in_gdb():
            gr = get_graph_reader()
            version = self.version.full
            for node in contents:
                data = node.data
                type_ = data["type"]
                if type_ in ["CHART", "NOTES"]:
                    name = data["name"]
                    libpath = data["libpath"]
                    if type_ == "CHART":
                        j = gr.load_dashgraph(libpath, version)
                        reader = self.read_info_from_dashgraph_json
                    else:
                        _, j = gr.load_annotation(libpath, version, load_html=False)
                        reader = self.read_info_from_anno_data_json
                    infos.append(reader(name, j))
        else:
            # We load directly from the build dir, since the `load_annotation`
            # function does extra work by loading the HTML file.
            pi = PathInfo(self.modpath)
            build_dir, fn = pi.get_build_dir_and_filename(version=self.version.full)
            anno_suffix = '.anno.json'
            dg_suffix = '.dg.json'
            for node in contents:
                data = node.data
                type_ = data["type"]
                if type_ in ["CHART", "NOTES"]:
                    if type_ == "CHART":
                        suffix = dg_suffix
                        reader = self.read_info_from_dashgraph_json
                    else:
                        suffix = anno_suffix
                        reader = self.read_info_from_anno_data_json
                    name = data["name"]
                    with open(os.path.join(build_dir, f'{name}{suffix}')) as f:
                        j = f.read()
                    infos.append(reader(name, j))
        return infos

    def load_goal_data(self):
        if self.type_ == IndexType.ANNO:
            html, j = load_annotation(self.libpath, version=self.version.full)
            anno_name = self.libpath.split('.')[-1]
            ai = self.read_info_from_anno_data_json(anno_name, j)
            return [ai] if ai is not None else []
        elif self.type_ == IndexType.DEDUC:
            j = load_dashgraph(self.libpath, version=self.version.full)
            deduc_name = self.libpath.split('.')[-1]
            di = self.read_info_from_dashgraph_json(deduc_name, j)
            return [di]
        else:
            assert self.type_ == IndexType.MODULE
            return self.load_module_data()


class ModuleLoad_GoalDataLoader(GoalDataLoader):
    """
    This is a GoalDataLoader that loads a module in order
    to obtain the required information.
    """

    @staticmethod
    def build_anno_info(anno):
        goal_widgets = list(filter(lambda w: isinstance(w, GoalWidget), anno.get_widget_lookup().values()))
        ai = AnnoInfo(anno.name)
        for gw in goal_widgets:
            gw.compute_origin()
            ai.add_goal_widget(gw.name, gw.origin)
        return ai

    @staticmethod
    def build_deduc_info(deduc):
        nodes = []
        deduc.getAllNativeNodes(nodes)

        # Must compute origins for deduc and nodes.
        libpaths_by_label = {
            IndexType.DEDUC: [deduc.libpath],
            IndexType.NODE: [node.libpath for node in nodes]
        }
        major = deduc.getMajorVersion()
        origins = get_graph_reader().get_origins(libpaths_by_label, major)

        di = DeducInfo(deduc.name, origins[deduc.libpath])
        for node in nodes:
            di.add_node(node.getIntradeducPath(), origins[node.libpath])
        return di

    def load_goal_data(self):
        module = load_module(self.modpath, version=self.version.full)
        if self.type_ in [IndexType.ANNO, IndexType.DEDUC]:
            item_name = self.libpath[len(self.modpath) + 1:]
            item = module.get(item_name)
            items = [item]
        else:
            assert self.type_ == IndexType.MODULE
            items = module.getNativeItemsInDefOrder(hoist_expansions=True).values()
        infos = []
        for item in items:
            info = None
            if isinstance(item, Annotation):
                info = self.build_anno_info(item)
            elif isinstance(item, Deduction):
                info = self.build_deduc_info(item)
            if info is not None:
                infos.append(info)
        return infos


class Gdb_GoalDataLoader(GoalDataLoader):
    """
    INCOMPLETE:

        _You cannot actually use this class!_

        Before this class could actually work, we would need to record more info
        in the GDB; namely, we would need to record altpaths on goal widgets (or
        maybe an "ALT" edge pointing from one goal widget to another?).

        But, to justify doing that, we'd have to be seeing a significant speed
        up when testing this class on cases where it works (i.e. cases with no
        altpaths). In the tests I ran, I did _not_ see any speed up offered by
        this class over either of the others. So maybe we'll just not develop
        this any further.

    This is a GoalDataLoader that uses the graph database in order
    to obtain the required information.
    """

    @staticmethod
    def load_anno_data(annopath, version):
        M0 = adapt_maj(version.major)
        anno_name = annopath.split('.')[-1]
        ai = AnnoInfo(anno_name)
        gdb = get_gdb()
        with gdb.session() as session:
            # FIXME: Need to limit to results coming <= version.full
            res = session.run(
                f"""
                MATCH (u:{IndexType.WIDGET})
                WHERE u.libpath STARTS WITH $basepath
                AND u.major <= $major < u.cut
                AND u.{IndexType.EP_WTYPE} = "{WidgetTypes.GOAL}"
                RETURN u.libpath, u.major, u.origin
                """, basepath=annopath+'.', major=M0
            )
            for lp, maj, origin in res:
                name = lp.split('.')[-1]
                # FIXME:
                #  This is ultimately wrong in the case of a GoalWidget
                #  that uses an altpath!
                origin = origin or f'{lp}@{collapse_major_string(maj)}'
                ai.add_goal_widget(name, origin)
        return ai

    @staticmethod
    def load_deduc_data(deducpath, version):
        M0 = adapt_maj(version.major)
        deduc_name = deducpath.split('.')[-1]
        origins = get_graph_reader().get_origins({
            IndexType.DEDUC: [deducpath],
        }, version.major)
        deduc_origin = origins[deducpath]
        di = DeducInfo(deduc_name, deduc_origin)
        N = len(deducpath) + 1
        gdb = get_gdb()
        with gdb.session() as session:
            # FIXME: Need to limit to results coming <= version.full
            res = session.run(
                f"""
                MATCH (u:{IndexType.NODE})
                WHERE u.libpath STARTS WITH $basepath
                AND u.major <= $major < u.cut
                RETURN u.libpath, u.major, u.origin
                """, basepath=deducpath + '.', major=M0
            )
            for lp, maj, origin in res:
                idp = lp[N:]
                origin = origin or f'{lp}@{collapse_major_string(maj)}'
                di.add_node(idp, origin)
        return di

    def load_module_data(self, modpath, version):
        # FIXME: could optimize this method by doing custom GDB queries,
        #   instead of repeated use of the existing methods for single anno, single deduc.
        M0 = adapt_maj(version.major)
        items = {}
        gdb = get_gdb()
        with gdb.session() as session:
            for itype in [IndexType.ANNO, IndexType.DEDUC]:
                # FIXME: Need to limit to results coming <= version.full
                res = session.run(
                    f"""
                    MATCH (u:{itype})
                    WHERE u.libpath STARTS WITH $basepath
                    AND u.major <= $major < u.cut
                    RETURN u.libpath
                    """, basepath=modpath + '.', major=M0
                )
                items[itype] = [record[0] for record in res]
        infos = []
        infos.extend(self.load_anno_data(annopath, version) for annopath in items[IndexType.ANNO])
        infos.extend(self.load_deduc_data(deducpath, version) for deducpath in items[IndexType.DEDUC])
        return infos

    def load_goal_data(self):
        if self.type_ == IndexType.ANNO:
            ai = self.load_anno_data(self.libpath, self.version)
            return [ai]
        elif self.type_ == IndexType.DEDUC:
            di = self.load_deduc_data(self.libpath, self.version)
            return [di]
        else:
            assert self.type_ == IndexType.MODULE
            return self.load_module_data(self.modpath, self.version)

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

import re
import json

from markupsafe import escape, Markup
import jinja2

import pfsc.checkinput as checkinput
from pfsc.checkinput import IType, UndefinedInput
from pfsc.checkinput.doc import DocIdType
from pfsc.checkinput.libpath import CheckedLibpath, BoxListing
from pfsc.constants import (
    IndexType,
    DISP_WIDGET_BEGIN_EDIT, DISP_WIDGET_END_EDIT,
    MAX_WIDGET_GROUP_NAME_LEN,
)
from pfsc.lang.freestrings import render_anno_markdown, Libpath
from pfsc.build.lib.libpath import (
    expand_multipath,
    get_formal_moditempath,
    libpath_is_trusted,
)
from pfsc.build.repo import get_repo_part, make_repo_versioned_libpath
from pfsc.gdb import get_graph_reader
from pfsc.lang.objects import PfscObj
from pfsc.lang.doc import doc_ref_factory
from pfsc.util import topological_sort
from pfsc.excep import PfscExcep, PECode
from pfsc_util.imports import from_import


# Widget classes and HTML templates

# NB: blank line at end is important!
# This is so that on the final markdown pass, any text coming immediately after
# the widget gets wrapped in a <p> tag, like it should.
malformed_widget_template = jinja2.Template("""
<div class="widget malformedWidget">
    <p>Malformed Widget</p>
    <p>Error: {{ err_msg }}</p>
    <p>Label: <pre>{{ label }}</pre></p>
    <p>Data: <pre>{{ data }}</pre></p>
</div>

""")


class MalformedWidget:
    """
    This represents any Widget in which the user wrote malformed JSON.
    It provides a way to easily generate some nice HTML that reports the error, and can
    be displayed in the compiled document.
    """

    def __init__(self, name, label, data_text, err, lineno):
        self.name = name
        self.label = label
        self.data_text = data_text
        self.err = err
        self.lineno = lineno

    def writeHTML(self, label=None):
        if label is None: label = escape(self.label)
        # Must escape self.data_text, since, having _not_ successfully passed
        # through our JSON parser, strings in it have _not_ been escaped.
        # Must escape the error message too, since it may refer to a line
        # from the malformed text, which may contain malicious code.
        context = {
            'err_msg': escape(str(self.err)),
            'label': label,
            'data': escape(self.data_text)
        }
        return malformed_widget_template.render(context)


dummy_widget_template = jinja2.Template("""
<div class="widget dummyWidget {{ uid }}">
    <p>Widget</p>
    <p>Label: <pre>{{ label }}</pre></p>
    <p>Data: <pre>{{ data }}</pre></p>
</div>

""")


def make_widget_uid(widgetpath, version):
    return f'{widgetpath}_{version}'.replace('.', '-')


class Widget(PfscObj):
    """
    This is the parent class of all normal Widgets (i.e. all except the MalformedWidget).
    We should make a subclass for every particular type of Widget we might have.
    E.g. there's one for controlling Chart views. There should probably be another for
    controlling "Examplorers."
    """

    def __init__(self, type_, name, label, data, parent, lineno):
        PfscObj.__init__(self)
        self.parent = parent
        self.type_ = type_
        self.name = name
        self.label = label
        self.lineno_within_anno = lineno
        self.is_inline = None

        # The given object of widget data fields, which by this point should be a
        # de-serialized JSON object (actually the Python version thereof), is stored
        # under `self.raw_data`. This then goes through three transformations:
        #   (1) type checking: raw --> checked
        #   (2) libpath resolution: checked --> resolved
        #   (3) final translation: resolved --> translated
        #
        # Step (3) is just a final chance to ensure that all data types are
        # JSON-serializable, and does nothing unless subclasses override `self.data_translator()`.
        # Subclasses do *not* need to worry about translating instances of `CheckedLibpath` or
        # `BoxListing`, as those are automatically translated into strings or lists of strings,
        # in step (2).
        #
        # Finally, `self.data` is produced as a deep copy of the `self.translated_data` object
        # resulting from the three steps described above. This preserves `self.translated_data`,
        # which is useful in debugging.
        #
        # It is then `self.data` that is acted upon in the old `self.enrich_data()` method. The
        # name, "enrich data" may seem odd, as it dates from long before the process described
        # here was implemented. It used to be that the incoming raw data was simply "enriched"
        # before being written into the built representation of the widget.
        self.raw_data = data
        self.checked_data = {}
        self.resolved_data = {}
        self.translated_data = {}
        self.data = {}

        # Grab any default values that may have been set by now.
        # We record a mapping from field names to names of ctl widgets that set them.
        self.fields_accepted_from_ctl_widgets = {}
        self.accept_defaults_from_ctl_widgets()

        # Slot for recording the list of all repos to which resolved libpaths (in data fields) belong:
        self.repos = []
        # Lookup for referenced objects, by absolute libpath:
        self.objects_by_abspath = {}

    def check(self, types, raw=None, reify_undefined=True):
        """
        Method for checking this widget's data fields, and stashing the
        results in `self.checked_data`.

        :param types: the definition of the arg types to be checked. See docstring for
                      the `check_input()` function.

        :param raw: optional dictionary to check instead of `self.raw_data`.

        :param reify_undefined: forwarded to the `check_input()` function.

        :return: nothing
        """
        if raw is None:
            raw = self.raw_data
        try:
            checkinput.check_input(
                raw, self.checked_data, types,
                reify_undefined=reify_undefined,
                err_on_unexpected=True
            )
        except PfscExcep as pe:
            field = pe.bad_field()
            field_detail = f'"{field}" field in ' if field else ''
            pe.extendMsg(f'Problem is for {field_detail}{self.type_} widget {self.libpath}.')
            if field in self.fields_accepted_from_ctl_widgets:
                blame = self.fields_accepted_from_ctl_widgets[field]
                pe.extendMsg(f'Field value was set by ctl widget "{blame}"')
            raise pe

    @classmethod
    def generate_arg_spec(cls):
        """
        Subclasses must override.

        Generate the arg spec dictionary that should be passed to `self.check()` in order to
        check the input data fields.
        """
        raise NotImplementedError(f'Widget class `{cls.__class__}` needs to implement `generate_arg_spec()`')

    def check_fields(self):
        """
        Subclasses must override.

        They should call `self.check()`, passing the arg spec that defines all of their data fields.
        """
        raise NotImplementedError(f'Widget class `{self.__class__}` needs to implement `check_fields()`')

    def has_presence_in_page(self):
        """
        Say whether this widget is meant to "appear" in the page in some way.
        Controls whether we will record an info object for this widget in the
        page data. Usually true. False for e.g. `CtlWidget`, which just controls
        various things at build time.
        """
        return True

    def get_lineno_within_module(self):
        base = 1
        if callable(getattr(self.parent, 'getFirstRowNum', None)):
            n = self.parent.getFirstRowNum()
            if isinstance(n, int):
                base = n
        return base + self.lineno_within_anno - 1

    def get_index_type(self):
        return IndexType.WIDGET

    def get_type(self):
        return self.type_

    def set_pane_group(self, subtype=None, default_group_name=''):
        """
        Construct the group ID for this widget. Should be called from the `enrich_data()`
        methods of those subclasses that use group names.

        The group ID consists of ":"-separated parts.
        The first two parts are always:
         * The group namespace
         * The widget type

        The namespace is always the repo-versioned libpath of a certain Proofscape
        entity. By default this will be the page (anno or Sphinx) to which the
        widget belongs. However, if the author specifies a group name by defining
        a 'group' field in the widget data, then leading dots ('.') are chopped off
        and interpreted to point to modules above this page. One dot means the module
        in which the page is defined, two dots the module above that, and so on.

        Note: Just dots (e.g. '..') is indeed a valid value for the 'group' field.
        This just means the author wants the default group (empty name) in an ancestor
        namespace.

        After the first two parts may come a "subtype", if a string was passed to
        the `subtype` kwarg. E.g. `DocWidget` uses this to make the docId a part of
        the group ID (thus making it impossible for doc widgets pointing to different
        docs to belong to the same group).

        The final part is always the group's name, which is either the default specified
        by the `default_group_name` kwarg, or a name the author chose to supply in the
        'group' field of the widget data (after chopping off leading dots, as described
        above).
        """
        # Do a string conversion so that authors may provide, say, integers for 'group'
        # spec. For example, this is for the convenience of typing `2` instead of `"2"`.
        group_spec = str(self.data.get('group', default_group_name))

        if len(group_spec) > MAX_WIDGET_GROUP_NAME_LEN:
            msg = f'Widget group name too long: {group_spec[:MAX_WIDGET_GROUP_NAME_LEN]}...'
            raise PfscExcep(msg, PECode.WIDGET_GROUP_NAME_TOO_LONG)

        leading_dots = 0
        while group_spec and group_spec[0] == '.':
            leading_dots += 1
            group_spec = group_spec[1:]
        group_name = group_spec

        namespace_parts = self.parent.libpath.split('.')
        if len(namespace_parts) < 3 + leading_dots:
            msg = f'Widget group name has too many leading dots: {group_spec}'
            raise PfscExcep(msg, PECode.PARENT_DOES_NOT_EXIST)
        if leading_dots > 0:
            namespace_parts = namespace_parts[:-leading_dots]
        namespace_libpath = '.'.join(namespace_parts)

        # First two parts of group ID are:
        #  * repo-versioned libpath of the namespace object
        #  * our widget type
        parts = [
            make_repo_versioned_libpath(namespace_libpath, self.getVersion()),
            self.get_type(),
        ]

        # Sometimes we may want a "subtype", to be a third part:
        if subtype is not None:
            parts.append(subtype)

        # Final part is always the group's name (which may be the empty string).
        parts.append(group_name)

        pane_group = ":".join(parts)
        self.data['pane_group'] = pane_group

    def cascadeLibpaths(self):
        PfscObj.cascadeLibpaths(self)

    def resolveLibpathsRec(self):
        self.repos = self.resolve_libpaths_in_checked_data()
        PfscObj.resolveLibpathsRec(self)

    def translate_data(self):
        """
        This is a last chance to produce an altered form of the data, after type checking and
        libpath resolution, and before `enrich_data()` is called.

        For example, if there is some non-JSON-serializable type still present in the data,
        this should be translated into some JSON-serializable representation.

        Subclasses wishing to achieve something special here should NOT override THIS method,
        but instead override the `data_translator()` method.
        """
        self.translated_data = self._translate_data_rec(self.resolved_data, [])
        # Since `self.translated_data` is supposed to be JSON-serializable, we can use
        # the ser/deser trick to make a deep copy.
        self.data = json.loads(json.dumps(self.translated_data))

    def _translate_data_rec(self, obj, datapath):
        if isinstance(obj, dict):
            pairs = [
                (k, self._translate_data_rec(v0, datapath + [k]))
                for k, v0 in obj.items()
            ]
            return {k: v1 for k, v1 in pairs if not isinstance(v1, UndefinedInput)}
        elif isinstance(obj, list):
            L = [
                self._translate_data_rec(a0, datapath + [i])
                for i, a0 in enumerate(obj)
            ]
            return [a1 for a1 in L if not isinstance(a1, UndefinedInput)]
        else:
            return self.data_translator(obj, datapath)

    def data_translator(self, obj, datapath):
        """
        Subclasses should override this method if they want to achieve anything
        special during the `translate_data()` call.

        :param obj: the current object to be translated
        :param datapath: a list of dict keys and list indices, indicating how we
            reached the current object, while traversing `self.resolved_data`.
        :return: EITHER return the desired translation of `obj` (should always be
            some JSON-serializable type), OR return an instance of the
            `pfsc.checkinput.UndefinedInput` class, to indicate that you want to omit
            this object entirely, from the dict or list that contains it.
        """
        return obj

    def getRequiredRepoVersions(self):
        # Get ahold of the desired version for each repo implicated by libpaths
        # in this widget's data.
        extra_msg = f' Required by widget `{self.libpath}`.'
        return {
            r: self.getRequiredVersionOfObject(r, extra_err_msg=extra_msg)
            for r in self.repos
        }

    def writeUID(self):
        """
        Write a unique ID, based on the libpath, but in a suitable format for use at the front-end.
        In particular, we want to be able to use this as a class for a dom element, so it's not great
        if it contains dots.
        """
        libpath = self.getLibpath()
        version = self.getVersion()
        return make_widget_uid(libpath, version)

    def writeHTML(self, label=None, sphinx=False):
        if label is None: label = escape(self.label)
        # Unlike the case with the MalformedWidget, this time self.data _has_
        # successfully passed through our JSON parser, which means that any
        # strings occurring within it have been escaped. So we do not need
        # to escape here, before displaying.
        context = {
            'label': label,
            'data': json.dumps(self.data, indent=4),
            'uid': self.writeUID()
        }
        return dummy_widget_template.render(context)

    def writeData(self):
        # We wait until build time (i.e. now) to add the version number, so that
        # we can be sure to get the module's _represented_ version (not its "loading version").
        self.data["version"] = self.getVersion()
        return self.data

    def accept_defaults_from_ctl_widgets(self):
        lowercase_type = self.get_type().lower()
        for default_field_name in SUPPORTED_CTL_WIDGET_DEFAULT_FIELDS:
            _, widget_type, field_name = default_field_name.split('_')
            if widget_type == lowercase_type and field_name not in self.raw_data:
                if self.parent.check_ctl_widget_setting_defined(default_field_name):
                    self.raw_data[field_name] = self.parent.read_ctl_widget_setting(
                        default_field_name
                    )
                    blame = self.parent.check_ctl_widget_setting_blame(field_name)
                    self.fields_accepted_from_ctl_widgets[field_name] = blame

    def enrich_data(self):
        """
        Subclasses may wish to add fields atop those supplied by the user.
        This method will be called after libpaths have cascaded, and after
        libpaths within this widget's data have been resolved. In fact we
        call it as late as possible, right before writing the data to disk
        in the build process. In particular this means the enclosing Module
        will already know its represented version.
        """
        self.data['widget_libpath'] = self.libpath
        self.data["type"] = self.type_
        self.data["src_line"] = self.get_lineno_within_module()
        self.data['uid'] = self.writeUID()

    def resolve_libpath(self, libpath):
        """
        Given a relative libpath, resolve it to an absolute libpath.

        This method also achieves the critical side effect of checking that the
        object referenced by the libpath is actually present in the module in which
        the widget lives (whether defined there or imported into there). This is
        necessary so that we can know the repo to which the object belongs, and hence
        the version at which we're taking it (based on the declared dependencies of the
        repo being built).

        :param libpath: The relative libpath to be resolved.
        :return: The absolute libpath to which the given one resolves.
        :raises: PfscExcep if relative libpath cannot be resolved.
        """
        if libpath in self.objects_by_abspath:
            # This already is an absolute path to which we have resolved sth.
            return libpath
        obj, _ = self.getFromAncestor(libpath, missing_obj_descrip=f'named in widget {self.getLibpath()}')
        abspath = obj.getLibpath()
        self.objects_by_abspath[abspath] = obj
        return abspath

    def resolve_libpaths_in_checked_data(self):
        """
        The data defining a widget may contain relative libpaths which must be interpreted relative
        to the module in which the widget lives. It is important that all such libpaths be resolved
        to absolute ones, for use on the client side.

        This method is to be called after `self.check_fields()` has turned `self.raw_data` into
        `self.checked_data`. It traverses `self.checked_data`, looking for instances of the
        `CheckedLibpath` and `BoxListing` classes. When it finds these, it attempts to resolve the libpaths
        to absolute ones, and record the results in `self.resolved_data`.

        :return: self.resolved_data is built as a side effect; our return value is just the set of
          repo parts of all libpaths resolved.
        """
        repos = set()

        def res_checked_libpath(clp):
            abspath = self.resolve_libpath(clp.value)
            repos.add(get_repo_part(abspath))
            return abspath

        def res(obj):
            if isinstance(obj, dict):
                return {res(k): res(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [res(a) for a in obj]
            elif isinstance(obj, CheckedLibpath):
                return res_checked_libpath(obj)
            elif isinstance(obj, BoxListing):
                if obj.is_keyword():
                    return obj.bracketed_keyword
                else:
                    return [res_checked_libpath(clp) for clp in obj.checked_libpaths]
            else:
                return obj

        self.resolved_data = res(self.checked_data)

        return repos


class UnknownTypeWidget(Widget):

    def __init__(self, name, label, data, anno, lineno):
        Widget.__init__(self, "<unknown-type>", name, label, data, anno, lineno)

    def check_fields(self):
        pass


"""
Each field name must be of the form
    default_WIDGETTYPE_FIELDNAME
This is required for the current implementation of `Widget.accept_defaults_from_ctl_widgets()` to work.
Note that snake case is deliberately used here, so that the camel-cased FIELDNAME can easily fit inside.
At some point, we may just open it up and support all fields, but for the moment
we're listing those that are supported.
"""
SUPPORTED_CTL_WIDGET_DEFAULT_FIELDS = [
    'default_chart_group',
    'default_doc_group', 'default_doc_doc',
]


class CtlWidget(Widget):
    """
    This widget just provides a way to control various things at build time.
    It does not have any actual presence in the page.

    Currently supported options:

        * Everything in `SUPPORTED_CTL_WIDGET_DEFAULT_FIELDS`

        * Stuff for controlling Markdown rendering:

            sectionNumbers: {
                on: boolean (default True),
                topLevel: int from 1 to 6 (default 1), indicating at what heading
                    level numbers should begin to be automatically inserted
            }

            If `sectionNumbers` is defined at all, then its `on` property defaults to
            True; but, until a CtlWidget is found that switches section numbering on, it
            is off.
    """

    supported_default_fields = SUPPORTED_CTL_WIDGET_DEFAULT_FIELDS

    def __init__(self, name, label, data, anno, lineno):
        Widget.__init__(self, WidgetTypes.CTL, name, label, data, anno, lineno)
        self.record_default_fields()

    @classmethod
    def _generate_arg_spec_parts(cls):
        markdown_control_opts = {
            'sectionNumbers': {
                'type': IType.DICT,
                'spec': {
                    "OPT": {
                        'on': {
                            'type': IType.BOOLEAN,
                            'default_cooked': True,
                        },
                        'topLevel': {
                            'type': IType.INTEGER,
                            'min': 1,
                            'max': 6,
                            'default_cooked': 1,
                        },
                    }
                },
            },
        }
        spec = {
            "OPT": markdown_control_opts,
        }

        # We "check" the 'default-...' fields with `IType.ANY`. By even making it this far, we
        # know that they were parsable as JSON, and that's all we can check at this level.
        # When they are adopted by specific widget types, they will be checked there.
        # But they have to be named in our OPT dict, or else `self.check()` will raise an exception
        # when they are present.
        spec["OPT"].update({
            field_name: {'type': IType.ANY}
            for field_name in cls.supported_default_fields
        })

        return spec, markdown_control_opts

    @classmethod
    def generate_arg_spec(cls):
        spec, _ = cls._generate_arg_spec_parts()
        return spec

    def check_fields(self):
        spec, _ = self._generate_arg_spec_parts()
        self.check(spec)

    def data_translator(self, obj, datapath):
        is_default_field = datapath and datapath[-1] in self.supported_default_fields
        return UndefinedInput() if is_default_field else obj

    def has_presence_in_page(self):
        return False

    @staticmethod
    def malformed(detail):
        msg = 'Malformed control widget. '
        msg += detail
        raise PfscExcep(msg, PECode.MALFORMED_CONTROL_WIDGET)

    def record_default_fields(self):
        """
        Look for definitions of defaults, and record them.

        NOTE: It is critical that this method be called at construction time, so that
        the values set here can be available when subsequent widgets are constructed.
        """
        for field_name in self.supported_default_fields:
            if field_name in self.raw_data:
                value = self.raw_data[field_name]
                self.parent.make_ctl_widget_setting(field_name, value, self.name)

    def configure(self, renderer):
        sn = self.data.get('sectionNumbers')
        if sn is not None:
            renderer.sn_do_number = sn.get('on')
            renderer.sn_top_level = sn.get('topLevel')

    def writeHTML(self, label=None, sphinx=False):
        """
        Ctl widget has no page elements.
        """
        return ''


class NavWidget(Widget):
    """
    Superclass for "navigation" widget types, i.e. ones whose HTML representation
    is a single <a> tag, and whose job is to navigate (to) some other content.
    """

    def __init__(self, type_, html_template_name, name, label, data, parent, lineno):
        Widget.__init__(self, type_, name, label, data, parent, lineno)
        self.html_template_name = html_template_name
        self.is_inline = True

    @classmethod
    def add_common_options_to_arg_spec(cls, spec):
        """
        Before returning the arg spec from their `generate_arg_spec()` method, subclasses
        should pass the spec to this method, to add the optional `group` arg.
        """
        spec["OPT"] = spec.get("OPT", {})
        spec["OPT"]['group'] = {
            'type': IType.DISJ,
            'alts': [
                {
                    'type': IType.STR,
                    'max_len': MAX_WIDGET_GROUP_NAME_LEN,
                },
                # Integers are allowed. They will be converted to string later.
                {
                    'type': IType.INTEGER,
                    'min': 0,
                }
            ],
            'default_cooked': '',
        }

    def writeHTML(self, label=None, sphinx=False):
        if label is None:
            label = escape(self.label)

        classes = []
        if sphinx:
            # We want Sphinx's 'reference' class, which eliminates the
            # underscore text decoration.
            classes.append('reference')
        classes.append(self.writeUID())

        context = {
            'label': label,
            'classes': ' '.join(classes),
        }
        template = widget_templates[self.html_template_name]
        return template.render(context)


"""
Note: We need Widget classes (along with all PfscObj subclasses) to be
picklable, so that internal representations can be stored on disk, and restored
later to speed up re-builds.

Jinja templates appear not to be picklable, so we store the following templates
in a lookup, instead of storing them as attributes of their respective Widget
classes.
"""
chart_widget_template = jinja2.Template("""<a class="widget chartWidget {{ classes }}" href="#">{{ label }}</a>""")
doc_widget_template = jinja2.Template("""<a class="widget docWidget {{ classes }}" tabindex="-1" href="#">{{ label }}</a>""")
link_widget_template = jinja2.Template("""<a class="widget linkWidget {{ classes }}" href="#">{{ label }}</a>""")
label_widget_template = jinja2.Template("""<{{tag}} class="widget labelWidget {{ classes }}">{{contents}}<span class="labellink">¶</span></{{tag}}>""")
goal_widget_template = jinja2.Template("""<{{tag}} class="widget goalWidget {{ classes }}"><span class="graphics"></span>{{contents}}</{{tag}}>""")
widget_templates = {
    'chart_widget_template': chart_widget_template,
    'doc_widget_template': doc_widget_template,
    'link_widget_template': link_widget_template,
    'label_widget_template': label_widget_template,
    'goal_widget_template': goal_widget_template,
}


class ChartWidget(NavWidget):
    """
    A Widget class for controlling Chart views.
    """

    def __init__(self, name, label, data, anno, lineno):
        NavWidget.__init__(self, WidgetTypes.CHART, 'chart_widget_template', name, label, data, anno, lineno)

    @classmethod
    def generate_arg_spec(cls):
        spec = {
            "OPT": {
                'view': {
                    'type': IType.RELBOXLISTING,
                    'allowed_keywords': ['all'],
                },
                'onBoard': {
                    'type': IType.RELBOXLISTING,
                },
                'offBoard': {
                    'type': IType.RELBOXLISTING,
                    'allowed_keywords': ['all'],
                },
                'reload': {
                    'type': IType.RELBOXLISTING,
                    'allowed_keywords': ['all'],
                },
                'coords': {
                    'type': IType.DISJ,
                    'alts': [
                        {
                            'type': IType.STR,
                            'values': ['fixed'],
                        },
                        {
                            'type': IType.LIST,
                            'spec': [
                                {'type': IType.INTEGER},
                                {'type': IType.INTEGER},
                                {'type': IType.FLOAT, 'gt': 0},
                            ]
                        }
                    ],
                },
                'select': {
                    'type': IType.DISJ,
                    'alts': [
                        {
                            'type': IType.BOOLEAN,
                        },
                        {
                            'type': IType.RELBOXLISTING,
                        }
                    ],
                },
                'color': {
                    'type': IType.CHART_COLOR,
                    'update_allowed': True,
                },
                'hoverColor': {
                    'type': IType.CHART_COLOR,
                    'update_allowed': False,
                },
                'layout': {
                    'type': IType.STR,
                    'values': [
                        'KLayDown', 'KLayUp', 'OrderedList1',
                    ]
                },
                'transition': {
                    'type': IType.BOOLEAN
                },
                'flow': {
                    'type': IType.BOOLEAN
                },
                'viewOpts': {
                    'type': IType.DICT,
                    'spec': {
                        "OPT": {
                            'core': {
                                'type': IType.RELBOXLISTING,
                                'allowed_keywords': ['named'],
                            },
                            'center': {
                                'type': IType.RELBOXLISTING,
                                'allowed_keywords': ['all', 'core', 'named'],
                            },
                            'viewboxPaddingPx': {
                                'type': IType.INTEGER,
                                'min': 0,
                            },
                            'viewboxPaddingPercent': {
                                'type': IType.INTEGER,
                                'min': 0,
                            },
                            'maxZoom': {
                                'type': IType.FLOAT,
                                'gt': 0,
                            },
                            'minZoom': {
                                'type': IType.FLOAT,
                                'gt': 0,
                            },
                            'panPolicy': {
                                'type': IType.STR,
                                'values': [
                                    'centerAlways', 'centerNever', 'centerDistant',
                                ],
                            },
                            'insetAware': {
                                'type': IType.BOOLEAN,
                            },
                        }
                    }
                },
            },
        }
        cls.add_common_options_to_arg_spec(spec)
        return spec

    def check_fields(self):
        spec = self.generate_arg_spec()
        self.check(spec)

    def enrich_data(self):
        super().enrich_data()
        self.set_pane_group()
        self.data['versions'] = self.getRequiredRepoVersions()
        self.data['title_libpath'] = self.parent.libpath
        self.data['icon_type'] = 'nav'
        self.process_color_options()

    def process_color_options(self):
        hc_name = 'hoverColor'
        if hc_name in self.data:
            hc_dict = self.data[hc_name]
            hc_setup = set_up_hover_color(hc_dict)
            self.data[hc_name] = hc_setup


def set_up_hover_color(hc):
    """
    NOTE: hoverColor may only be used with *node* colors -- not *edge* colors.

    If user has requested hoverColor, we enrich the data for ease of
    use by the client-side code.

    Under `hoverColor`, the user provides an ordinary `color` request.
    The user should *not* worry about using any of `update`, `save`, `rest`;
    we take care of all of that. User should just name the colors they want.

    We transform the given color request so that under `hoverColor` our data
    instead features *two* ordinary color requests: one called `over` and one
    called `out`. These can then be applied on `mouseover` and `mouseout` events.
    """
    over = {':update': True}

    def set_prefix(s):
        if s[0] != ":":
            return s
        return f':save:tmp{s}'
    for k, v in hc.items():
        k, v = map(set_prefix, [k, v])
        over[k] = v

    out = {':update': True}

    def do_weak_restore(s):
        if s[0] != ":":
            return s
        return f':wrest'
    for k, v in hc.items():
        k, v = map(do_weak_restore, [k, v])
        out[k] = v

    return {
        'over': over,
        'out': out
    }


DOC_ID_TYPE_TO_CLIENTSIDE_CONTENT_TYPE = {
    DocIdType.PDF_FINGERPRINT_ID_TYPE: "PDF",
}


class DocWidget(NavWidget):
    """
    A Widget class for controlling document panes (PDF etc.).
    """

    def __init__(self, name, label, data, anno, lineno):
        NavWidget.__init__(self, WidgetTypes.DOC, 'doc_widget_template', name, label, data, anno, lineno)
        self.docReference = None

    @classmethod
    def generate_arg_spec(cls):
        spec = {
            "REQ": {
                'sel': {
                    'type': IType.DISJ,
                    'alts': [
                        {
                            'type': IType.RELPATH,
                            'is_Libpath_instance': True,
                        },
                        {
                            'type': IType.STR
                        }
                    ]
                },
            },
            "OPT": {
                'doc': {
                    'type': IType.DICT,
                    'spec': {
                        "REQ": {
                            'docId': {
                                'type': IType.DOC_ID,
                            },
                        },
                        "OPT": {
                            'url': {
                                'type': IType.URL,
                                'allowed_schemes': ['https', 'http'],
                            },
                            'aboutUrl': {
                                'type': IType.URL,
                                'allowed_schemes': ['https', 'http'],
                            },
                            'title': {
                                'type': IType.STR,
                            },
                            'author': {
                                'type': IType.STR,
                            },
                            'year': {
                                'type': IType.INTEGER,
                            },
                            'publisher': {
                                'type': IType.STR,
                            },
                            'ISBN': {
                                'type': IType.STR,
                            },
                            'eBookISBN': {
                                'type': IType.STR,
                            },
                            'DOI': {
                                'type': IType.STR,
                            },
                        }
                    },
                },
            },
        }
        cls.add_common_options_to_arg_spec(spec)
        return spec

    def check_fields(self):
        spec = self.generate_arg_spec()
        self.check(spec)

    def enrich_data(self):
        super().enrich_data()

        code = None
        origin_node = None
        doc_info_obj = None
        doc_info_libpath = None

        doc_field_name = 'doc'
        sel_field_name = 'sel'

        doc_field_value = self.data.get(doc_field_name)
        sel_field_value = self.data.get(sel_field_name)

        # The sel field can be a libpath pointing to a node, when you want to
        # clone the very same selection made by the doc ref of that node.
        # For now, we require a `Libpath` object. In future, could expand
        # support to libpaths given as strings. Then will have to perform a
        # check that it is not a combiner code string.
        if isinstance(sel_field_value, Libpath):
            abspath = self.resolve_libpath(sel_field_value)
            origin_node = self.objects_by_abspath[abspath]
        else:
            code = sel_field_value

        try:
            if sel_field_value is None and doc_field_value is None:
                msg = 'Failed to define doc info under `doc` or `sel`'
                raise PfscExcep(msg, PECode.MISSING_INPUT)
            if doc_field_value is not None:
                if isinstance(doc_field_value, dict):
                    doc_info_obj = doc_field_value
                elif isinstance(doc_field_value, str):
                    doc_info_libpath = doc_field_value
                else:
                    msg = '`doc` field should be dict (full info) or string (libpath)'
                    raise PfscExcep(msg, PECode.INPUT_WRONG_TYPE)
            self.docReference = doc_ref_factory(
                code=code, origin_node=origin_node, doc_info_obj=doc_info_obj,
                context=self.parent, doc_info_libpath=doc_info_libpath
            )
        except PfscExcep as e:
            e.extendMsg(f'in doc widget {self.libpath}')
            raise

        # Clean up. Doc descriptors go at top level of anno.json; don't need
        # to repeat them in each doc widget.
        if doc_field_name in self.data:
            del self.data[doc_field_name]

        doc_info = self.docReference.doc_info

        # docId
        # We extract this from the doc info.
        # It is needed:
        #  * in the final widget data
        #  * as a subtype in our pane group
        doc_id_field_name = 'docId'
        doc_id = doc_info[doc_id_field_name]
        self.data[doc_id_field_name] = doc_id
        self.set_pane_group(subtype=doc_id)

        # `type` field
        # For use by the client, we need the `type` field in the data object for this widget
        # to indicate the *content* type ("PDF", etc.), not the *widget* type ("DOC").
        id_type = self.docReference.id_type
        content_type = DOC_ID_TYPE_TO_CLIENTSIDE_CONTENT_TYPE.get(id_type)
        if not content_type:
            raise PfscExcep(f"Unknown doc ID type: {id_type}", PECode.MALFORMED_DOC_ID)
        self.data["type"] = content_type

        # Do we define a doc highlight?
        hid_field_name = 'highlightId'
        if (cc := self.docReference.combiner_code) is not None:
            # Final selection code must be pure combiner code (no two-part ref code)
            self.data[sel_field_name] = cc
            # The combiner code can be used for "ad hoc highlights"; for
            # "named highlights" we need a highlight ID:
            self.data[hid_field_name] = f'{self.parent.getLibpath()}:{self.getDocRefInternalId()}'

        # If a URL was provided, we want that in the widget data.
        url_field_name = 'url'
        if url_field_name in doc_info:
            self.data[url_field_name] = doc_info[url_field_name]

    def getDocRef(self):
        return self.docReference

    def getDocRefInternalId(self):
        # For siid in our highlight descriptors, we want to use the widget uid.
        # This is most useful on the client side for scrolling a notes page to
        # the widget in question.
        return self.writeUID()


class LinkWidget(NavWidget):
    """
    Link widgets are for making a link to another annotation, or directly to
    a particular widget within an annotation.

    Fields:

        REQ:

            ref: the libpath of the annotation or widget to which you wish to link

        OPT:

            tab: a string indicating the desired tab policy. This controls whether the
                content is loaded in the same tab where the link occurred, or another
                existing tab, or a new tab.

                The default value is `existing`. (See below.)

                In order to help define the policies, suppose the link occurs in
                annotation A and points (in)to annotation B. Suppose the link has
                been clicked inside tab T0. If B is currently open in one or more
                tabs, let R be the one among these with which the user has most
                recently interacted.

                Policies:

                existing: The idea is that if B is already open in any tab, then load
                    the content there. To be precise: If B != A and R exists, load in R.
                    Else load in T0.

                same: Load in T0 under all circumstances.

                other: The idea is that the content is to be loaded somwhere else.
                    To be precise, if R exists, load there. Else load in a new tab.

                new: Load in a new tab under all circumstances.
    """

    def __init__(self, name, label, data, anno, lineno):
        NavWidget.__init__(self, WidgetTypes.LINK, 'link_widget_template', name, label, data, anno, lineno)

    @classmethod
    def generate_arg_spec(cls):
        return {
            "REQ": {
                'ref': {
                    'type': IType.RELPATH,
                },
            },
            "OPT": {
                'tab': {
                    'type': IType.STR,
                    'values': [
                        'existing', 'same', 'other', 'new',
                    ],
                    'default_cooked': 'existing'
                },
            }
        }

    def check_fields(self):
        spec = self.generate_arg_spec()
        self.check(spec)

    def enrich_data(self):
        super().enrich_data()
        # Determine the type of thing the ref points to.
        # It should be either an annotation or a widget.
        target_libpath = self.data['ref']
        target_version = self.getRequiredVersionOfObject(target_libpath)
        target_annopath = get_formal_moditempath(target_libpath, version=target_version)
        target_type = "ANNO" if target_libpath == target_annopath else "WIDG"
        self.data["annopath"] = target_annopath
        self.data["target_version"] = target_version
        self.data['target_type'] = target_type
        if target_type == "WIDG":
            self.data['target_selector'] = '.' + make_widget_uid(target_libpath, target_version)


qna_widget_template = jinja2.Template("""
<div class="widget qna_widget {{ uid }}">
<div class="qna_question">
<span class="qna_label">{{ label }}</span>
{{ question }}
</div>
<div class="qna_answer">
<span class="qna_label">Answer:</span>
<div class="qna_hide">
{{ answer }}
</div>
</div>
</div>
""")


class QnAWidget(Widget):
    """
    Question & Answer widgets are for posing a question, and giving the answer.
    """

    def __init__(self, name, label, data, anno, lineno):
        Widget.__init__(self, WidgetTypes.QNA, name, label, data, anno, lineno)
        self.is_inline = False
        self.question = None
        self.answer = None

    @classmethod
    def generate_arg_spec(cls):
        return {
            "REQ": {
                'question': {
                    'type': IType.STR,
                },
                'answer': {
                    'type': IType.STR,
                },
            }
        }

    def check_fields(self):
        spec = self.generate_arg_spec()
        self.check(spec)
        self.question = self.checked_data['question']
        self.answer = self.checked_data['answer']

    def writeHTML(self, label=None, sphinx=False):
        if label is None: label = escape(self.label)
        context = {
            'label': label,
            'question': self.question,
            'answer': self.answer,
            'uid': self.writeUID()
        }
        return qna_widget_template.render(context)


heading_pattern = re.compile(r'<h([1-6])>(.+?)</h\1>$')


class WrapperWidget(Widget):
    """
    This is an abstract class, representing widgets that might want to wrap markdown
    text including both inline spans, and headings.

    Calling the determine_tag_and_contents method stores self.tag and self.contents, so that

        <{{ self.tag }}> {{ self.contents }} </{{ self.tag }}>

    would make a correct representation of the label text. Here the tag will be either `span` or
    else one of the heading tags h1 - h6.

    Subclasses may write their own writeHTML method, or, if it suffices, simply set self.template_name,
    and use the abstract method of this class.

    NB: The templates you use should be one-liners. This is because they are going to be passed
    through Markdown again, and linebreaks will cause it to do things you don't want.
    """

    def determine_tag_and_contents(self):
        mdtest = render_anno_markdown(self.label, {}, trusted=self.parent.trusted)
        M = heading_pattern.match(mdtest)
        if M:
            self.tag = 'h%s' % M.group(1)
            self.contents = M.group(2)
        else:
            self.tag = 'span'
            self.contents = self.label

    def cascadeLibpaths(self):
        super().cascadeLibpaths()
        # We need to know libpaths before we can determine tag and contents
        # (because we have to check whether we come from a trusted repo before
        # rendering markdown on our label).
        self.determine_tag_and_contents()

    def writeHTML(self, label=None, sphinx=False):
        classes = []
        if sphinx:
            classes.append('reference')
        classes.append(self.writeUID())

        context = {
            'tag': self.tag,
            'contents': self.contents,
            'classes': ' '.join(classes),
        }
        template = widget_templates[self.template_name]
        return template.render(context)


class LabelWidget(WrapperWidget):
    """
    Label widgets are intended as a means to mark a location in an annotation,
    so that it is possible to link to that spot.

    Format:

        <label:>[LABEL]{}
    """

    def __init__(self, name, label, data, anno, lineno):
        Widget.__init__(self, WidgetTypes.LABEL, name, label, data, anno, lineno)
        self.template_name = 'label_widget_template'
        self.is_inline = True

    @classmethod
    def generate_arg_spec(cls):
        return {}

    def check_fields(self):
        spec = self.generate_arg_spec()
        # Even though we accept no fields, it's important to call `self.check()`,
        # as this will raise an exception if the user *did* define any fields.
        self.check(spec)


class GoalWidget(WrapperWidget):
    """
    Goal widgets provide a way to add a checkbox in an annotation. Along with the
    checkboxes that appear on nodes in chart panes, this provides a way to
    represent learning objectives.

    Format:

        <goal:>[LABEL]{
        OPTIONAL:
            altpath: alternative goalpath
        }

    If an altpath is given, this will be used as the goalpath for this widget's
    checkbox. Otherwise the widget's own libpath will be used.
    """

    def __init__(self, name, label, data, anno, lineno):
        Widget.__init__(self, WidgetTypes.GOAL, name, label, data, anno, lineno)
        self.template_name = 'goal_widget_template'
        self.is_inline = True

    @classmethod
    def generate_arg_spec(cls):
        return {
            "OPT": {
                'altpath': {
                    'type': IType.RELPATH,
                },
            }
        }

    def check_fields(self):
        spec = self.generate_arg_spec()
        self.check(spec)

    def compute_origin(self, force=False):
        # If the origin was already given, don't bother to do anything (unless forcing).
        if 'origin' in self.data and not force:
            origin = self.data['origin']
        else:
            libpath = self.libpath
            altpath = self.data.get('altpath')
            origin = None
            if altpath:
                alt_repo = get_repo_part(altpath)
                own_repo = get_repo_part(self.libpath)
                if alt_repo == own_repo:
                    # The alternative goal comes from the same repo. So we can use
                    # the same major version, and just need to substitute the altpath.
                    libpath = altpath
                else:
                    # Must determine the major version and index type (Deduc, Node, Widget)
                    # of the alternative goal. Then can look up the origin using the GDB.
                    obj = self.objects_by_abspath[altpath]
                    label = obj.get_index_type()
                    major = obj.getMajorVersion()
                    origins = get_graph_reader().get_origins({label: [altpath]}, major)
                    if altpath not in origins:
                        raise PfscExcep(
                            (f'Could not find origin for goal path {altpath}.'
                             ' Have you built that repo yet?'),
                            PECode.MISSING_ORIGIN
                        )
                    origin = origins[altpath]
            if origin is None:
                origin = f'{libpath}@{self.getMajorVersion()}'
        self.origin = origin
        return origin

    def enrich_data(self):
        super().enrich_data()
        self.data['origin'] = self.compute_origin()


class ExampWidget(Widget):
    """
    Abstract class representing common functionality of widgets involved
    in examplorers.
    """

    def __init__(self, type_, name, label, data, anno, lineno):
        Widget.__init__(self, type_, name, label, data, anno, lineno)
        self.is_inline = False
        self.context_name = 'Basic'
        self._requested_imports = None
        self._generator = None
        self._trusted = None

    @classmethod
    def add_common_options_to_arg_spec(cls, spec):
        """
        Before returning the arg spec from their `generate_arg_spec()` method, subclasses
        should pass the spec to this method, to add the optional `context` arg.
        """
        spec["OPT"] = spec.get("OPT", {})
        spec["OPT"]['context'] = {
            'type': IType.STR,
            'default_cooked': 'Basic',
        }

    @property
    def requested_imports(self):
        # Note: This method is used (at least at present) only during the `enrich_data()`
        # phase, so it is correct to use `self.data` here.
        if self._requested_imports is None:
            self._requested_imports = self.data.get('import', {}).copy()
        return self._requested_imports

    @property
    def generator(self):
        if self._generator is None:
            self._generator = self.make_generator()
        return self._generator

    def make_generator(self):
        raise NotImplementedError

    @property
    def trusted(self):
        if self._trusted is None:
            assert (libpath := self.getLibpath()) is not None
            self._trusted = libpath_is_trusted(libpath)
        return self._trusted

    def raise_excep_if_untrusted(self):
        if not self.trusted:
            msg = 'Cannot evaluate examp widgets (Disp and Param) since repo is untrusted.'
            raise PfscExcep(msg, PECode.UNTRUSTED_REPO)

    @property
    def context(self):
        return self.context_name

    def get_examp_widget(self, libpath):
        """
        :param libpath: the absolute libpath of an ExampWidget named somewhere
          in the data for this widget
        :return: the ExampWidget itself
        """
        widget = self.objects_by_abspath.get(libpath)
        if widget is None:
            raise PfscExcep(f'Missing ExampWidget dependency {libpath}', PECode.EXAMP_WIDGET_DEPENDENCY_MISSING)
        if not isinstance(widget, ExampWidget):
            raise PfscExcep(f'{libpath} is not ExampWidget', PECode.EXAMP_WIDGET_WRONG_DEPENDENCY_TYPE)
        return widget

    def get_generator(self, libpath):
        widget = self.get_examp_widget(libpath)
        return widget.generator

    def enrich_data(self):
        super().enrich_data()
        if self.parent.get_index_type() == IndexType.SPHINX:
            # Since Sphinx pages are served statically, trust state isn't
            # injected at serve time; we record it instead at build time.
            self.data['trusted'] = self.trusted
        self.data['dependencies'] = self.compute_dependency_closure()
        self.context_name = self.data.get('context', 'Basic')

    def get_direct_dependencies(self):
        """
        Get the set of libpaths of all ExampWidgets that this widget uses
        directly, via imports.

        :return: list of libpaths
        """
        return list(self.requested_imports.values())

    def compute_dependency_closure(self):
        """
        Compute the list of all ExampWidgets that this one depends on,
        recursively, in topological order. (If B depends on A, then A comes
        before B in the list.)

        :return: list of dicts of the form {
            'libpath': the absolute libpath of an ExampWidget on which this one depends,
            'uid': the UID of that widget,
            'type': the `WidgetType` of that widget
            'direct': boolean, true iff the dependency is direct (i.e. one edge in dep graph)
        }
        """
        dep_graph = {}
        info_by_libpath = {}
        self._compute_dependency_closure_recursive(dep_graph, info_by_libpath, top_level=True)
        try:
            order = topological_sort(dep_graph, reversed=True)
        except PfscExcep as pe:
            if pe.code() == PECode.DAG_HAS_CYCLE:
                pe.extendMsg(f' Trying to resolve dependencies for widget {self.libpath}')
            raise pe
        closure = [info_by_libpath[lp] for lp in order if lp != self.libpath]
        return closure

    def _compute_dependency_closure_recursive(self, dep_graph, info_by_libpath, top_level=False):
        """
        Recursive, internal method used to compute the dependency closure.
        """
        dd = self.get_direct_dependencies()
        dep_graph[self.libpath] = dd[:]
        for lp in dd:
            w = self.objects_by_abspath.get(lp)
            if isinstance(w, (ParamWidget, DispWidget)):
                if top_level or (lp not in info_by_libpath):
                    info_by_libpath[lp] = {
                        'libpath': lp,
                        'uid': w.writeUID(),
                        'type': w.type_,
                        'direct': top_level,
                    }
            else:
                msg = f'Examp widget {self.libpath} depends on non-examp: {lp}'
                raise PfscExcep(msg, PECode.EXAMP_WIDGET_WRONG_DEPENDENCY_TYPE)
            if lp not in dep_graph:
                w._compute_dependency_closure_recursive(dep_graph, info_by_libpath, top_level=False)

    def write_evaluation_error_html(self, pe):
        return evaluation_error_template.render({
            'uid': self.writeUID(),
            'err_msg': str(pe),
        })


evaluation_error_template = jinja2.Template("""
<div class="widget dummyWidget {{ uid }}">
    <p>{{err_msg}}</p>
</div>

""")


class ParamWidget(ExampWidget):
    """
    Represents a parameter chooser in an examplorer.
    """

    def __init__(self, name, label, data, anno, lineno):
        ExampWidget.__init__(self, WidgetTypes.PARAM, name, label, data, anno, lineno)

    @classmethod
    def generate_arg_spec(cls):
        spec = {
            "REQ": {
                'ptype': {
                    'type': IType.STR,
                },
                'name': {
                    'type': IType.STR,
                },
                'default': {
                    'type': IType.ANY,
                },
            },
            "OPT": {
                'tex': {
                    'type': IType.STR,
                },
                'descrip': {
                    'type': IType.STR,
                },
                'import': {
                    'type': IType.DICT,
                    'keytype': {
                        'type': IType.STR,
                    },
                    'valtype': {
                        'type': IType.RELPATH,
                        'is_Libpath_instance': True,
                    },
                },
                'args': {
                    'type': IType.DICT,
                    'keytype': {
                        'type': IType.STR,
                    },
                    'valtype': {
                        'type': IType.ANY,
                    },
                },
            },
        }
        cls.add_common_options_to_arg_spec(spec)
        return spec

    def check_fields(self):
        spec = self.generate_arg_spec()
        self.check(spec)

    def make_generator(self):
        make_param = from_import('pfsc_examp', 'make_param')
        return make_param(self, self.writeData())

    def enrich_data(self):
        super().enrich_data()
        ri = self.requested_imports
        self.data['params'] = ri
        if 'import' in self.data:
            del self.data['import']

    def writeHTML(self, label=None, sphinx=False):
        html = f'<div class="widget exampWidget paramWidget {self.writeUID()}">\n'
        html += '<div class="exampWidgetErrMsg"></div>\n'
        html += '<div class="chooser_container">\n'  # <-- chooser HTML to be set as inner HTML here
        html += '</div>\n'
        html += (
            '<div class="exampWidgetOverlay">'
            '<div class="screen"></div>'
            '<div class="loadingIcon"><span class="pyodideLoading">Loading pyodide...</span></div>'
            '</div>\n'
        )
        html += '</div>\n'
        return html


class DispWidget(ExampWidget):
    """
    Represents a "display" in an examplorer.
    """

    def __init__(self, name, label, data, anno, lineno):
        ExampWidget.__init__(self, WidgetTypes.DISP, name, label, data, anno, lineno)

    @classmethod
    def generate_arg_spec(cls):
        spec = {
            "REQ": {
                'build': {
                    'type': IType.STR,
                },
            },
            "OPT": {
                'import': {
                    'type': IType.DICT,
                    'keytype': {
                        'type': IType.STR,
                    },
                    'valtype': {
                        'type': IType.RELPATH,
                        'is_Libpath_instance': True,
                    },
                },
                'export': {
                    'type': IType.LIST,
                    'itemtype': {
                        'type': IType.STR,
                    },
                },
            },
        }
        cls.add_common_options_to_arg_spec(spec)
        return spec

    def check_fields(self):
        spec = self.generate_arg_spec()
        self.check(spec)

    def make_generator(self):
        make_disp = from_import('pfsc_examp', 'make_disp')
        return make_disp(self, self.writeData())

    @staticmethod
    def split_build_code(build_code):
        """
        Split the build string into alternating fixed and user-editable
        segments, and validate the "begin"-"end" pairs.
        """
        parts = re.split(rf'({DISP_WIDGET_BEGIN_EDIT}|{DISP_WIDGET_END_EDIT})\n', build_code)

        def err():
            msg = 'Mismatched editable section markers in build code'
            raise PfscExcep(msg, PECode.MALFORMED_BUILD_CODE)

        n = len(parts)
        if n % 4 != 1:
            err()
        m = (n - 1) // 4
        for k in range(m):
            if (
                parts[4*k + 1] != DISP_WIDGET_BEGIN_EDIT or
                parts[4*k + 3] != DISP_WIDGET_END_EDIT
            ):
                err()

        return [parts[2*k] for k in range(2*m + 1)]

    def enrich_data(self):
        super().enrich_data()

        # Divide import directives into those for params and those for displays
        params = {}
        imports = {}
        for name, libpath in self.requested_imports.items():
            w = self.get_examp_widget(libpath)
            if isinstance(w, ParamWidget):
                params[name] = libpath
            else:
                assert isinstance(w, DispWidget)
                imports[name] = libpath
        self.data['params'] = params
        self.data['imports'] = imports
        if 'import' in self.data:
            del self.data['import']

        # Unescape build code
        build_code = self.data['build']
        if not isinstance(build_code, str):
            raise PfscExcep('Display build code must be string.')
        if not isinstance(build_code, Markup):
            build_code = Markup(build_code)
        build_code = build_code.unescape()

        # Split on "BEGIN EDIT" / "END EDIT" comments
        parts = self.split_build_code(build_code)

        self.data['build'] = parts

    def writeHTML(self, label=None, sphinx=False):
        html = f'<div class="widget exampWidget dispWidget {self.writeUID()}">\n'
        html += '<div class="dispWidgetInputArea">\n'
        html += '  <div class="dispWidgetEditors"></div>\n'
        html += '  <div class="exampWidgetErrMsg"></div>\n'
        html += '</div>\n'
        html += '<div class="dispWidgetOutputArea">\n'
        html += '  <div class="display_container">\n' # <-- display HTML to be set as inner HTML here
        html += '  </div>\n'
        html += '</div>\n'
        html += (
            '<div class="exampWidgetOverlay">'
            '<div class="screen"></div>'
            '<div class="loadingIcon"><span class="pyodideLoading">Loading pyodide...</span></div>'
            '</div>\n'
        )
        html += '</div>\n'
        return html

##############################################################################


class WidgetTypes:
    CTL = "CTL"
    CHART = "CHART"
    DISP = "DISP"
    LINK = "LINK"
    QNA = "QNA"
    LABEL = "LABEL"
    GOAL = "GOAL"
    PARAM = "PARAM"
    DOC = "DOC"


# We use a dictionary to map widget type names to subclasses of the Widget class.
# For example, CHART maps to the ChartWidget class.
WIDGET_TYPE_TO_CLASS = {
    WidgetTypes.CTL:   CtlWidget,
    WidgetTypes.CHART: ChartWidget,
    WidgetTypes.DISP:  DispWidget,
    WidgetTypes.LINK:  LinkWidget,
    WidgetTypes.QNA:   QnAWidget,
    WidgetTypes.LABEL: LabelWidget,
    WidgetTypes.GOAL:  GoalWidget,
    WidgetTypes.PARAM: ParamWidget,
    WidgetTypes.DOC:   DocWidget,
}

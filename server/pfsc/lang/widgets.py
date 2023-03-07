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

import re, json

from flask import escape, Markup
import jinja2

from pfsc.constants import (
    IndexType,
    DISP_WIDGET_BEGIN_EDIT, DISP_WIDGET_END_EDIT,
)
from pfsc.lang.freestrings import render_anno_markdown
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

def replace_data(data, datapaths, replacer, accept_absent=False):
    """
    Use this function to replace data at various places within a JSON object.

    Any location within a JSON object can be specified by a sequence of keys. When these keys (which
    should all be strings) are joined together with dots ("."), we refer to such a string as a "datapath".

    :param data: the JSON object in which data is to be replaced.

    :param datapaths: list of datapaths where replacement should occur.

                      The datapaths are interpreted as optional. This means the data they refer to need
                      not be present; but if it is, then we try to replace it.

    :param replacer: a function that accepts three arguments `(path, d, p)`, where `d` is an element
                     in the data, `p` its parent, and `path` the path that got us there.

                     Should either return the value by which `d` is to be replaced, or else
                     raise a `ValueError` if no replacement should be made after all.

    :param accept_absent: if True, then `replacer(path, None, p)` will be called in the case of a
                          datapath `path` every key of which was present _except the very last_.
                          In other words, this means we accept the case in which the item in question
                          is not defined, but its parent is.

    :return: nothing. The given data object is modified in-place.
    """
    for datapath in datapaths:
        keys = datapath.split('.')
        p = None
        d = data
        found_data = False
        n = len(keys)
        for i, key in enumerate(keys):
            try:
                p = d
                d = p[key]
            except TypeError:
                # This case can arise when multiple types are allowed for certain data members.
                # E.g. when updating the Forest in Moose, you can pass a string or a dict under
                # the `view` parameter. Therefore ChartWidgets consider both `view` and `view.objects`
                # as datapaths. If the user has set a string under the `view` parameter, then we
                # will get a `TypeError` when we examine the datapath `view.objects`.
                break
            except KeyError:
                if accept_absent and i == n - 1:
                    d = None
                else:
                    break
                # Error message to use if we do want to have "required" data at some point:
                #msg = "Key '%s' in datapath '%s' could not be located in data %s" % (
                #    key, datapath, data
                #)
                #raise PfscExcep(msg)
        else:
            # Only if we did _not_ break out of the above loop do we conclude that we
            # did manage to find some data.
            found_data = True
        # There is (at least for now) no "required" data; if we found nothing under a given
        # datapath, we just move on.
        if not found_data: continue
        # At this point, `d` should be the item pointed to by the datapath,
        # `p` should be that item's parent, and `key` should satisfy `p[key] = d`.
        try:
            r = replacer(datapath, d, p)
        except ValueError:
            # The replacer function can raise a ValueError to indicate that it doesn't
            # actually want to replace the data item after all.
            pass
        else:
            p[key] = r

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
        # Enrich the data object with the typename and lineno of the widget.
        data["type"] = type_
        data["src_line"] = self.get_lineno_within_module()
        self.data = data
        # In order to resolve relative libpaths, widget subclasses need only specify in this
        # field the "datapaths" where libpaths can (optionally) be found in their data.
        # See doctext for the `resolve_libpaths_in_data` method of this class, for more details.
        self.libpath_datapaths = []
        # Slot for recording the list of all repopaths implicated by the libpaths:
        self.repos = []
        # A lookup for referenced objects, by absolute libpath:
        self.objects_by_abspath = {}

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

    def set_pane_group(self, default_group_name=''):
        group_name = self.data.get('group', default_group_name)
        pane_group = ":".join([
            make_repo_versioned_libpath(self.parent.libpath, self.getVersion()),
            self.get_type(),
            str(group_name)
        ])
        self.data['pane_group'] = pane_group

    def check_required_fields(self, req):
        for rf in req:
            if rf not in self.data:
                msg = 'Widget %s is missing required "%s" field.' % (self.name, rf)
                raise PfscExcep(msg, PECode.WIDGET_MISSING_REQUIRED_FIELD)

    def cascadeLibpaths(self):
        PfscObj.cascadeLibpaths(self)
        self.data['widget_libpath'] = self.libpath

    def resolveLibpathsRec(self):
        self.repos = self.resolve_libpaths_in_data(self.libpath_datapaths)
        for item in self.items.values():
            if callable(getattr(item, 'resolveLibpathsRec', None)):
                item.resolveLibpathsRec()

    def getRequiredRepoVersions(self, loading_time=True):
        # Get ahold of the desired version for each repo implicated by libpaths
        # in this widget's data.
        extra_msg = f' Required by widget `{self.libpath}`.'
        return {
            r: self.getRequiredVersionOfObject(r, extra_err_msg=extra_msg, loading_time=loading_time)
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

    def writeHTML(self, label=None):
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

    def enrich_data(self):
        """
        Subclasses may wish to add fields atop those supplied by the user.
        This method will be called after libpaths have cascaded, and after
        libpaths within this widget's data have been resolved. In fact we
        call it as late as possible, right before writing the data to disk
        in the build process. In particular this means the enclosing Module
        will already know its represented version.
        """
        self.data['uid'] = self.writeUID()

    def resolve_libpath(self, libpath):
        """
        Given a libpath, which may (or may not) be relative, resolve it to an absolute libpath.

        This method also achieves the critical side effect of checking that the
        object referenced by the libpath is actually present in the module in which
        the widget lives (whether defined there or imported into there). This is
        necessary so that we can know the repo to which the object belongs, and hence
        the version at which we're taking it (based on the declared dependencies of the
        repo being built).

        :param libpath: The libpath to be resolved. May be relative or absolute.
        :return: The absolute libpath to which the given one resolves.
        :raises: PfscExcep if relative libpath cannot be resolved.
        """
        if libpath in self.objects_by_abspath:
            # This already is an absolute path to which we have resolved sth.
            return libpath
        obj, ancpath = self.getFromAncestor(libpath, missing_obj_descrip=f'named in widget {self.getLibpath()}')
        abspath = obj.getLibpath()
        self.objects_by_abspath[abspath] = obj
        return abspath

    def resolve_multipath(self, multipath):
        """
        Given a multipath, which may (or may not) be relative, resolve it to a list of absolute libpaths.
        @param multipath: The multipath to be resolved. May be relative or absolute; may be a plain libpath.
        @return: List of absolute libpaths.
        @raise: PfscExcep if any relative libpath cannot be resolved.
        """
        libpaths = expand_multipath(multipath)
        return [self.resolve_libpath(lp) for lp in libpaths]

    def resolve_libpaths_in_data(self, datapaths):
        """
        The data defining a widget may contain relative libpaths which must be interpreted relative
        to the module in which the widget lives. It is important that all such libpaths be resolved
        to absolute ones, for use by the front-end.

        Depending on the type of widget, libpaths might be found at various places in the data.
        But since the data takes the form of a JSON object, any location within it can be specified by
        a sequence of keys. We refer to such a sequence of keys as a "datapath".

        Therefore it is up to the various widget types to use this method, passing it a list of datapaths
        where libpaths may be found, so that they can be resolved.

        Each datapath should point to a string, a list, or a dict. These should be, respectively, a multipath,
        a list of multipaths, or a dict in which all values are multipaths or lists of multipaths.
        See doctext for the `expand_multipath` function for precise defn of a multipath.

        When a multipath is encountered as a string, it will remain a string when resolved, provided it expands
        to just a single libpath; otherwise it will be replaced by a list of libpaths.

        When a multipath is encountered within a list, that list will be replaced by the list of all libpaths to
        which its elements resolve. I.e. it will be flattened after expansion of its elements.

        For example, if multipath M expands to libpaths L1, L2, then

            M --> [L1, L2]              (string replaced by list)

        whereas

            [M, L3] --> [L1, L2, L3]    (list remains list).

        :param datapaths: list of datapaths pointing to strings, lists or dicts in the data, as described above.
        :return: self.data is modified in-place; our return value is the set of
          repo parts of all libpaths resolved.
        """
        # A "multipath or list thereof" is a "boxlisting".
        # We write a utility function here which resolves all libpaths within a boxlisting,
        # and which returns a string when possible, and a list otherwise.
        repos = set()
        def resolve_boxlisting(d):
            if isinstance(d, str):
                L = self.resolve_multipath(d)
                r = L if len(L) > 1 else L[0]
            elif isinstance(d, list):
                r = sum([self.resolve_multipath(m) for m in d], [])
            else:
                raise ValueError
            if isinstance(r, str):
                repos.add(get_repo_part(r))
            else:
                assert isinstance(r, list)
                repos.update(set(get_repo_part(lp) for lp in r))
            return r
        def replacer(path, d, p):
            try:
                # `d` should be either a boxlisting itself, or a dict in which (some of) the values are boxlistings.
                if isinstance(d, str) or isinstance(d, list):
                    r = resolve_boxlisting(d)
                elif isinstance(d, dict):
                    r = {}
                    for k in d:
                        try:
                            p = resolve_boxlisting(d[k])
                        except ValueError:
                            r[k] = d[k]
                        else:
                            r[k] = p
                else:
                    raise ValueError
            except PfscExcep as pe:
                raise pe
            except:
                raise ValueError
            else:
                return r
        replace_data(self.data, datapaths, replacer)
        return repos

class UnknownTypeWidget(Widget):

    def __init__(self, name, label, data, anno, lineno):
        Widget.__init__(self, "<unknown-type>", name, label, data, anno, lineno)


class CtlWidget(Widget):
    """
    A widget for passing control codes to control the Markdown rendering.

    Currently supported options:

        section_numbers: {
            on: boolean (default True),
            top_level: int from 1 to 6 (default 1), indicating at what heading
                level numbers should begin to be automatically inserted
        }

    If `section_numbers` is defined at all, then its `on` property defaults to
    True; but, until a CtlWidget is found that switches section numbering on, it
    is off.
    """

    def __init__(self, name, label, data, anno, lineno):
        Widget.__init__(self, WidgetTypes.CTL, name, label, data, anno, lineno)
        self.check_data()

    @staticmethod
    def malformed(detail):
        msg = 'Malformed control widget. '
        msg += detail
        raise PfscExcep(msg, PECode.MALFORMED_CONTROL_WIDGET)

    def check_data(self):
        """
        Check that the passed control codes/cmds are well-formed.
        This method can evolve as we add more options.
        """
        sn = self.data.get('section_numbers')
        if sn is not None:
            if not isinstance(sn, dict):
                raise self.malformed('section_numbers must be dict')
            c_on = sn.get('on')
            if c_on is not None:
                if not isinstance(c_on, bool):
                    raise self.malformed('section_numbers.on must be boolean')
            else:
                sn['on'] = True
            c_top_level = sn.get('top_level')
            if c_top_level is not None:
                if not isinstance(c_top_level, int) or c_top_level < 1 or c_top_level > 6:
                    raise self.malformed('section_numbers.top_level must be int from 1 to 6')
            else:
                sn['top_level'] = 1

    def configure(self, renderer):
        sn = self.data.get('section_numbers')
        if sn is not None:
            renderer.sn_do_number = sn.get('on')
            renderer.sn_top_level = sn.get('top_level')


chart_widget_template = jinja2.Template("""<a class="widget chartWidget {{ uid }}" href="#">{{ label }}</a>""")

class ChartWidget(Widget):
    """
    A Widget class for controlling Chart views.
    """

    def __init__(self, name, label, data, anno, lineno):
        Widget.__init__(self, WidgetTypes.CHART, name, label, data, anno, lineno)
        self.libpath_datapaths = (
            "on_board",
            "off_board",
            "view",
            "view.objects",
            "view.core",
            "view.center",
            "color",
            "hovercolor",
            "select",
            "checkboxes.deducs",
            "checkboxes.checked",
        )

    def enrich_data(self):
        super().enrich_data()
        self.set_pane_group()
        self.data['versions'] = self.getRequiredRepoVersions(loading_time=False)
        self.data['title_libpath'] = self.parent.libpath
        self.data['icon_type'] = 'nav'
        self.set_up_hovercolor()

    def set_up_hovercolor(self):
        """
        NOTE: hovercolor may only be used with _node_ colors -- not _edge_ colors.

        If user has requested hovercolor, we enrich the data for ease of
        use at the front-end.

        Under `hovercolor`, the user provides an ordinary `color` request.
        The user should _not_ worry about using any of `update`, `save`, `rest`;
        we take care of all of that. User should just name the colors they want.

        We transform the given color request so that under `hovercolor` our data
        instead features _two_ ordinary color requests: one called `over` and one
        called `out`. These can then be applied on `mouseover` and `mouseout` events.
        """
        hc_name = 'hovercolor'
        if hc_name in self.data:
            hc = self.data[hc_name]
            # Data for mouseover:
            over = {':update': True}
            def set_prefix(s):
                if s[0] != ":": return s
                return f':save:tmp{s}'
            for k, v in hc.items():
                k, v = map(set_prefix, [k, v])
                over[k] = v
            # Data for mouseout:
            out = {':update': True}
            def do_weak_restore(s):
                if s[0] != ":": return s
                return f':wrest'
            for k, v in hc.items():
                k, v = map(do_weak_restore, [k, v])
                out[k] = v
            self.data[hc_name] = {
                'over': over,
                'out': out
            }

    def writeHTML(self, label=None):
        if label is None: label = escape(self.label)
        context = {
            'label': label,
            'uid': self.writeUID()
        }
        return chart_widget_template.render(context)

pdf_widget_template = jinja2.Template("""<a class="widget pdfWidget {{ uid }}" tabindex="-1" href="#">{{ label }}</a>""")

class PdfWidget(Widget):
    """
    A Widget class for controlling PDF panes.
    """

    def __init__(self, name, label, data, anno, lineno):
        Widget.__init__(self, WidgetTypes.PDF, name, label, data, anno, lineno)
        self.docReference = None

    def enrich_data(self):
        super().enrich_data()
        self.set_pane_group()

        doc_info_obj = None
        doc_info_libpath = None

        doc_field_name = 'doc'
        sel_field_name = 'selection'
        hid_field_name = 'highlightId'

        doc_field_value = self.data.get(doc_field_name)
        code = self.data.get(sel_field_name)

        try:
            if code is None and doc_field_value is None:
                msg = 'Failed to define doc info under `doc` or `selection`'
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
                code=code, doc_info_obj=doc_info_obj,
                context=self.parent, doc_info_libpath=doc_info_libpath
            )
        except PfscExcep as e:
            e.extendMsg(f'in pdf widget {self.libpath}')
            raise

        # Clean up. Doc descriptors go at top level of anno.json; don't need
        # to repeat them in each pdf widget.
        if doc_field_name in self.data:
            del self.data[doc_field_name]

        doc_info = self.docReference.doc_info

        # Final widget data needs docId. We extract it from the doc info.
        doc_id_field_name = 'docId'
        self.data[doc_id_field_name] = doc_info[doc_id_field_name]

        # Do we define a doc highlight?
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

    def writeHTML(self, label=None):
        if label is None: label = escape(self.label)
        context = {
            'label': label,
            'uid': self.writeUID()
        }
        return pdf_widget_template.render(context)


link_widget_template = jinja2.Template("""<a class="widget linkWidget {{ uid }}" href="#">{{ label }}</a>""")

class LinkWidget(Widget):
    """
    Link widgets are for making a link to another annotation, or directly to
    a particular widget within an annotation.

    Fields:

        ref: the libpath of the annotation or widget to which you wish to link

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
        # FIXME:
        #  We really should be using the checkinput module to check given
        #  parameters, set default values, etc.
        defaults = {
            'tab': 'existing'
        }
        defaults.update(data)
        data = defaults
        Widget.__init__(self, WidgetTypes.LINK, name, label, data, anno, lineno)
        self.check_required_fields(["ref"])
        self.libpath_datapaths = (
            "ref",
        )

    def enrich_data(self):
        super().enrich_data()
        # Determine the type of thing the ref points to.
        # It should be either an annotation or a widget.
        target_libpath = self.data['ref']
        target_annopath = get_formal_moditempath(target_libpath)
        target_type = "ANNO" if target_libpath == target_annopath else "WIDG"
        self.data["annopath"] = target_annopath
        target_version = self.getRequiredVersionOfObject(target_annopath, loading_time=False)
        self.data["target_version"] = target_version
        self.data['target_type'] = target_type
        if target_type == "WIDG":
            self.data['target_selector'] = '.' + make_widget_uid(target_libpath, target_version)

    def writeHTML(self, label=None):
        if label is None: label = escape(self.label)
        context = {
            'label': label,
            'uid': self.writeUID()
        }
        return link_widget_template.render(context)

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

    # Required fields:
    QUESTION = 'question'
    ANSWER = 'answer'

    required_fields = [QUESTION, ANSWER]

    def __init__(self, name, label, data, anno, lineno):
        Widget.__init__(self, WidgetTypes.QNA, name, label, data, anno, lineno)
        self.check_required_fields(QnAWidget.required_fields)
        self.question = data[QnAWidget.QUESTION]
        self.answer   = data[QnAWidget.ANSWER]

    def writeHTML(self, label=None):
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

    Subclasses may write their own writeHTML method, or, if it suffices, simply set self.template,
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

    def writeHTML(self, label=None):
        context = {
            'tag': self.tag,
            'contents': self.contents,
            'uid': self.writeUID()
        }
        return self.template.render(context)


label_widget_template = jinja2.Template("""<{{tag}} class="widget labelWidget {{ uid }}">{{contents}}<span class="labellink">¶</span></{{tag}}>""")

class LabelWidget(WrapperWidget):
    """
    Label widgets are intended as a means to mark a location in an annotation,
    so that it is possible to link to that spot.

    Format:

        <label:>[LABEL]{}
    """

    def __init__(self, name, label, data, anno, lineno):
        Widget.__init__(self, WidgetTypes.LABEL, name, label, data, anno, lineno)
        self.template = label_widget_template


goal_widget_template = jinja2.Template("""<{{tag}} class="widget goalWidget {{ uid }}"><span class="graphics"></span>{{contents}}</{{tag}}>""")

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
        self.template = goal_widget_template
        self.libpath_datapaths = [
            'altpath'
        ]

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
        self.context_name = self.data.get('context', 'Basic')
        self.libpath_datapaths = (
            'import',
        )
        self._requested_imports = None
        self._generator = None
        self._trusted = None

    @property
    def requested_imports(self):
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
        self.data['dependencies'] = self.compute_dependency_closure()

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
        order = topological_sort(dep_graph, reversed=True)
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
        self.check_required_fields(['ptype', 'name'])

    def make_generator(self):
        make_param = from_import('pfsc_examp', 'make_param')
        return make_param(self, self.writeData())

    def enrich_data(self):
        super().enrich_data()
        ri = self.requested_imports
        self.data['params'] = ri
        if 'import' in self.data:
            del self.data['import']

    def writeHTML(self, label=None):
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
        self.check_required_fields(['build'])

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

    def writeHTML(self, label=None):
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
    PDF = "PDF"


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
    WidgetTypes.PDF:   PdfWidget,
}

# --------------------------------------------------------------------------- #
#   Sphinx-Proofscape                                                         #
#                                                                             #
#   Copyright (c) 2022-2023 Proofscape contributors                           #
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

from collections import defaultdict

from docutils.parsers.rst.directives import unchanged
from sphinx.errors import SphinxError

from pfsc.lang.widgets import set_up_hovercolor
from pfsc.sphinx.sphinx_proofscape.nav_widgets import (
    PfscNavWidgetRole, PfscNavWidgetDirective,
)
from pfsc.sphinx.sphinx_proofscape.util import (
    build_libpath, parse_box_listing, find_lp_defn_for_docname,
    ResolvedLibpath,
)


class SphinxChartWidget:
    """
    FIXME:
     Can we refactor, and base more of this on the widget classes
     defined in pfsc.lang.widgets?
    """

    def __init__(self, config, lp_defns, vers_defns,
                 docname, src_file, lineno, name, **fields):
        self.sphinx_config = config
        self.lp_defns = lp_defns
        self.vers_defns = vers_defns
        self.docname = docname
        self.src_file = src_file
        self.lineno = lineno
        self.name = name

        # Here we will record for each repopath (key) the version at which we
        # are taking it (value).
        self.versions = {}

        self.libpath = build_libpath(config, docname, extension=name)
        self.pane_group = build_libpath(config, docname, add_repo_version=True) + ':CHART:'
        self.given_fields = fields
        self.resolved_fields = self.resolve_fields(fields)

    @property
    def repopath(self):
        return self.sphinx_config.pfsc_repopath

    @property
    def repovers(self):
        return self.sphinx_config.pfsc_repovers

    def get_location(self):
        return ':'.join(str(s) for s in [self.src_file, self.lineno])

    def write_uid(self):
        return f"{self.libpath.replace('.', '-')}_{self.repovers}"

    def write_info_dict(self):
        info = self.resolved_fields.copy()
        info.update({
            'pane_group': self.pane_group,
            'src_line': self.lineno,
            'type': "CHART",
            'uid': self.write_uid(),
            'version': self.repovers,
            'widget_libpath': self.libpath,
        })
        return info

    def resolve_fields(self, fields):
        rf = {}
        versions = {}

        # TODO:
        #  Implement the full set of possibilities for each of these fields.
        #  See `TransitionManager` class in pfsc-moose.
        #  For now, we simply accept a boxlisting for each field.
        for name in ["on_board", "off_board", "view", "select"]:
            box_listing = fields.get(name)
            if box_listing:
                rf[name] = self.resolve_boxlisting(box_listing)

        for name in ["color", "hovercolor"]:
            raw = fields.get(name)
            if raw:
                update = False
                data = defaultdict(set)
                lines = [L.strip() for L in raw.split('\n')]
                for line in lines:
                    if line == 'update' and name == 'color':
                        update = True
                        continue
                    parts = [p.strip() for p in line.split(":")]
                    if len(parts) != 2:
                        raise SphinxError(f'{self.get_location()}: each line in the :{name}: option'
                                          ' should have a single colon (:), with a comma-separated list'
                                          ' of color codes on the left, and a boxlisting on the right.')
                    color_spec, box_listing = parts
                    color_codes = [c.strip() for c in color_spec.split(',')]
                    # Restore the leading colons expected by our old code.
                    k = ":" + ":".join(color_codes)
                    v = self.resolve_boxlisting(box_listing)
                    data[k].update(set(v))
                # Sort for deterministic output. Good for testing.
                data = {k: list(sorted(list(v))) for k, v in data.items()}

                if name == "hovercolor":
                    rf[name] = set_up_hovercolor(data)
                else:
                    if update:
                        data[':update'] = True
                    rf[name] = data

        rf['versions'] = self.versions.copy()
        return rf

    def resolve_boxlisting(self, box_listing):
        given_lps = parse_box_listing(box_listing)
        resolved_lps = []
        for lp in given_lps:
            rlp = self.resolve_libpath(lp)
            if rlp.repopath in self.versions:
                if rlp.version != (v := self.versions[rlp.repopath]):
                    raise SphinxError(f'Multiple versions {rlp.version},'
                                      f' {v} declared for {rlp.repopath}')
            else:
                self.versions[rlp.repopath] = rlp.version
            resolved_lps.append(rlp.libpath)
        return resolved_lps

    def resolve_libpath(self, given_path):
        """
        Given a (possibly relative, possibly absolute) libpath, and the dictionaries
        of libpath definitions and version definitions for a document, resolve the
        libpath. This means substituting for the first segment, if it has a definition,
        and determining the required version for the repo to which the absolute
        libpath belongs.

        If you do not want resolution from relative to absolute to be attempted,
        you can begin the given libpath with a dot ('.').
        """
        if not given_path:
            raise SphinxError(f'{self.get_location()}: Empty libpath')
        segs = given_path.split('.')
        s0 = segs[0]
        if s0 == '':
            # Given path began with dot. Do not try to substitute.
            segs = segs[1:]
        else:
            prefix = find_lp_defn_for_docname(self.lp_defns, s0, self.docname)
            if prefix:
                segs = prefix.split('.') + segs[1:]
        if len(segs) < 3:
            raise SphinxError(f'{self.get_location()}: Short libpath: {".".join(segs)}')
        repopath = '.'.join(segs[:3])
        if not repopath in self.vers_defns:
            raise SphinxError(f'{self.get_location()}: Missing version declaration for repo: {repopath}')
        version = self.vers_defns[repopath]
        libpath = '.'.join(segs)
        return ResolvedLibpath(libpath, repopath, version)


class PfscChartRole(PfscNavWidgetRole):
    """
    Example:

        Let's open :pfsc-chart:`the proof <libpath.of.some.proof>`.
    """
    widget_class = SphinxChartWidget
    html_class = 'chartWidget'
    widget_type_name = 'chart'
    target_field_name = 'view'


class PfscChartDirective(PfscNavWidgetDirective):
    r"""
    Full, directive syntax for chart widgets.

    Label text must be passed via exactly one of two ways: either as the one
    optional argument of the directive, or else via the 'alt' option.
    Note that, if we are defined under an rST substitution,
    (see https://docutils.sourceforge.io/docs/ref/rst/restructuredtext.html#substitution-definitions)
    then the 'alt' option will be automatically set equal to the inner text of
    the substitution.

    Label Rule
    ==========

    The label follows our general rule for widget labels, regarding optional
    definition of a widget name at the beginning. See the docs.

    Example: In

        Let's open the |w001: proof|.

        .. |w001: proof| pfsc-chart::
            :view: Pf
            :color:
                bgB: Pf.A03

    the widget name will be `w001`, while the label text will be "proof".

    Current support
    ===============

    The intention is to support the same options that are supported by chart
    widgets in the classic annotation syntax; however,
        * At this time, support is incomplete.
        * The syntax is somewhat different.
    See below.

    * Each of the `on_board`, `off_board`, `view`, and `select` fields
      can receive only a boxlisting. This means:
        - None of these fields can yet receive any keywords (e.g. "all" for `off_board`).
        - The `view` option cannot yet receive its more advanced format, where
          a whole dictionary is passed.
    * The `color` and `hovercolor` fields are fully supported.

    Syntax
    ======

    Generally, the goal is to take advantage of the possibilities of rST, to make
    a nicer, easier syntax than is available in annotations. In the latter, we
    are constrained by JSON format; here we are not.

    Boxlistings
    -----------

    There is no need for surrounding brackets to make a list, or
    for quotation marks to make a string. Thus, for example, you may write

        :view: Thm.A10, Pf.{A10,A20}

    which is equivalent to `view: ["Thm.A10", "Pf.{A10,A20}"]` in the old,
    annotation syntax.

    Color / Hovercolor
    ------------------

    In the old annotation syntax, this is defined by a dictionary
    of key-value pairs. Because keys must be unique there, we allowed the keys
    to be either color codes, or multipaths.

    Here, you should instead give a listing of `colorCodes: boxlisting` pairs,
    one per line.

    Because there is no unique-key constraint, there is no reason to allow
    multipaths on the left. (For annotations, we decided you might want to be
    able to use the same color spec twice, without having to make a giant RHS,
    so we allowed the option of putting the libpaths on the LHS.)
    Therefore color codes should always be on the left, boxlistings on the right.

    Since multipaths are no longer allowed on the left, there is no longer a
    need to disambiguate between color codes and libpaths, and therefore color
    codes no longer need to be preceded by colons. On the contrary, in rST we
    don't want color codes to begin and end with colons, since this would be
    recognized by syntax highlighters as being a part of rST.

    Therefore color codes should simply be separated by commas.

    As in the old annotation syntax, we support the special `update` color code,
    which applies to the whole directive, and therefore does not need any
    righthand side.

    Example:

        update
        push,bgR,olY,fi0,diGB: libpath.to.node1

    which means:

        Do not clear existing colors; simply add the given settings.
        For node1:
            - push current colors onto node1's color stack
            - set background red
            - set outline yellow
            - clear any existing colors from incoming flow edges
            - give incoming deduction edges a gradient from green to blue

    Note that `update` is meaningless in hovercolor, which is always done as
    an update.

    See the docstring for the ColorManager class in pfsc-moose for more info.

    """
    widget_class = SphinxChartWidget
    html_class = 'chartWidget'
    option_spec = {
        **PfscNavWidgetDirective.option_spec,
        "on_board": unchanged,
        "off_board": unchanged,
        "view": unchanged,
        "color": unchanged,
        "hovercolor": unchanged,
        "select": unchanged,
    }

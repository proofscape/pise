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

from pfsc.checkinput import check_boxlisting
from pfsc.lang.widgets import ChartWidget
from pfsc.sphinx.sphinx_proofscape.widgets.nav_widgets import PfscNavWidgetRole
from pfsc.sphinx.sphinx_proofscape.widgets.base import PfscOneArgWidgetDirective
from pfsc.sphinx.sphinx_proofscape.widgets.util import parse_box_listing


def regularize_color_option_text(raw, location, option_name):
    """
    Transform the raw text of a "color option" (``color`` or ``hovercolor``)
    into the format expected by the ChartWidget class.

    :param raw: the raw text
    :param location: a string giving the location of the option. For example,
        coule be based on the `src_file` and `lineno` returned by
        `self.get_source_info()`, where `self` is the `PfscChartDirective`
        whose option value this is
    :param option_name: the name of the option, such as "color" or "hovercolor"
    """
    update = False
    data = defaultdict(set)
    lines = [L.strip() for L in raw.split('\n')]
    for line in lines:
        if line == 'update' and option_name == 'color':
            update = True
            continue
        parts = [p.strip() for p in line.split(":")]
        if len(parts) != 2:
            raise SphinxError(f'{location}: each line in the :{option_name}: option'
                              ' should have a single colon (:), with a comma-separated list'
                              ' of color codes on the left, and a boxlisting on the right.')
        color_spec, box_listing = parts
        color_codes = [c.strip() for c in color_spec.split(',')]
        # Restore the leading colons expected in the old format.
        k = ":" + ":".join(color_codes)
        v = parse_box_listing(box_listing)
        data[k].update(set(v))
    # Sort for deterministic output. Good for testing.
    data = {k: list(sorted(list(v))) for k, v in data.items()}

    if option_name == "hovercolor":
        #result = set_up_hovercolor(data)  # ChartWidget class does this
        result = data
    else:
        if update:
            data[':update'] = True
        result = data

    return result


class PfscChartRole(PfscNavWidgetRole):
    """
    Role syntax for chart widgets.

    Interpreted text takes the form:

        LABEL <VIEW>

    where VIEW is the same as the `view` field in the directive syntax for
    chart widgets.

    Example:

        Let's open :pfsc-chart:`the proof <libpath.of.some.proof>`.
    """
    widget_class = ChartWidget
    widget_type_name = 'chart'
    target_field_name = 'view'


class PfscChartDirective(PfscOneArgWidgetDirective):
    r"""
    Directive syntax for chart widgets.


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

    Keywords may be passed surrounded by angle brackets, as in

        <all>

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
    widget_class = ChartWidget

    label_required = True

    option_spec = {
        **PfscOneArgWidgetDirective.option_spec,
        "on_board": unchanged,
        "off_board": unchanged,

        'view': lambda t: check_boxlisting('view', t, {
            'allowed_keywords': ['all'],
            'libpath_type': {
                'short_okay': True,
            }
        }).get_libpaths(),

        'color': lambda t: regularize_color_option_text(t, '', 'color'),

        'hovercolor': lambda t: regularize_color_option_text(t, '', 'hovercolor'),

        "select": unchanged,
    }

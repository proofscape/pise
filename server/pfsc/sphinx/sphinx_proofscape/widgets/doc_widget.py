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

from docutils.parsers.rst.directives import unchanged

from pfsc.lang.widgets import PdfWidget
from pfsc.sphinx.sphinx_proofscape.widgets.nav_widgets import PfscNavWidgetRole
from pfsc.sphinx.sphinx_proofscape.widgets.base import PfscOneArgWidgetDirective


class PfscPdfWidgetRole(PfscNavWidgetRole):
    """
    Role syntax for doc widgets.

    Interpreted text takes the form:

        LABEL <SEL>

    where SEL is the same as the `sel` field in the directive syntax for
    doc widgets.

    Example:

        Compare :pfsc-doc:`the original proof <doc1#v2;s3;(1:1758:2666:400:200:100:50)>`.
    """
    widget_class = PdfWidget
    widget_type_name = 'pdf'
    target_field_name = 'sel'


class PfscPdfWidgetDirective(PfscOneArgWidgetDirective):
    """
    Directive syntax for PDF widgets.

    Fields
    ======

    * **doc:** A specification of the referenced document.
      Accepted forms:
      - dict: The entire doc descriptor itself.
      - str: A libpath where the doc descriptor can be found.
      - undefined: Acceptable only if doc reference is made in the ``sel``
        field

    * **sel:** A selection within the document.
      Accepted forms:
      - libpath: Must point to a node within some deduction. Then this
        doc widget will point to the same selection made by the doc ref of that
        node.
      - str: Can be a pure combiner code, or a 2-part ref code of the form
        ``{ref}#{combiner_code}``. The 2-part form is required if the ``doc``
        field (see above) is undefined.

    """
    widget_class = PdfWidget

    label_required = True

    option_spec = {
        **PfscOneArgWidgetDirective.option_spec,
        "doc": unchanged,
        "sel": unchanged,
    }

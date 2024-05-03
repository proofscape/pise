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

import re, json

from markupsafe import Markup

from pfsc.lang.widgets import LinkWidget
from pfsc.lang.freestrings import MathRenderer, PfscRenderer, lookup_link_and_img_policy, Libpath
from pfsc.build.lib.libpath import expand_multipath
from pfsc.excep import PfscExcep, PECode
from pfsc.util import unindent

KNOWN_PROTOCOLS = re.compile(r'(notes|https?):')


class NodeLabelRenderer(PfscRenderer):
    """
    Do markdown processing for node labels.

    The links may be of various special types:

    * If the URL begins with our custom `notes:` protocol, then we interpret it
    as a link to an annotation or widget.

    * If the URL looks like a set of libpaths (or multipaths), we interpret it as
    one of Moose's classic "node links".

    In the future we will likely support other custom protocols.
    """

    def __init__(self, node):
        trusted = getattr(node.getDeduction(), 'trusted', False)
        allow_links, allow_images = lookup_link_and_img_policy(trusted)
        super().__init__({}, allow_links=allow_links, allow_images=allow_images)
        self.node = node
        self.nextLinkNum = 0

    def take_next_link_num(self):
        """
        At least for now, it looks like we're leveraging our existing Widget
        subclasses in order to set up the data for custom link protocols.
        So that these widgets can have names, we make a "link number" sequence.
        """
        n = self.nextLinkNum
        self.nextLinkNum = n + 1
        return n

    def render_auto_link(self, token):
        return self.render_link(token)

    def render_link(self, token):
        label = self.render_inner(token)
        url = token.target
        M = KNOWN_PROTOCOLS.match(url)
        if M is None:
            return processAsLibpaths(url, label, self.node)
        protocol = M.group()[:-1]
        if protocol == 'notes':
            n = self.take_next_link_num()
            return writeAnnolinkHTML(url, label, self.node, n)
        else:
            assert protocol in ['http', 'https']
            return super().render_link(token)

    # --------------------------------------------------------------------
    # Our superclass blocks html pass-through, but we need to allow it,
    # because we typically will already have added some html (such as <br> tags)
    # to the node label text. It is okay, because it was already html-escaped
    # _before_ those additions.
    def render_html_span(self, token):
        h = MathRenderer.render_html_span(token)
        return h

    def render_html_block(self, token):
        h = MathRenderer.render_html_block(token)
        return h
    # --------------------------------------------------------------------


def processAsLibpaths(url, label, node):
    from pfsc.lang.deductions import Deduction, Node
    # URL should be a semicolon-delimited list of multipaths.
    mps = url.split(';')
    rel_lps = sum(map(expand_multipath, mps), [])
    abspaths = []
    versions = {}
    for rlp in rel_lps:
        obj = node.resolveRelpathToRealOrClone(rlp)
        if isinstance(obj, Deduction) or isinstance(obj, Node):
            abspath = obj.getLibpath()
            version = obj.getVersion()
            abspaths.append(abspath)
            versions[abspath] = version
        else:
            msg = f'Cannot resolve node link target for: {rlp}'
            raise PfscExcep(msg, PECode.CANNOT_RESOLVE_NODE_LINK_TARGET)
    return writeNodelinkHTML(label, abspaths, versions)


def writeNodelinkHTML(label, libpaths, versions):
    """
    Write the HTML for a nodelink.
    @param label: The label to be displayed.
    @param libpaths: list of linked nodepaths,
    @param versions: the desired versions of the linked nodepaths.
    @return: the full HTML
    """
    d = json.dumps({
        'libpaths': libpaths,
        'versions': versions,
    })
    h = '<span class="nodelink">%s<span class="nodelinkInfo" style="display:none;">%s</span></span>' % (
        label, d
    )
    return h


def writeAnnolinkHTML(url, label, node, link_num):
    libpath_str = url[len('notes:'):]
    libpath = Libpath(libpath_str)
    lw = LinkWidget(f'_x{link_num}', '', {'ref': libpath, 'tab': 'other'}, node, 0)
    lw.cascadeLibpaths()
    lw.resolve()
    lw.enrich_data()
    data = lw.writeData()
    d = json.dumps(data)
    h = '<span class="annolink customlink">%s<span class="annolinkInfo" style="display:none;">%s</span></span>' % (
        label, d
    )
    return h


def ll(text):
    """
    Function for processing multi-line node labels.
      (1) strips off any leading and trailing newlines
      (2) ignores newlines within math mode (delimited by "$" or "$$")
      (3) takes indentation of first nonempty line as basic; adds &nbsp; chars
          for any additional spaces on the left of subsequent lines.
          All tab characters are expanded to 4 spaces.
    Its name 'll' should be thought of as 'lines'.
    """
    # First step: When a newline occurs in math mode, replace it and all
    # subsequent whitespace by a single space.
    state = 0
    t = ''
    N = len(text)
    p = -1
    while p+1 < N:
        p += 1
        c = text[p]
        if state==0:
            # Waiting for math mode to start.
            t += c
            if c=="$":
                if p+1<N and text[p+1]=="$":
                    t+="$"; p+=1
                state = 1
        elif state==1:
            # In math mode, no newline since last non-whitespace char.
            if c=='\n':
                c = ' '
                state = 2
            t += c
            if c=="$":
                if p+1<N and text[p+1]=="$":
                    t+="$"; p+=1
                state = 0
        elif state==2:
            # In math mode, no non-whitespace char since last newline.
            if c not in ' \t\n\r':
                t += c
                if c=="$":
                    if p+1<N and text[p+1]=="$":
                        t+="$"; p+=1
                    state = 0
                else:
                    state = 1
    text = t
    # The rest can be done by the generic `unindent()` function.
    br = Markup('<br>\n')
    nbsp = Markup('&nbsp;')
    return unindent(text, space=nbsp, newline=br)

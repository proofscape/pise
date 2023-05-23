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
import re

from sphinx.errors import SphinxError


class ChartWidget:
    """
    Ultimately should refactor, and base this on the widget classes
    defined in pfsc-server. For now, something good enough.
    """

    def __init__(self, lp_defns, vers_defns,
                 repopath, repovers, docname, src_file, lineno, wnum, **fields):
        self.lp_defns = lp_defns
        self.vers_defns = vers_defns
        self.repopath = repopath
        self.repovers = repovers
        self.docname = docname
        self.src_file = src_file
        self.lineno = lineno
        self.wnum = wnum

        # Here we will record for each repopath (key) the version at which we
        # are taking it (value).
        self.versions = {}

        self.intra_repo_docpath = f'_sphinx.{docname.replace("/", ".")}'
        self.libpath = f'{repopath}.{self.intra_repo_docpath}.w{wnum}'
        self.pane_group = f'{repopath}@{repovers}.{self.intra_repo_docpath}:CHART:'
        self.given_fields = fields
        self.resolved_fields = self.resolve_fields(fields)

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
                    k = ":" + ":".join(color_codes)
                    v = self.resolve_boxlisting(box_listing)
                    data[k].update(set(v))
                # Sort for deterministic output. Good for testing.
                data = {k:list(sorted(list(v))) for k, v in data.items()}

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


# FIXME:
#  This method was copied and modified from the ChartWidget class in the
#  pfsc-server project. When we refactor, this should be able to move to a common
#  location, and be implemented just once!
def set_up_hovercolor(hc):
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
    over = {':update': True}
    def set_prefix(s):
        if s[0] != ":": return s
        return f':save:tmp{s}'
    for k, v in hc.items():
        k, v = map(set_prefix, [k, v])
        over[k] = v

    out = {':update': True}
    def do_weak_restore(s):
        if s[0] != ":": return s
        return f':wrest'
    for k, v in hc.items():
        k, v = map(do_weak_restore, [k, v])
        out[k] = v

    return {
        'over': over,
        'out': out
    }


class ResolvedLibpath:

    def __init__(self, libpath, repopath, version):
        self.libpath = libpath
        self.repopath = repopath
        self.version = version


def find_lp_defn_for_docname(lp_defns, segment, docname, local_only=False):
    """
    Look for a libpath definition for a given segment, which pertains within
    a given document.

    If local_only is false, then we search definitions for the given document,
    as well as the index document of any directories above this one. If true,
    we search only defs for the given document.
    """
    lp = lp_defns.get(docname, {}).get(segment)
    if lp or local_only:
        return lp
    names = docname.split('/')
    for i in range(1, len(names) + 1):
        dn = '/'.join(names[:-i] + ['index'])
        lp = lp_defns.get(dn, {}).get(segment)
        if lp:
            return lp
    return None


def is_formal_libpath(lp):
    """
    Check whether a string is, at least syntactically, a well-formed libpath.
    """
    return re.match(r'\.?[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$', lp) is not None


def parse_box_listing(box_listing):
    """
    A box listing is a string giving a multipath or comma-separated list of
    multipaths.

    A multipath is a libpath in which at most one segment lists several
    alternative libpaths within braces, and separated by commas.

    We return a list of libpath strings, or raise a SphinxError.

    Example:

        foo.bar, foo.{spam.baz, cat}

    is transformed into

        ['foo.bar', 'foo.spam.baz', foo.cat]
    """
    if not isinstance(box_listing, str):
        raise SphinxError('Boxlisting must be a string.')
    mps = []
    mp = ''
    depth = 0
    for c in box_listing:
        if c in ' \t\r\n':
            continue
        if c == ',' and depth == 0:
            mps.append(mp)
            mp = ''
            continue
        elif c == '{':
            depth += 1
            if depth > 1:
                raise SphinxError(f'Boxlisting contains nested braces: {box_listing}')
        elif c == '}':
            depth -= 1
            if depth < 0:
                raise SphinxError(f'Boxlisting contains unmatched braces: {box_listing}')
        mp += c
    if mp:
        mps.append(mp)

    all_lps = []
    for mp in mps:
        lps = []
        i0 = mp.find("{")
        if i0 < 0:
            # No opening brace. In this case it should be just an ordinary libpath.
            lps = [mp]
        else:
            i1 = mp.find("}")
            if i1 <= i0:
                # If closing brace is missing, or does not come after opening brace, then malformed.
                raise SphinxError(f'Malformed multipath: {mp}')
            # Now we have 0 <= i0 < i1, and the two indices i0, i1 point to "{" and "}" chars, resp.
            prefix = mp[:i0]
            suffix = mp[i1 + 1:]
            multi = [p.strip() for p in mp[i0 + 1:i1].split(',')]
            lps = [prefix + m + suffix for m in multi]
        for lp in lps:
            if not is_formal_libpath(lp):
                raise SphinxError(f'Malformed multipath: {mp}')
            all_lps.append(lp)
    return all_lps

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

from sphinx.errors import SphinxError

from pfsc.lang.widgets import set_up_hovercolor
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
                 docname, src_file, lineno, wnum, **fields):
        self.sphinx_config = config
        self.lp_defns = lp_defns
        self.vers_defns = vers_defns
        self.docname = docname
        self.src_file = src_file
        self.lineno = lineno
        self.wnum = wnum

        # Here we will record for each repopath (key) the version at which we
        # are taking it (value).
        self.versions = {}

        self.libpath = build_libpath(config, docname, extension=f'w{wnum}')
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

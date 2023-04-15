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

from collections import defaultdict
from pathlib import Path

import click

from manage import cli, PFSC_ROOT


@cli.group()
def update():
    """
    Utilities for updating things like copyright statements.
    """
    pass


class FileInfo:

    def __init__(self, path, size):
        self.path = path
        self.size = size

    def __str__(self):
        return f'{self.size:15d}: {self.path}'

###############################################################################
"""
The `COPYRIGHT_INFO_PER_REPO` dict records all the settings that say how to
update copyright headers in each repo.

The format is: {
    <repo_name>: {
        "src_dir": <dirname_of_repo_in_PFSCROOT/src>,
        "statement": {
            "existing": <existing_copyright_header_string>,
            "desired": <desired_replacement_copyright_header_string>,
        },
        "dirs" {
            <dir_path_relative_to_repo_root>: [<list_of_globs>],
            <dir_path_relative_to_repo_root>: [<list_of_globs>],
            ...
        }
    },
    ...
}

You may list as many directories as necessary, for each one listing as many
file glob patterns as necessary. The globs follow the rules for the Python
`pathlib` package.

In particular, '**/' means search in this dir and in all subdirs recursively.
"""
COPYRIGHT_INFO_PER_REPO = {
    "demorepos": {
        "src_dir": "pfsc-demo-repos",
        "statement": {
            "existing": "Copyright (c) 2021-2022",
            "desired":  "Copyright (c) 2021-2023"
        },
        "dirs": {
            '': ['**/*.pfsc'],
        },
    },
    "deploy": {
        "src_dir": "pfsc-deploy",
        "statement": {
            "existing": "Copyright (c) 2020-2022",
            "desired":  "Copyright (c) 2020-2023"
        },
        "dirs": {
            '': ['*.py'],
            'tools': ['**/*.py', '**/*.yaml'],
        },
    },
    "displaylang": {
        "src_dir": "displaylang",
        "statement": {
            "existing": "Copyright (c) 2020-2022",
            "desired":  "Copyright (c) 2020-2023"
        },
        "dirs": {
            'displaylang': ['**/*.py'],
            'tests': ['**/*.py'],
        },
    },
    "examp": {
        "src_dir": "pfsc-examp",
        "statement": {
            "existing": "Copyright (c) 2018-2022",
            "desired":  "Copyright (c) 2018-2023"
        },
        "dirs": {
            '': ['*.py'],
            'pfsc_examp': ['**/*.py'],
            'tests': ['**/*.py'],
        },
    },
    "ise": {
        "src_dir": "pfsc-ise",
        "statement": {
            "existing": "Copyright (c) 2018-2022",
            "desired":  "Copyright (c) 2018-2023"
        },
        "dirs": {
            '': ['*.js'],
            'src': ['**/*.js', '**/*.css'],
        }
    },
    "manage": {
        # Yes, this project can update its own headers:
        "src_dir": "../pfsc-manage",
        "statement": {
            "existing": "Copyright (c) 2021-2022",
            "desired":  "Copyright (c) 2021-2023"
        },
        "dirs": {
            '': ['setup.py', 'manage.py'],
            'tools': ['**/*.py'],
            'topics': ['**/*.py', '**/Dockerfile*'],
        }
    },
    "moose": {
        "src_dir": "pfsc-moose",
        "statement": {
            "existing": "Copyright (c) 2011-2022",
            "desired":  "Copyright (c) 2011-2023"
        },
        "dirs": {
            '': ['*.js'],
            'src': ['**/*.js', '**/*.css'],
        }
    },
    "pbe": {
        "src_dir": "pbe",
        "statement": {
            "existing": "Copyright (c) 2020-2022",
            "desired":  "Copyright (c) 2020-2023"
        },
        "dirs": {
            '': ['*.js'],
            'src': ['**/*.js', '**/*.css', '**/*.html'],
        }
    },
    "pdf": {
        "src_dir": "pfsc-pdf",
        "statement": {
            "existing": "Copyright 2020-2021",
            "desired":  "Copyright 2020-2022"
        },
        "dirs": {
            'web': ['*.js', '*.css', '*.html'],
        }
    },
    "server": {
        "src_dir": "pfsc-server",
        "statement": {
            "existing": "Copyright (c) 2011-2022",
            "desired":  "Copyright (c) 2011-2023"
        },
        "dirs": {
            '': ['*.py'],
            'pfsc': ['**/*.py', 'templates/**/*.html'],
            'static': ['**/*.css'],
            'tests': ['**/*.py'],
            'util': ['**/*.py'],
        },
    },
    "testmodules": {
        "src_dir": "pfsc-test-modules",
        "statement": {
            "existing": "Copyright (c) 2011-2022",
            "desired":  "Copyright (c) 2011-2023"
        },
        "dirs": {
            'pfsc_test_modules': ['**/*.py'],
            'repos': ['**/*.pfsc'],
        },
    },
    "util": {
        "src_dir": "pfsc-util",
        "statement": {
            "existing": "Copyright (c) 2021-2022",
            "desired":  "Copyright (c) 2021-2023"
        },
        "dirs": {
            '': ['*.py'],
            'pfsc_util': ['**/*.py'],
            'tests': ['**/*.py'],
        },
    },
}


class LicensableFiles:
    """
    Provides iteration over the licensable files in a repo, and other info.
    """

    def __init__(self, repo):
        """
        repo: the name of a repo (a key in the COPYRIGHT_INFO_PER_REPO lookup)
        """
        info = COPYRIGHT_INFO_PER_REPO.get(repo)
        if info is None:
            raise click.UsageError(f'Unknown repo {repo}')
        self.info = info
        self.root = Path(PFSC_ROOT) / 'src' / info['src_dir']

    def paths(self):
        """
        Return an iterator over the paths of all licensable files in the repo.
        """
        for dirname, globs in self.info['dirs'].items():
            p = self.root / dirname
            for g in globs:
                for path in p.glob(g):
                    yield path

    def internal_path(self, path):
        """Turn an absolute path into one relative to the repo root dir."""
        return path.relative_to(self.root)


###############################################################################

@update.command()
@click.option('--dry-run', is_flag=True, help="Do not make changes; just print a report.")
@click.argument('repo')
def cyear(dry_run, repo):
    """
    Update Copyright Year in REPO.

    The settings for each repo are hard-coded in `tools/update.py`,
    and should be updated from time to time, as appropriate.

    This includes which headers to search for, and how to replace them, and in
    which directories and files to search.
    """
    info = COPYRIGHT_INFO_PER_REPO.get(repo)
    if info is None:
        raise click.UsageError(f'Unknown repo {repo}')

    has_no_header = []
    num_old = 0
    num_new = 0
    old_index_histo = defaultdict(list)
    new_index_histo = defaultdict(list)

    old_header = info["statement"]["existing"]
    new_header = info["statement"]["desired"]

    old_header_len = len(old_header)

    lf = LicensableFiles(repo)
    for path in lf.paths():
        with open(path) as f:
            text = f.read()
        i0 = text.find(old_header)
        i2 = text.find(new_header)
        rel_path = lf.internal_path(path)
        if i0 < 0 and i2 < 0:
            has_no_header.append(FileInfo(rel_path, len(text)))
        elif i0 >= 0:
            num_old += 1
            old_index_histo[i0].append(rel_path)
            if not dry_run:
                i1 = i0 + old_header_len
                newtext = text[:i0] + new_header + text[i1:]
                with open(path, 'w') as f:
                    f.write(newtext)
        else:
            num_new += 1
            new_index_histo[i2].append(rel_path)

    def report_histo(total, histo, descrip):
        print(f'Found {total} files {descrip}' + (":" if histo else '.'))
        items = sorted(histo.items(), key=lambda p: -len(p[1]))
        first = True
        for k, v in items:
            print(f'    {len(v):6d} occurred at char {k:10d}')
            if not first or len(v) < 6:
                for path in v:
                    print(f'        {path}')
            first = False

    print()
    report_histo(num_old, old_index_histo, 'with old header')

    print()
    report_histo(num_new, new_index_histo, 'with new header')

    print()
    if has_no_header:
        print('The following %s files had no header:' % len(has_no_header))
        print('    ', '          BYTES  PATH')
        for fn in has_no_header:
            print('    ', fn)
    else:
        print('All files had one header or the other.')

    print()


@update.command()
@click.option('-c', '--div-char', default="~", help="The divider character. Default: '~'")
@click.option('-n', '--div-len', default="80", help="The length of the divider. Default: 80")
@click.option('--dry-run', is_flag=True, help="Print a report instead of the concatenation.")
@click.option('-v', '--verbose', is_flag=True, help="In dry-run mode, print a more verbose report.")
@click.argument('repo')
def cat(div_char, div_len, dry_run, verbose, repo):
    """
    Concatenate to stdout all the licensable files in REPO.

    The license headers are chopped off, and in their place we put a simple
    divider containing the path to the file, relative to the repo root dir.
    """
    try:
        div_len = int(div_len)
        assert div_len >= 0
    except (ValueError, AssertionError):
        raise click.UsageError('div-len must be a non-negative integer')
    divider = div_char * div_len

    unique_headers = defaultdict(list)
    has_no_header = []
    total_length = 0

    lf = LicensableFiles(repo)
    for path in lf.paths():
        rel_path = lf.internal_path(path)
        with open(path) as f:
            text = f.read()

        # Auto-recognize comment style, and seek end of header
        header = None
        rem = None
        if text.startswith("#"):
            M = re.search(r'\n[^#]', text)
            if M:
                i = M.start()
                header, rem = text[:i+1], text[i+1:]
        elif text.startswith("/*"):
            i = text.find("*/\n")
            if i > 0:
                header, rem = text[:i+3], text[i+3:]
        elif text.startswith("<!--"):
            i = text.find("-->\n")
            if i > 0:
                header, rem = text[:i + 4], text[i + 4:]
        elif text.startswith("{#"):
            i = text.find("#}\n")
            if i > 0:
                header, rem = text[:i + 3], text[i + 3:]

        if header is None:
            has_no_header.append(FileInfo(rel_path, len(text)))
            continue

        unique_headers[header].append(rel_path)

        block = f'{divider}\n{rel_path}\n{divider}\n' + rem
        total_length += len(block)

        if not dry_run:
            print(block)

    if dry_run:
        print()
        print(f'Total concatenated length would be: {total_length}')

        print()
        if has_no_header:
            print('The following %s files had no header:' % len(has_no_header))
            print('    ', '          BYTES  PATH')
            for fn in has_no_header:
                print('    ', fn)
        else:
            print('All files had a header.')

        print()
        nh = len(unique_headers)
        print(f'Found {nh} distinct headers.')

        for h, (header, paths) in enumerate(unique_headers.items()):
            print('='*80)
            nf = len(paths)
            print(f'({h+1}/{nh}) The following header occurred in {nf} file{"" if nf == 1 else "s"}:')
            print()
            print(header)
            print()
            if verbose:
                print('The files where this header occurred were:')
                for path in paths:
                    print('    ', path)

        print()

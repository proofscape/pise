# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2024 Proofscape Contributors                           #
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

SEE ALSO: the SUPERPROJECTS dict defined below, for projects like `pise`, which
combine several of these (what used to be) separate repos into one larger project.
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
            "existing": "Copyright (c) 2020-2023",
            "desired":  "Copyright (c) 2020-2024"
        },
        "dirs": {
            'displaylang': ['**/*.py'],
            'tests': ['**/*.py'],
        },
    },
    "docs-site": {
        "src_dir": "pise-docs",
        "dirs": {
            'source': ['**/*.rst'],
            'other': ['**/*.tex'],
        },
    },
    "examp": {
        "src_dir": "pfsc-examp",
        "statement": {
            "existing": "Copyright (c) 2018-2023",
            "desired":  "Copyright (c) 2018-2024"
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
            "existing": "Copyright (c) 2011-2023",
            "desired":  "Copyright (c) 2011-2024"
        },
        "dirs": {
            '': ['*.js'],
            'src': ['**/*.js', '**/*.css'],
        }
    },
    "manage": {
        # Yes, this project can update its own headers:
        "src_dir": "pfsc-manage",
        "statement": {
            "existing": "Copyright (c) 2011-2023",
            "desired":  "Copyright (c) 2011-2024"
        },
        "dirs": {
            '': ['setup.py', 'manage.py'],
            'tests': ['**/*.py'],
            'tools': ['**/*.py'],
            'topics': ['**/*.py', '**/Dockerfile*', '**/*.conf'],
        }
    },
    "moose": {
        "src_dir": "pfsc-moose",
        "statement": {
            "existing": "Copyright (c) 2011-2023",
            "desired":  "Copyright (c) 2011-2024"
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
            "existing": "Copyright (c) 2011-2023",
            "desired":  "Copyright (c) 2011-2024"
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
            "existing": "Copyright (c) 2011-2023",
            "desired":  "Copyright (c) 2011-2024"
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

"""
In the `SUPERPROJECTS` dict, you can assemble several of the "repos" listed
above (which used to all be separate repos) into larger projects.

The format is: {
    <project_name>: {
        "subdir1": "reponame1",
        "subdir2": "reponame2",
        "subdir3": "reponame3",
        ...
    },
    ...
}

The "subdir" keys define internal directories under which the files for that
repo will be listed.
"""
SUPERPROJECTS = {
    'pise': {
        'server': 'server',
        'ise': 'ise',
        'manage': 'manage',
    },
}


# Make sure we're not duplicating any repo names:
repo_names = set(COPYRIGHT_INFO_PER_REPO.keys())
superproject_names = set(SUPERPROJECTS.keys())
duplicated_names = superproject_names.intersection(repo_names)
if duplicated_names:
    import sys
    print(
        '*** Error: `SUPERPROJECTS` dict duplicates keys from `COPYRIGHT_INFO_PER_REPO` dict,'
        ' in manage/tools/update.py:'
    )
    print(duplicated_names)
    sys.exit(1)


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

    def full_and_internal_paths(self):
        """
        Return an iterator over pairs (fpath, ipath), giving the full and
        internal paths of all licensable files in the repo.
        """
        for fpath in self.paths():
            ipath = self.internal_path(fpath)
            yield fpath, ipath


class SuperprojectLicensableFiles:
    """
    Provides iteration over the licensable files in *several* repos, regarded
    as parts of one larger superproject.
    """

    def __init__(self, project_name):
        proj = SUPERPROJECTS.get(project_name)
        if proj is None:
            raise click.UsageError(f'Unknown project name: {project_name}')
        self.proj = {
            subdir: LicensableFiles(repo)
            for subdir, repo in proj.items()
        }

    def full_and_internal_paths(self):
        """
        Return an iterator over pairs (fpath, ipath), giving the full and
        internal paths of all licensable files in the project.
        """
        for subdir, lf in self.proj.items():
            sdpath = Path(subdir)
            for fpath, repo_ipath in lf.full_and_internal_paths():
                proj_ipath = sdpath / repo_ipath
                yield fpath, proj_ipath


def get_licensable_files(name):
    """
    Construct a `LicensableFiles` for a repo, or `SuperprojectLicensableFiles`
    for a superproject, according to the given name.
    """
    if name in COPYRIGHT_INFO_PER_REPO:
        return LicensableFiles(name)
    elif name in SUPERPROJECTS:
        return SuperprojectLicensableFiles(name)
    else:
        raise click.UsageError(f'No known repo or superproject for name: {name}')


###############################################################################

@update.command()
@click.option('--dry-run', is_flag=True, help="Do not make changes; just print a report.")
@click.argument('repo')
def cyear(dry_run, repo):
    """
    Update Copyright Year in REPO.

    REPO can be any key in either the COPYRIGHT_INFO_PER_REPO lookup, or the
    SUPERPROJECTS lookup, in update.py.

    The settings for each repo are hard-coded in `tools/update.py`,
    and should be updated from time to time, as appropriate.
    This includes which headers to search for, and how to replace them, and in
    which directories and files to search.

    NOTE: For this command to work, you must make a symlink under PFSC_ROOT/src,
    pointing to each REPO. The name of the symlink must equal the value of the
    REPO's "src_dir" field, in the COPYRIGHT_INFO_PER_REPO lookup.
    """
    if repo in SUPERPROJECTS:
        repos = SUPERPROJECTS[repo].values()
        print('=' * 80)
        print(f'SUPERPROJECT: {repo}\n')
    else:
        repos = [repo]

    for repo in repos:
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

        if len(repos) > 1:
            print('-' * 80)
            print(f'REPO: {repo}')

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


def header_and_remainder(text):
    """
    Split the text of a file into header and remainder.
    """
    # Auto-recognize comment style, and seek end of header
    header = None
    rem = None
    if text.startswith("#"):
        # Python
        M = re.search(r'\n[^#]', text)
        if M:
            i = M.start()
            header, rem = text[:i + 1], text[i + 1:]
    elif text.startswith("/*"):
        # JS & CSS
        i = text.find("*/\n")
        if i > 0:
            header, rem = text[:i + 3], text[i + 3:]
    elif text.startswith("<!--"):
        # HTML
        i = text.find("-->\n")
        if i > 0:
            header, rem = text[:i + 4], text[i + 4:]
    elif text.startswith("{#"):
        # Jinja template file
        i = text.find("#}\n")
        if i > 0:
            header, rem = text[:i + 3], text[i + 3:]
    elif text.startswith("%"):
        # TeX
        M = re.search(r'\n[^%]', text)
        if M:
            i = M.start()
            header, rem = text[:i + 1], text[i + 1:]
    elif text.startswith(".. "):
        # rST
        i = text.find("..:\n")
        if i > 0:
            header, rem = text[:i + 4], text[i + 4:]

    return header, rem


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

    REPO can be any key in either the COPYRIGHT_INFO_PER_REPO lookup, or the
    SUPERPROJECTS lookup, in update.py.

    NOTE: For this command to work, you must make a symlink under PFSC_ROOT/src,
    pointing to each REPO. The name of the symlink must equal the value of the
    REPO's "src_dir" field, in the COPYRIGHT_INFO_PER_REPO lookup.
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

    lf = get_licensable_files(repo)
    for path, rel_path in lf.full_and_internal_paths():
        with open(path) as f:
            text = f.read()

        header, rem = header_and_remainder(text)

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

@update.command()
@click.option('--dry-run', is_flag=True, help="Print a report, but do not insert headers.")
@click.option('-v', '--verbose', is_flag=True, help="Show headers found.")
@click.argument('repo')
def license(dry_run, verbose, repo):
    """
    Add license headers to licensable files currently missing them, in REPO.

    For each file that is lacking a header, one can be supplied automatically only if:

    * At least one file with the same extension does have a header, and

    * Among all files with this extension and having headers, there is only one,
      unique header.

    REPO can be any key in the COPYRIGHT_INFO_PER_REPO lookup, in update.py.

    NOTE: For this command to work, you must make a symlink under PFSC_ROOT/src,
    pointing to each REPO. The name of the symlink must equal the value of the
    REPO's "src_dir" field, in the COPYRIGHT_INFO_PER_REPO lookup.
    """
    headers_by_ext = defaultdict(list)
    paths_lacking_header_by_ext = defaultdict(list)

    lf = get_licensable_files(repo)
    for path, rel_path in lf.full_and_internal_paths():
        with open(path) as f:
            text = f.read()

        header, rem = header_and_remainder(text)
        ext = path.suffix

        if header is None:
            paths_lacking_header_by_ext[ext].append(path)
        else:
            headers_by_ext[ext].append(header)

    if not paths_lacking_header_by_ext:
        print()
        print('No files lacking header.')
    else:
        for ext, paths in paths_lacking_header_by_ext.items():
            n = len(paths)
            print()
            print('-' * 80)
            print(f'Extension: {ext}')
            print(f'{n} files lacking header')

            headers = headers_by_ext.get(ext, [])
            m = len(headers)
            if m != 1:
                print('Cannot automatically supply header.')
                if m:
                    print(f'Found {m} different existing headers for this file extension.')
                    if verbose:
                        for header in headers:
                            print()
                            print(header)
                else:
                    print('Found no existing headers for this file extension.')

            else:
                header = headers[0]
                print('Found a unique existing header for this extension.')
                if verbose:
                    print()
                    print(header)
                print()

                if not dry_run:
                    for path in paths:
                        with open(path) as f:
                            text = f.read()
                        with open(path, 'w') as f:
                            text = header + '\n' + text
                            f.write(text)
                    print(f'Updated {n} files.')

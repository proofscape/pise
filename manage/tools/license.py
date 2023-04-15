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

import os
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess
import urllib.parse

import click
import jinja2
import requests

import conf as pfsc_conf
from manage import cli, PFSC_ROOT, PFSC_MANAGE_ROOT
from tools.util import (
    get_version_numbers,
    get_python_version_for_images,
    get_redis_server_version_for_oca,
)
import topics.pfsc.notice
import topics.pfsc.write_license_files as write_license_files


PFSC_MANAGE_ROOT = Path(PFSC_MANAGE_ROOT)
PFSC_ROOT = Path(PFSC_ROOT)

this_dir = os.path.dirname(__file__)
templates_dir = os.path.join(this_dir, 'templates')
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(
    PFSC_MANAGE_ROOT / 'topics' / 'pfsc' / 'templates'
))

GITHUB_REPO_URL = re.compile(r'[^:]+://github.com/[^/]+/[^/]+/?$')


@cli.group()
def license():
    """
    Generate combined license files and "About" dialogs.
    """
    pass


SUPPORTED_PROJECTS = {
    'ise': {
        'lang': 'js',
        'proj_name': 'pfsc-ise',
    },
    'client': {
        'lang': 'js',
        'proj_name': 'pfsc-ise',
    },
    'pbe': {
        'lang': 'js',
        'proj_name': 'pbe',
    },
    'server': {
        'lang': 'py',
        'proj_name': 'pfsc-server',
    },
}


@license.command()
def projects():
    """
    List the Proofscape projects for which license support is provided.
    """
    print("The supported project names are:")
    for k in SUPPORTED_PROJECTS.keys():
        print('  ', k)


@license.command()
@click.argument('project')
@click.option('--image', help="Name a docker image. Reject packages not occurring in `pip freeze` in this image.")
def show(project, image):
    """
    Show the license info we have for PROJECT (e.g. 'ise', 'pbe', or 'server').

    You should run this any time the set of dependencies for a project changes
    (including after upgrades), in order to make a visual check of whether we
    have complete license information for all packages.

    If and when it is necessary to supply manually any missing information for
    any packages, the way to do that is to enter the information in the
    `MANUAL_PY_PKG_INFO` and `MANUAL_JS_PKG_INFO` dictionaries defined at the
    end of `tools/license.py` in this (`pfsc-manage`) project.
    """
    info = SUPPORTED_PROJECTS.get(project)
    if info is None:
        raise click.UsageError('Unknown project. Use `pfsc license projects` to list known projects.')
    proj_name = info['proj_name']
    if info['lang'] == 'py':
        gather_dep_info_for_python_project(proj_name, print_report=True, image=image)
    elif info['lang'] == 'js':
        gather_dep_info_for_javascript_project(proj_name, print_report=True)
    else:
        raise Exception('unknown language')


# DEPRECATED
#  The pfsc-ise and pbe projects now use custom loaders to build their About
#  dialogs at build time, using Webpack.
#  Therefore this command is no longer needed.
#  However, we do still need to build the combined license file for the OCA
#  image, which includes JS packages. Therefore in this license.py module we
#  retain all the infrastructure for building JS package info.
#  This function itself can probably be removed, but we keep it for now.
#@license.command()
@click.argument('project')
@click.option('--dry-run', is_flag=True, help="Do not write anything; just print what would be written.")
def about(project, dry_run):
    """
    Generate the HTML table rows for the "About" dialog for PROJECT (e.g. 'ise').
    Use `pfsc license projects` for list of known PROJECT names.

    The result is written directly into the appropriate file in the PROJECT.
    """
    info = SUPPORTED_PROJECTS.get(project)
    if info is None:
        raise click.UsageError('Unknown project. Use `pfsc license projects` to list known projects.')
    if info['lang'] != 'js':
        raise click.UsageError('That is not a JavaScript project.')
    proj_name = info['proj_name']

    pkgs, _ = gather_dep_info_for_javascript_project(proj_name)
    # We're keeping the ordering that you get from `npm list`. It's
    # hierarchical, so that you get your project first, then its _direct_
    # dependencies, and then recursive deps come later. I think this is good,
    # because it lists the packages in order of importance. Alphabetical would
    # be kind of meaningless, and there's no obligation to make it easy to find
    # a given package in the list.

    if proj_name == 'pfsc-ise':
        # In pfsc-ise we also have pdf.js, plus Pyodide and all the Python
        # packages we load in there. I want these to get high billing, after
        # pfsc-ise.
        pkgs = pkgs[:1] + [get_other_pkg_info_lookup()['pdfjs']] + list(get_pyodide_pkg_info_lookup().values()) + pkgs[1:]
        # Actually I want to lift elkjs and SymPy and give them higher billing.
        for i, pkg in enumerate(pkgs):
            if pkg.name == 'elkjs':
                break
        elkjs = pkg
        pkgs = pkgs[:i] + pkgs[i+1:]

        for j, pkg in enumerate(pkgs):
            if pkg.name == 'sympy':
                break
        sympy = pkg
        pkgs = pkgs[:j] + pkgs[j+1:]

        pkgs = [pkgs[0], elkjs, sympy] + pkgs[1:]

    rows = ''
    for pkg in pkgs:
        rows += HTML_TABLE_ROW_TEMPLATE.render(
            src_url=pkg.get_src_url(vers=True),
            proj_name=pkg.name,
            vers_no=pkg.version,
            license_url=pkg.get_license_url(),
            license_name=pkg.license_name,
        )
    code = PFSC_ABOUT_ROWS_TEMPLATE.render(project=project, rows=rows)
    if project == 'pbe':
        dst = PFSC_ROOT / 'src' / 'pbe' / 'src' / 'options' / 'about.js'
    elif project == 'ise':
        dst = PFSC_ROOT / 'src' / 'pfsc-ise' / 'src' / 'about.js'
    else:
        raise click.UsageError(f'No write rule for project {project}')
    if dry_run:
        print(code)
        print(f'\n\n...would be written to: {dst}')
    else:
        with open(dst, 'w') as f:
            f.write(code)
        print(f'Wrote {len(code)} bytes to {dst}.')


HTML_TABLE_ROW_TEMPLATE = jinja2.Template("""

<!-- {{proj_name}} -->
<tr><td><a target="_blank"
href="{{src_url}}">
{{proj_name}}
</a><span class="vers" data-proj-name="{{proj_name}}">
{{vers_no}}
</span></td>
<td><a target="_blank"
href="{{license_url}}">
{{license_name}}
</a></td></tr>
""")


PFSC_ABOUT_ROWS_TEMPLATE = jinja2.Template("""\
/* 
 * This file was generated by running
 *   $ pfsc license about {{ project }}
 * in the pfsc-manage project.
 */
export const softwareTableRows = `
{{ rows }}
`;
""")


def gather_licensing_info(verbose=False):
    """
    Gather all the licensing info that could be needed by any of our docker
    images, and assemble it in one giant dictionary.
    """
    py_comp, py_prob = gather_dep_info_for_python_project('pfsc-server', print_report=verbose)
    js_comp, js_prob = gather_dep_info_for_javascript_project('pfsc-ise', print_report=verbose)

    if len(py_prob) > 0:
        raise click.UsageError(
            'Missing some info on Python packages.\n'
            'Try running\n'
            '  $ pfsc license show server\n'
            'to learn more.'
        )

    if len(js_prob) > 0:
        raise click.UsageError(
            'Missing some info on JavaScript packages.\n'
            'Try running\n'
            '  $ pfsc license show ise\n'
            'to learn more.'
        )

    pyodide_pkg_info = get_pyodide_pkg_info_lookup()
    py_other = {name: pyodide_pkg_info[name] for name in [
        'sympy', 'pfsc-examp', 'displaylang',
        'mpmath', 'Jinja2', 'MarkupSafe',
        'lark-parser', 'typeguard',
        'pfsc-util',
    ]}

    js_other = {
        'pdfjs': get_other_pkg_info_lookup()['pdfjs'],
        'pyodide': pyodide_pkg_info['pyodide'],
    }

    python_package_two_liners = {
        pkg.name: f'{pkg.write_two_column_text_row()}\n  {pkg.get_src_url()}\n'
        for pkg in py_comp
    }

    javascript_package_two_liners = {
        pkg.name: f'{pkg.write_two_column_text_row()}\n  {pkg.get_src_url()}\n'
        for pkg in js_comp
    }

    pyodide_package_two_liners = {
        pkg.name: f'{pkg.write_two_column_text_row()}\n  {pkg.get_src_url()}\n'
        for pkg in py_other.values()
    }

    py_d = {pkg.name: pkg for pkg in py_comp}
    py_d = dict(py_other, **py_d)

    js_d = {pkg.name: pkg for pkg in js_comp}
    js_d = dict(js_other, **js_d)

    py_pkgs = list(py_d.values())
    js_pkgs = list(js_d.values())
    all_pkgs = py_pkgs + js_pkgs

    licenses = [
        {
            'name': pkg.name,
            'src_url': pkg.get_src_url(),
            'license_text': pkg.get_license_text(),
        }
        for pkg in all_pkgs
    ]

    vers = get_version_numbers()
    vers['python'] = get_python_version_for_images()
    vers['supervisor'] = pfsc_conf.SUPERVISOR_VERSION
    vers['redisgraph'] = pfsc_conf.REDISGRAPH_IMAGE_TAG
    vers['redis-server'] = get_redis_server_version_for_oca()
    vers['nginx'] = pfsc_conf.NGINX_IMAGE_TAG

    # These are the one-off cases:
    LICENSE_URLS = {
        'RSAL': f'https://raw.githubusercontent.com/RedisGraph/RedisGraph/v{vers["redisgraph"]}/LICENSE',
        'redis': f'https://raw.githubusercontent.com/redis/redis/{vers["redis-server"]}/COPYING',
        'supervisor': f'https://raw.githubusercontent.com/Supervisor/supervisor/{vers["supervisor"]}/LICENSES.txt',
        'gcc_runtime': 'https://raw.githubusercontent.com/gcc-mirror/gcc/master/COPYING.RUNTIME',
        'gpl3': 'https://raw.githubusercontent.com/gcc-mirror/gcc/master/COPYING3',
        'nginx': 'http://nginx.org/LICENSE',
    }

    special_licenses = {
        name: obtain_license_text(URL)
        for name, URL in LICENSE_URLS.items()
    }
    with open(PFSC_MANAGE_ROOT.parent / 'LICENSE') as f:
        special_licenses['pise'] = f.read()
    with open(PFSC_MANAGE_ROOT / 'topics' / 'licenses' / f'psf-{vers["python"]}') as f:
        special_licenses['PSF'] = f.read()

    top_credits = [
        ('pise-server', vers['pise'], 'Apache 2.0'),
        ('redis', vers["redis-server"], 'BSD-3-Clause'),
        ('redisgraph', vers["redisgraph"], 'RSAL'),
        ('supervisor', vers["supervisor"], 'BSD-derived'),
        ('pise-client', vers['pise'], 'Apache 2.0'),
        ('SymPy', f"(DisplayLang fork v{vers['displaylang-sympy']})", 'BSD-3-Clause'),
        ('pyodide', vers['pyodide'], 'MPL-2.0'),
        ('PDF.js', f"(Proofscape fork v{vers['pfsc-pdf']})", 'Apache 2.0'),
        ('mathjax', vers['mathjax'], 'Apache 2.0'),
        ('elkjs', vers['elkjs'], 'EPL-2.0'),
        ('python', vers["python"], 'PSF License'),
        ('pfsc-demo-repos', '', 'MPL-2.0'),
        ('nginx', vers['nginx'], 'BSD-2-Clause'),
    ]
    tab_stop = 56
    credits = {}
    for name, version, license in top_credits:
        head = f'{name} {version}'
        credits[name] = f'{head}{" " * (tab_stop - len(head))}{license}'

    for_about_rows = [
        ('pise-server', vers['pise'], 'Apache 2.0',
         'https://github.com/proofscape/pise',
         'https://github.com/proofscape/pise/blob/main/LICENSE'),
        ('redis', vers["redis-server"], 'BSD-3-Clause',
         'https://github.com/redis/redis',
         'https://github.com/redis/redis/blob/unstable/COPYING'),
        ('redisgraph', vers["redisgraph"], 'RSAL',
         'https://github.com/RedisGraph/RedisGraph',
         'https://github.com/RedisGraph/RedisGraph/blob/v2.4.13/LICENSE'),
        ('supervisor', vers["supervisor"], 'BSD-derived',
         'https://github.com/Supervisor/supervisor',
         'https://github.com/Supervisor/supervisor/blob/main/LICENSES.txt'),
        ('libgomp', '', 'GCC RLE',
         'https://github.com/gcc-mirror/gcc/tree/master/libgomp',
         'https://www.gnu.org/licenses/gcc-exception-3.1.html')
    ]

    def tuple_to_obj_for_abt_rows(tup):
        return {
            k: v for k, v in zip([
                'projName', 'version', 'licName', 'projURL', 'licURL'
            ], tup)
        }

    notice_list = [
        n['text']
        for n in topics.pfsc.notice.notices
        if 'oca' in n['usage']
    ]

    oca_about_info = {
        'extraSoftware': [
                             tuple_to_obj_for_abt_rows(tup) for tup in for_about_rows[:4]
                         ] + [
                             pkg.write_obj_for_abt_row()
                             for pkg in py_comp if pkg.name not in [
                                # Don't repeat packages that already got special mention.
                                'sympy',
                             ]
                         ] + [
                             tuple_to_obj_for_abt_rows(tup) for tup in for_about_rows[4:]
                         ],
        'notices': notice_list,
    }

    info = {
        'python_package_two_liners': python_package_two_liners,
        'javascript_package_two_liners': javascript_package_two_liners,
        'pyodide_package_two_liners': pyodide_package_two_liners,
        'credits': credits,
        'notices': topics.pfsc.notice.notices,
        'oca_about_info': oca_about_info,
        'licenses': licenses,
        'special_licenses': special_licenses,
    }

    return info


@license.command()
@click.option('--image', default='pise:testing', help="The docker image where the python packages have been installed.")
@click.option('--dump', type=click.Choice(['lhead', 'lfull', 'notice', 'about']),
              help="Print to stdout. lhead=just header of LICENSES.txt, lfull=LICENSES.txt, notice=NOTICE.txt, about=about.json")
@click.option('-v', '--verbose', is_flag=True, default=False, help="Print diagnostic info.")
def oca(image, dump=None, verbose=False):
    """
    Write the "licensing info files" for the one-container app:
        LICENSES.txt
        NOTICE.txt
        about.json
    """
    license_info = gather_licensing_info(verbose=verbose)
    image_tag = image.split(":")[1]
    licenses_txt, notice_txt, about_json = write_license_files.build_oca_files(
        license_info, image_tag=image_tag)

    if dump == 'lfull':
        print(licenses_txt)
    elif dump == 'lhead':
        i1 = licenses_txt.find("LICENSES")
        print(licenses_txt[:i1])
    elif dump == 'notice':
        print(notice_txt)
    elif dump == 'about':
        print(about_json)

    return licenses_txt, notice_txt, about_json


@license.command()
@click.option('--image', default='pise-server:testing', help="The docker image where the python packages have been installed.")
@click.option('--dump', type=click.Choice(['lhead', 'lfull', 'notice']),
              help="Print to stdout. lhead=just header of LICENSES.txt, lfull=LICENSES.txt, notice=NOTICE.txt")
@click.option('-v', '--verbose', is_flag=True, default=False, help="Print diagnostic info.")
def server(image, dump=None, verbose=False):
    """
    Write the "licensing info files" for the pise-server image:
        LICENSES.txt
        NOTICE.txt
    """
    license_info = gather_licensing_info(verbose=verbose)
    image_tag = image.split(":")[1]
    licenses_txt, notice_txt = write_license_files.build_server_files(
        license_info, image_tag=image_tag)

    if dump == 'lfull':
        print(licenses_txt)
    elif dump == 'lhead':
        i1 = licenses_txt.find("LICENSES")
        print(licenses_txt[:i1])
    elif dump == 'notice':
        print(notice_txt)

    return licenses_txt, notice_txt


@license.command()
@click.option('--dump', type=click.Choice(['lhead', 'lfull', 'notice']),
              help="Print to stdout. lhead=just header of LICENSES.txt, lfull=LICENSES.txt, notice=NOTICE.txt")
@click.option('-v', '--verbose', is_flag=True, default=False, help="Print diagnostic info.")
def frontend(dump=None, verbose=False):
    """
    Write the "licensing info files" for the pise-frontend image:
        LICENSES.txt
        NOTICE.txt
    """
    license_info = gather_licensing_info(verbose=verbose)
    licenses_txt, notice_txt = write_license_files.build_frontend_files(license_info)

    if dump == 'lfull':
        print(licenses_txt)
    elif dump == 'lhead':
        i1 = licenses_txt.find("LICENSES")
        print(licenses_txt[:i1])
    elif dump == 'notice':
        print(notice_txt)

    return licenses_txt, notice_txt


class PyNoDistInfo(Exception):
    ...

class PyNoMetadata(Exception):
    ...

class VersionMismatch(Exception):
    ...


class SoftwarePackage:

    def __init__(self, name=None,
                 version=None, gh_url=None, license_name=None,
                 license_text='', license_url=None, v=True):
        self.name = name
        self.version = version
        self.gh_url = gh_url
        self.src_url = None  # any src URL besides GitHub
        self.license_name = license_name
        self.license_text = license_text
        # When we are able to find the file in the distribution, we record the
        # filename here. This can then be used to generate a GitHub URL pointing
        # directly to the file.
        self.license_filename = None
        self.license_url = license_url
        self.license_not_provided = False
        # v `True` means use URLs with 'vM.m.p', `False` means 'M.m.p',
        # while `None` means no version extension at all.
        self.v = v
        self.src_dir = None
        self.license_dir = None

    def get_src_url(self, vers=False):
        if self.src_url and not self.gh_url:
            return self.src_url
        path_ext = (
            '' if (self.v is None or self.version.startswith('commit-') or not vers)
            else f'/tree/{"v" if self.v else ""}{self.version}'
        )
        return f'{self.gh_url}{path_ext}'

    def get_license_url(self, quiet=False):
        if not self.license_url:
            if self.license_filename:
                ref = 'master' if self.v is None else 'main' if self.v == 'main' else f'{"v" if self.v else ""}{self.version}'
                self.license_url = f'{self.gh_url}/blob/{ref}/{self.license_filename}'
            else:
                if quiet:
                    return None
                raise Exception(f'No license URL: {self.name}')
        return self.license_url

    def get_raw_license_url(self):
        url = self.get_license_url()
        gh_prefix = 'https://github.com/'
        if url.startswith(gh_prefix):
            url = 'https://raw.githubusercontent.com/' + url[len(gh_prefix):]
            url = re.sub(r'/blob/', '/', url)
        return url

    def __str__(self):
        n = len(self.license_text)
        s = (
            f'Package: {self.name}@{self.version}\n'
            f'  Source: {self.gh_url or self.src_url or "unknown"}\n'
            f'  License name: {self.license_name or "unknown"}\n'
            f'  License length: {n}'
        )

        license_url = self.get_license_url(quiet=True)
        s += f'\n  License URL: {self.license_url if license_url else "unknkown"}'

        if self.license_not_provided:
            s += '\n  License not provided.'

        return s

    def write_obj_for_abt_row(self):
        return {
            'projName': self.name,
            'version': self.version,
            'licName': self.license_name,
            'projURL': self.get_src_url(),
            'licURL': self.get_license_url(),
        }

    def write_two_column_text_row(self, vers=True, license_tab_stop=56):
        head = self.name
        if vers:
            head += f' {self.version}'
        return head + (' ' * (license_tab_stop - len(head))) + self.license_name

    def set_license_text(self, text):
        self.license_text = text

    def get_license_text(self):
        if self.license_not_provided:
            return None
        if not self.license_text:
            text = None
            try:
                path = self.get_license_path()
                with open(path, 'r') as f:
                    text = f.read()
            except (FileNotFoundError, UnknownLocalLicensePath):
                pass
            if text is None:
                url = self.get_raw_license_url()
                text = obtain_license_text(url)
            self.license_text = text
        return self.license_text

    def get_license_path(self):
        if (not self.license_dir) or (not self.license_filename):
            raise UnknownLocalLicensePath(self.name)
        return self.license_dir / self.license_filename

    def override(self, info):
        for name in "name gh_url license_name license_text license_url license_not_provided v src_url".split():
            if name in info:
                setattr(self, name, info[name])

    def is_incomplete(self):
        return (
            (self.gh_url is None and self.src_url is None) or
            self.license_name is None or
            self.license_name == "UNKNOWN" or
            ( len(self.license_text) == 0 and (self.license_url is None) and (self.license_not_provided is False) )
        )

    def search_dir_for_license_file(self, dir_path):
        names = [x.name for x in dir_path.iterdir()]
        for name in names:
            p = name.split('.')
            if len(p) in [1, 2] and p[0].upper() in ["LICENSE", "COPYING"]:
                self.license_filename = name
                return dir_path / name
        return None


class UnknownLocalLicensePath(Exception):
    ...


class PyPackage(SoftwarePackage):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.site_packages_dir = None

    def get_src_path(self, parent_dir=None):
        assert self.src_dir
        if isinstance(parent_dir, str):
            parent_dir = Path(parent_dir)
        if isinstance(parent_dir, Path):
            return parent_dir / self.src_dir.name
        return self.src_dir

    def resolve_for_project(self, proj_name, expected_package_version=None):
        sp = find_venv_python_site_packages(proj_name)
        self.site_packages_dir = sp
        n = len(self.name)
        lc = self.name.lower().replace('-', "_")
        info_dir = None
        for d in sp.iterdir():
            if d.is_dir():
                dn = d.name
                if dn[:n].lower() == lc:
                    m = len(dn)
                    if m == n:
                        self.src_dir = d
                    elif m > n and dn[n] == '-' and dn.endswith('-info'):
                        info_dir = d
            if self.src_dir and info_dir:
                break
        self.license_dir = info_dir
        if info_dir is None:
            raise PyNoDistInfo(proj_name)

        M = re.match(r'(.+)(\.dist-info|-py\d\.\d\.egg-info)$', info_dir.name[n+1:])
        if not M:
            raise PyNoDistInfo(proj_name)
        vers_from_dir_name = M.group(1)
        if expected_package_version and vers_from_dir_name != expected_package_version:
            raise VersionMismatch(proj_name)

        md = info_dir / "METADATA"
        if not md.exists():
            md = info_dir / "PKG-INFO"
            if not md.exists():
                raise PyNoMetadata(proj_name)

        with open(md, 'r') as f:
            text = f.read()
            lines = text.split('\n')
        headers = defaultdict(list)
        for line in lines:
            if not line:
                break
            if line[0].isspace():
                continue
            i0 = line.find(":")
            k, v = line[:i0].strip(), line[i0+1:].strip()
            headers[k].append(v)

        v = headers.get("Version")
        if not v:
            self.version = vers_from_dir_name
        elif v[0] != vers_from_dir_name:
            raise VersionMismatch(proj_name)
        else:
            self.version = v[0]

        gh_url = None
        urls = headers.get("Home-page")
        if urls and GITHUB_REPO_URL.match(urls[0]):
            gh_url = urls[0]
        if not gh_url:
            purls = headers.get("Project-URL", [])
            for purl in purls:
                i1 = purl.find(',')
                url = purl[i1+1:].strip()
                if GITHUB_REPO_URL.match(url):
                    gh_url = url
                    break
        self.gh_url = normalize_gh_url(gh_url)

        ln = headers.get("License")
        if ln:
            self.license_name = ln[0]

        lfp = None
        lfn = headers.get("License-File")
        if lfn:
            lfp = info_dir / lfn[0]
            if not lfp.exists():
                lfp = None
        if not lfp:
            lfp = self.search_dir_for_license_file(info_dir)
        if lfp:
            with open(lfp, 'r') as f:
                self.license_filename = lfp.name
                text = f.read()
                self.set_license_text(text)


class JsMissingPackageDir(Exception):
    ...


class JsMissingPackageJson(Exception):
    ...


class JsPackage(SoftwarePackage):

    def resolve(self, abs_path_str):
        #nm = PFSC_ROOT / 'src' / proj_name / 'node_modules'
        #pkg_dir = nm / self.name
        pkg_dir = Path(abs_path_str)
        if not pkg_dir.exists():
            raise JsMissingPackageDir(abs_path_str)
        self.src_dir = pkg_dir
        self.license_dir = pkg_dir

        pjson_path = pkg_dir / 'package.json'
        if not pjson_path.exists():
            raise JsMissingPackageJson(abs_path_str)

        with open(pjson_path, 'r') as f:
            pjson = f.read()
            info = json.loads(pjson)

        self.name = info.get('name')
        self.version = info.get('version')

        #v = info.get('version')
        #if v and v != expected_package_version:
        #    raise VersionMismatch(abs_path_str)
        #self.version = expected_package_version

        gh_url = None
        repo_info = info.get('repository', {})
        if isinstance(repo_info, str):
            repo_url = repo_info
        else:
            repo_url = repo_info.get('url', '')
        if GITHUB_REPO_URL.match(repo_url):
            gh_url = repo_url
        if not gh_url:
            hp = info.get('homepage', '')
            if GITHUB_REPO_URL.match(hp):
                gh_url = hp
        self.gh_url = normalize_gh_url(gh_url)

        self.license_name = info.get('license')

        lfp = self.search_dir_for_license_file(pkg_dir)
        if lfp:
            with open(lfp, 'r') as f:
                text = f.read()
                self.set_license_text(text)


def normalize_gh_url(url):
    if url:
        # Ensure https is the protocol
        i0 = url.find(":")
        url = 'https' + url[i0:]
        # Don't want to end with a '/' or with '.git'
        if url[-1] == '/':
            url = url[:-1]
        if url[-4:] == '.git':
            url = url[:-4]
    return url


def find_venv_python_site_packages(proj_name, py_vers=None):
    """
    Find the "site-packages" dir for a project's venv.

    @param proj_name: (str) the name of the project
    @param py_vers: (str) the Python version you want, if multiple ones are
        installed in the project's venv. E.g. '3.8'

    @return: Path
    """
    lib = PFSC_ROOT / 'src' / proj_name / 'venv' / 'lib'
    if py_vers is not None:
        vers_dir = lib / f'python{py_vers}'
    else:
        pydirs = [x for x in lib.iterdir() if x.is_dir() and x.name.startswith('python')]
        n = len(pydirs)
        if n == 0:
            raise click.FileError(f'No python dirs found in venv for {proj_name}')
        elif n > 1:
            raise click.FileError(
                f'Multiple python dirs found in venv for {proj_name}.'
                ' Please specify desired version using `vers` arg.'
            )
        else:
            vers_dir = pydirs[0]
    return vers_dir / "site-packages"


def gather_dep_info_for_javascript_project(proj_name, print_report=False, dedup=True):
    """
    Find out what we know about all the dependencies of a given JS project.
    (This includes manually supplied information.)

    @param proj_name: (str) the full name of the project, e.g. 'pfsc-ise'
    @param print_report: (bool) set True if you want to see a report in the
        terminal, sorting package info by incomplete/complete
    @param dedup: (bool) if True (default) we prune duplicates.
    @return: list of JsPackage instances
    """
    dir_path = PFSC_ROOT / 'src' / proj_name
    cmd = f'cd {dir_path}; npm list -ap --prod'
    out = subprocess.check_output(cmd, shell=True)
    lines = out.decode().split('\n')

    seen = set()
    incomplete = []
    complete = []
    total = 0

    for line in lines:
        if not line:
            continue
        p = JsPackage()
        p.resolve(line)
        if dedup and p.name in seen:
            continue
        seen.add(p.name)
        total += 1
        info = get_manual_pkg_info(p.name, 'js')
        if isinstance(info, dict):
            p.override(info)
        if p.is_incomplete():
            incomplete.append(p)
        else:
            complete.append(p)

    if print_report:

        if complete:
            print('\nComplete:')
            for p in complete:
                print('\n' + str(p))

        if incomplete:
            print('\nIncomplete:')
            for p in incomplete:
                print('\n' + str(p))

        print()
        print(f'Total:           {total:4d}')
        print(f'Incomplete:      {len(incomplete):4d}')
        print(f'Complete:        {len(complete):4d}')

    return complete, incomplete


def gather_dep_info_for_python_project(proj_name, print_report=False, image=None):
    """
    Find out what we know about all the dependencies of a given Python project.
    (This includes manually supplied information.)

    @param proj_name: (str) the full name of the project, e.g. 'pfsc-server'
    @param print_report: (bool) set True if you want to see a report in the
        terminal, sorting package info by incomplete/complete
    @param image: (str, optional) name:tag of Docker image where we should run
        `pip freeze` in order to get a list of packages to accept. Any package
        not occurring in this list will be rejected.
    @return: list of PyPackage instances
    """
    pip_line = re.compile(r'([-a-zA-Z0-9_]+)==(\d+(\.\w+)*)$')

    accepted_pkgs = None
    if image:
        accepted_pkgs = set()
        cmd = f'docker run --rm --entrypoint=bash {image} -c "pip freeze"'
        out = subprocess.check_output(cmd, shell=True)
        lines = out.decode().split('\n')
        for line in lines:
            if (M := pip_line.match(line)):
                accepted_pkgs.add(M.group(1))

    ignored_pkgs = get_ignored_packages()

    pip = PFSC_ROOT / 'src' / proj_name / 'venv' / 'bin' / 'pip'
    cmd = f'{pip} freeze'
    out = subprocess.check_output(cmd, shell=True)
    lines = out.decode().split('\n')

    abnormal_freeze_line = []
    no_dist_info = []
    no_metadata = []
    version_mismatch = []
    rejected = []
    ignored = []
    incomplete = []
    complete = []
    total = 0

    for line in lines:
        if not line:
            continue
        total += 1
        M = pip_line.match(line)
        py_pkg = None
        if not M:
            info = get_manual_pkg_info(line, 'py')
            if isinstance(info, PyPackage):
                py_pkg = info
            else:
                abnormal_freeze_line.append(line)
        else:
            package_name, expected_version = M.group(1), M.group(2)
            if package_name in ignored_pkgs:
                ignored.append(package_name)
                continue
            if (accepted_pkgs is not None) and (package_name not in accepted_pkgs):
                rejected.append(package_name)
                continue
            p = PyPackage(name=package_name)
            try:
                p.resolve_for_project(proj_name, expected_version)
            except PyNoDistInfo:
                no_dist_info.append(line)
            except PyNoMetadata:
                no_metadata.append(line)
            except VersionMismatch:
                version_mismatch.append(line)
            else:
                py_pkg = p
        if py_pkg:
            info = get_manual_pkg_info(line, 'py')
            if isinstance(info, dict):
                py_pkg.override(info)
            if py_pkg.is_incomplete():
                incomplete.append(py_pkg)
            else:
                complete.append(py_pkg)

    if print_report:

        if complete:
            print('\nComplete:')
            for p in complete:
                print('\n'+str(p))

        if incomplete:
            print('\nIncomplete:')
            for p in incomplete:
                print('\n'+str(p))

        if rejected:
            print('\nRejected:')
            for p in rejected:
                print('  ', p)

        if ignored:
            print('\nIgnored:')
            for p in ignored:
                print('  ', f'{p} ({ignored_pkgs[p]})')

        if abnormal_freeze_line:
            print('\nAbnormal pip:')
            for line in abnormal_freeze_line:
                print('  ', line)

        if no_dist_info:
            print('\nNo dist info dir:')
            for line in no_dist_info:
                print('  ', line)

        if no_metadata:
            print('\nNo METADATA file:')
            for line in no_metadata:
                print('  ', line)

        if version_mismatch:
            print('\nVersion mismatch:')
            for line in version_mismatch:
                print('  ', line)

        print()
        print(f'Total:           {total:4d}')
        print(f'Abnormal pip:    {len(abnormal_freeze_line):4d}')
        print(f'No dist info:    {len(no_dist_info):4d}')
        print(f'No METADATA:     {len(no_metadata):4d}')
        print(f'Vers mismatch:   {len(version_mismatch):4d}')
        print(f'Rejected:        {len(rejected):4d}')
        print(f'Ignored:         {len(ignored):4d}')
        print(f'Incomplete:      {len(incomplete):4d}')
        print(f'Complete:        {len(complete):4d}')

    problematic = {}
    if abnormal_freeze_line:
        problematic['abnormal-freeze-line'] = abnormal_freeze_line
    if no_dist_info:
        problematic['no-dist-info'] = no_dist_info
    if no_metadata:
        problematic['no-metadata'] = no_metadata
    if version_mismatch:
        problematic['version-mismatch'] = version_mismatch
    if incomplete:
        problematic['incomplete'] = incomplete

    return complete, problematic


def obtain_license_text(url):
    """
    Obtain the full text for a license.

    We first check our cache, at `PFSC_ROOT/src/.licenses`. If it's there, we
    use that. Otherwise, we go to the web, and store the results in the cache.

    @param url: URL where the license can be found online.
    """
    name = urllib.parse.quote(url, safe='')
    licenses_dir = PFSC_ROOT / 'src' / '.licenses'
    cache_path = licenses_dir / name
    if cache_path.exists():
        with open(cache_path, 'r') as f:
            text = f.read()
    else:
        r = requests.get(url)
        if r.status_code != 200:
            raise Exception(f'Could not obtain license from: {url}')
        text = r.text
        if not licenses_dir.exists():
            os.makedirs(licenses_dir)
        with open(cache_path, 'w') as f:
            f.write(text)
    return text


class NonUniqueManualInfoMatch(Exception):
    ...


def get_manual_pkg_info(identifier, lang):
    """
    Search for manually supplied package info matching the given identifier
    string.

    Matching means that the key for the info occurs as a regex in the given
    string.

    Raises `NonUniqueManualInfoMatch` if more than one key matches
    (we check them all).

    @param identifier: string that identifies the package
    @param lang: string identifying the language

    @return: `SoftarePackage`, `dict`, or `None`
    """
    lookup = None
    if lang == 'py':
        lookup = get_manual_py_pkg_info_lookup()
    elif lang == 'js':
        lookup = MANUAL_JS_PKG_INFO
    else:
        raise Exception("Unknown language")
    info = None
    for k, v in lookup.items():
        if re.search(k, identifier):
            if info is not None:
                raise NonUniqueManualInfoMatch(identifier)
            info = v
    return info


def get_ignored_packages():
    """
    Some packages are ignored when generating licensing tables, because they
    are actually parts of other projects we are already naming elsewhere.
    This function returns a dict, in which ignored package names point to
    the name of the package that subsumes them, or else to some other string
    that explains why they are ignored.
    """
    return {
        'sphinxcontrib-applehelp': 'Sphinx',
        'sphinxcontrib-devhelp': 'Sphinx',
        'sphinxcontrib-htmlhelp': 'Sphinx',
        'sphinxcontrib-jsmath': 'Sphinx',
        'sphinxcontrib-qthelp': 'Sphinx',
        'sphinxcontrib-serializinghtml': 'Sphinx',
    }

###############################################################################
###############################################################################
# MANUAL PACKAGE INFO


def get_manual_py_pkg_info_lookup():
    vers = get_version_numbers()
    return {
        r'github\.com/proofscape/sympy': PyPackage(
            name='sympy',
            version=f"(DisplayLang fork v{vers['displaylang-sympy']})",
            gh_url='https://github.com/proofscape/sympy',
            license_name='BSD',
            license_url='https://github.com/sympy/sympy/blob/master/LICENSE',
            v=None,
        ),
        r'github\.com/proofscape/pfsc-examp': PyPackage(
            name='pfsc-examp',
            version=vers['pfsc-examp'],
            gh_url='https://github.com/proofscape/pfsc-examp',
            license_name='Apache 2.0',
            license_url='https://www.apache.org/licenses/LICENSE-2.0.txt',
        ),
        r'github\.com/proofscape/pfsc-util': PyPackage(
            name='pfsc-util',
            version=vers['pfsc-util'],
            gh_url='https://github.com/proofscape/pfsc-util',
            license_name='Apache 2.0',
            license_url='https://www.apache.org/licenses/LICENSE-2.0.txt',
        ),
        'aenum': {
            'license_url': 'https://github.com/ethanfurman/aenum/blob/master/aenum/LICENSE',
        },
        'bidict': {
            'gh_url': 'https://github.com/jab/bidict/tree/v0.21.4',
            'license_url': 'https://github.com/jab/bidict/blob/v0.21.4/LICENSE',
        },
        'blinker': {
            'gh_url': 'https://github.com/jek/blinker/tree/rel-1.4',
            'license_url': 'https://github.com/jek/blinker/blob/rel-1.4/LICENSE',
        },
        'cffi': {
            'src_url': 'https://foss.heptapod.net/pypy/cffi/-/tree/branch/default',
            'license_url': 'https://foss.heptapod.net/pypy/cffi/-/blob/branch/default/LICENSE',
        },
        'click': {
            'license_url': 'https://github.com/pallets/click/blob/main/LICENSE.rst',
        },
        'dill': {
            "license_url": 'https://github.com/uqfoundation/dill/blob/dill-0.3.4/LICENSE',
        },
        'dnspython': {
            'gh_url': 'https://github.com/rthalley/dnspython/tree/v1.16.0',
        },
        'eventlet': {
            "license_name": 'MIT',
            'gh_url': 'https://github.com/eventlet/eventlet/tree/v0.30.2',
            'license_url': 'https://github.com/eventlet/eventlet/blob/v0.30.2/LICENSE',
        },
        'exceptiongroup': {
            "license_name": 'MIT',
        },
        'Flask=': {
            'license_url': 'https://github.com/pallets/flask/blob/main/LICENSE.rst',
        },
        'Flask-Login': {
            'license_url': 'https://github.com/maxcountryman/flask-login/blob/main/LICENSE',
        },
        'Flask-Mail': {
            'gh_url': 'https://github.com/mattupstate/flask-mail/tree/0.9.1',
            'license_url': 'https://github.com/mattupstate/flask-mail/blob/0.9.1/LICENSE',
        },
        'Flask-SocketIO': {
            'license_name': 'MIT',
        },
        'greenlet': {
            'license_url': 'https://github.com/python-greenlet/greenlet/blob/master/LICENSE',
        },
        'gremlinpython': {
            'gh_url': 'https://github.com/apache/tinkerpop',
        },
        'hiredis': {
            'license_url': 'https://github.com/redis/hiredis-py/blob/master/LICENSE',
        },
        'importlib-metadata': {
            'license_name': 'Apache 2.0',
        },
        'isodate': {
            'license_url': 'https://github.com/gweis/isodate/blob/master/LICENSE',
        },
        'lark-parser': {
            'license_url': 'https://github.com/lark-parser/lark/blob/0.6.7/LICENSE',
        },
        'lark067': {
            'name': 'lark-parser',
            'version': vers['lark'],
            'gh_url': 'https://github.com/lark-parser/lark',
            'license_name': 'MIT',
            'license_url': f'https://github.com/lark-parser/lark/blob/{vers["lark"]}/LICENSE',
            'v': False,
        },
        'mmh3': {
            'license_name': 'CC0 1.0',
            'license_url': 'https://github.com/hajimes/mmh3/blob/master/LICENSE',
        },
        'neo4j': {
            'license_name': 'Apache 2.0',
            'license_url': 'https://github.com/neo4j/neo4j-python-driver/blob/4.2.1/LICENSE.txt',
        },
        'pep517': {
            'license_name': 'MIT',
        },
        'pfsc-test-modules': {
            'license_name': 'MPL-2.0',
            'license_url': 'https://github.com/proofscape/pfsc-test-modules/blob/main/LICENSE',
        },
        r'\bpy\b': {
            'gh_url': 'https://github.com/pytest-dev/py',
        },
        'pyparsing': {
            'license_name': 'MIT',
        },
        'python-dotenv': {
            'license_name': 'BSD',
        },
        'python-engineio': {
            'license_name': 'MIT',
        },
        'python-socketio': {
            'license_name': 'MIT',
        },
        'pytz': {
            'gh_url': 'https://github.com/stub42/pytz/tree/release_2021.3',
        },
        'rq': {
            'license_url': 'https://github.com/rq/rq/blob/v1.8.0/LICENSE',
        },
        'tomli': {
            'license_name': 'MIT',
        },
        'typing_extensions': {
            'gh_url': 'https://github.com/python/typing/tree/4.0.1',
            'license_name': 'PSF License',
        },
        'zipp': {
            'license_name': 'MIT',
        },
    }



MANUAL_JS_PKG_INFO = {
    '@socket.io/component-emitter': {
        'v': False,
    },
    'atoa': {
        'v': None,
    },
    'backo2': {
        'gh_url': 'https://github.com/mokesmokes/backo',
        'license_url': 'https://github.com/mokesmokes/backo/blob/280597dede9a7c97ff47a3fa01f3b412c1d94438/LICENSE',
        'v': None,
    },
    'custom-event': {
        'license_url': 'https://github.com/webmodules/custom-event/blob/725c41146f970df345d57cd97b2bf5acd6c8e9f7/LICENSE',
        'v': False,
    },
    'debug': {
        'v': False,
    },
    'dijit': {
        'license_name': 'BSD-3-Clause',
        'v': False,
    },
    'dojo-util': {
        'license_name': 'BSD-3-Clause',
        'v': False,
    },
    'dojox': {
        'license_name': 'BSD-3-Clause',
        'v': False,
    },
    '^dojo$': {
        'license_name': 'BSD-3-Clause',
        'v': False,
    },
    # elkjs is currently lacking a tag for v0.8.1, so we hard code the URLs
    'elkjs': {
        'gh_url': 'https://github.com/kieler/elkjs',
        'license_url': 'https://github.com/kieler/elkjs/blob/master/LICENSE.md',
        'v': None,
    },
    'engine.io-client': {
        'v': False,
    },
    'engine.io-parser': {
        'v': False,
    },
    # has-cors is a funny case.
    # The `license_url` is for use in an "About" dialog in a JS program. It links
    # to some page that gives some indication as to the license under which the
    # library is released.
    # The `license_not_provided` is to guide us when generating the combined
    # license file for inclusion in the OCA docker image. It tells us that
    # there's nothing we can provide for this library.
    'has-cors': {
        'license_url': 'https://github.com/component/has-cors/blob/27e9b96726b669e9594350585cc1e97474d3f995/Readme.md',
        'license_not_provided': True,
        'v': False,
    },
    'http-parser-js': {
        'v': None,
    },
    'jquery': {
        'v': False,
    },
    'mathjax': {
        'gh_url': 'https://github.com/mathjax/MathJax',
        'v': False,
    },
    '^ms$': {
        'gh_url': 'https://github.com/vercel/ms',
        'v': False,
    },
    'nanobar': {
        'gh_url': 'https://github.com/jacoborus/nanobar',
    },
    'popper.js': {
        'license_url': 'https://github.com/floating-ui/floating-ui/blob/v1.16.1/LICENSE.md',
    },
    'socket.io-client': {
        'v': False,
    },
    'socket.io-parser': {
        'v': False,
    },
    'webcola': {
        'v': None,
    },
    'webextension-polyfill': {
        'v': False,
    },
    'websocket-driver': {
        'v': False,
    },
    'websocket-extensions': {
        'v': False,
    },
    '^ws$': {
        'v': False,
    },
    'xmlhttprequest-ssl': {
        'license_name': "MIT",
        'v': False,
    },
    'yeast': {
        'v': False,
    }
}

def get_pyodide_pkg_info_lookup():
    vers = get_version_numbers()
    m = get_manual_py_pkg_info_lookup()
    return {

        ###########################
        # Packages loaded as wheels
        ###########################

        'pyodide': JsPackage(
            name='pyodide',
            version=vers['pyodide'],
            gh_url='https://github.com/pyodide/pyodide',
            license_name='MPL-2.0',
            license_url=f'https://github.com/pyodide/pyodide/blob/{vers["pyodide"]}/LICENSE',
            v=False,
        ),
        'sympy': m[r'github\.com/proofscape/sympy'],
        'pfsc-examp': m[r'github\.com/proofscape/pfsc-examp'],
        'displaylang': PyPackage(
            name='displaylang',
            version=vers['displaylang'],
            gh_url='https://github.com/proofscape/displaylang',
            license_name='Apache 2.0',
            license_url='https://www.apache.org/licenses/LICENSE-2.0.txt',
            v=None,
        ),
        'lark-parser': PyPackage(
            name='lark-parser',
            version=vers['lark'],
            gh_url='https://github.com/lark-parser/lark',
            license_name='MIT',
            license_url=f'https://github.com/lark-parser/lark/blob/{vers["lark"]}/LICENSE',
            v=False,
        ),
        'typeguard': PyPackage(
            name='typeguard',
            version=vers['typeguard'],
            gh_url='https://github.com/agronholm/typeguard',
            license_name='MIT',
            license_url=f'https://github.com/agronholm/typeguard/blob/{vers["typeguard"]}/LICENSE',
            v=False,
        ),
        'pfsc-util': m[r'github\.com/proofscape/pfsc-util'],

        ###############################################
        # Packages loaded from the Pyodide distribution
        ###############################################

        'mpmath': PyPackage(
            name='mpmath',
            version=vers['mpmath'],
            gh_url='https://github.com/fredrik-johansson/mpmath',
            license_name='BSD-3-Clause',
            license_url=f'https://github.com/fredrik-johansson/mpmath/blob/{vers["mpmath"]}/LICENSE',
            v=False,
        ),
        'Jinja2': PyPackage(
            name='Jinja2',
            version=vers['Jinja2'],
            gh_url='https://github.com/pallets/jinja/',
            license_name='BSD-3-Clause',
            license_url=f'https://github.com/pallets/jinja/blob/{vers["Jinja2"]}/LICENSE.rst',
            v=False,
        ),
        'MarkupSafe': PyPackage(
            name='MarkupSafe',
            version=vers['MarkupSafe'],
            gh_url='https://github.com/pallets/markupsafe',
            license_name='BSD-3-Clause',
            license_url=f'https://github.com/pallets/markupsafe/blob/{vers["MarkupSafe"]}/LICENSE.rst',
            v=False,
        ),
    }

def get_other_pkg_info_lookup():
    vers = get_version_numbers()
    return {
        'pdfjs': JsPackage(
            name='pdf.js',
            version=f"(Proofscape fork v{vers['pfsc-pdf']})",
            gh_url='https://github.com/proofscape/pfsc-pdf',
            license_name='Apache 2.0',
            license_url='https://www.apache.org/licenses/LICENSE-2.0.txt',
            v=None,
        ),
    }

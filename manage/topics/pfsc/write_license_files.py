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

from collections import defaultdict
import json
import pathlib
import re
import subprocess
import sys

import jinja2


def check_present_python_pkgs(image=None):
    """
    Use `pip freeze` to determine the actual list of python packages that are
    present.
    """
    pip_line = re.compile(r'([-a-zA-Z0-9_]+)==(\d+(\.\d+)*)')
    present_pkgs = set()
    if image:
        # For use in testing on localhost
        cmd = f'docker run --rm --entrypoint=bash {image} -c "pip freeze"'
    else:
        # For use during a docker build, inside the building image
        cmd = 'pip freeze'
    out = subprocess.check_output(cmd, shell=True)
    lines = out.decode().split('\n')
    for line in lines:
        if M := pip_line.match(line):
            present_pkgs.add(M.group(1))
    return present_pkgs


def make_combined_license_list(pkgs):
    """
    Given a list of "packages", assemble the giant block of text that is the
    concatenation of all their licenses texts, with at least some grouping,
    where stripped licenses are the same.

    Here a "package" is a dictionary with the fields 'name', 'src_url', and
    'license_text'.
    """
    # We try to group software having the same license text after stripping of
    # exterior whitespace.
    d = defaultdict(list)
    for p in pkgs:
        t = p['license_text']
        if t:
            d[t.strip()].append(p)

    # FIXME
    #  I would have expected better grouping. We're getting 83 groups, for
    #  103 software packages (in the OCA). Why, e.g. so many different versions of Apache?
    #  Should try to do better. For now this is good enough.

    # Examine grouping:
    # print()
    # print(f'{len(pkgs)} packages')
    # print(f'{len(d.keys())} groups')
    # print()
    # v = sorted(list(d.values()), key=lambda a: len(a))
    # for a in v:
    #    print(f'{len(a)}: {" ".join([f"({p.license_name}/{p.name})" for p in a])}')

    # Generate all the license blocks for all the packages:
    other_license_list = []
    for G in d.values():
        header = ''
        license = ''
        for p in G:
            header += f'  {p["name"]}\n    {p["src_url"]}\n'
            t = p['license_text']
            if len(t) > len(license):
                license = t
        block = 'The license for:\n\n' + header + '\nis:\n\n' + license
        other_license_list.append(block)
    divider = '\n' + ("~" * 79 + '\n') * 2
    other_licenses = divider.join(other_license_list)
    return other_licenses


def get_template(image_name):
    """
    For use in testing on the host. Grabs the appropriate license file template.

    image_name: one of 'oca', 'server', 'frontend'.
    """
    p = pathlib.Path(__file__).parent / 'templates' / f'combined_license_file_{image_name}.txt'
    with open(p, 'r') as f:
        text = f.read()
    return text


def assemble_notices(license_info, image_name):
    """
    Build the NOTICE.txt file contents for a given image.

    license_info: as passed to each of the `build_..._files` functions
    image_name: one of 'oca', 'server', 'frontend'
    """
    notice_info = license_info['notices']
    divider = '-' * 79 + '\n'
    notice_txt = divider.join(
        n['text'] for n in notice_info
        if image_name in n['usage']
    )
    return notice_txt


def build_oca_files(license_info, license_template=None, image_tag='testing'):
    """
    Build the files for the oca image.

    In testing on the host, can call this function directly.
    `license_info` should be as computed by `tools.license.gather_licensing_info()`.
    """
    if license_template is None:
        license_template = get_template('oca')
    template = jinja2.Template(license_template)

    image = None if __name__ == "__main__" else f"pise:{image_tag}"
    present_python_pkgs = check_present_python_pkgs(image)

    pyodide_python_packages = '\n'.join(
        v for k, v in license_info['pyodide_package_two_liners'].items()
    )

    python_packages = '\n'.join(
        v for k, v in license_info['python_package_two_liners'].items()
        if k in present_python_pkgs and k not in [
            # Don't repeat packages that already got special mention.
            'sympy',
        ]
    )

    javascript_packages = '\n'.join(
        v for k, v in license_info['javascript_package_two_liners'].items()
        if k not in [
            # Don't repeat packages that already got special mention.
            '@proofscape/pise-client', 'mathjax',
            'pyodide', 'pdf.js',
        ]
    )

    licenses_txt = template.render(
        credits=license_info['credits'],
        pyodide_python_packages=pyodide_python_packages,
        python_packages=python_packages,
        javascript_packages=javascript_packages,
        pfsc_server_Apache=license_info['special_licenses']['pise'],
        RSAL=license_info['special_licenses']['RSAL'],
        redis_BSD=license_info['special_licenses']['redis'],
        supervisor_license=license_info['special_licenses']['supervisor'],
        PSF_license = license_info['special_licenses']['PSF'],
        other_licenses=make_combined_license_list(license_info['licenses']),
        gcc_runtime=license_info['special_licenses']['gcc_runtime'],
        gpl3=license_info['special_licenses']['gpl3']
    )

    divider = '-'*79 + '\n'
    notice_txt = divider.join(license_info['oca_about_info']['notices'])

    about_json = json.dumps(license_info['oca_about_info'], indent=4)

    return licenses_txt, notice_txt, about_json


def build_server_files(license_info, license_template=None, image_tag='testing'):
    """
    Build the files for the server image.

    In testing on the host, can call this function directly.
    `license_info` should be as computed by `tools.license.gather_licensing_info()`.
    """
    if license_template is None:
        license_template = get_template('server')
    template = jinja2.Template(license_template)

    image = None if __name__ == "__main__" else f"pise-server:{image_tag}"
    present_python_pkgs = check_present_python_pkgs(image)

    python_packages = '\n'.join(
        v for k, v in license_info['python_package_two_liners'].items()
        if k in present_python_pkgs
    )

    other_licenses = make_combined_license_list([
        info for info in license_info['licenses']
        if info['name'] in present_python_pkgs
    ])

    licenses_txt = template.render(
        credits=license_info['credits'],
        python_packages=python_packages,
        pfsc_server_Apache=license_info['special_licenses']['pise'],
        PSF_license = license_info['special_licenses']['PSF'],
        other_licenses=other_licenses,
    )

    notice_txt = assemble_notices(license_info, 'server')

    return licenses_txt, notice_txt


def build_frontend_files(license_info, license_template=None):
    """
    Build the files for the frontend image.

    In testing on the host, can call this function directly.
    `license_info` should be as computed by `tools.license.gather_licensing_info()`.
    """
    if license_template is None:
        license_template = get_template('frontend')
    template = jinja2.Template(license_template)

    pyodide_python_packages = '\n'.join(
        v for k, v in license_info['pyodide_package_two_liners'].items()
    )

    javascript_packages = '\n'.join(
        v for k, v in license_info['javascript_package_two_liners'].items()
        if k not in [
            # Don't repeat packages that already got special mention.
            '@proofscape/pise-client', 'mathjax',
            'pyodide', 'pdf.js',
        ]
    )

    other_licenses = make_combined_license_list([
        info for info in license_info['licenses']
        if info['name'] in license_info['javascript_package_two_liners']
    ])

    licenses_txt = template.render(
        credits=license_info['credits'],
        pyodide_python_packages=pyodide_python_packages,
        javascript_packages=javascript_packages,
        nginx_license=license_info['special_licenses']['nginx'],
        other_licenses=other_licenses,
    )

    notice_txt = assemble_notices(license_info, 'frontend')

    return licenses_txt, notice_txt


def build_files(license_info, license_template, image_name):
    """
    Return list of tuples (filename, file contents) defining the license files
    that are to be written into the image.
    """
    if image_name == 'oca':
        licenses_txt, notice_txt, about_json = build_oca_files(license_info, license_template)
        return [
            ("LICENSES.txt", licenses_txt),
            ("NOTICE.txt", notice_txt),
            ("about.json", about_json),
        ]
    elif image_name == 'server':
        licenses_txt, notice_txt = build_server_files(license_info, license_template)
        return [
            ("LICENSES.txt", licenses_txt),
            ("NOTICE.txt", notice_txt),
        ]
    elif image_name == 'frontend':
        licenses_txt, notice_txt = build_frontend_files(license_info, license_template)
        return [
            ("LICENSES.txt", licenses_txt),
            ("NOTICE.txt", notice_txt),
        ]


def main():
    """
    Designed to be run from the commandline while in a docker build.
    Reads license info and Jinja2 template from sibling files,
        license_info.json
        license_template.txt
    and writes the generated license files into an `output` subdirectory (which
    need not already exist, but may).
    """
    # The license_info.json and license_template.txt files must be present:
    with open('./license_info.json', 'r') as f:
        license_info = json.load(f)
    with open('./license_template.txt', 'r') as f:
        license_template = f.read()
    # The name of the image must be passed as argument.
    # Should be one of 'oca', 'server', 'frontend'.
    image_name = sys.argv[1]
    files = build_files(license_info, license_template, image_name)
    outputdir = pathlib.Path('.') / 'output'
    outputdir.mkdir(exist_ok=True)
    for filename, contents in files:
        with open(outputdir / filename, 'w') as f:
            f.write(contents)


if __name__ == "__main__":
    main()

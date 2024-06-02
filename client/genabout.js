/* ------------------------------------------------------------------------- *
 *  Copyright (c) 2011-2024 Proofscape Contributors                          *
 *                                                                           *
 *  Licensed under the Apache License, Version 2.0 (the "License");          *
 *  you may not use this file except in compliance with the License.         *
 *  You may obtain a copy of the License at                                  *
 *                                                                           *
 *      http://www.apache.org/licenses/LICENSE-2.0                           *
 *                                                                           *
 *  Unless required by applicable law or agreed to in writing, software      *
 *  distributed under the License is distributed on an "AS IS" BASIS,        *
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. *
 *  See the License for the specific language governing permissions and      *
 *  limitations under the License.                                           *
 * ------------------------------------------------------------------------- */

// Generate the software table rows for the "About" dialog.
// Invoked by Webpack as a loader, replacing the contents of the
// `piseAboutDialogContents.js` module.

const path = require('path');
const fsPromises = require('fs').promises;
const makeRow = require('./src/dialog');

/* Pass package-lock.json. Get array of recursive production dependencies, by name.
 */
function listDeps(plj) {
    const packages = plj.packages;
    const allDeps = [];
    let deps = packages[""].dependencies;
    const queue = [deps];
    while (queue.length) {
        deps = queue.shift();
        for (let name in deps) {
            if (deps.hasOwnProperty(name)) {
                if (!allDeps.includes(name)) {
                    allDeps.push(name);
                    let nextDeps = packages[`node_modules/${name}`]?.dependencies || {};
                    queue.push(nextDeps);
                }
            }
        }
    }
    return allDeps;
}

function normalizeRepoUrl(url) {
    // Ensure https is the protocol
    const i0 = url.indexOf(":")
    url = 'https' + url.slice(i0);
    // Don't want to end with a '/' or with '.git'
    if (url.slice(-1) === '/') {
        url = url.slice(0, -1);
    }
    if (url.slice(-4) === '.git') {
        url = url.slice(0, -4);
    }
    return url
}

/* Search a package directory for the name of its license file.
 * Return the name, or `null` if it couldn't be found.
 */
function findLicenseFilename(projName) {
    const dir = `node_modules/${projName}`;
    const options = ["LICENSE", "LICENCE", "COPYING"];
    return fsPromises.readdir(dir).then(files => {
        for (let file of files) {
            const p = file.split('.');
            if ([1, 2].includes(p.length) && options.includes(p[0].toUpperCase())) {
                return file;
            }
        }
        return null;
    });
}

const GITHUB_REPO_URL = /[^:]+:\/\/github.com\/[^\/]+\/[^\/]+\/?$/;

class JsPackage {

    constructor({name, version, license}) {
        this.name = name;
        this.version = version;
        this.license = license;

        this.gh_url = null;
        this.license_url = null;
        /* `this.v` controls how we generate a ref, for use in the license URL.
         *   null: use 'master'
         *   false: use this.version
         *   true: use v${this.version}
         *   any other value is used as given (e.g. 'main')
         */
        this.v = false;
        this.license_filename = null;
    }

    async findLicenseFilename() {
        this.license_filename = await findLicenseFilename(this.name);
    }

    lookForGhUrlInPackageInfo(info) {
        let gh_url = null;
        let repo_url = null;
        let hp_url = null;
        const repoInfo = info.repository || {};
        if (typeof repoInfo === 'string' || repoInfo instanceof String) {
            repo_url = repoInfo;
        } else {
            repo_url = repoInfo.url || '';
        }
        if (GITHUB_REPO_URL.test(repo_url)) {
            gh_url = repo_url;
        }
        if (!gh_url) {
            hp_url = info.homepage || '';
            if (GITHUB_REPO_URL.test(hp_url)) {
                gh_url = hp_url;
            }
        }
        if (gh_url) {
            this.gh_url = normalizeRepoUrl(gh_url);
        }
    }

    acceptManualInfo(info) {
        if ('license_name' in info) {
            this.license = info.license_name;
        }
        for (let field of ['gh_url', 'license_url', 'v']) {
            if (field in info) {
                this[field] = info[field];
            }
        }
    }

    get projName() { return this.name; }

    get projURL() {
        return this.gh_url;
    }

    get licName() { return this.license; }

    get licURL() {
        if (this.license_url) {
            return this.license_url;
        }
        const filename = this.license_filename;
        if (filename === null) {
            return "#";
        }
        const v = this.v;
        const ref = v === null ? 'master' :
                    v === true ? `v${this.version}` :
                    v === false ? this.version : v;
        return `${this.gh_url}/blob/${ref}/${filename}`;
    }

}

const MANUAL_PKG_INFO = {
    'atoa': {
        'v': null,
    },
    'backo2': {
        'gh_url': 'https://github.com/mokesmokes/backo',
        'license_url': 'https://github.com/mokesmokes/backo/blob/280597dede9a7c97ff47a3fa01f3b412c1d94438/LICENSE',
        'v': null,
    },
    'custom-event': {
        'license_url': 'https://github.com/webmodules/custom-event/blob/725c41146f970df345d57cd97b2bf5acd6c8e9f7/LICENSE',
    },
    'dijit': {
        'license_name': 'BSD-3-Clause',
    },
    'dojo-util': {
        'license_name': 'BSD-3-Clause',
    },
    'dojox': {
        'license_name': 'BSD-3-Clause',
    },
    'dojo': {
        'license_name': 'BSD-3-Clause',
    },
    // elkjs is currently lacking a tag for v0.8.1, so we hard code the URLs
    'elkjs': {
        'license_url': 'https://github.com/kieler/elkjs/blob/master/LICENSE.md',
        'v': null,
    },
    'has-cors': {
        'license_url': 'https://github.com/component/has-cors/blob/27e9b96726b669e9594350585cc1e97474d3f995/Readme.md',
    },
    'mathjax': {
        'gh_url': 'https://github.com/mathjax/MathJax',
    },
    'ms': {
        'gh_url': 'https://github.com/vercel/ms',
    },
    'nanobar': {
        'gh_url': 'https://github.com/jacoborus/nanobar',
    },
    'webcola': {
        'v': null,
    },
    'xmlhttprequest-ssl': {
        'license_name': "MIT",
    },
};

// Here, `name` must always match the name used in other-version.json:
const OTHER_PKG_INFO = [
    {
        name: 'pfsc-pdf',
        displayName: 'pdf.js',
        version: v => `(Proofscape fork v${v})`,
        licName: 'Apache 2.0',
    },
    {
        name: 'displaylang-sympy',
        displayName: 'sympy',
        version: v => `(DisplayLang fork v${v})`,
        projURL: 'https://github.com/proofscape/sympy',
        licName: "BSD",
        licURL: v => `https://github.com/proofscape/sympy/blob/v${v}/LICENSE`,
    },
    {
        name: 'pyodide',
        projURL: 'https://github.com/pyodide/pyodide',
        licName: 'MPL-2.0',
        licURL: v => `https://github.com/pyodide/pyodide/blob/${v}/LICENSE`,
    },
    {
        name: 'pfsc-examp',
        licName: 'Apache 2.0',
    },
    {
        name: 'displaylang',
        licName: 'Apache 2.0',
    },
    {
        name: 'pfsc-util',
        licName: 'Apache 2.0',
    },
    {
        name: 'lark',
        displayName: 'lark-parser',
        projURL: 'https://github.com/lark-parser/lark',
        licName: "MIT",
        licURL: v => 'https://github.com/lark-parser/lark/blob/0.6.7/LICENSE',
    },
    {
        name: 'typeguard',
        projURL: 'https://github.com/agronholm/typeguard',
        licName: "MIT",
        licURL: v => `https://github.com/agronholm/typeguard/blob/${v}/LICENSE`,
    },
    {
        name: 'mpmath',
        projURL: 'https://github.com/fredrik-johansson/mpmath',
        licName: 'BSD-3-Clause',
        licURL: v => `https://github.com/fredrik-johansson/mpmath/blob/${v}/LICENSE`,
    },
    {
        name: 'Jinja2',
        projURL: 'https://github.com/pallets/jinja',
        licName: 'BSD-3-Clause',
        licURL: v => `https://github.com/pallets/jinja/blob/${v}/LICENSE.rst`,
    },
    {
        name: 'MarkupSafe',
        projURL: 'https://github.com/pallets/markupsafe',
        licName: 'BSD-3-Clause',
        licURL: v => `https://github.com/pallets/markupsafe/blob/${v}/LICENSE.rst`,
    },
];

module.exports = async function loader(source) {
    const pjPath = path.resolve('package.json');
    const pljPath = path.resolve('package-lock.json');
    const ovjPath = path.resolve('other-versions.json');
    this.addDependency(pjPath);
    this.addDependency(pljPath);
    this.addDependency(ovjPath);
    const pj = require(pjPath);
    const plj = require(pljPath);
    const ovj = require(ovjPath);

    let js = "export const softwareTableRows = `\n";

    const ownProjURL = normalizeRepoUrl(pj.repository.url);
    let ownProjName = pj.name;
    // For the software table, we want to use the unscoped package name
    if (ownProjName.startsWith("@proofscape/")) {
        ownProjName = ownProjName.slice(12);
    }
    js += makeRow({
        projName: ownProjName,
        projURL: ownProjURL,
        version: pj.version,
        licName: pj.license,
        licURL: `${ownProjURL}/blob/v${pj.version}/LICENSE`,
    });

    for (let info of OTHER_PKG_INFO) {
        const vnum = ovj[info.name];
        const version = info.version ? info.version(vnum) : vnum;
        const licURL = info.licURL ? info.licURL(vnum) : `https://github.com/proofscape/${info.name}/blob/v${vnum}/LICENSE`;
        js += makeRow({
            projName: info.displayName || info.name,
            projURL: info.projURL || `https://github.com/proofscape/${info.name}`,
            version: version,
            licName: info.licName,
            licURL: licURL,
        });
    }

    const allDeps = listDeps(plj);
    for (let projName of allDeps) {
        const pkgPath = path.resolve(`node_modules/${projName}/package.json`);
        this.addDependency(pkgPath);

        const pkgInfo = require(pkgPath);
        const manualInfo = MANUAL_PKG_INFO[projName];

        const pkg = new JsPackage(pkgInfo);
        pkg.lookForGhUrlInPackageInfo(pkgInfo);
        if (manualInfo) {
            pkg.acceptManualInfo(manualInfo);
        }
        await pkg.findLicenseFilename();

        js += makeRow(pkg);
    }

    js += "`;\n";
    return js;
}

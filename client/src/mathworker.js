/* ------------------------------------------------------------------------- *
 *  Copyright (c) 2011-2023 Proofscape Contributors                          *
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


import { DedicatedWorkerPeer } from "browser-peers/src/dedworkerpeer";


const ise = {};
define([
    "ise/errors",
], function(
    iseErrors,
) {
    ise.errors = iseErrors;
});
const mathworkerErrorCodes = ise.errors.mathworkerErrorCodes;


const pyodidePackages = [
    "micropip",
    "Jinja2",
    "mpmath",
];


const pyodideImports = [
    'import pfsc_examp',
];


function echo(args, meta) {
    console.log('echo', args, meta);
    return 'echoed';
}


function ping(args) {
    return 'pong';
}


function startup(args) {
    self.pfscExampConfig = args.pfscExampConfig;
    let indexURL = args.pyodideIndexURL;
    if (!indexURL.endsWith('/')) {
        indexURL += '/';
    }
    const pyodideJsURL = indexURL + 'pyodide.js';
    importScripts(pyodideJsURL);

    let code = 'import micropip\n';

    const noDeps = args.micropipNoDeps ? ', deps=False' : '';
    code += `await micropip.install(${JSON.stringify(args.micropipInstallTargetsArray)}${noDeps})\n`;

    for (let imp of pyodideImports) {
        code += `${imp}\n`;
    }

    // Final expression makes the return value.
    // (See https://pyodide.org/en/stable/usage/api/js-api.html#pyodide.runPythonAsync)
    // We grab info about the installed packages.
    code += '{k:vars(v) for k, v in micropip.list().items()}\n';

    console.debug(code);

    self.pyoReady = new Promise(resolve => {
        loadPyodide({indexURL: indexURL}).then(pyodide => {
            self.pyodide = pyodide;
            pyodide.loadPackage(pyodidePackages).then(() => {
                pyodide.runPythonAsync(code).then(pkginfoProxy => {
                    const pkginfo = pkginfoProxy.toJs();
                    pkginfoProxy.destroy();
                    resolve({
                        status: 0,
                        message: 'loaded Pyodide and all packages',
                        // Up to v0.21.2, it's pyodide.version. In v0.21.3, it's pyodide.default.
                        pyodideVersion: pyodide.default || pyodide.version,
                        // pkginfo is a Map, in which package names point to Maps, in which
                        // the keys are 'name', 'version', and 'source'.
                        pkginfo: pkginfo,
                    });
                });
            });
        });
    });
    return self.pyoReady;
}


/* Make a new PyProxy for a widget.
 *
 * args: {
 *   info: the info object that defines the widget,
 *   paneId: the id of the pane where this representative is to be active.
 * }
 *
 * return: promise that resolves with new total number of proxies for this widget
 */
async function makePyProxy(args) {
    await self.pyoReady;
    const info = args.info;
    const paneId = args.paneId;
    const uid = info['uid'];
    const w = self.pfscisehub.notesManager.ensureWidget(uid);
    const makeObject = self.pyodide.globals.get('pfsc_examp').make_examp_generator_obj_from_js;
    const obj = makeObject(info, paneId);
    makeObject.destroy();  // destroy proxy of factory func to avoid memory leak
    w.addPyProxy(paneId, obj);
    return w.getNumProxies();
}


/* Destroy a single PyProxy for a widget. If this was the widget's
 * last proxy, also delete the widget from the NotesManager.
 *
 * args: {
 *   uid: the uid of the widget that wants to destroy a PyProxy
 *   paneId: the id of the pane whose proxy should be destroyed
 * }
 *
 * return: the new total number of proxies for this widget
 */
function destroyPyProxy(args) {
    const nm = self.pfscisehub.notesManager;
    const uid = args.uid;
    const paneId = args.paneId;
    const w = nm.getWidget(uid);
    if (w) {
        w.destroyProxy(paneId);
        const n = w.getNumProxies();
        if (n === 0) {
            nm.deleteWidget(uid);
        }
        return n;
    } else {
        return 0;
    }
}

/* Rebuild an examp widget.
 *
 * args: {
 *   uid: the widget uid,
 *   paneId: the id of the pane where we want to rebuild
 *   value: optional, new raw value to pass to this widget's `build` method
 *   writeHtml: bool, optional, default false: if true, ask the widget to
 *     generate its (new) HTML
 * }
 *
 * return: promise that resolves with the response from the `rebuild_examp_generator_from_js()`
 *   function in the pfsc-examp python package. This is a formatted object, which contains
 *   an error level, error message, and result value if successful.
 */
async function rebuild(args) {
    await self.pyoReady;
    const {
        uid,
        paneId,
        value = null,
        writeHtml = false,
    } = args;

    let respObj = {
        err_lvl: mathworkerErrorCodes.UNKNOWN,
        err_msg: 'unknown error',
    };

    const nm = self.pfscisehub.notesManager;
    const w = nm.getWidget(uid);
    if (!w) {
        respObj.err_lvl = mathworkerErrorCodes.MISSING_WIDGET;
        respObj.err_msg = `Missing widget for uid: ${uid}`;
        return respObj;
    }

    const obj = w.getPyProxyCopy(paneId);
    if (!obj) {
        respObj.err_lvl = mathworkerErrorCodes.MISSING_PY_PROXY;
        respObj.err_msg = `Missing PyProxy for uid/paneId: ${uid}/${paneId}`;
        return respObj;
    }

    const rebuildFunc = self.pyodide.globals.get('pfsc_examp').rebuild_examp_generator_from_js;
    const response = rebuildFunc.callKwargs(obj, {value: value, write_html: writeHtml});
    // Destroy PyProxy of `rebuild` to avoid memory leak.
    // `response` object does not need to be destroyed, since it was converted with `to_js()`
    // on the python side.
    rebuildFunc.destroy();
    // `response` is a Map. Convert to an Object.
    respObj = Object.fromEntries(response);
    return respObj;
}


class NotesManager {

    constructor() {
        this.widgets = new Map();
    }

    getWidget(uid) {
        return this.widgets.get(uid);
    }

    ensureWidget(uid) {
        if (this.widgets.has(uid)) {
            return this.widgets.get(uid);
        } else {
            const w = new Widget(uid);
            this.widgets.set(uid, w);
            return w;
        }
    }

    deleteWidget(uid) {
        this.widgets.delete(uid);
    }

}


class Widget {

    constructor(uid) {
        this.uid = uid;
        this.pyProxiesByPaneId = new Map();
    }

    addPyProxy(paneId, proxy) {
        this.pyProxiesByPaneId.set(paneId, proxy);
    }

    /* This method is intended for use by Python code running in Pyodide.
     * The reason for returning a *copy* of the PyProxy object we have stored
     * is that this prevents the PyProxy from being destroyed as a result of
     * being passed back to the Py side.
     * See:
     *   https://pyodide.org/en/stable/usage/type-conversions.html#calling-javascript-functions-from-python
     */
    getPyProxyCopy(paneId) {
        const proxy = this.pyProxiesByPaneId.get(paneId);
        if (!proxy) {
            return null;
        }
        return proxy.copy();
    }

    getNumProxies() {
        return this.pyProxiesByPaneId.size;
    }

    destroyProxy(paneId) {
        const p = this.pyProxiesByPaneId.get(paneId);
        if (p) {
            p.destroy();
            this.pyProxiesByPaneId.delete(paneId);
        }
    }

}


/* We build a dummy environment so that the same code that was designed to
 * work with Pyodide running in the main page can also work here.
 */
self.pfscisehub = {
    notesManager: new NotesManager(),
};


const peer = new DedicatedWorkerPeer(self);
peer.addHandler('echo', echo);
peer.addHandler('ping', ping);
peer.addHandler('startup', startup);
peer.addHandler('makePyProxy', makePyProxy);
peer.addHandler('destroyPyProxy', destroyPyProxy);
peer.addHandler('rebuild', rebuild);
peer.setReady();

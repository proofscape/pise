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

import { BasePageViewer } from "./BasePageViewer";

/* Note: One of the reasons to subclass the BasePageViewer is to overcome some
 * of the deficiencies of using the browser's built-in History API, i.e. simply
 * doing things like
 *     this.cw.history.back();
 * in order to navigate backward. Problems with the native API include:
 *  * No way to ask where we are in the history, and whether forward or backward
 *    navigation is currently possible.
 *  * Requesting backward navigation when no further backward nav is possible within
 *    an iframe can cause *the entire page* to navigate backward, unloading the ISE!
 */
export class SphinxViewer extends BasePageViewer {

    /*
     * param nm: The NotesManager.
     * param parent: The DOM element in which page content is to be set.
     * param pane: The ContentPane where parent lives.
     * param uuid: The uuid of the pane where parent lives.
     * param options: {
     *   overviewScale: desired initial scale for overview panel
     * }
     */
    constructor(nm, parent, pane, uuid, options) {
        super();

        // overviewScale option not (yet?) supported

        this.mgr = nm;
        this.pane = pane;
        this.uuid = uuid;

        const iframe = document.createElement('iframe');
        iframe.setAttribute('width', '100%');
        iframe.setAttribute('height', '100%');
        parent.appendChild(iframe);
        this.iframe = iframe;

        iframe.addEventListener('load', event => {
            this.handleFrameLoad();
        });

        this.resolvePageUpdate = null;
    }

    /* When the frame navigates to a new page, we get a new content window.
     * So we want a getter method for this, for a convenient way to always
     * be working with the current window.
     */
    get cw() {
        return this.iframe.contentWindow;
    }

    /* Handle the event of our iframe completing loading of a new page.
     */
    handleFrameLoad() {
        const sphinxPageInfo = this.spi;
        console.log(sphinxPageInfo);

        // Listen for hashchange within the page.
        this.cw.addEventListener('hashchange', event => {
            const sphinxPageInfo = this.spi;
            console.log(sphinxPageInfo);
            this.observeLocationChange();
        });

        // Is it a sphinx page?
        if (sphinxPageInfo) {
            // Apply global theme & zoom.
            this.setTheme(this.mgr.hub.currentTheme);
            this.setZoom(this.mgr.hub.currentGlobalZoom);

            // Remove Furo's light/dark toggle
            const buttons = this.cw.document.getElementsByClassName("theme-toggle");
            Array.from(buttons).forEach((btn) => {
                btn.remove();
            });

            this.activateWidgets();
        }

        this.observeLocationChange();
    }

    observeLocationChange() {
        const loc = this.getContentDescriptor();
        if (this.resolvePageUpdate) {
            // The location change resulted from a deliberate call to this.updatePage().
            // Let the Promise returned by that method now resolve.
            this.resolvePageUpdate();
            this.resolvePageUpdate = null;
        } else {
            // The location change did not result for a deliberate call to this.updatePage().
            // This means it must have resulted from the user clicking an <a> tag within the
            // panel. We must update our history accordingly.
            this.recordNewHistory(loc);
        }
    }

    activateWidgets() {
        // TODO
    }

    /* Extract the URL from a content descriptor object of SPHINX type.
     */
    makeUrlFromCdo(cdo) {
        let url = cdo.url;
        if (cdo.libpath && cdo.version) {
            // Libpath goes: host, owner, repo, '_sphinx', remainder...
            // For the URL we need the version tag in place of '_sphinx'.
            const parts = cdo.libpath.split('.');
            parts[3] = cdo.version;
            const hash = cdo.hash || '';
            url = `static/sphinx/${parts.join("/")}.html${hash}`
        }
        return url;
    }

    showOverviewSidebar(doShow) {
        // Not supported (yet)
    }

    async updatePage(loc) {
        return new Promise(resolve => {
            this.resolvePageUpdate = resolve;
            const url = this.makeUrlFromCdo(loc);
            this.cw.location = url;
        });
    }

    writeContentDescriptor(serialOnly) {
        // We have to consult our history, instead of calling
        // our `getContentDescriptor()` method, due to the behavior when the
        // TabContainerTree introduces a new split. When that happens, iframes that were
        // moved get reloaded, and, if we try to compute our state description
        // before we have finished reloading, we may report a URL like 'about:blank'.
        // Therefore we always use the last, stable, fully loaded content descriptor.
        const loc = this.getCurrentLoc() || {};
        return Object.assign({}, loc);
    }

    getCurrentLibpathv() {
        const loc = this.writeContentDescriptor();
        if (loc.libpath && loc.version) {
            return `${loc.libpath}@${loc.version}`;
        }
    }

    destroy() {
    }

    /* Set the theme on a single sphinx content window.
     */
    setTheme(theme) {
        if (this.spi) {
            // Note: This implementation relies on our use of the Furo theme.
            this.cw.document.body.dataset.theme = theme;
        }
    }

    /* Set the zoom level on a single sphinx content window.
     */
    setZoom(level) {
        if (this.spi) {
            this.cw.document.body.style.fontSize = level + "%";
        }
    }

    /* Determine whether our content window is currently at a locally hosted sphinx page,
     * and if so determine the libpath and version of that page, as well as any
     * in-page hash at which the window is currently located.
     *
     * return: object of the form {
     *   libpath: str,
     *   version: str,
     *   hash: str,
     * } if at a locally hosted sphinx page, else null.
     */
    get spi() {
        const frameLoc = this.cw.location;
        const pageLoc = window.location;
        let result = null;
        if (frameLoc.origin === pageLoc.origin) {
            let prefix = pageLoc.pathname;
            if (!prefix.endsWith('/')) {
                prefix += '/';
            }
            prefix += 'static/sphinx/';
            const framePath = frameLoc.pathname;
            if (framePath.startsWith(prefix) && framePath.endsWith('.html')) {
                const frameTail = framePath.slice(prefix.length, -5);
                const parts = frameTail.split('/');
                // Parts go: host, owner, repo, version, remainder...
                const version = parts[3];
                parts[3] = "_sphinx";
                const libpath = parts.join('.');
                const hash = frameLoc.hash;
                result = {libpath, version, hash};
            }
        }
        return result;
    }

    getContentDescriptor() {
        const cdo = this.spi || {};
        cdo.type = this.mgr.hub.contentManager.crType.SPHINX;
        cdo.url = this.cw.location.href;
        return cdo;
    }

}
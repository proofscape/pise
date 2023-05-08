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


export class SphinxController {

    constructor(mgr, cdo, pane, iframe) {
        this.mgr = mgr;
        this.initialCdo = cdo;
        this.lastLoadedCdo = null;
        this.pane = pane;
        this.iframe = iframe;

        iframe.addEventListener('load', event => {
            this.handleFrameLoad();
        });
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
        this.lastLoadedCdo = this.getContentDescriptor();
        const sphinxPageInfo = this.spi;
        console.log(sphinxPageInfo);

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

            // Listen for hashchange within the page.
            this.cw.addEventListener('hashchange', event => {
                this.lastLoadedCdo = this.getContentDescriptor();
                const sphinxPageInfo = this.spi;
                console.log(sphinxPageInfo);
            });

            this.activateWidgets();
        }
    }

    goForward() {
        return this.cw.history.forward();
    }

    goBackward() {
        return this.cw.history.back();
    }

    goTo(url) {
        this.cw.location = url;
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

    activateWidgets() {
        // TODO
    }
}

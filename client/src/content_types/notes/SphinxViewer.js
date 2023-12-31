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
        super(nm, "SPHINX");

        // overviewScale option not (yet?) supported

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

        this.resolveMovementInducedReload = null;
        this.promiseMovementInducedReload = Promise.resolve();

        this.subscriptionManager = nm.sphinxSubscriptionManager;
    }

    /* When the frame navigates to a new page, we get a new content window.
     * So we want a getter method for this, for a convenient way to always
     * be working with the current window.
     */
    get cw() {
        return this.iframe.contentWindow;
    }

    get contentElement() {
        return this.cw.document.querySelector('html');
    }

    get mainContentArea() {
        return this.cw.document.querySelector('.main');
    }

    get scrollNode() {
        return this.cw.document.querySelector('html');
    }

    pushScrollFrac() {
        super.pushScrollFrac();
        this.promiseMovementInducedReload = new Promise(resolve => {
            this.resolveMovementInducedReload = resolve;
        });
    }

    async popScrollFrac() {
        await this.promiseMovementInducedReload;
        await this.heightStable();
        await super.popScrollFrac();
    }

    // Return a promise that resolves when the height of the scroll node has been
    // stable for 100ms, or has failed to do so for 2s, whichever comes first.
    heightStable() {
        return new Promise(resolve => {
            const maxTries = 20;
            let numTries = 0;
            let h0 = this.scrollNode.scrollHeight;
            console.debug(h0);
            const ival = this.cw.setInterval(() => {
                const h1 = this.scrollNode.scrollHeight;
                console.debug(h1);
                if (h1 === h0 || numTries > maxTries) {
                    this.cw.clearInterval(ival);
                    resolve();
                } else {
                    h0 = h1;
                    numTries++;
                }
            }, 100);
        });
    }

    /* When a Sphinx page is sufficiently narrow, it gains a visible header bar.
     * We have to account for this in autoscroll, to ensure objects wind up visible,
     * and not hidden behind the bar.
     *
     * Note: This solution also adds unnecessary padding at the bottom of the window.
     * Eventually we might want a more refined system, where we can add it just at the
     * top.
     */
    addScrollPadding(options) {
        let px = options.padPx || 0;
        const header = this.cw.document.querySelector('header.mobile-header');
        px += header.offsetHeight;
        options.padPx = px;
    }

    typeset(elements) {
        return super.typeset(elements, this.cw);
    }

    /* Handle the event of our iframe completing loading of a new page.
     */
    handleFrameLoad() {
        // Listen for hashchange within the page.
        this.cw.addEventListener('hashchange', event => {
            console.debug(this.spi);
            this.observeLocationChange();
        });

        const hub = this.mgr.hub;
        hub.markPyodideLoadedInDocument(this.cw.document, hub.pyodideIsLoaded());

        this.setupBackgroundClickHandler();
        this.attachContextMenu(this.iframe, '.main', ['source']);
        this.updateContextMenu(this.getContentDescriptor());

        // Is it a sphinx page?
        const sphinxPageInfo = this.spi;
        console.debug(sphinxPageInfo);
        if (sphinxPageInfo) {
            // Apply global theme & zoom.
            this.setTheme(this.mgr.hub.currentTheme);
            this.setZoom(this.mgr.hub.currentGlobalZoom);

            // Remove Furo's light/dark toggle
            const buttons = this.cw.document.getElementsByClassName("theme-toggle");
            Array.from(buttons).forEach((btn) => {
                btn.remove();
            });

            // Add custom CSS
            const styleScript = this.cw.document.createElement("script");
            styleScript.type = "text/javascript";
            styleScript.src = this.mgr.hub.urlFor('staticISE') + "/sphinxpage.js";
            this.cw.document.querySelector('body').appendChild(styleScript);

            this.activateWidgets();
            this.customizeInternalLinks();
        }

        this.observeLocationChange();
    }

    observeLocationChange() {
        if (this.resolvePageUpdate) {
            // The location change resulted from a deliberate call to this.updatePage().
            // Let the Promise returned by that method now resolve.
            // No need to manage history here, since it was already handled elsewhere.
            this.resolvePageUpdate();
            this.resolvePageUpdate = null;
        } else if (this.resolveMovementInducedReload) {
            // The page was reloaded due to the iframe being moved in the document.
            this.resolveMovementInducedReload();
            this.resolveMovementInducedReload = null;
        }
    }

    activateWidgets() {
        const data = this.cw.pfsc_page_data;
        console.debug('page data:', data);
        this.currentPageData = data;
        const elt = this.cw.document.body;
        this.mgr.setupWidgets(data, elt, this.pane);
    }

    /* Get the URL of the top-level window, and make sure it is "clean," meaning
     * that it does *not* have any trailing `#`.
     */
    getCleanTopLevelWindowUrl() {
        // We don't use `window.location.href`, since that will include
        // any trailing `#` that may have been added to the page URL due to
        // clicks on various <a> tags that use that. Instead, use `origin`
        // plus `pathname`.
        return window.location.origin + window.location.pathname;
    }

    /* Unfortunately, when the user clicks a link in an iframe, the web browser does
     * not update the `src` attribute of the `iframe` element. For us, it's important
     * that the `src` attribute stay up to date, because if the iframe is moved in the
     * DOM (due to changes in the TCT splits), the frame is going to reload at this
     * address.
     */
    customizeInternalLinks() {
        // Note: We do not just search for 'a.internal', because there are `a` tags in Sphinx
        // pages that *are* internal, but do *not* have this class. (They have other classes, like
        // 'sidebar-brand', 'next-page', and 'prev-page'.) So, we grab *all* the `a` tags, and then
        // determine by checking their `href` whether they are internal or not.
        const links = this.cw.document.querySelectorAll('a');

        const pisePageUrl = this.getCleanTopLevelWindowUrl();
        let sphinxRootUrl = pisePageUrl;
        if (!sphinxRootUrl.endsWith('/')) {
            sphinxRootUrl += '/';
        }
        sphinxRootUrl += 'static/sphinx/';

        for (const link of links) {
            const hrefAsWritten = link.getAttribute('href');
            // In testing, I found that for hash navigations within the same page, setting
            // the iframe's `src` attribute does not cause the desired navigation. So we leave
            // those links alone.
            if (!hrefAsWritten.startsWith("#")) {
                // In both Chrome and Firefox, the `.href` property of an anchor element returns the absolute URL,
                // starting with scheme, even when the text of the 'href' attribute is relative.
                const absoluteUrl = link.href;
                if (absoluteUrl.startsWith(sphinxRootUrl)) {
                    // It appears to be an internal link (to the collection of Sphinx pages).
                    const urlRelativeToPisePage = absoluteUrl.slice(pisePageUrl.length);
                    link.setAttribute('href', '#');
                    (url => {
                        link.addEventListener('click', () => {
                            const loc = this.urlToFullLoc(url);
                            this.goTo(loc);
                        });
                    })(urlRelativeToPisePage);
                }
            }
        }
    }

    /* Extract the URL from a content descriptor object of SPHINX type.
     */
    makeUrlFromCdo(cdo) {
        let url = cdo.url;
        if (cdo.libpath && cdo.version) {
            url = this.mgr.makeSphinxUrl(cdo.libpath, cdo.version, cdo.hash);
        }
        return url;
    }

    showOverviewSidebar(doShow) {
        // Not supported (yet)
    }

    async refresh(url) {
        const loc = {url};
        const current = this.describeCurrentLocation();
        if (current) {
            loc.scrollFrac = current.scrollFrac;
            loc.scrollSel = current.scrollSel;
        }
        await super.reloadPage(loc);
    }

    async pageContentsUpdateStep(loc) {
        let url = null;

        const update = this.describeLocationUpdate(loc);
        if (update.pageChange) {
            url = this.makeUrlFromCdo(loc);
        }

        return !url ? Promise.resolve() : new Promise(resolve => {
                // Store the resolution function to be called later, from `observeLocationChange()`,
                // after the page has finished loading.
                this.resolvePageUpdate = resolve;
                this.iframe.src = url;
            });
    }

    locIsAtWip(loc) {
        let version = '';
        if (loc.version) {
            version = loc.version;
        } else if (loc.url) {
            const parts = this.mgr.decomposeSphinxUrl(loc.url);
            version = parts.version;
        }
        return version === "WIP";
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

    /* Set the theme on a single sphinx content window.
     */
    setTheme(theme) {
        if (this.spi) {
            // Note: This implementation relies on our use of the Furo theme.
            this.cw.document.body.dataset.theme = theme;
            // We also use some of the same CSS that we apply to anno pages, so we
            // need to set the same theme classes.
            if (theme === 'dark') {
                this.cw.document.body.classList.add('themeDark');
            } else {
                this.cw.document.body.classList.remove('themeDark');
            }
        }
    }

    /* Set the zoom level on a single sphinx content window.
     */
    setZoom(level) {
        if (this.spi) {
            this.cw.document.body.style.fontSize = level + "%";
        }
    }

    /* spi = "Sphinx page info"
     * Determine whether our content window is currently at a locally hosted sphinx page,
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
            const framePath = frameLoc.pathname;
            if (framePath.startsWith(prefix)) {
                const frameTail = framePath.slice(prefix.length);
                result = this.mgr.decomposeSphinxUrl(frameTail);
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

    /* If the content descriptor has a url, ensure that it is a relative one, starting
     * with 'static/sphinx/'.
     *
     * If there is a url, but missing either libpath or version, then derive the latter
     * from the url.
     */
    normalizeHistoryRecord(rec) {
        super.normalizeHistoryRecord(rec);
        if (rec.url) {
            let url = rec.url;
            const pageUrl = this.getCleanTopLevelWindowUrl();
            if (url.startsWith(pageUrl)) {
                url = url.slice(pageUrl.length);
            }
            if (url.startsWith('static/sphinx/')) {
                rec.url = url;
                if (rec.libpath === undefined || rec.version === undefined) {
                    const decomp = this.mgr.decomposeSphinxUrl(url);
                    rec.libpath = decomp.libpath;
                    rec.version = decomp.version;
                }
            } else {
                this.mgr.hub.errAlert(`Bad Sphinx URL: ${rec.url}`);
            }
        }
    }

    /* Turn the URL for a Sphinx page into a full location descriptor object,
     * with which to load that page.
     */
    urlToFullLoc(url) {
        const loc = {
            type: this.mgr.hub.contentManager.crType.SPHINX,
            url: url,
        };
        this.normalizeHistoryRecord(loc);
        return loc;
    }

}

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

define([
    "dojo/_base/declare",
    "dojo/dom-construct",
    "ise/content_types/AbstractContentManager",
], function(
    declare,
    domConstruct,
    AbstractContentManager
) {

// Abstract content manager class, to specify the interface.
const SphinxManager = declare(AbstractContentManager, {

    // Properties
    hub: null,

    // FIXME:
    //  Should instead be a lookup of SphinxControllers (once we have that class)
    iframesByPaneId: null,

    // Methods

    constructor: function() {
        this.iframesByPaneId = new Map();
    },

    /* Initialize a ContentPane with content of this manager's type.
     *
     * param info: An info object, indicating the content that is to be initialized.
     * param elt: The DOM element to which the content is to be added.
     * param pane: The ContentPane in which `elt` has already been set. This is provided
     *             mainly with the expectation that this manager will use `pane.id` as an
     *             index under which to store any data that will be required in order to
     *             do further management of the contents of this pane, e.g. copying.
     *             The entire ContentPane (not just its id) is provided in case this is useful.
     * return: promise that resolves when the content is loaded.
     */
    initContent: async function(info, elt, pane) {
        // Get the parts of the libpath, minus the trailing `_sphinx` segment.
        const p = info.libpath.split('.').slice(0, -1);
        const url = `static/sphinx/${p.join("/")}/${info.version}/index.html`

        const iframe = domConstruct.toDom(`
            <iframe
                width="100%"
                height="100%"
                src="${url}">
            </iframe>
        `);
        elt.appendChild(iframe);
        const iframeElt = pane.domNode.children[0].children[0];
        this.iframesByPaneId.set(pane.id, iframeElt);

        iframeElt.addEventListener('load', event => {
            this.handleFrameLoad(event.target);
        });
    },

    /* Handle the event of a sphinx panel iframe completing loading of a new page.
     */
    handleFrameLoad: function(frame) {
        const cw = frame.contentWindow;
        const sphinxPageInfo = this.getContentWindowSphinxPageInfo(cw);
        console.log(sphinxPageInfo);

        // Is it a sphinx page?
        if (sphinxPageInfo) {
            // Apply global theme & zoom.
            this.setThemeOnSphinxContentWindow(this.hub.currentTheme, cw);
            this.setZoomOnSphinxContentWindow(this.hub.currentGlobalZoom, cw);

            // Remove Furo's light/dark toggle
            const buttons = cw.document.getElementsByClassName("theme-toggle");
            Array.from(buttons).forEach((btn) => {
                btn.remove();
            });

            // Listen for hashchange within the page.
            cw.addEventListener('hashchange', event => {
                const cw = event.target;
                const sphinxPageInfo = this.getContentWindowSphinxPageInfo(cw);
                console.log(sphinxPageInfo);
            });

            // TODO:
            //  Activate widgets
        }
    },

    /* Determine whether a content window is currently at a locally hosted sphinx page,
     * and if so determine the libpath and version of that page, as well as any
     * in-page hash at which the window is currently located.
     *
     * param cw: the content window
     *
     * return: object of the form {
     *   libpath: str,
     *   version: str,
     *   hash: str,
     * } if at a locally hosted sphinx page, else null.
     */
    getContentWindowSphinxPageInfo: function(cw) {
        const frameLoc = cw.location;
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
    },

    /* Set light or dark theme in all sphinx content panels.
     *
     * theme: string "light" or "dark"
     */
    setTheme: function(theme) {
        for (const iframe of this.iframesByPaneId.values()) {
            this.setThemeOnSphinxContentWindow(theme, iframe.contentWindow);
        }
    },

    /* Set the zoom level in all sphinx content panels.
     *
     * level: number (str or int) giving a percentage
     */
    setZoom: function(level) {
        for (const iframe of this.iframesByPaneId.values()) {
            this.setZoomOnSphinxContentWindow(level, iframe.contentWindow);
        }
    },

    /* Set the theme on a single sphinx content window.
     */
    setThemeOnSphinxContentWindow: function(theme, cw) {
        // Note: This implementation relies on our use of the Furo theme.
        cw.document.body.dataset.theme = theme;
    },

    /* Set the zoom level on a single sphinx content window.
     */
    setZoomOnSphinxContentWindow: function(level, cw) {
        cw.document.body.style.fontSize = level + "%";
    },

    /* Update the content of an existing pane of this manager's type.
     *
     * param info: An info object indicating the desired content.
     * param paneId: The ID of the ContentPane that is to be updated.
     * return: nothing
     */
    updateContent: function(info, paneId) {
    },

    /* Write a serializable info object, completely describing the current state of a
     * given pane of this manager's type. Must be understandable by this manager's
     * own `initContent` and `updateContent` methods. Must contain `type` field.
     *
     * param oldPaneId: The id of an existing ContentPane of this manager's type.
     * param serialOnly: boolean; set true if you want only serializable info.
     * return: The info object.
     */
    writeStateInfo: function(oldPaneId, serialOnly) {
    },

    /* Take note of the fact that one pane of this manager's type has been copied to a
     * new one. This may for example be relevant if we want the view or selection, say, in
     * the two panes to track one another.
     *
     * param oldPaneId: The id of the original pane.
     * param newPaneId: The id of the new pane.
     * return: nothing
     */
    noteCopy: function(oldPaneId, newPaneId) {
    },

    /* Take note of the fact that a pane of this manager's type is about to close.
     *
     * param closingPane: The ContentPane that is about to close.
     * return: nothing
     */
    noteClosingContent: function(closingPane) {
        this.iframesByPaneId.delete(closingPane.id);
    },

    /*
     * Move "forward" or "backward" in the content. What this means is dependent upon
     * the particular type of content hosted by panes of this manager's type.
     *
     * param pane: the pane in which navigation is desired
     * param direction: integer indicating the desired navigation direction:
     *   positive for forward, negative for backward, 0 for no navigation. Passing 0 serves
     *   as a way to simply check the desired enabled state for back/fwd buttons.
     * return: Promise that resolves with a pair of booleans indicating whether back resp.
     *   fwd buttons should be enabled for this pane _after_ the requested navigation takes place.
     */
    navigate: function(pane, direction) {
        return Promise.resolve([false, false]);
    },

    /* For the content in a given pane, return an object describing all the
     * document highlights (if any) defined by that content.
     *
     * param paneId: The id of the pane in question.
     * return: Object of the form {
     *     'docs': Map(
     *         docId1 => {
     *             ...,
     *             ISBN: ...
     *             url: ...
     *             docId: ...
     *         },
     *         docId2 => {
     *             ...docInfo2...
     *         },
     *     ),
     *     'refs': Map(
     *         docId1 => [
     *             {
     *                  ccode: ...a combiner code string...,
     *                  siid: ...a "supplier internal id"...--some unique id that makes sense to the supplier,
     *                  slp: the supplier libpath,
     *                  stype: the supplier type ("CHART", "NOTES", anything else?)
     *              },
     *             {...ref2...},
     *         ],
     *         docId2 => [
     *             {...ref3...},
     *             {...ref4...},
     *         ],
     *     ),
     * }
     */
    getSuppliedDocHighlights: function(paneId) {
        return {
            docs: new Map(),
            refs: new Map(),
        };
    },

});

return SphinxManager;
});

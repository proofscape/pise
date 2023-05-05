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

import { SphinxController } from "./SphinxController";

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

    sphinxControllersByPaneId: null,

    // Methods

    constructor: function() {
        this.sphinxControllersByPaneId = new Map();
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
        const url = this.makeUrlFromCdo(info);
        const iframe = domConstruct.toDom(`
            <iframe
                width="100%"
                height="100%"
                src="${url}">
            </iframe>
        `);
        elt.appendChild(iframe);
        const iframeElt = pane.domNode.children[0].children[0];
        const sc = new SphinxController(this, info, pane, iframeElt);
        this.sphinxControllersByPaneId.set(pane.id, sc);
    },

    /* Extract the URL from a content descriptor object of SPHINX type.
     */
    makeUrlFromCdo: function(cdo) {
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
    },

    /* Set light or dark theme in all sphinx content panels.
     *
     * theme: string "light" or "dark"
     */
    setTheme: function(theme) {
        for (const sc of this.sphinxControllersByPaneId.values()) {
            sc.setTheme(theme);
        }
    },

    /* Set the zoom level in all sphinx content panels.
     *
     * level: number (str or int) giving a percentage
     */
    setZoom: function(level) {
        for (const sc of this.sphinxControllersByPaneId.values()) {
            sc.setZoom(level);
        }
    },

    /* Update the content of an existing pane of this manager's type.
     *
     * param info: An info object indicating the desired content.
     * param paneId: The ID of the ContentPane that is to be updated.
     * return: nothing
     */
    updateContent: function(info, paneId) {
        const sc = this.sphinxControllersByPaneId.get(paneId);
        const url = this.makeUrlFromCdo(info);
        sc.goTo(url);
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
        const sc = this.sphinxControllersByPaneId.get(oldPaneId);
        // We have to read the `lastLoadedCdo` property, instead of calling
        // the `getContentDescriptor()` method, due to the behavior when the
        // TabContainerTree introduces a new split. When that happens, iframes that were
        // moved get reloaded, and, if we ask a Sphinx panel for its state description
        // before it has finished reloading, it will report a URL like 'about:blank'.
        // Therefore we always ask for the last, stable, fully loaded content descriptor.
        return sc.lastLoadedCdo;
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
        this.sphinxControllersByPaneId.delete(closingPane.id);
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
    navigate: async function(pane, direction) {
        const sc = this.sphinxControllersByPaneId.get(pane.id);
        if (direction < 0) {
            await sc.goBackward();
        } else if (direction > 0) {
            await sc.goForward();
        }
        // For now, we are not making any effort to try to know whether forward or
        // backward navigation is possible. We'll just always say they are, and either
        // something will happen or it won't when the user clicks.
        return [true, true];
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

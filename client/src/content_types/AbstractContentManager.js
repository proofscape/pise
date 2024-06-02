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

define([
    "dojo/_base/declare"
], function(
    declare
) {

// Abstract content manager class, to specify the interface.
var AbstractContentManager = declare(null, {

    // Properties

    // Methods

    constructor: function() {
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
    initContent: function(info, elt, pane) {
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

    pushScrollFrac: function(paneId) {
    },

    popScrollFrac: function(paneId) {
    },

});

return AbstractContentManager;
});

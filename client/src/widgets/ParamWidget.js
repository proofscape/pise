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

import { util as iseUtil } from "../util";

define([
    "dojo/_base/declare",
    "ise/widgets/ExampWidget",
    "ise/examp/Chooser",
    "ise/examp/NfChooser"
], function(
    declare,
    ExampWidget,
    Chooser,
    NfChooser
) {

const ParamWidget = declare(ExampWidget, {

    choosersByPaneId: null,
    contentElementSelector: '.chooser_container',

    constructor: function(hub, libpath, info) {
        this.choosersByPaneId = new Map();
    },

    val: function(paneId) {
        const chooser = this.choosersByPaneId.get(paneId);
        if (chooser) {
            return chooser.getValue();
        } else {
            return null;
        }
    },

    okayToBuild: async function() {
        return true;
    },

    setNewHtml: function(pane, html) {
        this.clearErrorMessage(pane.id);
        this.makeNewGraphics(pane, html);
    },

    /* Make a new Chooser for a given pane where this widget appears.
     *
     * @param pane: the pane in question
     * @param html: the new html with which to make the new Chooser
     */
    makeNewGraphics: function(pane, html) {
        const contentElement = this.contentElementByPaneId.get(pane.id);
        iseUtil.removeAllChildNodes(contentElement);
        contentElement.innerHTML = html;

        this.typeset(pane.id, [contentElement]).then(() => {
            this.dispatch({
                type: "widgetVisualUpdate",
                paneId: pane.id,
                widget: this,
            });
        });

        let chooser;
        // The `is_invalid` flag means this isn't a true param widget, but just
        // a dummy widget to display an error message.
        if (!this.origInfo.is_invalid) {
            if (this.origInfo.ptype === 'NumberField') {
                chooser = new NfChooser(this, contentElement, pane);
            } else {
                chooser = new Chooser(this, contentElement, pane);
            }
            this.choosersByPaneId.set(pane.id, chooser);
            chooser.on('change', this.observeChooserChange.bind(this));
        }
    },

    /* Handler for `change` event on Chooser instances.
     *
     * Incoming event format: {
     *     type: 'change',
     *     chooser: the Chooser instance,
     *     value: the new value, which is `null` if Chooser currently has _no_ value.
     *   }
     */
    observeChooserChange: async function(event) {
        const paneId = event.chooser.pane.id;
        const newValue = event.value;
        // This parameter, whose value has just changed, does need to be rebuilt,
        // in case the new value was free input from the user (i.e. not just clicking
        // a button and choosing from among preset alternatives), in order to check
        // for any errors in the raw value. But we do not need to recompute this
        // parameter's chooser HTML.
        const writeHtml = false;
        return this.receiveNewValue(paneId, newValue, writeHtml);
    },

    grayOut: function grayOut(paneId, makeGray) {
        this.inherited(grayOut, arguments); // <-- superclass call in Dojo
        const chooser = this.choosersByPaneId.get(paneId);
        if (chooser) {
            chooser.enable(!makeGray || this.hasError(paneId));
        }
    },

    setErrorMessage: function setErrorMessage(paneId, msg) {
        this.inherited(setErrorMessage, arguments);
        const chooser = this.choosersByPaneId.get(paneId);
        if (chooser) {
            chooser.enable(true);
        }
    },

    noteClosingPane: function noteClosingPane(pane) {
        this.inherited(noteClosingPane, arguments);
        this.choosersByPaneId.delete(pane.id);
    },

});

return ParamWidget;

});

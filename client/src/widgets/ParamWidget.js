/* ------------------------------------------------------------------------- *
 *  Copyright (c) 2011-2022 Proofscape contributors                          *
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
    "ise/widgets/ExampWidget",
    "ise/examp/Chooser",
    "ise/examp/NfChooser",
    "ise/util",
], function(
    declare,
    ExampWidget,
    Chooser,
    NfChooser,
    iseUtil
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

    okayToBuild: function() {
        return true;
    },

    setNewHtml: function(pane, html) {
        this.clearErrorMessage(pane.id);
        this.makeNewGraphics(pane, html);
        this.liveInfo.chooser_html = html;
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

        iseUtil.typeset([contentElement]).then(() => {
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
     *
     */
    observeChooserChange: async function(event) {
        const paneId = event.chooser.pane.id;

        const activation = this.activationByPaneId.get(paneId);
        await activation;

        this.clearErrorMessage(paneId); // (presumed innocence)

        const contentElement = this.contentElementByPaneId.get(paneId);
        this.liveInfo.chooser_html = contentElement.innerHTML;

        const newValue = event.value;

        // Sort all descendants in topological order.
        const desc = Array.from(this.descendants.values());
        desc.sort((a, b) => {
            if (a.hasDescendant(b)) {
                return -1;
            } else if (b.hasDescendant(a)) {
                return 1;
            } else {
                return 0;
            }
        });
        // Prepend self to list, so that we have the list of all widgets
        // that we want to rebuild, and in the right order.
        desc.unshift(this);

        // This parameter, whose value has just changed, does need to be rebuilt,
        // in case the new value was free input from the user (i.e. not just clicking
        // a button and choosing from among preset alternatives), in order to check
        // for any errors in the raw value. But we do not need to recompute this
        // parameter's chooser HTML.
        const rebuildRequests = [{
            widget: this, newValue: newValue, writeHtml: false,
        }];
        // For all proper descendants, we need to rebuild without any new raw value.
        // We also recompute HTML.
        for (let w of desc.slice(1)) {
            rebuildRequests.push({
                widget: w,
                newValue: null,
                writeHtml: true,
            });
        }

        this.rebuildSequence(paneId, rebuildRequests);

        this.dispatch({
            type: "widgetVisualUpdate",
            paneId: paneId,
            widget: this,
        });
    },

    grayOut: function(paneId, makeGray) {
        this.inherited(arguments); // <-- superclass call in Dojo
        const chooser = this.choosersByPaneId.get(paneId);
        if (chooser) {
            chooser.enable(!makeGray || this.hasError(paneId));
        }
    },

    setErrorMessage: function(paneId, msg) {
        this.inherited(arguments);
        const chooser = this.choosersByPaneId.get(paneId);
        if (chooser) {
            chooser.enable(true);
        }
    },

    noteClosingPane: function(pane) {
        this.inherited(arguments);
        this.choosersByPaneId.delete(pane.id);
    },

});

return ParamWidget;

});

/* ------------------------------------------------------------------------- *
 *  Copyright (c) 2011-2023 Proofscape contributors                          *
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
    "ise/util",
], function(
    declare,
    ExampWidget,
    iseUtil
) {

const DispWidget = declare(ExampWidget, {

    codeByPaneId: null,
    contentElementSelector: '.display_container',

    constructor: function(hub, libpath, info) {
        this.codeByPaneId = new Map();
    },

    val: function(paneId) {
        const code = this.codeByPaneId.get(paneId);
        return code || null;
    },

    okayToBuild: function() {
        const selfOkay = (this.liveInfo.trusted || this.liveInfo.approved);
        if (!selfOkay) {
            return false;
        }
        let ancestorsOkay = true;
        for (let w of this.ancestorDisplays.values()) {
            if (!w.okayToBuild()) {
                return false;
            }
        }
        return (selfOkay && ancestorsOkay);
    },

    writeSubstituteHtml: function() {
        return `<pre>${this.liveInfo.build}</pre>`;
    },

    setNewHtml: function(pane, html) {
        this.makeNewGraphics(pane, html);
        this.liveInfo.display_html = html;
    },

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
        const code = contentElement.querySelector('.displayCode').innerText;
        this.codeByPaneId.set(pane.id, code);
    },

    noteClosingPane: function(pane) {
        this.inherited(arguments);
        this.codeByPaneId.delete(pane.id);
    },

});

return DispWidget;

});

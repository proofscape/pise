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
    "ise/widgets/Widget",
    "ise/util"
], function(
    declare,
    Widget,
    iseUtil
) {

var LinkWidget = declare(Widget, {

    onClick: function(event) {
        const pane = this.hub.contentManager.getSurroundingPane(event.target);
        const nm = this.hub.notesManager;
        const info = this.getInfoCopy();

        const annopath = info.annopath,
            targetVersion = info.target_version,
            annopathv = iseUtil.lv(annopath, targetVersion),
            targetType = info.target_type,
            tabPolicy = info.tab;
        let loadingPane = null;

        let currentPanes = {};
        let mostRecentPane = null;
        if (tabPolicy === 'existing' || tabPolicy === 'other') {
            // Among existing panes showing the annotation in question (if any),
            // find the one that has been most recently selected.
            currentPanes = nm.getPanesForAnnopathv(annopathv);
            if (tabPolicy === 'other') {
                // If the goal is to put the content in a different pane, then remove the
                // home pane from the search for most recent (if it was there to begin with).
                delete currentPanes[pane.id];
            }
            mostRecentPane = nm.hub.tabContainerTree.findMostRecentlyActivePane(currentPanes);
        }

        // Prepare an info object to use, if necessary.
        const targetInfo = {
            type: "NOTES",
            libpath: annopath,
            version: targetVersion,
            scrollSel: null
        };
        if (targetType === "WIDG") {
            targetInfo.scrollSel = info.target_selector;
        }

        if (tabPolicy === 'same') {
            loadingPane = pane;
        } else if (tabPolicy === 'other') {
            loadingPane = mostRecentPane;
        } else if (tabPolicy === 'existing') {
            loadingPane = (pane.id in currentPanes) || mostRecentPane === null ? pane : mostRecentPane;
        } else if (tabPolicy === 'new') {
            loadingPane = null;
        }

        // Take action.
        if (loadingPane === null) {
            // There is no existing pane where we want to load the content,
            // so open it beside the current tab.
            nm.hub.contentManager.openContentBeside(targetInfo, event.target);
        } else {
            // There already is a pane where we want to load the content.
            const makeActive = true;
            nm.hub.tabContainerTree.selectPane(loadingPane, makeActive);
            nm.updateContent(targetInfo, loadingPane.id);
        }

        // Very important to stop propagation of the click event.
        // Otherwise, consider the case where you click a link in a page in tabcontainer TC1,
        // and it activates a tab in tabcontainer TC2. The link click will activate the tab
        // in TC2, and that tab will get the blue highlight color that we want it to get.
        // That's all good. THEN, the click will propagate to TC1, whereupon TC1 will promptly
        // be made into the active TC, and the blue highlight color will come right back. Not good.
        event.stopPropagation();
    },

    activate: function(wdq, uid, nm, pane) {
        wdq.on('click', this.onClick.bind(this));
    },

});

return LinkWidget;

});

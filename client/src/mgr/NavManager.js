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
    "dojo/_base/declare",
    "dojo/query",
    "dojo/on",
    "dojo/dom-construct"
], function(
    declare,
    query,
    dojoOn,
    domConstruct
) {

const NavManager = declare(null, {

    hub: null,
    activePane: null,
    backButton: null,
    fwdButton: null,

    /**
     * param tct: the app's TabContainerTree.
     */
    constructor: function(tct) {
        tct.registerEmptyBoardListener(this);
        tct.registerActivePaneListener(this);
    },

    noteEmptyBoard: function() {
        this.activePane = null;
        this.enableNavButtons(false, false);
    },

    noteActivePane: function(cp) {
        this.activePane = cp;
        this.enableNavButtonsForPane(cp);
    },

    enableNavButtonsForPane: function(pane) {
        this.navigate(pane, 0);
    },

    navigate: function(pane, direction) {
        // Users can leave pane undefined or null to say "use active pane".
        pane = pane || this.activePane;
        // If pane is _still_ null -- as occurs if there are currently no
        // panes open whatsoever, then we just ensure the buttons are disabled.
        if (pane === null) {
            this.enableNavButtons(false, false);
        } else {
            const mgr = this;
            this.hub.contentManager.navigate(pane, direction).then(e => {
                mgr.enableNavButtons(e[0], e[1]);
            });
        }
    },

    handleNavEnable: function({ back, fwd, paneId }) {
        const ap = this.activePane;
        if (ap !== null && ap.id === paneId) {
            this.enableNavButtons(back, fwd);
        }
    },

    /*
     * param back: boolean saying whether back button should be enabled
     * param fwd: boolean saying whether forward button should be enabled
     */
    enableNavButtons: function(back, fwd) {
        let data = [
            [this.backButton, back],
            [this.fwdButton, fwd]
        ];
        data.forEach(pair => {
            let button = pair[0],
                enabled = pair[1];
            if (enabled) {
                button.classList.remove('disabled');
            } else {
                button.classList.add('disabled');
            }
        });
    },

    clickNavButton: function(button, direction) {
        if (button.classList.contains('disabled')) return;
        this.navigate(this.activePane, direction);
    },

    buildNavButtons: function() {
        let lhm = query('#lhMenu')[0];
        let buttons = domConstruct.toDom(`
            <span id="navButtons">
                <span class="navButton navBack disabled" title="Back Alt-[">&#x2794</span>
                <span class="navButton navFwd disabled" title="Fwd Alt-]">&#x2794</span>
            </span>
        `);
        lhm.appendChild(buttons);
        this.backButton = lhm.querySelector('.navBack');
        this.fwdButton = lhm.querySelector('.navFwd');
        let mgr = this;
        dojoOn(this.backButton, 'click', function(e){
            mgr.clickNavButton(this, -1);
        });
        dojoOn(this.fwdButton, 'click', function(e){
            mgr.clickNavButton(this, 1);
        });

        // Register as nav enable handler.
        this.hub.chartManager.addNavEnableHandler(this.handleNavEnable.bind(this));
        this.hub.notesManager.addNavEnableHandler(this.handleNavEnable.bind(this));
        this.hub.pdfManager.addNavEnableHandler(this.handleNavEnable.bind(this));
        this.hub.theorymapManager.addNavEnableHandler(this.handleNavEnable.bind(this));
    },

});

return NavManager;

});
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
    "dojo/_base/declare"
], function(
    declare
) {

const KeyListener = declare(null, {

    homeDiv: null,
    hub: null,
    tct: null,
    activePane: null,
    activeTC: null,

    constructor: function(homeDiv, tct) {
        this.homeDiv = homeDiv;
        this.tct = tct;
        tct.registerActivePaneListener(this);
        tct.registerEmptyBoardListener(this);
    },

    noteEmptyBoard: function() {
        this.activePane = null;
        this.activeTC = null;
    },

    noteActivePane: function(cp) {
        this.activePane = cp;
        this.activeTC = cp.getParent();
    },

    activate: function() {
        const kl = this;
        this.homeDiv.addEventListener('keyup', event => {
            //console.log('KeyListener:', event);
            if (event.ctrlKey) {
                if (event.altKey) {
                    // -------------------------------------------------------
                    // CTRL-ALT
                    // -------------------------------------------------------
                    // Ctrl-Alt-[ and Ctrl-Alt-] cycle left and right through
                    // all the tab containers.
                    if (kl.activeTC) {
                        let id = null;
                        if (event.code === "BracketLeft") {
                            //console.log("Previous TC!");
                            id = kl.tct.getPrevTcId(kl.activeTC.id, false);
                        }
                        else if (event.code === "BracketRight") {
                            //console.log("Next TC!");
                            id = kl.tct.getNextTcId(kl.activeTC.id, false);
                        }
                        if (id) {
                            kl.tct.setActiveTcById(id);
                            const pane = kl.tct.getActivePane();
                            if (pane) {
                                pane.domNode.focus();
                            }
                        }
                    }
                } else {
                    // -------------------------------------------------------
                    // JUST CTRL
                    // -------------------------------------------------------
                    // Ctrl-[ and Ctrl-] move left and right through the tabs
                    // within the active tab container.
                    if (kl.activeTC) {
                        if (event.code === "BracketLeft") {
                            //console.log("Tab left!");
                            kl.activeTC.back();
                        }
                        else if (event.code === "BracketRight") {
                            //console.log("Tab right!");
                            kl.activeTC.forward();
                        }
                    }
                }
            } else if (event.altKey) {
                // -------------------------------------------------------
                // JUST ALT
                // -------------------------------------------------------
                // Alt-[ and Alt-] activate the global navigation (back/fwd) buttons.
                if (event.code === "BracketLeft") {
                    //console.log("back");
                    kl.hub.navManager.navigate(null, -1);
                }
                else if (event.code === "BracketRight") {
                    //console.log("forward");
                    kl.hub.navManager.navigate(null, 1);
                }
            }
        });
    },

});

return KeyListener;

});
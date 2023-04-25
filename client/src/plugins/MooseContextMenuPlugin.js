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
    "dijit/layout/ContentPane",
    "dijit/Menu",
    "dijit/MenuItem",
    "dijit/CheckedMenuItem",
    "dijit/PopupMenuItem",
    "dijit/MenuSeparator",
    "ise/util"
], function(
    declare,
    ContentPane,
    Menu,
    MenuItem,
    CheckedMenuItem,
    PopupMenuItem,
    MenuSeparator,
    iseUtil
){

/* This class implements the necessary interface to serve as a
 * "context menu plugin" for Moose.
 *
 * This means an instance can be passed to a Moose Forest, and then it will
 * be used to construct context menus on objects appearing in the Forest
 * display area, such as nodes, the background, and the overview inset.
 */
var MooseContextMenuPlugin = declare(null, {

    // Properties
    chartManager: null,
    forest: null,
    // A place to store references to menu items for the background menu:
    bgItems: null,
    // A place to store references to menu items for the overview inset menu:
    ovItems: null,
    // A place to store the "auto-reload" CheckedMenuItems for deducs, by deducpath:
    autoReloadByDeducpath: null,

    // Methods

    constructor: function(chartManager) {
        this.chartManager = chartManager;
        this.bgItems = {
            menu: null,
            showOverviewPanel: null,
        };
        this.ovItems = {
            moveSubMenu: null,
        };
        this.autoReloadByDeducpath = new Map();
    },

    // begin plugin interface ------------------------------------------------

    /* param forest: the Moose Forest for which this instance is constructing
     *      context menus
     */
    setForest: function(forest) {
        this.forest = forest;
    },

    // begin background menu methods ----------------

    /* Make the context menu for the background.
     *
     * param host: the DOM element to which the menu is to be attached.
     */
    makeBackgroundContextMenu: function(host) {
        this.bgItems.menu = new Menu({
            targetNodeIds: [host]
        });
        var theForest = this.forest;
        this.bgItems.showOverviewPanel = new MenuItem({
            label: "Show Inset",
            onClick: function(e) {
                var floor = theForest.getFloor();
                floor.showOverviewPanel(true);
            },
            disabled: false
        });
        this.bgItems.menu.addChild(this.bgItems.showOverviewPanel);
    },

    /* Moose will call this method when the visibility of the overview inset
     * changes.
     *
     * param b: (bool) true if overview is visible; false if not.
     */
    noteOverviewVisibility: function(b) {
        this.bgItems.showOverviewPanel.set('disabled', b);
    },

    // begin overlay menu methods ----------------

    /* Make the context menu for the overview inset.
     *
     * param host: the DOM element to which the menu is to be attached.
     * param pos_names: lookup for the names of the possible inset positions.
     * param initial_pos: the initial position; should be a key in the pos_names lookup.
     */
    makeOverviewInsetContextMenu: function(host, pos_names, initial_pos) {
        var menu = new Menu({
            targetNodeIds: [host]
        });
        // Movement options
        var moveSubMenu = new Menu();
        this.ovItems.moveSubMenu = moveSubMenu;
        var theForest = this.forest;
        for (var p in pos_names) {
            moveSubMenu.addChild(new MenuItem({
                label: '<span class="cornerIcon '+p+'Icon"></span><span>'+pos_names[p]+'</span>',
                moosePosCode: p,
                onClick: function(e) {
                    var floor = theForest.getFloor();
                    floor.setOverviewPos(this.moosePosCode);
                },
                disabled: p === initial_pos
            }));
        }
        menu.addChild(new PopupMenuItem({
            label: "Move...",
            popup: moveSubMenu
        }));
        // Close option
        menu.addChild(new MenuItem({
            label: "Close",
            onClick: function(e) {
                var floor = theForest.getFloor();
                floor.showOverviewPanel(false);
            }
        }));
        // AutoView option
        menu.addChild(new CheckedMenuItem({
            label: "AutoView",
            checked: true,
            onChange: function() {
                const floor = theForest.getFloor();
                const overview = floor.getOverview();
                const nbhdview = floor.getNbhdview();
                overview.setAutoView(this.checked);
                nbhdview.setAutoView(this.checked);
            }
        }));
    },

    /* Moose will call this method when the position of the overview inset
     * changes.
     *
     * param pos: (str) name of position
     */
    setOverviewPos: function(pos) {
        // Enable/disable movement items
        var movementItems = this.ovItems.moveSubMenu.getChildren();
        for (var i in movementItems) {
            var item = movementItems[i];
            //console.log(item);
            item.set('disabled', item.moosePosCode === pos);
        }
    },

    // begin node menu methods ----------------

    /* Make the context menu for a node.
     * This method can be called repeatedly, in order to refresh/update the menu.
     *
     * param host: the DOM element to which the menu is to be attached.
     * param existingMenu: null, or the Menu already attached to the node.
     * param theNode: the node itself.
     *
     * return: the menu.
     */
    makeNodeContextMenu: function(host, existingMenu, theNode) {

        var menu = existingMenu;
        // If we already have a menu, clear it.
        if (menu) {
            menu.destroyDescendants();
        }
        // Otherwise make a menu and attach it to the given host.
        else {
            menu = new Menu({
                targetNodeIds: [host]
            });
        }

        const forest = theNode.forest;
        const theUID = theNode.uid;
        const version = theNode.getVersion();
        const deducInfo = theNode.getDeducInfo();

        var tsHome = document.createElement("div");
        iseUtil.addTailSelector(tsHome, theUID.split('.'));

        var deducLibpath = theNode.home;
        var modpath = deducLibpath.split('.').slice(0, -1).join('.');
        var editInfo = {
            type: "SOURCE",
            origType: "CHART",
            libpath: deducLibpath,
            version: version,
            modpath: modpath,
            useExisting: true
        };
        var textRange = theNode.textRange || deducInfo.textRange;
        if (textRange) {
            var r0 = textRange[0];
            if (r0 !== null) editInfo.sourceRow = r0;
        }

        // Putting the actual construction of the menu items into a separate
        // function is more than just a matter of readability; it is necessary
        // that we have a closure to fix the values of the passed args, since
        // this method is going to be called once for each and every node.
        this.addItemsToNodeContextMenu(
            menu, theNode, forest, theUID, version, tsHome, editInfo
        );

        return menu;
    },

    // end plugin interface --------------------------------------------------

    addItemsToNodeContextMenu: function(
        menu, theNode, forest, theUID, version, tsHome, editInfo
    ) {
        const theVersion = version;
        const chartManager = this.chartManager;
        const isWIP = version === "WIP";

        // Option to copy (part of) the libpath.
        menu.addChild(new PopupMenuItem({
            label: 'Copy libpath',
            popup: new ContentPane({
                class: 'popupCP',
                content: tsHome
            })
        }));

        // Option to edit source:
        menu.addChild(new MenuItem({
            label: `${isWIP ? "Edit" : "View"} source`,
            onClick: function(){
                chartManager.openExternalContent(editInfo);
            }
        }));

        if (theNode.cloneOf) {
            const original = iseUtil.parseTailVersionedLibpath(theNode.cloneOf);

            menu.addChild(new MenuSeparator());

            const cloneOfSubmenu = new Menu({});
            menu.addChild(new PopupMenuItem({
                label: 'Clone of...',
                popup: cloneOfSubmenu,
            }));

            const cloneOfTsHome = document.createElement("div");
            iseUtil.addTailSelector(cloneOfTsHome, original.libpath.split('.'));
            cloneOfSubmenu.addChild(new PopupMenuItem({
                label: 'Copy libpath',
                popup: new ContentPane({
                    class: 'popupCP',
                    content: cloneOfTsHome,
                }),
            }));

            cloneOfSubmenu.addChild(new MenuItem({
                label: 'Open / Go to',
                onClick: function(){
                    forest.requestState({
                        view: original.libpath,
                        versions: {
                            [original.libpath]: original.version,
                        },
                    });
                }
            }));

            cloneOfSubmenu.addChild(new MenuItem({
                label: 'Open in new tab',
                onClick: function(){
                    chartManager.openExternalContent({
                        type: "CHART",
                        libpath: original.libpath,
                        version: original.version,
                        view: original.libpath,
                    });
                }
            }));
        }

        if (theNode.nodetype !== 'ded') {

            // Separator.
            menu.addChild(new MenuSeparator());

            // Open Study Page
            menu.addChild(new MenuItem({
                label: 'Open study page',
                onClick: function(){
                    chartManager.openExternalContent({
                        type: "NOTES",
                        libpath: `special.studypage.${editInfo.libpath}.studyPage`,
                        version: version,
                    });
                }
            }));

        } else {

            // Separator.
            menu.addChild(new MenuSeparator());

            // Running defs
            menu.addChild(new PopupMenuItem({
                label: 'Running defs',
                popup: new ContentPane({
                    class: 'popupCP',
                    content: theNode.numRdefs > 0 ? theNode.buildRdefsDiv(1.5) : undefined,
                }),
                disabled: theNode.numRdefs === 0
            }));

            // Separator.
            menu.addChild(new MenuSeparator());

            // Options to open theory maps:
            if (theNode.isTLD() && !theNode.isTheorymap()) {
                menu.addChild(new MenuItem({
                    label: 'Upper theory map',
                    onClick: function(){
                        chartManager.openExternalContent({
                            type: "THEORYMAP",
                            theorymap: {
                                deducpath: theUID,
                                type: 'upper',
                                version: version,
                            }
                        });
                    }
                }));
                menu.addChild(new MenuItem({
                    label: 'Lower theory map',
                    onClick: function(){
                        chartManager.openExternalContent({
                            type: "THEORYMAP",
                            theorymap: {
                                deducpath: theUID,
                                type: 'lower',
                                version: version,
                            }
                        });
                    }
                }));

                // Separator.
                menu.addChild(new MenuSeparator());
            }

            // Open Study Page
            menu.addChild(new MenuItem({
                label: 'Open study page',
                onClick: function(){
                    chartManager.openExternalContent({
                        type: "NOTES",
                        libpath: `special.studypage.${theUID}.studyPage`,
                        version: version,
                    });
                }
            }));
            menu.addChild(new MenuSeparator());

            if (!theUID.startsWith('special.')) {
                // Toggle flow arrows
                menu.addChild(new CheckedMenuItem({
                    label: 'Suppress flow arrows',
                    checked: !theNode.showFlowEdges,
                    onChange: theNode.toggleFlowEdges.bind(theNode)
                }));
                // Option to refresh enrichment:
                menu.addChild(new MenuItem({
                    label: 'Refresh links',
                    onClick: theNode.refreshLinks.bind(theNode)
                }));
            }

            // Option to reload the deduction:
            if (isWIP) {
                menu.addChild(new MenuItem({
                    label: 'Reload',
                    onClick: function () {
                        forest.refreshDeduc(theUID);
                    }
                }));
            }

            // Option to auto-reload the deduction:
            if (isWIP && !theUID.startsWith('special.')) {
                let autoReloadItem = new CheckedMenuItem({
                    label: 'Auto-Reload',
                    checked: chartManager.checkAutoRefreshDeduc(forest.id, theUID),
                    onChange: function () {
                        var doAutoReload = this.checked;
                        chartManager.setAutoRefreshDeduc(forest.id, theUID, doAutoReload);
                    }
                });
                menu.addChild(autoReloadItem);
                this.autoReloadByDeducpath.set(theUID, autoReloadItem);
            }

            // Option to close the deduction:
            if (!theNode.isTheorymap()) {
                menu.addChild(new MenuItem({
                    label: 'Close',
                    onClick: function(){
                        forest.requestState({
                            off_board: theUID,
                            transition: true
                        });

                    }
                }));
            }
        }
        // Make options to open any expansions or ghosted nodes.
        var en = theNode.enrichment || {},
            dd = en.Deduc || [],
            aa = en.Anno  || [],
            cc = (en.CF || []).concat(theNode.cfOut || []);
        //console.log(theUID, en);
        var gp = theNode.ghostOf();
        var haveExpansions = (dd.length || aa.length || cc.length || gp);
        if (haveExpansions) {
            // Add a separator, and then the expansion(s).
            menu.addChild(new MenuSeparator());
            if (gp) {
                menu.addChild(new MenuItem({
                    label: 'Open:<br>&nbsp;&nbsp;&nbsp;&nbsp;<span class="mooseMonospace">'+gp+'</span>',
                    onClick: function(){
                        var doTransition = true;
                        theNode.viewGhostedNode(doTransition);
                    }
                }));
            }
            for (let info of dd) {
                const xpanpath = info.libpath;
                const versions = [];
                if (info.latest) versions.push(info.latest);
                if (info.WIP) versions.push("WIP");
                for (let version of versions) {
                    // Need closure for path and version
                    (function (xpanpath, version) {
                        menu.addChild(new MenuItem({
                            //label: "Open " + xpanpath,
                            label: `Expansion:<br>&nbsp;&nbsp;&nbsp;&nbsp;<span class="mooseMonospace">${xpanpath}@${version}</span>`,
                            title: "Click to open. Alt-Click to open in new tab.",
                            onClick: function (event) {
                                const state = {
                                    view: {
                                        objects: [theUID, xpanpath]
                                    },
                                    versions: {
                                        [xpanpath]: version,
                                    },
                                    select: theUID,
                                };
                                if (event.altKey) {
                                    state.type = "CHART";
                                    state.versions[theUID] = theVersion;
                                    chartManager.openExternalContent(state);
                                } else {
                                    state.transition = true;
                                    forest.requestState(state);
                                }
                            }
                        }));
                    })(xpanpath, version);
                }
            }
            for (let info of aa) {
                const annopath = info.libpath;
                const versions = [];
                if (info.latest) versions.push(info.latest);
                if (info.WIP) versions.push("WIP");
                for (let version of versions) {
                    // Need closure for path and version
                    (function (annopath, version) {
                        menu.addChild(new MenuItem({
                            label: `Notes:<br>&nbsp;&nbsp;&nbsp;&nbsp;<span class="mooseMonospace">${annopath}@${version}</span>`,
                            onClick: function () {
                                //console.log(annopath);
                                chartManager.openExternalContent({
                                    type: "NOTES",
                                    libpath: annopath,
                                    version: version,
                                });
                            }
                        }));
                    })(annopath, version);
                }
            }
            for (let info of cc) {
                const nodepath = info.libpath;
                const versions = [];
                // Comparisons OUT have a 'version' field:
                if (info.version) versions.push(info.version);
                // Comparisons IN have potentially the 'latest' and/or 'WIP'
                // fields that all enrichments have:
                if (info.latest) versions.push(info.latest);
                if (info.WIP) versions.push("WIP");
                for (let version of versions) {
                    // Need closure for path and version
                    (function (nodepath, version) {
                        menu.addChild(new MenuItem({
                            label: `Compare:<br>&nbsp;&nbsp;&nbsp;&nbsp;<span class="mooseMonospace">${nodepath}@${version}</span>`,
                            title: "Click to open. Alt-Click to open in new tab.",
                            onClick: function (event) {
                                const state = {
                                    view: {
                                        objects: [nodepath]
                                    },
                                    versions: {
                                        [nodepath]: version,
                                    },
                                    select: nodepath,
                                };
                                if (event.altKey) {
                                    state.type = "CHART";
                                    chartManager.openExternalContent(state);
                                } else {
                                    state.transition = true;
                                    forest.requestState(state);
                                }
                            }
                        }));
                    })(nodepath, version);
                }
            }
        }
    },

});

return MooseContextMenuPlugin;
});

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

import { util as iseUtil } from "../util";

define([
    "dojo/_base/declare",
    "dijit/layout/ContentPane",
    "dijit/Menu",
    "dijit/MenuItem",
    "dijit/CheckedMenuItem",
    "dijit/PopupMenuItem",
    "dijit/MenuSeparator"
], function(
    declare,
    ContentPane,
    Menu,
    MenuItem,
    CheckedMenuItem,
    PopupMenuItem,
    MenuSeparator
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
                            offBoard: theUID,
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
                menu.addChild(makeEnrichmentMenuItem({
                    heading: 'Open',
                    subtitle: gp,
                    onClickCustom: function(){
                        const doTransition = true;
                        theNode.viewGhostedNode(doTransition);
                    },
                }));
            }
            for (let info of dd) {
                const xpanpath = info.libpath;
                const versions = selectEnrichmentVersions(info);
                for (let version of versions) {
                    menu.addChild(makeEnrichmentMenuItem({
                        heading: 'Expansion',
                        subtitle: `${xpanpath}@${version}`,
                        onClickChartOpen: {
                            view: [theUID, xpanpath],
                            versions: {
                                [xpanpath]: version,
                                [theUID]: theVersion,
                            },
                            select: theUID,
                        },
                        chartManager, forest,
                    }));
                }
            }
            for (let info of aa) {
                const annopath = info.libpath;
                const versions = selectEnrichmentVersions(info);
                for (let version of versions) {
                    menu.addChild(makeEnrichmentMenuItem({
                        heading: 'Notes',
                        subtitle: `${annopath}@${version}`,
                        onClickOEC: {
                            type: "NOTES",
                            libpath: annopath,
                            version: version,
                        },
                        chartManager,
                    }));
                }
            }
            for (let info of cc) {
                const nodepath = info.libpath;
                const versions = selectEnrichmentVersions(info);
                for (let version of versions) {
                    menu.addChild(makeEnrichmentMenuItem({
                        heading: 'Compare',
                        subtitle: `${nodepath}@${version}`,
                        onClickChartOpen: {
                            view: [nodepath],
                            versions: {
                                [nodepath]: version,
                            },
                            select: nodepath,
                        },
                        chartManager, forest,
                    }));
                }
            }
        }
    },

});

/* Given the object describing an enrichment, extract from it the array of
 * versions we want to list. For now, we're keeping this simple:
 *   * If available at one or more numbered versions, we will list only the
 *     latest of these.
 *   * If available at WIP, we will list this.
 *   * If available both at a numbered version and at WIP, we will list the
 *     numbered version first.
 * In the future, we may want to provide the user with a more complete listing,
 * or at least a way to load a more complete listing.
 */
function selectEnrichmentVersions(enr) {
    const selectedVersions = [];
    let givenVersions = enr.versions;
    // Some enrichment descriptors (such as comparisons OUT, i.e. the value of a
    // node's `.cfOut` property) have only a `.version` field, instead of `.versions`.
    if (givenVersions === undefined && enr.version) {
        givenVersions = [enr.version];
    }
    if (givenVersions !== undefined) {
        // We assume the given versions list is sorted so that:
        //  * If WIP is present, it comes last.
        //  * Any numerical versions are sorted in increasing order.
        const n = givenVersions.length;
        if (n === 1) {
            selectedVersions.push(givenVersions[0]);
        } else if (n >= 2) {
            const m = givenVersions.slice(-1)[0] === "WIP" ? 2 : 1;
            selectedVersions.push(...givenVersions.slice(-m));
        }
    }
    return selectedVersions;
}

/* Construct the MenuItem for an enrichment available on a given node.
 *
 * :param heading: Text for first line in menu item.
 * :param subtitle: Text for second, indented line in menu item.
 * :param onClickCustom: One alternative for defining the click handler for the menu item.
 *      Here you can pass any function you want.
 * :param onClickOEC: One alternative for defining the click handler for the menu item.
 *      Pass a content descriptor object you want forwarded to `ChartManager.openExternalContent()`.
 * :param onClickChartOpen: One alternative for defining the click handler for the menu item.
 *      Pass a content descriptor object that could serve to define a whole new chart panel, OR could
 *      serve to update the existing one. The user will be informed (via hover title) that clicking
 *      opens in this tab, while Alt-click opens in a new tab. You can omit the `type: "CHART"` field.
 * :param chartManager: for (onClickOEC, onClickChartOpen), we need a reference to the ChartManager.
 * :param forest: for (onClickChartOpen), we need a ref to the Forest where the node lives.
 */
function makeEnrichmentMenuItem(
    {
        heading, subtitle,
        onClickCustom, onClickOEC, onClickChartOpen,
        chartManager, forest,
    }) {
    const label = `${heading}:<br>&nbsp;&nbsp;&nbsp;&nbsp;<span class="mooseMonospace">${subtitle}</span>`;
    let onClick;
    if (onClickCustom) {
        onClick = onClickCustom;
    } else if (onClickOEC) {
        onClick = function() {
            chartManager.openExternalContent(onClickOEC);
        }
    } else if (onClickChartOpen) {
        onClick = function(event) {
            if (event.altKey) {
                onClickChartOpen.type = "CHART";
                chartManager.openExternalContent(onClickChartOpen);
            } else {
                onClickChartOpen.transition = true;
                forest.requestState(onClickChartOpen);
            }
        }
    }
    const menuItemFields = {label, onClick};
    if (onClickChartOpen) {
        menuItemFields.title = "Click to open. Alt-Click to open in new tab.";
    }
    return new MenuItem(menuItemFields);
}

return MooseContextMenuPlugin;
});

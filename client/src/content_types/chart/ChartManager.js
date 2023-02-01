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


//const moose = require('pfsc-moose');
import {head, Forest} from "pfsc-moose/src/moose/main";
const moose = {
    head: head,
    Forest: Forest
};

import { MooseNodeLabelPlugin } from "../../plugins/MooseNodeLabelPlugin";
import { NoGroupError } from "browser-peers/src/errors";

define([
    "dojo/_base/declare",
    "dojo/_base/lang",
    "ise/content_types/AbstractContentManager",
    "ise/plugins/MooseContextMenuPlugin",
    "ise/util",
    "ise/errors"
], function(
    declare,
    lang,
    AbstractContentManager,
    MooseContextMenuPlugin,
    iseUtil,
    iseErrors
) {

// ChartManager class
var ChartManager = declare(AbstractContentManager, {

    // Properties

    hub: null,
    // lookup where pane id points to the Forest instance in that pane:
    forestsByPaneId: null,
    // lookup where Forest id points to the id of the pane where that Forest lives:
    paneIdByForestId: null,

    navEnableHandlers: null,

    deducpathsToSubscribedForestIds: null,
    modpathsToDeducpathsHavingSubscribers: null,

    pdfInfoByFingerprint: null,

    defaultSelectionStyle: "NodeEdges",

    // Methods

    constructor: function() {
        this.forestsByPaneId = {};
        this.paneIdByForestId = {};
        this.navEnableHandlers = [];
        this.deducpathsToSubscribedForestIds = new iseUtil.LibpathSetMapping();
        this.modpathsToDeducpathsHavingSubscribers = new iseUtil.LibpathSetMapping();
        this.pdfInfoByFingerprint = new Map();
    },

    activate: function(ISE_state) {
        this.hub.socketManager.on('moduleBuilt', this.handleModuleBuiltEvent.bind(this));
        this.hub.windowManager.on('forestColoring', this.handleGroupcastForestColoring.bind(this));
        this.setAppUrlPrefix(ISE_state.appUrlPrefix || '');
        // Make Moose's XHRs go through the Hub, so we can add our CSRF token.
        moose.head.xhr = this.hub.xhr.bind(this.hub);
    },

    paneCount: function() {
        let n = 0;
        for (let id in this.forestsByPaneId) { n++; }
        return n;
    },

    getForestById: function(id) {
        const paneId = this.paneIdByForestId[id];
        return this.forestsByPaneId[paneId];
    },

    addNavEnableHandler: function(callback) {
        this.navEnableHandlers.push(callback);
    },

    publishNavEnable: function({back, fwd, origin}) {
        const paneId = this.paneIdByForestId[origin.id];
        this.navEnableHandlers.forEach(cb => {
            cb({
                back: back,
                fwd: fwd,
                paneId: paneId,
            });
        });
    },

    setDefaultSelectionStyle: function(style) {
        this.defaultSelectionStyle = style;
    },

    setAppUrlPrefix: function(prefix) {
        moose.head.appUrlPrefix = prefix;
    },

    getForest: function(paneId) {
        return this.forestsByPaneId[paneId];
    },

    openExternalContent: function(info) {
        this.hub.contentManager.openContentInActiveTC(info);
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
        const forest = this.constructForest(info, elt, pane);
        const N = this.paneCount();
        if (N === 1) {
            this.hub.menuManager.setActiveForest(forest);
        }
        const params = this.makeInitialForestRequestParams(info);
        return forest.requestState(params);
    },

    constructForest: function(info, elt, pane) {
        const mcmp = new MooseContextMenuPlugin(this);
        const mnlp = new MooseNodeLabelPlugin(this.hub);
        const forest_params = {
            overview: info.overview,
            showLibpathSubtitles: info.showLibpathSubtitles,
            selectionStyle: this.defaultSelectionStyle,
            expansionMode: info.expansionMode,
            gid: info.gid,
            showGhostPreviews: true,
            suppressFlowEdges: true,  // TODO: make this a configurable ISE setting.
            contextMenuPlugin: mcmp,
            // The study manager will be in charge of goal boxes. If one is provided in the given info
            // (such as a ChartWidget) that will be used; else we use the app-wide one.
            studyManager: info.studyManager || this.hub.studyManager,
            // Provide a way to render label content based on doc references.
            nodeLabelPlugin: mnlp,
            // Since we have global nav keys Alt-[/], we deactivate those in the Forest to avoid redundancy.
            activateNavKeys: false,
        };

        // Read optional parameters out of the given info object.
        if (info.forest) {
            // For now we just have one: `overview`.
            if (info.forest.overview) forest_params.overview = info.forest.overview;
        }

        var forest = new moose.Forest(elt, forest_params);

        // Store it.
        this.forestsByPaneId[pane.id] = forest;
        this.paneIdByForestId[forest.id] = pane.id;

        // Register as listener.
        forest.addForestListener(this);
        forest.addNodeClickListener(this.noteNodeClick.bind(this));
        forest.getColorManager().on('setColor', this.handleSetColor.bind(this));

        // Forward navigation enable events.
        forest.getHistoryManager().addNavEnableHandler(this.publishNavEnable.bind(this));

        // On focus, see that the tab conatiner is activated.
        let tct = this.hub.tabContainerTree;
        elt.addEventListener('focus', e => {
            tct.setActiveTcByPane(pane);
        });

        return forest;
    },

    makeInitialForestRequestParams: function(info) {
        // By default, for loading initial content, we assume that we want no
        // transition, and we want to see an overview of all objects on the board.
        var params = {
            transition: false,
            view: {
                objects: 'all',
                pan_policy: moose.head.autopanPolicy_CenterAlways
            }
        };
        // Info objects coming from the tree may use an alternative request format
        // with the fields `libpath` and `version`. We convert this into the standard
        // `on_board` and `versions` properties.
        const libpath = info.libpath;
        const version = info.version;
        if (libpath) {
            params.on_board = [libpath];
            params.versions = {
                [libpath]: version,
            };
        }
        // Otherwise, we expect an info object that already conforms to the format
        // accepted by Forest.requestState.
        else {
            Object.assign(params, info);
        }
        return params
    },

    // -----------------------------------------------------------------------
    // ForestListener interface

    noteForestTransition: function(info) {
        //...
    },

    noteForestClosedAndOpenedDeductions: function(info) {
        const forest = info.forest;
        const openedDeducs = info.opened; // Map from deducpaths to deducs themselves
        const closedDeducpaths = info.closed; // Array of deducpaths

        // Gather any PDF info
        for (let [deducpath, deduc] of openedDeducs) {
            const deducInfo = deduc.getDeducInfo();
            //console.log(deducInfo);
            const docInfo = deducInfo.docInfo;
            if (docInfo) {
                for (let docId of Object.keys(docInfo.docs)) {
                    if (docId.startsWith("pdffp:")) {
                        const info = docInfo.docs[docId];
                        const fingerprint = docId.slice(6);
                        this.pdfInfoByFingerprint.set(fingerprint, info);
                    }
                }
            }
        }

        // Manage auto-refresh
        const menuPlugin = forest.contextMenuPlugin;
        if (typeof(menuPlugin) === 'undefined') return;
        // For newly opened deducs, set auto-refresh option.
        const openedDeducpaths = Array.from(openedDeducs.keys());
        for (let deducpath of openedDeducpaths) {
            // If deduc was also closed, then it was reloaded, so we do not
            // consider it _newly_ opened.
            if (closedDeducpaths.includes(deducpath)) continue;
            let autoReloadMenuItem = menuPlugin.autoReloadByDeducpath.get(deducpath);
            if (autoReloadMenuItem) {
                // TODO:
                //   Make checked state a configurable ISE option.
                //   For now, it defaults to true.
                autoReloadMenuItem.set('checked', true);
                autoReloadMenuItem.onChange();
            }
        }
        // For deducs that have been closed (and not reloaded), unsubscribe from refresh,
        // and delete the auto reload menu item from the menu plugin's mapping to free memory.
        for (let deducpath of closedDeducpaths) {
            if (openedDeducpaths.includes(deducpath)) continue;
            this.setAutoRefreshDeduc(forest, deducpath, false);
            // Free memory:
            menuPlugin.autoReloadByDeducpath.delete(deducpath);
        }
    },

    // -----------------------------------------------------------------------

    /* Update the content of an existing pane of this manager's type.
     *
     * param info: An info object indicating the desired content.
     * param paneId: The ID of the ContentPane that is to be updated.
     */
    updateContent: function(info, paneId) {
        var forest = this.forestsByPaneId[paneId];
        forest.requestState(info);
    },

    /* Write a serializable info object, completely describing the current state of a
     * given pane of this manager's type. Must be understandable by this manager's
     * own `initContent` method.
     *
     * param oldPaneId: The id of an existing ContentPane of this manager's type.
     * param serialOnly: boolean; set true if you want only serializable info.
     * return: The info object.
     */
    writeStateInfo: function(oldPaneId, serialOnly) {
        var forest = this.forestsByPaneId[oldPaneId];
        var state = forest.describeState();
        state.type = this.hub.contentManager.crType.CHART;
        return state;
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
        const closingForest = this.forestsByPaneId[closingPane.id];
        this.removeAllAutoRefreshForForest(closingForest);
        if (closingForest === this.hub.menuManager.activeForest) {
            this.hub.menuManager.setActiveForest(null);
        }
        delete this.forestsByPaneId[closingPane.id];
        delete this.paneIdByForestId[closingForest.id];
        const N = this.paneCount();
        if (N === 1) {
            let lastForest;
            for (let id in this.forestsByPaneId) {
                lastForest = this.forestsByPaneId[id];
            }
            this.hub.menuManager.setActiveForest(lastForest);
        }
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
        let forest = this.forestsByPaneId[pane.id],
            hm = forest.getHistoryManager();
        if (direction < 0 && hm.canGoBack()) {
            hm.goBack();
        } else if (direction > 0 && hm.canGoForward()) {
            hm.goForward();
        }
        return Promise.resolve([hm.canGoBack(), hm.canGoForward()]);
    },

    /* Note that a node was clicked in a Forest.
     *
     * param forest: the Forest in which the click took place
     * param nodepath: the libpath of the node that was clicked
     * param e: the click event
     */
    noteNodeClick: function(forest, nodepath, e) {

        // For now we just implement one thing:
        // If the clicked node is now the singleton selection,
        // and if it carries a doc reference, attempt to highlight
        // the referenced selection in an open doc.
        // If Alt key was pressed, then also auto scroll the selection into view.

        //console.log(nodepath, e);
        var selMgr = forest.getSelectionManager(),
            singleton = selMgr.getSingletonNode();
        if (singleton !== null && singleton.uid === nodepath) {
            const docRef = singleton.docRef;
            const docId = singleton.docId;
            if (docId) {
                if (docId.startsWith('pdffp:')) {
                    const pdfFingerprint = docId.slice(6);
                    const pdfc = this.hub.pdfManager.getMostRecentPdfcForFingerprint(pdfFingerprint);
                    if (pdfc) {
                        if (docRef) {
                            pdfc.highlightFromCodes([docRef], e.altKey);
                        } else {
                            pdfc.clearHighlight();
                        }
                    }
                }
            }
        }

    },

    /* Handle a 'setColor' event from a Forest's ColorManager.
     *
     * @param req: the color request object representing the new coloring.
     * @param forestId: the id of the Forest where this took place.
     */
    handleSetColor: function({ req, forestId }) {
        const forest = this.forestsByPaneId[this.paneIdByForestId[forestId]];
        try {
            this.hub.windowManager.groupcastEvent({
                type: 'forestColoring',
                req: req,
                gid: forest.gid,
                uuid: forest.uuid,
            }, {
                includeSelf: true,
                selfSync: true,
            });
        } catch (e) {
            if (e instanceof NoGroupError) {
                /* Fail silently. This case arises if we reload a browser tab with
                 * an ISE instance that has any chart panes to reload as initial content.
                 * In such cases, opening deducs in the Forests triggers Moose selection
                 * managers to redo selections, which redoes node coloring, which leads
                 * here. But all this happens long before the WindowManager can asynchronously
                 * enable its WindowPeer, and thus complete the "join/hello" event handshake
                 * whereby the peer learns its window group id. Hence we cannot expect to be
                 * ready to groupcast the coloring event in such a case. And it shouldn't matter.
                 */
            } else {
                throw e;
            }
        }
    },

    /* Handle a 'forestColoring' event from the WindowManager.
     *
     * @param req: a color request object.
     * @param gid: the group id of the forest chain to which this coloring
     *   is meant to apply.
     * @param uuid: the uuid of the Forest that initiated the coloring event.
     */
    handleGroupcastForestColoring: function({ req, gid, uuid }) {
        for (let forest of Object.values(this.forestsByPaneId)) {
            if (forest.gid === gid && forest.uuid !== uuid) {
                // If we don't clear the selection, we can wind up with surprising
                // results if that forest is later moved to another window (at which
                // time a possibly very old selection still registered there becomes
                // restored, making all other forests in the group follow suit).
                // But must not clear colors in this call, or set off infinite loop.
                const alsoClearColors = false;
                forest.getSelectionManager().clear(alsoClearColors);
                forest.getColorManager().doColoring(req);
            }
        }
    },

    /* Open a deduction in an existing chart pane.
     *
     * @param deducpath: the libpath of the deduction to be opened.
     * @param version: the version of teh deduction to be opened.
     * @param pane: the ContentPane where it is to be opened.
     */
    openDeducInExistingPane: function(deducpath, version, pane) {
        //console.log("ChartManager: open deduc in pane: ", deducpath, pane);
        const forest = this.forestsByPaneId[pane.id];
        const info = {
            view: deducpath,
            versions: {
                [deducpath]: version,
            },
        };
        forest.requestState(info);
    },

    /* Say whether a certain deduction in a certain forest should be auto-refreshed
     * or not, whenever a new dashgraph is published for that deduction.
     *
     * param forest: the Forest in question
     * param deducpath: the libpath of the deduction in question
     * param doAutoRefresh: boolean, saying whether we do (true) or don't (false) want auto-refresh
     */
    setAutoRefreshDeduc: function(forest, deducpath, doAutoRefresh) {
        const modpath = iseUtil.getModpathFromTopLevelEntityPath(deducpath);
        if (doAutoRefresh) {
            this.deducpathsToSubscribedForestIds.add(deducpath, forest.id);
            this.modpathsToDeducpathsHavingSubscribers.add(modpath, deducpath);
        } else {
            this.deducpathsToSubscribedForestIds.remove(deducpath, forest.id);
            if (!this.deducpathsToSubscribedForestIds.mapping.has(deducpath)) {
                this.modpathsToDeducpathsHavingSubscribers.remove(modpath, deducpath);
            }
        }
    },

    removeAllSubscriptionsForItem: function(deducpath) {
        const modpath = iseUtil.getModpathFromTopLevelEntityPath(deducpath);
        this.deducpathsToSubscribedForestIds.mapping.delete(deducpath);
        this.modpathsToDeducpathsHavingSubscribers.remove(modpath, deducpath);
    },

    /* Remove a given forest from all its auto-refresh subscriptions.
     */
    removeAllAutoRefreshForForest: function(forest) {
        const deducpathsFromWhichToRemove = [];
        for (let deducpath of this.deducpathsToSubscribedForestIds.mapping.keys()) {
            if (this.checkAutoRefreshDeduc(forest, deducpath)) {
                deducpathsFromWhichToRemove.push(deducpath);
            }
        }
        for (let deducpath of deducpathsFromWhichToRemove) {
            this.setAutoRefreshDeduc(forest, deducpath, false);
        }
    },

    /* Check whether a certain deduction in a certain forest is currently subscribed
     * for auto-refresh.
     */
    checkAutoRefreshDeduc: function(forest, deducpath) {
        return this.deducpathsToSubscribedForestIds.has(deducpath, forest.id);
    },

    /* Respond to iseEvent of type 'moduleBuilt' by requesting dashgraphs under that module and
     * distributing them to any subscribed forests.
     */
    handleModuleBuiltEvent: function({ modpath, recursive, timestamp }) {
        const deducpaths = recursive ?
            this.modpathsToDeducpathsHavingSubscribers.getUnionOverLibpathPrefix(modpath) :
            this.modpathsToDeducpathsHavingSubscribers.mapping.get(modpath) || [];
        for (let deducpath of deducpaths) {
            this.hub.xhrFor('loadDashgraph', {
                query: { libpath: deducpath, cache_code: `${timestamp}`, vers: "WIP" },
                handleAs: 'json',
            }).then(resp => {
                //console.log(resp);
                const forestIds = this.deducpathsToSubscribedForestIds.mapping.get(deducpath) || [];
                if (resp.err_lvl === iseErrors.serverSideErrorCodes.MISSING_DASHGRAPH) {
                    this.removeAllSubscriptionsForItem(deducpath);
                    for (let forestId of forestIds) {
                        const forest = this.getForestById(forestId);
                        forest.requestState({off_board: deducpath});
                    }
                } else {
                    const dashgraph = resp.dashgraph;
                    for (let forestId of forestIds) {
                        const forest = this.getForestById(forestId);
                        forest.refreshDeduc(deducpath, dashgraph);
                    }
                }
            });
        }
    },

});

return ChartManager;
});

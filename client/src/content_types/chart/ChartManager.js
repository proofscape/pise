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
import {GlobalLinkingMap} from "../linking";

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

    // Our GlobalLinkingMap instance.
    // The "secondary IDs" ("x" in method calls) are docIDs.
    linkingMap: null,

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
        this.initLinking();
    },

    initLinking: function() {
        const name = 'linking_charts';
        this.linkingMap = new GlobalLinkingMap(this.hub, name);
        this.linkingMap.activate();
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

    getPanelUuidOfForest: function(forest) {
        const paneId = this.paneIdByForestId[forest.id];
        return this.hub.contentManager.getUuidByPaneId(paneId);
    },

    getSuppliedDocHighlights: function(paneId) {
        const forest = this.forestsByPaneId[paneId];
        return forest.getMergedDocInfos();
    },

    /* Synchronously return array of all triples (u, s, d),
     * in just this window,
     * where:
     *   u is a chart panel uuid,
     *   s is the libpath of a deduc hosted by that panel,
     *   d is the docId of a document referenced by that deduc, or null if that
     *     deduc does not reference any documents
     */
    getAllDocRefTriplesLocal: function({}) {
        const triples = [];
        for (const [paneId, forest] of Object.entries(this.forestsByPaneId)) {
            const u = this.hub.contentManager.getUuidByPaneId(paneId);
            const m = forest.getReferencedDocIdsByDeduc();
            for (const [s, D] of m) {
                if (D) {
                    for (const d of D) {
                        triples.push([u, s, d]);
                    }
                } else {
                    triples.push([u, s, null]);
                }
            }
        }
        return triples;
    },

    /* Return promise that resolves with array of all triples (u, s, d),
     * across all windows,
     * where:
     *   u is a chart panel uuid,
     *   s is the libpath of a deduc hosted by that panel,
     *   d is the docId of a document referenced by that deduc, or null if that
     *     deduc does not reference any documents
     */
    getAllDocRefTriples: function() {
        return this.hub.windowManager.broadcastAndConcat(
            'hub.chartManager.getAllDocRefTriplesLocal',
            {},
            {excludeSelf: false}
        );
    },

    /* Handle the case of a single closed deduction E, in a chart panel C which
     * is not itself closing, and which belongs to our window.
     *
     * When this method is invoked, the forest in the chart panel has finished
     * removing the deduc from the board.
     *
     * param deducpath: the libpath of the deduction E that has been removed
     * param uuid: the uuid of the chart panel C
     */
    updateLinkingForClosedDeduc: async function(deducpath, uuid) {
        const LC = this.linkingMap;
        const LD = this.hub.pdfManager.linkingMap;

        // Clean up L_C.
        // Find the set D0 of doc Ids that are still referenced by panel C:
        const drt = this.getAllDocRefTriplesLocal({});
        let D0 = drt.filter(([u, s, d]) => (u === uuid && d !== null)).map(t => t[2]);
        D0 = new Set(D0);
        // Find the set D1 of doc Ids that are no longer referenced by panel C:
        const T = await LC.getTriples({u: uuid});
        let D1 = T.filter(([u, x, w]) => !D0.has(x)).map(t => t[1]);
        D1 = new Set(D1);
        // Remove linking entries for panel C and doc Ids in D1:
        for (const x of D1) {
            await LC.removeTriples({u: uuid, x});
        }

        // Clean up L_D.
        // If L_D is telling any doc panels to carry out navigations for this deduc
        // in this panel, it must remove such links.
        await LD.removeTriples({x: deducpath, w: uuid});
    },

    /* Establish default links for a deduction E in a chart panel C.
     *
     * param deducpath: the libpath of deduction E
     * param uuid: the uuid of chart panel C
     */
    makeDefaultLinks: async function(deducpath, uuid) {
        // TODO:
        //  Refactor to handle more cases? As a first approximation, we are only
        //  *consciously* handling the case of a newly-opened (not reloaded) deduction.
        //  Maybe this also works for reloaded? Maybe not? Haven't thought it through yet...

        // Refer to the newly opened deduc as E.
        const drt = await this.getAllDocRefTriples();
        // Panel uuids where E is hosted:
        let UE = new Set();
        // Docs referenced by E:
        let DE = new Set();
        for (const [u, s, d] of drt) {
            if (s === deducpath) {
                UE.add(u);
                if (d) {
                    DE.add(d);
                }
            }
        }
        UE = Array.from(UE);
        DE = Array.from(DE);

        if (DE.length === 0) {
            // The new deduc does not reference any docs. Nothing to do.
            return;
        }

        // Linking maps:
        const LC = this.linkingMap;
        const LD = this.hub.pdfManager.linkingMap;
        const LN = this.hub.notesManager.linkingMap;

        // Range of L_N:
        const WN = await LN.range();
        // Map from open docIds to array of panel uuids where they are hosted:
        const mD = await this.hub.pdfManager.getHostingMapping();

        // Utility method:
        const cm = this.hub.contentManager;
        const mra = cm.mostRecentlyActive.bind(cm);

        for (const d of DE) {
            if (!mD.has(d)) {
                // The new deduc references doc d, but doc d is not currently on the board.
                continue;
            }
            const Ud = mD.get(d);
            const LC_current = await LC.get(uuid, d);
            // If the panel where the deduc has been opened does not currently have a place
            // to navigate doc d, then we choose one now.
            if (LC_current.length === 0) {
                let v;
                const T = await LC.getTriples({x: d});
                // Does *any* chart panel currently navigate a copy of doc d?
                if (T.length > 0) {
                    // ...if so, then we choose a most-recently-active one of these
                    // doc panels. We prefer one navigated by a chart panel that hosts
                    // deduc E, if possible.
                    const WE = T.filter(t => UE.includes(t[0])).map(t => t[2]);
                    if (WE.length > 0) {
                        v = await mra(WE);
                    } else {
                        v = await mra(T.map(t => t[2]));
                    }
                } else {
                    // ...if not, is doc d currently navigated by any notes panel?
                    const Ud_and_WN = Ud.filter(u => WN.includes(u));
                    if (Ud_and_WN.length > 0) {
                        // ...if so, choose a most-recently-active doc panel that is
                        // so navigated.
                        v = await mra(Ud_and_WN);
                    } else {
                        // ...if not, then just choose any most-recently-active panel
                        // where d is hosted.
                        v = await mra(Ud);
                    }
                }
                await LC.add(uuid, d, v);
            }
            // Every panel hosting doc d should navigate *some* panel hosting deduc E.
            for (const u of Ud) {
                const LD_current = await LD.get(u, deducpath);
                if (LD_current.length === 0) {
                    // Inductive hypothesis says that, in this case, the newly opened copy of E
                    // must be the *first* occurrence in any panel, in any window. (Otherwise,
                    // some link would have already been established.) So, we're happy to make
                    // it be the navigated copy.
                    await this.hub.pdfManager.loadHighlightsGlobal(u, uuid, {
                        acceptFrom: [deducpath],
                        linkTo: [deducpath],
                    });
                }
            }
        }
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

    noteForestClosedAndOpenedDeductions: async function(info) {
        const forest = info.forest;
        const uuid = this.getPanelUuidOfForest(forest);

        const openedDeducs = info.opened; // Object mapping from deducpaths to deducs themselves
        const closedDeducpaths = info.closed; // Array of deducpaths

        // All deducpaths that were opened, whether newly opened, or just reloaded:
        const openedDeducpaths = Array.from(openedDeducs.keys());
        // Deducpaths that were newly opened, i.e. not reloaded:
        const newlyOpenedDeducpaths = [];
        // Deducpaths that were reloaded, i.e. both closed and opened:
        const reloadedDeducpaths = [];
        // Deducpaths that were just closed, i.e. not reloaded:
        const trulyClosedDeducpaths = [];

        for (const deducpath of openedDeducpaths) {
            if (closedDeducpaths.includes(deducpath)) {
                reloadedDeducpaths.push(deducpath);
            } else {
                newlyOpenedDeducpaths.push(deducpath);
            }
        }
        for (const deducpath of closedDeducpaths) {
            if (!reloadedDeducpaths.includes(deducpath)) {
                trulyClosedDeducpaths.push(deducpath);
            }
        }

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

        const menuPlugin = forest.contextMenuPlugin;
        if (typeof(menuPlugin) !== 'undefined') {
            // Manage auto-refresh
            // For newly opened deducs, set auto-refresh option.
            for (let deducpath of newlyOpenedDeducpaths) {
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
            for (let deducpath of trulyClosedDeducpaths) {
                this.setAutoRefreshDeduc(forest, deducpath, false);
                // Free memory:
                menuPlugin.autoReloadByDeducpath.delete(deducpath);
            }
        }

        // Linking
        // TODO:
        //  Decide how to handle reloaded deducs.
        for (const deducpath of newlyOpenedDeducpaths) {
            await this.makeDefaultLinks(deducpath, uuid);
        }
        for (const deducpath of trulyClosedDeducpaths) {
            await this.updateLinkingForClosedDeduc(deducpath, uuid);
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

    handleDocHighlightClick: function(paneId, {supplierUuids, siid, altKey}) {
        const info = {};
        // For highlights supplied by a chart, the siid's simply are the libpaths
        // of the nodes that supplied them. So we either want to view or select
        // that node, according to whether the alt key was held.
        if (altKey) {
            info.view = siid;
        } else {
            info.select = siid;
        }
        this.updateContent(info, paneId);
    },

    /* Note that a node was clicked in a Forest.
     *
     * param forest: the Forest in which the click took place
     * param nodepath: the libpath of the node that was clicked
     * param e: the click event
     */
    noteNodeClick: async function(forest, nodepath, e) {
        // For now we just implement one thing:
        // If the clicked node is now the singleton selection,
        // and if it carries a doc reference, navigate to that highlight
        // in a linked doc panel, if any.
        // If Alt key was pressed, then also auto scroll the selection into view.
        const selMgr = forest.getSelectionManager();
        const singleton = selMgr.getSingletonNode();
        if (singleton !== null && singleton.uid === nodepath) {
            const docId = singleton.docId;
            if (docId) {
                // For now we're only handling pdffp-type docs.
                if (docId.startsWith('pdffp:')) {
                    const uuid = this.getPanelUuidOfForest(forest);
                    const deducInfo = singleton.getDeducInfo();
                    const deducpath = deducInfo?.getLibpath();
                    if (deducpath) {
                        const highlightId = `${deducpath}:${nodepath}`;
                        const info = {
                            type: "PDF",
                            highlightId: highlightId,
                            gotosel: e.altKey ? 'always' : 'never',
                        }
                        const W = await this.linkingMap.get(uuid, docId);
                        for (const w of W) {
                            this.hub.contentManager.updateContentAnywhereByUuid(info, w, {
                                selectPane: true
                            });
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

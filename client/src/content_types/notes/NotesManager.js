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

import { GlobalLinkingMap } from "../linking";
import { DynamicSubscriptionManager, StaticSubscriptionManager } from "../SubscriptionManager";
import { AnnoViewer } from "./AnnoViewer";
import { SphinxViewer } from "./SphinxViewer";
import { util as iseUtil } from "../../util";

define([
    "dojo/_base/declare",
    "dojo/query",
    "ise/content_types/AbstractContentManager",
    "ise/widgets/Widget",
    "ise/widgets/ChartWidget",
    "ise/widgets/LinkWidget",
    "ise/widgets/QnAWidget",
    "ise/widgets/LabelWidget",
    "ise/widgets/GoalWidget",
    "ise/widgets/DocWidget",
    "ise/widgets/ParamWidget",
    "ise/widgets/DispWidget",
    "ise/errors",
    "dojo/NodeList-dom",
    "dojo/NodeList-manipulate",
    "dojo/NodeList-traverse",
], function(
    declare,
    query,
    AbstractContentManager,
    Widget,
    ChartWidget,
    LinkWidget,
    QnAWidget,
    LabelWidget,
    GoalWidget,
    DocWidget,
    ParamWidget,
    DispWidget,
    iseErrors
) {


function constructWidget(hub, libpath, info) {
    switch(info.type) {
    case "CHART":
        return new ChartWidget(hub, libpath, info);
    case "LINK":
        return new LinkWidget(hub, libpath, info);
    case "QNA":
        return new QnAWidget(hub, libpath, info);
    case "LABEL":
        return new LabelWidget(hub, libpath, info);
    case "GOAL":
        return new GoalWidget(hub, libpath, info);
    case "PDF":
        return new DocWidget(hub, libpath, info);
    case "PARAM":
        return new ParamWidget(hub, libpath, info);
    case "DISP":
        return new DispWidget(hub, libpath, info);
    default:
        return new Widget(hub, libpath, info);
    }
}

const DOC_CONTENT_TYPES = [
    "PDF",
];

// NotesManager class
var NotesManager = declare(AbstractContentManager, {

    // Properties
    hub: null,
    // Lookup for viewers (AnnoViewer and SphinxViewer instances) by pane id:
    viewers: null,
    // Mapping that records which tail-versioned page paths are open,
    // and how many copies of each:
    openPagepathvCopyCount: null,

    // Lookup for widgets by uid.
    widgets: null,

    navEnableHandlers: null,

    annoSubscriptionManager: null,
    sphinxSubscriptionManager: null,

    wvuCallback: null,

    // Our GlobalLinkingMap instance.
    // The "secondary IDs" ("x" in method calls) are widget group IDs.
    linkingMap: null,

    // Methods

    constructor: function() {
        this.viewers = {};
        this.openPagepathvCopyCount = new Map();
        this.widgets = new Map();
        this.navEnableHandlers = [];
        this.wvuCallback = this.observeWidgetVisualUpdate.bind(this);
    },

    activate: function() {
        this.hub.windowManager.on('linkingMapNewlyUndefinedAt',
            this.onLinkingMapNewlyUndefinedAt.bind(this));
        this.initLinking();
        this.initSubscrips();
    },

    initLinking: function() {
        const name = 'linking_notes';
        this.linkingMap = new GlobalLinkingMap(this.hub, name);
        this.linkingMap.activate();
    },

    initSubscrips: function() {
        const viewers = this.viewers;
        const nm = this;
        this.annoSubscriptionManager = new DynamicSubscriptionManager(this.hub, {
            fetchName: 'loadAnnotation',
            fetchArgBuilder: (libpath, timestamp) => {
                return {
                    method: "POST",
                    query: { libpath: libpath, cache_code: `${timestamp}`, vers: "WIP" },
                    form: {},
                    handleAs: 'json',
                };
            },
            missingObjErrCode: iseErrors.serverSideErrorCodes.MISSING_ANNOTATION,
            missingObjHandler: (libpath, paneIds, resp) => {
                for (const paneId of paneIds) {
                    const viewer = viewers[paneId];
                    // FIXME: Maybe better than closing the whole pane would be to
                    //  first ask the viewer to remove the current page from its history,
                    //  and move to an adjacent history entry, if possible. Only if there
                    //  was no other history entry would we close the pane.
                    viewer.pane.onClose();
                }
            },
            reloader: (libpath, paneIds, resp) => {
                const data_json = resp.data_json;
                const contents = {
                    html: resp.html,
                    data: JSON.parse(data_json)
                };
                for (const paneId of paneIds) {
                    const viewer = viewers[paneId];
                    viewer.receivePublication(contents);
                }
            },
        });
        this.sphinxSubscriptionManager = new StaticSubscriptionManager(this.hub, {
            staticUrlBuilder: libpath => {
                return nm.makeSphinxUrl(libpath, "WIP");
            },
            fetchContent: false,
            missingObjHandler: (libpath, paneIds, status) => {
                for (const paneId of paneIds) {
                    const viewer = viewers[paneId];
                    // FIXME: Maybe better than closing the whole pane would be to
                    //  first ask the viewer to remove the current page from its history,
                    //  and move to an adjacent history entry, if possible. Only if there
                    //  was no other history entry would we close the pane.
                    viewer.pane.onClose();
                }
            },
            reloader: (libpath, paneIds, url) => {
                for (const paneId of paneIds) {
                    const viewer = viewers[paneId];
                    viewer.refresh(url);
                }
            },
        });
    },

    /* Build the RELATIVE static url for a Sphinx page.
     */
    makeSphinxUrl: function(libpath, version, hash) {
        // Libpath goes: host, owner, repo, remainder, '_page'
        // For the URL we need to:
        //  - insert the version tag as the 4th segment
        //  - chop off the '_page' segment
        const parts = libpath.split('.');
        parts.splice(3, 0, version);
        parts.pop()
        hash = hash || '';
        return `static/sphinx/${parts.join("/")}.html${hash}`
    },

    /* Given the RELATIVE static url for a Sphinx page, return the
     * libpath, version, and hash.
     */
    decomposeSphinxUrl: function(url) {
        const h = url.split("#");
        const hash = h.length === 2 ? h[1] : null;

        const prefix = 'static/sphinx/'
        const suffix = '.html'
        const p = h[0].slice(prefix.length, -suffix.length);
        const parts = p.split('/');

        // parts go: host, owner, repo, version, remainder
        const version = parts.splice(3, 1)[0];

        parts.push('_page');
        const libpath = parts.join('.');

        return {libpath, version, hash};
    },

    // Get an array of the content windows of all Sphinx panels.
    getAllSphinxWindows: function() {
        const wins = [];
        for (const viewer of Object.values(this.viewers)) {
            if (viewer.pageType === "SPHINX") {
                wins.push(viewer.cw);
            }
        }
        return wins;
    },

    getViewerForPaneId: function(paneId) {
        return this.viewers[paneId];
    },

    getSuppliedDocHighlights: function(paneId) {
        const viewer = this.viewers[paneId];
        const docInfoObj = viewer?.currentPageData?.docInfo;
        const hls = {
            docs: new Map(),
            refs: new Map(),
        };
        if (docInfoObj) {
            hls.docs = new Map(Object.entries(docInfoObj.docs));
            hls.refs = new Map(Object.entries(docInfoObj.refs));
        }
        return hls;
    },

    /* Given the full page data object for a notes page, return a Map
     * whose keys are all the widget group Ids occurring within this page,
     * and the value for each key is the docId referenced by that group if
     * any, else null.
     */
    extractGroupsToDocsMapFromPageData: function(pageData) {
        const W = pageData.widgets;
        const groupsToDocs = new Map();
        for (const w of Object.values(W)) {
            const g = w.pane_group;
            const d = w.docId || null;
            if (g) {
                groupsToDocs.set(g, d);
            }
        }
        return groupsToDocs;
    },

    /* Given the group id of a widget, extract the type of the widget.
     */
    extractWidgetTypeFromGroupId: function(groupId) {
        return groupId.split(":")[1];
    },

    /* Synchronously return array of all quadruples (u, s, g, d),
     * in just this window,
     * where:
     *   u is a notes panel uuid,
     *   s is the libpath of the notes page hosted by that panel,
     *   g is a widget group id present in that page,
     *   d is the docId of the document referenced by that widget group,
     *     or null if it's not a doc widget group
     */
    getAllDocRefQuadsLocal: function({}) {
        const quads = [];
        for (const [paneId, viewer] of Object.entries(this.viewers)) {
            const u = this.hub.contentManager.getUuidByPaneId(paneId);
            const pageData = viewer.currentPageData;
            const s = pageData.libpath;
            const groupsToDocs = this.extractGroupsToDocsMapFromPageData(pageData);
            for (const [g, d] of groupsToDocs) {
                quads.push([u, s, g, d]);
            }
        }
        return quads;
    },

    /* Return promise that resolves with array of all quadruples (u, s, g, d),
     * across all windows,
     * where:
     *   u is a notes panel uuid,
     *   s is the libpath of the notes page hosted by that panel,
     *   g is a widget group id present in that page,
     *   d is the docId of the document referenced by that widget group,
     *     or null if it's not a doc widget group
     */
    getAllDocRefQuads: function() {
        return this.hub.windowManager.broadcastAndConcat(
            'hub.notesManager.getAllDocRefQuadsLocal',
            {},
            {excludeSelf: false}
        );
    },

    /* Control visibility of the overview sidebar for a given notes pane.
     #
     * param paneId: the pane id of the notes pane in question.
     * param doShow: boolean: true to show sidebar, false to hide it.
     */
    showOverviewSidebar: function(paneId, doShow) {
        const viewer = this.viewers[paneId];
        if (viewer) {
            viewer.showOverviewSidebar(doShow);
        }
    },

    addNavEnableHandler: function(callback) {
        this.navEnableHandlers.push(callback);
    },

    publishNavEnable: function(data) {
        this.navEnableHandlers.forEach(cb => {
            cb(data);
        });
    },

    /* Say whether we currently have any widgets belonging to a given widget group.
     */
    groupHasRepresentative: function(groupId) {
        for (let [uid, widget] of this.widgets) {
            if (widget.groupId() === groupId) {
                return true;
            }
        }
        return false;
    },

    getPanesForAnnopathv: function(annopathv) {
        const panes = {};
        for (let id of Object.keys(this.viewers)) {
            const viewer = this.viewers[id];
            if (viewer.getCurrentLibpathv() === annopathv) {
                panes[id] = viewer.pane;
            }
        }
        return panes;
    },

    // ----------------------------------------------------------------------------------
    // ContentManager Interface

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
        const options = {};
        const sbProps = info.sidebar || {};
        if (sbProps.scale) {
            options.overviewScale = sbProps.scale;
        }
        const viewer = info.type === this.hub.contentManager.crType.SPHINX ?
            new SphinxViewer(this, elt, pane, info.uuid, options) :
            new AnnoViewer(this, elt, pane, info.uuid, options);
        viewer.addNavEnableHandler(this.publishNavEnable.bind(this));
        viewer.on('pageChange', this.notePageChange.bind(this));
        viewer.on('pageReload', this.notePageReload.bind(this));
        this.viewers[pane.id] = viewer;
        const hasHistory = ('history' in info && 'ptr' in info);
        return viewer.goTo(info).then(function() {
            if (hasHistory) {
                viewer.forceHistory(info.history, info.ptr);
            }
            if (sbProps.visible) {
                viewer.showOverviewSidebar(true);
            }
        });
    },

    pushScrollFrac: function(paneId) {
        const viewer = this.viewers[paneId];
        if (viewer) {
            viewer.pushScrollFrac();
        }
    },

    popScrollFrac: function(paneId) {
        const viewer = this.viewers[paneId];
        if (viewer) {
            viewer.popScrollFrac();
        }
    },

    /* Update the content of an existing pane of this manager's type.
     *
     * param info: An info object indicating the desired content.
     * param paneId: The ID of the ContentPane that is to be updated.
     * return: nothing
     */
    updateContent: function(info, paneId) {
        const viewer = this.viewers[paneId];
        viewer.goTo(info);
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
        const viewer = this.viewers[oldPaneId];
        return viewer.writeContentDescriptor(serialOnly);
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
        for (let w of this.widgets.values()) {
            w.noteCopy(oldPaneId, newPaneId);
        }
    },

    noteNewMathWorker: function() {
        for (let w of this.widgets.values()) {
            w.noteNewMathWorker();
        }
    },

    /* This is our listener for the "pageChange" event of each of
     * our viewer instances. That event is fired iff the viewer has
     * loaded a page of different libpath or version from what it was before.
     */
    notePageChange: async function(event) {
        // Maintain records of which pagepaths are open, and how many copies of each.

        // newLibpath is always defined
        const nlv = event.newLibpathv;
        let nlpCount = this.openPagepathvCopyCount.get(nlv) || 0;
        this.openPagepathvCopyCount.set(nlv, ++nlpCount);

        // oldLibpath may be null
        const olv = event.oldLibpathv;
        if (olv) {
            this.notePageClose(olv);
            await this.updateLinkingForPage(event.uuid, event.oldPageData, event.newPageData);
        }

        // Make default links for newly loaded page.
        const nlp = nlv.split("@")[0];
        await this.makeDefaultLinks(nlp, event.uuid);
    },

    /* This is our listener for the "pageReload" event of each of
     * our viewer instances. That event is fired after the viewer has
     * finished reloading a page that was just rebuilt.
     */
    notePageReload: async function({uuid, libpath, oldPageData, newPageData}) {
        // First step handles widget groups that went away or stayed, and
        // doc references that went away or stayed:
        await this.updateLinkingForPage(uuid, oldPageData, newPageData);
        // Second step handles new widget groups, and new doc references:
        await this.makeDefaultLinks(libpath, uuid);
    },

    notePageClose: function(pagepathv) {
        let count = this.openPagepathvCopyCount.get(pagepathv);
        if (count) {
            this.openPagepathvCopyCount.set(pagepathv, --count);
            if (count === 0) {
                this.openPagepathvCopyCount.delete(pagepathv);
                this.purgeAllWidgetsForPagepathv(pagepathv);
            }
        }
    },

    /* Take note of the fact that a pane of this manager's type is about to close.
     *
     * param closingPane: The ContentPane that is about to close.
     * return: nothing
     */
    noteClosingContent: function(closingPane) {
        for (let w of this.widgets.values()) {
            w.noteClosingPane(closingPane);
            w.destroyContextMenu(closingPane.id);
        }
        const paneId = closingPane.id;
        const viewer = this.viewers[paneId];
        const pagepathv = viewer.getCurrentLibpathv();
        if (pagepathv) {
            this.notePageClose(pagepathv);
        }
        viewer.destroy();
        delete this.viewers[paneId];
    },

    /* Handle the case of a notes panel N for which either:
     *   - the user has navigated away from page P to page Q, or
     *   - the user has rebuilt the page P that is hosted in panel N
     * where panel N belongs to our window.
     *
     * When this method is invoked, the page viewer in the notes panel has finished
     * navigating to the new page, or reloading the existing page.
     *
     * param uuid: the uuid of the notes panel N
     * param oldPageData: the full page data object for the page before the change
     * param newPageData: the full page data object for the page after the change
     */
    updateLinkingForPage: async function(uuid, oldPageData, newPageData) {
        const LD = this.hub.pdfManager.linkingMap;

        // Note: We used to remove mappings from L_N for widget groups that were
        // no longer present in the page, but that is not correct behavior. We want
        // those mappings to persist until the panel is closed. Consider a user who
        // is clicking through Sphinx pages P, Q, R, where pages P and R have chart
        // widgets belonging to a common group, but Q does not. The user wants page R
        // to continue navigating the same chart panel that P navigated. If we pruned
        // the mapping when page Q was loaded, this would be broken.

        const pageChanged = (
            newPageData.libpath !== oldPageData.libpath ||
            newPageData.version !== oldPageData.version
        );

        if (pageChanged) {
            // We have moved to a new page.
            const oldpagepath = oldPageData.libpath;

            // Clean up L_D.
            // If L_D is telling any doc panels to carry out navigations for the old page
            // in this panel, it must remove such links.
            await LD.removeTriples({x: oldpagepath, w: uuid});
        } else {
            // We are still on the same page, which therefore must have been rebuilt, as
            // that is the only other reason for calling this method.
            const mD = await this.hub.pdfManager.getHostingMapping();

            const gd1 = this.extractGroupsToDocsMapFromPageData(oldPageData);
            const gd2 = this.extractGroupsToDocsMapFromPageData(newPageData);

            const pagepath = newPageData.libpath;

            // Docs referenced before:
            const D1 = new Set(Array.from(gd1.values()).filter(d => d !== null));
            // Docs referenced now:
            const D2 = new Set(Array.from(gd2.values()).filter(d => d !== null));

            // Docs that went away:
            const Dminus = Array.from(D1).filter(d => !D2.has(d));
            // Docs that stayed:
            const D0 = Array.from(D1).filter(d => D2.has(d));

            // For docs that went away, there should not be any linking from panels hosting
            // those docs to this panel.
            for (const d of Dminus) {
                if (mD.has(d)) {
                    for (const u of mD.get(d)) {
                        await LD.removeTriples({u, x: pagepath, w: uuid});
                    }
                }
            }

            // Note: since the docId referenced by a doc widget is incorporated in
            // the group id of that widget, it is impossible for any of the groups
            // that stayed to now reference a different doc than they did before.

            // For docs that stayed, the set of highlights could have changed, so they have
            // to be reloaded.
            for (const d of D0) {
                if (mD.has(d)) {
                    for (const u of mD.get(d)) {
                        await this.hub.pdfManager.loadHighlightsGlobal(u, uuid, {
                            acceptFrom: [pagepath],
                            linkTo: [],
                            reload: true,
                        });
                    }
                }
            }
        }
    },

    /* Establish default links for notes page p in notes panel N.
     *
     * param pagepath: the libpath of notes page p
     * param uuid: the uuid of notes panel N
     */
    makeDefaultLinks: async function(pagepath, uuid) {
        const quads = await this.getAllDocRefQuads();
        const mD = await this.hub.pdfManager.getHostingMapping();

        // Map from docIds to sets of widget group ids, for notes panel N:
        const Ndg = new iseUtil.SetMapping();
        // Set of all widget group ids in notes panel N:
        const G = new Set();
        for (const [u, s, g, d] of quads) {
            if (u === uuid) {
                G.add(g);
                if (d) {
                    Ndg.add(d, g);
                }
            }
        }

        const LN = this.linkingMap;
        const LD = this.hub.pdfManager.linkingMap;

        const cm = this.hub.contentManager;
        const mra = cm.mostRecentlyActive.bind(cm);
        const mrat = cm.moreRecentlyActiveThan.bind(cm);

        // Find most-recently-active navigated panel, if any, for each group in G.
        const T = await LN.getTriples({});
        const R = new Map();
        for (const [u, x, w] of T) {
            if (G.has(x) && await mrat(w, R.get(x))) {
                R.set(x, w);
            }
        }

        // For each group g in G, if it has a most-recently-active navigated panel, and L_N is
        // not yet defined at this group for panel N, then make panel N navigate that one too.
        for (const g of G) {
            const w = R.get(g);
            if (w) {
                const LN_current = await LN.get(uuid, g);
                if (LN_current.length === 0) {
                    await LN.add(uuid, g, w);
                    // Note: in the case that w is a doc panel, there is no need to load highlights
                    // into it right now, since that will be handled (if necessary) at the end of
                    // this method, where we iterate over the `mD` map.
                }
            }
        }

        // Note: Except for any link (uuid, g) |--> R(g) that may have been formed above, we
        // deliberately do not form any default links N --> C. If a chart panel C was not already
        // navigated by any of the groups occurring in our notes page, then there is no good reason
        // for any of them to link to it now. Chart panels are different from notes and doc panels
        // in that their "topic" is completely free: they can host any (changing) combination of
        // deductions. So we assume that C may already be navigated by some *other* group(s), or
        // the user may just be using it for manual exploration, and we leave it alone.

        // For docs d referenced by doc widgets in N, if there's just a sole group referencing
        // that doc in N, and if that doc is already on the board, and if that group hasn't received
        // a mapping for panel N yet, then we assign it to an m.r.a. panel in which the doc is found.
        for (const [d, Gd] of Ndg.mapping) {
            if (Gd.size === 1 && mD.has(d)) {
                const g = Array.from(Gd)[0];
                const LN_current = await LN.get(uuid, g);
                if (LN_current.length === 0) {
                    const w = await mra(mD.get(d));
                    await LN.add(uuid, g, w);
                    // We do not load the highlights into doc panel w at this time.
                    // Either doc panel w already navigates a copy of notes page p, or it does not.
                    // If it does, then it already has the highlights, and we don't want to make it
                    // navigate a second copy. If it does not, then the iteration below, over mD, will
                    // take care of it, i.e. will link to panel N and load the highlights.
                }
            }
        }

        // Every panel hosting any doc d referenced by notes page p should navigate *some*
        // panel hosting this page.
        for (const [d, Ud] of mD) {
            if (Ndg.mapping.has(d)) {
                for (const u of Ud) {
                    const LD_current = await LD.get(u, pagepath);
                    if (LD_current.length === 0) {
                        // Inductive hypothesis says that, in this case, the given copy of notes page
                        // p must be the only occurrence in any panel, in any window. (Otherwise,
                        // some link would have already been established.) So, we're happy to make
                        // it be the navigated copy.
                        await this.hub.pdfManager.loadHighlightsGlobal(u, uuid, {
                            acceptFrom: [pagepath],
                            linkTo: [pagepath],
                        });
                    }
                }
            }
        }
    },

    /* "Claim" linking: a doc widget may be left without a default link, even when its doc
     * is present; however, in such cases, a doc panel may sometimes be claimed for it at
     * click time.
     *
     * Default links are turned down when there are two or more widget groups in a page that
     * reference the same doc; it would be unfair to give either one the default link, so we
     * give it to neither. However, such a doc panel can be "claimed" at the time that such
     * a doc widget is actually clicked, and we call this "claim linking". This method
     * determines whether there is a panel that could be claimed, and chooses a best one.
     *
     * param d0: the docId for which we want to claim an existing panel (if any)
     * param g0: the widget group id of the group that wants to claim a panel
     * param u0: the uuid of the panel where group g0 was clicked
     *
     * return: uuid of panel to be claimed, or null if none can be claimed
     */
    findClaimableDocPanel: async function(d0, g0, u0) {
        let claimed = null;
        const mD = await this.hub.pdfManager.getHostingMapping();
        if (mD.has(d0)) {
            const quads = await this.getAllDocRefQuads();
            // Find the set of group ids in panel u0 referencing doc d0, and
            // different from g0. These are group g0's "competition"; g0 must
            // not navigate a panel navigated by any of these groups. (This is
            // the whole point of widget groups.)
            const Gcontra = new Set();
            for (const [u, s, g, d] of quads) {
                if (u === u0 && d === d0 && g !== g0) {
                    Gcontra.add(g);
                }
            }

            // Doc panels already navigated by group g0 (therefore hosting d0):
            const W0 = new Set();
            // Doc panels navigated by groups in Gcontra (therefore hosting d0):
            const Wcontra = new Set();
            // Doc panels (hosting *any* doc) navigated by anything else:
            let Wother = new Set();

            const LN = this.linkingMap;
            const LC = this.hub.chartManager.linkingMap;

            const T = await LN.getTriples({});
            for (const [u, x, w] of T) {
                if (x === g0) {
                    W0.add(w);
                } else if (Gcontra.has(x)) {
                    Wcontra.add(w);
                } else {
                    Wother.add(w);
                }
            }

            const cm = this.hub.contentManager;
            const mra = cm.mostRecentlyActive.bind(cm);

            if (W0.size > 0) {
                // If group g0 already has an assignment in any panel, we join it.
                claimed = await mra(Array.from(W0));
            } else {
                // Otherwise, we have to choose from among existing panels hosting doc d0,
                // that are *not* in Wcontra.
                const Ud = mD.get(d0);
                const candidates = Ud.filter(u => !Wcontra.has(u));
                if (candidates.length > 0) {
                    // We prefer to choose a panel that is already navigated (by anything).
                    const WC = await LC.range();
                    const alreadyNaved = new Set(Array.from(Wother).concat(WC));
                    const alreadyNavedCandidates = candidates.filter(w => alreadyNaved.has(w));
                    if (alreadyNavedCandidates.length > 0) {
                        claimed = await mra(alreadyNavedCandidates);
                    } else {
                        claimed = await mra(candidates);
                    }
                }
            }

        }
        return claimed;
    },

    // Handle the event that a linking map has become newly undefined at a pair (u, x).
    onLinkingMapNewlyUndefinedAt: async function({name, pair, doNotRelink}) {
        if (doNotRelink) {
            return;
        }
        // Is it our linking map?
        if (name === this.linkingMap.name) {
            const [u0, g0] = pair;
            const paneId = this.hub.contentManager.getPaneIdByUuid(u0);
            // Does the pane of uuid u0 exist in our window?
            if (paneId) {
                let canRelink = false;
                // Does group g0 still exist within it?
                const quads = this.getAllDocRefQuadsLocal({});
                for (const [u, s, g, d] of quads) {
                    if (u === u0 && g === g0) {
                        canRelink = true;
                        break;
                    }
                }
                if (canRelink) {
                    // Since the (panel, group) pair is still present, but has lost a nav target, it
                    // may be possible to establish a new default link to fill this vacuum.
                    const viewer = this.viewers[paneId];
                    const loc = viewer.describeCurrentLocation();
                    if (loc) {
                        const pagepath = loc.libpath;
                        await this.makeDefaultLinks(pagepath, u0);
                    }
                }
            }
        }
    },

    setTheme: function(theme) {
        for (const v of Object.values(this.viewers)) {
            v.setTheme(theme);
        }
        for (const w of this.widgets.values()) {
            w.setTheme(theme);
        }
    },

    setZoom: function(level) {
        for (const v of Object.values(this.viewers)) {
            v.setZoom(level);
        }
    },

    /* Given the libpathv of a page, get an array of the UIDs of all
     * widgets currently loaded in memory that belong to that page.
     */
    getAllOpenWidgetUidsUnderPagepathv: function(pagepathv) {
        const uids = [];
        for (let [uid, widget] of this.widgets) {
            if (widget.getPagepathv() === pagepathv) {
                uids.push(uid);
            }
        }
        return uids;
    },

    /* Purge all widgets that belong to a given page.
     */
    purgeAllWidgetsForPagepathv: function(pagepathv) {
        const uids = this.getAllOpenWidgetUidsUnderPagepathv(pagepathv);
        for (let uid of uids) {
            this.purgeWidget(uid);
        }
    },

    /* Completely remove a widget from all data structures.
     *
     * @param uid: the UID of the widget to be purged.
     */
    purgeWidget: function(uid) {
        if (this.widgets.has(uid)) {
            this.widgets.delete(uid);
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
        let viewer = this.viewers[pane.id];
        let p = Promise.resolve();
        if (direction < 0) {
            p = viewer.goBackward();
        } else if (direction > 0) {
            p = viewer.goForward();
        }
        return p.then(() => [viewer.canGoBackward(), viewer.canGoForward()]);
    },

    // ----------------------------------------------------------------------------------

    /* Handle mouse events on NavWidgets.
     *
     * param uid: the unique id of the widget
     * param event: the browser-native mouse event object
     * param pane: the Dijit pane in which the event happened
     */
    handleNavWidgetMouseEvent: async function(uid, event, pane) {
        const action = {mouseover: 'show', mouseout: 'hide', click: 'click'}[event.type];
        const clickedElt = event.target;
        const LN = this.linkingMap;

        const widget = this.widgets.get(uid);
        const gid = widget.groupId();

        const cm = this.hub.contentManager;
        const clickedPane = pane;
        const clickedPanelUuid = cm.getUuidByPaneId(clickedPane.id);
        const targetUuids = await LN.get(clickedPanelUuid, gid);

        const {existing, nonExisting} = await cm.sortUuidsByExistenceInAnyWindow(targetUuids);
        // Do we really need this self-repairing step here? Theoretically, we're already
        // doing bookkeeping elsewhere, so should never have to purge lost targets here....
        if (nonExisting.length > 0) {
            for (const missingUuid of nonExisting) {
                await LN.removeTriples({w: missingUuid})
            }
        }

        // Before we can handle clicks or mouseover/mouseout, we have to check
        // to see if there is a claim-link to be made.
        let claimable = null;
        const info = widget.getInfoCopy();
        if (DOC_CONTENT_TYPES.includes(info.type) && existing.length === 0) {
            const d = info.docId;
            claimable = await this.findClaimableDocPanel(d, gid, clickedPanelUuid);
            if (claimable) {
                existing.push(claimable);
            }
        }

        if (action === 'click') {
            const viewer = this.viewers[clickedPane.id];
            viewer.markWidgetElementAsSelected(clickedElt);
            if (DOC_CONTENT_TYPES.includes(info.type)) {
                if (existing.length === 0) {
                    // The only reason not to auto-scroll to a selection is to avoid disrupting sth
                    // the user was already looking at; hence, with a newly spawned panel, we should
                    // always scroll.
                    info.gotosel = 'always';
                } else {
                    // This is our hacky way of getting the "alt key semantics" passed all the
                    // way to the content update, without trying to pipe an event object all the
                    // way there.
                    // Currently just doing this for DOC widgets.
                    // Do we want sth similar for chart widgets? There we have long supported the
                    // author in saying whether navigation happens. It seems we're moving toward
                    // making this the user's choice instead, but, not ready to implement this today.
                    info.gotosel = event.altKey ? 'never' : 'always';
                }
                // Another hack. This is so that, if a doc panel is to be spawned, it knows how
                // to obtain named highlights, if we requested one under `highlightId`.
                info.requestingUuid = clickedPanelUuid;
            }
            const {spawned} = await cm.updateOrSpawnBeside(info, existing, clickedPanelUuid);
            if (spawned) {
                await LN.add(clickedPanelUuid, gid, spawned);
            } else if (claimable) {
                await LN.add(clickedPanelUuid, gid, claimable);
            }
        } else {
            this.hub.windowManager.groupcastEvent({
                type: 'intentionToNavigate',
                action: action,
                source: clickedPanelUuid,
                panels: existing,
            }, {
                includeSelf: true,
            });
        }
    },

    constructWidget: function(info) {
        return constructWidget(this.hub, info.widget_libpath, info);
    },

    getWidget: function(uid) {
        return this.widgets.get(uid);
    },

    /* Instantiate and activate the Widget instances for a page.
     *
     * @param data: This is an object of the form {
     *   libpath: the libpath of the page where these widgets are defined
     *   version: the version of the page where these widgets are defined
     *   widgets: {
     *     widgetUID1: widgetData1,
     *     widgetUID2: widgetData2,
     *     ...
     *   }
     * }
     *   Here a widget UID is of the form
     *     xy-foo-bar-path-to-widget_vM-m-p
     *   or
     *     xy-foo-bar-path-to-widget_WIP
     *   while the format of the widgetDatas varies by widget type.
     * @param elt: The DOM element in which page content is to be set.
     * @param pane: The ContentPane where elt lives.
     */
    setupWidgets: function(data, elt, pane) {
        const incomingUids = Object.keys(data.widgets);

        // Purge any widgets that no longer belong to the page.
        const pagepathv = iseUtil.lv(data.libpath, data.version);
        const uidsUnderPage = this.getAllOpenWidgetUidsUnderPagepathv(pagepathv);
        for (let uid of uidsUnderPage) {
            if (!incomingUids.includes(uid)) {
                this.purgeWidget(uid);
            }
        }

        // Build or update widgets.
        for (let uid of incomingUids) {
            /* We make this method work both for initial content load, and content
             * update, by first checking whether we have a widget that is both of
             * the given uid and of the same type. If so, we update its info, instead
             * of making a new widget.
             *
             * It is important that we demand the types match before we are willing to
             * merely update the existing widget; in other words, if the libpaths are
             * the same, but the types differ, then we must replace the existing widget
             * with a completely new one.
             *
             * This is no mere edge case; a very common case is that a
             * widget will first show up as of "malformed" type, due to a syntax error,
             * and then will show up again with its intended type (but the same libpath),
             * after the user fixes the error. If we only updated the MalformedWidget with
             * the new info, it would be a bug, and the user would have to reload the
             * entire ISE to get this page to load correctly.
             */
            const info = data.widgets[uid];
            //console.log(info);
            let widget = null;
            if (this.widgets.has(uid)) {
                widget = this.widgets.get(uid);
                if (widget.origInfo.type === info.type) {
                    widget.updateInfo(info);
                } else {
                    this.purgeWidget(uid);
                    widget = null;
                }
            }
            if (widget === null) {
                widget = this.constructWidget(info);
                this.widgets.set(uid, widget);
            }
        }

        const socket = query(elt);
        const theNotesManager = this;

        // Pre-activate widgets.
        // (This provides a chance for _every_ widget to make any necessary preparations
        // before _any_ widget has activated itself.)
        for (let uid of incomingUids) {
            const widget = this.widgets.get(uid);
            const wdq = socket.query('.' + uid);
            widget.preactivate(wdq, uid, theNotesManager, pane);
        }

        // Activate widgets, make context menus, set listeners.
        for (let uid of incomingUids) {
            const widget = this.widgets.get(uid);
            const wdq = socket.query('.' + uid);
            widget.makeContextMenu(pane);
            widget.activate(wdq, uid, theNotesManager, pane);
            widget.on('widgetVisualUpdate', this.wvuCallback, {nodup: true});
        }

        // Setting up the widgets is the last step of loading a new page, so signal to the
        // viewer that it can now announce any waiting page change event.
        const viewer = this.getViewerForPaneId(pane.id);
        viewer.announcePageChangeIfAny();
    },

    observeWidgetVisualUpdate: function(event) {
        const viewer = this.viewers[event.paneId];
        viewer.observeWidgetVisualUpdate(event);
    },

});

return NotesManager;

});
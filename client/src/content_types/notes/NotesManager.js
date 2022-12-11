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

import { UnknownPeerError } from "browser-peers/src/errors";

define([
    "dojo/_base/declare",
    "dojo/query",
    "ise/content_types/notes/PageViewer",
    "ise/widgets/Widget",
    "ise/widgets/ChartWidget",
    "ise/widgets/LinkWidget",
    "ise/widgets/QnAWidget",
    "ise/widgets/LabelWidget",
    "ise/widgets/GoalWidget",
    "ise/widgets/PdfWidget",
    "ise/widgets/ParamWidget",
    "ise/widgets/DispWidget",
    "ise/util",
    "ise/errors",
    "dojo/NodeList-dom",
    "dojo/NodeList-manipulate",
    "dojo/NodeList-traverse",
], function(
    declare,
    query,
    PageViewer,
    Widget,
    ChartWidget,
    LinkWidget,
    QnAWidget,
    LabelWidget,
    GoalWidget,
    PdfWidget,
    ParamWidget,
    DispWidget,
    iseUtil,
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
        return new PdfWidget(hub, libpath, info);
    case "PARAM":
        return new ParamWidget(hub, libpath, info);
    case "DISP":
        return new DispWidget(hub, libpath, info);
    default:
        return new Widget(hub, libpath, info);
    }
}

// NotesManager class
var NotesManager = declare(null, {

    // Properties
    hub: null,
    // Lookup for PageViewers by pane id:
    viewers: null,
    // Mapping that records which annopathvs are open, and how many copies of each:
    openAnnopathvCopyCount: null,

    // Lookup for widgets by uid.
    widgets: null,

    // At any given time, a widget group may or may not have a controlled pane.
    // When it does, we keep a mapping from group ID to pane location, and the
    // inverse mapping as well.
    groupId2paneLoc: null,
    paneLoc2groupId: null,

    navEnableHandlers: null,

    annopathsToSubscribedPaneIds: null,
    modpathsToAnnopathsHavingSubscribers: null,

    wvuCallback: null,

    // Methods

    constructor: function() {
        this.viewers = {};
        this.openAnnopathvCopyCount = new Map();
        this.widgets = new Map();
        this.groupId2paneLoc = new Map();
        this.paneLoc2groupId = new Map();
        this.navEnableHandlers = [];
        this.annopathsToSubscribedPaneIds = new iseUtil.LibpathSetMapping();
        this.modpathsToAnnopathsHavingSubscribers = new iseUtil.LibpathSetMapping();
        this.wvuCallback = this.observeWidgetVisualUpdate.bind(this);
    },

    activate: function() {
        this.hub.socketManager.on('moduleBuilt', this.handleModuleBuiltEvent.bind(this));
        this.hub.windowManager.on('paneClose', this.checkForClosingWidgetPane.bind(this));
        this.hub.windowManager.on('paneMove', this.updateControlledPaneLocation.bind(this));
        this.hub.windowManager.on('updateMapping', this.handleUpdatedWindowMapping.bind(this));
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

    groupHasControlledPane: function(groupId) {
        return this.groupId2paneLoc.has(groupId);
    },

    /* Say whether we currently have any widgets belonging to a given widget group.
     */
    groupHasRepresentative: function(groupId) {
        for (let [uid, widget] of this.widgets) {
            if (widget.groupId === groupId) {
                return true;
            }
        }
        return false;
    },

    getPaneLocForGroup: function(groupId) {
        return this.groupId2paneLoc.get(groupId);
    },

    getPaneLoc2GroupIdMapping: function() {
        return this.paneLoc2groupId;
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
        const viewer = new PageViewer(this, elt, pane, options);
        viewer.addNavEnableHandler(this.publishNavEnable.bind(this));
        viewer.on('pageChange', this.notePageChange.bind(this));
        this.viewers[pane.id] = viewer;
        const hasHistory = ('history' in info && 'ptr' in info);
        if (info.wgcm) {
            // If a WGCM was provided, we take it as a suggestion.
            this.considerWgcm(info.wgcm);
        }
        return viewer.goTo(info).then(function() {
            if (hasHistory) {
                viewer.forceHistory(info.history, info.ptr);
            }
            if (sbProps.visible) {
                viewer.showOverviewSidebar(true);
            }
        });
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
        const viewer = this.viewers[oldPaneId],
            stateInfo = viewer.describeCurrentLocation();
        stateInfo.type = this.hub.contentManager.crType.NOTES;
        stateInfo.history = viewer.copyHistory();
        stateInfo.sidebar = viewer.getSidebarProperties();
        stateInfo.ptr = viewer.ptr;
        stateInfo.wgcm = this.getWidgetGroupControlMapping({
            annopathv: `${stateInfo.libpath}@${stateInfo.version}`,
            absolute: true,
        });
        return stateInfo;
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

    /* This is our listener for the "pageChange" event of each and every one of
     * our PageViewer instances.
     *
     * We use this to maintain our records of which annopaths are open, and how
     * many copies of each.
     */
    notePageChange: function(event) {
        // newLibpath is always defined
        const nlv = event.newLibpathv;
        let nlpCount = this.openAnnopathvCopyCount.get(nlv) || 0;
        this.openAnnopathvCopyCount.set(nlv, ++nlpCount);
        // oldLibpath may be null
        const olv = event.oldLibpathv;
        if (olv) {
            this.notePageClose(olv);
        }
    },

    notePageClose: function(annopathv) {
        let count = this.openAnnopathvCopyCount.get(annopathv);
        if (count) {
            this.openAnnopathvCopyCount.set(annopathv, --count);
            if (count === 0) {
                this.openAnnopathvCopyCount.delete(annopathv);
                this.purgeAllWidgetsForAnnopathv(annopathv);
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
        const annopathv = viewer.getCurrentLibpathv();
        if (annopathv) {
            this.notePageClose(annopathv);
        }
        viewer.destroy();
        delete this.viewers[paneId];
    },

    /* Given the libpathv of an annotation, get an array of the UIDs of all
     * widgets currently loaded in memory that belong to that annotation.
     */
    getAllOpenWidgetUidsUnderAnnopathv: function(annopathv) {
        const uids = [];
        for (let [uid, widget] of this.widgets) {
            if (widget.getAnnopathv() === annopathv) {
                uids.push(uid);
            }
        }
        return uids;
    },

    /* Respond to the fact that a content pane has moved to a new location.
     * This may or may not affect our current WGCM. The purpose of this method
     * is to update our mapping as necessary.
     *
     * @param oldAbsLoc {string} the absolute location from which a pane has moved.
     * @param newAbsLoc {string} the absolute location to which the pane has moved.
     */
    updateControlledPaneLocation: function({ oldAbsLoc, newAbsLoc }) {
        const groupId = this.paneLoc2groupId.get(oldAbsLoc);
        if (groupId) {
            this.paneLoc2groupId.delete(oldAbsLoc);
            this.setPaneLocForWidgetGroup(newAbsLoc, groupId);
        }
    },

    /* Respond to the fact that the window group enumeration has changed.
     * Existing windows may have received new numbers, and/or an existing
     * window may have closed. We must update the WGCM accordingly.
     *
     * @param numberUpdates {Obj} pairs oldNumber:newNumber for windows that
     *   received a new number.
     * @param deletedNumber {int|null} at most one window goes away per event;
     *   this either the number of the window that went away, or null if none did.
     */
    handleUpdatedWindowMapping: function({ numberUpdates, deletedNumber }) {
        // We'll iterate over `this.groupId2paneLoc`. So we can safely
        // delete entries from `this.paneLoc2groupId` as we go, but must also
        // build up a plan of changes to be carried out after iteration.
        // This includes deletions from `this.groupId2paneLoc`, and all setting
        // of new locations.
        const groupUpdates = new Map();
        for (let [groupId, paneLoc] of this.groupId2paneLoc) {
            const [n, paneId] = this.hub.windowManager.digestLocation(paneLoc);
            if (n === deletedNumber) {
                groupUpdates.set(groupId, null);
                this.paneLoc2groupId.delete(paneLoc);
            } else if (numberUpdates.hasOwnProperty(n)) {
                const newLoc = `${numberUpdates[n]}:${paneId}`;
                groupUpdates.set(groupId, newLoc);
                this.paneLoc2groupId.delete(paneLoc);
            }
        }
        for (let [groupId, update] of groupUpdates) {
            if (update === null) {
                this.groupId2paneLoc.delete(groupId);
            } else {
                this.setPaneLocForWidgetGroup(update, groupId);
            }
        }
    },

    /* A "widget group control mapping" (WGCM) is a mapping from widget group IDs
     * to "pane locs" (pane locations) for controlled panes. The complete, current mapping
     * is maintained in our `groupId2paneLoc` Map.
     *
     * This method computes a WGCM based on our current one, and according to certain
     * options.
     *
     * @param options {
     *   annopathv: {string} an optional annotation libpathv. If provided, we restrict
     *     the mapping to those group IDs falling under this annotation and version.
     *   asMap: {bool, default false} if true we return a Map; otherwise just an object in which
     *     the key-value pairs represent the mapping.
     *   absolute: {bool, default false} if true we ensure that all pane locations are absolute.
     * }
     * @return: the computed mapping.
     */
    getWidgetGroupControlMapping: function(options) {
        const {
            annopathv = null,
            asMap = false,
            absolute = false,
        } = options || {};
        const uids = annopathv ? this.getAllOpenWidgetUidsUnderAnnopathv(annopathv) : this.widgets.keys();
        const wgcm = asMap ? new Map() : {};
        for (let uid of uids) {
            const widget = this.widgets.get(uid);
            const groupId = widget.groupId;
            let paneLoc = this.groupId2paneLoc.get(groupId);
            if (paneLoc) {
                if (absolute) {
                    paneLoc = this.hub.windowManager.makeLocationAbsolute(paneLoc);
                }
                if (asMap) {
                    wgcm.set(groupId, paneLoc);
                } else {
                    wgcm[groupId] = paneLoc;
                }
            }
        }
        return wgcm;
    },

    /* Purge all widgets that belong to a given annotation.
     */
    purgeAllWidgetsForAnnopathv: function(annopathv) {
        const uids = this.getAllOpenWidgetUidsUnderAnnopathv(annopathv);
        for (let uid of uids) {
            this.purgeWidget(uid);
        }
    },

    /* Completely remove a widget from all data structures.
     *
     * @param uid: the UID of the widget to be purged.
     */
    purgeWidget: function(uid) {
        this.widgets.delete(uid);
        /* Note: we make no effort to clean up the `this.groupId2paneLoc` mapping (and its inverse)
         * when the last widget belonging to a given group is purged; we actually prefer to keep this
         * mapping in place. For suppose notes pane N is controlling, say, chart pane C. Suppose then
         * that N is closed while C remains open. The user might want to reopen N, and will be happy
         * to have this new copy of N already controlling the existing pane C. If not, they can simply
         * close C, since we do clean up the mappings when the controlled panes close.
         */
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

    /* This is our handler for the `paneClose` event, which occurs when any pane
     * in any window is closing. We can then check whether this was a controlled
     * pane, and, if so, update the WGCM accordingly.
     *
     * @param paneId: the id of the ContentPane that is closing
     * @param origin: the window number where the pane was located
     */
    checkForClosingWidgetPane: function({paneId, origin}) {
        const paneLoc = `${origin}:${paneId}`;
        const groupId = this.paneLoc2groupId.get(paneLoc);
        if (groupId) {
            // It was a controlled pane.
            // We clean up our records of that pane, so that a new one can be
            // spawned if any widget in that group is clicked again.
            this.groupId2paneLoc.delete(groupId);
            this.paneLoc2groupId.delete(paneLoc);
        }
    },

    // ----------------------------------------------------------------------------------

    /* Handle a widget click.
     *
     * param uid: The unique id of the widget that was clicked.
     * param clickedElt: The DOM element that was clicked.
     */
    click: function(uid, clickedElt) {
        // Retrieve the widget and its info.
        const widget = this.widgets.get(uid);
        // Not all widget types have pane groups (e.g. `qna` widgets).
        // This method _should_ never be called on a widget that doesn't have a group,
        // but we check just in case.
        if (!widget.groupId) {
            console.error('Widget has no pane group.');
            return;
        }
        // Attempt to retrieve the pane location for this group.
        let paneLoc = this.groupId2paneLoc.get(widget.groupId);
        const info = widget.getInfoCopy();
        if (paneLoc) {
            // In this case the pane group already has (or had) a pane, so we attempt to use it.
            try {
                this.hub.contentManager.updateContent(info, paneLoc, { selectPane: true });
            } catch (e) {
                // Following MDN's recommendation for conditional catch blocks:
                //   <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/try...catch#Conditional_catch-blocks>
                if (e instanceof UnknownPeerError) {
                    // This case can arise if the controlled pane was in another window, and
                    // that window was closed without closing the pane first, _and_ if the socket
                    // disconnect has not yet been detected and handled. It should be a corner case.
                    paneLoc = null;
                } else {
                    throw e;
                }
            }
        }
        if (!paneLoc) {
            // The pane group does not have a pane. Get one, and associate it with the group.
            const pane = this.hub.contentManager.openContentBeside(info, clickedElt).pane;
            this.setPaneLocForWidgetGroup(pane.id, widget.groupId);
        }
    },

    /* Set the content pane that is to be controlled by a given widget group.
     *
     * @param paneLoc {string} the location of the pane that is to be controlled.
     *   Callers may pass an absolute or relative location, but we will make relative
     *   locations absolute by prepending the present window number.
     * @param groupId {string} the id of a pane group.
     */
    setPaneLocForWidgetGroup: function(paneLoc, groupId) {
        paneLoc = this.hub.windowManager.makeLocationAbsolute(paneLoc);
        this.groupId2paneLoc.set(groupId, paneLoc);
        this.paneLoc2groupId.set(paneLoc, groupId);
    },

    /* Like the `setPaneLocForWidgetGroup` method, except this time it is implied
     * that the NotesManager should decide whether or not to accept the mapping.
     *
     * The intention is that this be used when moving a controlling pane to another
     * window.
     *
     * Our behavior is to reject the suggestion if the group currently has both a
     * controlled pane, and a loaded widget representing it. Otherwise we accept.
     */
    suggestPaneLocForWidgetGroup: function(paneLoc, groupId) {
        if (this.groupHasControlledPane(groupId) && this.groupHasRepresentative(groupId)) {
            console.log(`Reject WGC mapping ${groupId} --> ${paneLoc}`);
        } else {
            this.setPaneLocForWidgetGroup(paneLoc, groupId);
        }
    },

    /* Given a widget group control mapping, consider adopting each entry.
     */
    considerWgcm(wgcm)  {
        for (let groupId of Object.keys(wgcm)) {
            const paneLoc = wgcm[groupId];
            this.suggestPaneLocForWidgetGroup(paneLoc, groupId);
        }
    },

    constructWidget: function(info) {
        return constructWidget(this.hub, info.widget_libpath, info);
    },

    getWidget: function(uid) {
        return this.widgets.get(uid);
    },

    /* Instantiate and activate the Widget instances for an annotation.
     *
     * @param data: This is an object of the form {
     *   libpath: the libpath of the annotation where these widgets are defined
     *   version: the version of the annotation where these widgets are defined
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

        // Purge any widgets that no longer belong to the annotation.
        const annopathv = iseUtil.lv(data.libpath, data.version);
        const uidsUnderAnno = this.getAllOpenWidgetUidsUnderAnnopathv(annopathv);
        for (let uid of uidsUnderAnno) {
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
            widget.makeContextMenu(wdq, pane.id);
            widget.activate(wdq, uid, theNotesManager, pane);
            widget.on('widgetVisualUpdate', this.wvuCallback, {nodup: true});
        }

    },

    observeWidgetVisualUpdate: function(event) {
        const viewer = this.viewers[event.paneId];
        viewer.observeWidgetVisualUpdate(event);
    },

    // FIXME: Refactor. This method is a clone of ChartManager.setAutoRefreshDeduc.
    //  Should be moved to a superclass.
    setSubscription: function(pane, annopath, doSubscribe) {
        const modpath = iseUtil.getModpathFromTopLevelEntityPath(annopath);
        if (doSubscribe) {
            this.annopathsToSubscribedPaneIds.add(annopath, pane.id);
            this.modpathsToAnnopathsHavingSubscribers.add(modpath, annopath);
        } else {
            this.annopathsToSubscribedPaneIds.remove(annopath, pane.id);
            if (!this.annopathsToSubscribedPaneIds.mapping.has(annopath)) {
                this.modpathsToAnnopathsHavingSubscribers.remove(modpath, annopath);
            }
        }
    },

    removeAllSubscriptionsForItem: function(annopath) {
        const modpath = iseUtil.getModpathFromTopLevelEntityPath(annopath);
        this.annopathsToSubscribedPaneIds.mapping.delete(annopath);
        this.modpathsToAnnopathsHavingSubscribers.remove(modpath, annopath);
    },

    // FIXME: Refactor. This method is a clone of ChartManager.handleModuleBuiltEvent.
    //  Should be moved to a superclass.
    handleModuleBuiltEvent: function({ modpath, recursive, timestamp }) {
        const annopaths = recursive ?
            this.modpathsToAnnopathsHavingSubscribers.getUnionOverLibpathPrefix(modpath) :
            this.modpathsToAnnopathsHavingSubscribers.mapping.get(modpath) || [];
        for (let annopath of annopaths) {
            this.hub.xhrFor('loadAnnotation', {
                method: "POST",
                query: { libpath: annopath, cache_code: `${timestamp}`, vers: "WIP" },
                form: {},
                handleAs: 'json',
            }).then(resp => {
                //console.log(resp);
                const paneIds = this.annopathsToSubscribedPaneIds.mapping.get(annopath) || [];
                if (resp.err_lvl === iseErrors.serverSideErrorCodes.MISSING_ANNOTATION) {
                    this.removeAllSubscriptionsForItem(annopath);
                    for (let paneId of paneIds) {
                        const viewer = this.viewers[paneId];
                        // FIXME: Maybe better than closing the whole pane would be to
                        //  first ask the viewer to remove the current page from its history,
                        //  and move to an adjacent history entry, if possible. Only if there
                        //  was no other history entry would we close the pane.
                        viewer.pane.onClose();
                    }
                } else {
                    const data_json = resp.data_json;
                    const contents = {
                        html: resp.html,
                        data: JSON.parse(data_json)
                    };
                    for (let paneId of paneIds) {
                        const viewer = this.viewers[paneId];
                        viewer.receivePublication(contents);
                    }
                }
            });
        }
    },

});

return NotesManager;

});
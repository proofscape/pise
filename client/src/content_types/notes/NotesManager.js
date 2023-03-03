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
    "ise/content_types/AbstractContentManager",
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
    AbstractContentManager,
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
var NotesManager = declare(AbstractContentManager, {

    // Properties
    hub: null,
    // Lookup for PageViewers by pane id:
    viewers: null,
    // Mapping that records which annopathvs are open, and how many copies of each:
    openAnnopathvCopyCount: null,

    // Lookup for widgets by uid.
    widgets: null,

    // At any given time, a widget group may or may not have a controlled pane.
    // When it does, we keep a mapping from group ID to uuid.
    groupId2PaneUuid: null,

    navEnableHandlers: null,

    annopathsToSubscribedPaneIds: null,
    modpathsToAnnopathsHavingSubscribers: null,

    wvuCallback: null,

    // Methods

    constructor: function() {
        this.viewers = {};
        this.openAnnopathvCopyCount = new Map();
        this.widgets = new Map();
        this.groupId2PaneUuid = new Map();
        this.navEnableHandlers = [];
        this.annopathsToSubscribedPaneIds = new iseUtil.LibpathSetMapping();
        this.modpathsToAnnopathsHavingSubscribers = new iseUtil.LibpathSetMapping();
        this.wvuCallback = this.observeWidgetVisualUpdate.bind(this);
    },

    activate: function() {
        this.hub.socketManager.on('moduleBuilt', this.handleModuleBuiltEvent.bind(this));
        this.hub.windowManager.on('paneClose', this.checkForClosingWidgetPane.bind(this));
    },

    getSuppliedDocHighlights: function(paneId) {
        const viewer = this.viewers[paneId];
        const docInfoObj = viewer?.currentPageDocInfo;
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

    handleDocHighlightClick: function(paneId, {supplierUuids, siid, altKey}) {
        const info = {};

        const viewer = this.viewers[paneId];
        const currentInfo = viewer.describeCurrentLocation();
        if (currentInfo) {
            info.libpath = currentInfo.libpath;
            info.version = currentInfo.version;
        }

        // For highlights supplied by a notes page, the siid's are the widget uids
        // of the widgets that supplied them.
        const selector = `.${siid}`;

        info.focus = selector;

        if (altKey) {
            info.scrollSel = selector;
        }

        this.updateContent(info, paneId);
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
        return this.groupId2PaneUuid.has(groupId);
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

    getPaneUuidForGroup: function(groupId) {
        return this.groupId2PaneUuid.get(groupId);
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

    setTheme: function(theme) {
        for (const w of this.widgets.values()) {
            w.setTheme(theme);
        }
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

    /* A "widget group control mapping" (WGCM) is a mapping from widget group IDs
     * to pane uuids for controlled panes. The complete, current mapping
     * is maintained in our `groupId2PaneUuid` Map.
     *
     * This method computes a WGCM based on our current one, and according to certain
     * options.
     *
     * @param options {
     *   annopathv: {string} an optional annotation libpathv. If provided, we restrict
     *     the mapping to those group IDs falling under this annotation and version.
     *   asMap: {bool, default false} if true we return a Map; otherwise just an object in which
     *     the key-value pairs represent the mapping.
     * }
     * @return: the computed mapping.
     */
    getWidgetGroupControlMapping: function(options) {
        const {
            annopathv = null,
            asMap = false,
        } = options || {};
        const widgetUids = annopathv ? this.getAllOpenWidgetUidsUnderAnnopathv(annopathv) : this.widgets.keys();
        const wgcm = new Map();
        for (let widgetUid of widgetUids) {
            const widget = this.widgets.get(widgetUid);
            const groupId = widget.groupId;
            const paneUuid = this.groupId2PaneUuid.get(groupId);
            if (paneUuid) {
                wgcm.set(groupId, paneUuid);
            }
        }
        return asMap ? wgcm : Object.fromEntries(wgcm);
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
        /* Note: we make no effort to clean up the `this.groupId2PaneUuid` mapping
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
     * @param uuid: the uuid of the ContentPane that is closing
     * @param paneId: the Dijit pane id of the ContentPane that is closing
     * @param origin: the window number where the pane was located
     */
    checkForClosingWidgetPane: function(event) {
        const uuid = event.uuid;
        for (let groupId of Object.keys(this.groupId2PaneUuid)) {
            if (this.groupId2PaneUuid[groupId] === uuid) {
                // It was a controlled pane.
                // We clean up our records of that pane, so that a new one can be
                // spawned if any widget in that group is clicked again.
                this.groupId2PaneUuid.delete(groupId);
            }
        }
    },

    // ----------------------------------------------------------------------------------

    /* Handle a widget click.
     *
     * param uid: The unique id of the widget that was clicked.
     * param clickedElt: The DOM element that was clicked.
     */
    click: async function(uid, clickedElt) {
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
        let paneUuid = this.groupId2PaneUuid.get(widget.groupId);
        const info = widget.getInfoCopy();
        if (paneUuid) {
            // In this case the pane group already has (or had) a pane, so we attempt to use it.
            // However, we begin with a check to see if it still exists or not, and self-repair if not.
            // One reason for anticipating such a case is our `purgeWidget()` method, which
            // deliberately does not clean up the `groupId2PaneUuid` mapping.
            // Another reason is just as a safety net, in case our maintenance system, based on
            // things like `beforeunload` handlers, should fail for any reason.
            const stillExists = await this.hub.contentManager.uuidExistsInAnyWindow(paneUuid);
            if (stillExists) {
                this.hub.contentManager.updateContentAnywhereByUuid(info, paneUuid, { selectPane: true });
            } else {
                this.groupId2PaneUuid.delete(widget.groupId);
                paneUuid = null;
            }
        }
        if (!paneUuid) {
            // The pane group does not have a pane. Get one, and associate it with the group.
            const {pane, promise} = this.hub.contentManager.openContentBeside(info, clickedElt);
            promise.then(() => {
                let info = this.hub.contentManager.getContentInfo(pane.id);
                this.setUuidForWidgetGroup(info.uuid, widget.groupId);
            });
        }
    },

    /* Set the content pane that is to be controlled by a given widget group.
     *
     * @param uuid {string} the uuid of the pane that is to be controlled.
     * @param groupId {string} the id of a pane group.
     */
    setUuidForWidgetGroup: function(uuid, groupId) {
        this.groupId2PaneUuid.set(groupId, uuid);
    },

    /* Like the `setUuidForWidgetGroup` method, except this time it is implied
     * that the NotesManager should decide whether or not to accept the mapping.
     *
     * The intention is that this be used when moving a controlling pane to another
     * window.
     *
     * Our behavior is to reject the suggestion if the group currently has both a
     * controlled pane, and a loaded widget representing it. Otherwise we accept.
     */
    suggestUuidForWidgetGroup: function(uuid, groupId) {
        if (this.groupHasControlledPane(groupId) && this.groupHasRepresentative(groupId)) {
            console.debug(`Reject WGC mapping ${groupId} --> ${uuid}`);
        } else {
            this.setUuidForWidgetGroup(uuid, groupId);
        }
    },

    /* Given a widget group control mapping, consider adopting each entry.
     */
    considerWgcm(wgcm)  {
        for (let groupId of Object.keys(wgcm)) {
            const uuid = wgcm[groupId];
            this.suggestUuidForWidgetGroup(uuid, groupId);
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
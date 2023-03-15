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

// Utilities for loading and managing the various content types that go
// in the ContentPanes in the Proofscape ISE app.

import { v4 as uuid4 } from 'uuid';

define([
    "dojo/_base/declare",
    "dojo/query",
    "dojo/dom-style",
    "dojo/dom-construct",
    "dijit/registry",
    "dijit/MenuItem",
    "dijit/PopupMenuItem",
    "dijit/MenuSeparator",
    "dijit/layout/ContentPane",
    "ise/util",
    "dojo/NodeList-dom",
    "dojo/NodeList-manipulate"
], function(
    declare,
    query,
    domStyle,
    domConstruct,
    registry,
    MenuItem,
    PopupMenuItem,
    MenuSeparator,
    ContentPane,
    iseUtil
) {

// ContentManager class
var ContentManager = declare(null, {

    // Properties

    hub: null,
    // content registry types
    crType: {
        CHART:  "CHART",
        NOTES:  "NOTES",
        SOURCE: "SOURCE",
        PDF: "PDF",
        THEORYMAP: "THEORYMAP"
    },
    // Types that have a libpath:
    libpathTypes: null,
    // Types that are editable:
    editableTypes: null,
    // Types for which a study page can be loaded:
    studyPageTypes: null,
    // Content registry will map pane IDs to the info object on which that pane was initialized.
    // Note: We do not maintain a lookup of Dijit panes themselves, because we have a `getPane()`
    // method for that.
    contentRegistry: null,
    // This will be a mapping from content types to methods for setting up content panes
    // to hold content of that type.
    setupMethods: null,
    // We will need a TabContainerTree
    tct: null,
    // Place to store info for pane whose tab's context menu has been opened:
    currentContextMenuInfo: null,

    // We use iseUtil.eventsMixin to make this class listenable.
    listeners: null,

    // Methods

    constructor: function() {

        this.contentRegistry = {};

        // Method Lookup
        // This maps each content type to the method that sets up panes for that type.
        var f = {};
        f[this.crType.NOTES]  = this.setupNotesContentPane.bind(this);
        f[this.crType.CHART]  = this.setupChartContentPane.bind(this);
        f[this.crType.SOURCE] = this.setupEditorContentPane.bind(this);
        f[this.crType.PDF]    = this.setupPdfContentPane.bind(this);
        f[this.crType.THEORYMAP] = this.setupTheorymapContentPane.bind(this);
        this.setupMethods = f;

        // Type category arrays
        this.libpathTypes = [
            this.crType.NOTES, this.crType.SOURCE
        ];
        this.editableTypes = [
            this.crType.NOTES
        ];
        this.studyPageTypes = [
            this.crType.NOTES
        ];

        this.listeners = {};
    },

    activate: function() {
        this.hub.windowManager.on('contentUpdateByUuidBroadcast', this.handleContentUpdateByUuidBroadcast.bind(this));
        this.hub.windowManager.on('docHighlight_click', this.handleDocHighlightClick.bind(this));
        this.hub.windowManager.on('docHighlight_mouseover', this.handleDocHighlightMouseover.bind(this));
        this.hub.windowManager.on('docHighlight_mouseout', this.handleDocHighlightMouseout.bind(this));
    },

    // Locate a ContentPane by its id.
    getPane: function(id) {
        return this.lookUpInDijitRegistry(id);
    },

    // Locate a Tabcontainer by its id.
    getTabContainer: function(id) {
        return this.lookUpInDijitRegistry(id);
    },

    lookUpInDijitRegistry: function(id) {
        return registry.byId(id);
    },

    // Get the ContentPane in which any given DOM element lives.
    getSurroundingPane: function(elt) {
        const paneElt = query(elt).closest('.dijitContentPane')[0];
        return this.getPane(paneElt.id);
    },

    // Get the TabContainer in which any given DOM element lives.
    getSurroundingTabContainer: function(elt) {
        const tcElt = query(elt).closest('.dijitTabContainer')[0];
        return this.getTabContainer(tcElt.id);
    },

    getManager: function(type) {
        switch(type) {
        case this.crType.CHART: return this.hub.chartManager;
        case this.crType.NOTES: return this.hub.notesManager;
        case this.crType.SOURCE: return this.hub.editManager;
        case this.crType.PDF: return this.hub.pdfManager;
        case this.crType.THEORYMAP: return this.hub.theorymapManager;
        }
    },

    setTabContainerTree: function(tct) {
        this.tct = tct;
        tct.registerClosingPaneListener(this);
        tct.registerMenuBuilder(this);
        tct.registerMenuOpenListener(this);
        tct.registerActivePaneListener(this);
    },

    getTabContainerTree: function() {
        return this.tct;
    },

    getContentInfo: function(cpId) {
        return this.contentRegistry[cpId];
    },

    /* Search this window for a pane having a given uuid.
     * Return the Dijit paneId if found, else null.
     */
    getPaneIdByUuid: function(uuid) {
        for (let paneId of Object.keys(this.contentRegistry)) {
            const info = this.contentRegistry[paneId];
            if (info.uuid === uuid) {
                return paneId;
            }
        }
        return null;
    },

    /* Search this window for a pane having a given Dijit paneId.
     * Return the pane's uuid if found, else null.
     */
    getUuidByPaneId: function(paneId) {
        const info = this.contentRegistry[paneId];
        if (info) {
            return info.uuid;
        }
        return null;
    },

    /* Search for a pane having a given uuid, in this window alone.
     * If found, return an object of the form {
     *   windowNumber: int,
     *   paneId: the Dijit pane id used in that window,
     *   activityTimestamp: int giving the time at which this panel was last active,
     *   uuid: just echoing the given uuid,
     * }
     * If not found, return null.
     *
     * Note: This method is synchronous, and searches only the present window.
     * It is designed to be callable by other windows.
     * If working purely locally, consider using `getPaneIdByUuid()` instead.
     */
    getPaneInfoByUuidThisWindow: function({uuid}) {
        const numbers = this.hub.windowManager.getNumbers();
        const myNumber = numbers.myNumber;
        const paneId = this.getPaneIdByUuid(uuid);
        if (paneId !== null) {
            const pane = this.getPane(paneId);
            return {
                windowNumber: myNumber,
                paneId: paneId,
                activityTimestamp: pane._pfsc_ise_selectionTimestamp,
                uuid: uuid,
            };
        }
        return null;
    },

    /* Search for a pane having a given uuid, across all windows.
     *
     * param uuid: The uuid to search for.
     * param options: {
     *   excludeSelf: if false (the default), include our own window in the search;
     *     if true, exclude this window from the search.
     * }
     *
     * return: null or a "pane info" object of the same kind returned by
     *   the `getPaneInfoByUuidThisWindow()` method.
     *
     * Note: This method is asynchronous, and searches all windows.
     */
    getPaneInfoByUuidAllWindows: async function(uuid, options) {
        const {
            excludeSelf = false,
        } = (options || {});
        const searches = this.hub.windowManager.broadcastRequest(
            'hub.contentManager.getPaneInfoByUuidThisWindow',
            {uuid},
            {
                excludeSelf: excludeSelf,
            }
        );
        return Promise.all(searches).then(values => {
            for (let value of values) {
                if (value !== null) {
                    return value;
                }
            }
            return null;
        });
    },

    // Say whether a pane uuid exists, in this or any other window.
    uuidExistsInAnyWindow: async function(uuid, options) {
        const info = await this.getPaneInfoByUuidAllWindows(uuid, options);
        return info !== null;
    },

    // Select the most recently active uuid from an array.
    // return: uuid; else null if empty array was given, or no panel could be found, or no
    //   panel had an activity stamp
    mostRecentlyActive: async function(U) {
        const panelInfos = [];
        for (const u of U) {
            const info = await this.getPaneInfoByUuidAllWindows(u);
            panelInfos.push(info || {uuid: u, activityTimestamp: -1});
        }
        let timeToBeat = -1;
        let mra = null;
        for (const info of panelInfos) {
            const ats = info.activityTimestamp;
            if (ats > timeToBeat) {
                timeToBeat = ats;
                mra = info.uuid;
            }
        }
        return mra;
    },

    // Say whether panel of uuid u was more recently active than panel of uuid v.
    // The panels can belong to any window.
    // If v undefined or null, return true.
    // If we can't locate panel v, return true.
    // Else if we can't locate panel u, return false.
    // Else actually compare their timestamps.
    moreRecentlyActiveThan: async function(u, v) {
        if (!v) {
            return true;
        }
        const vInfo = await this.getPaneInfoByUuidAllWindows(v)
        if (!vInfo) {
            return true;
        }
        const uInfo = await this.getPaneInfoByUuidAllWindows(u)
        if (!uInfo) {
            return false;
        }
        return uInfo.activityTimestamp > vInfo.activityTimestamp;
    },

    /* Given an array of uuids, determine which ones still exist in any window,
     * and which ones do not.
     */
    sortUuidsByExistenceInAnyWindow: async function(uuids) {
        const ex = [];
        const ne = [];
        for (const uuid of uuids) {
            if (await this.uuidExistsInAnyWindow(uuid)) {
                ex.push(uuid);
            } else {
                ne.push(uuid);
            }
        }
        return {
            existing: ex,
            nonExisting: ne,
        };
    },

    /*
     * Make a title for a tab.
     *
     * param info: The info object specifying the content of the pane whose tab this title is for.
     *
     *   Optional fields in this object to control the title are as follows:
     *
     *      tab_title: If given, the value will be used as the title. This can be arbitrary HTML.
     *
     *      icon_type: A type value to be used in selecting the icon.
     *      type: This will be used to select the icon if icon_type is not provided.
     *
     *      title_libpath: A libpath to be used in writing title text.
     *      libpath: This will be used to write title text if title_libpath is not provided.
     */
    makeTabTitle: function(info) {

        // If a title has been provided, use that. This can be arbitrary HTML.
        if (info.tab_title !== undefined) {
            return info.tab_title;
        }

        // Otherwise we construct a title.

        // We aim to provide an icon, based on the content type.
        // For the type, we first chck `icon_type`, then `type`, then give up.
        var icon_part = '';
        var it = info.icon_type || info.type;
        if (it !== undefined) {
            var iconClass = '',
                iconText = '';
            switch(it) {
                case this.crType.CHART: iconClass = 'tabIcon contentIcon deducIcon20'; break;
                case this.crType.NOTES: iconClass = 'tabIcon contentIcon notesIcon20'; break;
                case 'nav': iconClass = 'tabIcon contentIcon navIcon20'; break;
                case this.crType.SOURCE: iconClass = 'tabIcon contentIcon srcIcon20'; break;
                case this.crType.PDF: iconClass = 'tabIcon pdfContentTypeIcon'; break;
                case this.crType.THEORYMAP: iconClass = 'tabIcon contentIcon deducIcon20'; break;
            }
            icon_part = '<span class="'+iconClass+'">'+iconText+'</span>';
        }

        // For the text part, we look for a libpath.
        // We aim to use the libpath minus the initial repo segment,
        // and let the full libpath appear on hover.
        // An exception is that if the libpath names a repo itself, then we do not truncate.
        // Additionally, if the info type is SOURCE while the origType is _not_ MODULE,
        // then we aim to lop off the final libpath segment. The idea here is that whenever
        // editing source code, we want to display the libpath of the module itself, not that
        // of any particular top-level content from which the source may have been opened.
        var text_part = '';
        // We take a `title_libpath` field first, if defined.
        // Else take `libpath` field, if defined.
        // Else give up.

        // FIXME: should refactor in order to use `getContentLibpath` method.
        var lp = info.title_libpath || info.libpath;
        if (lp !== undefined) {
            var parts = lp.split('.'),
                N = parts.length,
                a = (N > 3) ? 3 : 0,
                b = (info.type === "SOURCE" && info.origType !== "MODULE") ? N - 1 : N,
                subpath = parts.slice(a, b).join('.');
            text_part = '<span title="'+lp+'">'+subpath+'</span>';
        }

        // Assemble and return.
        var title = icon_part + text_part;
        return title;
    },

    /* Given an info object that was used to open some content, attempt to build
     * the libpath of the content that was actually opened.
     * If the type was SOURCE but the original type was _*defined* and not equal to MODULE_, then this
     * means source was opened via some top-level item defined in a module, and in
     * such a case we want to chop the final segment off the libpath.
     * In all other cases, we simply want the libpath itself.
     */
    getContentLibpath: function(info) {
        var lp = info.libpath;
        if (!lp) {
            console.log("Info has no libpath:", info);
            return null;
        }
        var parts = lp.split('.'),
            N = parts.length,
            a = 0,
            b = (info.type === "SOURCE" &&
                 info.origType !== undefined &&
                 info.origType !== "MODULE") ? N - 1 : N,
            subpath = parts.slice(a, b).join('.');
        return subpath;
    },

    setupTheorymapContentPane: function(title, cp) {
        // Same as for Chart panes, only here we add the `theorymap` class.
        domStyle.set(cp.domNode, "padding", 0);
        cp.getParent().resize();
        cp.set('content', '<div class="cpSocket mooseGraphArea theorymap"></div>');
        cp.set('title', title);
        var sel = '#' + cp.id + ' .cpSocket';
        return sel;
    },

    setupPdfContentPane: function(title, cp) {
        cp.set('content', '<div class="cpSocket fullheight tex2jax_ignore"></div>');
        cp.set('title', title);
        var sel = '#' + cp.id + ' .cpSocket';
        return sel;
    },

    setupEditorContentPane: function(title, cp) {
        cp.set('content', '<div class="cpSocket edSocket tex2jax_ignore"></div>');
        cp.set('title', title);
        var sel = '#' + cp.id + ' .cpSocket';
        return sel;
    },

    setupNotesContentPane: function(title, cp) {
        cp.set('content', '<div class="cpSocket notesSocket markdown"></div>');
        cp.set('title', title);
        var sel = '#' + cp.id + ' .cpSocket';
        return sel;
    },

    setupChartContentPane: function(title, cp) {
        // For chart panes, we remove the default padding of 8px (all around) that ordinarily
        // comes with ContentPanes. Why? Two reasons:
        // (1) It is arguably visually better this way. Only the top and left padding were visible
        // anyway, due to overflow of the chart's contents. And it looked kind of weird, with the
        // edges of the chart vanishing into a void for no apparent reason.
        // (2) It is a workaround for a very bizarre issue. If you keep the padding, something inexplicable
        // happens the first time you click into the chart area. At that moment, the Forest's div's focus
        // method is called (expected behavior), and then (bizarre behavior) this causes the ContentPane's
        // bounding client rect to jump up 8px. Now only the left padding is visible. And the user sees the
        // chart jump upward. This seems like a browser issue beyond my control (or a DojoToolkit issue?),
        // and the only solution I found was to get rid of the ContentPane's padding altogether.
        // So first eliminate the padding:
        domStyle.set(cp.domNode, "padding", 0);
        // And now we have to ask the parent to resize, because the ContentPane now needs to be bigger,
        // occupying the space its padding used to take up. If we don't do this, we get a band of unused
        // space at the bottom of the pane, 16 pixels high.
        cp.getParent().resize();
        cp.set('content', '<div class="cpSocket mooseGraphArea"></div>');
        cp.set('title', title);
        var sel = '#' + cp.id + ' .cpSocket';
        return sel;
    },

    /* This method will be called before a ContentPane closes.
     */
    noteClosingPane: function(closingPane) {
        this.handleClosingPaneId(closingPane.id);
    },

    handleClosingPaneId: function(paneId) {
        const closingPane = this.getPane(paneId);
        const info = this.contentRegistry[paneId];
        if (info && closingPane) {
            const mgr = this.getManager(info.type);
            if (mgr) {
                mgr.noteClosingContent(closingPane);
            }
        }
        const uuid = info?.uuid;
        const {myNumber} = this.hub.windowManager.getNumbers();

        // We have a mixed (local/synchronous) / (global/asynchronous) event design.
        // Sometimes you want to respond to an event only when it happened in your own
        // window; we call such events "local", and we dispatch them synchronously.
        // Other times, you want to respond to an event no matter in which window
        // it happened; we call such events "global," and they are handled
        // asynchronously (over BroadcastChannel).

        // Local/synchronous event:
        this.dispatch({
            type: 'localPaneClose',
            uuid: uuid,
            paneId: paneId,
        });

        // Global/asynchronous event:
        this.hub.windowManager.groupcastEvent({
            type: 'paneClose',
            uuid: uuid,
            paneId: paneId,
            origin: myNumber,
        }, {
            includeSelf: true,
        });

        // Delete the entry from the content registry.
        delete this.contentRegistry[paneId];
    },

    handleClosingWindow: function() {
        const paneIds = Object.keys(this.contentRegistry);
        for (let paneId of paneIds) {
            this.handleClosingPaneId(paneId);
        }
    },

    buildTabContainerMenu: function(menu) {
        //console.log('ContentManager.buildTabContainerMenu', menu);
        // Prepare place to put a tailselector for the libpath of the content in the clicked pane.
        var tsHome = domConstruct.create("div");
        var tsPopup = new PopupMenuItem({
            label: 'Copy libpath',
            popup: new ContentPane({
                class: 'popupCP',
                content: tsHome
            })
        })
        menu.addChild(tsPopup);
        // Option to open source code
        var mgr = this;
        var editSrcItem = new MenuItem({
            label: 'Source',
            onClick: function(evt){
                mgr.editSourceFromContextMenu();
            }
        });
        menu.addChild(editSrcItem);
        // Option to load a study page
        menu.addChild(new MenuSeparator());
        let studyPageItem = new MenuItem({
            label: 'Open study page',
            onClick: function(evt) {
                const info = mgr.currentContextMenuInfo;
                mgr.openContentInActiveTC({
                    type: "NOTES",
                    libpath: `special.studypage.${info.libpath}.studyPage`,
                    version: info.version,
                });
            }
        });
        menu.addChild(studyPageItem);
        // Final separator
        menu.addChild(new MenuSeparator());
        // Stash objects in the Menu instance.
        // We give them names with "pfsc_ise" prefix in order to keep them in a presumably
        // safe namespace, where they will not collide with anything in Dojo.
        menu.pfsc_ise_tsPopup = tsPopup;
        menu.pfsc_ise_tsHome = tsHome;
        menu.pfsc_ise_editSrcItem = editSrcItem;
        menu.pfsc_ise_studyPageItem = studyPageItem;
    },

    noteTabContainerMenuOpened: function(menu, clicked) {
        //console.log('ContentManager.noteTabContainerMenuOpened', menu, clicked);
        // Grab the info object for the pane whose tab was clicked.
        const button = registry.byNode(clicked.currentTarget),
            pane = button.page,
            info = this.getCurrentStateInfo(pane, true),
            isWIP = info.version === "WIP";
        // Store info object globally.
        // First make a copy and set `useExisting` property.
        const infoCopy = JSON.parse(JSON.stringify(info));
        infoCopy.useExisting = true;
        this.currentContextMenuInfo = infoCopy;
        // Add tail selector for content's libpath, unless it is a type of pane for which
        // the notion really doesn't make sense.
        var enableTailSelector = false;
        if (this.libpathTypes.includes(info.type)) {
            var tsHome = menu.pfsc_ise_tsHome;
            query(tsHome).innerHTML('');
            var lp = this.getContentLibpath(info);
            if (lp) {
                iseUtil.addTailSelector(tsHome, lp.split('.'));
                enableTailSelector = true;
            }
        }
        menu.pfsc_ise_tsPopup.set('disabled', !enableTailSelector);
        // Enable "edit source" item
        menu.pfsc_ise_editSrcItem.set('disabled', !this.editableTypes.includes(info.type));
        menu.pfsc_ise_editSrcItem.set('label', `${isWIP ? "Edit" : "View"} Source`);
        // Enable "Study Page" item
        menu.pfsc_ise_studyPageItem.set('disabled', !this.studyPageTypes.includes(info.type));
    },

    editSourceFromContextMenu: function() {
        var item = this.currentContextMenuInfo,
            source = true;
        this.hub.repoManager.buildMgr.openItem({item, source});
    },

    markInfoForLoadingSource: function(info) {
        // Save the original type under `origType`.
        info.origType = info.type;
        // And set `type` to SOURCE.
        info.type = this.crType.SOURCE;
    },

    /* Among all panes currently hosting certain content (if any), find a
     * most recently active one.
     *
     * @param info: An object describing the content you are looking for.
     *   Whether this can be found for a given content type depends on the
     *   way the `getExistingPaneIds` method for the corresponding type
     *   manager (e.g. EditManager for source code) has been implemented.
     *
     * @return: either a ContentPane, or `null` if it was impossible to find one.
     */
    findMostRecentlyActivePaneHostingContent: function(info) {
        let pane = null;
        const mgr = this.getManager(info.type);
        if (mgr.getExistingPaneIds) {
            const ids = mgr.getExistingPaneIds(info);
            const panes = ids.map(id => this.getPane(id));
            pane = this.hub.tabContainerTree.findMostRecentlyActivePane(panes);
        }
        return pane;
    },

    /*
     * This method is typically used internally only. There is no reason clients cannot
     * use it directly, but they usually will use the `openContentInActiveTC` or
     * `openContentInTC` methods defined below, instead.
     *
     * In order to use this method directly, the client must already have a ContentPane
     * in hand. Usually clients will prefer to let this class handle pane procurement for them.
     *
     * return: promise that resolves when the content has been loaded.
     */
    openContentInPane: async function(info, pane) {
        await this.hub.contentLoadingOkay();
        // Every content pane must have a uuid. This goes above and beyond Dijit's
        // pane ids, because it's unique across windows, and across reloads.
        // If you already supplied a uuid, we assume you have good reason,
        // and we leave it alone. (For example, this happens when content is being
        // *moved* from one window to another.) Otherwise we supply one.
        if (info.uuid === undefined) {
            info.uuid = uuid4();
        }
        // Grab the specified info type.
        var type = info.type;
        // Get the pane setup method.
        var setupMethod = this.setupMethods[type];
        // Did we get a known type?
        if (setupMethod === undefined) {
            console.log("ERROR: Unknown content type: " + type);
            return;
        }
        // Make a tab title.
        var title = this.makeTabTitle(info);
        // Set up the pane.
        var sel = setupMethod(title, pane);
        // Grab the DOM element to which content is to be added.
        var elt = query(sel)[0];
        // Locate the appropriate manager.
        var mgr = this.getManager(type);
        // Ask the manager to initialize the content.
        const p = mgr.initContent(info, elt, pane);
        // Record the info object in our content registry.
        this.contentRegistry[pane.id] = info;
        // Announce the active pane after the content has finished loading.
        p.then(() => {
            this.tct.announceActivePane();
        });
        // Need to resize the tab container in order to recover the
        // line at the top that separates the tabs from the content.
        // Possibly related issue: https://bugs.dojotoolkit.org/ticket/9849
        this.tct.activeTC.resize();
        return p;
    },

    /*
     * Pass an existing content pane. We return an info object describing
     * the current, up-to-the-moment state of the content in that pane.
     * We also copy the title from that pane.
     *
     * param existingPane: the pane whose state info is to be obtained
     * param serialOnly: boolean; set true if you want only serializable info
     */
    getCurrentStateInfo: function(existingPane, serialOnly) {
        const origInfo = this.contentRegistry[existingPane.id];
        const mgr  = this.getManager(origInfo.type);
        const currentInfo = mgr.writeStateInfo(existingPane.id, serialOnly);
        // Copy the title.
        currentInfo.tab_title = existingPane.title;
        // Ensure that the original uuid is reproduced.
        currentInfo.uuid = origInfo.uuid;
        return currentInfo;
    },

    /*
     * This method serves as middle man to forward a navigation request to
     * the appropriate content type manager, for a given pane, and return the result.
     *
     * param pane: the pane in which navigation is desired
     * param direction: integer indicating the desired navigation direction:
     *   positive for forward, negative for backward, 0 for no navigation. Passing 0 serves
     *   as a way to simply check the desired enabled state for back/fwd buttons.
     * return: Promise that resolves with a pair of booleans indicating whether back resp.
     *   fwd buttons should be enabled for this pane _after_ the requested navigation takes place.
     */
    navigate: function(pane, direction) {
        let info = this.contentRegistry[pane.id];
        if (info) {
            let mgr  = this.getManager(info.type);
            return mgr.navigate(pane, direction);
        }
        return Promise.resolve([false, false]);
    },

    /*
     *  This is used by the TabContainerTree to handle splits.
     *
     *  param oldCP: The ContentPane being split.
     *  param newCP: A new ContentPane, which is to be initialized with a copy of the
     *               current contents of the old pane.
     *
     * return: the info object describing the content in the new pane
     */
    openCopy: function(oldCP, newCP) {
        const newInfo = this.getCurrentStateInfo(oldCP);
        // The new content description is the same as the old in all respects,
        // *except* that it gets its own, distinct uuid.
        newInfo.uuid = uuid4();
        const mgr = this.getManager(newInfo.type);
        this.openContentInPane(newInfo, newCP).then(() => {
            // Let the manager know that the new pane is a copy of the old one.
            mgr.noteCopy(oldCP.id, newCP.id);
        });
        return newInfo;
    },

    /* Open content in a certain TabContainer.
     *
     * param info: An object specifying the content to be opened.
     *             Must include at least a `type` field.
     * param tcId: The id of the TabContainer in which the content is to be opened.
     *
     * return: object of the form {
     *     pane: the new content pane,
     *     promise: Promise that resolves when the content has been loaded
     * }
     */
    openContentInTC: function(info, tcId) {
        const newCP = this.tct.addContentPaneToTC(tcId);
        const pr = this.openContentInPane(info, newCP);
        return {
            pane: newCP,
            promise: pr,
        };
    },

    /* Open content in a tab container beside a given one, making a new tab container
     * if necessary.
     *
     * @param info: An object specifying the content to be opened.
     *   Must include at least a `type` field.
     * @param elt: _Any_ DOM element inside an existing tab container.
     *   The content will be opened in another tab container, beside this one.
     * @param dim: Optional string indicating the desired dimension for a split, if
     *   necessary. (Must equal 'v' or 'h'; defaults to 'v'.)
     * @return: object of the form {
     *     pane: the new content pane,
     *     promise: Promise that resolves when the content has been loaded
     * }
     */
    openContentBeside: function(info, elt, dim = 'v') {
        const tc = this.getSurroundingTabContainer(elt);
        let nextId = this.tct.getNextTcId(tc.id, true);
        if (nextId === null) {
            nextId = this.tct.splitTC(tc.id, dim);
        }
        return this.openContentInTC(info, nextId);
    },

    /* Open content in whichever TabContainer is currently the active one.
     * A TabContainer can become active in various ways, for example, whenever the user
     * clicks on any pane therein, or selects a tab therein.
     *
     * Alternatively, by giving the passed info object a truthy `useExisting` property,
     * clients can request that the content be opened in a (most recently active) existing
     * pane that already hosts the content in question. It is up to the specific manager
     * type to determine whether there exists such a pane.
     *
     * param info: An object specifying the content to be opened.
     *             Must include at least a `type` field.
     *
     * return: the id of the content pane where the content was loaded
     */
    openContentInActiveTC: async function(info) {
        let paneId = null;
        // If requested to use existing pane, and if there is a (most recent)
        // existing pane, then use that.
        const mgr = this.getManager(info.type);
        if (info.useExisting && mgr.getExistingPaneIds) {
            const pane = this.findMostRecentlyActivePaneHostingContent(info);
            if (pane) {
                const makeActive = true;
                this.hub.tabContainerTree.selectPane(pane, makeActive);
                mgr.updateContent(info, pane.id);
                paneId = pane.id;
            }
        }
        // If didn't already find a pane, make a new one.
        if (!paneId) {
            const newCP = this.tct.addContentPaneToActiveTC();
            await this.openContentInPane(info, newCP);
            paneId = newCP.id;
        }
        return paneId;
    },

    /*
     * Update the content in any pane, in any window.
     *
     * param info: Object of the kind returned by a manager's `writeStateInfo` method.
     *             Must contain `type` field.
     * param uuid: The uuid of the ContentPane whose content is to be updated.
     * param options: {
     *   selectPane {bool}: set true if you want the updated pane to also become the
     *       selected pane in its tab container.
     * }
     * return: nothing
     */
    updateContentAnywhereByUuid: function(info, uuid, options) {
        const event = {
            type: 'contentUpdateByUuidBroadcast',
            info: info,
            uuid: uuid,
            options: options,
        };
        this.hub.windowManager.groupcastEvent(event, {
            includeSelf: true,
        });
    },

    /* Update a list of existing panels, or spawn a new one beside an existing one, and
     * set its contents.
     *
     * param info: content descriptor object that can be used to update existing panels,
     *  or to initialize a new one
     * param uuids: array of uuids of panels to be updated. If this is empty, or it turns
     *  out none of these exists (in any window), then we spawn a new panel instead.
     * param elt: some DOM element from inside the panel we want to spawn beside, if we
     *  do spawn.
     *
     * return: Object {
     *  existing: array of those given uuids that were confirmed to exist,
     *  nonExisting: array of those given uuids that turned out not to exist,
     *  spawned: uuid of newly spawned panel if that happened, else null
     * }
     */
    updateOrSpawnBeside: async function(info, uuids, elt) {
        let spawned = null;

        const {existing, nonExisting} = await this.sortUuidsByExistenceInAnyWindow(uuids);

        if (existing.length > 0) {
            // Update existing panels.
            for (const uuid of existing) {
                this.updateContentAnywhereByUuid(info, uuid, {selectPane: true});
            }
        } else {
            // Spawn new panel.
            const {pane, promise} = this.openContentBeside(info, elt);
            await promise;
            spawned = this.getUuidByPaneId(pane.id);
        }
        return {existing, nonExisting, spawned};
    },

    /* Handle a 'contentUpdateByUuidBroadcast' event.
     * The format of the event is: {
     *   type: 'contentUpdateByUuidBroadcast',
     *   info: as passed to ContentManager.updateContentAnywhereByUuid(),
     *   uuid: as passed to ContentManager.updateContentAnywhereByUuid(),
     *   options: as passed to ContentManager.updateContentAnywhereByUuid(),
     * }
     * If we have a pane with the given uuid, we ask it to update its
     * content. If not, we simply do nothing.
     */
    handleContentUpdateByUuidBroadcast: function(event) {
        const paneId = this.getPaneIdByUuid(event.uuid);
        if (paneId !== null) {
            const {
                selectPane = false,
            } = event.options || {};
            if (selectPane) {
                const pane = this.getPane(paneId);
                this.tct.selectPane(pane);
            }
            const info = event.info;
            const mgr = this.getManager(info.type);
            mgr.updateContent(info, paneId);
        }
    },

    // Handle the click of a named highlight, in a doc panel's highlight layer.
    handleDocHighlightClick: function(event) {
        for (let supplierUuid of event.supplierUuids) {
            const paneId = this.getPaneIdByUuid(supplierUuid);
            if (paneId) {
                // If we got a paneId, then the panel belongs to this window.
                const info = this.contentRegistry[paneId];
                const mgr = this.getManager(info.type);
                mgr.handleDocHighlightClick(paneId, event);
            }
        }
    },

    // Handle the mouseover of a named highlight, in a doc panel's highlight layer.
    handleDocHighlightMouseover: function(event) {
        for (let supplierUuid of event.supplierUuids) {
            const paneId = this.getPaneIdByUuid(supplierUuid);
            if (paneId) {
                // If we got a paneId, then the panel belongs to this window.
                const pane = this.getPane(paneId);
                const button = this.tct.getTabButtonForPane(pane);
                const buttonNode = button.domNode;
                buttonNode.classList.add('pisePreNavGlow');
            }
        }
    },

    // Handle the mouseout of a named highlight, in a doc panel's highlight layer.
    handleDocHighlightMouseout: function(event) {
        for (let supplierUuid of event.supplierUuids) {
            const paneId = this.getPaneIdByUuid(supplierUuid);
            if (paneId) {
                // If we got a paneId, then the panel belongs to this window.
                const pane = this.getPane(paneId);
                const button = this.tct.getTabButtonForPane(pane);
                const buttonNode = button.domNode;
                buttonNode.classList.remove('pisePreNavGlow');
            }
        }
    },

    /* When there's a new active pane, we check to see if its content
     * defines any doc highlights. If so, we groupcast an event containing
     * the list of docIds for which highlights are available, and the uuid
     * of the newly active panel. This allows documents open in any
     * window to (potentially) follow up and request full highlight info.
     */
    noteActivePane: function(pane) {
        const info = this.contentRegistry[pane.id];
        // Our event structure is not perfect; it seems the active pane event
        // will sometimes be triggered twice: once on a new pane's `show`
        // event, and then again when we invoke `this.tct.announceActivePane()`
        // in our `openContentInPane()` method, after actually loading the content.
        // We have to wait until that second event, for the info to actually be
        // available in our contentRegistry. Could some day try to perfect all this,
        // but for now we just check to see if we got an info.
        if (info) {
            const mgr = this.getManager(info.type);
            const docInfo = mgr.getSuppliedDocHighlights(pane.id);
            // Make sure we grab only those docIds for which there actually are (one or more) highlights.
            const docIds = Array.from(docInfo.refs.keys()).filter(
                docId => docInfo.refs.get(docId).length > 0
            );
            if (docIds.length) {
                this.hub.windowManager.groupcastEvent({
                    type: 'newlyActiveHighlightSupplierPanel',
                    uuid: info.uuid,
                    docIds: docIds,
                }, {
                    includeSelf: true,
                });
            }
        }
    },

    /* Search for a pane of a given `uuid`. If found in this window,
     * then return the array of doc highlights defined by the content in
     * that pane, for the documents of those ids named in the `docIds`
     * array. Otherwise return `null`.
     */
    getHighlightsFromSupplier: function({supplierUuid, docIds}) {
        const paneId = this.getPaneIdByUuid(supplierUuid);
        if (paneId !== null) {
            const info = this.contentRegistry[paneId];
            const mgr = this.getManager(info.type);
            const docInfo = mgr.getSuppliedDocHighlights(paneId);
            const hls = {};
            for (const [key, value] of docInfo.refs) {
                if (docIds.includes(key)) {
                    hls[key] = value;
                }
            }
            return hls;
        }
        return null;
    },

    /* Move a content pane to another window.
     *
     * return: Promise that resolves when the entire operation is complete, including all
     *   necessary update of relevant data structures. The resolved value is the state
     *   descriptor object that was used to open the new copy in the other window.
     */
    movePaneToAnotherWindow: async function(pane, newWindowNumber) {
        const stateDescriptor = this.getCurrentStateInfo(pane, true);
        await this.hub.windowManager.makeWindowRequest(
            newWindowNumber, 'hub.contentManager.openContentInActiveTC', stateDescriptor
        );

        await this.dispatch({
            type: 'paneMovedToAnotherWindow',
            uuid: stateDescriptor.uuid,
            newWindow: newWindowNumber,
        });

        pane.onClose();

        return stateDescriptor;
    },

});

Object.assign(ContentManager.prototype, iseUtil.eventsMixin);

return ContentManager;
});

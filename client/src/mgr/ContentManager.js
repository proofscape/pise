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
    typeColors: {
        PDF: "red",
        CHART: "green",
        NOTES: "blue",
        TREE: "cyan",
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
        this.hub.windowManager.on('intentionToNavigate', this.handleIntentionToNavigate.bind(this));
        this.hub.windowManager.on('tempTabOverlays', this.handleTempTabOverlays.bind(this));
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
            const cdo = this.contentRegistry[paneId];
            return {
                windowNumber: myNumber,
                paneId: paneId,
                activityTimestamp: pane._pfsc_ise_selectionTimestamp,
                uuid: uuid,
                type: cdo.type,
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
    // param U: array of uuids
    // return: promise resolving with uuid, or with null if empty array was given, or no panel
    //   could be found, or no panel had an activity stamp
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
    //
    // param u: uuid or falsey
    // param v: uuid or falsey
    // return: promise resolving with boolean
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

    /* Given the pane id of a local pane, determine its content type.
     */
    getContentTypeOfLocalPane: function(paneId) {
        const info = this.contentRegistry[paneId];
        if (!info) {
            return;
        }
        return info.type;
    },

    getLinkingMapForContentType: function(contentType) {
        const mgr = this.getManager(contentType);
        return mgr?.linkingMap;
    },

    /* Given the pane id of a pane that lives in this window, synchronously get
     * array of all triples [u, x, w] where u represents this pane.
     */
    getOutgoingLinkTriplesForLocalPane: function(paneId) {
        const contentType = this.getContentTypeOfLocalPane(paneId);
        const linkingMap = this.getLinkingMapForContentType(contentType);
        if (!linkingMap) {
            return;
        }
        const uuid = this.getUuidByPaneId(paneId);
        return linkingMap.localComponent.getTriples({u: uuid});
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
        cp.set('content', '<div class="cpSocket pdfSocket fullheight tex2jax_ignore"></div>');
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

        // Option to edit links
        const linksItem = new MenuItem({
            label: 'Links...',
        });
        menu.addChild(linksItem);

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
        menu.pfsc_ise_linksItem = linksItem;
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
        menu.pfsc_ise_editSrcItem.set('disabled', !this.editableTypes.includes(info.type));
        menu.pfsc_ise_editSrcItem.set('label', `${isWIP ? "Edit" : "View"} Source`);
        menu.pfsc_ise_studyPageItem.set('disabled', !this.studyPageTypes.includes(info.type));
        menu.pfsc_ise_linksItem.set('disabled', this.getOutgoingLinkTriplesForLocalPane(pane.id).length === 0);
        menu.pfsc_ise_linksItem.set('onClick', event => {
            this.showLinkingDialog(pane.id);
        });
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
     * @param nbr: A specification of the "neighbor" tab container, beside which the
     *   content is to be loaded. Either a string, which must be the uuid of a panel
     *   living in the neighbor TC; or else any DOM element inside the neighbor TC.
     * @param dim: Optional string indicating the desired dimension for a split, if
     *   necessary. (Must equal 'v' or 'h'; defaults to 'v'.)
     * @return: object of the form {
     *     pane: the new content pane,
     *     promise: Promise that resolves when the content has been loaded
     * }
     */
    openContentBeside: function(info, nbr, dim = 'v') {
        if (typeof(nbr) === "string") {
            const paneId = this.getPaneIdByUuid(nbr);
            const pane = this.getPane(paneId);
            nbr = pane.domNode;
        }
        const tc = this.getSurroundingTabContainer(nbr);
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

    /* Update a list of existing panels (in any windows), or spawn a new one beside an
     * existing one, and set its contents.
     *
     * param info: content descriptor object that can be used to update existing panels,
     *  or to initialize a new one
     * param uuids: array of uuids of panels to be updated. If this is empty, or it turns
     *  out none of these exists (in any window), then we spawn a new panel instead.
     * param sourceLoc: A specification of the "source location", so that we can decide
     *  what "beside" means, in case a new panel is to be spawned. Either a string, which
     *  must be the uuid of an existing panel, or else any DOM element belonging to an
     *  existing tab container.
     *
     * return: Object {
     *  existing: array of those given uuids that were confirmed to exist,
     *  nonExisting: array of those given uuids that turned out not to exist,
     *  spawned: uuid of newly spawned panel if that happened, else null
     * }
     */
    updateOrSpawnBeside: async function(info, uuids, sourceLoc) {
        let spawned = null;

        const {existing, nonExisting} = await this.sortUuidsByExistenceInAnyWindow(uuids);

        if (existing.length > 0) {
            // Update existing panels.
            for (const uuid of existing) {
                this.updateContentAnywhereByUuid(info, uuid, {selectPane: true});
            }
        } else {
            // Spawn new panel.
            const {pane, promise} = this.openContentBeside(info, sourceLoc);
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

    /* Handle groupcast event {
     *     type: 'intentionToNavigate',
     *     action: 'show' or 'hide',
     *     source: uuid of panel having a nav intention
     *     panels: optional array of panel uuids where nav might happen,
     *     tree: optional libpath of item where nav might happen,
     *     iid: optional "internal id" (describing intended object *within* panel/treeitem)
     * }
     */
    handleIntentionToNavigate: function(event) {
        // tree: not yet supported
        // iid: not yet supported
        const panels = event.panels || [];
        for (const uuid of panels) {
            const paneId = this.getPaneIdByUuid(uuid);
            if (paneId) {
                // If we got a paneId, then the panel belongs to this window.
                const pane = this.getPane(paneId);
                const button = this.tct.getTabButtonForPane(pane);
                const buttonNode = button.domNode;
                const glowClass = 'pisePreNavGlow';
                if (event.action === 'show') {
                    buttonNode.classList.add(glowClass);
                } else if (event.action === 'hide') {
                    buttonNode.classList.remove(glowClass);
                }
            }
        }
    },

    /* Handle groupcast event {
     *     type: 'tempTabOverlays',
     *     action: 'set' or 'clear',
     *     tabs: for action 'set', an object of the form {
     *       uuid: {color: 'red', 'green', or 'blue', label: string}, ...
     *     }
     * }
     */
    handleTempTabOverlays: function(event) {
        if (event.action === 'clear') {
            document.querySelectorAll('.tmpTabOverlay').forEach(e => e.remove());
        } else if (event.action === 'set') {
            for (const [uuid, settings] of Object.entries(event.tabs)) {
                const paneId = this.getPaneIdByUuid(uuid);
                if (paneId) {
                    // If we got a paneId, then the panel belongs to this window.
                    const pane = this.getPane(paneId);
                    const button = this.tct.getTabButtonForPane(pane);
                    const buttonNode = button.domNode;
                    const overlay = document.createElement('div');
                    overlay.classList.add('tmpTabOverlay', 'areaFillOverlay', 'tmpTabStyle');
                    overlay.classList.add(`tmpTabStyle-${settings.color}`);
                    const text = document.createTextNode(settings.label);
                    overlay.appendChild(text);
                    buttonNode.appendChild(overlay);
                }
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

    /* Find references in a given local panel P to a given local doc panel D.
     *
     * NOTE: Both panels must be local, i.e. belong to this window.
     *
     * param uuid: the uuid of panel P
     * param type: the content type of panel P
     * param dUuid: the uuid of doc panel D
     *
     * return: Object of the form {
     *   docId: the id of the doc in panel D,
     *   refsFrom: array (possibly empty) of libpaths of entities in panel P that reference docId
     * }
     */
    panelReferencesDocPanel: function(uuid, type, dUuid) {
        const d0 = this.hub.pdfManager.getDocIdByUuid(dUuid);
        const refsFrom = new Set();
        let tuples = [];
        if (type === this.crType.CHART) {
            tuples = this.hub.chartManager.getAllDocRefTriplesLocal({});
        } else if (type === this.crType.NOTES) {
            tuples = this.hub.notesManager.getAllDocRefQuadsLocal({});
        }
        for (const t of tuples) {
            if (t.at(-1) === d0 && t[0] === uuid) {
                refsFrom.add(t[1]);
            }
        }
        return {
            docId: d0,
            refsFrom: Array.from(refsFrom),
        };
    },

    /* Show the linking dialog for a content pane.
     *
     * param sourceId: the dijit pane id of the content pane that is the
     *      source endpoint of the links to be reviewed.
     * param options: {
     *  targetId: the dijit pane id of a content pane being proposed as a
     *      new target for linking.
     *  targetTreeItem: object of the form {libpath, version} indicating a
     *      tree item to be linked. (Only valid when source panel is a doc panel.)
     * }
     * param
     */
    showLinkingDialog: async function(sourceId, options) {
        const {
            targetId = null,
            targetTreeItem = null,
        } = (options || {});

        if (targetId === sourceId) {
            // Can't link to self
            return;
        }

        const sUuid = this.getUuidByPaneId(sourceId);
        const tUuid = targetId ? this.getUuidByPaneId(targetId) : null;

        const sourceType = this.getContentTypeOfLocalPane(sourceId);

        let proposedTargetInfo;
        let targetType;
        let secondaryIds;
        // If there's a proposed link, then we need to determine whether such a link
        // can be made or not. If not, reject, possibly with a helpful message.
        // If so, determine the array of secondary IDs for link(s) to be formed.
        if (tUuid) {
            proposedTargetInfo = await this.getPaneInfoByUuidAllWindows(tUuid);
            targetType = proposedTargetInfo.type;
            // If the types are unlinkable, just silently do nothing.

            // Can't link two panels of the same type.
            if (sourceType === targetType) {
                return;
            }

            // Links C --> X
            if (sourceType === this.crType.CHART) {
                // Can't link CHART --> NOTES.
                if (targetType === this.crType.NOTES) {
                    return;
                }

                // CHART --> DOC: We require that the doc be currently referenced by the set
                // of deducs open in the chart panel.
                if (targetType === this.crType.PDF) {
                    const {refsFrom, docId} = this.panelReferencesDocPanel(sUuid, sourceType, tUuid);
                    if (refsFrom.length === 0) {
                        this.hub.alert({
                            title: "Linking",
                            content: "Cannot link, since panel does not reference document.",
                        });
                        return;
                    }
                    secondaryIds = [docId];
                }
            }

            // Links N --> X are tricky, if there are multiple widget groups.
            // Theoretically we could require the user to drag and drop onto a specific widget,
            // but for now we're going to put that off. For now, the rule will be that we'll form
            // a new link iff there is *exactly one* widget group relevant to the target content.
            if (sourceType === this.crType.NOTES) {
                const nm = this.hub.notesManager;
                const quads = nm.getAllDocRefQuadsLocal({});
                let test = (g, d) => false;
                if (targetType === this.crType.CHART) {
                    test = (g, d) => nm.extractWidgetTypeFromGroupId(g) === this.crType.CHART;
                } else if (targetType === this.crType.PDF) {
                    const d0 = this.hub.pdfManager.getDocIdByUuid(tUuid);
                    test = (g, d) => d === d0;
                }
                const G = new Set(quads.filter(([u, s, g, d]) => u === sUuid && test(g, d)).map(q => q[2]));
                const n = G.size;
                if (n === 1) {
                    secondaryIds = Array.from(G);
                } else {
                    const issue = n > 1 ? "multiple related widget groups" : "no related widgets";
                    this.hub.alert({
                        title: "Linking",
                        content: `Cannot link, since page contains ${issue}.`,
                    });
                    return;
                }
            }

            // For links D --> X, we require that panel X make references to the document.
            if (sourceType === this.crType.PDF) {
                const {refsFrom, docId} = this.panelReferencesDocPanel(tUuid, targetType, sUuid);
                if (refsFrom.length === 0) {
                    this.hub.alert({
                        title: "Linking",
                        content: "Cannot link, since panel does not reference document.",
                    });
                    return;
                }
                secondaryIds = refsFrom;
            }
        } else if (targetTreeItem) {
            // User wants to link a tree item.
            // This is only meaningful if the source panel is a doc panel.
            if (sourceType !== this.crType.PDF) {
                return;
            }
        }

        const existingLinks = this.getOutgoingLinkTriplesForLocalPane(sourceId);
        const existingTargetInfos = new Map();
        for (const [u, x, w] of existingLinks) {
            if (w === tUuid) {
                // Already linked
                this.hub.alert({
                    title: "Linking",
                    content: "Already linked!",
                });
                return;
            }
            const info = await this.getPaneInfoByUuidAllWindows(w);
            existingTargetInfos.set(w, info);
        }
        const n = existingLinks.length;

        let existingTreeItem;
        let sourcePdfc;
        if (sourceType === this.crType.PDF) {
            sourcePdfc = this.hub.pdfManager.getPdfcByUuid(sUuid);
            if (sourcePdfc.linkedTreeItemLibpath) {
                existingTreeItem = {
                    libpath: sourcePdfc.linkedTreeItemLibpath,
                    version: sourcePdfc.linkedTreeItemVersion,
                };
            }
        }

        // The type of dialog we show depends on:
        //  n: the number of existing links outgoing from sUuid, and
        //  tUuid: i.e. whether or not a new target has been proposed

        const sourceColor = this.typeColors[sourceType];
        const sourceLabel = "A";

        function buildLinkRow(targetColor, targetLabel, options) {
            const {
                includeCheckbox = false,
            } = (options || {});
            const cbId = `linkingDialog-${targetLabel}`;
            let cb = '';
            if (includeCheckbox) {
                cb = `<input type="checkbox" id="${cbId}" name="${targetLabel}" checked>`;
            }
            const targetExtraClass = targetLabel.includes('.') ? 'libpathLink' : '';
            return `
                <div class="navLinkRow">
                ${cb}
                <label class="${includeCheckbox ? 'clickableLabel' : ''}" for="${cbId}">
                <span class="navLinkLabel tmpTabStyle tmpTabStyle-${sourceColor}">${sourceLabel}</span>
                <span class="navLinkArrow">&#10230;</span>
                <span class="navLinkLabel tmpTabStyle tmpTabStyle-${targetColor} ${targetExtraClass}">${targetLabel}</span>
                </label>
                </div>
            `;
        }

        function buildLinkTable(linkRows) {
            let tab = '<div class="navLinkTable">\n';
            for (const row of linkRows) {
                tab += row;
            }
            tab += '</div>\n';
            return tab;
        }

        function writeTreeItemLabel({libpath, version}) {
            let label = libpath;
            if (version !== "WIP") {
                label += "@" + version;
            }
            return label;
        }

        let proposedLinkTab;
        let targetColor;
        let targetLabel;
        if (tUuid) {
            targetColor = this.typeColors[targetType];
            targetLabel = "B";
        } else if (targetTreeItem) {
            targetColor = this.typeColors.TREE;
            targetLabel = writeTreeItemLabel(targetTreeItem);
        }
        if (targetLabel) {
            proposedLinkTab = buildLinkTable(
                [buildLinkRow(targetColor, targetLabel, {includeCheckbox: n > 0})]
            );
        }

        let existingLinkTab;
        if (n > 0) {
            // Source tab always gets label "A". If target given, it gets "B", while
            // existing targets start at "C"; else the latter start at "B".
            let q = 0;
            let r = tUuid ? 2 : 1;
            const elRows = [];

            if (existingTreeItem) {
                const label = writeTreeItemLabel(existingTreeItem);
                const color = this.typeColors.TREE;
                elRows.push(buildLinkRow(color, label, {includeCheckbox: true}));
            }

            for (const info of existingTargetInfos.values()) {
                const label = `${String.fromCharCode(65 + r)}${q > 0 ? q : ''}`;
                const color = this.typeColors[info.type];
                info.label = label;
                info.color = color;
                elRows.push(buildLinkRow(color, label, {includeCheckbox: true}));
                if (++r === 27) {
                    q++;
                    r = 0;
                }
            }

            existingLinkTab = buildLinkTable(elRows);
        }

        const thereAreLinks = proposedLinkTab || existingLinkTab;
        const labelsToUuids = new Map();

        if (thereAreLinks) {
            // Paint colored labels on tabs, so user knows what we're talking about!
            const tabsToLabel = {
                [sUuid]: {color: sourceColor, label: sourceLabel},
            };
            if (tUuid) {
                tabsToLabel[tUuid] = {color: targetColor, label: targetLabel};
                labelsToUuids.set(targetLabel, tUuid);
            }
            for (const info of existingTargetInfos.values()) {
                tabsToLabel[info.uuid] = {color: info.color, label: info.label};
                labelsToUuids.set(info.label, info.uuid);
            }
            this.hub.windowManager.groupcastEvent({
                type: 'tempTabOverlays',
                action: 'set',
                tabs: tabsToLabel,
            }, {
                includeSelf: true,
            });
        }

        const title = "Linking";
        const okButtonText = existingLinkTab ? "Keep Selected" : "OK";
        let dismissCode = null;
        let content = '';
        if (proposedLinkTab) {
            content += `
            <h2>New Link:</h2>
            ${proposedLinkTab}
            `;
        }
        if (existingLinkTab) {
            content += `
            <h2>Existing Links:</h2>
            ${existingLinkTab}
            `;
        }
        if (proposedLinkTab && !existingLinkTab) {
            dismissCode = 'makeSoleLink';
        }
        if (!content) {
            content = 'No existing links!';
        }
        content = `
        <div class="iseDialogContentsStyle02 iseDialogContentsStyle03m">
        ${content}
        </div>
        `;

        const result = await this.hub.choice({
            title, content, okButtonText, dismissCode
        });

        this.hub.windowManager.groupcastEvent({
            type: 'tempTabOverlays',
            action: 'clear',
        }, {
            includeSelf: true,
        });

        const accepted = result.accepted;
        const decisionsByLabel = new Map();
        result.dialog.domNode.querySelectorAll('input[type=checkbox]').forEach(cb => {
            const name = cb.getAttribute('name');
            const checked = cb.checked;
            decisionsByLabel.set(name, checked);
        });
        // Important to destroy the dialog now, so we can reuse checkbox id's next time.
        result.dialog.destroy();

        if (thereAreLinks && accepted) {
            const linkingMap = this.getLinkingMapForContentType(sourceType);

            if (existingLinkTab) {
                // Any existing links to be removed?
                for (const [label, checked] of decisionsByLabel.entries()) {
                    if (label === targetLabel) {
                        continue;
                    }
                    if (!checked) {
                        const w0 = labelsToUuids.get(label);
                        if (w0) {
                            // Remove links (sUuid x _) |--> w0
                            await linkingMap.removeTriples({u: sUuid, w: w0}, {doNotRelink: true});
                        } else {
                            // Remove existing tree item.
                            sourcePdfc.removeLinkedTreeItem();
                        }
                    }
                }
            }

            if (proposedLinkTab && (decisionsByLabel.get(targetLabel) || !existingLinkTab)) {
                if (targetTreeItem) {
                    // Establish a tree item link
                    sourcePdfc.linkTreeItem(targetTreeItem);
                } else {
                    // Form a new link for each secondaryId determined above.
                    for (const x of secondaryIds) {
                        await linkingMap.add(sUuid, x, tUuid);
                    }
                }
            }
        }
    }

});

Object.assign(ContentManager.prototype, iseUtil.eventsMixin);

return ContentManager;
});

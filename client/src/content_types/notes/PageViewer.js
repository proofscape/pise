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
    "dojo/_base/declare",
    "dojo/query",
    "dojo/on",
    "dojo/dom-construct",
    "dijit/Menu",
    "dijit/MenuItem",
    "dijit/PopupMenuItem",
    "ise/util",
    "dojo/NodeList-dom",
    "dojo/NodeList-manipulate",
    "dojo/NodeList-traverse",
], function(
    declare,
    query,
    dojoOn,
    domConstruct,
    Menu,
    MenuItem,
    PopupMenuItem,
    iseUtil
) {

// PageViewer class
var PageViewer = declare(null, {

    // Properties

    // nm: the NotesManager
    nm: null,
    // elt: the DOM element where we display our content
    elt: null,
    // mainview: the DOM element where the content lives
    mainview: null,
    // sidebar: the DOM element where the sidebar lives
    sidebar: null,
    sidebarGlass: null,
    overviewScale: 20,
    contextMenu: null,
    // pane: the ContentPane where we live
    pane: null,
    // uuid: the uuid of the pane where we live
    uuid: null,
    // scrollNode: the element whose scrollTop property sets the scroll position
    scrollNode: null,
    // history: array of location objects.
    // Just like in a web browser, a "location" consists of an address, plus an
    // optional element within that page (to which we should scroll).
    // In a web browser, the latter is given by the id of a page element, and is
    // set off by a "#" char after the page address.
    // For us, you may use any CSS selector, and we will scroll to the first element
    // that matches it (if any).
    // When we record a location, we always record a scrollSel, recording null
    // if none was specified.
    history: null,
    // ptr: always points at the location object in our history that
    // represents the content we are currently showing. Remains null until
    // the first location has been loaded.
    ptr: null,
    // subscribedLibpath: the libpath to which we are currently subscribed
    subscribedLibpath: null,
    // Each time we load a new page, we overwrite this with the data JSON for
    // that page.
    currentPageData: null,

    navEnableHandlers: null,

    listeners: null,

    // Methods

    /*
     * param nm: The NotesManager.
     * param parent: The DOM element in which page content is to be set.
     * param pane: The ContentPane where elt lives.
     * param uuid: The uuid of the pane where elt lives.
     * param options: {
     *   overviewScale: desired initial scale for overview panel
     * }
     */
    constructor: function(nm, parent, pane, uuid, options) {
        options = options || {};
        this.overviewScale = options.overviewScale || this.overviewScale;
        this.nm = nm;
        this.uuid = uuid;

        this.elt = document.createElement('div');
        this.sidebar = document.createElement('div');
        this.sidebar.classList.add('overviewSidebar', 'globalZoom');
        this.mainview = document.createElement('div');
        const main = this.mainview;
        main.classList.add('mainview', 'globalZoom');
        main.appendChild(this.elt);
        parent.appendChild(main);
        parent.appendChild(this.sidebar);

        main.addEventListener('scroll', this.observeMainAreaScroll.bind(this));
        main.addEventListener('click', this.backgroundClick.bind(this));
        this.attachContextMenu(this.elt);
        this.attachSidebarContextMenu();

        this.pane = pane;
        this.scrollNode = main;
        this.history = [];
        this.navEnableHandlers = [];
        this.listeners = {};
        this.on('pageChange', this.updateOverview.bind(this));
    },

    destroy: function() {
        this.unsubscribe();
    },

    attachContextMenu: function(elt) {
        const menu = new Menu({
            targetNodeIds: [elt]
        });
        const viewer = this;
        menu.addChild(new MenuItem({
            label: 'Toggle Overview',
            onClick: function () {
                viewer.toggleOverviewSidebar();
            }
        }));
        const editSrcItem = new MenuItem({
            label: 'Source',
            onClick: function () {
                viewer.editSource();
            }
        })
        menu.addChild(editSrcItem);
        menu.pfsc_ise_editSrcItem = editSrcItem;
        this.contextMenu = menu;
    },

    updateContextMenu: function(loc) {
        if (this.contextMenu) {
            const isWIP = loc.version === "WIP";
            this.contextMenu.pfsc_ise_editSrcItem.set('label', `${isWIP ? "Edit" : "View"} Source`);
        }
        return loc;
    },

    attachSidebarContextMenu: function() {
        const menu = new Menu({
            targetNodeIds: [this.sidebar]
        });
        const viewer = this;

        const zoomSubMenu = new Menu();
        for (let z = 2; z < 11; z++) {
            const scale = 5*z;
            zoomSubMenu.addChild(new MenuItem({
                label: `${scale}`,
                onClick: function() {
                    viewer.setOverviewScale(scale);
                    const siblings = this.getParent().getChildren();
                    for (let sib of siblings) {
                        sib.set('disabled', sib === this);
                    }
                },
                disabled: scale === viewer.overviewScale,
            }));
        }
        menu.addChild(new PopupMenuItem({
            label: 'Zoom',
            popup: zoomSubMenu,
        }));

        menu.addChild(new MenuItem({
            label: 'Refresh',
            onClick: function () {
                viewer.updateOverview();
            }
        }));
        menu.addChild(new MenuItem({
            label: 'Close',
            onClick: function () {
                viewer.showOverviewSidebar(false);
            }
        }));
    },

    editSource: function() {
        const desc = this.describeCurrentLocation();
        if (desc) {
            const info = {
                type: "SOURCE",
                origType: "NOTES",
                libpath: desc.libpath,
                modpath: desc.modpath,
                version: desc.version,
                useExisting: true,
                sourceRow: desc.sourceRow,
            };
            this.nm.hub.contentManager.openContentInActiveTC(info);
        }
    },

    observeMainAreaScroll: function(evt) {
        this.updateOverviewGlass();
    },

    backgroundClick: function(event) {
        // Do not clear the selection if the click target itself is selected.
        const selectedTargetClick = event.target.classList.contains('selected');
        if (!selectedTargetClick) {
            this.clearWidgetSelection();
        }
    },

    markWidgetElementAsSelected: function(elt) {
        this.clearWidgetSelection();
        elt.classList.add('selected');
    },

    clearWidgetSelection: function() {
        document.querySelectorAll('a.widget.selected').forEach(a => {
            a.classList.remove('selected');
        });
    },

    showOverviewSidebar: function(doShow) {
        const grandparent = this.elt.parentElement.parentElement;
        if (doShow) {
            this.updateOverview();
            this.centerGlass();
            grandparent.classList.add('showSidebar');
        } else {
            grandparent.classList.remove('showSidebar');
        }
    },

    toggleOverviewSidebar: function() {
        this.showOverviewSidebar(!this.sidebarIsVisible());
    },

    sidebarIsVisible: function() {
        const grandparent = this.elt.parentElement.parentElement;
        return grandparent.classList.contains('showSidebar');
    },

    getSidebarProperties: function() {
        return {
            visible: this.sidebarIsVisible(),
            scale: this.overviewScale,
        };
    },

    /* param s: Desired scale percentage, as integer. E.g. 20 for 20%.
     */
    setOverviewScale: function(s) {
        this.overviewScale = s;
        this.updateOverview();
    },

    updateOverview: function() {
        const doCloneChildren = true;
        const clone = this.elt.cloneNode(doCloneChildren);
        clone.classList.add('sidebarContents');
        clone.style.transform = `scale(${this.overviewScale/100})`;
        iseUtil.removeAllChildNodes(this.sidebar);
        this.sidebar.appendChild(clone);

        const glass = this.makeOverviewGlass();
        this.sidebar.appendChild(glass);
        this.sidebarGlass = glass;
        this.updateOverviewGlass();
    },

    makeOverviewGlass: function() {
        const glass = document.createElement('div');
        glass.classList.add('glass');
        glass.addEventListener('mousedown', mdEvent => {
            const ay = mdEvent.clientY;
            const a_s = this.scrollNode.scrollTop;
            const moveHandler = mmEvent => {
                const ey = mmEvent.clientY,
                    dy = ey - ay;
                this.scrollNode.scrollTop = a_s + dy / (this.overviewScale/100);
                mmEvent.stopPropagation();
            };
            const upHandler = muEvent => {
                document.documentElement.removeEventListener('mousemove', moveHandler);
                document.documentElement.removeEventListener('mouseup', upHandler);
                muEvent.stopPropagation();
            };
            document.documentElement.addEventListener('mousemove', moveHandler);
            document.documentElement.addEventListener('mouseup', upHandler);
            mdEvent.stopPropagation();
        });
        return glass;
    },

    updateOverviewGlass: function() {
        const sf = this.computeScrollFrac();
        const h = this.sidebar.scrollHeight * this.overviewScale/100;
        const t = sf * h;
        this.sidebarGlass.style.top = t + 'px';
        const view_height = this.mainview.clientHeight;
        this.sidebarGlass.style.height = view_height * this.overviewScale/100 + 'px';
        this.keepGlassInView();
    },

    keepGlassInView: function() {
        const visible0 = this.sidebar.scrollTop;
        const visible1 = visible0 + this.sidebar.clientHeight;
        const glass0 = this.sidebarGlass.offsetTop;
        const glass1 = glass0 + this.sidebarGlass.offsetHeight;
        if (glass0 < visible0) {
            this.sidebar.scrollTop -= visible0 - glass0;
        } else if (glass1 > visible1) {
            this.sidebar.scrollTop += glass1 - visible1;
        }
    },

    centerGlass: function() {
        const visible0 = this.sidebar.scrollTop;
        const visible1 = visible0 + this.sidebar.clientHeight;
        const glass0 = this.sidebarGlass.offsetTop;
        const glass1 = glass0 + this.sidebarGlass.offsetHeight;
        this.sidebar.scrollTop += (glass0 + glass1)/2 - (visible0 + visible1)/2;
    },

    observeWidgetVisualUpdate: function(event) {
        this.updateOverview();
    },

    addNavEnableHandler: function(callback) {
        this.navEnableHandlers.push(callback);
    },

    publishNavEnable: function() {
        let b = this.canGoBackward(),
            f = this.canGoForward();
        this.navEnableHandlers.forEach(cb => {
            cb({
                back: b,
                fwd: f,
                paneId: this.pane.id,
            });
        });
    },

    // -----------------------------------------------------------------------
    // Navigation
    //
    // These are high-level methods that manage the history while setting
    // what it is that we are to be viewing.

    /* Navigate to a location.
     *
     * param loc: An object describing the desired location.
     *  All fields are optional, except that if we do not yet have a current
     *  location, then libpath and version are required (else it's a no-op).
     *  optional fields:
     *      libpath: the libpath of the annotation to be viewed.
     *          If undefined, use current.
     *      version: the version of the annotation to be viewed.
     *          If undefined, use current.
     *      scrollSel: a CSS selector. Will scroll to first element in
     *          the page that matches the selector, if any.
     *      scrollFrac: a float between 0 and 1 indicating what fraction of
     *          the page we should scroll to vertically. If scrollSel is
     *          also defined, scrollFrac overrides it.
     *      select: a CSS selector. Will mark this element as "selected" by
     *          adding the 'selected' class to it, after removing that class
     *          from all others.
     *
     * return: a Promise that resolves after we have finished loading and updating history
     */
    goTo: function(loc) {
        const cur = this.getCurrentLoc() || {};
        loc.libpath = loc.libpath || cur.libpath;
        loc.version = loc.version || cur.version;
        if (!loc.libpath || !loc.version) {
            return;
        }
        const oldPageData = this.currentPageData;
        this.recordScrollFrac();
        return this.updatePage(loc).then(() => {
            const update = this.describeLocationUpdate(loc);
            if (update.locationChange) {
                if (update.annotationChange) {
                    // Note: it is critical that these steps happen before
                    // the `recordNewHistory` step, since that changes the
                    // _current_ location, which these methods rely upon.
                    this.announcePageChange(loc, oldPageData);
                    this.updateSubscription(loc);
                }
                this.recordNewHistory(loc);
            }
        });
    },

    canGoForward: function() {
        if (this.ptr === null) return false;
        let n = this.history.length;
        return this.ptr < n - 1;
    },

    canGoBackward: function() {
        if (this.ptr === null) return false;
        return this.ptr > 0;
    },

    /* Navigate to the next location forward in the history, if any.
     *
     * return: a Promise that resolves after we have finished loading and updating history
     */
    goForward: function() {
        const oldPageData = this.currentPageData;
        this.recordScrollFrac();
        return new Promise((resolve, reject) => {
            if (this.ptr === null) reject();
            var n = this.history.length;
            if (this.ptr < n - 1) {
                var loc = this.history[this.ptr + 1];
                this.updatePage(loc).then(() => {
                    const update = this.describeLocationUpdate(loc);
                    if (update.annotationChange) {
                        this.announcePageChange(loc, oldPageData);
                        this.updateSubscription(loc);
                    }
                    this.incrPtr();
                }).then(resolve);
            } else {
                // Could reject if wanted to make it an error to try to go
                // forward when there are no more pages, but we'll just fail silently.
                resolve();
            }
        });
    },

    /* Navigate to the previous location in the history, if any.
     *
     * return: a Promise that resolves after we have finished loading and updating history
     */
    goBackward: function() {
        const oldPageData = this.currentPageData;
        this.recordScrollFrac();
        return new Promise((resolve, reject) => {
            if (this.ptr === null) reject();
            if (this.ptr > 0) {
                var loc = this.history[this.ptr - 1];
                this.updatePage(loc).then(() => {
                    const update = this.describeLocationUpdate(loc);
                    if (update.annotationChange) {
                        this.announcePageChange(loc, oldPageData);
                        this.updateSubscription(loc);
                    }
                    this.decrPtr();
                }).then(resolve);
            } else {
                // Could reject if wanted to make it an error to try to go
                // backward when there are no more pages, but we'll just fail silently.
                resolve();
            }
        });
    },

    /* Return a location object describing the current location.
     * It will be a fresh object, not a ref to any element of our history, so clients
     * may modify the returned object with impunity.
     *
     * The returned description either will include all three of libpath, scrollSel, and scrollFrac;
     * OR it will be null if we do not have a current location.
     */
    describeCurrentLocation: function() {
        var loc = this.getCurrentLoc();
        if (loc === null) {
            return null;
        }
        // Make a copy.
        var desc = {
            libpath: loc.libpath,
            version: loc.version,
            scrollSel: loc.scrollSel,
            sourceRow: loc.sourceRow,
            modpath: loc.modpath,
        }
        // Note scrollFrac.
        var f = this.computeScrollFrac();
        desc.scrollFrac = f;
        return desc;
    },

    computeScrollFrac: function() {
        var h = this.scrollNode.scrollHeight,
            t = this.scrollNode.scrollTop,
            f = t/h;
        return f;
    },

    // -----------------------------------------------------------------------
    // History tools

    /* Record a new location in the history.
     * We actually record a _copy_ of the given location object.
     * We ensure that the object we record always has a scrollSel field, setting
     * this to null if no value was provided.
     */
    recordNewHistory: function(loc) {
        var rec = {
            libpath: loc.libpath,
            version: loc.version,
            scrollSel: (loc.scrollSel === undefined) ? null : loc.scrollSel,
            sourceRow: loc.sourceRow,
            modpath: loc.modpath,
        };
        if (this.ptr === null) {
            this.history = [rec];
            this.ptr = 0;
        } else {
            this.history.splice(this.ptr + 1);
            this.history.push(rec);
            this.incrPtr();
        }
    },

    /* Get a shallow copy of the history.
     * So it is a new array, but it points to the same history elements.
     */
    copyHistory: function() {
        var h = [];
        for (var i in this.history) h.push(this.history[i]);
        return h;
    },

    /* Inelegantly force this viewer's history and pointer to be certain values.
     * Use wisely.
     */
    forceHistory: function(history, ptr) {
        this.history = history;
        this.ptr = ptr;
    },

    /* If there is a current history frame, record the current scroll frac in it.
     */
    recordScrollFrac: function() {
        if (this.ptr !== null) this.history[this.ptr].scrollFrac = this.computeScrollFrac();
    },

    /* Increment history pointer.
     * This gets a method since we may want some allied activity.
     */
    incrPtr: function() {
        this.ptr++;
        this.publishNavEnable();
    },

    /* Decrement history pointer.
     * This gets a method since we may want some allied activity.
     */
    decrPtr: function() {
        this.ptr--;
        this.publishNavEnable();
    },

    /* Get the current location.
     * null if we don't have one yet; else the current element of our history.
     * Note that you do not get a copy; you get the history element itself.
     */
    getCurrentLoc: function() {
        if (this.ptr === null) return null;
        return this.history[this.ptr];
    },

    /* Given a location, describe (with booleans) in what way(s) it
     * differs from the current location.
     *
     * If the current location is null (we don't have a location yet), then
     * the given one will be said to differ from it in every way.
     */
    describeLocationUpdate: function(loc) {
        const cur = this.getCurrentLoc() || {};
        const libpathChange = cur.libpath !== loc.libpath;
        const versionChange = cur.version !== loc.version;
        const scrollSelChange = cur.scrollSel !== loc.scrollSel;
        return {
            libpathChange: libpathChange,
            versionChange: versionChange,
            scrollSelChange: scrollSelChange,
            annotationChange: libpathChange || versionChange,
            locationChange: libpathChange || versionChange || scrollSelChange,
        };
    },

    getCurrentLibpath: function() {
        var loc = this.getCurrentLoc();
        return loc === null ? null : loc.libpath;
    },

    getCurrentLibpathv: function() {
        var loc = this.getCurrentLoc();
        return loc === null ? null : iseUtil.lv(loc.libpath, loc.version);
    },

    announcePageChange: function(loc, oldPageData) {
        const event = {
            type: 'pageChange',
            uuid: this.uuid,
            oldLibpathv: null,
            oldPageData: oldPageData,
            newLibpathv: `${loc.libpath}@${loc.version}`,
        }
        const cur = this.getCurrentLoc();
        if (cur) {
            event.oldLibpathv = `${cur.libpath}@${cur.version}`;
        }
        this.dispatch(event);
    },

    /* Remove any existing subscription, and subscribe to the libpath
     * we are currently viewing (but only if it is WIP).
     */
    updateSubscription: function(loc) {
        this.unsubscribe();
        if (loc.version === "WIP") {
            this.subscribe(loc.libpath);
        }
    },

    unsubscribe: function() {
        if (this.subscribedLibpath !== null) {
            this.nm.subscriptionManager.setSubscription(this.pane.id, this.subscribedLibpath, false);
        }
    },

    subscribe: function(libpath) {
        // Do not subscribe to special libpaths.
        if (libpath.startsWith('special.')) libpath = null;
        this.subscribedLibpath = libpath;
        if (libpath !== null) {
            this.nm.subscriptionManager.setSubscription(this.pane.id, this.subscribedLibpath, true);
        }
    },

    // -----------------------------------------------------------------------
    // Low-level functions

    /* Receive updated page contents.
     *
     * param contents: object with `html` and `data` (widget JSON) properties.
     */
    receivePublication: async function(contents) {
        const oldPageData = this.currentPageData;

        // We can use a description of our current location to get the
        // scroll fraction. Then setting the contents directly in the location
        // object will get what we want from our updatePage method.
        const loc = this.describeCurrentLocation();
        loc.contents = contents;
        await this.updatePage(loc);

        const event = {
            type: 'pageReload',
            uuid: this.uuid,
            libpath: loc.libpath,
            oldPageData: oldPageData,
            newPageData: this.currentPageData,
        }
        this.dispatch(event);
    },

    /* Update the page, according to a location descriptor.
     * Here we do not touch the history. We only work with the actual contents of the page.
     *
     * Note: It is important that you NOT update the history before calling this method.
     *  This method assumes that the history pointer still points at a descriptor of what
     *  is currently loaded in the page. If you are planning to update the history, you
     *  should do that AFTER this method's promise resolves.
     *
     * param loc: a location descriptor:
     *   MAY include libpath
     *   MAY include scrollFrac
     *   MAY include scrollSel
     *   MAY include contents = {html: ..., data: ...}
     *
     * return: a promise that resolves after the page has been updated.
     */
    updatePage: function(loc) {
        const viewer = this;
        const currentLoc = this.getCurrentLoc();
        const currentPath = (currentLoc === null) ? null : currentLoc.libpath;
        const currentVers = (currentLoc === null) ? null : currentLoc.version;
        const pageContentsStep = new Promise(function(resolve, reject){
            // If page contents were provided directly, just use them.
            if (loc.contents) {
                viewer.setPageContents(loc.contents.html, loc.contents.data);
                resolve(loc);
            }
            // If not, then retrieve page contents from back-end if we want
            // a different libpath or version than the current one.
            else if (loc.libpath !== currentPath || loc.version !== currentVers) {
                viewer.loadPageContents(loc).then(function(contents) {
                    viewer.setPageContents(contents.html, contents.data);
                    resolve(loc);
                });
            }
            // Otherwise we don't need to change the page contents.
            else {
                resolve(loc);
            }
        });
        return pageContentsStep
            .then(this.updateContextMenu.bind(this))
            .then(this.doScrolling.bind(this))
            .then(this.doSelection.bind(this))
            .then(this.updateOverview.bind(this));
    },

    /* Load page data from back-end.
     *
     * return: a promise that resolves with the page contents.
     */
    loadPageContents: function({libpath, version}) {
        return this.prepareDataForPageLoad({libpath, version}).then(data => {
            return this.nm.hub.xhrFor('loadAnnotation', {
                method: "POST",
                query: {libpath: libpath, vers: version},
                form: data,
                handleAs: "json",
            }).then(function(resp){
                if (resp.err_lvl > 0) {
                    throw new Error(resp.err_msg);
                }
                const data_json = resp.data_json;
                return {
                    html: resp.html,
                    data: JSON.parse(data_json)
                };
            });
        })
    },

    prepareDataForPageLoad: async function({libpath, version}) {
        const data = {};

        const ssnrMode = this.nm.hub.studyManager.inSsnrMode();
        const studyPagePrefix = 'special.studypage.';
        const studyPageSuffix = '.studyPage';

        if (libpath.startsWith(studyPagePrefix)) {
            data.special = 'studypage';
            if (!ssnrMode) {
                const studypath = libpath.slice(studyPagePrefix.length, -studyPageSuffix.length);
                const resp = await this.nm.hub.xhrFor('lookupGoals', {
                    query: { libpath: studypath, vers: version },
                    handleAs: 'json',
                });
                if (resp.err_lvl > 0) {
                    throw new Error(resp.err_msg);
                }
                const origins = resp.origins;
                const studyData = this.nm.hub.studyManager.buildGoalLookupByList(origins);
                data.studyData = JSON.stringify(studyData)
            }
        }

        return data;
    },

    /* Given the actual HTML and widget data that define the page we wish to
     * show, set these contents into the page.
     * This means setting the HTML into our page element,
     * requesting MathJax typesetting, and setting up the widgets.
     */
    setPageContents: function(html, data) {
        const elt = this.elt;
        query(elt).innerHTML(html);
        iseUtil.typeset([elt]);

        this.currentPageData = data;

        this.nm.setupWidgets(data, this.elt, this.pane);
    },

    /* Presuming the page data for a location is already loaded, do the scrolling
     * that the location requests.
     *
     * scrollFrac controls, if defined.
     */
    doScrolling: function(loc) {
        if (loc.scrollFrac) {
            this.scrollToFraction(loc.scrollFrac);
        } else if (loc.scrollSel || loc.scrollSel === null) {
            this.scrollToSelector(loc.scrollSel);
        }
        return loc;
    },

    /* Mark any selection requested by the location descriptor.
     */
    doSelection: function(loc) {
        if (loc.select) {
            const selectedElt = this.elt.querySelector(loc.select);
            if (selectedElt) {
                this.markWidgetElementAsSelected(selectedElt);
            }
        }
        return loc;
    },

    /* Scroll a fraction of the way down the page.
     *
     * param frac: a number between 0 and 1
     */
    scrollToFraction: function(frac) {
        if (frac < 0 || frac > 1) throw new Error('Scroll fraction out of bounds.');
        var h = this.scrollNode.scrollHeight;
        var t = frac * h;
        this.scrollNode.scrollTop = t;
    },

    /* Scroll to the first element matching the given CSS selector.
     *
     * param sel: the CSS selector. If null, we scroll to top.
     * return: boolean: true iff we found an element to scroll to.
     */
    scrollToSelector: function(sel) {
        if (sel === null) {
            this.scrollNode.scrollTop = 0;
            return false;
        }
        var elt = this.scrollNode.querySelector(sel);
        if (elt === null) return false;
        this.scrollNode.scrollTop = elt.offsetTop;
        return true;
    },

});

Object.assign(PageViewer.prototype, iseUtil.eventsMixin);

return PageViewer;

});

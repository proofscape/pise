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

import { Listenable } from "browser-peers/src/util";
import { util as iseUtil } from "../../util";

const dojo = {};

define([
    "dijit/Menu",
    "dijit/MenuItem"
], function(
    Menu,
    MenuItem
) {
    dojo.Menu = Menu;
    dojo.MenuItem = MenuItem;
});

export class BasePageViewer extends Listenable {

    constructor(notesManager, pageType) {
        super({});
        this.mgr = notesManager;
        this.pageType = pageType;
        this.navEnableHandlers = [];

        // history: array of location objects.
        // Just like in a web browser, a "location" consists of an address, plus an
        // optional element within that page (to which we should scroll).
        // In a web browser, the latter is given by the id of a page element, and is
        // set off by a "#" char after the page address.
        // For us, you may use any CSS selector, and we will scroll to the first element
        // that matches it (if any).
        // When we record a location, we always record a scrollSel, recording null
        // if none was specified.
        this.history = [];
        // ptr: always points at the location object in our history that
        // represents the content we are currently showing. Remains null until
        // the first location has been loaded.
        this.ptr = null;
        // Each time we load a new page, we overwrite this with the data JSON for
        // that page.
        this.currentPageData = null;

        this.subscribedLibpath = null;
        this.subscriptionManager = null;
        this.contextMenu = null;
        this.lastScrollFrac = null;

        // Page change events are built in stages, so we need to store the event.
        this.pageChangeEvent = null;
    }

    destroy() {
        this.unsubscribe();
    }

    pushScrollFrac() {
        this.lastScrollFrac = this.computeScrollFrac();
    }

    async popScrollFrac() {
        if (this.lastScrollFrac) {
            this.scrollToFraction(this.lastScrollFrac);
        }
        this.lastScrollFrac = null;
    }

    typeset(elements, win) {
        return iseUtil.typeset(elements, win);
    }

    setupBackgroundClickHandler() {
        this.mainContentArea.addEventListener('click', this.backgroundClick.bind(this));
    }

    backgroundClick(event) {
        // Do not clear the selection if the click target itself is selected.
        const selectedTargetClick = event.target.classList.contains('selected');
        if (!selectedTargetClick) {
            this.clearWidgetSelection();
        }
    }

    markWidgetElementAsSelected(elt) {
        this.clearWidgetSelection();
        elt.classList.add('selected');
    }

    clearWidgetSelection() {
        this.contentElement.querySelectorAll('a.widget.selected').forEach(a => {
            a.classList.remove('selected');
        });
    }

    canGoForward() {
        if (this.ptr === null) return false;
        let n = this.history.length;
        return this.ptr < n - 1;
    }

    canGoBackward() {
        if (this.ptr === null) return false;
        return this.ptr > 0;
    }

    // Subclasses may wish to override.
    //
    // The purpose is to ensure that locations being recorded in our history
    // contain complete and well-formed information.
    //
    // rec: the content descriptor to be normalized. Should be modified in
    //  place. This object will be recorded in our history.
    // return: nothing. `rec` should be modified in-place.
    normalizeHistoryRecord(rec) {
        if (rec.scrollSel === undefined) {
            rec.scrollSel = null;
        }
    }

    // Record a copy of the given location as a new location in our history.
    recordNewHistory(loc) {
        const rec = Object.assign({}, loc);
        this.normalizeHistoryRecord(rec);
        if (this.ptr === null) {
            this.history = [rec];
            this.ptr = 0;
        } else {
            this.history.splice(this.ptr + 1);
            this.history.push(rec);
            this.incrPtr();
        }
    }

    /* Get a shallow copy of the history.
     * So it is a new array, but it points to the same history elements.
     */
    copyHistory() {
        return this.history.slice();
    }

    /* Inelegantly force this viewer's history and pointer to be certain values.
     * Use wisely.
     */
    forceHistory(history, ptr) {
        this.history = history;
        this.ptr = ptr;
    }

    /* If there is a current history frame, record the current scroll frac in it.
     */
    recordScrollFrac() {
        if (this.ptr !== null) this.history[this.ptr].scrollFrac = this.computeScrollFrac();
    }

    /* Increment history pointer.
     * This gets a method since we may want some allied activity.
     */
    incrPtr() {
        this.ptr++;
        this.publishNavEnable();
    }

    /* Decrement history pointer.
     * This gets a method since we may want some allied activity.
     */
    decrPtr() {
        this.ptr--;
        this.publishNavEnable();
    }

    /* Get the current location.
     * null if we don't have one yet; else the current element of our history.
     * Note that you do not get a copy; you get the history element itself.
     */
    getCurrentLoc() {
        if (this.ptr === null) return null;
        return this.history[this.ptr];
    }

    /* Return a location object describing the current location, including up-to-date
     * scrollFrac, or `null` if we do not have a current location.
     *
     * The inclusion of up-to-date scrollFrac makes the return value suitable for use
     * when reloading the page due to a rebuild.
     *
     * It will be a fresh object, not a ref to any element of our history, so clients
     * may modify the returned object with impunity.
     */
    describeCurrentLocation() {
        let loc = this.getCurrentLoc();
        loc = JSON.parse(JSON.stringify(loc));
        if (loc) {
            // Note up-to-date scrollFrac.
            loc.scrollFrac = this.computeScrollFrac();
        }
        return loc;
    }

    addNavEnableHandler(callback) {
        this.navEnableHandlers.push(callback);
    }

    publishNavEnable() {
        let b = this.canGoBackward(),
            f = this.canGoForward();
        this.navEnableHandlers.forEach(cb => {
            cb({
                back: b,
                fwd: f,
                paneId: this.pane.id,
            });
        });
    }

    /* This is a place to do anything (record data in various places, enrich page descriptor)
     * that should happen before a navigation (going forward or backward in history) takes place.
     * Subclasses may wish to override.
     */
    beforeNavigate() {
        this.recordScrollFrac();
        return this.currentPageData;
    }

    /* Reload the page, and dispatch an event announcing the reload.
     *
     * param loc: location object, to help reload the page.
     */
    async reloadPage(loc) {
        const oldPageData = this.currentPageData;
        await this.updatePage(loc);
        const event = {
            type: 'pageReload',
            uuid: this.uuid,
            libpath: loc.libpath,
            oldPageData: oldPageData,
            newPageData: this.currentPageData,
        }
        this.dispatch(event);
    }

    /* Update the page, according to a location descriptor.
     * Here we do not touch the history. We only work with the actual contents of the page.
     *
     * Note: It is important that you NOT update the history before calling this method.
     *  The abstract `pageContentsUpdateStep()` method is allowed to assume
     *  that the history pointer still points at a descriptor of what
     *  is currently loaded in the page. If you are planning to update the history, you
     *  should do that AFTER this method's promise resolves.
     *
     * param loc: a location descriptor:
     *   MAY include scrollFrac (see `scrollToFraction` method)
     *   MAY include scrollSel  (see `scrollToSelector` method)
     *   MAY include scrollOpts (see `scrollToSelector` method)
     *   MAY include select (see `doSelection` method)
     *   MAY include other fields, specific to the subclass, which in some way define
     *       the contents that are to be loaded in the page.
     *
     * return: a promise that resolves after the page has been updated.
     */
    async updatePage(loc) {
        await this.pageContentsUpdateStep(loc);
        this.updateContextMenu(loc);
        this.doScrolling(loc);
        this.doSelection(loc);
        this.observePageUpdate(loc);
    }

    /* param targetNode: dom element containing the background: must be iframe for Sphinx panels
     * param selector: CSS selector of background, within targetNode
     * param optNames: array of strings indicating which options should be added to the menu
     */
    attachContextMenu(targetNode, selector, optNames) {
        const menu = new dojo.Menu({
            targetNodeIds: [targetNode],
            selector: selector,
        });
        const viewer = this;

        if (optNames.includes('toggleOverview')) {
            menu.addChild(new dojo.MenuItem({
                label: 'Toggle Overview',
                onClick: function () {
                    viewer.toggleOverviewSidebar();
                }
            }));
        }

        if (optNames.includes('source')) {
            const editSrcItem = new dojo.MenuItem({
                label: 'Source',
                onClick: function () {
                    viewer.editSource();
                }
            })
            menu.addChild(editSrcItem);
            menu.pfsc_ise_editSrcItem = editSrcItem;
        }

        this.contextMenu = menu;
    }

    editSource() {
        const desc = this.describeCurrentLocation();
        if (desc) {
            const info = {
                type: "SOURCE",
                origType: this.pageType,
                libpath: desc.libpath,
                modpath: desc.modpath,
                version: desc.version,
                useExisting: true,
                sourceRow: desc.sourceRow,
                is_rst: (this.pageType === "SPHINX"),
            };
            this.mgr.hub.contentManager.openContentInActiveTC(info);
        }
    }

    updateContextMenu(loc) {
        if (this.contextMenu) {
            this.contextMenu.pfsc_ise_editSrcItem.set(
                'label', `${this.locIsAtWip(loc) ? "Edit" : "View"} Source`
            );
        }
    }

    /* Presuming the page data for a location is already loaded, do the scrolling
     * that the location requests.
     *
     * scrollFrac controls, if defined.
     */
    doScrolling(loc) {
        if (loc.scrollFrac) {
            this.scrollToFraction(loc.scrollFrac);
        } else if (loc.scrollSel || loc.scrollSel === null) {
            this.scrollToSelector(loc.scrollSel, loc.scrollOpts);
        }
    }

    /* Mark any selection requested by the location descriptor.
     */
    doSelection(loc) {
        if (loc.select) {
            const selectedElt = this.contentElement.querySelector(loc.select);
            if (selectedElt) {
                this.markWidgetElementAsSelected(selectedElt);
            }
        }
    }

    /* Called when a widget in the page has updated its appearance. Subclasses may wish
     * to carry out corresponding updates at this time (e.g. update an overview panel).
     */
    observeWidgetVisualUpdate(event) {
    }

    /* This is called at the end of our `updatePage()` method. It is a place where
     * subclasses may perform any additional steps that are appropriate after the page
     * has been updated, e.g. updating an overview panel, etc.
     */
    observePageUpdate(loc) {
    }

    /* Scroll a fraction of the way down the page.
     *
     * param frac: a number between 0 and 1
     */
    scrollToFraction(frac) {
        if (frac < 0 || frac > 1) {
            throw new Error('Scroll fraction out of bounds.');
        }
        const h = this.scrollNode.scrollHeight;
        this.scrollNode.scrollTop = frac * h;
    }

    computeScrollFrac() {
        const h = this.scrollNode.scrollHeight;
        const t = this.scrollNode.scrollTop;
        return t/h;
    }

    /* Scroll to the first element matching the given CSS selector.
     *
     * param sel: the CSS selector. If null, scroll to top.
     * param options: {
     *  padPx: pixels of padding at each of top and bottom of view area.
     *      Default 0. Adds to pad from padFrac.
     *  padFrac: padding at each of top and bottom of view area, as fraction
     *      of total height of panel. Should be a float between 0.0 and 1.0.
     *      Default 0.0. Adds to pad from padPx.
     *  pos: ['top', 'mid'], default 'top'. Scroll the object to
     *      this position, vertically.
     *  policy: ['pos', 'min', 'distant'], default 'pos'.
     *      'pos': scroll object to pos, no matter what.
     *      'min': scroll just enough to put object in padded view area.
     *          (Under this setting, value of pos is irrelevant.)
     *      'distant': scroll to pos if object "is distant", else min.
     *          If the min scroll to bring object into padded view area
     *          preserves at least one pad width of context, do that;
     *          else scroll to pos.
     * }
     * return: boolean: true iff we found an element to scroll to.
     */
    scrollToSelector(sel, options) {
        options = options || {};
        const display = this.scrollNode;

        if (sel === null) {
            display.scrollTop = 0;
            return false;
        }

        const elt = display.querySelector(sel);
        if (!elt) {
            return false;
        }

        this.addScrollPadding(options);

        iseUtil.scrollIntoView(elt, display, options);
        return true;
    }

    /* Given a location, describe (with booleans) in what way(s) it
     * differs from the current location.
     *
     * If the current location is null (we don't have a location yet), then
     * the given one will be said to differ from it in every way.
     */
    describeLocationUpdate(loc) {
        const cur = this.getCurrentLoc() || {};
        const libpathChange = cur.libpath !== loc.libpath;
        const versionChange = cur.version !== loc.version;
        const scrollSelChange = cur.scrollSel !== loc.scrollSel;
        return {
            libpathChange: libpathChange,
            versionChange: versionChange,
            scrollSelChange: scrollSelChange,
            pageChange: libpathChange || versionChange,
            locationChange: libpathChange || versionChange || scrollSelChange,
        };
    }

    startPageChangeEvent(newLoc, oldPageData) {
        const event = {
            type: 'pageChange',
            uuid: this.uuid,
            oldLibpathv: null,
            oldPageData: oldPageData,
            newLibpathv: `${newLoc.libpath}@${newLoc.version}`,
            newPageData: null,
        }
        // This method is called before the history is updated, so the
        // "old" location is the current location.
        const oldLoc = this.getCurrentLoc();
        if (oldLoc) {
            event.oldLibpathv = `${oldLoc.libpath}@${oldLoc.version}`;
        }
        this.pageChangeEvent = event;
    }

    announcePageChangeIfAny() {
        const event = this.pageChangeEvent;
        if (event) {
            event.newPageData = this.currentPageData;
            this.dispatch(event);
            this.pageChangeEvent = null;
        }
    }

    /* Remove any existing subscription, and subscribe to the libpath
     * we are currently viewing (but only if it is WIP).
     */
    updateSubscription(loc) {
        this.unsubscribe();
        if (loc.version === "WIP") {
            this.subscribe(loc.libpath);
        }
    }

    unsubscribe() {
        if (this.subscribedLibpath !== null) {
            this.subscriptionManager.setSubscription(this.pane.id, this.subscribedLibpath, false);
        }
    }

    subscribe(libpath) {
        // Do not subscribe to special libpaths.
        if (libpath.startsWith('special.')) libpath = null;
        this.subscribedLibpath = libpath;
        if (libpath !== null) {
            this.subscriptionManager.setSubscription(this.pane.id, this.subscribedLibpath, true);
        }
    }

    /* Given a location descriptor, ensure that it defines a libpath and version,
     * by copying these from our current location if necessary.
     *
     * return: true if we were able to ensure that both libpath and version are
     *  defined in the location object, false if not.
     */
    ensureLibpathAndVersion(loc) {
        const cur = this.getCurrentLoc() || {};
        loc.libpath = loc.libpath || cur.libpath;
        loc.version = loc.version || cur.version;
        return !!loc.libpath && !!loc.version;
    }

    /* Navigate to a location.
     *
     * param loc: An object describing the desired location.
     *  All fields are optional, except that if we do not yet have a current
     *  location, then libpath and version are required (else it's a no-op).
     *  optional fields:
     *      libpath: the libpath of the page to be viewed.
     *          If undefined, use current.
     *      version: the version of the page to be viewed.
     *          If undefined, use current.
     *      scrollSel: a CSS selector. Will scroll to first element in
     *          the page that matches the selector, if any. Type of scrolling
     *          is controlled by scrollOpts.
     *      scrollOpts: see `scrollToSelector()` method.
     *      scrollFrac: a float between 0 and 1 indicating what fraction of
     *          the page we should scroll to vertically. If scrollSel is
     *          also defined, scrollFrac overrides it.
     *      select: a CSS selector. Will mark this element as "selected" by
     *          adding the 'selected' class to it, after removing that class
     *          from all others.
     *
     * return: Promise that resolves after we have finished loading and updating history
     */
    async goTo(loc) {
        const ok = this.ensureLibpathAndVersion(loc);
        if (!ok) {
            console.debug('Cannot go to location without libpath and version.', loc);
            return;
        }
        const update = await this.go(loc);
        if (update.locationChange) {
            this.recordNewHistory(loc);
        }
    }

    /* Navigate to the next location forward in the history, if any.
     *
     * return: Promise that resolves after we have finished loading and updating history
     */
    async goForward() {
        if (this.canGoForward()) {
            const loc = this.history[this.ptr + 1];
            await this.go(loc);
            this.incrPtr();
        }
    }

    /* Navigate to the previous location in the history, if any.
     *
     * return: Promise that resolves after we have finished loading and updating history
     */
    async goBackward() {
        if (this.canGoBackward()) {
            const loc = this.history[this.ptr - 1];
            await this.go(loc);
            this.decrPtr();
        }
    }

    async go(loc) {
        const oldPageData = this.beforeNavigate();
        await this.updatePage(loc);
        const update = this.describeLocationUpdate(loc);
        if (update.pageChange) {
            // Note: it is critical that these steps happen before
            // the `recordNewHistory` step, since that changes the
            // *current* location, which these methods rely upon.
            this.startPageChangeEvent(loc, oldPageData);
            this.updateSubscription(loc);
        } else {
            // Ensure that we do not announce a page change.
            this.pageChangeEvent = null;
        }
        return update;
    }

    // ---------------------------------------------------------------------------
    // SUBCLASSES MUST OVERRIDE

    /* Get the element where content is displayed.
     */
    get contentElement() {
        return null;
    }

    /* Get the element where a background click should deselect any selected widget.
     */
    get mainContentArea() {
        return null;
    }

    /* Get the element whose `scrollTop` should be adjusted, to scroll the page.
     */
    get scrollNode() {
        return null;
    }

    // Return the tail-versioned libpath of the viewer's current location,
    // or null if none.
    getCurrentLibpathv() {
    }

    /* This is where subclasses implement the part of the `updatePage()` operation that
     * is responsible for (possibly) loading content.
     */
    async pageContentsUpdateStep(loc) {
    }

    /* Say whether a given location descriptor object (of the kind that gets recorded
     * in the viewer's history) represents a page @WIP version.
     */
    locIsAtWip(loc) {
        return false;
    }

    // ---------------------------------------------------------------------------
    // SUBCLASSES MAY OVERRIDE

    /* Opportunity for subclasses to add (or otherwise adjust) the padding that will
     * be used for scrolling to a selector.
     *
     * param options: As received by our `scrollToSelector()` method. Should be modified
     *  in place.
     * return: nothing
     */
    addScrollPadding(options) {
    }

}

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

const ise = {};

define([
    "ise/util",
], function(
    util
) {
    ise.util = util;
});

export class BasePageViewer extends Listenable {

    constructor(notesManager) {
        super({});
        this.mgr = notesManager;
        this.navEnableHandlers = [];
        this.history = [];
        this.ptr = null;
        this.currentPageData = null;
        this.subscribedLibpath = null;
        this.subscriptionManager = null;
    }

    // ---------------------------------------------------------------------------
    // SUBCLASSES MUST OVERRIDE

    /* Get the element where content is displayed.
     */
    get contentElement() {
        return null;
    }

    /* Get the element whose `scrollTop` should be adjusted, to scroll the page.
     */
    get scrollNode() {
        return null;
    }

    // ---------------------------------------------------------------------------

    destroy() {
        this.unsubscribe();
    }

    markWidgetElementAsSelected(elt) {
        this.clearWidgetSelection();
        elt.classList.add('selected');
    }

    clearWidgetSelection() {
        document.querySelectorAll('a.widget.selected').forEach(a => {
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

    describeCurrentLocation() {
        const loc = this.getCurrentLoc();
        // Return a copy.
        return JSON.parse(JSON.stringify(loc));
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
        this.updateOverview(loc);
    }

    // SUBCLASSES MUST OVERRIDE
    /* This is where subclasses implement the part of the `updatePage()` operation that
     * is responsible for (possibly) loading content.
     */
    async pageContentsUpdateStep(loc) {
    }

    updateContextMenu(loc) {
        if (this.contextMenu) {
            this.contextMenu.pfsc_ise_editSrcItem.set(
                'label', `${this.locIsAtWip(loc) ? "Edit" : "View"} Source`
            );
        }
    }

    // SUBCLASSES SHOULD OVERRIDE
    locIsAtWip(loc) {
        return false;
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

    /* If the page viewer has an overview panel of some kind, that may need some special
     * update steps, whenever the page is updated. Subclasses can perform such steps here.
     */
    updateOverview(loc) {
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
        const display = this.scrollNode;

        if (sel === null) {
            display.scrollTop = 0;
            return false;
        }

        const elt = display.querySelector(sel);
        if (!elt) {
            return false;
        }

        ise.util.scrollIntoView(elt, display, options);
        return true;
    }

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

    announcePageChange(update, loc, oldPageData) {
        if (update.pageChange) {
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
        }
    }

    updateSubscription(update, loc) {
        if (update.pageChange) {
            this.unsubscribe();
            if (loc.version === "WIP") {
                this.subscribe(loc.libpath);
            }
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

    async goTo(loc) {
        const update = await this.go(loc);
        if (update.locationChange) {
            this.recordNewHistory(loc);
        }
    }

    /* Navigate to the next location forward in the history, if any.
     *
     * return: a Promise that resolves after we have finished loading and updating history
     */
    async goForward() {
        if (this.canGoForward()) {
            const loc = this.history[this.ptr + 1];
            await this.go(loc);
            this.incrPtr();
        }
    }

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
        this.announcePageChange(update, loc, oldPageData);
        this.updateSubscription(update, loc);
        return update;
    }
}

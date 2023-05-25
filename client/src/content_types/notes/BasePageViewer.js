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

export class BasePageViewer extends Listenable {

    constructor() {
        super({});
        this.navEnableHandlers = [];
        this.history = [];
        this.ptr = null;
        this.currentPageData = null;
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

    enrichHistoryRecord(rec, loc) {
    }

    recordNewHistory(loc) {
        const rec = Object.assign({}, loc);
        this.enrichHistoryRecord(rec, loc);
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
    }

    async updatePage(loc) {
    }

    describeLocationUpdate(loc) {
    }

    announcePageChange(update, loc, oldPageData) {
    }

    updateSubscription(update, loc) {
    }

    async goTo(loc) {
        await this.go(loc);
        this.recordNewHistory(loc);
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
    }
}

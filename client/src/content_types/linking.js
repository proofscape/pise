/* ------------------------------------------------------------------------- *
 *  Copyright (c) 2011-2023 Proofscape contributors                          *
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

/* Classes to support global (i.e. across-window) linking maps
 */

/* Generally, you should use a GlobalLinkingMap, not a LinkingMapComponent.
 * The former uses the latter internally, on your behalf, and is the user-friendly
 * interface.
 *
 * To understand what a "linking map component" is, first we have to say what
 * a "linking map" is.
 *
 * A linking map is one of the maps
 *
 *      L: W x X --> 2^W
 *
 * we use to represent the linking of content panels. Here, W is the set of all panel
 * uuids in *all* windows, and X is some other set of IDs (of some kind, e.g. libpaths,
 * doc Ids, etc.).
 *
 * Each window maintains a *component* of this map, which we can render as
 *
 *      m: U x X --> 2^W
 *
 * where U is the set of all panel uuids in *this* window. An instance of this class
 * represents such a component m.
 *
 * Although we think of the values of the map as sets of uuids, we implement them
 * as arrays.
 */
export class LinkingMapComponent {

    constructor(hub, name) {
        this.hub = hub;
        this.name = name;
        this.map = new Map();
    }

    // ------------------------------------------------------------------------
    // FOR INTERNAL USE

    // Get m(u, x), returning `undefined` if not yet defined.
    _get(u, x) {
        const mu = this.map.get(u);
        if (mu === undefined) {
            return undefined;
        } else {
            return mu.get(x);
        }
    }

    // Set m(u, x) <-- W.
    _set(u, x, W) {
        let mu = this.map.get(u);
        if (mu === undefined) {
            mu = new Map();
            this.map.set(u, mu);
        }
        mu.set(x, W);
    }

    // Make m(u, x) undefined.
    // Broadcast the corresponding 'linkingMapNewlyUndefinedAt' event.
    // If this makes m(u) empty, then make m(u) undefined too.
    // Return boolean saying whether we deleted anything.
    _delete(u, x) {
        let mu = this.map.get(u);
        if (mu !== undefined) {
            let deleted = mu.delete(x);
            if (deleted) {
                this.notifyOfNewlyUndefined(u, x);
            }
            if (mu.size === 0) {
                this.map.delete(u);
            }
            return deleted
        }
        return false;
    }

    // Remove the triple (u, x, w) from this mapping, if present.
    // Return boolean saying whether it was found and removed.
    _remove_triple(u, x, w) {
        const mux = this._get(u, x);
        if (mux === undefined) {
            return false;
        } else {
            const i0 = mux.indexOf(w);
            if (i0 < 0) {
                return false;
            } else {
                mux.splice(i0, 1);
                if (mux.length === 0) {
                    this._delete(u, x);
                }
                return true;
            }
        }
    }

    /* Represent this component as an array of triples [u, x, w].
     *
     * return: array of triples [[u, x, w], [u, x, w], ...]
     */
    _asTriples() {
        const triples = [];
        for (const [u, mu] of this.map) {
            for (const [x, W] of mu) {
                for (const w of W) {
                    triples.push([u, x, w]);
                }
            }
        }
        return triples;
    }

    // Get m(u, x), making it into a new empty array if not yet defined.
    _get_default(u, x) {
        let mux = this._get(u, x);
        if (mux === undefined) {
            this._set(u, x, []);
        }
        return this._get(u, x);
    }

    // Find out whether a given panel uuid is hosted in our window.
    // return: `null` if not hosted here; else the Dijit paneId (guaranteed truthy)
    myWindowHostsUuid(u) {
        return this.hub.contentManager.getPaneIdByUuid(u);
    }

    notifyOfNewlyUndefined(u, x) {
        this.hub.windowManager.groupcastEvent({
            type: 'linkingMapNewlyUndefinedAt',
            name: this.name,
            pair: [u, x],
        }, {
            includeSelf: true,
        });
    }

    // ------------------------------------------------------------------------
    // REQUEST HANDLERS

    /* Add the uuid w to the set m(u, x), but only if u belongs to our window.
     *
     * Do not add if already present. In other words, although we use arrays,
     * we maintain them as sets.
     *
     * return: true if w was added as a new element, false otherwise
     */
    add({u, x, w}) {
        return this.addSet({u: u, x: x, W: [w]}) > 0;
    }

    /* For each uuid w in the array W, add w to the set m(u, x), but only if u
     * belongs to our window.
     *
     * Do not add if already present. In other words, although we use arrays,
     * we maintain them as sets.
     *
     * return: the number of additions that happened
     */
    addSet({u, x, W}) {
        let count = 0;
        if (this.myWindowHostsUuid(u) && W.length > 0) {
            const W0 = this._get_default(u, x);
            for (let w of W) {
                if (!W0.includes(w)) {
                    W0.push(w);
                    count++;
                }
            }
        }
        return count;
    }

    /* Remove existing definitions from this local component.
     *
     * You may define as many or as few of u, x, w as you wish. Whichever ones you define,
     * we delete from this component any and all triples [u, x, w] where the corresponding
     * variables have the values you set.
     *
     * return: the total number of triples [u, x, w] that were removed from this component
     */
    removeTriples({u, x, w}) {
        // We have a choice about how to implement this method: we can make it efficient,
        // or we can make it simple, uniform, and easily understood. We're opting for the latter,
        // since, in real usage, I will be surprised if the map ever holds as many as twenty entries.
        // We're talking about links from one open panel to another open panel, in PISE. How many
        // of those do you think the user will ever have at once?
        const triplesToRemove = this.getTriples({u, x, w});
        for (const [u1, x1, w1] of triplesToRemove) {
            this._remove_triple(u1, x1, w1);
        }
        return triplesToRemove.length;
    }

    /* Get existing definitions from this local component.
     *
     * You may define as many or as few of u, x, w as you wish. Whichever ones you define,
     * we return from this component any and all triples [u, x, w] where the corresponding
     * variables have the values you set.
     *
     * return: array of triples [u, x, w] that were found in this component
     */
    getTriples({u, x, w}) {
        const uFree = (u === undefined);
        const xFree = (x === undefined);
        const wFree = (w === undefined);
        const allTriples = this._asTriples();
        return allTriples.filter(([u1, x1, w1]) => (
            (uFree || u1 === u) && (xFree || x1 === x) && (wFree || w1 === w)
        ));
    }

    /* Get the value of m(u, x).
     *
     * return: array equal to the value of m(u, x), or empty array if
     *   m(u, x) is undefined
     */
    get({u, x}) {
        return this._get(u, x) || [];
    }

    /* For a given u, get an array of all x for which m(u, x) is defined in
     * this component.
     *
     * return: an array, possibly empty
     */
    getAllXForU({u}) {
        const mu = this.map.get(u);
        if (mu === undefined) {
            return [];
        } else {
            return Array.from(mu.keys());
        }
    }

    /* For a given u, say whether a given w is in m(u, x) for any x.
     * return: boolean
     */
    isInRangeForU({u, w}) {
        const mu = this.map.get(u);
        if (mu === undefined) {
            return false;
        } else {
            for (const W of mu.values()) {
                if (W.includes(w)) {
                    return true;
                }
            }
            return false;
        }
    }

}

/* A GlobalLinkingMap instantiates a local LinkingMapComponent for this window,
 * and provides methods for working with the map globally, across all windows.
 */
export class GlobalLinkingMap {

    /* param hub: We need access to the PISE Hub
     * param name: Pick a name under which the component can be registered as
     *  a handler in the WindowManager. This will happen in each window, and is
     *  how we communicate with all components, across all windows.
     */
    constructor(hub, name) {
        this.hub = hub;
        this.name = name;
        this.localComponent = null;
    }

    activate() {
        this.localComponent = new LinkingMapComponent(this.hub, this.name);
        this.hub.windowManager.addHandler(this.name, this.localComponent);
        this.hub.contentManager.on('localPaneClose', async event => {
            // Purge the target only if its uuid is absent from any other window. It will be present
            // in another window if we are in the process of moving it to that window.
            const existsElsewhere = await this.hub.contentManager.uuidExistsInAnyWindow(
                event.uuid, {excludeSelf: true});
            if (!existsElsewhere) {
                await this.removeTriples({w: event.uuid});
            }
            this.localComponent.removeTriples({u: event.uuid});
        });
        this.hub.contentManager.on('paneMovedToAnotherWindow', async event => {
            await this.noteMovedPanel(event.uuid);
        }, {'await': true});
    }

    // Broadcast and sum the (int or bool) results.
    _broadcastAndSum(funcName, args, options) {
        const handlerDescrip = `${this.name}.${funcName}`;
        return this.hub.windowManager.broadcastAndSum(handlerDescrip, args, options);
    }

    // Broadcast and concatenate the (array) results.
    _broadcastAndConcat(funcName, args, options) {
        const handlerDescrip = `${this.name}.${funcName}`;
        return this.hub.windowManager.broadcastAndConcat(handlerDescrip, args, options);
    }

    // Broadcast and do an "any" (logical disjunction) on the (!! boolified) results.
    _broadcastAndAny(funcName, args, options) {
        const handlerDescrip = `${this.name}.${funcName}`;
        return this.hub.windowManager.broadcastAndAny(handlerDescrip, args, options);
    }

    /* Add the uuid w to the set L(u, x).
     * return: promise resolving with the number of additions that happened
     */
    add(u, x, w, options) {
        return this._broadcastAndSum('add', {u, x, w}, options);
    }

    /* Add the array of W of uuids to the set L(u, x).
     * return: promise resolving with the number of additions that happened
     */
    addSet(u, x, W, options) {
        return this._broadcastAndSum('addSet', {u, x, W}, options);
    }

    /* Remove existing definitions from the global map.
     *
     * You may define as many or as few of u, x, w as you wish. Whichever ones you define,
     * we delete from the global mapping any and all triples [u, x, w] where the corresponding
     * variables have the values you set.
     *
     * return: promise resolving with the total number of triples [u, x, w] that were removed
     */
    removeTriples({u, x, w}) {
        return this._broadcastAndSum('removeTriples', {u, x, w});
    }

    /* Get existing definitions from the global map.
     *
     * You may define as many or as few of u, x, w as you wish. Whichever ones you define,
     * we return from the global mapping any and all triples [u, x, w] where the corresponding
     * variables have the values you set.
     *
     * return: promise resolving with array of triples [u, x, w] that were found
     */
    getTriples({u, x, w}) {
        return this._broadcastAndConcat('getTriples', {u, x, w});
    }

    /* Get the value of L(u, x).
     * return: promise resolving with array (empty array if L(u, x) undefined)
     */
    get(u, x) {
        return this._broadcastAndConcat('get', {u, x});
    }

    /* For a given u, get all x for which L(u, x) is defined.
     * return: promise resolving with array (possibly empty)
     */
    getAllXForU(u) {
        return this._broadcastAndConcat('getAllXForU', {u});
    }

    /* Get all uuids in the range of the global map.
     * return: promise resolving with array
     */
    async range() {
        const T = await this.getTriples({});
        return Array.from(new Set(T.map(t => t[2])));
    }

    /* For a given u, say whether a given w is in L(u, x) for any x.
     * return: promise resolving with boolean
     */
    isInRangeForU(u, w) {
        return this._broadcastAndAny('isInRangeForU', {u, w});
    }

    /* Respond to the event of a panel having been moved to a new window.
     *
     * Our job is to ensure that our distributed design is maintained, meaning
     * that all the map entries for the moved panel have to be moved into the
     * component for that window.
     *
     * In order to achieve this, we remove and re-add all entries (u, x) for
     * the given panel uuid u. Given the way our `add` operation works, this
     * achieves the desired result.
     *
     * return: promise that resolves with the number of x such that (u, x) was
     *  moved.
     */
    async noteMovedPanel(u) {
        const X = await this.getAllXForU(u);
        for (const x of X) {
            const W = await this.get(u, x);
            await this.removeTriples({u, x});
            await this.addSet(u, x, W, {excludeSelf: true});
        }
        return X.length;
    }

}

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
 * uuids in *all* windows, and X is some other set of IDs (of some kind).
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

    constructor(hub) {
        this.hub = hub;
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
    // If this makes m(u) empty, then make m(u) undefined too.
    _delete(u, x) {
        let mu = this.map.get(u);
        if (mu !== undefined) {
            mu.delete(x);
            if (mu.size === 0) {
                this.map.delete(u);
            }
        }
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

    /* Remove the uuid w from the set m(u, x).
     *
     * Fail silently if m(u, x) undefined, or w not in it to begin with.
     *
     * If removal happens, and m(u, x) becomes empty, delete the entry, making
     * m undefined at (u, x).
     *
     * return: true if w was removed, false if not
     */
    remove({u, x, w}) {
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

    /* Remove the uuid w from any and all sets m(u, x) in which it currently occurs.
     *
     * return: the number of removals that happened
     */
    purgeTarget({w}) {
        const places = [];
        for (const [u, mu] of this.map) {
            for (const [x, W] of mu) {
                if (W.includes(w)) {
                    places.push([u, x]);
                }
            }
        }
        for (const [u, x] of places) {
            this.remove({u, x, w});
        }
        return places.length;
    }

    /* Make m(u, x) undefined.
     *
     * return: array equal to the previous value of m(u, x), or empty array if
     *   m(u, x) was already undefined
     */
    delete({u, x}) {
        const W = this._get_default(u, x);
        this._delete(u, x);
        return W;
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
    }

    activate() {
        this.localComponent = new LinkingMapComponent(this.hub);
        this.hub.windowManager.addHandler(this.name, this.localComponent);
        this.hub.contentManager.on('localPaneClose', async event => {
            await this.purgeTarget(event.uuid);
        });
        this.hub.contentManager.on('paneMovedToAnotherWindow', async event => {
            await this.noteMovedPanel(event.uuid);
        }, {'await': true});
    }

    // Broadcast a request to all components (this one included).
    _broadcast(funcName, args) {
        return this.hub.windowManager.broadcastRequest(
            `${this.name}.${funcName}`,
            args,
            {excludeSelf: false}
        );
    }

    // Broadcast and sum the (int or bool) results.
    _broadcastAndSum(funcName, args) {
        const requests = this._broadcast(funcName, args);
        return Promise.all(requests).then(values => values.reduce(
            (a, c) => a + (+c),
            0
        ));
    }

    // Broadcast and concatenate the (array) results.
    _broadcastAndConcat(funcName, args) {
        const requests = this._broadcast(funcName, args);
        return Promise.all(requests).then(values => values.reduce(
            (a, c) => a.concat(c),
            []
        ));
    }

    /* Add the uuid w to the set L(u, x).
     * return: promise resolving with the number of additions that happened
     */
    add(u, x, w) {
        return this._broadcastAndSum('add', {u, x, w});
    }

    /* Add the array of W of uuids to the set L(u, x).
     * return: promise resolving with the number of additions that happened
     */
    addSet(u, x, W) {
        return this._broadcastAndSum('addSet', {u, x, W});
    }

    /* Remove the uuid w from the set L(u, x).
     * return: promise resolving with the number of removals that happened
     */
    remove(u, x, w) {
        return this._broadcastAndSum('remove', {u, x, w});
    }

    /* Remove the uuid w from any and all sets L(u, x) in which it currently occurs.
     * return: promise resolving with the number of removals that happened
     */
    purgeTarget(w) {
        return this._broadcastAndSum('purgeTarget', {w});
    }

    /* Make L undefined at (u, x).
     * return: promise resolving with array giving the old value L(u, x) before
     *  deletion (empty array if it was undefined)
     */
    delete(u, x) {
        return this._broadcastAndConcat('delete', {u, x});
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
            const W = await this.delete(u, x);
            await this.addSet(u, x, W);
        }
        return X.length;
    }

}

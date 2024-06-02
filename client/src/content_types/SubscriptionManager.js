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

import { util as iseUtil } from "../util";

/* Helper for content type managers (like ChartManager and NotesManager) that host
 * content that can be rebuilt (and for which a "subscription" is therefore needed).
 *
 * Content panes hosting content can "subscribe" to that content, so that, when it
 * is rebuilt, these panes can reload it and thereby refresh.
 *
 * This is an abstract base class.
 */
export class SubscriptionManager {

    /*
     * param hub: a ref to the Hub
     * param missingObjHandler: function accepting args (libpath, paneIds, resp), and
     *      taking application-specific steps to clean up after unsubscribing; does not
     *      have to unsubscribe, as we do that here.
     * param reloader: function accepting args (libpath, paneIds, resp), and
     *      taking application-specific steps to refresh after fetching updated info
     *      describing the rebuilt items.
     *
     */
    constructor(hub, {
        missingObjHandler,
        reloader
    }) {
        this.hub = hub;
        this.missingObjHandler = missingObjHandler;
        this.reloader = reloader;

        this.libpathsToSubscribedPaneIds = new iseUtil.LibpathSetMapping();
        this.modpathsToLibpathsHavingSubscribers = new iseUtil.LibpathSetMapping();

        this.hub.socketManager.on('repoBuilt', this.handleRepoBuiltEvent.bind(this));
    }

    /* Subscribe or unsubscribe a pane to/from a libpath.
     *
     * param paneId: the id of the pane
     * param libpath: the libpath
     * param doSubscripe: boolean true to subscribe, false to unsubscribe
     */
    setSubscription(paneId, libpath, doSubscribe) {
        const modpath = iseUtil.getModpathFromTopLevelEntityPath(libpath);
        if (doSubscribe) {
            this.libpathsToSubscribedPaneIds.add(libpath, paneId);
            this.modpathsToLibpathsHavingSubscribers.add(modpath, libpath);
        } else {
            this.libpathsToSubscribedPaneIds.remove(libpath, paneId);
            if (!this.libpathsToSubscribedPaneIds.mapping.has(libpath)) {
                this.modpathsToLibpathsHavingSubscribers.remove(modpath, libpath);
            }
        }
    }

    /* Check whether a pane is subscribed to a libpath.
     */
    checkSubscription(paneId, libpath) {
        return this.libpathsToSubscribedPaneIds.has(libpath, paneId);
    }

    /* Unsubscribe all panes from a given libpath.
     */
    removeAllSubscriptionsForLibpath(libpath) {
        const modpath = iseUtil.getModpathFromTopLevelEntityPath(libpath);
        this.libpathsToSubscribedPaneIds.mapping.delete(libpath);
        this.modpathsToLibpathsHavingSubscribers.remove(modpath, libpath);
    }

    /* Unsubscribe a pane from all libpaths.
     */
    removeAllSubscriptionsForPane(paneId) {
        const libpathsFromWhichToRemove = [];
        for (const libpath of this.libpathsToSubscribedPaneIds.mapping.keys()) {
            if (this.checkSubscription(paneId, libpath)) {
                libpathsFromWhichToRemove.push(libpath);
            }
        }
        for (const libpath of libpathsFromWhichToRemove) {
            this.setSubscription(paneId, libpath, false);
        }
    }

    /* Handle the fact that a repo has been (re)built, by refreshing all subscribers.
     */
    async handleRepoBuiltEvent({ repopath, clean, timestamp }) {
        const libpaths = this.modpathsToLibpathsHavingSubscribers.getUnionOverLibpathPrefix(repopath) || [];
        for (const libpath of libpaths) {
            const {missing, resp} = await this.makeRequest({libpath, clean, timestamp});
            const paneIds = this.libpathsToSubscribedPaneIds.mapping.get(libpath) || [];
            if (missing) {
                this.removeAllSubscriptionsForLibpath(libpath);
                this.missingObjHandler(libpath, paneIds, resp);
            } else {
                this.reloader(libpath, paneIds, resp);
            }
        }
    }

    // --------------------------------------------------------------------------------
    // SUBCLASSES MUST IMPLEMENT

    /* Make some kind of request for the updated version of the product at a given libpath.
     *
     * return: Promise resolving with object of the form {
     *   missing: boolean, saying whether the object turned out not to exist,
     *   resp: the full (application specific) response obtained
     * }
     */
    async makeRequest({ libpath, clean, timestamp }) {}

}

/* Version of SubscriptionManager for loading content from dynamic endpoints.
 */
export class DynamicSubscriptionManager extends SubscriptionManager {

    /*
     * param hub: a ref to the Hub
     * param fetchName: name of the endpoint from which we can request updated info
     *      about rebuilt items to which we are managing subscriptions
     * param fetchArgBuilder: function accepting args (libpath, timestamp), and returning
     *      args object, to be passed to XHR for updated info about rebuilt items
     * param missingObjErrCode: error code we can expect from the fetch endpoint, in
     *      the case the the updated item no longer exists
     * param missingObjHandler: as in base class
     * param reloader: as in base class
     *
     */
    constructor(hub, {
        fetchName, fetchArgBuilder,
        missingObjErrCode, missingObjHandler,
        reloader
    }) {
        super(hub, {missingObjHandler, reloader});
        this.fetchName = fetchName;
        this.fetchArgBuilder = fetchArgBuilder;
        this.missingObjErrCode = missingObjErrCode;
    }

    async makeRequest({ libpath, clean, timestamp }) {
        const fetchArgs = this.fetchArgBuilder(libpath, timestamp);
        const resp = await this.hub.xhrFor(this.fetchName, fetchArgs);
        const missing = (resp.err_lvl === this.missingObjErrCode);
        return {missing, resp};
    }

}

/* Version of SubscriptionManager for loading content from static URLs.
 */
export class StaticSubscriptionManager extends SubscriptionManager {

    /*
     * param hub: a ref to the Hub
     * param staticUrlBuilder: function accepting a libpath and returning the URL
     *      from which the latest version of the corresponding entity can be obtained
     * param fetchContent: boolean. If true, actually fetch the updated content, and
     *      return that as the response, to the `reloader()` function. If false, then
     *      just check for the existence of the content (via HTTP HEAD request), and
     *      return the URL as the response, to `reloader()`.
     * param missingObjHandler: as in base class
     * param reloader: as in base class
     *
     */
    constructor(hub, {
        staticUrlBuilder, fetchContent, missingObjHandler, reloader
    }) {
        super(hub, {missingObjHandler, reloader});
        this.staticUrlBuilder = staticUrlBuilder;
        this.fetchContent = fetchContent;
    }

    async makeRequest({ libpath, clean, timestamp }) {
        const url = this.staticUrlBuilder(libpath);
        const init = {
            method: this.fetchContent ? "GET" : "HEAD",
        };
        const resp = await fetch(url, init);
        const status = resp.status;
        if (!resp.ok) {
            return {
                missing: true,
                resp: status,
            };
        }
        if (this.fetchContent) {
            const text = await resp.text();
            return {
                missing: false,
                resp: text,
            };
        } else {
            return {
                missing: false,
                resp: url,
            };
        }
    }

}

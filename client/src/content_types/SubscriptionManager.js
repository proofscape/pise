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

const dojo = {};

define([
    "ise/util",
], function(
    iseUtil,
) {
    dojo.iseUtil = iseUtil;
});

/* Helper for content type managers (like ChartManager and NotesManager) that host
 * content that can be rebuilt (and for which a "subscription" is therefore needed).
 *
 * Content panes hosting content can "subscribe" to that content, so that, when it
 * is rebuilt, these panes can reload it and thereby refresh.
 */
export class SubscriptionManager {

    /*
     * param hub: a ref to the Hub
     * param fetchName: name of the endpoint from which we can request updated info
     *      about rebuilt items to which we are managing subscriptions
     * param fetchArgBuilder: function accepting args (libpath, timestamp), and returning
     *      args object, to be passed to XHR for updated info about rebuilt items
     * param missingObjErrCode: error code we can expect from the fetch endpoint, in
     *      the case the the updated item no longer exists
     * param missingObjHandler: function accepting args (libpath, paneIds, resp), and
     *      taking application-specific steps to clean up after unsubscribing; does not
     *      have to unsubscribe, as we do that here.
     * param reloader: function accepting args (libpath, paneIds, resp), and
     *      taking application-specific steps to refresh after fetching updated info
     *      describing the rebuilt items.
     *
     */
    constructor(hub, {
        fetchName, fetchArgBuilder,
        missingObjErrCode, missingObjHandler,
        reloader
    }) {
        this.hub = hub;

        this.fetchName = fetchName;
        this.fetchArgBuilder = fetchArgBuilder;
        this.missingObjErrCode = missingObjErrCode;
        this.missingObjHandler = missingObjHandler;
        this.reloader = reloader;

        this.libpathsToSubscribedPaneIds = new dojo.iseUtil.LibpathSetMapping();
        this.modpathsToLibpathsHavingSubscribers = new dojo.iseUtil.LibpathSetMapping();

        this.hub.socketManager.on('moduleBuilt', this.handleModuleBuiltEvent.bind(this));
    }

    /* Subscribe or unsubscribe a pane to/from a libpath.
     *
     * param paneId: the id of the pane
     * param libpath: the libpath
     * param doSubscripe: boolean true to subscribe, false to unsubscribe
     */
    setSubscription(paneId, libpath, doSubscribe) {
        const modpath = dojo.iseUtil.getModpathFromTopLevelEntityPath(libpath);
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
        const modpath = dojo.iseUtil.getModpathFromTopLevelEntityPath(libpath);
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

    /* Handle the fact that a module has been (re)built, by refreshing all subscribers.
     */
    handleModuleBuiltEvent({ modpath, recursive, timestamp }) {
        const libpaths = recursive ?
            this.modpathsToLibpathsHavingSubscribers.getUnionOverLibpathPrefix(modpath) :
            this.modpathsToLibpathsHavingSubscribers.mapping.get(modpath) || [];
        for (const libpath of libpaths) {
            const fetchArgs = this.fetchArgBuilder(libpath, timestamp);
            this.hub.xhrFor(this.fetchName, fetchArgs).then(resp => {
                const paneIds = this.libpathsToSubscribedPaneIds.mapping.get(libpath) || [];
                if (resp.err_lvl === this.missingObjErrCode) {
                    this.removeAllSubscriptionsForLibpath(libpath);
                    this.missingObjHandler(libpath, paneIds, resp);
                } else {
                    this.reloader(libpath, paneIds, resp);
                }
            });
        }
    }

}

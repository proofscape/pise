/* ------------------------------------------------------------------------- *
 *  Copyright (c) 2011-2024 Proofscape Contributors                          *
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

import { WindowPeer } from "browser-peers/src/windowpeer";
import { BroadcastChannelTransport, SocketTransport, ExtensionTransport } from "browser-peers/src/transport";

const dojo = {};

define([
    "dijit/registry",
    "dijit/Menu",
    "dijit/MenuItem",
    "dijit/PopupMenuItem",
    "dijit/MenuSeparator",
], function(
    registry,
    Menu,
    MenuItem,
    PopupMenuItem,
    MenuSeparator,
) {
    dojo.registry = registry;
    dojo.Menu = Menu;
    dojo.MenuItem = MenuItem;
    dojo.PopupMenuItem = PopupMenuItem;
    dojo.MenuSeparator = MenuSeparator;
});

const BASIC_WINDOW_TITLE = 'Proofscape ISE';

export class WindowManager {

    constructor(tct) {
        this.hub = null;
        this.windowPeer = null;
        tct.registerMenuBuilder(this);
        tct.registerMenuOpenListener(this);
    }

    // ------------------------------------------------------------------------------------
    // Convenience methods to forward calls to our windowPeer.

    makeWindowRequest(windowNumber, handlerDescrip, args, options) {
        return this.windowPeer.makeWindowRequest(windowNumber, handlerDescrip, args, options);
    }

    broadcastRequest(handlerDescrip, args, options) {
        return this.windowPeer.broadcastRequest(handlerDescrip, args, options);
    }

    // Broadcast a request, and sum the (int or bool) results.
    broadcastAndSum(handlerDescrip, args, options) {
        const requests = this.broadcastRequest(handlerDescrip, args, options);
        return Promise.all(requests).then(values => values.reduce(
            (a, c) => a + (+c),
            0
        ));
    }

    // Broadcast a request, and concatenate the (array) results.
    broadcastAndConcat(handlerDescrip, args, options) {
        const requests = this.broadcastRequest(handlerDescrip, args, options);
        return Promise.all(requests).then(values => values.reduce(
            (a, c) => a.concat(c),
            []
        ));
    }

    // Broadcast a request, and do an "any" (logical disjunction) on the (!! boolified) results.
    broadcastAndAny(handlerDescrip, args, options) {
        const requests = this.broadcastRequest(handlerDescrip, args, options);
        return Promise.all(requests).then(values => values.some(e => !!e));
    }

    /* Groupcast an event to the window group.
     *
     * @param event: the event to be groupcast
     * @param options: {
     *   includeSelf {bool} true to include this window in the groupcast. (default false)
     *   selfSync {bool} if includeSelf, set this true to dispatch the event to this window
     *     synchronously _instead of_ asynchronously; set false to let this window receive
     *     the event asynchronously, just like all other windows in the group. (default true)
     * }
     */
    groupcastEvent(event, options) {
        const {
            includeSelf = false,
            selfSync = true,
        } = options || {};
        if (includeSelf && selfSync) {
            this.windowPeer.dispatch(event);
        }
        const includeSelfAsync = includeSelf && !selfSync;
        return this.windowPeer.groupcastEvent(event, includeSelfAsync);
    }

    on(eventType, callback) {
        return this.windowPeer.on(eventType, callback);
    }

    off(eventType, callback) {
        return this.windowPeer.off(eventType, callback);
    }

    addHandler(name, handler) {
        this.windowPeer.addHandler(name, handler);
        return this;
    }

    getGroupId() {
        return this.windowPeer.getGroupId();
    }

    // ------------------------------------------------------------------------------------

    /* Check whether a pane location is local or not.
     *
     * @param paneLoc {string} the location to be checked.
     * @return {bool} true if the location is local, false otherwise.
     */
    isLocal(paneLoc) {
        const parts = paneLoc.split(":");
        if (parts.length === 1) return true;
        const myNumber = this.windowPeer.getWindowNumber();
        return parts[0] === `${myNumber}`;
    }

    /* Turn a pane location string into a more easily usable array.
     *
     * @param paneLoc {string} the location to be checked.
     * @return {Array[mixed]}: If the location belongs to the present window,
     *   the array will be of length one, its one entry being the relative pane
     *   location {string} -- so, just a ContentPane ID. If the location does not belong
     *   to the present window, the array will be of length two. The first entry
     *   will be the window number {int}, and the second will be the relative
     *   location {string} within that window.
     */
    digestLocation(paneLoc) {
        const parts = paneLoc.split(":");
        if (parts.length === 1) return parts;
        const myNumber = this.windowPeer.getWindowNumber();
        const givenNumber = +parts[0];
        if (givenNumber === myNumber) return parts.slice(1);
        return [givenNumber, parts[1]];
    }

    /* Ensure that a location is absolute, relative to this window.
     *
     * @param paneLoc {string} the location to be checked.
     * @return {string} If the given location is already absolute, it is
     *   returned unchanged. Otherwise we prefix it with our own window number.
     */
    makeLocationAbsolute(paneLoc) {
        const parts = paneLoc.split(":");
        if (parts.length === 2) return paneLoc;
        const myNumber = this.windowPeer.getWindowNumber();
        return `${myNumber}:${paneLoc}`;
    }

    initializePeer () {
        this.windowPeer = new WindowPeer(null, {
            eventNamePrefix: 'windowPeers',
        });
    }

    setupPeer() {
        const peer = this.windowPeer;
        peer.on('disconnect', event => {
            document.title = BASIC_WINDOW_TITLE;
        });
        peer.on('updateMapping', event => {
            const { myNumber, otherNumbers } = this.getNumbers();
            //console.log(`My window number: ${myNumber}. Others: ${otherNumbers}.`);
            if (otherNumbers.length) {
                document.title = `${BASIC_WINDOW_TITLE} (${myNumber})`;
            } else {
                document.title = BASIC_WINDOW_TITLE;
            }
        });
    }

    broadcastChannelsAreAvailable() {
        return !!window.BroadcastChannel;
    }

    simpleSettleTransport() {
        this.windowPeer.setTransport(new BroadcastChannelTransport({
            eventNamePrefix: 'windowPeers',
        }));
        this.windowPeer.enable();
    }

    delayedSettleTransport(delay, tries) {
        setTimeout(() => {
            this.settleTransport(tries).then(() => {
                this.windowPeer.enable();
            });
        }, delay);
    }

    async settleTransport(tries) {
        let transport = null;

        // We used to use the PBE as an optional transport, but now even Safari (as of v15.4)
        // supports the BroadcastChannel API, so we've eliminated that functionality from the PBE.
        // Therefore the attempt is shut off here. (Saving the code in case we want to reinstate.)
        //
        // Meanwhile, the potential to use the SocketTransport remains always interesting, since
        // this expands capabilities beyond what the BroadcastChannel can offer; namely, it
        // allows communication across different hosts.
        const tryExtension = false;
        if (tryExtension) {
            let n = 0;
            let seeExtension = false;
            while (!seeExtension && n++ < tries) {
                seeExtension = this.hub.pfscExtInterface.extensionAppearsToBePresent();
                if (!seeExtension) await new Promise(r => setTimeout(r, 100));
            }

            if (seeExtension) {
                await this.hub.pfscExtInterface.makeRequest('get-window-name', {}, {timeout: 1000})
                    .then(windowName => {
                        //console.log(`windowName: ${windowName}`);
                        transport = new ExtensionTransport(
                            windowName, 'pfsc-ext', 'pbeWindowGroupServer'
                        );
                    })
                    .catch(reason => {
                        console.error(reason);
                        // For whatever reason, it didn't work. We give up, and will use socket transport instead.
                    });
            }
        }

        if (!transport) {
            transport = new SocketTransport(this.hub.socketManager.socket)
        }

        this.windowPeer.setTransport(transport);
    }

    activate() {
        this.initializePeer();
        this.setupPeer();
        this.windowPeer
            .addHandler('hub', this.hub)
            .setReady();
        // Safari still does not support BroadcastChannels, so we check for their presence
        // and choose the transport accordingly.
        if (this.broadcastChannelsAreAvailable()) {
            this.simpleSettleTransport();
        } else {
            this.delayedSettleTransport(100, 9);
        }
    }

    getNumbers() {
        const peer = this.windowPeer;
        const numbers = peer.getAllWindowNumbers();
        const myNumber = peer.getWindowNumber();
        const otherNumbers = numbers.filter(n => n !== myNumber);
        return {
            myNumber: myNumber,
            otherNumbers: otherNumbers,
            allNumbers: numbers,
        };
    }

    isAlone() {
        const a = this.windowPeer.getAllWindowNumbers()
        return a.length < 2;
    }

    buildTabContainerMenu(menu) {
        const moveSubMenu = new dojo.Menu();
        const moveOption = new dojo.PopupMenuItem({
            label: "Move to window...",
            popup: moveSubMenu,
            disabled: true,
        });
        menu.addChild(moveOption);
        menu.addChild(new dojo.MenuSeparator());
        // Stash objects in the Menu instance.
        // We give them names with "pfsc_ise" prefix in order to keep them in a presumably
        // safe namespace, where they will not collide with anything in Dojo.
        menu.pfsc_ise_windowManager_moveSubMenu = moveSubMenu;
        menu.pfsc_ise_windowManager_moveOption = moveOption;
    }

    noteTabContainerMenuOpened(menu, clicked) {
        const { myNumber, otherNumbers, allNumbers } = this.getNumbers();
        const button = dojo.registry.byNode(clicked.currentTarget);
        const pane = button.page;
        const windowMgr = this;
        const moveSubMenu = menu.pfsc_ise_windowManager_moveSubMenu;
        const moveOption = menu.pfsc_ise_windowManager_moveOption;
        if (otherNumbers.length) {
            moveSubMenu.destroyDescendants();
            for (let n of allNumbers) {
                const item = new dojo.MenuItem({
                    label: `${n}`,
                    disabled: n === myNumber,
                    onClick: () => {
                        windowMgr.hub.contentManager.movePaneToAnotherWindow(pane, n);
                    }
                });
                moveSubMenu.addChild(item);
            }
            moveOption.set('disabled', false);
        } else {
            moveOption.set('disabled', true);
        }
    }

}

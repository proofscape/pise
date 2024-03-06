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


const io = require("socket.io-client");
import { v4 as uuid4 } from 'uuid';
const LRU = require("lru-cache");
import { Peer } from "browser-peers/src/peer";
import { enrichXhrParams } from "browser-peers/src/util";

const WEBSOCKET_NAMESPACE = '/pfsc-ise';

export class SocketManager extends Peer {

    constructor (ISE_state) {
        super('socketManager');
        this.hub = null;
        this.socket = null;
        this.cookie = {};

        // We keep a history of up to 5 of our most recent SIDs.
        // This is for robustness in case the socket connection is broken and reestablished
        // between the time we make a request, and receive a response. In such a case, the
        // history allows us to see that the message was intended for us.
        this.ids = new LRU({max: 5});
        // We initialize our history with at least one ID, in case `Hub.restoreState()` issues
        // any requests that require an SID before our socket has obtained one. Although this ID
        // is phony, it will serve the purpose of acting as a recipient ID.
        this.recordId(uuid4());

        // Open WebSocket connection
        const url = location.protocol + '//' + document.domain + ':' + location.port + WEBSOCKET_NAMESPACE;
        //console.log("url: ", url);
        // If `noSocket` defined in given state, do not connect. Useful for testing.
        if (typeof ISE_state.noSocket === 'undefined') {
            this.initializeConnection(url, ISE_state.appUrlPrefix);
        }
    }

    recordId (id) {
        this.ids.set(id, true);
    }

    formatSocketId (socketId) {
        /* In v2.x of the socketio client, the `id` would be of the form
         *   /NAMESPACE#HASH
         * and we wanted just the HASH, so we split on "#" and took the last part.
         * In v4.x (have not experimented with v3.x), the `id` is just a HASH.
         * The following code works for both versions.
         */
        return socketId.split("#").slice(-1)[0];
    }

    /* Get our socket ID, optionally blocking until it is ready or
     * throwing an Error if it does not become ready in time.
     *
     * @param block: number of milliseconds to block for an ID.
     *   If zero, and if we do not have a socket ID right now, then
     *   will return most recent ID from our history.
     *
     * @return: promise that resolves with the ID, or rejects if it
     *   could not be obtained in the allowed blocking time.
     */
    getId (block = 0) {
        if (this.socket.id) {
            return Promise.resolve(this.formatSocketId(this.socket.id));
        } else if (block > 0) {
            return new Promise((resolve, reject) => {
                block = Math.max(block, 200);
                let timeoutHandle = null;
                const intervalHandle = window.setInterval(() => {
                    if (this.socket.id) {
                        window.clearTimeout(timeoutHandle);
                        window.clearInterval(intervalHandle);
                        resolve(this.formatSocketId(this.socket.id));
                    }
                }, 100);
                timeoutHandle = window.setTimeout(() => {
                    window.clearInterval(intervalHandle);
                    reject('Could not obtain a socket ID.');
                }, block);
            });
        }
        return Promise.resolve(this.ids.keys()[0]);
    }

    /* Wrapper for the Hub's `xhr` function, which ensures that this
     * SocketManager's SID is set as the value of an "SID" argument.
     *
     * The "SID" argument is placed in `query` if that is defined, else
     * in `form` if that is defined. If neither is defined, then we define
     * `query` and put the "SID" argument in there.
     *
     * @param url: as for the basic `xhr` function.
     * @param params: as for the basic `xhr` function.
     * @param block: number of milliseconds to block, waiting for a socket connection.
     *   If it is critical that we actually have a socket connection before
     *   this request is issued, this should be positive.
     */
    xhr (url, params, block = 7000) {
        return this.getId(block).then(sid => {
            params = enrichXhrParams(params, {"SID": sid});
            return this.hub.xhr(url, params);
        });
    }

    xhrFor (role, params, block = 7000) {
        const url = this.hub.urlFor(role);
        return this.xhr(url, params, block);
    }

    initializeConnection (url, path_prefix) {
        path_prefix = path_prefix || '';
        let opts = {
            path: path_prefix + '/socket.io',
            // If you need to disallow websockets, can do so like this:
            // transports: ['polling'],
            reconnectionAttempts: 24,
        }
        this.socket = io.connect(url, opts);
        this.defineEventHandlers();
    }

    defineEventHandlers () {
        const socket = this.socket,
            manager = this;
        socket.on('connect', function() {
            //console.log("Opened WebSocket connection.", socket.id);
            manager.recordId(manager.formatSocketId(socket.id));
        });

        socket.on('iseEvent', function({ type, recipSID, msg }) {
            // recipSID === null means this is a groupcast event, intended for
            // action by all windows; otherwise, we should act only if recipSID
            // is in our ID history.
            if (recipSID === null || manager.ids.has(recipSID)) {
                switch (type) {
                    case 'console':
                        console.log(msg);
                        break;
                    case 'job_enqueued':
                        //console.debug(Date.now(), 'job_enqueued:', msg);
                        break;
                    case 'progress':
                        //console.debug(msg.job, msg.message, msg.fraction_complete);
                        manager.hub.feedbackManager.noteProgress(msg);
                        break;
                    case 'listenable':
                        //console.debug('SocketManager recd listenable:', msg);
                        manager.dispatch(msg);
                        break;
                    case 'delayed':
                        //console.debug('SocketManager recd delayed:', msg);
                        // A delayed response is always considered a "successful" response;
                        // it is up to any listeners to handle error messages that may reside
                        // therein. So this case just drops through to the `success` case.
                    case 'success':
                        manager.handleSuccessMessage(msg);
                        break;
                    case 'error':
                        manager.handleErrorMessage(msg);
                        break;
                    default:
                        console.log('Unknown socket event type: ', type, msg);
                }
            }
        });
    }

    handleSuccessMessage (msg) {
        if (msg.cookie) Object.assign(this.cookie, msg.cookie);
        if (msg.orig_req) {
            const seqNum = +msg.orig_req.event_num; // convert back from str to int
            const wrapper = {
                seqNum: seqNum,
                result: msg,
            };
            this.handleResponse(wrapper);
        }
    }

    handleErrorMessage (msg) {
        // Forward message to errback, if any.
        if (msg.orig_req) {
            const seqNum = +msg.orig_req.event_num; // convert back from str to int
            const wrapper = {
                seqNum: seqNum,
                rejection_reason: JSON.stringify(msg),
            };
            this.handleResponse(wrapper);
        }
    }

    /* General purpose function for emitting an event.
     *
     * @param event {string} the name of the event to be emitted
     * @param message {obj} the message to send along with the event
     *
     * @return: promise that resolves on success or rejects on error.
     */
    emit (event, message = {}) {
        message.CSRF = this.hub.getCsrfToken();
        return this.makeRequest('', '', {
            event: event,
            message: message,
        });
    }

    makeCookie(message) {
        // Start with a copy of our cookie.
        let cookie = JSON.parse(JSON.stringify(this.cookie));
        // Allow any cookie provided in the message to override.
        if (message.cookie) {
            // Is it a complete overwrite?
            if (message.overwriteCookie) {
                cookie = {};
            }
            Object.assign(cookie, message.cookie);
        }
        return cookie;
    }

    postMessageAsPeer(peerName, wrapper) {
        const args = wrapper.args;
        if (args.event === 'splitXhr') {
            args.callback(wrapper.seqNum);
        } else {
            args.message.event_num = wrapper.seqNum;
            args.message.cookie = this.makeCookie(args.message);
            this.socket.emit(args.event, args.message);
        }
    }

    /* Perform a "split XHR". This means that we expect an immediate response as
     * with a normal XHR, but we also anticipate a possible delayed response as
     * well.
     *
     * @param url: as for the basic `xhr` function.
     * @param params: as for the basic `xhr` function, except that it _must not_
     *   already have an `event_num` property, since we will override that for
     *   internal processing.
     * @param block: as for `SocketManager.xhr`.
     * @return: promise that resolves with an object of the form: {
     *   immediate: the immediate XHR response, as normal,
     *   delayed: either a promise that will resolve with the delayed response, if
     *     one is expected, or else `null` if we are not to expect a delayed response.
     * }
     */
    splitXhr (url, params, block=7000) {
        let delayedPromise;
        return new Promise(resolve => {
            delayedPromise = this.makeRequest('', '', {event: 'splitXhr', callback: resolve});
        }).then(seqNum => {
            params = enrichXhrParams(params, {"event_num": seqNum});
            return this.xhr(url, params, block).then(resp => {
                if (!resp.job_id) {
                    // There will be no delayed response.
                    this.consumeRequestData(seqNum);
                    delayedPromise = null;
                }
                return {
                    immediate: resp,
                    delayed: delayedPromise,
                };
            });
        });
    }

    splitXhrFor (role, params, block = 7000) {
        const url = this.hub.urlFor(role);
        return this.splitXhr(url, params, block);
    }

}

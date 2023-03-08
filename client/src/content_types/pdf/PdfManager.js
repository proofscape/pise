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


const LRU = require("lru-cache");
import {
    FetchResolvedNotOkError,
    ExtensionUnavailableError,
    LackingHostPermissionError,
} from "browser-peers/src/errors";
import {
    GlobalLinkingMap,
} from "../linking";

define([
    "dojo/_base/declare",
    "dojo/dom-construct",
    "dijit/Dialog",
    "ise/content_types/AbstractContentManager",
    "ise/content_types/pdf/PdfController",
    "ise/errors"
], function(
    declare,
    domConstruct,
    Dialog,
    AbstractContentManager,
    PdfController,
    pfscErrors
) {

/* PdfManager class
 *
 * In order to view PDFs in Proofscape we use our fork of Mozilla's pdf.js.
 * This manager class is for keeping track of panes in which we have iframes
 * hosting instances thereof.
 *
 * Note: If you are wondering how pdf.js can re-open PDFs to the same place
 * where you left off, it uses localStorage. If you look in localStorage you
 * will find the key `pdfjs.history`.
 *
 */
var PdfManager = declare(AbstractContentManager, {

    // Properties

    localPdfLibraryUrlPrefix: null,

    hub: null,
    panesById: null,
    pdfcsByPaneId: null,

    pdfProxyServiceEnabled: false,
    // LRU cache for PDF info by URL
    pdfInfoByURL: null,
    // Pending PDF promises by URL
    pdfPromisesByURL: null,
    // Mapping from global PDF URLs to local URLs.
    // (We distinguish between "local" URLs which are relative and point into the
    // server's PDF library, and "global" URLs which point to any location on the web.)
    pdfGlobalUrl2LocalUrl: null,

    navEnableHandlers: null,

    // Our GlobalLinkingMap instance.
    // The "secondary IDs" ("x" in method calls) are highlight supplier libpaths.
    linkingMap: null,

    // For now, we're simply shutting off dynamic linking (linking to highlight supplier
    // panels when they become active) by setting this false. Could some day want to revive
    // some of this functionality, maybe in a user-configurable way?
    doDynamicLinking: false,

    // Methods

    constructor: function(ISE_state) {
        this.panesById = {};
        this.pdfcsByPaneId = {};
        // In-memory cache is necessary if no PBE, but is also much faster than PBE cache,
        // so still advantageous in that case as well.
        // For now we set (arbitrarily) at 50 MB. In future must make this configurable.
        // See <https://www.npmjs.com/package/lru-cache> for LRU cache config documentation.
        this.pdfInfoByURL = new LRU({
            max: 50 * 1048576,
            length: (n, key) => n.size,
            updateAgeOnGet: true,
        });
        this.pdfProxyServiceEnabled = ISE_state.enablePdfProxy;
        this.pdfPromisesByURL = new Map();
        this.pdfGlobalUrl2LocalUrl = new Map();
        this.navEnableHandlers = [];
    },

    activate: function() {
        this.localPdfLibraryUrlPrefix = this.hub.urlFor('static') + "/PDFLibrary/";
        this.hub.windowManager.on('newlyActiveHighlightSupplierPanel',
            this.onNewlyActiveHighlightSupplierPanel.bind(this));
        this.hub.windowManager.on('linkingMapNewlyUndefinedAt',
            this.onLinkingMapNewlyUndefinedAt.bind(this));
        this.initLinking();
    },

    initLinking: function() {
        const name = 'linking_docs';
        this.linkingMap = new GlobalLinkingMap(this.hub, name);
        this.linkingMap.activate();
    },

    retryPausedDownloads: function() {
        for (let id in this.pdfcsByPaneId) {
            let pdfc = this.pdfcsByPaneId[id];
            if (pdfc.pausedOnDownload) {
                pdfc.retryDownload();
            }
        }
    },

    addNavEnableHandler: function(callback) {
        this.navEnableHandlers.push(callback);
    },

    publishNavEnable: function(data) {
        this.navEnableHandlers.forEach(cb => {
            cb(data);
        });
    },

    /* Initialize a ContentPane with content of this manager's type.
     *
     * param info: An info object, indicating the content that is to be initialized.
     * param elt: The DOM element to which the content is to be added.
     * param pane: The ContentPane in which `elt` has already been set. This is provided
     *             mainly with the expectation that this manager will use `pane.id` as an
     *             index under which to store any data that will be required in order to
     *             do further management of the contents of this pane, e.g. copying.
     *             The entire ContentPane (not just its id) is provided in case this is useful.
     * return: promise that resolves when the content is loaded.
     */
    initContent: function(info, elt, pane) {
        const url = this.hub.pdfjsURL;
        console.debug('Load pdfjs from:', url);
        const iframe = domConstruct.toDom(`
            <iframe
                width="100%"
                height="100%"
                src="${url}">
            </iframe>
        `);
        elt.appendChild(iframe);
        this.panesById[pane.id] = pane;
        const pdfc = new PdfController(this, pane, info);
        this.pdfcsByPaneId[pane.id] = pdfc;
        return pdfc.initialize();
    },

    /* Update the content of an existing pane of this manager's type.
     *
     * param info: An info object indicating the desired content.
     * param paneId: The ID of the ContentPane that is to be updated.
     * return: nothing
     */
    updateContent: function(info, paneId) {
        const pdfc = this.pdfcsByPaneId[paneId];
        pdfc.requestState(info);
    },

    /* Write a serializable info object, completely describing the current state of a
     * given pane of this manager's type. Must be understandable by this manager's
     * own `initContent` and `updateContent` methods. Must contain `type` field.
     *
     * param oldPaneId: The id of an existing ContentPane of this manager's type.
     * param serialOnly: boolean; set true if you want only serializable info.
     * return: The info object.
     */
    writeStateInfo: function(oldPaneId, serialOnly) {
        var pdfc = this.pdfcsByPaneId[oldPaneId];
        var info = pdfc.describeState(serialOnly);
        // Make sure it has a type property:
        info.type = "PDF";
        return info;
    },

    /* Take note of the fact that one pane of this manager's type has been copied to a
     * new one. This may for example be relevant if we want the view or selection, say, in
     * the two panes to track one another.
     *
     * param oldPaneId: The id of the original pane.
     * param newPaneId: The id of the new pane.
     * return: nothing
     */
    noteCopy: function(oldPaneId, newPaneId) {
    },

    /* Take note of the fact that a pane of this manager's type is about to close.
     *
     * param closingPane: The ContentPane that is about to close.
     * return: nothing
     */
    noteClosingContent: function(closingPane) {
        var id = closingPane.id;
        delete this.panesById[id];
        delete this.pdfcsByPaneId[id];
    },

    /*
     * Move "forward" or "backward" in the content. What this means is dependent upon
     * the particular type of content hosted by panes of this manager's type.
     *
     * param pane: the pane in which navigation is desired
     * param direction: integer indicating the desired navigation direction:
     *   positive for forward, negative for backward, 0 for no navigation. Passing 0 serves
     *   as a way to simply check the desired enabled state for back/fwd buttons.
     * return: Promise that resolves with a pair of booleans indicating whether back resp.
     *   fwd buttons should be enabled for this pane _after_ the requested navigation takes place.
     */
    navigate: function(pane, direction) {
        const pdfc = this.pdfcsByPaneId[pane.id];
        const history = pdfc.history;
        if (history === null) {
            return Promise.resolve([false, false]);
        }
        const controller = history.history;
        if (direction < 0 && controller.canGoBackward()) {
            history.back();
        } else if (direction > 0 && controller.canGoForward()) {
            history.forward();
        }
        return Promise.resolve([controller.canGoBackward(), controller.canGoForward()]);
    },

    /*
     * param theme: `light` or `dark`
     */
    setTheme: function(theme) {
        for (let id in this.pdfcsByPaneId) {
            var pdfc = this.pdfcsByPaneId[id];
            pdfc.setTheme(theme);
        }
    },

    /* Pass a PDF fingerprint. We return an array of the panes where
     * that PDF document is open, if any.
     */
    findPanesByFingerprint: function(fp) {
        var panes = [];
        for (var id in this.pdfcsByPaneId) {
            var pdfc = this.pdfcsByPaneId[id];
            if (pdfc.fingerprint === fp) panes.push(this.panesById[id]);
        }
        return panes;
    },

    /* Get array of all panes in which there is currently a selection, i.e. there
     * are one or more selection boxes.
     */
    findPanesWithSelection: function() {
        var panes = [];
        for (var id in this.pdfcsByPaneId) {
            var pdfc = this.pdfcsByPaneId[id];
            if (pdfc.getSelectionBoxes().length > 0) panes.push(this.panesById[id]);
        }
        return panes;
    },

    getPdfcForPane: function(pane) {
        return this.pdfcsByPaneId[pane.id];
    },

    /* Given an array of panes, return the PdfController for the most recently
     * active one. If the array is empty, return null.
     */
    getMostRecentPdfcAmongPanes: function(panes) {
        var recentPane = this.hub.tabContainerTree.findMostRecentlyActivePane(panes);
        return recentPane ? this.getPdfcForPane(recentPane) : null;
    },

    /* If one or more panes are open with the PDF of a given fingerprint,
     * return the PdfController for the most recently active pane among these.
     * Otherwise return null.
     */
    getMostRecentPdfcForFingerprint: function(fp) {
        var panes = this.findPanesByFingerprint(fp);
        return this.getMostRecentPdfcAmongPanes(panes);
    },

    /* If one or more panes currently have a selection, i.e. have one or more
     * selection boxes in them, then return the PdfController for the most
     * recently active pane among these.
     * Otherwise return null.
     */
    getMostRecentPdfcWithSelection: function() {
        var panes = this.findPanesWithSelection();
        return this.getMostRecentPdfcAmongPanes(panes);
    },

    /*
     * Get the byte array for a PDF by its URL.
     *
     * If we have already retrieved that one and have it in our in-memory cache, just
     * return the version that we have.
     *
     * Otherwise turn to various methods to try to obtain it, and store it in the cache:
     * We first look for the PBE. If present, we use that.
     * If not, then we simply try to fetch the PDF. This will work if it comes from the ISE server's origin,
     * or from a provider who has elected to send the ACAO* header.
     * If that fails, use the server's proxy service if enabled.
     * Otherwise it's time to give up.
     *
     * param url: {string} the URL of the desired PDF. May be a relative URL pointing into the ISE server's origin,
     *   or may point anywhere on the web.
     * param loadingPromise: {Promise} optional. Callers may wish to provide a Promise representing their intention
     *   to open and display the PDF, or otherwise do something useful with it. If so, we will use this to defer
     *   certain costly bookkeeping activities (namely PBE cache storage) until after the caller has finished doing
     *   what they want with the PDF. This can make for a more responsive app.
     * return: Promise that EITHER resolves with an object of the form:
     *  {
     *   REQUIRED:
     *     url: <string> the URL of the PDF
     *     bytes: <Uint8Array> the byte array (i.e. content) of the PDF
     *     size: <int> length of `bytes`
     *     source: <string> a code word indicating where the PDF came from. See below for possible values.
     *   OPTIONAL:
     *     comment: <string> user's comment (if any) on the PDF's entry in the PBE cache (set via PBE options page)
     *     accessUrl: <string> the URL of a page from which the PDF can be obtained manually (by clicking sth)
     *  }
     * or ELSE rejects, indicating that none of our automated means of obtaining a PDF could succeed.
     *
     * Possible values of the `source` attribute are:
     *   "mem-cache":   came from the PdfManager's in-memory cache
     *   "lib-fetch":   fetched from the server's PDF library
     *   "web-fetch":   fetched from somewhere else on the web (with ACAO* header)
     *   "ext-fetch":   came from PBE, which had to fetch it from the Internet
     *   "ext-mem":     came from PBE, which had already fetched it, but not yet committed it to storage
     *   "ext-cache":   came from PBE, which retrieved it from storage
     *   "proxy-fetch": fetched from the web by the server's proxy service
     *   "proxy-cache": came from proxy service, but was already in its PDF library
     */
    getPdfByteArray: function(url, loadingPromise) {
        loadingPromise = loadingPromise || Promise.resolve();
        // First check if we have it in the cache, either under the given URL itself, or possibly
        // under a local version to which the given global URL might have been translated.
        const info = this.pdfInfoByURL.get(url) || this.pdfInfoByURL.get(this.pdfGlobalUrl2LocalUrl.get(url));
        if (info) {
            info.source = 'mem-cache';
            return Promise.resolve(info);
        }
        // We don't have it in the cache. If there is a pending promise for this URL, return that; else
        // initiate a new promise representing an attempt to obtain the PDF by any means available to us.
        return this.pdfPromisesByURL.get(url) || this.getPdfByAnyMeans(url, loadingPromise);
    },

    getPdfByAnyMeans: function(url, loadingPromise) {
        const mgr = this;
        const p = Promise.resolve().then(() => {
            return mgr.getPdfFromPbe(url, loadingPromise).catch(reason1 => {
                /* If any of our methods fails due to an HTTP error, we want to quit and alert the
                 * user immediately. There's no sense trying additional methods if e.g. the URL is
                 * just wrong and we're getting 404's. */
                //console.log('reason1: ', reason1);
                pfscErrors.throwIfHttpError(reason1);
                /* We also want to stop immediately if we have the PBE but it currently lacks
                   the necessary host permission for the given URL. */
                if (reason1 instanceof LackingHostPermissionError) throw reason1;
                return mgr.getPdfFromDirectFetch(url).catch(reason2 => {
                    //console.log('reason2: ', reason2);
                    pfscErrors.throwIfHttpError(reason2);
                    return mgr.getPdfFromProxyService(url).catch(reason3 => {
                        //console.log('reason3: ', reason3);
                        pfscErrors.throwIfHttpError(reason3);
                        /* If we got this far, none of the methods appears to have encountered an HTTP error.
                         * If all of the errors appear to have been merely of the "insufficient services"
                         * type, then we throw such an error. Otherwise at least one unanticipated error
                         * occurred, and we throw the first one of those that we identify.
                         */
                        throw mgr.interpretPdfDownloadFailures(reason1, reason2, reason3);
                    });
                });
            });
        }).finally(() => {
            mgr.pdfPromisesByURL.delete(url);
        });
        mgr.pdfPromisesByURL.set(url, p);
        return p;
    },

    /*
     * The purpose of this method is to determine exactly which error we want to throw,
     * in the case that none of our PDF download methods succeeded.
     * It is assumed at this point that none of the errors was a mere HTTP error.
     */
    interpretPdfDownloadFailures: function(reason1, reason2, reason3) {
        const insufficientServiceErrors = [];

        if (reason1 instanceof pfscErrors.PfscInsufficientPdfServiceError) insufficientServiceErrors.push(reason1);
        else return reason1;

        /* As for reason2, if the direct attempt to fetch the PDF failed, and not due to a normal
         * HTTP error, I think it's good to just assume it's an insufficient service. It was just a shot
         * in the dark anyway (hoping the server would offer the ACAO* header). And it seems risky to
         * rely on the error messages we've identified in Chrome and Firefox, which could easily change
         * in future versions, without warning. Those messages are quite generic anyway, and don't
         * actually mention anything specific to CORS. */
        insufficientServiceErrors.push(reason2);

        if (reason3 instanceof pfscErrors.PfscInsufficientPdfServiceError) insufficientServiceErrors.push(reason3);
        else return reason3;

        // Bundle all three errors under an umbrella error. May be useful during development.
        const e = new pfscErrors.PfscInsufficientPdfServiceError("Insufficient services");
        for (let se of insufficientServiceErrors) {
            e.addSubError(se);
        }
        return e;
    },

    getPdfFromPbe: function(url, loadingPromise) {
        const mgr = this;
        return new Promise((resolve, reject) => {
            if (mgr.hub.pfscExtInterface.extensionAppearsToBePresent()) {
                mgr.hub.pfscExtInterface.checkExtensionPresence({})
                    .catch(reason => {
                        reject(new pfscErrors.PfscInsufficientPdfServiceError(reason.message));
                    })
                    .then(vers => {
                        /* If we successfully got a version number from the extension, then the extension must still
                         * be present. So now we can make the request for the PDF, and set no timeout,
                         * i.e. we will wait indefinitely. This is important since large PDFs may legitimately
                         * take a long time to load. */
                        mgr.hub.pfscExtInterface.makeRequest("request-pdf", { url: url }, {timeout: 0}).then(info => {
                            info.source = info.fromCache ? 'ext-cache' : info.fromMemory ? 'ext-mem' : 'ext-fetch';
                            delete info.fromCache;
                            // Even when using the PBE, which has its own cache, we still want to
                            // cache the PDF info in memory, since access is _much_ faster.
                            mgr.pdfInfoByURL.set(url, info);
                            // Wait until after the loadingPromise resolves to store the PDF.
                            console.debug('awaiting loading promise...');
                            loadingPromise.then(function() {
                                console.debug('loading promise resolved');
                                mgr.hub.pfscExtInterface.makeRequest("complete-delayed-pdf-storage", { url: url });
                            });
                            resolve(info);
                        }).catch(reject);
                    });
            } else {
                reject(new pfscErrors.PfscInsufficientPdfServiceError('PBE is not present.'));
            }
        });
    },

    basicPdfFetch: function(url) {
        return fetch(url).then(resp => {
            if (!resp.ok) {
                throw new FetchResolvedNotOkError(resp);
            }
            return resp.arrayBuffer().then(buffer => new Uint8Array(buffer));
        });
    },

    getPdfFromDirectFetch: function(url) {
        const mgr = this;
        return this.basicPdfFetch(url).then(byteArray => {
            const info = {
                url: url,
                bytes: byteArray,
                size: byteArray.length,
                source: url.startsWith(mgr.localPdfLibraryUrlPrefix) ? 'lib-fetch' : 'web-fetch',
            };
            // Store in cache.
            mgr.pdfInfoByURL.set(url, info);
            return info;
        });
    },

    getPdfFromProxyService: function(url) {
        const mgr = this;
        return new Promise((resolve, reject) => {
            if (mgr.pdfProxyServiceEnabled) {
                mgr.hub.socketManager.emit("proxy_get_pdf", { url: url }).then(msg => {
                    // Record the mapping from global to local URL.
                    mgr.pdfGlobalUrl2LocalUrl.set(url, msg.local_url);
                    // Resolve the pending promise.
                    resolve(mgr.basicPdfFetch(msg.local_url).then(byteArray => {
                        const info = {
                            url: url,
                            bytes: byteArray,
                            size: byteArray.length,
                            source: msg.download ? 'proxy-fetch' : 'proxy-cache',
                            accessUrl: msg.access_url,
                        };
                        // Store in cache.
                        mgr.pdfInfoByURL.set(url, info);
                        return info;
                    }));
                }).catch(reason => {
                    const msg = JSON.parse(reason.message);
                    let e = new Error(msg.err_msg);
                    switch (msg.err_lvl) {
                        case pfscErrors.serverSideErrorCodes.DOWNLOAD_FAILED:
                            e = new pfscErrors.PfscHttpError(msg.err_msg);
                            break;
                        case pfscErrors.serverSideErrorCodes.BAD_URL:
                        case pfscErrors.serverSideErrorCodes.PDF_PROXY_SERVICE_DISABLED:
                            e = new pfscErrors.PfscInsufficientPdfServiceError(msg.err_msg);
                            break;
                    }
                    reject(e);
                });
            } else {
                reject(new pfscErrors.PfscInsufficientPdfServiceError('Proxy service not enabled.'));
            }
        });
    },

    /*
     * Just in case something goes wrong and there is a leftover PDF promise, preventing
     * us from making another attmept, you can manually clear them all this way.
     * To be clear, this method is intended for manual use during development, and
     * might not be (and at time of writing is not) invoked programmatically anywhere.
     */
    clearPdfRequests: function() {
        this.pdfPromisesByURL.clear();
    },

    /*
     * Clear the PDF cache.
     */
    clearPdfCache: function() {
        this.pdfInfoByURL.reset();
    },

    /* Show a dialog box noting that a PDF is missing.
     *
     * @param message {string} a message describing the problem.
     * @param fingerprint {string} the fingerprint of the missing PDF.
     */
    showPdfMissingDialog: function(message, fingerprint) {
        const info = this.hub.chartManager.pdfInfoByFingerprint.get(fingerprint) || {};
        if (!info.fingerprint) info.fingerprint = fingerprint;
        //console.log(message, info);
        let content = `<div>${message}</div>`;

        const fields = [
            ['title', "Title"],
            ['author', "Author"],
            ['year', "Year"],
            ['publisher', 'Publisher'],
            ["ISBN", "ISBN"],
            ['eBookISBN', 'eBookISBN'],
            ["DOI", "DOI"],
            ['fingerprint', 'fingerprint'],
        ];
        const rows = [];
        for (let [field, fieldName] of fields) {
            if (info.hasOwnProperty(field)) {
                rows.push(`<tr><td>${fieldName}</td><td>${info[field]}</td></tr>`);
            }
        }
        content += `<table class="pdfInfo">${rows.join('\n')}</table>\n`;

        const pdfUrl = info.url;
        const aboutUrl = info.aboutUrl;

        if (pdfUrl) {
            content += `<div class="vpadded5">
                <a href="#" class="pdfDownloadLink">Download</a> from ${pdfUrl}
            </div>`;
        }

        if (aboutUrl) {
            const introText = pdfUrl ? "More info:" : "It may be available from:";
            content += `<div class="vpadded5">
                ${introText} <a target="_blank" class="external" href="${aboutUrl}">${aboutUrl}</a>
            </div>`;
        }

        content = `<div class="padded20">${content}</div>`;
        const dlg = new Dialog({
            title: "Need PDF",
            content: content,
        });

        if (pdfUrl) {
            dlg.domNode.querySelector('.pdfDownloadLink').addEventListener('click', event => {
                dlg.hide();
                this.hub.contentManager.openContentInActiveTC({
                    type: "PDF",
                    url: pdfUrl,
                });
            });
        }

        dlg.show();
    },

    onNewlyActiveHighlightSupplierPanel: async function({uuid, docIds}) {
        // Are we actually interested in dynamic linking?
        if (!this.doDynamicLinking) {
            return;
        }

        // For now, we request the lists of highlights from the new supplier for any docIds
        // that are currently open, and load these into those docs without question.
        // In the future, we may make this more selective if we have developed systems, e.g.
        // via drag and drop, whereby the user can form a more permanent link between a given
        // document panel, and a given supplier.

        // Build a mapping from docId's to PdfController instances.
        // The docId's must:
        //  - be in the incoming `docIds` list, and
        //  - be hosted by an existing PdfController that doesn't already have
        //    the highlights from the supplier of the given `uuid`.
        const controllersByDocId = new Map();
        for (const pdfc of Object.values(this.pdfcsByPaneId)) {
            const docId = pdfc.docId;
            if (!docIds.includes(docId)) {
                continue;
            }
            const alreadyLinked = await this.linkingMap.isInRangeForU(pdfc.uuid, uuid);
            if (!alreadyLinked) {
                if (!controllersByDocId.has(docId)) {
                    controllersByDocId.set(docId, []);
                }
                controllersByDocId.get(docId).push(pdfc);
            }
        }

        const desiredDocIds = Array.from(controllersByDocId.keys());
        if (desiredDocIds.length) {
            const requests = this.hub.windowManager.broadcastRequest(
                'contentManager.getHighlightsFromSupplier',
                {
                    supplierUuid: uuid,
                    docIds: desiredDocIds,
                },
                {
                    excludeSelf: false,
                }
            );
            Promise.all(requests).then(async values => {
                for (let value of values) {
                    if (value) {
                        for (const docId of Object.keys(value)) {
                            const hls = value[docId];
                            if (hls.length) {
                                for (const pdfc of controllersByDocId.get(docId)) {
                                    await pdfc.receiveHighlights(hls, uuid);
                                }
                            }
                        }
                        break;
                    }
                }
            });
        }
    },

    onLinkingMapNewlyUndefinedAt: async function({name, pair}) {
        if (name === this.linkingMap.name) {
            const [u, x] = pair;
            const paneId = this.hub.contentManager.getPaneIdByUuid(u);
            if (paneId) {
                const pdfc = this.pdfcsByPaneId[paneId];
                if (pdfc) {
                    await pdfc.dropHighlightsFromSupplier(x);
                }
            }
        }
    }

});

return PdfManager;
});

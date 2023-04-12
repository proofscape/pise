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

/*
 * Working with Selection Boxes
 * ----------------------------
 * Click and drag to make selection boxes.
 * Select them by clicking on them.
 * Then use the keyboard:
 *   Enter: open combiner dialog
 *   Backspace: delete the selected box
 *   Alt-Backspace: delete all boxes
 *   Shift-(arrow key): move the selected box
 *   (arrow key): resize the selected box
 *   Alt-Shift-(arrow key): move the selected box quickly
 *   Alt-(arrow key): resize the selected box quickly
 *
 * Box Combiner Dialog
 * -------------------
 * Whitespace is meaningless.
 * Every command ends with a semicolon (;)
 * Commands:
 *   `(box descrip)`: insert box contents at current location
 *   `n`: start a new line
 *   `x+N`, `x-N`, `y+N`, `y-N`: adjust the current position by N pixels
 * The box descrips are generated automatically for you, when the dialog opens.
 */

import { LackingHostPermissionError } from "browser-peers/src/errors";
import { Highlight, PageOfHighlights } from "../venn";

define([
    "dojo/_base/declare",
    "dojo/on",
    "dijit/Dialog",
    "dijit/layout/ContentPane",
    "ise/content_types/pdf/pdf_util",
    "ise/util",
    "ise/errors"
], function(
    declare,
    dojoOn,
    Dialog,
    ContentPane,
    pdf_util,
    iseUtil,
    pfscErrors
) {

const defaultPdfHighlightColor = 'blue';

var makeSelectionBoxFromDomNode = pdf_util.makeSelectionBoxFromDomNode;
var makeSelectionBoxFromDescrip = pdf_util.makeSelectionBoxFromDescrip;
var renderProgram = pdf_util.renderProgram;
var parseCombinerCode = pdf_util.parseCombinerCode;

/* We will use one instance of this class per PDF pane.
 * It wraps a PDFViewerApplication instance from Mozilla's pdf.js.
 */
var PdfController = declare(null, {

    mgr: null,
    pane: null,
    uuid: null,
    iframe: null,

    stateRequestPromise: null,

    docLoadResolve: null,
    docIsLoaded: false,
    pausedOnDownload: false,
    currentDoc: null,

    contentWindow: null,
    outerContainer: null,
    app: null,
    viewer: null,
    history: null,
    document: null,
    fingerprint: null,
    docId: null,

    urlBar: null,
    pdfUrlBox: null,
    accessUrlAnchor: null,

    viewerDiv: null,
    viewerContainerDiv: null,
    needPbeDiv: null,
    needPermissionDiv: null,
    openFileButton: null,

    origInfo: null,

    highlightPageIdx: null,
    selboxCombineDialog: null,
    combineDialogUpdateHandler: null,

    lastOpenedFilelist: null,

    // format: page _number_ (not index; i.e. 1-based, not 0-based) points to array of
    // functions that should be called after that page's text layer has rendered. These
    // functions are called only once. Then their records here are cleared.
    callbackOnTextLayerRenderLookup: null,

    // This is a mapping from document page numbers to arrays of Highlight instances
    // that have been constructed for that page.
    highlightsByPageNum: null,
    // This mapping provides a way to look up our current Highlights by their IDs.
    // We store them *both* under their *own* ID, and under their *original* ID
    // (for clone highlights these are different; for original highlights they are
    // the same).
    highlightsBySlpSiid: null,

    selectedHighlight: null,

    // This is for linking a doc panel to a tree item,
    // meaning that all the highlights at and under that item in a repo are loaded
    // "permanently" into this panel. "Permanent" means that they stay even when panels
    // hosting their suppliers are closed, and that clicking them can spawn such a panel,
    // if none is yet present.
    linkedTreeItemLibpath: null,
    linkedTreeItemVersion: null,

    constructor: function(mgr, pane, info) {
        this.mgr = mgr;
        this.pane = pane;
        this.uuid = info.uuid;
        this.origInfo = info;
        this.iframe = pane.domNode.children[0].children[0];

        this.callbackOnTextLayerRenderLookup = {};
        this.selboxCombineDialog = this.buildSelboxCombineDialog();

        this.stateRequestPromise = Promise.resolve();

        this.highlightsByPageNum = new iseUtil.SetMapping();
        this.highlightsBySlpSiid = new iseUtil.PairKeyMapping(":");
    },

    initialize: function(info) {
        info = info || this.origInfo;
        const pdfc = this;
        return this.grabAppAndInitialize().then(function() {
            // Prepare for reload if/when the content pane is moved within the DOM tree
            // (as happens when it is moved to a different TabContainer, or even when
            // the TC it's in is involved in making a new split).
            dojoOn(pdfc.iframe, 'load', pdfc.reloadFrame.bind(pdfc));
            // Request state described by the given info object.
            return pdfc.requestState(info);
        });
    },

    /* We need to get ahold of the PDFViewerApplication from the iframe.
     * While there will be a document-level `webviewerloaded` event fired when
     * iframe.contentWindow.PDFViewerApplication becomes defined, it is useless
     * to listen for this, since we still need to set up an interval to check
     * for when the app has been _initialized_. Nor can we bind to any events
     * on the app's own eventBus, since even that isn't defined yet. It is best
     * to simply wait until app.initialized becomes true. So we just set up an
     * interval to poll for the latter.
     *
     * return: promise that resolves after we have grabbed the app and initialized.
     */
    grabAppAndInitialize: function() {
        var pdfc = this;
        return new Promise((resolve, reject) => {
            const max_attempts = 100;
            let num_attempts = 0;
            var grabAppInterval = setInterval(function(){
                console.log('try to grab pdf app');
                num_attempts++;
                if (num_attempts > max_attempts) {
                    console.log('gave up trying to grab pdf app');
                    clearInterval(grabAppInterval);
                }
                var cw = pdfc.iframe.contentWindow;
                if (cw) {
                    var app = cw.PDFViewerApplication;
                    if (app && app.initialized) {
                        clearInterval(grabAppInterval);
                        console.log('pdf app initialized');

                        pdfc.contentWindow = cw;
                        pdfc.app = app;
                        pdfc.viewer = app.pdfViewer;
                        pdfc.history = app.pdfHistory;

                        pdfc.history.history.addNavEnableHandler(pdfc.navEnableHandler.bind(pdfc));

                        //app.eventBus.on("pagerendered", pdfc.onPageRendered.bind(pdfc));
                        app.eventBus.on("textlayerrendered", pdfc.onTextLayerRendered.bind(pdfc));
                        app.eventBus.on("documentinit", pdfc.onDocumentInit.bind(pdfc));
                        app.eventBus.on("initialviewset", pdfc.onInitialViewSet.bind(pdfc));
                        app.eventBus.on("fileinputchange", pdfc.onFileInputChange.bind(pdfc));
                        // Note: Other useful events on the app's eventBus to which we may
                        // want to listen are `documentloaded` and `documentinit`, which are
                        // fired after the viewer has loaded all pages
                        // (e.g. app.pdfViewer._pages.length will now be the expected number),
                        // and after some additional initialization has been done
                        // (e.g. I think this includes scrolling to last page viewed).

                        pdfc.outerContainer = cw.document.getElementById("outerContainer");
                        pdfc.outerContainer.classList.add("pfsc-ise-pdf");
                        pdfc.setTheme(pdfc.mgr.hub.currentTheme);

                        // URL bar
                        pdfc.urlBar = cw.document.getElementById("URLbar");
                        pdfc.pdfUrlBox = cw.document.getElementById("URL");
                        pdfc.accessUrlAnchor = cw.document.querySelector("#sourceLink a");
                        // For now we disable the input element in the URL bar.
                        pdfc.pdfUrlBox.disabled = true;

                        pdfc.viewerDiv = cw.document.getElementById("viewer");
                        pdfc.viewerContainerDiv = cw.document.getElementById("viewerContainer");

                        pdfc.needPbeDiv = cw.document.getElementById("needPbe");
                        pdfc.openFileButton = cw.document.getElementById("openFile");
                        pdfc.needPbeDiv.querySelector('.button').addEventListener('click', e => {
                            pdfc.openFileButton.click();
                        });
                        const pbeLinks = pdfc.needPbeDiv.querySelectorAll('.aboutPbeLink');
                        for (let link of pbeLinks) {
                            link.setAttribute('href', pdfc.mgr.hub.aboutPbeUrl);
                        }
                        const hostMentions = pdfc.needPbeDiv.querySelectorAll('.hostNeedingActivation');
                        for (let mention of hostMentions) {
                            mention.innerText = ` for ${window.location.hostname}${window.location.pathname}`;
                        }

                        pdfc.needPermissionDiv = cw.document.getElementById("needPermission");
                        pdfc.needPermissionDiv.querySelector('a').addEventListener('click', e => {
                            const url = e.target.getAttribute('data-url');
                            //console.log('ask bg script to open options page for host permission for: ', url);
                            pdfc.mgr.hub.pfscExtInterface.makeRequest("sendMessage", {
                                type: "requestHostPermission",
                                url: url,
                            });
                        });

                        // Add custom CSS
                        var link = document.createElement("link");
                        link.href = pdfc.mgr.hub.urlFor('staticISE') + "/pdf.css";
                        link.type = "text/css";
                        link.rel = "stylesheet";
                        cw.document.querySelector('head').appendChild(link);

                        resolve();
                    }
                }
            }, 100);
        });
    },

    showLoadingGif: function(/* bool */ b) {
        const list = this.viewerDiv.classList,
            iconClass = 'largeLoadingIcon';
        if (b) list.add(iconClass); else list.remove(iconClass);
    },

    hideBackPanelMessages: function() {
        this.needPermissionDiv.classList.add('hidden');
        this.needPbeDiv.classList.add('hidden');
    },

    showNeedPbeMessage: function(url) {
        this.hideBackPanelMessages();
        const div = this.needPbeDiv;
        const pdfLink = div.querySelector('a.pdf');
        pdfLink.setAttribute('href', url);
        // Apparently the `download` attribute only works for same-origin URLs. Too bad.
        //pdfLink.setAttribute('download', url);
        div.classList.remove('hidden');
    },

    showNeedPermissionMessage: function(url) {
        this.hideBackPanelMessages();
        const div = this.needPermissionDiv;
        const optionsLink = div.querySelector('a');
        optionsLink.setAttribute('data-url', url);
        const hostname = new URL(url).hostname;
        div.querySelector('code').innerHTML = hostname;
        div.classList.remove('hidden');
    },

    navEnableHandler: function({back, fwd, history}) {
        this.origInfo.history = JSON.stringify(history);
        this.mgr.publishNavEnable({
            back: back,
            fwd: fwd,
            paneId: this.pane.id,
        });
    },

    setUrlBar: function(pdfUrl, accessUrl) {
        if (pdfUrl || accessUrl) {
            if (pdfUrl) {
                this.pdfUrlBox.value = pdfUrl;
            }
            if (accessUrl) {
                this.accessUrlAnchor.setAttribute('href', accessUrl);
                this.accessUrlAnchor.classList.remove('hidden');
            } else {
                this.accessUrlAnchor.classList.add('hidden');
            }
            this.urlBar.classList.remove('hidden');
        } else {
            this.urlBar.classList.add('hidden');
        }
    },

    /* The iframe has been reloaded -- probably due to being moved in the DOM tree.
     * We try to restore its state.
     */
    reloadFrame: function() {
        //console.log('reload frame in pane: ', this.pane.id);
        //console.log('same content window: ', this.iframe.contentWindow === this.contentWindow);
        var pdfc = this;
        pdfc.docIsLoaded = false;
        this.grabAppAndInitialize().then(function() {
            return pdfc.requestState(pdfc.origInfo);
        });
    },

    /* Open a file.
     *
     * param fileList: the type of object you get from a file input dialog's
     *   `files` attribute. It should be a list of length (at least) 1. Only the
     *   first element of the list will be opened.
     */
    openFilelist: function(fileList) {
        this.app.eventBus.dispatch("fileinputchange", {
            fileInput: {
                files: fileList
            }
        });
        this.lastOpenedFilelist = fileList;
    },

    /* When the user opens a PDF manually through the app's "open" button, we
     * record here the file that was opened, so that we can automatically re-open
     * it when the iframe is reloaded (due to being moved in the DOM tree).
     * See `reloadFrame` method.
     */
    onFileInputChange: function({source, fileInput}) {
        this.lastOpenedFilelist = fileInput.files;
        this.origInfo.lastOpenedFilelist = this.lastOpenedFilelist;
        this.setUrlBar(null, null);
    },

    /* Build and return an info object describing the current state of
     * the pdf viewer, for use in initializing a new pdf pane that should
     * be a copy of this one.
     *
     * param serialOnly: boolean; set true if you want only serializable info
     */
    describeState: function(serialOnly) {
        const info = {};

        const props = [
            'fromLibrary', 'url', 'history',  'hash',
            'selection', 'gotosel', 'selcolor',
        ]
        const orig = this.origInfo;
        props.forEach(p => {
            if (orig.hasOwnProperty(p)) {
                info[p] = orig[p];
            }
        });

        if (!serialOnly) {
            const nonserialProps = [
                'lastOpenedFilelist',
            ]
            nonserialProps.forEach(p => {
                if (orig.hasOwnProperty(p)) {
                    info[p] = orig[p];
                }
            });
        }
        
        return info;
    },

    /* Request state according to an info object of the kind returned by
     * our `describeState` method.
     *
     * Optionally, a triggering event may be supplied (as when the state request was
     * triggered by a mouse click).
     *
     * return: Promise that resolves when the transition is complete.
     */
    requestState: function(info, event = null) {
        const pdfc = this;
        // If there is a paused download attempt, give it another go.
        if (this.pausedOnDownload) {
            this.retryDownload();
        }
        // Either way, we add the given request to the chain (understanding that it won't ever
        // get a chance unless the requests before it all resolve).
        this.stateRequestPromise = this.stateRequestPromise.then(() => pdfc.transitionToState(info, event));
        return this.stateRequestPromise;
    },

    retryDownload: function() {
        this.requestPdfFromManager(this.currentDoc);
    },

    /* Transition to a new state.
     * The state is described by an info object.
     * Optionally, a triggering event may be supplied (as when the state request was
     * triggered by a mouse click).
     *
     * param info: <object> describes the desired state
     * param event: <Event|optional> an event that triggered the transition
     * return: Promise that resolves when the transition is complete.
     *
     * All keys in the info object are optional. They are as described below:
     *
     * history
     *
     *   If defined, `history` should be a string giving the JSON representation of a
     * history record from a LocalHistory instance in pfsc-pdf. This will be used to
     * set the navigation history of the PDF pane.
     *
     * lastOpenedFilelist
     * fromLibrary
     * url
     *
     *   These keys can be used to specify the PDF document that is to be loaded. At most
     * one should be defined. If the doc is already open, none is needed.
     *
     *   lastOpenedFilelist: This can be used in order to load a PDF from the user's computer.
     *     If defined, it must be the type of object you get from a file input dialog's `files`
     *     attribute. It should be a list of length (at least) 1. (Only the first element of the
     *     list will be opened.)
     *
     *   fromLibrary: Use this to open a PDF from the server's PDFLibrary directory. Should be a
     *     string giving a valid _relative_ filesystem path within the PDFLibrary directory, and
     *     pointing to a PDF file. The advantage of this over `lastOpenedFilelist` is that it can
     *     be automatically re-opened the next time you reload the app.
     *
     *   url: a URL pointing to a PDF file anywhere on the Internet.
     *
     * hash
     *
     *   `hash` may be any string describing a location in the PDF, which would be valid
     * if appended as a hash on a URL for the PDF. For example, 'page=<N>' is always valid
     * if the document has an Nth page. Math PDFs often have other built-in location names
     * like 'lemma.2' etc.
     *
     * highlightId
     * selection
     * gotosel
     * selcolor
     *
     *   These keys define desired effects relating to selection highlights.
     *
     *   highlightId: {string} A highlight ID (i.e. string of the form `{slp}:{siid}`)
     *     indicating a "named highlight" that should be selected. This is as opposed to
     *     an "ad hoc highlight" that can be defined by the `selection` field (see below).
     *     If both `highlightId` and `selection` are defined, then `highlightId` is followed,
     *     and `selection` ignored.
     *
     *   selection: {string|array} Should be either a single selection code (string) or
     *     an array of selection codes, defining the desired highlight boxes. A "selection code"
     *     is the same as a "combiner code string", i.e. a string describing a combination of
     *     boxes. (See docs on that subject elsewhere.)
     *
     *   gotosel: {string} default = 'altKey'. This should be equal to one of the keywords
     *     defined below, and controls whether we will scroll to the selection. To be precise,
     *     scrolling to the selection means we put the _first_ selection box at the top of the
     *     viewport. If a `hash` was also defined, the selection scroll overrides it.
     *
     *     Keywords:
     *          always: do scroll to the selection;
     *          altKey (default): scroll unless we received an event with event.altKey true;
     *          never: do not scroll.
     *
     *   selcolor: {string} default is defined in `defaultPdfHighlightColor`, above.
     *     Define the color of the selection. Legal values
     *     are: `red`, `yellow`, `green`, `blue`, `clear`. By setting `clear` you make
     *     the selection invisible. This is useful if you only want to scroll to the position of
     *     the selection, but do not want to show it.
     *
     */
    transitionToState(info, event = null) {
        // If a navigation history is given, adopt it.
        if (info.history) {
            const h = JSON.parse(info.history);
            this.history.defineHistory(h.states, h.ptr, false);
            // Redefining the history instantiates a new LocalHistory object in the PDFHistory
            // instance (this all takes place in the pfsc-pdf code), rejecting the old one.
            // That means we're no longer registered as a nav enable handler, so must reregister.
            this.history.history.addNavEnableHandler(this.navEnableHandler.bind(this));
            this.history.history.publishNavEnable();
            // Update our info.
            this.origInfo.history = history;
        }
        // If the document is specified by a URL, we need to check that URL for a hash, even
        // if we don't need to load the document.
        let url = null;
        if (info.fromLibrary) {
            let inner = info.fromLibrary;
            url = this.mgr.localPdfLibraryUrlPrefix;
            if (inner[0] === '/') inner = inner.slice(1);
            url += inner;
        }
        else if (info.url) {
            url = info.url;
        }
        if (url !== null) {
            // Does the URL end with a hash?
            let h = url.indexOf("#");
            if (h > 0) {
                // If a hash was given, remove it.
                let hash = url.slice(h + 1);
                url = url.slice(0, h);
                // This hash will be used only if info.hash was not already defined;
                // in other words, the latter overrides.
                if (typeof info.hash === 'undefined') {
                    info.hash = hash;
                }
            }
        }
        // Begin the asynchronous steps.
        const pdfc = this;
        return new Promise((resolve, reject) => {
            // ----------------------------------------------------------------
            // Load document
            pdfc.docLoadResolve = resolve;
            // If the info specifies a docId, we can use this to identify the case where the desired
            // doc is already loaded. This is better than checking against `this.currentDoc`, because
            // that can take different forms for the same doc, if opened in different ways (like from
            // file system vs via URL).
            const sameDocId = (info.docId === pdfc.docId);
            if (info.lastOpenedFilelist) {
                // Want a document from the user's computer.
                const requestingCurrentDoc = (info.lastOpenedFilelist === pdfc.currentDoc);
                if (pdfc.docIsLoaded && (sameDocId || requestingCurrentDoc)) {
                    // The doc we want is already loaded.
                    resolve();
                } else {
                    pdfc.currentDoc = info.lastOpenedFilelist;
                    pdfc.docIsLoaded = false;
                    pdfc.origInfo.lastOpenedFilelist = info.lastOpenedFilelist;
                    this.setUrlBar(null, null);
                    this.openFilelist(info.lastOpenedFilelist);
                    // Leave it up to `pdfc.onInitialViewSet` to call `resolve`.
                }
            } else if (url !== null) {
                // Want a doc from PDFLibrary or from the web.
                const requestingCurrentDoc = (url === pdfc.currentDoc);
                if (pdfc.docIsLoaded && (sameDocId || requestingCurrentDoc)) {
                    // The doc we want is already loaded.
                    resolve();
                } else {
                    pdfc.currentDoc = url;
                    pdfc.docIsLoaded = false;
                    if (info.fromLibrary) {
                        pdfc.origInfo.fromLibrary = info.fromLibrary;
                    } else if (info.url) {
                        pdfc.origInfo.url = url;
                    }
                    pdfc.requestPdfFromManager(url);
                    // Leave it up to `pdfc.onInitialViewSet` to call `resolve`.
                }
            } else {
                // Not trying to load any doc.
                resolve();
            }
        }).then(() => {
            // ----------------------------------------------------------------
            // Hash navigation
            if (info.hash) {
                pdfc.origInfo.hash = info.hash;
                return pdfc.app.pdfLinkService.setHash(info.hash);
            } else {
                return Promise.resolve();
            }

        }).then(() => {
            // ----------------------------------------------------------------
            // Selections
            if (info.highlightId || info.selection) {
                let g = info.gotosel || 'altKey';
                let doAutoScroll = (
                    ( g === 'always' ) ||
                    ( g === 'altKey' && !event?.altKey )
                );
                pdfc.origInfo.gotosel = g;
                // If a "named highlight" is defined, this overrules any "ad hoc highlight".
                if (info.highlightId) {
                    return pdfc.selectNamedHighlight(
                        info.highlightId, doAutoScroll, info.requestingUuid);
                } else {
                    let codes = Array.isArray(info.selection) ? info.selection : [info.selection];
                    pdfc.origInfo.selection = codes;
                    let color = info.selcolor || defaultPdfHighlightColor;
                    pdfc.origInfo.selcolor = color;
                    return pdfc.highlightFromCodes(codes, doAutoScroll, color);
                }
            } else {
                // If no selection specified, clear any existing highlights.
                pdfc.clearNamedHighlight();
                pdfc.clearAdHocHighlight();
                return Promise.resolve();
            }
        });
    },

    requestPdfFromManager: function(url) {
        const pdfc = this;
        pdfc.hideBackPanelMessages();
        pdfc.showLoadingGif(true);
        pdfc.mgr.getPdfByteArray(url, this.stateRequestPromise).then(info => {
            console.log(info);
            pdfc.app.open(info.bytes);
            pdfc.setUrlBar(info.url, info.accessUrl);
        }).catch(reason => {
            pdfc.showLoadingGif(false);
            console.log(reason);
            if (reason instanceof pfscErrors.PfscInsufficientPdfServiceError) {
                /* This means we didn't detect any normal HTTP errors like 404,
                 * or even any unanticipated errors; instead, it just seems that
                 * we are unable -- for the usual reasons -- to use any of our automated
                 * means to download the PDF for the user. In this case, we recommend
                 * manual download or installing the PBE. */
                pdfc.showNeedPbeMessage(url);
                pdfc.pausedOnDownload = true;
            } else if (reason instanceof LackingHostPermissionError) {
                /* This means we have the PBE, but it currently lacks host permissions
                 * for the URL in question. So we want to prompt the user to grant the
                 * necessary permission. */
                pdfc.showNeedPermissionMessage(url);
                pdfc.pausedOnDownload = true;
            } else {
                /* Otherwise we show the user the error message. In most cases it
                 * will just be a 404, and they will find out they had the wrong URL.
                 * Or it might be some other HTTP error code. Otherwise, it is some
                 * unanticipated error, and hopefully they will send us a bug report. */
                // TODO: if reason has a stack trace, add it under moreInfo.
                //const msg = `Could not download ${url}. ${reason.message}`;
                pdfc.app.error(reason.message, false);
            }
        });
    },

    /*
     * param theme: `light` or `dark`
     */
    setTheme: function(theme) {
        if (!this.outerContainer) return;
        if (theme === 'dark') {
            this.outerContainer.classList.add("themeDark");
            this.outerContainer.classList.remove("themeLight");
        } else {
            this.outerContainer.classList.add("themeLight");
            this.outerContainer.classList.remove("themeDark");
        }
    },

    /* Set a callback function to be called when a page's text layer has rendered.
     * param pageNumber: the 1-based number of the page of interest
     * param callback: the function to be called
     */
    addCallbackOnTextLayerRender: function(pageNumber, callback) {
        var a = this.callbackOnTextLayerRenderLookup[pageNumber] || [];
        a.push(callback);
        this.callbackOnTextLayerRenderLookup[pageNumber] = a;
    },

    /* For internal use only. Called when a page's text layer has rendered.
     * Calls those callback functions that have been registered for this page,
     * and clears those records.
     */
    callbackOnTextLayerRender: function(pageNumber) {
        var a = this.callbackOnTextLayerRenderLookup[pageNumber] || [];
        for (var i in a) {
            var cb = a[i];
            cb();
        }
        // Clear records for this page number.
        delete this.callbackOnTextLayerRenderLookup[pageNumber];
    },

    onDocumentInit: function({source}) {
        this.showLoadingGif(false);
        this.document = this.viewer.pdfDocument;
        this.fingerprint = this.document.fingerprint;
        this.docId = `pdffp:${this.fingerprint}`;

        const wm = this.mgr.hub.windowManager;
        const {myNumber} = wm.getNumbers();
        const serialOnly = true;
        wm.groupcastEvent({
            type: 'pdfFingerprintAvailable',
            fingerprint: this.fingerprint,
            origInfo: this.describeState(serialOnly),
            windowNumber: myNumber,
            paneId: this.pane.id,
        }, {
            includeSelf: true,
        });
    },

    onInitialViewSet: function({source}) {
        // Call the resolve function stored when we set out to load the document
        // in our `transitionToState` method. This announces that the initial content is loaded.
        this.docLoadResolve();
        this.docIsLoaded = true;
        this.pausedOnDownload = false;
    },

    /* Handle a mouse event on a highlight we are hosting.
     *
     * param event: the browser-native mouse event object itself
     * param highlightDescriptor: the HDO of the highlight on which the event occurred
     */
    handleHighlightMouseEvent: function(event, highlightDescriptor) {
        return this.mgr.handleHighlightMouseEvent(this.uuid, event, highlightDescriptor);
    },

    /* Receive an array of highlight descriptors.
     *
     * New highlights in this array (those having highlightId not already present here) are
     * immediately inserted on existing rendered pages, and set up to appear on new
     * pages, as they render. Clones of highlights already present here are added to the
     * existing Highlight objects.
     *
     * param hlDescriptors: array of highlight descriptors
     * param options: {
     *   panelUuid: the uuid of the panel that supplied these highlights. Must be
     *     given if want to establish navigation links. See 'linkTo' option below.
     *   acceptFrom: optional array of libpaths. If defined, accept highlights only
     *     from suppliers of these libpaths. If undefined, accept from all.
     *   linkTo: optional array of libpaths. If defined, set up navigation links to
     *     the panel, for these suppliers. If undefined, set up links for all.
     *     NOTE: In all cases, the links established will be for a subset of the
     *     suppliers accepted by 'acceptFrom' (see above).
     *     NOTE: If 'panelUuid' (see above) is not defined, no links will be established.
     *   reload: boolean, default false. If true, then, for each supplier from which
     *     we are going to accept highlights, start by dropping any and all existing ones.
     * }
     */
    receiveHighlights: async function(hlDescriptors, options) {
        const {
            panelUuid = null,
            acceptFrom = true,
            linkTo = true,
            reload = false,
        } = (options || {});

        const newLinksEstablished = new Set();
        const suppliersCleared = new Set();
        let numberOfNewHighlights = 0;

        if (reload && Array.isArray(acceptFrom)) {
            for (const slp of acceptFrom) {
                this._basicDropHighlightsFromSupplier(slp);
                suppliersCleared.add(slp);
            }
        }

        for (let hlDescriptor of hlDescriptors) {
            const slp = hlDescriptor.slp;
            const siid = hlDescriptor.siid;

            // If we don't want to accept from this supplier, go to next.
            if (Array.isArray(acceptFrom) && !acceptFrom.includes(slp)) {
                continue;
            }

            // Set up link if desired, and possible, and not done already.
            const wantLink = (linkTo === true) || (linkTo.includes(slp));
            if (panelUuid && wantLink && !newLinksEstablished.has(slp)) {
                await this.mgr.linkingMap.add(this.uuid, slp, panelUuid);
                newLinksEstablished.add(slp);
            }

            const hlid = iseUtil.extractHlidFromHlDescriptor(hlDescriptor);
            const ohlid = iseUtil.extractOriginalHlidFromHlDescriptor(hlDescriptor);
            const existingHighlight = this.highlightsBySlpSiid.get(ohlid);
            if (existingHighlight) {
                // If we already have a Highlight instance, add the new supplier
                // to it, and record a mapping from its own ID.
                existingHighlight.addSupplier(hlDescriptor);
                this.highlightsBySlpSiid.set(hlid, existingHighlight);
            } else {
                // Otherwise, make a new highlight, and ensure that we have
                // a mapping for it under both IDs (which may be the same).
                numberOfNewHighlights++;
                const hl = new Highlight(this, hlDescriptor);
                this.highlightsBySlpSiid.set(ohlid, hl);
                this.highlightsBySlpSiid.set(hlid, hl);
                for (const p of hl.listPageNums()) {
                    this.highlightsByPageNum.add(p, hl);
                }
            }
        }

        const clearedAnything = (suppliersCleared.size > 0);
        const addedAnything = (numberOfNewHighlights > 0);
        if (clearedAnything || addedAnything) {
            await this.redoExistingHighlightLayers();
        }
    },

    /* Select a named (as opposed to ad hoc) highlight.
     *
     * param slpSiid: the id of the form `{slp}:{siid}` that uniquely
     *  identifies the named highlight.
     * param doAutoScroll: boolean saying whether to scroll to the highlight.
     * param supplierUuid: optional argument giving the uuid of a panel
     *  where the desired highlight definition can be obtained, in case we don't
     *  have it already.
     *
     * return: promise that resolves with boolean saying whether we found the
     *  requested highlight
     */
    selectNamedHighlight: async function(slpSiid, doAutoScroll, supplierUuid) {
        // If we don't already have the highlight, try to obtain it.
        if (!this.highlightsBySlpSiid.has(slpSiid)) {
            if (supplierUuid) {
                const [slp, siid] = slpSiid.split(":");
                await this.getAndLoadHighlightsFromSupplierPanel(supplierUuid, {
                    acceptFrom: [slp],
                    linkTo: [slp],
                });
            }
        }
        // If we have the highlight, proceed.
        let foundIt = false;
        const hl = this.highlightsBySlpSiid.get(slpSiid);
        if (hl) {
            foundIt = true;
            this.clearNamedHighlight();
            let scrollElt = hl.getScrollElement();
            // Check that scrollElt still has an offsetParent. It will not if it has been removed from
            // the document. This case arises when the page has been destroyed, but the Highlight instance
            // still retains a reference to its element.
            if (scrollElt && scrollElt.offsetParent) {
                // If the scroll element already exists, this means the first page on which
                // the highlight lives has already been rendered, so we can use the 'distant'
                // scroll policy.
                // Note that, if the highlight is just *below* the view area, the policy of
                // scrolling it just into view is not great, since we're using only the first
                // box of the highlight as he scroll target. To make up for this a little, we
                // add a bit of padding to the view box.
                hl.select(true);
                if (doAutoScroll) {
                    this.scrollIntoView(scrollElt, {pos: 'mid', policy: 'distant', padPx: 32});
                }
            } else {
                // If we didn't get a scroll element, it's because the first page on which
                // the highlight lives hasn't been rendered yet. We need to render the pages,
                // and we'll use the 'pos' scroll policy.
                const pages = hl.listPageNums();
                const firstPage = hl.firstPage();
                pages.reverse();  // Work by descending page number.
                for (const n of pages) {
                    await this.operateOnRenderedPage(n, doAutoScroll, pageView => {
                        // When the last of the rendering jobs -- the page with the smallest
                        // number -- has completed, then we can select the highlight.
                        if (n === firstPage) {
                            hl.select(true);
                            if (doAutoScroll) {
                                scrollElt = hl.getScrollElement();
                                // scrollElt should now exist, but we check just to be sure.
                                if (scrollElt && scrollElt.offsetParent) {
                                    this.scrollIntoView(scrollElt, {pos: 'mid', policy: 'pos'});
                                }
                            }
                        }
                    })
                }
            }
        }
        return foundIt;
    },

    /* Invoked by a Highlight instance when it becomes selected.
     */
    noteSelectedHighlight: function(hl) {
        this.selectedHighlight = hl;
    },

    /* Given the uuid of a panel (in any window), try to obtain the array of
     * all highlights defined in that panel, for our document. If obtained,
     * load them.
     *
     * param supplierUuid: the uuid of the supplier panel
     * param options: {
     *   acceptFrom: as in the `receiveHighlights()` method.
     *   linkTo: as in the `receiveHighlights()` method.
     *   reload: as in the `receiveHighlights()` method.
     * }
     *
     * return: promise resolving with boolean saying whether we managed to
     *   get and load the highlights.
     */
    getAndLoadHighlightsFromSupplierPanel: async function(supplierUuid, options) {
        const hls = await this.getHighlightsFromSupplierPanel(supplierUuid);
        if (hls !== null) {
            options.panelUuid = supplierUuid;
            await this.receiveHighlights(hls, options);
            return true;
        }
        return false;
    },

    /* Given the uuid of a panel (in any window), try to obtain the array of
     * all highlights defined in that panel, for our document.
     *
     * return: promise resolving with array of highlights (possibly emmpty),
     *   or null iff the panel was not found in any window.
     */
    getHighlightsFromSupplierPanel: function(supplierUuid) {
        const requests = this.mgr.hub.windowManager.broadcastRequest(
            'hub.contentManager.getHighlightsFromSupplier',
            {
                supplierUuid: supplierUuid,
                docIds: [this.docId],
            },
            {
                excludeSelf: false,
            }
        );
        return Promise.all(requests).then(async values => {
            for (let hlsByDocId of values) {
                if (hlsByDocId !== null) {
                    // We found the panel. The content hosted there may or may not
                    // define any highlights for our docId. In all cases, you get
                    // an array, possibly empty.
                    return hlsByDocId[this.docId] || [];
                }
            }
            // No window seems to host a panel of the given uuid.
            return null;
        });
    },

    libpathBelongsToLinkedTreeSet: function(lp) {
        return (this.linkedTreeItemLibpath &&
            iseUtil.libpathIsPrefix(this.linkedTreeItemLibpath, lp));
    },

    /* Drop any existing highlights we are holding from a particular supplier.
     *
     * Note: We ignore the request if we are holding *permanent* highlights from
     * that supplier.
     *
     * param slp: the libpath of the supplier
     */
    dropHighlightsFromSupplier: async function(slp) {
        if (this.libpathBelongsToLinkedTreeSet(slp)) {
            return;
        }
        this._basicDropHighlightsFromSupplier(slp);
        // Finally, since removing any highlights can completely change the Venn diagram
        // for any given page, we have to redo existing highlight layers.
        await this.redoExistingHighlightLayers();
    },

    /* Internal method, which carries out the basic operation of dropping highlights from
     * a supplier "logically" (i.e. from our records), but not "graphically" (i.e. not from
     * existing highlight layers).
     *
     * NOTE: *Goes ahead without checks.*
     * NOTE: *Does not rebuild existing highlight layers*.
     */
    _basicDropHighlightsFromSupplier: function(slp) {
        const hls = this.highlightsBySlpSiid.getValuesUnderFirstKey(slp);
        for (const hl of hls) {
            const hdo = hl.popSupplier(slp);
            if (hdo) {
                const hlid = iseUtil.extractHlidFromHlDescriptor(hdo);
                const ohlid = iseUtil.extractOriginalHlidFromHlDescriptor(hdo);
                if (hlid !== ohlid) {
                    this.highlightsBySlpSiid.delete(hlid);
                }
                if (hl.getSupplierCount() === 0) {
                    this.highlightsBySlpSiid.delete(ohlid);
                    for (const p of hl.listPageNums()) {
                        this.highlightsByPageNum.remove(p, hl);
                    }
                }
            }
        }
    },

    dropAllExistingHighlights: async function() {
        this.highlightsByPageNum.clear();
        this.highlightsBySlpSiid.clear();
        await this.redoExistingHighlightLayers();
    },

    /* Respond to the PDF viewer app's `pagerendered` event.
     * This is dispatched after the canvas layer of a pdf page has finished rendering.
     */
    onPageRendered: function({source, pageNumber, cssTransform, timestamp}) {
    },

    /* Respond to the PDF viewer app's `textlayerrendered` event.
     * This is dispatched after the text layer of a pdf page has finished rendering.
     */
    onTextLayerRendered: function({source, pageNumber, numTextDivs}) {
        this.addPageLayers(pageNumber);
        this.callbackOnTextLayerRender(pageNumber);
    },

    // -----------------------------------------------------------------------
    /* These methods were for highlighting using the text layer.
    * They're still good for that, and we should probably make them usable again.
    *
    * For future reference, note that this code was designed to work
    * with v2.2.228 of the prebuilt distribution of pdf.js. This may be important
    * to know, since we are doing hacky things like working with "private" object
    * properties (those beginning with "_"). Therefore our code may fail to work
    * with a future version, even if that version makes no published API changes.
    *
    */

    /* When a text range is selected anywhere in the PDF document,
     * call this function to compute a five-number code representing
     * the selection range.
     *
     * If the current selection lies outside the PDF document, return null.
     */
    encodeSelection_OLD: function() {

        var sel = this.contentWindow.getSelection(),
            rng = sel.getRangeAt(0),
            beginDiv = rng.startContainer.parentNode,
            beginOffset = rng.startOffset,
            endDiv = rng.endContainer.parentNode,
            endOffset = rng.endOffset;

        // Is the selection in the PDF viewer?
        try {
            var beginInViewer = beginDiv.parentNode.parentNode.parentNode.classList.contains("pdfViewer"),
                endInViewer = endDiv.parentNode.parentNode.parentNode.classList.contains("pdfViewer");
        } catch (e) {
            return null;
        }
        if (!beginInViewer || !endInViewer) {
            return null;
        }

        // Find indices of begin and end divs, as children.
        var di = 0;
        var child = endDiv;
        while (child !== beginDiv) {
            child = child.previousSibling;
            di++;
        }
        var i = 0;
        while ( (child = child.previousSibling) !== null ) i++;
        // Now i is index of beginDiv and i + di is index of endDiv.

        var dpn = beginDiv.parentNode.parentNode.attributes["data-page-number"];
        if (dpn === undefined) {
            console.error("Missing data page number.")
            return null;
        } else {
            var pageNumber = +dpn.value,
                pageIdx = pageNumber - 1;

            var selectionCode = `${pageIdx},${i},${beginOffset},${i+di},${endOffset}`;
            //console.log(selectionCode);
            return selectionCode;
        }
    },

    /* Pass a code of the kind returned by `this.encodeSelection`.
     * We decode it into parameters representing a selection range.
     */
    decodeSelection_OLD: function(code) {
        var parts = code.split(',');
        return {
            pageIdx: +parts[0],
            beginDivIdx: +parts[1],
            beginOffset: +parts[2],
            endDivIdx: +parts[3],
            endOffset: +parts[4]
        };
    },

    /* Highlight a selection in the PDF viewer.
     *
     * Optionally, scroll the selection into view (iff autoScroll is truthy).
     */
    // <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Destructuring_assignment#Object_destructuring>
    highlightSelection_OLD: function({pageIdx, beginDivIdx, beginOffset, endDivIdx, endOffset, autoScroll}) {
        this.clearHighlight_OLD();
        if (!this.app) return;
        var viewer = this.app.pdfViewer;
        if (!viewer) return;
        var pv = viewer.getPageView(pageIdx);
        if (!pv) return;
        var tl = pv.textLayer;
        var pageNumber = pageIdx + 1;

        // It's possible the page of interest hasn't been rendered yet. We will know that
        // is the case if the text layer is null.
        // We need to have a text layer before we can do anything else, so we may or may
        // not need some asynchronous processing here.
        var mgr = this;
        var getTextLayer = new Promise(function(resolve, reject) {
            if (autoScroll && tl === null) {
                // Page has not yet been rendered, but user wants to auto-scroll to it.
                // So we need to scroll to the page now, so it will render, and we can proceed.
                mgr.addCallbackOnTextLayerRender(pageNumber, resolve);
                viewer.scrollPageIntoView({pageNumber: pageNumber});
            } else {
                resolve();
            }
        });
        getTextLayer.then(function() {
            tl = pv.textLayer;
            // Text layer may still be null, if the page was not yet rendered, and
            // the user was _not_ requesting an autoscroll. In that case just do nothing.
            if (!tl) return;
            var matches = [
                {
                    begin: {
                        divIdx: beginDivIdx,
                        offset: beginOffset
                    },
                    end: {
                        divIdx: endDivIdx,
                        offset: endOffset
                    }
                }
            ];
            var dummyFC = {
                selected: {
                    pageIdx: pageIdx,
                    matchIdx: 0
                },
                state: {
                    highlightAll: true
                },
                scrollMatchIntoView: function(p) {
                    if (autoScroll) {
                        viewer._scrollIntoView({pageDiv: p.element});
                    }
                }
            };
            var trueFC = tl.findController;
            tl.findController = dummyFC;
            tl.matches = matches;
            tl._renderMatches(matches);
            tl.findController = trueFC;
            mgr.highlightPageIdx = pageIdx;
        });
    },

    clearHighlight_OLD: function() {
        var pageIdx = this.highlightPageIdx;
        if (pageIdx === null) return;
        var pv = this.app.pdfViewer.getPageView(pageIdx),
            tl = pv.textLayer;
        var trueFC = tl.findController;
        tl.findController = null;
        tl._updateMatches();
        tl.matches = [];
        tl.findController = trueFC;
    },

    highlightFromCode_OLD: function(code, autoScroll) {
        var params = this.decodeSelection(code);
        params.autoScroll = autoScroll;
        this.highlightSelection(params);
    },

    // -----------------------------------------------------------------------

    // Ad hoc highlights are those that do not come from a highlight supplier, but
    // are just specified by passing an array of combiner codes to the `highlightFromCodes()` method.
    // See also: `clearNamedHighlight()`
    clearAdHocHighlight: function() {
        this.outerContainer.querySelectorAll('.highlightBox').forEach(box => box.remove());
    },

    /* Draw highlight boxes based on an array of combiner code strings.
     * Optionally auto scroll to bring the first of these into view.
     *
     * param codes: array of combiner code strings.
     * param doAutoScroll: boolean saying whether you want to scroll the first
     *   box into view if necessary.
     * param color: string naming the desired color for the highlight boxes,
     *   from among the valid options: {red, yellow, green, blue, clear}
     *
     * return: promise that resolves when all highlight boxes are drawn.
     */
    highlightFromCodes: function(codes, doAutoScroll, color = defaultPdfHighlightColor) {
        const colors = ['red', 'yellow', 'green', 'blue', 'clear'];
        if (!colors.includes(color)) {
            color = defaultPdfHighlightColor;
        }
        var boxes = pdf_util.makeAllBoxesFromCombinerCodes(codes);
        var sorted = pdf_util.sortBoxesByPageNumber(boxes);
        var N = sorted.length;
        if (N === 0) return Promise.resolve();
        var ctrl = this;
        return new Promise((resolve, reject) => {
            // We want to work by _descending_ page number, so reverse the array.
            sorted.reverse();
            function startNextJob(ptr) {
                var info = sorted[ptr];
                var job = ctrl.operateOnRenderedPage(info.pageNum, doAutoScroll, function(pageView) {
                    // Draw the boxes in the pageView's box layer.
                    var boxLayer = pageView.div.querySelector('.boxLayer'),
                        W = boxLayer.clientWidth;
                    var scaledBoxes = info.boxes.map(box => box.makeRoundedScaledCopy(W/box.W));
                    scaledBoxes.forEach(box => {
                        var rect = document.createElement("div");
                        rect.classList.add('highlightBox', color);
                        rect.style.left = box.x + 'px';
                        rect.style.top = box.y + 'px';
                        rect.style.width = box.w + 'px';
                        rect.style.height = box.h + 'px';
                        boxLayer.appendChild(rect);
                    });
                });
                job.then(() => {
                    if (++ptr < N) {
                        startNextJob(ptr);
                    } else {
                        if (doAutoScroll) {
                            // Scroll not just to the first page, but to the first highlight box on that page.
                            var rect = ctrl.outerContainer.querySelector('.highlightBox');
                            ctrl.scrollIntoView(rect);
                        }
                        resolve();
                    }
                });
            }
            ctrl.clearAdHocHighlight();
            startNextJob(0);
        });
    },

    // Our old technique, relying on the scoll operation offered by pdf.js:
    _native_scrollIntoView: function(element) {
        this.viewer._scrollIntoView({pageDiv: element});
    },

    // Note: so far tested only on elements belonging to a .highlightLayer div
    scrollIntoView: function(element, options) {
        iseUtil.scrollIntoView(element, this.viewerContainerDiv, options);
    },

    /* Suppose you have an operation to perform on a page, and that you may or
     * may not want to autoscroll to that page. There are several possibilities:
     *
     * If the page is not currently rendered, then...
     *   ...if you also don't want to autoscroll to it, you might as well do nothing.
     *   ...if you do want to autoscroll, then we must scroll to the page, which will
     *      cause it to render, and after it renders we can perform the desired operation.
     * Whereas if the page _is_ currently rendered, then you can perform the operation,
     * and autoscroll or not, as desired.
     * This method is for that.
     *
     * param pageNumber: the 1-based number of the page of interest
     * param doAutoScroll: boolean saying whether we want to autoscroll
     * param operation: the function that carries out the desired operation.
     *   Should accept a single argument, being a PDFPageView instance representing
     *   the rendered page.
     *
     * Note that if the page is not currently rendered AND we do not want to autoscroll,
     * then the operation will not be performed.
     *
     * return: a promise that resolves when we are through with everything we
     *   wanted to do.
     */
    operateOnRenderedPage: function(pageNumber, doAutoScroll, operation) {
        var pageIdx = pageNumber - 1;
        var view = this.viewer.getPageView(pageIdx);
        var ctrl = this;
        function performScroll() {
            ctrl.viewer.scrollPageIntoView({pageNumber: pageNumber});
        }
        if (!view.canvas || !view.textLayer) {
            // The page isn't rendered yet.
            if (doAutoScroll) {
                var renderPage = new Promise((resolve, reject) => {
                    ctrl.addCallbackOnTextLayerRender(pageNumber, resolve);
                    performScroll();
                });
                return renderPage.then(() => operation(view));
            } else {
                // We don't care to autoscroll. Just give up and do nothing.
                return Promise.resolve();
            }
        } else {
            // The page does appear to be rendered already.
            return Promise.resolve().then(() => {
                if (doAutoScroll) performScroll();
                operation(view);
            });
        }
    },

    // -----------------------------------------------------------------------

    /* Get the fully rendered canvas element for a page, given by 1-based page _number_.
     * Importantly, if the page in question doesn't yet have a rendered canvas, we take
     * steps to make it have one.
     *
     * param pageNumber: the 1-based page number of the page you want
     * return: a promise that resolves when the canvas is ready, passing the
     *   canvas to the resolution function.
     */
    getCanvas: function(pageNumber) {
        var pageIdx = pageNumber - 1;
        var viewer = this.app.pdfViewer;
        if (!viewer) throw new Error('PDF app has no viewer');
        var pageView = viewer.getPageView(pageIdx);
        if (!pageView) throw new Error('PDF viewer has no page ' + pageNumber);
        return new Promise((resolve, reject) => {
            if (pageView.canvas) {
                resolve(pageView.canvas);
            } else {
                // -------------------------------------------------------------------
                // Technical note: This next line is a bit hacky. I pulled it out of
                // the `forceRendering` method in the `BaseViewer` class (defined
                // in pdf.js/web/base_viewer.js). To be fair, using it directly like this
                // doesn't seem too out of line with the design of the BaseViewer (as
                // far as I can perceive it).
                //
                // One potential concern could be that by doing this we might unintentionally
                // circumvent some "cleanup" mechanism that was meant to keep track of which
                // canvases have been rendered, and to schedule them for destruction at an
                // appropriate time. But a little testing seems to suggest that in fact there's
                // nothing to worry about here. I see that a `PDFPageView` instance has its
                // canvas destroyed in its `reset` method, which is triggered I know not how
                // (timeout? scrolling?). Anyway, after using this hack to render the canvas
                // for a PDFPageView P that didn't already have one, I tried scrolling a bit,
                // and before long page P's `reset` method was called. So I think we're probably okay.
                var renderingPromise = viewer._ensurePdfPageLoaded(pageView).then(() => {
                    viewer.renderingQueue.renderView(pageView);
                });
                // -------------------------------------------------------------------
                renderingPromise.then(function() {
                    resolve(pageView.canvas);
                });
            }
        });
    },

    /* Copy image data from a page, rendered at a desired scale, and store in
     * SelectionBox instances describing the desired boxes.
     *
     * param boxes: an array of SelectionBox instances, all describing boxes on a single page
     * param pageNumber: the 1-based number of the desired page
     * param scale: the desired rendering scale
     *
     * return: promise that resolves when the boxes have been rendered, and the resources
     *   involved (e.g. canvas element) have been cleaned up.
     */
    renderBoxesFromPage: function(boxes, pageNumber, scale) {
        var viewer = this.app.pdfViewer;
        // The container has to be added to the document within the iframe, or
        // else the page won't actually render.
        var container = this.contentWindow.document.createElement('div');
        container.style.display = 'none';
        this.contentWindow.document.documentElement.appendChild(container);
        return viewer.pdfDocument.getPage(pageNumber)
        .then(function(pdfPage) {
            var pdfPageView = new viewer.makeAvailable.PDFPageView({
                container: container,
                id: pageNumber,
                scale: scale,
                defaultViewport: pdfPage.getViewport({ scale: 1 }),
            });
            pdfPageView.setPdfPage(pdfPage);
            return pdfPageView;
        })
        .then(function(pdfPageView) {
            //return viewer.renderingQueue.renderView(pdfPageView).then(function() {
            return pdfPageView.draw().then(function() {
                //console.log(pdfPageView.canvas);
                var canvas = pdfPageView.canvas;
                boxes.forEach(box => box.captureFromCanvas(canvas));
            }).then(function() {
                // clean up and free memory
                pdfPageView.destroy();
                container.remove();
            });
        });
    },

    /* Copy image data from a PDF, rendered at a desired scale, and store in
     * SelectionBox instances describing the desired boxes.
     *
     * param boxes: an array of SelectionBox instances
     * param scale: the desired rendering scale
     */
    renderBoxes: function(boxes, scale) {
        var sorted = pdf_util.sortBoxesByPageNumber(boxes);
        var ctrl = this;
        var jobs = sorted.map(info => ctrl.renderBoxesFromPage(info.boxes, info.pageNum, scale));
        return Promise.all(jobs);
    },

    // // // // // testing -----

    /*
    testCopyBox1: function() {
        var scale = 4;
        var code = 's3.8;(151:2228:3377:422:1549:597:70);n;x+147;(151:2228:3377:1025:1539:753:78)';
        var prog = parseCombinerCode(code, null);
        var defTimeZoom = prog.scale;
        var descrips = prog.getBoxDescrips();
        var Bi = descrips.map(makeSelectionBoxFromDescrip);
        var mgr = this;
        this.renderBoxes(Bi, scale).then(function() {
            var renderingZoom = (Bi[0].captureBox.W/Bi[0].W).toFixed(2);
            // Make a lookup for the capture boxes by the original boxes' descriptions.
            var boxesByDescrip = {};
            Bi.forEach(box => {
                boxesByDescrip[box.writeDescription()] = box.captureBox;
            });
            var dlg = mgr.selboxCombineDialog;
            var previewCanvas = dlg.domNode.querySelector('canvas');
            prog = parseCombinerCode(code, boxesByDescrip);
            prog.scaleShifts(renderingZoom);
            var displayScaling = 1/(defTimeZoom * renderingZoom);
            renderProgram(prog, previewCanvas, displayScaling);
            dlg.show();
        });
    },
    */
    // // // // //

    addPageLayers: function(pageNumber) {
        const canvas = this.outerContainer.querySelector('.page'+pageNumber);
        const page = canvas.parentNode.parentNode;
        this.addBoxLayer(page, pageNumber);
        this.addHighlightLayer(page, pageNumber);
    },

    // Add a brand new highlight layer to a page.
    addHighlightLayer: function(page, pageNumber) {
        const hlLayer = document.createElement("div");
        hlLayer.style.width = page.style.width;
        hlLayer.style.height = page.style.height;
        hlLayer.classList.add('highlightLayer');
        this.buildHighlightsForHighlightLayer(hlLayer, pageNumber, page.clientWidth);
        page.appendChild(hlLayer);
    },

    // Find all existing highlight layers, and redo each one.
    // Useful when changing the set of highlights loaded into this doc.
    redoExistingHighlightLayers: async function() {
        const previousSelection = this.selectedHighlight;

        const highlightLayers = Array.from(this.outerContainer.querySelectorAll('.highlightLayer'));
        for (const highlightLayer of highlightLayers) {
            const pageNumber = +highlightLayer.parentNode.getAttribute('data-page-number');
            this.redoHighlightLayer(highlightLayer, pageNumber);
        }

        // Try to restore previous selection, if any, and if it still exists.
        if (previousSelection) {
            const exists = await this.selectNamedHighlight(
                previousSelection.highlightId, false, null);
            if (!exists) {
                this.clearNamedHighlight();
            }
        }
    },

    // Clear out an existing highlight layer, and rebuild its contents.
    redoHighlightLayer: function(highlightLayer, pageNumber) {
        iseUtil.removeAllChildNodes(highlightLayer);
        this.buildHighlightsForHighlightLayer(highlightLayer, pageNumber, highlightLayer.clientWidth);
    },

    // Build the contents of a highlight layer.
    buildHighlightsForHighlightLayer: function(highlightLayer, pageNumber, pageWidth) {
        const hls = Array.from(this.highlightsByPageNum.get(pageNumber) || []);
        if (!hls.length) {
            return;
        }
        const hlPage = new PageOfHighlights(this, pageNumber, pageWidth);
        hlPage.addHighlights(hls);
        hlPage.populateHighlightLayer(highlightLayer);
    },

    // Named highlights are those that appear in the highlightLayer of a page, and come from
    // a highlight descriptor from a highlight supplier.
    // See also: `clearAdHocHighlight()`
    clearNamedHighlight: function() {
        this.outerContainer.querySelectorAll('.hl-zone.selected').forEach(zone => {
            zone.classList.remove('selected');
        });
        this.selectedHighlight = null;
        // Also make sure the box-select layer is clear:
        this.removeAllHighlightBoxes();
    },

    addBoxLayer: function(page, pageNumber) {
        var boxLayer = document.createElement("div");
        boxLayer.style.width = page.style.width;
        boxLayer.style.height = page.style.height;
        boxLayer.classList.add('boxLayer');
        var doc = this.contentWindow.document;
        var mgr = this;
        boxLayer.setAttribute('tabindex', -1);
        dojoOn(boxLayer, 'keydown', function(e) {
            switch(e.code) {
            case "Backspace":
                if (e.altKey) {
                    // Alt-Backspace: remove ALL boxes
                    mgr.removeAllHighlightBoxes();
                }
                break;
            case 'Enter':
                var showDialog = true;
                mgr.readCombinerCodeFromSelectionBoxes(showDialog);
                break;
            }
            e.stopPropagation();
            e.preventDefault();
        });
        dojoOn(boxLayer, 'mousedown', function(mdEvent){
            //console.log(mdEvent);
            // "a" is for "anchor"; "c" is for "corner".
            // The corner needs to appear where the user actually clicked, so we must
            // use offset coords for that. However, offset coords are unstable for
            // computing (dx,dy) during drag, so we use client coords for that instead.
            // The instability is because offset coords are determined by the object the
            // mouse is currently over, and, as you drag, that object is variously the
            // background or the box itself which you are drawing.
            var ax = mdEvent.clientX,
                ay = mdEvent.clientY,
                cx = mdEvent.offsetX,
                cy = mdEvent.offsetY,
                rect = document.createElement("div");
            rect.classList.add('highlightBox');
            rect.classList.add('selectionBox');
            rect.style.left = cx+'px';
            rect.style.top = cy+'px';
            boxLayer.appendChild(rect);
            var moveHandler = dojoOn(doc.documentElement, 'mousemove', function(mmEvent){
                //console.log(mmEvent);
                var ex = mmEvent.clientX,
                    ey = mmEvent.clientY,
                    dx = ex - ax,
                    dy = ey - ay;
                //console.log(dx, dy);
                if (dx >= 0) {
                    rect.style.width = dx+'px';
                } else {
                    rect.style.left = (cx + dx)+'px';
                    rect.style.width = (-dx)+'px';
                }
                if (dy >= 0) {
                    rect.style.height = dy+'px';
                } else {
                    rect.style.top = (cy + dy)+'px';
                    rect.style.height = (-dy)+'px';
                }
                mmEvent.stopPropagation();
            });
            //console.log(moveHandler);
            var upHandler = dojoOn(doc.documentElement, 'mouseup', function(muEvent){
                //console.log(muEvent);
                moveHandler.remove();
                upHandler.remove();
                muEvent.stopPropagation();

                // If really small, just remove it. This case will arise e.g. when user
                // just clicks the bg and doesn't drag at all. It's also okay if they dragged
                // only a little.
                var w = rect.clientWidth,
                    h = rect.clientHeight;
                if (w < 10 && h < 10) {
                    //boxLayer.removeChild(rect);
                    rect.remove();
                    return;
                }

                rect.setAttribute('tabindex', -1);  // make focusable by script or mouse click
                dojoOn(rect, 'mousedown', function(mdEvent){
                    rect.focus();
                    mdEvent.stopPropagation();
                    var ax = mdEvent.clientX,
                        ay = mdEvent.clientY;
                    var x0 = rect.offsetLeft,
                        y0 = rect.offsetTop;
                    var rectMoveHandler = dojoOn(doc.documentElement, 'mousemove', function(mmEvent){
                        var ex = mmEvent.clientX,
                            ey = mmEvent.clientY,
                            dx = ex - ax,
                            dy = ey - ay;
                        rect.style.left = (x0 + dx) + 'px';
                        rect.style.top = (y0 + dy) + 'px';
                        mdEvent.stopPropagation();
                    });
                    var rectUpHandler = dojoOn(doc.documentElement, 'mouseup', function(muEvent){
                        rectMoveHandler.remove();
                        rectUpHandler.remove();
                        muEvent.stopPropagation();
                    });
                });
                dojoOn(rect, 'dblclick', function(e){
                    e.stopPropagation();
                    var showDialog = true;
                    mgr.readCombinerCodeFromSelectionBoxes(showDialog);
                });
                dojoOn(rect, 'keydown', function(e){
                    //console.log(e);
                    // offset height and width include the border, which we do not want;
                    // so we use client height and width.
                    // However, offset left and top give us the coords we need, whereas client coords do not.
                    var x = rect.offsetLeft,
                        y = rect.offsetTop,
                        w = rect.clientWidth,
                        h = rect.clientHeight;
                    var d = e.altKey ? 5 : 1;
                    //console.log(x, y, w, h);
                    switch(e.code) {
                    case "Backspace":
                        if (!e.altKey) {
                            // remove just THIS box
                            rect.remove();
                        }
                        break;
                    case "ArrowLeft":
                        if (e.shiftKey) {
                            rect.style.left = (x - d)+'px';
                        } else {
                            rect.style.width = (w - d)+'px';
                        }
                        break;
                    case "ArrowRight":
                        if (e.shiftKey) {
                            rect.style.left = (x + d)+'px';
                        } else {
                            rect.style.width = (w + d)+'px';
                        }
                        break;
                    case "ArrowUp":
                        if (e.shiftKey) {
                            rect.style.top = (y - d)+'px';
                        } else {
                            rect.style.height = (h - d)+'px';
                        }
                        break;
                    case "ArrowDown":
                        if (e.shiftKey) {
                            rect.style.top = (y + d)+'px';
                        } else {
                            rect.style.height = (h + d)+'px';
                        }
                        break;
                    }
                    // Do not stop propagation here, since we want the boxLayer to get a chance.
                    e.preventDefault();
                });

            });
            mdEvent.stopPropagation();
        });
        /* Wanted to make doubleclick on the background remove all boxes, but for
         * some reason the event is not getting fired. Haven't figured it out yet.
        dojoOn(boxLayer, 'dblclick', function(e){
            e.stopPropagation();
            // Remove all boxes.
            mgr.removeAllHighlightBoxes();
        });
        */
        page.appendChild(boxLayer);
    },

    getSelectionBoxes: function() {
        return this.outerContainer.querySelectorAll('.selectionBox');
    },

    removeAllHighlightBoxes: function() {
        this.outerContainer.querySelectorAll('.highlightBox').forEach(box => box.remove());
    },

    /* Read the combiner code from all current selection boxes.
     * Optionally, show the combiner dialog.
     *
     * param showDialog: set true if you want to show the dialog.
     * return: the full, automatically generated combiner code.
     */
    readCombinerCodeFromSelectionBoxes: function(showDialog) {
        // Grab any and all selection boxes, anywhere in the whole document
        // (they're probably only on one page, or maybe a neighboring one too).
        var boxList = this.getSelectionBoxes();
        // If no boxes, nothing to do.
        if (boxList.length === 0) return;
        // From the raw rectangles we need to form instances of our SelectionBox class.
        var Bi = [];
        boxList.forEach(box => Bi.push(makeSelectionBoxFromDomNode(box)));
        // Now make another list of boxes, these ones containing image data, and being
        // scaled to match the canvases.
        var Ri = [];
        Bi.forEach(box => Ri.push(box.captureFromCanvas()));

        // Need to know the zoom level of the viewer...
        var viewer = this.app.pdfViewer;
        var basicZoom = viewer._currentScale;
        // ...and any further zoom due to rendering. We assume it is the same for all
        // boxes, and the same in both horizontal and vertical dimensions.
        var renderingZoom = (Ri[0].W/Bi[0].W).toFixed(2);

        // Need a lookup for the rendering boxes.
        var boxesByDescrip = {};
        Ri.forEach(box => {
            boxesByDescrip[box.writeDescription()] = box;
        });

        // We'll start off with basic combiner code that puts one box per line.
        var initialCode = Ri.map(box => "("+box.writeDescription()+")").join(';n;\n');

        // Load up the dialog box and set it to render a preview canvas on
        // each keystroke in the code box.
        var dlg = this.selboxCombineDialog;
        var tas = dlg.domNode.querySelectorAll('textarea');
        var codeArea = tas[0],
            copyBox = tas[1],
            templateBox = tas[2];
        var previewCanvas = dlg.domNode.querySelector('canvas');

        if (this.combineDialogUpdateHandler !== null) this.combineDialogUpdateHandler.remove();
        codeArea.value = initialCode;

        var displayScaling = 1/renderingZoom;
        var fullZoom = basicZoom * renderingZoom;

        function update() {
            const code = 'v2;' + codeArea.value;
            // (1) render the preview canvas
            const prog = parseCombinerCode(code, boxesByDescrip);
            const dims = renderProgram(prog, previewCanvas, displayScaling);
            // (2) set the value of the copy box
            //var w = Math.ceil(dims.w/fullZoom),
            //    h = Math.ceil(dims.h/fullZoom);
            const progText = prog.write();
            const fullCode = `v2;s${fullZoom};` + progText;
            let toCopy = templateBox.value;
            toCopy = toCopy.replaceAll('${code}', fullCode);
            //toCopy += '\n' + `size="${w}x${h}"`;
            copyBox.value = toCopy;
            return fullCode;
        }

        var fullCode = update();
        this.combineDialogUpdateHandler = dojoOn(codeArea, 'input', update);
        if (showDialog) dlg.show();
        return fullCode
    },

    buildSelboxCombineDialog: function() {
        var dlg = new Dialog({
            title: "Selection Combiner",
            class: "pfsc-ise"
        });
        var pane = new ContentPane({
            style: "width: 650px; height: 300px;"
        });
        dlg.addChild(pane);

        var codeArea = document.createElement('textarea');
        codeArea.style.width = '100%';
        codeArea.style.height = '20%';
        iseUtil.noCorrect(codeArea);
        pane.domNode.appendChild(codeArea);

        var display = document.createElement('canvas');
        display.classList.add('selectionCombiner');
        display.style.border = '1px solid';
        pane.domNode.appendChild(display);

        var copyBox = document.createElement('textarea');
        copyBox.style.width = '100%';
        copyBox.style.height = '10%';
        iseUtil.noCorrect(copyBox);
        pane.domNode.appendChild(copyBox);

        const templateLabel = document.createElement('div');
        templateLabel.innerHTML = "Template:"
        pane.domNode.appendChild(templateLabel);

        const templateBox = document.createElement('textarea');
        templateBox.style.width = '50%';
        templateBox.style.height = '10%';
        iseUtil.noCorrect(templateBox);
        templateBox.value = 'doc = "#${code}"';
        pane.domNode.appendChild(templateBox);

        return dlg;
    },

    removeLinkedTreeItem: function() {
        const libpath = this.linkedTreeItemLibpath;
        const version = this.linkedTreeItemVersion;
        console.log('remove existing tree item', libpath, version);
        // TODO
    },

    linkTreeItem: async function({libpath, version}) {
        const btm = this.mgr.hub.repoManager.buildMgr;
        const selectedItem = btm.getItemByLibpathAndVersion(libpath, version);
        const items = btm.getAllDescendantsByLibpathAndVersion(libpath, version);
        items.unshift(selectedItem);
        const allHdos = [];
        for (const item of items) {
            const docRefs = item.docRefs || {};
            const newHdos = docRefs[this.docId] || [];
            allHdos.push(...newHdos);
        }
        await this.receiveHighlights(allHdos);
        this.linkedTreeItemLibpath = libpath;
        this.linkedTreeItemVersion = version;
    },

});


return PdfController;

});

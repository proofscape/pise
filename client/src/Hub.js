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

import { xhr, enrichXhrParams } from "browser-peers/src/util";
import { DedicatedWorkerPeer } from "browser-peers/src/dedworkerpeer";
import { ContentLoadTask } from "./delayed";
const otherVersions = require('../other-versions.json');


define([
    "dojo/_base/declare",
    "dojo/query",
    "dijit/Dialog",
    "dijit/ConfirmDialog",
    "ise/util"
], function(
    declare,
    query,
    Dialog,
    ConfirmDialog,
    iseUtil
){

/* The Hub class provides a central connection point, where the various
 * components of the application can be linked together.
 */
var Hub = declare(null, {

    // Properties
    PISE_version: null,
    appLayout: null,
    tabContainerTree: null,
    keyListener: null,
    socketManager: null,
    windowManager: null,
    menuManager: null,
    navManager: null,
    repoManager: null,
    contentManager: null,
    editManager: null,
    notesManager: null,
    chartManager: null,
    pdfManager: null,
    feedbackManager: null,
    resizeManager: null,
    studyManager: null,
    theorymapManager: null,
    pfscExtInterface: null,

    currentTheme: 'dark',
    currentGlobalZoom: 100,
    appUrlPrefix: '',
    csrf_token: null,
    reloadFromDisk: null,
    saveAllOnAppBlur: null,
    personalServerMode: null,
    ssnrAvailable: null,
    allowWIP: null,
    hostingByRequest: null,
    userInfo: null,
    bcastChannel: null,
    dismissalStorage: null,
    mathWorkerPeer: null,
    mathWorkerReady: null,
    pyodidePackageInfo: null,
    aboutPbeUrl: 'https://proofscape.org/download/pbe.html',
    bugReportUrl: 'https://github.com/proofscape/pise/issues',
    ocaUpgradeUrl: 'https://docs.proofscape.org/pise/basic.html#upgrading',

    OCA_version: null,
    OCA_checkForUpdates: null,
    OCA_updateCheckInterval: null,

    extraSoftware: null,
    notices: null,

    tosURL: null,
    tosVersion: null,
    prpoURL: null,
    prpoVersion: null,

    pdfjsURL: null,

    siblingScriptLoadingPromise: null,

    agreementAcceptanceStorage: null,
    tosVersionAcceptedKey: 'pfsc:tosVersionAccepted',
    prpoVersionAcceptedKey: 'pfsc:prpoVersionAccepted',
    ocaEulaVersionAcceptedKey: 'pfsc:ocaEulaVersionAccepted',

    appUrls: {
        static: '/static',
        makeNewSubmodule: '/ise/makeNewSubmodule',
        exampConstruct: '/ise/exampConstruct',
        loadSource: '/ise/loadSource',
        lookupGoals: '/ise/lookupGoals',
        loadAnnotation: '/ise/loadAnnotation',
        loadDashgraph: '/ise/loadDashgraph',
        loadRepoTree: '/ise/loadRepoTree',
        getModpath: '/ise/getModpath',
        makeIseStateUrlArgs: '/ise/makeIseStateUrlArgs',
        getTheoryMap: '/ise/getTheoryMap',
        renameModule: '/ise/renameModule',
        writeAndBuild: '/ise/writeAndBuild',
        modDiff: '/ise/modDiff',
        whoAmI: '/ise/whoAmI',
        userUpdate: '/ise/userUpdate',
        requestSsnr: '/ise/requestSsnr',
        recordNotes: '/ise/recordNotes',
        loadNotes: '/ise/loadNotes',
        requestHosting: '/ise/requestHosting',
        exportUserInfo: '/ise/exportUserInfo',
        purgeNotes: '/ise/purgeNotes',
        purgeUserAcct: '/ise/purgeUserAcct',
        login: '/auth/login',
        logout: '/auth/logout',
        checkLatestOcaVers: '/oca/latestVersion',
        getOcaEula: '/oca/EULA',
        extraAboutInfo: '/oca/extraAboutInfo',
    },

    // Methods
    constructor: function(
        appLayout,
        tabContainerTree,
        keyListener,
        socketManager,
        windowManager,
        menuManager,
        navManager,
        repoManager,
        contentManager,
        editManager,
        notesManager,
        chartManager,
        pdfManager,
        feedbackManager,
        resizeManager,
        studyManager,
        theorymapManager,
        pfscExtInterface
    ) {
        window.pfscisehub = this;
        this.PISE_version = PISE_VERSION;
        this.appUrls.staticISE = `/static/ise/v${this.PISE_version}`;

        this.setupGlobalRejectionHandler();

        this.restartMathWorker();

        this.appLayout = appLayout;

        this.dismissalStorage = window.localStorage;
        this.agreementAcceptanceStorage = window.localStorage;

        this.tabContainerTree = tabContainerTree;
        tabContainerTree.hub = this;

        this.keyListener = keyListener;
        keyListener.hub = this;

        this.socketManager = socketManager;
        socketManager.hub = this;

        this.windowManager = windowManager;
        windowManager.hub = this;

        this.menuManager = menuManager;
        menuManager.hub = this;

        this.navManager = navManager;
        navManager.hub = this;

        this.repoManager = repoManager;
        repoManager.hub = this;

        this.contentManager = contentManager;
        contentManager.hub = this;

        this.editManager = editManager;
        editManager.hub = this;

        this.notesManager = notesManager;
        notesManager.hub = this;

        this.chartManager = chartManager;
        chartManager.hub = this;

        this.pdfManager = pdfManager;
        pdfManager.hub = this;

        this.feedbackManager = feedbackManager;
        feedbackManager.hub = this;

        this.resizeManager = resizeManager;
        resizeManager.hub = this;

        this.studyManager = studyManager;
        studyManager.hub = this;

        this.theorymapManager = theorymapManager;
        theorymapManager.hub = this;

        this.pfscExtInterface = pfscExtInterface;
        pfscExtInterface.hub = this;
    },

    /* Any code that wants to load content should await this, to ensure we are ready.
     */
    contentLoadingOkay: async function() {
        await this.siblingScriptLoadingPromise;
    },

    getVersionStringForAboutDialog: function() {
        let v = this.OCA_version ? `oca-v${this.OCA_version}` : `v${this.PISE_version}`;
        // For now we're tacking -beta onto all version numbers. Should eventually remove this.
        v += '-beta';
        return v
    },

    getAgreementHtmlForAboutDialog: function() {
        if (this.OCA_version) {
            let h = 'By using this software you agree to the ';
            h += '<a href="javascript:pfscisehub.showEulaAndRequireAgreement()">EULA</a>.'
            return `<p>${h}</p>`;
        } else {
            return tosPrpoAgreementDialogContents(false, false, this.tosURL, this.prpoURL);
        }
    },

    getExtraSoftwareForAboutDialog: async function() {
        if (this.OCA_version) {
            if (this.extraSoftware === null) {
                await this.getExtraAboutDialogInfo();
            }
            return this.extraSoftware;
        } else {
            return [];
        }
    },

    getNoticesForAboutDialog: async function() {
        if (this.OCA_version) {
            if (this.notices === null) {
                await this.getExtraAboutDialogInfo();
            }
            return this.notices;
        } else {
            return [];
        }
    },

    getExtraAboutDialogInfo: async function() {
        const info = await this.xhrFor('extraAboutInfo', {
            handleAs: 'json',
        });
        this.extraSoftware = info.extraSoftware;
        this.notices = info.notices;
    },

    /* Write line about privacy policy for the hosting request dialog.
     *
     * Accepts optional state arg in case called before Hub has read the state.
     */
    getPrivacyPolicyHtmlForHostingRequestDialog: function(state) {
        state = state || this;
        const url = state.prpoURL;
        return url ?
            ` See our <a class="external" target="_blank" href="${url}">Privacy Policy</a>.` :
            '';
    },

    /* Start up a new math worker.
     *
     * return: Promise that resolves with object of the form {
     *  peer: the DedicatedWorkerPeer instance you'll use to communicate with the worker.
     *  result: the response from the peer's 'startup' method.
     * }
     */
    startupNewMathWorker: function() {
        const conf = window.pfsc_examp_config;

        conf.pyodideIndexURL = conf.pyodideIndexURL.replaceAll("VERSION", otherVersions.pyodide);

        const mitArray = [];
        for (let pkg in conf.micropipInstallTargets) {
            if (conf.micropipInstallTargets.hasOwnProperty(pkg)) {
                let url = conf.micropipInstallTargets[pkg];
                url = url.replaceAll("VERSION", otherVersions[pkg]);
                conf.micropipInstallTargets[pkg] = url;
                mitArray.push(url);
            }
        }
        conf.micropipInstallTargetsArray = mitArray;

        console.debug('filled pfsc_examp_config', conf);

        const mathWorker = new Worker(conf.mathworkerURL);
        const peer = new DedicatedWorkerPeer(mathWorker);

        return peer.postRequest('startup', {
            pyodideIndexURL: conf.pyodideIndexURL,
            micropipInstallTargetsArray: conf.micropipInstallTargetsArray,
            micropipNoDeps: conf.micropipNoDeps,
            pfscExampConfig: conf.vars,
        }, {doReadyCheck: true}).then(resp => {
            return {
                peer: peer,
                result: resp,
            };
        });
    },

    /* Really this is "(re)start math worker," i.e. it can be used both for the first
     * startup, and to terminate an existing worker and start up another.
     */
    restartMathWorker: function() {
        document.querySelector('body').classList.remove('pyodideLoaded');
        let trueRestart = false;
        if (this.mathWorkerPeer) {
            trueRestart = true;
            this.mathWorkerPeer.terminate();
            console.log('Math worker terminated.');
            this.mathWorkerPeer = null;
        }
        this.mathWorkerReady = this.startupNewMathWorker().then(info => {
            if (trueRestart) {
                this.notesManager.noteNewMathWorker();
            }
            this.mathWorkerPeer = info.peer;
            console.log('Math worker startup:', info.result);
            this.pyodidePackageInfo = info.result.pkginfo;
            document.querySelector('body').classList.add('pyodideLoaded');
        });
    },

    /* Ping the math worker. Return true if answered, false if timeout.
     */
    checkMathWorkerHealthy: async function(options) {
        const {
            timeout = 5000  // milliseconds
        } = options || {};
        await this.mathWorkerReady;
        try {
            await this.mathWorkerPeer.postRequest('ping', {}, {
                timeout: timeout,
            });
            return true;
        } catch (e) {
            return false;
        }
    },

    getCsrfToken: function() {
        return this.csrf_token;
    },

    /* Write the URL for a given role.
     *
     * options:
     *   addCsrfToken: boolean. If true, attach the CSRF token as a URL arg.
     *   addArgs: object. Attach arb key-value pairs as URL args.
     */
    urlFor: function(role, options) {
        let {
            addCsrfToken = false,
            addArgs = null,
        } = options || {};

        let url = this.appUrlPrefix + (this.appUrls[role] || '/');

        if (addCsrfToken) {
            addArgs = addArgs || {};
            addArgs.CSRF = this.csrf_token;
        }
        if (addArgs) {
            url += "?"+(new URLSearchParams(addArgs)).toString();
        }
        return url;
    },

    /* Wrapper for the basic `xhr` function, which ensures that the
     * CSRF token is set as the value of a "CSRF" argument.
     *
     * The "CSRF" argument is placed in `query` if that is defined, else
     * in `form` if that is defined. If neither is defined, then we define
     * `query` and put the "CSRF" argument in there.
     *
     * @param url: as in the basic `xhr` function
     * @param params: as in the basic `xhr` function
     */
    xhr (url, params) {
        params = enrichXhrParams(params, {"CSRF": this.csrf_token});
        return xhr(url, params);
    },

    xhrFor (role, params) {
        return this.xhr(this.urlFor(role), params);
    },

    toggleFullScreen: function() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            if (document.exitFullscreen) {
              document.exitFullscreen();
            }
        }
    },

    /* Generate a URL that can restore (most of) the current ISE state.
     *
     * return: promise that resolves with the desired URL
     */
    generateLink: function() {
        const state = this.describeState();
        return this.xhrFor('makeIseStateUrlArgs', {
            method: "POST",
            form: { state: JSON.stringify(state) },
            handleAs: 'json'
        }).then(resp => {
            if (this.errAlert3(resp)) return;
            const args = JSON.parse(resp.args);
            const arg_str = decodeURIComponent((new URLSearchParams(args)).toString());
            // Choosing from among the properties of `window.location`, we use
            // origin + pathname instead of href because the latter will include
            // any `#` fragment we may have as a result of clicking various <a> tags in the page.
            const origin = window.location.origin;
            const pathname = window.location.pathname;
            return `${origin}${pathname}?${arg_str}`;
        });
    },

    /* Build and return a serializable object representing a complete
     * description of the current state of the ISE.
     *
     * The format of the object is as follows:
     *
     * {
     *     autoSaveDelay: <int>,
     *     reloadFromDisk: <string>,
     *     saveAllOnAppBlur: <bool>,
     *     theme: <str>,
     *     zoom: <int>,
     *     showgoals: <bool>,
     *     noSocket: <bool>,
     *     sidebar: {
     *         isVisible: <bool>,
     *         width: <int>
     *     },
     *     trees: <object>,
     *     content: {
     *         tctStructure: <str[]>,
     *         tctSizeFractions: <float[]>,
     *         activeTcIndex: <int>,
     *         tcs: [
     *             {
     *                 tabs: <object[]>,
     *                 activeTab: <int>
     *             }
     *         ],
     *         linking: {
     *             C: [[u, x, w], [u, x, w], ...],
     *             D: [[u, x, w], [u, x, w], ...],
     *             N: [[u, x, w], [u, x, w], ...]
     *         }
     *     }
     * }
     *
     */
    describeState: function() {
        var state = {
            autoSaveDelay: this.editManager.getAutoSaveDelay(),
            reloadFromDisk: this.reloadFromDisk,
            saveAllOnAppBlur: this.saveAllOnAppBlur,
            theme: this.currentTheme,
            zoom: this.currentGlobalZoom,
            showgoals: this.studyManager.showgoals,
            selectionStyle: this.chartManager.defaultSelectionStyle,
            OCA_checkForUpdates: this.OCA_checkForUpdates,
        };

        // Sidebar
        state.sidebar = {
            isVisible: this.appLayout.sidebar._showing,
            width: this.appLayout.sidebar._currentSize.w,
        };

        // Trees
        state.trees = this.repoManager.describeState();

        // Content
        var content = {};

        // Tab container tree split structure...
        content.tctStructure = this.tabContainerTree.computeTreeDescrip();
        // ...and sizes
        content.tctSizeFractions = this.tabContainerTree.getLeftSizeFractions();

        // TabContainers ("tcs") array:
        // This will contain one entry per tab container currently open,
        // in the natural tree traversal order.
        // The entry for each tab container will be of the form
        //  {
        //    tabs: [INFO0, INFO1, ..., INFOn],
        //    activeTab: <INDEX>
        //  }
        // where `tabs` gives an array of info objects, one describing the
        // contents of each tab, in the order in which they appear
        // from left to right,
        // while `activeTab` gives an index into that array,
        // indicating which is the active tab.
        //
        // While we work, we also generate a mapping from pane IDs to
        // strings `i:j` indicating the tab container (i) and tab (j) in
        // which that pane is found. This may be useful for subsequent steps in
        // recording the state. (Currently not; used to be used for recording the WGCM.)
        var tcs = [];
        var paneId2ij = {};
        var activeTcIndex = null;
        var tcids = this.tabContainerTree.getTcIds();
        for (var i in tcids) {
            var id = tcids[i];
            var tc = this.tabContainerTree.getTC(id);
            if (this.tabContainerTree.tcIsActive(tc)) {
                activeTcIndex = i;
            }
            var selectedPane = tc.selectedChildWidget;
            var selectedId = selectedPane ? selectedPane.id : null;
            var activeTabIndex = -1;
            var contentPanes = tc.getChildren();
            var tabInfos = [];
            var serialOnly = true;
            for (var j in contentPanes) {
                var pane = contentPanes[j];
                if (pane.id === selectedId) {
                    activeTabIndex = j;
                }
                paneId2ij[pane.id] = i+":"+j;
                var info = this.contentManager.getCurrentStateInfo(pane, serialOnly);
                tabInfos.push(info);
            }
            var tcInfo = {
                tabs: tabInfos,
                activeTab: activeTabIndex
            };
            tcs.push(tcInfo);
        }
        content.tcs = tcs;

        content.activeTcIndex = activeTcIndex;

        // Note: we want only local triples, because we only want to describe the state of *this* window,
        // not any other. This is a synchronous method, so no need to await.
        content.linking = {
            C: this.chartManager.linkingMap.localComponent.getTriples({}),
            D: this.pdfManager.linkingMap.localComponent.getTriples({}),
            N: this.notesManager.linkingMap.localComponent.getTriples({}),
        };

        state.content = content;

        return state;
    },

    /* Pass an ISE state description to be recorded, or pass no args to
     * compute a description of the current state and record that.
     */
    recordState: function(state) {
        state = state || this.describeState();
        window.localStorage.setItem('pfsc:iseState', JSON.stringify(state));
    },

    restoreSettings: function(state) {
        if (typeof(state.CSRF) !== 'undefined') this.csrf_token = state.CSRF;
        if (typeof(state.appUrlPrefix) !== 'undefined') this.setAppUrlPrefix(state.appUrlPrefix);
        if (typeof(state.reloadFromDisk) !== 'undefined') this.setReloadFromDisk(state.reloadFromDisk);
        if (typeof(state.saveAllOnAppBlur) !== 'undefined') this.setSaveAllOnAppBlur(state.saveAllOnAppBlur);
        if (typeof(state.autoSaveDelay) !== 'undefined') this.editManager.setAutoSaveDelay(state.autoSaveDelay);
        if (typeof(state.personalServerMode) !== 'undefined') this.personalServerMode = state.personalServerMode;
        if (typeof(state.ssnrAvailable) !== 'undefined') this.ssnrAvailable = state.ssnrAvailable;
        if (typeof(state.allowWIP) !== 'undefined') this.allowWIP = state.allowWIP;
        if (typeof(state.hostingByRequest) !== 'undefined') this.hostingByRequest = state.hostingByRequest;
        if (typeof(state.OCA_version) !== 'undefined') this.OCA_version = state.OCA_version;

        if (typeof(state.tosURL) !== 'undefined') this.tosURL = state.tosURL;
        if (typeof(state.tosVersion) !== 'undefined') this.tosVersion = state.tosVersion;
        if (typeof(state.prpoURL) !== 'undefined') this.prpoURL = state.prpoURL;
        if (typeof(state.prpoVersion) !== 'undefined') this.prpoVersion = state.prpoVersion;

        if (typeof(state.pdfjsURL) !== 'undefined') this.pdfjsURL = state.pdfjsURL.replaceAll("VERSION", otherVersions["pfsc-pdf"]);

        if (typeof(state.theme) !== 'undefined') this.setTheme(state.theme);
        if (typeof(state.zoom) !== 'undefined') this.setZoom(state.zoom);
        if (typeof(state.showgoals) !== 'undefined') this.studyManager.setGoalBoxVisibility(state.showgoals);
        if (typeof(state.selectionStyle) !== 'undefined') this.chartManager.setDefaultSelectionStyle(state.selectionStyle);
        if (typeof(state.OCA_checkForUpdates) !== 'undefined') this.setUpdateCheckMode(state.OCA_checkForUpdates);
    },

    /* Given a state description object of the kind returned by our
     * `describeState` method, restore that state.
     */
    restoreState: function(state) {
        this.restoreSettings(state);
        // Note: state.sidebar settings are handled in AppLayout.js
        this.restoreContent(state);
    },

    restoreContent: function(state) {
        let treeLoading = Promise.resolve([]);
        if (typeof(state.trees) !== 'undefined') {
            treeLoading = this.repoManager.restoreState(state.trees);
        }
        treeLoading.then(delayed => {
            if (typeof(state.content) !== 'undefined') {
                const content = state.content;
                // We "consume" the content, so that if other windows are opened, they don't also load it.
                delete state.content;
                this.recordState(state);
                const task = new ContentLoadTask(this, delayed, content);
                task.activate();
            }
        });
    },

    loadContentByDescription: async function(content) {
        // We need a clean slate. So close all tabs, and remove all splits.
        this.tabContainerTree.closeAllPanes();
        // Set the desired split structure...
        this.tabContainerTree.makeStructure(content.tctStructure);
        // ...and sizes
        if (typeof(content.tctSizeFractions) !== 'undefined') {
            this.tabContainerTree.setLeftSizeFractions(content.tctSizeFractions);
        }
        // Load tabs.
        const tcs = content.tcs;
        const tcids = this.tabContainerTree.getTcIds();
        const uuids = new Set();
        for (let i of Object.keys(tcs)) {
            const tcInfo = tcs[i];
            const tcId = tcids[i];
            const tcTabInfos = tcInfo.tabs;
            const activeTabIndex = tcInfo.activeTab;
            let activePane = null;
            for (let j of Object.keys(tcTabInfos)) {
                const info = tcTabInfos[j];
                if (info.uuid) {
                    uuids.add(info.uuid);
                }
                const { pane, promise } = this.contentManager.openContentInTC(info, tcId);
                // Do not start loading another panel until after this one has finished loading.
                // This prevents issues with attempts to set up default links for one panel, while
                // another, or others, are in the process of loading and thus only partially initialized.
                await promise;
                // Be sure to compare j and activeTabIndex _as integers_.
                if (+j === +activeTabIndex) {
                    activePane = pane;
                }
            }
            if (activePane !== null) {
                this.tabContainerTree.selectPane(activePane);
            }
        }
        // Set active tab container.
        // (Need all content loaded first, so that NavManager can get a valid reading.)
        // Careful: use typeof test, since index could be zero!
        if (typeof(content.activeTcIndex) !== 'undefined') {
            const tcId = tcids[content.activeTcIndex];
            this.tabContainerTree.setActiveTcById(tcId);
        }
        // Re-establish links
        if (content.linking) {
            for (const [key, mgr] of [
                ["C", this.chartManager], ["D", this.pdfManager], ["N", this.notesManager],
            ]) {
                for (const [u, x, w] of (content.linking[key] || [])) {
                    if (await this.contentManager.uuidExistsInAnyWindow(w)) {
                        // No need to check for existence of `u`, since it will automatically
                        // only be added in that window (if any) where u exists.
                        await mgr.linkingMap.add(u, x, w);
                    }
                }
            }
        }
    },

    /* This is a place for any actions that need to be performed upon setting up
     * the ISE, but which must (or can) wait until after Hub.restoreState().
     */
    finalSetup: function() {
        this.setupBroadcastChannel();
        this.updateUser();
        this.checkAgreements();
    },

    /* Check that the user has agreed to the current versions of the applicable legal agreements.
     * If not, show an agreement dialog box, and update records accordingly.
     */
    checkAgreements: async function() {
        if (this.OCA_version) {
            const acceptedVersion = this.agreementAcceptanceStorage.getItem(this.ocaEulaVersionAcceptedKey);
            if (acceptedVersion !== this.OCA_version) {
                // Show EULA dialog.
                // On close, record OCA_version as the accepted version.
                console.debug('must get agreement for EULA', this.OCA_version);
                await this.showEulaAndRequireAgreement();
                this.agreementAcceptanceStorage.setItem(this.ocaEulaVersionAcceptedKey, this.OCA_version);
            }
        } else if (this.tosVersion || this.prpoVersion) {
            const acceptedTosVersion = this.agreementAcceptanceStorage.getItem(this.tosVersionAcceptedKey);
            const acceptedPrpoVersion = this.agreementAcceptanceStorage.getItem(this.prpoVersionAcceptedKey);
            const needTos = (acceptedTosVersion !== this.tosVersion);
            const needPrpo = (acceptedPrpoVersion !== this.prpoVersion);
            const updatedTos = needTos && (acceptedTosVersion !== null);
            const updatedPrpo = needPrpo && (acceptedPrpoVersion !== null);
            if (needTos || needPrpo) {
                // Show ToS / PrPo dialog.
                // On close, record the current versions as the accepted versions.
                console.debug('must get agreement for ToS/PrPo', needTos, needPrpo);
                await this.showToSPrPoAndRequireAgreement(updatedTos, updatedPrpo);
                this.agreementAcceptanceStorage.setItem(this.tosVersionAcceptedKey, this.tosVersion);
                this.agreementAcceptanceStorage.setItem(this.prpoVersionAcceptedKey, this.prpoVersion);
            }
        }
    },

    showEulaAndRequireAgreement: async function() {
        if (!this.OCA_version) return;
        const eulaText = await this.xhrFor('getOcaEula');
        const content = `<pre>${eulaText}</pre>`;
        let agreed = false;
        while (!agreed) {
            const result = await this.choice({
                title: "EULA",
                content: content,
                okButtonText: "Agree",
                cancelButtonText: "Do Not Agree",
                mustShow: true
            });
            agreed = result.accepted;
        }
    },

    showToSPrPoAndRequireAgreement: async function(updatedTos, updatedPrpo) {
        const content = tosPrpoAgreementDialogContents(updatedTos, updatedPrpo, this.tosURL, this.prpoURL);
        let agreed = false;
        while (!agreed) {
            const result = await this.choice({
                title: "Agreements",
                content: content,
                okButtonText: "Agree",
                cancelButtonText: "Do Not Agree",
                mustShow: true
            });
            agreed = result.accepted;
        }
    },

    /* Set the policy as to whether, if we're running the OCA, we'll check
     * for software updates.
     *
     * param mode: "yes" or "no"
     */
    setUpdateCheckMode: function(mode) {
        if (!this.OCA_version) {
            return;
        }
        this.menuManager.pfsc_update_dropdown.val(mode);
        const doCheck = (mode === 'yes');
        const changing = (this.OCA_checkForUpdates !== mode && this.OCA_checkForUpdates !== null);
        this.OCA_checkForUpdates = mode;
        if (doCheck) {
            // Set to check once a day.
            const dt = 24*60*60*1000;
            this.OCA_updateCheckInterval = window.setInterval(
                this.checkOcaForUpdates.bind(this), dt);
            // Also check right now.
            this.checkOcaForUpdates().then(foundNew => {
                if (changing && !foundNew) {
                    this.alert({
                        title: "Updates",
                        content: `
                        <p>There are currently no updates.</p>
                        <p>Will check automatically once a day, and on startup.</p>
                        `
                    })
                }
            });
        } else {
            window.clearInterval(this.OCA_updateCheckInterval);
            if (changing) {
                /* Reason for timeout: If you instead open the alert immediately, we're
                 * getting some weird error:
                 *   "Cannot read properties of null (reading '_closePopup')"
                 * from Dojo's _MenuBase.js, line 419. Maybe the alert popup is somehow
                 * conflicting with the one from the menu? Don't know. Only happens when
                 * setting the updates to "No", not when setting to "Yes".
                 */
                setTimeout(() => {
                    this.alert({
                        title: "Updates",
                        content: `
                        <p>Will not check for updates.</p>
                        <p>You can always perform a manual check by first noting<br>
                        the version number you are running (from the PISE menu,<br>
                        "About" dialog), and then visiting Docker Hub to see what<br>
                        is the latest version available.</p>
                        `
                    });
                });
            }
        }
    },

    /* If we're running the OCA, check to see if we're on the latest version,
     *
     * return: Promise that resolves to a boolean, which is true iff we found
     *   that there is a newer version available.
     */
    checkOcaForUpdates: function() {
        if (!this.OCA_version) {
            return Promise.resolve(false);
        }
        return this.xhrFor('checkLatestOcaVers').then(vers => {
            if (!vers) {
                this.errAlert('Unable to check for software updates.');
                return false;
            } else {
                const ours = this.OCA_version.split(/\.|-/);
                const latest = vers.split(/\.|-/);
                console.debug(ours, latest);
                if (ours < latest) {
                    console.debug('Newer OCA version is available.');
                    this.alert({
                        title: 'Newer Version Available',
                        content: `
                                <p>A newer version of PISE is available for download.</p>
                                <p>
                                You can find instructions for how to upgrade
                                <a class="external" target="_blank" href="${this.ocaUpgradeUrl}">here</a>.
                                </p>
                            `,
                    });
                    return true;
                } else {
                    console.debug('There is no newer OCA version available.');
                    return false;
                }
            }
        });
    },

    setupBroadcastChannel: function() {
        this.bcastChannel = new BroadcastChannel('login-messages');
        this.bcastChannel.addEventListener('message', event => {
            if (event.data === 'login-successful') {
                console.debug('updateUser after `login-successful` event');
                this.updateUser();
            }
        });
    },

    /*
    * param theme: `light` or `dark`
    */
    setTheme: function(theme) {
        //console.log('setTheme');
        // Make sure interface widgets are in agreement.
        this.menuManager.config_theme_dropdown.val(theme);
        // Set CSS class in body element
        if (theme === 'dark') {
            query('body').removeClass('themeLight').addClass('themeDark');
        } else {
            query('body').removeClass('themeDark').addClass('themeLight');
        }
        // Other managers
        this.editManager.setTheme(theme);
        this.pdfManager.setTheme(theme);
        this.notesManager.setTheme(theme);
        // Store the new theme value.
        this.currentTheme = theme;
    },

    /*
    * param zoom: An integer, being a multiple of 10, between 50 and 200 inclusive.
    *             In other words, an element of the set {50, 60, 70, ..., 200}.
    *             This indicates the percentage zoom that you want, ranging from
    *             half-size to double-size.
    */
    setZoom: function(zoom) {
        //console.log('setZoom');
        // Make sure interface widgets are in agreement.
        this.menuManager.config_zoom_dropdown.val(zoom);
        // Set CSS class.
        var newZoomLevel = zoom,
            oldZoomLevel = this.currentGlobalZoom,
            newZoomClass = "zoom"+newZoomLevel,
            oldZoomClass = "zoom"+oldZoomLevel;
        query('#appLayout').removeClass(oldZoomClass).addClass(newZoomClass);
        // Store the new value.
        this.currentGlobalZoom = newZoomLevel;
        // Ask the EditManager to update all editors.
        var fs = this.getCurrentEditorFontSize();
        this.editManager.setFontSize(fs);
    },

    setAppUrlPrefix: function(prefix) {
        this.appUrlPrefix = prefix;
    },

    setReloadFromDisk: function(method) {
        this.reloadFromDisk = method;
    },

    setSaveAllOnAppBlur: function(b) {
        this.saveAllOnAppBlur = b;
    },

    getCurrentEditorFontSize: function() {
        var z = this.currentGlobalZoom,
            fs = Math.round(12*z/100);
        return fs;
    },

    whoAmI: function() {
        return this.xhrFor('whoAmI', {
            handleAs: 'json'
        });
    },

    updateUser: function() {
        return this.whoAmI().then(info => {
            //console.log('whoami:', info);
            this.userInfo = info;
            this.menuManager.updateForUser();
            this.studyManager.updateForUser();
            this.editManager.updateForUser();
        });
    },

    isLoggedIn: function() {
        return this.userInfo && this.userInfo.username;
    },

    getUsername: function() {
        return this.isLoggedIn() ? this.userInfo.username : null;
    },

    getEmail: function() {
        return this.isLoggedIn() ? this.userInfo.props?.EMAIL : null;
    },

    /* Test whether the user (a) is currently logged in, and (b), if so, owns
     * a given libpath. This is so if the owner segment of the given libpath
     * equals the user's user segment, or equals the name of one of the
     * orgs owned by the user.
     */
    userOwns: function(libpath) {
        const d = this.getHostUserOrgs();
        if (d === null) {
            return false;
        }
        const {host, user, orgs} = d;

        const parts = libpath.split('.');
        if (parts.length < 2) {
            return false;
        }
        if (parts[0] !== host) {
            return false;
        }

        const owner = parts[1];
        return owner === user || orgs.includes(owner);
    },

    /* If user is logged in, return object of the form: {
     *   host: host segment of username,
     *   user: user segment of username,
     *   orgs: array of owned orgs
     * }
     * Else return null.
     */
    getHostUserOrgs: function() {
        const username = this.getUsername();
        if (!username) {
            return null;
        }
        const [host, user] = username.split('.');
        const orgs = this.userInfo?.props?.OWNED_ORGS || [];
        return {host, user, orgs};
    },

    isDemoLibpath: function(libpath) {
        const parts = libpath.split('.');
        return parts.length >= 3 && parts[0] === 'demo';
    },

    /* Test whether the user is expected to have read/write access to a given libpath.
     *
     * To be precise, this means either that the server is in PSM (personal server
     * mode), or that the libpath belongs to a demo repo, or that the user appears to
     * own the libpath.
     *
     * As a client-side method, this of course has nothing to do with security,
     * and everything to do with convenience. The idea is to help prevent the client
     * from making some requests that are only going to result in an error response
     * from the server, due to insufficient permissions.
     */
    userHasAccess: function(libpath) {
        return this.personalServerMode || this.isDemoLibpath(libpath) || this.userOwns(libpath);
    },

    /* Loss of focus means the user is preparing to interact with some other application
     * or interface. This then is the appropriate time to do things like save all open
     * documents, in case the user wants to now edit them somewhere else. It also means
     * that regaining focus is the time to restore docs from disk (if that option is
     * configured) in case they were edited elsewhere.
     */
    noteAppFocus: function(isFocused) {
        //console.log('focused: ', isFocused);
        if (!isFocused) {
            // App has lost focus.
            //console.log('hub blurred');
            if (this.saveAllOnAppBlur) {
                // Save all open modules to disk.
                this.editManager.saveAll();
            }
        } else {
            // App has regained focus.
            //console.log('hub focused');
            if (!this.personalServerMode) {
                console.debug('updateUser after app regained focus');
                this.updateUser();
            }
            // Mostly we let EditManager decide what to do based on the configured method;
            // however, we do not allow one combination: If the reload policy is 'auto', but
            // we are _not_ saving on blur, then we do not allow it.
            if (this.saveAllOnAppBlur || this.reloadFromDisk !== 'auto') {
                this.editManager.reloadAllDocs(this.reloadFromDisk);
            }
            // FIXME
            // For now, reloading all filesystem trees automatically is too annoying.
            // It should only result in a visible change if anything actually _has_ changed.
            // (And then it should make as subtle a visual disturbance as possible.)
            // Until we're ready to rewrite it that way, we'll just have to leave the user
            // to request a refresh manually via context menu option.
            //this.repoManager.reloadAllFsTrees();
        }
    },

    /* The app's visibility (but not necessarily its focus) will be changing when the
     * user is involved with things like going to another browser tab to
     * install the PBE, or grant the PBE a host permission. So we use this event to
     * trigger things that should happen after coming back to the ISE's browser tab.
     */
    noteVisibilityChange: function(isVisible) {
        //console.log('visible: ', isVisible);
        if (isVisible) {
            if (!this.personalServerMode) {
                console.debug('updateUser after app regained visibility');
                this.updateUser();
            }
            this.pdfManager.retryPausedDownloads();
        }
    },

    /* The app is being unloaded. This includes closing the window or tab,
     * reloading the page, or navigating to a new page.
     *
     * If we are the first, or the only Proofscape window, we record our state.
     */
    noteAppUnload: function() {
        // Important to record the state first, since when the ContentManager handles
        // the closing window below, it will take away things like linked panels, which
        // we want to record as a part of the state.
        this.recordStateIfSoleWindow();
        this.contentManager.handleClosingWindow();
    },

    recordStateIfSoleWindow: function() {
        const { allNumbers } = this.windowManager.getNumbers();
        if (allNumbers.length < 2) {
            this.recordState();
        }
    },

    // ------------------------------------------------------------------------
    // Useful stuff during development.

    /* Stops socketio.js from trying to reconnect
     * while the server is down, which can make the processor overheat if it goes on
     * long enough.
     */
    chill: function() {
        this.socketManager.socket.disconnect();
        console.log('WebSocket disconnected. Call `reconnect()` method to reconnect.');
    },

    reconnect: function() {
        this.socketManager.socket.connect();
    },

    /* Clears out various notations from localStorage, so that we can try things again
     * (like dismissing dialogs).
     */
    eraseNotation: function(nickname) {
        switch (nickname) {
            case 'wipnotes':
                this.dismissalStorage.removeItem('pfsc:dismiss:recordNotesAtWIP');
                break;
            case 'eula':
                this.agreementAcceptanceStorage.removeItem(this.ocaEulaVersionAcceptedKey);
                break;
            case 'tos':
                this.agreementAcceptanceStorage.removeItem(this.tosVersionAcceptedKey);
                break;
            case 'prpo':
                this.agreementAcceptanceStorage.removeItem(this.prpoVersionAcceptedKey);
                break;
            default:
                console.log('Unknown nickname');
        }
    },

    // ------------------------------------------------------------------------

    /* Show a ConfirmDialog (two buttons).
     *
     * title: The title of the dialog box.
     * content: HTML to be displayed as the content of the box.
     * okButtonText: text to appear on the "OK" button (default "OK")
     * cancelButtonText: text to appear on the "Cancel" button (default "Cancel")
     * dismissCode: if defined, should be a unique string representing this particular choice.
     *   In that case, a checkbox will be displayed. If checked by the user, the dismissal will
     *   be recorded in localStorage. Subsequent calls to open this same choice dialog will not show it.
     *   A prefix of 'pfsc:dismiss:' will automatically be prepended before writing to localStorage, so
     *   you do not need to supply any such prefix.
     * dismissMessage: text to go beside the dismissal checkbox. Defaults to "Do not show this again."
     * mustShow: set true to ensure a dialog is shown, no matter what dismissal settings may have
     *   been made in local storage.
     * onShow: optional callback to be called after the dialog is shown.
     *
     * return: Promise resolving with object of the form {
     *   shown: true if the dialog was shown (false if it was previously dismissed),
     *   accepted: if shown, then: true if "OK" was clicked, false if "Cancel" was clicked,
     *   dismissed: if shown, then: true if dismissal checkbox was shown and user checked it, false otherwise
     *   dialog: the ConfirmDialog instance that was shown
     * }
     */
    choice : function({title, content, okButtonText, cancelButtonText, dismissCode, dismissMessage, mustShow, onShow}) {
        okButtonText = okButtonText || "OK";
        cancelButtonText = cancelButtonText || "Cancel";
        dismissMessage = dismissMessage || "Do not show this again.";
        onShow = onShow || (() => {});
        const dismissalPrefix = 'pfsc:dismiss:';
        if (!mustShow) {
            if (dismissCode && this.dismissalStorage.getItem(dismissalPrefix + dismissCode)) {
                return Promise.resolve({
                    shown: false,
                });
            }
        }
        const storage = this.dismissalStorage;
        return new Promise(resolve => {
            function handleChoice(dlg, accepted) {
                let dismissed = false;
                const cb = dlg.domNode.querySelector('input[name="pfsc-choice-dismiss"]');
                if (cb?.checked) {
                    dismissed = true;
                    const code = cb.getAttribute('pfsc-data-dismissCode');
                    storage.setItem(dismissalPrefix + code, true);
                }
                resolve({
                    shown: true,
                    accepted: accepted,
                    dismissed: dismissed,
                    dialog: dlg,
                });
            }
            const dlg = new ConfirmDialog({
                title: title,
                content: content + (dismissCode ? `
                    <div class="iseChoiceDismissalBox">
                        <label>
                            <input type="checkbox" name="pfsc-choice-dismiss" pfsc-data-dismissCode="${dismissCode}">
                            ${dismissMessage}
                        </label>
                    </div>` : ''),
                onExecute: function() {
                    handleChoice(this, true);
                },
                onCancel: function() {
                    handleChoice(this, false);
                },
                onShow: onShow,
            });
            dlg.set('buttonOk', okButtonText);
            dlg.set('buttonCancel', cancelButtonText);
            dlg.show();
        });
    },

    alert: function({title, content}) {
        title = title || 'Info';
        content = content || '(nothing here)';
        content = `<div class="padded20">${content}</div>`;
        const dlg = new Dialog({
            title: title,
            content: content,
        });
        dlg.show();
    },

    errAlert: function(message) {
        if (message) {
            this.alert({
                title: "Error",
                content: message,
            });
        } else {
            console.log('Missing error message, in Hub.errAlert');
        }
    },

    errAlert2: function(resp) {
        this.alert({
            title: `Error ${resp.err_lvl}`,
            content: resp.err_msg,
        });
    },

    errAlert3: function(resp) {
        const is_error = resp.err_lvl > 0;
        if (is_error) {
            this.errAlert2(resp);
        }
        return is_error;
    },

    setupGlobalRejectionHandler: function() {
        window.addEventListener('unhandledrejection', event => {
            //console.log(event.promise);
            this.errAlert(event.reason.message);
        });
    },

    showCookieNoticeAsNeeded: function() {
        const acceptance_cookie_name = 'pfsc_ise_cookie_policy_acceptance';
        if (!this.personalServerMode && !iseUtil.getCookie(acceptance_cookie_name)) {
            const msg = `
            The Proofscape ISE uses your browser's
            <a class="external" target="_blank" href="https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies">cookie</a> and
            <a class="external" target="_blank" href="https://developer.mozilla.org/en-US/docs/Web/API/Web_Storage_API">local storage</a> capabilities
            only in ways that are necessary for its proper functioning, including retaining your settings for you.
            It does not use these to track you in any way.
            `;
            iseUtil.showCornerNoticeBox(msg, 'Accept', 'll', {
                width: '300px',
                'text-align': 'justify',
            }).then(() => {
                iseUtil.setCookie(acceptance_cookie_name, 1, 3650);
            });
        }
    },

});

function tosPrpoAgreementDialogContents(updatedTos, updatedPrpo, tosURL, prpoURL) {
    let h = '';
    if (updatedTos) {
        h += `
        <p>We've updated our Terms of Service!<br>
        You must agree to the new terms to continue using this site.
        </p>
        `;
    }
    if (updatedPrpo) {
        h += `
        <p>We've updated our Privacy Policy!<br>
        You must agree to the new policy to continue using this site.
        </p>
        `;
    }

    let links = '';
    if (tosURL) {
        links += `<a class="external" target="_blank" href="${tosURL}">Terms of Service</a>`;
    }
    if (tosURL && prpoURL) {
        links += ' and ';
    }
    if (prpoURL) {
        links += `<a class="external" target="_blank" href="${prpoURL}">Privacy Policy</a>`;
    }

    if (links) {
        h += `
        <p>
        By using this site you agree to the ${links}.
        </p>
        `;
    }
    return h;
}

return Hub;
});

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

import { ExtensionClient } from "browser-peers/src/ext";
import { SocketManager } from "./mgr/SocketManager";
import { WindowManager } from "./mgr/WindowManager";
import { RepoManager } from "./trees/RepoManager";

require("pfsc-moose/src/css/moose.css")

define([
    "dojo/ready",
    "ise/AppLayout",
    "ise/mgr/ContentManager",
    "ise/TabContainerTree",
    "ise/mgr/MenuManager",
    "ise/mgr/NavManager",
    "ise/content_types/source/EditManager",
    "ise/content_types/notes/NotesManager",
    "ise/content_types/chart/ChartManager",
    "ise/content_types/pdf/PdfManager",
    "ise/mgr/FeedbackManager",
    "ise/mgr/ResizeManager",
    "ise/mgr/StudyManager",
    "ise/content_types/chart/TheorymapManager",
    "ise/KeyListener",
    "ise/Hub",
    "ise/util",
    "css!dijit/themes/claro/claro.css",
    "css!dojox/layout/resources/ExpandoPane.css",
    "css!dragula/dist/dragula.css",
    "css!ise/css/pfsc.css",
    "css!ise/css/ise.css",
    "css!ise/examp/examp.css"
], function(
    ready,
    AppLayout,
    ContentManager,
    TabContainerTree,
    MenuManager,
    NavManager,
    EditManager,
    NotesManager,
    ChartManager,
    PdfManager,
    FeedbackManager,
    ResizeManager,
    StudyManager,
    TheorymapManager,
    KeyListener,
    Hub,
    iseUtil
) {

async function loadScripts() {
    const urlTemplates = window.pfsc_other_scripts;

    const mathjaxUrl = urlTemplates.mathjax.replaceAll("VERSION", MATHJAX_VERSION);
    await iseUtil.loadScript(mathjaxUrl);

    const elkjsUrl = urlTemplates.elkjs.replaceAll("VERSION", ELKJS_VERSION);
    await iseUtil.loadScript(elkjsUrl);
}

function computeState() {
    // The "computed state" (cs) will be a function of three inputs, which we call
    // the "default state" (ds), the "previous state" (ps) and the "served state" (ss).
    const ds = {
        theme: 'dark',
        zoom: 100,
        autoSaveDelay: 2000,
        reloadFromDisk: 'auto',
        saveAllOnAppBlur: true,
        showgoals: true,
        selectionStyle: 'NodeEdges',
        enablePdfProxy: false,
        offerPdfLibrary: false,
        appUrlPrefix: '',
        devMode: false,
        personalServerMode: false,
        ssnrAvailable: false,
        allowWIP: false,
        hostingByRequest: false,
        OCA_checkForUpdates: 'yes',
        loginsPossible: true,
    };
    const ps = JSON.parse( window.localStorage.getItem('pfsc:iseState') || "{}" );
    const ss = window.pfsc_ISE_state || {};
    // If there were any errors in processing URL args that go toward defining the
    // served state, there will be a positive error level.
    if (ss.err_lvl > 0) {
        const msg = 'Error in processing URL args: ' + ss.err_msg;
        console.error(msg);
    }
    // computed state:
    const cs = {};
    // simple order of precedence: ss > ps > ds:
    iseUtil.assign(cs, ['theme', 'zoom'], [ss, ps, ds]);
    // server has no say on these:
    iseUtil.assign(cs, ['showgoals', 'selectionStyle', 'OCA_checkForUpdates'], [ps, ds]);
    // these attributes should always be as served; we have defaults just as a backup:
    iseUtil.assign(cs, [
        'autoSaveDelay', 'reloadFromDisk', 'saveAllOnAppBlur', 'enablePdfProxy',
        'offerPdfLibrary', 'appUrlPrefix', 'devMode', 'personalServerMode', 'ssnrAvailable',
        'allowWIP', 'hostingByRequest', 'loginsPossible',
    ], [ss, ds]);
    // served only; default undefined:
    iseUtil.assign(cs, [
        'noSocket', 'CSRF', 'OCA_version',
        'tosURL', 'tosVersion', 'prpoURL', 'prpoVersion',
        'pdfjsURL',
    ], [ss]);
    // no default here, so just ss > ps, or else undefined:
    iseUtil.assign(cs, ['sidebar', 'trees', 'content'], [ss, ps]);
    return cs;
}

function construct(ISE_state) {
    // Build the home div for the application.
    // Looks like: <div id="appLayout" class="pfsc-ise"></div>
    const homeDiv = document.createElement('div');
    const homeId = "appLayout";
    homeDiv.setAttribute('id', homeId);
    homeDiv.classList.add("pfsc-ise");
    homeDiv.setAttribute('data-proofscape-ise-vers', PISE_VERSION);
    document.body.appendChild(homeDiv);

    // The AppLayout constructs the basic layout elements for the app.
    const appLayout = new AppLayout(homeId, ISE_state);
    // We need our ContentManager now, so we can pass its `openCopy` method to the TabContainerTree.
    const contentManager = new ContentManager();
    // Make a TabContainerTree, to manage all the tabs and splits.
    const tct = new TabContainerTree(appLayout.tctSocket, {
        openCopy: contentManager.openCopy.bind(contentManager)
    });
    // Layout elements in DojoToolkit need to be "started up".
    appLayout.startup();
    // Now we can set the TCT in the ContentManager.
    contentManager.setTabContainerTree(tct);

    // Make a ResizeManager, and add to it any important layout elements that already exist.
    const resizeManager = new ResizeManager(tct);
    resizeManager.addBorderContainer(appLayout.mainLayout);
    resizeManager.addExpandoPane(appLayout.sidebar);

    // Instantiate each of the remaining "Manager" types that we need.
    const socketManager = new SocketManager(ISE_state);
    const windowManager = new WindowManager(tct);
    const menuManager = new MenuManager(tct);
    const navManager = new NavManager(tct);
    const repoManager = new RepoManager(appLayout.librarySocket, ISE_state);
    const editManager = new EditManager(tct);
    const notesManager = new NotesManager();
    const chartManager = new ChartManager();
    const pdfManager = new PdfManager(ISE_state);
    const feedbackManager = new FeedbackManager(appLayout.feedbackSocket);
    const studyManager = new StudyManager();
    const theorymapManager = new TheorymapManager();
    const keyListener = new KeyListener(homeDiv, tct);
    const pfscExtInterface = new ExtensionClient(`pbeClient-@(${(new Date()).toISOString()})-${Math.random()}`,
        'pbeServer', 'pfsc-ext', '#appLayout.pfsc-ise', 'data-pbe-vers'
    );

    // And connect them all through a Hub.
    const hub = new Hub(
        appLayout,
        tct,
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
    );

    // A number of our classes have setup steps that need to be done after
    // linking together through the Hub.
    menuManager.buildMenus(ISE_state);
    keyListener.activate();
    windowManager.activate();
    editManager.activate();
    chartManager.activate(ISE_state);
    notesManager.activate();
    repoManager.activate();
    studyManager.activate();
    pdfManager.activate();
    contentManager.activate();

    // Listen for window focus changes and document visibility changes.
    window.addEventListener("focus", function(){
        hub.noteAppFocus(true);
    }, false);
    window.addEventListener("blur", function(){
        hub.noteAppFocus(false);
    }, false);
    document.addEventListener("visibilitychange", function(event){
        hub.noteVisibilityChange(document.visibilityState === 'visible');
    }, false);

    // Listen for any event in which the page is unloaded.
    window.addEventListener("beforeunload", function(){
        hub.noteAppUnload();
    }, false);

    return hub;
}

function startup() {
    const ISE_state = computeState();
    const hub = construct(ISE_state);
    hub.siblingScriptLoadingPromise = loadScripts();
    hub.restoreState(ISE_state);
    hub.showCookieNoticeAsNeeded();
    hub.finalSetup();
}

ready(startup);

});

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


define([
    "dojo/_base/declare",
    "dojo/query",
    "dojo/dom-construct",
    "dojo/dom-style",
    "dijit/layout/BorderContainer",
    "dijit/layout/LayoutContainer",
    "dijit/layout/ContentPane",
    "dojox/layout/ExpandoPane",
    // ------------------------------------------------------------------------
    // These go at the end because we don't need names for them.
    "dojo/NodeList-dom",
    "dojo/NodeList-manipulate"
], function(
    declare,
    query,
    domConstruct,
    domStyle,
    BorderContainer,
    LayoutContainer,
    ContentPane,
    ExpandoPane
){

/* The AppLayout class builds the basic layout components, and maintains
 * references to them.
 */
var AppLayout = declare(null, {

    // Properties
    homeDivId: null,
    homeDiv: null,
    mainLayout: null,
    sidebar: null,
    tctSocket: null,
    librarySocket: null,
    feedbackSocket: null,

    // Methods

    /*
    * param homeDivId: the id of the div element in which the app is to be built
    * param desiredState: info object describing desired state of the ISE.
    */
    constructor: function(homeDivId, desiredState) {
        this.homeDivId = homeDivId;
        this.homeDiv = query("#"+homeDivId)[0];
        // Put focus on the home div so that it can receive keystrokes right away.
        this.homeDiv.setAttribute('tabindex', '-1');
        this.homeDiv.focus();

        // Set body class.
        query('body').addClass('claro');

        // Make a BorderContainer.
        this.mainLayout = new BorderContainer({
            design: "headline"
        }, this.homeDivId);

        var headerInitialContent = '<span id="lhMenu"></span><span id="rhMenu"></span>';

        // Add the BorderContainer edge regions.
        this.mainLayout.addChild(
            new ContentPane({
                region: "top",
                id: 'topBar',
                "class": "edgePanel",
                content: headerInitialContent
            })
        );

        // Prepare settings for the sidebar from the previous state.
        let startExpanded = true;
        let sidebarWidth = 200;
        if (desiredState) {
            if (desiredState.sidebar) {
                startExpanded = desiredState.sidebar.isVisible;
                sidebarWidth = +desiredState.sidebar.width;
            }
        }
        // Set up the sidebar.
        var sidebarId = "leftCol";
        this.sidebar = new ExpandoPane({
            region: "left",
            id: sidebarId,
            "class": "edgePanel",
            title: "Library",
            splitter: true,
            startExpanded: startExpanded
        })
        this.mainLayout.addChild(this.sidebar);
        if (sidebarWidth !== undefined) {
            domStyle.set(sidebarId, 'width', sidebarWidth+'px');
        }

        // Add the library socket.
        this.librarySocket = domConstruct.create("div");
        this.sidebar.set("content", this.librarySocket);

        // Add the socket for the TCT.
        this.tctSocket = new LayoutContainer({
            region: "center",
            gutters: false
        });
        this.mainLayout.addChild(this.tctSocket);

        // Add the feedback socket.
        // For now we just use a raw div. Later, may wish to use some Dijit class.
        this.feedbackSocket = domConstruct.create("div", {"id": "feedback"});
        this.homeDiv.appendChild(this.feedbackSocket);

    },

    startup: function() {
        // start up and do layout
        this.mainLayout.startup();
    }

});

return AppLayout;
});
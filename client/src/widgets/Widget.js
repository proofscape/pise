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

define([
    "dojo/_base/declare",
    "dijit/layout/ContentPane",
    "dijit/Menu",
    "dijit/MenuItem",
    "dijit/PopupMenuItem",
    "dijit/MenuSeparator"
], function(
    declare,
    ContentPane,
    Menu,
    MenuItem,
    PopupMenuItem,
    MenuSeparator
) {

var Widget = declare(null, {

    // Properties

    // reference to the Hub:
    hub: null,
    // the libpath of this widget:
    libpath: null,
    // the version of this widget:
    version: null,
    // widget UID, which equals `libpath_version` with dots replaced by hyphens:
    uid: null,
    // the libpath of the page to which this widget belongs:
    pagepath: null,
    // the ID of the "widget group" (or "pane group") to which this widget belongs, if any:
    groupId: null,
    // the info object as originally passed:
    origInfo: null,
    // a "live" info object: starts as a copy of the one originally passed;
    // may be updated in response to various events:
    liveInfo: null,

    // a widget maintains one context menu per pane in which the widget appears
    contextMenuByPaneId: null,

    listeners: null,

    // Methods

    constructor: function(hub, libpath, info) {
        this.hub = hub;
        this.libpath = libpath;
        this.version = info.version;
        this.uid = info.uid;
        this.pagepath = libpath.slice(0, libpath.lastIndexOf('.'));
        this.modpath = libpath.slice(0, this.pagepath.lastIndexOf('.'));
        this.groupId = info.pane_group;
        this.origInfo = info;
        this.liveInfo = this.getInfoCopy();
        this.contextMenuByPaneId = new Map();
        this.listeners = {};
    },

    getPagepathv: function() {
        return `${this.pagepath}@${this.version}`
    },

    // Get a deep copy of the original info object.
    getInfoCopy: function() {
        return JSON.parse(JSON.stringify(this.origInfo));
    },

    /* Replace this widget's info object with a new one.
     * This is useful when an annotation is being updated from the back-end.
     */
    updateInfo: function(newInfo) {
        // The variable names make this operation sound a bit funny, but the "orig" in
        // `origInfo` is meant to distinguish it from the `liveInfo`, _not_ from the
        // `newInfo` that's now to be set.
        this.origInfo = newInfo;
        this.liveInfo = this.getInfoCopy();
    },

    noteCopy: function(oldPaneId, newPaneId) {
        // Subclasses may wish to override.
    },

    noteClosingPane: function(pane) {
        // Subclasses may wish to override.
    },

    setTheme: function(theme) {
        // Subclasses may wish to override.
    },

    noteNewMathWorker: function() {
        // Subclasses may wish to override.
    },

    /* Activate the widget.
     *
     * This is a place to do anything like setting event handlers on the widget
     * so that it is "activated".
     *
     * Subclasses should override as appropriate.
     *
     * param wdq: the Dojo query object on the widget's DOM element
     * param uid: the unique ID under which the NotesManager has stored the widget
     * param nm: the NotesManager, in case the widget needs to use this
     *           for its particular activity
     * param pane: the pane in which the widget is being opened
     */
    activate: function(wdq, uid, nm, pane) {
    },

    /* Some widgets also need a "pre-activation" step.
     *
     * Arguments are the same as for the `activate` method.
     */
    preactivate: function(wdq, uid, nm, pane) {
    },

    getContextMenu: function(paneId) {
        return this.contextMenuByPaneId.get(paneId);
    },

    destroyContextMenu: function(paneId) {
        if (this.contextMenuByPaneId.has(paneId)) {
            const cm = this.getContextMenu(paneId);
            cm.destroyDescendants();
            cm.destroy();
            this.contextMenuByPaneId.delete(paneId);
        }
    },

    makeContextMenu: function(pane) {
        // In case of refreshing an open page (after rebuild), must clear old context menus
        // first. Else there is an old menu, which still thinks it is attached
        // to a DOM element that no longer exists.
        this.destroyContextMenu(pane.id);

        const paneNode = pane.domNode;
        const socket = paneNode.querySelector('.cpSocket');
        const isSphinx = socket.classList.contains('sphinxSocket');
        const panelType = isSphinx ? "SPHINX": "NOTES";
        const targetNode = isSphinx ? socket.querySelector('iframe') : socket;

        const cm = new Menu({
            targetNodeIds: [targetNode],
            selector: `.${this.uid}`,
        });
        this.contextMenuByPaneId.set(pane.id, cm);

        // For now we do not have any menu items that make sense on widgets in study pages.
        const isStudyPage = this.pagepath.startsWith("special.studypage.");
        if (!isStudyPage) {
            // Tail selector for our libpath.
            const tsHome = document.createElement('div');
            iseUtil.addTailSelector(tsHome, this.libpath.split('.'));
            cm.addChild(new PopupMenuItem({
                label: 'Copy libpath',
                popup: new ContentPane({
                    class: 'popupCP',
                    content: tsHome
                })
            }));

            // Option to edit or view source code
            const widget = this;
            const info = {
                type: "SOURCE",
                origType: panelType,
                libpath: this.pagepath,
                modpath: this.modpath,
                version: this.version,
                useExisting: true,
                sourceRow: widget.origInfo.src_line,
            };
            cm.addChild(new MenuItem({
                label: `${this.version === "WIP" ? "Edit" : "View"} Source`,
                onClick: function (e) {
                    widget.hub.contentManager.openContentInActiveTC(info);
                }
            }));
        }
    }

});

Object.assign(Widget.prototype, iseUtil.eventsMixin);

return Widget;

});
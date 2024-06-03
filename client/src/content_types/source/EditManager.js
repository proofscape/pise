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

const ace = require("ace-builds/src-noconflict/ace.js");
require("src/content_types/source/mode-proofscape.js");
require("ace-builds/src-noconflict/mode-markdown.js");
require("ace-builds/src-noconflict/mode-python.js");
require("ace-builds/src-noconflict/mode-rst");
require("ace-builds/src-noconflict/theme-tomorrow.js");
require("ace-builds/src-noconflict/theme-tomorrow_night_eighties.js");
require("ace-builds/src-noconflict/ext-searchbox.js");

import { SrcViewManager } from "./SrcViewManager";
import { util as iseUtil } from "../../util";

define([
    "dojo/_base/declare",
    "dojo/query",
    "dijit/Menu",
    "dijit/MenuItem",
    "dijit/PopupMenuItem",
    "dijit/MenuSeparator",
    "dijit/ConfirmDialog",
    "ise/content_types/AbstractContentManager",
    "dojo/NodeList-dom",
    "dojo/NodeList-manipulate",
    "dojo/NodeList-traverse",
], function(
    declare,
    query,
    Menu,
    MenuItem,
    PopupMenuItem,
    MenuSeparator,
    ConfirmDialog,
    AbstractContentManager
) {

// EditManager class
var EditManager = declare(AbstractContentManager, {

    // Properties
    hub: null,
    srcViewManager: null,
    // Lookup for all Ace Editor instances, by pane id:
    editors: null,
    // Lookup for Ace Editor instances by modpath.
    // Here, a modpath points to an object in which pane id points to editor instance.
    edsByModpath: null,
    // Count _how many_ editors we have for each modpath.
    numEdsPerModpath: null,
    // Lookup for Ace Document instances, by modpath:
    docsByModpath: null,
    // Change handlers by modpath (one per document):
    changeHandlersByModpath: null,
    // Lookup for initial info, by pane id.
    initialInfos: null,
    // Lookup mapping pane id to the libpath of the _module_ that is opened in that pane:
    modpaths: null,
    // We'll be setting timeouts per module, in order to trigger auto-save:
    autoSaveDelay: 2000,
    autoSaveTimeout: null,
    doAutoSave: null,

    overviewEditorInitialFontSize: 4,

    // Map: modpath |--> { promise: (Promise p), resolve: (resolve function for p) }
    // Represents our intention to write modules to disk.
    pendingWrites: null,
    // Similarly represents our intention to build modules:
    pendingBuilds: null,

    // Methods
    constructor: function(tct) {
        this.srcViewManager = new SrcViewManager(this);
        this.editors = {};
        this.edsByModpath = {};
        this.numEdsPerModpath = {};
        this.docsByModpath = {};
        this.changeHandlersByModpath = {};
        this.initialInfos = {};
        this.modpaths = {};
        this.autoSaveTimeout = {};
        this.doAutoSave = {};
        this.pendingWrites = new Map();
        this.pendingBuilds = new Map();
        tct.registerActivePaneListener(this);
    },

    activate: function() {

        this.hub.socketManager.on('writeComplete', event => {
            this.resolvePendingWrites(event.libpathsWritten);
        });

        this.hub.socketManager.on('buildComplete', event => {
            this.resolvePendingBuilds(event.libpathsBuilt);
        });

        this.hub.windowManager.on('editDelta', event => {
            const { myNumber } = this.hub.windowManager.getNumbers();
            if (event.origin !== myNumber) {
                const doc = this.docsByModpath[event.modpath];
                if (doc) {
                    doc.applyDelta(event.delta);
                }
            }
        });
    },

    resolvePendingWrites: function(libpaths, info=null) {
        for (let lp of libpaths) {
            if (this.pendingWrites.has(lp)) {
                this.pendingWrites.get(lp).resolve(info);
                this.pendingWrites.delete(lp);
            }
        }
    },

    resolvePendingBuilds: function(libpaths, info=null) {
        for (let lp of libpaths) {
            if (this.pendingBuilds.has(lp)) {
                this.pendingBuilds.get(lp).resolve(info);
                this.pendingBuilds.delete(lp);
            }
        }
    },

    noteActivePane: function(cp) {
        if (cp.id in this.editors) {
            var ed = this.editors[cp.id];
            ed.focus();
        }
    },

    getAutoSaveDelay: function() {
        return this.autoSaveDelay;
    },

    setAutoSaveDelay: function(delay) {
        this.autoSaveDelay = delay;
    },

    /* Get the IDs of any existing panes hosting certain content. It is up to
     * the manager to determine exactly when a pane matches the given info.
     *
     * param info: an info object describing some content
     * return: an array of the ids of any existing panes that are deemed to be
     *   currently hosting the content specified by the given info object.
     */
    getExistingPaneIds: function(info) {
        if (info.version === "WIP" || !info.version) {
            const modpath = info.modpath;
            const ids = [];
            for (let id of Object.keys(this.modpaths)) {
                if (this.modpaths[id] === modpath) {
                    ids.push(id);
                }
            }
            return ids;
        } else {
            return this.srcViewManager.getExistingPaneIds(info);
        }
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
        // Keep a local record of the initial info.
        this.initialInfos[pane.id] = info;
        // Load the source code.
        return this.loadSource(info, elt, pane.id);
    },

    /* Update the content of an existing pane of this manager's type.
     *
     * param info: An info object indicating the desired content.
     * param paneId: The ID of the ContentPane that is to be updated.
     */
    updateContent: function(info, paneId) {
        // For now the only kind of update we allow is an autoscroll to a given row.
        var fvr = this.readFirstVisibleRowFromInfo(info);
        if (fvr !== undefined) {
            var editor = this.editors[paneId];
            this.scrollEditorToRow(editor, fvr);
        }
    },

    scrollEditorToRow: function(editor, row) {
        // It seems we can't scroll to the desired row immediately, in the case that
        // we are in the midst of setting the contents of the editor.
        // This may just be a JS event loop "run to completion" issue.
        // We set a short delay before asking to scroll. (Zero delay might also work.)
        setTimeout(() => {
            editor.scrollToLine(row);
            // Note: tried setting a callback as fourth arg to `scrollToLine()`, but
            // nothing happened. So we go with a timeout. 500ms seems to be enough.
            setTimeout(() => {
                this.flashGutterHighlight(editor, row);
            }, 500);
        }, 200);
    },

    flashGutterHighlight: function(editor, row) {
        const row_s = `${row + 1}`;
        const all_cells = editor.container.querySelectorAll('.ace_gutter-cell');
        const cell = Array.from(all_cells).find(d => d.firstChild.textContent === row_s);
        if (cell) {
            const flash = document.createElement('div');
            flash.classList.add('aceGutterFlash');
            // V. important to append -- not prepend -- this child element, or else we
            // cause an error within Ace (where it expects to find sth different as first child).
            cell.appendChild(flash);
            setTimeout(() => {
                flash.style.opacity = 0;
            }, 100);
            setTimeout(() => {
                flash.remove();
            }, 3000);
        }
    },

    /* Extract the specification of the first visible row from an info object.
     * We first check for a `firstVisibleRow` property. If that is defined, it will be returned.
     * If not, then we check for a `sourceRow` property. If that is defined, we will first
     * decrement this number, and then return that value.
     * Otherwise we return undefined.
     */
    readFirstVisibleRowFromInfo: function(info) {
        var fvr = info.firstVisibleRow;
        if (fvr === undefined && info.sourceRow !== undefined) fvr = info.sourceRow - 1;
        return fvr;
    },

    /* Write a serializable info object, completely describing the current state of a
     * given pane of this manager's type. Must be understandable by this manager's
     * own `initContent` method.
     *
     * param oldPaneId: The id of an existing ContentPane of this manager's type.
     * param serialOnly: boolean; set true if you want only serializable info.
     * return: The info object.
     */
    writeStateInfo: function(oldPaneId, serialOnly) {
        const initInfo = this.initialInfos[oldPaneId],
            editor = this.editors[oldPaneId];
        return {
            type            : initInfo.type,
            libpath         : initInfo.libpath,
            version         : initInfo.version,
            firstVisibleRow : editor.getFirstVisibleRow(),
            cursorPos       : editor.getCursorPosition(),
            sidebar         : this.getSidebarProperties(editor),
        };
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
        // Nothing for now.
    },

    /* Take note of the fact that a pane of this manager's type is about to close.
     *
     * param closingPane: The ContentPane that is about to close.
     * return: nothing
     */
    noteClosingContent: function(closingPane) {
        const paneId = closingPane.id;
        const ed = this.editors[paneId];
        if (!ed) {
            // We have no editor for this pane. It must have been opened
            // despite inability to load content.
            return;
        }
        const oed = ed.pfscIseOverviewEditor;
        if (this.isWorkingEditor(paneId)) {
            const modpath = this.modpaths[closingPane.id];
            // Save the module.
            // (Could do this just in the case below, where this is the _last_ editor
            //  for this module, but -- better safe than sorry.)
            this.saveByModpath(modpath);
            iseUtil.detachListeners(ed, ace);
            iseUtil.detachListeners(oed, ace);
            delete this.modpaths[paneId];
            delete this.edsByModpath[modpath][paneId];
            this.numEdsPerModpath[modpath] -= 1;
            // Was that the last editor for this modpath?
            if (this.numEdsPerModpath[modpath] === 0) {
                window.clearTimeout(this.autoSaveTimeout[modpath]);
                delete this.autoSaveTimeout[modpath];
                delete this.changeHandlersByModpath[modpath];
                delete this.edsByModpath[modpath];
                delete this.numEdsPerModpath[modpath];
                delete this.docsByModpath[modpath];
                delete this.doAutoSave[modpath];
            }
        } else {
            this.srcViewManager.noteClosingPane(paneId);
        }
        delete this.editors[paneId];
        delete this.initialInfos[paneId];
        ed.destroy();
        oed.destroy();
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
        return Promise.resolve([false, false]);
    },

    resizeAll: function() {
        //console.log('editManager resizeAll');
        var force = false;
        for (var k in this.editors) {
            var editor = this.editors[k];
            // See https://ace.c9.io/#nav=api&api=editor
            editor.resize(force);
        }
    },

    /* Control visibility of the overview sidebar for a given editor pane.
     #
     * param paneId: the pane id of the editor pane in question.
     * param doShow: boolean: true to show sidebar, false to hide it.
     */
    showOverviewSidebar: function(paneId, doShow) {
        const editor = this.editors[paneId];
        if (editor) {
            const parent = editor.container.parentElement;
            if (doShow) {
                parent.classList.add('showSidebar');
                editor.pfscIseOverviewEditor.resize(false);
                setTimeout(() => {
                    this.updateOverviewGlass(paneId, true);
                }, 500);
            } else {
                parent.classList.remove('showSidebar');
                editor.resize(false);
            }
        }
    },

    toggleOverviewSidebar: function(paneId) {
        const editor = this.editors[paneId];
        if (editor) {
            this.showOverviewSidebar(paneId, !this.sidebarIsVisible(editor));
        }
    },

    sidebarIsVisible: function(editor) {
        const parent = editor.container.parentElement;
        return parent.classList.contains('showSidebar');
    },

    getSidebarProperties: function(editor) {
        const oed = editor.pfscIseOverviewEditor;
        return {
            visible: this.sidebarIsVisible(editor),
            fontSize: oed.getFontSize(),
        };
    },

    updateOverviewGlass: function(paneId, center) {
        const editor = this.editors[paneId];
        if (editor) {
            const oed = editor.pfscIseOverviewEditor;
            const R0 = editor.getFirstVisibleRow();
            const R1 = editor.getLastVisibleRow();
            const r0 = oed.getFirstVisibleRow();
            const r1 = oed.getLastVisibleRow();
            if (center) {
                oed.scrollToRow((R0+R1)/2 - (r1-r0)/2);
            } else if (R0 < r0) {
                oed.scrollToRow(R0);
            } else if (R1 > r1) {
                oed.scrollToRow(r0 + R1 - r1);
            }
            const range = {start: {row: R0, column: 0}, end: {row: R1, column: 0}};
            oed.selection.setRange(range);
        }
    },

    onOverviewMousedown: function(mdEvent, editor, overviewEditor) {
        const px = mdEvent.pageX,
            py = mdEvent.pageY,
            row0 = overviewEditor.renderer.screenToTextCoordinates(px, py).row,
            R0 = editor.getFirstVisibleRow(),
            R1 = editor.getLastVisibleRow();
        if (R0 <= row0 && row0 <= R1) {
            const moveHandler = mmEvent => {
                const qx = mmEvent.pageX,
                    qy = mmEvent.pageY,
                    row1 = overviewEditor.renderer.screenToTextCoordinates(qx, qy).row,
                    dr = row1 - row0,
                    new_row = R0 + dr,
                    current_row = editor.getFirstVisibleRow();
                if (new_row !== current_row) {
                    editor.scrollToRow(new_row);
                }
                mmEvent.stopPropagation();
            };
            const upHandler = muEvent => {
                document.documentElement.removeEventListener('mousemove', moveHandler);
                document.documentElement.removeEventListener('mouseup', upHandler);
                muEvent.stopPropagation();
            };
            document.documentElement.addEventListener('mousemove', moveHandler);
            document.documentElement.addEventListener('mouseup', upHandler);
            mdEvent.stopPropagation();
        }
    },

    /*
    * Set the theme in all the editors.
    * param theme: `light` or `dark`
    */
    setTheme: function(theme) {
        var atp = iseUtil.getAceThemePath(theme);
        for (var k in this.editors) {
            var editor = this.editors[k];
            editor.setTheme(atp);
            editor.pfscIseOverviewEditor.setTheme(atp);
        }
    },

    /*
    * Set the font size in all the editors.
    * param size: size in pixels
    */
    setFontSize: function(size) {
        for (var k in this.editors) {
            var editor = this.editors[k];
            editor.setFontSize(size);
        }
    },

    saveCursorPoses: function(eds) {
        if (typeof(eds) === 'undefined') {
            eds = this.editors;
        }
        const poses = {};
        for (let k in eds) {
            let editor = eds[k];
            poses[k] = editor.getCursorPosition();
        }
        return poses;
    },

    restoreCursorPoses: function(eds, poses) {
        if (typeof(eds) === 'undefined') {
            eds = this.editors;
        }
        for (let k in eds) {
            let editor = eds[k],
                cp = poses[k];
            if (cp) {
                editor.moveCursorTo(cp.row, cp.column);
                editor.clearSelection();
            }
        }
    },

    /* Say whether the editor in a given pane is a "working editor," i.e.
     * one in which we are editing work-in-progress. The alternative is that
     * it is a read-only editor purely for viewing the source code of a
     * built, numbered release.
     */
    isWorkingEditor: function(paneId) {
        return !this.srcViewManager.hasPane(paneId);
    },

    /* Respond to a change in the logged-in user.
     */
    updateForUser: function() {
        // All editor panels will be frozen, unconditionally:
        this.freezeAllEditors(true);
        // Only those editors will thaw that are owned by the currently
        // logged-in user:
        this.freezeAllEditors(false);
        // This leaves us in just the state we want: you're able to make
        // changes only in those panels where you own the content.
    },

    /* Freeze (i.e. make read-only) or unfreeze all "working editors," i.e.
     * editors where a module is open @WIP.
     *
     * In fact, for each editor panel, we freeze unconditionally, but unfreeze
     * only if the user appears to have access to the module that's open in that panel.
     * This helps keep editors frozen if the owner logs out.
     *
     * param b: boolean. true means freeze; false means "unfreeze" or "thaw"
     */
    freezeAllEditors: function(/* boolean */ b) {
        //console.log(b ? " --- FREEZE --- " : " --- THAW --- ");
        for (let paneId of Object.keys(this.editors)) {
            if (this.isWorkingEditor(paneId)) {
                const modpath = this.modpaths[paneId];
                // If you want to freeze, we go ahead.
                // If you want to thaw, the user has to have access on the modpath.
                if (b || this.hub.userHasAccess(modpath)) {
                    this.makeEditorReadOnly(paneId, b, true);
                }
            }
        }
    },

    /* Make an existing editor readonly or not.
     *
     * Besides telling the Ace Editor whether to allow edits, we make visual
     * markings to indicate to the user whether the editor is readonly or not.
     *
     * paneId: the id of the pane where the editor is found
     * readonly: true to make readonly, false to make not readonly
     * frozen: set true if freezing a formerly read-write editor. Controls whether the
     *   visual markings appear instantly or not. For freezing, we want a delay, so
     *   that in an immediate freeze-thaw cycle (as when the ISE regains focus), the
     *   user sees no change.
     */
    makeEditorReadOnly: function(paneId, readonly, frozen) {
        const editor = this.editors[paneId];
        const pane = this.hub.contentManager.getPane(paneId);
        const node = pane.domNode;
        const gutter = node.querySelector('.ace_gutter');

        editor.setReadOnly(readonly);

        if (readonly) {
            if (frozen) {
                node.classList.add('frozenEditor');
            }
            node.classList.add('readonlyEditor');
            gutter.setAttribute('title', 'Read-Only');
        } else {
            node.classList.remove('frozenEditor');
            node.classList.remove('readonlyEditor');
            gutter.removeAttribute('title');
        }
    },

    /* Carefully overwrite the current contents of an open module.
     *
     * If text is actually unchanged, do nothing.
     * If text actually is changed:
     *   First request a shadow commit of the current text. Then:
     *   Save current cursor position in each of the affected editors.
     *   Pause auto save.
     *   Update the contents of the document.
     *   Restore cursor positions in each of the affected editors.
     *
     * @return: promise that resolves when the operation is complete.
     */
    carefullyOverwriteOpenModule: function(modpath, newText) {
        const doc = this.docsByModpath[modpath];
        const currentText = doc.getValue();
        if (newText === currentText) {
            return Promise.resolve();
        } else {
            return this.shadowCommitModtext(modpath, currentText).then(() => {
                this.setDocValueWithCursorRestore(modpath, newText);
            });
        }
    },

    setDocValueWithCursorRestore: function(modpath, newText) {
        const doc = this.docsByModpath[modpath];
        const edsForModule = this.edsByModpath[modpath];
        const poses = this.saveCursorPoses(edsForModule);
        this.pauseAutoSave(modpath);
        doc.setValue(newText);
        this.restoreCursorPoses(edsForModule, poses);
    },

    /* Callers can use this method to ask this EditManager whether, from
     * its point of view, it is okay to write certain modules. In fact they are asking
     * whether this EditManager has any pending write and/or build requests on those modules.
     *
     * @param writepaths {Array[string]} the libpaths of the modules one wants to write.
     * @return: promise that resolves when this EditManager says it's okay to write
     *   all of those modules.
     */
    checkWriteOkay: function(writepaths) {
        const pending = [];
        for (let writepath of writepaths) {
            if (this.pendingWrites.has(writepath)) {
                pending.push(this.pendingWrites.get(writepath).promise);
            }
            if (this.pendingBuilds.has(writepath)) {
                pending.push(this.pendingBuilds.get(writepath).promise);
            }
        }
        return Promise.all(pending);
    },

    /* Callers can use this method to ask this EditManager whether, from
     * its point of view, it is okay to read certain modules. In fact they are asking
     * whether this EditManager has any pending writes on those modules.
     *
     * @param readpaths {Array[string]} the libpaths of the modules one wants to read.
     * @return: promise that resolves when this EditManager says it's okay to read
     *   all of those modules.
     */
    checkReadOkay: function(readpaths) {
        const pending = [];
        for (let readpath of readpaths) {
            if (this.pendingWrites.has(readpath)) {
                pending.push(this.pendingWrites.get(readpath).promise);
            }
        }
        return Promise.all(pending);
    },

    /* Reload all documents from disk.
     *
     * Actually we only request to reload those docs that appear to be accessible by
     * the current user.
     *
     * param reloadMethod: string, indicating the desired method
     *      'none': do not overwrite any open modules with current disk contents
     *      'auto': overwrite all open modules with current disk contents
     *      'compare': interactive approach. Let the user compare their version with
     *        the version on disk, as well as a combined version, and choose the way
     *        they want to procede.
     */
    reloadAllDocs: function(reloadMethod) {
        const unfilteredReadpaths = Object.keys(this.docsByModpath);
        //console.log('unfilteredReadpaths:', unfilteredReadpaths);
        const readpaths = unfilteredReadpaths.filter(path => this.hub.userHasAccess(path));
        //console.log('filtered readpaths:', readpaths);
        const N = readpaths.length;
        // If no docs are open, don't do anything.
        if (N === 0) return;
        //console.log('Preparing to reload docs: ', readpaths);
        // Freeze all editors.
        this.freezeAllEditors(true);
        const theEditManager = this;
        // Cannot procede until all windows say it is okay to read these modules.
        const readyPromises = this.hub.windowManager.broadcastRequest('hub.editManager.checkReadOkay', readpaths);
        Promise.all(readyPromises).then(() => {
            // Load the source code for every open document.
            return this.hub.xhrFor('loadSource', {
                query: { libpaths: readpaths.join(','), versions: Array(N).fill("WIP").join(',') },
                handleAs: 'json',
            }).then(resp => {
                if (this.hub.errAlert3(resp)) return;
                const source = resp.source;
                const shadowCommitPromises = [];
                for (let modpath of Object.keys(theEditManager.docsByModpath)) {
                    if (source.hasOwnProperty(modpath)) {
                        const doc = theEditManager.docsByModpath[modpath],
                            currentText = doc.getValue(),
                            newText = source[modpath];
                        // There's nothing to do unless the version from disk is actually different.
                        // Besides just saving time and effort, we want to avoid reloading text in the
                        // editor if at all possible, since this makes the editor recompute all the
                        // syntax highlighting, which makes an annoying visual "blink".
                        if (newText !== currentText) {
                            // Decide what to do based on reload method.
                            if (reloadMethod === 'auto') {
                                // Under 'auto' policy, we automatically accept the new text.
                                // But we do a shadow commit of the current text first (it is
                                // done by the method we call here).
                                shadowCommitPromises.push(theEditManager.carefullyOverwriteOpenModule(modpath, newText));
                            } else if (reloadMethod === 'compare') {
                                // FIXME: Maybe make this more efficient by bundling all the modules togehter
                                //  into a single request? Maybe our current texts should even be added as optional
                                //  extra data sent with the XHR to `loadSource` (so it'd have to be a POST instead of GET)
                                //  and the fulltexts come back along with diffs?
                                const args = {
                                    modpaths: [modpath], modtexts: [currentText]
                                };
                                // Start with a shadow commit of the current text, just for safety.
                                const p = theEditManager.shadowCommitModtext(modpath, currentText).then(() => {
                                    theEditManager.hub.socketManager.xhrFor('modDiff', {
                                        method: "POST",
                                        form: {
                                            info: JSON.stringify(args)
                                        },
                                        handleAs: "json",
                                    }).then(resp => {
                                        if (theEditManager.hub.errAlert3(resp)) return;
                                        const mergetext = resp.mergetexts[modpath];
                                        const pane = theEditManager.hub.contentManager.findMostRecentlyActivePaneHostingContent({
                                            type: "SOURCE", modpath: modpath, version: "WIP"
                                        });
                                        return theEditManager.reconcile(modpath, mergetext, newText, pane);
                                    }).catch(reason => {
                                        this.hub.errAlert(`Could not obtain mergetext for module ${modpath}.\n${reason}`);
                                    });
                                });
                                shadowCommitPromises.push(p);
                            } else {
                                // Under any other policy, we reject the new text, keeping the
                                // current contents of the editor(s) unchanged; however, we do
                                // a shadow commit of the new text, so that it is not lost entirely.
                                shadowCommitPromises.push(theEditManager.shadowCommitModtext(modpath, newText));
                            }
                        }
                    } else {
                        this.hub.errAlert(`Failed to reload source for module ${modpath}`);
                    }
                }
                return Promise.all(shadowCommitPromises);
            }).catch(console.error);
        }).finally(() => {
            theEditManager.freezeAllEditors(false);
        });
    },

    /* Copy the selection code from the most recently active Pdf pane that has a
     * selection, and paste it into the editor pane of a given id.
     *
     * param paneId: id of editor pane where code should be pasted.
     */
    pastePdfRef: function(paneId) {
        var pdfc = this.hub.pdfManager.getMostRecentPdfcWithSelection();
        if (pdfc !== null) {
            var code = pdfc.readCombinerCodeFromSelectionBoxes();
            var ed = this.editors[paneId];
            ed.insert(code);
        }
    },

    /* General purpose build function.
     *
     * Clients pass an args object that may contain any of the following
     * optional fields:
     *
     *   buildpaths: list of libpaths of modules to be built
     *   makecleans: list of booleans saying whether corresp. builds should be made clean
     *      first, i.e. whether all pickle files should be erased first.
     *   autowrites: list of autowrite dictionaries. See doctext for `WriteHandler`
     *               class at the back-end in `handlers/write.py`.
     *
     * The following steps are taken:
     * 1. Freeze all editors (set into read-only mode)
     * 2. Augment the given args object with writepaths and writetexts for all
     *    modules currently open in editor panes. This means all open modules
     *    will be written to disk before any building takes place.
     * 3. Emit request to back-end, finally unfreezing editors after completion.
     *
     * @return: promise that resolves when the operation is complete.
     */
    build: function(args) {
        // Freeze all editors.
        this.freezeAllEditors(true);
        // Augment given args with write info.
        var writeinfo = this.prepareAllForWrite();
        args.writepaths = writeinfo.paths;
        args.writetexts = writeinfo.texts;
        // Emit request.
        var theEditManager = this;
        return this.writeAndBuild(args)
            .catch(console.log)
            .finally(() => {
                theEditManager.freezeAllEditors(false);
            });
    },

    /* Emit a "write_and_build" socket event.
     *
     * This method also manages the promises we use to safely chain reads and writes:
     *   - It does not do anything until all windows say it is okay to write and
     *     build the modules in question.
     *   - It sets up the "read resolve" function, to be called when we receive a
     *     'writeComplete' event listing all the writepaths we requested.
     *   - It emits the 'write_and_build' request, which returns a promise that should
     *     resolve when both write and build are completed by the server. This promise
     *     is both (a) set as the new "write okay" promise, and (b) returned from this
     *     method call.
     *
     * @param args: the message for the server's WriteHandler.
     *   NOTE: The writepaths and buildpaths (and corresponding args, writetexts and makecleans,
     *   resp.) will be filtered first. We will reject any paths that do not appear to belong
     *   to the current user.
     * @return: promise that resolves with the initial http response. This does not contain
     *   the results of writing and building, but only a job_id for that async task.
     */
    writeAndBuild: function(args) {
        /* FIXME: We could refine the startup checks a bit.
         *  We must not write a module if any window is waiting for it to write OR build.
         *  And if we want to write AND build it, of course we must not build until after we write.
         *  But consider the case of a module that we want to build without first writing.
         *  If any window is waiting to write that one, we must wait;
         *  but if any window is waiting to build that one, then we should _cancel_ our build request on that one.
         */
        //console.log('writeAndBuild initial args:', args);
        args = this.filterWriteAndBuildArgsByUserAccess(args);
        //console.log('writeAndBuild filtered args:', args);
        const writepaths = args.writepaths || [];
        this.clearAutoSaves(writepaths);
        const buildpaths = args.buildpaths || [];
        const allpaths = writepaths.concat(buildpaths);
        //console.log('Preparing to emitWriteAndBuild for:', allpaths);
        const readyPromises = this.hub.windowManager.broadcastRequest(
            'hub.editManager.checkWriteOkay', allpaths, { excludeSelf: true }
        );
        return Promise.all(readyPromises).then(() => {
            for (let wp of (args.writepaths || [])) {
                this.recordIntentionToWrite(wp);
            }
            for (let bp of (args.buildpaths || [])) {
                this.recordIntentionToBuild(bp);
            }
            //console.log(args);
            return this.hub.socketManager.splitXhrFor('writeAndBuild', {
                method: "POST",
                form: {
                    info: JSON.stringify(args)
                },
                handleAs: "json",
            }).then(resp => {
                if (this.hub.errAlert3(resp.immediate)) {
                    // FIXME: What is the right behavior here?
                    // Should we...
                    //   this.resolvePendingWrites(writepaths, resp);
                    //   this.resolvePendingBuilds(buildpaths, resp);
                    // ?
                    // It is a balance between deadlock on the one hand, and on the other
                    // hand the sorts of errors we wanted to avoid with our `checkWriteOkay`
                    // and `checkReadOkay` methods.
                    // Maybe if server returns more informative err report we can either try
                    // again, or accept permanent failure, on particular write/build paths.
                }
                if (resp.delayed) {
                    resp.delayed.then(this.hub.errAlert3.bind(this.hub));
                }
                return resp.immediate;
            });
        });
    },

    /* Utility method: Pass two arrays A, B. They must be the same
     * length, and A must be an array of libpaths.
     * We return the pair of arrays obtained by keeping only those
     * libpaths accessible by the current user, and keeping only the corresponding
     * entries of the second array.
     */
    filterMatchedArraysByUserAccess: function(A, B) {
        const A2 = [], B2 = [];
        for (let i = 0; i < A.length; i++) {
            const path = A[i];
            if (this.hub.userHasAccess(path)) {
                A2.push(path);
                B2.push(B[i]);
            }
        }
        return [A2, B2];
    },

    filterWriteAndBuildArgsByUserAccess: function(args) {
        const [writepaths, writetexts] = this.filterMatchedArraysByUserAccess(
            args.writepaths || [],
            args.writetexts || []
        );

        const [buildpaths, makecleans] = this.filterMatchedArraysByUserAccess(
            args.buildpaths || [],
            args.makecleans || []
        );

        // TODO:
        //  We should filter the autowrites as well. We would have to introduce a
        //  requirement in the format of all autowrite dicts, that they have a `writepaths`
        //  field indicating all libpaths to which they will attempt to write.
        //  For now we can skip it, because autowrites are not currently used.
        return {
            writepaths: writepaths,
            writetexts: writetexts,
            shadowonly: args.shadowonly,
            buildpaths: buildpaths,
            makecleans: makecleans,
            autowrites: args.autowrites,
        };
    },

    clearAutoSaves: function(modpaths) {
        for (let modpath of modpaths) {
            window.clearTimeout(this.autoSaveTimeout[modpath]);
        }
    },

    /* Build the module in an editor pane.
     *
     * @param paneId: the id of the pane whose module is to be built.
     * @return: promise that resolves when the operation is complete.
     */
    buildByPaneId: function(paneId) {
        var buildpath = this.modpaths[paneId];
        return this.build({
            buildpaths: [buildpath],
            makecleans: [false]
        });
    },

    /* Save the module in an editor pane.
     *
     * @param paneId: the id of the pane whose module is to be saved.
     * @return: promise that resolves when the operation is complete.
     */
    saveByPaneId: function(paneId) {
        var modpath = this.modpaths[paneId];
        return this.saveByModpath(modpath);
    },

    /* Save the module of a given libpath (must currently be open in at least one editor).
     *
     * @return: promise that resolves when the operation is complete.
     */
    saveByModpath: function(modpath) {
        var doc = this.docsByModpath[modpath],
            text = doc.getValue(),
            args = {
                writepaths: [modpath],
                writetexts: [text]
            };
        return this.writeAndBuild(args)
    },

    /* Save all currently open (and changed) modules.
     *
     * @param options {
     *   changedOnly {bool} default true. If true, we save only the currently
     *     open modules for which we have noted any changes. Set false to force
     *     save of all open modules even if no changes have been noted.
     * }
     *
     * @return: promise that resolves when the operation is complete.
     */
    saveAll: function(options) {
        const {
            changedOnly = true
        } = options || {};
        const args = {},
            writeinfo = this.prepareAllForWrite({ changedOnly: changedOnly });
        if (writeinfo.paths.length === 0) return;
        args.writepaths = writeinfo.paths;
        args.writetexts = writeinfo.texts;
        //console.log('save all:', args.writepaths);
        return this.writeAndBuild(args)
    },

    /* Do a shadow commit of given text for a given module.
     *
     * @return: promise that resolves when the operation is complete.
     */
    shadowCommitModtext: function(modpath, modtext) {
        //console.log(`Shadow commit ${modpath}`, modtext);
        const args = {
            writepaths: [modpath],
            writetexts: [modtext],
            shadowonly: true
        };
        return this.writeAndBuild(args)
    },

    /* Build lists of the paths of all open (and changed) modules, and their
     * current texts.
     *
     * @param options {
     *   changedOnly {bool} default true. If true, we report on only the currently
     *     open modules for which we have noted any changes. Set false to force
     *     reporting on all open modules even if no changes have been noted.
     * }
     *
     * @return: {
     *   paths: Array[string] the modpaths of the modules to be written
     *   texts: Array[string] the full texts of the modules to be written
     * }
     */
    prepareAllForWrite: function(options) {
        const {
            changedOnly = true
        } = options || {};
        const texts = [];
        const paths = [];
        let modpaths = changedOnly ? this.pendingWrites.keys() : Object.keys(this.docsByModpath);
        for (let modpath of modpaths) {
            const doc = this.docsByModpath[modpath];
            if (doc) {
                const text = doc.getValue();
                paths.push(modpath);
                texts.push(text);
            }
        }
        return {
            paths: paths,
            texts: texts,
        };
    },

    /* Load a module's source code into a new editor.
     *
     * At the risk of doing a little extraneous work, this method does two jobs at once.
     * The back-end function `loadSource` which we call does two things for us: (1) it resolves
     * the libpath we provide to a modpath, and (2) it supplies the full text, from disk, of
     * that module.
     *
     * If it then turns out that this module is already open in one or more editors, then
     * the full text from disk is extraneous, because we're simply going to make a new Editor
     * instance operating on the same Document instance that we already have for that module.
     *
     * The alternative would be a design in which we made an initial back-end call to resolve
     * the libpath to a modpath, and then made a second call for the full text iff it was
     * needed.
     *
     * param info: the info object defining the item to be opened.
     * param elt: the DOM element where the editor is to be placed.
     * param paneId: the id of the ContentPane where this content is being opened.
     *
     * return: promise that resolves when the content is loaded.
     */
    loadSource: function(info, elt, paneId) {
        const libpath = info.libpath;
        const version = info.version;
        const cpos = info.cursorPos;
        const fvr = this.readFirstVisibleRowFromInfo(info);
        return this.hub.xhrFor('loadSource', {
            query: { libpaths: libpath, versions: version },
            handleAs: 'json',
        }).then(resp => {
            if (this.hub.errAlert3(resp)) return;
            const text = resp.text;
            const modpath = resp.modpath;
            const readonly = version !== "WIP";
            const sbProps = info.sidebar || {};
            const editor = this.makeEditor(elt, paneId, readonly, sbProps);
            if (readonly) {
                this.srcViewManager.addCommandsAndContextMenu(editor, paneId);
                this.srcViewManager.setContent(editor, modpath, version, paneId, text, fvr, cpos);
            } else {
                this.addCommandsAndContextMenu(editor, paneId);
                this.modpaths[paneId] = modpath;
                this.setContent(modpath, paneId, text, fvr, cpos);
            }
            this.configureSession(editor, info.is_rst);
            this.configureSession(editor.pfscIseOverviewEditor, info.is_rst);
            if (sbProps.visible) {
                this.showOverviewSidebar(paneId, true);
            }
        });
    },

    configureSession: function(editor, is_rst) {
        const sesh = editor.getSession();

        const mode = is_rst ? 'rst' : 'proofscape';
        sesh.setMode("ace/mode/" + mode);

        sesh.setTabSize(4);
        sesh.setUseSoftTabs(true);
    },

    makeAuxPanel: function(div) {
        const html = `
        <div class="edAuxPanel">
            <div class="auxPanelTitle">Your version and the version on disk differ.</div>
            <div class="auxPanelBody">
                <span>Viewing:
                    <label class="auxPanelDocOpt"><input type="radio" name="vers" value="yours" checked>Yours</label>
                    <label class="auxPanelDocOpt"><input type="radio" name="vers" value="disk">Disk</label>
                    <label class="auxPanelDocOpt"><input type="radio" name="vers" value="combined">Combined</label>
                </span>
                <span class="auxPanelButton">Continue with this version</span>
            </div>
        </div>
        `;
        div.innerHTML = html;
    },

    /* Make a new Ace editor instance.
     *
     * param elt: the DOM element where the editor is to be placed.
     * param paneId: the id of the ContentPane where this content is being opened.
     * param readonly: boolean saying whether this editor is to be readonly for
     *   its entire lifetime, i.e. is to be used merely for viewing source code.
     * param sbProps: object defining desired properties for the sidebar.
     *
     * return: the editor
     */
    makeEditor: function(elt, paneId, readonly, sbProps) {
        const auxDiv = document.createElement('div');
        const mainDiv = document.createElement('div');
        const workDiv = document.createElement('div');
        const overviewDiv = document.createElement('div');
        auxDiv.classList.add('edHeader');
        mainDiv.classList.add('edBody');
        workDiv.classList.add('mainview');
        overviewDiv.classList.add('overviewSidebar');
        elt.appendChild(auxDiv);
        elt.appendChild(mainDiv);
        mainDiv.appendChild(workDiv);
        mainDiv.appendChild(overviewDiv);
        const editor = ace.edit(workDiv);
        const overviewEditor = ace.edit(overviewDiv, {showGutter: false});
        // Save a reference to it under the pane id.
        this.editors[paneId] = editor;
        // Set theme.
        const atp = iseUtil.getAceThemePath(this.hub.currentTheme);
        editor.setTheme(atp);
        this.makeEditorReadOnly(paneId, readonly, false);
        editor.setOption('scrollPastEnd', 0.5);
        // Set initial font size according to global setting.
        editor.setFontSize(this.hub.getCurrentEditorFontSize());

        overviewEditor.setTheme(atp);
        overviewEditor.setReadOnly(true);
        overviewEditor.setFontSize(sbProps.fontSize || this.overviewEditorInitialFontSize);
        overviewEditor.$blockScrolling = Infinity;
        editor.pfscIseOverviewEditor = overviewEditor;

        overviewDiv.addEventListener('mousedown', mdEvent => {
            this.onOverviewMousedown(mdEvent, editor, overviewEditor);
        });
        this.addOverviewContextMenu(overviewEditor, paneId);

        iseUtil.applyAceEditorFixes(editor);
        iseUtil.reclaimAceShortcutsForPise(editor);
        return editor;
    },

    addOverviewContextMenu: function(overviewEditor, paneId) {
        const overviewDiv = overviewEditor.container;
        const menu = new Menu({
            targetNodeIds: [overviewDiv]
        });
        const mgr = this;

        const fontSizeSubMenu = new Menu();
        for (let p = 3; p < 7; p++) {
            fontSizeSubMenu.addChild(new MenuItem({
                label: `${p}`,
                onClick: function() {
                    overviewEditor.setFontSize(p);
                    const siblings = this.getParent().getChildren();
                    for (let sib of siblings) {
                        sib.set('disabled', sib === this);
                    }
                },
                disabled: p === overviewEditor.getFontSize(),
            }));
        }
        menu.addChild(new PopupMenuItem({
            label: 'Font Size',
            popup: fontSizeSubMenu,
        }));

        menu.addChild(new MenuItem({
            label: 'Close',
            onClick: function () {
                mgr.showOverviewSidebar(paneId, false);
            }
        }));
    },

    addCommandsAndContextMenu: function(editor, paneId) {
        // Add special commands
        const theEditManager = this;
        editor.commands.addCommand({
            name: "Build",
            bindKey: {mac: "Ctrl-B"},
            exec: function (editor) {
                theEditManager.buildByPaneId(paneId);
            }
        });
        editor.commands.addCommand({
            name: "Save",
            bindKey: {mac: "Ctrl-S"},
            exec: function (editor) {
                theEditManager.saveByPaneId(paneId);
            }
        });
        editor.commands.addCommand({
            name: "Paste PDF Ref",
            bindKey: {mac: "Ctrl-Alt-P"},
            exec: function (editor) {
                theEditManager.pastePdfRef(paneId);
            }
        });
        // Attach a context menu.
        const menu = new Menu({
            targetNodeIds: [editor.container]
        });
        menu.addChild(new MenuItem({
            label: '<span class="lrMenuItem"><span>Save</span><span class="menuHint">Ctrl-S</span></span>',
            onClick: function (evt) {
                theEditManager.saveByPaneId(paneId);
            }
        }));
        menu.addChild(new MenuItem({
            label: '<span class="lrMenuItem"><span>Build</span><span class="menuHint">Ctrl-B</span></span>',
            onClick: function (evt) {
                theEditManager.buildByPaneId(paneId);
            }
        }));
        menu.addChild(new MenuSeparator());
        menu.addChild(new MenuItem({
            label: 'Toggle Overview',
            onClick: function (evt) {
                theEditManager.toggleOverviewSidebar(paneId);
            }
        }));

        // jog: to hit, like the Fonz, in order to regain functionality
        const provideJogOption = false;
        if (provideJogOption) {
            menu.addChild(new MenuSeparator());
            menu.addChild(new MenuItem({
                label: 'Jog',
                onClick: function (evt) {
                    theEditManager.resizeAll();
                    theEditManager.freezeAllEditors(false);
                }
            }));
        }
    },

    /* Deactivate the auto-save mechanism for a module a number of miliseconds.
     * Useful during programmatic change of editor contents.
     *
     * param modpath: the libpath of the module whose auto-save is to be paused
     * param delay: the time in miliseconds for which auto-save should be shut off.
     *              Defaults to 2000 (2 seconds) if not supplied.
     */
    pauseAutoSave: function(modpath, delay) {
        delay = delay || 2000;
        this.doAutoSave[modpath] = false;
        //console.log('auto-save paused');
        var theEditManager = this;
        window.setTimeout(function(){
            theEditManager.doAutoSave[modpath] = true;
            //console.log('auto-save resumed');
        }, delay);
    },

    /* Set the contents of an editor pane.
     *
     * param modpath: the libpath of the module that is open in this editor
     * param paneId: the id of the pane whose contents are to be set
     * param text: the text that is to be set as the contents of the pane
     * param fvr: "first visible row": (optional) an integer, indicating which row should be the first
     *      visible one at the top of the editor window
     * param cp: "cursor position": (optional) an object with `row` and `column` properties indicating
     *      where the cursor should be placed
     */
    setContent: function(modpath, paneId, text, fvr, cp) {
        var editor = this.editors[paneId];
        this.pauseAutoSave(modpath);
        // Is this the first editor for this module, or is it already open?
        var alreadyOpen = this.docsByModpath.hasOwnProperty(modpath);
        if (alreadyOpen) {
            // We already have one or more editors open for this module.
            // Grab the existing document, build a new editor session on it,
            // and set this in the new editor.
            // This way multiple editors are operating on one and the same document.
            const doc = this.docsByModpath[modpath];
            const sesh = ace.createEditSession(doc);
            editor.setSession(sesh);
            // Note the editor under the modpath.
            this.edsByModpath[modpath][paneId] = editor;
            this.numEdsPerModpath[modpath] += 1;
        } else {
            // This is the first editor for this module.
            editor.setValue(text);
            editor.clearSelection();
            // Save the document under the modpath.
            const doc = editor.getSession().getDocument();
            this.docsByModpath[modpath] = doc;
            // Note the editor under the modpath as well.
            this.edsByModpath[modpath] = {
                [paneId]: editor
            };
            this.numEdsPerModpath[modpath] = 1;
            // Set up auto-save.
            this.doAutoSave[modpath] = true;
            // Set a change handler.
            this.changeHandlersByModpath[modpath] = doc.on('change', delta => {
                this.docChangeHandler(modpath, delta);
            });
        }
        const doc = this.docsByModpath[modpath];
        const sesh = ace.createEditSession(doc);
        const oed = editor.pfscIseOverviewEditor;
        oed.setSession(sesh);

        editor.session.on("changeScrollTop", (scrollTop, session) => {
            this.updateOverviewGlass(paneId);
        });

        // Set scroll.
        if (fvr !== undefined) {
            this.scrollEditorToRow(editor, fvr);
        }
        // Set cursor position.
        if (cp !== undefined) {
            //console.log(cp);
            editor.moveCursorTo(cp.row, cp.column);
        } else if (!alreadyOpen) {
            // Cursor will be at the end of the text unless we move it.
            editor.moveCursorTo(0, 0);
        }
        // Do we need a delay before focusing the editor?
        //setTimeout(editor.focus(), 1000);
        editor.focus()
    },

    recordIntentionToWrite: function(modpath) {
        if (!this.pendingWrites.has(modpath)) {
            const p = new Promise(resolve => {
                this.pendingWrites.set(modpath, {resolve: resolve});
            });
            this.pendingWrites.get(modpath).promise = p;
        }
    },

    recordIntentionToBuild: function(modpath) {
        if (!this.pendingBuilds.has(modpath)) {
            const p = new Promise(resolve => {
                this.pendingBuilds.set(modpath, {resolve: resolve});
            });
            this.pendingBuilds.get(modpath).promise = p;
        }
    },

    docChangeHandler: function(modpath, delta) {
        /* If this window does not currently have focus, then an open document should be changing
         * only because we are responding to edit deltas groupcast from another window. In that case,
         * it is entirely up to that other window to take care of recording those changes, or doing
         * anything else that ordinarily should happen in response to a change in an open document
         * in the focused window.
         *
         * In particular, it is critical that we _not_ record an intention to write the changed module.
         * If we do, then the focused window will never be able to record the changes
         * that were made over there, since it will be blocked by our intention to write that module. And
         * then _we_ won't be able to write that module either, because of that window's intention. Now
         * the system is totally locked down.
         *
         * It is also critical that we _not_ emit change deltas ourselves, due to the obvious infinite
         * cycle that would ensue.
         *
         * If we don't have the focus, then we _do nothing_!
         */
        if (!document.hasFocus()) {
            return;
        }

        // The document now has an unsaved change, so make sure it is noted as a modpath
        // that we are waiting to write.
        this.recordIntentionToWrite(modpath);

        const {myNumber} = this.hub.windowManager.getNumbers();
        this.hub.windowManager.groupcastEvent({
            type: 'editDelta',
            modpath: modpath,
            delta: delta,
            origin: myNumber,
        }, {
            includeSelf: false,
        });

        // Clear existing auto-save timeout if any.
        window.clearTimeout(this.autoSaveTimeout[modpath]);
        //console.log('clear timeout', modpath, paneId);
        // If our auto-save delay is set to a positive number of milliseconds,
        // and if we are currently supposed to set up auto-save for this module,
        // then set a timeout for it.
        if (this.doAutoSave[modpath] && this.autoSaveDelay > 0) {
            this.autoSaveTimeout[modpath] = window.setTimeout(() => {
                // An unfocused window should not be trying to write anything, except in the
                // step where it writes everything immediately after losing focus. That is sort of
                // its "last act" as the controlling window, and is okay because it is achieved
                // before any changes can be made in the newly focused window. But autosave
                // timeouts have no business doing anything after focus is lost. They have
                // nothing to do anyway, precisely because of the "last act" just mentioned.
                if (document.hasFocus()) {
                    this.saveByModpath(modpath);
                    //console.log('auto-save from pane', paneId);
                }
            }, this.autoSaveDelay);
        }
        //console.log('set timeout', modpath, paneId);
    },

    reconcile: function(modpath, mergetext, newtext, pane) {
        //console.log('reconcile...');
        return new Promise(resolve => {
            const header = pane.domNode.querySelector('.edHeader');
            iseUtil.removeAllChildNodes(header);
            this.makeAuxPanel(header);
            const panel = header.querySelector('.edAuxPanel');
            const ed = this.editors[pane.id];
            const doc = this.docsByModpath[modpath];
            const yourtext = doc.getValue();
            let current = "yours";
            const dlg = new ConfirmDialog({
                title: "Confirm",
                onExecute: () => {
                    panel.style.display = 'none';
                    ed.resize(false);
                    resolve(current);
                }
            });
            panel.querySelectorAll('.auxPanelDocOpt').forEach(elt => {
                elt.addEventListener('click', event => {
                    const sel = panel.querySelector('input[name=vers]:checked');
                    const value = sel.value;
                    if (value !== current) {
                        current = value;
                        switch (value) {
                            case "yours":
                                this.setDocValueWithCursorRestore(modpath, yourtext);
                                break;
                            case "disk":
                                this.setDocValueWithCursorRestore(modpath, newtext);
                                break;
                            case "combined":
                                this.setDocValueWithCursorRestore(modpath, mergetext);
                                break;
                        }
                    }
                });
            });
            panel.querySelector('.auxPanelButton').addEventListener('click', event => {
                const versionPhrase = {
                    'yours': 'your version', 'disk': 'the version on disk', 'combined': 'the combined version'
                }[current];
                dlg.set('content', `Are you sure you want to continue with ${versionPhrase}?`);
                dlg.show();
            });
            panel.style.display = 'block';
            ed.resize(false);
        });
    },

});

return EditManager;
});
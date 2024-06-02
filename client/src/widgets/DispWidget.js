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

const ace = require("ace-builds/src-noconflict/ace.js");
require("ace-builds/src-noconflict/mode-python.js");
require("ace-builds/src-noconflict/theme-tomorrow.js");
require("ace-builds/src-noconflict/theme-tomorrow_night_eighties.js");
require("ace-builds/src-noconflict/ext-searchbox.js");

import { util as iseUtil } from "../util";

define([
    "dojo/_base/declare",
    "ise/widgets/ExampWidget"
], function(
    declare,
    ExampWidget
) {

const DispWidget = declare(ExampWidget, {

    // paneId points to Array of strings:
    fixedCodeByPaneId: null,
    // paneId points to Array of Ace editor instances:
    editorsByPaneId: null,
    // paneId points to element where editors go (if any):
    editorsElementByPaneId: null,

    editorMinHeightPixels: 50,
    contentElementSelector: '.display_container',

    constructor: function(hub, libpath, info) {
        this.fixedCodeByPaneId = new Map();
        this.editorsByPaneId = new Map();
        this.editorsElementByPaneId = new Map();
    },

    preactivate: function(wdq, uid, nm, pane) {
        // In case updating, destroy any existing editors.
        this.destroyEditors(pane.id);

        // Grab the build code, and make sure it is an array of strings.
        let buildCode = this.origInfo.build;
        if (iseUtil.isString(buildCode)) {
            buildCode = [buildCode];
        }

        // Even-indexed code strings are fixed; odd-indexed are editable.
        const fixedCode = [];
        const editors = [];

        for (let i = 0; i < buildCode.length; i++) {
            const code = buildCode[i];
            if (i % 2 === 0) {
                fixedCode.push(code);
            } else {
                const editorDiv = document.createElement('div');
                const numLines = code.split('\n').length;
                editorDiv.style.height = `${numLines + 2}em`;
                const editor = this.makeEditor(pane, editorDiv, code);
                editors.push(editor);
            }
        }

        // We want to set these up in a preactivation step, so that they are ready to
        // be returned by `this.val()`, when that is called by `ExampWidget.makePyProxyAndBuild()`,
        // which in turn is triggered by our superclass call of `ExampWidget.activate()`.
        this.fixedCodeByPaneId.set(pane.id, fixedCode);
        this.editorsByPaneId.set(pane.id, editors);
    },

    activate: function activate(wdq, uid, nm, pane) {
        this.inherited(activate, arguments);
        const activation = this.activationByPaneId.get(pane.id);
        activation.then(() => {
            // Proceed only if the pane still exists. It could have been closed while waiting
            // for Pyodide to load, and the math worker to be ready.
            if (this.existsInPane(pane.id)) {
                const widgetElement = this.widgetElementByPaneId.get(pane.id);
                const editorsElement = widgetElement.querySelector('.dispWidgetEditors');
                this.editorsElementByPaneId.set(pane.id, editorsElement);

                const eds = this.editorsByPaneId.get(pane.id);
                if (eds.length > 0) {
                    widgetElement.classList.add('editableDispWidget');
                }
                for (const editor of eds) {
                    const editorDiv = editor.container;
                    const code = editor.getValue();
                    const {
                        editorPanel, buildButton,
                        resetButton, resizeHandle
                    } = this.makeEditorPanel(editorDiv);
                    editorsElement.appendChild(editorPanel);
                    this.activateEditorPanel(pane, code, editor, editorDiv, editorPanel,
                        buildButton, resetButton, resizeHandle);
                }
            }
        });
    },

    activateEditorPanel: function(pane, code, editor, editorDiv, editorPanel,
                                  buildButton, resetButton, resizeHandle) {
        buildButton.addEventListener('click', event => {
            this.buildWithLatestCode(pane.id);
        });

        resetButton.addEventListener('click', event => {
            const currentValue = editor.getValue();
            if (currentValue === code) {
                return;
            }
            this.hub.choice({
                title: 'Confirm Reset',
                content: `<div class="iseDialogContentsStyle02 iseDialogContentsStyle04">
                          <h2>Reset to original code?</h2>
                          <h5>Original:</h5>
                          <pre class="dispWidgetCodeResetPreview">${iseUtil.escapeHtml(code)}</pre>
                          <h5>Current:</h5>
                          <pre class="dispWidgetCodeResetPreview">${iseUtil.escapeHtml(currentValue)}</pre>
                          </div>`,
                dismissCode: 'resetDisplayWidgetEditor',
            }).then(result => {
                if (result.accepted || !result.shown) {
                    editor.setValue(code);
                    editor.clearSelection();
                    this.buildWithLatestCode(pane.id);
                }
            });
        });

        resizeHandle.addEventListener('mousedown', dEvent => {
            const ay = dEvent.clientY;
            const h0 = editorDiv.clientHeight;
            const min_dy = Math.min(0, this.editorMinHeightPixels - h0);
            const resizeOverlay = editorPanel.querySelector('.dispWidgetEditorResizeOverlay');
            const resizeHandle = editorPanel.querySelector('.dispWidgetEditorResizeHandle');
            resizeOverlay.style.opacity = 0.2;
            let dy = 0;
            const moveHandler = mEvent => {
                const ey = mEvent.clientY;
                dy = ey - ay;
                dy = Math.max(min_dy, dy);
                resizeOverlay.style.bottom = (-dy)+'px';
                resizeHandle.style.bottom = (-dy)+'px';
                mEvent.stopPropagation();
            }
            const upHandler = uEvent => {
                document.documentElement.removeEventListener('mousemove', moveHandler);
                document.documentElement.removeEventListener('mouseup', upHandler);
                const h1 = Math.max(this.editorMinHeightPixels, h0 + dy);
                editorDiv.style.height = h1+'px';
                resizeOverlay.style.opacity = 0;
                resizeOverlay.style.bottom = 0;
                resizeHandle.style.bottom = 0;
                editor.resize(false);
                uEvent.stopPropagation();
            }
            document.documentElement.addEventListener('mousemove', moveHandler);
            document.documentElement.addEventListener('mouseup', upHandler);
            dEvent.stopPropagation();
        });
    },

    makeEditorPanel: function(editorDiv) {
        editorDiv.classList.add('dispWidgetEditor');

        const editorPanel = document.createElement('div');
        editorPanel.classList.add('dispWidgetEditorPanel');

        const buttonsDiv = document.createElement('div');
        buttonsDiv.classList.add('dispWidgetEditorButtonPanel');

        const buildButton = document.createElement('div');
        buildButton.classList.add('dispWidgetEditorButton', 'dispWidgetEditorBuildButton');
        buildButton.setAttribute('title', 'Build (Ctrl-B)')

        const resetButton = document.createElement('div');
        resetButton.classList.add('dispWidgetEditorButton', 'dispWidgetEditorResetButton');
        resetButton.setAttribute('title', 'Reset')

        const resizeOverlay = document.createElement('div');
        resizeOverlay.classList.add('dispWidgetEditorResizeOverlay');

        const resizeHandle = document.createElement('div');
        resizeHandle.classList.add('dispWidgetEditorResizeHandle');

        buttonsDiv.appendChild(buildButton);
        buttonsDiv.appendChild(resetButton);

        editorPanel.appendChild(editorDiv);
        editorPanel.appendChild(buttonsDiv);
        editorPanel.appendChild(resizeOverlay);
        editorPanel.appendChild(resizeHandle);

        return {editorPanel, buildButton, resetButton, resizeHandle};
    },

    makeEditor: function(pane, homeDiv, code) {
        const editor = ace.edit(homeDiv);
        const atp = iseUtil.getAceThemePath(this.hub.currentTheme);
        editor.setTheme(atp);
        editor.setOption('scrollPastEnd', 0.5);
        editor.setFontSize(this.hub.getCurrentEditorFontSize());
        iseUtil.applyAceEditorFixes(editor);
        iseUtil.reclaimAceShortcutsForPise(editor);

        const sesh = editor.getSession();
        sesh.setMode("ace/mode/python");
        sesh.setTabSize(4);
        sesh.setUseSoftTabs(true);

        editor.setValue(code);
        editor.clearSelection();

        const theDispWidget = this;
        editor.commands.addCommand({
            name: "Build",
            bindKey: {mac: "Ctrl-B"},
            exec: function (editor) {
                theDispWidget.buildWithLatestCode(pane.id);
            }
        });

        editor.resize(false);

        return editor;
    },

    /*
    * Set the theme in all the editors.
    * param theme: `light` or `dark`
    */
    setTheme: function(theme) {
        const atp = iseUtil.getAceThemePath(theme);
        for (const edArray of this.editorsByPaneId.values()) {
            for (const ed of edArray) {
                ed.setTheme(atp);
            }
        }
    },

    buildWithLatestCode: function(paneId) {
        const newValue = this.val(paneId);
        return this.receiveNewValue(paneId, newValue, true);
    },

    val: function(paneId) {
        const fixedCode = this.fixedCodeByPaneId.get(paneId);
        const editors = this.editorsByPaneId.get(paneId);

        if (!fixedCode) {
            return null;
        }

        const n = editors.length;
        let code = ''
        for (let i = 0; i < n; i++) {
            code += fixedCode[i] + editors[i].getValue();
        }
        // fixedCode array should always be one longer than editors array
        code += fixedCode[n];
        return code;
    },

    /* Check whether this widget is currently marked as trusted, under either site-wide
     * or per-user settings.
     */
    isTrusted: async function() {
        const repopath = iseUtil.getRepoPart(this.libpath);
        return await this.hub.trustManager.checkCombinedTrustSetting(
            repopath, this.version
        );
    },

    okayToBuild: async function() {
        // Note: We used to consult `this.liveInfo.trusted`, but that is now defunct as
        // we instead check live settings. (To-do: Could probably stop recording this at build time.)
        const selfOkay = (this.liveInfo.approved || await this.isTrusted());
        if (!selfOkay) {
            return false;
        }
        let ancestorsOkay = true;
        for (let w of this.ancestorDisplays.values()) {
            const ok = await w.okayToBuild();
            if (!ok) {
                return false;
            }
        }
        return (selfOkay && ancestorsOkay);
    },

    writeSubstituteHtml: function() {
        let buildCode = this.liveInfo.build;
        if (!iseUtil.isString(buildCode)) {
            let code = buildCode[0];
            for (let i = 1; i < buildCode.length; i++) {
                code += `# ${i%2===1 ? "BEGIN" : "END"} EDIT\n` + buildCode[i];
            }
            buildCode = code;
        }
        buildCode = iseUtil.escapeHtml(buildCode);
        return `<pre>${buildCode}</pre>`;
    },

    setNewHtml: function(pane, html) {
        this.makeNewGraphics(pane, html);
    },

    makeNewGraphics: function(pane, html) {
        const contentElement = this.contentElementByPaneId.get(pane.id);
        iseUtil.removeAllChildNodes(contentElement);
        contentElement.innerHTML = html;
        this.typeset(pane.id, [contentElement]).then(() => {
            this.dispatch({
                type: "widgetVisualUpdate",
                paneId: pane.id,
                widget: this,
            });
        });
    },

    destroyEditors: function(paneId) {
        const editors = this.editorsByPaneId.get(paneId);
        if (editors) {
            for (let ed of editors) {
                iseUtil.detachListeners(ed, ace);
                ed.destroy();
            }
        }
    },

    noteCopy: async function(oldPaneId, newPaneId) {
        await this.noteCopyInternal(oldPaneId, newPaneId);
        if (!this.existsInPane(oldPaneId)) {
            return;
        }
        const newEditors = this.editorsByPaneId.get(newPaneId);
        const oldEditors = this.editorsByPaneId.get(oldPaneId);
        for (let i = 0; i < newEditors.length; i++) {
            const newEd = newEditors[i];
            newEd.setValue(oldEditors[i].getValue());
            newEd.clearSelection();
        }
    },

    noteClosingPane: function noteClosingPane(pane) {
        this.inherited(noteClosingPane, arguments);
        const paneId = pane.id;

        this.destroyEditors(paneId);

        this.fixedCodeByPaneId.delete(paneId);
        this.editorsByPaneId.delete(paneId);
        this.editorsElementByPaneId.delete(paneId);
    },

});

return DispWidget;

});

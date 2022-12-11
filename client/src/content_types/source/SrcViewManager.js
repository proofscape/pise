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

const dojo = {};
const ise = {};
define([
    "dijit/Menu",
    "dijit/MenuItem",
    "dijit/MenuSeparator",
    "ise/util"
], function(
    Menu,
    MenuItem,
    MenuSeparator,
    util
){
    dojo.Menu = Menu;
    dojo.MenuItem = MenuItem;
    dojo.MenuSeparator = MenuSeparator;
    ise.util = util;
});

export class SrcViewManager {

    constructor(editManager) {
        this.editManager = editManager;
        this.vmpsByPaneId = new Map();
    }

    hasPane(paneId) {
        return this.vmpsByPaneId.has(paneId);
    }

    addCommandsAndContextMenu(editor, paneId) {
        const theEditManager = this.editManager;
        const menu = new dojo.Menu({
            targetNodeIds: [editor.container]
        });
        menu.addChild(new dojo.MenuItem({
            label: 'Toggle Overview',
            onClick: function (evt) {
                theEditManager.toggleOverviewSidebar(paneId);
            }
        }));
        menu.addChild(new dojo.MenuSeparator());
        menu.addChild(new dojo.MenuItem({
            label: 'Jog',
            onClick: function (evt) {
                theEditManager.resizeAll();
                theEditManager.freezeAllEditors(false);
            }
        }));
    }

    setContent(editor, modpath, version, paneId, text, fvr, cpos) {
        editor.setValue(text);
        editor.clearSelection();
        const vmp = ise.util.lv(modpath, version);
        this.vmpsByPaneId.set(paneId, vmp);

        const oed = editor.pfscIseOverviewEditor;
        oed.setValue(text);
        oed.clearSelection();

        editor.session.on("changeScrollTop", (scrollTop, session) => {
            this.editManager.updateOverviewGlass(paneId);
        });

        if (fvr !== undefined) {
            this.editManager.scrollEditorToRow(editor, fvr);
        }
        // Set cursor position.
        if (cpos !== undefined) {
            editor.moveCursorTo(cpos.row, cpos.column);
        } else {
            // Cursor will be at the end of the text unless we move it.
            editor.moveCursorTo(0, 0);
        }
    }

    getExistingPaneIds(info) {
        const modpath = info.modpath;
        const version = info.version;
        const vmp0 = ise.util.lv(modpath, version);
        const ids = [];
        for (let [id, vmp] of this.vmpsByPaneId) {
            if (vmp === vmp0) {
                ids.push(id);
            }
        }
        return ids;
    }

    noteClosingPane(paneId) {
        this.vmpsByPaneId.delete(paneId);
    }

}

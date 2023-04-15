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

define([
    "dojo/_base/declare",
    "dojo/dom-construct",
    "dojo/on",
    "dijit/Menu",
    "dijit/PopupMenuItem",
    "dijit/layout/ContentPane",
    "ise/widgets/Widget",
    "ise/util"
], function(
    declare,
    domConstruct,
    dojoOn,
    Menu,
    PopupMenuItem,
    ContentPane,
    Widget,
    iseUtil
) {

const LabelWidget = declare(Widget, {

    activate: function(wdq, uid, nm, pane) {
        const widget = nm.widgets.get(uid);
        // Attach a context menu.
        const menu = new Menu({
            targetNodeIds: [wdq[0]]
        });
        // Add a tail selector for the libpath.
        const tsHome = domConstruct.create("div");
        iseUtil.addTailSelector(tsHome, widget.libpath.split('.'));
        menu.addChild(new PopupMenuItem({
            label: 'Copy libpath',
            popup: new ContentPane({
                class: 'popupCP',
                content: tsHome
            })
        }));
        // Also let left-click copy the full libpath.
        dojoOn(wdq[0], 'click', function(event) {
            iseUtil.copyTextWithMessageFlashAtClick(widget.libpath, event);
        });
    },

});

return LabelWidget;

});
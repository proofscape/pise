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

define([
    "dojo/_base/declare",
    "dijit/MenuSeparator",
    "ise/widgets/Widget"
], function(
    declare,
    MenuSeparator,
    Widget
) {

const GoalWidget = declare(Widget, {

    toggleEventHandlersByPaneId: null,

    constructor: function(hub, libpath, info) {
        this.toggleEventHandlersByPaneId = new Map();
    },

    activate: function(wdq, uid, nm, pane) {
        const elt = wdq.query('.graphics')[0];
        const goalId = this.origInfo.origin;
        const homepath = this.getGoalpath();
        const studyManager = nm.hub.studyManager;

        if (goalId) {
            if (this.origInfo.user_notes) {
                studyManager.recordGoalInfoFromServer(goalId, this.origInfo.user_notes);
            }

            const cm = this.getContextMenu(pane.id);
            if (cm.getChildren().length) {
                cm.addChild(new MenuSeparator());
            }

            studyManager.addGoalbox(elt, goalId, homepath, {
                addTs: false,
                menu: cm,
            });

            const widget = this;
            const toggleHandler = function(event) {
                if (event.goalId === goalId) {
                    widget.dispatch({
                        type: 'widgetVisualUpdate',
                        paneId: pane.id,
                        widget: widget,
                    });
                }
            }
            this.toggleEventHandlersByPaneId.set(pane.id, toggleHandler);
            studyManager.on('goalBoxToggle', toggleHandler);
        }
    },

    noteClosingPane: function(pane) {
        const handler = this.toggleEventHandlersByPaneId.get(pane.id);
        if (handler) {
            this.hub.studyManager.off('goalBoxToggle', handler);
            this.toggleEventHandlersByPaneId.delete(pane.id);
        }
    },

    /* Get the libpath of the goal that this widget represents.
     * If an `altpath` has been set, we return that; otherwise, it is just
     * the libpath of this widget itself.
     */
    getGoalpath: function() {
        return this.origInfo.altpath || this.libpath;
    },

});

return GoalWidget;

});

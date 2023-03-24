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
    "dojo/on",
    "dojo/dom-class",
    "ise/widgets/NavWidget"
], function(
    declare,
    dojoOn,
    domClass,
    NavWidget
) {

const ChartWidget = declare(NavWidget, {

    // Properties
    forest: null,
    checkboxes: null,

    // Methods

    constructor: function(hub, libpath, info) {
        // Initialize our local lookup for checkboxes.
        this.checkboxes = {};
    },

    getInfoCopy: function() {
        // Start with a deep copy, as in the basic Widget class.
        var copy = this.inherited(arguments);
        // Set self as study manager, if there are any checkbox settings.
        if (copy.checkboxes) copy.studyManager = this;
        return copy;
    },

    activate: function(wdq, uid, nm, pane) {
        // Let our superclass set up the click handler.
        this.inherited(arguments);
        // If we have hovercolor, set that up.
        const info = this.origInfo;
        if (info.hovercolor) {
            const over = info.hovercolor.over,
                out  = info.hovercolor.out;
            wdq.on('mouseover', async () => {
                const targetUuids = await nm.linkingMap.get(info.uuid, this.groupId);
                for (const targetUuid of targetUuids) {
                    this.hub.contentManager.updateContentAnywhereByUuid(
                        {type: "CHART", color: over}, targetUuid, { selectPane: true });
                }
            });
            wdq.on('mouseout', async () => {
                const targetUuids = await nm.linkingMap.get(info.uuid, this.groupId);
                for (const targetUuid of targetUuids) {
                    this.hub.contentManager.updateContentAnywhereByUuid(
                        {type: "CHART", color: out}, targetUuid, { selectPane: true });
                }
            });
        }
    },

    /* Control whether checkboxes are displayed or not.
     * NB: this only works if the checkboxes were originally constructed when the Nodes in question
     *     were first being constructed. In other words, they cannot be constructed by this method,
     *     only shown or hidden.
     *
     * param b: boolean, saying whether the checkboxes should be shown (true) or hidden (false).
     */
    showCheckboxes: function(/* bool */ b) {
        if (!this.pane) return;
        if (b) {
            this.pane.domNode.classList.remove('goalBoxesHidden');
        } else {
            this.pane.domNode.classList.add('goalBoxesHidden');
        }
    },

    updateInfo: function(newInfo) {
        // Begin by updating both our `origInfo` and `liveInfo` fields, as in the base class.
        this.inherited(arguments);
        // Now update checkboxes.
        var cbInfo = this.liveInfo.checkboxes;
        if (!cbInfo) {
            // Checkbox info is not even defined. So hide checkboxes if they exist.
            this.showCheckboxes(false);
        } else {
            // Checkbox info is defined, so checkboxes should be shown.
            this.showCheckboxes(true);
            // Consider the array of nodepaths marked as checked.
            var A = cbInfo.checked || [];
            // Convert into the set of nodes that should be checked.
            var shouldBeChecked = {};
            A.forEach(function(nodepath){ shouldBeChecked[nodepath] = 1 });
            // Iterate over all checkboxes, and update their state accordingly.
            for (var nodepath in this.checkboxes) {
                var cb = this.checkboxes[nodepath];
                if (nodepath in shouldBeChecked) {
                    cb.classList.add('checked');
                } else {
                    cb.classList.remove('checked');
                }
            }
        }
    },

    /**************************************************************************
     * In very early versions of PISE, instances of ChartWidget were in charge
     * of the checkboxes on nodes. At this time, we gave checkboxes the power
     * to edit the module where the corresp. chart widget was defined. They
     * would add and remove notations to record their state as checked or not.
     *
     * That system was shut off when we introduced the StudyManager, and the
     * recording of checkbox states (and notes on checkboxes) first in the
     * browser's localStorage, and later (if the user requests it) on the server.
     *
     * The methods commented out below were involved in making ChartWidgets
     * manage checkboxes. There are now similar methods defined in the
     * StudyManager.
     *
     * For now we're keeping this dead code around, since the idea of widgets
     * that can edit modules is still an interesting one, and this serves as
     * a good model. It also helps explain other (largely? totally?) defunct
     * systems (like the `autowrites` arg of the `writeAndBuild` endpoint).
     *
     * At some point, it might be good to do a thorough review, and either
     * cut all such systems, or else keep them around if they will really
     * be used in some way. For now, it does no harm.
     **************************************************************************/
    /**************************************************************************
    addGoalboxForNode: function(elt, deducpath, nodepath) {
        var boxElt = null;
        if (this.liveInfo.checkboxes.deducs.includes(deducpath)) {
            var addTs = true,
                mgr = this;
            boxElt = this.hub.studyManager.addGoalbox(elt, nodepath, addTs, mgr).box;
            boxElt.querySelector('.checkmark').classList.add('checkmarkBlue');
            this.checkboxes[nodepath] = boxElt;
        }
        return boxElt;
    },

    isChecked: function(nodepath) {
        if (!this.liveInfo.checkboxes.checked) return;
        return this.liveInfo.checkboxes.checked.includes(nodepath);
    },

    noteCheckboxToggle: function(libpath, isChecked) {
        this.setCheckbox(libpath, isChecked);
    },

    showNotesDialog: function(libpath) {
        this.hub.studyManager.showNotesDialog(libpath);
    },

    // Set the checked/unchecked state of the checkbox for a node managed by this widget.
    //
    //param nodepath: the libpath of the node whose checkbox is to be set
    //param checked: boolean, true if the box is to be checked, false if to be unchecked.
    //
    setCheckbox: function(nodepath, checked) {
        // Set the value of the DOM element.
        var cb = this.checkboxes[nodepath];
        if (checked) {
            cb.classList.add('checked');
        } else {
            cb.classList.remove('checked');
        }
        // Is any checkbox info defined at all?
        var cbInfo = this.liveInfo.checkboxes;
        if (!cbInfo) {
            // If not, then consider whether we are being asked to set a box as checked or not.
            if (checked) {
                // In this case, a box is to be checked, so we are going to need checkbox info.
                this.liveInfo.checkboxes = {};
            } else {
                // In this case, we assume we need do nothing.
                return;
            }
        }
        // Update the array of checked nodes.
        // First: do we _have_ an array of checked nodes yet?
        if (this.liveInfo.checkboxes.checked === undefined) this.liveInfo.checkboxes.checked = [];
        var A = this.liveInfo.checkboxes.checked,
            i0 = A.findIndex(libpath => libpath === nodepath),
            present = i0 >= 0;
        // Only if the booleans `present` and `checked` differ is there sth to do.
        if (checked !== present) {
            if (present) {
                // The node has been unchecked.
                A.splice(i0, 1)
            } else {
                // The node has been checked.
                A.push(nodepath);
            }
            // Now write the new info to the back-end, if we're not in readonly mode.
            if (!this.hub.readonly) {
                new_checked_list = this.liveInfo["checkboxes"]["checked"]
                widget_path = this.libpath
                // Prepare data in the format required in order to make a targeted update
                // of fields within the data for an existing widget.
                widget_update_data = {};
                widget_update_data[widget_path] = {
                    "checkboxes.checked": new_checked_list
                }
                //console.log('Update widget ', widget_path, widget_update_data);
                this.hub.editManager.build({
                    autowrites: [{
                        type: 'widget_data',
                        widgetpath: widget_path,
                        data: widget_update_data
                    }]
                });
            }
        }
    },
    **************************************************************************/

});

return ChartWidget;

});
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
    "dojo/_base/lang",
    "ise/content_types/chart/ChartManager"
], function(
    declare,
    lang,
    ChartManager
) {

// TheorymapManager class
var TheorymapManager = declare(ChartManager, {

    // Properties
    hub: null,
    mapDescripsByPaneId: null,

    // Methods

    constructor: function() {
        this.mapDescripsByPaneId = {};
    },

    /* The info object should conform to the format accepted by Forest.requestState,
    // except that it should also define a `theorymap` property. Thus, `info` should
    // look like this:
    //
    //  {
    //      ...
    //      theorymap: {
    //          deducpath: the libpath of the deduction whose theory map you want,
    //          type: 'upper' or 'lower',
    //          version: the version of the deduction whose theory map you want,
    //          realmpath: (optional) the libpath of the realm in which the theory map
    //              should be confined. If not supplied, defaults to the repopath of
    //              the deduction in question, <-- EDIT: since switching to multi-version indexing,
    //                                             realm can only be the repo; it _could_ be fully general,
    //                                             we just haven't done it yet. For now, just don't use this!
    //      },
    //      ...
    //  }
    */
    initContent: function(info, elt, pane) {
        var theorymap = info.theorymap;
        this.mapDescripsByPaneId[pane.id] = theorymap;

        delete info.theorymap;
        var forest = this.constructForest(info, elt, pane);
        var params = this.makeInitialForestRequestParams(info);
        // Theory maps are drawn with upward flow layout:
        var layoutMethod = "KLayUp";
        params.layout = layoutMethod;

        return this.hub.xhrFor('getTheoryMap', {
            query: {
                deducpath: theorymap.deducpath,
                type: theorymap.type,
                vers: theorymap.version,
            },
            handleAs: 'json',
        }).then(resp => {
            if (this.hub.errAlert3(resp)) {
                throw new Error(resp.err_msg);
            }
            const dg = resp.dashgraph;
            const lp = dg.libpath;
            return forest.requestState({
                local: true,
                known_dashgraphs: {
                    [lp]: dg
                },
                layout: layoutMethod,
                transition: false,
                view: lp
            });
        }).then(() => {
            // Since any additional deducs will be loaded after the theory map has
            // already been displayed, we do want a transition here.
            params.transition = true;
            return forest.requestState(params);
        });
    },

    /* Write a serializable info object, completely describing the current state of a
     * given pane of this manager's type. Must be understandable by this manager's
     * own `initContent` method.
     *
     * param oldPaneId: The id of an existing ContentPane of this manager's type.
     * param serialOnly: boolean; set true if you want only serializable info.
     * return: The info object.
     */
    writeStateInfo: function writeStateInfo(oldPaneId, serialOnly) {
        var state = this.inherited(writeStateInfo, arguments);
        state.theorymap = this.mapDescripsByPaneId[oldPaneId];
        state.type = this.hub.contentManager.crType.THEORYMAP;
        return state;
    },

    /* Take note of the fact that a pane of this manager's type is about to close.
     *
     * param closingPane: The ContentPane that is about to close.
     * return: nothing
     */
    noteClosingContent: function noteClosingContent(closingPane) {
        this.inherited(noteClosingContent, arguments);
        delete this.mapDescripsByPaneId[closingPane.id];
    },

});

return TheorymapManager;
});

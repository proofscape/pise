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
    "dojo/on",
    "dojo/query"
], function(
    declare,
    dojoOn,
    query
){

/* The ResizeManager aims to keep track of any changes that can result in any
 * content pane being resized.
 *
 * For now, the only reason we need this is so we can tell Ace editors to resize
 * themselves. If we don't do that, scrolling within editors gets messed up.
 *
 * At present we respond to the following events:
 *   - resize of the outer window
 *   - clicking of the toggle button on any ExpandoPane (must register with `addExpandoPane`)
 *   - clicking of the splitter of any BorderContainer (must register with `addBorderContainer`)
 *   - adding or removing of any split by the TabContianerTree
 *
 * In the (near?) future, we may not need a whole "Manager" class to handle this.
 * There is a `ResizeObserver`
 *     https://caniuse.com/#feat=resizeobserver
 * that is already supported in Chrome and Opera, but not yet in any of the other
 * major browsers.
 *
 */
var ResizeManager = declare(null, {

    // Properties
    hub: null,
    resizeTimeout: null,
    resizeDelay: 500, // ms
    expandoDelay: 500, // ms

    // Methods

    /* param tct: The app's TabContainerTree
     */
    constructor: function(tct) {
        // Watch resize of the window.
        dojoOn(window, 'resize', this.noteGeneralResize.bind(this));
        // Register as a split listener with the TCT.
        tct.registerSplitListener(this);
    },

    // begin SplitListener interface ----------------

    noteNewSplit: function(bc) {
        this.addBorderContainer(bc);
    },

    noteRemovedSplit: function(bc) {
        this.removeBorderContainer(bc);
    },

    // end SplitListener interface ------------------

    /* This is a place for us to take note of any dojox ExpandoPanes. We need to watch
     * clicks on their expand/collapse buttons, since this generally results in resize
     * of neighboring containers (not to mention resize of the ExpandoPane itself).
     *
     * param ep: an ExpandoPane instance
     */
    addExpandoPane: function(ep) {
        var button = query(ep.domNode).query('.dojoxExpandoIcon')[0];
        //console.log('expando button', button);
        var manager = this;
        dojoOn(button, 'click', function(event){
            // Set a delay to give the expando pane time to do its animation,
            // before we note the resize.
            setTimeout(function(){
                manager.noteGeneralResize();
            }, manager.expandoDelay);
        });
    },

    /* Any time a new BorderContainer is added to the layout, it should be passed to
     * this method.
     *
     * param bc: a BorderContainer instance
     */
    addBorderContainer: function(bc) {
        // We watch click events on the BorderContainer's splitter.
        var splitter = query(bc.domNode).query('.dijitSplitter')[0];
        var manager = this;
        // Note: wanted to use 'mouseup' rather than 'click', but that is not available in Dojo???
        //     https://dojotoolkit.org/reference-guide/1.9/quickstart/events.html#events-available-for-connection
        dojoOn(splitter, 'click', function(event){
            manager.noteGeneralResize();
        });
        // And we also observe that some content panes have probably been resized
        // by the introduction of a new border container.
        this.noteGeneralResize();
    },

    /* Any time a BorderContainer is removed from the layout, it should be passed to
     * this method.
     *
     * param bc: a BorderContainer instance
     */
    removeBorderContainer: function(bc) {
        // Some content panes have probably been resized by the removal of the border container.
        this.noteGeneralResize();
    },

    /* This is meant to be a catch-all method, for responding to the fact that _something_
     * has happened which could have resulted in _some_ content pane(s) being resized.
     */
    noteGeneralResize: function() {
        //console.log('note general resize');
        // We do not do anything immediately; instead, we set a timeout.
        // This serves two purposes:
        //  (1) it allows us to respond only once when there is a rapid series of
        //      resize events, such as when the outer window is resized.
        //  (2) it introduces a pause which seems to be necessary in order to give Ace a chance
        //      to be ready for the resize request.
        if (this.resizeTimeout) {
            window.clearTimeout(this.resizeTimeout);
        }
        this.resizeTimeout = window.setTimeout(this.doGeneralResize.bind(this), this.resizeDelay);
    },

    /* This is where we do the actual resizing in answer to our `noteGeneralResize` method.
     */
    doGeneralResize: function() {
        //console.log('DO general resize');
        // For now, there is only one thing we need to do; namely, ask the EditManager to
        // resize all of the existing Ace editors.
        this.hub.editManager.resizeAll();
    },

});

return ResizeManager;
});
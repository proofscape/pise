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
    "ise/widgets/Widget",
    "ise/util",
    "ise/errors",
], function(
    declare,
    Widget,
    iseUtil,
    iseErrors
) {

// Abstract superclass of widgets involved in examplorers.
const ExampWidget = declare(Widget, {

    panesById: null,
    widgetElementByPaneId: null,
    contentElementByPaneId: null,
    errmsgElementByPaneId: null,
    errmsgByPaneId: null,
    activationByPaneId: null,

    // We keep two lookups of ParamWidgets, by UID:
    // (1) "required" params are all those whose current value is required,
    // if I am to recompute my own html, or request a validation.
    // (2) "trigger" params are those such that I do want to recompute
    // my html, and reset to a default value choice, when their value changes.

    // Example: If I am an ideal prime lying above a rational prime p, then p
    // is a trigger param, since I need to compute a whole new set of options
    // when p changes. However, if I am just an integer that is supposed to be
    // greater than p, then I don't want to reset my current value or compute a
    // new chooser display when p changes. I might need to display an error message
    // (if I am now not greater than p), but that is all. In this case, p is a
    // required param, but not a trigger param.

    ancestorParams: null,
    parentParams: null,
    ancestorDisplays: null,
    allDeps: null,

    descendants: null,

    currentEvalNumber: 0,

    constructor: function(hub, libpath, info) {
        this.panesById = new Map();
        this.widgetElementByPaneId = new Map();
        this.contentElementByPaneId = new Map();
        this.errmsgElementByPaneId = new Map();
        this.errmsgByPaneId = new Map();
        this.activationByPaneId = new Map();
        this.ancestorParams = new Map();
        this.parentParams = new Map();
        this.ancestorDisplays = new Map();
        this.allDeps = new Map();
        this.descendants = new Map();
        this.setupDependencyRelations();
    },

    registerDescendant: function(uid, widget) {
        this.descendants.set(uid, widget);
    },

    unregisterDescendant: function(uid) {
        this.descendants.delete(uid);
    },

    hasDescendant: function(uid) {
        return this.descendants.has(uid);
    },

    updateInfo: function(newInfo) {
        this.inherited(arguments);
        this.setupDependencyRelations();
    },

    /* This sets up our relations to other parameters and displays
     * on which we depend.
     *
     * We form a lookup mapping widget UIDs to Widget instances, for all
     * our dependencies.
     *
     * For parameters on which we depend: Some we just record as "required";
     * for others, we set ourselves to listen to their changes.
     *
     * This method has to work both on initialization, and on update.
     */
    setupDependencyRelations: function() {
        // Clean up anything from before.
        for (let w of this.allDeps.values()) {
            w.unregisterDescendant(this.uid);
        }
        this.ancestorParams.clear();
        this.parentParams.clear();
        this.ancestorDisplays.clear();
        this.allDeps.clear();

        // Make new settings.
        const deps = this.liveInfo['dependencies'];
        const nm = this.hub.notesManager;
        for (let depInfo of deps) {
            const w = nm.getWidget(depInfo.uid);
            this.allDeps.set(w.uid, w);
            w.registerDescendant(this.uid, this);
            if (depInfo.type === "PARAM") {
                this.ancestorParams.set(w.uid, w);
                if (depInfo.direct) {
                    this.parentParams.set(w.uid, w);
                }
            } else {
                this.ancestorDisplays.set(w.uid, w);
            }
        }
    },

    /* Given an array of examp widgets, say whether this one
     * depends directly on any of those in the array, i.e. whether
     * any of those is a parent.
     */
    hasParentDependency: function(widgets) {
        for (let w of widgets) {
            if (this.parentParams.has(w.uid)) {
                return true;
            }
        }
        return false;
    },

    /* We often want to call `val()` on an examp widget, without worrying about whether it's
     * a param or disp widget, and in such cases we're happy to get `null` for disp widgets.
     */
    val: function(paneId) {
        return null;
    },

    activate: function(wdq, uid, nm, pane) {
        const activation = new Promise(async resolve => {
            this.panesById.set(pane.id, pane);
            const widgetElement = wdq[0];
            this.widgetElementByPaneId.set(pane.id, widgetElement);
            const errmsgElement = widgetElement.querySelector('.exampWidgetErrMsg');
            this.errmsgElementByPaneId.set(pane.id, errmsgElement);

            const contentElement = wdq[0].querySelector(this.contentElementSelector);
            this.contentElementByPaneId.set(pane.id, contentElement);

            await this.makePyProxyAndBuild(pane.id, true);
            resolve();
        });
        this.activationByPaneId.set(pane.id, activation);
        return activation;
    },

    /* Say whether this widget has presence in a given notes pane.
     */
    existsInPane: function(paneId) {
        return this.widgetElementByPaneId.has(paneId);
    },

    makePyProxyAndBuild: async function(paneId, writeHtml) {
        if (this.okayToBuild()) {
            // At present, the `okayToBuild()` test is not really necessary here, as nothing
            // risky happens in the `__init__()` method of the `ExampDisplay` class. But we
            // don't want to count on this never changing during future development.
            await this.hub.mathWorkerReady;
            await this.hub.mathWorkerPeer.postRequest('makePyProxy', {
                info: this.liveInfo,
                paneId: paneId,
            });
        }
        return await this.rebuildSequence(paneId, [{
            widget: this,
            newValue: this.val(paneId),
            writeHtml: writeHtml,
        }]);
    },

    remakeAllPyProxies: function() {
        for (let paneId of this.panesById.keys()) {
            const reactivation = this.makePyProxyAndBuild(paneId, false);
            this.activationByPaneId.set(paneId, reactivation);
        }
    },

    noteNewMathWorker: function() {
        this.remakeAllPyProxies();
    },

    clearErrorMessage: function(paneId) {
        this.setErrorMessage(paneId, '');
    },

    setErrorMessage: function(paneId, msg) {
        const current_err_msg = this.errmsgByPaneId.get(paneId);
        if (msg === current_err_msg) return;

        const widget_elt = this.widgetElementByPaneId.get(paneId);
        const err_elt = this.errmsgElementByPaneId.get(paneId);
        if (widget_elt && err_elt) {
            iseUtil.removeAllChildNodes(err_elt);
            err_elt.innerHTML = msg;
            if (msg.length) {
                widget_elt.classList.add('widgetHasError');
                iseUtil.typeset([err_elt]);
            } else {
                widget_elt.classList.remove('widgetHasError');
            }
            this.errmsgByPaneId.set(paneId, msg);
        }
    },

    hasError: function(paneId) {
        const widget_elt = this.widgetElementByPaneId.get(paneId);
        return widget_elt.classList.contains('widgetHasError');
    },

    showLoadingOverlay: function(paneId, doShow) {
        const elt = this.widgetElementByPaneId.get(paneId);
        if (elt) {
            if (doShow) {
                elt.classList.add('loading');
            } else {
                elt.classList.remove('loading');
            }
        }
    },

    grayOut: function(paneId, makeGray) {
        const elt = this.widgetElementByPaneId.get(paneId);
        if (elt) {
            if (makeGray) {
                elt.classList.add('grayout');
            } else {
                elt.classList.remove('grayout');
            }
        }
    },

    /* Get an object mapping param libpaths to current values
     * for all this widget's ancestor params, in a given pane.
     */
    lookupAncestorParamValues: function(paneId) {
        const values = {};
        for (let param of this.ancestorParams.values()) {
            values[param.libpath] = param.val(paneId);
        }
        return values;
    },

    takeNextEvalNum: function() {
        const n = this.currentEvalNumber + 1;
        this.currentEvalNumber = n;
        return n;
    },

    okayToBuild: function() {
        return false;
    },

    writeSubstituteHtml: function() {
        return '';
    },

    /* Rebuild this examp widget.
     *
     * param paneId: the id of the pane where we want to build HTML for this widget
     * param options: {
     *   value: (any) new raw value on which to build (if it's a parameter)
     *   writeHtml: (bool) whether to rewrite the widget's HTML (as opposed to just rebuilding)
     * }
     * return: Promise that resolves with a formatted object (with 'err_lvl' and other fields).
     */
    rebuild: async function(paneId, options) {
        const {
            value = null,
            writeHtml = false,
        } = options || {};
        if (this.okayToBuild()) {
            await this.hub.mathWorkerReady;
            return this.hub.mathWorkerPeer.postRequest('rebuild', {
                uid: this.uid,
                paneId: paneId,
                value: value,
                writeHtml: writeHtml,
            });
        } else {
            const html = this.writeSubstituteHtml();
            return {
                err_lvl: 0,
                html: html,
            };
        }
    },

    /* Rebuild a sequence of examp widgets.
     *
     * This method manages all the appropriate visual updates. It manages gray-out, spinners, and
     * error message displays. It tries to rebuild each widget, in order, stopping if and when any
     * errors arise, and displaying error messages accordingly.
     *
     * paneId: the pane where rebuilding should happen
     * requests: array of objects of the form {
     *  widget: the examp widget instance to be rebuilt,
     *  newValue: if defined and not `null`, a new value for this widget (which must be a ParamWidget),
     *  writeHtml: (bool) whether to regenerate this widget's HTML (as opposed to just rebuilding)
     * } It is assumed that this array is in topological order, w.r.t. widget dependencies.
     */
    rebuildSequence: async function(paneId, requests) {
        //console.log('rebuildSequence', paneId, requests);

        for (let req of requests) {
            if (req.writeHtml) {
                const w = req.widget;
                w.grayOut(paneId, true);
                w.showLoadingOverlay(paneId, true);
            }
        }

        for (let req of requests) {
            const w0 = req.widget;
            const response = await w0.rebuild(paneId, {
                value: req.newValue,
                writeHtml: req.writeHtml,
            });
            const errLvl = response.err_lvl;
            if (errLvl !== 0) {
                if (errLvl === iseErrors.serverSideErrorCodes.BAD_PARAMETER_RAW_VALUE_WITH_BLAME) {
                    const uid = response.blame_widget_uid;
                    const w = uid === this.uid ? this : this.descendants.get(uid);
                    // Sometimes the uid is not among our descendants. This happens if C depends on A and B,
                    // and B does not depend on A, and A is in an error state, and the user changes B.
                    // Then C tries to update, but gets an error message blaming A. In such a case, we assume A is
                    // already displaying its error message, so there's nothing for us to do.
                    if (w) {
                        w.setErrorMessage(paneId, response.err_msg);
                    }
                } else {
                    this.hub.errAlert2(response);
                }
                console.log(response);
                break;
            } else if (req.writeHtml) {
                const html = response.html;
                // `acceptNewHtml()` includes a call to `markErrorFree()`.
                w0.acceptNewHtml(paneId, html);
            } else {
                w0.markErrorFree(paneId);
            }
        }

        for (let req of requests) {
            req.widget.showLoadingOverlay(paneId, false);
        }
    },

    markErrorFree: function(paneId) {
        this.clearErrorMessage(paneId);
        for (let param of this.ancestorParams.values()) {
            param.clearErrorMessage(paneId);
        }
        this.grayOut(paneId, false);
    },

    acceptNewHtml: function(paneId, html) {
        this.markErrorFree(paneId);
        const pane = this.panesById.get(paneId);
        this.setNewHtml(pane, html);
        this.showLoadingOverlay(paneId, false);
    },

    noteCopy: async function(oldPaneId, newPaneId) {
        // If we don't exist in the pane that's being copied, then this doesn't concern us.
        if (!this.existsInPane(oldPaneId)) {
            return;
        }
        // Wait for the initial build to take place as normal. Default param values will be used.
        // It's not that we need the initial build; it's just that this is the easiest way, given
        // the architecture of how the ContentManager makes copies of panes, and then sends out
        // the notice that one is in fact a copy of another.
        const activation = this.activationByPaneId.get(newPaneId);
        await activation;
        // Now a rebuild after copying the old pane's value will put the new pane in the same
        // state as the old. (In case of DispWidget, call to `.val()` just returns `null`.)
        await this.rebuildSequence(newPaneId, [{
            widget: this,
            newValue: this.val(oldPaneId),
            writeHtml: true,
        }]);
    },

    noteClosingPane: async function(pane) {
        const paneId = pane.id;

        // Destroy PyProxy to prevent memory leak.
        await this.hub.mathWorkerReady;
        this.hub.mathWorkerPeer.postRequest('destroyPyProxy', {
            uid: this.uid,
            paneId: paneId,
        });

        // Clean up maps
        this.panesById.delete(paneId);
        this.widgetElementByPaneId.delete(paneId);
        this.contentElementByPaneId.delete(paneId);
        this.errmsgElementByPaneId.delete(paneId);
        this.errmsgByPaneId.delete(paneId);
        this.activationByPaneId.delete(paneId);
    },

    setNewHtml: function(pane, html) {
        // Abstract method; subclasses must implement.
    },

    makeNewGraphics: function(pane, html) {
        // Abstract method; subclasses must implement.
    },

});

return ExampWidget;

});
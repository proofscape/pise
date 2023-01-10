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

                // A widget displaying an error should never be grayed out.
                // It is important the user understand they are enabled to
                // interact with -- and thus repair -- a widget having an error.
                this.grayOut(paneId, false);

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
     *   value: (any) new raw value on which to build
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
     * error message displays. It tries to rebuild each widget, in order. If a widget has an error,
     * we display an error message. We cancel the rebuild for any of this widget's descendants, but
     * continue trying to rebuild non-descendants.
     *
     * paneId: the pane where rebuilding should happen
     * requests: array of objects of the form {
     *  widget: the examp widget instance to be rebuilt,
     *  newValue: if defined and not `null`, a new value for this widget,
     *  writeHtml: (bool) whether to regenerate this widget's HTML (as opposed to just rebuilding)
     * } It is assumed that this array is in topological order, w.r.t. widget dependencies.
     */
    rebuildSequence: async function(paneId, requests) {
        for (let req of requests) {
            if (req.writeHtml) {
                const w = req.widget;
                w.grayOut(paneId, true);
                w.showLoadingOverlay(paneId, true);
            }
        }

        const widgetsWithErrors = [];

        for (let req of requests) {
            const w0 = req.widget;

            // Should we skip this one?
            let skip = false;
            for (let errW of widgetsWithErrors) {
                if (errW.hasDescendant(w0)) {
                    skip = true;
                    break;
                }
            }
            if (skip) {
                continue;
            }

            // Not skipping. Try to rebuild.
            const response = await w0.rebuild(paneId, {
                value: req.newValue,
                writeHtml: req.writeHtml,
            });

            // Handle the result.
            const errLvl = response.err_lvl;
            if (errLvl !== 0) {
                widgetsWithErrors.push(w0);
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
                console.debug(response);
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

    /* Make this examp widget receive a new raw value.
     *
     * paneId: the pane in which this value is to be received.
     * newValue: the new value.
     * writeHtml: boolean, whether to rewrite the html for this widget.
     *  That of all descendants will be rewritten regardless.
     */
    receiveNewValue: async function(paneId, newValue, writeHtml) {
        const activation = this.activationByPaneId.get(paneId);
        await activation;

        this.clearErrorMessage(paneId); // (presumed innocence)

        // Sort all descendants in topological order.
        const desc = Array.from(this.descendants.values());
        desc.sort((a, b) => {
            if (a.hasDescendant(b)) {
                return -1;
            } else if (b.hasDescendant(a)) {
                return 1;
            } else {
                return 0;
            }
        });
        // Prepend self to list, so that we have the list of all widgets
        // that we want to rebuild, and in the right order.
        desc.unshift(this);

        const rebuildRequests = [{
            widget: this, newValue: newValue, writeHtml: writeHtml,
        }];
        // For all proper descendants, we need to rebuild without any new raw value.
        // We also recompute HTML.
        for (let w of desc.slice(1)) {
            rebuildRequests.push({
                widget: w,
                newValue: null,
                writeHtml: true,
            });
        }

        this.rebuildSequence(paneId, rebuildRequests);

        this.dispatch({
            type: "widgetVisualUpdate",
            paneId: paneId,
            widget: this,
        });
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
        // state as the old.
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
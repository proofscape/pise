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
    "dojo/query",
    "dojo/request",
    "dojo/dom-class",
    "ise/examp/Chooser",
    "ise/examp/NfChooser",
    "ise/util",
    "dojo/NodeList-traverse"
], function(
    declare,
    query,
    request,
    domClass,
    Chooser,
    NfChooser,
    iseUtil
) {

// Examplorer class
var Examplorer = declare(null, {

    // Properties

    // It's useful to keep both the raw DOM element in which this examplorer lives:
    homeElt: null,
    // ...and also the Dojo `query()` thereof:
    homeQ: null,
    // libpath of the examplorer:
    libpath: null,
    // name of the examplorer:
    name: null,
    // a lookup of this examplorer's "chooser" widgets, by the name of the parameter:
    choosers: null,

    // Methods

    constructor: function(elt, libpath, name) {
        this.homeElt = elt;
        this.homeQ = query(elt);
        this.libpath = libpath;
        this.name = name;
        this.choosers = {};
        // Activate reload buttons.
        var recomputeStep = this.recomputeStep.bind(this);
        this.homeQ.query('.reload').on('click', function() {
            var reload_elt = this;
            recomputeStep(reload_elt);
        });
        // Activate choosers.
        this.activateChoosers(this.homeQ);
    },

    activateChoosers: function(eltQ) {
        // Will need reference to this Examplorer.
        var theExamplorer = this;
        // Lookup from chooser class to manaing JS type:
        var chooserTypes = {
            int_chooser: Chooser,
            nf_chooser: NfChooser,
            radio_panel_chooser: Chooser,
            prime_chooser: Chooser,
            prim_res: Chooser
        };
        // Search for choosers of each type, and activate.
        for (var cls in chooserTypes) {
            eltQ.query('.'+cls).forEach(function(elt){
                var name = query(elt).attr('name')[0],
                    chooserType = chooserTypes[cls],
                    chooser = new chooserType(theExamplorer, elt);
                theExamplorer.choosers[name] = chooser;
            });
        }
    },

    // Write an object giving each current parameter value, by name.
    getParameterLookup: function() {
        var pl = {};
        for (var name in this.choosers) {
            pl[name] = this.choosers[name].getValue();
        }
        return pl;
    },

    /* Recompute all steps up to the one in which a given element occurs.
     *
     * param elt: a DOM element belonging to the step to be recomputed
    */
    recomputeStep: function(elt) {
        //console.log('recompute up to step with element: ', elt);
        var theExamplorer = this,
            eltQ = query(elt),
            step = eltQ.closest('.step'),
            prevSteps = step.prevAll('.step'),
            stepNum = prevSteps.length + 1,
            args = {},
            params = {};
        // Grab all the parameter values
        this.extractParamVals(step[0], params);
        prevSteps.forEach(function(el){
            theExamplorer.extractParamVals(el, params);
        });
        // Set up the request args.
        args.libpath = this.libpath;
        args.name = this.name;
        args.step_num = stepNum;
        args.params = params;
        var args_j = JSON.stringify(args);
        // Ask the back end to recompute.
        request.get("/exampRecompute", {
            query: {
                args: args_j
            },
            handleAs: "json"
        }).then(
            function(resp){
                if (resp.err_lvl > 0) {
                    alert(resp.err_msg);
                    return;
                }
                //console.log(resp);
                var update = resp.update;
                // Display error if there was any.
                theExamplorer.clearAllErrs();
                var err = update.error;
                if (err !== null) {
                    theExamplorer.showErr(err);
                }
                // Do any substitutions.
                var subst_info = update.subst;
                for (var css_selector in subst_info) {
                    var html = subst_info[css_selector],
                        selection = theExamplorer.homeQ.query(css_selector);
                    // Plug in the provided html.
                    selection.innerHTML(html);
                    // If we're subbing in a new chooser, we need to activate it.
                    selection.forEach(function(elt){
                        var eltQ = query(elt);
                        if (domClass.contains(elt, 'chooser_container')) {
                            theExamplorer.activateChoosers(eltQ);
                        }
                    });
                }
                // Typeset math.
                theExamplorer.typesetMath();
            },
            function(err){console.log(err);}
        );
    },

    typesetMath: function() {
        var theExamplorer = this;
        iseUtil.typeset([this.homeElt]).then(() => {
            // Resize display elements.
            theExamplorer.homeQ.query('.display_container').forEach(function(elt) {
                theExamplorer.resizeForMath(elt);
            });
        });
    },

    resizeForMath: function(elt) {
        var min_width = 0,
            eltQ = query(elt);
        eltQ.query('.MathJax_SVG').forEach(function(el) {
            var w = el.clientWidth;
            if (w > min_width) min_width = w;
        });
        // Extra padding for math display container elements
        if (domClass.contains(elt, 'display_container')) {
            min_width += 2*32;
        }
        // Set minimum width.
        eltQ.style('min-width', min_width);
    },

    /*
     * step_elt: a step element
     * raw_params: an object into which we should store all parameter values within the step
    */
    extractParamVals: function(step_elt, raw_params) {
        var theExamplorer = this;
        query(step_elt).query('.chooser').forEach(function(elt){
            var name = query(elt).attr('name')[0],
                chooser = theExamplorer.choosers[name],
                value = chooser.value;
            raw_params[name] = value;
        });
    },

    clearAllErrs: function() {
        this.homeQ.query('.error_display').innerHTML('');
        this.homeQ.query('.inactive').removeClass('inactive');
    },

    showErr: function(err_info) {
        var msg = err_info.msg,
            name = err_info.paramName,
            num = err_info.stepNum,
            step = this.homeQ.query('.step'+num);
        step.query('.chooser').forEach(function(elt){
            var chooserQ = query(elt),
                chooserName = chooserQ.attr('name')[0];
            if (chooserName === name) {
                chooserQ.query('.error_display').innerHTML(msg);
            }
        });
        step.query('.display_container').addClass('inactive');
    },

});

return Examplorer;
});
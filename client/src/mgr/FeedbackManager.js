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

const Nanobar = require("nanobar");

define([
    "dojo/_base/declare",
    "dojo/query",
    "dojo/dom-construct",
], function(
    declare,
    query,
    domConstruct
){

// FeedbackManager class
var FeedbackManager = declare(null, {

    // Properties
    hub: null,
    homeDiv: null,
    homeQ: null,
    msgDiv: null,
    msgQ: null,
    barDiv: null,
    nanobar: null,
    isVisible: false,

    // Methods

    constructor: function(homeDiv) {
        this.homeDiv = homeDiv;
        this.homeQ = query(this.homeDiv);
        this.msgDiv = domConstruct.create('div', {'class': 'message'});
        this.msgQ = query(this.msgDiv);
        this.barDiv = domConstruct.create('div', {'class': 'progbar'});
        this.homeDiv.appendChild(this.msgDiv);
        this.homeDiv.appendChild(this.barDiv);
        this.nanobar = new Nanobar({
            target: this.barDiv
        });

        /*
        this.setPercent(63.375948574);
        this.setMessage("Building...");
        this.show(true);
        */
    },

    show: function(/* bool */ b) {
        if (b !== this.isVisible) {
            this.homeQ.style('display', b ? 'block' : 'none');
            this.isVisible = b;
        }
    },

    setPercent: function(p) {
        this.nanobar.go(p);
    },

    setMessage: function(msg) {
        this.msgQ.html(msg);
    },

    display: function(msg, pct) {
        this.setMessage(msg);
        this.show(true);
        this.setPercent(pct);
    },

    hideWithDelay: function(delay) {
        delay = delay || 1000;
        var fm = this;
        setTimeout(function(){
            fm.show(false);
            fm.setMessage('');
        }, delay);
    },

    /* Note the progress indicated by a _progress message_.
     *
     * A _progress message_ is an object that may contain the following fields:
     *      fraction_complete: a number between 0 and 1
     *      message: a text message to be displayed
     *      complete: if defined and truthy, indicates that the job is done
     */
    noteProgress: function(msg) {
        var fc = msg.fraction_complete;
        /* Subtle point: Rather than letting fc === 1 be our completion condition, we wait
         * for the msg to have a truthy `complete` field. Why? Suppose you are monitoring progress
         * on a multi-stage process that's going to reach 100% several times before it's done. Each
         * time you pass 100% to our progreess bar (we are using Nanobar http://nanobar.jacoborus.codes/),
         * the bar vanishes (with CSS transition), and any subsequent settings necessitate construction
         * of a new bar. Due to the time delay involved in the CSS transitions, if several stages complete
         * in rapid succession, you can get several bars stacked vertically, all visible on screen at
         * once. The effect is jarring and disturbing!
         */
        if (msg.crashed) {
            // The process crashed. For now at least, we just hide the progress monitor.
            // There should be other mechanisms in place to display error information to the user.
            this.show(false);
        } else if (msg.complete) {
            // The process completed. Let the progress bar run to 100, and then hide.
            this.setPercent(100);
            this.hideWithDelay();
        } else {
            // Progressing. Update message and percent complete.
            if (msg.message) this.setMessage(msg.message);
            this.show(true);
            if (fc < 1) {
                this.setPercent(fc*100);
            }
        }
    },

});

return FeedbackManager;

});
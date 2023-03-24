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
    "ise/widgets/Widget"
], function(
    declare,
    Widget
) {

/* This is an abstract Widget class representing all those widgets
 * whose job is to navigate various content types, either spawning
 * a new pane to host them, or navigating an existing pane.
 */
const NavWidget = declare(Widget, {

    activate: function(wdq, uid, nm, pane) {
        wdq.on('click', event => {
            nm.handleNavWidgetMouseEvent(uid, event);
            // Alt-click on an <a> tag seems to trigger a request to download
            // (observed in Chrome on macOS), so we need to prevent the default.
            event.preventDefault();
        });
        wdq.on('mouseover', event => {
            nm.handleNavWidgetMouseEvent(uid, event);
        });
        wdq.on('mouseout', event => {
            nm.handleNavWidgetMouseEvent(uid, event);
        });
    },

});

return NavWidget;

});
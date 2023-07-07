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

import { BasePageViewer } from "./BasePageViewer";

export class AnnoViewer extends BasePageViewer {

    /*
     * param nm: The NotesManager.
     * param parent: The DOM element in which page content is to be set.
     * param pane: The ContentPane where parent lives.
     * param uuid: The uuid of the pane where parent lives.
     * param options: {
     *   overviewScale: desired initial scale for overview panel
     * }
     */
    constructor(nm, parent, pane, uuid, options) {
        super(nm);
        options = options || {};
        this.overviewScale = options.overviewScale || this.overviewScale;
        this.nm = nm;
        this.uuid = uuid;
        this.subscriptionManager = nm.annoSubscriptionManager;

        this.elt = document.createElement('div');
        this.sidebar = document.createElement('div');
        this.sidebar.classList.add('overviewSidebar', 'globalZoom');
        this.mainview = document.createElement('div');
        const main = this.mainview;
        main.classList.add('mainview', 'globalZoom');
        main.appendChild(this.elt);
        parent.appendChild(main);
        parent.appendChild(this.sidebar);

        main.addEventListener('scroll', this.observeMainAreaScroll.bind(this));
        main.addEventListener('click', this.backgroundClick.bind(this));
        this.attachContextMenu(this.elt);
        this.attachSidebarContextMenu();

        this.pane = pane;
        this.scrollNode = main;
        this.history = [];
        this.navEnableHandlers = [];
        this.listeners = {};
        this.on('pageChange', this.updateOverview.bind(this));
    }

    beforeNavigate() {
        this.recordScrollFrac();
        return this.currentPageData;
    }

    async updatePage(loc) {
        // TODO
    }

    describeCurrentLocation() {
        const loc = super.describeCurrentLocation();
        if (loc) {
            // Note scrollFrac.
            loc.scrollFrac = this.computeScrollFrac();
        }
        return loc;
    }

    announcePageChange(update, loc, oldPageData) {
        if (update.annotationChange) {
            const event = {
                type: 'pageChange',
                uuid: this.uuid,
                oldLibpathv: null,
                oldPageData: oldPageData,
                newLibpathv: `${loc.libpath}@${loc.version}`,
            }
            const cur = this.getCurrentLoc();
            if (cur) {
                event.oldLibpathv = `${cur.libpath}@${cur.version}`;
            }
            this.dispatch(event);
        }
    }

    writeContentDescriptor(serialOnly) {
        // TODO
    }

    getCurrentLibpathv() {
        var loc = this.getCurrentLoc();
        return loc === null ? null : iseUtil.lv(loc.libpath, loc.version);
    }

    destroy() {
        // TODO
    }

    /* Set the theme on a single sphinx content window.
     */
    setTheme(theme) {
    }

    /* Set the zoom level on a single sphinx content window.
     */
    setZoom(level) {
    }

    /* Receive updated page contents.
     *
     * param contents: object with `html` and `data` (widget JSON) properties.
     */
    async receivePublication(contents) {
        // We can use a description of our current location to get the
        // scroll fraction. Then setting the contents directly in the location
        // object will get what we want from our updatePage method.
        const loc = this.describeCurrentLocation();
        loc.contents = contents;
        await super.reloadPage(loc);
    }

}

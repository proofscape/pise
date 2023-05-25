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
        super();
        options = options || {};
        this.overviewScale = options.overviewScale || this.overviewScale;
        this.nm = nm;
        this.uuid = uuid;

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

    describeLocationUpdate(loc) {
        const cur = this.getCurrentLoc() || {};
        const libpathChange = cur.libpath !== loc.libpath;
        const versionChange = cur.version !== loc.version;
        const scrollSelChange = cur.scrollSel !== loc.scrollSel;
        return {
            libpathChange: libpathChange,
            versionChange: versionChange,
            scrollSelChange: scrollSelChange,
            annotationChange: libpathChange || versionChange,
            locationChange: libpathChange || versionChange || scrollSelChange,
        };
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

    updateSubscription(update, loc) {
        if (update.annotationChange) {
            this.unsubscribe();
            if (loc.version === "WIP") {
                this.subscribe(loc.libpath);
            }
        }
    }

    unsubscribe() {
        if (this.subscribedLibpath !== null) {
            this.nm.subscriptionManager.setSubscription(this.pane.id, this.subscribedLibpath, false);
        }
    }

    subscribe(libpath) {
        // Do not subscribe to special libpaths.
        if (libpath.startsWith('special.')) libpath = null;
        this.subscribedLibpath = libpath;
        if (libpath !== null) {
            this.nm.subscriptionManager.setSubscription(this.pane.id, this.subscribedLibpath, true);
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

}

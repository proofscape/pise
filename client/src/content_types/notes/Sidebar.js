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

const dojo = {};
const ise = {};

define([
    "dijit/Menu",
    "dijit/MenuItem",
    "dijit/PopupMenuItem",
    "ise/util",
], function(
    Menu,
    MenuItem,
    PopupMenuItem,
    util
) {
    dojo.Menu = Menu;
    dojo.MenuItem = MenuItem;
    dojo.PopupMenuItem = PopupMenuItem;
    ise.util = util;
});

export class Sidebar {

    /*
     * :param viewer: the viewer instance that is using this sidebar
     * :param displayElt: the dom element where the sidebar can display its content
     * :param viewedElt: the dom element of which we are showing an overview
     * :param scrollNode: dom element whose scrolling we match
     */
    constructor(viewer, displayElt, viewedElt, scrollNode, initialScale) {
        this.viewer = viewer;
        this.displayElt = displayElt;
        this.viewedElt = viewedElt;
        this.scrollNode = scrollNode;
        this.glass = null;
        this.scale = initialScale;
        this.displayElt.classList.add('overviewSidebar', 'globalZoom');
        this.scrollNode.addEventListener('scroll', this.observeScroll.bind(this));
        this.buildContextMenu();
    }

    setScale(s) {
        this.scale = s;
        this.update();
    }

    update() {
        const doCloneChildren = true;
        const clone = this.viewedElt.cloneNode(doCloneChildren);
        clone.classList.add('sidebarContents');
        clone.style.transform = `scale(${this.scale/100})`;
        ise.util.removeAllChildNodes(this.displayElt);
        this.displayElt.appendChild(clone);

        const glass = this.makeOverviewGlass();
        this.displayElt.appendChild(glass);
        this.glass = glass;
        this.updateGlass();
    }

    makeOverviewGlass() {
        const glass = document.createElement('div');
        glass.classList.add('glass');
        glass.addEventListener('mousedown', mdEvent => {
            const ay = mdEvent.clientY;
            const a_s = this.scrollNode.scrollTop;
            const moveHandler = mmEvent => {
                const ey = mmEvent.clientY,
                    dy = ey - ay;
                this.scrollNode.scrollTop = a_s + dy / (this.scale/100);
                mmEvent.stopPropagation();
            };
            const upHandler = muEvent => {
                document.documentElement.removeEventListener('mousemove', moveHandler);
                document.documentElement.removeEventListener('mouseup', upHandler);
                muEvent.stopPropagation();
            };
            document.documentElement.addEventListener('mousemove', moveHandler);
            document.documentElement.addEventListener('mouseup', upHandler);
            mdEvent.stopPropagation();
        });
        return glass;
    }

    observeScroll() {
        this.updateGlass();
    }

    updateGlass() {
        const sf = this.viewer.computeScrollFrac();
        const h = this.displayElt.scrollHeight * this.scale/100;
        const t = sf * h;
        this.glass.style.top = t + 'px';
        const view_height = this.scrollNode.clientHeight;
        this.glass.style.height = view_height * this.scale/100 + 'px';
        this.keepGlassInView();
    }

    keepGlassInView() {
        const visible0 = this.displayElt.scrollTop;
        const visible1 = visible0 + this.displayElt.clientHeight;
        const glass0 = this.glass.offsetTop;
        const glass1 = glass0 + this.glass.offsetHeight;
        if (glass0 < visible0) {
            this.displayElt.scrollTop -= visible0 - glass0;
        } else if (glass1 > visible1) {
            this.displayElt.scrollTop += glass1 - visible1;
        }
    }

    centerGlass() {
        const visible0 = this.displayElt.scrollTop;
        const visible1 = visible0 + this.displayElt.clientHeight;
        const glass0 = this.glass.offsetTop;
        const glass1 = glass0 + this.glass.offsetHeight;
        this.displayElt.scrollTop += (glass0 + glass1)/2 - (visible0 + visible1)/2;
    }

    buildContextMenu() {
        const menu = new dojo.Menu({
            targetNodeIds: [this.displayElt]
        });
        const sidebar = this;

        const zoomSubMenu = new dojo.Menu();
        for (let z = 2; z < 11; z++) {
            const scale = 5*z;
            zoomSubMenu.addChild(new dojo.MenuItem({
                label: `${scale}`,
                onClick: function() {
                    sidebar.setScale(scale);
                    const siblings = this.getParent().getChildren();
                    for (let sib of siblings) {
                        sib.set('disabled', sib === this);
                    }
                },
                disabled: scale === sidebar.scale,
            }));
        }
        menu.addChild(new dojo.PopupMenuItem({
            label: 'Zoom',
            popup: zoomSubMenu,
        }));

        menu.addChild(new dojo.MenuItem({
            label: 'Refresh',
            onClick: function () {
                sidebar.update();
            }
        }));
        menu.addChild(new dojo.MenuItem({
            label: 'Close',
            onClick: function () {
                sidebar.viewer.showOverviewSidebar(false);
            }
        }));
    }

}

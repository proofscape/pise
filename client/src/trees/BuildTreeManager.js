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

const dragula = require("dragula");

import { TreeManager } from "./TreeManager";

const ise = {};
const dojo = {};

define([
    "dojo/query",
    "dojo/dom-construct",
    "dijit/MenuSeparator",
    "dijit/MenuItem",
    "dijit/PopupMenuItem",
    "dijit/layout/ContentPane",
    "ise/util",
    "dojo/NodeList-traverse",
    "dojo/NodeList-manipulate",
], function(
    query,
    domConstruct,
    MenuSeparator,
    MenuItem,
    PopupMenuItem,
    ContentPane,
    iseUtil,
) {
    dojo.query = query;
    dojo.domConstruct = domConstruct;
    dojo.MenuSeparator = MenuSeparator;
    dojo.MenuItem = MenuItem;
    dojo.PopupMenuItem = PopupMenuItem;
    dojo.ContentPane = ContentPane;
    ise.util = iseUtil;
});

// We make use of these in managing drag-and-drop:
const deducIconClass = 'deducIcon16';
const deducpathClassPrefix = 'deducpath-';


export class BuildTreeManager extends TreeManager {

    constructor(treeDiv) {
        super(treeDiv, {});
        this.drake = this.setUpDragAndDrop();
        this.contextMenu = this.setUpContextMenu(this.treeDiv, this.rebuildContextMenu.bind(this));
    }

    setUpDragAndDrop() {
        const drake = dragula({
            copy: true,
            isContainer: this.isDragContainer.bind(this),
            moves: this.isDraggable.bind(this),
            accepts: this.acceptsDrag.bind(this)
        });
        drake.on('drop', this.onDeducDrop.bind(this));
        return drake;
    }

    activate() {
    }

    // -----------------------------------------------------------------------------
    // DnD Handling

    isDragContainer(el) {
        const isNodeContainer = el.classList.contains('dijitTreeNodeContainer');
        const isMooseGraphArea = el.classList.contains('mooseGraphArea');
        return isNodeContainer || isMooseGraphArea;
    }

    isDraggable(el, source, handle, sibling) {
        // The user has to click either on a deduc icon, or on a deduc label.
        const handleIsDeducIcon = handle.classList.contains(deducIconClass);
        let handleIsDeducLabel = null;
        // Only if a deduc icon was not clicked do we bother checking whether a deduc label was clicked.
        if (!handleIsDeducIcon) {
            handleIsDeducLabel = dojo.query(handle).siblings('.'+deducIconClass).length;
        }
        return handleIsDeducIcon || handleIsDeducLabel;
    }

    acceptsDrag(el, target, source, sibling) {
        return target.classList.contains('mooseGraphArea');
    }

    onDeducDrop(el, target, source, sibling) {
        // We're getting `target === null` if you drop a deduc over the tree, where
        // you picked it up. Odd. I would think that the `false` returned by our `acceptsDrag`
        // method would be enough to stop us from ever getting this far in such a case.
        // And yet we do. So we start by checking for null `target`.
        if (target === null) return;
        // Find the libpath of the deduction.
        const iconElt = dojo.query(el).query('.'+deducIconClass)[0],
            iconClasses = iconElt.classList,
            n = deducpathClassPrefix.length;
        let deducpathv;
        for (let cl of iconClasses.values()) {
            if (cl.substring(0, n) === deducpathClassPrefix) {
                deducpathv = cl.substring(n);
            }
        }
        // Get the ContentPane in which the moose graph area lives.
        const pane = dojo.query(target).parent()[0];
        const [deducpath, version] = deducpathv.split("@");
        this.hub.chartManager.openDeducInExistingPane(deducpath, version, pane);
        // Destroy the copy of the tree row that was added to the moose graph area.
        dojo.domConstruct.destroy(el);
    }

    // -----------------------------------------------------------------------------

    repoIsOpen(repopathv) {
        return this.treeDivs.has(repopathv);
    }

    /* Given the data describing a repo tree model, load and display this repo tree.
     *
     * @param repopath: the libpath of the repo whose tree is given
     * @param version: the version of the repo whose tree is given
     * @param model: an array, giving the repo tree as a relational model of the kind returned
     *   by `ManifestTreeNode.build_relational_model` in `build.py` at the back-end.
     */
    loadTree({repopath, version, model}) {
        const repopathv = ise.util.lv(repopath, version);
        if (this.repoIsOpen(repopathv)) return;
        const hub = this.hub;
        const mgr = this;
        super.loadTree({
            treeUid: repopathv,
            model: model,
            modifyData: theStore => {
                // Rename root item, so that it displays the version.
                theStore.query({id: repopath})[0].name = repopathv;
            },
            initialQuery: {id: repopath},
            mayHaveChildren: function(item) {
                return item.type === "MODULE";
            },
            getIconClass: function(/*dojo.store.Item*/ item, /*Boolean*/ opened){
                if (!item || this.model.mayHaveChildren(item)) {
                    //return opened ? "dijitFolderOpened" : "dijitFolderClosed";
                    return "menuIcon ringIcon";
                }
                else if (item.type === hub.contentManager.crType.NOTES) {
                    return "menuIcon contentIcon notesIcon16";
                }
                else if (item.type === hub.contentManager.crType.CHART) {
                    let cl = "menuIcon iconDepth" + item.depth + " contentIcon deducIcon16";
                    // Embed the libpath of the deduction so we can extract it in drag-and-drop.
                    cl += " " + deducpathClassPrefix + item.libpath + "@" + version;
                    return cl;
                }
                else {
                    return "dijitLeaf";
                }
            },
            activateTreeItem: (item, event) => {mgr.activateTreeItem(item, version, event)},
            homeId: "repotree_" + repopathv.replaceAll('.', '-').replaceAll("@", "_"),
            treeDiv: this.treeDiv,
        });
        this.dispatch({
            type: 'treeLoaded',
            repopathv: repopathv,
        });
    }

    activateTreeItem(item, version, event) {
        // Do we want to load the content, or edit the source?
        // For now the rule is: holding Alt (Opt on Mac) means you want to open the source.
        let source = event.altKey;
        this.openItem({item, version, source});
    }

    /* Open a tree item.
     *
     * param item: the item to be opened. We'll make a deep copy of it; you don't have to.
     * param version: the version at which the item is to be opened.
     * param source: boolean: true if you want to edit the source code for this item,
     *               rather than opening/viewing its content.
     */
    openItem({item, version, source}) {
        const itemCopy = JSON.parse(JSON.stringify(item));
        // Given `item` might already contain `version`, in which case `version`
        // arg to this method need not be given. But if it is given, it overrides.
        if (version) {
            itemCopy.version = version;
        }
        if (source || item.type === "MODULE") {
            this.hub.contentManager.markInfoForLoadingSource(itemCopy);
        }
        this.hub.contentManager.openContentInActiveTC(itemCopy);
    }

    rebuildContextMenu(treeNode) {
        const rootItem = this.getRootItemForTreeElement(treeNode.domNode);
        const repopathv = rootItem.name;
        const [repopath, version] = repopathv.split("@");
        const item = treeNode.item;
        const isWIP = (version === "WIP");
        const cm = this.contextMenu;
        const mgr = this;

        cm.destroyDescendants();

        const tsHome = dojo.domConstruct.create("div");
        ise.util.addTailSelector(tsHome, item.libpath.split('.'));
        cm.addChild(new dojo.PopupMenuItem({
            label: 'Copy libpath',
            popup: new dojo.ContentPane({
                class: 'popupCP',
                content: tsHome
            })
        }));

        cm.addChild(new dojo.MenuSeparator());

        let sourceLabel = `${isWIP ? "Edit" : "View"} Source`;
        if (item.type !== "MODULE") {
            sourceLabel = `<span class="lrMenuItem"><span>${sourceLabel}</span><span class="menuHint">Alt-Double-Click</span></span>`;
        }
        cm.addChild(new dojo.MenuItem({
            label: sourceLabel,
            onClick: function (evt) {
                mgr.openItem({item, version, source: true});
            }
        }));

        if (item.type !== "MODULE") {
            // If not a module, then can be opened.
            cm.addChild(new dojo.MenuItem({
                label: '<span class="lrMenuItem"><span>Open</span><span class="menuHint">Double-Click</span></span>',
                onClick: function(evt){
                    mgr.openItem({item, version, source: false});
                }
            }));
            if (item.type === "CHART" && item.depth === 0) {
                // It's a TLD.
                cm.addChild(new dojo.MenuSeparator());
                cm.addChild(new dojo.MenuItem({
                    label: 'Upper theory map',
                    onClick: function(){
                        mgr.hub.contentManager.openContentInActiveTC({
                            type: "THEORYMAP",
                            theorymap: {
                                deducpath: item.libpath,
                                type: 'upper',
                                version: version,
                            }
                        });
                    }
                }));
                cm.addChild(new dojo.MenuItem({
                    label: 'Lower theory map',
                    onClick: function(){
                        mgr.hub.contentManager.openContentInActiveTC({
                            type: "THEORYMAP",
                            theorymap: {
                                deducpath: item.libpath,
                                type: 'lower',
                                version: version,
                            }
                        });
                    }
                }));
            }
            if (item.type === "CHART" || item.type === "NOTES") {
                cm.addChild(new dojo.MenuSeparator());
                this.addOpenStudyPageOption(cm, item.libpath, version);
            }
        } else {
            // The item does represent a module.
            cm.addChild(new dojo.MenuSeparator());
            this.addOpenStudyPageOption(cm, item.libpath, version);
            if (isWIP) {
                cm.addChild(new dojo.MenuSeparator());
                cm.addChild(new dojo.MenuItem({
                    label: "Build",
                    onClick: function(evt){
                        mgr.hub.editManager.build({
                            buildpaths: [item.libpath],
                            recursives: [false]
                        });
                    }
                }));
                cm.addChild(new dojo.MenuItem({
                    label: "Build Recursive",
                    onClick: function(evt){
                        mgr.hub.editManager.build({
                            buildpaths: [item.libpath],
                            recursives: [true]
                        });
                    }
                }));
            }
            if (item.libpath === repopath) {
                // It's the repo itself.
                cm.addChild(new dojo.MenuSeparator());
                // Repo options
                cm.addChild(new dojo.MenuItem({
                    label: "Refresh",
                    onClick: function(evt){
                        mgr.hub.repoManager.reloadBuildTree(repopathv);
                    }
                }));
                cm.addChild(new dojo.MenuItem({
                    label: "Close",
                    onClick: function(evt){
                        mgr.hub.repoManager.closeRepo(repopath, version);
                    }
                }));
            }
        }

        if (ise.util.libpathIsRemote(item.libpath)) {
            let modpath = item.libpath;
            let sourceRow = null;
            let modIsTerm;
            if (item.type === "MODULE") {
                modIsTerm = item.isTerminal;
            } else {
                // Any item in the structure tree that is not a module, must be an entity
                // defined within (and at the top level of) a module.
                modpath = item.modpath;
                sourceRow = item.sourceRow;
                const parentItem = treeNode.tree.model.store.get(item.parent);
                modIsTerm = parentItem.isTerminal;
            }
            const url = ise.util.libpath2remoteHostPageUrl(modpath, version, false, sourceRow, modIsTerm);
            const host = modpath.startsWith('gh.') ? 'GitHub' : 'BitBucket';
            cm.addChild(new dojo.MenuSeparator());
            cm.addChild(new dojo.MenuItem({
                label: `<span title="${url} (opens in new tab)">View at ${host}</span>`,
                onClick: function(){
                    ise.util.openInNewTab(url);
                }
            }));
        }

    }

    addOpenStudyPageOption(menu, libpath, version) {
        const hub = this.hub;
        menu.addChild(new dojo.MenuItem({
            label: 'Open study page',
            onClick: function(){
                hub.contentManager.openContentInActiveTC({
                    type: "NOTES",
                    libpath: `special.studypage.${libpath}.studyPage`,
                    version: version,
                });
            }
        }));
    }

}

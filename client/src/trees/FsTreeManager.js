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

import { TreeManager } from "./TreeManager";
import { manageBuildJob} from "../mgr/BuildManager";
import { util as iseUtil } from "../util";

const dojo = {};

define([
    "dojo/query",
    "dojo/on",
    "dojo/dom-construct",
    "dijit/MenuSeparator",
    "dijit/MenuItem",
    "dijit/PopupMenuItem",
    "dijit/layout/ContentPane",
    "dijit/ConfirmDialog",
    "dojo/NodeList-traverse",
    "dojo/NodeList-manipulate",
], function(
    query,
    on,
    domConstruct,
    MenuSeparator,
    MenuItem,
    PopupMenuItem,
    ContentPane,
    ConfirmDialog
) {
    dojo.query = query;
    dojo.on = on;
    dojo.domConstruct = domConstruct;
    dojo.MenuSeparator = MenuSeparator;
    dojo.MenuItem = MenuItem;
    dojo.PopupMenuItem = PopupMenuItem;
    dojo.ContentPane = ContentPane;
    dojo.ConfirmDialog = ConfirmDialog;
});

export class FsTreeManager extends TreeManager {

    constructor(treeDiv) {
        super(treeDiv, {});
        this.contextMenu = this.setUpContextMenu(this.treeDiv, this.rebuildContextMenu.bind(this));
    }

    activate() {
    }

    repoIsOpen(repopath) {
        return this.treeDivs.has(repopath);
    }

    loadTree({repopath, fs_model}) {
        if (this.repoIsOpen(repopath)) return;
        super.loadTree({
            treeUid: repopath,
            model: fs_model,
            initialQuery: {id: "."},
            mayHaveChildren: function(item) {
                return item.type === "DIR";
            },
            getIconClass: function(/*dojo.store.Item*/ item, /*Boolean*/ opened){
                if (!item || this.model.mayHaveChildren(item)) {
                    //return opened ? "dijitFolderOpened" : "dijitFolderClosed";
                    return "menuIcon folder2Icon";
                }
                else {
                    return "menuIcon fileIcon";
                }
            },
            activateTreeItem: this.activateTreeItem.bind(this),
            homeId: "repoFsTree_" + repopath.replaceAll('.', '-'),
            treeDiv: this.treeDiv,
        });
        this.dispatch({
            type: 'treeLoaded',
            repopath: repopath,
            repopathv: iseUtil.lv(repopath, "WIP"),
        });
    }

    activateTreeItem(item, event) {
        if (item.type === "FILE") {
            this.editItem(item);
        }
    }

    editItem(item) {
        const moduleItem = this.makeModuleItem(item);
        this.hub.repoManager.buildMgr.openItem({
            item: moduleItem,
            source: true,
        });
    }

    /* Convert an item from this tree into the sort of item that
     * can be used to load a module.
     */
    makeModuleItem(item) {
        return {
            type: "MODULE",
            version: "WIP",
            libpath: item.libpath,
            is_rst: item.name.endsWith('.rst'),
        }
    }

    libpath2treeUid(libpath) {
        return iseUtil.getRepoPart(libpath);
    }

    lookupItemByLibpathAndType(libpath, type) {
        const treeUid = this.libpath2treeUid(libpath);
        const dataStore = this.stores.get(treeUid);
        const items = dataStore.query({libpath: libpath, type: type});
        return items[0];
    }

    /* Given the libpath of any item in a repo,
     * retrieve the root item for that tree.
     *
     * See also: BuildTreeManager.getRootItemForMemberLibpathAndVersion()
     */
    getRootItemForMemberLibpath(libpath) {
        const repopath = iseUtil.getRepoPart(libpath);
        return this.lookupItemByLibpathAndType(repopath, "DIR");
    }

    /* Locate a TreeNode by the libpath and type it represents.
     *
     * Note: type is required since some items have the same libpath.
     * For example, in a non-terminal module, the directory and the
     * dunder file both have the same libpath, whereas one is of type
     * "DIR" while the other is of type "FILE".
     *
     * @param libpath: the libpath of the item
     * @param type: the type of the item, such as "DIR" or "FILE"
     * @return: the TreeNode, or null if it could not be found.
     *   NOTE: If a node has not yet been loaded into a tree (by expansion
     *   of its ancestors, if any), then this method will fail to find it.
     */
    lookupTreeNode(libpath, type) {
        const item = this.lookupItemByLibpathAndType(libpath, type);
        const treeUid = this.libpath2treeUid(libpath);
        const tree = this.trees.get(treeUid);
        const treeNode = tree ? tree.getNodesByItem(item.id)[0] : null;
        return treeNode;
    }

    rebuildContextMenu(treeNode) {
        const rootItem = this.getRootItemForTreeElement(treeNode.domNode);
        const repopath = rootItem.name;
        const item = treeNode.item;
        const cm = this.contextMenu;
        const mgr = this;

        cm.destroyDescendants();

        const tsHome = dojo.domConstruct.create("div");
        iseUtil.addTailSelector(tsHome, item.libpath.split('.'));
        cm.addChild(new dojo.PopupMenuItem({
            label: 'Copy libpath',
            popup: new dojo.ContentPane({
                class: 'popupCP',
                content: tsHome
            })
        }));

        cm.addChild(new dojo.MenuSeparator());

        cm.addChild(new dojo.MenuItem({
            label: "Edit",
            onClick: function (evt) {
                mgr.editItem(item);
            }
        }));

        cm.addChild(new dojo.MenuSeparator());

        if (item.name !== '__.pfsc' && !item.name.endsWith('.rst')) {
            cm.addChild(new dojo.MenuItem({
                label: "New Submodule",
                onClick: function (evt) {
                    mgr.addNewSubmodule(item, treeNode);
                },
            }));
        }
        cm.addChild(new dojo.MenuItem({
            label: "Build",
            onClick: function(evt){
                const job = {
                    // Q: Should a build request on a module other than root add this module
                    // as a "forced re-read"?
                    buildpaths: [repopath],
                    makecleans: [false]
                };
                manageBuildJob(mgr.hub.repoManager, job);
                mgr.hub.editManager.build(job);
            }
        }));
        cm.addChild(new dojo.MenuItem({
            label: "Build Clean",
            onClick: function(evt){
                const job = {
                    buildpaths: [repopath],
                    makecleans: [true]
                };
                manageBuildJob(mgr.hub.repoManager, job);
                mgr.hub.editManager.build(job);
            }
        }));

        const isRepo = item.libpath === repopath && item.name !== '__.pfsc';
        if (!isRepo) {
            // If not a repo then can rename if not a dunder module.
            if (item.name !== '__.pfsc') {
                cm.addChild(new dojo.MenuItem({
                    label: "Rename",
                    onClick: function (evt) {
                        mgr.renameTreeItem(item, treeNode);
                    }
                }));
            }
        } else {
            // It is the repo.
            cm.addChild(new dojo.MenuSeparator());
            cm.addChild(new dojo.MenuItem({
                label: "Trust...",
                onClick: function(evt){
                    mgr.hub.trustManager.showTrustDialog(repopath, "WIP", item.repoTrustedSiteWide);
                }
            }));
            cm.addChild(new dojo.MenuItem({
                label: "Refresh",
                onClick: function(evt){
                    mgr.hub.repoManager.reloadFsTree(repopath);
                }
            }));
            cm.addChild(new dojo.MenuItem({
                label: "Close",
                onClick: function(evt){
                    mgr.hub.repoManager.closeRepo(repopath);
                }
            }));
        }

        if (iseUtil.libpathIsRemote(item.libpath)) {
            const modpath = item.libpath;
            const isDir = item.type === "DIR";
            const modIsTerm = (!isDir && item.name !== '__.pfsc');
            const fileExt = isDir ? null : '.' + item.name.split('.')[1];
            const url = iseUtil.libpath2remoteHostPageUrl(
                modpath, "WIP", isDir, fileExt, null, modIsTerm
            );
            const host = modpath.startsWith('gh.') ? 'GitHub' : 'BitBucket';
            cm.addChild(new dojo.MenuSeparator());
            cm.addChild(new dojo.MenuItem({
                label: `<span title="${url} (opens in new tab)">View at ${host}</span>`,
                onClick: function(){
                    iseUtil.openInNewTab(url);
                }
            }));
        }

    }

    addNewSubmodule(item, treeNode) {
        const parentpath = item.libpath;
        const mgr = this;
        let name_input;
        const warning = item.type === "FILE" ?
            (`<p class="warning">The existing module will be converted from a file into a directory.</p>` +
             `<p class="warningIndent">Its contents will move to a <span class="monospace">__.pfsc</span> file.</p>`) : '';
        const dlg = new dojo.ConfirmDialog({
            title: `Add new submodule under <code>${parentpath}</code>`,
            content: `
                <div class="newSubmoduleDialog">
                    ${warning}
                    <p>Choose a filename for the new submodule.</p>
                    <p>Filename must end with either <span class="monospace">.pfsc</span> &nbsp; or <span class="monospace">.rst</span></p>
                    <input type="text" size="48" placeholder="name.ext"/>
                </div>
            `,
            onExecute: function() {
                mgr.markTreeNodeAsWaiting({
                    treeNode: treeNode,
                    text: treeNode.label,
                });
                const name = name_input.value;
                mgr.hub.socketManager.splitXhrFor('makeNewSubmodule', {
                    method: "PUT",
                    handleAs: "json",
                    form: {
                        parentpath: parentpath,
                        name: name,
                    }
                }).then(resp => {
                    if (mgr.hub.errAlert3(resp.immediate) || !resp.delayed) {
                        mgr.settleWaitingTreeNode({
                            treeNode: treeNode,
                            accept: false,
                        });
                    } else {
                        resp.delayed.then(msg => {
                            if (mgr.hub.errAlert3(msg)) {
                                mgr.settleWaitingTreeNode({
                                    treeNode: treeNode,
                                    accept: false,
                                });
                            } else {
                                mgr.reloadSubtree(msg.parentpath, msg.oldFiletype).then(() => {
                                    const parentNode = mgr.lookupTreeNode(msg.parentpath, "DIR");
                                    if (parentNode) mgr.expandTreeNode(parentNode);
                                })
                            }
                        });
                    }
                });
            },
            //onCancel: function() { console.log('cancel'); }
        });
        name_input = dlg.domNode.querySelector('input')
        iseUtil.noCorrect(name_input);
        dojo.on(name_input, 'keydown', e => {
            if (e.code === "Enter") {
                dlg.okButton.domNode.querySelector('.dijitButtonNode').click();
            }
        });
        dlg.show();
    }

    renameTreeItem(item, treeNode) {
        const labelQuery = dojo.query(treeNode.domNode).children('.dijitTreeRow').query('.dijitTreeLabel');
        const existingLabel = treeNode.label;
        const inputBox = dojo.domConstruct.create("input", {
            type: "text",
            value: existingLabel,
            spellcheck: false,
            placeholder: "Enter a name"
        });
        let revert = false;
        // Stop propagation on click, so tree element doesn't open/close, stealing the focus!
        dojo.on(inputBox, "click", function(e){e.stopPropagation();});
        // Stop propagation on keypress, so tree doesn't try to navigate or open/close.
        dojo.on(inputBox, "keypress", function(e){e.stopPropagation();});
        // Capture keydown events.
        dojo.on(inputBox, "keydown", function(e){
            if (e.key === "Escape") {
                // Revert value.
                revert = true;
                labelQuery.innerHTML(existingLabel);
            }
            else if (e.key === "Enter") {
                inputBox.blur();
            }
            // Also need to stop propagation here.
            e.stopPropagation();
        });
        // On blur we want to accept the current value.
        dojo.on(inputBox, "blur", e => {
            if (!revert) {
                // Accept value.
                let newName = e.target.value;
                if (newName === existingLabel) {
                    // Revert.
                    labelQuery.innerHTML(existingLabel);
                } else {
                    const args = {
                        libpath: item.libpath,
                    };
                    if (item.type === "FILE") {
                        args.newFilename = newName;
                    } else if (item.type === "DIR") {
                        args.newDirname = newName;
                    }
                    this.hub.socketManager.splitXhrFor('renameModule', {
                        method: "PATCH",
                        handleAs: "json",
                        form: args,
                    }).then(resp => {
                        if (this.hub.errAlert3(resp.immediate) || !resp.delayed) {
                            // Revert.
                            labelQuery.innerHTML(existingLabel);
                        } else {
                            this.markTreeNodeAsWaiting({
                                treeNode: treeNode,
                                text: newName,
                                revertTo: existingLabel,
                            });
                            resp.delayed.then(msg => {
                                if (this.hub.errAlert3(msg)) {
                                    this.settleWaitingTreeNode({
                                        treeNode: treeNode,
                                        accept: false,
                                    });
                                } else {
                                    // I think we _should_ be able to just reload the subtree for the renamed
                                    // item itself, like this:
                                    //    this.reloadSubtree(msg.oldLibpath, msg.filetype, msg.newLibpath);
                                    // and it _almost_ works. We've told our data store to sort by `sibling`
                                    // attribute, but the sorting seems to be slightly broken. The item usually
                                    // does move, but it seems to land one step away from where it should. Is it
                                    // a bug in Dojo code? Should investigate....
                                    // Until then, our workaround is to reload the subtree rooted at the _parent_
                                    // of the renamed item:
                                    const parentpath = iseUtil.getParentPath(msg.newLibpath);
                                    this.reloadSubtree(parentpath, "DIR");
                                }
                            })
                        }
                    });
                }
            }
        });
        // Replace the existing label with the input box, then focus and select all.
        labelQuery.innerHTML(inputBox);
        inputBox.select();
        inputBox.focus();
    }

    reloadSubtree(oldLibpath, oldType, newLibpath) {
        newLibpath = newLibpath || oldLibpath;
        const repopath = iseUtil.getRepoPart(oldLibpath);
        return this.hub.socketManager.xhrFor('loadRepoTree', {
            query: { repopath: repopath, vers: "WIP" },
            handleAs: 'json',
        }).then(resp => {
            if (this.hub.errAlert3(resp)) return;
            if (!resp.fs_model) {
                this.hub.errAlert('Could not obtain new directory scan.');
                return;
            }
            const items = resp.fs_model;
            const basepath = newLibpath + '.';
            const newItems = items.filter(item => item.libpath === newLibpath || item.libpath.startsWith(basepath));
            //console.log('items', items);
            //console.log('newItems', newItems);
            const oldItem = this.lookupItemByLibpathAndType(oldLibpath, oldType);
            if (!oldItem) {
                this.hub.errAlert('Could not locate old tree item.');
                return;
            }
            const treeUid = this.libpath2treeUid(oldLibpath);

            super.reloadSubtree(treeUid, oldItem.id, newItems);
        });
    }

}

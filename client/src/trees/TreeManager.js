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

import { Listenable } from "browser-peers/src/util";

const dojo = {};

define([
    "dojo/query",
    "dojo/on",
    "dojo/mouse",
    "dijit/registry",
    "dojo/dom-construct",
    "dojo/store/Memory",
    "dojo/store/Observable",
    "dijit/tree/ObjectStoreModel",
    "dijit/Tree",
    "dijit/Menu",
    "dojo/NodeList-traverse",
    "dojo/NodeList-manipulate",
], function(
    query,
    on,
    mouse,
    registry,
    domConstruct,
    Memory,
    Observable,
    ObjectStoreModel,
    Tree,
    Menu,
) {
    dojo.query = query;
    dojo.on = on;
    dojo.mouse = mouse;
    dojo.registry = registry;
    dojo.domConstruct = domConstruct;
    dojo.Memory = Memory;
    dojo.Observable = Observable;
    dojo.ObjectStoreModel = ObjectStoreModel;
    dojo.Tree = Tree;
    dojo.Menu = Menu;
});

export class TreeManager extends Listenable {

    constructor(treeDiv, listeners) {
        super(listeners);
        this.hub = null;
        this.treeDiv = treeDiv;
        this.stores = new Map();
        this.models = new Map();
        this.trees  = new Map();
        this.treeDivs = new Map();
    }

    getAllOpenTreeUids() {
        return this.trees.keys();
    }

    setUpContextMenu(div, rebuild) {
        // See https://dojotoolkit.org/reference-guide/1.10/dijit/Menu.html#attaching-to-multiple-nodes
        //     https://dojotoolkit.org/reference-guide/1.10/dijit/Tree.html#context-menu
        const contextMenu = new dojo.Menu({
            targetNodeIds: [div.id],
            selector: ".dijitTreeNode"
        });
        /* Would be great to listen to the "open" event of the context menu, but, as discussed here,
               http://dojo-toolkit.33424.n3.nabble.com/dijit-menu-event-quot-before-open-quot-td3699277.html
           that is too late. By then, the size and position of the context menu have already been calculated.
           So if we now change its contents, it may wind up being drawn partially off-screen.
           Unfortunately, there is no "before open" event. So we cannot do sth like this:

             dojo.on(menu, 'beforeopen', function(e){//rebuild menu...});

           Instead, we listen to mousedown anywhere in the tree area, and filter to see if it was a
           right-click and if the target lies within a dijitTreeNode.
         */
        dojo.on(div, 'mousedown', function(e) {
            if (dojo.mouse.isRight(e)) {
                // Get the clicked element.
                const clickedElt = e.target;
                // Any ancestor that is of class dijitTreeNode?
                const dtnList = dojo.query(clickedElt).closest('.dijitTreeNode');
                if (dtnList.length) {
                    // If so, then we can access the TreeNode widget behind this, and rebuild the menu.
                    const dtn = dtnList[0];
                    const tn = dojo.registry.byNode(dtn);
                    rebuild(tn);
                }
            }
        });
        return contextMenu;
    }

    closeRepo(treeUid) {
        const treeDiv = this.treeDivs.get(treeUid);
        if (treeDiv) {
            this.treeDiv.removeChild(treeDiv);
            this.stores.delete(treeUid);
            this.models.delete(treeUid);
            this.trees.delete(treeUid);
            this.treeDivs.delete(treeUid);
        }
    }

    loadTree({
         treeUid, model, modifyData,
         initialQuery, mayHaveChildren,
         getIconClass, activateTreeItem,
         homeId, treeDiv
    }) {
        let theStore = new dojo.Memory({
            data: model,
            getChildren: function(item) {
                return this.query(
                    {parent: item.id},
                    {sort: [{attribute: "sibling"}]},
                    // See https://dojotoolkit.org/api/1.10/dojo/store/api/Store.QueryOptions
                );
            }
        });
        // Wrap the store as an observable.
        theStore = new dojo.Observable(theStore);

        if (modifyData) {
            modifyData(theStore);
        }

        const theModel = new dojo.ObjectStoreModel({
            store: theStore,
            // Initial query loads the root node of the tree.
            query: initialQuery,
            mayHaveChildren: mayHaveChildren,
        });

        const tree = new dojo.Tree({
            model: theModel,
            openOnClick: true, // open/close by clicking anywhere (not just on +/- icon)
            getIconClass: getIconClass,
            onClick: function(item, row, event){
                // We'll set a boolean, `activate` to true iff the item should be activated.
                // (Usually this means it should be "opened".)
                let activate = false;
                // One possibility is that the user pressed the 'Enter' key.
                if (event.type === "click" && event._origType === "keyup") {
                    // With a dijit tree, this happens only when the user hit the Enter key.
                    activate = true;
                }
                // Activate?
                if (activate) {
                    activateTreeItem(item, event);
                }
            },
            onDblClick: function(item, node, event) {
                activateTreeItem(item, event);
            },
        });
        // Make a div where the tree can live.
        const home = dojo.domConstruct.create("div", {
            id: homeId
        });
        // Insert home div in lexicographic order by ID.
        let refNode = null;
        for (let c of treeDiv.childNodes) {
            if (homeId <= c.id) {
                refNode = c;
                break;
            }
        }
        // If refNode still `null`, then `home` will just be inserted as last child.
        treeDiv.insertBefore(home, refNode);
        // Finally, can place the tree and start it up.
        tree.placeAt(home);
        tree.startup();
        // Keep references.
        this.stores.set(treeUid, theStore);
        this.models.set(treeUid, theModel);
        this.trees.set(treeUid, tree);
        this.treeDivs.set(treeUid, home);
    }

    /* Given any DOM element belonging to a repo tree, figure out which
     * tree we're in.
     *
     * @param element: any DOM element belonging to a repo tree
     * @return: the data item for the root node of the tree, or else `null` if
     *   the given element does not appear to actually belong to any repo tree.
     */
    getRootItemForTreeElement(element) {
        const rootElt = dojo.query(element).closest('.dijitTreeIsRoot')[0];
        if (!rootElt) return null;
        const rootNode = dojo.registry.byNode(rootElt);
        return rootNode.item;
    }

    /* Prune a tree at a given item.
     *
     * @param treeUid: the unique id of the tree in question.
     * @param itemId: the id of the item at which pruning should be done.
     * @param options: {
     *   includeItem {bool| default true}: prune the named item too.
     * }
     */
    pruneTreeAtItem(treeUid, itemId, options) {
        const {
            includeItem = true,
        } = options || {};
        const dataStore = this.stores.get(treeUid);
        if (!dataStore) return;
        const descendants = this.getAllDescendants(treeUid, itemId);
        for (let desc of descendants) {
            dataStore.remove(desc.id);
        }
        if (includeItem) {
            dataStore.remove(itemId);
        }
    }

    /* Get all descendants of a given item in a given tree.
     *
     * @param treeUid: the unique id of the tree in question.
     * @param itemId: the id of the item in question.
     * @return: array of items
     */
    getAllDescendants(treeUid, itemId) {
        const dataStore = this.stores.get(treeUid);
        if (!dataStore) return [];
        let descendants = [];
        let queue = [itemId];
        while (queue.length) {
            const id = queue.shift();
            const children = dataStore.query({parent: id});
            for (let child of children) {
                descendants.push(child);
                queue.push(child.id);
            }
        }
        return descendants;
    }

    /* Prune the tree at a particular item, and then load new items.
     *
     * @param newItems: array of new items to be added.
     * All other params are exactly as for the `pruneTreeAtItem()` method.
     */
    reloadSubtree(treeUid, itemId, newItems, options) {
        this.pruneTreeAtItem(treeUid, itemId, options);
        const dataStore = this.stores.get(treeUid);
        for (let item of newItems) {
            dataStore.add(item);
        }
    }

    /* Mark a tree node (i.e. row in the tree view) as "waiting".
     * This means display a spinner on that row, and change the label text.
     *
     * @param treeNode: the TreeNode whose label is to be changed.
     * @param text: the text that should appear beside the spinner.
     * @param revertTo: optional label to revert to in case we later call `settleWaitingTreeNode` with
     *   `accept = false`. If not provided, we use the existing label of the TreeNode.
     * @return: nothing
     */
    markTreeNodeAsWaiting({ treeNode, text, revertTo }) {
        const labelQuery = dojo.query(treeNode.domNode).children('.dijitTreeRow').query('.dijitTreeLabel');
        const existingLabel = revertTo || treeNode.label;
        const img_src = this.hub.urlFor('staticISE') + '/loading-icon.gif';
        labelQuery.innerHTML(`
            <span class="waitingTreeRow" data-ise-old-label="${existingLabel}">
                <img src="${img_src}" width="16px" height="16px"/>
                <span class="newText">${text}</span>
            </span>
        `);
    }

    /* After marking a tree node as waiting (see `markTreeNodeAsWaiting` method), use this
     * method to "settle" that node, one way or another. This means to take away the spinner,
     * and either restore the original text, accept the alternate text provided while waiting,
     * or supply some completely new text.
     *
     * @param treeNode: the TreeNode whose label is to be settled.
     * @param accept: boolean. False means you want to simply revert the label to what it was
     *   before the node was marked as waiting. True means you want to accept instead the text
     *   you supplied while waiting; however, see also `text` arg.
     * @param text: optional string. If supplied, and if `accept` is true, then take this as
     *   the new label text.
     * @return: nothing
     */
    settleWaitingTreeNode({ treeNode, accept, text }) {
        const labelQuery = dojo.query(treeNode.domNode).children('.dijitTreeRow').query('.dijitTreeLabel');
        const waitingRowQuery = labelQuery.query('.waitingTreeRow');
        if (!waitingRowQuery) return;
        let label;
        if (accept) {
            if (text) {
                label = text;
            } else {
                const newTextSpan = waitingRowQuery.query('.newText')[0];
                label = newTextSpan.innerText;
            }
        } else {
            label = waitingRowQuery[0].getAttribute('data-ise-old-label');
        }
        labelQuery.innerHTML(label);
    }

    /* Find the ids of all "essential" expanded nodes. A node is considered
     * essential if it is expanded, but none of its children is. Expanding these
     * nodes and their ancestors at a later time will restore a newly opened (and
     * thus completely collapsed) tree to its present state.
     *
     * @param treeUids: optional array of uids of the trees you want to survey;
     *   if not supplied, we look at all currently open trees.
     * @return: Map from treeUids to arrays of itemIds.
     */
    findEssentialExpandedIds(treeUids) {
        treeUids = treeUids || this.trees.keys();
        const essentialIdsByTreeUid = new Map();
        for (let treeUid of treeUids) {
            const tree = this.trees.get(treeUid);
            if (!tree) continue;
            const root = tree.rootNode;
            const ids = [];
            if (root.isExpanded) {
                this._findEssentialExpandedIdsRec(root, ids);
            }
            essentialIdsByTreeUid.set(treeUid, ids);
        }
        return essentialIdsByTreeUid;
    }

    // Recursive method used by `findEssentialExpandedIds`.
    _findEssentialExpandedIdsRec(u, ids) {
        const children = u.getChildren();
        let hasExpandedChildren = false;
        for (let ch of children) {
            if (ch.isExpanded) {
                hasExpandedChildren = true;
                this._findEssentialExpandedIdsRec(ch, ids);
            }
        }
        if (!hasExpandedChildren) {
            ids.push(u.item.id);
        }
    }

    /* Expand a set of nodes belonging to a single tree, plus all their ancestors.
     *
     * @param treeUid: the unique id of a tree.
     * @param itemIds: an array of ids of items belonging to this tree.
     * @return: promise that resolves when all the node expansions are complete (or as many
     *   as we could complete before anything went wrong).
     */
    expandNodesPlusAncestors(treeUid, itemIds) {
        let lastJob = Promise.resolve();
        const tree = this.trees.get(treeUid);
        const dataStore = this.stores.get(treeUid);
        if (!tree || !dataStore) return lastJob;
        for (let itemId of itemIds) {
            const path = [];
            let skip = false;
            let item = {parent: itemId}; // dummy item to get loop started
            while (item.parent) {
                item = dataStore.query({id: item.parent})[0];
                if (!item) {
                    skip = true;
                    break;
                }
                path.unshift(item.id);
            }
            if (skip) continue;
            lastJob = lastJob.then(() => tree.set('path', path))
                // Setting the path only expands _to_ the last node, but we want to
                // expand the last node too:
                .then(() => {
                    const treeNode = tree.getNodesByItem(itemId)[0];
                    if (treeNode) {
                        return this.expandTreeNode(treeNode);
                    }
                });
        }
        // Finally set an empty path so no tree items are selected.
        return lastJob.then(() => tree.set('path', []));
    }

    /* Expand a TreeNode if not already, and return a promise that resolves
     * when the TreeNode is expanded.
     */
    expandTreeNode(treeNode) {
        return treeNode.isExpanded ? Promise.resolve() : treeNode.tree._expandNode(treeNode);
    }


    // Scrap -------

    /* This was an old method for trying to update just parts of a tree that had been
     * rebuilt, instead of reloading the entire tree. It was set aside since it seemed
     * a bit buggy.
     *
    noteRebuiltTreeItems: function({ items }) {
        // We expect that the first item will always be that representing the module that
        // was just rebuilt, while the subsequent items will represent all its contents.
        const moduleItem = items[0],
            newContents = items.slice(1),
            modpath = moduleItem.libpath,
            repopath = iseUtil.getRepoPart(modpath);
        // A tree can only be _re_built if it is @WIP:
        const repopathv = iseUtil.lv(repopath, "WIP");
        // Have we got a tree for this repo?
        const dataStore = this.stores.get(repopathv);
        if (!dataStore) return;  // Seems we don't have it.
        // Proceed if we do have a data store for the repo in question.
        // First remove any existing "content" children (i.e. _not_ submodules) of the module node.
        const existingChildren = dataStore.query({parent: moduleItem.id});
        existingChildren.forEach(function(child){
            if (child.type !== "MODULE") {
                dataStore.remove(child.id);
            }
        });
        // Now add the new items.
        newContents.forEach(function(item){
            dataStore.add(item);
        });
    },
     */

}

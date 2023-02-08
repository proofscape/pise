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

/**
 * Define a TabContainerTree class for use with Dojo Toolkit.
 *
 * Supports:
 *
 *      splitting vertically and horizontally
 *      moving an existing tab to, or opening an existing tab in, another tab container
 *      cleaning up when any tab container is emptied
 *
 * Author: Steve Kieffer <http://skieffer.info>
 *
 * About:
 *
 * The class name "TabContainerTree" refers to a "Tree" since this is what you have when
 * you begin introducing vertical and horizontal splits. The tree contains four types of
 * nodes: Root, Column, Row, and Leaf. These nodes correspond to graphical elements.
 *
 * The one Root node represents the outermost container, in which all the splits will
 * be arranged.
 *
 * Each TabContainer is represented by a Leaf node. If, initially, you just have one
 * TabContainer, then the tree looks like this:
 *
 *                                          *
 *                                          |
 *                                          L0
 *
 * When you split a TabContainer vertically, you replace its Leaf node with a Column
 * node. The Leaf node survives as one of the Column node's two children. The other
 * child is a new Leaf node, representing the new TabContainer you have introduced
 * by splitting. The Column node itself represents a BorderContainer we introduce to
 * hold the two TabContainers.
 *
 *                                          *
 *                                          |
 *                                          C
 *                                         / \
 *                                        L0  L1
 *
 * Similarly, a horizontal split introduces a Row node with two children. Like a
 * Column node, a Row node represents a new BorderContainer.
 *
 *                                          *
 *                                          |
 *                                          C
 *                                         / \
 *                                        L0  R
 *                                           / \
 *                                          L1  L2
 *
 * It is by traversing such trees that we can compute the "address" of each TabContainer,
 * e.g. "Column 2, Row 1" for the TabContainer represented by L1 in the above diagram.
 *
 * The code in this module is concerned with such tree computations e.g. when it prepares
 * popup menu options allowing the user to move a tab from one container to another.
 *
*/

const dragula = require("dragula");

define([
    "dojo/_base/declare",
    "dojo/on",
    "dojo/topic",
    "dojo/_base/lang",
    "dojo/dom-style",
    "dojo/dom-class",
    "dijit/registry",
    "dijit/layout/BorderContainer",
    "dijit/layout/LayoutContainer",
    "dijit/layout/TabContainer",
    "dijit/layout/ContentPane",
    "dijit/Menu",
    "dijit/MenuItem",
    "dijit/MenuSeparator",
    "dijit/PopupMenuItem"
], function(
    declare,
    dojoOn,
    dojoTopic,
    dojoLang,
    domStyle,
    domClass,
    registry,
    BorderContainer,
    LayoutContainer,
    TabContainer,
    ContentPane,
    Menu,
    MenuItem,
    MenuSeparator,
    PopupMenuItem
){

var tct = {};
tct.ROOTTYPE = 'Root';
tct.COLTYPE = 'Column';
tct.ROWTYPE = 'Row';
tct.LEAFTYPE = 'Leaf';

// -----------------------------------------------------------------------
// RcCounter class


tct.RcCounter = declare(null, {

    // Properties

    // Type (tct.COLTYPE or tct.ROWTYPE)
    type: null,
    // Number (a sequential counter)
    num: 1,

    // Methods

    constructor : function(type, num) {
        this.type = type;
        this.num = num;
    },

    // Increment the counter.
    inc : function() {
        this.num++;
    },

    // Write a string representation.
    toString : function() {
        return this.type + ' ' + this.num;
    }

});

// -----------------------------------------------------------------------
// Node class

tct.Node = declare(null, {

    type: null,
    parent: null,

    getParent : function() {
        return this.parent;
    },

    setParent : function(parent) {
        // Cannot set a parent for the root node.
        if (this.type !== tct.ROOTTYPE) {
            this.parent = parent;
        }
    }

});


// -----------------------------------------------------------------------
// RootNode class

tct.RootNode = declare(tct.Node, {

    // Properties

    type: tct.ROOTTYPE,
    child: null,
    tct: null,

    // Methods

    constructor : function(tct) {
        this.tct = tct;
    },

    // Set the one child of the root node.
    // (The root node only ever has one child.)
    setChild : function(child) {
        this.child = child;
        child.setParent(this);
    },

    replaceChild : function(oldChild, newChild) {
        // Since root node only has one child, there's nothing to figure out.
        this.setChild(newChild);
    },

    getLeftSizeFractions : function() {
        var fracs = [];
        this.child.getLeftSizeFractions(fracs);
        return fracs;
    },

    setLeftSizeFractions : function(fracs) {
        this.child.setLeftSizeFractions(fracs);
    },

    computeLeafOrder : function() {
        var order = [];
        this.child.computeLeafOrder(order);
        return order;
    },

    /* Computes a description of the current tree structure, in the form of
     * an array of "V", "H", and "L" chars. These describe the splits and
     * leaf nodes in Polish notation.
     */
    computeTreeDescrip : function() {
        var desc = [];
        this.child.computeTreeDescrip(desc);
        return desc;
    },

    /* Pass a structure description of the form returned by the `computeTreeDescrip` method.
     * We make that structure below this point, introducing new splits as necessary.
     */
    makeStructure : function(desc) {
        // Work with a copy, so as not to destroy the input.
        desc = desc.slice();
        this.child.makeStructure(desc);
    },

    /**
     * Return an Array of the appropriate MenuItems to represent the options for
     * moving a tab from one TC to another.
     *
     * If there is exactly one leaf in the entire tree:
     *      The Array will be empty. There are no movement options.
     *
     * If there are exactly two leaves in the entire tree:
     *      The Array will be contain two MenuItems. One will say, "Move To Opposite Group",
     *      and the other will say, "Open In Opposite Group".
     *
     * If there are three or more leaves in the tree:
     *      The Array will contain two PopupMenuItems, i.e. the kind of item that has
     *      an arrow that leads to a submenu. One will say, "Move To..." and the other
     *      will say, "Open In...". The submenus will describe the various tab groups
     *      in terms of rows and columns.
     *
     * Caveat: if an 'openCopy' function hasn't been provided, then divide the above
     * lengths by two; there will be no "Open" options, only "Move".
     *
     * param: forLeaf  The LeafNode for which this menu is being prepared.
     *        (This is so we can disable movement to self.)
    */
    writeMovementMenuItems : function(forLeaf) {
        // First consider the case that there is exactly one leaf in the entire tree.
        if (this.child.type === tct.LEAFTYPE) {
            // In this case there are no movement options.
            return [];
        }
        // Next consider the case that there are exactly two leaves in the entire tree.
        else if (this.child.isTerminal()) {
            // In this case we get two MenuItems, to move-to or open-in the "opposite group".
            var otherGrandChild = this.child.getOtherChild(forLeaf),
                otherTcId = otherGrandChild.getTC().id,
                theManager = this.tct,
                items = [];
            items.push(
                new MenuItem({
                    label: "Move To Opposite Group",
                    onClick: function(){
                        var button = registry.byNode(this.getParent().currentTarget);
                            pane = button.page;
                        theManager.movePane(pane, otherTcId);
                    }
                })
            );
            if (this.tct.canOpenCopy()) {
                items.push(
                    new MenuItem({
                        label: "Open In Opposite Group",
                        onClick: function(){
                            var button = registry.byNode(this.getParent().currentTarget);
                                pane = button.page;
                            theManager.openCopyOfPane(pane, otherTcId);
                        }
                    })
                );
            }
            return items;
        }
        // Finally, we have the case that there are three or more leaves in the tree.
        else {
            var moveSubMenu = new Menu(),
                openSubMenu = new Menu(),
                items = [],
            // Here we again use an rc-address array. But this time, unlike in the
            // setAddresses function, it's best if we initialize the array for our child's type.
                rcAddrArray = [new tct.RcCounter(this.child.type, 1)];
            this.child.writeMovementMenuItems(forLeaf, rcAddrArray, moveSubMenu, openSubMenu);
            items.push(
                new PopupMenuItem({
                    label: "Move To...",
                    popup: moveSubMenu
                })
            );
            if (this.tct.canOpenCopy()) {
                items.push(
                    new PopupMenuItem({
                        label: "Open In...",
                        popup: openSubMenu
                    })
                );
            }
            return items;
        }
    }

});

// -----------------------------------------------------------------------
// BinaryNode class

tct.BinaryNode = declare(tct.Node, {

    // Properties
    type: null,
    left: null,
    right: null,
    borderContainer: null,

    // Methods

    constructor : function(type, left, right, borderContainer) {
        this.type = type;
        this.left = left;
        this.right = right;
        this.borderContainer = borderContainer;
        left.setParent(this);
        right.setParent(this);
    },

    // Retrieve the left or right child by index 0 or 1 respectively.
    child : function(i) {
        return i === 0 ? this.left : this.right;
    },

    replaceChild : function(oldChild, newChild) {
        if (this.left === oldChild) this.left = newChild;
        else this.right = newChild;
        newChild.setParent(this);
    },

    getOtherChild : function(givenChild) {
        if (this.left === givenChild) {
            return this.right;
        } else if (this.right === givenChild) {
            return this.left;
        } else {
            return null;
        }
    },

    // A binary node is said to be "terminal" if both its children are leaves.
    isTerminal : function() {
        return this.left.type === tct.LEAFTYPE && this.right.type === tct.LEAFTYPE;
    },

    getLeftSizeFractions : function(fracs) {
        var bc = this.borderContainer,
            lc = bc.getChildren()[1],
            lcSize = this.type === tct.COLTYPE ? lc.w : lc.h,
            bcSize = this.type === tct.COLTYPE ? bc.w : bc.h,
            frac = lcSize / bcSize;
        fracs.push(frac);
        this.left.getLeftSizeFractions(fracs);
        this.right.getLeftSizeFractions(fracs);
    },

    setLeftSizeFractions : function(fracs) {
        var bc = this.borderContainer,
            lc = bc.getChildren()[1],
            frac = fracs.shift(),
            bcSize = this.type === tct.COLTYPE ? bc.w : bc.h,
            lcSize = frac * bcSize;
        bc._layoutChildren(lc.id, lcSize);
        this.left.setLeftSizeFractions(fracs);
        this.right.setLeftSizeFractions(fracs);
    },

    computeLeafOrder : function(order) {
        this.left.computeLeafOrder(order);
        this.right.computeLeafOrder(order);
    },

    computeTreeDescrip : function(desc) {
        var d = this.type === tct.COLTYPE ? "V" : "H";
        desc.push(d);
        this.left.computeTreeDescrip(desc);
        this.right.computeTreeDescrip(desc);
    },

    makeStructure : function(desc) {
        this.left.makeStructure(desc);
        this.right.makeStructure(desc);
    },

    writeMovementMenuItems : function(forLeaf, rcAddrArray, moveSubMenu, openSubMenu) {
        var givenMoveSubMenu = null,
            givenOpenSubMenu = null;
        if (rcAddrArray[rcAddrArray.length-1].type !== this.type) {
            // Add a new counter for this type.
            rcAddrArray.push( new tct.RcCounter(this.type, 1) );
            // Store the given menus.
            givenMoveSubMenu = moveSubMenu;
            givenOpenSubMenu = openSubMenu;
            // And make new ones.
            moveSubMenu = new Menu(),
            openSubMenu = new Menu();
        }
        // Recurse.
        this.left.writeMovementMenuItems(forLeaf, rcAddrArray, moveSubMenu, openSubMenu);
        rcAddrArray[rcAddrArray.length-1].inc();
        this.right.writeMovementMenuItems(forLeaf, rcAddrArray, moveSubMenu, openSubMenu);
        // If we made our own submenus, add PopupMenuItems to the given ones.
        if (givenMoveSubMenu !== null) {
            // First pop our new counter.
            rcAddrArray.pop();
            // And access the one before it.
            var counter = rcAddrArray[rcAddrArray.length-1];
            givenMoveSubMenu.addChild(new PopupMenuItem({
                label: counter.toString(),
                popup: moveSubMenu
            }));
            givenOpenSubMenu.addChild(new PopupMenuItem({
                label: counter.toString(),
                popup: openSubMenu
            }));
        }
    }

});

// -----------------------------------------------------------------------
// LeafNode class. Represents a TabContainer.

tct.LeafNode = declare(tct.Node, {

    // Properties

    type: tct.LEAFTYPE,
    tct: null,
    rootNode: null,
    socket: null,
    tc: null,
    tabController: null,
    menu: null,
    menuCloseItem: null,
    scrollStack: null,

    // Methods

    /**
     * Required:
     * tct: the manaaging TabContainerTree
     * socket: the LayoutContainer to which the TabContainer is to be added
     * tc: the TabContainer represented by this leaf
     * panes: (possibly empty) Array of ContentPanes to be added to the TabContainer
    */
    constructor : function(tct, socket, tc, panes) {
        // Store given data.
        this.tct = tct;
        this.socket = socket;
        this.tc = tc;
        // Get root node and menu.
        this.rootNode = this.tct.getRootNode();
        this.tabController = registry.byId(this.tc.id+"_tablist");
        this.menu = registry.byId(this.tc.id+"_tablist_Menu");
        var theLeaf = this;
        dojoOn(this.menu, 'open', function(e){
            theLeaf.tct.announceMenuOpening(theLeaf.menu, this);
        });
        // Initialize scroll stack.
        this.scrollStack = [];
        // Add the TC to the socket.
        this.socket.addChild(this.tc);
        // Add any panes to the TC.
        for (var i in panes) {
            var pane = panes[i];
            this.tc.addChild(pane);
        }
    },

    // Get the TabContainer represented by this LeafNode.
    getTC : function() {
        return this.tc;
    },

    getNumPanes : function() {
        return this.tc.getChildren().length;
    },

    // It's useful to be able to store the fraction, or percentage, that each
    // content pane is currently scrolled.
    pushScrollFractions : function() {
        const scrollFracs = {};
        const children = this.tc.getChildren();
        for (let i in children) {
            const c = children[i];
            let dn = c.domNode;
            // Scrolling in notes panes actually takes place inside a subelement
            // of class 'mainview' (which distinguishes it from the overview panel).
            // Question: Should we also try to record scroll fractions for overviews?
            const mv = dn.querySelector('.mainview');
            if (mv) {
                dn = mv;
            }
            const t = dn.scrollTop;
            const h = dn.scrollHeight;
            const p = t/h;
            //console.log(c.id, t, h, p);
            scrollFracs[c.id] = p;
        }
        this.scrollStack.push(scrollFracs);
    },

    // Restore scroll positions to the best of our ability. Note that if the width of
    // the tab container changes (as it will when we are adding or removing a vertical
    // split) then this method is highly imperfect. This is due to the reflowing of
    // paragraphs. I don't see much we can do about this.
    popScrollFractions : function() {
        const scrollFracs = this.scrollStack.pop();
        const children = this.tc.getChildren();
        for (let i in children) {
            const c = children[i];
            let dn = c.domNode;
            const mv = dn.querySelector('.mainview');
            if (mv) {
                dn = mv;
            }
            const h = dn.scrollHeight;
            const p = scrollFracs[c.id];
            if (p) {
                const t = p*h;
                //console.log(c.id, t, h, p);
                dn.scrollTop = t;
            }
        }
    },

    // Get the menu for this LeafNode's TabContainer.
    getMenu : function() {
        return this.menu;
    },

    getLeftSizeFractions : function(fracs) {},

    setLeftSizeFractions : function(fracs) {},

    computeLeafOrder : function(order) {
        order.push(this.tc.id);
    },

    computeTreeDescrip : function(desc) {
        desc.push("L");
    },

    makeStructure : function(desc) {
        var code = desc.shift();
        if (code === "L") {
            return;
        } else {
            this.openNewSplit(code.toLowerCase());
            this.parent.makeStructure(desc);
        }
    },

    splitAndCopyPane : function(pane, dim) {
        // Open a new split.
        var newTcId = this.openNewSplit(dim);
        // Populate the new TabContainer.
        this.tct.openCopyOfPane(pane, newTcId);
    },

    splitAndMovePane : function(pane, dim) {
        // Open a new split.
        var newTcId = this.openNewSplit(dim);
        // Populate the new TabContainer.
        this.tct.movePane(pane, newTcId);
    },

    /*
    * Open a new split.
    * param dim: 'v' or 'h', giving the desired orientation of the new splitter. Thus, 'v' puts the
    *      two splits side by side; 'h' puts one above the other.
    * return: The Id of the new (empty) TC formed by the split. This will always be the one on the
    *         right or bottom.
    */
    openNewSplit : function(dim) {
        // Build all the new layout widgets we'll need in order to add a new TabContainer.
        var bcDesign = dim === 'v' ? 'sidebar' : 'headline',
            primaryRegion = dim === 'v' ? 'left' : 'top',
            sharedDimension = dim === 'v' ? 'width' : 'height',
            newBorderContainer = new BorderContainer({
                design: bcDesign,
                region: "center",
                gutters: false
            }),
            newPrimarySocket = new LayoutContainer({
                region: primaryRegion,
                splitter: true,
                gutters: false
            }),
            newSecondarySocket = new LayoutContainer({region: "center", gutters: false}),
        // And make a new LeafNode, attached to one of the new sockets.
            newLeafNode = this.tct.makeNewLeafNode(newSecondarySocket);
        // Make the new primary socket take up half the space.
        domStyle.set(newPrimarySocket.domNode, sharedDimension, '50%');
        // Rearrange the widgets.
        newBorderContainer.addChild(newSecondarySocket);
        // Save scroll fractions (i.e. percentage each pane is scrolled).
        this.pushScrollFractions();
        // Remove and recombine.
        this.socket.removeChild(this.tc);
        newPrimarySocket.addChild(this.tc);
        newBorderContainer.addChild(newPrimarySocket);
        this.socket.addChild(newBorderContainer);
        // Restore scroll fractions.
        this.popScrollFractions();
        // Save the new primary socket.
        this.socket = newPrimarySocket;
        // Edit the tree structure, interposing the appropriate type of binary node.
        var parent = this.parent,
            nodeType = dim === 'v' ? tct.COLTYPE : tct.ROWTYPE,
            binaryNode = new tct.BinaryNode(nodeType, this, newLeafNode, newBorderContainer);
        parent.replaceChild(this, binaryNode);
        // Recompute all menus.
        this.tct.rebuildAllMenus();
        // Recompute order.
        this.tct.recomputeLeafOrder();
        // Announce the split.
        this.tct.announceNewSplit(newBorderContainer);
        // Return the Id of the new TC.
        return newLeafNode.tc.id
    },

    removeSelfFromTree : function() {
        //console.log('remove split!');
        // Cannot remove self from tree if parent is root.
        if (this.parent.type === tct.ROOTTYPE) return;
        // Rearrange the widgets.
        var borderContainer = this.socket.getParent();
        borderContainer.removeChild(this.socket);
        var otherSocket = borderContainer.getChildren()[0],
            otherContainer = otherSocket.getChildren()[0],
            upperSocket = borderContainer.getParent();
        upperSocket.removeChild(borderContainer);
        otherSocket.removeChild(otherContainer);
        upperSocket.addChild(otherContainer);
        // Edit the tree structure.
        var sibling = this.parent.getOtherChild(this),
            grandParent = this.parent.getParent();
        grandParent.replaceChild(this.parent, sibling);
        // If former sibling happens to be a leaf, update its socket.
        if (sibling.type === tct.LEAFTYPE) {
            sibling.socket = upperSocket;
        }
        // Recompute all menus.
        this.tct.rebuildAllMenus();
        // Recompute order.
        this.tct.recomputeLeafOrder();
        // Announce the removal of the split.
        this.tct.announceRemovedSplit(borderContainer);
    },

    // (Re)build the context menu for this leaf node.
    rebuildMenu : function() {

        // Remove children before destroying.
        // Don't know why, but if you destroy without first removing, then
        // get weird error the _first_ time you open a tab's context menu after splitting
        // on that tab.
        // Error is that variable `tn` is null at _CssStateMixin.js:196.
        // Top of stack trace is MenuItem.js:113.
        // It is weird because we get no such error e.g. in BuildViewManager, where we
        // do destroy without first removing, each time we rebuild the context menu.
        var ch = this.menu.getChildren();
        for (var i in ch) this.menu.removeChild(ch[i]);
        // Now can destroy all current items, to avoid a memory leak.
        this.menu.destroyDescendants();

        // Give registered menu builders a chance to build items.
        this.tct.invokeMenuBuilders(this.menu);
        // Add options to copy to a new split.
        var theLeaf = this;
        this.menu.addChild(new MenuItem({
            label: "Split Vertically",
            onClick: function(){
                var button = registry.byNode(this.getParent().currentTarget);
                    pane = button.page;
                theLeaf.splitAndCopyPane(pane, 'v');
            }
        }));
        this.menu.addChild(new MenuItem({
            label: "Split Horizontally",
            onClick: function(){
                var button = registry.byNode(this.getParent().currentTarget);
                    pane = button.page;
                theLeaf.splitAndCopyPane(pane, 'h');
            }
        }));
        // Add options to move to a new split, but enable only if the TC contains
        // at least one other tab.
        var numPanes = this.getNumPanes();
        this.menu.addChild(new MenuItem({
            label: "Split and Move Right",
            onClick: function(){
                var button = registry.byNode(this.getParent().currentTarget);
                    pane = button.page;
                theLeaf.splitAndMovePane(pane, 'v');
            },
            disabled: numPanes < 2
        }));
        this.menu.addChild(new MenuItem({
            label: "Split and Move Down",
            onClick: function(){
                var button = registry.byNode(this.getParent().currentTarget);
                    pane = button.page;
                theLeaf.splitAndMovePane(pane, 'h');
            },
            disabled: numPanes < 2
        }));
        // Add items for moving to other existing splits, if any.
        var mmi = this.rootNode.writeMovementMenuItems(this);
        if (mmi.length > 0) {
            this.menu.addChild(new MenuSeparator());
            for (var i in mmi) this.menu.addChild(mmi[i]);
        }
        // `Close` option
        this.menu.addChild(new MenuSeparator());
        this.menu.addChild(new MenuItem({
            label: "Close",
            onClick: function(){
                var button = registry.byNode(this.getParent().currentTarget);
                    pane = button.page;
                theLeaf.closePane(pane);
            }
        }));
    },

    writeMovementMenuItems : function(forLeaf, rcAddrArray, moveSubMenu, openSubMenu) {
        var counter = rcAddrArray[rcAddrArray.length-1],
            theManager = this.tct,
            theNewTcId = this.tc.id;
        moveSubMenu.addChild(new MenuItem({
            label: counter.toString(),
            onClick: function(){
                var button = registry.byNode(forLeaf.getMenu().currentTarget);
                    pane = button.page;
                theManager.movePane(pane, theNewTcId);
            },
            disabled: forLeaf === this
        }));
        openSubMenu.addChild(new MenuItem({
            label: counter.toString(),
            onClick: function(){
                var button = registry.byNode(forLeaf.getMenu().currentTarget);
                    pane = button.page;
                theManager.openCopyOfPane(pane, theNewTcId);
            },
            disabled: forLeaf === this
        }));
    },

    closePane : function(pane) {
        this.tabController.onCloseButtonClick(pane);
    },

    closePaneByIndex : function(i) {
        var chn = this.tc.getChildren();
        var pane = chn[i];
        this.closePane(pane);
    },

    closeAllPanes : function() {
        var chn = this.tc.getChildren();
        for (var i in chn) {
            var pane = chn[i];
            this.closePane(pane);
        }
    },

});


// -----------------------------------------------------------------------
// TabContainerTree class

tct.TabContainerTree = declare(null, {

    // Properties

    // Position for tabs in all TabContainers:
    tabPosition: "top",
    // The LayoutContainer to which this will be added:
    socket: null,
    // Function to call when opening copy of existing ContentPane:
    openCopy: null,

    // Counter for Ids of TabContainers:
    tcIdCounter: 0,
    // Counter for Ids of ContentPanes:
    cpIdCounter: 0,
    // Counter for selection sequence:
    selectionCounter: 0,
    // Our Id
    id: null,
    // A place to store LeafNodes under the Id of the TabContainer they manage:
    leavesByTCIds: null,
    // A place to store a listing of TC Ids in the natural tree traversal order:
    tcIdOrder: null,
    // The RootNode at the base of the tree of TabContainers:
    rootNode: null,
    // The "active" or most recently used TC:
    activeTC: null,
    // Registry for active pane listeners
    activePaneListeners: null,
    // Registry for closing pane listeners
    closingPaneListeners: null,
    // Registry for split listeners
    splitListeners: null,
    // Registry for menu builders
    menuBuilders: null,
    // Registry for menu open listeners
    menuOpenListeners: null,
    // Drag-n-drop controller
    drake: null,

    // Methods

    // -----------------------------------------------------------------------
    // User API

    /**
     * Required:
     *      layoutContainer: A dijit/layout/LayoutContainer, where the
     *                       TabContainerTree should live.
     * Optional:
     *      openCopy: Function to call when it's time to open a copy of an existing ContentPane.
     *                If omitted, then you can only move tabs, not open them in other containers.
     *                If provided, should be a function that accepts two ContentPanes: the old one, and
     *                  the new one (in that order). Doesn't need to return anything. Just takes
     *                  responsibility for adding content to the new CP.
     *      tabPosition: "top", "bottom", "left" or "right"
     */
    constructor : function(layoutContainer, args) {
        this.socket = layoutContainer
        declare.safeMixin(this, args);
        // Set our id.
        this.id = this.socket.id + "_tct";
        // Set up LeafNode storage.
        this.leavesByTCIds = {};
        // Set up listener storage.
        this.emptyBoardListeners = [];
        this.activePaneListeners = [];
        this.closingPaneListeners = [];
        this.splitListeners = [];
        this.menuBuilders = [];
        this.menuOpenListeners = [];
        // Set up the root for the tree of TCs.
        this.rootNode = new tct.RootNode(this);

        // Start with an initial TC.
        var initialTC = this.makeNewTC();
        // Build a leaf node for it.
        var initialLeaf = new tct.LeafNode(this, this.socket, initialTC, []);
        // Store the leaf.
        this.leavesByTCIds[initialTC.id] = initialLeaf;
        // Set it as the active TC.
        this.setActiveTc(initialTC);
        // Set it as child of the root node.
        this.rootNode.setChild(initialLeaf);
        // Compute the ordering (trivial now, since only one leaf).
        this.recomputeLeafOrder();
        // Rebuild the menu.
        initialLeaf.rebuildMenu();
        // Set up drag-n-drop to rearrange tabs within a single tab container.
        this.drake = dragula({
            isContainer: function (el) {
                return el.classList.contains('dijitTabContainerTop-tabs');
            },
            accepts: function (el, target, source, sibling) {
                return target === source;
            },
        });
        this.drake.on('drop', this.onTabDrop.bind(this));
    },

    /* When tabs are re-ordered by drag-and-drop, we have to get the
     * TabContainer to actually rearrange the tabs internally. (Otherwise,
     * e.g., when storing the state, we'll store them in their original
     * order, instead of the updated one.)
     */
    onTabDrop : function(el, target, source, sibling) {
        const button = registry.byNode(el);
        const page = button.page;
        const tc = page.getParent();
        const selectedBeforeDrag = tc.selectedChildWidget;
        const leaf = this.leavesByTCIds[tc.id];

        // Determine the index at which the tab needs to be inserted.
        // -1 means at the right-hand end.
        let i = -1;
        if (sibling) {
            let child = sibling;
            while ( (child = child.previousSibling) ) {
                i++;
            }
        }

        // Be sure to push/pop scroll fractions before/after removing/adding.
        leaf.pushScrollFractions();
        tc.removeChild(page);
        if (i < 0) {
            tc.addChild(page);
        } else {
            tc.addChild(page, i);
        }
        leaf.popScrollFractions();

        // Maintain the selection from before drag.
        if (selectedBeforeDrag) {
            this.selectPane(selectedBeforeDrag);
        }
    },

    /* Get an array of the IDs of the TCs, in the natural tree traversal order.
     */
    getTcIds : function() {
        return this.tcIdOrder.slice();
    },

    closeAllPanes : function() {
        for (var id in this.leavesByTCIds) {
            var leaf = this.leavesByTCIds[id];
            leaf.closeAllPanes();
        }
    },

    pushAllScrollFractions : function() {
        for (let id in this.leavesByTCIds) {
            const leaf = this.leavesByTCIds[id];
            leaf.pushScrollFractions();
        }
    },

    popAllScrollFractions : function() {
        for (let id in this.leavesByTCIds) {
            const leaf = this.leavesByTCIds[id];
            leaf.popScrollFractions();
        }
    },

    getTabButtonForPane : function(pane) {
        const tc = pane.getParent();
        const leaf = this.leavesByTCIds[tc.id];
        const controller = leaf.tabController;
        return controller.pane2button(pane.id);
    },

    /* Compute an array of fractions indicating, for each binary node, what
     * fraction of its size is occupied by the primary region (left for vertical
     * splits, top for horizontal splits). The fractions are reported in the
     * natural order of tree traversal.
     */
    getLeftSizeFractions : function() {
        return this.rootNode.getLeftSizeFractions();
    },

    /* Pass an array of fractions of the kind returned by the `getLeftSizeFractions`
     * method, in order to set the fractions to desired values.
     */
    setLeftSizeFractions : function(fracs) {
        this.rootNode.setLeftSizeFractions(fracs);
    },

    /* Computes a description of the current tree structure, in the form of
     * an array of "V", "H", and "L" chars. These describe the splits and
     * leaf nodes in Polish notation.
     */
    computeTreeDescrip : function() {
        return this.rootNode.computeTreeDescrip();
    },

    /* Pass a structure description of the form returned by the `computeTreeDescrip` method.
     * We make that structure, introducing new splits as necessary.
     *
     * param: desc  Either an array of "V", "H", and "L" characters, or a string
     *              made up of these characters.
     */
    makeStructure : function(desc) {
        if (typeof(desc) === "string") desc = desc.split("");
        this.rootNode.makeStructure(desc);
    },

    // Make a new content pane, add it to a given TabContainer, and return
    // the new content pane to the caller (so they can add content, set title, etc.).
    //
    // param: tc  The TabContainer to which to add. You may pass either a TabContainer
    //            object itself, OR the Id of an existing one.
    // param: cp  Optional ContentPane. If not supplied, we make one.
    addContentPaneToTC : function(tc, cp) {
        // Did we get a TC itself, or an Id?
        if (typeof tc === "string") {
            // We got (what should be) an Id.
            // So attempt to retrieve the TC itself.
            tc = this.getTC(tc);
        }
        // If no ContentPane was given, then make a new one.
        if (cp === undefined) cp = this.makeNewCP();
        tc.addChild(cp);
        // Make the newly added pane the selected pane.
        tc.selectChild(cp);
        // Make this container the active one.
        this.setActiveTc(tc);
        // Recompute the context menu for this TC.
        var leaf = this.leavesByTCIds[tc.id];
        leaf.rebuildMenu();
        return cp;
    },

    // Convenience method to add a new ContentPane to the active TabContainer.
    //
    // param: cp  Optional ContentPane. If not supplied, we make one.
    addContentPaneToActiveTC : function(cp) {
        return this.addContentPaneToTC(this.activeTC, cp);
    },

    // Split a given TabContainer, in a desired dimension.
    //
    // param: tcId  The Id of the TC to be split.
    // param: dim  'v' or 'h', for vertical or horizontal split.
    // return: The Id of the new (empty) TC formed by the split. This will always be the one on the
    //         right or bottom.
    splitTC : function(tcId, dim) {
        var leaf = this.leavesByTCIds[tcId];
        return leaf.openNewSplit(dim);
    },

    setActiveTcById : function(tcId) {
        var leaf = this.leavesByTCIds[tcId]
            tc = leaf.getTC();
        this.setActiveTc(tc);
    },

    setActiveTcByPane : function(pane) {
        let tc = pane.getParent();
        this.setActiveTc(tc);
    },

    setActiveTc : function(tc) {
        // First check if this TC still exists.
        // This is in order to catch a funny case that arises when we close a split.
        // In that case, first we properly set another TC as the active one; but then afterward
        // our onclick handler for the closed TC tries to set the closed one as active.
        if (!(tc.id in this.leavesByTCIds)) return;

        // Does this TC have a selected pane?
        var pane = tc.selectedChildWidget;
        if (pane) {
            // Advance the selected pane's selection sequence number.
            // This is an integer we stash directly in the ContentPane,
            // under the property, `_pfsc_ise_selectionSequenceNumber`.
            // It is useful in determining which pane has been most recently
            // selected.
            var n = this.selectionCounter;
            this.selectionCounter = n + 1;
            pane._pfsc_ise_selectionSequenceNumber = n;
            //console.log(pane.id, n);
        }

        // Next check if this is actually different from the currently active TC.
        // If not then there is nothing more to do.
        if (tc === this.activeTC) return;

        // Remove active status from old one.
        if (this.activeTC !== null) {
            domClass.remove(this.activeTC.domNode, "activeTC");
        }
        // Set new one as active.
        this.activeTC = tc;
        domClass.add(tc.domNode, "activeTC");
        // If there is a selection, make an announcement.
        var sel = this.activeTC.selectedChildWidget;
        if (sel !== undefined) this.announceActivePane(sel);
    },

    /* Say whether a given TabContainer is the active one.
     */
    tcIsActive : function(tc) {
        return tc === this.activeTC;
    },

    /* Attempt to determine which is the active pane.
     * If found, return it; else return undefined.
     */
    getActivePane : function() {
        var cp = undefined;
        if (this.activeTC !== null) cp = this.activeTC.selectedChildWidget;
        return cp;
    },

    /* Make a pane the selected one in its tab container.
     * Optionally, make that container the active one as well.
     *
     * param pane: The pane to be selected.
     * param makeActive: boolean; true iff you want the pane's TC to be
     *   made the active one
     */
    selectPane : function(pane, makeActive) {
        var tc = pane.getParent();
        if (tc) {
            tc.selectChild(pane);
            if (makeActive) this.setActiveTc(tc);
        } else {
            console.log('pane has no parent: ', pane.id);
        }
    },

    /* Register an object to receive notification when the board becomes empty, i.e. when
     * the very last pane is closed.
     * Listeners must publish a `noteEmptyBoard` method, which accepts no arguments.
     */
    registerEmptyBoardListener : function(listener) {
        this.emptyBoardListeners.push(listener);
    },

    /* Register an object to receive notification when the active pane is updated.
     * Listeners must publish a `noteActivePane` method, which accepts one argument, being
     * the active pane.
     */
    registerActivePaneListener : function(listener) {
        this.activePaneListeners.push(listener);
    },

    /* Register an object to receive notification when a pane is about to be closed.
     * Listeners must publish a `noteClosingPane` method, which accepts one argument, being
     * the pane that is about to close.
     */
    registerClosingPaneListener : function(listener) {
        this.closingPaneListeners.push(listener);
    },

    /* Register an object to receive notification when a split is introduced or removed.
     * Listeners must publish `noteNewSplit` and `noteRemovedSplit` methods, each of which
     * accepts one argument, being the BorderContainer that is being added or removed.
     */
     registerSplitListener : function(listener) {
        this.splitListeners.push(listener);
     },

     /* Register an object to participate in (re)building context menus for tab containers.
      * Builders must publish a `buildTabContainerMenu` method, which accepts one argument,
      * being the Dojo Menu instance that is being built.
      */
     registerMenuBuilder : function(builder) {
        this.menuBuilders.push(builder);
     },

     /* Register an object to receive notification when a tab container context menu has
      * opened. Listeners must publish a `noteTabContainerMenuOpened` method, which accepts
      * two arguments, being the menu instance, and the object that was clicked.
      */
     registerMenuOpenListener : function(listener) {
        this.menuOpenListeners.push(listener);
     },

    // -----------------------------------------------------------------------
    // Internals

    announceEmptyBoard : function() {
        for (var i in this.emptyBoardListeners) {
            var listener = this.emptyBoardListeners[i];
            listener.noteEmptyBoard();
        }
    },

    announceActivePane : function(cp) {
        //console.log("Active pane:");
        //console.log(cp);
        // If no content pane was named, try to determine which is the active one.
        if (cp === undefined) {
            cp = this.getActivePane();
        }
        // If it didn't work, give up.
        if (cp === undefined) return;
        // Otherwise, proceed.
        for (var i in this.activePaneListeners) {
            var listener = this.activePaneListeners[i];
            listener.noteActivePane(cp);
        }
    },

    announceClosingPane : function(cp) {
        for (var i in this.closingPaneListeners) {
            var listener = this.closingPaneListeners[i];
            listener.noteClosingPane(cp);
        }
    },

    announceNewSplit : function(bc) {
        for (var i in this.splitListeners) {
            var listener = this.splitListeners[i];
            listener.noteNewSplit(bc);
        }
    },

    announceRemovedSplit : function(bc) {
        for (var i in this.splitListeners) {
            var listener = this.splitListeners[i];
            listener.noteRemovedSplit(bc);
        }
    },

    invokeMenuBuilders : function(menu) {
        for (var i in this.menuBuilders) {
            var builder = this.menuBuilders[i];
            builder.buildTabContainerMenu(menu);
        }
    },

    announceMenuOpening : function(menu, e) {
        for (var i in this.menuOpenListeners) {
            var listener = this.menuOpenListeners[i];
            listener.noteTabContainerMenuOpened(menu, e);
        }
    },

    getRootNode : function() {
        return this.rootNode;
    },

    rebuildAllMenus : function() {
        for (var id in this.leavesByTCIds) {
            var leafNode = this.leavesByTCIds[id];
            leafNode.rebuildMenu();
        }
    },

    recomputeLeafOrder : function() {
        this.tcIdOrder = this.rootNode.computeLeafOrder();
    },

    /*
    * Get the "next" TabContainer Id in the natural ordering.
    * id: the id of the given TabContainer.
    * retro: boolean describing special case of return value. See below.
    * return:
    *   If the given id is not found, return undefined.
    *   If there are no other TabContainers besides the given one, return null.
    *   If the given TC Id is the last one, then:
    *       if retro is true then return the previous one, otherwise return very first TC Id.
    *   Otherwise, just return the next one, as expected.
    */
    getNextTcId : function(id, retro) {
        var order = this.tcIdOrder;
        var i0 = order.findIndex(function(elt) {
            return elt === id;
        });
        if (i0 === -1) return undefined;
        var n = order.length;
        if (n === 1) return null;
        if (i0 === n - 1) return retro ? order[n - 2] : order[0];
        return order[i0 + 1];
    },

    /*
     * Get the "previous" TabContainer Id in the natural ordering.
     * Works like the `getNextTcId` method, only reversed.
     */
    getPrevTcId : function(id, retro) {
        const order = this.tcIdOrder;
        const i0 = order.findIndex(elt => (elt === id));
        if (i0 === -1) return undefined;
        const n = order.length;
        if (n === 1) return null;
        if (i0 === 0) return retro ? order[1] : order[n - 1];
        return order[i0 - 1];
    },

    makeNewLeafNode : function(socket) {
        var newTC = this.makeNewTC(),
            newLeafNode = new tct.LeafNode(this, socket, newTC, []);
        this.leavesByTCIds[newTC.id] = newLeafNode;
        return newLeafNode;
    },

    // Make a new TabContainer.
    makeNewTC : function() {
        var theTCT = this;
        var newTC = new TabContainer({
            region: "center",
            id: this.takeNextTCId(),
            tabPosition: this.tabPosition,
            //"class": "centerPanel"
            onClick: function() {
                theTCT.setActiveTc(this);
            },
            /*
            * If the tab container needs to receive keystrokes, they can be handled
            * here. For now we have moved all this to the global KeyListener class.
            onKeyUp: function(event) {
            }
            */
        });
        // We can be notified any time a tab becomes the selected one in its container.
        // (Regarding use of dojo topic and lang here, we have simply immitated the code
        // in dijit/layout/StackController.js, where it subscribes to the -selectChild event.)
        dojoTopic.subscribe(newTC.id + "-selectChild", dojoLang.hitch(this, "onSelectPane"));
        return newTC;
    },

    /* Respond to the event that a tab has become the selected child in its tab container.
     *
     * Note 1: This event is triggered only if the tab was previously _not_ selected, and
     * has just now become selected. It is therefore _not_ triggered if you merely click on
     * a tab that is already selected. To respond in such a case you can instead add code to
     * the onClick handler defined in the `makeNewTC` method above.
     *
     * Note 2: We _also_ define an onShow handler for every ContentPane, which will call the TCT's
     * `showContentPane` method any time a pane is shown. So that is another way to respond.
     */
    onSelectPane : function(pane) {
        // At one point we experimented with doing something here, but for now we actually
        // have no use for this. We leave it here in case it is useful for future development.
    },

    /* This is a "staticmethod"; i.e. it needn't be a member of the TCT class; it is
     * just defined here for convenience, and because it deals with TCT-related stuff
     * (namely, the _pfsc_ise_selectionSequenceNumber attribute of ContentPanes).
     *
     * :param panes: any object in which the _values_ are ContentPanes. So could be
     *   a lookup by pane id, or could just be an array of panes.
     * :return: the pane which has been most recently active, as judged by
     *   its _pfsc_ise_selectionSequenceNumber attribute. (But if panes is empty,
     *   then return null.)
     */
    findMostRecentlyActivePane : function(panes) {
        var mostRecentPane = null,
            maxSeqNum = -1;
        for (var k in panes) {
            var pane = panes[k],
                seqNum = pane._pfsc_ise_selectionSequenceNumber;
            if (seqNum > maxSeqNum) {
                maxSeqNum = seqNum;
                mostRecentPane = pane;
            }
        }
        return mostRecentPane;
    },

    // Take the next available sequential Id for a new TabContainer.
    takeNextTCId : function() {
        var n = this.tcIdCounter;
        this.tcIdCounter = n + 1;
        var id = this.id + '_tc_' + n;
        return id;
    },

    // Make a new ContentPane.
    makeNewCP : function() {
        const newCP = new ContentPane({
            region: "center",
            id: this.takeNextCPId(),
            closable: true,
            // https://developer.mozilla.org/en-US/docs/Web/Accessibility/Keyboard-navigable_JavaScript_widgets
            tabindex: -1 // make focusable by script or mouse click
        });
        const theManager = this;
        newCP.onClose = function(){
            theManager.announceClosingPane(this);
            theManager.closeContentPane(this);
        };
        newCP.onShow = function(){
            theManager.showContentPane(this);
        };
        return newCP;
    },

    // Take the next available sequential Id for a new ContentPane.
    takeNextCPId : function() {
        var n = this.cpIdCounter;
        this.cpIdCounter = n + 1;
        var id = this.id + '_cp_' + n;
        return id;
    },

    // Handle the 'show' event for a content pane.
    showContentPane : function(contentPane) {
        //console.log('show');
        //console.log(contentPane);
        // Is the pane that has just been shown in the active TC?
        var tabContainer = contentPane.getParent();
        if (tabContainer === this.activeTC) {
            // If so then announce a new active pane.
            this.announceActivePane(contentPane);
        }
    },

    // Handle the 'close' event for a content pane.
    closeContentPane : function(contentPane) {
        //console.log('close tab!');
        var tabContainer = contentPane.getParent(),
            leafNode = this.leavesByTCIds[tabContainer.id],
            parentNode = leafNode.getParent(),
            numPanesBeforeClose = tabContainer.getChildren().length;
        // Remove the page being closed.
        tabContainer.removeChild(contentPane);
        // If this was the last pane, and if this leaf is _not_ just below the root,
        // then remove the split.
        if (numPanesBeforeClose === 1 && parentNode !== this.rootNode) {
            // First update the active TC, if necessary.
            if (tabContainer.id === this.activeTC.id) {
                var nextId = this.getNextTcId(tabContainer.id);
                console.assert(nextId !== undefined && nextId !== null, "missing next Id");
                this.setActiveTc(this.getTC(nextId));
            }
            // Remove the leaf node from our own records.
            delete this.leavesByTCIds[leafNode.getTC().id];
            // Ask the leaf node to remove itself from the tree.
            this.pushAllScrollFractions();
            leafNode.removeSelfFromTree();
            this.popAllScrollFractions();
        }
        // If this was the last pane, and this leaf _is_ just below the root,
        // then there are _no_ panes left anywhere.
        else if (numPanesBeforeClose === 1) {
            this.announceEmptyBoard();
        }
        // Otherwise ask the corresponding leaf node to recompute its context menus.
        else {
            leafNode.rebuildMenu();
        }
    },

    // Convenience function to look up a TabContainer by its Id.
    getTC : function(tcId) {
        var leafNode = this.leavesByTCIds[tcId];
        console.assert(leafNode !== undefined, "No leaf under id: " + tcId);
        return leafNode.getTC();
    },

    /**
     * Say whether we are able to open copies of tabs, which is the same as
     * asking whether the client supplied an `openCopy` function.
    */
    canOpenCopy : function() {
        return this.openCopy !== null;
    },

    /**
     * Move a given ContentPane (`pane`) to an existing
     * TabContainer specified by its Id (`newTcId`).
    */
    movePane : function(pane, newTcId) {
        this.closeContentPane(pane);
        var newTc = this.getTC(newTcId);
        this.addContentPaneToTC(newTc, pane);
    },

    /**
     * If possible, open a copy of a given ContentPane (`pane`) in an existing
     * TabContainer specified by its Id (`newTcId`).
    */
    openCopyOfPane : function(pane, newTcId) {
        if (this.canOpenCopy()) {
            // Grab the TabContainer to which the copy is to be added.
            var newTc = this.getTC(newTcId),
            // Make a new, empty ContentPane, and add it to the desired TC.
            newPane = this.addContentPaneToTC(newTc);
            // Pass the old and new CPs to the client-supplied openCopy function,
            // so that the client can take care of copying the content.
            this.openCopy(pane, newPane);
        } else {
            // We don't have a way of opening a copy, so move instead.
            this.movePane(pane, newTcId);
        }
    }

});

// -----------------------------------------------------------------------
// The module defines the TabContainerTree class.
return tct.TabContainerTree;

});
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

import { util as iseUtil } from "../util";

define([
    "dojo/_base/declare",
    "dojo/on",
    "dojo/dom-construct",
    "dijit/layout/ContentPane",
    "dijit/Dialog",
    "dijit/layout/TabContainer",
    "dijit/Menu",
    "dijit/MenuItem",
    "dijit/PopupMenuItem"
], function(
    declare,
    dojoOn,
    domConstruct,
    ContentPane,
    Dialog,
    TabContainer,
    Menu,
    MenuItem,
    PopupMenuItem
) {

const StudyManager = declare(null, {

    // Properties

    hub: null,
    showgoals: true,

    notesDialog: null,
    notesTab: null,
    editTab: null,
    editarea: null,
    editId: null,
    browserStorage: null,

    // Lookup mapping goalId to array of box elements representing widgets for that goal:
    boxElementsByGoalId: null,

    listeners: null,

    goalKeyPrefix: "pfsc:study:goal:",
    browserRecordingOptionKeyPrefix: "pfsc:study:recordNotesInBrowser:",

    // Methods

    constructor: function() {
        this.buildNotesDialog();
        this.boxElementsByGoalId = new Map();
        this.listeners = {};
        this.usePersistentBrowserStorage(false);
    },

    userBrowserRecordingOptionKey: function() {
        const username = this.hub.getUsername() || '';
        return `${this.browserRecordingOptionKeyPrefix}${username}:`;
    },

    checkBrowserRecordingOption: function() {
        return !!window.localStorage.getItem(this.userBrowserRecordingOptionKey());
    },
    
    setBrowserRecordingOption: function(doRecord) {
        const k = this.userBrowserRecordingOptionKey();
        if (doRecord) {
            window.localStorage.setItem(k, 'on');
        } else {
            window.localStorage.removeItem(k);
        }
    },

    updateBrowserStorageForUser: function() {
        const doUse = this.checkBrowserRecordingOption();
        this.usePersistentBrowserStorage(doUse);
    },

    usePersistentBrowserStorage: function(doUse) {
        this.browserStorage = doUse ? window.localStorage : window.sessionStorage;
    },

    updateForUser: function() {
        this.updateBrowserStorageForUser();
        this.refreshAllBoxElements();
    },

    buildNotesDialog: function() {
        const dlg = new Dialog({
            title: "",
            class: "pfsc-ise",
            onHide: this.onNotesDialogHide.bind(this)
        });
        const tc = new TabContainer({
            region: "center",
            tabPosition: "top",
            style: "width: 650px; height: 300px;"
        });
        const notesTab = new ContentPane({
            region: "center",
            title: "Notes",
            closable: false,
            onShow: this.onNotesTabShow.bind(this)
        });
        const editTab = new ContentPane({
            region: "center",
            content: "<textarea></textarea>",
            title: "Edit",
            closable: false
        });
        tc.addChild(notesTab);
        tc.addChild(editTab);
        dlg.addChild(tc);
        this.notesDialog = dlg;
        this.notesTab = notesTab;
        this.editTab = editTab;
        this.editarea = editTab.domNode.querySelector('textarea');
        iseUtil.noCorrect(this.editarea);
        this.notesTab.domNode.classList.add('studyNotesTab');
    },

    /* Say whether we're currently in "server-side note recording" mode.
     */
    inSsnrMode: function() {
        const info = this.hub.userInfo;
        return this.hub.ssnrAvailable && this.hub.isLoggedIn() && info.props.NOTES_STORAGE === "BROWSER_AND_SERVER";
    },

    // -----------------------------------------------------------------------
    // Handle toggle events from other windows (or the same window)

    activate: function() {
        this.hub.windowManager.on('goalBoxToggle', this.handleGoalBoxToggleEvent.bind(this));
    },

    handleGoalBoxToggleEvent: function(event) {
        const goalId = event.goalId;
        const checked = event.checked;
        const boxes = this.getAllBoxElements(goalId);
        for (let box of boxes) {
            if (checked) {
                box.classList.add('checked');
            } else {
                box.classList.remove('checked');
            }
        }
    },

    // -----------------------------------------------------------------------
    // Maintain and access goalbox lookup

    recordNewBoxElement: function(boxElt, goalId) {
        /* Note: It's important that we _not_ call `this.auditBoxElements(goalId)` here
         * (which at one time we tried), as it leads to a subtle bug. Suppose you open a
         * Thm and its Pf simultaneously. Before any new goal boxes get added to the document,
         * all will be recorded here. In particular, goalIds belonging to the Thm will be
         * recorded twice: once for their real node, and once for the ghost node from the Pf.
         * All of that is fine. However, if you audit each time you record, then the second
         * one causes the first to be audited away (since it's not in the document yet).
         *
         * Overall, this auditing system is imperfect. We're kind of relying on calls
         * to `this.getAllBoxElements()` to prevent memory leaks.
         * Better might be to actively audit whenever a notes or chart pane closes.
         */
        // Now add the new element, starting a new array if none exists yet.
        const currentList = this.boxElementsByGoalId.get(goalId) || [];
        currentList.push(boxElt);
        this.boxElementsByGoalId.set(goalId, currentList);
    },

    /* Get all registered box elements for a given goalId.
     */
    getAllBoxElements: function(goalId) {
        // Must clean house first.
        this.auditBoxElements(goalId);
        return (this.boxElementsByGoalId.get(goalId) || []).slice();
    },

    /* This is a way to get the "companion" elements to a given one.
     * In other words, we return an array of all box elements we have recorded
     * under the given goalId, _except for_ the one you pass.
     */
    getOtherBoxElements: function(boxElt, goalId) {
        const currentList = this.getAllBoxElements(goalId);
        return currentList.filter(elt => elt !== boxElt);
    },

    /* This is a house-keeping operation. For a given goalId, we check our
     * current record of box elements representing that goal. For each element,
     * we check whether it is still present or not. If not, we clear our record
     * of it.
     *
     * The idea is that this should be a preferable (and less error-prone!) system
     * than requiring that all goal boxes deregister themselves at any time that
     * they are made to disappear.
     */
    auditBoxElements: function(goalId) {
        const currentList = this.boxElementsByGoalId.get(goalId);
        if (!currentList) return;
        const newList = currentList.filter(elt => document.body.contains(elt));
        if (newList.length) {
            this.boxElementsByGoalId.set(goalId, newList);
        } else {
            this.boxElementsByGoalId.delete(goalId);
        }
    },

    /* Refresh the checked state of all existing checkboxes.
     *
     * This is useful e.g. when the user logs in or out.
     */
    refreshAllBoxElements: async function() {
        const goalIds = Array.from(this.boxElementsByGoalId.keys());

        if (this.inSsnrMode()) {
            const resp = await this.hub.xhrFor('loadNotes', {
                method: "POST",
                form: {
                    goal_ids: goalIds.join(','),
                },
                handleAs: 'json',
            });
            const goalInfo = resp.goal_info;
            if (goalInfo) {
                for (const goalId of goalIds) {
                    const info = goalInfo[goalId];
                    if (info) {
                        this.writeGoal(goalId, info);
                    } else {
                        this.removeGoal(goalId);
                    }
                }
            }
        }

        this.refreshBoxElementsFromStorage(goalIds);
    },

    refreshBoxElementsFromStorage: function(goalIds) {
        const wm = this.hub.windowManager;
        for (const goalId of goalIds) {
            const checked = this.getGoalData(goalId).checked;
            wm.groupcastEvent({
                type: 'goalBoxToggle',
                goalId: goalId,
                checked: checked,
            }, {
                includeSelf: true,
            });
        }
    },

    // -----------------------------------------------------------------------
    // Operate the notes dialog

    showTab: function(tab) {
        tab.getParent().selectChild(tab);
    },

    onNotesTabShow: function() {
        this.renderNotes();
    },

    renderNotes: function() {
        // FIXME: Maybe better to render MD on the client side?
        return this.hub.socketManager.emit('markdown', {
            md: this.editarea.value,
        }).then(msg => {
            this.notesTab.set('content', msg.html);
            iseUtil.typeset([this.notesTab.domNode]);
        }).catch(reason => {
            const msg = JSON.parse(reason.message);
            this.hub.errAlert2(msg);
        });
    },

    showNotesDialog: function(goalId, homepath) {
        //console.log('show notes dialog', goalId);
        const data = this.getGoalData(goalId),
            notes = data.notes || '',
            n = notes.length;
        this.editarea.value = notes;
        this.editId = goalId;
        this.notesTab.set('content', '');
        if (n > 0) {
            this.renderNotes();
            this.showTab(this.notesTab);
        } else {
            this.showTab(this.editTab);
        }
        const title = `Goal: ${homepath}`;
        this.notesDialog.set('title', title);
        this.notesDialog.show();
    },

    onNotesDialogHide: function() {
        //console.log('hid notes dialog');
        const notes = this.editarea.value,
            goalId = this.editId;
        const data = this.getGoalData(goalId);
        data.notes = notes;
        this.setGoalData(goalId, data);
    },

    // -----------------------------------------------------------------------
    // Operate checkboxes

    noteCheckboxToggle: function(goalId, isChecked) {
        //console.log('goal toggle', goalId, isChecked);
        const data = this.getGoalData(goalId);
        data.checked = isChecked;
        this.setGoalData(goalId, data);
    },

    isChecked: function(goalId) {
        const info = this.readGoal(goalId);
        return info === null ? false : info.checked;
    },

    setGoalBoxVisibility: function(b) {
        const body = document.querySelector('body'),
            name = 'goalBoxesHidden',
            isPresent = body.classList.contains(name);
        if (b === isPresent) body.classList.toggle(name);
        this.showgoals = b;
        // Setting the value of the CheckedMenuItem's checked property directly
        // does _not_ trigger its onChange handler, so we do not get an infinite
        // loop here. But we do need to do this, so that on app load we make the
        // menu item synced with the actual state of the goal boxes.
        this.hub.menuManager.studyOpt_goalsVisible.set('checked', b);
    },

    // -----------------------------------------------------------------------
    // Goalbox construction

    /* Add a goalbox to a DOM element.
     * Specifically, this method is used for goal widgets. See method
     * `addGoalboxForNode` below, for use with nodes in charts.
     *
     * param elt: the DOM element to which the goalbox is to be added
     * param goalId: the unique ID of the goal this box is to represent
     * param homepath: the libpath of the "home" where this goal box lives, the
     *   latter being a goal widget, a node, or a deduc.
     * param options: {
     *   addTs: boolean, default false: set true if you want a tail selector for
     *     the homepath in the context menu.
     *   studymgr: the object that will manage this goalbox. If
     *     undefined, we use this StudyManager itself.
     *   menu: an existing Dojo Menu to which this goal box's context menu options
     *     should be added. If undefined, we form a new Menu.
     * }
     *
     * return: object of the form {
     *   box: the newly constructed DOM element representing the goal box,
     *   menu: the context menu (Dojo Menu instance) attached to the box,
     * }
     */
    addGoalbox: function(elt, goalId, homepath, options) {
        let {
            addTs = false,
            studymgr = this,
            menu = null,
        } = options || {};
        if (!goalId) {
            console.error(`Goalbox construction requested with goalId: ${goalId}`);
            return;
        }

        const boxDoc = domConstruct.toDom(`
            <svg class="goalbox" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
                <rect x="7" y="14" width="24" height="24" stroke-width="3" class="checkbox"/>
                <text x="5" y="36" class="checkmark">&#x2713;</text>
            </svg>
        `);
        elt.appendChild(boxDoc);
        const boxElt = elt.querySelector('.goalbox');
        studymgr.recordNewBoxElement(boxElt, goalId);

        // Is this widget currently checked?
        if (studymgr.isChecked(goalId)) {
            boxElt.classList.add('checked');
        }

        const isWIP = goalId.endsWith("@WIP");

        // For left-clicks, we want to toggle the checkbox.
        dojoOn(boxElt, 'click', function(event){
            if (iseUtil.isRightClick(event)) return;

            const p = isWIP ?
                studymgr.showNotesAtWipChoice().then(d => d.accepted || !d.shown) :
                Promise.resolve(true);
            p.then(okay => {
                if (okay) {
                    const isChecked = boxElt.classList.toggle('checked');
                    // Propagate the checked state to companion boxes.
                    const others = studymgr.getOtherBoxElements(boxElt, goalId);
                    others.forEach(elt => elt.classList.toggle('checked'));
                    // Groupcast so any other windows can update accordingly.
                    const toggleEvent = {
                        type: 'goalBoxToggle',
                        goalId: goalId,
                        checked: isChecked,
                    };
                    studymgr.hub.windowManager.groupcastEvent(toggleEvent, {
                        includeSelf: false,
                    });
                    studymgr.dispatch(toggleEvent);
                    // Record the state.
                    studymgr.noteCheckboxToggle(goalId, isChecked);
                }
            });

            event.stopPropagation();
        });

        // For right-clicks, we want a context menu.
        if (!menu) {
            menu = new Menu({
                targetNodeIds: [boxElt]
            });
        }

        if (addTs) {
            // Add a tail selector for the libpath.
            const tsHome = domConstruct.create("div");
            iseUtil.addTailSelector(tsHome, homepath.split('.'));
            menu.addChild(new PopupMenuItem({
                label: 'Copy libpath',
                popup: new ContentPane({
                    class: 'popupCP',
                    content: tsHome
                })
            }));
        }

        // An option to copy the goal ID:
        menu.addChild(new PopupMenuItem({
            label: 'Copy goal ID',
            popup: new ContentPane({
                content: `${goalId}`,
                class: 'clickable popupCP',
                onClick: function(event) {
                    iseUtil.copyTextWithMessageFlashAtClick(goalId, event);
                }
            })
        }));

        // Notes access
        menu.addChild(new MenuItem({
            label: 'Notes',
            onClick: function() {
                const p = isWIP ?
                    studymgr.showNotesAtWipChoice().then(d => d.accepted || !d.shown) :
                    Promise.resolve(true);
                p.then(okay => {
                    if (okay) {
                        studymgr.showNotesDialog(goalId, homepath);
                    }
                });
            }
        }));

        return {
            box: boxElt,
            menu: menu,
        };
    },

    showNotesAtWipChoice: function() {
        return this.hub.choice({
            title: "Record notes @WIP?",
            content: `<div class="iseDialogContentsStyle01 iseDialogContentsStyle02"><p>
                Are you sure you want to record notes on goals in the WIP (work in progress)
                version of this repo? These goals are unstable, and your notes will be deleted
                the next time the repo is rebuilt. Do you want to record them anyway?
            </p></div>`,
            okButtonText: 'Yes, record notes.',
            dismissCode: 'recordNotesAtWIP',
        });
    },

    /* This is a variant of the `addGoalbox` method, for use with nodes in charts.
     */
    addGoalboxForNode: function(elt, goalId, deducpath, nodepath) {
        // This StudyManager class wants goalboxes on all nodes, regardless of
        // the deduction to which they belong, so we have no use for the `deducpath`
        // argument.
        // Meanwhile, a goalbox on a node should not have its own tailselector for
        // the nodepath, since the node already has one of these.
        return this.addGoalbox(elt, goalId, nodepath, {
            addTs: false,
        }).box;
    },

    // -----------------------------------------------------------------------
    // Mid-level read/write operations
    //
    // These methods are at a higher level than the writeGoal and readGoal
    // methods. The latter do literally what they say; these methods do something
    // more intricate.

    // Record goal info from the server only if we're in the right mode to accept that.
    recordGoalInfoFromServer: function(goalId, info) {
        if (this.inSsnrMode()) {
            // Info format on server is a little more general, in that it records a 'state'
            // instead of a 'checked' property. Eventually client side should catch up.
            // For now we convert to client side format.
            const data = {
                checked: info.state === 'checked',
                notes: info.notes,
            };
            this.writeGoal(goalId, data);
        }
    },

    // Store a record only if the goal is checked or we have notes on it.
    // Otherwise clear any existing record.
    // If in SSNR mode, first try to update server, and rollback changes if this fails.
    setGoalData: function(goalId, data) {
        if (this.inSsnrMode()) {
            this.hub.xhrFor('recordNotes', {
                method: "POST",
                form: {
                    goal_id: goalId,
                    state: data.checked ? 'checked' : 'unchecked',
                    // Be sure `notes` is always a string (not e.g. undefined, which will
                    // get converted to the string 'undefined' and then recorded in the GDB!).
                    notes: data.notes || '',
                },
                handleAs: 'json',
            }).then(resp => {
                if (resp.notes_successfully_recorded) {
                    this._setGoalData(goalId, data);
                } else {
                    // Don't want user to lose written notes, so log them to console
                    // and show them in err dialog as well.
                    const notes_str = JSON.stringify(data);
                    console.log('Could not record notes.');
                    console.log(goalId);
                    console.log(notes_str);
                    let msg = '<p>Could not record notes. Please try again later.</p>';
                    msg += '<p>You may want to copy your notes and save them elsewhere for now.</p>'
                    msg += '<p>They have also been logged to the browser console.</p>'
                    msg += '<p>Notes:</p>';
                    msg += `<p><pre>${goalId}</pre></p>`;
                    msg += `<p><pre>${notes_str}</pre></p>`;
                    this.hub.errAlert(msg);
                    // Rollback, to stay in sync with server.
                    this.refreshBoxElementsFromStorage([goalId]);
                }
            });
        } else {
            this._setGoalData(goalId, data);
        }
    },

    _setGoalData: function(goalId, data) {
        if (data.checked || data.notes) {
            this.writeGoal(goalId, data);
        } else {
            this.removeGoal(goalId);
        }
    },

    // Read existing data, or return a default data object if none yet exists.
    getGoalData: function(goalId) {
        let data = this.readGoal(goalId);
        if (data === null) {
            data = {
                checked: false,
                notes: ""
            };
        }
        return data;
    },

    // -----------------------------------------------------------------------
    // Low-level read/write operations

    userGoalKeyPrefix: function() {
        const username = this.hub.getUsername() || '';
        return `${this.goalKeyPrefix}${username}:`;
    },

    /* Record info for a goal, in this.browserStorage.
     *
     * param goalId: the ID of the goal
     * param checked: boolean. This is where the user says that they have or have
     *   not yet completed this goal.
     * param notes: string. The user can record any string of notes they want on this goal.
     */
    writeGoal: function(goalId, {checked, notes}) {
        const info = {
            checked: checked,
            notes: notes
        };
        const k = this.userGoalKeyPrefix() + goalId;
        this.browserStorage.setItem(k, JSON.stringify(info));
    },

    readGoal: function(goalId) {
        const k = this.userGoalKeyPrefix() + goalId;
        return JSON.parse(this.browserStorage.getItem(k));
    },

    removeGoal: function(goalId) {
        const k = this.userGoalKeyPrefix() + goalId;
        this.browserStorage.removeItem(k);
    },

    /* Build an object containing current goal info.
     * Keys are goal IDs, values are objects of the form
     *   {
     *     checked: boolean,
     *     notes: string
     *   }
     *
     * param prefix: Optional prefix. If defined, then gather
     *   goal info only for IDs that begin with this prefix.
     *   This is understood as a prefix in the sense of whole segments,
     *   where IDs are made up of segments joined by dots.
     *   Thus, an ID must either equal the prefix, or begin with it
     *   followed immediately by a dot.
     */
    buildGoalLookupByPrefix: function(prefix) {
        prefix = prefix || '';
        const lookup = {};
        const fullPrefix = this.userGoalKeyPrefix() + prefix;
        const m = fullPrefix.length;
        const p = prefix.length;
        for (let i = 0; i < this.browserStorage.length; i++) {
            let k = this.browserStorage.key(i);
            let r = k.slice(m);
            // To be accepted, the key must satisfy two conditions:
            // (1) It must begin with the "full prefix", i.e. the fixed "goal key prefix"
            // plus any initial libpath segments we require.
            // (2) One of three things must be true: either
            //      (a) we require no initial libpath segments (p === 0), or
            //      (b) there is nothing after the initial segments (r is empty), or
            //      (c) the remainder r begins with a dot.
            if ( k.startsWith(fullPrefix) && (p === 0 || r.length === 0 || r[0] === '.' ) ) {
                let goalId = prefix + r;
                let info = JSON.parse(this.browserStorage.getItem(k));
                lookup[goalId] = info;
            }
        }
        return lookup;
    },

    /* Build an object containing current goal info.
     * Keys are goal IDs, values are objects of the form
     *   {
     *     checked: boolean,
     *     notes: string
     *   }
     *
     * param goalIds: Array listing those goal IDs for which
     *   we should gather existing info.
     * return: object whose keys are a subset of the given array
     *   of goal IDs. A goal ID will appear as key iff we actually
     *   have any goal info stored for it.
     */
    buildGoalLookupByList: function(goalIds) {
        const lookup = {};
        for (let id of goalIds) {
            const k = this.userGoalKeyPrefix() + id;
            const info = JSON.parse(this.browserStorage.getItem(k));
            if (info) {
                lookup[id] = info;
            }
        }
        return lookup;
    },

    exportGoalsAsJSON: function() {
        const L = this.buildGoalLookupByPrefix();
        const J = JSON.stringify(L, null, 4);
        iseUtil.download('pise_study_notes.json', J);
    },

    importGoalsFromJSON: function(j) {
        const goals = JSON.parse(j);
        this.importGoals(goals);
    },

    /* Import goal data, recording it in this.browserStorage.
     *
     * param goals: Object of the form built by the buildGoalLookup method.
     */
    importGoals: function(goals) {
        // TODO:
        //   Check that the given object is well-formatted.
        for (let goalId of Object.keys(goals)) {
            // TODO:
            //   Warn user if going to overwrite existing data in this.browserStorage.
            const k = this.userGoalKeyPrefix() + goalId;
            this.browserStorage.setItem(k, JSON.stringify(goals[goalId]));
        }
    },

    /* Say whether the current user has any locally recorded study goal data whatsoever.
     *
     * return: boolean
     */
    userHasAnyLocalStudyGoalData: function() {
        const prefix = this.userGoalKeyPrefix();
        for (let storage of [window.sessionStorage, window.localStorage]) {
            for (let i = 0; i < storage.length; i++) {
                let k = storage.key(i);
                if (k.startsWith(prefix)) {
                    return true;
                }
            }
        }
        return false;
    },

    /* Remove all recorded study goal data, either just under the present user,
     # or globally.
     *
     * NOTE: Study goal data is removed from both sessionStorage and localStorage.
     *
     * param global: If truthy, we remove all study goal data whatsoever. Otherwise,
     *     we remove only the study goal data under the current user.
     */
    removeAllStudyGoalData: function(global) {
        const prefix = global ? this.goalKeyPrefix : this.userGoalKeyPrefix();
        for (let storage of [window.sessionStorage, window.localStorage]) {
            const toRemove = [];
            for (let i = 0; i < storage.length; i++) {
                let k = storage.key(i);
                if (k.startsWith(prefix)) {
                    toRemove.push(k);
                }
            }
            for (let k of toRemove) {
                storage.removeItem(k);
            }
        }
        this.refreshAllBoxElements();
    },

});

Object.assign(StudyManager.prototype, iseUtil.eventsMixin);

return StudyManager;

});
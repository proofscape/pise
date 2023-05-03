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

import { softwareTableRows } from "../piseAboutDialogContents";
const makeSoftwareTableRow = require('../dialog');

define([
    "dojo/_base/declare",
    "dojo/query",
    "dojo/on",
    "dojo/dom-construct",
    "dijit/layout/ContentPane",
    "dijit/MenuBar",
    "dijit/PopupMenuBarItem",
    "dijit/Menu",
    "dijit/MenuItem",
    "dijit/CheckedMenuItem",
    "dijit/PopupMenuItem",
    "dijit/DropDownMenu",
    "dijit/MenuSeparator",
    "dijit/ConfirmDialog",
    "ise/util",
    "ise/errors"
], function(
    declare,
    query,
    dojoOn,
    domConstruct,
    ContentPane,
    MenuBar,
    PopupMenuBarItem,
    Menu,
    MenuItem,
    CheckedMenuItem,
    PopupMenuItem,
    DropDownMenu,
    MenuSeparator,
    ConfirmDialog,
    iseUtil,
    pfscErrors
){

// MenuManager class
const MenuManager = declare(null, {

    // Properties
    hub: null,
    lhMenuBar: null,
    rhMenuBar: null,

    proofscapeMenu: null,
    proofscapeMenuPopup: null,
    pfscOpt_about: null,
    pfscOpt_copyLink: null,
    pfscOpt_pbe: null,
    pfscOpt_updateCheck: null,
    pfsc_update_dropdown: null,

    configMenu: null,
    configMenuPopup: null,
    config_theme_dropdown: null,
    config_zoom_dropdown: null,

    chartMenu: null,
    chartMenuPopup: null,
    chartOpt_Back: null,
    chartOpt_Fwd: null,
    chartOpt_CopyLibpath: null,
    chart_tsHome: null,
    chart_ov_opts: null,
    chart_layout_dropdown: null,
    chart_expansion_mode_dropdown: null,
    chart_selection_style_dropdown: null,
    chartOpt_showLibpaths: null,
    activeForest: null,

    pdfMenu: null,
    pdfMenuPopup: null,
    pdfOpt_Open: null,
    pdfOpt_FromLib: null,
    pdfOpt_ClearMemCache: null,
    pdfDialog_FromLib: null,
    pdfInput_FromLib: null,

    viewMenu: null,
    viewMenuPopup: null,
    viewOpt_ToggleFullscren: null,

    studyMenu: null,
    studyMenuPopup: null,
    studyOpt_goalsVisible: null,
    studyOpt_BNR: null,
    studyDialog_confirmEnableBnr: null,
    studyDialog_confirmDisableBnr: null,
    studyOpt_ExportGoals: null,
    studyOpt_ImportGoals: null,
    studyDialog_confirmEraseBrowserNotes: null,
    studyOpt_EraseBrowserNotes: null,
    studyDialog_confirmEnableSsnr: null,
    studyDialog_confirmDisableSsnr: null,
    studyOpt_SSNR: null,

    sympyMenu: null,
    sympyMenuPopup: null,
    sympyOpt_about: null,
    sympyOpt_status: null,
    sympyOpt_restart: null,

    userMenuPopup: null,
    logged_out_userMenu: null,
    logged_in_userMenu: null,
    userDialog_requestHosting: null,
    userDialog_settings: null,
    userDialog_confirmDeleteNotes: null,
    userDialog_confirmDeleteAcct: null,

    helpMenu: null,
    helpMenuPopup: null,

    // Methods

    /**
     * param tct: the app's TabContainerTree.
     */
    constructor: function(tct) {
        tct.registerActivePaneListener(this);
    },

    noteActivePane: function(cp) {
        // If the new active pane is a Chart pane, then set its forest as the active one.
        if (!cp) return;
        const info = this.hub.contentManager.getContentInfo(cp.id);
        if (!info) return;
        if (info.type === this.hub.contentManager.crType.CHART) {
            const forest = this.hub.chartManager.getForest(cp.id);
            this.setActiveForest(forest);
        }
    },

    updateForUser: function() {
        this.updateUserMenu();
        this.updateStudyMenu();
    },

    /*
     * param ISE_state: object describing the ISE_state, as computed by main.js
     */
    buildMenus: function(ISE_state) {
        this.buildLefthandMenu(ISE_state);
        this.buildRighthandMenu(ISE_state);
        this.hub.navManager.buildNavButtons();
    },

    buildLefthandMenu: function(ISE_state) {
        this.lhMenuBar = new MenuBar({});

        this.proofscapeMenu = new DropDownMenu({});

        this.proofscapeMenuPopup = new PopupMenuBarItem({
            label: '<span id="title"><span class="title-logo"></span>PISE<span class="beta">beta</span></span>',
            popup: this.proofscapeMenu
        });
        this.lhMenuBar.addChild(this.proofscapeMenuPopup);

        this.buildProofscapeMenu(ISE_state);

        this.lhMenuBar.placeAt("lhMenu");
        this.lhMenuBar.startup();
        this.lhMenuBar.domNode.style.display = 'inline-block';
    },

    buildRighthandMenu: function(ISE_state) {
        this.rhMenuBar = new MenuBar({});

        this.studyMenu = new DropDownMenu({});
        this.viewMenu = new DropDownMenu({});
        this.pdfMenu = new DropDownMenu({});
        this.chartMenu = new DropDownMenu({});
        this.configMenu = new DropDownMenu({});
        this.sympyMenu = new DropDownMenu({});
        this.helpMenu = new DropDownMenu({});
        this.logged_out_userMenu = new DropDownMenu({});
        this.logged_in_userMenu = new DropDownMenu({});

        this.studyMenuPopup = new PopupMenuBarItem({
            label: "Study",
            popup: this.studyMenu
        });
        this.rhMenuBar.addChild(this.studyMenuPopup);

        this.viewMenuPopup = new PopupMenuBarItem({
            label: "View",
            popup: this.viewMenu
        });
        this.rhMenuBar.addChild(this.viewMenuPopup);

        this.pdfMenuPopup = new PopupMenuBarItem({
            label: "PDF",
            popup: this.pdfMenu
        });
        this.rhMenuBar.addChild(this.pdfMenuPopup);

        this.chartMenuPopup = new PopupMenuBarItem({
            label: "Chart",
            popup: this.chartMenu
        });
        this.rhMenuBar.addChild(this.chartMenuPopup);
        // Disable the Chart menu popup. Will re-enable only when appropriate.
        this.chartMenuPopup.set('disabled', true);

        this.sympyMenuPopup = new PopupMenuBarItem({
            label: "Engine",
            popup: this.sympyMenu
        })
        this.rhMenuBar.addChild(this.sympyMenuPopup);

        this.configMenuPopup = new PopupMenuBarItem({
            label: "Config",
            popup: this.configMenu
        });
        this.rhMenuBar.addChild(this.configMenuPopup);

        this.helpMenuPopup = new PopupMenuBarItem({
            label: "Help",
            popup: this.helpMenu
        })
        this.rhMenuBar.addChild(this.helpMenuPopup);

        this.userMenuPopup = new PopupMenuBarItem({
            label: "User",
            popup: this.logged_out_userMenu,
        });
        if (ISE_state.loginsPossible && !ISE_state.personalServerMode) {
            this.rhMenuBar.addChild(this.userMenuPopup);
        }

        this.buildConfigMenu();
        this.buildChartMenu();
        this.buildPdfMenu(ISE_state);
        this.buildViewMenu();
        this.buildStudyMenu();
        this.buildUserMenus(ISE_state);
        this.buildHelpMenu();
        this.buildSymPyMenu();
    
        this.rhMenuBar.placeAt("rhMenu");
        this.rhMenuBar.startup();
    },

    buildProofscapeMenu: function(ISE_state) {
        var menu = this.proofscapeMenu,
            mgr = this;

        // "About" dialog
        this.pfscOpt_about = new MenuItem({
            label: "About Proofscape ISE",
            onClick: async function(event) {
                const extraSoftware = await mgr.hub.getExtraSoftwareForAboutDialog();
                const notices = await mgr.hub.getNoticesForAboutDialog();
                mgr.hub.alert({
                    title: "About Proofscape ISE",
                    content: aboutIseHtml(
                        mgr.hub.getVersionStringForAboutDialog(),
                        mgr.hub.getAgreementHtmlForAboutDialog(),
                        extraSoftware,
                        notices,
                    ),
                });
            },
        });
        menu.addChild(this.pfscOpt_about);

        // If we're running the OCA, we need an option for whether to check for updates.
        if (ISE_state.OCA_version) {
            const dd = domConstruct.toDom(`
                <select>
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                </select>
            `);
            const popup = new ContentPane({
                class: 'popupCP',
                content: dd,
            });
            this.pfscOpt_updateCheck = new PopupMenuItem({
                label: 'Check for Updates...',
                popup: popup,
            });
            menu.addChild(this.pfscOpt_updateCheck);
            this.pfsc_update_dropdown = query(popup.domNode).query('select');
            this.pfsc_update_dropdown.on('change', function(e){
                mgr.hub.setUpdateCheckMode(this.value);
            });
        }

        // Generate a link to restore (most of) the current ISE state, and copy it to clipboard.
        this.pfscOpt_copyLink = new MenuItem({
            label: "Copy link",
            onClick: function(event) {
                mgr.hub.generateLink().then(link => {
                    iseUtil.copyTextWithMessageFlashAtClick(link, event);
                });
            }
        });
        menu.addChild(this.pfscOpt_copyLink);

        // PBE item:
        this.pfscOpt_pbe = new MenuItem({
            onClick: function(event) {
                if (mgr.hub.pfscExtInterface.extensionAppearsToBePresent()) {
                    mgr.hub.pfscExtInterface.makeRequest('sendMessage', {
                        type: "openOptionsPage"
                    });
                } else {
                    iseUtil.openInNewTab(mgr.hub.aboutPbeUrl);
                }
            }
        });
        menu.addChild(this.pfscOpt_pbe);

        // Set to update on open.
        dojoOn(menu, 'open', function(e){
            mgr.updateProofscapeMenu();
        });
    },

    updateProofscapeMenu: function() {
        const presentLabel = "Extension options...";
        const absentLabel = "Get browser extension...";
        // We base our choice on the non-blocking (but faulty) check:
        const apparentlyPresent = this.hub.pfscExtInterface.extensionAppearsToBePresent();
        const label = apparentlyPresent ? presentLabel : absentLabel;
        this.pfscOpt_pbe.set('label', label);
        // But if the extension appeared to be present then we also fire off a self-repairing check too.
        // This way we might err once, but not twice.
        if (apparentlyPresent) {
            const mgr = this;
            mgr.hub.pfscExtInterface.checkExtensionPresence({timeout: 1000})
                .then(vers => {
                    mgr.pfscOpt_pbe.set('label', presentLabel);
                })
                .catch(reason => {
                    mgr.pfscOpt_pbe.set('label', absentLabel);
                });
        }
    },

    buildSymPyMenu: function() {
        const mgr = this;

        this.sympyOpt_status = new MenuItem({
            label: "Status",
            onClick: function(event) {
                mgr.updateSymPyMenu();
            }
        });
        this.sympyMenu.addChild(this.sympyOpt_status);

        this.sympyOpt_restart = new MenuItem({
            label: "Restart",
            onClick: function(event) {
                mgr.hub.choice({
                    title: "Restart Engine",
                    okButtonText: "Restart",
                    content: restartSymPyConfirmationHtml,
                    dismissCode: "restartSymPy",
                }).then(result => {
                    if (result.accepted || !result.shown) {
                        mgr.hub.restartMathWorker();
                    }
                })
            }
        });
        this.sympyMenu.addChild(this.sympyOpt_restart);

        this.sympyOpt_about = new MenuItem({
            label: "About the SymPy math engine",
            onClick: function(event) {
                mgr.hub.alert({
                    title: "About the SymPy math engine",
                    content: aboutSymPyEngineHtml,
                })
            }
        });
        this.sympyMenu.addChild(this.sympyOpt_about);

        dojoOn(this.sympyMenu, 'open', mgr.updateSymPyMenu.bind(mgr));
    },

    updateSymPyMenu: function() {
        const statusItem = this.sympyOpt_status;
        statusItem.set('label', '<span class="lrMenuItem sympyStatusMenuItem"><span>Status: checking...</span><span class="menuItemSpinner"></span></span>');
        this.hub.checkMathWorkerHealthy().then(healthy => {
            if (healthy) {
                statusItem.set('label', '<span class="lrMenuItem sympyStatusMenuItem"><span>Status: Ready</span><span class="menuItemGreenDot">&#9679;</span></span>');
            } else {
                statusItem.set('label', '<span class="lrMenuItem sympyStatusMenuItem"><span>Status: Not responding</span><span class="menuItemRedDot">&#9679;</span></span>');
            }
        });
    },

    buildHelpMenu: function() {
        const mgr = this;
        this.helpMenu.addChild(new MenuItem({
            label: "Report Bug",
            onClick: function(event) {
                iseUtil.openInNewTab(mgr.hub.bugReportUrl);
            }
        }));
    },

    buildUserMenus: function(ISE_state) {
        const mgr = this;

        const menu_out = this.logged_out_userMenu;
        menu_out.addChild(new MenuItem({
            label: 'Sign In',
            onClick: function() {
                iseUtil.openPopupWindow(
                    mgr.hub.urlFor('login'),
                    'loginWindow', {
                    width: 500, height: 530,
                    centerX: true, centerY: true,
                });
            }
        }));

        const menu_in = this.logged_in_userMenu;

        if (ISE_state.hostingByRequest) {
            let clearOnLoad = true;
            const prpoHtml = this.hub.getPrivacyPolicyHtmlForHostingRequestDialog(ISE_state);
            this.userDialog_requestHosting = new ConfirmDialog({
                title: "Request Hosting",
                content: hostingRequestHtml(prpoHtml),
                onExecute: function() {
                    const dlg = mgr.userDialog_requestHosting;
                    const node = dlg.domNode;

                    const ownerSelect = node.querySelector('.owner-segment select');
                    const hostSpan = node.querySelector('.host-segment');
                    const repoInput = node.querySelector('.repo-segment input');
                    const versionInput = node.querySelector('input[name=version]');
                    const commentArea = node.querySelector('textarea');

                    const host = hostSpan.innerText;
                    const owner = ownerSelect.value;
                    const repo = repoInput.value;
                    const repopath = `${host}.${owner}.${repo}`;

                    const vers = versionInput.value;
                    const comment = commentArea.value;

                    //console.log('request info:', repopath, vers, comment);
                    mgr.hub.xhrFor('requestHosting', {
                        method: "POST",
                        form: {repopath, vers, comment},
                        handleAs: 'json',
                    }).then(resp => {
                        clearOnLoad = true;
                        if (resp.err_lvl > 0) {
                            if (resp.err_lvl === pfscErrors.serverSideErrorCodes.HOSTING_REQUEST_REJECTED) {
                                resp.err_msg = `<h2>Cannot Request</h2><p>${resp.err_msg}</p>`;
                            } else if (resp.err_lvl === pfscErrors.serverSideErrorCodes.HOSTING_REQUEST_UNNECESSARY) {
                                resp.err_msg = `<h2>No Request Necessary</h2><p>${resp.err_msg}</p>`;
                            }
                            mgr.hub.errAlert2(resp);
                            return;
                        }
                        const status = resp.new_hosting_status;
                        if (status === "PENDING") {
                            mgr.hub.alert({
                                title: "Hosting Request Received",
                                content: `<h2>Success!</h2>
                                    <p>Your request to host <span class="monospace">${repopath}</span>
                                    at <span class="monospace">${vers}</span> has been received!</p>
                                    <p>We'll try to get back to you as soon as possible!</p>`,
                            })
                        } else {
                            mgr.hub.errAlert('Unknown error. Please contact site administrator.');
                            clearOnLoad = false;
                        }
                    });
                },
            });

            const dlg = mgr.userDialog_requestHosting;
            dlg.set('buttonOk', "Make Request");

            const node = dlg.domNode;
            const repoInput = node.querySelector('.repo-segment input');
            const versionInput = node.querySelector('input[name=version]');
            const charCount = node.querySelector('.charCount');
            const commentArea = node.querySelector('textarea');
            iseUtil.noCorrect(repoInput);
            iseUtil.noCorrect(versionInput);
            const updateChars = iseUtil.showRemainingChars(commentArea, charCount);

            menu_in.addChild(new MenuItem({
                label: 'Request Hosting',
                onClick: function() {
                    const d = mgr.hub.getHostUserOrgs();
                    if (d === null) {
                        // This should never happen, since the "Request Hosting" option only
                        // appears in the menu for a logged in user; but, just in case...
                        mgr.hub.errAlert('You must log in if you want to request hosting.');
                        return;
                    }
                    const {host, user, orgs} = d;

                    const hostSegment = node.querySelector('.host-segment');
                    hostSegment.innerHTML = host;

                    const ownerSelect = node.querySelector('.owner-segment select');
                    let options = `<option value="${user}">${user}</option>\n`;
                    for (let org of orgs) {
                        options += `<option value="${org}">${org}</option>\n`;
                    }
                    ownerSelect.innerHTML = options;

                    if (clearOnLoad) {
                        repoInput.value = '';
                        versionInput.value = '';
                        commentArea.value = '';
                        updateChars();
                    }

                    dlg.show();
                }
            }));
        }

        this.userDialog_settings = new ConfirmDialog({
            title: "Settings",
            content: userSettingsHtml,
        });
        this.userDialog_confirmDeleteNotes = new ConfirmDialog({
            title: "Confirm Notes Deletion",
            content: deleteSsnrConfirmDialog,
        });
        this.userDialog_confirmDeleteAcct = new ConfirmDialog({
            title: "Confirm Account Deletion",
            content: deleteUserAcctConfirmDialog,
        });

        const settingsDlg = this.userDialog_settings;
        const settingsNode = settingsDlg.domNode;
        const settingsUsername = settingsNode.querySelector('span.username');
        const settingsEmail = settingsNode.querySelector('span.email');
        const settingsOrgList = settingsNode.querySelector('span.orgList');
        const settingsExportNotesButton = settingsNode.querySelector('a.exportNotesButton');
        const settingsExportAcctButton = settingsNode.querySelector('a.exportAcctButton');
        const settingsDeleteNotesButton = settingsNode.querySelector('a.deleteNotesButton');
        const settingsDeleteAcctButton = settingsNode.querySelector('a.deleteAcctButton');

        const confDelNotesDlg = this.userDialog_confirmDeleteNotes;
        const confDelNotesNode = confDelNotesDlg.domNode;
        const confDelNotesConfInput = confDelNotesNode.querySelector('input[name=confirmation]');
        const confDelNotesGoAheadButton = confDelNotesNode.querySelector('a.dangerButton');

        const confDelAcctDlg = this.userDialog_confirmDeleteAcct;
        const confDelAcctNode = confDelAcctDlg.domNode;
        const confDelAcctConfInput = confDelAcctNode.querySelector('input[name=confirmation]');
        const confDelAcctGoAheadButton = confDelAcctNode.querySelector('a.dangerButton');

        menu_in.addChild(new MenuItem({
            label: 'Settings',
            onClick: function() {
                const d = mgr.hub.getHostUserOrgs();
                if (d === null) {
                    // This should never happen, since the "Request Hosting" option only
                    // appears in the menu for a logged in user; but, just in case...
                    mgr.hub.errAlert('You must log in if you want to request hosting.');
                    return;
                }
                const {host, user, orgs} = d;
                const emailAddr = mgr.hub.getEmail();
                settingsUsername.innerText = `${host}.${user}`;
                settingsEmail.innerText = emailAddr;
                settingsOrgList.innerText = orgs.join(', ');
                settingsDlg.show();
            }
        }));

        settingsExportNotesButton.addEventListener('click', event => {
            iseUtil.openPopupWindow(
                mgr.hub.urlFor('exportUserInfo', {
                    addArgs: {
                        target: 'notes',
                        mode: 'page',
                    },
                    addCsrfToken: true,
                }),
                'downloadWindow', {
                    width: 500, height: 530,
                    centerX: true, centerY: true,
                });
        });


        settingsExportAcctButton.addEventListener('click', event => {
            iseUtil.openPopupWindow(
                mgr.hub.urlFor('exportUserInfo', {
                    addArgs: {
                        target: 'all',
                        mode: 'page',
                    },
                    addCsrfToken: true,
                }),
                'downloadWindow', {
                width: 500, height: 530,
                centerX: true, centerY: true,
            });
        });


        const delNotesActivationCheck = iseUtil.confStringActivatesDangerButton(
            confDelNotesConfInput, 'DeleteAllMyNotes', confDelNotesGoAheadButton,
            async event => {
                console.debug('user requested to delete all notes');
                settingsNode.classList.add('waiting');

                const confString = confDelNotesConfInput.value;
                const resp = await this.hub.xhrFor('purgeNotes', {
                    method: "POST",
                    form: {
                        confirmation: confString,
                    },
                    handleAs: 'json',
                });

                settingsNode.classList.remove('waiting');

                if (!mgr.hub.errAlert3(resp)) {
                    const n = resp.num_remaining_notes;
                    if (n > 0) {
                        mgr.hub.errAlert("Something seems to have gone wrong. Please try again later.");
                    } else {
                        await mgr.hub.studyManager.refreshAllBoxElements();
                        mgr.hub.alert({
                            title: "Notes Deleted",
                            content: `
                            <div class="iseDialogContentsStyle03">
                            <p>Your notes were successfully deleted from the server.</p>
                            <p>NOTE: Unless you de-activate server-side note recording
                            now (from the Study menu), any new notes you enter will continue to
                            be recorded on the server!
                            </p>
                            </div>
                            `,
                        });
                    }
                }

                confDelNotesDlg.hide();
            }
        );

        const delAcctActivationCheck = iseUtil.confStringActivatesDangerButton(
            confDelAcctConfInput, 'DeleteMyAccount', confDelAcctGoAheadButton,
            async event => {
                console.debug('user requested to delete acct');
                settingsNode.classList.add('waiting');
                const confString = confDelAcctConfInput.value;

                const resp = await this.hub.xhrFor('purgeUserAcct', {
                    method: "POST",
                    form: {
                        confirmation: confString,
                    },
                    handleAs: 'json',
                });

                settingsNode.classList.remove('waiting');

                if (!mgr.hub.errAlert3(resp)) {
                    const n = resp.user_nodes_deleted;
                    const username = resp.username;
                    if (n === 0) {
                        mgr.hub.errAlert("Something seems to have gone wrong. Please try again later.");
                    } else {
                        await mgr.hub.updateUser();
                        mgr.hub.alert({
                            title: "User Account Deleted",
                            content: `
                            <div class="iseDialogContentsStyle03">
                            <p>Your ${username} account was successfully deleted from the server.
                            Sorry to see you go!
                            </p>
                            <p>You can always sign in again, using the same OAuth provider and the
                            same username, and a brand new account will be created.
                            </p>
                            </div>
                            `,
                        });
                    }
                }

                confDelAcctDlg.hide();
            }
        );

        settingsDeleteNotesButton.addEventListener('click', event => {
            if (mgr.hub.studyManager.inSsnrMode()) {
                confDelNotesConfInput.value = '';
                delNotesActivationCheck();
                confDelNotesDlg.show();
            } else {
                mgr.hub.alert({
                    title: "Cannot delete notes",
                    content: `
                    <div class="iseDialogContentsStyle03">
                    <p>You cannot delete server-side notes while the server-side note
                    recording option is not active.</p>
                    <p>If you want to delete your notes, you have to first go to the Study menu,
                    and reactivate server-side note recording.</p>
                    <p class="danger">WARNING: If in the meantime you have recorded other notes in your browser's local storage,
                    you may want to export those first, as they will be overwritten by any notes currently
                    on the server.</p>
                    </div>
                    `,
                });
            }
        });

        settingsDeleteAcctButton.addEventListener('click', event => {
            if (mgr.hub.studyManager.userHasAnyLocalStudyGoalData()) {
                mgr.hub.alert({
                    title: "Cannot delete account",
                    content: `
                    <div class="iseDialogContentsStyle03">
                    <p>You cannot delete your account while you have any study notes
                    stored in your browser under this account name. This is to prevent
                    a state in which you have recorded notes you cannot access.</p>
                    <p>If you want to delete your account, you have to first go to the Study menu,
                    and erase your browser notes. You may want to export them first.</p>
                    <p>Also note that you will not be able to erase your browser notes
                    if server-side note recording is activated.</p>
                    </div>
                    `,
                });
            } else {
                confDelAcctConfInput.value = '';
                delAcctActivationCheck();
                confDelAcctDlg.show();
            }
        });

        menu_in.addChild(new MenuItem({
            label: 'Sign Out',
            onClick: function() {
                mgr.hub.xhrFor('logout').then(() => {
                    mgr.hub.updateUser();
                });
            }
        }));
    },

    updateUserMenu: function() {
        const username = this.hub.getUsername();
        //console.log('update user menu for:', username);
        if (username) {
            this.userMenuPopup.set('popup', this.logged_in_userMenu);
            this.userMenuPopup.set('label', username);
        } else {
            this.userMenuPopup.set('popup', this.logged_out_userMenu);
            this.userMenuPopup.set('label', 'User');
        }
    },

    buildStudyMenu: function() {
        const menu = this.studyMenu,
            mgr = this,
            studymgr = this.hub.studyManager;

        // Goal box visibility
        this.studyOpt_goalsVisible = new CheckedMenuItem({
            label: 'Show Goal Boxes',
            checked: true, // Actual initial value will be set by Hub.restoreState().
            onChange: function(){
                const showGoalBoxes = this.checked;
                studymgr.setGoalBoxVisibility(showGoalBoxes);
            }
        });
        menu.addChild(this.studyOpt_goalsVisible);

        // --------------------------------
        menu.addChild(new MenuSeparator());

        // Browser Note Recording option
        this.studyDialog_confirmEnableBnr = new ConfirmDialog({
            title: "Enable Browser Note Recording",
            content: enableBnrHtml,
            onExecute: function() {
                studymgr.setBrowserRecordingOption(true);
                studymgr.updateBrowserStorageForUser();
                mgr.studyOpt_BNR.set("checked", true);
            },
        });
        this.studyDialog_confirmDisableBnr = new ConfirmDialog({
            title: "Disable Browser Note Recording",
            content: disableBnrHtml,
            onExecute: function() {
                studymgr.setBrowserRecordingOption(false);
                studymgr.updateBrowserStorageForUser();
                mgr.studyOpt_BNR.set("checked", false);
            },
        });
        this.studyOpt_BNR = new CheckedMenuItem({
            label: 'Record Notes in Browser',
            checked: false,
            // By overriding the underscore-prefixed `_onClick`, we can wait for
            // confirmation from dialogs before actually making the change.
            _onClick: function(){
                if (this.checked) {
                    mgr.studyDialog_confirmDisableBnr.show();
                } else {
                    mgr.studyDialog_confirmEnableBnr.show();
                }
            },
        });
        menu.addChild(this.studyOpt_BNR);

        // Export browser notes
        this.studyOpt_ExportGoals = new MenuItem({
            label: 'Export Browser Notes to .json',
            onClick: studymgr.exportGoalsAsJSON.bind(studymgr)
        });
        menu.addChild(this.studyOpt_ExportGoals);

        // Import browser notes
        this.studyOpt_ImportGoals = new MenuItem({
            label: 'Import Browser Notes from .json',
            onClick: function() {
                iseUtil.uploadFileContents('.json')
                    .then(studymgr.importGoalsFromJSON.bind(studymgr));
            }
        });
        menu.addChild(this.studyOpt_ImportGoals);

        // Erase browser notes
        this.studyDialog_confirmEraseBrowserNotes = new ConfirmDialog({
            title: "Erase Browser Notes",
            content: clearBnrHtml,
            onExecute: function() {
                studymgr.removeAllStudyGoalData();
            },
        });
        this.studyOpt_EraseBrowserNotes = new MenuItem({
            label: 'Erase Browser Notes',
            onClick: function() {
                mgr.studyDialog_confirmEraseBrowserNotes.show();
            }
        })
        menu.addChild(this.studyOpt_EraseBrowserNotes);

        // --------------------------------
        menu.addChild(new MenuSeparator());

        // Server-Side Note Recording option
        this.studyDialog_confirmEnableSsnr = new ConfirmDialog({
            title: "Enable Server Side Note Recording",
            onExecute: function() {
                mgr.hub.xhrFor('requestSsnr', {
                    method: "POST",
                    form: {
                        activate: 1,
                        confirm: 1
                    },
                    handleAs: 'json',
                }).then(resp => {
                    if (resp.err_lvl === pfscErrors.serverSideErrorCodes.SSNR_SERVICE_DISABLED) {
                        // Fail silently.
                        return;
                    }
                    const new_setting = resp.new_setting;
                    if (new_setting !== "BROWSER_AND_SERVER") {
                        mgr.hub.errAlert('Server unavailable. Please try again later.');
                        return;
                    }
                    mgr.studyOpt_SSNR.set("checked", true);
                    mgr.hub.updateUser();
                    mgr.hub.alert({
                        title: "Server Side Note Recording",
                        content: "Server Side Note Recording is now enabled.",
                    });
                });
            },
        });
        this.studyDialog_confirmDisableSsnr = new ConfirmDialog({
            title: "Disable Server Side Note Recording",
            onExecute: function() {
                mgr.hub.xhrFor('requestSsnr', {
                    method: "POST",
                    form: {
                        activate: 0,
                        confirm: 1
                    },
                    handleAs: 'json',
                }).then(resp => {
                    if (resp.err_lvl === pfscErrors.serverSideErrorCodes.SSNR_SERVICE_DISABLED) {
                        // Fail silently.
                        return;
                    }
                    const new_setting = resp.new_setting;
                    if (new_setting !== "BROWSER_ONLY") {
                        mgr.hub.errAlert('Server unavailable. Please try again later.');
                        return;
                    }
                    mgr.studyOpt_SSNR.set("checked", false);
                    mgr.hub.updateUser();
                    mgr.hub.alert({
                        title: "Server Side Note Recording",
                        content: "Server Side Note Recording has been deactivated.",
                    });
                });
            },
        });
        this.studyOpt_SSNR = new CheckedMenuItem({
            label: 'Record Notes on Server',
            checked: false,
            disabled: true,
            _onClick: function() {
                const activate = !this.checked;
                mgr.hub.xhrFor('requestSsnr', {
                    method: "POST",
                    form: {
                        activate: activate ? 1 : 0,
                        confirm: 0
                    },
                    handleAs: 'json',
                }).then(resp => {
                    if (resp.err_lvl === pfscErrors.serverSideErrorCodes.SSNR_SERVICE_DISABLED) {
                        // Fail silently.
                        return;
                    }
                    const html = resp.conf_dialog_html;
                    if (!html) {
                        mgr.hub.errAlert('Server unavailable. Please try again later.');
                        return;
                    }
                    const dialog = activate ? mgr.studyDialog_confirmEnableSsnr : mgr.studyDialog_confirmDisableSsnr;
                    dialog.set('content', html);
                    dialog.show();
                });
            },
        });
        menu.addChild(this.studyOpt_SSNR);

    },

    updateStudyMenu: function() {
        const bnr_opt = this.studyOpt_BNR;
        bnr_opt.set('checked', this.hub.studyManager.checkBrowserRecordingOption());

        const ssnr_opt = this.studyOpt_SSNR;
        ssnr_opt.set('disabled', !this.hub.ssnrAvailable || !this.hub.isLoggedIn() || this.hub.personalServerMode);
        ssnr_opt.set('checked', this.hub.studyManager.inSsnrMode());
    },

    buildViewMenu: function() {
        var menu = this.viewMenu,
            mgr = this;

        // Toggle fullscreen
        this.viewOpt_ToggleFullscren = new MenuItem({
            label: 'Toggle Fullscreen',
            onClick: mgr.hub.toggleFullScreen
        });
        menu.addChild(this.viewOpt_ToggleFullscren);
    },

    buildPdfMenu: function(ISE_state) {
        var menu = this.pdfMenu,
            mgr = this,
            pdfmgr = this.hub.pdfManager;

        // Open from your computer
        this.pdfOpt_Open = new MenuItem({
            label: 'Open PDF from your computer...',
            onClick: function(evt){
                let input = document.createElement('input');
                input.type = 'file';
                input.accept = '.pdf';
                input.onchange = e => {
                    let filelist = e.target.files;
                    mgr.hub.contentManager.openContentInActiveTC({
                        type: "PDF",
                        lastOpenedFilelist: filelist,
                    });
                }
                input.click();
            }
        });
        menu.addChild(this.pdfOpt_Open);

        // Open from library
        if (ISE_state.offerPdfLibrary) {
            var dlg = new ConfirmDialog({
                title: "Open PDF from library...",
                content: '<input type="text" size="48" placeholder="path/to/yourfile.pdf"/>',
                //style: "width: 300px",
                onExecute: function() {
                    var path = mgr.pdfInput_FromLib.value;
                    //console.log('open from library: ', path);
                    mgr.hub.contentManager.openContentInActiveTC({
                        type: "PDF",
                        fromLibrary: path
                    });
                },
                //onCancel: function() { console.log('cancel'); }
            });
            //console.log(dlg);
            var input = dlg.domNode.querySelector('input');
            iseUtil.noCorrect(input);
            dojoOn(input, 'keydown', e => {
                // Accept on `Enter`
                if (e.code === "Enter") {
                    //console.log('pressed enter');
                    dlg.okButton.domNode.querySelector('.dijitButtonNode').click();
                }
            });
            this.pdfInput_FromLib = input;
            this.pdfDialog_FromLib = dlg;
            this.pdfOpt_FromLib = new MenuItem({
                label: 'Open PDF from library...',
                onClick: function(evt){
                    mgr.pdfDialog_FromLib.show();
                }
            });
            menu.addChild(this.pdfOpt_FromLib);
        }

        // Open from web
        const web_dlg = new ConfirmDialog({
            title: "Open PDF from the web...",
            content: '<input type="text" size="48" placeholder="http://......pdf"/>',
            //style: "width: 300px",
            onExecute: function() {
                let url = mgr.pdfInput_FromWeb.value;
                //console.log('open from web: ', url);
                mgr.hub.contentManager.openContentInActiveTC({
                    type: "PDF",
                    url: url
                });
            },
            //onCancel: function() { console.log('cancel'); }
        });
        //console.log(dlg);
        const web_input = web_dlg.domNode.querySelector('input');
        iseUtil.noCorrect(web_input);
        dojoOn(web_input, 'keydown', e => {
            // Accept on `Enter`
            if (e.code === "Enter") {
                //console.log('pressed enter');
                web_dlg.okButton.domNode.querySelector('.dijitButtonNode').click();
            }
        });
        this.pdfInput_FromWeb = web_input;
        this.pdfDialog_FromWeb = web_dlg;
        this.pdfOpt_FromWeb = new MenuItem({
            label: 'Open PDF from the web...',
            onClick: function(evt){
                mgr.pdfDialog_FromWeb.show();
            }
        });
        menu.addChild(this.pdfOpt_FromWeb);

        // --------------------------------
        menu.addChild(new MenuSeparator());

        // Clear mem cache
        this.pdfOpt_ClearMemCache = new MenuItem({
            label: 'Clear in-memory cache',
            onClick: function(evt) {
                mgr.hub.pdfManager.clearPdfCache();
                console.log('PDF mem cache cleared.');
            }
        });
        menu.addChild(this.pdfOpt_ClearMemCache);

    },

    buildConfigMenu: function() {
        var theMenuManager = this;

        // `Theme` options:
        var theme_dropdown = domConstruct.toDom(`
            <select>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
            </select>
        `);
        var theme_popup = new ContentPane({
            class: 'popupCP',
            content: theme_dropdown
        });
        this.configMenu.addChild(new PopupMenuItem({
            label: 'Theme',
            popup: theme_popup
        }));
        this.config_theme_dropdown = query(theme_popup.domNode).query('select');
        this.config_theme_dropdown.on('change', function(e){
            theMenuManager.hub.setTheme(this.value);
        });

        // `Zoom` options:
        var zoom_dropdown = domConstruct.toDom(`
            <select></select>
        `);
        var zoom_popup = new ContentPane({
            class: 'popupCP',
            content: zoom_dropdown
        });
        this.configMenu.addChild(new PopupMenuItem({
            label: 'Zoom',
            popup: zoom_popup
        }));
        this.config_zoom_dropdown = query(zoom_popup.domNode).query('select');

        var zsq = this.config_zoom_dropdown,
            zs = zsq[0];
        for (var f = 5; f <= 20; f++) {
            var g = 10*f;
            domConstruct.create("option", { value: g, innerHTML: g+"%" }, zs);
        }
        zsq.on('change', function(e){
            theMenuManager.hub.setZoom(this.value);
        });

        // TESTING ---------------
        // Sometimes it's handy during development to trigger sth from a menu...
        /*
        this.configMenu.addChild(new MenuItem({
            label: "Test 1",
            onClick: function(){
                // Whatever you want to test...
            }
        }));
        */
        // -----------------------
    },
    
    // Build the Chart menu.
    buildChartMenu: function() {
        var menu = this.chartMenu,
            mgr = this;
    
        // Back / Forward options
        var backLabel = '<span class="lrMenuItem"><span>Back</span><span class="menuHint">Alt-[</span></span>';
        var fwdLabel = '<span class="lrMenuItem"><span>Forward</span><span class="menuHint">Alt-]</span></span>';
        this.chartOpt_Back = new MenuItem({
            label: backLabel,
            onClick: function(evt){
                mgr.activeForest.getHistoryManager().goBack();
            }
        });
        this.chartOpt_Fwd = new MenuItem({
            label: fwdLabel,
            onClick: function(evt){
                mgr.activeForest.getHistoryManager().goForward();
            }
        });
        menu.addChild(this.chartOpt_Back);
        menu.addChild(this.chartOpt_Fwd);

        // Separator
        menu.addChild(new MenuSeparator());

        // "Copy libpath" option
        this.chart_tsHome = domConstruct.create("div");
        this.chartOpt_CopyLibpath = new PopupMenuItem({
            label: 'Copy libpath',
            popup: new ContentPane({
                class: 'popupCP',
                content: this.chart_tsHome
            })
        });
        menu.addChild(this.chartOpt_CopyLibpath);

        // Separator
        menu.addChild(new MenuSeparator());

        // Overview options
        this.chart_ov_opts = {};
        var pos_names = {
            tl: "Top-Left",
            tr: "Top-Right",
            bl: "Bottom-Left",
            br: "Bottom-Right"
        };
        var ovSubMenu = new Menu();
        for (var p in pos_names) {
            var ch = new MenuItem({
                label: '<span class="cornerIcon '+p+'Icon"></span><span>'+pos_names[p]+'</span>',
                moosePosCode: p,
                onClick: function(e) {
                    mgr.activeForest.floor.setOverviewPos(this.moosePosCode);
                    mgr.activeForest.floor.showOverviewPanel(true);
                }
            });
            ovSubMenu.addChild(ch);
            this.chart_ov_opts[p] = ch;
        }
        var hide = new MenuItem({
            label: "Hide",
            onClick: function(e) {
                mgr.activeForest.floor.showOverviewPanel(false);
            }
        });
        ovSubMenu.addChild(hide);
        this.chart_ov_opts.hide = hide;
        menu.addChild(new PopupMenuItem({
            label: "Inset",
            popup: ovSubMenu
        }));

        // Layout options
        var layout_dropdown = domConstruct.toDom(`
            <select>
                <option value="KLayDown">FlowChart Down</option>
                <option value="KLayUp">FlowChart Up</option>
                <option value="OrderedList1">OrderedList</option>
            </select>
        `);
        var chart_layout_popup = new ContentPane({
            class: 'popupCP',
            content: layout_dropdown
        });
        menu.addChild(new PopupMenuItem({
            label: 'Layout',
            popup: chart_layout_popup
        }));
        this.chart_layout_dropdown = query(chart_layout_popup.domNode).query('select');
        this.chart_layout_dropdown.on('change', function(e){
            mgr.activeForest.changeLayoutStyle(this.value);
        });

        // Expansion mode options
        const expansion_mode_dropdown = domConstruct.toDom(`
            <select>
                <option value="unified">Unified</option>
                <option value="embedded">Embedded</option>
            </select>
        `);
        const expansion_mode_popup = new ContentPane({
            class: 'popupCP',
            content: expansion_mode_dropdown,
        });
        menu.addChild(new PopupMenuItem({
            label: 'Expansions',
            popup: expansion_mode_popup
        }));
        this.chart_expansion_mode_dropdown = query(expansion_mode_popup.domNode).query('select');
        this.chart_expansion_mode_dropdown.on('change', function(e){
            mgr.activeForest.setExpansionMode(this.value);
        });



        // Selection options
        const selection_dropdown = domConstruct.toDom(`
            <select>
                <option value="Node">Node</option>
                <option value="NodeEdges">Node & Edges</option>
                <option value="NodeEdgesNbrs">Node, Edges, Nbrs</option>
            </select>
        `);
        const selection_popup = new ContentPane({
            class: "popupCP",
            content: selection_dropdown
        })
        menu.addChild(new PopupMenuItem({
            label: 'Selection Style',
            popup: selection_popup
        }));
        this.chart_selection_style_dropdown = query(selection_popup.domNode).query('select');
        this.chart_selection_style_dropdown.on('change', function(e){
            mgr.activeForest.changeSelectionStyle(this.value);
            mgr.hub.chartManager.setDefaultSelectionStyle(this.value);
        })

        // Libpath subtitles
        this.chartOpt_showLibpaths = new CheckedMenuItem({
            label: 'Show Libpaths',
            //checked: true,
            onChange: function(){
                mgr.activeForest.setShowingLibpathSubtitles(this.checked);
            }
        });
        menu.addChild(this.chartOpt_showLibpaths);

        // Set to update on open.
        dojoOn(menu, 'open', function(e){
            mgr.updateChartMenu();
        });
    },

    // Update the Chart menu, based on the current state of the Forest in the active pane.
    updateChartMenu: function() {
        var forest = this.activeForest;
        if (!forest) return;

        // Enable/disable back/fwd options
        var histmgr = forest.getHistoryManager();
        this.chartOpt_Back.set('disabled', !histmgr.canGoBack());
        this.chartOpt_Fwd.set('disabled', !histmgr.canGoForward());

        // Enable/disable and rebuild "copy libpath" option
        var mp = forest.getSelectionManager().getSelectionMultipath();
        if (mp === null) {
            this.chartOpt_CopyLibpath.set('disabled', true);
        } else {
            query(this.chart_tsHome).innerHTML('');
            iseUtil.addTailSelector(this.chart_tsHome, mp.split('.'));
            this.chartOpt_CopyLibpath.set('disabled', false);
        }

        // Enable/disable overview options
        var floor = forest.getFloor(),
            visible = floor.overviewPanelIsVisible(),
            pos = floor.getOverviewPos();
        for (var k in this.chart_ov_opts) {
            var menuItem = this.chart_ov_opts[k];
            if (k === 'hide') {
                menuItem.set('disabled', !visible);
            } else {
                menuItem.set('disabled', visible && pos === menuItem.moosePosCode);
            }
        }

        // Set current values in dropdowns.
        const currentLayoutMethod = forest.getLayoutMethod();
        this.chart_layout_dropdown.val(currentLayoutMethod);

        const currentExpansionMode = forest.getExpansionMode();
        this.chart_expansion_mode_dropdown.val(currentExpansionMode);

        const currentSelectionStyle = forest.getSelectionStyle();
        this.chart_selection_style_dropdown.val(currentSelectionStyle);

        this.chartOpt_showLibpaths.set('checked', forest.showingLibpathSubtitles());
    },

    /* Set the active forest, i.e. the forest to be controlled by the Chart menu.
     * Pass null to disable the Chart menu.
     */
    setActiveForest: function(forest) {
        const popup = this.chartMenuPopup;
        if (forest) {
            this.activeForest = forest;
            popup.set('disabled', false);
        } else {
            popup.set('disabled', true);
        }
    },

});

const enableBnrHtml = `
<div class="iseDialogContentsStyle01">
<h1>Recording Notes in the Browser</h1>
<p style="font-size: 1.2em;">
If you enable this option, then checkmarks and notes you record on study goals will be recorded in
your browser, using a feature called
<a target="_blank" href="https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage">local storage</a>.
This means they should persist after closing the tab or the browser, unless you deliberately clear local storage
(or your browser is set to clear it automatically, e.g. when closed). 
</p>

<h2>Things to Know About Recording Notes in the Browser</h2>

<h3>Per-User Recording</h3>
<p>
If you enable browser recording while logged into Proofscape, then your notes will be recorded under your username.
This means that, if you share your computer with another user, you will each see only your own checkmarks and notes
displayed in the ISE, as long as you are logged in.
</p>
<p>
If you enable browser recording while <i>not</i> logged into Proofscape, then your notes will be recorded under an
"anonymous user".
</p>

<h3>Visible to Any User of Your Computer</h3>
<p>
If you choose to record notes in the browser, your notes will NOT be private, in the sense that anyone who uses your
computer would be able to read them (with a little effort), even when you are not logged into Proofscape.
</p>

<h3>Easy to Delete</h3>
<p>
Notes are recorded in the browser using something called
<a target="_blank" href="https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage">local storage</a>.
Just as you can delete cookies in your browser, you can delete local storage.
</p>
<p>
Different browsers (Firefox, Chrome, etc.) behave differently, but in some cases clearing your cookies will also
clear local storage.
</p>
<p>
If you clear local storage, you will erase ALL recorded notes, not just for you but also for any
other Proofscape users who use your browser. This cannot be undone.
</p>
<p>
If you want to erase just your own recorded notes (not those of any other Proofscape users who may use your browser),
use the "Erase Browser Notes" option in the "Study" menu, while logged in.
</p>

<h3>Activated on a Per-Browser Basis</h3>
<p>
When you activate browser recording in the Proofscape ISE, the setting that says "record my notes in local storage" is
itself stored in local storage!
</p>
<p>
This means that if you log into the Proofscape ISE on another computer, or even in another browser on the same computer,
your setting will not be in effect there.
</p>
<p>
This also means that the setting will go away if you clear local storage via your browser's control panel (for you and
for any other Proofscape users who may use your browser).
</p>
</div>
`;

const disableBnrHtml = `
<h2>Are you sure you want to disable recording of notes in the browser?</h2>
<p>
As long as recording is disabled, changes you make to your in-browser notes will not persist after you close
the current browser tab.
</p>
`;

const clearBnrHtml = `
<h2>Are you sure you want to erase all in-browser notes and checkmarks for the current user?</h2>
<p>
This cannot be undone.
</p>
`;

/* versionString: string giving version number of PISE
 * agreementsHtml: HTML containing any desired links to ToS etc.
 * extraSoftware: array of objects passable to `makeSoftwareTableRow()`
 * notices: array of strings giving license notices
 */
function aboutIseHtml(versionString, agreementsHtml, extraSoftware, notices) {
    let extraSoftwareTableRows = '';
    for (let info of extraSoftware) {
        extraSoftwareTableRows += makeSoftwareTableRow(info) + '\n';
    }

    let noticesHtml = '';
    if (notices.length) {
        noticesHtml += '<hr>\n<h2>Notices</h2>\n<hr>\n';
        for (let notice of notices) {
            noticesHtml += `<pre>\n${notice}\n</pre>\n<hr>\n`;
        }
    }

    return `
<div class="aboutIseDialog iseDialogContentsStyle01">
<div class="pise-logo"></div>
<div class="pise-title">Proofscape Integrated Study Environment</div>
<div class="pise-version">${versionString}</div>
<div class="pise-copyright">
  Copyright (c) 2018-2023
  <a class="external" target="_blank=" href="https://proofscape.org">Proofscape</a>
  Contributors
</div>
<div class="pise-legal">${agreementsHtml}</div>
<div class="pise-blurb">
This is an open-source project, built on the following components (scroll for more):
</div>
<div class="pise-software-table-wrapper">
<table class="pise-software-table">
<thead>
<tr><td>Software</td><td>License</td></tr>
</thead>
<tbody>
${softwareTableRows}
${extraSoftwareTableRows}
</tbody>
</table>
${noticesHtml}
</div>
</div>
`;
}

const restartSymPyConfirmationHtml = `
<div class="iseDialogContentsStyle01 iseDialogContentsStyle02">
<h2>Restart SymPy?</h2>
<p>
<b>BEFORE RESTARTING:</b> If you have an open example widget that caused
SymPy to hang, either <i>close that annotation</i>, or
<i>change one or more parameters</i>
to values that do <i>not</i> cause a hang.
</p>
<p>
Otherwise the exact same evaluation
will be attempted as soon as SymPy restarts, and it will hang again!
</p>
</div>
`;

const aboutSymPyEngineHtml = `
<div class="iseDialogContentsStyle01 iseDialogContentsStyle02 sympyEngineDialogStyle">
<h2>SymPy math engine</h2>
<p>
All mathematical calculations taking place in example explorers in PISE
are carried out by <a target="_blank" class="external" href="https://sympy.org">SymPy</a>,
an open-source computer algebra system written entirely in Python.
</p>
<p>
SymPy runs in your browser, thanks to
<a target="_blank" class="external" href="https://pyodide.org">Pyodide</a>.
</p>
</div>
`;

function hostingRequestHtml(prpoHtml) {
    return `
<div class="iseDialogContentsStyle01 iseDialogContentsStyle02 hostingRequestDialog">
<h2>Request Hosting</h2>
<p>
Have a Proofscape repo you'd like us to host?
</p>
<p>
Tell us the repopath and version.
We'll review the request, and get in touch.
</p>
<table>
<tbody>
<tr>
<td><span class="row-title">Repo:</span></td>
<td>
<span class="host-segment">
</span>
<span class="dot">.</span>
<span class="owner-segment">
  <select name="owner">
  </select>
</span>
<span class="dot">.</span>
<span class="repo-segment">
  <input name="repo" type="text" placeholder="name of repo"/>
</span>
</td>
</tr>
<tr>
<td><span class="row-title">Version:</span></td>
<td>
<input name="version" type="text" placeholder="vM.m.p"/>
</td>
</tr>
</tbody>
</table>
<div class="sec-title">Comments:<span class="remChars">(<span class="charCount"></span> chars remaining)</span></div>
<textarea name="comments" rows="6" maxlength="512"></textarea>
<div>
<p>
NOTE: Your email address will be sent to the reviewers, so that they
can get in touch with you directly.${prpoHtml}
</p>
</div>
</div>
`;
}

const userSettingsHtml = `
<div class="iseDialogContentsStyle01 iseDialogContentsStyle02 userSettingsDialog">
<!-- BASIC INFO -->
<div class="section">
<h3>Basic info</h3>
<table>
<tbody>
<tr>
<td><b>Username:</b><span class="fillIn username"></span></td>
<td><b>Email:</b><span class="fillIn email"></span></td>
</tr>
<tr>
<td class="helpText">
The first segment of your username reflects the OAuth provider
under which you logged in. The second segment is your username
with them.
</td>
<td class="helpText">
We always use the primary, verified email address you have on
record with your OAuth provider. We update it each time you log in. 
</td>
</tr>
<tr class="orgRow">
<td><b>Organizations:</b><span class="fillIn orgList"></span></td>
</tr>
<tr class="orgRow">
<td class="helpText">
If you chose to have us check organization ownership when you logged in,
we list here the organizations you own, at your OAuth provider.
</td>
</tr>
</tbody>
</table>
</div>
<!-- DATA EXPORT -->
<div class="section">
<h3>Data export</h3>
<table>
<tbody>
<tr>
<td><a href="#" class="dialogButton exportNotesButton">Export Server-Side Study Notes</a></td>
<td><a href="#" class="dialogButton exportAcctButton">Export All User Account Info</a></td>
</tr>
<tr>
<td class="helpText">
If you have opted into server-side note recording, you can export any notes
we have recorded for you. They'll download in a machine-readable JSON file.
</td>
<td class="helpText">
You can export all account info we have for you, <i>including</i> any server-side
notes we may have recorded for you. It all downloads together in a machine-readable
JSON file. 
</td>
</tr>
</tbody>
</table>
</div>
<!-- DANGER ZONE -->
<div class="finalSection">
<h3>Danger Zone</h3>
<table>
<tbody>
<tr>
<td><a href="#" class="dangerLink deleteNotesButton">Delete Server-Side Study Notes...</a></td>
<td><a href="#" class="dangerLink deleteAcctButton">Delete All User Account Info...</a></td>
</tr>
<tr>
<td class="helpText">
If you decide you want us to delete any and all server-side
notes we may have recorded for you, you can do that here.
</td>
<td class="helpText">
If you want us to delete your entire account, <i>including</i> any server-side
notes we may have recorded for you, you can do that here.
You will also be logged out immediately.
</td>
</tr>
</tbody>
</table>
</div>
`;

const deleteSsnrConfirmDialog = `
<div class="irreversibleActionConfirmDialog">
<h2>Delete All Server-Side Notes</h2>
<div>
<p>
You are asking us to irreversibly delete any and all notes we may have
recorded for you on the server, using server-side note recording.
</p>
<p>
If you have not done so already, you may want to close this dialog and export
your notes, before you ask us to delete them.
</p>
<p>
If you go ahead, your notes will be permanently deleted.
</p>
<p>
THIS CANNOT BE UNDONE.
</p>
</div>
<div class="input">
<p>
To confirm that you really want us to delete all your notes,
type <span class="monospace">DeleteAllMyNotes</span> (no spaces)
in the box below.
</p>
<input name="confirmation" type="text" placeholder="DeleteAllMyNotes"/>
</div>
<div class="button">
<a href="#" class="dialogButton dangerButton dangerButtonDisabled">Delete Server-Side Study Notes</a>
</div>
</div>
`;

const deleteUserAcctConfirmDialog = `
<div class="irreversibleActionConfirmDialog">
<h2>Delete User Account</h2>
<div>
<p>
You are asking us to irreversibly delete your entire account with us.
This includes any and all notes we may have
recorded for you on the server, using server-side note recording.
It also includes any hosting permissions that may have been granted
for your username, and/or organizations you own.
</p>
<p>
If you have not done so already, you may want to close this dialog and export
all your account info, before you ask us to delete it.
</p>
<p>
Hosting permissions, in particular, cannot be restored at a later date,
except by once again going through the hosting request process.
</p>
<p>
If you go ahead, all your user account info will be permanently deleted.
</p>
<p>
THIS CANNOT BE UNDONE.
</p>
</div>
<div class="input">
<p>
To confirm that you really want us to delete your user account,
type <span class="monospace">DeleteMyAccount</span> (no spaces)
in the box below.
</p>
<input name="confirmation" type="text" placeholder="DeleteMyAccount"/>
</div>
<div class="button">
<a href="#" class="dialogButton dangerButton dangerButtonDisabled">Delete All User Account Info</a>
</div>
</div>
`;

return MenuManager;

});

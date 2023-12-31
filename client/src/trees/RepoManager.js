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

import { BuildTreeManager } from "./BuildTreeManager";
import { FsTreeManager } from "./FsTreeManager";
import { NodeExpandTask } from "../delayed";
import { util as iseUtil } from "../util";

const dojo = {};

define([
    "dojo/query",
    "dojo/on",
    "dijit/focus",
    "dojo/dom-construct",
    "dijit/layout/BorderContainer",
    "dijit/layout/LayoutContainer",
    "dijit/layout/TabContainer",
    "dijit/layout/ContentPane",
    "dijit/ConfirmDialog",
    "dojo/NodeList-traverse",
    "dojo/NodeList-manipulate",
], function(
    query,
    on,
    focus,
    domConstruct,
    BorderContainer,
    LayoutContainer,
    TabContainer,
    ContentPane,
    ConfirmDialog
) {
    dojo.query = query;
    dojo.on = on;
    dojo.focus = focus;
    dojo.domConstruct = domConstruct;
    dojo.BorderContainer = BorderContainer;
    dojo.LayoutContainer = LayoutContainer;
    dojo.TabContainer = TabContainer;
    dojo.ContentPane = ContentPane;
    dojo.ConfirmDialog = ConfirmDialog;
});

export class RepoManager {

    constructor(homeDiv, ISE_state) {
        this.hub = null;
        this.div = homeDiv;

        this.tabContainer = null;
        this.buildTab = null;
        this.filesystemTab = null;
        this.buildDiv = null;
        this.fsDiv = null;
        this.buildLayout(this.div, ISE_state);

        this.buildMgr = new BuildTreeManager(this.buildDiv);
        this.fsMgr = new FsTreeManager(this.fsDiv);
    }

    activate() {
        // Seem to need to call `resize` on the sidebar in order to get our BorderContainer
        // layout to display properly.
        this.hub.appLayout.sidebar.resize();

        this.hub.socketManager.on('repoIsBuilt', this.noteRepoIsBuilt.bind(this));
        this.hub.socketManager.on('repoIsPresent', this.noteRepoIsPresent.bind(this));

        this.buildMgr.hub = this.hub;
        this.buildMgr.activate();

        this.fsMgr.hub = this.hub;
        this.fsMgr.activate();
    }

    buildLayout(homeDiv, ISE_state) {
        const mainContainer = new dojo.BorderContainer({
            design: "headline",
        }, homeDiv);

        // We put the input box inside a (deactivated) form so the browser might remember past inputs.
        // (At least this works on Chrome.)
        const repoInputWidget = dojo.domConstruct.toDom(`
            <div id="repoInput">
                <form onsubmit="return false;">
                    <input id="repoInputText" type="text" placeholder="host.user.repo@version" spellcheck="false"/>
                    <span id="repoInputButton">+</span>
                </form>
            </div>
        `);
        const repoInputPane = new dojo.ContentPane({
            region: "top",
            id: 'repoInputPane',
            "class": "edgePanel",
            content: repoInputWidget,
        });
        mainContainer.addChild(repoInputPane);

        const mgr = this;
        dojo.on(dojo.query('#repoInputButton'), 'click', this.openRepoFromInputWidget.bind(this));
        dojo.on(dojo.query('#repoInputText'), 'keyup', function(e){
            if (e.key === "Enter") mgr.openRepoFromInputWidget();
        });

        const tabArea = new dojo.LayoutContainer({
            region: "center",
            gutters: false,
        });
        mainContainer.addChild(tabArea);

        this.tabContainer = new dojo.TabContainer({
            region: "center",
            tabPosition: "top",
        });
        tabArea.addChild(this.tabContainer);

        const selectedTab = (ISE_state.trees || {}).tab;

        this.buildTab = new dojo.ContentPane({
            region: "center",
            title:"Structure",
            id: "buildTab",
            closable: false,
            selected: selectedTab === 'build',
        });
        this.tabContainer.addChild(this.buildTab);

        this.filesystemTab = new dojo.ContentPane({
            region: "center",
            title:"File System",
            id: "fsTab",
            closable: false,
            selected: selectedTab === 'fs',
        });
        this.tabContainer.addChild(this.filesystemTab);

        this.buildDiv = dojo.domConstruct.create("div", {"id": "buildPanel", "class": "treePanel"});
        this.buildTab.set('content', this.buildDiv);

        this.fsDiv = dojo.domConstruct.create("div", {"id": "fsPanel", "class": "treePanel"});
        this.filesystemTab.set('content', this.fsDiv);

        mainContainer.startup();
    }

    openRepoFromInputWidget() {
        const input = dojo.query('#repoInputText')
        const repopathv = input.val();
        // Clear the input box, and remove the focus.
        input.val('');
        dojo.focus.curNode && dojo.focus.curNode.blur();

        // Catch malformed input and alert the user.
        try {
            iseUtil.parseTailVersionedLibpath(repopathv);
        } catch (e) {
            this.hub.errAlert(e.message);
            return;
        }

        this.openRepo({
            repopathv: repopathv,
            // If user omits version, let server decide for
            // WIP or latest, depending on its config:
            defaultVersion: null,
        });
    }

    selectTab(tabName) {
        if (tabName === 'fs') {
            this.tabContainer.selectChild(this.filesystemTab);
        } else if (tabName === 'build') {
            this.tabContainer.selectChild(this.buildTab);
        }
    }

    getSelectedTabName() {
        const sel = this.tabContainer.selectedChildWidget;
        if (sel === this.filesystemTab) {
            return 'fs';
        }
        if (sel === this.buildTab) {
            return 'build';
        }
        return null;
    }

    /* Open a proofscape repository.
     *
     * @param repopathv: tail-versioned libpath of the repo to be loaded. In fact version may
     *   be omitted (use a pure libpath), in which case use the defaultVersion arg (see below).
     * @param doBuild: boolean, saying whether you want to build if necessary
     * @param doClone: boolean, saying whether you want to clone if necessary
     * @param fail_silently: boolean; if true, and repo cannot be opened, suppress
     *   associated error dialogs.
     * @param ignoreBuildTree: boolean; if true, we do not (re)load the build tree
     *   even if the server provides it.
     * @param ignoreFsTree: boolean; if true, we do not (re)load the filesystem
     *   tree, even if the server provides it.
     * @param defaultVersion: version to request if repopathv is a pure libpath with no
     *   version. Defaults to "WIP". Set to null to let server decide which version you
     *   want (WIP or latest numbered, depending on server config).
     * @return: promise that resolves with the _immediate_ response from the server.
     *   Note that this is distinct from any delayed response that may come later,
     *   if the request results in any asynchronous processing.
     */
    openRepo({repopathv, doBuild, doClone, fail_silently, ignoreBuildTree, ignoreFsTree, defaultVersion = "WIP"}) {
        let {libpath, version} = iseUtil.parseTailVersionedLibpath(repopathv, {
            defaultVersion: defaultVersion,
        });
        const repopath = libpath;
        const query = { repopath: repopath, doBuild: doBuild + "", doClone: doClone + "" };
        if (version) {
            query.vers = version;
        }
        return this.hub.socketManager.splitXhrFor('loadRepoTree', {
            query: query,
            handleAs: 'json',
        }).then(parts => {
            const resp = parts.immediate;
            if (parts.delayed) {
                parts.delayed.then(this.hub.errAlert3.bind(this.hub));
            }
            if (this.hub.errAlert3(resp)) return resp;
            const success = resp.fs_model || resp.model || resp.will_clone || resp.will_build;
            // Receive the version number the server decided was being loaded.
            version = resp.version;
            if (resp.fs_model && !ignoreFsTree) {
                this.fsMgr.loadTree(resp);
                if (!resp.model) {
                    this.selectTab('fs');
                }
            }
            if (resp.model && !ignoreBuildTree) {
                this.buildMgr.loadTree({
                    repopath: resp.repopath,
                    version: version,
                    model: resp.model,
                });
                if (!resp.fs_model) {
                    this.selectTab('build');
                }
            }
            if (!success) {
                this.handleOpenRepoFailures(repopath, version, resp, fail_silently);
            }
            return resp;
        });
    }

    handleOpenRepoFailures(repopath, version, resp, fail_silently=false) {
        if (fail_silently) return;
        if (resp.privileged) {
            let doClone = false;
            let doBuild = false;
            let msg;
            let question = '';
            if (resp.present) {
                msg = `<p>Repo <span class="monospace">${repopath}</span> has not been built at <span class="monospace">${version}</span> on this server.</p>`;
                question = `<p>Do you want to build?</p>`;
                doBuild = true;
            } else {
                msg = `<p>Repo <span class="monospace">${repopath}</span> is not present on this server.</p>`;
                if (resp.clonable) {
                    if (version === "WIP") {
                        question = `<p>Do you want to clone the repo?</p>`;
                        doBuild = false;
                    } else {
                        question = `<p>Do you want to clone the repo and build at <span class="monospace">${version}</span>?</p>`;
                        doBuild = true;
                    }
                    doClone = true;
                } else {
                    this.hub.errAlert(msg);
                    return;
                }
            }
            msg += question;
            if (doBuild && version !== "WIP") {
                msg += `<p>WARNING: once a numbered release has been built, this CANNOT BE UNDONE.</p>`
            }
            const mgr = this;
            const dlg = new dojo.ConfirmDialog({
                title: 'Repo is not ready',
                content: msg,
                onExecute: function() {
                    mgr.openRepo({
                        repopathv: iseUtil.lv(repopath, version),
                        doBuild: doBuild,
                        doClone: doClone,
                    });
                },
            });
            dlg.show();
        } else {
            let msg = '';
            const ownership_msg = '<p>If you own this repo, you may log in to demonstrate ownership.</p>';
            if (version === "WIP") {
                if (this.hub.allowWIP) {
                    // If the server allows WIP, but you don't have build permission, it must be
                    // because you don't appear to own the repo.
                    msg += '<p>Repos you do not own cannot be opened at work-in-progress.</p>';
                    msg += ownership_msg;
                } else {
                    msg += '<p>This server does not allow repos to be opened at work-in-progress.</p>';
                }
            } else {
                const nli = 'not_logged_in'
                const hosting = (resp.hosting || nli);
                // Note: I don't know about other IDEs, but in WebStorm, most of the following cases appear grayed-out,
                // even though they are actual code! Do not delete!
                switch (hosting) {
                    case nli:
                    case "DOES_NOT_OWN":
                        msg += `<p>Repo <span class="monospace">${repopath}</span> has not been built at <span class="monospace">${version}</span> on this server.</p>`;
                        msg += ownership_msg;
                        break;
                    case "MAY_NOT_REQUEST":
                    case "DENIED":
                        msg += `<p>Repo <span class="monospace">${repopath}</span> at <span class="monospace">${version}</span> cannot be built on this server.</p>`;
                        break;
                    case "MAY_REQUEST":
                        msg += `<p>If you wish to build <span class="monospace">${repopath}</span> at <span class="monospace">${version}</span>, you can request hosting,`;
                        msg += ` using the "Request Hosting" option under the user menu.</p>`;
                        break;
                    case "PENDING":
                        msg += `<p>It looks like a request to build <span class="monospace">${repopath}</span> at <span class="monospace">${version}</span> is pending.</p>`;
                        msg += `<p>We aim to be in touch as soon as possible.</p>`;
                        break;
                    default:
                        // This should not happen.
                        msg += `<p>Unable to determine hosting status for <span class="monospace">${repopath}</span> at <span class="monospace">${version}</span> at this time.</p>`;
                        msg += `<p>Please try again later.</p>`;
                }

            }
            this.hub.errAlert(msg);
        }
    }

    noteRepoIsPresent({ repopath }) {
        // `repoisPresent` events are fired only after cloning. So the repo couldn't
        // already be open, and there's no question of reloading. We just open it.
        // Also we must be trying to load @WIP, since if we were trying to load a
        // numbered release then the server would also build after cloning, and
        // it would suppress the `repoIsPresent` event in favor of a `repoIsBuilt`
        // event.
        const repopathv = iseUtil.lv(repopath, "WIP");
        this.openRepo({
            repopathv: repopathv,
        });
    }

    noteRepoIsBuilt({ repopath, version }) {
        const repopathv = iseUtil.lv(repopath, version);
        if (this.buildMgr.repoIsOpen(repopathv)) {
            this.reloadBuildTree(repopathv);
        } else {
            this.openRepo({
                repopathv: repopathv,
            });
        }
    }

    closeRepo(repopath, version = "WIP") {
        const repopathv = iseUtil.lv(repopath, version);
        this.buildMgr.closeRepo(repopathv);
        this.fsMgr.closeRepo(repopath);
    }

    /* Describe the set of open repos.
     *
     * @return: opject of the form: {
     *     tab: selectedTabName,
     *     trees: {
     *          repopathv1: {
     *              expand: {
     *                  fsNodeIds: [ array of filesystem node ids ],
     *                  buildNodeIds: [ array of build node ids ],
     *              }
     *          },
     *          repopathv2: ...
     *     }
     * }
     *
     * However: For repopathv's at numbered releases, the `fsNodeIds` property
     * is not just empty but _undefined_. This is more appropriate since for
     * numbered releases we _cannot_ open filesystem trees at all.
     */
    describeState() {
        const build = this.buildMgr.findEssentialExpandedIds();
        const fs = this.fsMgr.findEssentialExpandedIds();
        const trees = {};
        // repos @WIP:
        for (let [repopath, fsNodeIds] of fs) {
            const repopathv = iseUtil.lv(repopath, "WIP");
            const info = {
                expand: {
                    fsNodeIds: fsNodeIds,
                    buildNodeIds: [],
                }
            };
            if (build.has(repopathv)) {
                info.expand.buildNodeIds = build.get(repopathv);
                // Delete this entry now, so that later we're left
                // with only numbered releases.
                build.delete(repopathv);
            }
            trees[repopathv] = info;
        }
        // numbered releases:
        for (let [repopathv, buildNodeIds] of build) {
            trees[repopathv] = {
                expand: {
                    buildNodeIds: buildNodeIds,
                }
            };
        }
        return {
            tab: this.getSelectedTabName(),
            trees: trees,
        };
    }

    /* Try to restore the set of open repo trees to a given state.
     *
     * @param state: an object of the kind returned by our `describeState()` method.
     * @return: promise that resolves with (possibly empty) array of tail-versioned repopaths
     *   of those repos that were not ready to load immediately, but which are being built now
     *   by the server, and for which a `repoIsBuilt` event should later arrive.
     */
    restoreState(state) {
        this.selectTab(state.tab);
        const trees = state.trees || {};
        const repopathvs = Array.from(Object.keys(trees));
        const jobs = repopathvs.map(repopathv => this.openRepo({
            repopathv: repopathv,
            // Mustn't build numbered releases automatically, since that can't be undone.
            // Don't bother building unless want to expand at least one build node.
            doBuild: repopathv.endsWith('@WIP') && trees[repopathv].expand.buildNodeIds.length > 0,
            fail_silently: true,
        }));
        return Promise.all(jobs).then(responses => {
            const delayed = [];
            let i = 0;
            for (let repopathv of repopathvs) {
                const resp = responses[i++];
                const toExpand = trees[repopathv].expand;
                // Note: even though we're never passing `doClone` above, it's still possible that we might
                // require delayed node expansion in an FS tree because of demo repos.
                const now = resp.fs_model || resp.model;
                const later = resp.will_build || resp.will_make_demo;
                if (now || later) {
                    const task = new NodeExpandTask(this.hub, repopathv, toExpand);
                    task.activate();
                    if (later) {
                        delayed.push(repopathv);
                    }
                }
            }
            return delayed;
        });
    }

    /* Check whether (and to what extent) a repo is currently loaded,
     *
     * @params repopathv, repopath: You need only pass one of these. If you
     *   are interested in a numbered release, then you must pass `repopathv`;
     *   otherwise (i.e. if interested in the repo @WIP) either one will do.
     * @return: object of the form {
     *   fs: <bool> true iff the filesystem tree for this repo is loaded,
     *   build: <bool> true iff the build tree for this repo is loaded
     * }
     */
    repoIsLoaded({ repopathv, repopath }) {
        repopathv = repopathv || iseUtil.lv(repopath, "WIP");
        repopath = repopath || iseUtil.parseTailVersionedLibpath(repopathv).libpath;
        return {
            fs: this.fsMgr.repoIsOpen(repopath),
            build: this.buildMgr.repoIsOpen(repopathv),
        };
    }

    expandNodesPlusAncestors(repopathv, toExpand) {
        if (toExpand.fsNodeIds) {
            const repopath = iseUtil.parseTailVersionedLibpath(repopathv).libpath;
            this.fsMgr.expandNodesPlusAncestors(repopath, toExpand.fsNodeIds);
        }
        if (toExpand.buildNodeIds) {
            this.buildMgr.expandNodesPlusAncestors(repopathv, toExpand.buildNodeIds);
        }
    }

    reloadBuildTree(repopathv) {
        const itemIds = this.buildMgr.findEssentialExpandedIds([repopathv]).get(repopathv);
        this.buildMgr.closeRepo(repopathv);
        return this.openRepo({
            repopathv: repopathv,
            ignoreFsTree: true,
        }).then(resp => {
            if (resp.model) {
                return this.buildMgr.expandNodesPlusAncestors(repopathv, itemIds);
            }
        })
    }

    reloadFsTree(repopath) {
        const itemIds = this.fsMgr.findEssentialExpandedIds([repopath]).get(repopath);
        this.fsMgr.closeRepo(repopath);
        return this.openRepo({
            repopathv: iseUtil.lv(repopath, "WIP"),
            ignoreBuildTree: true,
        }).then(resp => {
            if (resp.fs_model) {
                return this.fsMgr.expandNodesPlusAncestors(repopath, itemIds);
            }
        })
    }

    reloadAllFsTrees() {
        const repopaths = this.fsMgr.getAllOpenTreeUids();
        for (let repopath of repopaths) {
            this.reloadFsTree(repopath);
        }
    }

}

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


/* Abstract base class for tasks whose readiness awaits one or more
 * trees being loaded in the BuildTreeManager.
 *
 * To make use of any subclass, users should make a new instance, and
 * then call its `activate()` method. That is all.
 *
 * At the time that `activate()` is called, we check to see if we are
 * _already_ ready to execute, and if so the task is carried out immediately.
 * Otherwise, at that time we register as a listener on the relevant
 * `treeLoaded` event of the BuildTreeManager.
 *
 * In that case the task will execute when on handling a `treeLoaded` event
 * it finds that it is ready. Then it will unregister itself as event listener.
 * Provided users have not made any other references to the object,
 * it will then be unreachable and will be garbage collected.
 */
class AwaitTreeTask {

    constructor(hub) {
        this.hub = hub;
        this.myCallback = this.noteTreeLoaded.bind(this);
        this.isRegistered = false;
    }

    activate() {
        const alreadyDone = this.attempt();
        if (!alreadyDone) {
            this.register();
        }
    }

    register() {
        this.hub.repoManager.buildMgr.on('treeLoaded', this.myCallback);
        this.hub.repoManager.fsMgr.on('treeLoaded', this.myCallback);
        this.isRegistered = true;
    }

    unregister() {
        if (this.isRegistered) {
            this.hub.repoManager.buildMgr.off('treeLoaded', this.myCallback);
            this.hub.repoManager.fsMgr.off('treeLoaded', this.myCallback);
        }
    }

    noteTreeLoaded(event) {
        this.attempt();
    }

    attempt() {
        if (this.isReady()) {
            this.execute();
            this.unregister();
            return true;
        }
        return false;
    }

    /* Subclasses must override.
     * This is where they decide if they are ready yet.
     *
     * @return: boolean saying whether this task is ready to execute.
     */
    isReady() {
        return true;
    }

    /* Subclasses must override.
     * This is where they carry out their task.
     */
    execute() {
    }

}

export class NodeExpandTask extends AwaitTreeTask {

    constructor(hub, repopathv, toEpand) {
        super(hub);
        this.repopathv = repopathv;
        this.toExpand = toEpand;
    }

    isReady() {
        const loaded = this.hub.repoManager.repoIsLoaded({repopathv: this.repopathv});
        return (
            (loaded.fs || !this.toExpand.fsNodeIds) &&
            (loaded.build || !this.toExpand.buildNodeIds)
        );
    }

    execute() {
        this.hub.repoManager.expandNodesPlusAncestors(this.repopathv, this.toExpand);
    }

}

export class ContentLoadTask extends AwaitTreeTask {

    constructor(hub, repopathvs, content) {
        super(hub);
        this.repopathvs = repopathvs;
        this.content = content;
    }

    isReady() {
        // TODO:
        //  Really the content to be loaded should be organized by repopathv,
        //  so that we can delay only as really necessary.
        return this.repopathvs.every(repopathv => {
            return this.hub.repoManager.buildMgr.repoIsOpen(repopathv);
        });
    }

    execute() {
        this.hub.loadContentByDescription(this.content);
    }

}

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

const ise = {};

define([
    "ise/errors",
], function(
    errors
) {
    ise.errors = errors;
});


export const BUILD_JOB_TYPES = {
    EDIT_MGR_BUILD: "EDIT_MGR_BUILD",
    REPO_MGR_OPEN_REPO: "REPO_MGR_OPEN_REPO",
};


/* A class to manage a repo build, along with possible builds of missing dependencies.
 */
class BuildManager {

    constructor(repoManager, initialJob) {
        this.repoManager = repoManager;
        this.hub = this.repoManager.hub;
        this.manageJob(initialJob);

        // Set of repopathvs the user has already ok'ed:
        this.okedRepopathvs = new Set();

        // Stack of job defns still to be done:
        this.jobDefnStack = [];

        // Flag for user to dismiss further confirmation dialogs:
        this.stopAsking = false;
    }

    /* Modify a job description, so that this `BuildManager` will manage missing deps for it.
     */
    manageJob(job) {
        job.buildMgrCallback = this.handleManagedBuildResponse.bind(this);
    }

    /* This is the callback in which we handle the response from a managed build.
     */
    handleManagedBuildResponse({response, jobDefn}) {
        const isMissingDepsErr = (
            response.err_lvl === ise.errors.serverSideErrorCodes.REPO_DEPENDENCIES_NOT_BUILT
        );
        if (isMissingDepsErr) {
            this.handleMissingDeps(response, jobDefn);
        } else if (!this.hub.errAlert3(response)) {
            this.doNextJob();
        }
    }

    async handleMissingDeps(response, jobDefn) {
        const {err_msg, err_info} = response;

        // First determine the set of new repopathvs, so we can see if we need to ask the user,
        // or if they have already all been ok'ed.
        // While doing this, it's convenient to also build the array of new jobs, even though
        // we might wind up not doing them.
        let anythingNew = false;
        const newRepopathvs = new Set();
        // The job that failed has to be repeated:
        const newJobDefns = [jobDefn];
        const newMissingDeps = [];
        for (const md of err_info) {
            const mdJobDefn = this.makeJobDefnForMissingDep(md);
            newJobDefns.push(mdJobDefn);

            const repopathv = mdJobDefn.jobArgs.repopathv;
            newRepopathvs.add(repopathv);

            if (!this.okedRepopathvs.has(repopathv)) {
                anythingNew = true;
                newMissingDeps.push(md);
            }
        }

        let goAhead = true;

        if (anythingNew && !this.stopAsking) {
            const lines = err_msg.split('\n');
            let choiceHtml = '';
            for (const line of lines) {
                if (line.startsWith('<li>')) {
                    // Skip repopathv's that have already been ok'ed.
                    const rpv = line.slice(4).split(":")[0];
                    if (this.okedRepopathvs.has(rpv)) {
                        continue;
                    }
                }
                choiceHtml += '\n' + line;
            }

            let action = 'build these dependencies';
            for (const md of newMissingDeps) {
                if (!md.present) {
                    action = 'clone and/or build these dependencies as necessary';
                    break;
                }
            }
            choiceHtml += `<p>Do you want to ${action}?</p>`;

            const dismissalName = 'auto-deps-stop-asking';
            choiceHtml += `
                <div>
                    <label>
                        <input type="checkbox" name="${dismissalName}">
                        If further missing dependencies are discovered, build them all without asking again.
                    </label>
                </div>`;

            const choiceResult = await this.hub.choice({
                title: "Missing Dependencies",
                content: choiceHtml,
            });

            const cb = choiceResult.dialog.domNode.querySelector(`input[name="${dismissalName}"]`);
            if (cb?.checked) {
                this.stopAsking = true;
            }

            goAhead = choiceResult.accepted;
        }

        if (goAhead) {
            for (const rpv of newRepopathvs) {
                this.okedRepopathvs.add(rpv);
            }

            // Want to add all the new jobs to the top of the jobs stack, but do not want any repeats,
            // so first remove any of these if they already exist.
            this.jobDefnStack = this.jobDefnStack.filter(
                j => (
                    // There can be at most one EDIT_MGR_BUILD job (it's always at the base of the stack),
                    // and it always stays.
                    j.jobType === BUILD_JOB_TYPES.EDIT_MGR_BUILD ||
                    // For existing REPO_MGR_OPEN_REPO jobs, we want to keep them only if we're not about to
                    // repeat them on the top of the stack.
                    (
                        j.jobType === BUILD_JOB_TYPES.REPO_MGR_OPEN_REPO &&
                        !newRepopathvs.has(j.jobArgs.repopathv)
                    )
                )
            ).concat(newJobDefns);

            //console.debug('BuildManager updated job stack:', this.jobDefnStack.slice());

            this.doNextJob();
        }
    }

    makeJobDefnForMissingDep(md) {
        const repopathv = `${md.repopath}@${md.version}`;
        return {
            jobType: BUILD_JOB_TYPES.REPO_MGR_OPEN_REPO,
            jobArgs: {
                repopathv,
                ignoreBuildTree: true,
            },
        };
    }

    doNextJob() {
        const jobDefn = this.jobDefnStack.pop();
        if (jobDefn) {
            const args = jobDefn.jobArgs;
            this.manageJob(args);
            switch (jobDefn.jobType) {
                case BUILD_JOB_TYPES.REPO_MGR_OPEN_REPO:
                    // Job is free to build and clone as necessary:
                    Object.assign(args, {
                        doBuild: true, doClone: true,
                    });
                    this.repoManager.openRepo(args);
                    break;
                case BUILD_JOB_TYPES.EDIT_MGR_BUILD:
                    this.hub.editManager.build(args);
                    break;
            }
        }
    }

}


/* Set a "job" to be "managed," which means that attempts will be
 * made to (with the user's go-ahead) recursively build any missing dependencies.
 *
 * At this time there are only two different "job types" that can be managed; namely,
 * calls to `EditManager.build()` and `RepoManager.openRepo()`. Each of these methods
 * takes a single `args` object, in which there is one optional arg called `buildMgrCallback`.
 * This function will automatically set that arg.
 *
 * :param repoManager: the `RepoManager` singleton.
 * :param jobArgs: args object in which the `buildMgrCallback` arg is to be set.
 */
export function manageBuildJob(repoManager, jobArgs) {
    // Just forming a BuildManager sets it up to manage the job.
    // Callers will often have no need of the return value.
    return new BuildManager(repoManager, jobArgs);
}

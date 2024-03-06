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

/* A class to manage a repo build, along with possible builds of missing dependencies.
 */
class BuildManager {

    constructor(repoManager, initialJob) {
        this.repoManager = repoManager;
        this.hub = this.repoManager.hub;
        this.manageJob(initialJob);
        this.jobs = [];
    }

    /* Modify an `openRepo()` job so that this `BuildManager` will manage missing deps for it.
     */
    manageJob(job) {
        job.buildMgrCallback = this.handleManagedBuildResponse.bind(this);
    }

    /* This is the callback in which we handle the response from a managed build.
     */
    handleManagedBuildResponse(response) {
        const isMissingDepsErr = (
            response.err_lvl === ise.errors.serverSideErrorCodes.REPO_DEPENDENCIES_NOT_BUILT
        );
        if (isMissingDepsErr) {
            this.handleMissingDeps(response);
        } else if (!this.hub.errAlert3(response)) {
            this.doNextJob();
        }
    }

    makeNewJob(repopathv, ignoreBuildTree) {
        const job = {
            repopathv: repopathv,
            // Happy to build and clone as necessary:
            doBuild: true, doClone: true,
            // After the build completes, say whether we want to actually load the tree view:
            ignoreBuildTree: ignoreBuildTree,
        };
        this.manageJob(job);
        return job;
    }

    async handleMissingDeps({err_msg, err_info, repopath, version, ignoreBuildTree}) {
        let choiceHtml = err_msg;
        choiceHtml += `<p>Do you want to clone and/or build these dependencies as necessary?</p>`;
        const choiceResult = await this.hub.choice({
            title: "Missing Dependencies",
            content: choiceHtml,
        });
        if (choiceResult.accepted) {
            const newRepopathvs = new Set();
            const newJobs = [];

            const repopathv = `${repopath}@${version}`;
            // In the job that replaces the one that failed, we want to replicate `ignoreBuildTree`:
            const job = this.makeNewJob(repopathv, ignoreBuildTree);
            newRepopathvs.add(repopathv);
            newJobs.push(job);

            for (const md of err_info) {
                const repopathv = `${md.repopath}@${md.version}`;
                // In all jobs to build dependencies, we set `ignoreBuildTree` to true:
                const job = this.makeNewJob(repopathv, true);
                newRepopathvs.add(repopathv);
                newJobs.push(job);
            }
            // Want to add all the new jobs to the top of the jobs stack, but do not want any repeats,
            // so first remove any of these if they already exist.
            this.jobs = this.jobs.filter(j => !newRepopathvs.has(j.repopathv)).concat(newJobs);
            this.doNextJob();
        }
    }

    doNextJob() {
        const job = this.jobs.pop();
        if (job) {
            this.repoManager.openRepo(job);
        }
    }

}


/* Set a repo build job to be "managed," which means that attempts will be
 * made to (with the user's go-ahead) recursively build any missing dependencies.
 *
 * :param repoManager: the `RepoManager` singleton.
 * :param job: object that will be passed to `RepoManager.openRepo()`, representing the
 *    initial build job, which is to be managed.
 */
export function manageBuildJob(repoManager, job) {
    // Just forming a BuildManager sets it up to manage the job.
    // Callers will often have no need of the return value.
    return new BuildManager(repoManager, job);
}

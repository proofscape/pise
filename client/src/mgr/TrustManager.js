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

/* Manages user trust settings for repos at versions.
 */
export class TrustManager {

    constructor(ISE_state) {
        this.hub = null;
        this.browserStorage = window.localStorage;

        this.canRecordTrustSettingsOnServer = !!ISE_state.userTrustRecordingAvailable;
        this.trustKeyPrefix = "pfsc:user:trust:";

        this.docsUrlPrefix = 'https://docs.proofscape.org/en/stable';
        // Useful in development:
        //this.docsUrlPrefix = 'http://localhost:8008';

        this.displayWidgetsDocsUrl = `${this.docsUrlPrefix}/ref/widgets/examp/disp.html`;
        this.piseConfigDocsUrl = `${this.docsUrlPrefix}/pise/advanced.html#configuration`;
    }

    async showTrustDialog(repopath, version, repoTrustedSiteWide) {
        const title = 'Trust settings';
        const dispWidgetsLink = `<a target="_blank" href="${this.displayWidgetsDocsUrl}">display widgets</a>`;
        const piseConfigLink = `<a target="_blank" href="${this.piseConfigDocsUrl}">PISE config</a>`;

        // The value of the passed `repoTrustedSiteWide` boolean was loaded along with the structure
        // or file system model, when the repo was loaded, and reports only on the site-wide
        // setting for the repo.
        if (repoTrustedSiteWide) {
            // In this case, the user can't override the site-wide setting, so instead of a choice
            // dialog, we display a merely informational dialog.
            const location = this.hub.OCA_version ? `in your ${piseConfigLink}` : 'at this website';
            const content = `<p>The repo ${repopath} is marked as trusted ${location},
                             so all of its ${dispWidgetsLink} run by default.</p>`;
            this.hub.alert({title, content});
        } else {
            const currentlyTrustedByUser = await this.checkPerUserTrustSetting(repopath, version);

            const innerContent = currentlyTrustedByUser ?
                `<h2>Repo is currently trusted.</h2>
                 <p>Do you want to revoke trust from <code>${repopath}@${version}</code>
                    and prevent its ${dispWidgetsLink} from running?</p>` :
                `<h2>Repo is currently untrusted.</h2>
                 <p>Do you want to trust <code>${repopath}@${version}</code>
                    and allow its ${dispWidgetsLink} to run?</p>`;

            const content = `<div class="iseDialogContentsStyle01">${innerContent}</div>`;

            const okButtonText = currentlyTrustedByUser ? 'Revoke trust' : 'Grant trust';

            const choiceResult = await this.hub.choice({
                title: title,
                content: content,
                okButtonText: okButtonText,
            });
            if (choiceResult.accepted) {
                const newTrustSetting = !currentlyTrustedByUser;
                await this.recordTrustSetting(repopath, version, newTrustSetting);
                await this.reloadPages(repopath, version);
            }
        }
    }

    /* Reload all open pages (Sphinx and anno) that belong to the given repopath@version,
     * and that contain one or more display widgets, thus allowing new trust settings to
     * take effect.
     */
    async reloadPages(repopath, version) {
        // Grab all existing display widgets belonging to the given repo@version.
        const libpathPrefix = repopath + '.';
        const disps = Array.from(this.hub.notesManager.widgets.values()).filter(
            w => w.origInfo.type === "DISP" && w.version === version && w.libpath.startsWith(libpathPrefix)
        );

        // Can a display widget import from one belonging to a different page?
        // Just in case that's possible, start by sorting.
        disps.sort((a, b) => a.compareByDependency(b));

        // Get all paneIds where these widgets appear.
        const paneIdsInOrder = [];
        const paneIdsSeenSoFar = new Set();
        for (const disp of disps) {
            for (const paneId of disp.panesById.keys()) {
                if (!paneIdsSeenSoFar.has(paneId)) {
                    paneIdsInOrder.push(paneId);
                    paneIdsSeenSoFar.add(paneId);
                }
            }
        }

        // Reload panels
        for (const paneId of paneIdsInOrder) {
            const viewer = this.hub.notesManager.getViewerForPaneId(paneId);
            await viewer.refresh();
        }
    }

    /* Record a trust setting for repopath@version.
     *
     * This is the high-level API method. It decides whether to record on the server,
     * or record locally.
     *
     * @param repopath: the repopath
     * @param version: the full version string
     * @param trusted: boolean, saying whether you want to trust or not
     * @return: boolean saying whether we made any change to existing records
     */
    async recordTrustSetting(repopath, version, trusted) {
        if (this.canRecordTrustSettingsOnServer) {
            const resp = await this.hub.xhrFor('setUserTrust', {
                query: {
                    repopath: repopath,
                    vers: version,
                    trusted: trusted + '',
                },
                handleAs: 'json',
            });
            if (this.hub.errAlert3(resp)) {
                return false;
            } else {
                return resp.made_change;
            }
        } else {
            return this.recordTrustSettingLocally(repopath, version, trusted);
        }
    }

    /* Check the user's trust setting for repopath@version.
     *
     * See also:
     *   checkCombinedTrustSetting()
     *   RepoManager.repoIsTrustedSiteWide()
     *
     * This is the high-level API method. It decides whether to check the server,
     * or check locally, and returns the appropriate result.
     *
     * @param repopath: the repopath
     * @param version: the full version string
     * @return: boolean saying whether repopath@version is currently trusted
     */
    async checkPerUserTrustSetting(repopath, version) {
        if (this.canRecordTrustSettingsOnServer) {
            const resp = await this.hub.xhrFor('checkUserTrust', {
                query: {
                    repopath: repopath,
                    vers: version,
                },
                handleAs: 'json',
            });
            if (this.hub.errAlert3(resp)) {
                return false;
            } else {
                // Server uses 3-valued logic (boolean or null), but here we just
                // want boolean.
                return resp.user_trust_setting || false;
            }
        } else {
            return this.checkTrustSettingLocally(repopath, version);
        }
    }

    /* Check the "combined" trust setting for repopath@version, which disjoins
     * the site-wide setting with the per-user setting.
     *
     * * See also:
     *   checkPerUserTrustSetting()
     *   RepoManager.repoIsTrustedSiteWide()
     */
    async checkCombinedTrustSetting(repopath, version) {
        if (this.hub.repoManager.repoIsTrustedSiteWide(repopath, version)) {
            return true;
        }
        return await this.checkPerUserTrustSetting(repopath, version);
    }

    // -----------------------------------------------------------------------
    // Low-level read/write operations

    /* Generate the prefix for keys under which trust settings should be
     * recorded, for the current user.
     */
    getUserTrustKeyPrefix() {
        const username = this.hub.getUsername() || '';
        return `${this.trustKeyPrefix}${username}:`;
    }

    /* Record a trust setting for repopath@version locally, i.e. in the browser.
     *
     * @param repopath: the repopath
     * @param version: the full version string
     * @param trusted: boolean, saying whether you want to trust or not
     * @return: boolean saying whether we made any change to existing records
     */
    recordTrustSettingLocally(repopath, version, trusted) {
        const trustedVersions = this.loadTrustedVersionsForRepo(repopath);
        let madeChange = false;

        if (trusted && !trustedVersions.includes(version)) {
            trustedVersions.push(version);
            madeChange = true;
        } else if (!trusted && trustedVersions.includes(version)) {
            const i0 = trustedVersions.indexOf(version);
            trustedVersions.splice(i0, 1);
            madeChange = true;
        }

        if (madeChange) {
            this.saveTrustedVersionsForRepo(repopath, trustedVersions);
        }

        return madeChange;
    }

    /* Check a trust setting for repopath@version locally, i.e. in the browser.
     *
     * @param repopath: the repopath
     * @param version: the full version string
     * @return: boolean saying whether repopath@version is currently trusted
     */
    checkTrustSettingLocally(repopath, version) {
        const trustedVersions = this.loadTrustedVersionsForRepo(repopath);
        return trustedVersions.includes(version);
    }

    /* Return (possibly empty) array of trusted version strings for a given repopath.
     */
    loadTrustedVersionsForRepo(repopath) {
        const k = this.getUserTrustKeyPrefix() + repopath;
        return JSON.parse(this.browserStorage.getItem(k)) || [];
    }

    /* Record array of trusted version strings for a given repopath.
     */
    saveTrustedVersionsForRepo(repopath, trustedVersions) {
        const k = this.getUserTrustKeyPrefix() + repopath;
        this.browserStorage.setItem(k, JSON.stringify(trustedVersions));
    }

}

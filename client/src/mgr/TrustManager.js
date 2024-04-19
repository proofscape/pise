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
    }

    async showTrustDialog(repopath, version) {
        const currentlyTrusted = await this.checkTrustSetting(repopath, version);
        let content = '';  // TODO

        const choiceResult = await this.hub.choice({
            title: 'Trust settings',
            content: content,
        });

        // TODO...
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

    /* Check a trust setting for repopath@version.
     *
     * This is the high-level API method. It decides whether to check the server,
     * or check locally, and returns the appropriate result.
     *
     * @param repopath: the repopath
     * @param version: the full version string
     * @return: boolean saying whether repopath@version is currently trusted
     */
    async checkTrustSetting(repopath, version) {
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

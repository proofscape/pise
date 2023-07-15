# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2023 Proofscape Contributors                           #
#                                                                             #
#   Licensed under the Apache License, Version 2.0 (the "License");           #
#   you may not use this file except in compliance with the License.          #
#   You may obtain a copy of the License at                                   #
#                                                                             #
#       http://www.apache.org/licenses/LICENSE-2.0                            #
#                                                                             #
#   Unless required by applicable law or agreed to in writing, software       #
#   distributed under the License is distributed on an "AS IS" BASIS,         #
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  #
#   See the License for the specific language governing permissions and       #
#   limitations under the License.                                            #
# --------------------------------------------------------------------------- #

import json

import pfsc.constants
from pfsc.constants import UserProps
from pfsc.excep import PfscExcep, PECode
from pfsc.gdb.reader import GraphReader
from pfsc.gdb.user import User, make_new_user_properties_dict


class GraphWriter:
    """Abstract base class for graph database writers. """

    def __init__(self, reader):
        self.gdb = reader.gdb
        self._reader = reader

    @property
    def reader(self) -> GraphReader:
        return self._reader

    def new_transaction(self):
        """Start a new transaction. """
        raise NotImplementedError

    def commit_transaction(self, tx):
        """Commit a transaction. """
        raise NotImplementedError

    def rollback_transaction(self, tx):
        """Roll back a transaction. """
        raise NotImplementedError

    def index_module(self, mii):
        """
        This function "indexes" a module, meaning that it updates the graph
        database to accurately reflect any and all entities and relationships
        defined in this module.

        :param mii: a ModuleIndexInfo instance.

        """
        if not mii.is_WIP():
            # Sanity check: When indexing a numbered release version (i.e.
            # anything other than a WIP build), the operation relies heavily
            # on the assumption that that version _has not yet been indexed_.
            # Violating that assumption will lead to an untold mixture of
            # bizarre errors.
            already_indexed = self.reader.version_is_already_indexed(
                                        mii.repopath, mii.version)
            if already_indexed:
                msg = f'Release `{mii.version}` of repo `{mii.repopath}`' \
                      ' has already been indexed.'
                raise PfscExcep(msg, PECode.ATTEMPTED_RELEASE_REINDEX)
        tx = self.new_transaction()
        try:
            self.ix0100(mii, tx)
            new_targeting_relns = self.ix0200(mii, tx)
            self.ix0300(mii, new_targeting_relns, tx)
            self.ix0400(mii, tx)
        except Exception as e:
            self.rollback_transaction(tx)
            raise e from None
        else:
            self.commit_transaction(tx)

    def clear_wip_indexing(self, mii, tx):
        """
        Delete every j-node and j-reln falling under the module and having
        major version number "WIP"

        Since WIP indexing is done in ISOLATED mode, this is enough. (In
        particular, there is no need to reset any `cut` properties on other
        nodes.)
        """
        mii.note_begin_indexing_phase(110)
        # Any j-relns added in a previous WIP build should have at least
        # one endpoint which is a j-node added in that build, so dropping
        # just the nodes should be enough.
        for modpath in mii.all_modpaths_with_changes():
            self._drop_wip_nodes_under_module(modpath, tx)
            mii.note_task_element_completed(111)

    def _drop_wip_nodes_under_module(self, modpath, tx):
        """Drop all nodes having a given modpath and major=WIP. """
        raise NotImplementedError

    def ix0100(self, mii, tx):
        """Clear existing WIP indexing, if any. """
        if mii.is_WIP():
            self.clear_wip_indexing(mii, tx)

    def ix0200(self, mii, tx):
        """V_cut, E_cut, V_add, E_add. """
        raise NotImplementedError

    def ix0300(self, mii, new_targeting_relns, tx):
        """
        Movements, retargeting, etc.
        I.e. relationships resulting from movement.
        """
        self.ix0330(mii, tx)
        self.ix0360(mii, tx, new_targeting_relns)

    def ix0330(self, mii, tx):
        """
        Movements.

        Note: we only formally record movements for the pairs that were explicitly
        noted in the given move mapping. All the rest can be inferred from these.
        See `GraphReader.find_move_conjugate()`.
        """
        raise NotImplementedError

    def ix0360(self, mii, tx, new_targeting_relns):
        """
        Retargeting.

        We add "RETARGETS" edges.
        There are two sides to this:
        (1) For any new enrichments we have added, we add retargeting edges if
            their declared targets have moved forward;
        (2) For anything that has moved in this release, we add retargeting edges
            from any existing enrichments on them, to their new location.

        Note that the major/cut interval on a TARGETS edge indicates the set of
        versions of the *tail*, over which this relationship to the head holds.
        Therefore the RETARGETS edges we add will be given the same major/cut as
        the TARGETS edges they correspond to. Essentially, a TARGETS edge says,
        "Enrichment e at major version M was designed as an enrichment on target
        t," while a corresp. RETARGETS edge says, "But now t can be found at
        a new address, so e@M is still designed as an enrichment on the thing
        at this new address."
        """
        raise NotImplementedError

    def ix0400(self, mii, tx):
        """
        Finishing steps.

        Record the fact that this repo:vers has been indexed.
        """
        raise NotImplementedError

    def clear_test_indexing(self):
        """
        Clear all indexing under the `test` repo family.
        """
        raise NotImplementedError

    def delete_everything_under_repo(self, repopath):
        """
        Delete all nodes and edges under a given repopath, at all versions.
        """
        # Check for indexed versions should be faster than deletion operation,
        # since it can make a targeted search for nodes of label `Version`.
        # If nothing indexed yet, can skip the expensive operation of searching
        # whole database for any node (of any label) having the given repopath.
        infos = self.reader.get_versions_indexed(repopath, include_wip=True)
        if infos:
            self._do_delete_all_under_repo(repopath)

    def _do_delete_all_under_repo(self, repopath):
        """
        Internal method for deleting everything under a repo.
        """
        raise NotImplementedError

    def delete_full_wip_build(self, repopath):
        """
        Delete everything for a given repo @WIP.
        """
        self.delete_full_build_at_version(repopath, version=pfsc.constants.WIP_TAG)

    def delete_full_build_at_version(self, repopath, version=pfsc.constants.WIP_TAG):
        """
        Delete everything for a given repo at a given version.

        WARNING: If numbered versions have been built under DIFFERENTIAL indexing
        mode, then deleting any but the latest numbered version for a given
        repo will result in an inconsistent state in the index.
        """
        raise NotImplementedError

    # ----------------------------------------------------------------------

    def add_user(self, username, usertype, email, orgs_owned_by_user):
        """
        Add a new user.

        @param usertype: a value of `UserProps.V_USERTYPE`, telling us whether
            this is a true user, or an organization.
        @param username: Full proofscape username in the form `host.user`
        @param email: The user's email address
        @param orgs_owned_by_user: list of strings. Each string should be the
            name of an organization itself, without the hostname. E.g. 'bar',
            not 'test.bar'.
        @return: User instance representing the new user
        """
        props = make_new_user_properties_dict(usertype, email, orgs_owned_by_user)
        j_props = json.dumps(props)
        self._add_user(username, j_props)
        return User(username, props)

    def _add_user(self, username, j_props):
        raise NotImplementedError

    def merge_user(self, username, usertype, email, orgs_owned_by_user):
        """
        Load a user if they already exist; otherwise add them as new.

        @return: pair (User, is_new) where is_new is a boolean saying whether
          the user had to be added.
        """
        user, is_new = self.reader.load_user(username), False
        if user is None:
            user, is_new = self.add_user(username, usertype, email, orgs_owned_by_user), True
        else:
            # If the user already exists, we update the email and the orgs.
            # We want these to always be up to date.
            user.update_email(email)
            user.update_owned_orgs(orgs_owned_by_user)
        return user, is_new

    def delete_user(self, username, *,
                    definitely_want_to_delete_this_user=False):
        """
        Delete a user completely from the database. This also deletes all
        edges connected to the user, hence any notes the user may have stored.

        @param username: the user to be deleted.
        @param definitely_want_to_delete_this_user: bool, a programming check
        @return: int, being the number of User nodes deleted (always 0 or 1)
        """
        raise NotImplementedError

    def delete_all_notes_of_one_user(self, username, *,
                    definitely_want_to_delete_all_notes=False):
        """
        Delete all the notes recorded for a given a user.

        @param username: the user whose notes are to be deleted.
        @param definitely_want_to_delete_all_notes: bool, a programming check
        """
        raise NotImplementedError

    def update_user(self, user):
        """
        Update the properties of an existing user.

        @param user: User instance
        """
        username = user.username
        j_props = json.dumps(user.props)
        self._update_user(username, j_props)

    def _update_user(self, username, j_props):
        raise NotImplementedError

    def record_user_notes(self, username, user_notes):
        """
        Record a user's notes on a goal.

        Note that in particular if the given notes are blank, then any existing
        NOTES edge for this user/goal will be deleted.

        @param username: str, the user
        @param user_notes: UserNotes to be recorded
        """
        raise NotImplementedError

    # ----------------------------------------------------------------------

    def record_module_source(self, modpath, version, modtext):
        """
        Record the pfsc source code for a given module at a given version.

        @param modpath: the libpath of the module
        @param version: the version of the module
        @param modtext: the pfsc source code of the module
        """
        raise NotImplementedError

    def record_repo_manifest(self, repopath, version, manifest_json):
        """
        Record the JSON for a given repo's manifest, at a given version.

        @param repopath: the libpath of the repo
        @param version: the version of the repo
        @param manifest_json: the JSON of the repo's manifest
        """
        raise NotImplementedError

    def record_dashgraph(self, deducpath, version, dg_json):
        """
        Record the JSON for a given deduc's dashgraph, at a given version.

        @param deducpath: the libpath of the deduc
        @param version: the version of the deduc
        @param dg_json: the JSON of the deduc's dashgraph
        """
        raise NotImplementedError

    def record_annobuild(self, annopath, version, anno_html, anno_json):
        """
        Record the HTML and JSON for a given anno, at a given version.

        @param annopath: the libpath of the anno
        @param version: the version of the anno
        @param anno_html: the anno's HTML
        @param anno_json: the anno's JSON
        """
        raise NotImplementedError

    def delete_builds_under_module(self, modpath, version):
        """
        Delete all edges and nodes representing built products, under a given
        module at a given version. This means all `BUILD` edges and their
        target nodes, where the `BUILD` edge has the desired `version` prop,
        and the source node has the given modpath.

        @param modpath: the libpath of the module
        @param version: the version of the module
        """
        raise NotImplementedError

    # ----------------------------------------------------------------------

    def set_approval(self, widgetpath, version, approved):
        """
        This provides a mechanism for reviewing display code on `disp` widgets
        in untrusted repos, and marking them as "approved". This should mean,
        "a human being has reviewed this code, and it appears harmless".

        Thus, this is meant to support websites wishing to host untrusted repos,
        with a finer-grained review mechanism than the `PFSC_TRUSTED_LIBPATHS`
        config var.

        NOTE: Marking a libpath as trusted WILL OVERRIDE THESE APPROVALS.
        I.e. once a libpath is included in `PFSC_TRUSTED_LIBPATHS`, then it is
        as if all `disp` widgets at or under that path are immediately approved.

        @param widgetpath: the libpath of the widget whose approval status
            is to be set.
        @param version: *full* version (WIP or vM.m.p) of the widget.
        @param approved: boolean: True means approved, False not approved.
        """
        j_in = self.reader._load_approvals_dict_json(widgetpath, version)
        approvals = {} if j_in is None else json.loads(j_in)
        current_setting = approvals.get(version, False)
        if approved != current_setting:
            approvals[version] = approved
            j_out = json.dumps(approvals)
            self._set_approvals_dict_json(widgetpath, version, j_out)

    def _set_approvals_dict_json(self, widgetpath, version, j):
        """
        Set the approvals dictionary JSON for a given widget.

        @param widgetpath: the libpath of the widget.
        @param version: the version of the widget.
        @param j: the JSON string to be recorded.
        """
        raise NotImplementedError

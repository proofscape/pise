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

import os, sys

# This is the base directory of the Proofscape installation.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Test resources directory
TEST_RESOURCE_DIR = os.path.join(BASE_DIR, 'tests', 'resources')

# See `pfsc.handlers.RepoTaskHandler.process()`:
SYNC_JOB_RESPONSE_KEY = "SYNC_JOB_RESPONSE"

# Namespaces / channel names / queue names / event names
WEBSOCKET_NAMESPACE = '/pfsc-ise'
REDIS_CHANNEL = 'pfsc-io'
MAIN_TASK_QUEUE_NAME = 'pfsc-tasks'
MATH_CALC_QUEUE_NAME = 'pfsc-math-calc'
RQ_QUEUE_NAMES = [
    MAIN_TASK_QUEUE_NAME,
    MATH_CALC_QUEUE_NAME,
]
ISE_EVENT_NAME = 'iseEvent'

ISE_PREFIX = '/ise'

STUDYPAGE_ANNO_NAME = 'studyPage'

SHADOW_PREFIX = '.shadow_'

DEMO_USERNAME_SESSION_KEY = 'demo_username'
DELETE_DEMO_REPO_JOB_PREFIX = 'pfsc:delete_demo_repo'

MAX_NOTES_MARKDOWN_LENGTH = 4096

# -----------------------------------------------------------------
# The following values must not change from one installation to the
# next. They define aspects of the pfsc language itself, or aspects of
# the indexing system that need to be the same no matter where the system
# is running, for the sake of interoperability.

# Version tag for work-in-progress
WIP_TAG = "WIP"

# Cut tag value for index items that have not yet been cut.
# Note: It is critical that this be lowercase so that "WIP" < "inf"
# in the normal lexicographic ordering on strings.
INF_TAG = "inf"

# This says how version components will be recorded as 0-padded
# strings in our graph database. This puts an upper limit on the
# maximum allowed version number component. Proper sorting persists
# through one more digit than the pad length. So e.g. if we use %06d,
# then you may use version numbers up to 10^7 - 1. (We cannot accept
# 10^7, since it would get sorted before 2*10^6.)
PADDED_VERSION_COMPONENT_FORMAT = '%06d'
PADDED_VERSION_COMPONENT_LENGTH = 6
MAX_NUMERICAL_VERSION_COMPONENT = 10**7 - 1

# LHS for repo dependencies declaration.
# Internally, dependencies should look like:
# {
#   repopath: version,
#   ...
# }
DEPENDENCIES_LHS = "dependencies"

# LHS for repo change log declaration.
# Internally, a change log should look like:
# {
#    moved: {
#      old_libpath_rel_prefix1: new_libpath_prefix1,
#      old_libpath_rel_prefix2: null,
#      ...
#    }
# }
# Here, "rel" ("relative") means the libpath must be relative to
# that of the repo; "prefix" means the mapping is applied to all
# libpaths that begin this way.
CHANGE_LOG_LHS = "change_log"
MOVE_MAPPING_NAME = "moved"

# LHS for version number declaration.
VERSION_NUMBER_LHS = "version"

# Special comments for display widgets:
DISP_WIDGET_BEGIN_EDIT = "# BEGIN EDIT"
DISP_WIDGET_END_EDIT = "# END EDIT"

# Prefix character for LaTeX math modes to indicate that VerTeX should be used
VERTEX_KEY_CHAR = "@"
# Max length for a libpath:
MAX_LIBPATH_LEN = 192
# Max length for a libseg:
MAX_LIBSEG_LEN = 48
# Max length for the name of a widget group (including leading dots):
MAX_WIDGET_GROUP_NAME_LEN = 48

# Recusion limits
# For processing input that describes a forest of nested deductions:
MAX_FOREST_EXPANSION_DEPTH = min(100, sys.getrecursionlimit() - 1)
# For scanning a pfsc repo:
MAX_REPO_DIR_DEPTH = min(50, sys.getrecursionlimit() - 1)

# When operating in personal server mode, user needs an identity e.g.
# so that NOTES edges can be recorded in the GDB.
DEFAULT_USER_NAME = 'admin._'
DEFAULT_USER_EMAIL = 'pfsc_default_user@localhost'

# User name and email for git commits made programmatically:
PROGRAMMATIC_COMMIT_USER_NAME = 'Pfsc Bot'
PROGRAMMATIC_COMMIT_USER_EMAIL = 'pfsc_bot@localhost'

# Source file extensions
PFSC_EXT = '.pfsc'
RST_EXT = '.rst'

# Extension used for pickled cache files
PICKLE_EXT = '.pickle'

# These are the names of "special" pages that Sphinx generates, which must
# therefore not have user-defined rst files at the root level of a repo.
PROHIBITED_RST_DOCNAMES = [
    'genindex', 'search',
]

# Presence of this string in error messages is used to mark Sphinx warnings
# as meriting immediate halt of the build process.
PFSC_SPHINX_CRIT_ERR_MARKER = 'PROOFSCAPE-SPHINX-ERROR'


class ContentDescriptorType:
    """
    Type names for manifest tree nodes, and content descriptor
    dictionaries. Matches content type names used on the client side.
    """
    CHART = 'CHART'
    MODULE = 'MODULE'
    NOTES = 'NOTES'
    SPHINX = 'SPHINX'


class IndexType:
    """
    Labels and type names for nodes and edges in the GDB.
    """
    # -----------------------------------------------------
    # j-node types
    VERSION = 'Version'
    MODULE = 'Module'

    DEDUC = 'Deduc'
    EXAMP = 'Examp'
    ANNO  = 'Anno'
    SPHINX = 'Sphinx'

    DEFN = 'Defn'
    ASGN = 'Asgn'

    NODE  = 'Node'
    GHOST = 'Ghost'
    SPECIAL = 'Special'
    # (Question and UnderConstruction nodes are of `Special` type.)

    WIDGET = 'Widget'

    VOID = 'Void'

    USER = 'User'

    MOD_SRC = 'ModSrc'
    DEDUC_BUILD = 'DeducBuild'
    ANNO_BUILD = 'AnnoBuild'

    # -----------------------------------------------------
    # j-reln types

    TARGETS = 'TARGETS'
    EXPANDS = 'EXPANDS'
    IMPLIES = 'IMPLIES'
    FLOWSTO = 'FLOWSTO'
    GHOSTOF = 'GHOSTOF'

    RETARGETS = 'RETARGETS'

    UNDER = 'UNDER'
    MOVE = 'MOVE'

    NOTES = 'NOTES'
    CF = 'CF'
    BUILD = 'BUILD'

    # -----------------------------------------------------
    # Extra property names
    #  These are properties for k-Nodes and k-Relns which go outside the set
    #  of fixed properties of these objects, and are specifically meant to be
    #  set in `kObj.extra_props`.

    # Widget type:
    EP_WTYPE = 'wtype'

    # When deduc E is written as an expansion of deduc D, at that
    # time deduc D is _taken at_ a particular version.
    EP_TAKEN_AT = 'taken_at'

    # -----------------------------------------------------
    # Other property names
    #   These are any other properties we want to use in the GDB, but which
    #   don't relate to the whole `kObj.extra_props` system.

    # The "version" property of a `BUILD` edge. The value should be a full
    # version tag, i.e. either "WIP" or of the form "vM.m.p".
    P_BUILD_VERS = 'vers'

    # Property where we record JSONified dict whose keys are the full versions
    # "vM.m.p" at which a given display widget's code has been approved.
    P_APPROVALS = 'approvals'

    # -----------------------------------------------------
    # Groupings

    ENRICHMENT_TYPES = [DEDUC, EXAMP, ANNO]
    INFERRED_RELNS = [RETARGETS]


class UserProps:
    """
    Here we define keys (K_...) for user properties, and values (V_...) for
    use as or within (i.e. in lists or dicts) user properties.

    The schema for a user's properties dict is defined by the
        pfsc.gdb.user.make_new_user_properties_dict()
    function.
    """

    # At various places in the model, we may want to define a default value
    # (for something). This is a generic key to be used for that purpose:
    K_DEFAULT = 'DEFAULT'

    # We use our User class to represent both true users, and organizations
    # (or "workspaces") at our OAuth providers. The USERTYPE property lets
    # us know which type of entity it is.
    K_USERTYPE = 'USERTYPE'
    class V_USERTYPE:
        USER = 'USER'
        ORG  = 'ORG'

    K_CREATION_TIME = 'CTIME'

    # The address at which the user can be reached
    K_EMAIL = 'EMAIL'

    # The names of organizations that the user owns (has admin access to)
    K_OWNED_ORGS = 'OWNED_ORGS'

    # How the user wants notes to be stored
    K_NOTES_STORAGE = 'NOTES_STORAGE'
    class V_NOTES_STORAGE:
        BROWSER_ONLY = 'BROWSER_ONLY'
        BROWSER_AND_SERVER = 'BROWSER_AND_SERVER'

        ALL_ = [BROWSER_ONLY, BROWSER_AND_SERVER]
        INCLUDES_SERVER = [BROWSER_AND_SERVER]

    # Per-repo hosting settings
    K_HOSTING = 'HOSTING'
    class V_HOSTING:
        # These are not used directly as values under the K_HOSTING key;
        # instead, the value is a dictionary d. In d, keys are repo names
        # (not libpaths but just the repo segment). Each value in d is again
        # a dictionary e. In e, the keys are version numbers, and the values
        # are the constants defined below.
        #
        # There are however two exceptions:
        #
        # (1) K_DEFAULT may also appear as key in d or e.
        # Its value is again one of the constants
        # below, meaning a decision that should apply if no more specific one
        # has been listed. As a default value, PENDING means the user may
        # make a request.
        #
        # (2) When granting hosting for a particular version of a particular
        # repo, onto "GRANTED" you may append ":" and a Git commit hash. If you
        # do this, then the system will refuse to build the repo at that version
        # unless the commit hash matches. This is a way to ensure that the
        # version being built is the version you approved.
        #
        # Defaults are not required, as we will always look to a more general
        # decision in absence of a default at any level, bottoming out at the
        # DEFAULT_HOSTING_STANCE config var.

        PENDING = 'PENDING'
        DENIED = 'DENIED'
        GRANTED = 'GRANTED'

    # Some properties can be freely set by the user, via an appropriate
    # HTTP request (including a valid CSRF token), but not all. For example,
    # K_EMAIL cannot be set freely.
    FREELY_SETTABLE_BY_USER = [
        # Actually right now there are no settings that are freely settable.
        # We used to list `K_NOTES_STORAGE` here, before this became controlled
        # by the '/requestSsnr' endpoint.
    ]

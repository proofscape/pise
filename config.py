# --------------------------------------------------------------------------- #
#   Proofscape Server                                                         #
#                                                                             #
#   Copyright (c) 2011-2022 Proofscape contributors                           #
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

import os

from dotenv import load_dotenv
# Load pfsc-server/instance/.env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOTENV_PATH = os.path.join(BASE_DIR, 'instance', '.env')
load_dotenv(DOTENV_PATH)
if bool(int(os.getenv("LOAD_PFSC_CONF_FROM_STANDARD_DEPLOY_DIR", 0))):
    # Look for PFSC_ROOT/deploy/pfsc.conf, in a standard installation, and
    # if found load it, overriding instance/.env as well as existing env vars.
    PFSC_CONF_PATH = os.path.join(BASE_DIR, '..', '..', 'deploy', 'pfsc.conf')
    load_dotenv(PFSC_CONF_PATH, override=True)


def format_url_prefix(raw):
    """
    Ensure that the URL prefix is a string that is either empty or
    begins with a slash.
    :param raw: the prefix as defined in the config or env var
    :return: empty string or string beginning with a slash
    """
    if not isinstance(raw, str) or len(raw) == 0:
        return ''
    if raw[0] != '/':
        return '/' + raw
    return raw


def parse_cd_list(raw):
    """
    Turn a string giving a comma-delimited list into a python list.
    Ensure that an empty string results in an empty list.
    Allow whitespace.
    """
    return [] if len(raw) == 0 else [p.strip() for p in raw.split(',')]


class HostingStance:
    """
    Each setting controls what happens when a logged-in user attempts to build
    a new releease of a repo they own, and for which the admin has not yet made
    a per-repo setting.
    """
    # User is simply told that this action is not allowed at this site:
    UNAVAILABLE = "UNAVAILABLE"
    # User is told that they can request hosting:
    BY_REQUEST = "BY_REQUEST"
    # The build goes ahead immediately:
    FREE = "FREE"


class Config:
    """
    Abstract base class for all config classes.
    """
    IS_DEV = False
    IS_OCA = False

    # Setting PERSONAL_SERVER_MODE to True is appropriate in only two cases:
    # (1) the server is running on a user's personal machine, in which case
    # that user is intended to be able to do anything they want, with any repo;
    # (2) the app is running as an RQ worker, started by the `worker.py` script,
    # in which case it needs to be able to do whatever it is asked. (Permission
    # checks happen before jobs reach workers.)
    PERSONAL_SERVER_MODE = bool(int(os.getenv("PERSONAL_SERVER_MODE", 0)))

    # When _not_ in PERSONAL_SERVER_MODE, you are most likely running the
    # server online, and you have to decide if you want your users to be able
    # to edit and develop pfsc modules at your site, or if you are running a
    # "pure hosting" site, i.e. one where repos can only be loaded at numbered
    # release versions, never at WIP. The ALLOW_WIP config var defaults to
    # False, meaning it is a "pure hosting" site. If you want to allow WIP,
    # you will have to implment a solution for your users to obtain their work,
    # i.e. to do a commit and then either push that work somewhere else or
    # do a pull from your server. (Or perhaps not do a commit but simply do an
    # rsync?) Currently, the server does not yet provide any support for any of
    # this.
    ALLOW_WIP = bool(int(os.getenv("ALLOW_WIP", 0)))

    # When asking to load a repo, the client can omit the version tag, prompting
    # us to load it at the "default version." This variable defines what the
    # default version is. If False, the default version is WIP. If True, then
    # the default version is "latest." What this means is that we first
    # consult the GDB to see if any numbered releases of this repo have been
    # built. If so, we load the latest one; if not, we try to load @WIP.
    # Note: There is one exception, which is that for a demo repo, the default
    # version is always WIP, regardless of this variable.
    DEFAULT_REPO_VERSION_IS_LATEST_RELEASE = bool(int(os.getenv("DEFAULT_REPO_VERSION_IS_LATEST_RELEASE", 0)))

    # If you are running online, you can take different approaches to giving
    # your users permission to host their content repos at your site.
    # For each user, you can make per-repo settings.
    # See `pfsc.constants.UserProps.V_HOSTING`.
    # Here, you set the default stance taken on any repo for which you have
    # not yet made a per-repo setting.
    # See the `HostingStance` enum class defined above, for the legal values.
    DEFAULT_HOSTING_STANCE = os.getenv("DEFAULT_HOSTING_STANCE", HostingStance.BY_REQUEST)

    # When operating in PERSONAL_SERVER_MODE (see above), you can clone any
    # repo, and build any release of any repo.
    # Otherwise, there is a question of who should be able to build releases.
    # Can admins build releases of repos they don't own? If not (the default),
    # then only repo owners can build releases, when not operating in personal
    # server mode.
    ADMINS_CAN_BUILD_RELEASES = bool(int(os.getenv("ADMINS_CAN_BUILD_RELEASES", 0)))

    FORCE_RQ_SYNCHRONOUS = bool(int(os.getenv("FORCE_RQ_SYNCHRONOUS", 0)))
    REQUIRE_CSRF_TOKEN = bool(int(os.getenv("REQUIRE_CSRF_TOKEN", 1)))

    ISE_DEV_MODE = bool(int(os.getenv("ISE_DEV_MODE", 0)))

    PROVIDE_DEMO_REPOS = bool(int(os.getenv("PROVIDE_DEMO_REPOS", 0)))
    DEMO_REPO_HOURS_TO_LIVE = int(os.getenv("DEMO_REPO_HOURS_TO_LIVE", 24))
    SHOW_DEMO_ENRICHMENTS = bool(int(os.getenv("SHOW_DEMO_ENRICHMENTS", 0)))

    BYPASS_CACHE_FOR_REPO_MODEL_LOAD = bool(int(os.getenv("BYPASS_CACHE_FOR_REPO_MODEL_LOAD", 0)))
    ADMIN_USERS = parse_cd_list(os.getenv('ADMIN_USERS', ''))

    # One way to generate a secret key in Python is to use sth like
    #   import secrets
    #   key = secrets.token_urlsafe(32)
    # However, we do not generate a value for you here, because it would be
    # different each time you restarted the app. Then, unless you also cleared
    # cookies in your browser, you would see weird errors (usually complaining
    # of a wrong or missing CSRF token).
    SECRET_KEY = os.getenv('SECRET_KEY')
    SESSION_COOKIE_NAME = 'pfsc_ise_session'

    # If running this Flask app behind a reverse proxy (like Nginx), you need
    # to account for how many `X-Forwarded-...` headers your reverse prox(y|ies)
    # are setting. Otherwise Flask's `url_for()` doesn't work properly.
    #
    # (E.g. an `https` request comes in, but Flask sees it as an `http` request,
    # and therefore generates an `http` URL. Not good! By the way, in production
    # you should probably be using the HSTS header anyway, to guard against
    # issues like these!)
    #
    # See <https://werkzeug.palletsprojects.com/en/2.1.x/middleware/proxy_fix/>
    # Our `PROXY_FIX_<WORD>` config var is the integer passed as the `x_<word>`
    # kwarg to the `ProxyFix` class.
    #
    # WARNING: It is dangerous to set these values too large! If you say there
    # are more headers than your proxies actually set, this means you trust
    # headers written by the client, which opens the door to CSRF attacks.
    PROXY_FIX_FOR = int(os.getenv("PROXY_FIX_FOR", 0))
    PROXY_FIX_PROTO = int(os.getenv("PROXY_FIX_PROTO", 0))

    # Static assets:

    ISE_VERSION = os.getenv("ISE_VERSION", "0.0")
    ISE_SERVE_MINIFIED = bool(int(os.getenv("ISE_SERVE_MINIFIED", 0)))
    # Since a worker script must obey the same-origin policy
    #   https://developer.mozilla.org/en-US/docs/Web/API/Worker/Worker
    # we cannot serve the mathworker script over a CDN. However, we can decide
    # whether to serve it minified or not.
    MATHWORKER_SERVE_MINIFIED = bool(int(os.getenv("MATHWORKER_SERVE_MINIFIED", 1)))

    # From where should static assets be obtained?
    # "locally" means from pfsc-server; otherwise via jsdelivr
    ISE_SERVE_LOCALLY = bool(int(os.getenv("ISE_SERVE_LOCALLY", 1)))
    ELKJS_SERVE_LOCALLY = bool(int(os.getenv("ELKJS_SERVE_LOCALLY", 0)))
    MATHJAX_SERVE_LOCALLY = bool(int(os.getenv("MATHJAX_SERVE_LOCALLY", 0)))
    PYODIDE_SERVE_LOCALLY = bool(int(os.getenv("PYODIDE_SERVE_LOCALLY", 0)))

    # When loading locally from `/static/...`, some assets have a debug version.
    ELK_DEBUG = bool(int(os.getenv("ELK_DEBUG", 0)))

    # See <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy>
    REFERRER_POLICY = os.getenv("REFERRER_POLICY", 'no-referrer')

    APP_URL_PREFIX = format_url_prefix(os.getenv("APP_URL_PREFIX"))
    SOCKETIO_PATH = APP_URL_PREFIX + '/socket.io'

    # Legal docs:
    # Updating the versions will cause the user to be prompted to
    # review the new versions, and again agree.
    # Terms of Service:
    TOS_URL = os.getenv("TOS_URL")
    TOS_VERSION = os.getenv("TOS_VERSION")
    # Privacy Policy:
    PRPO_URL = os.getenv("PRPO_URL")
    PRPO_VERSION = os.getenv("PRPO_VERSION")

    # Login window customization:
    # An image with your own branding to be displayed at top of page:
    LOGIN_PAGE_BRANDING_IMG_URL = os.getenv("LOGIN_PAGE_BRANDING_IMG_URL")
    # If TOS_URL and/or PRPO_URL are so much as defined, the user will be told
    # they agree by signing in. If in addition you want checkboxes that must
    # be checked to proceed, then set this true:
    LOGIN_PAGE_USE_AGREEMENT_CHECKBOXES = bool(int(os.getenv("LOGIN_PAGE_USE_AGREEMENT_CHECKBOXES", 0)))

    # Server-Side Note Recording:
    # Elect whether to offer the service or not:
    OFFER_SERVER_SIDE_NOTE_RECORDING = bool(int(os.getenv("OFFER_SERVER_SIDE_NOTE_RECORDING", 0)))
    # If offering SSNR at all, will we record notes on goals@WIP? The index nodes
    # representing goals@WIP are unstable. They will vanish on the next build, and
    # so will the user's notes on them. Refusing to record is one way to ensure
    # the user doesn't waste effort; but it may be considered overkill, since the
    # client-side code will also offer them a warning.
    REFUSE_SSNR_AT_WIP = bool(int(os.getenv("REFUSE_SSNR_AT_WIP", 0)))
    # When the user requests to activate SSNR, the client will display a
    # confirmation dialog. You may define a URL from which to obtain the HTML to
    # be displayed in this dialog. Otherwise some default HTML is used.
    # See pfsc/templates/ssnr_on_conf.html
    SSNR_ACTIVATION_DIALOG_PROXY_URL = os.getenv("SSNR_ACTIVATION_DIALOG_PROXY_URL")
    # Likewise, for the confirmation dialog when requesting to deactivate SSNR:
    # See pfsc/templates/ssnr_off_conf.html
    SSNR_DEACTIVATION_DIALOG_PROXY_URL = os.getenv("SSNR_DEACTIVATION_DIALOG_PROXY_URL")

    # Accept OAuth logins via GitHub?
    ALLOW_GITHUB_LOGINS = bool(int(os.getenv("ALLOW_GITHUB_LOGINS", 0)))
    OAUTH_GH_ID = os.getenv("OAUTH_GH_ID", "")
    OAUTH_GH_SECRET = os.getenv("OAUTH_GH_SECRET", "")
    # Accept OAuth logins via BitBucket?
    ALLOW_BITBUCKET_LOGINS = bool(int(os.getenv("ALLOW_BITBUCKET_LOGINS", 0)))
    OAUTH_BB_ID = os.getenv("OAUTH_BB_ID", "")
    OAUTH_BB_SECRET = os.getenv("OAUTH_BB_SECRET", "")
    # Should users starting with the `test.` host segment be allowed to log in?
    # If so, their password equals their username, and there will be a special
    # log-in box for them on the log-in page.
    ALLOW_TEST_REPO_LOGINS = bool(int(os.getenv("ALLOW_TEST_REPO_LOGINS", 0)))
    # If allowing users like `test.foo` to log in, their email address will be
    # their full username, at a domain you specify here. E.g. `test.foo@localhost`.
    # This can be useful for testing functions that send emails to users.
    EMAIL_DOMAIN_FOR_TEST_USERS = os.getenv("EMAIL_DOMAIN_FOR_TEST_USERS", "localhost")

    # If PRE_APPROVED_LOGINS_ONLY is true, then among `gh.` and `bb.` users,
    # only those listed either under ADMIN_USERS or APPROVED_LOGINS will be
    # allowed to log in. For example, if ADMIN_USERS was empty, while
    # APPROVED_LOGINS was equal to ['gh.example'], then `gh.example` would be
    # the only user under `gh.` or `bb.` that could log in.
    PRE_APPROVED_LOGINS_ONLY = bool(int(os.getenv("PRE_APPROVED_LOGINS_ONLY", 0)))

    # NOTE: APPROVED_LOGINS does not take effect unless PRE_APPROVED_LOGINS_ONLY
    # is true! Then only these users and ADMIN_USERS can log in.
    APPROVED_LOGINS = parse_cd_list(os.getenv('APPROVED_LOGINS', ''))

    # In case of errors you might want to supply the user with something other
    # than the standard, built-in error pages. (This should be extremely rare
    # anyway, since it is a one-page app.) In that case you may supply URLs
    # from which we can try to obtain HTML to display on errors. (The user
    # is _not_ redirected.)
    ERR_404_PROXY_URL = os.getenv("ERR_404_PROXY_URL")
    ERR_500_PROXY_URL = os.getenv("ERR_500_PROXY_URL")

    REDIS_URI = os.getenv("REDIS_URI")

    GRAPHDB_URI = os.getenv("GRAPHDB_URI")
    # Username and password for the GDB are optional.
    GDB_USERNAME = os.getenv("GDB_USERNAME") or ''
    GDB_PASSWORD = os.getenv("GDB_PASSWORD") or ''

    # Some GDB systems support transactions, some do not. If we can tell based
    # on the GRAPHDB_URI (such as RedisGraph versus Neo4j) then we ignore this
    # variable; if we cannot (such as with a Gremlin URI) then we follow this.
    USE_TRANSACTIONS = bool(int(os.getenv("USE_TRANSACTIONS", 0)))

    # NOTE: math job timeouts are only relevant if you are performing math jobs
    # on the server. Generally speaking, this is now considered obsolete, since
    # math calculations are performed in the user's browser via Pyodide.
    #
    # Number of seconds before math calculations for examp widgets are timed out.
    # Set to -1 for no timeout (_NOT_ recommended for a public server!!!).
    MATH_CALCULATION_TIMEOUT = os.getenv('MATH_CALCULATION_TIMEOUT', 3)
    # Safety net timeout (seconds) in case for any reason math jobs can't even
    # get out of the queue. So, this should cover time to sit in queue _plus_
    # calculation time.
    MATH_JOB_QUEUE_TIMEOUT = os.getenv('MATH_JOB_QUEUE_TIMEOUT', 180)

    # These vars are still relevant, even with math jobs being performed on the
    # client side, since these values are served to and configure the client.
    #
    # When we parse strings that are meant to give mathematical expressions
    # parsable by SymPy, we should limit their maximum length and parenthesis
    # depth, for safety.
    MAX_SYMPY_EXPR_LEN = os.getenv("MAX_SYMPY_EXPR_LEN", 1024)
    MAX_SYMPY_EXPR_DEPTH = os.getenv("MAX_SYMPY_EXPR_DEPTH", 32)
    # Similarly, we must limit length and especially depth of build strings for
    # display widgets, so that we do not crash the Python ast parser.
    MAX_DISPLAY_BUILD_LEN = os.getenv("MAX_DISPLAY_BUILD_LEN", 4096)
    MAX_DISPLAY_BUILD_DEPTH = os.getenv("MAX_DISPLAY_BUILD_DEPTH", 32)

    SOCKETIO_ASYNC_MODE = os.getenv("SOCKETIO_ASYNC_MODE", "eventlet")
    SOCKETIO_MESSAGE_QUEUE = os.getenv("SOCKETIO_MESSAGE_QUEUE", REDIS_URI)

    # Optionally, the compiled forms of annos and deducs (their HTML and JSON),
    # and the source files for modules at numbered versions, may be stored in
    # the graph database, instead of in the build dir. The build dir is then
    # not used at all, and `PFSC_BUILD_ROOT` (see below) need not be defined.
    BUILD_IN_GDB = bool(int(os.getenv("BUILD_IN_GDB", 0)))

    PFSC_LIB_ROOT = os.getenv("PFSC_LIB_ROOT")
    PFSC_BUILD_ROOT = os.getenv("PFSC_BUILD_ROOT")
    PFSC_DEMO_ROOT = os.getenv("PFSC_DEMO_ROOT")

    RECYCLING_BIN = os.getenv("RECYCLING_BIN") or "/tmp/org.proofscape.recycling"

    # ISE_OFFER_PDFLIB merely controls whether the client-side ISE app will be instructed
    # to _offer_ the option to open PDFs from the library. Setting it false does not actually shut
    # off anything on the server side, since there is nothing in the app to shut off. The PDFLibrary
    # is deployed as a static directory, and that is a deployment decision made outside the
    # scope of this app.
    ISE_OFFER_PDFLIB = int(os.getenv("ISE_OFFER_PDFLIB", 0))
    # However the app may need to know where the PDF Library lives, such as when it wishes to write
    # to it when offering the PDF proxy service.
    PFSC_PDFLIB_ROOT = os.getenv("PFSC_PDFLIB_ROOT")
    # It is recommended that you set up a cron job to periodically clean the PDF cache directory,
    # which lives below the PDFLIB ROOT.
    PFSC_PDFLIB_CACHE_SUBDIR = os.getenv("PFSC_PDFLIB_CACHE_SUBDIR") or "cache"

    PFSC_ENABLE_PDF_PROXY = int(os.getenv("PFSC_ENABLE_PDF_PROXY", 0))
    # If nonempty, the APPROVED string will be used as a regex pattern, and only netlocations (i.e. domain + port) matching
    # this pattern will be allowed for PDF download.
    PFSC_PDF_NETLOC_APPROVED = os.getenv("PFSC_PDF_NETLOC_APPROVED") or ""
    # If nonempty, the BANNED string will be used as a regex pattern, and any netlocations (i.e. domain + port) matching
    # this pattern will be disallowed for PDF download.
    PFSC_PDF_NETLOC_BANNED = os.getenv("PFSC_PDF_NETLOC_BANNED") or ""

    # 'all': shadow all repos
    # comma-delimited list of repopaths: shadow just these repos
    # empty string: do not shadow any repos
    # DEFAULT: 'all'
    PFSC_SHADOWSAVE = parse_cd_list(os.getenv("PFSC_SHADOWSAVE", 'all'))

    ######################################################################
    # The following settings tell the client side code how to behave, regarding
    # various questions. Ultimately, these can only be considered "suggestions,"
    # but at this time there is no user interface to change these, and the
    # user would have to do some hacking to make any changes.

    # positive number of milliseconds before autosave after last change in editor panes
    #     or
    # zero to turn off autosave
    # DEFAULT: 5000 ms
    PFSC_AUTOSAVEDELAY = os.getenv("PFSC_AUTOSAVEDELAY", 5000)

    # 'auto': silently just overwrite with version from disk;
    #           however, at this time (15 May 2020), front end (pfsc-ise)
    #           currently blocks this policy if PFSC_SAVEALLONAPPBLUR not truthy.
    # 'compare': bring up a comparison dialog, and make the user decide
    # 'none': silently just keep the version in the app
    # DEFAULT: 'compare'
    PFSC_RELOADFROMDISK = os.getenv("PFSC_RELOADFROMDISK", 'compare')

    # truthy: do save all open modules on app blur
    # falsey: don't
    # DEFAULT: 1
    PFSC_SAVEALLONAPPBLUR = int(os.getenv("PFSC_SAVEALLONAPPBLUR", 1))

    ######################################################################

    PFSC_REQUIRE_CLEAN_REPO_BEFORE_INDEX = int(os.getenv("PFSC_REQUIRE_CLEAN_REPO_BEFORE_INDEX", 0))
    PFSC_SHOW_PRIVATE_ERR_MSGS_IN_DEVEL = int(os.getenv("PFSC_SHOW_PRIVATE_ERR_MSGS_IN_DEVEL", 0))
    PFSC_ADD_ERR_NUM_TO_MSG = int(os.getenv("PFSC_ADD_ERR_NUM_TO_MSG", 0))
    PFSC_MARKDOWN_ERR_MSG = int(os.getenv("PFSC_MARKDOWN_ERR_MSG", 0))

    # You can set which pfsc modules will be treated as "trusted" code, and
    # which not. Whether a module is trusted controls things like rendering of
    # links and images in markdown, and execution of display code in display
    # widgets.
    #
    # MARKING A LIBPATH AS TRUSTED IS LIKE DOWNLOADING SOFTWARE FROM THE
    # INTERNET AND RUNNING IT ON YOUR COMPUTER. BE CAREFUL. DO NOT MARK A
    # LIBPATH AS TRUSTED UNLESS YOU ARE CONFIDENT THAT IT CONTAINS NO
    # MALICIOUS CODE.
    #
    # WHEN YOU MARK A LIBPATH AS TRUSTED YOU ARE ALSO SAYING THAT EVERY LIBPATH
    # UNDER THAT ONE, i.e. EVERY EXTENSION OF IT, IS ALSO TRUSTED.
    #
    # The set of trusted libpaths is determined by the following three variables.
    #
    # Every libpath in the list is interpreted as absolute (i.e. as starting
    # from a repo segment).
    #
    # Every libpath in the list must be at least two segments long, with one
    # exception: you may include the libpath `lh`, meaning that you trust all
    # code in repos stored under the `lh` or "localhost" directory.
    #
    # The full set of trusted prefixes is the union of those obtained from the
    # following two config vars, each of which is given as a comma-delim list,
    # plus "gh.proofscape" unless TRUST_LIBPATH_GH_PROOFSCAPE is set to false.
    #
    # The difference between the first two vars is:
    #  * End users are generally expected to use the first var via pfsc.conf,
    #    and leave the second alone, although they may clear it if they wish.
    #  * The second var is intended to be used by application distributors,
    #    in order to make presets.
    PFSC_TRUSTED_LIBPATHS = parse_cd_list(os.getenv("PFSC_TRUSTED_LIBPATHS", ""))
    PFSC_DEFAULT_TRUSTED_LIBPATHS = parse_cd_list(os.getenv("PFSC_DEFAULT_TRUSTED_LIBPATHS", ""))
    # By default, even if you don't set any trusted libpaths (and also if you do),
    # the server will be configured to trust everything under 'gh.proofscape'.
    # If you _really_ want to shut this off, you can.
    TRUST_LIBPATH_GH_PROOFSCAPE = bool(int(os.getenv("TRUST_LIBPATH_GH_PROOFSCAPE", 1)))

    # Set "domain policies" for links and images in markdown, in trusted and untrsuted repos.
    # A domain policy has one of the following formats:
    #  0: block all domains
    #  1: allow all domains
    #  comma-delimited list of domain names (e.g. `example.com,example.org`): allow only these domains
    PFSC_MD_LINKS_FOR_TRUSTED_REPOS = os.getenv("PFSC_MD_LINKS_FOR_TRUSTED_REPOS", 1)
    PFSC_MD_LINKS_FOR_UNTRUSTED_REPOS = os.getenv("PFSC_MD_LINKS_FOR_TRUSTED_REPOS", 1)
    PFSC_MD_IMGS_FOR_TRUSTED_REPOS = os.getenv("PFSC_MD_IMGS_FOR_TRUSTED_REPOS", 1)
    PFSC_MD_IMGS_FOR_UNTRUSTED_REPOS = os.getenv("PFSC_MD_IMGS_FOR_UNTRUSTED_REPOS", "upload.wikimedia.org,commons.wikimedia.org")

    # The server can send emails for various reasons, such as 500s (internal
    # errors), and hosting requests. Configure the SMTP connection here.
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = bool(int(os.getenv("MAIL_USE_TLS", 1)))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    # From what email address should automatically generated emails be sent?
    # For example, 'no-reply@example.com'.
    MAIL_FROM_ADDR = os.environ.get('MAIL_FROM_ADDR')

    # Who should receive an email when there is a 500, internal system error?
    ERR_MAIL_RECIPS = parse_cd_list(os.environ.get('ERR_MAIL_RECIPS', ""))
    # Who should receive an email when a user requests hosting?
    HOSTING_REQ_REVIEWER_ADDRS = parse_cd_list(os.environ.get('HOSTING_REQ_REVIEWER_ADDRS', ""))

    # During testing, at times you may want to check your production setup to
    # see that emails can actually be sent, while at other times you may only
    # need to see the email printed. Set this True to print only.
    PRINT_EMAILS_INSTEAD_OF_SENDING = bool(int(os.getenv("PRINT_EMAILS_INSTEAD_OF_SENDING", 0)))

    # Email customization
    # The server comes with some "dummy templates" for transactional emails
    # (e.g. an email sent to the user when they have requested hosting).
    #
    # When running a production site, you should design your own template files.
    # These are Jinja2 templates. See https://jinja.palletsprojects.com/en/latest/.
    # You can copy and use the dummy templates (found in this project under
    # pfsc/templates/email) as a starting point.
    #
    # Set the EMAIL_TEMPLATE_DIR config var to the absolute filesystem
    # path pointing to the directory where your template files are found. The
    # filenames must be the same as those in pfsc/templates/email in this project.
    #
    # If EMAIL_TEMPLATE_DIR is not defined, the server will refuse to start in
    # production mode. You can define it to point to the pfsc/templates/email
    # directory if you choose to use the dummy templates.
    EMAIL_TEMPLATE_DIR = os.getenv("EMAIL_TEMPLATE_DIR", "")

    # If you choose to use the dummy templates for email -- or even if you use
    # some of the same format fields in your own custom templates -- the
    # following vars help you customize your emails.
    # An image with your own branding to be displayed at the top of emails sent
    # to users:
    EMAIL_BRANDING_IMG_URL = os.getenv("EMAIL_BRANDING_IMG_URL")
    # A title (alt text) for your branding image, in case user's email client
    # does not display images:
    EMAIL_BRANDING_IMG_TITLE = os.getenv("EMAIL_BRANDING_IMG_TITLE")
    # A phrase that describes the place where hosting happens, e.g. "on our website",
    # but probably involving your specific branding in some way. Should fit in
    # the sentence, "We've received your request to host your repo __________."
    HOSTING_PHRASE = os.getenv("HOSTING_PHRASE", "")

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    """
    Abstract base class for development configurations.
    """
    IS_DEV = True
    DEBUG = bool(int(os.getenv("DEBUG", 1)))
    PROPAGATE_EXCEPTIONS = bool(int(os.getenv("PROPAGATE_EXCEPTIONS", 1)))

    ALLOW_WIP = bool(int(os.getenv("ALLOW_WIP", 1)))

    PRINT_EMAILS_INSTEAD_OF_SENDING = True
    MAIL_FROM_ADDR = 'no-reply@localhost'
    EMAIL_TEMPLATE_DIR = os.path.join(BASE_DIR, 'pfsc', 'templates', 'email')
    EMAIL_BRANDING_IMG_URL = 'http://localhost:8888/email_banner.png'
    EMAIL_BRANDING_IMG_TITLE = 'Some Website'
    HOSTING_PHRASE = 'on our website'
    HOSTING_REQ_REVIEWER_ADDRS = ['reviewer1@localhost', 'reviewer2@localhost']

    MATHWORKER_SERVE_MINIFIED = bool(int(os.getenv("MATHWORKER_SERVE_MINIFIED", 0)))


class LocalDevConfig(DevelopmentConfig):
    """
    For use during development, when the Flask app is running on the local
    host (as opposed to in a docker container -- see DockerDevConfig).

    For example, this is the right configuration for running unit tests
    in an IDE or at the command line, but not for running tests in a web browser.
    """
    TESTING = True

    PFSC_ADD_ERR_NUM_TO_MSG = 1

    ALLOW_TEST_REPO_LOGINS = True
    ADMIN_USERS = ['test.admin']

    SOCKETIO_ASYNC_MODE = "threading"
    SOCKETIO_MESSAGE_QUEUE = None

    PFSC_SHADOWSAVE = 'all'
    PFSC_AUTOSAVEDELAY = 30000
    PFSC_RELOADFROMDISK = 'auto'
    PFSC_SAVEALLONAPPBLUR = 1

    # For testing PDF proxy system:
    # You must choose an actual host, along with a pdf URL that is present there,
    # and one that is not. This host must be on the approved list for the unit tests to work.
    # See tests/test_proxy_pdf.py.
    #PDF_TEST_HOSTNAME = 'example.org'
    PFSC_ENABLE_PDF_PROXY = 0
    PFSC_PDF_NETLOC_APPROVED = r"^(www\.)?(example\.(org|net))$"
    PFSC_PDF_NETLOC_BANNED = ""
    PDF_TEST_MISSING = 'http://example.org/does_not_exist.pdf'
    PDF_TEST_PRESENT = 'http://example.org/does_exist.pdf'
    PDF_TEST_PRESENT_UUID3 = 'uuid3 of does_exist.pdf'


class DockerDevConfig(DevelopmentConfig):
    """
    For use during development, when the Flask app is running in a docker
    container (as opposed to running on the local host  -- see LocalDevConfig).

    Thus, this is ordinarily the right config for a pfsc web server or pfsc RQ
    worker container deployed in a docker-compose.yml. This will then pertain to
    tests run through a web browser.
    """
    # For container-based development tasks, there are several settings which
    # we still want to be configurable via env vars, but for which we want to
    # change the _default_ value from false to true. Here `true` supports most
    # ordinary development tasks, but we occasionally do want to switch these
    # to `false` for certain specialized tests.
    ALLOW_TEST_REPO_LOGINS = bool(int(os.getenv("ALLOW_TEST_REPO_LOGINS", 1)))
    ISE_DEV_MODE = bool(int(os.getenv("ISE_DEV_MODE", 1)))
    BYPASS_CACHE_FOR_REPO_MODEL_LOAD = bool(int(os.getenv("BYPASS_CACHE_FOR_REPO_MODEL_LOAD", 1)))
    PFSC_MARKDOWN_ERR_MSG = int(os.getenv("PFSC_MARKDOWN_ERR_MSG", 1))

    PFSC_LIB_ROOT = "/home/pfsc/proofscape/lib"
    PFSC_BUILD_ROOT = "/home/pfsc/proofscape/build"
    PFSC_PDFLIB_ROOT = "/home/pfsc/proofscape/PDFLibrary"

    REDIS_URI = os.getenv("REDIS_URI") or "redis://redis:6379"

    SOCKETIO_MESSAGE_QUEUE = REDIS_URI

    # DockerDevConfig is used by the pfscweb and pfscworker containers in
    # the MCA (multi-container app) deployment generated by the pfsc-manage
    # project. There, we have an Nginx reverse proxy,
    # and we need to account for its X-Forwarded-... headers.
    # E.g. this makes it so we can successfully test OAuth logins, with Flask's
    # `url_for()` properly generating `https` redirects, based on what (by
    # virtue of the proxy fix) it sees as incoming `https` requests.
    PROXY_FIX_FOR = 1
    PROXY_FIX_PROTO = 1


class OcaConfig(DockerDevConfig):
    """
    Configure for deployment as the One-Container App.
    This is intended for use by a single user, on their own machine.
    """
    IS_OCA = True
    TESTING = False
    OCA_LATEST_VERSION_URL = 'https://raw.githubusercontent.com/proofscape/pfsc-manage/main/topics/pfsc/oca_version.txt'
    OCA_VERSION_FILE = "/home/pfsc/VERSION.txt"
    EULA_FILE = "/home/pfsc/EULA.txt"

    PERSONAL_SERVER_MODE = True
    ALLOW_WIP = True
    DEFAULT_HOSTING_STANCE = HostingStance.FREE
    SECRET_KEY = "fixed_value_for_the_oca"
    FORCE_RQ_SYNCHRONOUS = True
    ISE_DEV_MODE = True
    OFFER_SERVER_SIDE_NOTE_RECORDING = True
    REDIS_URI = "redis://localhost:6379"
    SOCKETIO_MESSAGE_QUEUE = "redis://localhost:6379"
    GRAPHDB_URI = "redis://localhost:6379"

    # The app URL prefix is important, so that the URL at which the ISE loads,
    # `localhost:7372/ProofscapeISE` is recognizable by the PBE (Proofscape
    # Browser Extension).
    APP_URL_PREFIX = "/ProofscapeISE"

    ISE_SERVE_LOCALLY = True
    ELKJS_SERVE_LOCALLY = True
    MATHJAX_SERVE_LOCALLY = True
    PYODIDE_SERVE_LOCALLY = True
    ISE_SERVE_MINIFIED = False
    MATHWORKER_SERVE_MINIFIED = False

    # Later we may set up demo repos for use in the OCA, but for now it's disabled.
    # Issues include:
    #  * shouldn't try to delete after 24h (or ever), because
    #    (a) we have no RQ scheduler, and
    #    (b) for one user there's no reason
    #  * shouldn't generate new demo repo copy for new session cookie.
    PROVIDE_DEMO_REPOS = False


class ProductionConfig(Config):
    """
    For use in production.
    """
    DEBUG = False
    TESTING = False
    PROPAGATE_EXCEPTIONS = False
    ISE_DEV_MODE = False
    PERSONAL_SERVER_MODE = False

    REQUIRE_CSRF_TOKEN = True
    MAIL_USE_TLS = True

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True
    # It is necessary that the samesite policy on the session cookie
    # be 'Lax', so that OAuth logins work.
    SESSION_COOKIE_SAMESITE = 'Lax'

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)


class ConfigName:
    LOCALDEV = 'localdev'
    DOCKERDEV = 'dockerdev'
    OCA = 'OCA'
    PRODUCTION = 'production'

config_lookup = {
    ConfigName.LOCALDEV: LocalDevConfig,
    ConfigName.DOCKERDEV: DockerDevConfig,
    ConfigName.OCA: OcaConfig,
    ConfigName.PRODUCTION: ProductionConfig,
}

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

import os
import pathlib
from contextlib import nullcontext

from flask import (
    Flask, has_app_context, current_app, request, redirect, url_for,
    has_request_context,
)
from flask.cli import AppGroup
from flask_socketio import SocketIO
from flask_login import LoginManager
from flask_mail import Mail
from werkzeug.middleware.proxy_fix import ProxyFix

from pfsc.constants import REDIS_CHANNEL, ISE_PREFIX
from pfsc.excep import PfscExcep, PECode
from config import (
    config_lookup, ProductionConfig,
    MATHJAX_VERSION, ELKJS_VERSION,
)

socketio = SocketIO()
pfsc_cli = AppGroup('pfsc')
login = LoginManager()
mail = Mail()


def get_config_name():
    # We deliberately do NOT supply a default value.
    # Default configuration is dangerous.
    # You must always explicitly say which configuration you want.
    return os.getenv('FLASK_CONFIG')


def get_config_class(config_name=None):
    if config_name is None:
        config_name = get_config_name()
    config_class = config_lookup.get(config_name)
    if config_class is None:
        raise Exception("You must choose a configuration for the Flask app!")
    return config_class


def check_config(var_name):
    """
    Retrieve the value of a configuration variable, for the current config.
    :param var_name: The name (string) of the config variable to be checked.
    :return: The value of the config variable, or `None` if it is undefined.
    """
    if has_app_context():
        config = current_app.config
        return config.get(var_name)
    else:
        config_class = get_config_class()
        return getattr(config_class, var_name, None)


def get_build_dir(cache_dir=False, sphinx_dir=False):
    """
    Get a directory for recording output files.

    :param cache_dir: leave False if you are recording build products like
        html or json files that are meant to be served for browsing; set True
        if you want to record cache files, which are build byproducts, and are
        not meant to be served.
    :param sphinx_dir: leave False for output from the native pfsc build; set
        True if you are recording output from the Sphinx part of the build.

    :return: pathlib.Path
    """
    build_dir = check_config("PFSC_BUILD_ROOT")
    parts = [build_dir]
    if cache_dir:
        parts.append('cache')
    else:
        parts.append('html')
    if sphinx_dir:
        parts.append('_sphinx')
    return pathlib.Path(*parts)


def local_url_for_static_file(relpath, req_env=None):
    """
    Build the local (no origin part) URL for a static file.

    :param relpath: the path of the file, relative to the static dir.
    :param req_env: optional dictionary, defining a request context (see
        docstring for `flask.app.Flask.test_request_context()`).
        If calling this function outside of a Flask request context:
            You can use this to make a fake request context, whose `url_adapter`
            will then be used by `url_for()` to build the URL. Otherwise, the
            app's `url_adapter` will be used (you must at least be inside an
            app context). The latter relies on the `APPLICATION_ROOT` and
            `SERVER_NAME` Flask config vars.
        If calling inside a request context, that context is used, and
            `req_env` is ignored.
    """
    ctx = (
        current_app.test_request_context(**req_env)
        if not has_request_context() and isinstance(req_env, dict)
        else nullcontext()
    )
    with ctx:
        return url_for('static', filename=relpath, _external=False)


def get_js_url(package_name, version=None):
    """
    Assemble the URL for a javascript asset.

    The result is controlled by config vars, determining things like whether
    to serve locally or from CDN, and whether to serve a debug or normal
    version.

    :param package_name: the name of the library
    :param version: optionally pass the string you want for the version number.
        If not given, the number from client/package-lock.json is used.
    """
    if package_name == 'mathjax':
        version = version or MATHJAX_VERSION
        return (
            local_url_for_static_file(f'mathjax/v{version}/tex-svg.js', req_env={})
            if check_config("MATHJAX_SERVE_LOCALLY") else
            f'https://cdn.jsdelivr.net/npm/mathjax@{version}/es5/tex-svg.js'
        )
    if package_name == 'elkjs':
        version = version or ELKJS_VERSION
        return (
            local_url_for_static_file(
                f'elk/v{version}/elk{"-api" if check_config("ELK_DEBUG") else ".bundled"}.js',
                req_env={}
            )
            if check_config("ELKJS_SERVE_LOCALLY") else
            f'https://cdn.jsdelivr.net/npm/elkjs@{version}/lib/elk.bundled.js'
        )


def get_app():
    """
    Get a Proofscape Flask app, preferring the current one, or making a new
    one if there is none.

    @return: pair (app, new) where app is a Flask app, and new is a boolean
        saying whether this is a newly formed app.
    """
    if has_app_context():
        return current_app, False
    return make_app(), True


def make_app(config_name=None):
    """
    Form a new Proofscape Flask app.
    """
    # Make sure we have a config_name, for settings below that may use this.
    if config_name is None:
        config_name = get_config_name()
    else:
        os.environ["FLASK_CONFIG"] = config_name
    config_class = get_config_class(config_name)

    PREFIX = config_class.APP_URL_PREFIX
    config_class.SOCKETIO_PATH = f'{PREFIX}/socket.io'

    app = Flask(
        __name__,
        static_url_path=f'{PREFIX}/static',
        static_folder='../static',
    )

    # See
    #  <https://flask.palletsprojects.com/en/2.1.x/api/#flask.Flask.wsgi_app>
    #  <https://github.com/pallets/flask/issues/3256#issuecomment-500217747>
    # on the proper way to apply middlewares to a Flask app, by using the
    # `app.wsgi_app` attribute, as we do here:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=config_class.PROXY_FIX_FOR,
        x_proto=config_class.PROXY_FIX_PROTO,
        x_host=0, x_port=0, x_prefix=0
    )
    app.config.from_object(config_class)
    config_class.init_app(app)

    # Certain config vars (a) lack a default value in the base `Config` class,
    # but (b) _must_ have a value for ordinary functioning. Thus, it is up to
    # the operator to choose a combination of FLASK_CONFIG and .env file to
    # ensure these vars have values. Here we perform a simple check that they
    # are at least defined.
    essential_vars = """
    REDIS_URI
    GRAPHDB_URI
    PFSC_BUILD_ROOT
    PFSC_LIB_ROOT
    SECRET_KEY
    """.split()
    num_ev = len(essential_vars)
    # Some config vars can be undefined in development, but must have a value
    # in production.
    production_essential_vars = """
    EMAIL_TEMPLATE_DIR
    """.split()
    if config_class == ProductionConfig:
        essential_vars.extend(production_essential_vars)
    for i, var in enumerate(essential_vars):
        if not app.config.get(var):
            msg = f'Config var `{var}` is not defined.'
            msg += f' Server cannot run{" in production" if i >= num_ev else ""}.'
            msg += ' Review choice of FLASK_CONFIG and .env file to ensure this var is defined.'
            raise PfscExcep(msg, PECode.ESSENTIAL_CONFIG_VAR_UNDEFINED)

    trusted_lps = set(
        app.config.get("PFSC_TRUSTED_LIBPATHS", []) +
        app.config.get("PFSC_DEFAULT_TRUSTED_LIBPATHS", [])
    )
    if check_config("TRUST_LIBPATH_GH_PROOFSCAPE"):
        trusted_lps.add('gh.proofscape')
    trusted_prefixes = {}
    # Check that trusted libpaths are well-formed.
    for lp in trusted_lps:
        p = lp.split('.')
        if len(p) < 2 and p != ['lh']:
            msg = 'PFSC_TRUSTED_LIBPATHS config var is malformed.'
            msg += ' With the exception of `lh`, all trusted libpaths must be at least two segments long.'
            raise PfscExcep(msg, PECode.MALFORMED_CONFIG_VAR)
        trusted_prefixes[lp] = True
    from pfsc.build.lib.prefix import LibpathPrefixMapping
    app.config['trusted_prefix_mapping'] = LibpathPrefixMapping(trusted_prefixes)

    socketio.init_app(
        app,
        path=config_class.SOCKETIO_PATH,
        async_mode=config_class.SOCKETIO_ASYNC_MODE,
        message_queue=config_class.SOCKETIO_MESSAGE_QUEUE,
        channel=REDIS_CHANNEL,
        # These are very helpful in debugging:
        #logger=True,
        #engineio_logger=True,
    )

    login.init_app(app)
    mail.init_app(app)

    app.cli.add_command(pfsc_cli)
    import pfsc.blueprints.cli

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from pfsc import gdb
    gdb.init_app(app)

    @login.user_loader
    def load_user(username):
        return gdb.get_graph_reader().load_user(username)

    from . import rq
    rq.init_app(app)

    from pfsc.blueprints import vstat
    app.register_blueprint(vstat.bp, url_prefix=PREFIX)

    from pfsc.blueprints import root
    app.register_blueprint(root.bp, url_prefix=PREFIX)

    from pfsc.blueprints import ise
    app.register_blueprint(ise.bp, url_prefix=PREFIX + ISE_PREFIX)

    from pfsc.blueprints import docs
    app.register_blueprint(docs.bp, url_prefix=PREFIX + '/docs')

    from pfsc.blueprints import oca
    app.register_blueprint(oca.bp, url_prefix=PREFIX + '/oca')

    # In some deployments -- notably the OCA or one-container-app -- there
    # may be a nonempty PREFIX under which the app is meant to be accessed,
    # even while _all_ URLs -- even those that do not begin with this PREFIX
    # -- are routed to this Flask app. In such cases it will be important to
    # redirect the root URL '/' to that under which the ISE is meant to load,
    # so that users navigating to the server will get the right page.
    app_load_url = PREFIX or '/'
    def bounce_to_app():
        return redirect(app_load_url)
    root_url = '/'
    for url in {root_url} - {app_load_url}:
        app.add_url_rule(url, view_func=bounce_to_app)

    from pfsc.blueprints import windowpeers
    # The windowpeers module actually no longer defines a Blueprint; it only
    # registers SocketIO handlers. So importing it is enough.

    from pfsc.blueprints import auth
    app.register_blueprint(auth.bp, url_prefix=PREFIX + '/auth')

    from pfsc.methods import proxy_or_render

    @app.errorhandler(404)
    def page_not_found(error):
        html = proxy_or_render("ERR_404_PROXY_URL", "error.html",
            title="Proofscape Error",
            css=[
                url_for('vstat.static', filename='css/base.css'),
            ],
            img_src=url_for('vstat.static', filename='img/404.png'),
            msg="Page not found!",
        )
        return html, 404

    @app.errorhandler(500)
    def handle_internal_error(error):
        import sys, datetime
        from pfsc.email import send_error_report_mail

        hidden_fields = ["CSRF", "SID"]
        values = {k:v for k, v in request.values.items() if k not in hidden_fields}
        body = f'{datetime.datetime.utcnow()}\n{request.base_url}\n{values}\n{error}\n'
        send_error_report_mail(body=body, exc_info=sys.exc_info())

        html = proxy_or_render("ERR_500_PROXY_URL", "error.html",
            title="Proofscape Error",
            css=[
                url_for('vstat.static', filename='css/base.css'),
            ],
            img_src=url_for('vstat.static', filename='img/500.png'),
            msg="Internal System Error!",
        )
        return html, 500

    REFERRER_POLICY = app.config.get("REFERRER_POLICY")
    @app.after_request
    def set_headers(response):
        response.headers["Referrer-Policy"] = REFERRER_POLICY
        return response

    return app

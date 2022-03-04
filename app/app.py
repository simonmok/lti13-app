import datetime
import os
import pprint

from tempfile import mkdtemp
from flask import Flask, jsonify, render_template, url_for
from flask_caching import Cache
from pylti1p3.contrib.flask import FlaskOIDCLogin, FlaskMessageLaunch, FlaskRequest, FlaskCacheDataStorage
from pylti1p3.deep_link_resource import DeepLinkResource
from pylti1p3.tool_config import ToolConfJsonFile
from pylti1p3.registration import Registration


class ReverseProxied(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        scheme = environ.get('HTTP_X_FORWARDED_PROTO')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


app = Flask('lti-app', template_folder='templates', static_folder='static')
app.wsgi_app = ReverseProxied(app.wsgi_app)

config = {
    "DEBUG": False,
    "ENV": "development",
    "CACHE_TYPE": "simple",
    "CACHE_DEFAULT_TIMEOUT": 600,
    "SECRET_KEY": "some_secure_secret",
    "SESSION_TYPE": "filesystem",
    "SESSION_FILE_DIR": mkdtemp(),
    "SESSION_COOKIE_NAME": "flask-session-id",
    "SESSION_COOKIE_HTTPONLY": True,
    "SESSION_COOKIE_SECURE": True,
    "SESSION_COOKIE_SAMESITE": None,
    "DEBUG_TB_INTERCEPT_REDIRECTS": False
}

app.config.from_mapping(config)
cache = Cache(app)


def get_lti_config_path():
    return os.path.join(app.root_path, '..', 'config', 'app.json')


def get_launch_data_storage():
    return FlaskCacheDataStorage(cache)


@app.route('/login/', methods=['GET'])
def login():
    print('Login URL')
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    launch_data_storage = get_launch_data_storage()
    flask_request = FlaskRequest()
    target_link_uri = flask_request.get_param('target_link_uri')
    if not target_link_uri:
        raise Exception('Missing target_link_uri parameter')

    oidc_login = FlaskOIDCLogin(flask_request, tool_conf, launch_data_storage=launch_data_storage)
    print('Redirect data', oidc_login.enable_check_cookies().redirect(target_link_uri).data.decode("utf-8"))
    return oidc_login.enable_check_cookies().redirect(target_link_uri)


@app.route('/launch', methods=['POST'])
def launch():
    print('Launch page')
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    message_launch = FlaskMessageLaunch(flask_request, tool_conf, launch_data_storage=launch_data_storage)
    print('Getting ID token', flask_request.get_param('id_token'))
    message_launch_data = message_launch.get_launch_data()
    pprint.pprint(message_launch_data)
    print('Launch ID', message_launch.get_launch_id())
    args = {
        'launch_data': message_launch_data,
        'user_name': message_launch_data.get('name')
    }
    return render_template('app.html', **args)


@app.route('/jwks/', methods=['GET'])
def get_jwks():
    print('JWKS page')
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    return jsonify({'keys': tool_conf.get_jwks()})


if __name__ == '__main__':
    app.run(host='localhost', port=8080)

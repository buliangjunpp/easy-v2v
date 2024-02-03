import sys
import eventlet
from flask import Flask, Blueprint
from flask_restx import Api

from v2v.api.v1.clouds import ns_clouds
from v2v.api.v1.flavors import ns_flavors
from v2v.api.v1.networks import ns_networks
from v2v.api.v1.servers import ns_servers
from v2v.api.v1.tasks import ns_tasks
from v2v.api.v1.license import ns_license
from v2v.api.v1.volumes import ns_volumes
import v2v.conf
from v2v import config

eventlet.monkey_patch()

CONF = v2v.conf.CONF


def register_blueprints(app):
    bp_api = Blueprint('api', __name__)
    api_version_1 = Api(version='v1', prefix='/v1', doc=CONF.use_doc)
    api_version_1.init_app(bp_api, add_specs=CONF.add_specs)
    api_version_1.add_namespace(ns_clouds, '/clouds')
    api_version_1.add_namespace(ns_flavors, '/flavors')
    api_version_1.add_namespace(ns_networks, '/networks')
    api_version_1.add_namespace(ns_servers, '/servers')
    api_version_1.add_namespace(ns_tasks, '/tasks')
    api_version_1.add_namespace(ns_license, '/license')
    api_version_1.add_namespace(ns_volumes, '/volumes')
    app.register_blueprint(bp_api, url_prefix='/v2v')


def create_app():
    config.parse_args(sys.argv[4:], default_config_files=['/etc/v2v/v2v.conf'])
    app = Flask(__name__)
    app.config.from_object(config.AppConfig)
    register_blueprints(app)
    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6080)

from flask_restx import Namespace, Resource
from v2v.common.utils import resp_message, get_request_info
from v2v.api.v1.api import v2v_api

ns_servers = Namespace('servers', description="Endpoint to manage servers")


@ns_servers.route('', methods=['GET', 'POST'])
class Servers(Resource):
    """manage server"""

    def get(self):
        """
        获取server列表

        :return:
        """
        request_info = get_request_info()
        args_data = request_info.get('args_data')
        cloud_uuid = args_data.get('cloud')
        if not cloud_uuid:
            return resp_message(success=False, code=400, message='cloud uuid is need for get VMware instances.')
        servers = v2v_api.list_servers(cloud_uuid)
        if not isinstance(servers, list):
            return resp_message(success=False, code=400, message=servers.get('msg'))
        return resp_message(servers)

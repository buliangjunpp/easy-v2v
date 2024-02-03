from flask_restx import Namespace, Resource
from v2v.common.utils import resp_message, get_request_info
from v2v.api.v1.api import v2v_api

ns_networks = Namespace('networks', description="Endpoint to manage networks")


@ns_networks.route('', methods=['GET', 'POST'])
class Networks(Resource):
    """manage network"""

    def get(self):
        """
        获取network列表

        :return:
        """
        request_info = get_request_info()
        args_data = request_info.get('args_data')
        cloud_uuid = args_data.get('cloud')
        if not cloud_uuid:
            return resp_message(success=False, code=400, message='cloud uuid is need for get es network.')
        networks = v2v_api.list_networks(cloud_uuid)
        return resp_message(networks)

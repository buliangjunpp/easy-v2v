from flask_restx import Namespace, Resource
from v2v.common.utils import resp_message, get_request_info
from v2v.api.v1.api import v2v_api

ns_volumes = Namespace('volumes', description="Endpoint to manage volumes")


@ns_volumes.route('/type', methods=['GET'])
class Types(Resource):
    """manage volume type"""

    def get(self):
        """
        获取volume type列表

        :return:
        """
        request_info = get_request_info()
        args_data = request_info.get('args_data')
        cloud_uuid = args_data.get('cloud')
        if not cloud_uuid:
            return resp_message(success=False, code=400, message='cloud uuid is need for get es volume type.')
        types = v2v_api.list_volume_types(cloud_uuid)
        return resp_message(types)

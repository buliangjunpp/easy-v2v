from flask_restx import Namespace, Resource
from v2v.common.utils import resp_message, get_request_info
from v2v.api.v1.api import v2v_api

ns_flavors = Namespace('flavors', description="Endpoint to manage flavors")


@ns_flavors.route('', methods=['GET'])
class Flavors(Resource):
    """manage flavor"""

    def get(self):
        """
        获取flavor列表

        :return:
        """
        request_info = get_request_info()
        args_data = request_info.get('args_data')
        cloud_uuid = args_data.get('cloud')
        if not cloud_uuid:
            return resp_message(success=False, code=400, message='cloud uuid is need for get es flavor.')
        flavors = v2v_api.list_flavors(cloud_uuid)
        return resp_message(flavors)

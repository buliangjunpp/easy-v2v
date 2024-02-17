from flask_restx import Namespace, Resource
from v2v.common.utils import resp_message, get_request_info
from v2v.api.v1.api import v2v_api
from v2v.api.schema.cloud_schema import create_license_schema

ns_license = Namespace('license', description="Endpoint to manage license")


@ns_license.route('', methods=['GET', 'POST'])
class Licenses(Resource):
    """manage license"""

    def get(self):
        """
        获取license列表

        :return:
        """
        licenses = v2v_api.list_license()
        return resp_message(licenses)

    @ns_license.expect(
        ns_license.schema_model('create license', create_license_schema), validate=True)
    def post(self):
        """
        新增license

        :return:
        """
        request_data = get_request_info()
        data = request_data.get('json_data')
        try:
            license = v2v_api.create_license(**data)
        except Exception as ex:
            return resp_message(success=False, code=400, message=str(ex))

        return resp_message(license)


@ns_license.route("/<string:uuid>")
class License(Resource):

    def get(self, uuid):
        """
        获取单个license信息

        :param uuid:
        :return:
        """
        task = v2v_api.list_license_by_uuid(uuid)
        return resp_message(task)

    @ns_license.expect(
        ns_license.schema_model('create license', create_license_schema), validate=True)
    def put(self, uuid):
        """
        更新license

        :return:
        """
        request_data = get_request_info()
        data = request_data.get('json_data')
        try:
            license = v2v_api.update_license_by_uuid(uuid, **data)
        except Exception as ex:
            return resp_message(success=False, code=400, message=str(ex))

        return resp_message(license)

    def delete(self, uuid):
        """删除指定license

        :param uuid:
        :return:
        """
        return resp_message(v2v_api.delete_license_by_uuid(uuid))

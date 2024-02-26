from flask_restx import Namespace, Resource
from v2v.common.utils import resp_message, get_request_info
from v2v.api.v1.api import v2v_api
from v2v.api.schema.cloud_schema import create_openstack_schema, create_vmware_schema

ns_clouds = Namespace('clouds', description="Endpoint to manage clouds")


@ns_clouds.route('/openstack', methods=['GET', 'POST'])
class OpenStackClouds(Resource):
    """manage openstack clouds"""

    def get(self):
        """
        获取注册过的openstack cloud认证列表

        :return:
        """
        clouds = v2v_api.list_openstack()
        return resp_message(clouds)

    @ns_clouds.expect(
        ns_clouds.schema_model('create openstack cloud', create_openstack_schema), validate=True)
    def post(self):
        """
        注册openstack cloud认证信息

        :return:
        """
        request_data = get_request_info()
        data = request_data.get('json_data')
        cloud = v2v_api.create_openstack(**data)
        return resp_message(cloud)


@ns_clouds.route("/openstack/<string:uuid>")
class OpenStackCloud(Resource):

    def get(self, uuid):
        """
        获取单个openstack cloud 认证信息

        :param uuid:
        :return:
        """
        cloud = v2v_api.list_openstack_by_uuid(uuid)
        return resp_message(cloud)


    def put(self, uuid):
        """
        修改单个openstack cloud 认证信息

        :param uuid:
        :return:
        """
        pass

    def delete(self, uuid):
        """删除指定openstack cloud认证信息

        :param uuid:
        :return:
        """
        try:
            resp = v2v_api.delete_openstack_by_uuid(uuid)
        except Exception as ex:
            return resp_message(success=False, code=400, message=str(ex))
        return resp_message(resp)


@ns_clouds.route('/vmware', methods=['GET', 'POST'])
class VMwareClouds(Resource):
    """manage vmware clouds"""

    def get(self):
        """
        获取注册过的vmware cloud认证列表

        :return:
        """
        clouds = v2v_api.list_vmware()
        return resp_message(clouds)

    @ns_clouds.expect(
        ns_clouds.schema_model('create vmware cloud', create_vmware_schema), validate=True)
    def post(self):
        """
        注册vmware cloud认证信息

        :return:
        """
        request_data = get_request_info()
        data = request_data.get('json_data')
        cloud = v2v_api.create_vmware(**data)
        return resp_message(cloud)


@ns_clouds.route("/vm/<string:uuid>")
class VMwareCloud(Resource):

    def get(self, uuid):
        """
        获取单个vmware cloud 认证信息

        :param uuid:
        :return:
        """
        cloud = v2v_api.list_vmware_by_uuid(uuid)
        return resp_message(cloud)

    def put(self, uuid):
        """
        修改vmware cloud 认证信息

        :param uuid:
        :return:
        """
        pass

    def delete(self, uuid):
        """删除指定vmvare cloud认证信息

        :param uuid:
        :return:
        """
        try:
            resp = v2v_api.delete_vmware_by_uuid(uuid)
        except Exception as ex:
            return resp_message(success=False, code=400, message=str(ex))
        return resp_message(resp)

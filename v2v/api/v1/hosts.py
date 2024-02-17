from flask_restx import Namespace, Resource
from v2v.common.utils import resp_message, get_request_info
from v2v.api.v1.api import v2v_api
from v2v.api.schema.cloud_schema import update_hosts_schema

ns_hosts = Namespace('hosts', description="Endpoint to manage hosts")


@ns_hosts.route('/domain', methods=['GET', 'PUT'])
class Domains(Resource):
    """manage /etc/hosts"""

    def get(self):
        """
        获取 /etc/hosts 内容

        :return:
        """
        hosts = v2v_api.list_hosts()
        return resp_message(hosts)

    @ns_hosts.expect(
        ns_hosts.schema_model('update hosts', update_hosts_schema), validate=True)
    def put(self):
        """
        更新 /etc/hosts 内容

        :return:
        """
        request_data = get_request_info()
        data = request_data.get('json_data')
        try:
            hosts = v2v_api.update_hosts(**data)
        except Exception as ex:
            return resp_message(success=False, code=400, message=str(ex))

        return resp_message(hosts)

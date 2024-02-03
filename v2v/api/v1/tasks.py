from flask_restx import Namespace, Resource
from v2v.common.utils import resp_message, get_request_info
from v2v.api.v1.api import v2v_api
from v2v.api.schema.cloud_schema import create_task_schema, task_action_schema

ns_tasks = Namespace('tasks', description="Endpoint to manage tasks")


@ns_tasks.route('', methods=['GET', 'POST'])
class Tasks(Resource):
    """manage task"""

    def get(self):
        """
        获取task列表

        :return:
        """
        tasks = v2v_api.list_tasks()
        return resp_message(tasks)

    @ns_tasks.expect(
        ns_tasks.schema_model('create convert task', create_task_schema), validate=True)
    def post(self):
        """
        新增迁移task

        :return:
        """
        request_data = get_request_info()
        data = request_data.get('json_data')
        try:
            task = v2v_api.create_task(**data)
        except Exception as ex:
            return resp_message(success=False, code=400, message=str(ex))

        return resp_message(task)


@ns_tasks.route("/<string:uuid>")
class Task(Resource):

    def get(self, uuid):
        """
        获取单个task信息

        :param uuid:
        :return:
        """
        task = v2v_api.list_task_by_uuid(uuid)
        return resp_message(task)

    def delete(self, uuid):
        """删除指定task

        :param uuid:
        :return:
        """
        return resp_message(v2v_api.delete_task_by_uuid(uuid))


@ns_tasks.route("/<string:uuid>/action")
class TaskAction(Resource):

    @ns_tasks.expect(
        ns_tasks.schema_model('task action', task_action_schema), validate=True)
    def post(self, uuid):
        """
        针对task执行其他操作，例如重试

        :param uuid:
        :return:
        """
        request_data = get_request_info()
        data = request_data.get('json_data')
        try:
            task = v2v_api.action_task(uuid, **data)
        except Exception as ex:
            return resp_message(success=False, code=400, message=str(ex))
        return resp_message(task)

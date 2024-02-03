import json
import uuid
import types
import functools
from oslo_log import log as logging
from dateutil import tz
from datetime import datetime
from pyVmomi import vim
import oslo_messaging as messaging
from oslo_context import context
import v2v.conf
from v2v import rpc
from v2v.db import api as db_api
from v2v.db.models import Openstack, VMware, Task, License
from v2v.cloud.openstack import OpenStack
from v2v.cloud.vsphere import vSphere
from v2v.common import utils
from v2v.common.encryption import decrypt

LOG = logging.getLogger(__name__)
CONF = v2v.conf.CONF


def logger_decorator(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        LOG.info(f"Start {func.__name__}, args={args}, kwargs={kwargs}")
        return func(self, *args, **kwargs)
    return wrapper


class LogMeta(type):
    def __new__(cls, name, bases, attrs):
        for k, v in attrs.items():
            if not k.startswith("_") and isinstance(v, types.FunctionType):
                attrs[k] = logger_decorator(v)
        return type.__new__(cls, name, bases, attrs)


def check_server_numbers(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        licenses = db_api.get_all(License, to_dict=False)
        filters = {'state': ['succeed', 'running']}
        tasks = db_api.task_get_all_by_filter(filters)

        if not licenses and len(tasks) >= CONF.allowed_server_number:
            raise Exception('Exceeded maximum quantity limit')
        license = licenses[-1]
        license = json.loads(decrypt(license.license))
        uuid = license.get('uuid')
        if uuid != utils.get_host_uuid():
            raise Exception('License is illegal')

        server_num = int(license.get('server'))
        if server_num <= len(tasks):
            raise Exception('Exceeded the maximum license limit')

        expired_at = license.get('expired_at')
        if expired_at != '-1' and expired_at < str(datetime.utcnow()):
            raise Exception('License has expired')

        return func(*args, **kwargs)

    return wrapper


class API(object, metaclass=LogMeta):

    def __init__(self):
        pass

    def _detail_license(self, license):
        l = json.loads(decrypt(license.get('license')))
        l.pop('uuid', None)
        license['license'] = l
        return license

    def list_license(self):
        licenses = db_api.get_all(License)
        return [self._detail_license(l) for l in licenses]

    def create_license(self, **kwargs):
        kwargs['uuid'] = str(uuid.uuid4())
        db_api.create(License(**kwargs))

    def list_license_by_uuid(self, uuid):
        license = db_api.get_by_uuid(License, uuid)
        return self._detail_license(license)

    def update_license_by_uuid(self, uuid, **kwargs):
        db_api.license_update_by_uuid(uuid, kwargs.get('license'))

    def delete_license_by_uuid(self, uuid):
        return db_api.delete_by_uuid(License, uuid)

    def list_task_by_uuid(self, uuid):
        return db_api.get_by_uuid(Task, uuid)

    def delete_task_by_uuid(self, uuid):
        return db_api.delete_by_uuid(Task, uuid)

    def list_tasks(self):

        def _detail(task):
            if task is None:
                return {}
            for i in ('src_server', 'dest_server'):
                task[i] = json.loads(task[i])
            task['src_cloud'] = self.list_vmware_by_uuid(task['src_cloud'])
            task['dest_cloud'] = self.list_openstack_by_uuid(task['dest_cloud'])
            return task

        tasks = db_api.get_all(Task)
        return [_detail(t) for t in tasks]

    @check_server_numbers
    def create_task(self, **kwargs):
        for i in ('src_server', 'dest_server'):
            kwargs[i] = json.dumps(kwargs[i])
        kwargs['state'] = 'init'
        kwargs['percent'] = 0
        kwargs['uuid'] = str(uuid.uuid4())
        task = db_api.create(Task(**kwargs))
        self.async_task(task.uuid)
        return {'task_id': task.uuid}

    def action_task(self, uuid, **kwargs):
        task = db_api.get_by_uuid(Task, uuid, to_dict=False)
        if not task:
            raise Exception(f'no task with uuid={uuid}')
        action = kwargs.get('action')
        if action == 'retry':
            return self.retry_task(uuid, task)

    def retry_task(self, uuid, task):
        if task.state not in ('aborted', 'failed'):
            raise Exception(f'task with uuid={uuid} and state={task.state} not support retry')
        self.async_task(uuid)

    def async_task(self, task_id):
        ctxt = context.get_admin_context()
        target = messaging.Target(topic='manager')
        rpc_client = rpc.get_client(target=target)
        cctxt = rpc_client.prepare(namespace='v2v', server=CONF.host, version='1.0')
        return cctxt.cast(ctxt=ctxt, method='task', task_id=task_id)

    def transfer_to_local_time(self, utc_time):
        # UTC Zone
        from_zone = tz.gettz('UTC')
        # China Zone
        to_zone = tz.gettz('CST')

        # Tell the datetime object that it's in UTC time zone
        utc = utc_time.replace(tzinfo=from_zone)

        # Convert time zone
        local = utc.astimezone(to_zone)
        local_time = datetime.strftime(local, "%Y-%m-%d %H:%M:%S")
        return local_time

    def list_openstack(self):
        return db_api.get_all(Openstack)

    def create_openstack(self, **kwargs):
        kwargs['uuid'] = str(uuid.uuid4())
        db_api.create(Openstack(**kwargs))

    def list_openstack_by_uuid(self, uuid):
        return db_api.get_by_uuid(Openstack, uuid)

    def delete_openstack_by_uuid(self, uuid):
        return db_api.delete_by_uuid(Openstack, uuid)

    def list_vmware(self):
        return db_api.get_all(VMware)

    def create_vmware(self, **kwargs):
        kwargs['uuid'] = str(uuid.uuid4())
        db_api.create(VMware(**kwargs))

    def list_vmware_by_uuid(self, uuid):
        return db_api.get_by_uuid(VMware, uuid)

    def delete_vmware_by_uuid(self, uuid):
        return db_api.delete_by_uuid(VMware, uuid)

    def list_volume_types(self, cloud_uuid):
        cloud = db_api.get_by_uuid(Openstack, cloud_uuid)
        types = OpenStack(cloud).cinder.list_types()
        return [t.to_dict() for t in types]

    def list_flavors(self, cloud_uuid):
        cloud = db_api.get_by_uuid(Openstack, cloud_uuid)
        flavors = OpenStack(cloud).nova.flavor_list()
        return [f.to_dict() for f in flavors]

    def list_networks(self, cloud_uuid):
        cloud = db_api.get_by_uuid(Openstack, cloud_uuid)
        return OpenStack(cloud).neutron.net_list().get('networks', [])

    def list_servers(self, cloud_uuid):

        def _disk_number(disk_device):
            disk_num = 0
            for device in disk_device:
                if device.__class__.__name__ == 'vim.vm.device.VirtualDisk':
                    disk_num = disk_num + 1
            return disk_num

        def _detail(s):
            if s is None:
                return {}
            return {
                "name": s.get("name"),
                'template': s.get("config.template"),
                "os": s.get("guest.guestFullName"),
                "hostName": s.get("guest.hostName"),
                "ipAddress": s.get("guest.ipAddress"),
                "numCpu": s.get("config.hardware.numCPU"),
                "memoryGB": str(s.get("config.hardware.memoryMB") / 1024),
                "diskGB": str("%.2f" % (s.get("summary.storage.committed") / 1024 ** 3)),
                "diskNum": _disk_number(s.get("config.hardware.device")),
                "driver": None,
                "toolsStatus": s.get("guest.toolsStatus"),
                "toolsRunningStatus": s.get("guest.toolsRunningStatus"),
                "powerState": s.get("runtime.powerState")
            }
        cloud = db_api.get_by_uuid(VMware, cloud_uuid)
        servers = self._list_servers_on_exsi(cloud.get('ip'), cloud.get('user'), cloud.get('password'), cloud.get('uri'))
        if not isinstance(servers, list):
            return servers

        servers_list = []
        for server in servers:
            try:
                server = _detail(server)
                if not server.get('template', False):
                    servers_list.append(server)
            except KeyError:
                pass
        return servers_list

    def _list_servers_on_exsi(self, ip, user, pwd, uri):
        """ List servers and templates on specified ESXi

        :param ip: The Ip address of vcenter
        :param user: The username of vcenter
        :param pwd: The password of vcenter
        :param uri: The uri of ESXi will be searched
        :returns: dict or list
            when return is dict, the return is fault message
            of connect to vcenter or search uri.
            when return is list. the return is list of servers
            and templates.
        """
        # Ensure the uri does not start with '/'
        # and end with '/'
        if uri.startswith('/'):
            uri = uri.split('/', 1)[1]
        if uri.endswith('/'):
            uri = uri.rsplit('/', 1)[0]

        uri = uri.split('/')

        with vSphere(host=ip, user=user, pwd=pwd) as vs:
            if vs.si is None:
                return {
                    "msg": "Could not connect to the specified vcenter "
                           "using specified username and password."
                }

            datacenters = vs.si.content.rootFolder.childEntity
            find_dc = False
            for dc in datacenters:
                if dc.name == uri[0]:
                    find_dc = True
                    break

            if not find_dc:
                LOG.error("Could not find specified datacenter %s." % dc.name)
                return {"msg": "Could not find specified datacenter." % dc.name}

            hosts = vs.get_container_view(dc, [vim.HostSystem])
            find_host = False
            for host in hosts:
                if host.name == uri[-1]:
                    find_host = True
                    break

            if not find_host:
                LOG.error("Could not find specified esxi %s." % host.name)
                return {"msg": "Could not find specified esxi %s." % host.name}

            prop_spec = {
                "VirtualMachine": ["name", "guest.toolsStatus", "guest.toolsRunningStatus",
                                   "guest.guestFullName", "guest.hostName", "guest.ipAddress",
                                   "runtime.powerState", "config.template", "config.hardware.device", "config.hardware.numCPU",
                                   "config.hardware.memoryMB", "summary.storage.committed"]
            }
            servers = vs.property_collector(host, [vim.VirtualMachine], prop_spec)
            return servers


v2v_api = API()

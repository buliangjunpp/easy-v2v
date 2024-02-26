import traceback
import eventlet.event
import subprocess
import os
import tempfile
import time
import re
import json
import six
import sys
import math
import v2v.conf
from oslo_log import log as logging
import oslo_messaging as messaging
from v2v.db import api as db_api
from v2v.db.models import VMware, Openstack
from v2v.db.models import Task as Task_db
from v2v import manager
from v2v.common import utils


LOG = logging.getLogger(__name__)
CONF = v2v.conf.CONF

VIRT_V2V = '/usr/bin/virt-v2v'

DEVNULL = subprocess.DEVNULL

LOG_DIR = '/var/log/v2v'
WORK_DIR = '/var/lib/v2v'
DEFAULT_OPENRC = {
    'OS_IDENTITY_API_VERSION': '3',
    'OS_PROJECT_DOMAIN_NAME': 'Default',
    'OS_PROJECT_NAME': 'admin',
    'OS_USER_DOMAIN_NAME': 'Default',
    'OS_USERNAME': 'admin',
    'OS_PASSWORD': 'Admin@ES20!9',
    'OS_AUTH_URL': 'http://keystone.opsl2.svc.cluster.local:80/v3',
    'OS_REGION_NAME': 'RegionOne',
    'OS_ENDPOINT_TYPE': 'publicURL',
    'OS_INTERFACE': 'publicURL',
    'PYTHONIOENCODING': 'UTF-8'
}


class STATUS:
    '''
    INIT: request granted and starting the convert process
    RUNNING: copying disk and covert in progress
    ABORTED: user initiated aborted
    FAILED: error during covert process
    SUCCEED: convert process successfully finished
    '''
    INIT = 'init'
    RUNNING = 'running'
    ABORTED = 'aborted'
    FAILED = 'failed'
    SUCCEED = 'succeed'


class V2VManager(manager.Manager):
    """v2v Manager
    """
    target = messaging.Target(version='1.0')

    def __init__(self, *args, **kwargs):
        super(V2VManager, self).__init__(service_name='v2v-agent', *args, **kwargs)
        self.v2v_task = V2VTaskManager()
        self.additional_endpoints.append(self.v2v_task)
        LOG.info(f'Agent is start at {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}')


class V2VTaskManager(object):
    target = messaging.Target(namespace='v2v', version='1.0')

    def __init__(self):
        super(V2VTaskManager, self).__init__()
        if CONF.max_concurrent_tasks != 0:
            self._task_semaphore = eventlet.semaphore.Semaphore(
                CONF.max_concurrent_tasks)
        else:
            self._task_semaphore = utils.UnlimitedSemaphore()

    def task(self, ctxt, *args, **kwargs):
        """Do actual v2v task

        :param ctxt: request context
        :param args: the arguments
        """
        task_id = kwargs.get('task_id')
        LOG.info(f'Beginning with task={task_id}')
        start_time = time.time()
        try:
            with self._task_semaphore:
                wait_time = time.time()
                LOG.info(f'Waiting {wait_time-start_time}s and now to start task={task_id}')
                task = db_api.get_by_uuid(Task_db, task_id)
                if task.get('state') == STATUS.INIT:
                    pass
                # In retry
                elif task.get('state') in (STATUS.ABORTED, STATUS.FAILED):
                    LOG.info(f'task with id={task_id} has state={task.get("state")} and now retry')
                    db_api.task_update_state_by_uuid(task_id, STATUS.INIT)
                else:
                    return
                v2vtask = V2VTask(task_id,
                                  task.get('src_cloud'),
                                  json.loads(task.get('src_server')),
                                  task.get('dest_cloud'),
                                  json.loads(task.get('dest_server')))
                v2vtask.run()
        except Exception as ex:
            traceback.print_exc()
            LOG.exception(f'task={task_id}, end with error={str(ex)}')
        finally:
            end_time = time.time()
            LOG.info(f'Ending with task={task_id}, and it cost {end_time-start_time}s')


class V2VTask(object):
    # PROGRESS DATA EXAMPLE:
    # [   1.5] Opening the source
    # [   4.3] Creating an overlay to protect the source from being modified
    # [   5.4] Opening the overlay
    # [  36.8] Inspecting the overlay
    # [ 134.2] Checking for sufficient free disk space in the guest
    # [ 134.2] Estimating space required on target for each disk
    # [ 134.2] Converting
    # [ 716.5] Mapping filesystem data to avoid copying unused and blank areas
    # [ 721.7] Closing the overlay
    # [ 722.3] Assigning disks to buses
    # [ 722.3] Checking if the guest needs BIOS or UEFI to boot
    # [ 722.3] Initializing the target -o openstack
    # [ 748.8] Copying disk 1/2
    # [1564.5] Copying disk 2/2
    # [1648.0] Creating output metadata
    # [1846.0] Finishing off
    PROGRESS_OPEN_SOURCE = 'Opening the source'
    PROGRESS_OPEN_OVERLAY = 'Opening the overlay'
    PROGRESS_MAPPING = 'Mapping filesystem data'
    PROGRESS_CLOSE_OVERLAY = 'Closing the overlay'
    PROGRESS_INIT_TARGET = 'Initializing the target'
    PROGRESS_COPY_DISK = 'Copying disk'
    PROGRESS_CREATE_M = 'Creating output metadata'
    PROGRESS_FINISH = 'Finishing off'

    def __init__(self, task_id, src_cloud, src_server, dest_cloud, dest_server):
        super(V2VTask, self).__init__()
        self.server_name = CONF.server_name
        self.task_id = task_id
        self.src_cloud = db_api.get_by_uuid(VMware, src_cloud)
        self.src_server = src_server
        self.dest_cloud = db_api.get_by_uuid(Openstack, dest_cloud)
        self.dest_server = dest_server
        self.vmware_password_file = None
        self.v2v_log = None
        self.v2v_log_exist = False
        self.image_ids = {}
        self.image_names = {}
        self.image_sizes = {}
        self.volume_ids = {}
        self.failed = False
        self.task_percent = 0

    @property
    def task(self):
        return db_api.get_by_uuid(Task_db, self.task_id)

    def write_task(self, state=None, percent=None):
        if state is not None:
            db_api.task_update_state_by_uuid(self.task_id, state)
        if percent is not None:
            self.task_percent = percent
            db_api.task_update_percent_by_uuid(self.task_id, percent)
            self.log(f"v2v migrate percent is {percent}%")

    def log(self, msg, l='info'):
        m = f'[task id: {self.task_id}] ' + msg
        if l == 'info':
            LOG.info(m)
        elif l == 'debug':
            LOG.debug(m)
        elif l == 'error':
            LOG.error(m)
        elif l == 'exception':
            LOG.exception(m)
        else:
            LOG.info(m)

    def run(self):

        self.log(f'run v2v task, task id:{self.task_id}, source cloud info:{self.src_cloud},'
                 f' source vm info:{self.src_server}, target cloud info:{self.dest_cloud},'
                 f' target vm info:{self.dest_server}')
        self.write_task(state=STATUS.RUNNING)
        src_cloud_url = self.sure_uri(self.src_cloud.get('user'), self.src_cloud.get('ip'), self.src_cloud.get('uri'))
        password_files = []
        uid = self.get_uid()
        gid = self.get_gid()
        self.vmware_password_file = self.write_password(self.src_cloud.get('password'), password_files, uid, gid)
        self.log(f'save password to {password_files}')
        log_dir = self.get_logs()
        work_dir = self.get_work_dir()
        log_tag = f"{self.task_id}-{self.src_server.get('name')}-{time.strftime('%Y%m%dT%H%M%S')}"
        self.v2v_log = os.path.join(log_dir, 'v2v-migrate-%s.log' % log_tag)

        # Prepare virt-v2v shell
        src_server_name = self.src_server.get('name')
        if CONF.openstack_type == 'local':
            v2v_args = [
                '-v', '-x',
                src_server_name,
                '--root', 'first',
            ]
            v2v_args.extend([
                '-ic', src_cloud_url,
                '-o', 'local',
                '-os', work_dir,
                '--password-file', self.vmware_password_file
            ])
        elif CONF.openstack_type == 'glance':
            v2v_args = [
                '-v', '-x',
                src_server_name,
                '--root', 'first',
            ]
            v2v_args.extend([
                '-ic', src_cloud_url,
                '-o', 'glance',
                '--password-file', self.vmware_password_file
            ])
        elif CONF.openstack_type == 'openstack':
            v2v_args = [
                '-v', '-x',
                src_server_name,
                '--root', 'first',
            ]
            v2v_args.extend([
                '-ic', src_cloud_url,
                '-o', 'openstack',
                '-oo', 'server-id=%s' % self.server_name,
                '-os', self.dest_server.get('volume_type'),
                '--password-file', self.vmware_password_file
            ])

        # Prepare v2v environment
        v2v_env = os.environ.copy()

        # v2v current environment parameters of LANG
        self.log("Set the current v2v's environment variable parameter LANG to C")
        v2v_env['LANG'] = 'C'

        # v2v current environment parameters of LIBGUESTFS_BACKEND
        self.log("Set the current v2v's environment variable parameter LIBGUESTFS_BACKEND to direct")
        v2v_env['LIBGUESTFS_BACKEND'] = 'direct'

        # v2v current environment parameters of VIRTIO_WIN
        self.log("Set the current v2v's environment variable parameter VIRTIO_WIN to /usr/share/virtio-win")
        v2v_env['VIRTIO_WIN'] = '/usr/share/virtio-win'

        # v2v current environment parameters of Openstack
        self.log("Set the current v2v's environment for openstack")

        if os.path.exists(CONF.openrc_path):
            openrc_file = open(CONF.openrc_path)
            try:
                # Search the str started with "export" and contains "=".
                patt_save_str = re.compile(r'^export.*=.*')
                # Search "=".
                patt_rm_str = re.compile(r'=')

                # Read openrc file content by lines.
                lines = openrc_file.readlines()

                for line in lines:
                    match = patt_save_str.search(line)
                    if match:
                        # Remove the "export" and "" from match.group(0)
                        temp_str = match.group(0).strip("export").strip()

                        # Split the str into a list by "=".
                        environ_value_dic = patt_rm_str.split(temp_str)

                        # Set openstack_env for each env parameters.
                        k, v = environ_value_dic[0], environ_value_dic[1].strip("'")
                        self.log(f"Openstack's environment parameter is {k}, value is {v}")
                        v2v_env[k] = v
            finally:
                openrc_file.close()
        else:
            DEFAULT_OPENRC['OS_AUTH_URL'] = self.dest_cloud.get('auth_url')
            DEFAULT_OPENRC['OS_USERNAME'] = self.dest_cloud.get('username')
            DEFAULT_OPENRC['OS_PASSWORD'] = self.dest_cloud.get('password')
            DEFAULT_OPENRC['OS_PROJECT_NAME'] = self.dest_cloud.get('project_name')
            DEFAULT_OPENRC['OS_PROJECT_DOMAIN_NAME'] = self.dest_cloud.get('project_domain_name')
            DEFAULT_OPENRC['OS_USER_DOMAIN_NAME'] = self.dest_cloud.get('user_domain_name')
            v2v_env.update(DEFAULT_OPENRC)

        # v2v migrate
        try:
            self.log(f'run v2v migrate begin with cmd: {v2v_args}, env: {v2v_env}')
            self.start(self.v2v_log, v2v_args, v2v_env)
            self.write_task(percent=5)
        except Exception as ex:
            self.log(f'run v2v migrate start error with {str(ex)}', l='error')
            self.write_task(state=STATUS.FAILED)
            raise

        try:
            while self.is_running():
                self.progress()
                time.sleep(1)
            # return_code
            # None -- subprocess has not ended
            # ==0 -- subprocess exits normally
            # > 0 -- subprocess exits abnormally, and the returncode corresponds to the error code
            # < 0 -- subprocess was killed by the signal
            self.log(f"virt-v2v terminated with return code {self.return_code}")
            if self.return_code != 0:
                self.log('v2v migrate failed in progress with return code != 0', l='error')
                self.write_task(state=STATUS.FAILED)
                self.failed = True
            else:
                self.parse_log()
                self.log(f'get the image={self.image_ids}, get the volume={self.volume_ids}')
                self.log("v2v migrated has finished, begin to create target server.")
        except Exception as ex:
            self.kill()
            self.log(f'run v2v migrate in progress error with {str(ex)}', l='error')
            self.write_task(state=STATUS.FAILED)
            raise
        # Create Openstack Instance
        try:
            if not self.failed:
                self.failed = not self.handle_finish(v2v_env)
        except Exception as ex:
            self.failed = True
            self.log(f'create target server error with {str(ex)}', l='error')
            self.write_task(state=STATUS.FAILED)
            raise
        finally:
            if self.failed:
                self.log('create openstack server failed...')
                self.log('clean up ...')
                self.handle_cleanup()

        # Remove password files
        self.log('Removing password files')
        for f in password_files:
            try:
                os.remove(f)
            except OSError as ex:
                self.log(f'when removing password file: {f} has error: {str(ex)}', l='error')
        if self.failed:
            self.write_task(state=STATUS.FAILED)

    def is_running(self):
        return self._proc.poll() is None

    def kill(self):
        self._proc.kill()

    @staticmethod
    def get_logs():
        log_dir = LOG_DIR
        if not os.path.isdir(log_dir):
            os.makedirs(log_dir)
        return log_dir

    @staticmethod
    def get_work_dir():
        work_dir = WORK_DIR
        if not os.path.isdir(work_dir):
            os.makedirs(work_dir)
        return work_dir

    @property
    def pid(self):
        return self._proc.pid

    @property
    def return_code(self):
        self._proc.poll()
        return self._proc.returncode

    def start(self, _log, _args, _env):
        with open(_log, 'w') as log:
            self._proc = subprocess.Popen(
                [VIRT_V2V] + _args,
                stdin=DEVNULL,
                stderr=subprocess.STDOUT,
                stdout=log,
                env=_env
            )

    @staticmethod
    def get_uid():
        """ Tell under which user to run virt-v2v """
        return os.geteuid()

    @staticmethod
    def get_gid():
        """ Tell under which group to run virt-v2v """
        return os.getegid()

    @staticmethod
    def write_password(password, password_files, uid, gid):
        """ Make vcenter password temp-file """
        pfile = tempfile.mkstemp(suffix='.v2v_pwd')
        password_files.append(pfile[1])
        os.fchown(pfile[0], uid, gid)
        os.write(pfile[0], bytes(password.encode('utf-8')))
        os.close(pfile[0])
        return pfile[1]

    @staticmethod
    def sure_uri(user, vcenter_ip, uri):
        """ Sure migrate uri """
        li = []
        for i in user:
            li.append(i)
        for i in range(len(li)):
            if li[i] == '@':
                li[i] = '%40'
        transfer_user = ''.join(li)
        total_uri = 'vpx://' + transfer_user + '@' + vcenter_ip + '/' + uri + '/?no_verify=1'
        LOG.info(f'source VMware uri: {total_uri}')
        return total_uri

    def handle_cleanup(self):
        """Handle cleanup after failed conversion
        :return: handle cleanup results
        """
        pass

    # Create an instance
    def handle_finish(self, v2v_env):
        """Handle finish after successfull conversion
        """
        # Instance name
        vm_name = self.dest_server.get('name') or self.src_server.get('name')
        if CONF.use_openstack_cli:
            # Init keystone
            if self.run_openstack(['token', 'issue'], v2v_env) is None:
                self.log('check openstack cli failed')
                return False

            if CONF.openstack_type == 'glance':
                images = []
                image_names = []
                image_sizes = []
                # Build image list
                for k in sorted(self.image_ids.keys()):
                    images.append(self.image_ids[k])
                for m in sorted(self.image_names.keys()):
                    image_names.append(self.image_names[m])
                for n in sorted(self.image_sizes.keys()):
                    image_sizes.append(self.image_sizes[n])
                if len(images) == 0:
                    self.log('No images found!')
                    return False

                image_volumes = []
                image_creating_volumes = []
                # after image 0 disk convert to volume
                for i in range(1, len(images)):
                    image_cmd = [
                        'volume', 'create',
                        '--format', 'json',
                        '--type', '%s' % self.dest_server.get('volume_type'),
                        '--image', '%s' % str(images[i]),
                        '--size', '%s' % str(image_sizes[i]),
                                   '%s' % str(image_names[i])
                    ]
                    image_volume = self.run_openstack(image_cmd, v2v_env)
                    if image_volume is None:
                        self.log('Failed to convert image to volume', l='error')
                        return False
                    image_volume = json.loads(image_volume)
                    image_creating_volumes.append(image_volume)

                for vol in image_creating_volumes:
                    self.log(f'Transfering volume: {vol}')
                    retries = CONF.block_device_allocate_retries
                    image_volume_state_cmd = [
                        'volume', 'show',
                        '--format', 'json',
                        '%s' % str(vol['id'])
                    ]
                    for attempt in range(1, retries + 1):
                        image_volume_json_state = self.run_openstack(image_volume_state_cmd, v2v_env)
                        image_volume_state = json.loads(image_volume_json_state)
                        if image_volume_state['status'] == 'available':
                            image_volumes.append(image_volume_state)
                            break
                        elif image_volume_state['status'] in ['creating', 'downloading']:
                            time.sleep(CONF.block_device_allocate_retries_interval)
                        else:
                            break
                    image_volume_json_state = self.run_openstack(image_volume_state_cmd, v2v_env)
                    image_volume_state = json.loads(image_volume_json_state)
                    if image_volume_state['status'] != 'available':
                        self.log(f'after a long wait volume={str(vol["id"])} status is {image_volume_state["status"]} not available')
                        return False

                # Create Instance from image
                os_command = [
                    'server', 'create',
                    '--format', 'json',
                    '--flavor', self.dest_server.get('flavor'),
                ]
                os_command.extend(['--image', images[0]])
                for i in range(len(image_volumes)):
                    os_command.extend([
                        '--block-device-mapping',
                        '%s=%s' % (self._get_disk_name(i + 2), image_volumes[i]['id'])
                    ])

                os_command.extend(['--nic', 'net-id=%s' % self.dest_server.get('network')])
                os_command.append(vm_name)
            elif CONF.openstack_type == 'openstack':
                # openstack_type is volume
                volumes = []

                # Build volume list
                for k in sorted(self.volume_ids.keys()):
                    if self.volume_ids[k] not in volumes:
                        volumes.append(self.volume_ids[k])
                if len(volumes) == 0:
                    self.log('No volumes found!', l='error')
                    return False
                # if len(volumes) != len(self.volume_ids):
                #     self.log(f'Source volume map: {self.volume_ids}', l='error')
                #     self.log(f'Assume volume list: {volumes}', l='error')
                #     return False

                os_command = [
                    'server', 'create',
                    '--format', 'json',
                    '--flavor', self.dest_server.get('flavor'),
                ]

                os_command.extend(['--volume', volumes[0]])
                for i in range(1, len(volumes)):
                    os_command.extend([
                        '--block-device-mapping',
                        '%s=%s' % (self._get_disk_name(i + 1), volumes[i]),
                    ])

                v4_fixed_ip = self.dest_server.get('v4_fixed_ip')
                if v4_fixed_ip:
                    os_command.extend(['--nic', 'net-id=%s,v4-fixed-ip=%s' % (self.dest_server.get('network'), v4_fixed_ip)])
                else:
                    os_command.extend(['--nic', 'net-id=%s' % self.dest_server.get('network')])
                os_command.append(vm_name)
            elif CONF.openstack_type == 'local':
                # TODO deal with local type
                return False
            # Let's get rolling...
            vm = self.run_openstack(os_command, v2v_env)
            if vm is None:
                self.log(f'Create openstack instance with name={vm_name} failed', l='error')
                self.write_task(state=STATUS.FAILED)
                return False
            else:
                vm = json.loads(vm)
                vm_id = str(vm.get('id'))
                self.log(f'Create openstack instance with id={vm_id} success.')
                self.write_task(state=STATUS.SUCCEED)
                self.write_task(percent=100)
                return True
        else:
            # TODO use request do this
            return False

    # run openstack command
    def run_openstack(self, cmd, v2v_env):
        """Run the openstack commands with necessary arguments. When @destination
        is True the command is run in destination project. Otherwise it is run
        in current project.

        :param cmd: run openstack command
        :param v2v_env: v2v migrate current environment
        :return: run openstack results
        """
        command = ['openstack']
        command.extend(cmd)
        self.log(f'run openstack with cmd={command}')

        try:
            return subprocess.check_output(command,
                                           stderr=subprocess.STDOUT,
                                           env=v2v_env)
        except subprocess.CalledProcessError as e:
            # Note: Do NOT use logging.exception() here as it leaks passwords
            # into the log!
            self.log(f'Command exited with non-zero return code {e.returncode}, output: \n{e.output}\n')
            return None
        except Exception as e:
            # Note: because of eventlet.monkey_patch() can not get subprocess.CalledProcessError, so workaround
            self.log(f'Command exited with non-zero return code {e.returncode}, output: \n{e.output}\n')
            return None

    # Get disk name
    @staticmethod
    def _get_disk_name(index):
        if index < 1:
            raise ValueError('Index less then 1', index)
        if index > 702:
            raise ValueError('Index too large', index)
        index = index - 1
        one = index // 26
        two = index % 26
        enumid = (lambda i: chr(ord('a') + i))
        return 'vd%s%s' % ('' if one == 0 else enumid(one - 1), enumid(two))

    def check_cmd_output(self, cmd):
        try:
            return subprocess.check_output(cmd, shell=True)
        except subprocess.CalledProcessError as e:
            self.log(f'Command exited with non-zero return code {e.returncode}, output: \n{e.output}\n', l='exception')
            return json.dumps(0)

    def progress(self):
        if not self.v2v_log_exist:
            for i in range(10):
                if os.path.exists(self.v2v_log):
                    self.v2v_log_exist = True
                    break
                time.sleep(1)
        if self.task_percent < 10:
            cmd = f'cat {self.v2v_log} | grep "{self.PROGRESS_OPEN_SOURCE}" | wc -l'
            if json.loads(self.check_cmd_output(cmd)) > 0:
                self.write_task(percent=10)
        elif 10 <= self.task_percent < 15:
            cmd = f'cat {self.v2v_log} | grep "{self.PROGRESS_OPEN_OVERLAY}" | wc -l'
            if json.loads(self.check_cmd_output(cmd)) > 0:
                self.write_task(percent=15)
        elif 15 <= self.task_percent < 30:
            cmd = f'cat {self.v2v_log} | grep "{self.PROGRESS_MAPPING}" | wc -l'
            if json.loads(self.check_cmd_output(cmd)) > 0:
                self.write_task(percent=30)
        elif 30 <= self.task_percent < 40:
            cmd = f'cat {self.v2v_log} | grep "{self.PROGRESS_CLOSE_OVERLAY}" | wc -l'
            if json.loads(self.check_cmd_output(cmd)) > 0:
                self.write_task(percent=40)
        elif 40 <= self.task_percent < 60:
            cmd = f'cat {self.v2v_log} | grep "{self.PROGRESS_INIT_TARGET}" | wc -l'
            if json.loads(self.check_cmd_output(cmd)) > 0:
                self.write_task(percent=60)
        elif 60 <= self.task_percent < 70:
            cmd = f'cat {self.v2v_log} | grep "{self.PROGRESS_COPY_DISK}" | wc -l'
            if json.loads(self.check_cmd_output(cmd)) > 0:
                self.write_task(percent=70)
        elif 70 <= self.task_percent < 78:
            cmd = f'cat {self.v2v_log} | grep "{self.PROGRESS_CREATE_M}" | wc -l'
            if json.loads(self.check_cmd_output(cmd)) > 0:
                self.write_task(percent=78)
        elif 78 <= self.task_percent < 88:
            cmd = f'cat {self.v2v_log} | grep "{self.PROGRESS_FINISH}" | wc -l'
            if json.loads(self.check_cmd_output(cmd)) > 0:
                self.write_task(percent=88)

    def parse_log(self):
        if not self.v2v_log_exist:
            self.failed = True
            self.log(f'not {self.v2v_log} exists failed to create openstack server.', l='error')
            return
        with open(self.v2v_log) as f:
            line = f.readline()
            while line:
                self.parse_log_line(line)
                line = f.readline()

    @staticmethod
    def format_size(num):
        """
        Returns the human-readable version if a file size
        Unified conversion of units to GB
        :param num:
        :return:
        """
        if not isinstance(num, (six.integer_types, float)):
            return 0
        convert_to_GB = 1024.0 ** 3
        num /= convert_to_GB
        return int(math.ceil(num))

    def parse_log_line(self, line):
        image_id = re.compile(r'\|\s*id\s*\|\s*(?P<uuid>[a-fA-F0-9-]+)\s*\|')
        image_name = re.compile(r'\|\s*name\s*\|\s*(?P<name>.*)\s*\|')
        image_size = re.compile(r'\|\s*size\s*\|\s*(?P<size>\d+)\s*\|')
        volume_id = re.compile(r'openstack .*volume show -f json (?P<uuid>[a-fA-F0-9-]+)')
        # Openstack image UUID
        match = image_id.search(line)
        if match:
            i_uuid = match.group('uuid')
            ids = self.image_ids
            ids[len(ids) + 1] = i_uuid
            self.log(f'Adding openstack image id: {i_uuid}')
        # Openstack image name
        match = image_name.search(line)
        if match:
            i_name = match.group('name')
            names = self.image_names
            names[len(names) + 1] = i_name
            self.log(f'Adding openstack image name {i_name}')
        # Openstack image size
        match = image_size.search(line)
        if match:
            image_size = match.group('size')
            image_size_gb = self.format_size(int(image_size))
            sizes = self.image_sizes
            sizes[len(sizes) + 1] = image_size_gb
            self.log(f'Adding openstack image size {image_size}')
        # Openstack volume UUID
        match = volume_id.search(line)
        if match:
            v_id = match.group('uuid')
            ids = self.volume_ids
            ids[len(ids) + 1] = v_id
            self.log(f'Adding openstack volume {v_id}')


class save_and_reraise_exception(object):
    """Save current exception, run some code and then re-raise.

    In some cases the exception context can be cleared, resulting in None
    being attempted to be re-raised after an exception handler is run. This
    can happen when eventlet switches greenthreads or when running an
    exception handler, code raises and catches an exception. In both
    cases the exception context will be cleared.

    To work around this, we save the exception state, run handler code, and
    then re-raise the original exception. If another exception occurs, the
    saved exception is logged and the new exception is re-raised.

    In some cases the caller may not want to re-raise the exception, and
    for those circumstances this context provides a reraise flag that
    can be used to suppress the exception.  For example::

      except Exception:
          with save_and_reraise_exception() as ctxt:
              decide_if_need_reraise()
              if not should_be_reraised:
                  ctxt.reraise = False

    If another exception occurs and reraise flag is False,
    the saved exception will not be logged.

    If the caller wants to raise new exception during exception handling
    he/she sets reraise to False initially with an ability to set it back to
    True if needed::

      except Exception:
          with save_and_reraise_exception(reraise=False) as ctxt:
              [if statements to determine whether to raise a new exception]
              # Not raising a new exception, so reraise
              ctxt.reraise = True

    .. versionchanged:: 1.4
       Added *logger* optional parameter.
    """
    def __init__(self, reraise=True, logger=None):
        self.reraise = reraise
        if logger is None:
            logger = logging.getLogger()
        self.logger = logger
        self.type_, self.value, self.tb = (None, None, None)

    def force_reraise(self):
        if self.type_ is None and self.value is None:
            raise RuntimeError("There is no (currently) captured exception"
                               " to force the reraising of")
        try:
            if self.value is None:
                self.value = self.type_()
            if self.value.__traceback__ is not self.tb:
                raise self.value.with_traceback(self.tb)
            raise self.value
        finally:
            self.value = None
            self.tb = None

    def capture(self, check=True):
        (type_, value, tb) = sys.exc_info()
        if check and type_ is None and value is None:
            raise RuntimeError("There is no active exception to capture")
        self.type_, self.value, self.tb = (type_, value, tb)
        return self

    def __enter__(self):
        # TODO(harlowja): perhaps someday in the future turn check here
        # to true, because that is likely the desired intention, and doing
        # so ensures that people are actually using this correctly.
        return self.capture(check=False)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if self.reraise:
                self.logger.error('Original exception being dropped: %s',
                                  traceback.format_exception(self.type_,
                                                             self.value,
                                                             self.tb))
            return False
        if self.reraise:
            self.force_reraise()


if __name__ == '__main__':
    pass

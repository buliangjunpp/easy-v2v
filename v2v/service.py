import os
import sys

from oslo_log import log as logging
import oslo_messaging as messaging
from oslo_service import service
from oslo_utils import importutils

import v2v.conf
from v2v.i18n import _
from v2v import rpc

LOG = logging.getLogger(__name__)

CONF = v2v.conf.CONF


class Service(service.Service):
    """Service object for binaries running on hosts.

    A service takes a manager and enables rpc by listening to queues based
    on topic. It also periodically runs tasks on the manager and reports
    it state to the database services table.
    """

    def __init__(self, host, binary, topic, manager, *args, **kwargs):
        super(Service, self).__init__()
        self.host = host
        self.binary = binary
        self.topic = topic
        self.manager_class_name = manager
        manager_class = importutils.import_class(self.manager_class_name)
        self.manager = manager_class(host=self.host, *args, **kwargs)
        self.saved_args, self.saved_kwargs = args, kwargs
        self.rpcserver = None

    def start(self):
        if CONF.use_rpc:
            target = messaging.Target(topic=self.topic, server=self.host)

            endpoints = [
                self.manager,
            ]

            endpoints.extend(self.manager.additional_endpoints)

            self.rpcserver = rpc.get_server(target, endpoints)
            self.rpcserver.start()

        self.tg.add_dynamic_timer(self.periodic_tasks,
                                  initial_delay=None,
                                  periodic_interval_max=30)
        LOG.info("Started service %s on host %s.", self.binary, self.host)

    def __getattr__(self, key):
        manager = self.__dict__.get('manager', None)
        return getattr(manager, key)

    @classmethod
    def create(cls, host=None, binary=None, topic=None, manager=None):
        """Instantiates class and passes back application object.

        :param host: defaults to CONF.host
        :param binary: defaults to basename of executable
        :param manager: defaults to CONF.<topic>_manager

        """
        if not host:
            host = CONF.host
        if not binary:
            binary = os.path.basename(sys.argv[0])
        if not topic:
            topic = binary.rpartition('v2v-')[2]

        service_obj = cls(host, binary, topic, manager)

        return service_obj

    def stop(self):
        if self.rpcserver:
            try:
                self.rpcserver.stop()
                self.rpcserver.wait()
            except Exception:
                pass

        try:
            self.manager.cleanup_host()
        except Exception:
            LOG.exception('Service error occurred during cleanup_host')
            pass

        super(Service, self).stop()

    def periodic_tasks(self, raise_on_error=False):
        """Tasks to be run at a periodic interval."""
        # TODO(gcb) Need add real context whe we have context support
        return self.manager.periodic_tasks({'context': 'name'},
                                           raise_on_error=raise_on_error)


def process_launcher():
    return service.ProcessLauncher(CONF)


_launcher = None


def serve(server, workers=None):
    global _launcher
    if _launcher:
        raise RuntimeError(_('serve() can only be called once'))

    _launcher = service.launch(CONF, server, workers=workers)


def wait():
    _launcher.wait()


def get_launcher():
    return process_launcher()

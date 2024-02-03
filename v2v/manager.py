import os

from oslo_log import log as logging
from oslo_service import periodic_task

import v2v.conf

CONF = v2v.conf.CONF
LOG = logging.getLogger(__name__)
_PID = os.getpid()


class Manager(periodic_task.PeriodicTasks):

    def __init__(self, host=None, service_name='undefined'):
        if not host:
            host = CONF.host
        self.host = host
        self.service_name = service_name
        self.additional_endpoints = []
        super(Manager, self).__init__(CONF)

    def periodic_tasks(self, context, raise_on_error=False):
        """Tasks to be run at a periodic interval."""
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    def init_host(self):
        """Hook to do additional manager initialization.

        when one requests the service be started.  This is called before any
        service record is created. Child classes should override this method.
        """
        pass

    def cleanup_host(self):
        """Hook to do cleanup work when the service shuts down.

        Child classes should override this method.
        """
        pass

    # NOTE(gcb) This is just an example showing usage of periodic task.
    @periodic_task.periodic_task(spacing=CONF.check_interval)
    def log_pid(self, context):
        """periodical task for logging pid of the current process"""
        LOG.info('Run v2v-engine with pid:%s on host:%s' % (_PID, self.host))

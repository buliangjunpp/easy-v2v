import sys
import eventlet
import v2v.conf

from v2v import config
from v2v import service

eventlet.monkey_patch()

CONF = v2v.conf.CONF


def main():
    config.parse_args(sys.argv[1:], default_config_files=['/etc/v2v/v2v.conf'])
    server = service.Service.create(binary='v2v-manager', manager='v2v.agent.manager.V2VManager')
    service.serve(server)
    service.wait()


if __name__ == "__main__":
    sys.exit(main())

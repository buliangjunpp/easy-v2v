import socket
from oslo_config import cfg

engine_opts = [
    cfg.StrOpt(
        "host",
        default=socket.gethostname(),
        help="The host name which agent run on."
    ),
    cfg.IntOpt(
        "check_interval",
        default=-1,
        help="The interval time to check hosts. "
             "Set -1 to skip periodical task by default."
    ),
    cfg.BoolOpt(
        "use_rpc",
        default=True,
        help="Set True to enable RPC service."
    ),
    cfg.StrOpt('server_name',
               default='v2v',
               help="The server name for converting volume."),
    cfg.StrOpt('openstack_type',
               default='openstack',
               help="The convert type."),
    cfg.BoolOpt('use_openstack_cli',
               default=True,
               help="Set True to use openstack cli not request."),
    cfg.IntOpt(
        "max_concurrent_tasks",
        default=1,
        help="Maximum concurrent execution allowed at the same time."
    ),
    cfg.StrOpt('openrc_path',
               default='/root/openrc',
               help="The openrc file path."),
    cfg.IntOpt('block_device_allocate_retries',
               default=60,
               min=0,
               help=''),
    cfg.IntOpt('block_device_allocate_retries_interval',
               default=3,
               min=0,
               help='')

]


def register_opts(conf):
    conf.register_opts(engine_opts)
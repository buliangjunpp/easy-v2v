from oslo_config import cfg

from v2v.conf import api
from v2v.conf import manager

conf_modules = [
    api,
    manager
]

CONF = cfg.CONF


def configure(conf=None):
    """Register all options of module in conf_modules

    :param conf: An Object of ConfigOpts in oslo_conf.cfg,
                 usually is ``cfg.CONF``

    :returns: None
    """

    if conf is None:
        conf = CONF

    for module in conf_modules:
        module.register_opts(conf)


# Need to invoke configure function to register options
configure(CONF)

# Copyright 2017 EasyStack, Inc.

from oslo_log import log as logging

import v2v.conf
from v2v import rpc
from v2v.db import api as db_api

CONF = v2v.conf.CONF


def prepare_logging(conf=None):
    """Prepare Oslo Logging

    Use of Oslo Logging involves the following
      * logging.register_options (required)
      * logging.set_defaults (optional)
      * logging.setup (required, setup will be done in main function)
    """
    if conf is None:
        conf = CONF

    logging.register_options(conf)

    logging.set_defaults(
        default_log_levels=logging.get_default_log_levels()
    )


def parse_args(argv, project='v2v', default_config_files=None, configure_db=True, init_rpc=True):
    prepare_logging(CONF)

    CONF(argv,
         project=project,
         version='1.0',
         default_config_files=default_config_files)

    # Involve setup method to set up logging.
    # Usually we should set up logging after CONF(),
    # because the logging level and formatter
    # may be set in config files.
    logging.setup(CONF, project)

    if init_rpc:
        rpc.init(CONF)

    if configure_db:
        db_api.register_models()


# flask app 配置
class AppConfig(object):
    """
    flask app 配置项
    """
    pass

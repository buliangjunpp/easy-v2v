from oslo_config import cfg

v2v_api_opts = [
    cfg.StrOpt(
        "api_listen",
        default="0.0.0.0",
        help="IP address on which v2v API listen."
    ),
    cfg.PortOpt(
        "api_listen_port",
        default=6666,
        help="Port on which v2v API listen."
    ),
    cfg.StrOpt('use_doc',
               default='/',
               help='文档路径， 填写False或字符串路径, 例如"/"， 如果为false, 则不使用文档， 默认为 "/"'),
    cfg.BoolOpt('add_specs',
                default=True,
                help='swagger.json 接口是否可以请求， 填写False或True， 如果为false, '
                     '则不显示swagger.json 接口， 同时文档也不会显示，默认为 True'),
    cfg.IntOpt(
        "allowed_server_number",
        default=5,
        help="when no license the server number allow to convert"
    ),
]


def register_opts(conf):
    conf.register_opts(v2v_api_opts)

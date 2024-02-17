from v2v.api.schema import base


create_openstack_schema = {
    'type': 'object',
    'properties': {
        'name': base.name,
        'platform': base.platform,
        'auth_url': {
            'type': 'string',
            'description': 'keystone认证URL',
            'example': 'http://keystone.opsl2.svc.cluster.local:80/v3'
        },
        'username': base.username,
        'password': base.password,
        'project_name': base.project_name,
        'project_domain_name': base.project_domain_name,
        'user_domain_name': base.user_domain_name
    },
    'additionalProperties': False,
    'required': ['name', 'platform', 'auth_url', 'username', 'password',
                 'project_name', 'project_domain_name', 'user_domain_name']
}

create_vmware_schema = {
    'type': 'object',
    'properties': {
        'name': base.name,
        'platform': base.platform,
        'ip': {
            'type': 'string',
            'description': 'IP地址',
            'example': '192.168.5.10'
        },
        'user': base.username,
        'password': base.password,
        'uri': {
            'type': 'string',
            'description': '数据中心的url',
            'example': 'Datacenter/192.168.5.12'
        }
    },
    'additionalProperties': False,
    'required': ['name', 'platform', 'ip', 'user', 'password', 'uri']
}

src_server = {
    'type': 'object',
    'properties': {
        'name': {
            'type': 'string',
            'description': '要转换的虚拟机名字',
            'example': 'src_test'
        }
    },
    'required': ['name']
}

dest_server = {
    'type': 'object',
    'properties': {
        'name': {
            'type': 'string',
            'description': '目标虚拟机名字',
            'example': 'dest_test'
        },
        'network': {
            'type': 'string',
            'description': '目标虚拟机网络uuid',
            'example': '98f71b70-98b3-4d50-893d-30bd8fb677f0'
        },
        'flavor': {
            'type': 'string',
            'description': '目标虚拟机规格',
            'example': '2dc4743e-9d7d-47e9-942a-0cf3ad3ea1fb'
        },
        'volume_type': {
            'type': 'string',
            'description': '目标虚拟机磁盘的类型',
            'example': 'hdd'
        }
    },
    'required': ['network', 'flavor', 'volume_type']
}

create_task_schema = {
    'type': 'object',
    'properties': {
        'src_cloud': {
            'type': 'string',
            'description': '源云的注册uuid',
            'example': '65d793f2-0dd7-403f-847e-1c1f2aa10f7f'
        },
        'src_server': src_server,
        'dest_cloud': {
            'type': 'string',
            'description': '目标云的注册uuid',
            'example': '7260925c-ae95-4ace-8b01-6a8e64f0dcb8'
        },
        'dest_server': dest_server
    },
    'additionalProperties': False,
    'required': ['src_cloud', 'src_server', 'dest_cloud', 'dest_server']
}

create_license_schema = {
    'type': 'object',
    'properties': {
        'license': {
            'type': 'string',
            'description': '要注册的license内容',
            'example': 'xxxx'
        },
    },
    'additionalProperties': False,
    'required': ['license']
}

task_action_schema = {
    'type': 'object',
    'properties': {
        'action': {
            'type': 'string',
            'description': "action",
            'enum': ['retry']
        }
    },
    'required': ['action'],
    'additionalProperties': False
}

update_hosts_schema = {
    'type': 'object',
    'properties': {
        'hosts': {
            'type': 'string',
            'description': '/etc/hosts的内容',
            'example': 'xxxx'
        },
    },
    'additionalProperties': False,
    'required': ['hosts']
}

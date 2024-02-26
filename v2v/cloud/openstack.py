from keystoneauth1 import identity
from keystoneauth1 import session
from oslo_utils import importutils
import requests
import json
from requests import sessions


DOMAIN_AUTH = {
    'os_auth_url': 'http://keystone.opsl2.svc.cluster.local:80/v3',
    'os_password': 'GwqoXZrD',
    'os_username': 'drone',
    'os_domain_name': 'default',
    'os_user_domain_name': 'Default'
}
ADMIN_AUTH = {
    'os_auth_url': 'http://keystone.opsl2.svc.cluster.local:80/v3',
    'os_password': 'Admin@ES20!9',
    'os_username': 'admin',
    'os_project_domain_name': 'Default',
    'os_project_name': 'admin',
    'os_user_domain_name': 'Default'
}

AUTH = {
    'os_auth_url': 'http://keystone.opsl2.svc.cluster.local:80/v3',
    'os_password': 'test123!',
    'os_project_name': 'telecom_test',
    'os_username': 'test-1',
    'os_project_domain_name': 'telecom_test',
    'os_user_domain_name': 'telecom_test'
}

NOVA_API_VERSION = '2.67'
GLANCE_API_VERSION = '2'


class Base(object):

    def __init__(self, component, session):
        self.session = session
        self.running = True
        self.component = component

    def client_proxy(self, client_name, client_version, api_version,
                     endpoint_type, endpoint):
        if client_name in ('neutron', 'keystone'):
            mod_str = "%sclient.%s.client" % (client_name, client_version)
        else:
            mod_str = "%sclient.client" % client_name
        client = importutils.import_module(mod_str)
        client_params = {'session': self.session}
        if client_name != 'glance':
            client_params['endpoint_type'] = endpoint_type
        else:
            client_params['endpoint'] = endpoint
        if api_version:
            return client.Client(api_version, **client_params)
        return client.Client(**client_params)

    def get_client(self, client_name, api_version=None,
                   endpoint_type='public', endpoint=None):
        default_client_version = {
            'nova': 'v2',
            'neutron': 'v2_0',
            'cinder': 'v2',
            'glance': 'v2',
            'keystone': 'v3'
        }
        client_version = default_client_version[client_name]
        return self.client_proxy(client_name,
                                 client_version,
                                 api_version,
                                 endpoint_type,
                                 endpoint)


class Nova(Base):

    def __init__(self, session):
        super(Nova, self).__init__('nova', session)
        self.nc = self.get_client(self.component, api_version=NOVA_API_VERSION)

    def flavor_list(self):
        flavors = self.nc.flavors.list()
        return flavors

    def get_quota(self, project_id):
        return self.nc.quotas.get(project_id, detail=True)

    def update_quota(self, project_id, **kwargs):
        return self.nc.quotas.update(project_id, **kwargs)

    def boot(self, name, image, flavor, meta=None, files=None,
             reservation_id=None, min_count=None,
             max_count=None, security_groups=None, userdata=None,
             key_name=None, availability_zone=None,
             block_device_mapping=None, block_device_mapping_v2=None,
             nics=None, scheduler_hints=None,
             config_drive=None, disk_config=None, admin_pass=None,
             access_ip_v4=None, access_ip_v6=None, **kwargs):
        self.nc.servers.create(name, image, flavor, userdata=userdata,
                               security_groups=security_groups,
                               key_name=key_name, block_device_mapping=block_device_mapping,
                               block_device_mapping_v2=block_device_mapping_v2,
                               nics=nics, availability_zone=availability_zone,
                               min_count=min_count, admin_pass=admin_pass,
                               disk_config=disk_config, config_drive=config_drive,
                               meta=meta, scheduler_hints=scheduler_hints)


class Glance(Base):
    def __init__(self, session):
        super(Glance, self).__init__('glance', session)
        self.gc = self.get_client(self.component, api_version=GLANCE_API_VERSION)

    def image_list(self):
        images = self.gc.images.list()
        return images


class Keystone(object):
    def __init__(self):
        self.auth_url = ADMIN_AUTH.get('os_auth_url')
        self.default_content_type = 'application/json'
        self.auth_token, self.domain_token = None, None
        self.init_token()
        self.init_domain_token()

    def init_token(self):
        auth_dict = {
            'auth': {
                'identity': {
                    'methods': ['password'],
                    'password': {
                        'user': {
                            'domain': {
                                'name': ADMIN_AUTH.get('os_user_domain_name')
                            },
                            'name': ADMIN_AUTH.get('os_username'),
                            'password': ADMIN_AUTH.get('os_password')
                        }
                    }
                },
                'scope': {
                    'project': {
                        'domain': {
                            'name': ADMIN_AUTH.get('os_project_domain_name')
                        },
                        'name': ADMIN_AUTH.get('os_project_name')
                    }
                }
            }
        }

        response = self.request(self.auth_url + "/auth/tokens",
                                data=json.dumps(auth_dict), method="POST")
        if response.status_code == 401:
            raise Exception('UNAUTHORIZED')
        elif response.status_code in [200, 201]:
            self.auth_token = response.headers.get('x-subject-token')
        else:
            print(response.status_code, response.reason or response.text)

    def init_domain_token(self):
        auth_dict = {
            'auth': {
                'identity': {
                    'methods': ['password'],
                    'password': {
                        'user': {
                            'domain': {
                                'name': DOMAIN_AUTH.get('os_user_domain_name')
                            },
                            'name': DOMAIN_AUTH.get('os_username'),
                            'password': DOMAIN_AUTH.get('os_password')
                        }
                    }
                },
                'scope': {
                    'domain': {
                        'id': DOMAIN_AUTH.get('os_domain_name')
                    },
                }
            }
        }
        response = self.request(self.auth_url + "/auth/tokens",
                                data=json.dumps(auth_dict), method="POST")
        if response.status_code == 401:
            raise Exception('UNAUTHORIZED')
        elif response.status_code in [200, 201]:
            self.domain_token = response.headers.get('x-subject-token')
        else:
            print(response.status_code, response.reason or response.text)

    def _normalize_headers(self, headers):
        headers = headers or {}

        for key, value in headers.items():
            if isinstance(value, (int, float)):
                headers[key] = str(value)

        return headers

    def add_default_header(self, headers=None, is_domain=False):
        if headers is None:
            headers = {}
        if self.auth_token and not is_domain:
            headers['X-Auth-Token'] = self.auth_token

        if self.domain_token and is_domain:
            headers['X-Auth-Token'] = self.domain_token
        return headers

    def request(self, url, method='GET', params=None, data=None, headers=None, is_domain=False):
        headers = self.add_default_header(headers, is_domain=is_domain)
        headers = self._normalize_headers(headers=headers)
        if "Content-Type" not in headers:
            if method.upper() in ['POST', 'PATCH', 'DELETE', 'PUT']:
                headers.update({'Content-Type': self.default_content_type})
        try:
            with sessions.Session() as session:
                return session.request(method=method, url=url, params=params,
                                       data=data, headers=headers, timeout=30)
        except requests.exceptions.ConnectionError:
            raise Exception('cannot connect')
        except requests.Timeout:
            raise Exception('Connection expired')

    def parse_body(self, response):
        body = response.text.strip() if response.text is not None else ""
        if not body:
            return None
        content_type = response.headers.get('content-type', response.headers.get('Content-Type')) or ''
        if content_type == self.default_content_type:
            try:
                return json.loads(body)
            except Exception:
                raise Exception("body not json")
        else:
            return body

    def parse_response(self, response):
        status = response.status_code
        if status in range(200, 300):
            body = self.parse_body(response)
            return body
        else:
            print(response.status_code, response.reason or response.text)
            raise Exception('response error')

    def list_project(self, domain_id):
        url = self.auth_url + '/projects'
        params = {'domain_id': domain_id}
        res = self.request(url, params=params, is_domain=True)
        return self.parse_response(res).get('projects')

    def create_project(self, p_name, d_id):
        url = self.auth_url + '/projects'
        data = {
            "project": {
                "is_domain": False,
                "enabled": True,
                "description": "create by boot",
                "name": p_name,
                "domain_id": d_id}
        }
        res = self.request(url, method='POST', data=json.dumps(data), is_domain=True)
        return self.parse_response(res)

    def list_domain(self):
        url = self.auth_url + '/domains?root_only=False'
        res = self.request(url, is_domain=True)
        return self.parse_response(res).get('domains')

    def get_user_by_domain(self, domain_id):
        url = self.auth_url + '/users'
        params = {'domain_id': domain_id}
        res = self.request(url, params=params, is_domain=True)
        return self.parse_response(res).get('users')

    def list_role(self):
        url = self.auth_url + '/roles'
        res = self.request(url, is_domain=True)
        return self.parse_response(res).get('roles')

    def add_role(self, project_id, user_id, role='admin'):
        role_id = None
        roles = {i.get('id'): i.get('name') for i in self.list_role()}
        for k, v in roles.items():
            if role in (k, v):
                role_id = k
                break
        if role_id is not None:
            url = self.auth_url + '/projects/' + project_id + '/users/' + user_id + '/roles/' + role_id
            self.request(url, method='PUT', is_domain=True)


class Neutron(Base):

    def __init__(self, session):
        super(Neutron, self).__init__('neutron', session)
        self.nc = self.get_client(self.component)

    def net_list(self):
        networks = self.nc.list_networks()
        return networks

    def subnet_list(self):
        subnets = self.nc.list_subnets()
        return subnets

    def show_network_ip_availability(self, net_id):
        return self.nc.show_network_ip_availability(net_id)

    def port_list(self):
        ports = self.nc.list_ports()
        return ports

    def get_quota(self, project_id):
        return self.nc.show_quota_details(project_id)

    def update_quota(self, project_id, **kwargs):
        return self.nc.update_quota(project_id, kwargs)

    def create_security_groups(self, project_id):
        body = {
            "security_group": {
                "name": "default",
                "description": "create by boot",
                "project_id": project_id
            }
        }
        return self.nc.create_security_group(body=body)

    def create_security_group_rule(self, project_id, sec_id):
        body = {
            "security_group_rule": {
                "direction": "ingress",
                "ethertype": "IPv4",
                "security_group_id": sec_id,
                "remote_ip_prefix": "0.0.0.0/0",
                "tenant_id": project_id
            }
        }
        self.nc.create_security_group_rule(body=body)
        body = {
            "security_group_rule": {
                "direction": "ingress",
                "ethertype": "IPv6",
                "security_group_id": sec_id,
                "remote_ip_prefix": "::/0",
                "tenant_id": project_id
            }
        }
        self.nc.create_security_group_rule(body=body)

    def delete_security_group_rule(self, rule_id):
        return self.nc.delete_security_group_rule(rule_id)

    def list_security_groups(self, project_id):
        return self.nc.list_security_groups(project_id=project_id)


class Cinder(Base):

    def __init__(self, session):
        super(Cinder, self).__init__('cinder', session)
        self.cc = self.get_client(self.component, api_version='2')

    def get_quota(self, project_id):
        return self.cc.quotas.get(project_id, usage=True)

    def update_quota(self, project_id, **kwargs):
        return self.cc.quotas.update(project_id, **kwargs)

    def list_types(self):
        return self.cc.volume_types.list()


class Boot(object):

    def __init__(self):

        self.new_p = False
        self.session = None
        self.nova = None
        self.glance = None
        self.neutron = None
        self.admin_session = self.get_session(ADMIN_AUTH)
        self.a_nova = Nova(self.admin_session)
        self.a_neutron = Neutron(self.admin_session)
        self.a_keystone = Keystone()
        self.a_cinder = Cinder(self.admin_session)
        self.a_glance = Glance(self.admin_session)

    def init_client(self):
        self.session = self.get_session(AUTH)
        self.nova = Nova(self.session)
        # self.glance = Glance(self.session)
        self.neutron = Neutron(self.session)

    def check_need_quota(self, q_obj, n):
        q_need = 0
        limit = q_obj.get('limit')
        if limit != -1:
            in_use = q_obj.get('in_use', 0) or q_obj.get('used', 0)
            i_free = q_obj.get('limit', 0) - in_use - q_obj.get('reserved', 0)
            if i_free < n:
                q_need = limit + n
        return q_need

    def check_nova_quota(self, project_id, vcpus, ram, instance=1):
        compute_q = self.a_nova.get_quota(project_id)
        q_cores = compute_q.cores
        q_ram = compute_q.ram
        q_instances = compute_q.instances
        i_need = self.check_need_quota(q_instances, instance)
        v_need = self.check_need_quota(q_cores, vcpus)
        r_need = self.check_need_quota(q_ram, ram)
        update_dict = dict()
        if i_need != 0:
            update_dict['instances'] = i_need
        if v_need != 0:
            update_dict['cores'] = v_need
        if r_need != 0:
            update_dict['ram'] = r_need
        if update_dict:
            self.a_nova.update_quota(project_id, **update_dict)

    def check_cinder_quota(self, project_id, volume_type, size, vol_num=1):
        cinder_q = self.a_cinder.get_quota(project_id)
        vol_type = 'volumes_' + volume_type
        gigabytes_type = 'gigabytes_' + volume_type
        vol_need = self.check_need_quota(getattr(cinder_q, vol_type), vol_num)
        gigabytes_need = self.check_need_quota(getattr(cinder_q, gigabytes_type), size)
        update_dict = dict()
        if vol_need != 0:
            update_dict[vol_type] = vol_need
        if gigabytes_need != 0:
            update_dict[gigabytes_type] = gigabytes_need
        if update_dict:
            self.a_cinder.update_quota(project_id, **update_dict)

    def check_neutron_quota(self, project_id):
        neutron_q = self.a_neutron.get_quota(project_id).get('quota')
        port_need = self.check_need_quota(neutron_q.get('port'), 1)
        update_dict = dict()
        if port_need != 0:
            update_dict['quota'] = {'port': port_need}
        if update_dict:
            self.a_neutron.update_quota(project_id, **update_dict)

    def check_security_group(self, project_id):
        sec_g = self.neutron.list_security_groups(project_id).get('security_groups', [])
        defalut_sec = None
        ingress_4_id, ingress_6_id = None, None
        for s in sec_g:
            if s.get('project_id') == project_id and s.get('name') == 'default':
                defalut_sec = s.get('id')
                rules = s.get('security_group_rules')
                for r in rules:
                    if r.get('ethertype') == 'IPv4' and r.get('direction') == 'ingress' and r.get(
                            'project_id') == project_id:
                        ingress_4_id = r.get('id')
                    if r.get('ethertype') == 'IPv6' and r.get('direction') == 'ingress' and r.get(
                            'project_id') == project_id:
                        ingress_6_id = r.get('id')
                break

        if defalut_sec is None:
            neutron_q = self.a_neutron.get_quota(project_id).get('quota')
            update_dict = {'quota': {}}
            sec_need = self.check_need_quota(neutron_q.get('security_group'), 1)
            sec_rule_need = self.check_need_quota(neutron_q.get('security_group_rule'), 4)
            if sec_need != 0:
                update_dict['quota']['security_group'] = sec_need
            if sec_rule_need != 0:
                update_dict['quota']['security_group_rule'] = sec_rule_need
            if update_dict:
                self.a_neutron.update_quota(project_id, **update_dict)
            sec = self.a_neutron.create_security_groups(project_id).get('security_groups', {})
            defalut_sec = sec.get('id')
            rules = s.get('security_group_rules')
            for r in rules:
                if r.get('ethertype') == 'IPv4' and r.get('direction') == 'ingress' and r.get(
                        'project_id') == project_id:
                    ingress_4_id = r.get('id')
                if r.get('ethertype') == 'IPv6' and r.get('direction') == 'ingress' and r.get(
                        'project_id') == project_id:
                    ingress_6_id = r.get('id')
        else:
            neutron_q = self.a_neutron.get_quota(project_id).get('quota')
            update_dict = {'quota': {}}
            sec_need = self.check_need_quota(neutron_q.get('security_group'), 1)
            sec_rule_need = self.check_need_quota(neutron_q.get('security_group_rule'), 4)
            if sec_need != 0:
                update_dict['quota']['security_group'] = sec_need
            if sec_rule_need != 0:
                update_dict['quota']['security_group_rule'] = sec_rule_need
            if update_dict:
                self.a_neutron.update_quota(project_id, **update_dict)

        if defalut_sec is not None:
            if ingress_4_id is not None:
                self.a_neutron.delete_security_group_rule(ingress_4_id)
            if ingress_6_id is not None:
                self.a_neutron.delete_security_group_rule(ingress_6_id)
            self.a_neutron.create_security_group_rule(project_id, defalut_sec)

    def check_project(self, d_name, p_name):
        domains = {i.get('id'): i.get('name') for i in self.a_keystone.list_domain()}
        for k, v in domains.items():
            if d_name in (k, v):
                d_name = k
                break
        projects = {i.get('id'): i.get('name') for i in self.a_keystone.list_project(d_name)}
        p_id = None
        for k, v in projects.items():
            if p_name in (k, v):
                p_id = k
                break
        if p_id is None:
            project = self.a_keystone.create_project(p_name, d_name)
            self.new_p = True
            p_id = project.get('project', {}).get('id')
            users = {i.get('id'): i.get('name') for i in self.a_keystone.get_user_by_domain(d_name)}
            user_id = None
            for k, v in users.items():
                if AUTH.get('os_username') in (k, v):
                    user_id = k
                    break
            if user_id is not None:
                self.a_keystone.add_role(p_id, user_id)
                self.a_keystone.add_role(p_id, user_id, role='domain_admin')

        return p_id

    def get_session(self, auth_dict):
        auth_info = {
            "username": auth_dict.get('os_username'),
            "password": auth_dict.get('os_password'),
            "auth_url": auth_dict.get('os_auth_url'),
            "project_name": auth_dict.get('os_project_name'),
            "project_domain_name": auth_dict.get('os_project_domain_name'),
            "user_domain_name": auth_dict.get('os_user_domain_name')
        }
        auth = identity.Password(**auth_info)
        sess = session.Session(auth=auth)
        return sess

    def boot(self, servers):
        flavors_obj = self.a_nova.flavor_list()
        flavors = {i.id: i.name for i in flavors_obj}
        images = {i.id: i.name for i in self.a_glance.image_list()}
        networks = {i.get('id'): i.get('name') for i in self.a_neutron.net_list().get('networks', [])}
        for s in servers:
            d_name = s.get('os_project_domain_name')
            p_name = s.get('os_project_name')
            project_id = self.check_project(d_name, p_name)
            name = s.get('name', '')
            flavor = s.get('flavor', '')
            for k, v in flavors.items():
                if flavor in (k, v):
                    flavor = k
                    break
            image = s.get('image', '')
            for k, v in images.items():
                if image in (k, v):
                    image = k
                    break
            boot_volume_type = s.get('boot_volume_type')
            boot_volume_size = s.get('boot_volume_size')
            data_volume_type = s.get('data_volume_type')
            data_volume_size = s.get('data_volume_size')
            boot_volume_map = {
                "source_type": "image",
                "uuid": image,
                "destination_type": "volume",
                "volume_type": boot_volume_type,
                "volume_size": boot_volume_size,
                "boot_index": "0"}
            block_device_mapping_v2 = [boot_volume_map]
            if data_volume_type:
                data_volume_map = {"source_type": "blank",
                                   "destination_type": "volume",
                                   "volume_type": data_volume_type,
                                   "volume_size": data_volume_size}
                block_device_mapping_v2.append(data_volume_map)
            f_vcpus = f_ram = 0
            for f in flavors_obj:
                if f.id == flavor:
                    f_vcpus = int(f.vcpus)
                    f_ram = int(f.ram)
                    break
            self.check_nova_quota(project_id, f_vcpus, f_ram)
            if data_volume_type:
                if data_volume_type == boot_volume_type:
                    self.check_cinder_quota(project_id, boot_volume_type, int(boot_volume_size) + int(data_volume_size),
                                            vol_num=2)
                else:
                    self.check_cinder_quota(project_id, boot_volume_type, int(boot_volume_size))
                    self.check_cinder_quota(project_id, data_volume_type, int(data_volume_size))
            else:
                self.check_cinder_quota(project_id, boot_volume_type, int(boot_volume_size))
            self.check_neutron_quota(project_id)
            self.init_client()
            if self.new_p:
                self.check_security_group(project_id)
            net = s.get('net')
            for k, v in networks.items():
                if net in (k, v):
                    net = k
                    break
            ipv4 = s.get('ipv4')
            nics = [{"net-id": net, "v4-fixed-ip": ipv4}]
            password = s.get('password')
            description = s.get('description')
            availability_zone = s.get('availability_zone')
            self.nova.boot(name, '', flavor, admin_pass=None if password == '' else password,
                           availability_zone=availability_zone,
                           block_device_mapping_v2=block_device_mapping_v2,
                           nics=nics, description=description)


class OpenStack(object):

    def __init__(self, cloud):

        self.session = self.get_session(cloud)
        self.nova = Nova(self.session)
        self.glance = None
        self.neutron = Neutron(self.session)
        self.cinder = Cinder(self.session)

    def get_session(self, auth_dict):
        auth_info = {
            "username": auth_dict.get('username'),
            "password": auth_dict.get('password'),
            "auth_url": auth_dict.get('auth_url'),
            "project_name": auth_dict.get('project_name'),
            "project_domain_name": auth_dict.get('project_domain_name'),
            "user_domain_name": auth_dict.get('user_domain_name')
        }
        auth = identity.Password(**auth_info)
        sess = session.Session(auth=auth)
        return sess
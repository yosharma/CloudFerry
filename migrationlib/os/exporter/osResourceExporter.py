# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.


"""
Package with OpenStack resources export/import utilities.
"""
from migrationlib.os import osCommon
from utils import log_step, get_log, render_info, write_info
import sqlalchemy
import ipaddr


LOG = get_log(__name__)
ADMIN_TENANT = 'admin'


class ResourceExporter(osCommon.osCommon):
    """
    Exports various cloud resources (tenants, users, flavors, etc.)
    to a container to be later imported by ResourceImporter
    """

    def __init__(self, conf):
        self.data = dict()
        self.config = conf['clouds']['source']
        self.funcs = []
        super(ResourceExporter, self).__init__(self.config)
        self.info_values = {}

    def set_state(self, obj_dict):
        self.data = obj_dict['data']

    def convert_to_dict(self):
        res = {'data': self.data}
        res['_type_class'] = ResourceExporter.__name__
        return res

    @log_step(LOG)
    def get_flavors(self):
        def process_flavor(flavor):
            if hasattr(flavor, "is_public"):
                if flavor.is_public:
                    return flavor, []
            else:
                tenants = self.nova_client.flavor_access.list(flavor=flavor)
                tenants = [self.keystone_client.tenants.get(t.tenant_id).name for t in tenants]
                return flavor, tenants

        flavor_list = self.nova_client.flavors.list()
        self.data['flavors'] = map(process_flavor, flavor_list)
        return self

    @log_step(LOG)
    def get_tenants(self):
        self.data['tenants'] = self.keystone_client.tenants.list()
        return self

    @log_step(LOG)
    def get_roles(self):
        self.data['roles'] = self.keystone_client.roles.list()
        return self

    @log_step(LOG)
    def get_user_info(self):
        self.__get_user_info(self.config['keep_user_passwords'])
        return self

    @log_step(LOG)
    def detect_neutron(self):
        self.__data_network_service_dict_init()
        self.data['network_service_info']['service'] = osCommon.osCommon.network_service(self)

    @log_step(LOG)
    def get_security_groups(self):
        self.__data_network_service_dict_init()
        security_groups = self.__get_neutron_security_groups() \
            if osCommon.osCommon.network_service(self) == 'neutron'  else \
            self.__get_nova_security_groups()
        self.data['network_service_info']['security_groups'] = security_groups
        return self

    def __data_network_service_dict_init(self):
        if not 'network_service_info' in self.data:
            self.data['network_service_info']= {}

    def __get_nova_security_groups(self):
        return self.nova_client.security_groups.list()

    def __get_neutron_security_groups(self):
        return self.network_client.list_security_groups()['security_groups']

    def __get_user_info(self, with_password):
        users = self.keystone_client.users.list()
        info = {}
        if with_password:
            with sqlalchemy.create_engine(self.keystone_db_conn_url).begin() as connection:
                for user in users:
                    for password in connection.execute(sqlalchemy.text("SELECT password FROM user WHERE id = :user_id"),
                                                       user_id=user.id):
                        info[user.name] = password[0]
        self.data['users'] = info

    @log_step(LOG)
    def get_network_resources(self):
        if osCommon.osCommon.network_service(self) == 'neutron':
            self\
                .get_neutron_networks()\
                .get_neutron_subnets()\
                .get_neutron_routers()\
                .get_neutron_router_ports()\
                .get_neutron_floatings()
        elif osCommon.osCommon.network_service(self) == 'nova':
            self.get_nova_networks()\
                .get_nova_floatings()
        return self

    @log_step(LOG)
    def get_neutron_networks(self):
        networks = self.network_client.list_networks()['networks']
        get_tenant_name = self.__get_tenants_func()
        self.data['neutron'] = dict(networks=[])
        for network in networks:
            source_net = dict()
            source_net['name'] = network['name']
            source_net['admin_state_up'] = network['admin_state_up']
            source_net['shared'] = network['shared']
            source_net['tenant_name'] = get_tenant_name(network['tenant_id'])
            source_net['router:external'] = network['router:external']
            source_net['provider:physical_network'] = network['provider:physical_network']
            source_net['provider:network_type'] = network['provider:network_type']
            source_net['provider:segmentation_id'] = network['provider:segmentation_id']
            self.data['neutron']['networks'].append(source_net)
        return self

    @log_step(LOG)
    def get_neutron_subnets(self):
        subnets = self.network_client.list_subnets()['subnets']
        get_tenant_name = self.__get_tenants_func()
        self.data['neutron']['subnets'] = []
        for subnet in subnets:
            src_subnet = dict()
            src_subnet['name'] = subnet['name']
            src_subnet['enable_dhcp'] = subnet['enable_dhcp']
            src_subnet['allocation_pools'] = subnet['allocation_pools']
            src_subnet['gateway_ip'] = subnet['gateway_ip']
            src_subnet['ip_version'] = subnet['ip_version']
            src_subnet['cidr'] = subnet['cidr']
            src_subnet['network_name'] = self.network_client.show_network(subnet['network_id'])['network']['name']
            src_subnet['tenant_name'] = get_tenant_name(subnet['tenant_id'])
            self.data['neutron']['subnets'].append(src_subnet)
        return self

    @log_step(LOG)
    def get_neutron_routers(self):
        routers = self.network_client.list_routers()['routers']
        get_tenant_name = self.__get_tenants_func()
        self.data['neutron']['routers'] = []
        for router in routers:
            src_router = dict()
            src_router['name'] = router['name']
            src_router['admin_state_up'] = router['admin_state_up']
            src_router['routes'] = router['routes']
            src_router['external_gateway_info'] = router['external_gateway_info']
            if router['external_gateway_info']:
                ext_net = \
                    self.network_client.show_network(router['external_gateway_info']['network_id'])['network']
                src_router['ext_net_name'] = ext_net['name']
                src_router['ext_net_tenant_name'] = get_tenant_name(ext_net['tenant_id'])
            src_router['tenant_name'] = get_tenant_name(router['tenant_id'])
            self.data['neutron']['routers'].append(src_router)
        return self

    @log_step(LOG)
    def get_neutron_router_ports(self):
        ports = self.network_client.list_ports()['ports']
        get_tenant_name = self.__get_tenants_func()
        self.data['neutron']['ports'] = []
        for port in filter(lambda p: p['device_owner'] == 'network:router_interface', ports):
            router_port = dict()
            # network_name, mac_address, ip_address, device_owner and admin_state_up
            # are not used. May be these data will be needed in the future
            router_port['network_name'] = self.network_client.show_network(port['network_id'])['network']['name']
            router_port['mac_address'] = port['mac_address']
            router_port['subnet_name'] = \
                self.network_client.show_subnet(port['fixed_ips'][0]['subnet_id'])['subnet']['name']
            router_port['ip_address'] = port['fixed_ips'][0]['ip_address']
            router_port['router_name'] = self.network_client.show_router(port['device_id'])['router']['name']
            router_port['tenant_name'] = get_tenant_name(port['tenant_id'])
            router_port['device_owner'] = port['device_owner']
            router_port['admin_state_up'] = port['admin_state_up']
            self.data['neutron']['ports'].append(router_port)
        return self

    @log_step(LOG)
    def get_neutron_floatings(self):
        floatings = self.network_client.list_floatingips()['floatingips']
        get_tenant_name = self.__get_tenants_func()
        self.data['neutron']['floatingips'] = []
        for floating in floatings:
            src_float = dict()
            extnet = self.network_client.show_network(floating['floating_network_id'])['network']
            src_float['network_name'] = extnet['name']
            src_float['ext_net_tenant_name'] = get_tenant_name(extnet['tenant_id'])
            src_float['tenant_name'] = get_tenant_name(floating['tenant_id'])
            src_float['fixed_ip_address'] = floating['fixed_ip_address']
            src_float['floating_ip_address'] = floating['floating_ip_address']
            self.data['neutron']['floatingips'].append(src_float)

    @log_step(LOG)
    def get_nova_floatings(self):
        tenants = self.data['tenants']
        self.data['nova']['floatingips'] = []
        for tenant in tenants:
            #NOTE(SOM)Essex has no mechanism to respond on all IP's hence this code block
            try:
                params = { 'user': self.config['user'],
                           'password': self.config['password'],
                           'apihost': self.config['apihost'],
                           'tenant': tenant.name}
                nova_temp = self.get_nova_client(params)
                floatings = nova_temp.floating_ips.list()
                for floating in floatings:
                    src_float = dict()
                    src_float['network_name'] = floating.pool
                    src_float['ext_net_tenant_name'] = tenant.name
                    src_float['tenant_name'] = tenant.name
                    src_float['fixed_ip_address'] = floating.fixed_ip
                    src_float['floating_ip_address'] = floating.ip
                    self.data['nova']['floatingips'].append(src_float)
            except Exception, e:
                LOG.info("Unknown or not Authorised: %s, %s " % (e, tenant))



    def __get_tenants_func(self):
        tenants = {tenant.id: tenant.name for tenant in self.keystone_client.tenants.list()}

        def f(tenant_id):
            return tenants[tenant_id] if tenant_id in tenants.keys() else ADMIN_TENANT

        return f


    #NOTE(SOM) working
    @log_step(LOG)
    def get_nova_networks(self):
        networks = self.nova_client.networks.list()
        get_tenant_name = self.__get_tenants_func()
        self.data['nova'] = dict(networks=[])
        self.data['nova']['subnets'] =[]
        for network in networks:
            source_net = dict()
            source_net['name'] = network.label
            source_net['admin_state_up'] = True
            source_net['shared'] = False
            source_net['tenant_name'] = get_tenant_name(network.project_id)
            source_net['router:external'] = False
            #  This will need to be set on the destination side
            #source_net['provider:physical_network'] = network['provider:physical_network']
            source_net['provider:network_type'] = 'vlan'
            source_net['provider:segmentation_id'] = network.vlan
            self.data['nova']['networks'].append(source_net)

            src_subnet = dict()
            src_subnet['name'] = network.label
            src_subnet['enable_dhcp'] = True
            src_subnet['allocation_pools'] = [{"start": network.dhcp_start, "end": ipaddr.IPNetwork(network.cidr).__getitem__(-2)}]
            src_subnet['ip_version'] = '4'
            src_subnet['gateway_ip'] = network.gateway
            src_subnet['cidr'] = network.cidr
            src_subnet['network_name'] = network.label
            src_subnet['tenant_name'] = get_tenant_name(network.project_id)
            self.data['nova']['subnets'].append(src_subnet)


        return self



    @log_step(LOG)
    def build(self):
        return self.data

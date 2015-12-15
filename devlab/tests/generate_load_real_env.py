import argparse
import time
import generate_load
import sys
import os
import logging
import logging.handlers
from argparse import RawTextHelpFormatter
from keystoneclient import exceptions as ks_exceptions
from neutronclient.common import exceptions as nt_exceptions
from novaclient import exceptions as nv_exceptions
from cinderclient import exceptions as cd_exceptions
from glanceclient.common import exceptions as gl_exceptions

TIMEOUT = 600
VM_SPAWNING_LIMIT = 11

CREATE_CLEAN_METHODS_MAP = {
    'create_tenants': 'clean_tenants',
    'create_flavors': 'clean_flavors',
}

RESOURCE_CREATE_MAP = {
    '1': 'create_tenants',
    '2': 'create_keypairs',
    '3': 'upload_image',
    '4': 'create_flavors',
    '5': 'create_all_networking',
    '6': 'create_vms',
    '7': 'create_vm_snapshots',
    '8': 'create_cinder_objects',
    '9': 'create_security_groups',
}


def clean_if_exists(func):
    def wrapper(self, *args, **kwargs):
        try:
            logging.info('>>>In wrapper')
            return func(self, *args, **kwargs)
        except (ks_exceptions.Conflict,
                nv_exceptions.Conflict,
                nt_exceptions.NeutronClientException):
            logging.warning('>>>Method "%s" failed,'
                            'current resource already exists', func.__name__)
            clean_method = getattr(self.clean_tools,
                                   CREATE_CLEAN_METHODS_MAP[func.__name__])
            logging.info('>>>Run cleanup method "%s"', clean_method.__name__)
            clean_method()
            logging.info('>>>Run method "%s" one more time', func.__name__)
            func(self, *args, **kwargs)
    return wrapper


def retry_until_resources_created(resource_name):
    def actual_decorator(func):
        def wrapper(_list):
            for _ in range(TIMEOUT):
                _list = func(_list)
                if _list:
                    time.sleep(1)
                    continue
                else:
                    break
            else:
                msg = '{0}s with ids {1} have not become in active state'
                raise RuntimeError(msg.format(resource_name, _list))
        return wrapper
    return actual_decorator


class Prerequisites(generate_load.Prerequisites):

    def __init__(self, config=None, cloud_prefix='SRC'):
        super(Prerequisites, self).__init__(config, cloud_prefix)
        self.prefix = None

    def update_vm_status(self):
        src_cloud = Prerequisites(self.config, cloud_prefix='SRC')
        src_vms = [x.__dict__ for x in
                   src_cloud.novaclient.servers.list(
                       search_opts={'all_tenants': 1})]
        return src_vms

    def create_keypairs(self):
        try:
            for user, keypair in zip(self.config.users, self.config.keypairs):
                if user['enabled']:
                    self.switch_user(user=user['name'],
                                     tenant=self.update_name_with_prefix
                                     (user['tenant']),
                                     password=user['password'])
                    keypair['name'] = self.prefix + keypair['name']
                    self.novaclient.keypairs.create(**keypair)
                    logging.info('>>> keypair "%s" created for user "%s"',
                                 keypair['name'], user['name'])
            self.switch_user(user=self.username, password=self.password,
                             tenant=self.tenant)
        except nv_exceptions.ClientException as e:
            logging.error('>>>Keypair failed to create:\n "%s"', (repr(e)))

    def create_tenants(self, tenants=None):
        if tenants is None:
            tenants = self.config.tenants
        for tenant in tenants:
            tenant['name'] = self.prefix + tenant['name']
            for tnt in self.keystoneclient.tenants.list():
                if tnt.name == tenant['name']:
                    print ">>>Tenant", tenant['name'],
                    print "and its resources already exist."
                    print ">>>Please run --clean to clean tenant resources"
                    logging.info(">>>Tenant %s & its resources already exist",
                                 tenant['name'])
                    logging.info(">>>Please run --clean first to"
                                 " clean existing tenant resources")
                    sys.exit(0)
            logging.info('>>> Creating Tenant "%s"', tenant['name'])
            self.keystoneclient.tenants.create(tenant_name=tenant['name'],
                                               description=tenant[
                                                   'description'],
                                               enabled=tenant['enabled'])
            self.keystoneclient.roles.add_user_role(
                self.get_user_id(self.username),
                self.get_role_id('admin'),
                self.get_tenant_id(tenant['name']))

    def create_vms(self):
        @retry_until_resources_created('vm')
        def wait_until_vms_created(vm_list):
            for vm in vm_list[:]:
                if self.check_vm_state(vm):
                    vm_list.remove(vm)
            return vm_list
        vm_ids = []
        for vm in self.config.vms:
            vm['name'] = self.update_name_with_prefix(vm['name'])
            image_name = self.update_name_with_prefix(vm['image'])
            vm['image'] = self.get_image_id(image_name)
            flavor_name = self.update_name_with_prefix(vm['flavor'])
            vm['flavor'] = self.get_flavor_id(flavor_name)
            logging.info(">>> Creating VM %s with image %s and flavor %s",
                         vm['name'], image_name, flavor_name)
            niclist = []
            for server in self.config.serverNetList:
                if self.update_name_with_prefix(server['name']) == vm['name']:
                    if 'netList' in server:
                        for net_name in server['netList']:
                            temp = {}
                            ntwrk_name = list(net_name)[0]
                            tmp_name = self.update_name_with_prefix(ntwrk_name)
                            temp['net-id'] = self.get_net_id(tmp_name)
                            niclist.append(temp)
            vm['nics'] = niclist
            logging.info(">>> Networks for the VM: %s", niclist)
            _vm = self.novaclient.servers.create(**vm)
            vm_ids.append(_vm.id)
            wait_until_vms_created([_vm.id])

    def create_networks(self, networks):

        def get_body_for_network_creating(_net):
            # Possible parameters for network creating
            params = ['name', 'admin_state_up', 'shared', 'router:external',
                      'provider:network_type', 'provider:segmentation_id',
                      'provider:physical_network']
            return {param: _net[param] for param in params if param in _net}

        def get_body_for_subnet_creating(_subnet):
            # Possible parameters for subnet creating
            params = ['name', 'cidr', 'dns_nameservers', 'allocation_pools',
                      'ip_version', 'network_id', 'enable_dhcp', 'gateway_ip']
            return {param: _subnet[param] for param in params
                    if param in _subnet}

        for network in networks:
            network_new = get_body_for_network_creating(network)
            network_new['name'] = self.update_name_with_prefix(
                network_new['name'])
            net = self.neutronclient.create_network(
                {'network': network_new})
            for subnet in network['subnets']:
                subnet['network_id'] = net['network']['id']
                subnet_new = get_body_for_subnet_creating(subnet)
                if 'name' in subnet.keys():
                    subnet_new['name'] = self.update_name_with_prefix(
                        subnet_new['name'])
                _subnet = self.neutronclient.create_subnet(
                    {'subnet': subnet_new})
                if not subnet.get('routers_to_connect'):
                    continue
                # If network has attribute routers_to_connect, interface to
                # this network is crated for given router, in case when network
                # is internal and gateway set if - external.
                for router in subnet['routers_to_connect']:
                    router = self.update_name_with_prefix(router)
                    router_id = self.get_router_id(router)
                    if network.get('router:external'):
                        self.neutronclient.add_gateway_router(
                            router_id, {"network_id": net['network']['id']})
                    else:
                        self.neutronclient.add_interface_router(
                            router_id, {"subnet_id": _subnet['subnet']['id']})

    def create_all_networking(self):
        self.create_routers()
        self.create_networks(self.config.networks)

    def create_routers(self):
        for router in self.config.routers:
            router['router']['name'] = self.prefix + router['router']['name']
            logging.info(">>> Creating Router %s", router['router']['name'])
            self.neutronclient.create_router(router)

    def create_security_grp(self, sg_list):
        for security_group in sg_list:
            if security_group['name'] != 'default':
                name = self.update_name_with_prefix(security_group['name'])
                logging.info('>>> Creating Security Group: %s', name)
                gid = self.novaclient.security_groups.create(
                    name, description=security_group['description']).id
                logging.info('>>> Adding rules to Security Group: %s', name)
            else:
                security_group_list = self.novaclient.security_groups.list()
                for sg_list in security_group_list:
                    if sg_list.name == 'default':
                        gid = sg_list.id
                logging.info('>>> Adding rules to Security Group: Default')
            if 'rules' in security_group:
                for rule in security_group['rules']:
                    self.novaclient.security_group_rules.create(
                        gid,
                        ip_protocol=rule['ip_protocol'],
                        from_port=rule['from_port'], to_port=rule['to_port'],
                        cidr=rule['cidr'])

    def upload_image(self):
        @retry_until_resources_created('image')
        def wait_until_images_created(image_ids):
            for img_id in image_ids[:]:
                img = self.glanceclient.images.get(img_id)
                if img.status == 'active':
                    image_ids.remove(img_id)
            return image_ids

        img_ids = []
        for tenant in self.config.tenants:
            if not tenant.get('images'):
                continue
            for image in tenant['images']:
                self.switch_user(user=self.username, password=self.password,
                                 tenant=self.update_name_with_prefix(
                                     tenant['name']))
                img = self.glanceclient.images.create(**image)
                img_ids.append(img.id)
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)
        for image in self.config.images:
            image['name'] = self.update_name_with_prefix(image['name'])
            logging.info(">>> Uploading Image: %s", image['name'])
            img = self.glanceclient.images.create(**image)
            img_ids.append(img.id)
        wait_until_images_created(img_ids)
        src_cloud = Prerequisites(cloud_prefix='SRC', config=self.config)
        src_img = [x.__dict__ for x in
                   src_cloud.glanceclient.images.list()]
        for image in src_img:
            img_list = []
            for img_name in self.config.img_to_add_members:
                img_list.append(self.update_name_with_prefix(img_name))
            if image['name'] in img_list:
                image_id = image['id']
                tenant_list = self.keystoneclient.tenants.list()
                for tenant in tenant_list:
                    tenant = tenant.__dict__
                    img_mem_list = []
                    for mem_name in self.config.members:
                        img_mem_list.append(
                            self.update_name_with_prefix(mem_name))

                    if tenant['name'] in img_mem_list:
                        member_id = tenant['id']
                        self.glanceclient.image_members.create(image_id,
                                                               member_id)
        if getattr(self.config, 'create_zero_image', None):
            self.glanceclient.images.create()

    def create_security_groups(self):
        for sec_grp in self.config.security_groups:
            self.create_security_grp(sec_grp['security_groups'])

    def create_cinder_volumes(self, volumes_list):
        @retry_until_resources_created('volume')
        def wait_for_volumes(volume_ids):
            for volume_id in volume_ids[:]:
                _vlm = self.cinderclient.volumes.get(volume_id)
                if _vlm.status == 'available' or _vlm.status == 'in-use':
                    volume_ids.remove(volume_id)
                elif _vlm.status == 'error':
                    msg = 'Volume with id {0} was created with error'
                    raise RuntimeError(msg.format(volume_id))
            return volume_ids

        vlm_ids = []
        for volume in volumes_list:
            volume['name'] = self.update_name_with_prefix(volume['name'])
            logging.info('>>> Creating Volume:%s', volume['name'])
            vlm = self.cinderclient.volumes.create(display_name=volume['name'],
                                                   size=volume['size'])
            vlm_ids.append(vlm.id)
            wait_for_volumes(vlm_ids)
            if 'server_to_attach' in volume:
                server_to_attach = self.update_name_with_prefix(
                    volume['server_to_attach'])
                logging.info('>>> attaching volume to server:%s',
                             server_to_attach)
                self.novaclient.volumes.create_server_volume(
                    server_id=self.get_vm_id(server_to_attach),
                    volume_id=vlm.id,
                    device=volume['device'])
            wait_for_volumes(vlm_ids)
            vms = self.update_vm_status()
            inst_name = None
            for vol in self.config.cinder_volumes:
                if 'server_to_attach' in vol.keys():
                    inst_name = self.update_name_with_prefix(
                        vol['server_to_attach'])
            for vm in vms:
                if vm['name'] == inst_name:
                    index = vms.index(vm)
                    while vms[index]['status'] != 'ACTIVE':
                        time.sleep(5)
                        vms = self.update_vm_status()

    def create_cinder_snapshot(self, snapshot_list):
        for snapshot in snapshot_list:
            snapshot['volume_name'] = self.update_name_with_prefix(
                snapshot['volume_name'])
            snapshot['display_name'] = self.update_name_with_prefix(
                snapshot['display_name'])
            logging.info('>>> Creating snapshot: %s for volume: %s',
                         snapshot['display_name'],
                         snapshot['volume_name'])
            for vol in self.config.cinder_volumes:
                v_id = self.get_volume_id(vol['name'])
                if snapshot['volume_name'] == vol['name']:
                    snapshot['volume_id'] = v_id
                    self.cinderclient.volume_snapshots.create(
                        volume_id=v_id, force=True,
                        display_name=snapshot['display_name'])

    def create_cinder_objects(self):
        logging.info('>>> Creating Cinder Volumes:')
        self.create_cinder_volumes(self.config.cinder_volumes)
        logging.info('>>> Creating Cinder Snapshots:')
        self.create_cinder_snapshot(self.config.cinder_snapshots)
        self.cinderclient.volume_snapshots.list()

    def emulate_vm_states(self):
        for vm_state in self.config.vm_states:
            # emulate error state:
            if vm_state['state'] == u'error':
                self.novaclient.servers.reset_state(
                    server=self.get_vm_id(vm_state['name']),
                    state=vm_state['state'])
            # emulate suspend state:
            if vm_state['state'] == u'suspend':
                self.novaclient.servers.suspend(
                    self.get_vm_id(vm_state['name']))
            # emulate resize state:
            elif vm_state['state'] == u'pause':
                self.novaclient.servers.pause(self.get_vm_id(vm_state['name']))
            # emulate stop/shutoff state:
            elif vm_state['state'] == u'stop':
                self.novaclient.servers.stop(self.get_vm_id(vm_state['name']))
            # emulate resize state:
            elif vm_state['state'] == u'resize':
                self.novaclient.servers.resize(
                    self.get_vm_id(vm_state['name']), '2')

    def modify_quotas(self):
        for tenant in self.config.tenants:
            if 'quota' in tenant:
                self.novaclient.quotas.update(tenant_id=self.get_tenant_id(
                    tenant['name']), **tenant['quota'])

    def update_network_quotas(self):
        tenants = {ten.name: ten.id
                   for ten in self.keystoneclient.tenants.list()}
        for tenant in self.config.tenants:
            if "quota_network" not in tenant:
                continue
            ten_id = tenants[tenant["name"]]
            quota_net = tenant["quota_network"]
            self.neutronclient.update_quota(ten_id,
                                            {"quota": quota_net})

    @clean_if_exists
    def create_flavors(self):
        for flavor in self.config.flavors:
            flavor['name'] = self.update_name_with_prefix(flavor['name'])
            self.novaclient.flavors.create(**flavor)

    def create_vm_snapshots(self):
        @retry_until_resources_created('vm_snapshot')
        def wait_until_vm_snapshots_created(snapshot_ids):
            for snp_id in snapshot_ids[:]:
                snp = self.glanceclient.images.get(snp_id)
                if snp.status == 'active':
                    snp_ids.remove(snp_id)
                elif snp.status == 'error':
                    msg = 'Snapshot with id {0} has become in error state'
                    raise RuntimeError(msg.format(snp_id))
            return snapshot_ids

        snp_ids = []
        for snapshot in self.config.snapshots:
            snapshot['server'] = self.update_name_with_prefix(
                snapshot['server'])
            snapshot['image_name'] = self.update_name_with_prefix(
                snapshot['image_name'])
            logging.info(">>> Creating snapshot %s", snapshot['image_name'])
            self.novaclient.servers.create_image(
                server=self.get_vm_id(snapshot['server']),
                image_name=snapshot['image_name'])
            snp = self.glanceclient.images.get(self.get_image_id(
                snapshot['image_name']))
            snp_ids.append(snp.id)
        wait_until_vm_snapshots_created(snp_ids)

    def set_prefix(self, pref=None):
        self.prefix = pref + '_'

    def update_name_with_prefix(self, resource_name=None):
        new_name = self.prefix + resource_name
        return new_name

    def create_options(self, function=None):
        ''' This function is used to create resources
            depending upon the option provided for the
            tenant in configuration file '''
        print "going to call :" + function
        if function != 'create_tenants':
            ten = self.config.tenants[0]
            tenant_nm = self.update_name_with_prefix(ten['name'])
            found = False
            for tenant in self.keystoneclient.tenants.list():
                if tenant_nm in tenant.name:
                    found = True
                    for user in self.config.users:
                        self.switch_user(user['name'], user['password'],
                                         self.update_name_with_prefix(
                                             user['tenant']))
                    f = getattr(self, function)
                    f()
            if not found:
                logging.error(">>> Dependency Error: Tenant not found,"
                              "could not create resource")
        else:
            f = getattr(self, function)
            f()

    def run_preparation_scenario(self):
        logging.info(">>> Creating Resources ")
        self.create_tenants(self.config.tenants)
        user = None
        for user in self.config.users:
            self.switch_user(user['name'], user['password'],
                             self.update_name_with_prefix(user['tenant']))
        logging.info('>>> Creating Keypairs:')
        self.create_keypairs()  # Added prefix
        logging.info('>>> Modifying quotas:')
        self.modify_quotas()  # Added prefix
        self.update_network_quotas()  # Added Prefix
        logging.info('>>> Uploading images:')
        self.upload_image()
        self.switch_user(user['name'], user['password'],
                         self.update_name_with_prefix(user['tenant']))
        logging.info('>>> Creating Networks:')
        self.create_all_networking()  # Added prefix
        logging.info('>>> Creating Flavors:')
        self.create_flavors()  # Added prefix
        logging.info('>>> Creating VMs:')
        self.create_vms()  # Added Prefix
        logging.info('>>> Creating Security Groups:')
        self.create_security_groups()
        logging.info('>>> Creating VM Snapshots:')
        self.create_vm_snapshots()   # Added Prefix
        logging.info('>>> Creating Cinder Objects:')
        self.create_cinder_objects()  # Added Prefix

    def clean_tenant(self):
        tenants_names = [self.update_name_with_prefix(
            tenant['name']) for tenant in self.config.tenants]
        for tenant in self.keystoneclient.tenants.list():
            if tenant.name not in tenants_names:
                continue
            self.keystoneclient.tenants.delete(self.get_tenant_id(tenant.name))
            logging.info('>>> Tenant "%s" Deleted !!', tenant.name)

    def clean_flavors(self):
        flavors_names = [self.update_name_with_prefix(
            flavor['name']) for flavor in self.config.flavors]
        for flavor in self.novaclient.flavors.list():
            if flavor.name not in flavors_names:
                continue
            self.novaclient.flavors.delete(self.get_flavor_id(flavor.name))
            logging.info('>>> Flavor "%s" Deleted !!', flavor.name)

    def delete_port(self, port):
        port_owner = port['device_owner']
        if port_owner == 'network:router_gateway':
            self.neutronclient.remove_gateway_router(port['device_id'])
        elif port_owner == 'network:router_interface':
            self.neutronclient.remove_interface_router(
                port['device_id'], {'port_id': port['id']})
        elif port_owner == 'network:dhcp' or not port_owner:
            self.neutronclient.delete_port(port['id'])
        else:
            msg = 'Unknown port owner %s'
            raise RuntimeError(msg % port['device_owner'])

    def clean_router_ports(self, router_id):
        ports = self.neutronclient.list_ports(device_id=router_id)['ports']
        for port in ports:
            self.delete_port(port)

    def clean_objects(self):
        try:
            logging.info(">>> Cleaning Resources")
            for user, keypair in zip(self.config.users, self.config.keypairs):
                keypair['name'] = self.update_name_with_prefix(keypair['name'])
                if user['enabled'] is True:
                    self.switch_user(user=user['name'],
                                     tenant=self.update_name_with_prefix(
                                         user['tenant']),
                                     password=user['password'])
                    self.novaclient.keypairs.delete(keypair['name'])
                    logging.info('>>> Keypair: %s Deleted !!', keypair['name'])
        except (nv_exceptions.NotFound, generate_load.NotFound) as e:
            logging.error(">>> Keypair failed to delete:\n %s", (repr(e)))
        vms = self.config.vms
        logging.info('>>> Cleaning VMs')
        for vm in vms:
            vm['name'] = self.update_name_with_prefix(vm['name'])
            try:
                self.novaclient.servers.delete(self.get_vm_id(vm['name']))
                logging.info('>>> VM: %s Deleted !!', vm['name'])
            except (nv_exceptions, generate_load.NotFound) as e:
                logging.error(">>> VM failed to delete:\n %s", (repr(e)))
        logging.info('>>> Cleaning Images')
        for image in self.config.images:
            image['name'] = self.update_name_with_prefix(image['name'])
            try:
                self.glanceclient.images.delete(
                    self.get_image_id(image['name']))
                time.sleep(2)
                logging.info('>>> Image: %s Deleted !!', image['name'])
            except (gl_exceptions, generate_load.NotFound) as e:
                logging.warning(">>> Image %s failed to delete: %s",
                                image['name'], repr(e))
        nets = self.config.networks
        floatingips = self.neutronclient.list_floatingips()['floatingips']
        for ip in floatingips:
            try:
                self.neutronclient.delete_floatingip(ip['id'])
            except (nt_exceptions, generate_load.NotFound):
                pass
        try:
            router_name = self.update_name_with_prefix(
                self.config.routers[0]['router']['name'])
            self.neutronclient.remove_gateway_router(
                self.get_router_id(router_name))
        except (nt_exceptions, generate_load.NotFound):
            pass

        tnt_id = self.get_tenant_id(self.update_name_with_prefix(
            self.config.tenants[0]['name']))
        for port in self.neutronclient.list_ports(tnt_id)['ports']:
            try:
                for tnt in self.config.tenants:
                    if port['tenant_id'] == self.get_tenant_id(
                            self.update_name_with_prefix(tnt['name'])):
                        self.neutronclient.remove_interface_router(
                            self.get_router_id(self.update_name_with_prefix(
                                self.config.routers[0]['router']['name'])),
                            {'port_id': port['id']})
            except (nt_exceptions.NeutronClientException,
                    generate_load.NotFound):
                pass
        logging.info('>>> Cleaning Routers')
        for router in self.config.routers:
            router['router']['name'] = self.update_name_with_prefix(
                router['router']['name'])
            try:
                time.sleep(1)
                router_id = self.get_router_id(router['router']['name'])
                self.clean_router_ports(router_id)
                time.sleep(1)
                self.neutronclient.delete_router(router_id)
                logging.info('>>> Router: %s Deleted !!',
                             router['router']['name'])
            except (nt_exceptions, generate_load.NotFound):
                pass
        logging.info('>>> Cleaning Networks')
        for network in nets:
            try:
                time.sleep(5)
                network['name'] = self.update_name_with_prefix(network['name'])
                self.neutronclient.delete_network(self.get_net_id(
                    network['name']))
                logging.info(">>> Network: %s Deleted !!", network['name'])
            except (nt_exceptions, generate_load.NotFound):
                pass
        for snapshot in self.config.snapshots:
            try:
                time.sleep(2)
                snapshot['image_name'] = self.update_name_with_prefix(
                    snapshot['image_name'])
                self.glanceclient.images.delete(
                    self.get_image_id(snapshot['image_name']))
                logging.info(">>> VM Snapshot: : %s Deleted !!",
                             snapshot['image_name'])
            except (gl_exceptions, generate_load.NotFound) as e:
                logging.info(">>> Image %s failed to delete: %s",
                             snapshot['image_name'], repr(e))
        time.sleep(5)
        logging.info('>>> Cleaning Security Groups:')
        sgs = self.neutronclient.list_security_groups()['security_groups']
        for sg in sgs:
            try:
                for tnt in self.config.tenants:
                    if sg['tenant_id'] == self.get_tenant_id(
                            self.update_name_with_prefix(tnt['name'])):
                        self.neutronclient.delete_security_group(
                            self.get_sg_id(sg['name']))
                        time.sleep(3)
                        logging.info(">>> Security Group: : %s Deleted !!",
                                     sg['name'])
            except (nt_exceptions.NeutronClientException,
                    generate_load.NotFound):
                pass
        logging.info('>>> Cleaning Volume Snapshots:')
        snapshots = self.config.cinder_snapshots
        for snapshot in snapshots:
            snapshot['display_name'] = self.update_name_with_prefix(
                snapshot['display_name'])
            try:
                time.sleep(1)
                self.cinderclient.volume_snapshots.delete(
                    self.get_volume_snapshot_id(snapshot['display_name']))
                logging.info(">>> Volume Snapshot: : %s Deleted !!",
                             snapshot['display_name'])
            except (cd_exceptions, generate_load.NotFound):
                pass
        logging.info('>>> Cleaning Volumes:')
        time.sleep(5)
        volumes = self.config.cinder_volumes
        for volume in volumes:
            volume['name'] = self.update_name_with_prefix(volume['name'])
            try:
                time.sleep(5)
                self.cinderclient.volumes.delete(self.cinderclient.volumes.get(
                    self.get_volume_id(volume['name'])))
                logging.info('>>> Volume: : "%s" Deleted !!', volume['name'])
            except (cd_exceptions, generate_load.NotFound):
                pass

        logging.info('>>> Cleaning Flavors:')
        self.clean_flavors()
        time.sleep(2)
        logging.info('>>> Cleaning Tenant:')
        self.clean_tenant()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to generate load and delete generated resources',
        formatter_class=RawTextHelpFormatter)
    parser.add_argument('--clean', action='store_true',
                        help='clean objects described in real_env_conf.ini')
    help_str = ""
    for item in sorted([(k, v) for k, v in RESOURCE_CREATE_MAP.iteritems()]):
        help_str = help_str + '\n' + str(item[0]) + ' : ' + str(item[1])
    help_str = help_str + "\n\n" + "Note: Dependent resources must exist\n\n"
    parser.add_argument('--option', type=int, required=False, help=help_str)
    parser.add_argument('--config_file', type=argparse.FileType('r'),
                        help='input config file', required=True)
    parser.add_argument('--prefix',
                        help='input prefix to be added to resource names',
                        required=True)
    _args = parser.parse_args()
    modname = _args.config_file.name
    cfname = os.path.basename(modname)
    cfig = cfname.split('.')
    real_env_conf = __import__(cfig[0])
    preqs = Prerequisites(config=real_env_conf)
    log_file = cfig[0] + '_' + _args.prefix + '.log'
    logging.basicConfig(filename=log_file,
                        format='%(asctime)s %(levelname)s: %(message)s',
                        level=logging.DEBUG)
    logging.handlers.RotatingFileHandler(log_file, backupCount=20)
    preqs.set_prefix(_args.prefix)

    if _args.option:
        option_num = _args.option
        keyoption = str(option_num)
        funct = RESOURCE_CREATE_MAP[keyoption]
        logging.info(">>> Option selected:" + keyoption)
        logging.info(">>> Going to create resource:" +
                     RESOURCE_CREATE_MAP[keyoption])
        preqs.create_options(funct)
        sys.exit()

    if _args.clean:
        preqs.clean_objects()
    else:
        preqs.run_preparation_scenario()

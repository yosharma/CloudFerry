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


import copy
import time
from sqlalchemy import exc

from cloudferrylib.cs.client import client
from cloudferrylib.base import compute
from cloudferrylib.utils import mysql_connector
from cloudferrylib.utils import timeout_exception
from cloudferrylib.utils import utils as utl


LOG = utl.get_log(__name__)


DISK = "disk"
LOCAL = ".local"
LEN_UUID_INSTANCE = 36
INTERFACES = "interfaces"


class Compute(compute.Compute):
    PATH_STORAGE = "/mnt/usr/export/primary"
    """The main class for working with Openstack Nova Compute Service. """

    def __init__(self, config, cloud):
        super(Compute, self).__init__()
        self.config = config
        self.cloud = cloud
        # self.identity = cloud.resources['identity']
        # self.mysql_connector = mysql_connector.MysqlConnector(config.mysql,
        #                                                       'nova')
        self.client = self.proxy(self.get_client(), config)

    def get_client(self, params=None):
        """Getting nova client. """

        params = self.config if not params else params

        return client.ClientCloudStack(params.cloud.auth_url,
                                       params.cloud.user,
                                       params.cloud.password,
                                       params.cloud.secretkey,
                                       params.cloud.apikey,)

    def stop_vm(self, inst_id):
        self.client.stop_vm(id=inst_id)

    def get_status(self, inst_id):
        status = self.client.get_instances(inst_id=inst_id)[0]['state']
        return status

    def __read_info_instances(self, **kwargs):
        instances = self.client.get_instances(**getattr(kwargs, 'search_opts', {}))
        instances_new = {}
        for inst in instances:
            instances_new[inst['id']] = self.convert_instance(inst,
                                                              self.config,
                                                              self.cloud)
            flavor = self.__get_flavor(inst['serviceofferingid'],
                                       inst['id'])
            instances_new[inst['id']]['instance']['flavors'] = [flavor]
            instances_new[inst['id']]['diff'] = self.__get_diff(inst['id'])
            root = self.client.get_volumes(virtualmachineid=inst['id'], type="ROOT")[0]
            instances_new[inst['id']]['instance']['rootDisk'] = [root]
            instances_new[inst['id']]['instance']['is_template'] = \
                self.__is_load_from_template(inst['templateid'])
            instances_new[inst['id']]['instance']['disks'] = self.__get_disks(inst['id'])
        return instances_new

    def __get_disks(self, inst_id):
        type_disk = 'DATADISK'
        volumes = self.client.get_volumes(virtualmachineid=inst_id, type=type_disk)
        return volumes

    def __get_diff(self, inst_id):
        root = self.client.get_volumes(virtualmachineid=inst_id, type="ROOT")[0]
        diff = {
            'host_src': self.config.cloud.host,
            'host_dst': None,
            'path_src': '%s/%s' % (self.PATH_STORAGE, root['id']),
            'path_dst': None
        }
        return diff

    def __get_flavor(self, serviceofferingid, inst_id):
        serviceoffering = self.client.get_service_offering(id=serviceofferingid)
        root = self.client.get_volumes(virtualmachineid=inst_id, type="ROOT")[0]
        flavor = {
            'name': serviceoffering[0]['name'],
            'ram': serviceoffering[0]['memory'],
            'vcpus': serviceoffering[0]['cpunumber'],
            'disk': root['size']/(1024*1024*1024),
            'ephemeral': 0,
            'swap': 0,
            'rxtx_factor': 1.0,
            'is_public': True,
            # 'tenants': ['admin']
        }
        return flavor

    def __is_load_from_template(self, templateid):
        templates = [temp['id'] for temp in self.client.get_templates(templatefilter="all")]
        return templateid in templates

    def read_info(self, target='instances', **kwargs):
        info = {}
        if target == 'instances':
            info['instances'] = self.__read_info_instances(**kwargs)
        return info

    @staticmethod
    def convert_instance(instance, cfg, cloud):
        inst_raw = {
            'instance': copy.deepcopy(instance),
            'diff': {},
            'volumes': [],
            'meta': {}
        }
        inst = {
            'rootDisk': [],
            'disks': {},
            'backing_file': instance['serviceofferingid'],
            'name': instance['name'],
            'network': instance['nic'],
            'interfaces': [{
                'ip': None,
                'mac': nic['macaddress'],
                'name': 'net04',
                'floatingip': nic["ipaddress"]
            } for nic in instance['nic']],
            'security_groups': ['default'],
            'tenant_name': 'admin',
            'nics': [],
            'key_name': 'qwerty',
            'flavor': None,
            'image': None,
            'boot_mode': 'image',
            'flavors': []}
        inst_raw['instance'].update(inst)
        return inst_raw

    def deploy(self, info, target='instances', **kwargs):
        """
        Deploy compute resources to the cloud.

        :param target: Target objects to deploy. Possible values:
                       "instances" or "resources",
        :param identity_info: Identity info.
        """

        info = copy.deepcopy(info)

        if target == 'instances':
            info = self._deploy_instances(info)
        else:
            raise ValueError('Only "resources" or "instances" values allowed')

        return info

    def _deploy_instances(self, info_compute):
        pass

    def create_instance(self, **kwargs):
        pass

    def get_instances_list(self, detailed=True, search_opts=None, marker=None,
                           limit=None):
        """
        Get a list of servers.

        :param detailed: Whether to return detailed server info (optional).
        :param search_opts: Search options to filter out servers (optional).
        :param marker: Begin returning servers that appear later in the server
                       list than that represented by this server id (optional).
        :param limit: Maximum number of servers to return (optional).

        :rtype: list of :class:`Server`
        """
        pass

    def get_instance(self, instance_id):
        pass

    def change_status(self, status, instance=None, instance_id=None):
        pass

    def wait_for_status(self, id_obj, status, limit_retry=90):
        #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        count = 0
        while self.get_status(id_obj).lower() != status.lower():
            time.sleep(2)
            count += 1
            if count > limit_retry:
                raise timeout_exception.TimeoutException(
                    getter.get(id_obj).status.lower(), status, "Timeout exp")
        #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        pass

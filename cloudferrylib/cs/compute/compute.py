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
                                       params.cloud.username,
                                       params.cloud.password,
                                       params.cloud.secretkey,
                                       params.cloud.apikey,)

    def __read_info_instances(self, **kwargs):
        instances = self.client.get_instances(**kwargs)
        instances_new = {}
        for inst in instances:
            instances_new[inst['id']] = self.convert_instance(inst,
                                                              self.config,
                                                              self.cloud)
        return instances_new

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
            'meta': {},
        }
        inst = {}
        # inst = {'name': instance["name"],
        #         'instance_name': instance["instancename"],
        #         'id': instance['id'],
        #         'tenant_id': instance["projectid"],
        #         'tenant_name': instance["project"],
        #         'status': instance["state"],
        #         'flavor_id': None,
        #         'serviceofferingid': instance["serviceofferingid"],
        #         'diskofferingid': instance["diskofferingid"],
        #         'diskofferingname': instance["diskofferingname"],
        #         'serviceofferingname': instance["serviceofferingname"],
        # }
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
        getter = self.client.servers
        while getter.get(id_obj).status.lower() != status.lower():
            time.sleep(2)
            count += 1
            if count > limit_retry:
                raise timeout_exception.TimeoutException(
                    getter.get(id_obj).status.lower(), status, "Timeout exp")
        #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        pass

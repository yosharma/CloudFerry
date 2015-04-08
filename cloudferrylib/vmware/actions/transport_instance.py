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

from fabric.api import env
from fabric.api import run
from fabric.api import settings

from cloudferrylib.base.action import action
from cloudferrylib.os.actions import convert_file_to_image
from cloudferrylib.os.actions import convert_image_to_file
from cloudferrylib.os.actions import convert_volume_to_image
from cloudferrylib.os.actions import copy_g2g
from cloudferrylib.os.actions import task_transfer
from cloudferrylib.utils import utils as utl, forward_agent


CLOUD = 'cloud'
BACKEND = 'backend'
CEPH = 'ceph'
ISCSI = 'iscsi'
COMPUTE = 'compute'
INSTANCES = 'instances'
INSTANCE_BODY = 'instance'
INSTANCE = 'instance'
DIFF = 'diff'
EPHEMERAL = 'ephemeral'
DIFF_OLD = 'diff_old'
EPHEMERAL_OLD = 'ephemeral_old'

PATH_DST = 'path_dst'
HOST_DST = 'host_dst'
PATH_SRC = 'path_src'
HOST_SRC = 'host_src'

TEMP = 'temp'
FLAVORS = 'flavors'


TRANSPORTER_MAP = {CEPH: {CEPH: 'ssh_ceph_to_ceph',
                          ISCSI: 'ssh_ceph_to_file'},
                   ISCSI: {CEPH: 'ssh_file_to_ceph',
                           ISCSI: 'ssh_file_to_file'}}
from cloudferrylib.utils.ssh_util import SshUtil


class TransportInstance(action.Action):
    # TODO constants

    def run(self, info=None, **kwargs):
        DC = "test"
        DS = "datastore1"
        VM = "centos2"
        src_cloud = self.src_cloud
        dst_cloud = self.dst_cloud
        ssh = SshUtil(None, None, "localhost")
        computeVMWare = src_cloud.resources['compute']
        network = dst_cloud.resources['network']
        identity = dst_cloud.resources['identity']
        compute = dst_cloud.resources['compute']
        info = computeVMWare.get(DC, DS, VM)
        data = info['instances'][0]['instance']
        cfg = self.dst_cloud.cloud_config.cloud

        computeVMWare.download_disk('root',
                                    dst_cloud.getIpSsh(),
                                    data['dcPath'],
                                    data['dsName'],
                                    data['diskFile'][0],
                                    data['vmName'],
                                    data['diskFile'][0])
        computeVMWare.convert_flat_disk('root',
                                        dst_cloud.getIpSsh(),
                                        data['diskFile'][0],
                                        "%s.img" % data['diskFile'][0])
        cmd = ("glance --os-username=%s --os-password=%s --os-tenant-name=%s " +
                       "--os-auth-url=%s " +
                       "image-create --name %s --disk-format=%s --container-format=bare --file %s| " +
                       "grep id") %\
              (cfg.user,
               cfg.password,
               cfg.tenant,
               cfg.auth_url,
               data['vmName'] + '.img',
               'qcow2',
               "%s.img" % data['diskFile'][0])
        image_id = ssh.execute(cmd, host_exec=cfg.host, user='root').split("|")[2].replace(' ', '')
        data['image'] = image_id
        dest_flavors = {flavor.name: flavor.id for flavor in
                        compute.get_flavor_list(is_public=None)}
        if data['flavors'][0]['name'] not in dest_flavors:
            data['flavor'] = compute.create_flavor(
                name=data['flavors'][0]['name'],
                ram=data['flavors'][0]['ram'],
                vcpus=data['flavors'][0]['vcpus'],
                disk=data['flavors'][0]['disk'],
                ephemeral=data['flavors'][0]['ephemeral'],
                swap=data['flavors'][0]['swap'],
                rxtx_factor=data['flavors'][0]['rxtx_factor'],
                is_public=data['flavors'][0]['is_public']).id
        else:
            data['flavor'] = dest_flavors[data['flavors'][0]['name']]
        tenant_id = identity.get_tenant_id_by_name("admin")
        dst_net = network.get_network({'name': 'net04'}, tenant_id, False)
        port_id = network.check_existing_port(dst_net['id'],
                                              data['network'][0]['mac'])
        if port_id:
            network.delete_port(port_id)
        port = network.create_port(dst_net['id'],
                                   data['network'][0]['mac'],
                                   data['network'][0]['ip'],
                                   tenant_id,
                                   False, [])
        data['nics'] = [{'net-id': dst_net['id'], 'port-id': port['id']}]
        compute.create_instance(**{'name': data['name'],
                                   'flavor': data['flavor'],
                                   'key_name': data['key_name'],
                                   'nics': data['nics'],
                                   'image': data['image']})
        return {}
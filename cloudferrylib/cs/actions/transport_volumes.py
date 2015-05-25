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


from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl
from fabric.api import settings, run
from cloudferrylib.utils.drivers import ssh_file_to_file
from cloudferrylib.os.actions import prepare_networks

AVAILABLE = 'available'

CMD_GLANCE = ("glance --os-username=%s --os-password=%s --os-tenant-name=%s " +
                   "--os-auth-url=%s " +
                   "image-create --name %s --disk-format=%s --container-format=bare --file %s| " +
                   "grep id")


class TransportVolumes(action.Action):
    def __init__(self, init, cloud=None):
        super(TransportVolumes, self).__init__(init, cloud)

    def run(self, info=None, **kwargs):
        # search_opts = kwargs.get('search_opts', {})
        compute_resource_dst = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]
        storage_resource_dst = self.dst_cloud.resources[utl.STORAGE_RESOURCE]
        cfg_cloud_dst = compute_resource_dst.config.cloud
        #Create LOOP
        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']
            for i, disk in enumerate(data['disks']):
                image_vol = self.convert_to_image(data['name']+'_vol',
                                                  "%s/%s" % (cfg_cloud_dst.temp, disk['id']))
                #Deploy Volume
                info_vol = {
                    'size': disk["size"]/(1024*1024*1024),
                    'display_name': disk["name"],
                    'display_description': disk["name"],
                    'volume_type': None,
                    'imageRef': image_vol
                }
                volume = storage_resource_dst.create_volume(**info_vol)
                inst['meta']['volume'].append({
                    'volume': {
                        'id': volume.id,
                        'device': "/dev/vd"+chr(ord("b")+i)
                    }
                })
                storage_resource_dst.wait_for_status(volume.id, AVAILABLE)

        return {
            'info': info
        }

    def convert_to_image(self, name, path, format_img='qcow2'):
        compute_resource_dst = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]
        cfg_cloud_dst = compute_resource_dst.config.cloud
        with settings(host_string=cfg_cloud_dst.host):
                    out = run(CMD_GLANCE %
                              (cfg_cloud_dst.user,
                               cfg_cloud_dst.password,
                               cfg_cloud_dst.tenant,
                               cfg_cloud_dst.auth_url,
                               name,
                               format_img,
                               path))
                    image_id = out.split("|")[2].replace(' ', '')
                    return image_id


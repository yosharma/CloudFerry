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


class PrepareDataVolumes(action.Action):
    def __init__(self, init, cloud=None):
        super(PrepareDataVolumes, self).__init__(init, cloud)

    def run(self, info=None, **kwargs):
        # search_opts = kwargs.get('search_opts', {})
        compute_resource_src = self.src_cloud.resources[utl.COMPUTE_RESOURCE]
        compute_resource_dst = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]
        cfg_cloud_src = compute_resource_src.config.cloud
        cfg_cloud_dst = compute_resource_dst.config.cloud
        info_volumes = {
            'volumes': {

            }
        }
        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']
            for i, disk in enumerate(data['disks']):
                #NOTE: Need add it is struct in INSTANCES INFO
                data_trans = {'volume': {
                    'host_src': cfg_cloud_src.host,
                    'path_src': "%s/%s" % (compute_resource_src.PATH_STORAGE, disk['id']),
                    'host_dst': cfg_cloud_dst.host,
                    'path_dst': "%s/%s" % (cfg_cloud_dst.temp, disk['id'])
                }}
                info_volumes['volumes'][disk['id']] = data_trans

        return {
            'info_volumes': info_volumes
        }

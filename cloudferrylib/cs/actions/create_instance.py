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


class CreateInstance(action.Action):
    def __init__(self, init, cloud=None):
        super(CreateInstance, self).__init__(init, cloud)

    def run(self, info=None, **kwargs):
        # search_opts = kwargs.get('search_opts', {})
        compute_resource_dst = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]
        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']
            data['id'] = compute_resource_dst.create_instance(**{'name': data['name'],
                                                                 'flavor': data['flavor'],
                                                                 'key_name': data['key_name'],
                                                                 'nics': data['nics'],
                                                                 'image': data['image']})
            compute_resource_dst.wait_for_status(data['id'], 'active')
        return {
            'info': info
        }

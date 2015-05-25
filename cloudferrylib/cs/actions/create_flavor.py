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


class CreateFlavor(action.Action):
    def __init__(self, init, cloud=None):
        super(CreateFlavor, self).__init__(init, cloud)

    def run(self, info=None, **kwargs):
        # search_opts = kwargs.get('search_opts', {})
        compute_resource_dst = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]
        #Create LOOP
        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']
            # Task Create Flavor
            dest_flavors = {flavor.name: flavor.id for flavor in
                            compute_resource_dst.get_flavor_list(is_public=None)}
            if data['flavors'][0]['name'] not in dest_flavors:
                data['flavor'] = compute_resource_dst.create_flavor(**data['flavors'][0]).id
            else:
                data['flavor'] = dest_flavors[data['flavors'][0]['name']]

        return {
            'info': info
        }

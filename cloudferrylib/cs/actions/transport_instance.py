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


class TransportInstances(action.Action):
    def __init__(self, init, cloud=None):
        super(TransportInstances, self).__init__(init, cloud)

    def run(self, **kwargs):
        search_opts = kwargs.get('search_opts', None)
        compute_resource_src = self.src_cloud.resources[utl.COMPUTE_RESOURCE]
        compute_resource_dst = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]
        info = compute_resource_src.read_info(search_opts=search_opts)
        #create flavor
        flavor_dst =
        #create port
        #get diff image
        #trans diff to glance
        #trans volume
        #create instance
        return {
            'info': info
        }

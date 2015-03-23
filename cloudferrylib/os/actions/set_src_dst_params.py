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

from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl


class SetSrcDstParams(action.Action):
    def __init__(self, init, cloud=None, src_data="src_info", dst_data="dst_info", result="info"):
        self.src_data = src_data
        self.dst_data = dst_data
        self.result = result
        super(SetSrcDstParams, self).__init__(init, cloud)

    def run(self, **kwargs):
        src = kwargs[self.src_data]
        dst = kwargs[self.dst_data]
        res = kwargs[self.result]
        # import pdb; pdb.set_trace()
        storage_resource_src = self.src_cloud.resources[utl.STORAGE_RESOURCE]
        storage_resource_dst = self.dst_cloud.resources[utl.STORAGE_RESOURCE]


        return {}

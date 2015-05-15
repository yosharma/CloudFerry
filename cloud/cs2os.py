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


import cloud
import cloud_ferry
from cloudferrylib.scheduler import scheduler
from cloudferrylib.scheduler import namespace
from cloudferrylib.scheduler import cursor
from cloudferrylib.cs.compute import compute
from cloudferrylib.cs.actions import transport_instance
from cloudferrylib.utils import utils as utl


class CS2OSFerry(cloud_ferry.CloudFerry):

    def __init__(self, config):
        super(CS2OSFerry, self). __init__(config)
        resources = {'compute': compute.Compute}
        self.src_cloud = cloud.Cloud(resources, cloud.SRC, config)
        self.dst_cloud = cloud.Cloud(resources, cloud.DST, config)
        self.init = {
            'src_cloud': self.src_cloud,
            'dst_cloud': self.dst_cloud,
            'cfg': self.config
        }

    def migrate(self, scenario=None):
        namespace_scheduler = namespace.Namespace({
            '__init_task__': self.init,
            'info_result': {
                utl.INSTANCES_TYPE: {}
            }
        })
        if not scenario:
            process_migration = {"migration": cursor.Cursor(self.process_migrate())}
        else:
            scenario.init_tasks(self.init)
            scenario.load_scenario()
            process_migration = {k: cursor.Cursor(v) for k, v in scenario.get_net().items()}
        scheduler_migr = scheduler.Scheduler(namespace=namespace_scheduler, **process_migration)
        scheduler_migr.start()

    def process_migrate(self):
        return transport_instance.TransportInstances(self.init, 'src_cloud')

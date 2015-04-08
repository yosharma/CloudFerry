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
from cloudferrylib.os.image import glance_image
from cloudferrylib.os.storage import cinder_storage
from cloudferrylib.os.network import neutron
from cloudferrylib.os.identity import keystone
from cloudferrylib.os.compute import nova_compute
from cloudferrylib.os.object_storage import swift_storage
from cloudferrylib.utils import utils as utl
from cloudferrylib.vmware.compute import compute
from cloudferrylib.vmware.actions import transport_instance


class Vmware2OSFerry(cloud_ferry.CloudFerry):

    def __init__(self, config):
        super(Vmware2OSFerry, self). __init__(config)
        resources_os = {'identity': keystone.KeystoneIdentity,
                        'image': glance_image.GlanceImage,
                        'storage': cinder_storage.CinderStorage,
                        'network': neutron.NeutronNetwork,
                        'compute': nova_compute.NovaCompute}
        resources_vmware = {'compute': compute.ComputeVMWare,
                            'identity': compute.ComputeVMWare
        }
        self.src_cloud = cloud.Cloud(resources_vmware, cloud.SRC, config)
        self.dst_cloud = cloud.Cloud(resources_os, cloud.DST, config)
        self.init = {
            'src_cloud': self.src_cloud,
            'dst_cloud': self.dst_cloud,
            'cfg': self.config,
        }

    def migrate(self, scenario=None):
        namespace_scheduler = namespace.Namespace({
            '__init_task__': self.init,
            'info_result': {
                utl.INSTANCES_TYPE: {}
            }
        })
        process_migration = {"migration": cursor.Cursor(self.process_migrate())}
        scheduler_migr = scheduler.Scheduler(namespace=namespace_scheduler, **process_migration)
        scheduler_migr.start()

    def process_migrate(self):
        return transport_instance.TransportInstance(self.init, 'src_cloud')

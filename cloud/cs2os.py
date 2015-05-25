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
from cloudferrylib.os.compute import nova_compute
from cloudferrylib.os.identity import keystone
from cloudferrylib.os.image import glance_image
from cloudferrylib.os.storage import cinder_storage
from cloudferrylib.os.network import neutron
from cloudferrylib.cs.actions import transport_volumes
from cloudferrylib.cs.actions import create_flavor
from cloudferrylib.cs.actions import merge_root
from cloudferrylib.os.actions import attach_used_volumes_via_compute
from cloudferrylib.cs.actions import create_instance
from cloudferrylib.cs.actions import prepare_data_volumes
from cloudferrylib.cs.actions import upload_file_to_glance
from cloudferrylib.os.actions import get_filter
from cloudferrylib.os.actions import get_info_instances
from cloudferrylib.os.actions import prepare_networks
from cloudferrylib.os.actions import stop_vm
from cloudferrylib.utils import utils as utl
from cloudferrylib.base.action import copy_var, rename_info, merge, is_end_iter, get_info_iter
from cloudferrylib.base.action import create_reference
from cloudferrylib.utils.drivers import ssh_ceph_to_ceph
from cloudferrylib.utils.drivers import ssh_ceph_to_file
from cloudferrylib.utils.drivers import ssh_file_to_file
from cloudferrylib.utils.drivers import ssh_file_to_ceph
from cloudferrylib.os.actions import task_transfer


class CS2OSFerry(cloud_ferry.CloudFerry):

    def __init__(self, config):
        super(CS2OSFerry, self). __init__(config)
        resources_os = {'identity': keystone.KeystoneIdentity,
                        'image': glance_image.GlanceImage,
                        'storage': cinder_storage.CinderStorage,
                        'network': neutron.NeutronNetwork,
                        'compute': nova_compute.NovaCompute}
        resources = {'compute': compute.Compute,
                     'identity': compute.Compute}
        self.src_cloud = cloud.Cloud(resources, cloud.SRC, config)
        self.dst_cloud = cloud.Cloud(resources_os, cloud.DST, config)
        self.init = {
            'src_cloud': self.src_cloud,
            'dst_cloud': self.dst_cloud,
            'cfg': self.config,
            'SSHCephToCeph': ssh_ceph_to_ceph.SSHCephToCeph,
            'SSHCephToFile': ssh_ceph_to_file.SSHCephToFile,
            'SSHFileToFile': ssh_file_to_file.SSHFileToFile,
            'SSHFileToCeph': ssh_file_to_ceph.SSHFileToCeph
        }

    def migrate(self, scenario=None):
        namespace_scheduler = namespace.Namespace({
            '__init_task__': self.init,
            'info_result': {
                utl.INSTANCES_TYPE: {}
            }
        })
        # if not scenario:
        process_migration = {"migration": cursor.Cursor(self.process_migrate())}
        # else:
        #     scenario.init_tasks(self.init)
        #     scenario.load_scenario()
        #     process_migration = {k: cursor.Cursor(v) for k, v in scenario.get_net().items()}
        scheduler_migr = scheduler.Scheduler(namespace=namespace_scheduler, **process_migration)
        scheduler_migr.start()

    def process_migrate(self):
        name_data = 'info'
        name_result = 'info_result'
        name_backup = 'info_backup'
        name_iter = 'info_iter'
        save_result = self.save_result(name_data, name_result, name_result, 'instances')
        act_get_filter = get_filter.GetFilter(self.init)
        act_get_info_inst = get_info_instances.GetInfoInstances(self.init, cloud='src_cloud')
        init_iteration_instance = self.init_iteration_instance(name_data, name_backup, name_iter)
        is_instances = is_end_iter.IsEndIter(self.init)
        rename_info_iter = rename_info.RenameInfo(self.init, name_result, name_data)
        get_next_instance = get_info_iter.GetInfoIter(self.init)
        trans_one_inst = self.trans_one_inst()
        transport_instances_and_dependency_resources = \
            act_get_filter >> \
            act_get_info_inst >> \
            init_iteration_instance >> \
            get_next_instance >> \
            trans_one_inst >> \
            save_result >> \
            (is_instances | get_next_instance) >>\
            rename_info_iter
        return transport_instances_and_dependency_resources

    def trans_one_inst(self):
        act_stop_vms = stop_vm.StopVms(self.init, cloud='src_cloud')
        act_trans_volumes = transport_volumes.TransportVolumes(self.init, 'src_cloud')

        act_root_transport_data = task_transfer.TaskTransfer(self.init,
                                                             'SSHFileToFile',
                                                             input_info='info',
                                                             resource_name=utl.INSTANCES_TYPE,
                                                             resource_root_name=utl.DIFF_BODY)
        act_vol_transport_data = task_transfer.TaskTransfer(self.init,
                                                            'SSHFileToFile',
                                                            input_info='info_volumes',
                                                            resource_name=utl.VOLUMES_TYPE,
                                                            resource_root_name=utl.VOLUME_BODY)
        act_prepare_data_volumes = prepare_data_volumes.PrepareDataVolumes(self.init, 'src_cloud')
        act_merge_root = merge_root.MergeRoot(self.init, 'src_cloud')
        create_flavor_act = create_flavor.CreateFlavor(self.init, 'src_cloud')
        net = prepare_networks.PrepareNetworks(self.init, 'dst_cloud')
        act_upload_file_to_glance = upload_file_to_glance.UploadFileToGlance(self.init, 'dst_cloud')
        act_create_instance = create_instance.CreateInstance(self.init, 'dst_cloud')
        act_attach_volumes = attach_used_volumes_via_compute.AttachVolumesCompute(self.init, 'dst_cloud')
        return act_stop_vms >> create_flavor_act >> \
               act_merge_root >> act_root_transport_data >> act_upload_file_to_glance >>\
               act_prepare_data_volumes >> act_vol_transport_data >>\
               act_trans_volumes >> net >> act_create_instance >> act_attach_volumes

    def init_iteration_instance(self, data, name_backup, name_iter):
        init_iteration_instance = copy_var.CopyVar(self.init, data, name_backup, True) >>\
                                  create_reference.CreateReference(self.init, data, name_iter)
        return init_iteration_instance

    def save_result(self, data1, data2, result, resources_name):
        return merge.Merge(self.init, data1, data2, result, resources_name)

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


class TransportInstances(action.Action):
    def __init__(self, init, cloud=None):
        super(TransportInstances, self).__init__(init, cloud)

    def run(self, **kwargs):
        search_opts = kwargs.get('search_opts', {})
        compute_resource_src = self.src_cloud.resources[utl.COMPUTE_RESOURCE]
        compute_resource_dst = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]
        storage_resource_dst = self.dst_cloud.resources[utl.STORAGE_RESOURCE]
        cfg_cloud_src = compute_resource_src.config.cloud
        cfg_cloud_dst = compute_resource_dst.config.cloud
        cmd_glance = ("glance --os-username=%s --os-password=%s --os-tenant-name=%s " +
                           "--os-auth-url=%s " +
                           "image-create --name %s --disk-format=%s --container-format=bare --file %s| " +
                           "grep id")
        temp = cfg_cloud_src.temp
        #get info instances
        info = compute_resource_src.read_info(search_opts=search_opts)

        #Create LOOP
        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']
            compute_resource_src.stop_vm(id_inst)
            compute_resource_src.wait_for_status(id_inst, "stopped")
            # Task Create Flavor
            dest_flavors = {flavor.name: flavor.id for flavor in
                            compute_resource_dst.get_flavor_list(is_public=None)}
            if data['flavors'][0]['name'] not in dest_flavors:
                data['flavor'] = compute_resource_dst.create_flavor(**data['flavors'][0]).id
            else:
                data['flavor'] = dest_flavors[data['flavors'][0]['name']]
            #merge diff and base
            base = "%s/%s" % (temp,
                              'base')
            diff = "%s/%s" % (temp,
                              'diff')
            #Create Condition
            if data['is_template']:
                cmd_cp = "cp %s/%s %s"
                cmd_rebase = "cd %s && qemu-img rebase -u -b base diff"
                cmd_commit = "cd %s && qemu-img commit diff"
                cmd_cp_base = cmd_cp % ('/mnt/usr/export/primary',
                                        data['templateid'],
                                        base)
                cmd_cp_diff = cmd_cp % ('/mnt/usr/export/primary',
                                        data['templateid'],
                                        diff)
                qemu_img_rebase = cmd_rebase % temp
                qemu_img_commit = cmd_commit % temp
                with settings(host_string=cfg_cloud_src.host):
                    #CP BASE
                    run(cmd_cp_base)
                    #CP DIFF
                    run(cmd_cp_diff)
                    #REBASE
                    run(qemu_img_rebase)
                    #MERGE
                    run(qemu_img_commit)
                inst['diff']['path_src'] = base
            #Prepare Trans Diff
            inst['diff']['path_dst'] = "%s/%s" % (cfg_cloud_dst.temp, 'diff')
            inst['diff']['host_dst'] = cfg_cloud_dst.host
            #trans between hosts
            drv = ssh_file_to_file.SSHFileToFile(self.src_cloud, self.dst_cloud, self.cfg)
            drv.transfer_direct(inst['diff'])
            #create image from file
            with settings(host_string=cfg_cloud_dst.host):
                out = run(cmd_glance %
                          (cfg_cloud_dst.user,
                           cfg_cloud_dst.password,
                           cfg_cloud_dst.tenant,
                           cfg_cloud_dst.auth_url,
                           data['name']+'_img',
                           'qcow2',
                           "%s/%s" % (cfg_cloud_dst.temp, 'diff')))
                image_id = out.split("|")[2].replace(' ', '')
                data['image'] = image_id
            #trans volumes (CREATE LOOP)
            for i, disk in enumerate(data['disks']):
                #NOTE: Need add it is struct in INSTANCES INFO
                data_trans = {
                    'host_src': cfg_cloud_src.host,
                    'path_src': "%s/%s" % (compute_resource_src.PATH_STORAGE, disk['id']),
                    'host_dst': cfg_cloud_dst.host,
                    'path_dst': "%s/%s" % (cfg_cloud_dst.temp, "vol")
                }
                #Trans
                drv.transfer_direct(data_trans)
                #Create image from file
                with settings(host_string=cfg_cloud_dst.host):
                    out = run(cmd_glance %
                              (cfg_cloud_dst.user,
                               cfg_cloud_dst.password,
                               cfg_cloud_dst.tenant,
                               cfg_cloud_dst.auth_url,
                               data['name']+'_vol',
                               'qcow2',
                               "%s/%s" % (cfg_cloud_dst.temp, "vol")))
                    image_id = out.split("|")[2].replace(' ', '')
                    data_trans['image'] = image_id
                #Deploy Volume
                info = {
                    'size': disk["size"]/(1024*1024*1024),
                    'display_name': disk["name"],
                    'display_description': disk["name"],
                    'volume_type': None,
                    'imageRef': data_trans['image']
                }
                volume = storage_resource_dst.create_volume(**info)
                inst['volumes'].append({'id': volume.id, 'device': "/dev/vd"+chr(ord("b")+i)})
                storage_resource_dst.wait_for_status(volume.id, AVAILABLE)
            #create port
            init = {
                'src_cloud': self.src_cloud,
                'dst_cloud': self.dst_cloud,
                'cfg': self.cfg
            }
            net = prepare_networks.PrepareNetworks(init, 'dst_cloud')
            info_net = {
                'instances': {
                    id_inst: inst
                }
            }
            nics = net.run(info=info_net)['info']['instances'][id_inst]['instance']['nics']
            data['nics'] = nics
            #create instance
            data['id'] = compute_resource_dst.create_instance(**{'name': data['name'],
                                                                 'flavor': data['flavor'],
                                                                 'key_name': data['key_name'],
                                                                 'nics': data['nics'],
                                                                 'image': data['image']})
            compute_resource_dst.wait_for_status(data['id'], 'active')
            #Attachment volume to instance
            for disk in inst['volumes']:
                compute_resource_dst.attach_volume_to_instance(inst, {'volume': disk})
                storage_resource_dst.wait_for_status(disk['id'],
                                                     'in-use')
        return {
            'info': info
        }

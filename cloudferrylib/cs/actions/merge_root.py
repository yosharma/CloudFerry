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


class MergeRoot(action.Action):
    def __init__(self, init, cloud=None):
        super(MergeRoot, self).__init__(init, cloud)

    def run(self, info=None, **kwargs):
        # search_opts = kwargs.get('search_opts', {})
        compute_resource_src = self.src_cloud.resources[utl.COMPUTE_RESOURCE]
        compute_resource_dst = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]
        cfg_cloud_src = compute_resource_src.config.cloud
        cfg_cloud_dst = compute_resource_dst.config.cloud
        temp = cfg_cloud_src.temp

        #Create LOOP
        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']
            base = "%s/%s" % (temp,
                              'base')
            diff = "%s/%s" % (temp,
                              'diff')
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

        return {
            'info': info
        }

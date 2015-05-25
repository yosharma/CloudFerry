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


class UploadFileToGlance(action.Action):
    def __init__(self, init, cloud=None):
        super(UploadFileToGlance, self).__init__(init, cloud)

    def run(self, info=None, **kwargs):
        # search_opts = kwargs.get('search_opts', {})
        compute_resource_dst = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]
        cfg_cloud_dst = compute_resource_dst.config.cloud
        cmd_glance = ("glance --os-username=%s --os-password=%s --os-tenant-name=%s " +
                           "--os-auth-url=%s " +
                           "image-create --name %s --disk-format=%s --container-format=bare --file %s| " +
                           "grep id")
        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']

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

        return {
            'info': info
        }

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

from fabric.api import local
import json


class ClientCloudStack(object):
    MODE_DISPLAY = 'json'
    SRC_CLI = "/usr/local/bin/cloudmonkey"
    SET_CONFIG = [
        'url',
        'username',
        'password',
        'secretkey',
        'apikey',
        'display'
    ]

    def __init__(self,
                 url,
                 username,
                 password="",
                 secretkey="",
                 apikey=""):
        self.url = url
        self.username = username
        self.password = password
        self.secretkey = secretkey
        self.apikey = apikey
        self.display = self.MODE_DISPLAY
        self.set_configs()

    def set_configs(self):
        for i in self.SET_CONFIG:
            self.set_cmd("%s %s" % (i, getattr(self, i)))

    def set_cmd(self, opt):
        return self.run_cmd("set %s" % opt)

    def clean_trash(self, res):
        if res:
            index = res.find("{")
            return res[index:]
        return res

    def build_api_cmd(self, cmd, opts={}):
        opts_str = ""
        for k, v in opts.iteritems():
            opts_str += "%s=\"%s\" " % (k, v)
        api_cmd = "api %s %s" % (cmd, opts_str)
        res = self.run_cmd(api_cmd)
        res = self.clean_trash(res)
        return json.loads(res if res else "{}")

    def run_cmd(self, cmd):
        return self.__run_local_ssh_cmd("%s %s" % (self.SRC_CLI, cmd))

    def processing_result(self, res, arg):
        return res[arg] if arg in res else res

    def __run_local_ssh_cmd(self, cmd):
        s = local("%s >&1" % cmd, capture=True)
        return s

    def get_list_zones(self, **kwargs):
        cmd = 'listZones'
        select_field = 'zone'
        opts = {}
        opts.update(kwargs if kwargs else {})
        result = self.build_api_cmd(cmd, opts)
        return self.processing_result(result, select_field)

    def get_instances(self, **kwargs):
        cmd = "listVirtualMachines"
        select_field = 'virtualmachine'
        opts = {}
        opts.update(kwargs if kwargs else {})
        result = self.build_api_cmd(cmd, opts)
        return self.processing_result(result, select_field)

    def get_disk_offering(self, **kwargs):
        cmd = "listDiskOfferings"
        select_field = 'diskoffering'
        opts = {}
        opts.update(kwargs if kwargs else {})
        result = self.build_api_cmd(cmd, opts)
        return self.processing_result(result, select_field)

    def get_service_offering(self, **kwargs):
        cmd = "listServiceOfferings"
        select_field = 'serviceoffering'
        opts = {}
        opts.update(kwargs if kwargs else {})
        result = self.build_api_cmd(cmd, opts)
        return self.processing_result(result, select_field)

    def get_os_types(self, **kwargs):
        cmd = "listOsTypes"
        select_field = 'ostype'
        opts = {}
        opts.update(kwargs if kwargs else {})
        result = self.build_api_cmd(cmd, opts)
        return self.processing_result(result, select_field)

    def get_volumes(self, **kwargs):
        cmd = "listVolumes"
        select_field = 'volume'
        opts = {}
        opts.update(kwargs if kwargs else {})
        result = self.build_api_cmd(cmd, opts)
        return self.processing_result(result, select_field)

    def get_templates(self, **kwargs):
        cmd = "listTemplates"
        select_field = 'template'
        opts = {}
        opts.update(kwargs if kwargs else {})
        result = self.build_api_cmd(cmd, opts)
        return self.processing_result(result, select_field)

    def stop_vm(self, **kwargs):
        cmd = "stopVirtualMachine"
        select_field = ''
        opts = {}
        opts.update(kwargs if kwargs else {})
        result = self.build_api_cmd(cmd, opts)
        return self.processing_result(result, select_field)








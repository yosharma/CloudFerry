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

    def build_api_cmd(self, cmd, opts={}):
        opts_str = ""
        for k, v in opts.iteritems():
            opts_str += "%s %s " % (k, v)
        api_cmd = "api %s \"%s\"" % (cmd, opts_str)
        return json.loads(self.run_cmd(api_cmd))

    def run_cmd(self, cmd):
        return self.__run_local_ssh_cmd("%s %s" % (self.SRC_CLI, cmd))

    def __run_local_ssh_cmd(self, cmd):
        s = local("%s >&1" % cmd, capture=True)
        return s

    def get_list_zones(self, **kwargs):
        cmd = 'listZones'
        select_field = 'zone'
        opts = {}
        opts.update(kwargs)
        return self.build_api_cmd(cmd, opts)[select_field]

    def get_instances(self, **kwargs):
        cmd = "listVirtualMachines"
        select_field = 'zone'
        opts = {}
        opts.update(kwargs)
        return self.build_api_cmd(cmd, opts)[select_field]









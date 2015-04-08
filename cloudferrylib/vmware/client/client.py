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

__author__ = 'mirrorcoder'
import urllib2
import base64
from cloudferrylib.vmware.client.parser import ParserVSphere
from cloudferrylib.utils.ssh_util import SshUtil

SIZE_CHUNK = 1024*1024


class ClientDatastore:
    def __init__(self, user, password, tenant, auth_url, parser=ParserVSphere()):
        self.user = user
        self.password = password
        self.tenant = tenant
        self.auth_url = auth_url
        self.parser = parser
        self.ssh = SshUtil(None, None, "localhost")

    def get_data(self, url): #return file-like object
        request = urllib2.Request(urllib2.quote(url, ":/&=?"))
        base64string = base64.encodestring('%s:%s' % (self.user, self.password)).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string)
        result = urllib2.urlopen(request)
        return result

    def get_datacenters(self): #https://172.16.40.37/folder
        data = self.get_data("%s/folder" % self.auth_url).read()
        return self.parser.parse(data)

    def get_datastores(self, dc): #https://172.16.40.37/folder?dcPath=test
        dc = urllib2.quote(dc)
        data = self.get_data("%s/folder?dcPath=%s" % (self.auth_url, dc)).read()
        return self.parser.parse(data)

    def get_vms(self, dc, ds): #https://172.16.40.37/folder?dcPath=test&dsName=datastore1
        data = self.get_data("%s/folder?dcPath=%s&dsName=%s" % (self.auth_url, dc, ds)).read()
        return self.parser.parse(data)

    def get_files_vm(self, dc, ds, vm): #https://172.16.40.37/folder/New%20Virtual%20Machine?dcPath=test&dsName=datastore1
        data = self.get_data("%s/folder/%s?dcPath=%s&dsName=%s" % (self.auth_url, vm, dc, ds)).read()
        return self.parser.parse(data)

    def download(self, dc, ds, file_obj, vm="", output=""):
        if vm:
            data = self.get_data("%s/folder/%s/%s?dcPath=%s&dsName=%s" % (self.auth_url, vm, file_obj, dc, ds))
        else:
            data = self.get_data("%s/folder/%s?dcPath=%s&dsName=%s" % (self.auth_url, file_obj, dc, ds))
        if output:
            with file(output, "wb+") as f:
                d = data.read(SIZE_CHUNK)
                while d:
                    f.write(d)
                    d = data.read(SIZE_CHUNK)
        else:
            return data.read()

    def download_to_host(self, user, host, dc, ds, file_obj, vm="", output=""):
        if vm:
            url = "%s/folder/%s/%s?dcPath=%s&dsName=%s" % (self.auth_url, vm, file_obj, dc, ds)
        else:
            url = "%s/folder/%s?dcPath=%s&dsName=%s" % (self.auth_url, file_obj, dc, ds)
        cmd = 'curl -v -k -H "Expect:" -u \'%s:%s\' -o %s "%s"' % (self.user, self.password, output, url)
        self.ssh.execute(cmd, host_exec=host, user=user)

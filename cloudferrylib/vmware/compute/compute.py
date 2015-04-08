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

# displayName = "ubuntu1"
# memSize = "1024"
# ----------- Split in separate category 'disk' -------------
# ethernet0.virtualDev = "vmxnet3"
# ethernet0.networkName = "VM Network"
# ethernet0.addressType = "vpx"
# ethernet0.generatedAddress = "00:50:56:8d:1e:c9"

# guestOS = "ubuntu-64"
#scsi0:0.deviceType = "scsi-hardDisk"
#scsi0:0.fileName = "CentOS.vmdk"
#scsi0:0.present = "TRUE"
# sched.swap.derivedName = "/vmfs/volumes/5510090f-229cfc1c-532e-002590a25198/ubuntu1/ubuntu1-2ef6e383.vswp"
# if numvcpus = 1 then options `numvcpus` is missing
#numvcpus = 2
__author__ = 'mirrorcoder'
from cloudferrylib.utils.ssh_util import SshUtil
from cloudferrylib.vmware.client import client


class ComputeVMWare:
    def __init__(self, config, cloud):
        self.config = config
        self.cloud = cloud
        self.client = client.ClientDatastore("Administrator@vsphere.local", "Pa$$w0rd", None, "https://172.16.40.37")
        self.ssh = SshUtil(None, None, "localhost")

    def parse_cfg(self, data):
        res = {}
        for i in data.split("\n"):
            if i:
                key, value = i.split(" = ")
                res[key] = value
        return res

    def download_disk(self, user, host, dc, ds, file_obj, vm="", output=""):
        return self.client.download_to_host(user, host, dc, ds, file_obj, vm, output)

    def convert_flat_disk(self, user, host, src_path, dst_path, format_disk='qcow2'):
        cmd = 'qemu-img convert %s -O %s %s' % (src_path, format_disk, dst_path)
        self.ssh.execute(cmd, host_exec=host, user=user)

    def get_info_instance(self, dcPath, dsName, vmName):
        return self.parse_cfg(self.client.download(dcPath, dsName, "%s.vmx" % vmName, vmName))

    def get(self, dcPath, dsName, vmName):
        data = self.get_info_instance(dcPath, dsName, vmName)
        swap_file = data['sched.swap.derivedName'].split('/')[-1].replace("\"", "")
        disk_file = data['scsi0:0.fileName'].replace("\"", "")
        disk_file_flat = "%s-flat.vmdk" % disk_file.split(".")[0]
        list_files = self.client.get_files_vm(dcPath, dsName, vmName)
        size_flat = 0
        size_swap = 0
        for f in list_files:
            if f['Name'] == disk_file_flat:
                size_flat = int(f['Size']) / (1024*1024*1024)
            if f['Name'] == swap_file:
                size_swap = int(f['Size']) / (1024*1024*1024)
        res = {
            'instances': [{
                'instance': {
                    'dcPath': dcPath,
                    'dsName': dsName,
                    'vmName': vmName,
                    'diskFile': [disk_file_flat],
                    'name': data['displayName'].replace("\"", ''),
                    'guestOS': data['guestOS'].replace("\"", ''),
                    'network': [{
                        'mac': data['ethernet0.generatedAddress'].replace("\"", ''),
                        'ip': None
                    }],
                    'nics': [],
                    'key_name': "qwerty",
                    'flavor': None,
                    'image': None,
                    'boot_mode': 'image',
                    'flavors': [{
                        'name': "%s_flavor" % vmName.replace("\"", ''),
                        'ram': int(data['memSize'].replace("\"", '')),
                        'vcpus': int(data['numvcpus'].replace("\"", '')) if 'numvcpus' in data else 1,
                        'disk': size_flat,
                        'swap': int(data['memSize'].replace("\"", ''))/1024,
                        'ephemeral': 0,
                        'rxtx_factor': 1.0,
                        'is_public': True

                    }]
                }
            }]
        }
        return res
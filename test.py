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

from cloudferrylib.vmware.client import client
from cloudferrylib.vmware.compute import compute
c = client.ClientDatastore("Administrator@vsphere.local", "Pa$$w0rd", None, "https://172.16.40.37")
computeVMWare = compute.ComputeVMWare(c)
print "DATACENTERS ------------"
for i in c.get_datacenters():
    print i
print "DATASTORES (DC: test)------------"
for i in c.get_datastores("test"):
    print i
print "VMS(DC: test, DS: datastore1) ------------"
for i in c.get_vms("test", "datastore1"):
    print i
print "FILES(DC: test, DS: datastore1, VM: CentOS) ------------"
for i in c.get_files_vm("test", "datastore1", "CentOS"):
    print i
data = computeVMWare.get("test", "datastore1", "CentOS")['instances'][0]['instance']
c.download_to_host('root',
                   '172.18.172.77',
                   data['dcPath'],
                   data['dsName'],
                   data['diskFile'],
                   data['vmName'],
                   data['diskFile'])
#qemu-img convert CentOS-flat.vmdk -O qcow2 vm.img
computeVMWare.convert_flat_disk('root',
                                '172.18.172.77',
                                data['diskFile'],
                                "%s.img" % data['diskFile'])
#glance image-create --name CentOS --disk-format qcow2 --container-format bare --is-public True --file vm.img
#create-ports
#nova instance-create


#
# DATACENTERS ------------
# {'Path': 'test'}
# DATASTORES (DC: test)------------
# {'Capacity': '492042190848', 'Name': 'datastore1', 'Free': '329009594368'}
# VMS(DC: test, DS: datastore1) ------------
# {'Last modified': u'\xa0', 'Name': 'Parent Datacenter', 'Size': '  - '}
# {'Last modified': '06-Apr-2015 15:26', 'Name': 'CentOS/', 'Size': '  - '}
# {'Last modified': '06-Apr-2015 11:52', 'Name': 'CentOS-6.4-x86_64-minimal.iso', 'Size': '358959104'}
# {'Last modified': '24-Mar-2015 15:57', 'Name': 'New Virtual Machine/', 'Size': '  - '}
# {'Last modified': '23-Mar-2015 18:23', 'Name': 'SW_DVD5_Windows_Svr_DC_EE_SE_Web_2008_R2_64Bit_English_w_SP1_MLF_X17-22580.ISO', 'Size': '3166720000'}
# {'Last modified': '03-Apr-2015 18:38', 'Name': 'achtung/', 'Size': '  - '}
# {'Last modified': '06-Apr-2015 15:07', 'Name': 'ubuntu1/', 'Size': '  - '}
# FILES(DC: test, DS: datastore1, VM: CentOS) ------------
# {'Last modified': u'\xa0', 'Name': 'Parent Directory', 'Size': '  - '}
# {'Last modified': '06-Apr-2015 15:24', 'Name': 'CentOS-56af591b.vswp', 'Size': '2147483648'}
# {'Last modified': '08-Apr-2015 14:27', 'Name': 'CentOS-flat.vmdk', 'Size': '42949672960'}
# {'Last modified': '06-Apr-2015 15:25', 'Name': 'CentOS.nvram', 'Size': '8684'}
# {'Last modified': '06-Apr-2015 15:26', 'Name': 'CentOS.vmdk', 'Size': '467'}
# {'Last modified': '06-Apr-2015 15:22', 'Name': 'CentOS.vmsd', 'Size': '0'}
# {'Last modified': '06-Apr-2015 15:24', 'Name': 'CentOS.vmx', 'Size': '2857'}
# {'Last modified': '06-Apr-2015 15:24', 'Name': 'CentOS.vmx.lck', 'Size': '0'}
# {'Last modified': '06-Apr-2015 15:22', 'Name': 'CentOS.vmxf', 'Size': '261'}
# {'Last modified': '06-Apr-2015 15:24', 'Name': 'CentOS.vmx~', 'Size': '2857'}
# {'Last modified': '06-Apr-2015 15:24', 'Name': 'vmware-1.log', 'Size': '114049'}
# {'Last modified': '06-Apr-2015 15:43', 'Name': 'vmware.log', 'Size': '149408'}
# {'Last modified': '06-Apr-2015 15:24', 'Name': 'vmx-CentOS-1454332187-1.vswp', 'Size': '135266304'}

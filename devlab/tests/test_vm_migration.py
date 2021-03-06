import unittest
import json
import functional_test
import config


class VmMigration(functional_test.FunctionalTest):

    def setUp(self):
        src_vms = self.filter_vms()
        if not src_vms:
            self.skipTest("Nothing to migrate - source vm list is empty")
        self.dst_vms = self.dst_cloud.novaclient.servers.list(
            search_opts={'all_tenants': 1})
        if not self.dst_vms:
            self.fail("No VM's on destination. Either Migration was not "
                      "successful for resource 'VM' or it was not initiated")
        src_vms = [vm for vm in src_vms if vm.status != 'ERROR' and
                   self.tenant_exists(self.src_cloud.keystoneclient,
                                      vm.tenant_id)]
        self.dst_vm_indexes = []
        for vm in src_vms:
            if vm.name not in config.vms_not_in_filter:
                self.dst_vm_indexes.append(
                    [x.name for x in self.dst_vms].index(vm.name))
        with open('pre_migration_vm_states.json') as data_file:
            self.before_migr_states = json.load(data_file)
        self.filter_vms = self.filtering_utils.filter_vms(src_vms)

    def test_vms_not_in_filter_stay_active_on_src(self):
        original_states = self.before_migr_states
        for vm in config.vms_not_in_filter:
            vm_list = [x for x in self.src_cloud.novaclient.servers.list(
                search_opts={'all_tenants': 1}) if x.name == vm]
            for filtered_vm in vm_list:
                self.assertTrue(
                    filtered_vm.status == original_states[filtered_vm.name],
                    msg="Vm %s has wrong state" % filtered_vm.name)

    def test_vm_not_in_filter_did_not_migrate(self):
        dst_vms = [x.name for x in self.dst_cloud.novaclient.servers.list(
                   search_opts={'all_tenants': 1})]
        for vm in config.vms_not_in_filter:
            self.assertTrue(vm not in dst_vms,
                            'VM migrated despite that it was not included in '
                            'filter, VM info: \n{}'.format(vm))

    def test_cold_migrate_vm_state(self):
        original_states = self.before_migr_states
        for vm_name in original_states.keys():
            if vm_name in config.vms_not_in_filter:
                original_states.pop(vm_name)
        src_vms = self.filter_vms[0]
        for src_vm, vm_index in zip(src_vms, self.dst_vm_indexes):
            if src_vm.name in original_states.keys():
                if original_states[src_vm.name] == 'ACTIVE' or \
                        original_states[src_vm.name] == 'VERIFY_RESIZE':
                    self.assertTrue(
                        src_vm.status == 'SHUTOFF' and
                        self.dst_vms[vm_index].status == 'ACTIVE')
                else:
                    self.assertTrue(
                        src_vm.status == 'SHUTOFF' and
                        self.dst_vms[vm_index].status == 'SHUTOFF')
            else:
                self.assertTrue(src_vm.status == 'SHUTOFF' and
                                self.dst_vms[vm_index].status == 'ACTIVE')

    def test_cold_migrate_vm_ip(self):
        src_vms = self.filter_vms[0]
        for src_vm, vm_index in zip(src_vms, self.dst_vm_indexes):
            for src_net in src_vm.addresses:
                for src_net_addr, dst_net_addr in zip(src_vm.addresses
                                                      [src_net],
                                                      self.dst_vms[vm_index]
                                                      .addresses[src_net]):
                    self.assertTrue(src_net_addr['addr'] ==
                                    dst_net_addr['addr'])

    def test_cold_migrate_vm_security_groups(self):
        src_vms = self.filter_vms[0]
        for src_vm, vm_index in zip(src_vms, self.dst_vm_indexes):
            dst_sec_group_names = [x['name'] for x in
                                   self.dst_vms[vm_index].security_groups]
            for security_group in src_vm.security_groups:
                self.assertTrue(security_group['name'] in dst_sec_group_names)

    @unittest.skip("Temporarily disabled: image's id changes after migrating")
    def test_cold_migrate_vm_image_id(self):
        src_vms = self.filter_vms[0]
        for src_vm, vm_index in zip(src_vms, self.dst_vm_indexes):
            self.assertTrue(src_vm.image.id ==
                            self.dst_vms[vm_index].image.id)

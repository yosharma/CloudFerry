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
# See the License for the specific language governing permissions and
# limitations under the License.

import pika

from cloudferrylib.cs.client import client

from cloudferrylib.base import identity
from cloudferrylib.utils import utils as utl


LOG = utl.get_log(__name__)


class Identity(identity.Identity):

    def __init__(self, config, cloud):
        super(Identity, self).__init__()
        self.config = config
        self.cloud = cloud
        self.client = self.proxy(self.get_client(), config)
        self.keystone_client = self.client

    def get_client(self, params=None):
        """Getting nova client. """

        params = self.config if not params else params

        return client.ClientCloudStack(params.cloud.auth_url,
                                       params.cloud.user,
                                       params.cloud.password,
                                       params.cloud.secretkey,
                                       params.cloud.apikey,)

    def read_info(self, **kwargs):
        """"""
        users = self.client.get_users()
        domains = self.client.get_domains()
        accounts = self.client.get_accounts()
        projects = self.client.get_projects()

        info = {'tenants': self.get_tenants(projects),
                'users': self.get_users(users),
                'roles': self.get_roles(accounts),
                'user_passwords': [],
                'user_tenants_roles': self.get_user_tenants(users, projects)}

        info['user_tenants_roles'].update(
            self.get_user_tenant_roles(domains,
                                       projects,
                                       accounts,
                                       users,
                                       info['user_tenants_roles']))
        return info

    def get_user_tenants(self, users, projects):
        roles = {}
        for user in users:
            user_name = self.client.get_user_name(user)
            for project in projects:
                tenant_name = self.client.get_tenant_name(project)
                roles.setdefault(user_name, {})
                roles[user_name].setdefault(tenant_name, [])
        return roles

    def get_domains_admins(self, domains, users):
        domain_admins = {}
        for domain in domains:
            domain_name = domain['name']
            domain_admins[domain_name] = []
            for parent in domain['path'].split('/'):
                for user in users:
                    if user['accounttype'] and user['domain'] == parent:
                        domain_admins[domain_name].append(user)
        return domain_admins

    def get_user_roles(self, user, roles, uname, tname):
        account = self.client.get_accounts(id=user['accountid'])[0]
        urole = self.convert(user, 'user_role', self.config, self.client)
        arole = self.convert(account, 'account_role', self.config, self.client)

        roles_new = []

        roles_cur = [r.values()[1:][0]['name'] for r in roles[uname][tname]]
        if arole['role']['name'] not in roles_cur:
            roles_new.append(arole)
        if urole['role']['name'] not in roles_cur:
            if urole['role']['name'] != arole['role']['name']:
                roles_new.append(urole)

        return roles_new

    def get_user_tenant_roles(self, domains, project, accounts, users, roles):
        domains_admins = self.get_domains_admins(domains, users)
        roles_new = roles

        for domain in domains:
            for project in self.client.get_projects(domainid=domain['id']):
                tenant_name = self.client.get_tenant_name(project)

                for account in self.client.get_projectaccounts(project['id']):
                    for user in account['user']:
                        user_name = self.client.get_user_name(user)
                        user_roles = self.get_user_roles(
                            user, roles_new, user_name, tenant_name)
                        roles[user_name][tenant_name].extend(user_roles)

                for user in domains_admins[project['domain']]:
                        user_name = self.client.get_user_name(user)
                        user_roles = self.get_user_roles(
                            user, roles_new, user_name, tenant_name)
                        roles[user_name][tenant_name].extend(user_roles)
        return roles

    def get_tenants(self, projects):
        tenants = []
        for project in projects:
            tenants.append(
                self.convert(project, 'tenant', self.config, self.client))
        return tenants

    def get_roles(self, accounts):
        roles = []
        for acc in accounts:
            roles.append(
                self.convert(acc, 'account_role', self.config, self.client))
        return roles

    def get_users(self, users):
        users_new = []
        for user in users:
            users_new.append(
                self.convert(user, 'user', self.config, self.client))
        return users_new

    @staticmethod
    def convert(cs_object, obj_name, config=None, client=None):
        """Convert CloudStack Identity info to CloudFerry identity info"""
        obj_map = {'user': Identity.convert_user,
                   'tenant': Identity.convert_tenant,
                   'account_role': Identity.convert_account_role,
                   'user_role': Identity.convert_user_role}

        return obj_map[obj_name](cs_object, config, client)

    @staticmethod
    def convert_user(user, config, client):
        """Convert CloudStack user info to CloudFerry user info"""
        return {'user':
                {'name': client.get_user_name(user),
                    #migrate hungs on _send_msg
                    #'email': user.get('email'),
                    'email': "",
                    'id': user['id'],
                    'tenantId': None},
                'meta': {
                    'overwrite_password':
                    config.migrate.overwrite_user_passwords}}

    @staticmethod
    def convert_tenant(project, config, client):
        """Convert CloudStack project info to CloudFerry tenant info"""
        return {'tenant':
                {'name': client.get_tenant_name(project),
                    'id': project['id'],
                    'description': project['displaytext']},
                'meta': {}}

    @staticmethod
    def convert_account_role(account, config, client):
        """Convert CloudStack user account info to CloudFerry role"""
        aid = account['accountid'] if account.get('role') else account['id']
        return {'role':
                {'name': client.get_account_name(account),
                    'id': aid},
                'meta': {}}

    @staticmethod
    def convert_user_role(account, config, client):
        """Convert CloudStack user role info to CloudFerry role"""
        if not account['accounttype']:
            role = {'role': {'name': u"_member_"}, 'meta': {}}
        else:
            role = {'role': {'name': u"admin"}, 'meta': {}}
        return role

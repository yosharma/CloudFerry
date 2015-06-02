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


import copy
import json
import time

from fabric.api import run
from fabric.api import settings

from cloudferrylib.cs.client import client

from cloudferrylib.base import image
from cloudferrylib.utils import file_like_proxy
from cloudferrylib.utils import utils as utl
import urllib
import cStringIO


LOG = utl.get_log(__name__)
IMAGE = 'image'
TEMPLATE = 'template'


class Image(image.Image):
    PATH_STORAGE_SECONDARY = ""
    PATH_STORAGE_PRIMARY = ""

    def __init__(self, config, cloud):
        self.config = config
        self.host = config.cloud.host
        self.cloud = cloud
        # self.identity_client = cloud.resources['identity']
        self.client = self.proxy(self.get_client(), config)
        super(Image, self).__init__(config)

    def get_client(self, params=None):
        """Getting nova client. """

        params = self.config if not params else params

        return client.ClientCloudStack(params.cloud.auth_url,
                                       params.cloud.user,
                                       params.cloud.password,
                                       params.cloud.secretkey,
                                       params.cloud.apikey,)

    def get_image_list(self):
        return self.client.get_listisos()

    def get_template_list(self, templatefilter="all"):
        return self.client.get_list_template(templatefilter=templatefilter)

    def delete_image(self, image_id):
        return self.client.deleteiso(id=image_id)

    def get_image_by_id(self, image_id):
        return self.client.get_listisos(id=image_id)

    def get_template_by_id(self, image_id, templatefilter="all"):
        return self.client.get_list_template(id=image_id, templatefilter=templatefilter)

    def get_image_by_name(self, image_name):
        return self.client.get_listisos(name=image_name)

    def get_template_by_name(self, image_name, templatefilter="all"):
        return self.client.get_list_template(name=image_name, templatefilter=templatefilter)

    def get_img_id_list_by_checksum(self, checksum):
        isos = self.get_image_list()
        return [iso for iso in isos if iso['checksum'] == checksum]

    def get_image(self, im):
        """ Get image by id or name. """
        pass

    def get_image_status(self, image_id):
        return self.get_image_by_id(image_id).status

    def what_id(self, image_id):
        with settings(ok_ret_codes=[0, 1]):
            image = self.get_image_by_id(image_id)
            template = self.get_template_by_id(image_id)
        if image:
            return IMAGE
        if template:
            return TEMPLATE
        return None

    def get_ref_image(self, image_id, mode='HTTP_DOWNLOAD'):
        type_id = self.what_id(image_id)
        if type_id == IMAGE:
            return self._get_ref_image(image_id, mode)
        if type_id == TEMPLATE:
            return self._get_ref_template(image_id, mode)
        return None

    def _get_ref_image(self, image_id, mode='HTTP_DOWNLOAD'):
        class WrapStringIO(object):
            length = None

            def __init__(self, obj):
                self.obj = obj

            def read(self, *args, **kwargs):
                return self.obj.read(*args, **kwargs)

        res = self.client.extract_iso(id=image_id, mode=mode)
        url = res['jobresult']['iso']['url']
        obj = urllib.urlopen(url)
        return WrapStringIO(obj)

    def _get_ref_template(self, image_id, mode='HTTP_DOWNLOAD'):
        class WrapStringIO(object):
            length = None

            def __init__(self, obj):
                self.obj = obj

            def read(self, *args, **kwargs):
                return self.obj.read(*args, **kwargs)

        res = self.client.extract_template(id=image_id, mode=mode)
        url = res['jobresult']['template']['url']
        obj = urllib.urlopen(url)
        return WrapStringIO(obj)

    def get_image_checksum(self, image_id):
        return self.get_image_by_id(image_id).checksum

    @staticmethod
    def convert(img, cloud):
        """Convert OpenStack Glance image object to CloudFerry object.

        :param glance_image:    Direct OS Glance image object to convert,
        :param cloud:           Cloud object.
        """
        g_i_data = img
        resource = cloud.resources[utl.IMAGE_RESOURCE]
        gl_image = {
            'id': img['id'],
            'size': img['size'],
            'name': img['name'],
            'checksum': img['checksum'],
            'container_format': 'bare',
            'disk_format': 'qcow2' if not 'format' in img else img['format'],
            'is_public': img['ispublic'],
            'protected': False,
            'resource': resource,
            'properties': {
                'image_type': 'image'
           }
        }
        g_i_data.update(gl_image)
        return g_i_data

    def read_info(self, **kwargs):
        """Get info about images or specified image.

        :param image_id: Id of specified image
        :param image_name: Name of specified image
        :param images_list: List of specified images
        :param images_list_meta: Tuple of specified images with metadata in
                                 format [(image, meta)]
        :rtype: Dictionary with all necessary images info
        """

        info = {'images': {}}
        if kwargs.get('image_id'):
            glance_image = self.get_image_by_id(kwargs['image_id'])+self.get_template_by_id(kwargs['image_id'])
            info = self.make_image_info(glance_image, info)

        elif kwargs.get('image_name'):
            glance_image = self.get_image_by_name(kwargs['image_name'])+self.get_template_by_name(kwargs['image_name'])
            info = self.make_image_info(glance_image, info)

        elif kwargs.get('images_list'):
            for im in kwargs['images_list']:
                glance_image = self.get_image(im)
                info = self.make_image_info(glance_image, info)

        elif kwargs.get('images_list_meta'):
            for (im, meta) in kwargs['images_list_meta']:
                glance_image = self.get_image(im)
                info = self.make_image_info(glance_image, info)
                info['images'][glance_image.id]['meta'] = meta

        else:
            for glance_image in self.get_image_list()+self.get_template_list():
                info = self.make_image_info(glance_image, info)

        return info

    def make_image_info(self, glance_image, info):
        if glance_image:
            gl_image = self.convert(glance_image, self.cloud)

            info['images'][glance_image['id']] = {'image': gl_image,
                                               'meta': {},
                                               }
        else:
            LOG.error('Image has not been found')

        return info

    def deploy(self, info, callback=None):
        pass

    def wait_for_status(self, id_res, status):
        while self.client.images.get(id_res).status != status:
            time.sleep(1)

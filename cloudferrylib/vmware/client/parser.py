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

from pyquery import PyQuery


class ParserVSphere(object):
    def parse(self, html_data):
        pq = PyQuery(html_data)
        #output: -> [{'name': "temp", 'size': 123}]
        tag = pq('table')
        trs = tag[1].findall("tr")
        heads = []
        data = []
        for th in trs[0].findall("th"):
            heads.append(th.text)
        for tr in trs[1:]:
            tds = tr.findall("td")
            if tds:
                d = {}
                d[heads[0]] = tds[0].find("a").text
                for i in xrange(1, len(heads)):
                    d[heads[i]] = tds[i].text
                data.append(d)
        return data



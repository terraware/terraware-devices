import time
import logging
from xml.etree import ElementTree

try:
    from httplib import HTTPConnection
except ModuleNotFoundError:
    from http.client import HTTPConnection
import gevent

from .base import TerrawareDevice


class RelayDevice(TerrawareDevice):

    def __init__(self, host, port, settings, diagnostic_mode):
        self._host = host
        self._port = port
        self._last_update_time = None
        self._sim_state = 0
        print('created relay device (%s:%d)' % (host, port))

    def reconnect(self):
        pass

    def poll(self):
        self._last_update_time = time.time()
        return {
            'relay-1': self.read_state(),
        }

    def read_state(self):
        if self._host == 'sim':
            xml = self.sample_data()
        else:
            conn = HTTPConnection('%s:%d' % (self._host, self._port))
            conn.request('GET', '/state.xml')
            xml = conn.getresponse().read()
            conn.close()
        tree = ElementTree.fromstring(xml)
        return int(tree.find('relay1state').text)

    def set_state(self, state):
        if self._host == 'sim':
            self._sim_state = state
        else:
            conn = HTTPConnection('%s:%d' % (self._host, self._port))
            conn.request('GET', '/state.xml?relay1state=%d' % state)
            conn.close()

    def sample_data(self):
        return f'''<?xml version='1.0' encoding='utf-8'?>
            <datavalues>
                <relay1state>{self._sim_state}</relay1state>
                <relay2state>0</relay2state>
                <relay3state>0</relay3state>
                <relay4state>0</relay4state>
            </datavalues>'''

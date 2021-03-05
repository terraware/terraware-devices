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

    def __init__(self, controller, server_path, host, port, settings, polling_interval, diagnostic_mode):
        print('initializing device %s (%s:%d)' % (server_path, host, port))
        self._controller = controller
        self._server_path = server_path
        self._host = host
        self._port = port
        self._polling_interval = polling_interval
        self._last_update_time = None
        self._sim_state = 0

    def server_path(self):
        return self._server_path

    def reconnect(self):
        pass

    def run(self):
        logging.info('starting relay monitoring/control for %s; polling interval: %.1fs', self._server_path, self._polling_interval)
        while True:
            print('polling %s now' % self._server_path)
            v = self.read_state()
            seq_rel_path = self._server_path + '/relay-1'
            if False:
                print('    %s: %d' % (seq_rel_path, v))
            self._controller.sequences.update(seq_rel_path, v)
            self._controller.sequences.update_value(seq_rel_path, v)
            self._last_update_time = time.time()
            gevent.sleep(self._polling_interval)

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

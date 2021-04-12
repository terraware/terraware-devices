import time
import socket
import logging
from io import BytesIO
from xml.etree import ElementTree

import gevent

from .base import TerrawareDevice


class RelayDevice(TerrawareDevice):

    def __init__(self, host, port, settings, diagnostic_mode):
        self._host = host
        self._port = port
        self._sim_state = 0
        self.last_update_time = None
        print('created relay device (%s:%d)' % (host, port))

    def reconnect(self):
        pass

    def poll(self):
        self.last_update_time = time.time()
        return {
            'relay-1': self.read_state(),
        }

    def read_state(self):
        if self._host == 'sim':
            xml = self.sample_data()
        else:
            xml = request_data(self._host, self._port, 'GET', '/state.xml').decode()
        tree = ElementTree.fromstring(xml)
        return int(tree.find('relay1state').text)

    def set_state(self, state):
        if self._host == 'sim':
            self._sim_state = state
        else:
            request_data(self._host, self._port, 'GET', '/state.xml?relay1state=%d' % state)

    def sample_data(self):
        return f'''<?xml version='1.0' encoding='utf-8'?>
            <datavalues>
                <relay1state>{self._sim_state}</relay1state>
                <relay2state>0</relay2state>
                <relay3state>0</relay3state>
                <relay4state>0</relay4state>
            </datavalues>'''


# request data via HTTP/1.0 but accept a HTTP/0.9 response
# based on https://stackoverflow.com/questions/27393282/what-is-up-with-python-3-4-and-reading-this-simple-xml-site
def request_data(host, port, action, url):
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((host, port))
    conn.settimeout(1.0)  # this doesn't seem to have an effect
    message = '%s %s HTTP/1.0\r\n\r\n' % (action, url)
    conn.send(message.encode())
    buffer = BytesIO()
    start_time = time.time()
    while time.time() - start_time < 1.0:
        try:
            chunk = conn.recv(4096)
            if chunk:
                buffer.write(chunk)
        except socket.timeout:
            break
    return buffer.getvalue()

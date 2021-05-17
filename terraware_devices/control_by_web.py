import time
import socket
import logging
import requests
from io import BytesIO
from xml.etree import ElementTree
import gevent
from .base import TerrawareDevice


class CBWRelayDevice(TerrawareDevice):

    def __init__(self, host, port, settings, local_sim):
        self._host = host
        self._port = port
        self._sim_state = 0
        self._local_sim = local_sim
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
        if self._local_sim:
            xml = self.sample_data()
        else:
            xml = request_data(self._host, self._port, 'GET', '/state.xml').decode()
        tree = ElementTree.fromstring(xml)
        return int(tree.find('relay1state').text)

    def set_state(self, state):
        if self._local_sim:
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


# e.g. ControlByWeb X-DTHS-WMX
class CBWTemperatureHumidityDevice(TerrawareDevice):

    def __init__(self, settings):
        self.sensor_index = int(settings)
        print('created CBW temperature and humidity sensor')

    def reconnect(self):
        pass

    def poll(self):
        return {}


# e.g. ControlByWeb X-405
class CBWSensorHub():

    def __init__(self, address, polling_interval, local_sim):
        self.address = address
        self.polling_interval = polling_interval
        self.local_sim = local_sim
        self.make = 'ControlByWeb'
        self.devices = []

    def add_device(self, device):
        self.devices.append(device)

    # similar to the device poll method, but each name in the dictionary should include the server path
    def poll(self):
        if self.local_sim == 'sim':
            xml = self.sample_data()
        else:
            response = requests.get(f'http://{self.address}/state.xml')
            xml = response.text
        print(xml)
        tree = ElementTree.fromstring(xml)
#        return int(tree.find('relay1state').text)
        return {}

    def sample_data(self):
        return '''<?xml version="1.0" encoding="utf-8" ?>
            <datavalues>
                <vin>23.3</vin>
                <register1>0</register1>
                <oneWireSensor1>18.6</oneWireSensor1>
                <oneWireSensor2>54.6</oneWireSensor2>
                <oneWireSensor3>18.6</oneWireSensor3>
                <oneWireSensor4>55.1</oneWireSensor4>
                <oneWireSensor5>18.8</oneWireSensor5>
                <oneWireSensor6>54.5</oneWireSensor6>
                <utcTime>25678</utcTime>
                <timezoneOffset>-25200</timezoneOffset>
                <serialNumber>00:0C:C8:05:56:53</serialNumber>
                <downloadSettings>1</downloadSettings>
            </datavalues>
            '''


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

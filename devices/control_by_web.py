import time
import socket
import logging
import requests
from io import BytesIO
from xml.etree import ElementTree
import gevent
from .base import TerrawareDevice, TerrawareHub


class CBWRelayDevice(TerrawareDevice):

    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        self._host = dev_info["address"]
        self._port = dev_info["port"]
        self._sim_state = 0
        print('created relay device (%s:%d)' % (self._host, self._port))

    def get_timeseries_definitions(self):
        return [[self.id, 'relay-1', 'numeric', 2]]

    def reconnect(self):
        pass

    def poll(self):
        return {
            (self.id, 'relay-1'): self.read_state(),
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


class CBWWeatherStationDevice(TerrawareDevice):

    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        self._host = dev_info["address"]
        self._port = dev_info["port"]
        self._sim_state = 0
        self.fields = ['temp', 'humidity', 'windSpd', 'windDir', 'rainTot', 'solarRad', 'barPressure', 'dewPoint']
        print('created CBW weather station device (%s:%d)' % (self._host, self._port))

    def get_timeseries_definitions(self):
        return [[self.id, name, 'numeric', 2] for name in self.fields]

    def reconnect(self):
        pass

    def poll(self):
        if self._local_sim:
            xml = self.sample_data()
        else:
            r = requests.get('http://%s:%d/state.xml' % (self._host, self._port))
            xml = r.text
        tree = ElementTree.fromstring(xml)
        state = {}
        for name in self.fields:
            state[(self.id, name)] = float(tree.find(name).text)
        if self._diagnostic_mode:
            print(state)
        return state

    def sample_data(self):
        return open('sample-cbw-weather.xml').read()


########################################################################################################
#### NOTE BSHARP: BROKEN - THIS WAS UNUSED when I took over the device manager. I'm leaving the code here
#### but it is not included in device_manager, you can't create one of these, and the code has certainly rotten. 
########################################################################################################
# e.g. ControlByWeb X-DTHS-WMX
class CBWTemperatureHumidityDevice(TerrawareDevice):

    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        self.sensor_index = int(dev_info["settings"])
        print('created CBW temperature and humidity sensor')

    def reconnect(self):
        pass

    def poll(self):
        return {}


########################################################################################################
#### NOTE BSHARP: BROKEN - THIS WAS UNUSED when I took over the device manager. I'm leaving the code here
#### but it is not included in device_manager, you can't create one of these, and the code has certainly rotten. 
########################################################################################################
# e.g. ControlByWeb X-405
class CBWSensorHub(TerrawareHub):

    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        self.address = dev_info["address"]

    # This code appears to be unused, since poll never returns anything...
    def get_timeseries_definitions(self):
        return [[]]

    # similar to the device poll method, but each name in the dictionary should include the server path
    def poll(self):
        if self._local_sim:
            xml = self.sample_data()
        else:
            response = requests.get(f'http://{self.address}/state.xml')
            xml = response.text
        print(xml)
        tree = ElementTree.fromstring(xml)
#        return int(tree.find('relay1state').text)
        return {}

    def reconnect(self):
        pass

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

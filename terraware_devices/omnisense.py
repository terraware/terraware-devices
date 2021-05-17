import random
import socket
import socketserver
import gevent
from .base import TerrawareDevice


# for now we assume a single omnisense hub object
hub_instance = None


# a UDP message handler
class SyslogUDPHandler(socketserver.BaseRequestHandler):

    def handle(self):
        data = bytes.decode(self.request[0].strip())  # from https://gist.github.com/marcelom/4218010
        hub_instance.process_data(data)


class OmniSenseHub():

    def __init__(self, polling_interval, local_sim):
        global hub_instance
        hub_instance = self
        self.devices = []
        self.polling_interval = polling_interval
        self.local_sim = local_sim
        self.recent_sensor_data = {}
        self.address = None
        self.make = 'OmniSense'
        gevent.spawn(self.run_syslog_server)
        if self.local_sim:
            gevent.spawn(self.sim)

    def add_device(self, device):
        self.devices.append(device)

    def run_syslog_server(self):
        ip_address = current_ip_address()
        print('launching syslog service listening on %s' % ip_address)
        server = socketserver.UDPServer((ip_address, 514), SyslogUDPHandler)
        server.serve_forever(poll_interval=0.5)

    def process_data(self, data):
        data = str(data)
        # e.g.: <13>May 16 03:39:38 OmniSense sensorReading: 100407E500293303AC000B021900050294B2EE02790000000002785E7F9209
        if 'sensorReading' in data:
            parts = data.split()
            if len(parts) >= 3 and parts[-3] == 'OmniSense' and parts[-2] == 'sensorReading:' and len(parts[-1]) == 62:
                sensor_id, temperature, humidity = parse_message(parts[-1])
                device = self.find_device(sensor_id)
                if device:
                    self.recent_sensor_data[device.server_path + '/temperature'] = temperature
                    self.recent_sensor_data[device.server_path + '/humidity'] = humidity
                else:
                    print('data from unknown omnisense device: %s' % sensor_id)

    def poll(self):
        result = self.recent_sensor_data
        self.recent_sensor_data = {}
        return result

    def sim(self):
        prefix = '<13>May 16 03:39:38 OmniSense sensorReading: '
        while True:
            if random.randint(0, 1):
                self.process_data(prefix + '100407E5002933027B000B021900050294B33C02730000000102A85EC99193')
            else:
                self.process_data(prefix + '100407E500293303AC000B021900050294B2EE02790000000002785E7F9209')
            gevent.sleep(5)

    def find_device(self, sensor_id):
        result = None
        for device in self.devices:
            if device.sensor_id == sensor_id:
                result = device
                break
        return result


class OmniSenseTemperatureHumidityDevice(TerrawareDevice):

    def __init__(self, address):
        self.sensor_id = address
        print('created OmniSenseTemperatureHumidityDevice with id %s' % self.sensor_id)

    # not used; polling is done in hub class
    def poll(self):
        pass

    def reconnect(self):
        pass


# based on https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
def current_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('10.255.255.255', 1))  # does not have to be reachable
    ip = s.getsockname()[0]
    s.close()
    return ip


def parse_message(message):
    assert len(message) == 62
    sensor_id = message[10:18]
    t_raw = int(message[-8:-4], 16)  # convert 4 hex characters to integer
    rh_raw = int(message[-4:], 16)  # convert 4 hex characters to integer
    t_proc = -45 + 175 * (t_raw / 65535)
    rh_proc = 100 * rh_raw / 65535
    return (sensor_id, t_proc, rh_proc)


def test_parse_message():
    sensor_id, temperature, humidity = parse_message('100407E5002933027B000B021900050294B33C02730000000102A85EC99193')
    assert sensor_id == '2933027B'
    print('t: %.2f, rh: %.2f' % (temperature, humidity))
    sensor_id, temperature, humidity = parse_message('100407E500293303AC000B021900050294B2EE02790000000002785E7F9209')
    assert sensor_id == '293303AC'
    print('t: %.2f, rh: %.2f' % (temperature, humidity))

import time
import random
import socket
import socketserver
import gevent
from .base import TerrawareDevice, TerrawareHub


# for now we assume a single omnisense hub object
hub_instance = None


# a UDP message handler
class SyslogUDPHandler(socketserver.BaseRequestHandler):

    def handle(self):
        data = bytes.decode(self.request[0].strip())  # from https://gist.github.com/marcelom/4218010
        hub_instance.process_data(data)


class OmniSenseHub(TerrawareHub):

    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        global hub_instance
        assert hub_instance is None
        hub_instance = self
        self.recent_sensor_data = {}
        self.address = None
        self.unknown_device_log = None
        if self._diagnostic_mode:
            print("running OmniSenseHub in diagnostic mode")

    def notify_all_devices_added(self):
        if self._local_sim:
            gevent.spawn(self.sim)
        else:
            gevent.spawn(self.run_syslog_server)

    def get_timeseries_definitions(self):
        return []

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
                sensor_addr, temperature, humidity = parse_message(parts[-1])
                device = self.find_device(sensor_addr)
                if device:
                    # Note that "sensor_addr" is actually the hardware identifier of the physical sensor from omnisense,
                    # not the unique device ID our server assigned to the device, so we need device.id for the timeseries
                    # key, not sensor_addr. We should clean up all this terminology at some point.
                    self.recent_sensor_data[(device.id, 'temperature')] = temperature
                    self.recent_sensor_data[(device.id, 'humidity'   )] = humidity
                    device.last_update_time = time.time()
                else:
                    print('data from unknown omnisense device: %s' % sensor_addr)
                    if not self.unknown_device_log:
                        self.unknown_device_log = open('omni-devices.txt', 'w')
                    self.unknown_device_log.write('%s\n' % sensor_addr)
                    self.unknown_device_log.flush()

    def poll(self):
        result = self.recent_sensor_data
        self.recent_sensor_data = {}
        return result

    def reconnect(self):
        pass

    def sim(self):
        prefix = '<13>May 16 03:39:38 OmniSense sensorReading: '
        while True:
            if random.randint(0, 1):
                self.process_data(prefix + '100407E5002933027B000B021900050294B33C02730000000102A85EC99193')
            else:
                self.process_data(prefix + '100407E500293303AC000B021900050294B2EE02790000000002785E7F9209')
            gevent.sleep(5)

    def find_device(self, sensor_addr):
        result = None
        for device in self.devices:
            if device.sensor_addr == sensor_addr:
                result = device
                break
        return result


class OmniSenseTemperatureHumidityDevice(TerrawareDevice):

    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        self.sensor_addr = dev_info["address"]
        self.expected_update_interval = 30 * 60
        print('created OmniSenseTemperatureHumidityDevice with id %s' % self.sensor_addr)

    # These actually get returned by the hub object - our poll() does nothing - but that's fine - we can supply
    # the definitions. (It would also be fine if the hub object replied with a list of all of these in its; it's just
    # easier to implement here.)
    def get_timeseries_definitions(self):
        return [[self.id, timeseries_name, 'numeric', 2] for timeseries_name in ['temperature', 'humidity']]

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
    sensor_addr = message[10:18]  # aka sensor ID
    t_raw = int(message[-8:-4], 16)  # convert 4 hex characters to integer
    rh_raw = int(message[-4:], 16)  # convert 4 hex characters to integer
    t_proc = -45 + 175 * (t_raw / 65535)
    rh_proc = 100 * rh_raw / 65535
    return (sensor_addr, t_proc, rh_proc)


def test_parse_message():
    sensor_addr, temperature, humidity = parse_message('100407E5002933027B000B021900050294B33C02730000000102A85EC99193')
    assert sensor_addr == '2933027B'
    print('t: %.2f, rh: %.2f' % (temperature, humidity))
    sensor_addr, temperature, humidity = parse_message('100407E500293303AC000B021900050294B2EE02790000000002785E7F9209')
    assert sensor_addr == '293303AC'
    print('t: %.2f, rh: %.2f' % (temperature, humidity))

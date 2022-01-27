import json
import random
import socket
import gevent
from pysmartweatherudp.utils import getDataSet
from .base import TerrawareDevice


SENSOR_TYPES = [
    'temperature',
    'dewpoint',
#    'feels_like',
#    'heat_index',
#    'wind_chill',
    'wind_speed',
    'wind_bearing',
    'wind_gust',
    'wind_lull',
    'wind_direction',
    'precipitation_rate',
    'humidity',
    'pressure',
    'uv',
    'solar_radiation',
    'illuminance',
    'lightning_count',
    'airbattery',
    'skybattery',
]


test_message = '{"serial_number":"ST-00051516","type":"obs_st","hub_sn":"HB-00041917","obs":[[1638242453,0.00,0.00,0.00,0,3,1016.47,13.19,82.26,0,0.00,0,0.000000,0,0,0,2.745,1]],"firmware_revision":156}'


class TempestWeatherStation(TerrawareDevice):

    def __init__(self, dev_info, local_sim, diagnostic_mode, spec_path):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        if self._diagnostic_mode:
            print("running TempestWeatherStation in diagnostic mode")
        self._state = {}
        if self._local_sim:
            self.update(getDataSet(test_message, 'metric', ignore_errors=True))  # do a quick test
            gevent.spawn(self.sim)
        else:
            UDP_IP = "0.0.0.0"
            UDP_PORT = 50222
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind((UDP_IP, UDP_PORT))
            gevent.spawn(self.run)
            if self._diagnostic_mode:
                print("started weather station UDP receiver")

    def run(self):
        while True:
            data, addr = self.sock.recvfrom(1024)
            data = data.decode()
            data_json = json.loads(data)
            if data_json['type'] == 'obs_st':
                self.update(getDataSet(data, 'metric', ignore_errors=True))

    def update(self, dataset):
        for sensor_type in SENSOR_TYPES:
            if hasattr(dataset, sensor_type):
                self._state[(self.id, sensor_type)] = getattr(dataset, sensor_type)
        if self._diagnostic_mode:
            print("Data received: %s %s %s" % (dataset.type, dataset.timestamp, dataset.temperature))

    def get_timeseries_definitions(self):
        return [[self.id, a, 'numeric', 2] for a in SENSOR_TYPES]

    def poll(self):
        result = self._state
        self._state = {}
        return result

    def reconnect(self):
        pass

    def sim(self):
        while True:
            for a in SENSOR_TYPES:
                self._state[a] = random.randint(0,100)
            gevent.sleep(5)


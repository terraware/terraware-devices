# This file is a modified version of the home assistant driver, sensor.py, from here:
# https://github.com/briis/smartweatherudp
# It's licensed under the MIT License so this use is permitted but the license needs to be included
from pysmartweatherudp import SWReceiver
from .base import TerrawareDevice, TerrawareHub
import gevent
import random

SENSOR_TYPES = [
    'temperature',
    'dewpoint',
    'feels_like',
    'heat_index',
    'wind_chill',
    'wind_speed',
    'wind_bearing',
    'wind_speed_rapid',
    'wind_bearing_rapid',
    'wind_gust',
    'wind_lull',
    'wind_direction',
    'precipitation',
    'precipitation_rate',
    'humidity',
    'pressure',
    'uv',
    'solar_radiation',
    'illuminance',
    'lightning_count',
    'airbattery',
    'skybattery'
]

class TempestWeatherStation(TerrawareDevice):
    def __init__(self, dev_info, local_sim, diagnostic_mode, spec_path):
        super().__init__(dev_info, local_sim, diagnostic_mode)

        self._unit_system = 'metric'
        settings = dev_info.get('settings')
        if settings:
            # Can be either 'metric
            self._unit_system = settings.get('unitSystem', 'metric')

        self._state = {}

        if self._local_sim:
            gevent.spawn(self.sim)
        else:
            module = SWReceiver(units=self._unit_system)
            module.registerCallback(self._update_callback)
            module.start()

    def _update_callback(self, data):
        for (a, b) in data:
            if a in SENSOR_TYPES:
                self._state[(self.id, a)] = b

        if self.diagnostic_mode:
            print("Data received: %s %s %s %s", data.type, data.timestamp, data.precipitation, data.temperature)

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


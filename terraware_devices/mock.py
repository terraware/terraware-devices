import json
from .base import TerrawareDevice


# this device loads sensor values from a file call mock.json on every polling loop; you can edit the file to change the values
class MockSensorDevice(TerrawareDevice):

    def __init__(self, dev_info, local_sim, diagnostic_mode, spec_path):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        print('created MockSensorDevice')

    def get_timeseries_definitions(self):
        return [
            [self.id, 'value_a', 'numeric', 2],
            [self.id, 'value_b', 'numeric', 2],
        ]

    def reconnect(self):
        pass

    def poll(self):
        values = json.loads(open('mock.json').read())
        return {
            (self.id, 'value_a'): values['value_a'],
            (self.id, 'value_b'): values['value_b'],
        }

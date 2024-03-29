import json
from .base import TerrawareDevice


# this device loads sensor values from a file call mock.json on every polling loop; you can edit the file to change the values
class MockSensorDevice(TerrawareDevice):

    def __init__(self, dev_info):
        super().__init__(dev_info)
        self._polling_interval = 10
        print('created MockSensorDevice')

    def get_timeseries_definitions(self):
        return [
            [self.id, 'value_a', 'Numeric', 2],
            [self.id, 'value_b', 'Numeric', 2],
        ]

    def reconnect(self):
        pass

    def poll(self):
        values = json.loads(open('mock.json').read())
        return {
            (self.id, 'value_a'): values['value_a'],
            (self.id, 'value_b'): values['value_b'],
        }

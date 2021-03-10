import random
import gevent
import psutil
from .base import TerrawareDevice


# performs monitoring a raspberry pi
class RasPiDevice(TerrawareDevice):

    def __init__(self, local_sim):
        self._local_sim = local_sim
        print('created RasPiDevice')

    def reconnect(self):
        pass

    def poll(self):
        if self._local_sim:
            values = {
                'temperature': random.uniform(40, 60),
            }
        else:
            values = {
                'temperature': psutil.sensors_temperatures()['cpu_thermal'][0].current,
            }
        return values

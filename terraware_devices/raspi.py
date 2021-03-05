import random
import gevent
import psutil
from .base import TerrawareDevice


# performs monitoring a raspberry pi
class RasPiDevice(TerrawareDevice):

    def __init__(self, controller, server_path, local_sim):
        self._controller = controller
        self._server_path = server_path
        self._local_sim = local_sim
        print('created RasPiDevice')

    def server_path(self):
        return self._server_path

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

    def run(self):
        controller_path = self._controller.path_on_server()
        while True:
            status = self.poll()
            seq_values = {}
            for name, value in status.items():
                full_path = controller_path + '/' + self._server_path + '/' + name
                seq_values[full_path] = value
                print('    %s/%s: %.2f' % (self._server_path, name, value))
            self._controller.sequences.update_multiple(seq_values)
            gevent.sleep(60)

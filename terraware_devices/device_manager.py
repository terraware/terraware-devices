import gevent
from gevent import monkey
monkey.patch_all()

# standard library imports
import csv
import time
import gevent
import logging
from typing import List

# other imports
from rhizo.controller import Controller
from .base import TerrawareDevice
from .relay_device import RelayDevice
from .modbus_device import ModbusDevice


# manages a set of devices; each device handles a connection to physical hardware
class DeviceManager(object):

    devices: List[TerrawareDevice]

    def __init__(self):
        self.controller = Controller()
        self.devices = []
        self.start_time = None
        self.diagnostic_mode = self.controller.config.device_diagnostics
        self.handler = None
        if self.controller.config.get('sim', False):
            self.load('config/sim_devices.csv')
        else:
            self.load('config/devices.csv')
        self.controller.messages.add_handler(self)

    # initialize devices using a CSV file
    def load(self, device_list_file_name):
        with open(device_list_file_name) as csvfile:
            reader = csv.DictReader(csvfile)
            for line in reader:
                if int(line['enabled']):
                    device_type = line['type']
                    settings = line['settings']
                    server_path = line['server_path']
                    host = line['host']
                    port = int(line['port'])
                    polling_interval = int(line['polling_interval'])
                    if device_type == 'relay':
                        device = RelayDevice(self.controller, server_path, host, port, settings, polling_interval, self.diagnostic_mode)
                    elif device_type == 'modbus':
                        device = ModbusDevice(self.controller, server_path, host, port, settings, polling_interval, self.diagnostic_mode)
                    else:
                        print('unrecognized device type: %s' % device_type)
                        device = None
                    if device:
                        self.devices.append(device)

    def set_handler(self, handler):
        self.handler = handler

    def handle_message(self, message_type, params):
        if self.handler:
            self.handler.handle_message(message_type, params)

    # launch device polling greenlets
    def run(self):
        for device in self.devices:
            device.greenlet = gevent.spawn(device.run)
        self.start_time = time.time()
        while True:
            try:
                if self.handler:
                    self.handler.update()
            except KeyboardInterrupt:
                print('exiting')
                break
            except Exception as e:
                logging.warning('exception in handler: %s', e)
            gevent.sleep(10)

    # find a device by server_path
    def find(self, server_path):
        for device in self.devices:
            if device.server_path() == server_path:
                return device

    # check on devices; restart them as needed; if all is good, send watchdog message to server
    def watchdog_update(self):
        auto_restart = False  # disable auto-restart for now; we seem to occasionally get duplicate device greenlets

        # if it has been a while since startup, start checking device updates
        if time.time() - self.start_time > 30:
            devices_ok = True
            for device in self.devices:
                if device.last_update_time is None or time.time() - device.last_update_time > 10 * 60:
                    logging.info('no recent update for device %s', device.server_path())
                    if auto_restart:
                        device.greenlet.kill()  # this doesn't seem to work; we end up with multiple greenlets for the same device
                        device.greenlet = gevent.spawn(device.run)
                    devices_ok = False

            # if all devices are updating, send a watchdog message to server
            if devices_ok:
                self.controller.send_message('watchdog', {})


if __name__ == '__main__':
    d = DeviceManager()
    d.run

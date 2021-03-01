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
import requests
from rhizo.controller import Controller
from .base import TerrawareDevice
from .relay_device import RelayDevice
from .modbus_device import ModbusDevice
from .blue_maestro_device import BlueMaestroDevice, find_blue_maestro_devices


# manages a set of devices; each device handles a connection to physical hardware
class DeviceManager(object):

    devices: List[TerrawareDevice]

    def __init__(self):
        self.controller = Controller()
        self.devices = []
        self.has_bluetooth_devices = False
        self.start_time = None
        self.diagnostic_mode = self.controller.config.device_diagnostics
        self.handler = None
        if self.controller.config.get('load_from_server', False):
            self.load_from_server()
        else:
            if self.controller.config.get('sim', False):
                self.load_from_file('config/sim_devices.csv')
            else:
                self.load_from_file('config/devices.csv')
        self.controller.messages.add_handler(self)

    # initialize devices using a CSV file
    def load_from_file(self, device_list_file_name):
        with open(device_list_file_name) as csvfile:
            reader = csv.DictReader(csvfile)
            count_added = 0
            for line in reader:
                if int(line['enabled']):
                    device_type = line['type']
                    settings = line['settings']
                    server_path = line['server_path']
                    host = line['host']
                    polling_interval = int(line['polling_interval'])
                    if device_type == 'relay':
                        port = int(line['port'])
                        device = RelayDevice(self.controller, server_path, host, port, settings, polling_interval, self.diagnostic_mode)
                    elif device_type == 'modbus':
                        port = int(line['port'])
                        device = ModbusDevice(self.controller, server_path, host, port, settings, polling_interval, self.diagnostic_mode)
                    elif device_type == 'blue-maestro':
                        device = BlueMaestroDevice(server_path, host)
                        self.has_bluetooth_devices = True
                    else:
                        print('unrecognized device type: %s' % device_type)
                        device = None
                    if device:
                        self.devices.append(device)
                        count_added += 1
            print('loaded %d devices from %s' % (count_added, device_list_file_name))

    # initialize devices using JSON data from server
    def load_from_server(self):
        server_name = self.controller.config.server_name
        secret_key = self.controller.config.secret_key
        r = requests.get('http://' + server_name + '/api/v1/device/all/config', auth=('', secret_key))
        if r.status_code == 200:
            dev_infos = r.json()['devices']
        else:
            print('error reading devices from server %s' % server_name)
            return
        count_added = 0
        for dev_info in dev_infos:
            device = None
            if dev_info['type'] == 'sensor' and dev_info['make'] == 'Blue Maestro' and dev_info['model'] == 'Tempo Disc':
                server_path = dev_info['serverPath']
                label = dev_info['address']
                device = BlueMaestroDevice(server_path, label)
                self.has_bluetooth_devices = True
            if device:
                self.devices.append(device)
                count_added += 1
        print('loaded %d devices from %s' % (count_added, server_name))

    def set_handler(self, handler):
        self.handler = handler

    def handle_message(self, message_type, params):
        if self.handler:
            self.handler.handle_message(message_type, params)

    # launch device polling greenlets
    def run(self):
        for device in self.devices:
            device.greenlet = gevent.spawn(device.run)
        if self.has_bluetooth_devices:
            gevent.spawn(self.update_bluetooth_devices)
        self.start_time = time.time()
        while True:
            try:
                if self.handler:
                    self.handler.update()
            except KeyboardInterrupt:
                print('exiting')
                break
            except Exception as ex:
                logging.warning('exception in handler: %s', ex)
                logging.debug('exception details', ex)
            gevent.sleep(10)

    # a greenlet for update bluetooth devices
    def update_bluetooth_devices(self):
        interface = self.controller.config.bluetooth_interface
        scan_timeout = self.controller.config.bluetooth_scan_timeout
        while True:
            timestamp = time.time()

            # get list of all devices currently in range
            dev_infos = find_blue_maestro_devices(timeout=scan_timeout, iface=interface)

            # update our device objects and send values to server
            seq_values = {}
            for dev_info in dev_infos:
                label = dev_info['label']
                for device in self.devices:
                    if hasattr(device, 'label') and device.label() == label:
                        temperature = dev_info['temperature']
                        humidity = dev_info['humidity']
                        device.update(timestamp, temperature, humidity, dev_info['rssi'])
                        device_path = self.controller.path_on_server() + '/' + device.server_path()
                        seq_values[device_path + '/temperature'] = temperature
                        seq_values[device_path + '/humidity'] = humidity
                        print('    %s/temperature: %.2f' % (device_path, temperature))
                        print('    %s/humidity: %.2f' % (device_path, humidity))
            print('updating %d sequences' % len(seq_values))
            self.controller.sequences.update_multiple(seq_values)

            # sleep until next cycle
            gevent.sleep(15)

    # find a device by server_path
    def find(self, server_path):
        for device in self.devices:
            if device.server_path() == server_path:
                return device

    # check on devices; restart them as needed; if all is good, send watchdog message to server
    def watchdog_update(self):

        # if it has been a while since startup, start checking device updates
        if time.time() - self.start_time > 30:
            devices_ok = True
            for device in self.devices:
                if device.last_update_time is None or time.time() - device.last_update_time > 10 * 60:
                    logging.info('no recent update for device %s; reconnecting', device.server_path())
                    device.reconnect()
                    devices_ok = False

            # if all devices are updating, send a watchdog message to server
            if devices_ok:
                self.controller.send_message('watchdog', {})


if __name__ == '__main__':
    d = DeviceManager()
    d.run()

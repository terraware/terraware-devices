import gevent
from gevent import monkey
monkey.patch_all()

# standard library imports
import csv
import time
import json
import gevent
import random
import logging
import base64  # temp for forwarding data to cloud server
import datetime  # temp for forwarding data to cloud server
from typing import List

# other imports
import requests
from rhizo.controller import Controller
from rhizo.resources import send_request  # temp for forwarding data to cloud server
from .base import TerrawareDevice
from .relay import RelayDevice
from .modbus import ModbusDevice
from .raspi import RasPiDevice
from .inhand_router import InHandRouterDevice
from .blue_maestro import BlueMaestroDevice, find_blue_maestro_devices


# manages a set of devices; each device handles a connection to physical hardware
class DeviceManager(object):

    devices: List[TerrawareDevice]

    def __init__(self):
        self.controller = Controller()
        self.devices = []
        self.has_bluetooth_devices = False
        self.start_time = None
        self.diagnostic_mode = self.controller.config.device_diagnostics
        self.local_sim = self.controller.config.get('local_sim', False)
        self.handler = None
        local_device_file_name = self.controller.config.get('local_device_file_name')
        if local_device_file_name:
            self.load_from_file(local_device_file_name)
        else:
            self.load_from_server()
        self.controller.messages.add_handler(self)

    # initialize devices using a JSON file (with same format as device list from server)
    def load_from_file(self, device_list_file_name):
        if device_list_file_name.endswith('json'):
            with open(device_list_file_name) as json_file:
                device_infos = json.loads(json_file.read())['devices']
                count_added = self.create_devices(device_infos)
        else:  # will remove this case after migrate away from CSV device list
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
                            device = RelayDevice(host, port, settings, self.diagnostic_mode)
                        elif device_type == 'modbus':
                            port = int(line['port'])
                            spec_file_name = 'config/%s.csv' % server_path
                            device = ModbusDevice(host, port, settings, self.diagnostic_mode, spec_file_name)
                        elif device_type == 'blue-maestro':
                            device = BlueMaestroDevice(host)
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
            device_infos = r.json()['devices']
        else:
            print('error reading devices from server %s' % server_name)
            return
        count_added = self.create_devices(device_infos)
        print('loaded %d devices from %s' % (count_added, server_name))

    # add/initialize devices using a list of dictionaries of device info
    def create_devices(self, device_infos):
        count_added = 0
        print('device list has information for %d device(s)' % len(device_infos))
        for dev_info in device_infos:
            dev_type = dev_info['type']
            make = dev_info['make']
            model = dev_info['model']
            server_path = dev_info['serverPath']
            address = dev_info['address']
            protocol = dev_info.get('protocol')
            polling_interval = dev_info['pollingInterval']

            # initialize a device based on the make/model/type
            device = None
            if dev_type == 'sensor' and make == 'Blue Maestro' and model == 'Tempo Disc':
                device = BlueMaestroDevice(address)
                self.has_bluetooth_devices = True
            elif dev_type == 'server' and make == 'Raspberry Pi':
                device = RasPiDevice(self.local_sim)
            elif dev_type == 'router' and make == 'InHand Networks' and model == 'IR915L':
                device = InHandRouterDevice(address, self.controller.config.router_password, self.local_sim)
            elif protocol == 'modbus':
                port = dev_info['port']
                settings = dev_info['settings']
                spec_file_name = 'specs/' + dev_info['make'] + '_' + dev_info['model'] + '.csv'
                device = ModbusDevice(address, port, settings, self.diagnostic_mode, spec_file_name)

            # if a device was created, add it to our collection
            if device:
                device.set_server_path(server_path)
                device.set_polling_interval(polling_interval)
                self.devices.append(device)
                count_added += 1
            else:
                print('device not recognized; type: %s, make: %s, model: %s' % (dev_type, make, model))
        return count_added

    def set_handler(self, handler):
        self.handler = handler

    def handle_message(self, message_type, params):
        if self.handler:
            self.handler.handle_message(message_type, params)

    # run this function as a greenlet, polling the given device
    def polling_loop(self, device):
        controller_path = self.controller.path_on_server()
        cloud_controller_path = self.controller.config.get('cloud_path')
        while True:
            values = device.poll()
            seq_values = {}
            cloud_seq_values = {}
            for name, value in values.items():
                seq_rel_path = device.server_path + '/' + name
                seq_values[controller_path + '/' + seq_rel_path] = value
                if cloud_controller_path:
                    cloud_seq_values[cloud_controller_path + '/' + seq_rel_path] = value
                self.controller.sequences.update_value(seq_rel_path, value)
                print('    %s/%s: %.2f' % (device.server_path, name, value))
            if seq_values:
                self.controller.sequences.update_multiple(seq_values)
                if cloud_controller_path and 'BMU' in device.server_path:  # just send BMU values for now
                    self.send_to_cloud_server(cloud_seq_values)
            gevent.sleep(device.polling_interval)  # TODO: need to subtract out poll duration

    # launch device polling greenlets and run handlers
    def run(self):
        for device in self.devices:
            device.greenlet = gevent.spawn(self.polling_loop, device)
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
            if self.local_sim:
                dev_infos = []
                for device in self.devices:
                    if hasattr(device, 'label'):
                        dev_infos.append({
                            'label': device.label(),
                            'temperature': random.uniform(10, 20),
                            'humidity': random.uniform(20, 30),
                            'rssi': -random.randint(40, 70),
                        })
            else:
                dev_infos = find_blue_maestro_devices(timeout=scan_timeout, iface=interface)

            # update our device objects and send values to server
            seq_values = {}
            for dev_info in dev_infos:
                label = dev_info['label']
                for device in self.devices:
                    if hasattr(device, 'label') and device.label() == label:
                        temperature = dev_info['temperature']
                        humidity = dev_info['humidity']
                        device_path = self.controller.path_on_server() + '/' + device.server_path
                        seq_values[device_path + '/temperature'] = temperature
                        seq_values[device_path + '/humidity'] = humidity
                        if False:  # use device verbose flag?
                            print('    %s/temperature: %.2f' % (device_path, temperature))
                            print('    %s/humidity: %.2f' % (device_path, humidity))
            print('updating %d blue maestro sequences' % len(seq_values))
            self.controller.sequences.update_multiple(seq_values)

            # sleep until next cycle
            gevent.sleep(15)

    # find a device by server_path
    def find(self, server_path):
        for device in self.devices:
            if device.server_path == server_path:
                return device

    # check on devices; restart them as needed; if all is good, send watchdog message to server
    def watchdog_update(self):

        # if it has been a while since startup, start checking device updates
        if time.time() - self.start_time > 30:
            devices_ok = True
            for device in self.devices:
                if device.last_update_time is None or time.time() - device.last_update_time > 10 * 60:
                    logging.info('no recent update for device %s; reconnecting', device.server_path)
                    device.reconnect()
                    devices_ok = False

            # if all devices are updating, send a watchdog message to server
            if devices_ok:
                self.controller.send_message('watchdog', {})

    # temporary code for forwarding data to cloud server
    def send_to_cloud_server(self, values):
        server_name = self.controller.config.cloud_server
        secure = not server_name.startswith('127.0.0.1')
        secret_key = self.controller.config.cloud_secret_key
        basic_auth = base64.b64encode(('dev-mgr:' + secret_key).encode('utf-8')).decode()  # send secret key as password
        send_values = {k: str(v) for k, v in values.items()}  # make sure values are strings
        params = {
            'values': json.dumps(send_values),
            'timestamp': datetime.datetime.utcnow().isoformat() + ' Z',
        }
        (status, reason, data) = send_request(server_name, 'PUT', '/api/v1/resources', params, secure, 'text/plain', basic_auth)
        if status == 200:
            print('sent %d values to cloud server' % len(values))
        else:
            print('error sending values to cloud server')


if __name__ == '__main__':
    d = DeviceManager()
    d.run()

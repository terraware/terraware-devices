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
import pathlib
import base64  # temp for forwarding data to cloud server
import datetime  # temp for forwarding data to cloud server
from typing import List

# other imports
import requests
from .base import TerrawareDevice
from .control_by_web import CBWRelayDevice, CBWSensorHub, CBWTemperatureHumidityDevice
from .omnisense import OmniSenseHub, OmniSenseTemperatureHumidityDevice
from .modbus import ModbusDevice
from .raspi import RasPiDevice
from .inhand_router import InHandRouterDevice
from .blue_maestro import BlueMaestroDevice, find_blue_maestro_devices
from .nut_ups import NutUpsDevice


# manages a set of devices; each device handles a connection to physical hardware
class DeviceManager(object):

    devices: List[TerrawareDevice]

    def __init__(self):
        # Logic here is:
        # This device manager is running on a device that handles sensing for one or more facilities.
        # For example, this could be running on a raspberry pi that is hooked up to all the sensors for
        # the seed bank it's inside, but also all the sensors for the nearby nursery because it's close enough
        # and there was no reason to get a second computer for the nursery.
        # 
        # We use device envvars to point us both to the place the config data should come from, and also
        # the list of facilities this device is responsible for.
        #
        # One final detail is that we do then inform the server about all these timeseries, not because it is an
        # authoritative source of information about them, but so that on the other end, when analyzing or visualizing
        # the data, we have a way to query, for example, "Give me all temperature readings from facility #84".
        self.devices = []
        self.has_bluetooth_devices = False
        self.start_time = None
        self.diagnostic_mode = os.environ['DEVICE_MANAGER_DIAGNOSTIC_MODE']

        self.server_path = os.environ['DEVICE_MANAGER_SERVER']

        self.offline_refresh_token = os.environ['DEVICE_MANAGER_OFFLINE_REFRESH_TOKEN']
        self.access_token_request_url = os.environ['DEVICE_MANAGER_ACCESS_TOKEN_REQUEST_URL']
        self.access_token = self.get_access_token_from_server()

        self.local_sim = False

        self.facilities = os.environ['DEVICE_MANAGER_FACILITIES']
        self.load_config_from_server(self.facilities)

        self.timeseries_values_to_send = []

    # add/initialize devices using a list of dictionaries of device info
    def create_devices(self, device_infos):
        count_added = 0
        spec_path = str(pathlib.Path(__file__).parent.absolute()) + '/../specs'
        print('device list has information for %d device(s)' % len(device_infos))

        # Create the devices and hubs and save in a flat list
        for dev_info in device_infos:
            device = None
            device_class = self.get_device_class_to_instantiate(dev_info)
            if device_class:
                device = device_class(dev_info, spec_path, self.local_sim, self.diagnostic_mode, spec_path)
                self.devices.append(device)
                count_added += 1
            else:
                print('device not recognized; type: %s, make: %s, model: %s' % (dev_type, make, model))

        # For devices that are children hooked to hubs, find the hubs and link them up.
        for device in self.devices:
            if device.hub_id:
                hub_device = next(x for x in self.devices if x.id == hub_id, None)
                if hub_device:
                    if hasattr(hub_device, 'add_device'):
                        hub_device.add_device(device)
                    else:
                        print('Error: Device {} has hub id {}, but device with that id is not a hub! (does not inherit from TerrawareHub).'.format(device.name, device.hub_id))
                else:
                    print('Error: Device {} has hub id {}, but no device with that id exists! Did you forget to add the hub to the configuration?'.format(device.name, device.hub_id))
        
        # We wait until here to query timeseries rather than asking right after creating the device, because in some cases 
        # the hub object may want to enumerate the timeseries, so we only ask after all the child devices are linked to their hubs,
        # just so the devices can all assume they're fully constructed by the time this gets called.
        timeseries_definitions = []
        timeseries_definitions.extend(newdevice.get_timeseries_definitions()) for newdevice in self.devices
        self.send_timeseries_definitions_to_server(timeseries_definitions)

        return count_added

    # run this function as a greenlet, polling the given device
    def device_polling_loop(self, device):
        while True:
            # do the polling
            try:
                values = device.poll()
            except Exception as e:
                print('error polling device {} (id {})'.format(device.name, device.id))
                print(e)
                values = {}

            self.record_timeseries_values_and_maybe_push_to_server(values)

            if self.diagnostic_mode:
                print('    %s: %.2f' % (id_name_pair, value)) for id_name_pair, value in values.items()

            # wait until next round of polling
            gevent.sleep(device.polling_interval)  # TODO: need to subtract out poll duration

    # launch device polling greenlets and run handlers
    def run(self):
        device_polling_greenlet_count = 0
        for device in self.devices:
            if device.polling_interval:
                device.greenlet = gevent.spawn(self.device_polling_loop, device)
                device_polling_greenlet_count += 1
        print('launched %d greenlet(s) for device & hub polling' % device_polling_greenlet_count)
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
    # these are handles separately from other devices since we poll for a whole batch of devices in a single operation
    def update_bluetooth_devices(self):
        interface = self.controller.config.bluetooth_interface
        scan_timeout = self.controller.config.bluetooth_scan_timeout
        use_ubertooth = self.controller.config.get('use_ubertooth', False)
        controller_path = self.controller.path_on_server() if self.controller.config.enable_server else ''
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
                try:
                    dev_infos = find_blue_maestro_devices(timeout=scan_timeout, iface=interface, ubertooth=use_ubertooth)
                except Exception as e:
                    print('error in find_blue_maestro_devices')
                    print(e)
                    dev_infos = {}

            # update our device objects and send values to server
            seq_values = {}
            found_count = 0
            not_found_labels = []
            for dev_info in dev_infos:
                label = dev_info['label']
                found = False
                for device in self.devices:
                    if hasattr(device, 'label') and device.label() == label:
                        device_path = controller_path + '/' + device.server_path
                        for metric in ['temperature', 'humidity', 'rssi']:
                            metric_path = device_path + '/' + metric
                            seq_values[metric_path] = dev_info[metric]
                            if self.controller.config.enable_server:
                                self.create_sequence(metric_path, 'numeric', decimal_places=2)  # TODO: determine data type and decimal places from device
                        found_count += 1
                        found = True
                if not found:
                    not_found_labels.append(label)
            if self.controller.config.enable_server:
                self.controller.sequences.update_multiple(seq_values)
            print('blue maestro devices detected: %d, updated: %d' % (len(dev_infos), found_count))
            if not_found_labels:
                print('blue maestro devices not found in device list: %s' % (', '.join(not_found_labels)))

            # sleep until next cycle
            gevent.sleep(30)

    # check on devices; restart them as needed; if all is good, send watchdog message to server
    def watchdog_update(self):
        # if it has been a while since startup, start checking device updates
        if time.time() - self.start_time > 30:
            devices_ok = True
            for device in self.devices:
                if device.last_update_time is None or time.time() - device.last_update_time > 10 * 60:
                    logging.info('no recent update for device {} (id {}); reconnecting'.format(device.name, device.id))
                    device.reconnect()
                    devices_ok = False

            # if all devices are updating, send a watchdog message to server
            if devices_ok:
                self.controller.send_message('watchdog', {})

    def load_config_from_server(self, facilities):
        device_infos = self.query_config_from_server(self.facilities)

        count_added = self.create_devices(device_infos)
        print('loaded %d devices from %s' % (count_added, server_name))

    # APIs for communicating with the terraware-server.

    # We use expiring access tokens for server access, and need to periodically request a new one; this is how you do that.
    # Called immediately on startup and then anytime a query fails
    def get_access_token_from_server(self):
        request_url = self.access_token_request_url
        offline_refresh_token = self.offline_refresh_token
        # assemble a request with those two and then return success or failure blah blah

    def query_config_from_server(self, facilities):
        server_name = self.server_path
        secret_key = self.server_auth_key
        url = 'http://' + server_name + '/api/v1/device/all/config'
        device_infos = None

        while device_infos is None:
            try:
                r = requests.get(url, auth=('', secret_key))
                r.raise_for_status()
                device_infos = r.json()['devices']
            except Exception as ex:
                print('error requesting devices from server %s: %s' % (server_name, ex))
                gevent.sleep(10)

        return device_infos

    def send_timeseries_definitions_to_server(self, timeseries_definitions):
        pass

    def record_timeseries_values_and_maybe_push_to_server(self, values):
        # values is a dictionary that maps from the tuple (device id, timeseries name) -> value
        pass

    # This is sort of a glorified dictionary lookup, and it could be extracted out of this file and
    # we could do something like walk the directory and ask each py file to add class defs to some
    # dictionary so there's not even a direct awareness of the various sensor classes here in this
    # file. But this seems like the right compromise of legibility and decoupling at the moment.
    def get_device_class_to_instantiate(self, dev_info):
        dev_type = dev_info['type']
        make = dev_info['make']
        model = dev_info['model']
        server_path = dev_info['serverPath']
        address = dev_info['address']
        polling_interval = dev_info['pollingInterval']

        port = dev_info.get('port')
        protocol = dev_info.get('protocol')

        if dev_type == 'sensor' and make == 'Blue Maestro' and model == 'Tempo Disc':
            return BlueMaestroDevice
        elif dev_type == 'ups':
            return NutUpsDevice
        elif dev_type == 'server' and make == 'Raspberry Pi':
            return RasPiDevice
        elif dev_type == 'router' and make == 'InHand Networks' and model == 'IR915L':
            return InHandRouterDevice
        elif dev_type == 'relay' and make == 'ControlByWeb' and model == 'WebRelay':
            return CBWRelayDevice
        elif dev_type == 'sensor' and make == 'ControlByWeb' and model == 'X-DTHS-WMX':
            return CBWTemperatureHumidityDevice
        elif dev_type == "hub" and make == "ControlByWeb":
            return CBWSensorHub
        elif dev_type == 'sensor' and make == 'OmniSense' and model == 'S-11':
            return OmniSenseTemperatureHumidityDevice
        elif dev_type == "hub" and make == "OmniSense":
            return OmniSenseHub
        elif protocol == 'modbus':
            return ModbusDevice


if __name__ == '__main__':
    d = DeviceManager()
    d.run()

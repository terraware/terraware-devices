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

# For timestamping our timeseries values locally since we batch them up and don't send immediately
from datetime import timezone
from datetime import date
import datetime

from typing import List
from collections import defaultdict

import os

# other imports
import requests
from .base import TerrawareDevice, TerrawareHub
from .control_by_web import CBWRelayDevice, CBWSensorHub, CBWTemperatureHumidityDevice
from .omnisense import OmniSenseHub, OmniSenseTemperatureHumidityDevice
from .modbus import ModbusDevice
from .raspi import RasPiDevice
from .inhand_router import InHandRouterDevice
from .nut_ups import NutUpsDevice
from .weatherflow import TempestWeatherStation

from .chirpstack import ChirpStackHub, SenseCapSoilSensor, DraginoSoilSensor


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
        self.diagnostic_mode = os.environ.get('DIAGNOSTIC_MODE', False)

        self.devices = []
        self.timeseries_values_to_send = []
        self.start_time = None

        self.local_config_file = os.environ.get('LOCAL_CONFIG_FILE_OVERRIDE', None)
        self.local_sim = os.environ.get('LOCAL_SIM', False)

        self.server_path = os.environ.get('SERVER')

        self.api_client_id = os.environ.get('KEYCLOAK_API_CLIENT_ID')
        self.offline_refresh_token = os.environ.get('OFFLINE_REFRESH_TOKEN')
        self.access_token_request_url = os.environ.get('ACCESS_TOKEN_REQUEST_URL')

        facilities_string = os.environ.get('FACILITIES', None)
        self.facilities = [int(a) for a in facilities_string.split(',')] if facilities_string else []

        print('*' * 70)
        now_str = datetime.datetime.now().isoformat()
        print ('Device Manager starting at {} with server {} for facilities {}'.format(now_str, self.server_path, self.facilities))

        self.refresh_access_token_from_server()


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
                device_diagnostic_mode = self.diagnostic_mode
                if 'settings' in dev_info and 'diagnostic_mode' in dev_info['settings']:
                    device_diagnostic_mode = dev_info['settings']['diagnostic_mode']
                device = device_class(dev_info, self.local_sim, device_diagnostic_mode, spec_path)
                self.devices.append(device)
                count_added += 1
            else:
                print('device not recognized: {}'.format(dev_info))

        # For devices that are children hooked to hubs, find the hubs and link them up.
        for device in self.devices:
            if device.parent_id:
                hub_device = next((x for x in self.devices if x.id == device.parent_id), None)
                if hub_device:
                    if hasattr(hub_device, 'add_device'):
                        if self.diagnostic_mode:
                            print('Attached device {} to its parent (hub) device {}'.format(device.name, hub_device.name))
                        hub_device.add_device(device)
                    else:
                        print('Error: Device {} has hub id {}, but device with that id is not a hub! (does not inherit from TerrawareHub).'.format(device.name, device.parent_id))
                else:
                    print('Error: Device {} has hub id {}, but no device with that id exists! Did you forget to add the hub to the configuration?'.format(device.name, device.parent_id))
        
        # Let hubs know they all have their child sensors bound up so they can start services or whatever
        for device in self.devices:
            if hasattr(device, 'notify_all_devices_added'):
                device.notify_all_devices_added()

        # We wait until here to query timeseries rather than asking right after creating the device, because in some cases 
        # the hub object may want to enumerate the timeseries, so we only ask after all the child devices are linked to their hubs,
        # just so the devices can all assume they're fully constructed by the time this gets called.
        timeseries_definitions = []
        for newdevice in self.devices:
            timeseries_definitions.extend(newdevice.get_timeseries_definitions())
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

            self.record_timeseries_values(values)

            if self.diagnostic_mode:
                print('=== DEVICE POLLING LOOP [{}] - {} values received: ==='.format(device.name, len(values)))
                for id_name_pair, value in values.items():
                    print('    %s: %.2f' % (id_name_pair, value))
                print('======================================================')

            # wait until next round of polling
            gevent.sleep(device.polling_interval)  # TODO: need to subtract out poll duration

    # launch device polling greenlets and run handlers
    def run(self):
        device_polling_greenlet_count = 0
        for device in self.devices:
            if device.polling_interval:
                device.greenlet = gevent.spawn(self.device_polling_loop, device)
                device_polling_greenlet_count += 1
        print('launched %d greenlet(s) for device and hub polling' % device_polling_greenlet_count)
        self.start_time = time.time()
        while True:
            self.send_timeseries_values_to_server()
            gevent.sleep(120)

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

    # APIs for communicating with the terraware-server.

    # We use expiring access tokens for server access, and need to periodically request a new one; this is how you do that.
    # Called immediately on startup and then anytime a query fails
    def refresh_access_token_from_server(self):
        if self.diagnostic_mode:
            print('refresh_access_token_from_server called')

        if self.local_sim:
            return

        request_url = self.access_token_request_url
        access_token = None
        parameters = {'client_id': self.api_client_id, 'grant_type': 'refresh_token', 'refresh_token': self.offline_refresh_token}
        while access_token is None:
            try:
                r = requests.post(request_url, data=parameters)
                r.raise_for_status()

                # There's other stuff in the response like 'expires_in' for how many seconds this is valid and stuff
                # But we don't use them right now - could potentially preemptively request new tokens when that time
                # is nearing to avoid serialized interruptions and maybe save a failed roundtrip or two.
                json = r.json()
                access_token = '{} {}'.format(json['token_type'], json['access_token'])
                self.auth_header = {"Authorization": access_token}

                if self.diagnostic_mode:
                    print('    Success, auth_header is [{}...]'.format(abbreviate_string(self.auth_header, 30, 20)))
            except Exception as ex:
                print('error requesting access token from server {}: {}'.format(request_url, ex))
                gevent.sleep(120)

    def load_device_config(self):
        if self.diagnostic_mode:
            print('load_device_config called for facilities {}'.format(self.facilities))

        if self.local_config_file:
            print('reading device manager config from local config file {}'.format(self.local_config_file))
            with open(self.local_config_file) as json_file:
                site_info = json.loads(json_file.read())
                return site_info['devices']

        server_name = self.server_path
        url = server_name + 'api/v1/facility/{}/devices'
        
        # All this is doing is "Ask the server for each facility's device list and combine them and return them" but all
        # the error handling makes it look rather complicated.
        device_infos = []
        for facility_id in self.facilities:
            got_facility_devices = False
            while not got_facility_devices:
                try:
                    r = self.send_request(requests.get, url.format(facility_id))
                    r.raise_for_status()

                    if self.diagnostic_mode:
                        print('Received the following devices from server for facility id {}:'.format(facility_id))
                    device_infos += r.json()['devices']
                    got_facility_devices = True
                except Exception as ex:
                    print('error requesting devices from server %s: %s' % (server_name, ex))
                    gevent.sleep(120)

        print('loaded %d devices from %s' % (len(device_infos), self.local_config_file if self.local_config_file else self.server_path))

        return device_infos

    def send_device_definition_to_server(self, device_info):
        assert not 'id' in device_info
        server_name = self.server_path
        url = server_name + 'api/v1/devices'
        upload_device_info = device_info.copy()
        upload_device_info['facilityId'] = self.facilities[0]  # use first facility in list
        print('creating device with type %s' % device_info['type'])
        print(upload_device_info)
        r = self.send_request(requests.post, url, upload_device_info)
        r.raise_for_status()
        return r.json()['id']  # return ID assigned by server

    def update_device_definition_on_server(self, device_info):
        assert 'id' in device_info
        server_name = self.server_path
        url = server_name + 'api/v1/devices/%s' % device_info['id']
        upload_device_info = device_info.copy()
        del upload_device_info['id']  # ID goes in URL, not payload
        print('updating device info for device %d' % device_info['id'])
        print(upload_device_info)
        r = self.send_request(requests.put, url, upload_device_info)
        r.raise_for_status()

    def send_timeseries_definitions_to_server(self, timeseries_definitions):
        if self.diagnostic_mode:
            print('=== SEND TIMESERIES DEFINITIONS TO SERVER - values received: ===')
            for a in timeseries_definitions:
                print('    id: {}, name "{}", data type "{}", decimal places "{}"'.format(a[0], a[1], a[2], a[3]))
            print('======================================================')

        if self.local_sim:
            return

        server_name = self.server_path
        url = server_name + 'api/v1/seedbank/timeseries/create'

        create_timeseries_entries = [{
            'deviceId': definition[0],
            'timeseriesName': definition[1],
            'type': definition[2].capitalize(),
            'decimalPlaces': definition[3],
        } for definition in timeseries_definitions]

        payload = {'timeseries': create_timeseries_entries}

        # The incoming format of timseries_definitions is just a list of lists, where each contained list is four elements:
        # [device id, timeseries name, data type, decimal places].
        success = False
        while not success:
            try:
                r = self.send_request(requests.post, url, payload)
                r.raise_for_status()
                success = True
            except Exception as ex:
                print('error sending timeseries definitions to server %s: %s' % (server_name, ex))
                print('---- payload ----')
                print(payload)  # some debug printing
                print('---- end payload ----')
                gevent.sleep(120)

    # values is a dictionary that maps from the tuple (device id, timeseries name) -> value
    def record_timeseries_values(self, values):
        if self.local_sim:
            return
        
        ts = int(time.time()) # UTC timestamp
        timestamp = datetime.datetime.fromtimestamp(ts, timezone.utc).isoformat()

        # The server-side API takes a dictionary 
        for key_tuple, scalar_value in values.items():
            found = False
            for entry in self.timeseries_values_to_send:
                if entry['deviceId'] == key_tuple[0] and entry['timeseriesName'] == key_tuple[1]:
                    entry['values'].append({
                        'timestamp': timestamp,
                        'value': str(scalar_value)
                    })
                    found = True
            if not found:
                self.timeseries_values_to_send.append({
                    'deviceId': key_tuple[0],
                    'timeseriesName': key_tuple[1],
                    'values': [{
                        'timestamp': timestamp,
                        'value': str(scalar_value)
                    }]
                })

    def send_timeseries_values_to_server(self):
        server_name = self.server_path
        url = server_name + 'api/v1/seedbank/timeseries/values'
        if len(self.timeseries_values_to_send) > 0:
            values_to_send = self.timeseries_values_to_send.copy()
            self.timeseries_values_to_send = []  # assuming this is atomic with line above
            payload = {
                'timeseries': values_to_send
            }
            if self.diagnostic_mode:
                print('Sending {} timeseries values to server'.format(len(payload)))
            try:
                r = self.send_request(requests.post, url, payload)
                r.raise_for_status()
                response = r.json()
            except Exception as ex:
                print('error sending timeseries values to server %s: %s' % (server_name, ex))
                self.timeseries_values_to_send += values_to_send  # we'll try again later
                return
            if response['status'] == 'error':
                failures = response['failures']
                print('failed updates:')
                for failed_update in failures:
                    print('    device: %d, time series: %s' % (failed_update['deviceId'], failed_update['timeseriesName']))
                fail_count = len(failures)
            else:
                fail_count = 0
            now_str = datetime.datetime.now().strftime('%H:%M:%S')
            print('%s: sent %d updates; had %d failures' % (now_str, len(values_to_send), fail_count))

    # send a request to the server and retry if expired token
    def send_request(self, request_func, url, json_payload=None):
        # To be really robust this should probably timeout after some period to make sure the other greenlets
        # get to run, but that also means gracefully handling just utterly failed attempts to talk to the server
        # which will certainly happen if the internet goes down, but so for now, just hang here and keep going in case
        # it ever comes back. Other devices shouldn't have timeouts or anything that prevent us from resuming if and
        # when things come back, and it just means we'll miss a bunch of device samples - but that would happen in
        # any case, it's just a question of which samples we end up missing.
        #
        # I'm actually not sure if Python lambdas / closures capture by reference or value or what, but safest just
        # to say this lambda should NOT capture self.auth_header so we can pass it in every time and make sure it is
        # using the new value every time.
        #
        # This - https://stackoverflow.com/questions/2295290/what-do-lambda-function-closures-capture - makes
        # it sound like it's captured by reference and it would work to capture self.auth_header, but I think it
        # makes the code more legible to pass it as an arg so I'm leaving it this way.
        while True:
            if self.diagnostic_mode:
                print('Submitting request [{}, {}] with auth header [{}]'.format(request_func, url, abbreviate_string(self.auth_header, 30, 20)))
            r = request_func(url, headers=self.auth_header, json=json_payload)
            if self.diagnostic_mode:
                print('    Request sent: status {}, content {}'.format(r.status_code, r.content))
            if (r.status_code == 401):
                if self.diagnostic_mode:
                    print('    Expired token for request [{}], refreshing...'.format(r.request))
                self.refresh_access_token_from_server()
            else:
                if self.diagnostic_mode:
                    print('    Success, returning result')
                    print('**************************************************')
                return r

    # This is sort of a glorified dictionary lookup, and it could be extracted out of this file and
    # we could do something like walk the directory and ask each py file to add class defs to some
    # dictionary so there's not even a direct awareness of the various sensor classes here in this
    # file. But this seems like the right compromise of legibility and decoupling at the moment.
    def get_device_class_to_instantiate(self, dev_info):
        dev_type = dev_info.get('type')
        make = dev_info.get('make')
        model = dev_info.get('model')
        protocol = dev_info.get('protocol')

        # This list doesn't include all the things we have driver classes for. The missing ones (bluetooth stuff,
        # two of the ControlByWeb devices) were unused when I took over the device manager in 9/13/2021 and therefore
        # I couldn't test or validate the code. I left those classes in, with comments, and removed them from this
        # list so if they're needed again it's clear the code will need work and testing.
        if dev_type == 'ups':
            return NutUpsDevice
        elif dev_type == 'server' and make == 'Raspberry Pi':
            return RasPiDevice
#        elif dev_type == 'router' and make == 'InHand Networks' and model == 'IR915L':
#            return InHandRouterDevice
        elif dev_type == 'relay' and make == 'ControlByWeb' and model == 'WebRelay':
            return CBWRelayDevice
        elif dev_type == 'sensor' and make == 'OmniSense' and model == 'S-11':
            return OmniSenseTemperatureHumidityDevice
        elif dev_type == "hub" and make == "OmniSense":
            return OmniSenseHub
        elif protocol == 'modbus':
            return ModbusDevice
 
        # SenseCap doesn't really have a model number / name for this sensor:
        # https://www.seeedstudio.com/LoRaWAN-Soil-Moisture-and-Temperature-Sensor-EU868-p-4316.html
        elif dev_type == 'sensor' and make == 'SenseCAP':
            return SenseCapSoilSensor

        # https://www.dragino.com/products/lora-lorawan-end-node/item/159-lse01.html
        elif dev_type == 'sensor' and make == 'Dragino' and model == 'LSE01':
            return DraginoSoilSensor

        elif dev_type == 'hub' and make == 'SenseCAP':
            return ChirpStackHub

        elif dev_type == 'sensor' and make == 'WeatherFlow' and model == 'Tempest':
            return TempestWeatherStation

        else:
            return None


def abbreviate_string(thing_to_stringify, prefix, suffix):
    long_str = '{}'.format(thing_to_stringify)
    if len(long_str) > prefix+suffix:
        long_str = '{}...{}'.format(long_str[0:prefix], long_str[-suffix:])
    return long_str

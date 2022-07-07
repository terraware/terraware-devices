import logging
import socket
import socketserver
import requests
import gevent
import json
import os
import ipaddress
import random

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from chirpstack_api.as_pb import integration
from google.protobuf.json_format import Parse

from .base import TerrawareDevice, TerrawareHub

HTTP_LISTEN_PORT = 8090

# for now we assume a single ChirpStack hub object (done this way because the HTTPServer ctor doesn't let you pass an instance of the handler in,
# so we have no way to marshal a specific hub reference over to the other thread, so we cheat with this global var.)
hub_instance = None

class ChirpStackUplinkHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.end_headers()
        query_args = parse_qs(urlparse(self.path).query)

        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len)

        if query_args["event"][0] == "up":
            self.up(body)

        elif query_args["event"][0] == "join":
            self.join(body)

        else:
            print("handler for event %s is not implemented" % query_args["event"][0])

    def up(self, body):
        up = self.unmarshal(body, integration.UplinkEvent())
        print("Uplink received from: %s with payload: %s" % (up.dev_eui.hex(), up.data.hex()))
        hub_instance.process_uplink(up.dev_eui.hex(), up.data)

    def join(self, body):
        join = self.unmarshal(body, integration.JoinEvent())
        print("Device: %s joined with DevAddr: %s" % (join.dev_eui.hex(), join.dev_addr.hex()))

    def unmarshal(self, body, pl):
        return Parse(body, pl)

class ChirpStackHub(TerrawareHub):
    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        if self._diagnostic_mode:
            print('running ChirpStackHub in diagnostic mode')

        global hub_instance
        assert hub_instance is None
        hub_instance = self

        self.gateway_port = dev_info['port']
        self.gateway_ip = dev_info['address']
        self.expected_update_interval = None  # don't expect sensor updates for the hub itself, only connected devices
        
        self.application_id = 0
        self.api_token = "no token specified in config data"
        settings = dev_info.get('settings')
        if settings:
            self.application_id = settings.get('applicationId', 0)
            self.api_token = settings.get('apiToken', "no token specified in config data")

    def notify_all_devices_added(self):
        if self._local_sim:
            if self._diagnostic_mode:
                print('ChirpStackHub got notification all children added, spawning local simulation')
            gevent.spawn(self.sim)
        else:
            if self._diagnostic_mode:
                print('ChirpStackHub got notification all children added, spawning chirpstack listening service')
            gevent.spawn(self.run_chirpstack_listener)

    def run_chirpstack_listener(self):
        # Install this new HTTP server as the endpoint for uplink data from the chirpstack gateway
        ip_address = local_ip_address_visible_to_target(self.gateway_ip)
        if ip_address:
            self.cs_headers = {'Accept': 'application/json', 'Grpc-Metadata-Authorization': 'Bearer {}'.format(self.api_token)}
            self.cs_url = 'http://{}:{}/api/applications/{}/integrations/http'.format(self.gateway_ip, self.gateway_port, self.application_id)
            self.cs_install_body = json.dumps({
                'integration': {
                    'marshaler': 'JSON',
                    'uplinkDataURL': 'http://{}:{}/'.format(ip_address, HTTP_LISTEN_PORT),
                    'applicationID': "{}".format(self.application_id)
                }
            })
            print('ChirpStack Installing HTTP integration: url [{}], headers [{}], data [{}]'.format(self.cs_url, self.cs_headers, self.cs_install_body))
            try:
                r = requests.post(self.cs_url, headers=self.cs_headers, data=self.cs_install_body)
                print('ChirpStack Installed HTTP integration for {}, response {}'.format(self.cs_url, r.text))
                r = requests.put(self.cs_url, headers=self.cs_headers, data=self.cs_install_body)
                print('ChirpStack PUT HTTP integration for {}, response {}'.format(self.cs_url, r.text))
            except Exception as e:
                print ('ChirpStack failed to install HTTP integration for {}, error: {}'.format(self.cs_url, e))

            self.httpd = HTTPServer(('', HTTP_LISTEN_PORT), ChirpStackUplinkHandler)
            self.httpd.serve_forever()
        else:
            print('ChirpStack service FAILED to start!')

    # TODO - this should be invoked if the greenlet is ever stopped. Not 100% sure how to do that.    
#    def stop(self):
#        if self.httpd:
#            print('ChirpStack Deleting HTTP integration: url [{}], headers [{}], data [{}]'.format(self.cs_url, self.cs_headers, self.cs_uninstall_body))
#            try:
#                r = requests.delete(self.cs_url, headers=self.cs_headers)
#                print('ChirpStack deleted HTTP integration for {}, response {}'.format(self.cs_url, r.text))
#            except Exception as e:
#                print ('ChirpStack failed to delete HTTP integration for {}, error: {}'.format(self.cs_url, e))
#
#            self.httpd.stop()

    def sim(self):
        while True:
            if random.randint(0, 1):
                # Test sensecap soil sensor
                self.process_uplink('2cf7f12121000107', b'\x01\x07\x10\x72\x51\x00\x00')
                self.process_uplink('2cf7f12121000107', b'\x01\x06\x10\x00\x7d\x00\x00')
            else:
                # Test dragino soil sensor
                self.process_uplink('a84041e7b182a733', b'\x00\x00\x00\x00\x03\x10\xfd\x00\x04\x40\x00')
            gevent.sleep(5)

    def process_uplink(self, dev_eui: str, payload: bytes):
        sensor_address = dev_eui.lower()
        sensor = next((x for x in self.devices if x.address == sensor_address), None)
        if sensor:
            sensor.receive_payload(payload)
 
    #######################################
    # A bit inconsistent since the OmniSense driver has the hub return all the values, but this was set up to make it easier
    # to return values from the sensors themselves for the ChirpStack setup.
    def poll(self):
        return {}

    def reconnect(self):
        pass

    def get_timeseries_definitions(self):
        return []
    #######################################

# based on https://stackoverflow.com/questions/24196932/how-can-i-get-the-ip-address-from-nic-in-python
def local_ip_address_visible_to_target(target_ip_address):
    try:
        # Parse gateway address as ipv4 and break into 4 bytes
        target_ipv4 = ipaddress.IPv4Address(target_ip_address)
        target_ipv4_bytes = int(target_ipv4).to_bytes(4, 'big')
        
        # Query list of host machine ip addresses from balena supervisor API (it doesn't seem to give enough info to match
        # the addresses to network interfaces, unfortunately
        balena_supervisor_address = os.environ['BALENA_SUPERVISOR_ADDRESS']
        balena_supervisor_api_key = os.environ['BALENA_SUPERVISOR_API_KEY']
        r = requests.get('{}/v1/device?api'.format(balena_supervisor_address), params={'apikey': balena_supervisor_api_key})
        ip_addresses_string = r.json()['ip_address']
        ip_addresses = ip_addresses_string.split(' ')

        # Compare the addresses and find the one that matches the most bytes from the start of the gateway and assume
        # that's the one on the same interface as the gateway.
        best_ip = ''
        best_ip_bytes = 0
        for ip_address in ip_addresses:
            local_ipv4 = ipaddress.IPv4Address(ip_address)
            local_ipv4_bytes = int(local_ipv4).to_bytes(4, 'big')

            byte_index = 0
            while byte_index < 4 and local_ipv4_bytes[byte_index] == target_ipv4_bytes[byte_index]:
                byte_index += 1

            if byte_index > best_ip_bytes:
                best_ip_bytes = byte_index
                best_ip = ip_address

        print('Best host IP address was [{}], matching [{}] bytes of gateway address [{}]'.format(best_ip, best_ip_bytes, target_ip_address))
        return best_ip
    except Exception as e:
        print('ChirpStack failed to find local IP address to give to target gateway; exception [{}]'.format(e))


class LoRaSensor(TerrawareDevice):
    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)

        """Initialize the sensor."""
        self._address = dev_info['address']
        self._state = {}
        self._polling_interval = 10  # we don't actually poll these sensors; this just specifies how often the device manager retrieves values stored in this class

    def set_state(self, timeseries, value):
        self._state[(self.id, timeseries)] = value

    def reconnect(self):
        pass

    def poll(self):
        result = self._state
        self._state = {}
        return result

    @property
    def address(self):
        return self._address
    

##################################################################
### SENSECAP SOIL MOISTURE SENSOR (includes temperature too)   ###
##################################################################
# parse from SenseCap payload format:
#
# Temperature:
# 010610007D0000:
#   01 is the channel number.
#   0610 is 0x1006（little-endian byte order）, which is the measurement ID for soil temperature.
#   007D0000 is actually 0x00007D00, whose equivalent decimal value is 32000. Divide it by 1000, and you’ll get the
#            actual measurement value for Soil Temperature as 32.0℃.
#
# Moisture
# 01071072510000
#   01 is the channel number.
#   0710 is 0x1007（little-endian byte order）, which is the measurement ID for soil moisture. 
#   72510000 is actually 0x00005172, whose equivalent decimal value is 20850. Divide it by 1000, and 
#            you’ll get the actual measurement value for Soil Moisture as 20.85%
#
# Note: since this sensor sends separate uplinks for the temp & moisture payloads, both sensor types will get both,
# just ignore the payloads that aren't for us        
class SenseCapSoilSensor(LoRaSensor):
    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        self.expected_update_interval = 24 * 60 * 60  # expect at least one update a day

    def receive_payload(self, payload: bytearray):
        if payload[1] == 0x7 and payload[2] == 0x10:
            moisture_raw = int.from_bytes(payload[3:7], 'little', signed=False)
            moisture = float(moisture_raw) / 1000
            self.set_state('moisture', moisture)
            print('sensecap soil moisture set to {}'.format(moisture))
        elif payload[1] == 0x6 and payload[2] == 0x10:
            temperature_raw = int.from_bytes(payload[3:7], 'little', signed=True)
            temperature = float(temperature_raw) / 1000
            self.set_state('temperature', temperature)
            print('sensecap soil temperature set to {}'.format(temperature))

    def get_timeseries_definitions(self):
        return [[self.id, timeseries_name, 'Numeric', 2] for timeseries_name in ['temperature', 'moisture']]

#########################################################################
### DRAGINO SOIL MOISTURE SENSOR (includes temp & conductivity too)   ###
#########################################################################
# Dragino sensor payload spec:
# 2 bytes: battery voltage, in mV
# 2 bytes: reserved
# 2 bytes: soil moisture - dec 0-10,000, divide by 100 for percent
# 2 bytes: soil temperature - dec -4000 to +800, divide by 100 to get degrees C
# 2 bytes: soil conductivity - dev 0-20,000 (or greater, it says, strangely) - value is in uS/cm
# 1 byte: digital interrupt (optional)
class DraginoSoilSensor(LoRaSensor):
    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        self.expected_update_interval = 24 * 60 * 60  # expect at least one update a day

    def receive_payload(self, payload: bytes):
        moisture_raw = int.from_bytes(payload[4:6], 'big', signed=False)
        moisture = float(moisture_raw) / 100
        self.set_state('moisture', moisture)
        print('dragino soil moisture set to {}'.format(moisture))

        temperature_raw = int.from_bytes(payload[6:8], 'big', signed=True)
        temperature = float(temperature_raw) / 100
        self.set_state('temperature', temperature)
        print('dragino soil temperature set to {}'.format(temperature))

        conductivity_raw = int.from_bytes(payload[8:10], 'big', signed=False)
        conductivity = conductivity_raw
        self.set_state('conductivity', conductivity_raw)
        print('dragino soil conductivity set to {}'.format(conductivity))

    def get_timeseries_definitions(self):
        return [[self.id, timeseries_name, 'Numeric', 2] for timeseries_name in ['temperature', 'moisture', 'conductivity']]


class DraginoLeakSensor(LoRaSensor):

    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        self.expected_update_interval = 24 * 60 * 60  # expect at least one update a day

    def receive_payload(self, payload: bytes):
        if len(payload) == 10:
            batt_raw = ((payload[0] << 8) | payload[1]) & 0x3FFF
            batt_volts = batt_raw / 1000
            model = payload[2]
            if model == 2:
                leak_status = 1 if (payload[0] & 0x40) else 0
                leak_count = (payload[3] << 16) | (payload[4] << 8) | payload[5]
                leak_duration = (payload[6] << 16) | (payload[7] << 8) | payload[8]
                self.set_state('battery level', batt_volts)
                self.set_state('leak status', leak_status)
                self.set_state('total leak count', leak_count)
                self.set_state('total leak duration', leak_duration)  # minutes
                if self._diagnostic_mode:
                    print('batt: %.2f, status: %d, count: %d, minutes: %d' % (batt_volts, leak_status, leak_count, leak_duration))

    def get_timeseries_definitions(self):
        return [
            [self.id, 'battery level', 'Numeric', 3],
            [self.id, 'leak status', 'Numeric', 0],
            [self.id, 'total leak count', 'Numeric', 0],
            [self.id, 'total leak duration', 'Numeric', 0],
        ]


class BoveFlowSensor(LoRaSensor):

    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        self.expected_update_interval = 24 * 60 * 60  # expect at least one update a day

    def receive_payload(self, payload: bytes):
        message = payload.hex()
        if message.startswith('810a901f'):
            flow = int(payload[9:5:-1].hex())  # assuming simple binary coded decimal
            self.set_state('flow', flow)
            if self._diagnostic_mode:
                print('flow: %d' % flow)

    def get_timeseries_definitions(self):
        return [[self.id, timeseries_name, 'Numeric', 2] for timeseries_name in ['flow']]


# NOTE $BSHARP commenting this out for now - in the homeassistant driver I added this so Amy could see the raw hex string of the payload
# coming in from the dev board. But the device manager doesn't love string-valued timeseries (it's really only setup for scalar numeric ones right now)
# so I'm just commenting this out - but it should be easy to add later when there are more LoRa devices with paylods ready to decode.
#######################################
### LORA DEV BOARD STAND-IN SENSOR  ###
#######################################
# This is just a string-value sensor to show the payloads coming in from the dev board for debug visualization
# until we know what exactly we're doing with it and what sensor types it'll support etc etc etc
#class LoRaDevBoardRawPayloadSensor(LoRaSensor):
#    def receive_payload(self, payload: bytes):
#        self.set_state(payload.hex())
#        print('lora ray payload set to {}'.format(self.state))
#
#def add_lora_dev_board_raw_payload_sensor(hass, name, address):
#    return [
#        LoRaDevBoardRawPayloadSensor(hass, 'payload', name, address),
#    ]


if __name__ == '__main__':
    sensor = DraginoLeakSensor({'id': 1000, 'name': 'test', 'address': 'a840414aa1833eac'}, False, True, '')
    sensor.receive_payload(bytes.fromhex('4c180200010200030400'))
    sensor.receive_payload(bytes.fromhex('0c720200000100000000'))

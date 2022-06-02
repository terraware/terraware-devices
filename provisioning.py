import os
import sys
import json
import random
import yaml
from balena import Balena

# This script prepares an SD card for a device manager instance. See readme.md for usage instructions.

# get configuration
config = yaml.safe_load(open('provisioning.yaml'))
auth_token = config['auth_token']
fleet_name = config['fleet_name']
balena_os_version = config['balena_os_version']

# generate a short code
short_code = str(random.randint(100000, 999999))

# prepare API object
print('Authenticating using token: %s...%s' % (auth_token[:3], auth_token[-3:]))
balena = Balena()
balena.auth.login_with_token(auth_token)

# get fleet ID from name
fleets = balena.models.application.get_all()
fleet_id = None
for fleet in fleets:
    if fleet['app_name'] == fleet_name:
        fleet_id = fleet['id']
if fleet_id is None:
    print('fleet %s not found' % fleet_name)
    sys.exit(1)

# generate device UUID
device_uuid = balena.models.device.generate_uuid().decode()
print('Generated device UUID: %s...' % device_uuid[:6])

# register device
print('Registering device to fleet: %s' % fleet_name)
balena.models.device.register(fleet_id, device_uuid)
balena.models.device.rename(device_uuid, short_code)
balena.models.tag.device.set(device_uuid, 'short_code', short_code)

# generate config file for SD card
# TODO: can we just write the device UUID to the config file? would be nice to avoid specifying balena_os_version
print('Generating config file for SD card.')
os.system(f'balena config generate --version {balena_os_version} --network ethernet --appUpdatePollInterval 10 -d {device_uuid} -o balena-config.json')

# inject the config into the device
# TODO: test this; doesn't seem to work on windows; could resort to directly editing the config.json file on the SD card if needed
print('Copying config file to SD card.')
os.system('balena config inject balena-config.json')

# display short code for user
print('Short code: %s' % short_code)

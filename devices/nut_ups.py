import subprocess
import os.path
import re
from enum import Enum
from .base import TerrawareDevice, TerrawareHub

# Originally this was an enum but python enums don't auto-cast to numeric types very well and we store this
# as a timeseries so instead the sensor 'value' is an int and this is the list you import to convert them to strings
# for readable display.
UPS_ONLINE = 0
UPS_ON_BATTERY = 1
UPS_LOW_BATTERY = 2
UPS_UNKNOWN = 3
UPS_STATUS_NAMES = ['Online', 'On Battery', 'Low Battery', 'Unknown']

# We could use the existence of these files in init_ to decide we don't need to start the services if they're already running, but just in case they get
# hung or whatever, for now I just always kill them and restart them in init.
def shutdown_nut_server(verbose=False):
    if verbose:
        print('Shutting down NUT services')

    if os.path.exists('/var/run/nut/usbhid-ups-terrabrainups'):
        driver_shutdown = subprocess.run(['upsdrvctl', 'stop', 'terrabrainups'], stdout=subprocess.PIPE)
        if verbose:
            print('NUT UPS Driver Shutdown: %s' % driver_shutdown.stdout.decode('utf-8'))
    
    if os.path.exists('/var/run/nut/upsd.pid'):
        daemon_shutdown = subprocess.run(['upsd', '-c', 'stop'], stdout=subprocess.PIPE)
        if verbose:
            print('NUT Daemon Shutdown: %s' % daemon_shutdown.stdout.decode('utf-8'))


def init_nut_server(verbose=False):
    shutdown_nut_server(verbose)

    if verbose:
        print('Initializing NUT services')

    driver_startup = subprocess.run(['upsdrvctl', 'start', 'terrabrainups'], stdout=subprocess.PIPE)
    daemon_startup = subprocess.run(['upsd'], stdout=subprocess.PIPE)

    if verbose:
        print('NUT UPS Driver Startup: %s' % driver_startup.stdout.decode('utf-8'))
        print('NUT Daemon Startup: %s' % daemon_startup.stdout.decode('utf-8'))


def status_from_string(ups_status_string):
    # It looks like most NUT drivers support 'ups.status' and they may return an arbitrary string but it SEEMS that
    # they guarantee they contain the substring 'OL', 'OB', or 'LB', flanked by newline/eol/whitespace, so this assumes
    # that's true and sufficient to parse all this.
    result = UPS_UNKNOWN
    if re.match('(^|\s)OL($|\s)', ups_status_string):
        result = UPS_ONLINE 
    elif re.match('(^|\s)OB($|\s)', ups_status_string):
        result = UPS_ON_BATTERY
    elif re.match('(^|\s)LB($|\s)', ups_status_string):
        result = UPS_LOW_BATTERY

    return result

# If the supplied string is trivially convertible to an int it returns that int, otherwise it returns -1 for 
# "unknown" - probably NUT isn't running or isn't connected to a UPS.
def battery_charge_from_string(battery_charge_string):
    try:
        battery_charge = int(battery_charge_string)
        return battery_charge
    except ValueError:
        return -1

# Standard output from 'upsc terrabrainups@localhost' (for an APC Smart UPS 500 Lithium-Ion).
# You can pass any of these in fully and it will output only the value. For example, given the below,
# "upsc terrabrainups@localhost ups.status" would output to stdout only "OL CHRG"
#
# Notable is that 'ups.status' is the primary field we want and it will return 'OL', 'OB', or 'LB' 
# for "online", "on battery", or "low battery" and should be the primary signal we're using here to determine when 
# actions must be taken.
#
#battery.charge: 98
#battery.charge.low: 10
#battery.charge.warning: 50
#battery.runtime: 3600
#battery.runtime.low: 120
#battery.type: LION
#battery.voltage: 15.6
#battery.voltage.nominal: 12.0
#device.mfr: American Power Conversion 
#device.model: Smart-UPS 500
#device.serial: 5S2039T39752    
#device.type: ups
#driver.name: usbhid-ups
#driver.parameter.pollfreq: 30
#driver.parameter.pollinterval: 2
#driver.parameter.port: auto
#driver.parameter.synchronous: no
#driver.version: 2.7.4
#driver.version.data: APC HID 0.96
#driver.version.internal: 0.41
#ups.beeper.status: enabled
#ups.delay.shutdown: 20
#ups.firmware: UPS 02.3 / ID=1030
#ups.mfr: American Power Conversion 
#ups.mfr.date: 2020/09/24
#ups.model: Smart-UPS 500
#ups.productid: 0003
#ups.serial: 5S2039T39752    
#ups.status: OL CHRG
#ups.timer.reboot: -1
#ups.timer.shutdown: -1
#ups.vendorid: 051d

# Returns a list where the first value is the status enum (UpsStatus) and the second is the integer battery charge value (0-100)
# If the enum value is UpsStatus.unknown the battery charge value will be -1
def poll_upsc(device_id):
    ups_status_result = subprocess.run(['upsc', 'terrabrainups@localhost', 'ups.status'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    battery_charge_result = subprocess.run(['upsc', 'terrabrainups@localhost', 'battery.charge'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {(device_id, 'ups_status'    ): status_from_string(ups_status_result.stdout.decode('utf-8')), 
            (device_id, 'battery_charge'): battery_charge_from_string(battery_charge_result.stdout.decode('utf-8'))}

class NutUpsDevice(TerrawareDevice):

    def __init__(self, dev_info, local_sim, diagnostic_mode, spec_path):
        super().__init__(dev_info, local_sim, diagnostic_mode)

        if not self._local_sim:
            init_nut_server(True)
            # For testing
            print(poll_upsc(self.id))

    def get_timeseries_definitions(self):
        return [[self.id, timeseries_name, 'numeric', 2] for timeseries_name in ['ups_status', 'battery_charge']]

    def reconnect(self):
        pass

    def poll(self):
        if self._local_sim:
            return {(self.id, 'ups_status'    ): UPS_ONLINE, 
                    (self.id, 'battery_charge'): 89}
        
        return poll_upsc(self.id)


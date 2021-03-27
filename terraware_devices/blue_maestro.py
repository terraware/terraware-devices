import time
import subprocess
from .base import TerrawareDevice


# returns a list of currently accessible Blue Maestro devices; each device is returned as a dictionary of information
def find_blue_maestro_devices(iface=0, timeout=2, verbose=False, ubertooth=False):
    if ubertooth:
        return ubertooth_scan(iface, timeout, verbose)
    else:
        return standard_scan(iface, timeout, verbose)


# returns a list of currently accessible Blue Maestro devices; each device is returned as a dictionary of information
def ubertooth_scan(iface=0, timeout=10, verbose=False):
    proc = subprocess.Popen(['ubertooth-btle', '-U%d' % iface, '-n'], stdout=subprocess.PIPE)
    start_time = time.time()
    line_count = 0
    reading_count = 0
    device_infos = {}
    device_info = {}
    for line in iter(proc.stdout.readline, ''):
        line = line.decode().rstrip()
        line_count += 1
        done = process_ubertooth_line(line, device_info)
        if done and 'label' in device_info and 'temperature' in device_info and device_info['temperature'] < 100:
            reading_count += 1
            device_infos[device_info['label']] = device_info.copy()
            device_info = {}
        if time.time() - start_time > timeout:
            break
    proc.terminate()
    if verbose:
        print('processed %d lines' % line_count)
        print('found %d readings' % reading_count)
        print('found %d sensors' % len(device_infos))
    return list(device_infos.values())  # want to return a list, not a dictionary


# processes a line of output from ubertooth-btle;
# updates fields in device_info dictionary; returns True if device_info is for a Blue Maestro device;
# note that between Blue Maestro devices, device_info will get updated with info from other devices (to be overwritten with next Blue Maestro reading)
def process_ubertooth_line(line, device_info):
    line = line.strip()
    if line.startswith('systime'):
        parts = line.split()
        for part in parts:
            if part.startswith('rssi'):
                device_info['rssi'] = part.split('=')[1]
    elif line.startswith('AdvA:'):
        parts = line.split()
        device_info['label'] = parts[-2].replace(':', '').upper()
    elif line.startswith('AdvData:'):
        parts = line.split()
        if len(parts) >= 18:
            device_info['temperature'] = int(parts[14] + parts[15], 16) * 0.1
            device_info['humidity'] = int(parts[16] + parts[17], 16) * 0.1
    elif line == 'Company: Blue Maestro Limited':
        return True


# returns a list of currently accessible Blue Maestro devices; each device is returned as a dictionary of information
def standard_scan(iface=0, timeout=2, verbose=False):
    from bluepy import btle  # importing here for now so that we can test device manager code on systems without bluepy installed
    btle.Debugging = verbose
    scanner = btle.Scanner(iface)
    try:
        devices = scanner.scan(timeout)
    except btle.BTLEDisconnectError:  # seems to occur sometimes if the timeout is too long
        print('BTLE disconnect error')
        devices = []
    dev_infos = []
    for d in devices:
        manufacturer = d.getValueText(255)
        if manufacturer and manufacturer.startswith('3301'):
            label = d.getValueText(9)
            if label and len(d.rawData) > 17:
                rssi = d.rssi
                vals = d.rawData
                temperature = (vals[13] * 256 + vals[14]) * 0.1
                humidity = (vals[15] * 256 + vals[16]) * 0.1
                if temperature < 100 and humidity < 100:
                    dev_info = {
                        'label': label,
                        'rssi': d.rssi,
                        'temperature': temperature,
                        'humidity': humidity,
                    }
                    dev_infos.append(dev_info)
    return dev_infos


class BlueMaestroDevice(TerrawareDevice):

    def __init__(self, label):
        self._label = label  # ID from the sticker on the blue maestro device
        print('created BlueMaestroDevice with label %s' % label)

    def label(self):
        return self._label

    def reconnect(self):
        pass

    def poll(self):  # polling for Blue Maestro devices is handled in device manager (update_bluetooth_devices)
        return {}


if __name__ == "__main__":
    dev_infos = find_blue_maestro_devices()
    for d in dev_infos:
        print('label: %s, rssi: %d, t: %.1f, h: %.1f' % (d['label'], d['rssi'], d['temperature'], d['humidity']))

from bluepy import btle


# returns a list of currently accessible Blue Maestro devices; each device is returned as a dictionary of information
def find_blue_maestro_devices(iface=0, timeout=2, verbose=False):
    btle.Debugging = verbose
    scanner = btle.Scanner(iface)
    devices = scanner.scan(timeout)
    dev_infos = []
    for d in devices:
        manufacturer = d.getValueText(255)
        if manufacturer and manufacturer.startswith('3301'):
            label = d.getValueText(9).decode()
            if label and len(d.rawData) > 17:
                rssi = d.rssi
                vals = [ord(v) for v in d.rawData]
                dev_info = {
                    'label': label,
                    'rssi': d.rssi,
                    'temperature': (vals[13] * 256 + vals[14]) * 0.1,
                    'humidity': (vals[15] * 256 + vals[16]) * 0.1,
                }
                dev_infos.append(dev_info)
    return dev_infos


if __name__ == "__main__":
    dev_infos = find_blue_maestro_devices()
    for d in dev_infos:
        print('label: %s, rssi: %d, t: %.1f, h: %.1f' % (d['label'], d['rssi'], d['temperature'], d['humidity']))

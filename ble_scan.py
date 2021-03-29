import sys
from terraware_devices.blue_maestro import find_blue_maestro_devices


# a simple script for running a blue maestro scan


def run_scan():
    print('running blue maestro scan')
    device_infos = find_blue_maestro_devices(timeout=10, iface=0, verbose=True, ubertooth=True)
    rssi = []
    for device_info in device_infos:
        rssi.append(float(device_info['rssi']))
    print('mean RSSI: %.2f' % (sum(rssi) / len(rssi)))


if __name__ == '__main__':
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print('doing %d scan(s)' % count)
    for i in range(count):
        run_scan()

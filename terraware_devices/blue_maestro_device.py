from .base import TerrawareDevice


# returns a list of currently accessible Blue Maestro devices; each device is returned as a dictionary of information
def find_blue_maestro_devices(iface=0, timeout=2, verbose=False):
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

    def __init__(self, server_path, label):
        self._server_path = server_path
        self._label = label  # ID from the sticker on the blue maestro device

        # most recent values
        self._timestamp = None
        self._temperature = None
        self._humidity = None
        self._rssi = None

    def server_path(self):
        return self._server_path

    def label(self):
        return self._label

    def update(self, timestamp, temperature, humidity, rssi):
        self._timestamp = timestamp
        self._temperature = temperature
        self._humidity = humidity
        self._rssi = rssi

    def reconnect(self):
        pass

    def run(self):
        pass


if __name__ == "__main__":
    dev_infos = find_blue_maestro_devices()
    for d in dev_infos:
        print('label: %s, rssi: %d, t: %.1f, h: %.1f' % (d['label'], d['rssi'], d['temperature'], d['humidity']))

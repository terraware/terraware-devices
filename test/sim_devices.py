import csv
import time
import random
from pyModbusTCP.server import ModbusServer, DataBank


def run_modbus_server(host, port):
    print('starting modbus server at %s:%d' % (host, port))
    server = ModbusServer(host=host, port=port, no_block=True)
    server.start()
    DataBank.set_words(0, [0] * 100)
    while True:
        DataBank.set_words(0x39, [random.randint(1, 10), 0])
        DataBank.set_words(0x41, [random.randint(1, 10), 0])
        DataBank.set_words(0x4b, [random.randint(1, 10), 0])
        DataBank.set_words(0x50, [random.randint(1, 10), 0])
        time.sleep(1)


if __name__ == "__main__":
    with open('../config/sim_devices.csv') as csvfile:
        lines = csv.DictReader(csvfile)
        for line in lines:
            if int(line['enabled']):
                run_modbus_server(line['host'], int(line['port']))
                break  # only run one server for now

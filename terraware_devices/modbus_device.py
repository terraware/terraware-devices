import csv
import time
import random
import logging
from typing import Optional

import gevent
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.transaction import ModbusRtuFramer, ModbusSocketFramer

from .base import TerrawareDevice


class ModbusDevice(TerrawareDevice):

    def __init__(self, controller, server_path, host, port, settings, polling_interval, diagnostic_mode):
        settings_items = settings.split(';')
        self._controller = controller
        self._server_path = server_path
        self._polling_interval = polling_interval
        self._host = host
        self._unit = 1  # aka modbus slave number
        for setting in settings_items:
            if setting.startswith('unit='):
                self._unit = int(setting.split('=')[1])
        print('initializing device %s (%s:%d, unit: %d)' % (server_path, host, port, self._unit))
        self.last_update_time = None
        self._diagnostic_mode = diagnostic_mode
        framer = ModbusRtuFramer if ('rtu-over-tcp' in settings_items) else ModbusSocketFramer
        self._modbus_client = ModbusTcpClient(host, port=port, framer=framer)
        self._read_holding = ('holding' in settings_items)
        self._seq_infos = []

        # load seqeuence info
        with open('config/%s.csv' % server_path) as csvfile:
            lines = csv.DictReader(csvfile)
            for line in lines:
                self._seq_infos.append(line)

    def server_path(self):
        return self._server_path

    def reconnect(self):
        self._modbus_client.connect()

    def run(self):
        logging.info('starting modbus monitoring/control for %s; polling interval: %.1fs', self._server_path, self._polling_interval)
        if self._host != 'sim':
            self._modbus_client.connect()
        while True:
            if self._host != 'sim' and not self._modbus_client.is_socket_open():
                self._modbus_client.connect()
            seq_values = {}
            for seq_info in self._seq_infos:
                address = int(seq_info['address'], 0)
                value = self.read_register(address, seq_info['type'], self._unit)
                if value is not None:
                    value *= float(seq_info['scale_factor'])
                    seq_rel_path = self._server_path + '/' + seq_info['name']
                    full_seq_name = self._controller.path_on_server() + '/' + seq_rel_path
                    if self._diagnostic_mode:
                        print('    %s: %.2f' % (seq_rel_path, value))
                    self._controller.sequences.update_value(seq_rel_path, value)
                    if int(seq_info['send_to_server']):
                        self._controller.sequence.create(seq_rel_path, 'numeric', decimal_places=2)
                        seq_values[full_seq_name] = value
            if seq_values:
                self._controller.sequences.update_multiple(seq_values)
                self.last_update_time = time.time()
            print('received %d value(s) from %s' % (len(seq_values), self._server_path))
            gevent.sleep(self._polling_interval)

    def read_register(self, address, register_type, unit):
        if self._host == 'sim':
            return random.randint(1, 100)
        if register_type.endswith('32'):
            count = 2
        else:
            count = 1
        if self._read_holding:
            result = self._modbus_client.read_holding_registers(address, count, unit=unit)
        else:
            result = self._modbus_client.read_input_registers(address, count, unit=unit)
        if not hasattr(result, 'registers'):
            return None
        if register_type == 'uint16':
            return result.registers[0]
        elif register_type == 'sint16':
            v = result.registers[0]
            if v > 0x7fff:  # rough sign manipulation; should check/fix
                v = v - 0x10000
            return v
        elif register_type == 'uint32':
            return result.registers[0] * 0x10000 + result.registers[1]
        elif register_type == 'sint32':
            v = result.registers[0] * 0x10000 + result.registers[1]
            if v > 0x7fffffff:  # rough sign manipulation; should check/fix
                v = v - 0x100000000
            return v

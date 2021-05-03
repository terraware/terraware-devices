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

    def __init__(self, host, port, settings, diagnostic_mode, local_sim, spec_file_name):
        settings_items = settings.split(';')
        self._host = host
        self._unit = 1  # aka modbus slave number
        for setting in settings_items:
            if setting.startswith('unit='):
                self._unit = int(setting.split('=')[1])
        self.last_update_time = None
        self._diagnostic_mode = diagnostic_mode
        framer = ModbusRtuFramer if ('rtu-over-tcp' in settings_items) else ModbusSocketFramer
        self._modbus_client = ModbusTcpClient(host, port=port, framer=framer)
        self._read_holding = ('holding' in settings_items)
        self._seq_infos = []
        self._local_sim = local_sim

        # load seqeuence info
        with open(spec_file_name) as csvfile:
            lines = csv.DictReader(csvfile)
            for line in lines:
                self._seq_infos.append(line)

        print('created modbus device (%s:%d, unit: %d)' % (host, port, self._unit))

    def reconnect(self):
        self._modbus_client.close()
        gevent.sleep(0.5)
        self._modbus_client.connect()

    def poll(self):
        if (not self._local_sim) and (not self._modbus_client.is_socket_open()):
            self._modbus_client.connect()
        values = {}
        for seq_info in self._seq_infos:
            address = int(seq_info['address'], 0)
            value = self.read_register(address, seq_info['type'], self._unit)
            if value is not None:
                value *= float(seq_info['scale_factor'])
                values[seq_info['name']] = value
                if self._diagnostic_mode:
                    print('    %s/%s: %.2f' % (self.server_path, seq_info['name'], value))
#                if int(seq_info['send_to_server']):
#                    self._controller.sequence.create(seq_rel_path, 'numeric', decimal_places=2)
#                    seq_values[full_seq_name] = value
        if values:
            self.last_update_time = time.time()
        print('received %d of %d value(s) from %s' % (len(values), len(self._seq_infos), self.server_path))
        if len(values) != len(self._seq_infos):
            print('received fewer values than expected; reconnecting')
            self.reconnect()
            values = {}  # when this happens, we seem to get corrupt data; don't want to store that
        return values

    def read_register(self, address, register_type, unit):
        if self._local_sim:
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
        if register_type == 'uint16' and len(result.registers) >= 1:
            return result.registers[0]
        elif register_type == 'sint16' and len(result.registers) >= 1:
            v = result.registers[0]
            if v > 0x7fff:  # rough sign manipulation; should check/fix
                v = v - 0x10000
            return v
        elif register_type == 'uint32' and len(result.registers) >= 2:
            return result.registers[0] * 0x10000 + result.registers[1]
        elif register_type == 'sint32' and len(result.registers) >= 2:
            v = result.registers[0] * 0x10000 + result.registers[1]
            if v > 0x7fffffff:  # rough sign manipulation; should check/fix
                v = v - 0x100000000
            return v
        else:
            return None

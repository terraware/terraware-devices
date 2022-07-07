import csv
import time
import random
import logging
import pathlib
from typing import Optional

import gevent
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.transaction import ModbusRtuFramer, ModbusSocketFramer

from .base import TerrawareDevice, TerrawareHub


class ModbusDevice(TerrawareDevice):

    def __init__(self, dev_info, local_sim, diagnostic_mode, load_spec=True):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        self._host = dev_info["address"]
        self._unit = 1  # aka modbus slave number
        self._polling_interval = 60

        self._read_holding = False
        rtu_over_tcp = False
        settings_items = dev_info.get('settings')
        if settings_items:
            if settings_items.get("unit"):
                self._unit = settings_items["unit"]
            rtu_over_tcp = settings_items.get('rtu-over-tcp', False)
            self._read_holding = settings_items.get('holding', False)

        framer = ModbusRtuFramer if rtu_over_tcp else ModbusSocketFramer

        port = dev_info["port"]
        self._modbus_client = ModbusTcpClient(self._host, port=port, framer=framer)
        self._seq_infos = []

        # load register info for this device make/model
        if load_spec:
            spec_path = str(pathlib.Path(__file__).parent.absolute()) + '/../specs'
            spec_file_name = spec_path + '/' + dev_info['make'] + '_' + dev_info['model'] + '.csv'
            with open(spec_file_name) as csvfile:
                lines = csv.DictReader(csvfile)
                for line in lines:
                    self._seq_infos.append(line)

        print('created modbus device (%s:%d, unit: %d)' % (self._host, port, self._unit))

    def get_timeseries_definitions(self):
        return [[self.id, sequence['name'], 'Numeric', 2] for sequence in self._seq_infos]

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
                values[(self.id, seq_info['name'])] = value
                if self._diagnostic_mode:
                    print('    (%s, %s): %.2f' % (self.id, seq_info['name'], value))
        if self._diagnostic_mode:
            print('received %d of %d value(s) from %s' % (len(values), len(self._seq_infos), self._host))
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

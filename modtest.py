from optparse import OptionParser
from devices.modbus import ModbusDevice


# a modbus testing tool


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-a", "--address", dest="address",
                      help="IP address of modbus device")
    parser.add_option("-p", "--port", dest="port", default=502,
                      help="port number")
    parser.add_option("-u", "--unit", dest="unit", default=1,
                      help="unit number (aka slave number)")
    parser.add_option("-r", "--register", dest="register",
                      help="register number/address")
    parser.add_option("-t", "--type", dest="data_type", default='uint16',
                      help="register data type (uint16, sint16, uint32, or sint32)")
    parser.add_option("-R", "--rtu", action="store_true", dest="rtu", default=False,
                      help="use RTU over TCP mode")
    parser.add_option("-H", "--holding", action="store_true", dest="holding", default=False,
                      help="use holding registers")
    (options, args) = parser.parse_args()
    if options.address:
        device_info = {
            'id': 1,
            'name': 'test',
            'facilityId': 0,
            'address': options.address,
            'port': int(options.port),
            'settings': {
                'unit': int(options.unit),
                'holding': int(options.holding),
                'rtu-over-tcp': int(options.rtu),
            },
            'verbosity': 1
        }
        try:
            device = ModbusDevice(device_info, load_spec=False)
            value = device.read_register(int(options.register), options.data_type, int(options.unit))
            print('value: %s' % value)
        except Exception as e:
            print(e)
    else:
        parser.print_help()

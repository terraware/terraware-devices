from optparse import OptionParser
from terraware_devices.device_manager import DeviceManager


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-u", "--upload_devices", action="store_true", dest="upload_devices", default=False,
                      help="upload device specs from local JSON file to back end server")
    d = DeviceManager()
    (options, args) = parser.parse_args()
    if options.upload_devices:
        device_infos = d.load_device_config()
        id_map = {}
        no_parent_count = 0
        has_parent_count = 0
        for device_info in device_infos:
            if not 'parentId' in device_info:  # first create devices without parents
                new_device_id = d.send_device_definition_to_server(device_info)
                id_map[device_info['id']] = new_device_id
                no_parent_count += 1
        for device_info in device_infos:
            if 'parentId' in device_info:  # first create devices without parents
                device_info['parentId'] = id_map[device_info['parentId']]
                d.send_device_definition_to_server(device_info)
                has_parent_count += 1
        print('created %d devices without parents and %d device with parents' % (no_parent_count, has_parent_count))
    else:
        d.create_devices(d.load_device_config())
        d.run()

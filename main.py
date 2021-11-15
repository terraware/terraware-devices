import json
from optparse import OptionParser
from terraware_devices.device_manager import DeviceManager


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-g", "--get_devices", action="store_true", dest="get_devices", default=False,
                      help="get device specs from back end server")
    parser.add_option("-d", "--upload_devices", action="store_true", dest="upload_devices", default=False,
                      help="upload device specs from local JSON file to back end server")
    parser.add_option("-a", "--upload_automations", dest="upload_automations",
                      help="upload facility automations from local JSON file to back end server")
    d = DeviceManager()
    (options, args) = parser.parse_args()
    if options.get_devices:
        device_infos = d.load_device_config()  # assumes no local file set in environment variable
        open('devices.json', 'w').write(json.dumps({'devices': device_infos}, indent=2))
    elif options.upload_devices:
        device_infos = d.load_device_config()
        no_parent_count = 0
        has_parent_count = 0
        for device_info in device_infos:
            if not 'parentId' in device_info:  # first create devices without parents
                if 'id' in device_info:
                    device_id = device_info['id']
                    d.update_device_definition_on_server(device_info)
                else:
                    device_id = d.send_device_definition_to_server(device_info)
                no_parent_count += 1
        for device_info in device_infos:
            if 'parentId' in device_info:  # first create devices without parents
                if 'id' in device_info:
                    d.update_device_definition_on_server(device_info)
                else:
                    d.send_device_definition_to_server(device_info)
                has_parent_count += 1
        print('created/updated %d devices without parents and %d device with parents' % (no_parent_count, has_parent_count))
    elif options.upload_automations:
        automations = json.loads(open(options.upload_automations).read())
        print('loaded %d automations from %s' % (len(automations), options.upload_automations))
        for automation in automations:
            if 'id' in automation:
                d.update_automation_on_server(automation)
            else:
                d.create_automation_on_server(automation)
    else:
        d.create_devices(d.load_device_config())
        d.create_automations(d.load_automations())
        d.run()

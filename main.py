import json
from optparse import OptionParser
from device_manager import DeviceManager


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-g", "--get_facility_info", action="store_true", dest="get_facility_info", default=False,
                      help="get device specs and automations from back end server")
    parser.add_option("-d", "--upload_devices", dest="upload_devices",
                      help="upload device specs from local JSON file to back end server")
    parser.add_option("-a", "--upload_automations", dest="upload_automations",
                      help="upload facility automations from local JSON file to back end server")
    parser.add_option("-r", "--remove_device", dest="remove_device",
                      help="delete the specified device")
    d = DeviceManager()
    (options, args) = parser.parse_args()
    if options.get_facility_info:
        device_infos = d.load_device_config()  # assumes no local file set in environment variable
        automations = d.load_automations()
        facility_info = {
            'devices': device_infos,
            'automations': automations
        }
        open('data.json', 'w').write(json.dumps(facility_info, indent=2))
    elif options.upload_devices:
        device_infos = json.loads(open(options.upload_devices).read())['devices']
        print('loaded %d device(s) from %s' % (len(device_infos), options.upload_devices))
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
        print('created/updated %d device(s) without parents and %d device(s) with parents' % (no_parent_count, has_parent_count))
    elif options.upload_automations:
        automations = json.loads(open(options.upload_automations).read())['automations']
        print('loaded %d automation(s) from %s' % (len(automations), options.upload_automations))
        for automation in automations:
            if 'id' in automation:
                d.update_automation_on_server(automation)
            else:
                d.create_automation_on_server(automation)
    elif options.remove_device:
        d.delete_device_definition_on_server(options.remove_device)
    else:
        d.create_devices(d.load_device_config())
        d.create_automations(d.load_automations())
        d.run()

from optparse import OptionParser
from terraware_devices.device_manager import DeviceManager


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-u", "--upload_devices", action="store_true", dest="upload_devices", default=False,
                      help="upload device specs from local JSON file to back end server")
    d = DeviceManager()
    (options, args) = parser.parse_args()
    if options.upload_devices:
        pass
    else:
        d.run()

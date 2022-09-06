import time
from abc import ABC, abstractmethod
from typing import Optional


class TerrawareDevice(ABC):
    """Base class for device implementations."""

    last_update_time: Optional[float] = None
    """What time the device was last updated."""

    @abstractmethod
    def get_timeseries_definitions(self) -> None:
        """This method should return a list of timeseries definitions, where each definition is a 4-tuple (another list), containing:
            [device id, timeseries name, data type, decimal places] """
        ...

    @abstractmethod
    def reconnect(self) -> None:
        """Reconnect to the device. Will be called by the device manager if no recent readings from the device."""
        ...

    @abstractmethod
    def poll(self) -> dict:
        """Return a dictionary of values obtained from the hardware. Will be called by the device manager to obtain device data.
        The dictionary should map from the tuple (device id, timeseries name) to the timeseries value. The device id does not need
        to be the id of this device, for hubs that return the timeseries values of their child devices."""
        ...

    def __init__(self, dev_info):
        self._id = dev_info["id"]
        self._name = dev_info["name"]
        self.facility_id = dev_info['facilityId']
        self.last_update_time = time.time()  # used for watchdog; don't know when last update was on startup
        self.expected_update_interval = 5 * 60  # used for watchdog
        self._polling_interval = None  # we won't poll the device unless the device class specifies a polling interval

        self._local_sim = False
        if 'settings' in dev_info:
            settings = dev_info['settings']
            if 'local_sim' in settings:
                self._local_sim = settings['local_sim']

        self._verbosity = dev_info.get("verbosity", 0)
        self._parent_id = dev_info.get("parentId")

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def parent_id(self):
        return self._parent_id

    @property
    def polling_interval(self):
        return self._polling_interval

    def set_local_sim(self, local_sim):
        self._local_sim = local_sim

    def set_polling_interval(self, polling_interval):
        self._polling_interval = polling_interval


class TerrawareHub(TerrawareDevice):

    def __init__(self, dev_info):
        super().__init__(dev_info)
        self._devices = []

    def add_device(self, device):
        if device.parent_id != self.id:
            print('Error: Trying to add device {} with parent_id {} to device {} with id {}, parent_id and id should match!'.format(device.name, device.parent_id, self.name, self.id))
        else:
            self._devices.append(device)

    @property
    def devices(self):
        return self._devices

    def notify_all_devices_added(self):
        # This is called after all child sensors are added to a hub so you can e.g. start a listener service to get sensor data.
        ...

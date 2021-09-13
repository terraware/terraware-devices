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

    def set_server_path(self, path: str) -> None:
        """Sets the path of this device on the server (relative to the site)."""
        self.server_path = path

    def set_polling_interval(self, polling_interval: float) -> None:
        """Sets the time between polling calls, in seconds."""
        self.polling_interval = polling_interval

    def __init__(self, dev_info, local_sim, diagnostic_mode):
        self._id = dev_info["id"]
        self._name = dev_info["name"]
        self._local_sim = local_sim
        self._diagnostic_mode = diagnostic_mode
        self._hub_id = dev_info.get("hubId")

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def diagnostic_mode(self):
        return self._diagnostic_mode

    @property
    def server_path(self):
        return self._server_path

    @property
    def hub_id(self):
        return self._hub_id
    
    
class TerrawareHub(TerrawareDevice):

    def __init__(self, dev_info, local_sim, diagnostic_mode):
        super().__init__(dev_info, local_sim, diagnostic_mode)
        self._devices = []

    def add_device(self, device):
        if device.hub_id != self.id:
            print('Error: Trying to add device {} with hub_id {} to device {} with id {}, hub_id and id should match!'.format(device.name, device.hub_id, self.name, self.id))
        else
            self._devices.append(device)

    @property
    def devices(self):
        return self._devices
    
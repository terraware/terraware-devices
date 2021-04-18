from abc import ABC, abstractmethod
from typing import Optional


class TerrawareDevice(ABC):
    """Base class for device implementations."""

    last_update_time: Optional[float] = None
    """What time the device was last updated."""

    @abstractmethod
    def reconnect(self) -> None:
        """Reconnect to the device. Will be called by the device manager if no recent readings from the device."""
        ...

    @abstractmethod
    def poll(self) -> dict:
        """Return a dictionary of values obtained from the hardware. Will be called by the device manager to obtain device data."""
        ...

    def set_server_path(self, path: str) -> None:
        """Sets the path of this device on the server (relative to the site)."""
        self.server_path = path

    def set_polling_interval(self, polling_interval: float) -> None:
        """Sets the time between polling calls, in seconds."""
        self.polling_interval = polling_interval

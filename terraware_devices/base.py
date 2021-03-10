from abc import ABC, abstractmethod
from typing import Optional


class TerrawareDevice(ABC):
    """Base class for device implementations."""

    last_update_time: Optional[float] = None
    """What time the device was last updated."""

    @abstractmethod
    def reconnect(self) -> None:
        """Reconnect to the device."""
        ...

    @abstractmethod
    def poll(self) -> dict:
        """Return a dictionary of values obtained from the hardware."""
        ...

    def set_server_path(self, path: str) -> None:
        self.server_path = path

    def set_polling_interval(self, polling_interval: float) -> None:
        self.polling_interval = polling_interval

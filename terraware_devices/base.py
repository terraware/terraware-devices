from abc import ABC, abstractmethod
from typing import Optional


class TerrawareDevice(ABC):
    """Base class for device implementations."""

    last_update_time: Optional[float] = None
    """What time the device was last updated."""

    @abstractmethod
    def run(self) -> None:
        """Main loop for this device.

        This method is run in a greenlet and should not return. It should use gevent to perform blocking operations.
        """
        ...

    @abstractmethod
    def reconnect(self) -> None:
        """Reconnect to the device."""
        ...

    @abstractmethod
    def server_path(self) -> str:
        """Return the server-side path of this device."""
        ...

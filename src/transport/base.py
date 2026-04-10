"""Transport layer abstract interface."""

from abc import ABC, abstractmethod
from typing import Any, Callable


class Transport(ABC):
    """Abstract base for broker-to-broker communication."""

    @abstractmethod
    async def start(self):
        """Start listening for incoming connections and connect to known peers."""

    @abstractmethod
    async def stop(self):
        """Shut down all connections."""

    @abstractmethod
    async def send(self, machine_id: str, message: dict):
        """Send a message to a specific remote broker identified by machine_id."""

    @abstractmethod
    async def broadcast(self, message: dict):
        """Send a message to all connected remote brokers."""

    @abstractmethod
    def on_message(self, callback: Callable[[str, dict], Any]):
        """Register a callback for incoming messages.

        callback(machine_id: str, message: dict)
        """

    @abstractmethod
    def connected_peers(self) -> list[str]:
        """Return list of connected remote machine_ids."""

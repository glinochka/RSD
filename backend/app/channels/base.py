"""Base class for channel managers."""
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class ChannelManager(ABC):
    """
    Abstract base class for all channel managers (Telegram userbot, WhatsApp userbot, etc.)
    
    Each channel manager:
    - Manages connections/sessions for a specific channel type
    - Polls for or receives incoming messages
    - Routes messages to MessageProcessor
    - Handles channel-specific configuration
    """

    @abstractmethod
    async def run_forever(self) -> None:
        """
        Main loop: run the channel manager indefinitely.
        
        Should:
        - Poll or listen for messages
        - Handle reconnection on failure
        - Stop when shutdown() is called
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Gracefully shutdown the channel manager.
        
        Should:
        - Cancel running tasks
        - Close connections
        - Clean up resources
        """
        pass

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Return human-readable channel name."""
        pass

    @property
    @abstractmethod
    def active_count(self) -> int:
        """Return number of active connections/sessions."""
        pass

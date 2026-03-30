from typing import Protocol

from domain import User


class UserRepository(Protocol):
    """Contract for persisting domain users."""

    # Output port for persisting users without coupling the domain
    # to a specific database.
    def save_user(self, user: User) -> None: ...

    def update_user_status(self, user_id: int, status: str) -> None: ...


class SettingsRepository(Protocol):
    """Contract for reading bot configuration."""

    # Allows reading dynamic bot configuration from any source.
    def get_value(self, key: str) -> str: ...


class MessagingService(Protocol):
    """Contract for sending messages to the end user."""

    # Abstracts the delivery channel so the use case does not depend on Telegram.
    async def send_message(self, chat_id: int, text: str) -> None: ...

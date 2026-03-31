from datetime import datetime
from typing import Protocol

from domain import PostRaceBriefing, Session, User


class UserRepository(Protocol):
    """Contract for persisting domain users."""

    # Output port for persisting users without coupling the domain
    # to a specific database.
    def get_user(self, user_id: int) -> User | None: ...

    def save_user(self, user: User) -> None: ...

    def update_user_status(self, user_id: int, status: str) -> None: ...
    
    def update_user_timezone(self, user_id: int, timezone: str) -> None: ...

    def list_active_users(self) -> list[User]: ...


class SettingsRepository(Protocol):
    """Contract for reading bot configuration."""

    # Allows reading dynamic bot configuration from any source.
    def get_value(self, key: str) -> str: ...


class MessagingService(Protocol):
    """Contract for sending messages to the end user."""

    # Abstracts the delivery channel so the use case does not depend on Telegram.
    async def send_message(self, chat_id: int, text: str) -> None: ...

    async def send_country_options(
        self,
        chat_id: int,
        text: str,
        options: list[list[dict[str, str]]],
    ) -> None: ...

    async def send_subscribe_prompt(
        self,
        chat_id: int,
        text: str,
        button_text: str,
        callback_data: str,
    ) -> None: ...

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str,
    ) -> None: ...

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
    ) -> None: ...


class SessionProvider(Protocol):
    """Contract for retrieving the next upcoming session from any source."""

    def get_next_session_after(self, when: datetime) -> Session | None: ...

    def get_post_race_briefing(self, when: datetime) -> PostRaceBriefing | None: ...

    def get_source_name(self) -> str: ...

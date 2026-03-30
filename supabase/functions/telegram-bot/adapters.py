# pyright: reportMissingImports=false, reportMissingModuleSource=false

import logging

from telegram.ext import Application
from supabase import Client, create_client

from domain import User


logger = logging.getLogger(__name__)


class SupabaseAdapter:
    """Implement persistence and settings reads using Supabase."""

    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        self.client: Client = create_client(supabase_url, supabase_key)

    def save_user(self, user: User) -> None:
        """Insert a user or refresh profile data without resetting the status."""

        existing_status = self._get_user_status(user.user_id)
        record = user.to_record()
        if existing_status is not None:
            record["status"] = existing_status

        # Upsert avoids duplicates when the same user runs /start again.
        logger.info("Upserting user user_id=%s", user.user_id)
        self.client.table("users").upsert(
            record,
            on_conflict="user_id",
        ).execute()

    def _get_user_status(self, user_id: int) -> str | None:
        """Return the current status for an existing user, if present."""

        logger.info("Fetching current user status user_id=%s", user_id)
        response = self.client.table("users").select("status").eq("user_id", user_id).limit(1).execute()
        response_data: object = response.data
        if not isinstance(response_data, list) or len(response_data) == 0:
            return None

        first_row = response_data[0]
        if not isinstance(first_row, dict):
            return None

        status = first_row.get("status")
        return status if isinstance(status, str) else None

    def update_user_status(self, user_id: int, status: str) -> None:
        """Update the user's status if the row already exists."""

        logger.info("Updating user status user_id=%s status=%s", user_id, status)
        self.client.table("users").update({"status": status}).eq("user_id", user_id).execute()

    def get_value(self, key: str) -> str:
        """Get a required bot setting or fail when it does not exist."""

        # Validate the response shape because the SDK exposes `data`
        # with a broad type and does not always guarantee content.
        logger.info("Fetching bot setting key=%s", key)
        response = self.client.table("bot_settings").select("value").eq("key", key).execute()
        response_data: object = response.data
        if not isinstance(response_data, list) or len(response_data) == 0:
            raise ValueError(f"Missing bot setting: {key}")

        first_row = response_data[0]
        if not isinstance(first_row, dict):
            raise ValueError(f"Invalid bot setting row for key: {key}")

        value = first_row.get("value")
        if isinstance(value, str):
            return value

        raise ValueError(f"Invalid bot setting value for key: {key}")


class TelegramAdapter:
    """Wrap the Telegram client used to send bot messages."""

    def __init__(self, bot_token: str) -> None:
        self.app = Application.builder().token(bot_token).build()

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a simple message to a Telegram chat."""

        logger.info("Sending Telegram message chat_id=%s", chat_id)
        await self.app.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
        )

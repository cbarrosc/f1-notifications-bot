# pyright: reportMissingImports=false, reportMissingModuleSource=false

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from telegram import Update

from adapters import SupabaseAdapter, TelegramAdapter
from application import TelegramBotUseCase


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_env(name: str) -> str:
    """Return a required environment variable or fail at startup."""

    # Failing at startup simplifies diagnosis and avoids more opaque
    # request-time errors.
    value = os.getenv(name)
    if value is None or value == "":
        raise ValueError(f"Missing {name}.")
    return value


app = FastAPI()
supabase_adapter = SupabaseAdapter(
    supabase_url=_get_env("SUPABASE_URL"),
    supabase_key=_get_env("SUPABASE_KEY"),
)
telegram_adapter = TelegramAdapter(_get_env("TELEGRAM_TOKEN"))
bot_use_case = TelegramBotUseCase(supabase_adapter, supabase_adapter, telegram_adapter)


@app.post("/webhook")
async def telegram_webhook(request: Request) -> dict[str, str]:
    """Process Telegram updates and dispatch supported commands."""

    try:
        logger.info("Received Telegram webhook request")
        payload: object = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("Invalid Telegram payload.")

        # Telegram delivers the update as JSON; `de_json` reconstructs the
        # object using the configured bot to preserve SDK helpers.
        update = Update.de_json(payload, telegram_adapter.app.bot)
        if update is None:
            logger.warning("Telegram update could not be parsed")
            return {"status": "ok"}

        incoming_message = update.message
        if incoming_message is not None and incoming_message.text in {
            "/start",
            "/subscribe",
            "/unsubscribe",
        }:
            user = update.effective_user
            if user is None:
                raise ValueError("Update missing effective user.")
            logger.info(
                "Dispatching command=%s user_id=%s",
                incoming_message.text,
                user.id,
            )
            await bot_use_case.execute(
                incoming_message.text,
                user.id,
                user.first_name,
                user.username,
            )
        else:
            logger.info("Ignoring unsupported or empty Telegram message")

        return {"status": "ok"}
    except Exception as exc:
        logger.exception("Controller error: %s", exc)
        return {"status": "error", "detail": str(exc)}


@app.get("/")
async def health() -> dict[str, str]:
    """Expose a lightweight endpoint for health checks."""

    return {"status": "online", "architecture": "hexagonal"}

# pyright: reportMissingImports=false, reportMissingModuleSource=false

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, status
from telegram import Update

from adapters import (
    OpenF1SessionProvider,
    TelegramClient,
    SupabaseSettingsRepository,
    SupabaseUserRepository,
    _build_supabase_client,
)
from application import TelegramBotUseCase, WakeUpUseCase
from telegram_helpers import RecentUpdateRegistry, SUBSCRIBE_CALLBACK_DATA, extract_command


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
SUPPORTED_COMMANDS = {
    "/start",
    "/subscribe",
    "/unsubscribe",
    "/set_country",
}
recent_updates = RecentUpdateRegistry()


def _get_env(name: str) -> str:
    """Return a required environment variable or fail at startup."""

    # Failing at startup simplifies diagnosis and avoids more opaque
    # request-time errors.
    value = os.getenv(name)
    if value is None or value == "":
        raise ValueError(f"Missing {name}.")
    return value


def _get_bool_env(name: str, default: bool) -> bool:
    """Return a boolean environment variable with a safe default."""

    value = os.getenv(name)
    if value is None or value == "":
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


app = FastAPI()
supabase_client = _build_supabase_client(
    supabase_url=_get_env("SUPABASE_URL"),
    supabase_key=_get_env("SUPABASE_KEY"),
)
user_repository = SupabaseUserRepository(supabase_client)
settings_repository = SupabaseSettingsRepository(supabase_client)
telegram_client = TelegramClient(_get_env("TELEGRAM_TOKEN"))
bot_use_case = TelegramBotUseCase(
    user_repository,
    settings_repository,
    telegram_client,
)
session_provider = OpenF1SessionProvider()
wake_up_use_case = WakeUpUseCase(
    session_provider,
    settings_repository,
    user_repository,
    telegram_client,
    enforce_session_reminder_window=not _get_bool_env(
        "DISABLE_SESSION_REMINDER_WINDOW",
        default=False,
    ),
)
wake_up_token = _get_env("SECRET_TOKEN")


@app.post("/webhook")
async def telegram_webhook(request: Request) -> dict[str, str]:
    """Process Telegram updates and dispatch supported commands."""

    try:
        logger.info("Received Telegram webhook request")
        payload: object = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("Invalid Telegram payload.")
        raw_update_id = payload.get("update_id")
        if isinstance(raw_update_id, int) and not recent_updates.mark_seen(raw_update_id):
            logger.info("Ignoring duplicate Telegram update update_id=%s", raw_update_id)
            return {"status": "ok"}

        # Telegram delivers the update as JSON; `de_json` reconstructs the
        # object using the configured bot to preserve SDK helpers.
        update = Update.de_json(payload, telegram_client.app.bot)
        if update is None:
            logger.warning("Telegram update could not be parsed")
            return {"status": "ok"}

        incoming_message = update.message
        normalized_command = extract_command(incoming_message.text if incoming_message is not None else None)
        if incoming_message is not None and normalized_command in SUPPORTED_COMMANDS:
            user = update.effective_user
            if user is None:
                raise ValueError("Update missing effective user.")
            logger.info(
                "Dispatching command=%s user_id=%s",
                normalized_command,
                user.id,
            )
            await bot_use_case.execute(
                normalized_command,
                user.id,
                user.first_name,
                user.username,
            )
        elif update.callback_query is not None and update.callback_query.data is not None:
            callback_data = update.callback_query.data
            if callback_data == SUBSCRIBE_CALLBACK_DATA:
                user = update.callback_query.from_user
                await bot_use_case.handle_subscribe_callback(
                    update.callback_query.id,
                    user.id,
                    user.first_name,
                    update.callback_query.message.chat.id,
                    update.callback_query.message.message_id,
                )
            elif callback_data.startswith("tz_"):
                user = update.callback_query.from_user
                await bot_use_case.handle_country_callback(
                    update.callback_query.id,
                    callback_data,
                    user.id,
                    user.first_name,
                    update.callback_query.message.chat.id,
                    update.callback_query.message.message_id,
                )
            else:
                logger.info("Ignoring unsupported callback data=%s", callback_data)
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


@app.post("/wake-up")
async def wake_up(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    """Handle protected automation triggers such as the weekly digest."""

    try:
        _validate_bearer_token(authorization, wake_up_token)
        logger.info("Received wake-up request")
        payload: object = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("Invalid wake-up payload.")

        trigger_type = payload.get("trigger_type")
        if not isinstance(trigger_type, str) or trigger_type == "":
            raise ValueError("Missing trigger_type.")

        return await wake_up_use_case.execute(trigger_type)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Wake-up endpoint error: %s", exc)
        return {"status": "error", "detail": str(exc)}


def _validate_bearer_token(
    authorization_header: str | None,
    expected_token: str,
) -> None:
    """Require a valid bearer token for protected endpoints."""

    if authorization_header != f"Bearer {expected_token}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

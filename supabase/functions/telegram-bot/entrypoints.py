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
    """Devuelve una variable de entorno obligatoria o falla al iniciar."""

    # Fallar al arrancar simplifica el diagnóstico y evita errores más opacos
    # durante el manejo de requests.
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
    """Procesa updates de Telegram y despacha los comandos soportados."""

    try:
        payload: object = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("Invalid Telegram payload.")

        # Telegram entrega el update como JSON; `de_json` reconstruye el objeto
        # usando el bot configurado para conservar helpers del SDK.
        update = Update.de_json(payload, telegram_adapter.app.bot)
        if update is None:
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
            await bot_use_case.execute(
                incoming_message.text,
                user.id,
                user.first_name,
                user.username,
            )

        return {"status": "ok"}
    except Exception as exc:
        logger.error("Error en controlador: %s", exc)
        return {"status": "error", "detail": str(exc)}


@app.get("/")
async def health() -> dict[str, str]:
    """Expone un endpoint liviano para health checks."""

    return {"status": "online", "architecture": "hexagonal"}

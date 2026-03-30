# pyright: reportMissingImports=false, reportMissingModuleSource=false

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
from supabase import create_client, Client
from dotenv import load_dotenv

# ==========================================
# 0. CONFIGURACIÓN & LOGS
# ==========================================
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==========================================
# 1. DOMAIN (El corazón del negocio)
# ==========================================
class User:
    def __init__(
        self,
        user_id: int,
        first_name: str,
        username: Optional[str],
        status: str = "inactive",
    ):
        self.user_id = user_id
        self.first_name = first_name
        self.username = username
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "first_name": self.first_name,
            "username": self.username,
            "status": self.status,
        }


# ==========================================
# 2. PORTS (Interfaces / Contratos)
# ==========================================
class UserRepository(ABC):
    @abstractmethod
    def save_user(self, user: User) -> None:
        raise NotImplementedError


class SettingsRepository(ABC):
    @abstractmethod
    def get_value(self, key: str, default: str) -> str:
        raise NotImplementedError


class MessagingService(ABC):
    @abstractmethod
    async def send_welcome(self, chat_id: int, text: str) -> None:
        raise NotImplementedError


# ==========================================
# 3. APPLICATION (Casos de Uso)
# ==========================================
class StartBotUseCase:
    """Lógica pura de negocio para el comando /start"""

    def __init__(
        self,
        user_repo: UserRepository,
        settings_repo: SettingsRepository,
        messenger: MessagingService,
    ):
        self.user_repo = user_repo
        self.settings_repo = settings_repo
        self.messenger = messenger

    async def execute(
        self, user_id: int, first_name: str, username: Optional[str]
    ) -> None:
        # 1. Crear entidad de dominio
        user = User(user_id, first_name, username)

        # 2. Persistir (el puerto se encarga del 'cómo')
        self.user_repo.save_user(user)

        # 3. Obtener texto de bienvenida
        welcome_tpl = self.settings_repo.get_value("welcome_msg", "¡Wena {nombre}!")
        final_text = welcome_tpl.replace("{nombre}", first_name)

        # 4. Notificar
        await self.messenger.send_welcome(user_id, final_text)


# ==========================================
# 4. ADAPTERS (Implementaciones técnicas)
# ==========================================


class SupabaseAdapter(UserRepository, SettingsRepository):
    """Adaptador para persistencia en Supabase"""

    def __init__(self) -> None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if url is None or key is None:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY.")
        self.client: Client = create_client(url, key)

    def save_user(self, user: User) -> None:
        self.client.table("users").upsert(
            user.to_dict(), on_conflict="user_id"
        ).execute()

    def get_value(self, key: str, default: str) -> str:
        res = self.client.table("bot_settings").select("value").eq("key", key).execute()
        return res.data[0]["value"] if res.data else default


class TelegramAdapter(MessagingService):
    """Adaptador para hablar con Telegram"""

    def __init__(self, bot_token: str) -> None:
        self.app = Application.builder().token(bot_token).build()

    async def send_welcome(self, chat_id: int, text: str) -> None:
        keyboard = [[InlineKeyboardButton("🔔 Activar Alertas", callback_data="sub")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.app.bot.send_message(
            chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="Markdown"
        )


# ==========================================
# 5. DRIVING ADAPTER (Controlador FastAPI)
# ==========================================
app = FastAPI()

# Inyección de dependencias (Singleton para los adaptadores)
db_adapter = SupabaseAdapter()
telegram_token = os.getenv("TELEGRAM_TOKEN")
if telegram_token is None:
    raise ValueError("Missing TELEGRAM_TOKEN.")
telegram_adapter = TelegramAdapter(telegram_token)
start_use_case = StartBotUseCase(db_adapter, db_adapter, telegram_adapter)


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Controlador que expone el endpoint para Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_adapter.app.bot)

        if update.message and update.message.text == "/start":
            user = update.effective_user
            # Ejecutamos el caso de uso sin saber NADA de Supabase o Telegram internals
            await start_use_case.execute(user.id, user.first_name, user.username)

        return {"status": "ok"}
    except Exception as exc:
        logger.error("Error en controlador: %s", exc)
        return {"status": "error", "detail": str(exc)}


@app.get("/")
async def health():
    return {"status": "online", "architecture": "hexagonal"}

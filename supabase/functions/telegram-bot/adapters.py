# pyright: reportMissingImports=false, reportMissingModuleSource=false

from telegram.ext import Application
from supabase import Client, create_client

from domain import User


class SupabaseAdapter:
    """Implementa persistencia y lectura de ajustes usando Supabase."""

    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        self.client: Client = create_client(supabase_url, supabase_key)

    def save_user(self, user: User) -> None:
        """Inserta o actualiza un usuario identificado por `user_id`."""

        # Upsert evita duplicados cuando el mismo usuario vuelve a ejecutar /start.
        self.client.table("users").upsert(
            user.to_record(),
            on_conflict="user_id",
        ).execute()

    def update_user_status(self, user_id: int, status: str) -> None:
        """Actualiza el estado del usuario si ya existe en la tabla."""

        self.client.table("users").update({"status": status}).eq("user_id", user_id).execute()

    def get_value(self, key: str, default: str) -> str:
        """Obtiene un ajuste del bot y usa un fallback si no existe."""

        # Se valida la forma de la respuesta porque el SDK expone `data`
        # con un tipo amplio y no siempre garantiza contenido.
        response = self.client.table("bot_settings").select("value").eq("key", key).execute()
        response_data: object = response.data
        if not isinstance(response_data, list) or len(response_data) == 0:
            return default

        first_row = response_data[0]
        if not isinstance(first_row, dict):
            return default

        value = first_row.get("value")
        return value if isinstance(value, str) else default


class TelegramAdapter:
    """Envuelve el cliente de Telegram para enviar mensajes del bot."""

    def __init__(self, bot_token: str) -> None:
        self.app = Application.builder().token(bot_token).build()

    async def send_message(self, chat_id: int, text: str) -> None:
        """Envía un mensaje simple al chat de Telegram."""

        await self.app.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
        )

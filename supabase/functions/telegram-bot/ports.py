from typing import Protocol

from domain import User


class UserRepository(Protocol):
    """Contrato para persistir usuarios del dominio."""

    # Puerto de salida para persistir usuarios sin acoplar el dominio
    # a una base de datos concreta.
    def save_user(self, user: User) -> None: ...

    def update_user_status(self, user_id: int, status: str) -> None: ...


class SettingsRepository(Protocol):
    """Contrato para leer configuración del bot."""

    # Permite leer configuración dinámica del bot desde cualquier origen.
    def get_value(self, key: str, default: str) -> str: ...


class MessagingService(Protocol):
    """Contrato para enviar mensajes hacia el usuario final."""

    # Abstrae el canal de entrega para que el caso de uso no dependa de Telegram.
    async def send_message(self, chat_id: int, text: str) -> None: ...

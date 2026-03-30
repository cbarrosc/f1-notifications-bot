from domain import User
from ports import MessagingService, SettingsRepository, UserRepository


class TelegramBotUseCase:
    """Orquesta los comandos soportados por el bot de Telegram."""

    def __init__(
        self,
        user_repo: UserRepository,
        settings_repo: SettingsRepository,
        messenger: MessagingService,
    ) -> None:
        self._user_repo = user_repo
        self._settings_repo = settings_repo
        self._messenger = messenger

    async def execute(
        self,
        command: str,
        user_id: int,
        first_name: str,
        username: str | None,
    ) -> None:
        """Procesa `/start`, `/subscribe` y `/unsubscribe`."""

        if command == "/start":
            user = User(user_id=user_id, first_name=first_name, username=username)
            self._user_repo.save_user(user)
            welcome_template = self._settings_repo.get_value(
                "welcome_msg",
                "Hola {name}!",
            )
            final_text = welcome_template.replace("{name}", first_name)
            await self._messenger.send_message(user_id, final_text)
            return

        if command == "/subscribe":
            self._user_repo.update_user_status(user_id, "active")
            text = self._settings_repo.get_value(
                "subscribe_ok",
                "Suscripcion activada.",
            )
            await self._messenger.send_message(user_id, text)
            return

        if command == "/unsubscribe":
            self._user_repo.update_user_status(user_id, "inactive")
            text = self._settings_repo.get_value(
                "unsubscribe_ok",
                "Suscripcion desactivada.",
            )
            await self._messenger.send_message(user_id, text)

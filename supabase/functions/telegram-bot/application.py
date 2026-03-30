import logging

from domain import User
from ports import MessagingService, SettingsRepository, UserRepository


logger = logging.getLogger(__name__)


class TelegramBotUseCase:
    """Orchestrate the commands supported by the Telegram bot."""

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
        """Process `/start`, `/subscribe`, and `/unsubscribe`."""

        if command == "/start":
            logger.info("Processing command=%s user_id=%s", command, user_id)
            user = User(user_id=user_id, first_name=first_name, username=username)
            self._user_repo.save_user(user)
            welcome_template = self._settings_repo.get_value("welcome_msg")
            final_text = welcome_template.replace("{name}", first_name)
            await self._messenger.send_message(user_id, final_text)
            logger.info("Completed command=%s user_id=%s", command, user_id)
            return

        if command == "/subscribe":
            logger.info("Processing command=%s user_id=%s", command, user_id)
            self._user_repo.update_user_status(user_id, "active")
            text = self._settings_repo.get_value("subscribe_ok")
            await self._messenger.send_message(user_id, text)
            logger.info("Completed command=%s user_id=%s status=active", command, user_id)
            return

        if command == "/unsubscribe":
            logger.info("Processing command=%s user_id=%s", command, user_id)
            self._user_repo.update_user_status(user_id, "inactive")
            text = self._settings_repo.get_value("unsubscribe_ok")
            await self._messenger.send_message(user_id, text)
            logger.info("Completed command=%s user_id=%s status=inactive", command, user_id)
            return

        logger.warning("Ignoring unsupported command=%s user_id=%s", command, user_id)

import unittest

from application import TelegramBotUseCase
from domain import User


class FakeUserRepository:
    def __init__(self) -> None:
        self.saved_users: list[User] = []
        self.status_updates: list[tuple[int, str]] = []

    def save_user(self, user: User) -> None:
        self.saved_users.append(user)

    def update_user_status(self, user_id: int, status: str) -> None:
        self.status_updates.append((user_id, status))


class FakeSettingsRepository:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def get_value(self, key: str, default: str) -> str:
        return self.values.get(key, default)


class FakeMessagingService:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


class TelegramBotUseCaseTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_saves_user_and_replaces_name_placeholder(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({"welcome_msg": "Hola {name}, bienvenido"})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.execute("/start", 10, "Cam", "camtest")

        self.assertEqual(len(user_repo.saved_users), 1)
        self.assertEqual(user_repo.saved_users[0].status, "inactive")
        self.assertEqual(messenger.messages, [(10, "Hola Cam, bienvenido")])

    async def test_subscribe_updates_status_to_active(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({"subscribe_ok": "Alertas activadas"})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.execute("/subscribe", 10, "Cam", "camtest")

        self.assertEqual(user_repo.status_updates, [(10, "active")])
        self.assertEqual(messenger.messages, [(10, "Alertas activadas")])

    async def test_unsubscribe_updates_status_to_inactive(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({"unsubscribe_ok": "Alertas desactivadas"})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.execute("/unsubscribe", 10, "Cam", "camtest")

        self.assertEqual(user_repo.status_updates, [(10, "inactive")])
        self.assertEqual(messenger.messages, [(10, "Alertas desactivadas")])


if __name__ == "__main__":
    unittest.main()

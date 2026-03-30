import unittest
from types import ModuleType, SimpleNamespace
import sys

from application import TelegramBotUseCase
from domain import User

telegram_module = ModuleType("telegram")
telegram_ext_module = ModuleType("telegram.ext")
telegram_ext_module.Application = object
telegram_module.ext = telegram_ext_module
sys.modules.setdefault("telegram", telegram_module)
sys.modules.setdefault("telegram.ext", telegram_ext_module)

supabase_module = ModuleType("supabase")
supabase_module.Client = object
supabase_module.create_client = lambda *_args, **_kwargs: None
sys.modules.setdefault("supabase", supabase_module)

from adapters import SupabaseSettingsRepository, SupabaseUserRepository


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

    def get_value(self, key: str) -> str:
        return self.values[key]


class FakeMessagingService:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


class TelegramBotUseCaseTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_saves_user_and_replaces_name_placeholder(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({"welcome_msg": "Hello {name}, welcome"})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.execute("/start", 10, "Cam", "camtest")

        self.assertEqual(len(user_repo.saved_users), 1)
        self.assertEqual(user_repo.saved_users[0].status, "inactive")
        self.assertEqual(messenger.messages, [(10, "Hello Cam, welcome")])

    async def test_subscribe_updates_status_to_active(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({"subscribe_ok": "Notifications enabled"})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.execute("/subscribe", 10, "Cam", "camtest")

        self.assertEqual(user_repo.status_updates, [(10, "active")])
        self.assertEqual(messenger.messages, [(10, "Notifications enabled")])

    async def test_unsubscribe_updates_status_to_inactive(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({"unsubscribe_ok": "Notifications disabled"})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.execute("/unsubscribe", 10, "Cam", "camtest")

        self.assertEqual(user_repo.status_updates, [(10, "inactive")])
        self.assertEqual(messenger.messages, [(10, "Notifications disabled")])


class FakeSupabaseQuery:
    def __init__(self, response_data: object, table_name: str) -> None:
        self.response_data = response_data
        self.table_name = table_name
        self.filters: list[tuple[str, object]] = []
        self.limit_value: int | None = None

    def select(self, *_args: object, **_kwargs: object) -> "FakeSupabaseQuery":
        return self

    def eq(self, column: str, value: object) -> "FakeSupabaseQuery":
        self.filters.append((column, value))
        return self

    def limit(self, value: int) -> "FakeSupabaseQuery":
        self.limit_value = value
        return self

    def update(self, *_args: object, **_kwargs: object) -> "FakeSupabaseQuery":
        return self

    def upsert(self, *_args: object, **_kwargs: object) -> "FakeSupabaseQuery":
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.response_data)


class FakeSupabaseClient:
    def __init__(self, existing_rows: object) -> None:
        self.existing_rows = existing_rows
        self.upsert_calls: list[dict[str, object]] = []

    def table(self, name: str) -> object:
        if name == "users":
            return FakeUsersTable(self)
        if name == "bot_settings":
            return FakeSupabaseQuery(self.existing_rows, name)
        raise AssertionError(f"Unexpected table requested: {name}")


class FakeUsersTable:
    def __init__(self, client: FakeSupabaseClient) -> None:
        self.client = client

    def select(self, *_args: object, **_kwargs: object) -> FakeSupabaseQuery:
        return FakeSupabaseQuery(self.client.existing_rows, "users")

    def upsert(self, record: dict[str, object], on_conflict: str) -> FakeSupabaseQuery:
        self.client.upsert_calls.append(
            {"record": record, "on_conflict": on_conflict}
        )
        return FakeSupabaseQuery([], "users")


class SupabaseUserRepositoryTest(unittest.TestCase):
    def test_save_user_preserves_existing_status_when_user_already_exists(self) -> None:
        repository = SupabaseUserRepository(FakeSupabaseClient([{"status": "active"}]))

        repository.save_user(User(user_id=10, first_name="Cam", username="camtest"))

        self.assertEqual(len(repository.client.upsert_calls), 1)
        self.assertEqual(
            repository.client.upsert_calls[0]["record"],
            {
                "user_id": 10,
                "first_name": "Cam",
                "username": "camtest",
                "status": "active",
            },
        )

    def test_save_user_keeps_default_inactive_for_new_user(self) -> None:
        repository = SupabaseUserRepository(FakeSupabaseClient([]))

        repository.save_user(User(user_id=10, first_name="Cam", username="camtest"))

        self.assertEqual(len(repository.client.upsert_calls), 1)
        self.assertEqual(
            repository.client.upsert_calls[0]["record"],
            {
                "user_id": 10,
                "first_name": "Cam",
                "username": "camtest",
                "status": "inactive",
            },
        )


class SupabaseSettingsRepositoryTest(unittest.TestCase):
    def test_get_value_returns_string_setting(self) -> None:
        repository = SupabaseSettingsRepository(FakeSupabaseClient([{"value": "hello"}]))

        value = repository.get_value("welcome_msg")

        self.assertEqual(value, "hello")


if __name__ == "__main__":
    unittest.main()

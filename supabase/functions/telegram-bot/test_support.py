from datetime import datetime
from types import ModuleType, SimpleNamespace
import sys

from domain import Session, User


telegram_module = ModuleType("telegram")
telegram_ext_module = ModuleType("telegram.ext")
telegram_ext_module.Application = object


class InlineKeyboardButton:
    def __init__(self, text: str, callback_data: str) -> None:
        self.text = text
        self.callback_data = callback_data


class InlineKeyboardMarkup:
    def __init__(self, inline_keyboard: object) -> None:
        self.inline_keyboard = inline_keyboard


telegram_module.InlineKeyboardButton = InlineKeyboardButton
telegram_module.InlineKeyboardMarkup = InlineKeyboardMarkup
telegram_module.ext = telegram_ext_module
sys.modules.setdefault("telegram", telegram_module)
sys.modules.setdefault("telegram.ext", telegram_ext_module)

supabase_module = ModuleType("supabase")
supabase_module.Client = object
supabase_module.create_client = lambda *_args, **_kwargs: None
sys.modules.setdefault("supabase", supabase_module)


class FakeUserRepository:
    def __init__(self) -> None:
        self.saved_users: list[User] = []
        self.status_updates: list[tuple[int, str]] = []
        self.timezone_updates: list[tuple[int, str]] = []
        self.active_users: list[User] = []
        self.users_by_id: dict[int, User] = {}

    def get_user(self, user_id: int) -> User | None:
        return self.users_by_id.get(user_id)

    def save_user(self, user: User) -> None:
        self.saved_users.append(user)
        self.users_by_id[user.user_id] = user

    def update_user_status(self, user_id: int, status: str) -> None:
        self.status_updates.append((user_id, status))

    def update_user_timezone(self, user_id: int, timezone: str) -> None:
        self.timezone_updates.append((user_id, timezone))

    def list_active_users(self) -> list[User]:
        return self.active_users


class FakeSettingsRepository:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def get_value(self, key: str) -> str:
        return self.values[key]


class FakeMessagingService:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []
        self.country_messages: list[tuple[int, str, list[list[dict[str, str]]]]] = []
        self.subscribe_prompts: list[tuple[int, str, str, str]] = []
        self.callback_answers: list[tuple[str, str]] = []
        self.edited_messages: list[tuple[int, int, str]] = []
        self.fail_edit_message = False

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))

    async def send_country_options(
        self,
        chat_id: int,
        text: str,
        options: list[list[dict[str, str]]],
    ) -> None:
        self.country_messages.append((chat_id, text, options))

    async def send_subscribe_prompt(
        self,
        chat_id: int,
        text: str,
        button_text: str,
        callback_data: str,
    ) -> None:
        self.subscribe_prompts.append((chat_id, text, button_text, callback_data))

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str,
    ) -> None:
        self.callback_answers.append((callback_query_id, text))

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
    ) -> None:
        if self.fail_edit_message:
            raise RuntimeError("edit failed")
        self.edited_messages.append((chat_id, message_id, text))


class FakeSessionProvider:
    def __init__(
        self, next_session: Session | None, source_name: str = "OpenF1"
    ) -> None:
        self.next_session = next_session
        self.source_name = source_name
        self.requested_instants: list[datetime] = []

    def get_next_session_after(self, when: datetime) -> Session | None:
        self.requested_instants.append(when)
        return self.next_session

    def get_source_name(self) -> str:
        return self.source_name


class FakeSupabaseQuery:
    def __init__(self, response_data: object, table_name: str) -> None:
        self.response_data = response_data
        self.table_name = table_name
        self.filters: list[tuple[str, object]] = []
        self.limit_value: int | None = None
        self.update_payload: dict[str, object] | None = None

    def select(self, *_args: object, **_kwargs: object) -> "FakeSupabaseQuery":
        return self

    def eq(self, column: str, value: object) -> "FakeSupabaseQuery":
        self.filters.append((column, value))
        return self

    def limit(self, value: int) -> "FakeSupabaseQuery":
        self.limit_value = value
        return self

    def update(self, *_args: object, **_kwargs: object) -> "FakeSupabaseQuery":
        if len(_args) > 0 and isinstance(_args[0], dict):
            self.update_payload = _args[0]
        return self

    def upsert(self, *_args: object, **_kwargs: object) -> "FakeSupabaseQuery":
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.response_data)


class FakeSupabaseClient:
    def __init__(
        self,
        users_rows: object,
        settings_rows: object | None = None,
    ) -> None:
        self.users_rows = users_rows
        self.settings_rows = settings_rows if settings_rows is not None else users_rows
        self.upsert_calls: list[dict[str, object]] = []
        self.update_calls: list[dict[str, object]] = []

    def table(self, name: str) -> object:
        if name == "users":
            return FakeUsersTable(self)
        if name == "bot_settings":
            return FakeSupabaseQuery(self.settings_rows, name)
        raise AssertionError(f"Unexpected table requested: {name}")


class FakeUsersTable:
    def __init__(self, client: FakeSupabaseClient) -> None:
        self.client = client

    def select(self, *_args: object, **_kwargs: object) -> FakeSupabaseQuery:
        return FakeSupabaseQuery(self.client.users_rows, "users")

    def update(self, payload: dict[str, object]) -> FakeSupabaseQuery:
        query = FakeSupabaseQuery([], "users")
        query.update_payload = payload
        original_eq = query.eq

        def tracking_eq(column: str, value: object) -> FakeSupabaseQuery:
            self.client.update_calls.append(
                {"payload": payload, "filters": [(column, value)]}
            )
            return original_eq(column, value)

        query.eq = tracking_eq  # type: ignore[method-assign]
        return query

    def upsert(self, record: dict[str, object], on_conflict: str) -> FakeSupabaseQuery:
        self.client.upsert_calls.append(
            {"record": record, "on_conflict": on_conflict}
        )
        return FakeSupabaseQuery([], "users")

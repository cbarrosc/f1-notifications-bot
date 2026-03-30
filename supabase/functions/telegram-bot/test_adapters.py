import unittest

from test_support import FakeSupabaseClient

from adapters import (
    SupabaseSettingsRepository,
    SupabaseUserRepository,
    _build_session_display_name,
)
from domain import User


class SupabaseUserRepositoryTest(unittest.TestCase):
    def test_get_user_returns_user_when_row_exists(self) -> None:
        repository = SupabaseUserRepository(
            FakeSupabaseClient(
                [
                    {
                        "user_id": 10,
                        "first_name": "Cam",
                        "username": "camtest",
                        "status": "active",
                        "timezone": "America/Santiago",
                    }
                ]
            )
        )

        user = repository.get_user(10)

        self.assertEqual(
            user,
            User(
                user_id=10,
                first_name="Cam",
                username="camtest",
                status="active",
                timezone="America/Santiago",
            ),
        )

    def test_save_user_preserves_existing_status_when_user_already_exists(self) -> None:
        repository = SupabaseUserRepository(
            FakeSupabaseClient(
                [
                    {
                        "user_id": 10,
                        "first_name": "Cam",
                        "username": "camtest",
                        "status": "active",
                        "timezone": "Europe/Madrid",
                    }
                ]
            )
        )

        repository.save_user(User(user_id=10, first_name="Cam", username="camtest"))

        self.assertEqual(len(repository.client.upsert_calls), 1)
        self.assertEqual(
            repository.client.upsert_calls[0]["record"],
            {
                "user_id": 10,
                "first_name": "Cam",
                "username": "camtest",
                "status": "active",
                "timezone": "Europe/Madrid",
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
                "timezone": "UTC",
            },
        )

    def test_list_active_users_returns_only_valid_rows(self) -> None:
        repository = SupabaseUserRepository(
            FakeSupabaseClient(
                [
                    {
                        "user_id": 10,
                        "first_name": "Ana",
                        "username": "ana",
                        "status": "active",
                        "timezone": "America/Santiago",
                    },
                    {"user_id": "bad"},
                    {
                        "user_id": 20,
                        "first_name": "Beto",
                        "username": None,
                        "status": "active",
                        "timezone": None,
                    },
                ],
            )
        )

        active_users = repository.list_active_users()

        self.assertEqual(
            active_users,
            [
                User(
                    user_id=10,
                    first_name="Ana",
                    username="ana",
                    status="active",
                    timezone="America/Santiago",
                ),
                User(
                    user_id=20,
                    first_name="Beto",
                    username=None,
                    status="active",
                    timezone=None,
                ),
            ],
        )

    def test_update_user_timezone_persists_timezone_change(self) -> None:
        client = FakeSupabaseClient([])
        repository = SupabaseUserRepository(client)

        repository.update_user_timezone(10, "America/Santiago")

        self.assertEqual(
            client.update_calls,
            [{"payload": {"timezone": "America/Santiago"}, "filters": [("user_id", 10)]}],
        )

    def test_list_active_users_raises_on_invalid_payload_shape(self) -> None:
        repository = SupabaseUserRepository(FakeSupabaseClient({"user_id": 10}))

        with self.assertRaisesRegex(ValueError, "Invalid users response payload"):
            repository.list_active_users()


class SupabaseSettingsRepositoryTest(unittest.TestCase):
    def test_get_value_returns_string_setting(self) -> None:
        repository = SupabaseSettingsRepository(
            FakeSupabaseClient([], settings_rows=[{"value": "hello"}])
        )

        value = repository.get_value("welcome_msg")

        self.assertEqual(value, "hello")

    def test_get_value_raises_when_setting_is_missing(self) -> None:
        repository = SupabaseSettingsRepository(
            FakeSupabaseClient([], settings_rows=[])
        )

        with self.assertRaisesRegex(ValueError, "Missing bot setting: welcome_msg"):
            repository.get_value("welcome_msg")

    def test_get_value_raises_when_value_is_not_a_string(self) -> None:
        repository = SupabaseSettingsRepository(
            FakeSupabaseClient([], settings_rows=[{"value": 42}])
        )

        with self.assertRaisesRegex(
            ValueError, "Invalid bot setting value for key: welcome_msg"
        ):
            repository.get_value("welcome_msg")


class OpenF1FormattingTest(unittest.TestCase):
    def test_build_session_display_name_uses_official_meeting_name(self) -> None:
        display_name = _build_session_display_name(
            "Practice 1",
            "FORMULA 1 SINGAPORE AIRLINES SINGAPORE GRAND PRIX 2026",
        )

        self.assertEqual(
            display_name,
            "FORMULA 1 SINGAPORE AIRLINES SINGAPORE GRAND PRIX 2026 - Practice 1",
        )

    def test_build_session_display_name_falls_back_to_session_name(self) -> None:
        display_name = _build_session_display_name("Practice 1", None)

        self.assertEqual(display_name, "Practice 1")


if __name__ == "__main__":
    unittest.main()

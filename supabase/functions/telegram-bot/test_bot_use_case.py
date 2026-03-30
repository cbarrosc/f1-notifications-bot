import unittest

from application import (
    COUNTRY_OPTIONS,
    TelegramBotUseCase,
)
from domain import User
from telegram_helpers import SUBSCRIBE_BUTTON_TEXT, SUBSCRIBE_CALLBACK_DATA

from test_support import (
    FakeMessagingService,
    FakeSettingsRepository,
    FakeUserRepository,
)


class TelegramBotUseCaseTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_registers_new_user_sends_welcome_and_subscribe_prompt(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({"welcome_msg": "Hello {name}, welcome"})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.execute("/start", 10, "Cam", "camtest")

        self.assertEqual(len(user_repo.saved_users), 1)
        self.assertEqual(user_repo.saved_users[0].status, "inactive")
        self.assertEqual(user_repo.saved_users[0].timezone, "UTC")
        self.assertEqual(messenger.messages, [])
        self.assertEqual(
            messenger.subscribe_prompts,
            [
                (
                    10,
                    "Hello Cam, welcome",
                    SUBSCRIBE_BUTTON_TEXT,
                    SUBSCRIBE_CALLBACK_DATA,
                )
            ],
        )
        self.assertEqual(messenger.country_messages, [])

    async def test_start_uses_already_registered_for_existing_user(self) -> None:
        user_repo = FakeUserRepository()
        user_repo.users_by_id[10] = User(
            user_id=10,
            first_name="Cam",
            username="camtest",
            status="active",
            timezone="America/Santiago",
        )
        settings_repo = FakeSettingsRepository(
            {
                "already_registered": (
                    "Wena {name}! Ya estAs registrado en el sistema. "
                    "Tu zona horaria actual es: {tz}."
                )
            }
        )
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.execute("/start", 10, "Cam", "camtest")

        self.assertEqual(user_repo.saved_users, [])
        self.assertEqual(
            messenger.messages,
            [(10, "Wena Cam! Ya estAs registrado en el sistema. Tu zona horaria actual es: America/Santiago.")],
        )
        self.assertEqual(messenger.country_messages, [])
        self.assertEqual(messenger.subscribe_prompts, [])

    async def test_subscribe_updates_status_to_active_and_sends_single_message(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({"subscribe_ok": "Notifications enabled, {name}"})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.execute("/subscribe", 10, "Cam", "camtest")

        self.assertEqual(user_repo.status_updates, [(10, "active")])
        self.assertEqual(messenger.messages, [(10, "Notifications enabled, Cam")])
        self.assertEqual(messenger.country_messages, [])

    async def test_handle_subscribe_callback_edits_message_and_stops_there(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({"subscribe_ok": "Notifications enabled, {name}"})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.handle_subscribe_callback("cb-sub", 10, "Cam", 10, 55)

        self.assertEqual(user_repo.status_updates, [(10, "active")])
        self.assertEqual(messenger.callback_answers, [("cb-sub", "")])
        self.assertEqual(messenger.edited_messages, [(10, 55, "Notifications enabled, Cam")])
        self.assertEqual(messenger.country_messages, [])

    async def test_unsubscribe_updates_status_to_inactive(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({"unsubscribe_ok": "Notifications disabled"})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.execute("/unsubscribe", 10, "Cam", "camtest")

        self.assertEqual(user_repo.status_updates, [(10, "inactive")])
        self.assertEqual(messenger.messages, [(10, "Notifications disabled")])

    async def test_unsupported_command_does_not_persist_or_send(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.execute("/unknown", 10, "Cam", "camtest")

        self.assertEqual(user_repo.saved_users, [])
        self.assertEqual(user_repo.status_updates, [])
        self.assertEqual(messenger.messages, [])
        self.assertEqual(messenger.country_messages, [])

    async def test_start_propagates_missing_setting_error(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        with self.assertRaises(KeyError):
            await use_case.execute("/start", 10, "Cam", "camtest")

    async def test_set_country_sends_inline_country_options(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.execute("/set_country", 10, "Cam", "camtest")

        self.assertEqual(messenger.messages, [])
        self.assertEqual(
            messenger.country_messages,
            [
                (
                    10,
                    "Elige tu pais para configurar la zona horaria:",
                    COUNTRY_OPTIONS,
                )
            ],
        )

    async def test_handle_country_callback_updates_timezone_and_confirms(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository(
            {"timezone_confirmation_text": "Listo {name}, ya guardamos tu pais."}
        )
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.handle_country_callback("cb-1", "tz_cl", 10, "Cam", 10, 99)

        self.assertEqual(user_repo.timezone_updates, [(10, "America/Santiago")])
        self.assertEqual(
            messenger.callback_answers,
            [("cb-1", "")],
        )
        self.assertEqual(
            messenger.edited_messages,
            [(10, 99, "Listo Cam, ya guardamos tu pais.")],
        )
        self.assertEqual(messenger.messages, [])

    async def test_handle_country_callback_rejects_unknown_option(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.handle_country_callback("cb-2", "tz_xx", 10, "Cam", 10, 99)

        self.assertEqual(user_repo.timezone_updates, [])
        self.assertEqual(
            messenger.callback_answers,
            [("cb-2", "Opcion no soportada.")],
        )
        self.assertEqual(messenger.messages, [])

    async def test_handle_country_callback_requires_confirmation_template(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository({})
        messenger = FakeMessagingService()
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        with self.assertRaises(KeyError):
            await use_case.handle_country_callback("cb-3", "tz_cl", 10, "Cam", 10, 99)

        self.assertEqual(user_repo.timezone_updates, [(10, "America/Santiago")])
        self.assertEqual(messenger.callback_answers, [("cb-3", "")])

    async def test_handle_country_callback_falls_back_to_send_message_when_edit_fails(self) -> None:
        user_repo = FakeUserRepository()
        settings_repo = FakeSettingsRepository(
            {"timezone_confirmation_text": "Listo {name}, ya guardamos tu pais."}
        )
        messenger = FakeMessagingService()
        messenger.fail_edit_message = True
        use_case = TelegramBotUseCase(user_repo, settings_repo, messenger)

        await use_case.handle_country_callback("cb-4", "tz_cl", 10, "Cam", 10, 99)

        self.assertEqual(user_repo.timezone_updates, [(10, "America/Santiago")])
        self.assertEqual(messenger.callback_answers, [("cb-4", "")])
        self.assertEqual(messenger.edited_messages, [])
        self.assertEqual(messenger.messages, [(10, "Listo Cam, ya guardamos tu pais.")])


if __name__ == "__main__":
    unittest.main()

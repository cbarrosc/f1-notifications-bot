import unittest
from datetime import UTC, datetime

from application import WakeUpUseCase, _format_chile_datetime
from domain import Session, User

from test_support import (
    FakeMessagingService,
    FakeSessionProvider,
    FakeSettingsRepository,
    FakeUserRepository,
)


class WakeUpUseCaseTest(unittest.IsolatedAsyncioTestCase):
    async def test_weekly_digest_sends_message_to_active_users(self) -> None:
        now = datetime(2026, 3, 30, 14, 0, tzinfo=UTC)
        next_session = Session(
            session_name="FORMULA 1 AUSTRALIAN GRAND PRIX 2026 - Practice 1",
            date_start=datetime(2026, 4, 10, 1, 30, tzinfo=UTC),
            meeting_key=1290,
            location="Melbourne",
        )
        provider = FakeSessionProvider(next_session)
        settings_repo = FakeSettingsRepository(
            {"weekly_summary_msg": "Hola {name}, proxima parada: {location} a las {time}"}
        )
        user_repo = FakeUserRepository()
        user_repo.active_users = [
            User(user_id=101, first_name="Ana", username="ana", status="active"),
            User(user_id=202, first_name="Beto", username="beto", status="active"),
        ]
        messenger = FakeMessagingService()
        use_case = WakeUpUseCase(provider, settings_repo, user_repo, messenger)

        result = await use_case.execute("weekly_digest", now)

        self.assertEqual(provider.requested_instants, [now])
        self.assertEqual(
            messenger.messages,
            [
                (101, f"Hola Ana, proxima parada: Melbourne a las {_format_chile_datetime(next_session.date_start)}"),
                (202, f"Hola Beto, proxima parada: Melbourne a las {_format_chile_datetime(next_session.date_start)}"),
            ],
        )
        self.assertEqual(
            result,
            {
                "status": "awake",
                "source": "OpenF1",
                "trigger_type": "weekly_digest",
                "next_session": {
                    "name": "FORMULA 1 AUSTRALIAN GRAND PRIX 2026 - Practice 1",
                    "location": "Melbourne",
                    "utc_start": "2026-04-10T01:30:00Z",
                    "chile_start": _format_chile_datetime(next_session.date_start),
                    "minutes_to_start": 15090,
                },
                "action_taken": "weekly_digest_sent",
                "messages_sent": 2,
            },
        )

    async def test_weekly_digest_returns_no_active_users_when_there_are_none(self) -> None:
        now = datetime(2026, 3, 30, 14, 0, tzinfo=UTC)
        next_session = Session(
            session_name="Practice 1",
            date_start=datetime(2026, 4, 10, 1, 30, tzinfo=UTC),
            location="Melbourne",
        )
        provider = FakeSessionProvider(next_session)
        settings_repo = FakeSettingsRepository(
            {"weekly_summary_msg": "Proxima parada: {location} a las {time}"}
        )
        user_repo = FakeUserRepository()
        messenger = FakeMessagingService()
        use_case = WakeUpUseCase(provider, settings_repo, user_repo, messenger)

        result = await use_case.execute("weekly_digest", now)

        self.assertEqual(messenger.messages, [])
        self.assertEqual(result["action_taken"], "no_active_users")
        self.assertEqual(result["messages_sent"], 0)

    async def test_weekly_digest_returns_no_session_found_when_missing(self) -> None:
        now = datetime(2026, 3, 30, 14, 0, tzinfo=UTC)
        provider = FakeSessionProvider(None)
        settings_repo = FakeSettingsRepository({"weekly_summary_msg": "unused"})
        user_repo = FakeUserRepository()
        messenger = FakeMessagingService()
        use_case = WakeUpUseCase(provider, settings_repo, user_repo, messenger)

        result = await use_case.execute("weekly_digest", now)

        self.assertEqual(result["next_session"], None)
        self.assertEqual(result["action_taken"], "no_session_found")
        self.assertEqual(result["messages_sent"], 0)

    async def test_weekly_digest_falls_back_to_tbc_location(self) -> None:
        now = datetime(2026, 3, 30, 14, 0, tzinfo=UTC)
        next_session = Session(
            session_name="Practice 1",
            date_start=datetime(2026, 4, 10, 1, 30, tzinfo=UTC),
            location=None,
        )
        provider = FakeSessionProvider(next_session)
        settings_repo = FakeSettingsRepository(
            {"weekly_summary_msg": "Lugar: {location} / Hora: {time}"}
        )
        user_repo = FakeUserRepository()
        user_repo.active_users = [
            User(user_id=101, first_name="Ana", username="ana", status="active")
        ]
        messenger = FakeMessagingService()
        use_case = WakeUpUseCase(provider, settings_repo, user_repo, messenger)

        await use_case.execute("weekly_digest", now)

        self.assertEqual(
            messenger.messages,
            [(101, f"Lugar: TBC / Hora: {_format_chile_datetime(next_session.date_start)}")],
        )

    async def test_unsupported_trigger_raises_value_error(self) -> None:
        use_case = WakeUpUseCase(
            FakeSessionProvider(None),
            FakeSettingsRepository({}),
            FakeUserRepository(),
            FakeMessagingService(),
        )

        with self.assertRaisesRegex(ValueError, "Unsupported trigger_type"):
            await use_case.execute("daily_digest", datetime(2026, 3, 30, 14, 0, tzinfo=UTC))

    async def test_weekly_digest_propagates_missing_template(self) -> None:
        next_session = Session(
            session_name="Practice 1",
            date_start=datetime(2026, 4, 10, 1, 30, tzinfo=UTC),
            location="Melbourne",
        )
        user_repo = FakeUserRepository()
        user_repo.active_users = [
            User(user_id=101, first_name="Ana", username="ana", status="active")
        ]
        use_case = WakeUpUseCase(
            FakeSessionProvider(next_session),
            FakeSettingsRepository({}),
            user_repo,
            FakeMessagingService(),
        )

        with self.assertRaises(KeyError):
            await use_case.execute("weekly_digest", datetime(2026, 3, 30, 14, 0, tzinfo=UTC))


if __name__ == "__main__":
    unittest.main()

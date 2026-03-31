import unittest
from datetime import UTC, datetime

from application import WakeUpUseCase, _format_chile_datetime, _format_user_datetime
from domain import PodiumFinisher, PostRaceBriefing, Session, User

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
            {"weekly_summary_msg": "Hola {name}, proxima parada: {location} a las {time} {flag} ({tz})"}
        )
        user_repo = FakeUserRepository()
        user_repo.active_users = [
            User(
                user_id=101,
                first_name="Ana",
                username="ana",
                status="active",
                timezone="America/Santiago",
            ),
            User(
                user_id=202,
                first_name="Beto",
                username="beto",
                status="active",
                timezone="Europe/Madrid",
            ),
        ]
        messenger = FakeMessagingService()
        use_case = WakeUpUseCase(provider, settings_repo, user_repo, messenger)

        result = await use_case.execute("weekly_digest", now)

        self.assertEqual(provider.requested_instants, [now])
        self.assertEqual(
            messenger.messages,
            [
                (
                    101,
                    (
                        "Hola Ana, proxima parada: Melbourne a las "
                        f"{_format_user_datetime(next_session.date_start, 'America/Santiago')} "
                        "🇨🇱 (America/Santiago)"
                    ),
                ),
                (
                    202,
                    (
                        "Hola Beto, proxima parada: Melbourne a las "
                        f"{_format_user_datetime(next_session.date_start, 'Europe/Madrid')} "
                        "🇪🇸 (Europe/Madrid)"
                    ),
                ),
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
            {"weekly_summary_msg": "Lugar: {location} / Hora: {time} {flag} / TZ: {tz}"}
        )
        user_repo = FakeUserRepository()
        user_repo.active_users = [
            User(
                user_id=101,
                first_name="Ana",
                username="ana",
                status="active",
                timezone="UTC",
            )
        ]
        messenger = FakeMessagingService()
        use_case = WakeUpUseCase(provider, settings_repo, user_repo, messenger)

        await use_case.execute("weekly_digest", now)

        self.assertEqual(
            messenger.messages,
            [(101, f"Lugar: TBC / Hora: {_format_user_datetime(next_session.date_start, 'UTC')} 🌐 / TZ: UTC")],
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
            User(
                user_id=101,
                first_name="Ana",
                username="ana",
                status="active",
                timezone="UTC",
            )
        ]
        use_case = WakeUpUseCase(
            FakeSessionProvider(next_session),
            FakeSettingsRepository({}),
            user_repo,
            FakeMessagingService(),
        )

        with self.assertRaises(KeyError):
            await use_case.execute("weekly_digest", datetime(2026, 3, 30, 14, 0, tzinfo=UTC))

    async def test_weekly_digest_falls_back_to_utc_when_user_timezone_is_invalid(self) -> None:
        now = datetime(2026, 3, 30, 14, 0, tzinfo=UTC)
        next_session = Session(
            session_name="Practice 1",
            date_start=datetime(2026, 4, 10, 1, 30, tzinfo=UTC),
            location="Melbourne",
        )
        provider = FakeSessionProvider(next_session)
        settings_repo = FakeSettingsRepository(
            {"weekly_summary_msg": "Hora: {time} {flag} / TZ: {tz}"}
        )
        user_repo = FakeUserRepository()
        user_repo.active_users = [
            User(
                user_id=101,
                first_name="Ana",
                username="ana",
                status="active",
                timezone="Invalid/Timezone",
            )
        ]
        messenger = FakeMessagingService()
        use_case = WakeUpUseCase(provider, settings_repo, user_repo, messenger)

        await use_case.execute("weekly_digest", now)

        self.assertEqual(
            messenger.messages,
            [(101, f"Hora: {_format_user_datetime(next_session.date_start, 'Invalid/Timezone')} 🌐 / TZ: Invalid/Timezone")],
        )

    async def test_session_reminder_sends_when_session_is_within_alert_window(self) -> None:
        now = datetime(2026, 4, 10, 1, 15, tzinfo=UTC)
        next_session = Session(
            session_name="FORMULA 1 AUSTRALIAN GRAND PRIX 2026 - Race",
            date_start=datetime(2026, 4, 10, 1, 30, tzinfo=UTC),
            location="Melbourne",
            session_type="Race",
        )
        provider = FakeSessionProvider(next_session)
        settings_repo = FakeSettingsRepository(
            {
                "alert_lead_time": "15",
                "session_reminder_msg": (
                    "Hola {name}. GP: {circuit}. Hora local: {local_time} {flag} ({tz}). "
                    "Sesion: {session_type}"
                ),
            }
        )
        user_repo = FakeUserRepository()
        user_repo.active_users = [
            User(
                user_id=101,
                first_name="Ana",
                username="ana",
                status="active",
                timezone="America/Santiago",
            )
        ]
        messenger = FakeMessagingService()
        use_case = WakeUpUseCase(provider, settings_repo, user_repo, messenger)

        result = await use_case.execute("session_reminder", now)

        self.assertEqual(
            messenger.messages,
            [
                (
                    101,
                    (
                        "Hola Ana. GP: Melbourne. Hora local: "
                        f"{_format_user_datetime(next_session.date_start, 'America/Santiago')} "
                        "🇨🇱 (America/Santiago). Sesion: Race"
                    ),
                )
            ],
        )
        self.assertEqual(result["action_taken"], "session_reminder_sent")
        self.assertEqual(result["messages_sent"], 1)
        self.assertEqual(result["alert_lead_time_minutes"], 15)

    async def test_session_reminder_does_not_send_when_outside_alert_window(self) -> None:
        now = datetime(2026, 4, 10, 1, 0, tzinfo=UTC)
        next_session = Session(
            session_name="Practice 1",
            date_start=datetime(2026, 4, 10, 1, 30, tzinfo=UTC),
            location="Melbourne",
            session_type="Practice 1",
        )
        provider = FakeSessionProvider(next_session)
        settings_repo = FakeSettingsRepository(
            {
                "alert_lead_time": "15",
                "session_reminder_msg": "unused",
            }
        )
        user_repo = FakeUserRepository()
        user_repo.active_users = [
            User(
                user_id=101,
                first_name="Ana",
                username="ana",
                status="active",
                timezone="UTC",
            )
        ]
        messenger = FakeMessagingService()
        use_case = WakeUpUseCase(provider, settings_repo, user_repo, messenger)

        result = await use_case.execute("session_reminder", now)

        self.assertEqual(messenger.messages, [])
        self.assertEqual(result["action_taken"], "outside_alert_window")
        self.assertEqual(result["messages_sent"], 0)

    async def test_session_reminder_can_bypass_alert_window_when_disabled(self) -> None:
        now = datetime(2026, 4, 10, 1, 0, tzinfo=UTC)
        next_session = Session(
            session_name="Practice 1",
            date_start=datetime(2026, 4, 10, 1, 30, tzinfo=UTC),
            location="Melbourne",
            session_type="Practice 1",
        )
        provider = FakeSessionProvider(next_session)
        settings_repo = FakeSettingsRepository(
            {
                "alert_lead_time": "15",
                "session_reminder_msg": "Hola {name} - {session_type} - {local_time} {flag} ({tz})",
            }
        )
        user_repo = FakeUserRepository()
        user_repo.active_users = [
            User(
                user_id=101,
                first_name="Ana",
                username="ana",
                status="active",
                timezone="UTC",
            )
        ]
        messenger = FakeMessagingService()
        use_case = WakeUpUseCase(
            provider,
            settings_repo,
            user_repo,
            messenger,
            enforce_session_reminder_window=False,
        )

        result = await use_case.execute("session_reminder", now)

        self.assertEqual(
            messenger.messages,
            [(101, f"Hola Ana - Practice 1 - {_format_user_datetime(next_session.date_start, 'UTC')} 🌐 (UTC)")],
        )
        self.assertEqual(result["action_taken"], "session_reminder_sent")
        self.assertEqual(result["messages_sent"], 1)

    async def test_session_reminder_requires_valid_alert_lead_time(self) -> None:
        now = datetime(2026, 4, 10, 1, 15, tzinfo=UTC)
        next_session = Session(
            session_name="Race",
            date_start=datetime(2026, 4, 10, 1, 30, tzinfo=UTC),
            location="Melbourne",
            session_type="Race",
        )
        provider = FakeSessionProvider(next_session)
        settings_repo = FakeSettingsRepository(
            {
                "alert_lead_time": "soon",
                "session_reminder_msg": "unused",
            }
        )
        use_case = WakeUpUseCase(
            provider,
            settings_repo,
            FakeUserRepository(),
            FakeMessagingService(),
        )

        with self.assertRaisesRegex(ValueError, "Invalid bot setting value for key: alert_lead_time"):
            await use_case.execute("session_reminder", now)

    async def test_post_race_briefing_sends_podium_and_next_gp(self) -> None:
        now = datetime(2026, 4, 12, 18, 0, tzinfo=UTC)
        completed_race = Session(
            session_name="FORMULA 1 BAHRAIN GRAND PRIX 2026 - Race",
            date_start=datetime(2026, 4, 12, 15, 0, tzinfo=UTC),
            session_key=9158,
            meeting_key=1219,
            meeting_name="Bahrain Grand Prix",
            location="Sakhir",
            session_type="Race",
        )
        briefing = PostRaceBriefing(
            completed_race=completed_race,
            podium=(
                PodiumFinisher(1, "Max VERSTAPPEN", "Red Bull Racing"),
                PodiumFinisher(2, "Fernando ALONSO", "Aston Martin"),
                PodiumFinisher(3, "Esteban OCON", "Alpine"),
            ),
            next_grand_prix="Saudi Arabian Grand Prix",
            days_left=7,
        )
        provider = FakeSessionProvider(None, post_race_briefing=briefing)
        settings_repo = FakeSettingsRepository(
            {
                "post_race_briefing_msg": (
                    "¡GP de {circuit} Terminado! "
                    "🥇 {P1_driver} ({P1_team}) "
                    "🥈 {P2_driver} ({P2_team}) "
                    "🥉 {P3_driver} ({P3_team}) "
                    "Proxima cita: {next_gp} en {days_left} dias. "
                    "Usuario: {name}"
                )
            }
        )
        user_repo = FakeUserRepository()
        user_repo.active_users = [
            User(
                user_id=101,
                first_name="Camilo",
                username="camilo",
                status="active",
                timezone="UTC",
            )
        ]
        messenger = FakeMessagingService()
        use_case = WakeUpUseCase(provider, settings_repo, user_repo, messenger)

        result = await use_case.execute("post_race_briefing", now)

        self.assertEqual(provider.post_race_requested_instants, [now])
        self.assertEqual(
            messenger.messages,
            [
                (
                    101,
                    (
                        "¡GP de Sakhir Terminado! "
                        "🥇 Max VERSTAPPEN (Red Bull Racing) "
                        "🥈 Fernando ALONSO (Aston Martin) "
                        "🥉 Esteban OCON (Alpine) "
                        "Proxima cita: Saudi Arabian Grand Prix en 7 dias. "
                        "Usuario: Camilo"
                    ),
                )
            ],
        )
        self.assertEqual(
            result,
            {
                "status": "awake",
                "source": "OpenF1",
                "trigger_type": "post_race_briefing",
                "completed_race": {
                    "name": "FORMULA 1 BAHRAIN GRAND PRIX 2026 - Race",
                    "location": "Sakhir",
                    "utc_start": "2026-04-12T15:00:00Z",
                    "chile_start": _format_chile_datetime(completed_race.date_start),
                    "minutes_to_start": -180,
                },
                "next_gp": "Saudi Arabian Grand Prix",
                "days_left": 7,
                "action_taken": "post_race_briefing_sent",
                "messages_sent": 1,
            },
        )

    async def test_post_race_briefing_returns_no_completed_race_found_when_missing(self) -> None:
        now = datetime(2026, 4, 12, 18, 0, tzinfo=UTC)
        provider = FakeSessionProvider(None, post_race_briefing=None)
        use_case = WakeUpUseCase(
            provider,
            FakeSettingsRepository({}),
            FakeUserRepository(),
            FakeMessagingService(),
        )

        result = await use_case.execute("post_race_briefing", now)

        self.assertEqual(provider.post_race_requested_instants, [now])
        self.assertEqual(result["action_taken"], "no_completed_race_found")
        self.assertEqual(result["messages_sent"], 0)

    async def test_post_race_briefing_returns_no_active_users_when_there_are_none(self) -> None:
        now = datetime(2026, 4, 12, 18, 0, tzinfo=UTC)
        completed_race = Session(
            session_name="Race",
            date_start=datetime(2026, 4, 12, 15, 0, tzinfo=UTC),
            location="Sakhir",
        )
        briefing = PostRaceBriefing(
            completed_race=completed_race,
            podium=(
                PodiumFinisher(1, "Driver 1", "Team 1"),
                PodiumFinisher(2, "Driver 2", "Team 2"),
                PodiumFinisher(3, "Driver 3", "Team 3"),
            ),
            next_grand_prix="Saudi Arabian Grand Prix",
            days_left=7,
        )
        provider = FakeSessionProvider(None, post_race_briefing=briefing)
        use_case = WakeUpUseCase(
            provider,
            FakeSettingsRepository({"post_race_briefing_msg": "unused"}),
            FakeUserRepository(),
            FakeMessagingService(),
        )

        result = await use_case.execute("post_race_briefing", now)

        self.assertEqual(result["action_taken"], "no_active_users")
        self.assertEqual(result["messages_sent"], 0)


if __name__ == "__main__":
    unittest.main()

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from domain import PostRaceBriefing, Session, User
from ports import MessagingService, SessionProvider, SettingsRepository, UserRepository
from telegram_helpers import SUBSCRIBE_BUTTON_TEXT, SUBSCRIBE_CALLBACK_DATA


logger = logging.getLogger(__name__)
CHILE_TIMEZONE = ZoneInfo("America/Santiago")
COUNTRY_OPTIONS = [
    [
        {"text": "\U0001F1E8\U0001F1F1 Chile", "callback_data": "tz_cl"},
        {"text": "\U0001F1E6\U0001F1F7 Argentina", "callback_data": "tz_ar"},
    ],
    [
        {"text": "\U0001F1E8\U0001F1F4 Colombia", "callback_data": "tz_co"},
        {"text": "\U0001F1EA\U0001F1F8 Espa\u00f1a", "callback_data": "tz_es"},
    ],
    [
        {"text": "\U0001F1FA\U0001F1FE Uruguay", "callback_data": "tz_uy"},
    ],
]
TIMEZONE_BY_CALLBACK = {
    "tz_cl": "America/Santiago",
    "tz_ar": "America/Argentina/Buenos_Aires",
    "tz_co": "America/Bogota",
    "tz_es": "Europe/Madrid",
    "tz_uy": "America/Montevideo",
}
TIMEZONE_FLAG_BY_NAME = {
    "America/Santiago": "\U0001F1E8\U0001F1F1",
    "America/Argentina/Buenos_Aires": "\U0001F1E6\U0001F1F7",
    "America/Bogota": "\U0001F1E8\U0001F1F4",
    "Europe/Madrid": "\U0001F1EA\U0001F1F8",
    "America/Montevideo": "\U0001F1FA\U0001F1FE",
    "UTC": "\U0001F310",
}


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
        """Process supported Telegram bot commands."""

        if command == "/start":
            logger.info("Processing command=%s user_id=%s", command, user_id)
            existing_user = self._user_repo.get_user(user_id)
            if existing_user is not None:
                already_registered_text = self._settings_repo.get_value("already_registered")
                final_text = (
                    already_registered_text.replace("{name}", first_name)
                    .replace("{tz}", existing_user.timezone)
                )
                await self._messenger.send_message(user_id, final_text)
                logger.info("Completed command=%s user_id=%s existing_user=true", command, user_id)
                return

            user = User(
                user_id=user_id,
                first_name=first_name,
                username=username,
            )
            self._user_repo.save_user(user)
            welcome_template = self._settings_repo.get_value("welcome_msg")
            final_text = welcome_template.replace("{name}", first_name)
            await self._messenger.send_subscribe_prompt(
                user_id,
                final_text,
                SUBSCRIBE_BUTTON_TEXT,
                SUBSCRIBE_CALLBACK_DATA,
            )
            logger.info("Completed command=%s user_id=%s", command, user_id)
            return

        if command == "/subscribe":
            logger.info("Processing command=%s user_id=%s", command, user_id)
            self._user_repo.update_user_status(user_id, "active")
            text = self._settings_repo.get_value("subscribe_ok").replace("{name}", first_name)
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

        if command == "/set_country":
            logger.info("Processing command=%s user_id=%s", command, user_id)
            await self._messenger.send_country_options(
                user_id,
                "Elige tu pais para configurar la zona horaria:",
                COUNTRY_OPTIONS,
            )
            logger.info("Completed command=%s user_id=%s", command, user_id)
            return

        logger.warning("Ignoring unsupported command=%s user_id=%s", command, user_id)

    async def handle_country_callback(
        self,
        callback_query_id: str,
        callback_data: str,
        user_id: int,
        first_name: str,
        chat_id: int,
        message_id: int,
    ) -> None:
        """Persist the selected country timezone and confirm the callback."""

        timezone = TIMEZONE_BY_CALLBACK.get(callback_data)
        if timezone is None:
            logger.warning(
                "Ignoring unsupported country callback=%s user_id=%s",
                callback_data,
                user_id,
            )
            await self._messenger.answer_callback_query(
                callback_query_id,
                "Opcion no soportada.",
            )
            return

        logger.info(
            "Updating timezone callback=%s timezone=%s user_id=%s",
            callback_data,
            timezone,
            user_id,
        )
        self._user_repo.update_user_timezone(user_id, timezone)
        await self._messenger.answer_callback_query(
            callback_query_id,
            "",
        )
        confirmation_template = self._settings_repo.get_value("timezone_confirmation_text")
        confirmation_text = confirmation_template.replace("{name}", first_name)
        try:
            await self._messenger.edit_message(chat_id, message_id, confirmation_text)
        except Exception:
            logger.exception(
                "Falling back to send_message after edit failure user_id=%s message_id=%s",
                user_id,
                message_id,
            )
            await self._messenger.send_message(user_id, confirmation_text)

    async def handle_subscribe_callback(
        self,
        callback_query_id: str,
        user_id: int,
        first_name: str,
        chat_id: int,
        message_id: int,
    ) -> None:
        """Handle the inline onboarding CTA for enabling alerts."""

        logger.info("Processing subscribe callback user_id=%s", user_id)
        self._user_repo.update_user_status(user_id, "active")
        await self._messenger.answer_callback_query(callback_query_id, "")
        text = self._settings_repo.get_value("subscribe_ok").replace("{name}", first_name)
        try:
            await self._messenger.edit_message(chat_id, message_id, text)
        except Exception:
            logger.exception(
                "Falling back to send_message after subscribe edit failure user_id=%s message_id=%s",
                user_id,
                message_id,
            )
            await self._messenger.send_message(user_id, text)


class WakeUpUseCase:
    """Handle protected wake-up triggers used by automations or schedulers."""

    def __init__(
        self,
        session_provider: SessionProvider,
        settings_repo: SettingsRepository,
        user_repo: UserRepository,
        messenger: MessagingService,
        enforce_session_reminder_window: bool = True,
    ) -> None:
        self._session_provider = session_provider
        self._settings_repo = settings_repo
        self._user_repo = user_repo
        self._messenger = messenger
        self._enforce_session_reminder_window = enforce_session_reminder_window

    async def execute(
        self,
        trigger_type: str,
        now: datetime | None = None,
    ) -> dict[str, object]:
        """Dispatch the wake-up trigger to the appropriate action."""

        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)

        if trigger_type == "weekly_digest":
            return await self._send_weekly_digest(current_time)
        if trigger_type == "session_reminder":
            return await self._send_session_reminder(current_time)
        if trigger_type == "post_race_briefing":
            return await self._send_post_race_briefing(current_time)

        raise ValueError(f"Unsupported trigger_type: {trigger_type}")

    async def _send_weekly_digest(self, now: datetime) -> dict[str, object]:
        next_session = self._session_provider.get_next_race_after(now)
        response: dict[str, object] = {
            "status": "awake",
            "source": self._session_provider.get_source_name(),
            "trigger_type": "weekly_digest",
            "next_session": _build_session_payload(next_session, now),
        }
        if next_session is None:
            response["action_taken"] = "no_session_found"
            response["messages_sent"] = 0
            return response

        active_users = self._user_repo.list_active_users()
        if len(active_users) == 0:
            response["action_taken"] = "no_active_users"
            response["messages_sent"] = 0
            return response

        message_template = self._settings_repo.get_value("weekly_summary_msg")
        for user in active_users:
            message_text = _render_weekly_summary_message(
                message_template,
                next_session,
                user.first_name,
                user.timezone,
            )
            await self._messenger.send_message(user.user_id, message_text)

        response["action_taken"] = "weekly_digest_sent"
        response["messages_sent"] = len(active_users)
        return response

    async def _send_session_reminder(self, now: datetime) -> dict[str, object]:
        next_session = self._session_provider.get_next_session_after(now)
        response: dict[str, object] = {
            "status": "awake",
            "source": self._session_provider.get_source_name(),
            "trigger_type": "session_reminder",
            "next_session": _build_session_payload(next_session, now),
        }
        if next_session is None:
            response["action_taken"] = "no_session_found"
            response["messages_sent"] = 0
            return response

        alert_lead_time = self._get_alert_lead_time()
        response["alert_lead_time_minutes"] = alert_lead_time
        if (
            self._enforce_session_reminder_window
            and next_session.date_start - now > timedelta(minutes=alert_lead_time)
        ):
            response["action_taken"] = "outside_alert_window"
            response["messages_sent"] = 0
            return response

        active_users = self._user_repo.list_active_users()
        if len(active_users) == 0:
            response["action_taken"] = "no_active_users"
            response["messages_sent"] = 0
            return response

        message_template = self._settings_repo.get_value("session_reminder_msg")
        for user in active_users:
            message_text = _render_session_reminder_message(
                message_template,
                next_session,
                user.first_name,
                user.timezone,
            )
            await self._messenger.send_message(user.user_id, message_text)

        response["action_taken"] = "session_reminder_sent"
        response["messages_sent"] = len(active_users)
        return response

    async def _send_post_race_briefing(self, now: datetime) -> dict[str, object]:
        briefing = self._session_provider.get_post_race_briefing(now)
        response: dict[str, object] = {
            "status": "awake",
            "source": self._session_provider.get_source_name(),
            "trigger_type": "post_race_briefing",
        }
        if briefing is None:
            response["action_taken"] = "no_completed_race_found"
            response["messages_sent"] = 0
            return response

        response["completed_race"] = _build_session_payload(briefing.completed_race, now)
        response["next_gp"] = briefing.next_grand_prix
        response["days_left"] = briefing.days_left

        active_users = self._user_repo.list_active_users()
        if len(active_users) == 0:
            response["action_taken"] = "no_active_users"
            response["messages_sent"] = 0
            return response

        message_template = self._settings_repo.get_value("post_race_briefing_msg")
        for user in active_users:
            message_text = _render_post_race_briefing_message(
                message_template,
                briefing,
                user.first_name,
            )
            await self._messenger.send_message(user.user_id, message_text)

        response["action_taken"] = "post_race_briefing_sent"
        response["messages_sent"] = len(active_users)
        return response

    def _get_alert_lead_time(self) -> int:
        raw_value = self._settings_repo.get_value("alert_lead_time")
        try:
            lead_time = int(raw_value)
        except ValueError as exc:
            raise ValueError("Invalid bot setting value for key: alert_lead_time") from exc

        if lead_time < 0:
            raise ValueError("alert_lead_time must be zero or greater")

        return lead_time


def _build_session_payload(
    session: Session | None,
    now: datetime,
) -> dict[str, object] | None:
    """Return the session summary used by the wake-up endpoint."""

    if session is None:
        return None

    minutes_to_start = int((session.date_start - now).total_seconds() // 60)
    return {
        "name": session.session_name,
        "location": session.location,
        "utc_start": _format_utc_datetime(session.date_start),
        "chile_start": _format_chile_datetime(session.date_start),
        "minutes_to_start": minutes_to_start,
    }


def _render_weekly_summary_message(
    template: str,
    session: Session,
    first_name: str,
    timezone: str,
) -> str:
    """Replace weekly digest placeholders with session data."""

    return (
        template.replace("{name}", first_name)
        .replace("{location}", session.location or "TBC")
        .replace("{time}", _format_user_datetime(session.date_start, timezone))
        .replace("{flag}", _format_timezone_flag(timezone))
        .replace("{tz}", timezone)
        .replace("{session_name}", session.session_name)
    )


def _render_session_reminder_message(
    template: str,
    session: Session,
    first_name: str,
    timezone: str,
) -> str:
    """Replace session reminder placeholders with session and user data."""

    session_type = session.session_type or session.session_name
    return (
        template.replace("{name}", first_name)
        .replace("{circuit}", session.location or "TBC")
        .replace("{local_time}", _format_user_datetime(session.date_start, timezone))
        .replace("{flag}", _format_timezone_flag(timezone))
        .replace("{session_type}", session_type)
        .replace("{tz}", timezone)
    )


def _render_post_race_briefing_message(
    template: str,
    briefing: PostRaceBriefing,
    first_name: str,
) -> str:
    """Replace post-race placeholders with briefing data."""

    first_place, second_place, third_place = briefing.podium
    return (
        template.replace("{name}", first_name)
        .replace("{circuit}", briefing.completed_race.location or "TBC")
        .replace("{P1_driver}", first_place.driver_name)
        .replace("{P1_team}", first_place.team_name)
        .replace("{P2_driver}", second_place.driver_name)
        .replace("{P2_team}", second_place.team_name)
        .replace("{P3_driver}", third_place.driver_name)
        .replace("{P3_team}", third_place.team_name)
        .replace("{next_gp}", briefing.next_grand_prix or "TBC")
        .replace("{days_left}", str(briefing.days_left) if briefing.days_left is not None else "TBC")
    )


def _format_utc_datetime(value: datetime) -> str:
    """Serialize a datetime in the compact UTC format used by the endpoint."""

    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_chile_datetime(value: datetime) -> str:
    """Serialize a datetime in Chile local time for human-friendly messages."""

    return value.astimezone(CHILE_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")


def _format_user_datetime(value: datetime, timezone: str) -> str:
    """Serialize a time in the configured user timezone."""

    try:
        user_timezone = ZoneInfo(timezone)
    except Exception:
        user_timezone = UTC

    return value.astimezone(user_timezone).strftime("%H:%M")


def _format_timezone_flag(timezone: str) -> str:
    """Return the emoji flag associated with the configured timezone."""

    return TIMEZONE_FLAG_BY_NAME.get(timezone, "\U0001F310")

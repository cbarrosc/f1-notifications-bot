# pyright: reportMissingImports=false, reportMissingModuleSource=false

import logging
from datetime import UTC, datetime

import requests
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import Application
from supabase import Client, create_client

from domain import PodiumFinisher, PostRaceBriefing, Session, User


logger = logging.getLogger(__name__)
ALLOWED_SESSION_NAMES = {
    "Practice 1",
    "Practice 2",
    "Practice 3",
    "Qualifying",
    "Race",
    "Sprint Qualifying",
    "Sprint",
}


def _build_supabase_client(supabase_url: str, supabase_key: str) -> Client:
    """Create the shared Supabase client used by repositories."""

    return create_client(supabase_url, supabase_key)


class SupabaseUserRepository:
    """Persist and update bot users using Supabase."""

    def __init__(self, client: Client) -> None:
        self.client = client

    def get_user(self, user_id: int) -> User | None:
        """Return the current user row when it exists."""

        logger.info("Fetching user user_id=%s", user_id)
        response = (
            self.client.table("users")
            .select("user_id,first_name,username,status,timezone")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        response_data: object = response.data
        if not isinstance(response_data, list) or len(response_data) == 0:
            return None

        first_row = response_data[0]
        if not isinstance(first_row, dict):
            return None

        row_user_id = first_row.get("user_id")
        first_name = first_row.get("first_name")
        username = first_row.get("username")
        status = first_row.get("status")
        timezone = first_row.get("timezone")
        if (
            isinstance(row_user_id, int)
            and isinstance(first_name, str)
            and (username is None or isinstance(username, str))
            and isinstance(status, str)
            and isinstance(timezone, str)
        ):
            return User(
                user_id=row_user_id,
                first_name=first_name,
                username=username,
                status=status,
                timezone=timezone,
            )

        return None

    def save_user(self, user: User) -> None:
        """Insert a user or refresh profile data without resetting the status."""

        existing_user = self.get_user(user.user_id)
        record = user.to_record()
        if existing_user is not None:
            record["status"] = existing_user.status
            record["timezone"] = existing_user.timezone

        # Upsert avoids duplicates when the same user runs /start again.
        logger.info("Upserting user user_id=%s", user.user_id)
        self.client.table("users").upsert(
            record,
            on_conflict="user_id",
        ).execute()

    def update_user_status(self, user_id: int, status: str) -> None:
        """Update the user's status if the row already exists."""

        logger.info("Updating user status user_id=%s status=%s", user_id, status)
        self.client.table("users").update({"status": status}).eq("user_id", user_id).execute()

    def update_user_timezone(self, user_id: int, timezone: str) -> None:
        """Update the user's preferred timezone."""

        logger.info("Updating user timezone user_id=%s timezone=%s", user_id, timezone)
        self.client.table("users").update({"timezone": timezone}).eq("user_id", user_id).execute()

    def list_active_users(self) -> list[User]:
        """Return active users with the profile data needed for messaging."""

        logger.info("Fetching active users")
        response = self.client.table("users").select("user_id,first_name,username,status,timezone").eq("status", "active").execute()
        response_data: object = response.data
        if not isinstance(response_data, list):
            raise ValueError("Invalid users response payload.")

        active_users: list[User] = []
        for row in response_data:
            if not isinstance(row, dict):
                continue

            user_id = row.get("user_id")
            first_name = row.get("first_name")
            username = row.get("username")
            status = row.get("status")
            timezone = row.get("timezone")
            if (
                isinstance(user_id, int)
                and isinstance(first_name, str)
                and (username is None or isinstance(username, str))
                and isinstance(status, str)
                and (timezone is None or isinstance(timezone, str))
            ):
                active_users.append(
                    User(
                        user_id=user_id,
                        first_name=first_name,
                        username=username,
                        status=status,
                        timezone=timezone,
                    )
                )

        return active_users


class SupabaseSettingsRepository:
    """Read bot configuration values from Supabase."""

    def __init__(self, client: Client) -> None:
        self.client = client

    def get_value(self, key: str) -> str:
        """Get a required bot setting or fail when it does not exist."""

        # Validate the response shape because the SDK exposes `data`
        # with a broad type and does not always guarantee content.
        logger.info("Fetching bot setting key=%s", key)
        response = self.client.table("bot_settings").select("value").eq("key", key).execute()
        response_data: object = response.data
        if not isinstance(response_data, list) or len(response_data) == 0:
            raise ValueError(f"Missing bot setting: {key}")

        first_row = response_data[0]
        if not isinstance(first_row, dict):
            raise ValueError(f"Invalid bot setting row for key: {key}")

        value = first_row.get("value")
        if isinstance(value, str):
            return value

        raise ValueError(f"Invalid bot setting value for key: {key}")


class TelegramClient:
    """Wrap the Telegram client used to send bot messages."""

    def __init__(self, bot_token: str) -> None:
        self.app = Application.builder().token(bot_token).build()

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a simple message to a Telegram chat."""

        logger.info("Sending Telegram message chat_id=%s", chat_id)
        await self.app.bot.send_message(
            chat_id=chat_id,
            text=text,
        )

    async def send_country_options(
        self,
        chat_id: int,
        text: str,
        options: list[list[dict[str, str]]],
    ) -> None:
        """Send an inline keyboard with country options."""

        keyboard = [
            [
                InlineKeyboardButton(
                    button["text"],
                    callback_data=button["callback_data"],
                )
                for button in row
            ]
            for row in options
        ]
        logger.info("Sending Telegram country selector chat_id=%s", chat_id)
        await self.app.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def send_subscribe_prompt(
        self,
        chat_id: int,
        text: str,
        button_text: str,
        callback_data: str,
    ) -> None:
        """Send a one-button inline keyboard for the subscribe onboarding step."""

        keyboard = [[InlineKeyboardButton(button_text, callback_data=callback_data)]]
        logger.info("Sending Telegram subscribe prompt chat_id=%s", chat_id)
        await self.app.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str,
    ) -> None:
        """Acknowledge a Telegram callback query to stop the loading state."""

        logger.info("Answering callback query callback_query_id=%s", callback_query_id)
        await self.app.bot.answer_callback_query(
            callback_query_id=callback_query_id,
            text=text,
        )

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
    ) -> None:
        """Edit a previously sent Telegram message."""

        logger.info("Editing Telegram message chat_id=%s message_id=%s", chat_id, message_id)
        await self.app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
        )


class OpenF1SessionProvider:
    """Read session data from the OpenF1 API."""

    def __init__(self, base_url: str = "https://api.openf1.org/v1") -> None:
        self._base_url = base_url.rstrip("/")

    def get_next_session_after(self, when: datetime) -> Session | None:
        """Fetch and return the next upcoming session after the provided time."""

        year = when.year
        sessions = self._get_sessions_for_year(year)
        upcoming_sessions = [
            session for session in sessions if session.date_start > when
        ]
        if not upcoming_sessions:
            return None

        next_session = min(upcoming_sessions, key=lambda session: session.date_start)
        meeting_details = self._get_meeting_details(year, next_session.meeting_key)
        return Session(
            session_name=_build_session_display_name(
                next_session.session_name,
                meeting_details["name"],
            ),
            date_start=next_session.date_start,
            session_key=next_session.session_key,
            meeting_key=next_session.meeting_key,
            meeting_name=meeting_details["short_name"],
            location=meeting_details["location"],
            session_type=next_session.session_name,
        )

    def get_next_race_after(self, when: datetime) -> Session | None:
        """Fetch and return the next upcoming race after the provided time."""

        year = when.year
        sessions = self._get_sessions_for_year(year, session_name="Race")
        upcoming_races = [
            session for session in sessions if session.date_start > when
        ]
        if not upcoming_races:
            return None

        next_race = min(upcoming_races, key=lambda session: session.date_start)
        meeting_details = self._get_meeting_details(year, next_race.meeting_key)
        return Session(
            session_name=_build_session_display_name(
                next_race.session_name,
                meeting_details["name"],
            ),
            date_start=next_race.date_start,
            date_end=next_race.date_end,
            session_key=next_race.session_key,
            meeting_key=next_race.meeting_key,
            meeting_name=meeting_details["short_name"],
            location=meeting_details["location"],
            session_type=next_race.session_name,
        )

    def get_post_race_briefing(self, when: datetime) -> PostRaceBriefing | None:
        """Fetch the latest completed race, its podium and the next grand prix."""

        sessions = self._get_sessions_for_year(when.year, session_name="Race")
        previous_races = sorted(
            [
                session
                for session in sessions
                if session.date_start < when
            ],
            key=lambda session: session.date_start,
            reverse=True,
        )
        if not previous_races:
            return None

        completed_race = previous_races[0]
        if completed_race.session_key is None:
            return None
        meeting_details = self._get_meeting_details(when.year, completed_race.meeting_key)
        podium = self._get_session_podium(completed_race.session_key)
        if len(podium) < 3:
            return None

        upcoming_races = [
            session
            for session in sessions
            if session.date_start > when
        ]
        next_grand_prix: str | None = None
        days_left: int | None = None
        if upcoming_races:
            next_race = min(upcoming_races, key=lambda session: session.date_start)
            next_meeting = self._get_meeting_details(when.year, next_race.meeting_key)
            next_grand_prix = next_meeting["short_name"] or next_meeting["name"]
            days_left = (next_race.date_start.date() - when.date()).days

        return PostRaceBriefing(
            completed_race=Session(
                session_name=_build_session_display_name(
                    completed_race.session_name,
                    meeting_details["name"],
                ),
                date_start=completed_race.date_start,
                date_end=completed_race.date_end,
                session_key=completed_race.session_key,
                meeting_key=completed_race.meeting_key,
                meeting_name=meeting_details["short_name"],
                location=meeting_details["location"],
                session_type=completed_race.session_name,
            ),
            podium=(podium[0], podium[1], podium[2]),
            next_grand_prix=next_grand_prix,
            days_left=days_left,
        )

    def get_source_name(self) -> str:
        """Return the human-readable source label used by the endpoint."""

        return "OpenF1"

    def _get_sessions_for_year(self, year: int, session_name: str | None = None) -> list[Session]:
        """Fetch the sessions for the requested year."""

        logger.info("Fetching OpenF1 sessions year=%s session_name=%s", year, session_name)
        params: dict[str, object] = {"year": year}
        if session_name is not None:
            params["session_name"] = session_name
        response = requests.get(
            f"{self._base_url}/sessions",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        payload: object = response.json()
        if not isinstance(payload, list):
            raise ValueError("Invalid OpenF1 response payload.")

        sessions: list[Session] = []
        for row in payload:
            if not isinstance(row, dict):
                continue

            session_name = row.get("session_name")
            raw_date_start = row.get("date_start")
            raw_date_end = row.get("date_end")
            if not isinstance(session_name, str) or not isinstance(raw_date_start, str):
                continue
            if session_name not in ALLOWED_SESSION_NAMES:
                continue

            meeting_key = row.get("meeting_key")
            session_key = row.get("session_key")
            sessions.append(
                Session(
                    session_name=session_name,
                    date_start=_parse_openf1_datetime(raw_date_start),
                    date_end=_parse_openf1_datetime(raw_date_end) if isinstance(raw_date_end, str) else None,
                    session_key=session_key if isinstance(session_key, int) else None,
                    meeting_key=meeting_key if isinstance(meeting_key, int) else None,
                    session_type=session_name,
                )
            )

        return sessions

    def _get_meeting_details(self, year: int, meeting_key: int | None) -> dict[str, str | None]:
        """Return the official meeting name and location for a specific meeting key."""

        if meeting_key is None:
            return {"name": None, "short_name": None, "location": None}

        logger.info("Fetching OpenF1 meeting year=%s meeting_key=%s", year, meeting_key)
        response = requests.get(
            f"{self._base_url}/meetings",
            params={"year": year, "meeting_key": meeting_key},
            timeout=10,
        )
        response.raise_for_status()
        payload: object = response.json()
        if not isinstance(payload, list):
            raise ValueError("Invalid OpenF1 meetings payload.")

        for row in payload:
            if not isinstance(row, dict):
                continue

            meeting_official_name = row.get("meeting_official_name")
            meeting_name = row.get("meeting_name")
            location = row.get("location")
            resolved_name = None
            if isinstance(meeting_official_name, str) and meeting_official_name:
                resolved_name = meeting_official_name

            if resolved_name is None and isinstance(meeting_name, str) and meeting_name:
                resolved_name = meeting_name

            return {
                "name": resolved_name,
                "short_name": meeting_name if isinstance(meeting_name, str) else None,
                "location": location if isinstance(location, str) else None,
            }

        return {"name": None, "short_name": None, "location": None}

    def _get_session_podium(self, session_key: int) -> list[PodiumFinisher]:
        """Fetch the top three session results enriched with driver and team data."""

        logger.info("Fetching OpenF1 session results session_key=%s", session_key)
        response = requests.get(
            f"{self._base_url}/session_result?session_key={session_key}&position%3C=3",
            timeout=10,
        )
        response.raise_for_status()
        payload: object = response.json()
        if not isinstance(payload, list):
            raise ValueError("Invalid OpenF1 session results payload.")

        podium: list[PodiumFinisher] = []
        for row in payload:
            if not isinstance(row, dict):
                continue

            position = row.get("position")
            driver_number = row.get("driver_number")
            if not isinstance(position, int) or not isinstance(driver_number, int):
                continue

            driver_details = self._get_driver_details(session_key, driver_number)
            podium.append(
                PodiumFinisher(
                    position=position,
                    driver_name=driver_details["name"] or str(driver_number),
                    team_name=driver_details["team"] or "TBC",
                )
            )

        podium.sort(key=lambda finisher: finisher.position)
        return podium

    def _get_driver_details(self, session_key: int, driver_number: int) -> dict[str, str | None]:
        """Fetch a driver's display name and team for a specific session."""

        logger.info(
            "Fetching OpenF1 driver details session_key=%s driver_number=%s",
            session_key,
            driver_number,
        )
        response = requests.get(
            f"{self._base_url}/drivers",
            params={"session_key": session_key, "driver_number": driver_number},
            timeout=10,
        )
        response.raise_for_status()
        payload: object = response.json()
        if not isinstance(payload, list):
            raise ValueError("Invalid OpenF1 drivers payload.")

        for row in payload:
            if not isinstance(row, dict):
                continue

            full_name = row.get("full_name")
            team_name = row.get("team_name")
            return {
                "name": full_name if isinstance(full_name, str) else None,
                "team": team_name if isinstance(team_name, str) else None,
            }

        return {"name": None, "team": None}


def _parse_openf1_datetime(value: str) -> datetime:
    """Parse OpenF1 datetimes and normalize them to UTC."""

    normalized_value = value.replace("Z", "+00:00")
    parsed_value = datetime.fromisoformat(normalized_value)
    if parsed_value.tzinfo is None:
        return parsed_value.replace(tzinfo=UTC)

    return parsed_value.astimezone(UTC)


def _build_session_display_name(
    session_name: str,
    meeting_name: str | None,
) -> str:
    """Combine official meeting name and session name when available."""

    if not meeting_name:
        return session_name

    return f"{meeting_name} - {session_name}"

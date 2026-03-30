from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    """Represent the bot user inside the domain."""

    # The domain entity stays immutable to avoid accidental changes
    # once constructed inside the use case.
    user_id: int
    first_name: str
    username: str | None
    status: str = "inactive"
    timezone: str = "UTC"

    def to_record(self) -> dict[str, int | str]:
        """Convert the entity to the persistable format expected by Supabase."""

        # This format mirrors the structure expected by Supabase.
        return {
            "user_id": self.user_id,
            "first_name": self.first_name,
            "username": self.username,
            "status": self.status,
            "timezone": self.timezone,
        }


@dataclass(frozen=True)
class Session:
    """Represent an OpenF1 session relevant for notification checks."""

    session_name: str
    date_start: datetime
    meeting_key: int | None = None
    location: str | None = None

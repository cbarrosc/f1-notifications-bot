from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    """Represent the bot user inside the domain."""

    # The domain entity stays immutable to avoid accidental changes
    # once constructed inside the use case.
    user_id: int
    first_name: str
    username: str | None
    status: str = "inactive"

    def to_record(self) -> dict[str, int | str | None]:
        """Convert the entity to the persistable format expected by Supabase."""

        # This format mirrors the structure expected by Supabase.
        return {
            "user_id": self.user_id,
            "first_name": self.first_name,
            "username": self.username,
            "status": self.status,
        }

SUBSCRIBE_BUTTON_TEXT = "\U0001F514 Activar alertas"
SUBSCRIBE_CALLBACK_DATA = "subscribe_cta"


def extract_command(text: str | None) -> str | None:
    """Normalize Telegram command text."""

    if text is None:
        return None

    first_token = text.strip().split(maxsplit=1)
    if len(first_token) == 0:
        return None

    command = first_token[0]
    if "@" in command:
        command = command.split("@", maxsplit=1)[0]

    return command


class RecentUpdateRegistry:
    """Track recent Telegram update ids to avoid duplicate processing."""

    def __init__(self, capacity: int = 1000) -> None:
        self._capacity = capacity
        self._seen: set[int] = set()
        self._order: list[int] = []

    def mark_seen(self, update_id: int) -> bool:
        """Return False when the update id was already processed."""

        if update_id in self._seen:
            return False

        self._seen.add(update_id)
        self._order.append(update_id)
        if len(self._order) > self._capacity:
            oldest = self._order.pop(0)
            self._seen.discard(oldest)

        return True

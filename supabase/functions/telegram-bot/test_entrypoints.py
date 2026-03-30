import unittest

from telegram_helpers import (
    RecentUpdateRegistry,
    extract_command,
)


class EntryPointsTest(unittest.TestCase):
    def test_extract_command_supports_bot_suffix(self) -> None:
        self.assertEqual(extract_command("/set_country@f1notificationsbot"), "/set_country")

    def test_extract_command_supports_extra_arguments(self) -> None:
        self.assertEqual(extract_command("/set_country extra"), "/set_country")

    def test_extract_command_returns_none_for_empty_text(self) -> None:
        self.assertEqual(extract_command(""), None)

    def test_recent_update_registry_rejects_duplicates(self) -> None:
        registry = RecentUpdateRegistry()

        self.assertEqual(registry.mark_seen(123), True)
        self.assertEqual(registry.mark_seen(123), False)


if __name__ == "__main__":
    unittest.main()

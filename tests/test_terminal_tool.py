from __future__ import annotations

import subprocess
import unittest
from datetime import datetime
from unittest.mock import patch

from backend.tools.terminal_tool import run_terminal


class TerminalToolTestCase(unittest.TestCase):
    def test_unix_date_weekday_format_is_portable(self) -> None:
        self.assertEqual(run_terminal("date +%A"), datetime.now().strftime("%A"))

    def test_plain_date_is_non_interactive(self) -> None:
        self.assertEqual(run_terminal("date"), datetime.now().strftime("%Y-%m-%d"))

    def test_timeout_is_returned_instead_of_raised(self) -> None:
        with patch(
            "backend.tools.terminal_tool.subprocess.run",
            side_effect=subprocess.TimeoutExpired("slow command", 10),
        ):
            result = run_terminal("slow command")

        self.assertIn("Command timed out", result)
        self.assertIn("slow command", result)

    def test_blocked_command_is_reported_without_execution(self) -> None:
        with patch("backend.tools.terminal_tool.subprocess.run") as run:
            result = run_terminal("shutdown /s")

        self.assertEqual(result, "Blocked command")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()

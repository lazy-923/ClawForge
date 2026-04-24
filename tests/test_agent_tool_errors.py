from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.graph.agent import AgentManager


class AgentToolErrorTestCase(unittest.TestCase):
    def test_terminal_tool_error_is_returned_as_observation(self) -> None:
        manager = AgentManager()
        terminal_tool = next(tool for tool in manager.langchain_tools if tool.name == "terminal")

        with patch("backend.graph.agent.run_terminal", side_effect=RuntimeError("boom")):
            result = terminal_tool.invoke({"command": "date +%A"})

        self.assertIn("Tool `terminal` failed", result)
        self.assertIn("RuntimeError", result)
        self.assertIn("boom", result)

    def test_read_file_tool_error_is_returned_as_observation(self) -> None:
        manager = AgentManager()
        read_file_tool = next(tool for tool in manager.langchain_tools if tool.name == "read_file")

        with patch("backend.graph.agent.read_file", side_effect=FileNotFoundError("missing")):
            result = read_file_tool.invoke({"path": "missing.txt"})

        self.assertIn("Tool `read_file` failed", result)
        self.assertIn("FileNotFoundError", result)
        self.assertIn("missing", result)


if __name__ == "__main__":
    unittest.main()

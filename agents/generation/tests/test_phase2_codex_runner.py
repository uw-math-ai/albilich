from __future__ import annotations

import unittest

from agents.generation.phase2.codex_runner import DEFAULT_CODEX_MODEL, DEFAULT_REASONING_EFFORT


class CodexRunnerDefaultsTests(unittest.TestCase):
    def test_codex_defaults_to_sol_extra_high(self) -> None:
        self.assertEqual(DEFAULT_CODEX_MODEL, "gpt-5.6-sol")
        self.assertEqual(DEFAULT_REASONING_EFFORT, "xhigh")


if __name__ == "__main__":
    unittest.main()

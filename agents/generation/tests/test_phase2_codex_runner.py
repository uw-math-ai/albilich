from __future__ import annotations

import unittest

from agents.generation.phase2.codex_runner import extract_patch_from_text


class CodexPatchExtractionTests(unittest.TestCase):
    def test_preserves_unescaped_latex_commands_with_valid_json_prefixes(self) -> None:
        raw = (
            r'{"schema_version":1,"operations":[{"content":"'
            r'Let \\(W\neq0\\), \\beta, \\frac{x}{y}, \\rho, \\text{x}, and A\nleq B.'
            r'"}]}'
        )

        patch, error = extract_patch_from_text(raw)

        self.assertEqual(error, "")
        self.assertIsNotNone(patch)
        self.assertEqual(
            patch["operations"][0]["content"],
            r"Let \(W\neq0\), \beta, \frac{x}{y}, \rho, \text{x}, and A\nleq B.",
        )

    def test_leaves_ordinary_json_newlines_and_escaped_latex_unchanged(self) -> None:
        raw = (
            r'{"schema_version":1,"operations":[{"content":"'
            r'line one\nline two; \\(W\\neq0\\)'
            r'"}]}'
        )

        patch, error = extract_patch_from_text(raw)

        self.assertEqual(error, "")
        self.assertIsNotNone(patch)
        self.assertEqual(patch["operations"][0]["content"], "line one\nline two; \\(W\\neq0\\)")


if __name__ == "__main__":
    unittest.main()

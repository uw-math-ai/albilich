from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.writing.rubric import (
    AUTOFIXES,
    CHECKABILITIES,
    CRITICS,
    LAYERS,
    SCOPES,
    SEVERITIES,
    lint_rules,
    load_rubric,
    load_rubric_report,
    rules_for_critic,
)

RUBRIC_DIR = REPO_ROOT / "math-writing-harness" / "rubric"


class WritingRubricLoadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rules, cls.warnings = load_rubric_report(RUBRIC_DIR)
        cls.by_id = {rule.rule_id: rule for rule in cls.rules}

    def test_rubric_dir_exists(self) -> None:
        self.assertTrue(RUBRIC_DIR.is_dir(), f"missing rubric dir: {RUBRIC_DIR}")

    def test_parses_at_least_150_rules(self) -> None:
        self.assertGreaterEqual(len(self.rules), 150)

    def test_warning_count_is_small(self) -> None:
        print(f"rubric parse warnings ({len(self.warnings)}): {self.warnings}")
        self.assertLess(len(self.warnings), 15)

    def test_rule_ids_unique(self) -> None:
        self.assertEqual(len(self.by_id), len(self.rules))

    def test_known_rule_l1_cite_03(self) -> None:
        rule = self.by_id["L1-CITE-03"]
        self.assertEqual(rule.layer, "L1")
        self.assertEqual(rule.source, "CITE")
        self.assertEqual(rule.severity, "blocker")
        self.assertEqual(rule.checkability, "lint")
        self.assertEqual(rule.owner_critic, "provenance_auditor")
        self.assertIn("Residue scan", rule.statement)

    def test_known_rule_l4_logic_01(self) -> None:
        rule = self.by_id["L4-LOGIC-01"]
        self.assertEqual(rule.layer, "L4")
        self.assertEqual(rule.checkability, "lint")
        self.assertEqual(rule.owner_critic, "pedant")
        self.assertEqual(rule.autofix, "safe")
        self.assertEqual(rule.severity, "minor")

    def test_known_rule_l3_sell_01(self) -> None:
        rule = self.by_id["L3-SELL-01"]
        self.assertEqual(rule.layer, "L3")
        self.assertEqual(rule.checkability, "llm")
        self.assertEqual(rule.owner_critic, "skeptical_editor")
        self.assertEqual(rule.severity, "major")

    def test_terminology_governance_rules_are_auditable(self) -> None:
        standard = self.by_id["L3-TERM-01"]
        coinage = self.by_id["L3-TERM-02"]
        consultation = self.by_id["L3-TERM-03"]
        for rule in (standard, coinage, consultation):
            self.assertEqual("L3", rule.layer)
            self.assertEqual("llm", rule.checkability)
        self.assertEqual("major", standard.severity)
        self.assertIn("standard terminology", standard.statement.lower())
        self.assertEqual("major", coinage.severity)
        self.assertIn("justification", coinage.statement.lower())
        self.assertEqual("blocker", consultation.severity)
        self.assertIn("human", consultation.statement.lower())

    def test_introduction_high_control_rules_are_auditable(self) -> None:
        for rule_id in ("L3-INTRO-08", "L3-INTRO-09", "L3-INTRO-10"):
            self.assertIn(rule_id, self.by_id)
        self.assertEqual("major", self.by_id["L3-INTRO-08"].severity)
        self.assertIn("big-picture", self.by_id["L3-INTRO-08"].statement.lower())
        self.assertEqual("major", self.by_id["L3-INTRO-09"].severity)
        self.assertIn("causal", self.by_id["L3-INTRO-09"].statement.lower())
        self.assertEqual("meta", self.by_id["L3-INTRO-10"].checkability)
        self.assertIn("dedicated", self.by_id["L3-INTRO-10"].statement.lower())

    def test_known_hard_house_rules_l4_house_07_08(self) -> None:
        # The two deterministically enforced house hard rules: section openers
        # and the "we"-collocation discipline. Both lint, both major.
        for rule_id, fragment in (
            ("L4-HOUSE-07", "In this section, we"),
            ("L4-HOUSE-08", "we recall"),
        ):
            rule = self.by_id[rule_id]
            self.assertEqual(rule.layer, "L4")
            self.assertEqual(rule.checkability, "lint")
            self.assertEqual(rule.severity, "major")
            self.assertEqual(rule.owner_critic, "pedant")
            self.assertIn(fragment, rule.statement)

    def test_section_substantiality_rules_l4_house_09_10_11(self) -> None:
        # Stub sections and fragmentation are major lint rules; bullet
        # narration is a minor lint rule. All three are pedant-owned.
        for rule_id, severity, fragment in (
            ("L4-HOUSE-09", "major", "120 words"),
            ("L4-HOUSE-10", "major", "fragment"),
            ("L4-HOUSE-11", "minor", "bullet"),
        ):
            rule = self.by_id[rule_id]
            self.assertEqual(rule.layer, "L4")
            self.assertEqual(rule.checkability, "lint")
            self.assertEqual(rule.severity, severity)
            self.assertEqual(rule.owner_critic, "pedant")
            self.assertIn(fragment, rule.statement.lower())

    def test_layer_defaults_applied(self) -> None:
        # No explicit severity marker: falls back to the layer default.
        self.assertEqual(self.by_id["L1-FAITH-04"].severity, "blocker")
        # L2 default is major (stranded-reader failures).
        self.assertEqual(self.by_id["L2-CLARITY-02"].severity, "major")
        # L4 default is minor.
        self.assertEqual(self.by_id["L4-SENT-01"].severity, "minor")

    def test_checkability_normalization(self) -> None:
        # "[lint/llm]" resolves to its first token.
        self.assertEqual(self.by_id["L2-QUANT-01"].checkability, "lint")
        # "[tool]" folds into the verify tier.
        self.assertEqual(self.by_id["L1-CITE-01"].checkability, "verify")
        # "[meta]" is kept as-is.
        self.assertEqual(self.by_id["L5-AI-01"].checkability, "meta")

    def test_owner_critic_defaults(self) -> None:
        self.assertEqual(self.by_id["L1-GLOBAL-01"].owner_critic, "referee")
        self.assertEqual(self.by_id["L1-FAITH-01"].owner_critic, "provenance_auditor")
        self.assertEqual(self.by_id["L2-JUSTIFY-01"].owner_critic, "confused_reader")
        self.assertEqual(self.by_id["L3-ORG-01"].owner_critic, "skeptical_editor")
        self.assertEqual(self.by_id["L4-GRAM-01"].owner_critic, "pedant")
        self.assertEqual(self.by_id["L5-TEX-01"].owner_critic, "pedant")
        self.assertEqual(self.by_id["L5-AI-02"].owner_critic, "provenance_auditor")
        self.assertEqual(self.by_id["L5-VENUE-01"].owner_critic, "provenance_auditor")

    def test_autofix_extraction(self) -> None:
        # "autofix: **safe** (strip) + re-flag ..." resolves to "safe".
        self.assertEqual(self.by_id["L5-AI-03"].autofix, "safe")
        self.assertEqual(self.by_id["L2-DEF-05"].autofix, "safe")
        # No autofix marker at all.
        self.assertEqual(self.by_id["L1-GLOBAL-01"].autofix, "none")

    def test_every_rule_has_valid_enum_fields(self) -> None:
        for rule in self.rules:
            with self.subTest(rule_id=rule.rule_id):
                self.assertIn(rule.layer, LAYERS)
                self.assertIn(rule.severity, SEVERITIES)
                self.assertIn(rule.scope, SCOPES)
                self.assertIn(rule.checkability, CHECKABILITIES)
                self.assertIn(rule.owner_critic, CRITICS)
                self.assertIn(rule.autofix, AUTOFIXES)
                self.assertTrue(rule.rule_id.startswith(rule.layer + "-"))
                self.assertTrue(rule.statement.strip())
                self.assertTrue(rule.source)

    def test_all_layers_represented(self) -> None:
        layers = {rule.layer for rule in self.rules}
        self.assertEqual(layers, set(LAYERS))

    def test_load_rubric_matches_report(self) -> None:
        self.assertEqual(load_rubric(RUBRIC_DIR), self.rules)

    def test_rules_for_critic_partitions_rules(self) -> None:
        total = 0
        for critic in CRITICS:
            subset = rules_for_critic(self.rules, critic)
            total += len(subset)
            for rule in subset:
                self.assertEqual(rule.owner_critic, critic)
        self.assertEqual(total, len(self.rules))

    def test_lint_rules_subset(self) -> None:
        subset = lint_rules(self.rules)
        self.assertTrue(subset)
        for rule in subset:
            self.assertEqual(rule.checkability, "lint")
        self.assertIn("L1-CITE-03", {rule.rule_id for rule in subset})


if __name__ == "__main__":
    unittest.main()

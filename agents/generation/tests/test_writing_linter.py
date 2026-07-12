from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.writing.linter import (
    EXCERPT_MAX_CHARS,
    Finding,
    run_all,
    run_lint,
    run_residue_scan,
)


def rule_ids(findings: list[Finding]) -> set[str]:
    return {finding.rule_id for finding in findings}


def by_rule(findings: list[Finding], rule_id: str) -> list[Finding]:
    return [finding for finding in findings if finding.rule_id == rule_id]


class ResidueScanTest(unittest.TestCase):
    def test_ai_phrases_flagged_as_blockers(self) -> None:
        text = "As an AI language model, I cannot verify this.\n"
        findings = run_residue_scan(text)
        self.assertTrue(findings)
        for finding in findings:
            self.assertEqual(finding.rule_id, "L1-CITE-03")
            self.assertEqual(finding.severity, "blocker")
            self.assertEqual(finding.line, 1)

    def test_scaffolding_markers(self) -> None:
        text = "A clean line.\nTODO: prove the lemma.\nFIXME later.\nXXX\n"
        findings = run_residue_scan(text)
        self.assertEqual([f.line for f in findings], [2, 3, 4])

    def test_todo_lowercase_not_flagged(self) -> None:
        # Scaffolding markers are matched uppercase-only (conservative).
        self.assertEqual(run_residue_scan("we todo not flag lowercase todo.\n"), [])

    def test_here_is_the_only_at_line_start(self) -> None:
        flagged = run_residue_scan("Here is the proof of the claim.\n")
        self.assertEqual(len(flagged), 1)
        clean = run_residue_scan("What we presented here is the main theorem.\n")
        self.assertEqual(clean, [])

    def test_language_model_requires_article(self) -> None:
        flagged = run_residue_scan("Trained as a language model, it refuses.\n")
        self.assertTrue(flagged)
        clean = run_residue_scan("Language models were not involved here.\n")
        self.assertEqual(clean, [])

    def test_unresolved_reference_double_question_mark(self) -> None:
        flagged = run_residue_scan("By Theorem ?? the claim follows.\n")
        self.assertEqual(len(flagged), 1)
        self.assertIn("??", flagged[0].message)
        # Ordinary questions and single "?" are untouched.
        self.assertEqual(run_residue_scan("Is this sharp? We do not know.\n"), [])

    def test_triple_question_marks_and_citation_placeholders(self) -> None:
        text = "The bound is \\ldots???\nSee [CITATION NEEDED] and [REF].\n"
        findings = run_residue_scan(text)
        self.assertEqual([f.line for f in findings], [1, 2, 2])
        # Bracketed prose starting with "Ref..." as a word is not a placeholder.
        self.assertEqual(run_residue_scan("[Refined estimates appear in Section 2.]\n"), [])

    def test_placeholder_and_prompt_echoes(self) -> None:
        text = "placeholder text\n<insert proof>\nAs instructed, we omit it.\nper the prompt\n"
        findings = run_residue_scan(text)
        self.assertEqual([f.line for f in findings], [1, 2, 3, 4])

    def test_clean_math_text_has_no_residue(self) -> None:
        text = (
            "We prove that every finite group of odd order is solvable.\n"
            "The proof occupies Sections 2 through 5.\n"
        )
        self.assertEqual(run_residue_scan(text), [])


class MathStrippingTest(unittest.TestCase):
    def test_logic_symbol_inside_inline_math_not_flagged(self) -> None:
        findings = run_lint("The statement $\\forall x \\in X$ holds, where ∀ is read aloud.\n")
        logic = by_rule(findings, "L4-LOGIC-01")
        # Only the prose ∀ is flagged; the $\forall$ is inside math.
        self.assertEqual(len(logic), 1)
        self.assertEqual(logic[0].line, 1)

    def test_logic_symbol_in_prose_flagged(self) -> None:
        findings = run_lint("This holds ∀ integers n.\n")
        self.assertEqual(len(by_rule(findings, "L4-LOGIC-01")), 1)

    def test_logic_symbol_inside_display_env_not_flagged(self) -> None:
        text = "\\begin{equation}\n\\forall x\\; \\exists y\\; x < y.\n\\end{equation}\n"
        self.assertEqual(by_rule(run_lint(text), "L4-LOGIC-01"), [])

    def test_line_numbers_survive_multiline_display(self) -> None:
        text = (
            "Intro sentence.\n"          # line 1
            "\\[\n"                       # line 2
            "x + y = z.\n"                # line 3
            "\\]\n"                       # line 4
            "This holds ∀ n.\n"           # line 5
        )
        logic = by_rule(run_lint(text), "L4-LOGIC-01")
        self.assertEqual(len(logic), 1)
        self.assertEqual(logic[0].line, 5)
        self.assertEqual(logic[0].excerpt, "This holds ∀ n.")


class ProseLintTest(unittest.TestCase):
    def test_shorthand_flagged(self) -> None:
        text = "This holds iff n is even.\nChoose x s.t. WLOG x > 0 w.r.t. the order.\n"
        short = by_rule(run_lint(text), "L4-SHORT-01")
        self.assertEqual({f.line for f in short}, {1, 2})
        self.assertEqual(len(short), 4)

    def test_shorthand_not_flagged_inside_words(self) -> None:
        # "iff" inside "Griffiths" must not match.
        self.assertEqual(by_rule(run_lint("By Griffiths and Harris.\n"), "L4-SHORT-01"), [])

    def test_sentence_starting_with_math_flagged(self) -> None:
        text = "It follows. $x$ is positive.\n"
        sym = by_rule(run_lint(text), "L4-SYM-02")
        self.assertEqual(len(sym), 1)
        self.assertEqual(sym[0].line, 1)

    def test_sentence_starting_with_word_not_flagged(self) -> None:
        self.assertEqual(by_rule(run_lint("The set $X$ is closed.\n"), "L4-SYM-02"), [])

    def test_paragraph_starting_with_math_flagged(self) -> None:
        text = "First paragraph ends here.\n\n$f$ is continuous on the interval.\n"
        sym = by_rule(run_lint(text), "L4-SYM-02")
        self.assertEqual(len(sym), 1)
        self.assertEqual(sym[0].line, 3)

    def test_single_letter_sentence_start_flagged_but_articles_spared(self) -> None:
        flagged = by_rule(run_lint("x is positive whenever y is.\n"), "L4-SYM-02")
        self.assertEqual(len(flagged), 1)
        spared = by_rule(run_lint("A set is open if its complement is closed. I omit the proof.\n"), "L4-SYM-02")
        self.assertEqual(spared, [])

    def test_usage_traps(self) -> None:
        text = "The principle bundle has a non-negative and non-zero occurence count.\n"
        usage = by_rule(run_lint(text), "L4-USAGE-03")
        self.assertEqual(len(usage), 4)
        messages = " | ".join(f.message for f in usage)
        self.assertIn("principal bundle", messages)
        self.assertIn("nonnegative", messages)
        self.assertIn("nonzero", messages)
        self.assertIn("occurrence", messages)

    def test_usage_traps_negative(self) -> None:
        text = "The principal bundle has a nonnegative occurrence count.\n"
        self.assertEqual(by_rule(run_lint(text), "L4-USAGE-03"), [])

    def test_contractions_flagged(self) -> None:
        text = "We don't assume completeness, and it's clear we can't drop it.\n"
        contractions = by_rule(run_lint(text), "L4-USAGE-09")
        self.assertEqual(len(contractions), 3)
        # "it's" is double-listed in the rubric: also an L4-USAGE-03 review flag.
        self.assertEqual(len(by_rule(run_lint(text), "L4-USAGE-03")), 1)

    def test_contractions_negative(self) -> None:
        self.assertEqual(by_rule(run_lint("We do not assume completeness.\n"), "L4-USAGE-09"), [])

    def test_colon_before_display_flagged(self) -> None:
        text = "We obtain:\n\\[ x = y. \\]\n"
        gram = by_rule(run_lint(text), "L4-GRAM-04")
        self.assertEqual(len(gram), 1)
        self.assertEqual(gram[0].severity, "nit")
        self.assertEqual(gram[0].line, 1)

    def test_colon_before_display_allowed_after_as_follows(self) -> None:
        for lead in ("We proceed as follows:", "We obtain the following:"):
            text = f"{lead}\n\\[ x = y. \\]\n"
            self.assertEqual(by_rule(run_lint(text), "L4-GRAM-04"), [], lead)

    def test_exclamation_in_prose_flagged(self) -> None:
        gram = by_rule(run_lint("This bound is sharp!\n"), "L4-GRAM-07")
        self.assertEqual(len(gram), 1)

    def test_exclamation_in_math_or_parenthetical_not_flagged(self) -> None:
        # Factorial lives inside math; Halmos's "(!)" aside is permitted.
        text = "There are $n!$ orderings, all of them distinct (!) in this case.\n"
        self.assertEqual(by_rule(run_lint(text), "L4-GRAM-07"), [])

    def test_literal_dots_flagged_in_math_and_prose(self) -> None:
        # One line with math dots, one with prose dots: both must flag
        # (findings collapse to one per line per rule).
        text = "Take $x_1, ..., x_n$ in order.\nAnd so on...\n"
        dots = by_rule(run_lint(text), "L5-DISP-04")
        self.assertEqual([f.line for f in dots], [1, 2])
        self.assertIn("\\ldots", dots[0].message)

    def test_ldots_not_flagged(self) -> None:
        self.assertEqual(by_rule(run_lint("Take $x_1, \\ldots, x_n$.\n"), "L5-DISP-04"), [])

    def test_any_inside_theorem_env_flagged(self) -> None:
        text = (
            "Preamble prose.\n"
            "\\begin{theorem}\n"
            "For any $\\varepsilon > 0$ there is a bound.\n"
            "\\end{theorem}\n"
        )
        quant = by_rule(run_lint(text), "L2-QUANT-02")
        self.assertEqual(len(quant), 1)
        self.assertEqual(quant[0].severity, "minor")
        self.assertEqual(quant[0].line, 3)

    def test_any_outside_theorem_env_not_flagged(self) -> None:
        self.assertEqual(by_rule(run_lint("This works for any reasonable norm.\n"), "L2-QUANT-02"), [])

    def test_display_missing_punctuation_heuristic(self) -> None:
        text = "We compute\n\\[\nx = y\n\\]\nTherefore the claim holds.\n"
        sent = by_rule(run_lint(text), "L4-SENT-01")
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].severity, "nit")
        self.assertEqual(sent[0].line, 4)

    def test_display_with_punctuation_not_flagged(self) -> None:
        text = "We compute\n\\[\nx = y.\n\\]\nTherefore the claim holds.\n"
        self.assertEqual(by_rule(run_lint(text), "L4-SENT-01"), [])

    def test_display_followed_by_lowercase_not_flagged(self) -> None:
        text = "We compute\n\\[\nx = y\n\\]\nand the claim follows.\n"
        self.assertEqual(by_rule(run_lint(text), "L4-SENT-01"), [])


class CiteBibitemTest(unittest.TestCase):
    def test_cross_check_reports_undefined_and_uncited(self) -> None:
        text = (
            "We use \\cite{alpha} and \\cite[Thm. 2]{beta}.\n"   # line 1
            "\\begin{thebibliography}{9}\n"                      # line 2
            "\\bibitem{alpha} A. Author, Paper.\n"               # line 3
            "\\bibitem{gamma} C. Author, Unused.\n"              # line 4
            "\\end{thebibliography}\n"                           # line 5
        )
        refs = by_rule(run_lint(text), "L5-REF-03")
        self.assertEqual(len(refs), 2)
        undefined = [f for f in refs if "'beta'" in f.message]
        uncited = [f for f in refs if "'gamma'" in f.message]
        self.assertEqual(len(undefined), 1)
        self.assertEqual(undefined[0].line, 1)
        self.assertIn("no \\bibitem", undefined[0].message)
        self.assertEqual(len(uncited), 1)
        self.assertEqual(uncited[0].line, 4)
        self.assertIn("never cited", uncited[0].message)

    def test_multi_key_cite_resolves_each_key(self) -> None:
        text = (
            "See \\cite{a,b}.\n"
            "\\bibitem{a} X.\n"
            "\\bibitem{b} Y.\n"
        )
        self.assertEqual(by_rule(run_lint(text), "L5-REF-03"), [])

    def test_no_bibliography_block_skips_check(self) -> None:
        # External .bib file: nothing checkable, so nothing reported.
        text = "See \\cite{mystery}.\n\\bibliography{refs}\n"
        self.assertEqual(by_rule(run_lint(text), "L5-REF-03"), [])


class RunAllTest(unittest.TestCase):
    def test_sorted_by_severity_then_line(self) -> None:
        text = (
            "This holds iff n is even.\n"     # minor, line 1
            "We obtain:\n"                     # nit, line 2
            "\\[ x = y. \\]\n"
            "TODO tighten the constant.\n"     # blocker, line 4
        )
        findings = run_all(text)
        self.assertEqual(findings[0].rule_id, "L1-CITE-03")
        self.assertEqual(findings[0].severity, "blocker")
        severities = [f.severity for f in findings]
        rank = {"blocker": 0, "major": 1, "minor": 2, "nit": 3}
        self.assertEqual(severities, sorted(severities, key=rank.__getitem__))

    def test_residue_findings_not_duplicated(self) -> None:
        text = "TODO finish this section.\n"
        findings = run_all(text)
        residue = by_rule(findings, "L1-CITE-03")
        self.assertEqual(len(residue), 1)

    def test_lint_includes_residue_alias(self) -> None:
        # L5-AI-03 aliases the residue scan: run_lint alone must surface it.
        findings = run_lint("As an AI, I cannot continue.\n")
        self.assertIn("L1-CITE-03", rule_ids(findings))

    def test_excerpts_bounded(self) -> None:
        long_line = "This holds iff " + "n is even and " * 40 + "we stop.\n"
        for finding in run_all(long_line):
            self.assertLessEqual(len(finding.excerpt), EXCERPT_MAX_CHARS)

    def test_clean_text_yields_no_findings(self) -> None:
        text = (
            "We show that the polynomial $x^n - a$ has a root in every splitting field.\n"
            "The proof proceeds as follows:\n"
            "\\[ x^n - a = \\prod_{k=1}^{n} (x - \\zeta^k \\alpha). \\]\n"
            "The factors are pairwise distinct because the roots of unity are distinct.\n"
        )
        self.assertEqual(run_all(text), [])


if __name__ == "__main__":
    unittest.main()

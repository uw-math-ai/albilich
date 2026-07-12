from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.writing.linter import Finding, run_paper_lint

# Minimal document satisfying every L5-PAPER-03 structural element; the body
# hook lets each test inject the text under scrutiny into the main text.
GOOD_PAPER = r"""\documentclass[11pt]{amsart}
\usepackage{amsmath,amssymb,amsthm}
\newtheorem{theorem}{Theorem}[section]
\begin{document}
\begin{abstract}
We prove a small result.
\end{abstract}
\maketitle
\section{Introduction}
%BODY%
\begin{theorem}
The result holds.
\end{theorem}
\begin{proof}
Immediate from the definition.
\end{proof}
\appendix
\section{Certification}
Run archive: recorded in internal artifact records under art_final_paper_1.
\begin{thebibliography}{9}
\bibitem{a} A. Author, A title, J. Math. 1 (2000), 1--2.
\end{thebibliography}
\end{document}
"""


def paper_with_body(body: str) -> str:
    return GOOD_PAPER.replace("%BODY%", body)


def rule_ids(findings: list[Finding]) -> set[str]:
    return {finding.rule_id for finding in findings}


class PaperMarkdownResidueTest(unittest.TestCase):
    """L5-PAPER-01: markdown residue in LaTeX source, outside verbatim."""

    def test_clean_paper_has_no_findings(self) -> None:
        self.assertEqual([], run_paper_lint(paper_with_body("We recall the definition.")))

    def test_markdown_heading_lines_are_blockers(self) -> None:
        for heading in ("# Introduction", "## Setup", "##Setup"):
            findings = run_paper_lint(paper_with_body(heading))
            self.assertIn("L5-PAPER-01", rule_ids(findings), heading)
            self.assertTrue(all(f.severity == "blocker" for f in findings if f.rule_id == "L5-PAPER-01"))

    def test_bare_hash_without_space_is_not_flagged(self) -> None:
        # A leading "#" with no following space is LaTeX macro-parameter
        # territory, not a markdown heading.
        self.assertEqual([], run_paper_lint(paper_with_body("#1 denotes the first macro argument.")))

    def test_code_fence_is_a_blocker(self) -> None:
        findings = run_paper_lint(paper_with_body("```\ncode\n```"))
        self.assertIn("L5-PAPER-01", rule_ids(findings))

    def test_star_bullet_at_line_start_is_a_blocker(self) -> None:
        findings = run_paper_lint(paper_with_body("* first item"))
        self.assertIn("L5-PAPER-01", rule_ids(findings))

    def test_markdown_link_is_a_blocker_but_math_juxtaposition_is_not(self) -> None:
        flagged = run_paper_lint(paper_with_body("See [the source](https://example.org/paper)."))
        self.assertIn("L5-PAPER-01", rule_ids(flagged))
        # Interval-then-argument juxtaposition must not read as a link.
        spared = run_paper_lint(paper_with_body("The restriction [0,1](x) is not a link."))
        self.assertNotIn("L5-PAPER-01", rule_ids(spared))

    def test_bold_span_is_a_blocker(self) -> None:
        findings = run_paper_lint(paper_with_body("This is **important** text."))
        self.assertIn("L5-PAPER-01", rule_ids(findings))

    def test_verbatim_environment_is_exempt(self) -> None:
        body = "\\begin{verbatim}\n# heading\n* bullet\n**bold**\n\\end{verbatim}"
        self.assertEqual([], run_paper_lint(paper_with_body(body)))

    def test_findings_carry_line_and_excerpt(self) -> None:
        findings = run_paper_lint(paper_with_body("## Setup"))
        finding = next(f for f in findings if f.rule_id == "L5-PAPER-01")
        self.assertEqual(10, finding.line)
        self.assertIn("## Setup", finding.excerpt)


class PaperInternalRegisterTest(unittest.TestCase):
    """L5-PAPER-02: internal system vocabulary before the first \\appendix."""

    def test_art_identifier_in_main_text_is_a_blocker(self) -> None:
        findings = run_paper_lint(paper_with_body("As recorded in art_proof_7, the claim holds."))
        self.assertIn("L5-PAPER-02", rule_ids(findings))

    def test_art_identifier_in_appendix_is_allowed(self) -> None:
        # GOOD_PAPER's Run archive paragraph already carries art_final_paper_1
        # after \appendix; the clean body must not trip the register rule.
        self.assertEqual([], run_paper_lint(paper_with_body("The claim holds.")))

    def test_internal_vocabulary_words_are_blockers(self) -> None:
        for word in (
            "the manifest",
            "a ledger",
            "the artifact",
            "two artifacts",
            "the proof-state",
            "a verifier report",
            "one writing debt",
            "a state revision",
        ):
            findings = run_paper_lint(paper_with_body(f"We consult {word} for details."))
            self.assertIn("L5-PAPER-02", rule_ids(findings), word)

    def test_register_scan_is_case_insensitive(self) -> None:
        findings = run_paper_lint(paper_with_body("The Ledger records everything."))
        self.assertIn("L5-PAPER-02", rule_ids(findings))

    def test_manifestly_is_not_flagged(self) -> None:
        self.assertEqual([], run_paper_lint(paper_with_body("The bound is manifestly positive.")))

    def test_ordinary_mathematical_words_are_not_flagged(self) -> None:
        self.assertEqual(
            [],
            run_paper_lint(paper_with_body("The revision of the argument uses a debt-free verifier of parity.")),
        )


class PaperStructureTest(unittest.TestCase):
    """L5-PAPER-03: standalone-article skeleton."""

    def test_each_missing_element_is_reported(self) -> None:
        removals = {
            r"\documentclass": r"\documentclass[11pt]{amsart}",
            r"\begin{abstract}": "\\begin{abstract}\nWe prove a small result.\n\\end{abstract}",
            "a theorem environment": "\\begin{theorem}\nThe result holds.\n\\end{theorem}",
            r"\begin{proof}": "\\begin{proof}\nImmediate from the definition.\n\\end{proof}",
            "a bibliography": "\\begin{thebibliography}{9}\n\\bibitem{a} A. Author, A title, J. Math. 1 (2000), 1--2.\n\\end{thebibliography}",
            r"\end{document}": r"\end{document}",
        }
        for label, snippet in removals.items():
            broken = paper_with_body("Body text.").replace(snippet, "")
            findings = run_paper_lint(broken)
            structural = [f for f in findings if f.rule_id == "L5-PAPER-03"]
            self.assertTrue(any(label in f.message for f in structural), (label, findings))
            self.assertTrue(all(f.severity == "blocker" for f in structural))

    def test_missing_appendix_is_reported(self) -> None:
        # Removing \appendix also promotes the Run archive paragraph into the
        # main text, so the art_* identifier now trips the register rule too.
        broken = paper_with_body("Body text.").replace("\\appendix\n", "")
        findings = run_paper_lint(broken)
        self.assertTrue(any(f.rule_id == "L5-PAPER-03" and "appendix" in f.message for f in findings), findings)
        self.assertIn("L5-PAPER-02", rule_ids(findings))

    def test_starred_theorem_and_bibliography_command_also_satisfy_structure(self) -> None:
        alternative = (
            paper_with_body("Body text.")
            .replace("\\begin{theorem}\nThe result holds.\n\\end{theorem}", "\\begin{theorem*}\nThe result holds.\n\\end{theorem*}")
            .replace(
                "\\begin{thebibliography}{9}\n\\bibitem{a} A. Author, A title, J. Math. 1 (2000), 1--2.\n\\end{thebibliography}",
                "\\bibliography{refs}",
            )
        )
        self.assertNotIn("L5-PAPER-03", rule_ids(run_paper_lint(alternative)))


if __name__ == "__main__":
    unittest.main()

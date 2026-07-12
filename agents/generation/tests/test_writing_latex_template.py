"""Tests for the deterministic LaTeX template normalizer (writing/latex_template.py).

Covers the preamble rewrite (bad preamble -> house preamble, author packages
kept, hyperref last, \\numberwithin after theorem declarations), idempotence
(including the hand-typeset PSL(2,11) reference paper as a fixed point),
piped-table -> booktabs conversion, the three collapse artifacts, and a real
pdflatex compile of the normalized output.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.receipt import compile_latex_artifact
from agents.generation.phase2.writing.latex_template import normalize_paper_template

REFERENCE_TYPESET_PAPER = (
    REPO_ROOT
    / "experiments"
    / "kourovka_20_2_paper_v2_20260709"
    / "PSL211_paper_final_typeset.tex"
)

# A compilable article with a non-house preamble (author kept graphicx and a
# macro) and a fully piped table — what a non-compliant writer ships.
BAD_PREAMBLE_PAPER = r"""\documentclass[11pt]{amsart}
\usepackage{amsmath}
\usepackage{graphicx}
\usepackage{hyperref}
\newcommand{\myop}{\operatorname{op}}
\newtheorem{theorem}{Theorem}[section]
\title{A small theorem}
\author{The Albilich Project}
\begin{document}
\maketitle
\section{Introduction}
In this section, we state the theorem.
\begin{theorem}
Every group with one element is trivial.
\end{theorem}
\begin{table}[t]
\centering
\caption{A structural table.}
\begin{tabular}{|c|c|}
\hline
Object & Count \\
\hline
Groups & 1 \\
Elements & 1 \\
\hline
\end{tabular}
\end{table}
\end{document}
"""

HOUSE_PREAMBLE_LINES = [
    r"\usepackage[margin=1.25in]{geometry}",
    r"\usepackage{amsmath,amssymb,amsthm}",
    r"\usepackage{newpxtext,newpxmath}",
    r"\usepackage{microtype}",
    r"\usepackage{booktabs}",
    r"\usepackage{xcolor}",
    r"\definecolor{linkblue}{RGB}{0,0,128}",
    r"\usepackage[colorlinks=true,linkcolor=linkblue,citecolor=linkblue,urlcolor=linkblue]{hyperref}",
    r"\emergencystretch=1.5em",
]


def tabular_body(tex: str) -> str:
    match = re.search(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}", tex, re.DOTALL)
    assert match is not None, tex
    return match.group(1)


class PreambleNormalizationTest(unittest.TestCase):
    def test_bad_preamble_is_rewritten_to_the_house_template(self) -> None:
        out = normalize_paper_template(BAD_PREAMBLE_PAPER)
        preamble = out[: out.index(r"\begin{document}")]
        for line in HOUSE_PREAMBLE_LINES:
            self.assertIn(line, preamble, line)
        # House order: geometry first among packages, hyperref last.
        package_lines = [ln for ln in preamble.splitlines() if ln.startswith(r"\usepackage")]
        self.assertIn("geometry", package_lines[0])
        self.assertIn("hyperref", package_lines[-1])

    def test_author_additions_survive_the_rewrite(self) -> None:
        out = normalize_paper_template(BAD_PREAMBLE_PAPER)
        preamble = out[: out.index(r"\begin{document}")]
        self.assertIn(r"\usepackage{graphicx}", preamble)
        self.assertIn(r"\newcommand{\myop}{\operatorname{op}}", preamble)
        # The kept author package loads before hyperref (hyperref stays last).
        self.assertLess(preamble.index(r"\usepackage{graphicx}"), preamble.index("hyperref"))
        # The house-supplied amsmath is not loaded twice.
        self.assertEqual(1, preamble.count("amsmath"))

    def test_numberwithin_is_ensured_after_theorem_declarations(self) -> None:
        out = normalize_paper_template(BAD_PREAMBLE_PAPER)
        preamble = out[: out.index(r"\begin{document}")]
        self.assertIn(r"\numberwithin{equation}{section}", preamble)
        self.assertLess(
            preamble.index(r"\newtheorem{theorem}"),
            preamble.index(r"\numberwithin{equation}{section}"),
        )

    def test_numberwithin_before_theorems_is_moved_after_them(self) -> None:
        doc = (
            "\\documentclass{amsart}\n"
            "\\numberwithin{equation}{section}\n"
            "\\newtheorem{theorem}{Theorem}[section]\n"
            "\\begin{document}\nBody.\n\\end{document}\n"
        )
        out = normalize_paper_template(doc)
        self.assertEqual(1, out.count(r"\numberwithin{equation}{section}"))
        self.assertLess(
            out.index(r"\newtheorem{theorem}"), out.index(r"\numberwithin{equation}{section}")
        )

    def test_normalization_is_idempotent(self) -> None:
        once = normalize_paper_template(BAD_PREAMBLE_PAPER)
        self.assertEqual(once, normalize_paper_template(once))

    def test_reference_typeset_paper_is_a_fixed_point(self) -> None:
        # The hand-typeset PSL(2,11) paper IS the reference output: the
        # normalizer must leave it byte-identical.
        if not REFERENCE_TYPESET_PAPER.is_file():
            self.skipTest("reference typeset paper not present in this checkout")
        reference = REFERENCE_TYPESET_PAPER.read_text(encoding="utf-8")
        self.assertEqual(reference, normalize_paper_template(reference))

    def test_document_without_documentclass_is_untouched(self) -> None:
        fragment = "Just prose with a \\usepackage{tikz} mention.\n"
        self.assertEqual(fragment, normalize_paper_template(fragment))


class TableNormalizationTest(unittest.TestCase):
    def test_piped_table_becomes_clean_booktabs(self) -> None:
        out = normalize_paper_template(BAD_PREAMBLE_PAPER)
        spec = re.search(r"\\begin\{tabular\}\{([^}]*)\}", out)
        self.assertIsNotNone(spec)
        self.assertNotIn("|", spec.group(1))
        body = tabular_body(out)
        self.assertNotIn(r"\hline", body)
        # Canonical skeleton: \toprule, header, \midrule, body rows, \bottomrule.
        self.assertLess(body.index(r"\toprule"), body.index("Object & Count"))
        self.assertLess(body.index("Object & Count"), body.index(r"\midrule"))
        self.assertLess(body.index(r"\midrule"), body.index("Groups & 1"))
        self.assertLess(body.index("Elements & 1"), body.index(r"\bottomrule"))

    def test_single_row_table_gets_no_midrule(self) -> None:
        doc = "\\begin{tabular}{|c|}\n\\hline\nOnly \\\\\n\\hline\n\\end{tabular}\n"
        out = normalize_paper_template(doc)
        body = tabular_body(out)
        self.assertIn(r"\toprule", body)
        self.assertIn(r"\bottomrule", body)
        self.assertNotIn(r"\midrule", body)

    def test_toprule_immediately_followed_by_midrule_collapses(self) -> None:
        doc = (
            "\\begin{tabular}{c c}\n\\toprule\n\\midrule\nA & B \\\\\n\\midrule\n"
            "1 & 2 \\\\\n\\bottomrule\n\\end{tabular}\n"
        )
        body = tabular_body(normalize_paper_template(doc))
        self.assertNotRegex(body, r"\\toprule\s*\\midrule")
        self.assertEqual(1, body.count(r"\toprule"))

    def test_midrule_immediately_before_bottomrule_collapses(self) -> None:
        doc = (
            "\\begin{tabular}{c c}\n\\toprule\nA & B \\\\\n\\midrule\n"
            "1 & 2 \\\\\n\\midrule\n\\bottomrule\n\\end{tabular}\n"
        )
        body = tabular_body(normalize_paper_template(doc))
        self.assertNotRegex(body, r"\\midrule\s*\\bottomrule")
        self.assertEqual(1, body.count(r"\midrule"))

    def test_trailing_bare_row_break_before_bottomrule_is_removed(self) -> None:
        doc = (
            "\\begin{tabular}{c c}\n\\toprule\nA & B \\\\\n\\midrule\n"
            "1 & 2 \\\\\n\\\\\n\\bottomrule\n\\end{tabular}\n"
        )
        body = tabular_body(normalize_paper_template(doc))
        self.assertNotRegex(body, r"\\\\\s*\\\\\s*\\bottomrule")
        self.assertRegex(body, r"1 & 2 \\\\\s*\\bottomrule")

    def test_clean_booktabs_table_is_unchanged(self) -> None:
        doc = (
            "\\begin{tabular}{c c}\n\\toprule\nA & B \\\\\n\\midrule\n"
            "1 & 2 \\\\\n3 & 4 \\\\\n\\bottomrule\n\\end{tabular}\n"
        )
        self.assertEqual(doc, normalize_paper_template(doc))

    def test_grouped_booktabs_midrules_survive(self) -> None:
        # An already-booktabs table with an internal group \midrule keeps its
        # author-chosen row grouping (only artifacts are collapsed).
        doc = (
            "\\begin{tabular}{c c}\n\\toprule\nA & B \\\\\n\\midrule\n"
            "1 & 2 \\\\\n\\midrule\n3 & 4 \\\\\n\\bottomrule\n\\end{tabular}\n"
        )
        self.assertEqual(doc, normalize_paper_template(doc))


class NormalizedOutputCompilesTest(unittest.TestCase):
    def test_normalized_paper_compiles_with_real_pdflatex(self) -> None:
        if shutil.which("pdflatex") is None:
            self.skipTest("pdflatex is not installed")
        normalized = normalize_paper_template(BAD_PREAMBLE_PAPER)
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = Path(tmpdir) / "normalized.tex"
            tex_path.write_text(normalized, encoding="utf-8")
            sidecars = compile_latex_artifact(tex_path, tex_path.with_suffix(".pdf"))
            self.assertEqual("compiled", sidecars.get("pdf_status"), sidecars)
            self.assertTrue(tex_path.with_suffix(".pdf").is_file())


if __name__ == "__main__":
    unittest.main()

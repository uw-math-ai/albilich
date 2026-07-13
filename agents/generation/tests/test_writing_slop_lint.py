"""Tests for the deterministic anti-slop layer (rubric L4-SLOP-* + L4-HOUSE-03).

Covers, per rule, a positive and a negative case; math-mode immunity; the
density rules (L4-SLOP-01 lexicon, L4-SLOP-11 one-sentence paragraphs); the
"it remains to" non-flag; the L4-HOUSE-03 exceptions; and the paper-contract
anti-slop text.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.writing.linter import (
    BULLET_NARRATION_MIN_ITEMS,
    BULLET_NARRATION_MIN_ITEM_WORDS,
    FRAGMENTATION_MAX_SECTIONS_PER_1000_WORDS,
    FRAGMENTATION_MIN_STUB_SECTIONS,
    STUB_SECTION_MIN_WORDS,
    Finding,
    run_slop_lint,
)
from agents.generation.phase2.writing.paper_contract import (
    EDITOR_DIRECTIVE,
    PAPER_CONTRACT,
    WRITING_STYLE_CORE,
)


def by_rule(findings: list[Finding], rule_id: str) -> list[Finding]:
    return [finding for finding in findings if finding.rule_id == rule_id]


class SlopLexiconTest(unittest.TestCase):
    def test_two_lexicon_hits_emit_one_finding_per_hit_naming_the_word(self) -> None:
        text = "We delve into the theory. The interplay with duality is clear.\n"
        findings = by_rule(run_slop_lint(text), "L4-SLOP-01")
        self.assertEqual(2, len(findings), findings)
        messages = " ".join(finding.message for finding in findings)
        self.assertIn('"delve"', messages)
        self.assertIn('"interplay"', messages)
        for finding in findings:
            self.assertEqual("minor", finding.severity)

    def test_single_lexicon_hit_is_spared_by_the_density_rule(self) -> None:
        text = "The pivotal case is n equal to three.\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-SLOP-01"))

    def test_math_mode_lexicon_words_are_immune(self) -> None:
        # "pivotal" appears only inside math; the prose hit alone is below the
        # density threshold, so math immunity is what keeps this clean.
        text = "Let $x_{\\mathrm{pivotal}}$ and $y_{\\mathrm{pivotal}}$ be as in the tapestry lemma.\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-SLOP-01"))

    def test_underscore_word_matches_but_latex_underscore_does_not(self) -> None:
        text = "These bounds underscore the pattern. The realm of examples is wide.\n"
        findings = by_rule(run_slop_lint(text), "L4-SLOP-01")
        self.assertEqual(2, len(findings), findings)
        clean = "The file name\\_with\\_underscores stays. The index $a_i$ is fixed.\n"
        self.assertEqual([], by_rule(run_slop_lint(clean), "L4-SLOP-01"))


class SlopInflationTest(unittest.TestCase):
    def test_crucial_role_phrase_is_major(self) -> None:
        text = "This lemma plays a crucial role in the argument.\n"
        findings = by_rule(run_slop_lint(text), "L4-SLOP-02")
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("major", findings[0].severity)

    def test_all_inflation_phrase_families_match(self) -> None:
        text = (
            "It played a vital role here. It stands as a testament to the method. "
            "It serves as a reminder of duality. The result underscores the importance of it. "
            "It highlights its significance broadly. We are setting the stage for the sequel. "
            "This marks a key turning point in the field. This reflects broader currents.\n"
        )
        self.assertEqual(8, len(by_rule(run_slop_lint(text), "L4-SLOP-02")))

    def test_plain_role_sentence_is_not_flagged(self) -> None:
        text = "The subgroup plays a role in the factorization only through its order.\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-SLOP-02"))


class SlopCopulaTest(unittest.TestCase):
    def test_serves_as_and_boasts_are_minor(self) -> None:
        text = "The quotient serves as a classifying object. The group boasts three involutions.\n"
        findings = by_rule(run_slop_lint(text), "L4-SLOP-03")
        self.assertEqual(2, len(findings), findings)
        for finding in findings:
            self.assertEqual("minor", finding.severity)

    def test_copula_inside_an_inflation_phrase_dedupes_to_the_major(self) -> None:
        # "serves as a testament" is L4-SLOP-02's span; no L4-SLOP-03 double-report.
        text = "The identity serves as a testament to the symmetry.\n"
        findings = run_slop_lint(text)
        self.assertEqual(1, len(by_rule(findings, "L4-SLOP-02")))
        self.assertEqual([], by_rule(findings, "L4-SLOP-03"))

    def test_plain_is_prose_is_clean(self) -> None:
        text = "The quotient is a classifying object, and the group has three involutions.\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-SLOP-03"))


class SlopParallelismTest(unittest.TestCase):
    """L4-SLOP-04, the rhetorical-reversal family. The rule is MAJOR (it
    gates); coverage spans every punctuation costume of the single-sentence
    reversal, the low-false-positive cross-sentence arm, and negative
    listing — with the legitimate-mathematics boundary tested explicitly."""

    def flagged(self, text: str) -> list[Finding]:
        return by_rule(run_slop_lint(text), "L4-SLOP-04")

    def test_every_finding_is_major(self) -> None:
        text = (
            "The map is not only injective but also surjective. "
            "It is not a coincidence. It is a theorem.\n"
        )
        findings = self.flagged(text)
        self.assertEqual(2, len(findings), findings)
        for finding in findings:
            self.assertEqual("major", finding.severity)

    def test_not_only_but_also_flagged(self) -> None:
        text = "The map is not only injective but also surjective on each fiber.\n"
        self.assertEqual(1, len(self.flagged(text)))

    def test_but_rather_and_it_is_not_pair_flagged(self) -> None:
        text = (
            "The obstruction is not local, but rather global in nature. "
            "It is not a coincidence. It is a symmetry.\n"
        )
        self.assertEqual(2, len(self.flagged(text)))

    def test_em_dash_variant_flagged_in_both_dash_spellings(self) -> None:
        unicode_dash = "The obstruction is not local — but global in nature.\n"
        self.assertEqual(1, len(self.flagged(unicode_dash)))
        latex_dash = "The obstruction is not local---but global in nature.\n"
        self.assertEqual(1, len(self.flagged(latex_dash)))

    def test_en_dash_after_a_negation_is_spared(self) -> None:
        # "--" is an en dash, not an em dash: page ranges near a "not" survive.
        text = "The bound is not stated on pages 12--15, but on page 20 it is.\n"
        self.assertEqual([], self.flagged(text))

    def test_semicolon_variant_flagged(self) -> None:
        text = "The map is not injective; it is generically finite.\n"
        self.assertEqual(1, len(self.flagged(text)))

    def test_not_because_but_because_flagged_with_and_without_comma(self) -> None:
        with_comma = "The proof works not because the group is small, but because it is simple.\n"
        self.assertEqual(1, len(self.flagged(with_comma)))
        without_comma = "The proof works not because the group is small but because it is simple.\n"
        self.assertEqual(1, len(self.flagged(without_comma)))

    def test_not_only_across_a_sentence_boundary_is_spared(self) -> None:
        text = "The map is not only injective. Surjectivity holds but also requires care.\n"
        self.assertEqual([], self.flagged(text))

    def test_cross_sentence_reversal_with_framing_subjects_flagged(self) -> None:
        for text in (
            "It is not a coincidence. It is a theorem.\n",
            "This is not an accident. That is a symmetry of the construction.\n",
            "The point is not the constant. It is the exponent.\n",
            "The reason is not aesthetic. It's structural.\n",
            "It is not a coincidence. Rather, it is a theorem.\n",
            "It is not a coincidence. Instead, it is a theorem.\n",
        ):
            findings = self.flagged(text)
            self.assertEqual(1, len(findings), (text, findings))
            self.assertEqual("major", findings[0].severity)
            self.assertIn("cross-sentence", findings[0].message)

    def test_legitimate_math_with_different_predicate_structure_is_spared(self) -> None:
        # Sentence 2 opens with a possessive, not "It is": no reversal pair.
        text = "The group is not abelian. Its center is trivial.\n"
        self.assertEqual([], self.flagged(text))

    def test_legitimate_math_with_concrete_subject_is_spared(self) -> None:
        # Sentence 1 opens with a concrete mathematical subject, not a
        # rhetorical framing noun: the false-positive boundary holds.
        text = "G is not simple. It is solvable.\n"
        self.assertEqual([], self.flagged(text))

    def test_mid_sentence_negation_never_opens_a_reversal(self) -> None:
        # "it is not" occurs mid-sentence: sentence 1 is anchored at a
        # sentence start, so the pair is spared.
        text = "The computation shows that it is not zero. It is positive.\n"
        self.assertEqual([], self.flagged(text))

    def test_second_negation_is_not_a_reversal_pair(self) -> None:
        # Two negations without a positive closer: neither arm fires.
        text = "It is not local. It is not global either, and the case remains open.\n"
        self.assertEqual([], self.flagged(text))

    def test_negative_listing_flagged_once_at_its_first_sentence(self) -> None:
        text = "It was not luck. It was not brute force. It was a symmetry.\n"
        findings = self.flagged(text)
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("major", findings[0].severity)
        self.assertIn("negative listing", findings[0].message)

    def test_three_negations_before_the_positive_still_yield_one_finding(self) -> None:
        text = (
            "It was not luck. It was not brute force. It was not a computer search. "
            "It was a symmetry.\n"
        )
        findings = self.flagged(text)
        self.assertEqual(1, len(findings), findings)
        self.assertIn("3 copular negations", findings[0].message)

    def test_single_past_tense_negation_is_below_the_listing_floor(self) -> None:
        # One "was not" sentence then a positive "It was": not a listing (the
        # floor is two negations) and not a reversal pair ("It was" is not in
        # the reversal's second-sentence opener set).
        text = "It was not luck. It was a symmetry.\n"
        self.assertEqual([], self.flagged(text))

    def test_reversal_family_inside_math_mode_is_immune(self) -> None:
        text = (
            "The identity $\\text{not only } x \\text{ but also } y$ holds, and "
            "$\\text{It is not } A. \\text{ It is } B$ is a label.\n"
            "\\begin{align}\n\\text{It was not X. It was not Y. It was Z.}\n\\end{align}\n"
            "The claim follows by inspection of both displays at once.\n"
        )
        self.assertEqual([], self.flagged(text))


class SlopRecapTest(unittest.TestCase):
    def test_paragraph_initial_recap_is_major(self) -> None:
        text = "The proof is complete.\n\nIn summary, the bound holds for every prime power.\n"
        findings = by_rule(run_slop_lint(text), "L4-SLOP-05")
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("major", findings[0].severity)

    def test_par_command_also_opens_a_paragraph(self) -> None:
        text = "The proof is complete.\\par Overall, the estimates are uniform in the rank.\n"
        self.assertEqual(1, len(by_rule(run_slop_lint(text), "L4-SLOP-05")))

    def test_mid_sentence_in_summary_is_spared(self) -> None:
        text = "The argument given in summary form above extends verbatim to the twisted case.\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-SLOP-05"))


class SlopConnectorChainTest(unittest.TestCase):
    def test_second_consecutive_connector_sentence_is_flagged(self) -> None:
        text = "Moreover, the bound is sharp. Furthermore, the constant is explicit.\n"
        findings = by_rule(run_slop_lint(text), "L4-SLOP-06")
        self.assertEqual(1, len(findings), findings)

    def test_three_in_a_row_flag_the_second_and_third(self) -> None:
        text = (
            "Moreover, the bound is sharp. Furthermore, the constant is explicit. "
            "Additionally, the exponent is best possible.\n"
        )
        self.assertEqual(2, len(by_rule(run_slop_lint(text), "L4-SLOP-06")))

    def test_separated_connector_sentences_are_spared(self) -> None:
        text = (
            "Moreover, the bound is sharp. The constant depends on the rank. "
            "Furthermore, the exponent is best possible.\n"
        )
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-SLOP-06"))


class SlopEmDashTest(unittest.TestCase):
    def test_four_em_dashes_in_a_short_span_yield_one_cluster_finding(self) -> None:
        text = (
            "The proof — as noted — proceeds in stages — first local — then global analysis.\n"
        )
        findings = by_rule(run_slop_lint(text), "L4-SLOP-07")
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("nit", findings[0].severity)

    def test_latex_triple_hyphen_counts_but_en_dash_does_not(self) -> None:
        text = "One---two---three---four---dashes cluster here, unlike pages 12--15.\n"
        self.assertEqual(1, len(by_rule(run_slop_lint(text), "L4-SLOP-07")))

    def test_three_em_dashes_are_within_budget(self) -> None:
        text = "A sharp bound — a uniform constant — and an explicit exponent — all follow.\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-SLOP-07"))


class SlopChoreographyTest(unittest.TestCase):
    def test_choreography_phrases_are_major(self) -> None:
        text = (
            "We now proceed to the pair analysis. Having established the local bound, we turn to "
            "the global case. With these preparations in place, the necessary input is available, "
            "and we record the following estimate needed below. The mechanism is simple.\n"
        )
        findings = by_rule(run_slop_lint(text), "L4-SLOP-09")
        self.assertGreaterEqual(len(findings), 5, findings)
        for finding in findings:
            self.assertEqual("major", finding.severity)

    def test_proof_rests_on_n_points_flagged(self) -> None:
        text = "The proof rests on three points established in the previous section.\n"
        self.assertEqual(1, len(by_rule(run_slop_lint(text), "L4-SLOP-09")))

    def test_plain_it_remains_to_is_legitimate(self) -> None:
        # "it remains to" as filler is the editor's judgment call, not the linter's.
        text = "It remains to bound the error term, and it remains to check the base case.\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-SLOP-09"))


class SlopOneSentenceParagraphTest(unittest.TestCase):
    def test_two_one_sentence_paragraphs_are_both_flagged(self) -> None:
        text = (
            "The bound holds trivially.\n\n"
            "The constant is explicit.\n\n"
            "The general case now follows by induction on the rank, since every proper "
            "subgroup satisfies the hypothesis. The induction terminates at the trivial group.\n"
        )
        findings = by_rule(run_slop_lint(text), "L4-SLOP-11")
        self.assertEqual(2, len(findings), findings)

    def test_a_single_one_sentence_paragraph_is_spared_by_density(self) -> None:
        text = (
            "The bound holds trivially.\n\n"
            "The general case follows by induction on the rank. The induction terminates.\n"
        )
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-SLOP-11"))

    def test_headings_items_display_math_and_statements_are_exempt(self) -> None:
        text = (
            "\\section{Main results}\n\n"
            "\\begin{theorem}\nEvery finite group of prime order is cyclic.\n\\end{theorem}\n\n"
            "\\begin{abstract}\nWe prove a single clean statement.\n\\end{abstract}\n\n"
            "\\item The first case is immediate.\n\n"
            "$$x^2 + y^2 = z^2$$\n\n"
            "One lone prose sentence sits here.\n"
        )
        # Only ONE prose one-sentence paragraph exists, so nothing is flagged;
        # none of the exempt blocks may count toward the density threshold.
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-SLOP-11"))


class SlopVagueOpenerTest(unittest.TestCase):
    def test_paragraph_opening_this_shows_is_flagged(self) -> None:
        text = "The lemma is proved.\n\nThis shows that the kernel is trivial.\n"
        findings = by_rule(run_slop_lint(text), "L4-SLOP-12")
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("nit", findings[0].severity)

    def test_this_with_a_noun_is_spared(self) -> None:
        text = "The lemma is proved.\n\nThis identity shows that the kernel is trivial.\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-SLOP-12"))

    def test_mid_paragraph_this_is_is_spared(self) -> None:
        text = "The kernel is trivial, and this is the key point of the construction.\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-SLOP-12"))


class HouseColonSemicolonTest(unittest.TestCase):
    def test_prose_semicolon_and_colon_are_minor(self) -> None:
        text = "The kernel is trivial; the image is everything. There is one caveat: torsion.\n"
        findings = by_rule(run_slop_lint(text), "L4-HOUSE-03")
        self.assertEqual(2, len(findings), findings)
        for finding in findings:
            self.assertEqual("minor", finding.severity)

    def test_colon_introducing_display_math_is_spared(self) -> None:
        text = "The relation is the following:\n\\[ x^2 = y \\]\nand the claim follows.\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-03"))

    def test_colons_inside_ref_like_commands_are_spared(self) -> None:
        text = (
            "By Theorem~\\ref{thm:main} and \\cite[Lemma 2]{key:2020}, the bound of "
            "Section~\\label{sec:intro} holds.\n"
        )
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-03"))

    def test_case_labels_inside_proofs_are_spared(self) -> None:
        text = "\\begin{proof}\nCase 1: the rank is even, and the claim is immediate.\n\\end{proof}\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-03"))

    def test_bibliography_block_and_preamble_are_spared(self) -> None:
        text = (
            "\\documentclass{amsart}\n"
            "\\usepackage[colon:in;preamble]{options}\n"
            "\\begin{document}\n"
            "The bound holds.\n"
            "\\begin{thebibliography}{9}\n"
            "\\bibitem{a} A. Author, Title: subtitle; notes. J. Math. 1 (2000), 1--2.\n"
            "\\end{thebibliography}\n"
            "\\end{document}\n"
        )
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-03"))

    def test_math_mode_colons_and_semicolons_are_immune(self) -> None:
        text = "The set $\\{x : x > 0\\}$ and the pairing $f(x; y)$ appear in prose.\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-03"))


class HouseSectionOpenerTest(unittest.TestCase):
    def test_section_without_opener_is_major_and_names_the_title(self) -> None:
        text = (
            "\\section{Preliminaries}\n"
            "The group under study is finite, and its order is a prime power.\n"
        )
        findings = by_rule(run_slop_lint(text), "L4-HOUSE-07")
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("major", findings[0].severity)
        self.assertIn("'Preliminaries'", findings[0].message)
        self.assertIn("In this section, we", findings[0].message)

    def test_section_with_opener_in_first_paragraph_is_clean(self) -> None:
        text = (
            "\\section{Preliminaries}\n"
            "In this section, we fix notation for closures. Permutations act on the right.\n"
        )
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-07"))

    def test_opener_after_the_first_paragraph_still_flags(self) -> None:
        text = (
            "\\section{Preliminaries}\n"
            "The group under study is finite.\n"
            "\n"
            "In this section, we fix notation for closures.\n"
        )
        self.assertEqual(1, len(by_rule(run_slop_lint(text), "L4-HOUSE-07")))

    def test_references_acknowledgment_and_bibliography_sections_are_exempt(self) -> None:
        text = (
            "\\section{References}\nA list of works follows.\n"
            "\\section*{Acknowledgment}\nThe maintainers are gratefully acknowledged.\n"
            "\\section*{Acknowledgments}\nThe maintainers are gratefully acknowledged.\n"
            "\\section{Bibliography}\nA list of works follows.\n"
        )
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-07"))

    def test_appendix_sections_require_the_appendix_variant(self) -> None:
        flagged = (
            "\\section{Introduction}\nIn this section, we state the theorem.\n"
            "\\appendix\n"
            "\\section{Certification}\nIn this section, we record the data.\n"
        )
        findings = by_rule(run_slop_lint(flagged), "L4-HOUSE-07")
        self.assertEqual(1, len(findings), findings)
        self.assertIn("In this appendix, we", findings[0].message)
        clean = (
            "\\section{Introduction}\nIn this section, we state the theorem.\n"
            "\\appendix\n"
            "\\section{Certification}\nIn this appendix, we present the certificate data.\n"
        )
        self.assertEqual([], by_rule(run_slop_lint(clean), "L4-HOUSE-07"))

    def test_every_violating_section_is_flagged_separately(self) -> None:
        text = (
            "\\section{Setup}\nThe order of the group is finite.\n"
            "\\section{Main argument}\nThe bound follows by induction on the rank.\n"
        )
        findings = by_rule(run_slop_lint(text), "L4-HOUSE-07")
        self.assertEqual(2, len(findings), findings)
        messages = " ".join(finding.message for finding in findings)
        self.assertIn("'Setup'", messages)
        self.assertIn("'Main argument'", messages)


class HouseWeCollocationTest(unittest.TestCase):
    def test_banned_collocations_are_major_and_name_the_offender(self) -> None:
        text = (
            "We recall the definition of a closure. We note that the order is prime. "
            "We now show the converse, and we begin by fixing a generator.\n"
        )
        findings = by_rule(run_slop_lint(text), "L4-HOUSE-08")
        self.assertEqual(4, len(findings), findings)
        messages = " ".join(finding.message for finding in findings)
        for offender in ("We recall", "We note that", "We now show", "we begin by"):
            self.assertIn(repr(offender), messages)
        for finding in findings:
            self.assertEqual("major", finding.severity)

    def test_all_banned_collocations_match_case_insensitively(self) -> None:
        text = (
            "We record the value. we now prove the claim. We now turn to duality. "
            "We start by normalizing. We observe that the kernel is trivial.\n"
        )
        self.assertEqual(5, len(by_rule(run_slop_lint(text), "L4-HOUSE-08")))

    def test_legitimate_we_sentences_are_spared(self) -> None:
        text = (
            "We prove the theorem by a direct computation. We define the closure operator, "
            "and we construct an explicit coupling. We show that the survivor set is trivial.\n"
        )
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-08"))

    def test_collocations_inside_math_mode_are_immune(self) -> None:
        text = "The label $\\mathrm{we\\ recall}$ appears only in math, and the prose is plain.\n"
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-08"))


# A 40-word filler sentence, repeated to build section bodies of chosen size.
FILLER_SENTENCE = (
    "The argument proceeds carefully through the standard reduction, and the reader can "
    "verify each individual step of the reduction directly from the definitions without "
    "difficulty, because every object in sight is finite and every map in sight is a "
    "homomorphism of finite groups. "
)


def section(title: str, sentences: int) -> str:
    """A lint-quiet \\section with an opener plus ``sentences`` filler sentences."""
    return (
        f"\\section{{{title}}}\n"
        "In this section, we prove the bound. "
        + FILLER_SENTENCE * sentences
        + "\n"
    )


class HouseStubSectionTest(unittest.TestCase):
    def test_thin_section_is_major_and_names_title_and_word_count(self) -> None:
        text = section("Setup", 0)  # opener only: far below the word floor
        findings = by_rule(run_slop_lint(text), "L4-HOUSE-09")
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("major", findings[0].severity)
        self.assertIn("'Setup'", findings[0].message)
        self.assertIn("7 prose words", findings[0].message)
        self.assertIn(str(STUB_SECTION_MIN_WORDS), findings[0].message)

    def test_developed_section_is_clean(self) -> None:
        text = section("Setup", 4)  # 7 + 4*40 words, comfortably over the floor
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-09"))

    def test_references_and_acknowledgment_sections_are_exempt(self) -> None:
        text = (
            "\\section{References}\nA list of works follows.\n"
            "\\section*{Acknowledgments}\nThe maintainers are gratefully acknowledged.\n"
        )
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-09"))

    def test_appendix_sections_are_also_checked(self) -> None:
        text = (
            section("Introduction", 4)
            + "\\appendix\n"
            + "\\section{Certification}\nIn this appendix, we list the data.\n"
        )
        findings = by_rule(run_slop_lint(text), "L4-HOUSE-09")
        self.assertEqual(1, len(findings), findings)
        self.assertIn("'Certification'", findings[0].message)

    def test_math_displays_and_tables_do_not_count_as_prose(self) -> None:
        # The section is long on displays and tabular data but thin on prose:
        # still a stub. The identical prose alone under a developed section
        # heading stays a stub too, proving the exclusions did the work.
        display = "\\begin{equation}\n x^2 + y^2 = z^2 + w_{i,j,k} + a + b + c + d \\end{equation}\n" * 20
        table = (
            "\\begin{table}\\begin{tabular}{ll}\n"
            + "alpha beta gamma delta epsilon zeta eta theta iota kappa \\\\\n" * 20
            + "\\end{tabular}\\end{table}\n"
        )
        text = section("Computations", 0) + display + table
        findings = by_rule(run_slop_lint(text), "L4-HOUSE-09")
        self.assertEqual(1, len(findings), findings)
        self.assertIn("'Computations'", findings[0].message)


class HouseFragmentationTest(unittest.TestCase):
    def test_two_main_body_stub_sections_trigger_the_document_finding(self) -> None:
        text = section("Setup", 0) + section("Main bound", 0)
        findings = by_rule(run_slop_lint(text), "L4-HOUSE-10")
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("major", findings[0].severity)
        self.assertIn(f"{FRAGMENTATION_MIN_STUB_SECTIONS} stub sections", findings[0].message)
        self.assertIn("merge", findings[0].message)

    def test_section_density_ratio_triggers_without_any_stub(self) -> None:
        # Four sections of ~167 words each: every section clears the stub
        # floor, but 4 sections over ~0.67k words is a ratio above the cap.
        text = "".join(section(f"Part {name}", 4) for name in ("one", "two", "three", "four"))
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-09"))
        findings = by_rule(run_slop_lint(text), "L4-HOUSE-10")
        self.assertEqual(1, len(findings), findings)
        self.assertIn(f"max {FRAGMENTATION_MAX_SECTIONS_PER_1000_WORDS}", findings[0].message)

    def test_few_substantial_sections_are_clean(self) -> None:
        text = section("Setup", 12) + section("Main bound", 12)  # ~1000 words for 2 sections
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-10"))

    def test_one_stub_section_alone_is_not_fragmentation(self) -> None:
        # Two long sections keep the ratio under the cap; the lone stub stays
        # below the two-stub fragmentation floor.
        text = section("Setup", 16) + section("Main bound", 16) + section("Outlook", 0)
        self.assertEqual(1, len(by_rule(run_slop_lint(text), "L4-HOUSE-09")))
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-10"))

    def test_appendix_stubs_do_not_count_toward_main_body_fragmentation(self) -> None:
        text = (
            section("Setup", 12)
            + section("Main bound", 12)
            + "\\appendix\n"
            + "\\section{Tables}\nIn this appendix, we list the tables.\n"
            + "\\section{Code}\nIn this appendix, we list the code.\n"
        )
        self.assertEqual(2, len(by_rule(run_slop_lint(text), "L4-HOUSE-09")))
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-10"))

    def test_a_single_section_never_fragments(self) -> None:
        # Fragmentation is a plurality defect: one section, however short the
        # document, is flagged as a stub only.
        text = section("Setup", 0)
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-10"))


class HouseBulletNarrationTest(unittest.TestCase):
    LONG_ITEM = (
        "\\item This item narrates one full developed thought that clearly runs to more "
        "than fifteen words of continuous connected prose text.\n"
    )

    def test_four_prose_items_are_narrative_masquerading_as_bullets(self) -> None:
        text = (
            section("Setup", 4) + section("Main bound", 4)
            + "\\begin{itemize}\n" + self.LONG_ITEM * BULLET_NARRATION_MIN_ITEMS + "\\end{itemize}\n"
        )
        findings = by_rule(run_slop_lint(text), "L4-HOUSE-11")
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("minor", findings[0].severity)
        self.assertIn("bullet narration", findings[0].message)
        self.assertIn("cohesive prose", findings[0].message)

    def test_short_case_enumeration_passes(self) -> None:
        text = (
            section("Setup", 4) + section("Main bound", 4)
            + "\\begin{enumerate}\n"
            + "\\item The rank is even.\n\\item The rank is odd.\n"
            + "\\item The rank is zero.\n\\item The rank is infinite.\n"
            + "\\end{enumerate}\n"
        )
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-11"))

    def test_three_long_items_are_below_the_item_floor(self) -> None:
        text = (
            section("Setup", 4) + section("Main bound", 4)
            + "\\begin{itemize}\n" + self.LONG_ITEM * (BULLET_NARRATION_MIN_ITEMS - 1) + "\\end{itemize}\n"
        )
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-11"))

    def test_math_does_not_count_toward_item_word_counts(self) -> None:
        # Each item is one long formula plus a short label: under the word
        # floor once math is stripped, so the list is a genuine enumeration.
        item = "\\item The case $a_1 + a_2 + a_3 + a_4 + a_5 + a_6 + a_7 + a_8 + a_9 + a_{10} + a_{11} + a_{12} = 0$ is immediate.\n"
        text = (
            section("Setup", 4) + section("Main bound", 4)
            + "\\begin{itemize}\n" + item * BULLET_NARRATION_MIN_ITEMS + "\\end{itemize}\n"
        )
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-11"))

    def test_more_than_one_list_per_two_sections_is_density_flagged(self) -> None:
        enumeration = (
            "\\begin{enumerate}\n\\item The rank is even.\n\\item The rank is odd.\n\\end{enumerate}\n"
        )
        text = section("Setup", 4) + enumeration + section("Main bound", 4) + enumeration
        findings = by_rule(run_slop_lint(text), "L4-HOUSE-11")
        self.assertEqual(1, len(findings), findings)
        self.assertIn("list density", findings[0].message)
        self.assertIn("2 itemize/enumerate lists across 2 sections", findings[0].message)

    def test_one_short_list_across_two_sections_is_clean(self) -> None:
        enumeration = (
            "\\begin{enumerate}\n\\item The rank is even.\n\\item The rank is odd.\n\\end{enumerate}\n"
        )
        text = section("Setup", 4) + enumeration + section("Main bound", 4)
        self.assertEqual([], by_rule(run_slop_lint(text), "L4-HOUSE-11"))

    def test_item_word_floor_matches_the_named_constant(self) -> None:
        self.assertEqual(15, BULLET_NARRATION_MIN_ITEM_WORDS)
        self.assertEqual(4, BULLET_NARRATION_MIN_ITEMS)


class SlopMathImmunityTest(unittest.TestCase):
    def test_display_environments_are_never_scanned(self) -> None:
        text = (
            "\\begin{align}\n"
            "  \\mathrm{pivotal} &= \\mathrm{delve}; \\\\\n"
            "  \\mathrm{journey} &: \\mathrm{realm}\n"
            "\\end{align}\n"
            "The identity holds by inspection, and equality follows at once.\n"
        )
        self.assertEqual([], run_slop_lint(text))


class PaperContractSlopTest(unittest.TestCase):
    def test_paper_contract_carries_the_anti_slop_block(self) -> None:
        self.assertIn("Anti-slop", PAPER_CONTRACT)
        self.assertIn("Anti-slop", WRITING_STYLE_CORE)
        self.assertIn("Never inflate significance", WRITING_STYLE_CORE)
        # The block sits before the genre paragraph, inside the style core.
        self.assertLess(
            WRITING_STYLE_CORE.index("Anti-slop"),
            WRITING_STYLE_CORE.index("The genre of this paper"),
        )

    def test_editor_directive_carries_the_slop_hunt(self) -> None:
        self.assertIn("SLOP HUNT", EDITOR_DIRECTIVE)
        self.assertIn("significance inflation", EDITOR_DIRECTIVE)

    def test_style_core_marks_the_two_house_hard_rules(self) -> None:
        # Section openers and "we" discipline are HARD RULES: deterministically
        # enforced (L4-HOUSE-07/08), violations block the paper.
        self.assertEqual(2, WRITING_STYLE_CORE.count("HARD RULE (deterministically enforced; violations block the paper)"))
        self.assertIn('sentence beginning "In this section, we ..."', WRITING_STYLE_CORE)
        self.assertIn('"we note that"', WRITING_STYLE_CORE)

    def test_editor_directive_names_the_hard_rules_to_verify(self) -> None:
        self.assertIn("HARD house rules enforced deterministically", EDITOR_DIRECTIVE)
        self.assertIn('"In this section, we ..."', EDITOR_DIRECTIVE)
        self.assertIn('"we"-collocation discipline', EDITOR_DIRECTIVE)

    def test_style_core_carries_the_section_substantiality_hard_rule(self) -> None:
        # The L4-HOUSE-09/10/11 counterpart in the writer's style core, inside
        # the anti-slop block (before the genre paragraph) so the PAPER_CONTRACT
        # inherits it verbatim.
        self.assertIn(
            "Sections are substantial, cohesive units (HARD RULE, deterministically enforced)",
            WRITING_STYLE_CORE,
        )
        self.assertIn("never a ladder of stub sections", WRITING_STYLE_CORE)
        self.assertIn("itemized lists are reserved for genuine enumerations", WRITING_STYLE_CORE)
        self.assertIn("typically four to six for a short article", WRITING_STYLE_CORE)
        self.assertLess(
            WRITING_STYLE_CORE.index("Sections are substantial"),
            WRITING_STYLE_CORE.index("The genre of this paper"),
        )
        self.assertIn("Sections are substantial, cohesive units", PAPER_CONTRACT)

    def test_editor_directive_marks_fragmentation_as_blocking(self) -> None:
        self.assertIn("Fragmentation is blocking", EDITOR_DIRECTIVE)
        self.assertIn('direct specific merges ("fold Section 4 into Section 3")', EDITOR_DIRECTIVE)
        self.assertIn("a paper of many short sections is an internal report, not an article", EDITOR_DIRECTIVE)


if __name__ == "__main__":
    unittest.main()

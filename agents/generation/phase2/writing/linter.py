"""Deterministic, LaTeX-aware writing linter for the math-writing harness.

Implements the rubric's ``lint``-checkable rules that a regex can decide.
Prose checks run on a math-stripped copy of the text: inline and display math
are replaced by placeholder tokens while preserving newline counts, so line
numbers reported against the stripped text are valid for the original.

Two entry points mirror the rubric's cost-ordering contract:

- :func:`run_residue_scan` — the always-blocker residue scanner (L1-CITE-03).
- :func:`run_lint` — every deterministic rubric rule (includes the residue
  scan, satisfying L5-AI-03 which is an alias of L1-CITE-03).
- :func:`run_all` — both, deduplicated and sorted by (severity, line).
- :func:`run_slop_lint` — the anti-slop/house-rules layer (L4-SLOP-01..12
  deterministic subset + L4-HOUSE-03 + the hard house rules L4-HOUSE-07
  section openers, L4-HOUSE-08 "we" collocations, L4-HOUSE-09 stub sections,
  and L4-HOUSE-10 fragmentation, all major, plus L4-HOUSE-11 bullet
  narration, minor); gate debts, never attach-rejections.
- :func:`run_paper_lint` — final_paper-only paper-register blockers.
"""

from __future__ import annotations

import re
from bisect import bisect_left
from dataclasses import dataclass
from typing import Iterable, List, Tuple

EXCERPT_MAX_CHARS = 160
INLINE_MATH_PLACEHOLDER = "<<MATH>>"
DISPLAY_MATH_PLACEHOLDER = "<<DISPLAY>>"

_SEVERITY_RANK = {"blocker": 0, "major": 1, "minor": 2, "nit": 3}


@dataclass
class Finding:
    rule_id: str
    severity: str
    line: int
    excerpt: str
    message: str


@dataclass(frozen=True)
class _MathRegion:
    kind: str  # "inline" | "display"
    inner: str
    start_line: int
    end_line: int
    placeholder_start: int  # offset of the placeholder in the stripped text


class _LineIndex:
    """Maps character offsets to 1-based line numbers."""

    def __init__(self, text: str):
        self._newlines = [i for i, ch in enumerate(text) if ch == "\n"]

    def line_of(self, offset: int) -> int:
        return bisect_left(self._newlines, offset) + 1


# --- math stripping ---------------------------------------------------------

# Math regions, longest/display forms first so "$$" wins over "$", envs
# swallow their inner "$"s. Inline "$...$" uses (?<!\\) so escaped dollar
# signs in prose ("costs \$5") do not open a math region.
_MATH_REGION_RE = re.compile(
    r"(?P<dollars>\$\$.*?\$\$)"
    r"|(?P<bracket>\\\[.*?\\\])"
    r"|(?P<paren>\\\(.*?\\\))"
    r"|(?P<env>\\begin\{(?P<envname>equation|align|gather|multline|eqnarray|alignat|displaymath)\*?\}"
    r".*?\\end\{(?P=envname)\*?\})"
    r"|(?P<inline>(?<!\\)\$[^$]+?(?<!\\)\$)",
    re.DOTALL,
)
# Peels "\begin{...}" / "\end{...}" off an environment region to get its body.
_ENV_INNER_RE = re.compile(r"^\\begin\{[a-z]+\*?\}(.*)\\end\{[a-z]+\*?\}$", re.DOTALL)


def _strip_math(text: str) -> Tuple[str, List[_MathRegion]]:
    """Replace math with placeholders; newline counts (hence line numbers)
    are preserved by re-emitting each region's newlines after its placeholder."""
    raw_index = _LineIndex(text)
    parts: List[str] = []
    regions: List[_MathRegion] = []
    out_len = 0
    pos = 0
    for match in _MATH_REGION_RE.finditer(text):
        prefix = text[pos : match.start()]
        parts.append(prefix)
        out_len += len(prefix)
        region_text = match.group(0)
        inline = match.group("inline") is not None or match.group("paren") is not None
        if match.group("env") is not None:
            env_inner = _ENV_INNER_RE.match(region_text)
            inner = env_inner.group(1) if env_inner is not None else region_text
        elif inline and match.group("inline") is not None:
            inner = region_text[1:-1]
        else:  # $$...$$, \[...\], \(...\)
            inner = region_text[2:-2]
        placeholder = INLINE_MATH_PLACEHOLDER if inline else DISPLAY_MATH_PLACEHOLDER
        regions.append(
            _MathRegion(
                kind="inline" if inline else "display",
                inner=inner,
                start_line=raw_index.line_of(match.start()),
                end_line=raw_index.line_of(max(match.end() - 1, match.start())),
                placeholder_start=out_len,
            )
        )
        replacement = placeholder + "\n" * region_text.count("\n")
        parts.append(replacement)
        out_len += len(replacement)
        pos = match.end()
    parts.append(text[pos:])
    return "".join(parts), regions


# --- residue scanner (L1-CITE-03, always blocker) ---------------------------

# Each pattern is deliberately conservative: prefer missing a borderline case
# to flagging legitimate mathematical prose.
_RESIDUE_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    # AI self-reference: "as an AI ..." chat-disclaimer opener.
    (re.compile(r"\bas an ai\b", re.IGNORECASE), '"as an AI"'),
    # Full LLM self-description phrase.
    (re.compile(r"\bas a large language model\b", re.IGNORECASE), '"as a large language model"'),
    # "language model" only with a leading article (a/the), so a genuine
    # citation of e.g. "language models of type X" in an ML-adjacent remark
    # must still self-describe to trigger.
    (re.compile(r"\b(?:a|the)\s+(?:large\s+)?language model\b", re.IGNORECASE), '"language model" self-reference'),
    # Training-data disclaimer phrase.
    (re.compile(r"\bknowledge cutoff\b", re.IGNORECASE), '"knowledge cutoff"'),
    # First-person chat refusal; papers speak as "we".
    (re.compile(r"\bi cannot\b", re.IGNORECASE), '"I cannot"'),
    # Chat apology (apostrophe optional to catch "Im sorry").
    (re.compile(r"\bi'?m sorry\b", re.IGNORECASE), '"I\'m sorry"'),
    # Assistant enthusiasm marker.
    (re.compile(r"certainly!", re.IGNORECASE), '"Certainly!"'),
    # Chat preamble, only at the start of a line to spare legitimate uses
    # such as "presented here is the main theorem".
    (re.compile(r"^\s*here(?: is|'s) the\b", re.IGNORECASE | re.MULTILINE), '"Here is the ..." preamble'),
    # Scaffolding markers, uppercase-only on purpose: lowercase "todo"/"xxx"
    # could be legitimate prose or notation.
    (re.compile(r"\bTODO\b"), '"TODO"'),
    (re.compile(r"\bFIXME\b"), '"FIXME"'),
    (re.compile(r"\bXXX\b"), '"XXX"'),
    # Placeholder question marks (also covers "\ldots???").
    (re.compile(r"\?\?\?"), '"???"'),
    # Bracketed citation placeholders: "[CITATION NEEDED]"; \b keeps bracketed
    # prose like "[Citations follow ...]" from needing an exact bracket form.
    (re.compile(r"\[citation\b", re.IGNORECASE), '"[CITATION" placeholder'),
    # Bracketed reference placeholder: "[REF]"; \b keeps bracketed prose like
    # "[Refined ...]" from matching.
    (re.compile(r"\[ref\b", re.IGNORECASE), '"[REF" placeholder'),
    # Boilerplate filler text.
    (re.compile(r"\blorem ipsum\b", re.IGNORECASE), '"lorem ipsum"'),
    (re.compile(r"\bplaceholder\b", re.IGNORECASE), '"placeholder"'),
    (re.compile(r"<insert\b", re.IGNORECASE), '"<insert ..."'),
    (re.compile(r"\byour text here\b", re.IGNORECASE), '"your text here"'),
    # Instruction echoes from the generating prompt.
    (re.compile(r"\bas instructed\b", re.IGNORECASE), '"as instructed"'),
    (re.compile(r"\bper the prompt\b", re.IGNORECASE), '"per the prompt"'),
    (re.compile(r"\bsystem prompt\b", re.IGNORECASE), '"system prompt"'),
    # Unresolved LaTeX cross-reference as rendered ("see Theorem ?? for"):
    # exactly two "?" flanked by start/whitespace and end/whitespace/punct.
    (re.compile(r"(?:^|(?<=\s))\?\?(?=$|[\s.,;:)\]}])", re.MULTILINE), 'unresolved reference "??"'),
]


def run_residue_scan(text: str) -> List[Finding]:
    """ALWAYS-blocker scan for generation residue (rule L1-CITE-03)."""
    lines = text.split("\n")
    index = _LineIndex(text)
    findings: List[Finding] = []
    for pattern, label in _RESIDUE_PATTERNS:
        for match in pattern.finditer(text):
            line = index.line_of(match.start())
            findings.append(
                Finding(
                    rule_id="L1-CITE-03",
                    severity="blocker",
                    line=line,
                    excerpt=_excerpt(lines, line),
                    message=f"generation residue: {label}",
                )
            )
    return _dedupe_sort(findings)


# --- prose lint patterns -----------------------------------------------------

# L4-LOGIC-01: logic symbols used as prose abbreviations (unicode forms).
_LOGIC_SYMBOL_RE = re.compile(r"[∀∃∧∨⇒∴∵∋]")
# L4-LOGIC-01: the LaTeX commands for the same symbols, outside math.
_LOGIC_COMMAND_RE = re.compile(
    r"\\(?:forall|exists|Rightarrow|Longrightarrow|implies|iff|wedge|vee|land|lor|therefore|because)\b"
)
# L4-SHORT-01: blackboard shorthand in prose; (?<!\\) keeps "\iff" (a math
# command, L4-LOGIC-01's territory) from double-flagging as the word "iff".
_SHORTHAND_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<!\\)\biff\b", re.IGNORECASE), '"iff" — write "if and only if"'),
    (re.compile(r"\bs\.t\.", re.IGNORECASE), '"s.t." — write "such that"'),
    (re.compile(r"\bwlog\b", re.IGNORECASE), '"WLOG" — write "without loss of generality"'),
    (re.compile(r"\bw\.r\.t\.?", re.IGNORECASE), '"w.r.t." — write "with respect to"'),
]
# L4-SYM-02: sentence boundary = ./?/! after two word characters (rules out
# "e.g." / "w.r.t."-style abbreviations) followed by whitespace.
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=\w\w)[.?!]\s+")
# L4-SYM-02: paragraph starts (line following a blank line) also open sentences.
_PARAGRAPH_START_RE = re.compile(r"\n[ \t]*\n[ \t]*")
# L4-SYM-02: a lone letter followed by space/comma reads as a symbol; "A"/"a"
# (article) and "I" (pronoun) are excluded where this is applied.
_SINGLE_LETTER_START_RE = re.compile(r"^([A-Za-z])[ ,;:]")
# L4-USAGE-03: spelling traps and hyphenation fixes, case-insensitive.
_USAGE_TRAP_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bprinciple bundle\b", re.IGNORECASE), 'write "principal bundle"'),
    (re.compile(r"\bit's\b", re.IGNORECASE), '"it\'s" — contraction or misspelled possessive; review'),
    (re.compile(r"\boccurence\b", re.IGNORECASE), 'misspelling of "occurrence"'),
    (re.compile(r"\bdependant\b", re.IGNORECASE), 'write "dependent"'),
    (re.compile(r"\bauxillary\b", re.IGNORECASE), 'misspelling of "auxiliary"'),
    (re.compile(r"\bfeasable\b", re.IGNORECASE), 'misspelling of "feasible"'),
    (re.compile(r"\bpreceeding\b", re.IGNORECASE), 'misspelling of "preceding"'),
    (re.compile(r"\brefering\b", re.IGNORECASE), 'misspelling of "referring"'),
    (re.compile(r"\bcatagory\b", re.IGNORECASE), 'misspelling of "category"'),
    (re.compile(r"\bconsistant\b", re.IGNORECASE), 'misspelling of "consistent"'),
    (re.compile(r"\bnon-negative\b", re.IGNORECASE), 'prefer "nonnegative"'),
    (re.compile(r"\bnon-zero\b", re.IGNORECASE), 'prefer "nonzero"'),
]
# L4-USAGE-09: contractions; the generic "...n't" arm covers don't/can't/
# won't/isn't/doesn't and kin.
_CONTRACTION_RE = re.compile(
    r"\b(?:[A-Za-z]+n't|we'll|we're|we've|it's|let's|that's|there's|i'm|i've|i'll|you're)\b",
    re.IGNORECASE,
)
# L4-GRAM-07: "!" in prose; (?<!\\) spares the LaTeX thin-space command "\!".
_EXCLAMATION_RE = re.compile(r"(?<!\\)!")
# L5-DISP-04: a literal three-dot ellipsis anywhere (math or prose).
_LITERAL_DOTS_RE = re.compile(r"\.\.\.")
# L5-REF-03: \cite/\citet/\citep/... with optional [..] argument.
_CITE_RE = re.compile(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])?\{([^}]*)\}")
# L5-REF-03: \bibitem with optional [..] label.
_BIBITEM_RE = re.compile(r"\\bibitem(?:\[[^\]]*\])?\{([^}]*)\}")
# L2-QUANT-02: theorem-class environments whose statements ban "any".
_THEOREM_ENV_RE = re.compile(
    r"\\begin\{(theorem|lemma|proposition)\*?\}(.*?)\\end\{\1\*?\}", re.DOTALL
)
# L2-QUANT-02: the ambiguous quantifier itself.
_ANY_RE = re.compile(r"\bany\b", re.IGNORECASE)
# L4-SENT-01: trailing display tokens that carry no punctuation information.
_DISPLAY_TRAILING_NOISE_RE = re.compile(r"(?:\\label\{[^}]*\}|\\nonumber|\\notag|\\\\|\s)+$")


def run_lint(text: str) -> List[Finding]:
    """Run every deterministic rubric lint rule against ``text``."""
    stripped, regions = _strip_math(text)
    lines = text.split("\n")
    stripped_index = _LineIndex(stripped)
    raw_index = _LineIndex(text)
    findings: List[Finding] = []
    findings += _scan(stripped, stripped_index, lines, _LOGIC_SYMBOL_RE, "L4-LOGIC-01", "minor",
                      "logic symbol used as a prose abbreviation; write the words",
                      include_match=True)
    findings += _scan(stripped, stripped_index, lines, _LOGIC_COMMAND_RE, "L4-LOGIC-01", "minor",
                      "logic-symbol command in prose; write the words", include_match=True)
    for pattern, note in _SHORTHAND_PATTERNS:
        findings += _scan(stripped, stripped_index, lines, pattern, "L4-SHORT-01", "minor",
                          f"blackboard shorthand in prose: {note}")
    findings += _check_symbol_sentence_start(stripped, stripped_index, lines)
    for pattern, note in _USAGE_TRAP_PATTERNS:
        findings += _scan(stripped, stripped_index, lines, pattern, "L4-USAGE-03", "minor",
                          f"usage trap: {note}")
    findings += _scan(stripped, stripped_index, lines, _CONTRACTION_RE, "L4-USAGE-09", "minor",
                      "contraction in formal prose; expand it", include_match=True)
    findings += _check_colon_before_display(stripped, regions, stripped_index, lines)
    findings += _check_exclamations(stripped, stripped_index, lines)
    findings += _scan(text, raw_index, lines, _LITERAL_DOTS_RE, "L5-DISP-04", "minor",
                      'literal "..."; use \\ldots (between commas) or \\cdots (between operators)')
    findings += _check_cite_bibitem(text, raw_index, lines)
    findings += _check_any_in_theorems(stripped, stripped_index, lines)
    findings += _check_display_punctuation(stripped, regions, lines)
    # L5-AI-03 is an alias of the residue scan; its findings are emitted under
    # the canonical L1-CITE-03 rule id so run_all does not double-report.
    findings += run_residue_scan(text)
    return _dedupe_sort(findings)


def run_all(text: str) -> List[Finding]:
    """Residue scan + full lint, deduplicated and sorted by (severity, line)."""
    return _dedupe_sort(run_residue_scan(text) + run_lint(text))


# --- paper-register lint (final_paper deliverable) ----------------------------

# Rules L5-PAPER-01/02/03 gate the ``final_paper`` artifact: complete LaTeX
# article source authored under the paper contract
# (phase2/writing/paper_contract.py). All three are always-blocker: a paper
# with markdown residue, internal system register, or a missing article
# skeleton is not a paper. Rubric bullets live in
# math-writing-harness/rubric/L5-formatting.md ("Paper deliverable").

# L5-PAPER-01: verbatim environments are the one legitimate home for literal
# markdown-looking text; mask them (newline-preserving) before scanning.
_VERBATIM_ENV_RE = re.compile(
    r"\\begin\{(?P<envname>verbatim|lstlisting|Verbatim)\*?\}.*?\\end\{(?P=envname)\*?\}",
    re.DOTALL,
)
# L5-PAPER-01 patterns; each is deliberately conservative — prefer missing a
# borderline case to flagging legitimate LaTeX.
_PAPER_MARKDOWN_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    # Markdown heading: "# ..." (hash + space) or "##..." at line start. A bare
    # "#" at line start without a space is spared (LaTeX macro-parameter char).
    (re.compile(r"^#(?: |#)", re.MULTILINE), "markdown heading ('#'-line)"),
    # Triple-backtick code fence at line start.
    (re.compile(r"^```", re.MULTILINE), "markdown code fence (```)"),
    # Markdown bullet: "* " at line start ("- " is spared: LaTeX prose lines
    # legitimately start with a minus sign or an en-dash-as-hyphen).
    (re.compile(r"^\* ", re.MULTILINE), "markdown bullet ('* ' at line start)"),
    # Markdown link [text](url): the target must look like a URL so bracketed
    # math followed by a parenthesized argument, e.g. "[0,1](x)", is spared.
    (
        re.compile(r"\[[^\]\n]+\]\((?:https?://|www\.)[^)\n]+\)"),
        "markdown link [text](url)",
    ),
    # Markdown bold **...**: double asterisks are not meaningful LaTeX prose.
    (re.compile(r"\*\*[^*\n]+\*\*"), "markdown bold (**...**)"),
]
# L5-PAPER-02: internal system vocabulary that must not appear before the
# first \appendix (the Run archive paragraph of Appendix A is the only
# legitimate home). Word-boundary and case-insensitive; "manifestly" (and
# "manifestation" etc.) never matches because \b after "manifest" requires a
# non-word character. Common plurals of the single-word terms are included.
_PAPER_APPENDIX_RE = re.compile(r"^\\appendix\b", re.MULTILINE)
_PAPER_REGISTER_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bart_[a-z0-9_]+"), "internal artifact identifier (art_*)"),
    (re.compile(r"\bmanifest\b", re.IGNORECASE), '"manifest"'),
    (re.compile(r"\bledgers?\b", re.IGNORECASE), '"ledger"'),
    (re.compile(r"\bartifacts?\b", re.IGNORECASE), '"artifact"'),
    (re.compile(r"\bproof-state\b", re.IGNORECASE), '"proof-state"'),
    (re.compile(r"\bverifier reports?\b", re.IGNORECASE), '"verifier report"'),
    (re.compile(r"\bwriting debts?\b", re.IGNORECASE), '"writing debt"'),
    (re.compile(r"\bstate revisions?\b", re.IGNORECASE), '"state revision"'),
]
# L5-PAPER-03: the article skeleton every standalone paper must carry.
_PAPER_STRUCTURE_CHECKS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\\documentclass\b"), r"\documentclass"),
    (re.compile(r"\\begin\{abstract\}"), r"\begin{abstract}"),
    (re.compile(r"\\begin\{theorem\*?\}"), r"a theorem environment (\begin{theorem} or \begin{theorem*})"),
    (re.compile(r"\\begin\{proof\}"), r"\begin{proof}"),
    (re.compile(r"\\appendix\b"), r"\appendix"),
    (
        re.compile(r"\\begin\{thebibliography\}|\\bibliography\b"),
        r"a bibliography (\begin{thebibliography} or \bibliography)",
    ),
    (re.compile(r"\\end\{document\}"), r"\end{document}"),
]


def _mask_verbatim(text: str) -> str:
    """Blank verbatim environments, preserving newline counts (line numbers
    reported against the masked text stay valid for the original)."""

    def replace(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    return _VERBATIM_ENV_RE.sub(replace, text)


def run_paper_lint(text: str) -> List[Finding]:
    """Deterministic paper-register checks for ``final_paper`` LaTeX source.

    - ``L5-PAPER-01`` markdown residue in LaTeX (outside verbatim environments)
    - ``L5-PAPER-02`` internal system register before the first ``\\appendix``
    - ``L5-PAPER-03`` missing standalone-article structure

    All findings are blockers; complements (does not include) :func:`run_all`.
    """
    lines = text.split("\n")
    index = _LineIndex(text)
    findings: List[Finding] = []
    masked = _mask_verbatim(text)
    for pattern, label in _PAPER_MARKDOWN_PATTERNS:
        for match in pattern.finditer(masked):
            line = index.line_of(match.start())
            findings.append(
                Finding(
                    rule_id="L5-PAPER-01",
                    severity="blocker",
                    line=line,
                    excerpt=_excerpt(lines, line),
                    message=f"markdown residue in LaTeX: {label}",
                )
            )
    appendix_match = _PAPER_APPENDIX_RE.search(text)
    main_text_end = appendix_match.start() if appendix_match else len(text)
    main_text = text[:main_text_end]
    for pattern, label in _PAPER_REGISTER_PATTERNS:
        for match in pattern.finditer(main_text):
            line = index.line_of(match.start())
            findings.append(
                Finding(
                    rule_id="L5-PAPER-02",
                    severity="blocker",
                    line=line,
                    excerpt=_excerpt(lines, line),
                    message=f"internal register in main text: {label} (allowed only in Appendix A's Run archive)",
                )
            )
    for pattern, label in _PAPER_STRUCTURE_CHECKS:
        if not pattern.search(text):
            findings.append(
                Finding(
                    rule_id="L5-PAPER-03",
                    severity="blocker",
                    line=1,
                    excerpt=_excerpt(lines, 1),
                    message=f"paper structure: missing {label}",
                )
            )
    return _dedupe_sort(findings)


# --- anti-slop lint (L4-SLOP-01..12 deterministic subset + L4-HOUSE-03/07..11)

# Rubric section "AI-pattern slop & house anti-choreography" (rubric/L4-style.md,
# sources references/fetched/AI-SLOP.md + HOUSE.md): deterministic hunts for the
# fingerprints of machine prose. All checks run on the math-stripped text with
# LaTeX comments blanked, so math-mode content is never scanned. Findings flow
# into gate debts (majors gate, minors are ledger + editor-visible); they are
# NEVER attach-rejections — patches.py deliberately does not call run_slop_lint.

# Unescaped "%" to end of line: a LaTeX comment is not shipped prose; blanked
# length-preserving so offsets/line numbers stay valid.
_LATEX_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")

# L4-SLOP-01: AI-vocabulary lexicon, word-boundary + case-insensitive; each
# entry carries the base word so every finding names its offender. Density
# rule: findings are emitted only when the document has >= 2 total hits.
_SLOP_LEXICON_MIN_HITS = 2
_SLOP_LEXICON: List[Tuple[re.Pattern[str], str]] = [
    # delve/delves/delved/delving — the archetypal post-2022 AI verb.
    (re.compile(r"\bdelv(?:e|es|ed|ing)\b", re.IGNORECASE), "delve"),
    # tapestry — metaphor vocabulary.
    (re.compile(r"\btapestry\b", re.IGNORECASE), "tapestry"),
    # testament — "stands as a testament" fuel.
    (re.compile(r"\btestament\b", re.IGNORECASE), "testament"),
    # showcase/showcases/showcasing.
    (re.compile(r"\bshowcas(?:e|es|ing)\b", re.IGNORECASE), "showcase"),
    # underscore the WORD only: "\_" and subscripts never match (math is stripped).
    (re.compile(r"\bunderscor(?:e|es|ing)\b", re.IGNORECASE), "underscore"),
    # pivotal — significance-inflation adjective.
    (re.compile(r"\bpivotal\b", re.IGNORECASE), "pivotal"),
    # intricate/intricacies.
    (re.compile(r"\bintricate\b|\bintricacies\b", re.IGNORECASE), "intricate"),
    # interplay.
    (re.compile(r"\binterplay\b", re.IGNORECASE), "interplay"),
    # meticulous/meticulously.
    (re.compile(r"\bmeticulous(?:ly)?\b", re.IGNORECASE), "meticulous"),
    # boast/boasts (copula avoidance verb; also L4-SLOP-03's territory).
    (re.compile(r"\bboasts?\b", re.IGNORECASE), "boast"),
    # vibrant.
    (re.compile(r"\bvibrant\b", re.IGNORECASE), "vibrant"),
    # garner/garners/garnered.
    (re.compile(r"\bgarner(?:s|ed)?\b", re.IGNORECASE), "garner"),
    # foster/fosters/fostering/fostered.
    (re.compile(r"\bfoster(?:s|ing|ed)?\b", re.IGNORECASE), "foster"),
    # seamless/seamlessly.
    (re.compile(r"\bseamless(?:ly)?\b", re.IGNORECASE), "seamless"),
    # multifaceted.
    (re.compile(r"\bmultifaceted\b", re.IGNORECASE), "multifaceted"),
    # holistic.
    (re.compile(r"\bholistic\b", re.IGNORECASE), "holistic"),
    # commendable.
    (re.compile(r"\bcommendable\b", re.IGNORECASE), "commendable"),
    # resonate/resonates/resonating.
    (re.compile(r"\bresonat(?:e|es|ing)\b", re.IGNORECASE), "resonate"),
    # groundbreaking.
    (re.compile(r"\bgroundbreaking\b", re.IGNORECASE), "groundbreaking"),
    # renowned.
    (re.compile(r"\brenowned\b", re.IGNORECASE), "renowned"),
    # "valuable insights" as a fixed phrase.
    (re.compile(r"\bvaluable insights\b", re.IGNORECASE), "valuable insights"),
    # "ever-evolving" as a fixed phrase.
    (re.compile(r"\bever-evolving\b", re.IGNORECASE), "ever-evolving"),
    # metaphorical landscape/realm/journey — mathematical usage is rare enough
    # that the bare words are flagged.
    (re.compile(r"\blandscape\b", re.IGNORECASE), "landscape"),
    (re.compile(r"\brealm\b", re.IGNORECASE), "realm"),
    (re.compile(r"\bjourney\b", re.IGNORECASE), "journey"),
]

# L4-SLOP-02 (major): significance-inflation phrases, case-insensitive.
_SLOP_INFLATION_PATTERNS: List[re.Pattern[str]] = [
    # "plays a crucial/vital/pivotal/key/significant role" in any tense.
    re.compile(r"\bplay(?:s|ed|ing)? a (?:crucial|vital|pivotal|key|significant) role\b", re.IGNORECASE),
    # "stands as a testament/reminder".
    re.compile(r"\bstands? as a (?:testament|reminder)\b", re.IGNORECASE),
    # "serves as a testament/reminder".
    re.compile(r"\bserves? as a (?:testament|reminder)\b", re.IGNORECASE),
    # "underscores (its/the) importance/significance".
    re.compile(r"\bunderscor\w+ (?:its |the )?(?:importance|significance)\b", re.IGNORECASE),
    # "highlights (its/the) importance/significance".
    re.compile(r"\bhighlight\w+ (?:its |the )?(?:importance|significance)\b", re.IGNORECASE),
    # "setting the stage for".
    re.compile(r"\bsetting the stage for\b", re.IGNORECASE),
    # "marks a (key) shift/turning point".
    re.compile(r"\bmarks? a (?:key )?(?:shift|turning point)\b", re.IGNORECASE),
    # "reflects broader".
    re.compile(r"\breflects broader\b", re.IGNORECASE),
]

# L4-SLOP-03 (minor): copula avoidance; matches inside an L4-SLOP-02 span are
# deduplicated away (the phrase already carries the major finding).
_SLOP_COPULA_PATTERNS: List[re.Pattern[str]] = [
    # "serves as" where plain "is" is meant.
    re.compile(r"\bserves? as\b", re.IGNORECASE),
    # "stands as".
    re.compile(r"\bstands? as\b", re.IGNORECASE),
    # "boasts".
    re.compile(r"\bboasts?\b", re.IGNORECASE),
]

# L4-SLOP-04 (major — it gates): the rhetorical-reversal family ("negative
# parallelism", AI-SLOP §4). Two arms. The single-sentence arm below flags the
# not-A-but-B reversal in every punctuation costume; each pattern caps its
# middle run at [^.!?] so a match never crosses a sentence boundary, and all
# run case-insensitively on math-stripped, comment-blanked prose. The generic
# "not X" patterns exclude "only"/"because" after "not" so the dedicated
# "not only"/"not because" patterns own those phrases (one finding each).
_SLOP_PARALLELISM_PATTERNS: List[re.Pattern[str]] = [
    # "not only X but also Y" within one sentence (<= 120 chars between).
    re.compile(r"\bnot only\b[^.!?]{0,120}\bbut also\b", re.IGNORECASE),
    # "not X, but rather Y": comma + "but rather" within one sentence.
    re.compile(r"\bnot (?!only\b|because\b)\w+[^.!?]{0,60}, but rather\b", re.IGNORECASE),
    # "not X — but Y": the em-dash costume — a unicode em dash or LaTeX "---"
    # (exactly three hyphens, so en dashes "--" never match); non-greedy run so
    # the FIRST dash after the negation anchors the match.
    re.compile(r"\bnot (?!only\b|because\b)\w+[^.!?]{0,60}?(?:—|(?<!-)---(?!-))\s*but\b", re.IGNORECASE),
    # "not X; it is Y": the semicolon costume; [^.!?;] anchors the first
    # semicolon after the negation, then a positive "it is"/"it's" resumption.
    re.compile(r"\bnot (?!only\b|because\b)\w+[^.!?;]{0,60}; (?:it is|it['’]s)\b", re.IGNORECASE),
    # "not because X(,) but because Y" (the optional comma sits inside [^.!?]).
    re.compile(r"\bnot because\b[^.!?]{0,80}\bbut because\b", re.IGNORECASE),
]

# L4-SLOP-04 cross-sentence arm (major): flagged ONLY when the false-positive
# risk is low. Sentence 1 must OPEN with a rhetorical framing subject —
# It/This/That or "The point/question/issue/answer/key/goal/idea/reason/
# problem/result" — followed by a copular negation; concrete mathematical
# subjects ("The group is not abelian.", "G is not simple.") never match:
# that framing-subject requirement is the false-positive boundary.
_SLOP_FRAMING_SUBJECT = (
    r"(?:It|This|That|The\s+(?:point|question|issue|answer|key|goal|idea|reason|problem|result))"
)
# Copular negation: "is not"/"isn't"/"was not"/"wasn't"/"is no"/"are not"/
# "aren't" (apostrophes optional so "isnt" typos still count).
_SLOP_COPULAR_NEGATION = r"(?:is\s+not|isn'?t|was\s+not|wasn'?t|is\s+no|are\s+not|aren'?t)"
# Sentence 1 of a cross-sentence reversal, matched only AT a sentence start:
# framing subject + copular negation, the rest of the sentence (no internal
# sentence-ending mark, <= 160 chars), its closing mark, and the gap.
_SLOP_REVERSAL_FIRST_RE = re.compile(
    rf"{_SLOP_FRAMING_SUBJECT}\s+{_SLOP_COPULAR_NEGATION}\b[^.!?]{{0,160}}[.!?]\s+",
    re.IGNORECASE,
)
# Sentence 2 opener: a matching pronoun/framing subject + POSITIVE copula
# ("It is"/"It's"/"This is"/"That is", with an optional "Rather,"/"Instead,"
# lead-in before "it is"). "It's" requires its apostrophe so possessive "Its"
# never matches; the lookahead rejects "not"/"no" after the copula — a second
# negation is the negative-listing arm's business, not a reversal.
_SLOP_REVERSAL_SECOND_RE = re.compile(
    r"(?:(?:Rather|Instead),\s+it\s+is|It\s+is|It['’]s|This\s+is|That\s+is)"
    r"(?!\s+(?:not|no)\b)\b",
    re.IGNORECASE,
)
# L4-SLOP-04 negative-listing arm (major): one framing-subject copular-negation
# sentence, with trailing whitespace consumed so consecutive matches chain.
_SLOP_NEG_LIST_SENTENCE_RE = re.compile(
    rf"{_SLOP_FRAMING_SUBJECT}\s+{_SLOP_COPULAR_NEGATION}\b[^.!?]{{0,160}}[.!?]\s*",
    re.IGNORECASE,
)
# Negative-listing closer: a positive copular sentence of the same subject
# class ("It was Z."); the lookahead again rejects a further negation.
_SLOP_NEG_LIST_CLOSE_RE = re.compile(
    rf"(?:{_SLOP_FRAMING_SUBJECT}\s+(?:is|was|are)|It['’]s)(?!\s+(?:not|no)\b)\b",
    re.IGNORECASE,
)
# Negative listing needs at least this many consecutive negated sentences.
_SLOP_NEG_LIST_MIN_NEGATIONS = 2

# L4-SLOP-05 (major): paragraph-initial recap openers. Paragraph-initial means
# document start, a line start after a blank line, or right after \par.
_SLOP_RECAP_RE = re.compile(
    r"(?:\A|\n[ \t]*\n[ \t]*|\\par\s+)"
    r"(?P<opener>(?:In summary|Overall|In conclusion|Taken together|To summarize),)",
    re.IGNORECASE,
)

# L4-SLOP-06 (minor): a sentence/paragraph opener that is a bare connector.
_SLOP_CONNECTOR_RE = re.compile(r"(?P<word>Moreover|Furthermore|Additionally|Also)\b[,\s]", re.IGNORECASE)

# L4-SLOP-07 (nit): an em dash is a unicode em dash or LaTeX "---" (exactly
# three hyphens: "--" is an en dash and stays legal).
_EM_DASH_RE = re.compile(r"—|(?<!-)---(?!-)")
_EM_DASH_WINDOW_CHARS = 2000
_EM_DASH_MAX_PER_WINDOW = 3

# L4-SLOP-09 (major): task-narration/choreography phrases. Plain "it remains
# to" is legitimate mathematical usage and is deliberately NOT matched here —
# the rubric's "as filler" judgment belongs to the editor, not the linter.
_SLOP_CHOREOGRAPHY_PATTERNS: List[re.Pattern[str]] = [
    # "We now proceed to".
    re.compile(r"\bwe now proceed to\b", re.IGNORECASE),
    # "We first establish the following".
    re.compile(r"\bwe first establish the following\b", re.IGNORECASE),
    # "Having established X, we turn/proceed/move".
    re.compile(r"\bhaving established\b[^,.]*, we (?:turn|proceed|move)\b", re.IGNORECASE),
    # "With these/this preparation(s) in place".
    re.compile(r"\bwith (?:these|this) preparations? in place\b", re.IGNORECASE),
    # "the necessary input".
    re.compile(r"\bthe necessary input\b", re.IGNORECASE),
    # "the remaining calculation".
    re.compile(r"\bthe remaining calculation\b", re.IGNORECASE),
    # "the proof rests on two/three/.../N points/steps/pillars".
    re.compile(r"\bthe proof rests on (?:two|three|four|several|\d+) (?:points|steps|pillars)\b", re.IGNORECASE),
    # "we (now) record the following".
    re.compile(r"\bwe (?:now )?record the following\b", re.IGNORECASE),
    # "needed below".
    re.compile(r"\bneeded below\b", re.IGNORECASE),
    # "the mechanism is simple".
    re.compile(r"\bthe mechanism is simple\b", re.IGNORECASE),
]

# L4-SLOP-11 (minor): blank-line paragraph separator.
_PARAGRAPH_SPLIT_RE = re.compile(r"\n[ \t]*\n")
# L4-SLOP-11: statement environments whose bodies are exempt — the style core
# REQUIRES one-sentence theorem statements; the abstract's single paragraph is
# likewise required.
_STATEMENT_ENV_RE = re.compile(
    r"\\begin\{(theorem|lemma|proposition|corollary|definition|remark|example|conjecture|claim|abstract)\*?\}"
    r".*?\\end\{\1\*?\}",
    re.DOTALL,
)
_SLOP_ONE_SENTENCE_MIN_COUNT = 2

# L4-SLOP-12 (nit): paragraph-initial "This/These/It" + verb-like word (no
# single antecedent; repeat the noun). Capitalized on purpose: paragraph opener.
_SLOP_VAGUE_OPENER_RE = re.compile(
    r"(?:\A[ \t]*|\n[ \t]*\n[ \t]*|\\par\s+)"
    r"(?P<opener>(?:This|These|It)[ \t]+"
    r"(?:is|are|was|shows|means|suggests|implies|demonstrates|follows|gives|yields|establishes|highlights)\b)"
)

# \label/\ref-family, \cite-family, \url/\href/\path, sectioning + \title:
# their braced arguments hold keys, URLs, and headings — not prose. Shared by
# the L4-HOUSE-03 masking and the L4-HOUSE-09..11 prose word counter.
_KEY_ARG_COMMAND_RE = re.compile(
    r"\\(?:label|ref|eqref|cref|Cref|autoref|nameref|pageref|hyperref|vref"
    r"|cite[a-zA-Z]*|url|href|path"
    r"|section|subsection|subsubsection|paragraph|subparagraph|title)"
    r"\*?(?:\[[^\]]*\])?\{[^}]*\}"
)
# L4-HOUSE-03 (minor): colon/semicolon in prose. Masked before scanning
# (generous, per HOUSE 15: better under-flag than false-positive):
# bibliography blocks, and the arguments of label/ref/cite-like, url/href, and
# sectioning/title commands (colons there are technical, not prose).
_HOUSE03_MASK_RES: List[re.Pattern[str]] = [
    # The bibliography block is exempt wholesale.
    re.compile(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", re.DOTALL),
    _KEY_ARG_COMMAND_RE,
]
# L4-HOUSE-03: "Case 1:"-style labels (also Step/Subcase) are legitimate.
_HOUSE03_CASE_LABEL_RE = re.compile(r"\b(?:Case|Step|Subcase)[ ~]+[^\s:;]{1,20}$")
_HOUSE03_MARK_RE = re.compile(r"[:;]")
_BEGIN_DOCUMENT_RE = re.compile(r"\\begin\{document\}")

# L4-HOUSE-07 (major, HARD RULE per HOUSE 19): every section's first paragraph
# opens with a sentence beginning "In this section, we" ("In this appendix,
# we" after \appendix). References/Acknowledgment/bibliography sections (and
# their \section* variants) are exempt.
_HOUSE07_SECTION_RE = re.compile(r"\\section\*?\{(?P<title>[^}]*)\}")
_HOUSE07_EXEMPT_TITLE_RE = re.compile(r"references|acknowledgm|bibliography", re.IGNORECASE)
_HOUSE07_APPENDIX_RE = re.compile(r"^\\appendix\b", re.MULTILINE)
_HOUSE07_SECTION_OPENER_RE = re.compile(r"\bIn this section, we\b")
_HOUSE07_APPENDIX_OPENER_RE = re.compile(r"\bIn this appendix, we\b")
# The first paragraph ends at a blank line or at the next sectioning command.
_HOUSE07_PARAGRAPH_END_RE = re.compile(r"\n[ \t]*\n|\\section\b|\\appendix\b|\\begin\{thebibliography\}|\\end\{document\}")

# L4-HOUSE-08 (major, HARD RULE per HOUSE 25): the deterministic subset of the
# "we" discipline — habitual collocations banned outright in prose (the
# judgment remainder stays with the editor under L4-HOUSE-02).
_HOUSE08_WE_COLLOCATION_RE = re.compile(
    r"\bwe (?:recall|record|now show|now prove|now turn|begin by|start by|note that|observe that)\b",
    re.IGNORECASE,
)

# L4-HOUSE-09 (major, HARD RULE): a \section whose prose body carries fewer
# than this many words is a stub — a heading over one or two short paragraphs.
STUB_SECTION_MIN_WORDS = 120
# L4-HOUSE-10 (major): this many stub sections in the main body (before
# \appendix) is document-level fragmentation.
FRAGMENTATION_MIN_STUB_SECTIONS = 2
# L4-HOUSE-10 (major): main-body sections per 1000 prose words above this
# ratio is fragmentation even when no single section is a stub.
FRAGMENTATION_MAX_SECTIONS_PER_1000_WORDS = 2.5
# L4-HOUSE-11 (minor): a list is bullet narration at >= this many items ...
BULLET_NARRATION_MIN_ITEMS = 4
# L4-HOUSE-11 (minor): ... when EVERY item carries >= this many prose words.
BULLET_NARRATION_MIN_ITEM_WORDS = 15
# L4-HOUSE-11 density arm: more than one list per two sections is flagged.
LIST_DENSITY_MAX_LISTS_PER_SECTION = 0.5

# L4-HOUSE-09/10: a section's prose body ends at the next sectioning command
# (subsections stay inside their parent's body: a \section is judged with all
# of its content, and \subsection titles are masked out of the word count).
_SECTION_BODY_END_RE = re.compile(
    r"\\section\*?\{|\\appendix\b|\\begin\{thebibliography\}|\\end\{document\}"
)
# L4-HOUSE-09..11 word counting: environments whose content is data or code,
# not prose — tables/figures/floats, bibliographies, verbatim — are blanked.
_NON_PROSE_ENV_RE = re.compile(
    r"\\begin\{(?P<npenv>table|figure|tabular|tabularx|longtable|thebibliography|verbatim|lstlisting|Verbatim)\*?\}"
    r".*?\\end\{(?P=npenv)\*?\}",
    re.DOTALL,
)
# Word counting: a prose word is a letter run; hyphen/apostrophe compounds
# ("well-defined", "Zorn's") count once.
_PROSE_WORD_RE = re.compile(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*")
# Word counting: any residual command token is dropped, but the braced prose
# argument of formatting commands (\emph{...}) still counts as words.
_LATEX_COMMAND_TOKEN_RE = re.compile(r"\\[a-zA-Z@]+\*?|\\.")
# L4-HOUSE-11: itemize/enumerate lists. Non-greedy with a backreference: a
# nested list of the SAME environment name mismatches (rare; conservative).
_LIST_ENV_RE = re.compile(
    r"\\begin\{(?P<listenv>itemize|enumerate)\*?\}(?P<listbody>.*?)\\end\{(?P=listenv)\*?\}",
    re.DOTALL,
)
# L4-HOUSE-11: item boundaries within a list body (optional [label] skipped).
_ITEM_SPLIT_RE = re.compile(r"\\item\b(?:\[[^\]]*\])?")


def _blank_preserving_newlines(text: str) -> str:
    """Replace every non-newline character with a space (offsets survive)."""
    return "".join("\n" if ch == "\n" else " " for ch in text)


def _mask_regions(text: str, patterns: Iterable[re.Pattern[str]]) -> str:
    for pattern in patterns:
        text = pattern.sub(lambda match: _blank_preserving_newlines(match.group(0)), text)
    return text


def run_slop_lint(text: str) -> List[Finding]:
    """Deterministic anti-slop lint (rubric L4-SLOP-* subset + L4-HOUSE-03
    + the hard house rules L4-HOUSE-07/08/09/10 + L4-HOUSE-11).

    LaTeX-aware: math is stripped to placeholders first (math-mode content is
    never scanned) and comments are blanked. Complements :func:`run_lint`; the
    scheduler's writing-gate lint sync adds these findings as debts. They are
    debts, not attach-rejections.
    """
    stripped, _regions = _strip_math(text)
    prose = _mask_regions(stripped, [_LATEX_COMMENT_RE])
    lines = text.split("\n")
    index = _LineIndex(prose)
    findings: List[Finding] = []
    findings += _check_slop_lexicon(prose, index, lines)
    inflation_spans = _check_slop_inflation(prose, index, lines, findings)
    findings += _check_slop_copulas(prose, index, lines, inflation_spans)
    for pattern in _SLOP_PARALLELISM_PATTERNS:
        findings += _scan(prose, index, lines, pattern, "L4-SLOP-04", "major",
                          "negative-parallelism drama (rhetorical reversal); "
                          "state the positive claim directly",
                          include_match=True)
    findings += _check_slop_reversal_sentences(prose, index, lines)
    for match in _SLOP_RECAP_RE.finditer(prose):
        line = index.line_of(match.start("opener"))
        findings.append(Finding("L4-SLOP-05", "major", line, _excerpt(lines, line),
                                f"recap paragraph opener {match.group('opener')!r}; "
                                "math papers do not recap sections — delete the recap"))
    findings += _check_slop_connector_chains(prose, index, lines)
    findings += _check_slop_em_dash_density(prose, index, lines)
    for pattern in _SLOP_CHOREOGRAPHY_PATTERNS:
        findings += _scan(prose, index, lines, pattern, "L4-SLOP-09", "major",
                          "task-narration/choreography phrase; state the mathematical "
                          "implication in use instead", include_match=True)
    findings += _check_one_sentence_paragraphs(prose, index, lines)
    for match in _SLOP_VAGUE_OPENER_RE.finditer(prose):
        line = index.line_of(match.start("opener"))
        findings.append(Finding("L4-SLOP-12", "nit", line, _excerpt(lines, line),
                                f"vague-pronoun paragraph opener {match.group('opener')!r}; "
                                "repeat the noun"))
    findings += _check_house_colon_semicolon(prose, index, lines)
    findings += _check_house_section_openers(text, lines)
    findings += _scan(prose, index, lines, _HOUSE08_WE_COLLOCATION_RE, "L4-HOUSE-08", "major",
                      'habitual "we" collocation (HARD RULE, HOUSE 25); state the mathematical '
                      "fact directly or name the genuinely novel authorial act", include_match=True)
    findings += _check_section_substantiality(text, lines)
    findings += _check_bullet_narration(prose, index, lines)
    return _dedupe_sort(findings)


def _check_slop_lexicon(prose: str, index: _LineIndex, lines: List[str]) -> List[Finding]:
    """L4-SLOP-01: AI-vocabulary lexicon under the density rule — one finding
    per hit, emitted only when the document carries >= 2 total lexicon hits."""
    hits: List[Tuple[int, str]] = []
    for pattern, word in _SLOP_LEXICON:
        for match in pattern.finditer(prose):
            hits.append((match.start(), word))
    if len(hits) < _SLOP_LEXICON_MIN_HITS:
        return []
    findings: List[Finding] = []
    for start, word in hits:
        line = index.line_of(start)
        findings.append(Finding("L4-SLOP-01", "minor", line, _excerpt(lines, line),
                                f'AI-vocabulary word "{word}" '
                                f"({len(hits)} lexicon hits in this document); rewrite plainly"))
    return findings


def _check_slop_inflation(
    prose: str, index: _LineIndex, lines: List[str], findings: List[Finding]
) -> List[Tuple[int, int]]:
    """L4-SLOP-02: significance-inflation phrases. Appends findings in place and
    returns the matched spans so L4-SLOP-03 can dedupe against them."""
    spans: List[Tuple[int, int]] = []
    for pattern in _SLOP_INFLATION_PATTERNS:
        for match in pattern.finditer(prose):
            spans.append((match.start(), match.end()))
            line = index.line_of(match.start())
            findings.append(Finding("L4-SLOP-02", "major", line, _excerpt(lines, line),
                                    f"significance inflation: {match.group(0)!r}; state the "
                                    "specific mathematical fact or delete"))
    return spans


def _check_slop_copulas(
    prose: str, index: _LineIndex, lines: List[str], inflation_spans: List[Tuple[int, int]]
) -> List[Finding]:
    """L4-SLOP-03: copula avoidance, outside the L4-SLOP-02 phrase spans."""
    findings: List[Finding] = []
    for pattern in _SLOP_COPULA_PATTERNS:
        for match in pattern.finditer(prose):
            # Dedupe by span: inside an inflation phrase the major already covers it.
            if any(start <= match.start() < end for start, end in inflation_spans):
                continue
            line = index.line_of(match.start())
            findings.append(Finding("L4-SLOP-03", "minor", line, _excerpt(lines, line),
                                    f'copula avoidance: {match.group(0)!r}; write plain "is"/"are"/"has"'))
    return findings


def _sentence_starts(prose: str) -> List[int]:
    """Offsets where a sentence can begin: after a sentence boundary, at a
    paragraph start, and at the document's first non-whitespace character."""
    starts = {match.end() for match in _SENTENCE_BOUNDARY_RE.finditer(prose)}
    starts |= {match.end() for match in _PARAGRAPH_START_RE.finditer(prose)}
    starts.add(len(prose) - len(prose.lstrip()))
    return sorted(starts)


def _check_slop_reversal_sentences(
    prose: str, index: _LineIndex, lines: List[str]
) -> List[Finding]:
    """L4-SLOP-04 (major), the two cross-sentence arms. Both anchor sentence 1
    at a computed sentence start, so a mid-sentence "it is not ..." never
    opens a match and concrete mathematical subjects ("The group is not
    abelian. Its center is trivial."; "G is not simple. It is solvable.")
    stay unflagged.

    - Negative listing: >= _SLOP_NEG_LIST_MIN_NEGATIONS consecutive
      framing-subject copular-negation sentences followed by a positive
      copular sentence of the same subject class ("It was not X. It was not
      Y. It was Z.") — one finding per listing, at its first sentence.
    - Cross-sentence reversal: a framing-subject copular-negation sentence
      whose NEXT sentence opens with a matching pronoun/framing subject and a
      positive copula ("It is not a coincidence. It is a theorem."). Reversal
      pairs inside an already-flagged listing are not double-reported.
    """
    findings: List[Finding] = []
    starts = _sentence_starts(prose)
    listing_spans: List[Tuple[int, int]] = []
    for start in starts:
        if any(span_start <= start < span_end for span_start, span_end in listing_spans):
            continue  # inside a flagged listing: no sub-listing findings
        negations = 0
        pos = start
        while True:
            match = _SLOP_NEG_LIST_SENTENCE_RE.match(prose, pos)
            if match is None:
                break
            negations += 1
            pos = match.end()
        if negations < _SLOP_NEG_LIST_MIN_NEGATIONS:
            continue
        if _SLOP_NEG_LIST_CLOSE_RE.match(prose, pos) is None:
            continue
        listing_spans.append((start, pos))
        line = index.line_of(start)
        snippet = " ".join(prose[start : start + 80].split())
        findings.append(Finding(
            "L4-SLOP-04", "major", line, _excerpt(lines, line),
            f"negative listing ({negations} copular negations before the positive); "
            f"state the positive claim directly: {snippet!r}"))
    for start in starts:
        if any(span_start <= start < span_end for span_start, span_end in listing_spans):
            continue  # the listing finding already covers this construct
        first = _SLOP_REVERSAL_FIRST_RE.match(prose, start)
        if first is None:
            continue
        if _SLOP_REVERSAL_SECOND_RE.match(prose, first.end()) is None:
            continue
        line = index.line_of(start)
        snippet = " ".join(prose[start : first.end() + 24].split())
        findings.append(Finding(
            "L4-SLOP-04", "major", line, _excerpt(lines, line),
            "cross-sentence rhetorical reversal (It-is-not-A-It-is-B); "
            f"state the positive claim directly: {snippet!r}"))
    return findings


def _check_slop_connector_chains(
    prose: str, index: _LineIndex, lines: List[str]
) -> List[Finding]:
    """L4-SLOP-06: two or more consecutive sentences (or paragraph openings)
    starting with Moreover/Furthermore/Additionally/Also; the second and later
    openers are flagged."""
    findings: List[Finding] = []
    previous_was_connector = False
    for start in _sentence_starts(prose):
        match = _SLOP_CONNECTOR_RE.match(prose, start)
        if match is not None and previous_was_connector:
            line = index.line_of(start)
            # The connector word is named so distinct offenders on one line
            # survive deduplication (same convention as _scan include_match).
            findings.append(Finding("L4-SLOP-06", "minor", line, _excerpt(lines, line),
                                    "consecutive sentences open with a connector: "
                                    f"{match.group('word')!r}; vary or drop"))
        previous_was_connector = match is not None
    return findings


def _check_slop_em_dash_density(
    prose: str, index: _LineIndex, lines: List[str]
) -> List[Finding]:
    """L4-SLOP-07: more than 3 em dashes per ~2000 characters of prose; one
    finding per excess cluster (the window resets after each finding)."""
    positions = [match.start() for match in _EM_DASH_RE.finditer(prose)]
    findings: List[Finding] = []
    window_start = 0
    for i, pos in enumerate(positions):
        while pos - positions[window_start] > _EM_DASH_WINDOW_CHARS:
            window_start += 1
        if i - window_start >= _EM_DASH_MAX_PER_WINDOW:
            line = index.line_of(pos)
            findings.append(Finding("L4-SLOP-07", "nit", line, _excerpt(lines, line),
                                    f"em-dash density: more than {_EM_DASH_MAX_PER_WINDOW} em "
                                    f"dashes within ~{_EM_DASH_WINDOW_CHARS} characters of prose"))
            window_start = i + 1  # one finding per cluster
    return findings


def _check_one_sentence_paragraphs(
    prose: str, index: _LineIndex, lines: List[str]
) -> List[Finding]:
    """L4-SLOP-11: one-sentence prose paragraphs, flagged only when the
    document has >= 2 of them. Display math, heading/environment/\\item
    blocks, statement-environment bodies, and the abstract are exempt."""
    exempt_spans = [(m.start(), m.end()) for m in _STATEMENT_ENV_RE.finditer(prose)]
    offenders: List[int] = []
    pos = 0
    boundaries = [(m.start(), m.end()) for m in _PARAGRAPH_SPLIT_RE.finditer(prose)]
    boundaries.append((len(prose), len(prose)))
    for split_start, split_end in boundaries:
        paragraph = prose[pos:split_start]
        paragraph_start = pos + (len(paragraph) - len(paragraph.lstrip()))
        pos = split_end
        text = paragraph.strip()
        if not text:
            continue
        if any(start <= paragraph_start < end for start, end in exempt_spans):
            continue  # statement environments and the abstract
        if text.startswith("\\") or "\\begin{" in text or "\\end{" in text or "\\item" in text:
            continue  # heading/environment/preamble/item block, not a prose paragraph
        if re.fullmatch(rf"(?:{INLINE_MATH_PLACEHOLDER}|{DISPLAY_MATH_PLACEHOLDER}|[\s.,;:])+", text):
            continue  # bare (display) math with punctuation
        trimmed = text.rstrip("'\")”’")
        if not trimmed or trimmed[-1] not in ".?!":
            continue  # not a complete sentence at all — other rules' business
        if any(match.end() < len(text) for match in _SENTENCE_BOUNDARY_RE.finditer(text)):
            continue  # an internal sentence boundary: two or more sentences
        offenders.append(paragraph_start)
    if len(offenders) < _SLOP_ONE_SENTENCE_MIN_COUNT:
        return []
    findings: List[Finding] = []
    for start in offenders:
        line = index.line_of(start)
        findings.append(Finding("L4-SLOP-11", "minor", line, _excerpt(lines, line),
                                f"one-sentence paragraph ({len(offenders)} in this document); "
                                "merge it or develop the topic sentence"))
    return findings


def _check_house_colon_semicolon(
    prose: str, index: _LineIndex, lines: List[str]
) -> List[Finding]:
    """L4-HOUSE-03: colon/semicolon in prose. Exceptions (generous): the LaTeX
    preamble (scan starts at \\begin{document}), bibliography blocks, \\ref-like
    command arguments, "Case 1:"-style labels, and colons introducing math or a
    LaTeX environment."""
    body = _BEGIN_DOCUMENT_RE.search(prose)
    scan_from = body.end() if body else 0
    masked = _mask_regions(prose, _HOUSE03_MASK_RES)
    findings: List[Finding] = []
    for match in _HOUSE03_MARK_RE.finditer(masked, scan_from):
        mark = match.group(0)
        if mark == ":":
            # A colon introducing displayed/inline math or an environment
            # (itemize/enumerate lead-ins) is conventional; spare it.
            following = masked[match.end() : match.end() + 200].lstrip()
            if (
                following.startswith(DISPLAY_MATH_PLACEHOLDER)
                or following.startswith(INLINE_MATH_PLACEHOLDER)
                or following.startswith("\\begin{")
            ):
                continue
            # "Case 1:" / "Step 2:" / "Subcase 1a:" labels are legitimate.
            before = masked[max(0, match.start() - 40) : match.start()]
            if _HOUSE03_CASE_LABEL_RE.search(before):
                continue
        line = index.line_of(match.start())
        word = "colon" if mark == ":" else "semicolon"
        findings.append(Finding("L4-HOUSE-03", "minor", line, _excerpt(lines, line),
                                f"{word} in prose; prefer separate sentences or a connecting phrase"))
    return findings


def _check_house_section_openers(text: str, lines: List[str]) -> List[Finding]:
    """L4-HOUSE-07 (HARD RULE, HOUSE 19): every \\section's first paragraph
    carries a sentence beginning "In this section, we" — "In this appendix,
    we" for sections after \\appendix. References/Acknowledgment/bibliography
    sections are exempt. Scans the raw text with comments blanked (math never
    contains the opener, so stripping is unnecessary and would garble titles).
    """
    masked = _mask_regions(text, [_LATEX_COMMENT_RE])
    index = _LineIndex(masked)
    appendix_match = _HOUSE07_APPENDIX_RE.search(masked)
    appendix_start = appendix_match.start() if appendix_match else len(masked)
    findings: List[Finding] = []
    for section in _HOUSE07_SECTION_RE.finditer(masked):
        title = " ".join(section.group("title").split())
        if _HOUSE07_EXEMPT_TITLE_RE.search(title):
            continue
        in_appendix = section.start() >= appendix_start
        # First paragraph: skip whitespace after the heading, then read up to
        # the first blank line or the next sectioning command.
        rest = masked[section.end():]
        body_offset = len(rest) - len(rest.lstrip())
        body = rest[body_offset:]
        end = _HOUSE07_PARAGRAPH_END_RE.search(body)
        paragraph = body[: end.start()] if end else body
        opener = _HOUSE07_APPENDIX_OPENER_RE if in_appendix else _HOUSE07_SECTION_OPENER_RE
        if opener.search(paragraph):
            continue
        wanted = "In this appendix, we" if in_appendix else "In this section, we"
        line = index.line_of(section.start())
        findings.append(Finding("L4-HOUSE-07", "major", line, _excerpt(lines, line),
                                f'section {title!r} does not open with a sentence beginning '
                                f'"{wanted} ..." in its first paragraph (HARD RULE, HOUSE 19)'))
    return findings


def _prose_word_count(segment: str) -> int:
    """Count prose words in a LaTeX segment. Excluded from the count: math
    (inline and display), comments, non-prose environments (tables, figures,
    floats, bibliographies, verbatim), key-carrying command arguments
    (labels/refs/cites/URLs/headings), and command tokens themselves — the
    braced prose argument of formatting commands (\\emph{...}) still counts.
    Idempotent on already math-stripped text (placeholders are removed)."""
    stripped, _regions = _strip_math(segment)
    text = _mask_regions(stripped, [_LATEX_COMMENT_RE, _NON_PROSE_ENV_RE, _KEY_ARG_COMMAND_RE])
    text = text.replace(INLINE_MATH_PLACEHOLDER, " ").replace(DISPLAY_MATH_PLACEHOLDER, " ")
    text = _LATEX_COMMAND_TOKEN_RE.sub(" ", text)
    return len(_PROSE_WORD_RE.findall(text))


def _check_section_substantiality(text: str, lines: List[str]) -> List[Finding]:
    """L4-HOUSE-09 (HARD RULE) + L4-HOUSE-10: sections are substantial units.

    - ``L4-HOUSE-09`` (major): a \\section (main body or appendix) whose prose
      body — the text between its heading and the next sectioning command —
      has fewer than STUB_SECTION_MIN_WORDS words is a stub. Math, displays,
      tables, and figures never count, so a section that is mostly displays
      with thin connecting prose is still a stub.
      References/Acknowledgment/bibliography sections are exempt.
    - ``L4-HOUSE-10`` (major, document-level): the main body (before
      \\appendix) fragments when it has FRAGMENTATION_MIN_STUB_SECTIONS or
      more stub sections, or more than
      FRAGMENTATION_MAX_SECTIONS_PER_1000_WORDS sections per 1000 prose
      words. Fragmentation is a plurality defect: the check needs at least
      two main-body sections.

    Scans the raw text with comments blanked (titles must stay readable for
    the finding messages); word counts strip math per body.
    """
    masked = _mask_regions(text, [_LATEX_COMMENT_RE])
    index = _LineIndex(masked)
    appendix_match = _HOUSE07_APPENDIX_RE.search(masked)
    appendix_start = appendix_match.start() if appendix_match else len(masked)
    findings: List[Finding] = []
    main_sections = 0
    main_stubs = 0
    first_section_line: int | None = None
    for section in _HOUSE07_SECTION_RE.finditer(masked):
        title = " ".join(section.group("title").split())
        if _HOUSE07_EXEMPT_TITLE_RE.search(title):
            continue  # References/Acknowledgment(s)/bibliography sections
        end_match = _SECTION_BODY_END_RE.search(masked, section.end())
        body = masked[section.end() : end_match.start() if end_match else len(masked)]
        line = index.line_of(section.start())
        in_main = section.start() < appendix_start
        if in_main:
            main_sections += 1
            if first_section_line is None:
                first_section_line = line
        words = _prose_word_count(body)
        if words < STUB_SECTION_MIN_WORDS:
            if in_main:
                main_stubs += 1
            findings.append(Finding(
                "L4-HOUSE-09", "major", line, _excerpt(lines, line),
                f"stub section: {title!r} has {words} prose words "
                f"(fewer than {STUB_SECTION_MIN_WORDS}); merge it into a neighboring section "
                "or develop it into several full paragraphs (HARD RULE)"))
    if main_sections >= 2:
        body_match = _BEGIN_DOCUMENT_RE.search(masked)
        body_start = body_match.end() if body_match else 0
        main_words = _prose_word_count(masked[body_start:appendix_start])
        # Sections per 1000 prose words; max(1) guards the all-math degenerate case.
        ratio = main_sections * 1000.0 / max(main_words, 1)
        over_ratio = ratio > FRAGMENTATION_MAX_SECTIONS_PER_1000_WORDS
        if main_stubs >= FRAGMENTATION_MIN_STUB_SECTIONS or over_ratio:
            detail = (
                f"{main_stubs} stub sections"
                if main_stubs >= FRAGMENTATION_MIN_STUB_SECTIONS
                else f"{ratio:.1f} sections per 1000 prose words "
                     f"(max {FRAGMENTATION_MAX_SECTIONS_PER_1000_WORDS})"
            )
            line = first_section_line or 1
            findings.append(Finding(
                "L4-HOUSE-10", "major", line, _excerpt(lines, line),
                f"fragmentation: the main body has {main_sections} sections with {detail}; "
                "merge thin sections into fewer substantial, cohesive sections of developed prose"))
    return findings


def _check_bullet_narration(prose: str, index: _LineIndex, lines: List[str]) -> List[Finding]:
    """L4-HOUSE-11 (minor): itemized narrative and list density.

    A list whose items are developed prose (BULLET_NARRATION_MIN_ITEMS or
    more items of BULLET_NARRATION_MIN_ITEM_WORDS or more words each) is
    narrative masquerading as bullets; genuine short enumerations (case
    labels, short conditions) pass. The density arm flags more than
    LIST_DENSITY_MAX_LISTS_PER_SECTION lists per section (one per two
    sections) as one document-level finding.
    """
    findings: List[Finding] = []
    lists = list(_LIST_ENV_RE.finditer(prose))
    for match in lists:
        # Drop the chunk before the first \item (the list's lead-in, if any).
        items = _ITEM_SPLIT_RE.split(match.group("listbody"))[1:]
        if len(items) < BULLET_NARRATION_MIN_ITEMS:
            continue
        if all(_prose_word_count(item) >= BULLET_NARRATION_MIN_ITEM_WORDS for item in items):
            line = index.line_of(match.start())
            findings.append(Finding(
                "L4-HOUSE-11", "minor", line, _excerpt(lines, line),
                f"bullet narration: {match.group('listenv')} with {len(items)} prose items of "
                f"{BULLET_NARRATION_MIN_ITEM_WORDS}+ words each is narrative masquerading as "
                "bullets; convert to cohesive prose"))
    section_count = sum(1 for _ in _HOUSE07_SECTION_RE.finditer(prose))
    if lists and len(lists) > LIST_DENSITY_MAX_LISTS_PER_SECTION * section_count:
        line = index.line_of(lists[0].start())
        findings.append(Finding(
            "L4-HOUSE-11", "minor", line, _excerpt(lines, line),
            f"list density: {len(lists)} itemize/enumerate lists across {section_count} "
            "sections (max 1 per 2 sections); fold most lists into prose"))
    return findings


# --- individual checks -------------------------------------------------------

def _scan(
    haystack: str,
    index: _LineIndex,
    lines: List[str],
    pattern: re.Pattern[str],
    rule_id: str,
    severity: str,
    message: str,
    *,
    include_match: bool = False,
) -> List[Finding]:
    """Emit one finding per match. ``include_match`` appends the matched token
    to the message so distinct offenders on one line survive deduplication
    (dedupe semantics: at most one finding per (rule_id, line, message))."""
    findings: List[Finding] = []
    for match in pattern.finditer(haystack):
        line = index.line_of(match.start())
        text = f"{message}: {match.group(0)!r}" if include_match else message
        findings.append(Finding(rule_id, severity, line, _excerpt(lines, line), text))
    return findings


def _check_symbol_sentence_start(
    stripped: str, index: _LineIndex, lines: List[str]
) -> List[Finding]:
    """L4-SYM-02: no sentence begins with a math expression or bare symbol."""
    starts = {match.end() for match in _SENTENCE_BOUNDARY_RE.finditer(stripped)}
    starts |= {match.end() for match in _PARAGRAPH_START_RE.finditer(stripped)}
    head = stripped[: len(stripped) - len(stripped.lstrip())]
    starts.add(len(head))  # first non-whitespace character of the document
    findings: List[Finding] = []
    for start in sorted(starts):
        tail = stripped[start:]
        if not tail:
            continue
        flagged = tail.startswith(INLINE_MATH_PLACEHOLDER) or tail.startswith(
            DISPLAY_MATH_PLACEHOLDER
        )
        if not flagged:
            single = _SINGLE_LETTER_START_RE.match(tail)
            # "A"/"a" (article) and "I" (pronoun) are legitimate one-letter
            # sentence openers; every other lone letter reads as a symbol.
            flagged = single is not None and single.group(1) not in {"A", "a", "I"}
        if flagged:
            line = index.line_of(start)
            findings.append(
                Finding(
                    rule_id="L4-SYM-02",
                    severity="minor",
                    line=line,
                    excerpt=_excerpt(lines, line),
                    message="sentence begins with a symbol or formula; prepend the type word",
                )
            )
    return findings


def _check_colon_before_display(
    stripped: str,
    regions: List[_MathRegion],
    index: _LineIndex,
    lines: List[str],
) -> List[Finding]:
    """L4-GRAM-04 (heuristic): a colon introducing display math should follow
    a complete sentence, e.g. one ending in "following"/"as follows"."""
    findings: List[Finding] = []
    for region in regions:
        if region.kind != "display":
            continue
        before = stripped[: region.placeholder_start].rstrip()
        if not before.endswith(":"):
            continue
        lead = before[:-1].rstrip().lower()
        if lead.endswith("following") or lead.endswith("as follows"):
            continue
        colon_offset = len(before) - 1
        line = index.line_of(colon_offset)
        findings.append(
            Finding(
                rule_id="L4-GRAM-04",
                severity="nit",
                line=line,
                excerpt=_excerpt(lines, line),
                message="colon immediately before display math; make the lead-in a complete sentence",
            )
        )
    return findings


def _check_exclamations(
    stripped: str, index: _LineIndex, lines: List[str]
) -> List[Finding]:
    """L4-GRAM-07: no exclamation points in prose (Halmos's "(!)" is spared)."""
    findings: List[Finding] = []
    for match in _EXCLAMATION_RE.finditer(stripped):
        # Skip the parenthetical "(!)" aside, which the rubric permits.
        if stripped[max(match.start() - 1, 0) : match.start() + 2] == "(!)":
            continue
        line = index.line_of(match.start())
        findings.append(
            Finding(
                rule_id="L4-GRAM-07",
                severity="minor",
                line=line,
                excerpt=_excerpt(lines, line),
                message="exclamation point in prose",
            )
        )
    return findings


def _check_cite_bibitem(
    text: str, index: _LineIndex, lines: List[str]
) -> List[Finding]:
    """L5-REF-03: \\cite keys and \\bibitem entries must match one-to-one.
    Runs only when the document carries its own bibliography block."""
    bibitems: List[Tuple[str, int]] = []
    for match in _BIBITEM_RE.finditer(text):
        bibitems.append((match.group(1).strip(), index.line_of(match.start())))
    if not bibitems:
        return []  # external .bib file or no bibliography — nothing checkable
    defined = {key for key, _line in bibitems}
    cited: set[str] = set()
    findings: List[Finding] = []
    for match in _CITE_RE.finditer(text):
        line = index.line_of(match.start())
        for key in (part.strip() for part in match.group(1).split(",")):
            if not key:
                continue
            cited.add(key)
            if key not in defined:
                findings.append(
                    Finding(
                        rule_id="L5-REF-03",
                        severity="minor",
                        line=line,
                        excerpt=_excerpt(lines, line),
                        message=f"citation key {key!r} has no \\bibitem entry",
                    )
                )
    for key, line in bibitems:
        if key not in cited:
            findings.append(
                Finding(
                    rule_id="L5-REF-03",
                    severity="minor",
                    line=line,
                    excerpt=_excerpt(lines, line),
                    message=f"bibliography entry {key!r} is never cited",
                )
            )
    return findings


def _check_any_in_theorems(
    stripped: str, index: _LineIndex, lines: List[str]
) -> List[Finding]:
    """L2-QUANT-02: "any" is ambiguous between "every" and "some" inside
    formal statements (theorem/lemma/proposition environments)."""
    findings: List[Finding] = []
    for env in _THEOREM_ENV_RE.finditer(stripped):
        body_offset = env.start(2)
        for match in _ANY_RE.finditer(env.group(2)):
            line = index.line_of(body_offset + match.start())
            findings.append(
                Finding(
                    rule_id="L2-QUANT-02",
                    severity="minor",
                    line=line,
                    excerpt=_excerpt(lines, line),
                    message=f'"any" inside a {env.group(1)} statement; use "each"/"every" or recast',
                )
            )
    return findings


def _check_display_punctuation(
    stripped: str, regions: List[_MathRegion], lines: List[str]
) -> List[Finding]:
    """L4-SENT-01 (partial heuristic): a display that ends without punctuation
    and is followed by a capitalized new sentence probably dropped its period."""
    findings: List[Finding] = []
    for region in regions:
        if region.kind != "display":
            continue
        content = _DISPLAY_TRAILING_NOISE_RE.sub("", region.inner.strip())
        if not content or content[-1] in ".,;:!?":
            continue
        following = stripped[region.placeholder_start + len(DISPLAY_MATH_PLACEHOLDER) :].lstrip()
        if not following or not following[:1].isupper():
            continue
        findings.append(
            Finding(
                rule_id="L4-SENT-01",
                severity="nit",
                line=region.end_line,
                excerpt=_excerpt(lines, region.end_line),
                message="check display punctuation: display ends unpunctuated but a new sentence follows",
            )
        )
    return findings


# --- shared helpers ----------------------------------------------------------

def _excerpt(lines: List[str], line: int) -> str:
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()[:EXCERPT_MAX_CHARS]
    return ""


def _dedupe_sort(findings: Iterable[Finding]) -> List[Finding]:
    seen: set[Tuple[str, int, str, str]] = set()
    unique: List[Finding] = []
    for finding in findings:
        key = (finding.rule_id, finding.line, finding.message, finding.excerpt)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    unique.sort(key=lambda f: (_SEVERITY_RANK.get(f.severity, 99), f.line, f.rule_id, f.message))
    return unique

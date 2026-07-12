"""Stage 0 rubric compiler for the math-writing harness.

Parses the five layer files in ``math-writing-harness/rubric/`` into a flat list
of :class:`Rule` records. The parsing contract (see the rubric's ``SCHEMA.md``):

- A rule is a top-level markdown bullet of the form
  ``- `<LAYER>-<SOURCE>-<NN>` [checkability] **statement...** trailing prose``.
  Continuation lines are indented; they are joined into one logical bullet.
- ``severity`` is taken from the first ``severity: `X` `` marker in the bullet
  when ``X`` is one of the four severity enums; otherwise the layer default
  applies (see ``_default_severity``). Non-enum markers such as
  ``severity: meta`` or ``severity: routing rule`` fall back to the default.
- ``autofix`` is taken from the first ``autofix: X`` marker (asterisks and
  slash-alternatives like ``safe/assisted`` resolve to the first token);
  otherwise ``none``.
- ``checkability`` is the bracketed tag after the ID. ``[tool]`` is folded into
  ``verify`` (SCHEMA.md treats ``tool`` as a detector within the verify tier),
  and slashed tags like ``[lint/llm]`` resolve to the first token.
- ``owner_critic`` and ``scope`` use documented per-layer defaults unless the
  bullet carries an explicit ``scope:`` marker.

Bullets that look like rules (``- `L...``) but fail to parse are skipped and
reported through :func:`load_rubric_report`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

LAYERS = ("L1", "L2", "L3", "L4", "L5")
SEVERITIES = ("blocker", "major", "minor", "nit")
SCOPES = ("local", "global")
CHECKABILITIES = ("lint", "llm", "verify", "meta")
AUTOFIXES = ("safe", "assisted", "manual", "none")
CRITICS = (
    "pedant",
    "skeptical_editor",
    "referee",
    "confused_reader",
    "provenance_auditor",
)

LAYER_FILES = {
    "L1": "L1-correctness.md",
    "L2": "L2-logic.md",
    "L3": "L3-structure.md",
    "L4": "L4-style.md",
    "L5": "L5-formatting.md",
}

# Per-layer default severities, from each L-file's stated "Default severity"
# header: L1 gates shipping (blocker); L2 defaults to major (stranded-reader
# failures); L3 is major for the "Honesty of framing" section and minor
# elsewhere; L4 and L5 are surface layers (minor).
_LAYER_DEFAULT_SEVERITY = {
    "L1": "blocker",
    "L2": "major",
    "L3": "minor",  # overridden to "major" inside the Honesty section
    "L4": "minor",
    "L5": "minor",
}

# Matches a rule bullet head: "- `L4-SYM-01` [lint] rest-of-bullet".
_BULLET_HEAD_RE = re.compile(
    r"^- `(?P<rule_id>(?P<layer>L[1-5])-(?P<source>[A-Z0-9]+(?:-[A-Z0-9]+)*)-\d+)`"
    r"\s*\[(?P<check>[a-z/]+)\]\s*(?P<rest>.*)$"
)
# Any top-level bullet whose first token looks like a backticked rule ID —
# used to detect rule-shaped bullets that failed the strict head parse.
_BULLET_CANDIDATE_RE = re.compile(r"^- `L[1-5]-")
# First bold span in the joined bullet: the rule statement per SCHEMA.md.
_STATEMENT_RE = re.compile(r"\*\*(?P<statement>.+?)\*\*", re.DOTALL)
# "severity: `major`" (backticks optional); only enum values count.
_SEVERITY_RE = re.compile(r"severity:\s*`?(blocker|major|minor|nit)`?")
# "autofix: safe", "autofix: **safe**", "autofix: safe/assisted" → first token.
_AUTOFIX_RE = re.compile(r"autofix:\s*\**\s*(safe|assisted|manual)")
# Explicit scope marker (rare): "scope: `global`".
_SCOPE_RE = re.compile(r"scope:\s*`?(local|global)`?")
# Markdown section heading, tracked so L3 severity defaults can key off the
# "Honesty of framing" section.
_SECTION_RE = re.compile(r"^#{2,3}\s+(?P<title>.+?)\s*$")


@dataclass(frozen=True)
class Rule:
    rule_id: str
    layer: str
    source: str
    statement: str
    severity: str
    scope: str
    checkability: str
    owner_critic: str
    autofix: str


def load_rubric(rubric_dir: Path) -> List[Rule]:
    """Parse the five rubric layer files; returns the rules only."""
    rules, _warnings = load_rubric_report(rubric_dir)
    return rules


def load_rubric_report(rubric_dir: Path) -> Tuple[List[Rule], List[str]]:
    """Parse the rubric and return ``(rules, warnings)``.

    Warnings describe rule-shaped bullets that could not be parsed (they are
    skipped, never fatal) and missing layer files.
    """
    rubric_dir = Path(rubric_dir)
    rules: List[Rule] = []
    warnings: List[str] = []
    seen_ids: set[str] = set()
    for layer, filename in LAYER_FILES.items():
        path = rubric_dir / filename
        if not path.is_file():
            warnings.append(f"{filename}: missing rubric file")
            continue
        text = path.read_text(encoding="utf-8")
        for bullet, section in _iter_bullets(text):
            if not _BULLET_CANDIDATE_RE.match(bullet):
                continue
            rule, warning = _parse_bullet(bullet, layer=layer, section=section)
            if rule is None:
                warnings.append(f"{filename}: {warning}")
                continue
            if rule.rule_id in seen_ids:
                warnings.append(f"{filename}: duplicate rule id {rule.rule_id}")
                continue
            seen_ids.add(rule.rule_id)
            rules.append(rule)
    return rules, warnings


def rules_for_critic(rules: List[Rule], critic: str) -> List[Rule]:
    return [rule for rule in rules if rule.owner_critic == critic]


def lint_rules(rules: List[Rule]) -> List[Rule]:
    return [rule for rule in rules if rule.checkability == "lint"]


def _iter_bullets(text: str) -> List[Tuple[str, str]]:
    """Yield ``(joined_bullet, section_title)`` for every top-level bullet.

    A bullet starts with "- " at column 0; indented following lines are
    continuations and are joined with single spaces. Fenced code blocks are
    skipped so example config blocks cannot masquerade as bullets.
    """
    bullets: List[Tuple[str, str]] = []
    section = ""
    current: List[str] = []
    in_code_fence = False

    def flush() -> None:
        if current:
            bullets.append((" ".join(part.strip() for part in current), section))
            current.clear()

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            flush()
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        heading = _SECTION_RE.match(line)
        if heading is not None:
            flush()
            section = heading.group("title")
            continue
        if line.startswith("- "):
            flush()
            current.append(line)
        elif current and line.startswith(" ") and line.strip():
            current.append(line)
        else:
            flush()
    flush()
    return bullets


def _parse_bullet(bullet: str, *, layer: str, section: str) -> Tuple[Rule | None, str]:
    head = _BULLET_HEAD_RE.match(bullet)
    if head is None:
        return None, f"unparseable rule bullet: {bullet[:80]!r}"
    rule_id = head.group("rule_id")
    if head.group("layer") != layer:
        return None, f"{rule_id}: layer tag does not match its file ({layer})"
    checkability = _normalize_checkability(head.group("check"))
    if checkability is None:
        return None, f"{rule_id}: unknown checkability tag [{head.group('check')}]"
    statement_match = _STATEMENT_RE.search(bullet)
    if statement_match is None:
        return None, f"{rule_id}: no bold **statement** found"
    statement = " ".join(statement_match.group("statement").split())
    severity_match = _SEVERITY_RE.search(bullet)
    if severity_match is not None:
        severity = severity_match.group(1)
    else:
        severity = _default_severity(layer, section)
    autofix_match = _AUTOFIX_RE.search(bullet)
    autofix = autofix_match.group(1) if autofix_match is not None else "none"
    scope_match = _SCOPE_RE.search(bullet)
    source = head.group("source")
    if scope_match is not None:
        scope = scope_match.group(1)
    else:
        scope = _default_scope(layer, source)
    rule = Rule(
        rule_id=rule_id,
        layer=layer,
        source=source,
        statement=statement,
        severity=severity,
        scope=scope,
        checkability=checkability,
        owner_critic=_default_owner_critic(layer, source),
        autofix=autofix,
    )
    return rule, ""


def _normalize_checkability(tag: str) -> str | None:
    # Slashed tags ("lint/llm") resolve to the first token; the "tool"
    # detector tag folds into the verify tier per SCHEMA.md.
    first = tag.split("/", 1)[0]
    if first == "tool":
        first = "verify"
    return first if first in CHECKABILITIES else None


def _default_severity(layer: str, section: str) -> str:
    # L3's stated default is major for the "Honesty of framing" section
    # (overselling), minor elsewhere.
    if layer == "L3" and "honesty" in section.lower():
        return "major"
    return _LAYER_DEFAULT_SEVERITY[layer]


def _default_scope(layer: str, source: str) -> str:
    # L3 rules critique document-level structure/narrative, and L1's GLOBAL
    # screens are whole-document probes; everything else defaults to local.
    if layer == "L3" or source == "GLOBAL":
        return "global"
    return "local"


def _default_owner_critic(layer: str, source: str) -> str:
    # Layer defaults per the rubric's "Owner critics" headers: L1 splits
    # between the Referee (proof correctness) and the Provenance Auditor
    # (faithfulness/citations, i.e. the FAITH and CITE source keys); L5's
    # AI-governance and venue meta rules also belong to the Provenance
    # Auditor rather than the Pedant.
    if layer == "L1":
        return "provenance_auditor" if source in {"FAITH", "CITE"} else "referee"
    if layer == "L2":
        return "confused_reader"
    if layer == "L3":
        return "skeptical_editor"
    if layer == "L5" and source in {"AI", "VENUE"}:
        return "provenance_auditor"
    return "pedant"

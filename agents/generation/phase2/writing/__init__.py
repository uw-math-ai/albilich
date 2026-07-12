"""Stage 0 of the math-writing harness: rubric compiler + deterministic linter."""

from __future__ import annotations

from .linter import (
    DISPLAY_MATH_PLACEHOLDER,
    EXCERPT_MAX_CHARS,
    INLINE_MATH_PLACEHOLDER,
    Finding,
    run_all,
    run_lint,
    run_residue_scan,
    run_slop_lint,
)
from .rubric import (
    AUTOFIXES,
    CHECKABILITIES,
    CRITICS,
    LAYERS,
    SCOPES,
    SEVERITIES,
    Rule,
    lint_rules,
    load_rubric,
    load_rubric_report,
    rules_for_critic,
)

__all__ = [
    "AUTOFIXES",
    "CHECKABILITIES",
    "CRITICS",
    "DISPLAY_MATH_PLACEHOLDER",
    "EXCERPT_MAX_CHARS",
    "Finding",
    "INLINE_MATH_PLACEHOLDER",
    "LAYERS",
    "Rule",
    "SCOPES",
    "SEVERITIES",
    "lint_rules",
    "load_rubric",
    "load_rubric_report",
    "rules_for_critic",
    "run_all",
    "run_lint",
    "run_residue_scan",
    "run_slop_lint",
]

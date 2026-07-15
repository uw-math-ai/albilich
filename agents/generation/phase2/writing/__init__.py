"""Stage 0 of the math-writing harness: rubric compiler + deterministic linter."""

from __future__ import annotations

from .linter import (
    DISPLAY_MATH_PLACEHOLDER,
    EXCERPT_MAX_CHARS,
    INLINE_MATH_PLACEHOLDER,
    REQUIRED_FIX_MARKER,
    Finding,
    obligation_location,
    required_fix,
    required_fix_for_obligation,
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
    "REQUIRED_FIX_MARKER",
    "Rule",
    "SCOPES",
    "SEVERITIES",
    "lint_rules",
    "load_rubric",
    "load_rubric_report",
    "obligation_location",
    "required_fix",
    "required_fix_for_obligation",
    "rules_for_critic",
    "run_all",
    "run_lint",
    "run_residue_scan",
    "run_slop_lint",
]

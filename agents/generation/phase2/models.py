from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .action_contract import RUN_MODES

# Patch/context protocol version. Database migrations are deliberately tracked
# separately: changing this value invalidates every persisted patch contract.
SCHEMA_VERSION = 3
STORE_MIGRATION_VERSION = 21

CLAIM_KINDS = {"theorem", "lemma", "definition", "hypothesis", "obstruction", "counterexample", "reference"}
VALIDATION_STATUSES = {
    "untested",
    "plausible",
    "challenged",
    "informally_verified",
    "formally_verified",
    "refuted",
}
LIFECYCLE_STATUSES = {"active", "blocked", "abandoned", "integrated", "superseded"}
ROUTE_RELATIONS = {"sufficient", "necessary", "diagnostic", "variant"}
ROUTE_STATUSES = {"active", "blocked", "abandoned", "integrated", "superseded"}
INFERENCE_STATUSES = VALIDATION_STATUSES
DEBT_SEVERITIES = {"blocking", "major", "minor", "discarded"}
DEBT_STATUSES = {"active", "resolved", "refuted", "discarded"}
# Persisted whole-run control states (problem_state.run_status).
# dashboard_paused is reserved for a display-only dashboard freeze and never
# blocks the workflow; pause_requested/stopping are transient request states.
RUN_STATUSES = {
    "running",
    "dashboard_paused",
    "pause_requested",
    "paused",
    "stopping",
    "stopped",
    "awaiting_human",
    "completed",
}
# Run-level completion policy (problem_state.completion_policy, 2026-07-09
# Completion-policy design. full_proof_first is the default for theorem-solving problem files;
# publication_ready explicitly opts into post-proof paper authoring/review, and
# only partial_ok/exploratory select a partial deliverable.
COMPLETION_POLICIES = {"full_proof_first", "publication_ready", "partial_ok", "exploratory"}
DEFAULT_COMPLETION_POLICY = "full_proof_first"
VERIFYING_ROLES = {"strict_informal_verifier", "formal_backend", "counterexample_validator", "integration_verifier"}
NON_VERIFYING_ROLES = {
    "researcher",
    "adversarial_reviewer",
    "villain",
    "literature_researcher",
    "scheduler",
    "phd_advisor",
    "advisor",
    "writer",
    "referee",
    "writing_critic",
}

JSONDict = Dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else [], sort_keys=True, ensure_ascii=False)


def json_loads(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return [] if default is None else default
    # Scheduler-state helpers are intentionally usable with both raw SQLite
    # rows and already-decoded test/API dictionaries.  Treat decoded JSON as
    # decoded instead of passing it back through ``json.loads`` (which raises a
    # TypeError rather than JSONDecodeError for lists and mappings).
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    if not isinstance(value, (str, bytes, bytearray)):
        return [] if default is None else default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return [] if default is None else default


def normalize_text(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return " ".join(normalized.split())


def statement_is_interrogative_problem(text: str) -> bool:
    """Return whether a root statement asks for an answer rather than asserts one."""
    plain = re.sub(r"[#*_`]+", " ", str(text or ""))
    if "?" in plain:
        return True
    return bool(
        re.search(
            r"(?im)^\s*(?:\d+[.)]\s*)?(?:does|do|is|are|can|find|determine|decide|classify|what|which|whether)\b",
            plain,
        )
    )


def canonical_math_text(text: str) -> str:
    """Canonicalize storage text without erasing mathematical syntax.

    This intentionally preserves case, negation, order relations, operators,
    quantifiers, punctuation, and the entire statement.  It is suitable for an
    exact identity hash, not semantic-similarity search.
    """

    normalized = unicodedata.normalize("NFKC", str(text or "")).replace("\r\n", "\n").replace("\r", "\n")
    return " ".join(normalized.split())


def fingerprint_text(text: str, *, length: int = 64) -> str:
    canonical = canonical_math_text(text)
    if not canonical:
        return ""
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    bounded_length = max(1, min(64, int(length)))
    return digest[:bounded_length]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sanitize_problem_id(raw: str) -> str:
    normalized = raw.strip().replace("\\", "/")
    parts: List[str] = []
    for part in normalized.split("/"):
        stripped = part.strip()
        if stripped in {"", "."}:
            continue
        if stripped == "..":
            raise ValueError("problem_id must not contain '..'")
        cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", stripped)
        cleaned = re.sub(r"_+", "_", cleaned).strip("._")
        if cleaned:
            parts.append(cleaned)
    return "/".join(parts) or "problem"


def problem_id_from_file(problem_file: str) -> str:
    if not problem_file.startswith("data/") or not problem_file.endswith(".md"):
        raise ValueError("problem file must be a markdown path under data/")
    return sanitize_problem_id(problem_file[len("data/") : -len(".md")])


def ensure_allowed(value: str, allowed: Iterable[str], field: str) -> None:
    if value not in set(allowed):
        raise ValueError(f"invalid {field}: {value}")


@dataclass(frozen=True)
class PatchOutcome:
    accepted: bool
    revision: int
    patch_id: str
    errors: List[str]

    def to_dict(self) -> JSONDict:
        return {
            "accepted": self.accepted,
            "revision": self.revision,
            "patch_id": self.patch_id,
            "errors": self.errors,
        }


def compact_dict(row: Mapping[str, Any]) -> JSONDict:
    return {k: v for k, v in dict(row).items() if v is not None}

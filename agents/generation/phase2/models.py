from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

SCHEMA_VERSION = 1

CLAIM_KINDS = {"theorem", "lemma", "definition", "obstruction", "counterexample", "reference"}
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
DEBT_STATUSES = {"active", "resolved", "discarded"}
RUN_MODES = {
    "prove",
    "refute",
    "validate_counterexample",
    "reduce",
    "weaken",
    "strengthen",
    "retrieve",
    "synthesize_sources",
    "audit_definitions",
    "triage_routes",
    "integrate",
    "formalize",
    "write",
    "stop_with_partial_results",
    "stop_solved",
}

VERIFYING_ROLES = {"strict_informal_verifier", "formal_backend", "counterexample_validator", "integration_verifier"}
NON_VERIFYING_ROLES = {
    "researcher",
    "villain",
    "literature_researcher",
    "scheduler",
    "phd_advisor",
    "advisor",
    "writer",
}

JSONDict = Dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else [], sort_keys=True, ensure_ascii=False)


def json_loads(value: Optional[str], default: Any = None) -> Any:
    if value in (None, ""):
        return [] if default is None else default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return [] if default is None else default


def normalize_text(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return " ".join(normalized.split())


def fingerprint_text(text: str, *, length: int = 16) -> str:
    normalized = normalize_text(text)
    if len(normalized) > 500:
        normalized = normalized[:500]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:length] if normalized else ""


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

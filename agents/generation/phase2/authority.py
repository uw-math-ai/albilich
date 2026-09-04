from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Dict, Mapping

from .audit_chain import GENESIS_HASH


AUTHORITY_SOURCES = {"session", "system", "operator", "migration"}


@dataclass(frozen=True)
class PatchAuthority:
    """Host-issued authority for one proof-state mutation.

    Child patches are untrusted data.  In particular, ``actor_role`` in their
    JSON is an assertion to compare with this object, never the source of
    authorization.  The orchestrator creates session authorities; deterministic
    host code creates system authorities; the CLI creates operator authorities
    only after an explicit local invocation.
    """

    source: str
    actor_role: str
    mode: str = ""
    target_id: str = ""
    route_id: str = ""
    context_revision: int = 0
    context_hash: str = ""
    session_id: str = ""
    run_id: str = ""
    researcher_work_mode: str = ""
    web_search: str = ""
    cas_enabled: bool = False
    policy_event_head: str = GENESIS_HASH
    context_request_ids: tuple[str, ...] = ()
    reviewer_identity: str = ""
    reviewer_independence_class: str = ""
    reviewer_backend: str = ""
    reviewer_backend_version: str = ""
    backend_contract_hash: str = ""
    reviewer_model: str = ""
    authorized_existing_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.source not in AUTHORITY_SOURCES:
            raise ValueError(f"invalid patch authority source: {self.source}")
        if not self.actor_role:
            raise ValueError("patch authority actor_role must be non-empty")
        if self.context_revision < 0:
            raise ValueError("patch authority context_revision must be nonnegative")

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "actor_role": self.actor_role,
            "mode": self.mode,
            "target_id": self.target_id,
            "route_id": self.route_id,
            "context_revision": self.context_revision,
            "context_hash": self.context_hash,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "researcher_work_mode": self.researcher_work_mode,
            "web_search": self.web_search,
            "cas_enabled": self.cas_enabled,
            "policy_event_head": self.policy_event_head,
            "context_request_ids": list(self.context_request_ids),
            "reviewer_identity": self.reviewer_identity,
            "reviewer_independence_class": self.reviewer_independence_class,
            "reviewer_backend": self.reviewer_backend,
            "reviewer_backend_version": self.reviewer_backend_version,
            "backend_contract_hash": self.backend_contract_hash,
            "reviewer_model": self.reviewer_model,
            "authorized_existing_ids": list(self.authorized_existing_ids),
        }


def operator_authority(patch: Mapping[str, Any]) -> PatchAuthority:
    """Create authority for an explicitly operator-submitted local patch."""

    return PatchAuthority(
        source="operator",
        actor_role=str(patch.get("actor_role") or ""),
        target_id=str(patch.get("target_id") or ""),
        context_revision=max(0, int(patch.get("base_revision") or 0)),
        reviewer_identity="local-human-operator",
        reviewer_independence_class="human:operator",
        reviewer_backend="human",
        reviewer_model="human-operator",
    )


def system_authority(
    *,
    actor_role: str = "scheduler",
    mode: str = "",
    target_id: str = "root",
    route_id: str = "",
    context_revision: int = 0,
) -> PatchAuthority:
    return PatchAuthority(
        source="system",
        actor_role=actor_role,
        mode=mode,
        target_id=target_id,
        route_id=route_id,
        context_revision=max(0, int(context_revision)),
    )


def session_authority(
    action: Mapping[str, Any],
    session_plan: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> PatchAuthority:
    backend = str(execution.get("backend") or "codex")
    model = str(execution.get("model") or session_plan.get("model") or "unknown")
    attestation = execution.get("backend_attestation")
    attestation = dict(attestation) if isinstance(attestation, Mapping) else {}
    reviewer_class = reviewer_independence_class(backend, model)
    return PatchAuthority(
        source="session",
        actor_role=str(session_plan.get("actor_role") or ""),
        mode=str(session_plan.get("mode") or action.get("mode") or ""),
        target_id=str(session_plan.get("target_id") or action.get("target_id") or ""),
        route_id=str(session_plan.get("route_id") or action.get("route_id") or ""),
        context_revision=max(0, int(session_plan.get("state_revision") or 0)),
        context_hash=str(session_plan.get("context_hash") or ""),
        session_id=str(execution.get("session_id") or ""),
        run_id=str(execution.get("run_id") or ""),
        researcher_work_mode=str(session_plan.get("researcher_work_mode") or ""),
        web_search=str(session_plan.get("web_search") or execution.get("web_search") or ""),
        cas_enabled=bool(session_plan.get("cas_enabled", False)),
        policy_event_head=str(
            session_plan.get("policy_event_head") or GENESIS_HASH
        ),
        context_request_ids=tuple(
            sorted(
                {
                    str(item)
                    for item in session_plan.get("context_request_ids", []) or []
                    if str(item)
                }
            )
        ),
        reviewer_identity=f"{backend}:{model}",
        reviewer_independence_class=reviewer_class,
        reviewer_backend=backend,
        reviewer_backend_version=str(attestation.get("version") or ""),
        backend_contract_hash=str(attestation.get("attestation_sha256") or ""),
        reviewer_model=model,
        authorized_existing_ids=tuple(
            sorted(
                {
                    str(item)
                    for item in session_plan.get("authorized_existing_entity_ids", []) or []
                    if str(item)
                }
            )
        ),
    )


def reviewer_independence_class(backend: str, model: str) -> str:
    """Return a conservative provider/model-family independence class.

    GPT or Codex major-version changes do not count as independent reviews.
    The same rule already applies to Claude and Gemini variants.
    """

    backend_key = re.sub(r"[^a-z0-9]+", "-", backend.lower()).strip("-")
    model_key = model.lower().strip()
    if "claude" in model_key or backend_key == "claude":
        return "anthropic:claude"
    if "gemini" in model_key or backend_key == "gemini":
        return "google:gemini"
    gpt = re.search(r"(?:gpt|codex)(?:[-_ ]?\d+)?", model_key)
    if gpt or backend_key in {"codex", "openai"}:
        return "openai:gpt"
    family = re.split(r"[-_: ]+", model_key, maxsplit=1)[0] or "unknown"
    return f"{backend_key or 'unknown'}:{family}"


def _authority_contract_from_schema() -> tuple[
    dict[str, str], set[str], set[str], set[str]
]:
    """Load the identifier-scope registry from the public patch schema."""

    path = Path(__file__).with_name("schemas") / "phase2_patch.schema.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        contract = document["x-albilich-authority-contract"]
        created = {
            str(key): str(value)
            for key, value in contract["created_id_field_by_operation"].items()
        }
        references = {str(item) for item in contract["entity_reference_fields"]}
        reference_lists = {
            str(item) for item in contract["entity_reference_list_fields"]
        }
        opaque = {str(item) for item in contract["opaque_identifier_fields"]}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(f"invalid authority contract in {path}: {exc}") from exc
    if not created or not references:
        raise RuntimeError(f"authority contract in {path} must not be empty")
    return created, references, reference_lists, opaque


(
    _CREATED_ID_FIELD_BY_OPERATION,
    _ENTITY_REFERENCE_FIELDS,
    _ENTITY_REFERENCE_LIST_FIELDS,
    _OPAQUE_IDENTIFIER_FIELDS,
) = _authority_contract_from_schema()


def _operation_scope_errors(
    patch: Mapping[str, Any], authority: PatchAuthority
) -> list[str]:
    """Reject references to records absent from the host-disclosed packet.

    Same-patch identifiers are legal.  Session scope is enforced even when the
    explicit disclosure tuple is empty: the scheduled target and proof
    approach remain the only pre-existing identifiers then in scope.  Operator
    and deterministic system patches use their separate authority domains.
    """

    if authority.source != "session":
        return []
    operations = patch.get("operations")
    if not isinstance(operations, list):
        return []
    allowed = set(authority.authorized_existing_ids)
    allowed.update({authority.target_id, authority.route_id})
    allowed.discard("")
    created: set[str] = set()
    for operation in operations:
        if not isinstance(operation, Mapping):
            continue
        field = _CREATED_ID_FIELD_BY_OPERATION.get(str(operation.get("op") or ""))
        if field and operation.get(field):
            created.add(str(operation[field]))

    errors: list[str] = []
    def check_mapping(
        value: Mapping[str, Any],
        *,
        index: int,
        location: str,
        created_field: str | None = None,
    ) -> None:
        for field in _ENTITY_REFERENCE_FIELDS:
            if field == created_field:
                continue
            reference = str(value.get(field) or "")
            if reference and reference not in allowed and reference not in created:
                errors.append(
                    f"operation {index} references out-of-scope {location}{field} {reference!r}"
                )
        for field in _ENTITY_REFERENCE_LIST_FIELDS:
            references = value.get(field)
            if not isinstance(references, list):
                continue
            for raw_reference in references:
                reference = str(raw_reference or "")
                if reference and reference not in allowed and reference not in created:
                    errors.append(
                        f"operation {index} references out-of-scope {location}{field} value {reference!r}"
                    )
        for field, child in value.items():
            if isinstance(child, Mapping):
                check_mapping(
                    child,
                    index=index,
                    location=f"{location}{field}.",
                )
            elif isinstance(child, list):
                for child_index, item in enumerate(child):
                    if isinstance(item, Mapping):
                        check_mapping(
                            item,
                            index=index,
                            location=f"{location}{field}[{child_index}].",
                        )

    for index, operation in enumerate(operations):
        if not isinstance(operation, Mapping):
            continue
        operation_name = str(operation.get("op") or "")
        created_field = _CREATED_ID_FIELD_BY_OPERATION.get(operation_name)
        classified_identifier_fields = (
            _ENTITY_REFERENCE_FIELDS
            | _ENTITY_REFERENCE_LIST_FIELDS
            | _OPAQUE_IDENTIFIER_FIELDS
            | ({created_field} if created_field else set())
        )
        for raw_field in operation:
            field = str(raw_field)
            if (
                (field.endswith("_id") or field.endswith("_ids"))
                and field not in classified_identifier_fields
            ):
                errors.append(
                    f"operation {index} has unclassified identifier field {field!r}; "
                    "classify it in the patch schema authority contract"
                )
        check_mapping(
            operation,
            index=index,
            location="",
            created_field=created_field,
        )
    return errors


def authority_contract_errors(
    patch: Mapping[str, Any],
    authority: PatchAuthority,
    *,
    original_base_revision: int | None = None,
) -> list[str]:
    """Compare untrusted patch assertions with host-issued authority."""

    errors: list[str] = []
    actor = str(patch.get("actor_role") or "")
    if actor != authority.actor_role:
        errors.append(
            f"authority mismatch: patch actor_role {actor!r} != scheduled role {authority.actor_role!r}"
        )
    target = str(patch.get("target_id") or "")
    if authority.target_id and target != authority.target_id:
        errors.append(
            f"authority mismatch: patch target_id {target!r} != scheduled target {authority.target_id!r}"
        )
    if authority.source == "session":
        current_base = int(patch.get("base_revision") or 0) if str(patch.get("base_revision", "")).lstrip("-").isdigit() else -1
        asserted_base = current_base if original_base_revision is None else int(original_base_revision)
        if asserted_base != authority.context_revision:
            errors.append(
                f"authority mismatch: patch base_revision {asserted_base} != session context revision {authority.context_revision}"
            )
        if not authority.context_hash:
            errors.append("session authority is missing the host context hash")
        errors.extend(_operation_scope_errors(patch, authority))
    return errors

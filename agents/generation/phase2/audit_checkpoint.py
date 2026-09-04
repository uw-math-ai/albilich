from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .audit_chain import GENESIS_HASH, POLICY_EVENT_TYPES
from .bounded_io import read_bounded_text
from .invariants import validate_conn
from .models import SCHEMA_VERSION, json_loads, utc_now
from .replay import verify_event_journal, verify_patch_journal
from .store import ProofStateStore


CHECKPOINT_VERSION = 2
SIGNATURE_ALGORITHM = "ed25519"
MAX_CHECKPOINT_BYTES = 4 * 1024 * 1024


def _canonical_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(payload),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _openssl() -> str:
    executable = shutil.which("openssl")
    if not executable:
        raise RuntimeError("OpenSSL is required for Ed25519 audit checkpoints")
    return executable


def _run_openssl(args: list[str], *, input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        [_openssl(), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")[-1200:].strip()
        raise ValueError(f"OpenSSL checkpoint operation failed: {detail}")
    return bytes(completed.stdout)


def _public_key_der_from_private(private_key: Path) -> bytes:
    return _run_openssl(
        ["pkey", "-in", str(private_key), "-pubout", "-outform", "DER"]
    )


def _public_key_der(public_key: Path) -> bytes:
    return _run_openssl(
        ["pkey", "-pubin", "-in", str(public_key), "-pubout", "-outform", "DER"]
    )


def _sign_ed25519(payload: bytes, private_key: Path) -> bytes:
    with tempfile.NamedTemporaryFile(prefix="albilich-audit-payload-") as handle:
        handle.write(payload)
        handle.flush()
        return _run_openssl(
            [
                "pkeyutl",
                "-sign",
                "-rawin",
                "-inkey",
                str(private_key),
                "-in",
                handle.name,
            ]
        )


def _verify_ed25519(payload: bytes, signature: bytes, public_key: Path) -> bool:
    with tempfile.NamedTemporaryFile(
        prefix="albilich-audit-payload-"
    ) as payload_handle, tempfile.NamedTemporaryFile(
        prefix="albilich-audit-signature-"
    ) as signature_handle:
        payload_handle.write(payload)
        payload_handle.flush()
        signature_handle.write(signature)
        signature_handle.flush()
        completed = subprocess.run(
            [
                _openssl(),
                "pkeyutl",
                "-verify",
                "-rawin",
                "-pubin",
                "-inkey",
                str(public_key),
                "-in",
                payload_handle.name,
                "-sigfile",
                signature_handle.name,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    return completed.returncode == 0


# Public cryptographic helpers shared by signed retention bundles. Keeping the
# canonical encoding and key fingerprint implementation in one module prevents
# two subtly different signature formats from evolving.
canonical_signature_payload = _canonical_payload_bytes
public_key_der = _public_key_der
public_key_der_from_private = _public_key_der_from_private
run_openssl = _run_openssl
sign_ed25519 = _sign_ed25519
verify_ed25519 = _verify_ed25519


def _require_external_path(store: ProofStateStore, path: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == store.state_dir.resolve() or resolved.is_relative_to(
        store.state_dir.resolve()
    ):
        raise ValueError(
            f"{label} must be outside the mutable Albilich proof-state directory"
        )
    return resolved


def require_private_signing_key(
    store: ProofStateStore, path: Path, *, label: str = "private signing key"
) -> Path:
    """Resolve a private key outside proof state and reject unsafe permissions."""

    if path.is_symlink():
        raise ValueError(f"{label} must not be a symbolic link")
    resolved = _require_external_path(store, path, label=label)
    try:
        info = resolved.stat()
    except OSError as exc:
        raise ValueError(f"{label} does not exist: {resolved}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"{label} must be a regular file: {resolved}")
    if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError(
            f"{label} must not grant group or other permissions: {resolved}"
        )
    return resolved


def create_signed_audit_checkpoint(
    store: ProofStateStore,
    *,
    output_path: Path,
    private_key_path: Path,
) -> dict[str, Any]:
    """Write an externally stored Ed25519 checkpoint for a clean audit state."""

    expanded_output = output_path.expanduser()
    if expanded_output.is_symlink():
        raise ValueError("checkpoint output must not be a symbolic link")
    output = _require_external_path(store, output_path, label="checkpoint output")
    if output.exists() and not output.is_file():
        raise ValueError("checkpoint output must be a regular file or a new path")
    private_key = require_private_signing_key(
        store, private_key_path, label="checkpoint private key"
    )

    with store.connect() as conn:
        # Checkpoint fields must describe one database snapshot.  The writer
        # lock prevents a proof patch or event-only append from landing between
        # the patch replay, event replay, invariant check, and state metadata
        # reads.  The lock is released before the comparatively slow signature
        # operation; subsequent appends then make this checkpoint a valid
        # prefix rather than changing what was signed.
        conn.execute("BEGIN IMMEDIATE")
        patch_replay = verify_patch_journal(store, conn=conn)
        event_replay = verify_event_journal(store, conn=conn)
        invariant_errors = validate_conn(conn)
        state = conn.execute(
            "SELECT schema_version, current_revision FROM problem_state "
            "WHERE problem_id = ?",
            (store.problem_id,),
        ).fetchone()
        migration_versions = [
            int(row["version"])
            for row in conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
    errors = [
        *invariant_errors,
        *[f"patch journal: {item}" for item in patch_replay["errors"]],
        *[f"event journal: {item}" for item in event_replay["errors"]],
    ]
    if errors:
        raise ValueError(
            "refusing to sign an invalid audit state: " + "; ".join(errors[:8])
        )
    if state is None:
        raise ValueError("problem state is not initialized")

    payload = {
        "checkpoint_version": CHECKPOINT_VERSION,
        "problem_id": store.problem_id,
        "schema_version": int(state["schema_version"] or 0),
        "created_at": utc_now(),
        "proof_revision": int(state["current_revision"] or 0),
        "patch_count": int(patch_replay["patch_count"]),
        "patch_journal_head": str(patch_replay["journal_entry_head"]),
        "proof_state_hash": str(patch_replay["current_state_hash"]),
        "run_provenance_hash": str(
            patch_replay["current_run_provenance_hash"]
        ),
        "journal_start_revision": int(
            patch_replay.get("journal_start_revision") or 0
        ),
        "journal_start_state_hash": str(
            patch_replay.get("journal_start_state_hash") or ""
        ),
        "journal_start_entry_hash": str(
            patch_replay.get("journal_start_entry_hash") or GENESIS_HASH
        ),
        "legacy_patch_count": int(
            patch_replay.get("legacy_patch_count") or 0
        ),
        "migration_backup_sha256": str(
            patch_replay.get("migration_backup_sha256") or ""
        ),
        "event_count": int(event_replay["event_count"]),
        "event_chain_head": str(event_replay["event_chain_head"]),
        "policy_event_head": str(event_replay["policy_event_head"]),
        "schema_migrations": migration_versions,
        "prior_history_status": str(
            patch_replay.get("prior_history_status")
            or "replay_verified_from_genesis"
        ),
    }
    payload_bytes = _canonical_payload_bytes(payload)
    public_der = _public_key_der_from_private(private_key)
    signature = _sign_ed25519(payload_bytes, private_key)
    document = {
        "payload": payload,
        "signature": {
            "algorithm": SIGNATURE_ALGORITHM,
            "key_id_sha256": hashlib.sha256(public_der).hexdigest(),
            "value_base64": base64.b64encode(signature).decode("ascii"),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=str(output.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return {
        "valid": True,
        "path": str(output),
        "payload": payload,
        "key_id_sha256": document["signature"]["key_id_sha256"],
    }


def _safe_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return -1
    return value if value >= 0 else -1


def _is_sha256(value: Any, *, allow_empty: bool = False) -> bool:
    text = str(value or "").lower()
    if allow_empty and not text:
        return True
    return len(text) == 64 and all(
        character in "0123456789abcdef" for character in text
    )


def _checkpoint_payload_errors(
    payload: Mapping[str, Any], *, problem_id: str
) -> list[str]:
    errors: list[str] = []
    if _safe_nonnegative_int(payload.get("checkpoint_version")) != CHECKPOINT_VERSION:
        errors.append("unsupported checkpoint version")
    if str(payload.get("problem_id") or "") != problem_id:
        errors.append("checkpoint problem_id does not match this proof state")
    for field in (
        "schema_version",
        "proof_revision",
        "patch_count",
        "journal_start_revision",
        "legacy_patch_count",
        "event_count",
    ):
        if _safe_nonnegative_int(payload.get(field)) < 0:
            errors.append(f"checkpoint {field} must be a nonnegative integer")
    if _safe_nonnegative_int(payload.get("schema_version")) < 1:
        errors.append("checkpoint schema_version must be positive")
    if _safe_nonnegative_int(payload.get("journal_start_revision")) > _safe_nonnegative_int(
        payload.get("proof_revision")
    ):
        errors.append("checkpoint journal start revision exceeds its proof revision")
    for field in (
        "patch_journal_head",
        "proof_state_hash",
        "journal_start_state_hash",
        "journal_start_entry_hash",
        "event_chain_head",
        "policy_event_head",
    ):
        if not _is_sha256(payload.get(field)):
            errors.append(f"checkpoint {field} must be a SHA-256 digest")
    if "run_provenance_hash" in payload and not _is_sha256(
        payload.get("run_provenance_hash")
    ):
        errors.append("checkpoint run_provenance_hash must be a SHA-256 digest")
    if not _is_sha256(payload.get("migration_backup_sha256"), allow_empty=True):
        errors.append("checkpoint migration_backup_sha256 must be empty or a SHA-256 digest")
    migrations = payload.get("schema_migrations")
    if (
        not isinstance(migrations, list)
        or any(_safe_nonnegative_int(item) < 1 for item in migrations)
        or [int(item) for item in migrations] != sorted({int(item) for item in migrations})
    ):
        errors.append("checkpoint schema_migrations must be sorted unique positive integers")
    if not str(payload.get("created_at") or "").strip():
        errors.append("checkpoint created_at must be nonempty")
    if str(payload.get("prior_history_status") or "") not in {
        "replay_verified_from_genesis",
        "legacy_pre_v3_nonreplayable_before_signed_migration_baseline",
        # Compatibility with checkpoints produced during the short-lived
        # pre-release spelling of the same conservative status.
        "legacy_history_backed_up_not_semantically_replayed",
    }:
        errors.append("checkpoint prior_history_status is unsupported")
    return errors


def verify_signed_audit_checkpoint(
    store: ProofStateStore,
    *,
    checkpoint_path: Path,
    public_key_path: Path,
) -> dict[str, Any]:
    """Verify signature and prove that the checkpoint is a prefix of this state."""

    errors: list[str] = []
    try:
        document = json.loads(
            read_bounded_text(
                checkpoint_path,
                max_bytes=MAX_CHECKPOINT_BYTES,
                label="audit checkpoint",
            )
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return {"valid": False, "errors": [f"cannot read checkpoint: {exc}"]}
    if not isinstance(document, dict):
        return {"valid": False, "errors": ["checkpoint must be a JSON object"]}
    payload = document.get("payload")
    signature_card = document.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature_card, dict):
        return {
            "valid": False,
            "errors": ["checkpoint payload and signature must be objects"],
        }
    errors.extend(_checkpoint_payload_errors(payload, problem_id=store.problem_id))
    if str(signature_card.get("algorithm") or "") != SIGNATURE_ALGORITHM:
        errors.append("checkpoint signature algorithm is not ed25519")
    try:
        signature = base64.b64decode(
            str(signature_card.get("value_base64") or ""), validate=True
        )
    except (ValueError, TypeError):
        signature = b""
        errors.append("checkpoint signature is not valid base64")

    public_key = public_key_path.expanduser().resolve()
    signature_valid = False
    try:
        public_der = _public_key_der(public_key)
        actual_key_id = hashlib.sha256(public_der).hexdigest()
        if actual_key_id != str(signature_card.get("key_id_sha256") or ""):
            errors.append("checkpoint public-key fingerprint does not match")
        elif not _verify_ed25519(
            _canonical_payload_bytes(payload), signature, public_key
        ):
            errors.append("checkpoint Ed25519 signature is invalid")
        else:
            signature_valid = True
    except (OSError, RuntimeError, ValueError) as exc:
        errors.append(str(exc))

    # An invalid document is untrusted input.  Do not let its counts select
    # database prefixes or trigger an expensive local replay.
    if errors or not signature_valid:
        return {
            "valid": False,
            "problem_id": store.problem_id,
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_proof_revision": _safe_nonnegative_int(
                payload.get("proof_revision")
            ),
            "current_proof_revision": None,
            "signature_valid": signature_valid,
            "errors": errors or ["checkpoint signature is not trusted"],
        }

    with store.connect() as conn:
        # One WAL read snapshot avoids accepting or rejecting a mixed view when
        # a legitimate writer appends concurrently.
        conn.execute("BEGIN")
        patch_replay = verify_patch_journal(store, conn=conn)
        event_replay = verify_event_journal(store, conn=conn)
        errors.extend(
            f"current patch journal: {item}" for item in patch_replay["errors"]
        )
        errors.extend(
            f"current event journal: {item}" for item in event_replay["errors"]
        )
        errors.extend(f"current invariant: {item}" for item in validate_conn(conn))
        errors.extend(
            _checkpoint_prefix_errors(
                store,
                payload,
                current_patch_replay=patch_replay,
                conn=conn,
            )
        )
        state = conn.execute(
            "SELECT current_revision FROM problem_state WHERE problem_id = ?",
            (store.problem_id,),
        ).fetchone()
        current_revision = int(state["current_revision"] or 0) if state else None
    return {
        "valid": not errors,
        "problem_id": store.problem_id,
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_proof_revision": _safe_nonnegative_int(
            payload.get("proof_revision")
        ),
        "current_proof_revision": current_revision,
        "signature_valid": signature_valid,
        "errors": errors,
    }


def _checkpoint_prefix_errors(
    store: ProofStateStore,
    payload: Mapping[str, Any],
    *,
    current_patch_replay: Mapping[str, Any],
    conn: sqlite3.Connection,
) -> list[str]:
    errors: list[str] = []
    checkpoint_revision = int(payload.get("proof_revision") or 0)
    checkpoint_patch_count = int(payload.get("patch_count") or 0)
    checkpoint_event_count = int(payload.get("event_count") or 0)
    checkpoint_start_revision = int(payload.get("journal_start_revision") or 0)
    if not conn.in_transaction:
        raise ValueError("checkpoint prefix verification requires one shared transaction")
    state = conn.execute(
            "SELECT schema_version, current_revision FROM problem_state WHERE problem_id = ?",
            (store.problem_id,),
    ).fetchone()
    all_patches = [
        dict(row)
        for row in conn.execute(
                "SELECT applied_revision, journal_entry_hash, state_hash_before, "
                "state_hash_after FROM patches WHERE status = 'applied' "
                "ORDER BY applied_revision ASC, patch_id ASC"
            ).fetchall()
    ]
    baseline_row = conn.execute(
            "SELECT * FROM audit_baselines WHERE problem_id = ?",
            (store.problem_id,),
    ).fetchone()
    baseline = dict(baseline_row) if baseline_row else {}
    events = [
        dict(row)
        for row in conn.execute(
                "SELECT event_id, event_type, event_hash FROM events ORDER BY event_id ASC"
            ).fetchall()
    ]
    current_migrations = [
        int(row["version"])
        for row in conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
    ]
    if state is None:
        return ["problem_state row is missing"]
    if int(state["schema_version"] or 0) != int(payload.get("schema_version") or 0):
        errors.append("checkpoint schema version does not match current state")
    checkpoint_migrations = [
        int(item) for item in payload.get("schema_migrations", [])
    ]
    if current_migrations[: len(checkpoint_migrations)] != checkpoint_migrations:
        errors.append(
            "checkpoint schema migrations are not a prefix of the current migration history"
        )
    if int(state["current_revision"] or 0) < checkpoint_revision:
        errors.append("current proof state predates the checkpoint")
    checkpoint_run_provenance = str(payload.get("run_provenance_hash") or "")
    if checkpoint_run_provenance and checkpoint_revision == int(
        state["current_revision"] or 0
    ) and checkpoint_run_provenance != str(
        current_patch_replay.get("current_run_provenance_hash") or ""
    ):
        errors.append(
            "checkpoint run-selection provenance does not match current state"
        )
    current_start_revision = int(baseline.get("baseline_revision") or 0)
    current_start_head = str(
        baseline.get("patch_journal_head") or GENESIS_HASH
    )
    suffix_patches = [
        row
        for row in all_patches
        if int(row.get("applied_revision") or 0) > current_start_revision
    ]
    current_start_hash = str(baseline.get("baseline_state_hash") or "")
    if not current_start_hash:
        current_start_hash = (
            str(suffix_patches[0].get("state_hash_before") or "")
            if suffix_patches
            else str(current_patch_replay.get("current_state_hash") or "")
        )
    if checkpoint_start_revision != current_start_revision:
        errors.append("checkpoint journal start revision does not match current baseline")
    if str(payload.get("journal_start_state_hash") or "") != current_start_hash:
        errors.append("checkpoint journal start state hash does not match current baseline")
    if str(payload.get("journal_start_entry_hash") or "") != current_start_head:
        errors.append("checkpoint journal start entry hash does not match current baseline")
    if int(payload.get("legacy_patch_count") or 0) != int(
        baseline.get("legacy_patch_count") or 0
    ):
        errors.append("checkpoint legacy patch count does not match current baseline")
    current_prior_status = str(
        baseline.get("prior_history_status") or "replay_verified_from_genesis"
    )
    if str(payload.get("prior_history_status") or "") != current_prior_status:
        errors.append("checkpoint prior-history status does not match current baseline")
    if str(payload.get("migration_backup_sha256") or "") != str(
        baseline.get("migration_backup_sha256") or ""
    ):
        errors.append("checkpoint migration-backup hash does not match current baseline")

    if checkpoint_patch_count != checkpoint_revision - checkpoint_start_revision:
        errors.append("checkpoint patch count is inconsistent with its proof revision")
    if len(suffix_patches) < checkpoint_patch_count:
        errors.append("current patch journal is shorter than the checkpoint")
    elif checkpoint_patch_count:
        row = suffix_patches[checkpoint_patch_count - 1]
        if int(row.get("applied_revision") or 0) != checkpoint_revision:
            errors.append("checkpoint proof revision is not at the recorded patch position")
        if str(row.get("journal_entry_hash") or "") != str(
            payload.get("patch_journal_head") or ""
        ):
            errors.append("checkpoint patch head is not a prefix of the current journal")
        if str(row.get("state_hash_after") or "") != str(
            payload.get("proof_state_hash") or ""
        ):
            errors.append("checkpoint proof-state hash does not match its patch endpoint")
    else:
        if str(payload.get("patch_journal_head") or "") != current_start_head:
            errors.append("baseline checkpoint has the wrong patch-journal head")
        if str(payload.get("proof_state_hash") or "") != current_start_hash:
            errors.append("baseline checkpoint has the wrong proof-state hash")

    if len(events) < checkpoint_event_count:
        errors.append("current event journal is shorter than the checkpoint")
    elif checkpoint_event_count:
        prefix = events[:checkpoint_event_count]
        if str(prefix[-1].get("event_hash") or "") != str(
            payload.get("event_chain_head") or ""
        ):
            errors.append("checkpoint event head is not a prefix of the current journal")
        policy_head = GENESIS_HASH
        for row in prefix:
            if str(row.get("event_type") or "") in POLICY_EVENT_TYPES:
                policy_head = str(row.get("event_hash") or "")
        if policy_head != str(payload.get("policy_event_head") or ""):
            errors.append("checkpoint policy-event head does not match its event prefix")
    elif str(payload.get("event_chain_head") or "") != GENESIS_HASH:
        errors.append("zero-event checkpoint has a non-genesis event head")
    return errors

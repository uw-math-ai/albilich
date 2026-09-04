"""Bounded local retention with signed, restorable cold-storage bundles.

Proof-state rows and mathematical artifacts are authoritative and are never
deleted by this module.  Per-session context capsules and raw workflow logs are
audit-relevant but can be moved to external cold storage once a replay-clean,
externally signed audit checkpoint exists.  Every archived byte is hashed, the
archive is signed, pruning rechecks hashes, and restoration refuses path
traversal or silent overwrite.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from .audit_checkpoint import (
    MAX_CHECKPOINT_BYTES,
    SIGNATURE_ALGORITHM,
    canonical_signature_payload,
    public_key_der,
    public_key_der_from_private,
    require_private_signing_key,
    run_openssl,
    sign_ed25519,
    verify_ed25519,
    verify_signed_audit_checkpoint,
)
from .bounded_io import read_bounded_text
from .models import utc_now
from .store import ProofStateStore


STORAGE_POLICY_VERSION = 1
COLD_STORAGE_BUNDLE_VERSION = 1
MAX_BUNDLE_MANIFEST_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_FILE_COUNT = 1_000_000
DEFAULT_LOCAL_HARD_LIMIT_BYTES = 20 * 1024 * 1024 * 1024
LOCAL_HARD_LIMIT_ENV = "ALBILICH_LOCAL_STORAGE_HARD_LIMIT_BYTES"
COLD_RETENTION_ROOTS = (
    "contexts",
    "workflow_runs",
    "hmt_snapshots",
    "albilich_run_console.json",
    "albilich_run_console.md",
    "attempt_result.partial.json",
    "phase2_report.md",
)
AUTHORITATIVE_NAMES = {
    "proof_state.sqlite3",
    "proof_state.sqlite3-wal",
    "proof_state.sqlite3-shm",
    "proof_state_snapshot.json",
    "parallel_exchange.jsonl",
    "artifacts",
    "migration_backups",
    ".refs",
    "downloads",
    "sources",
    "formal_handoff",
}


class StoragePolicyError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _stream_digest(
    handle: Any, *, maximum_bytes: int | None = None
) -> tuple[int, str, bool]:
    """Hash an archive member without loading it into process memory."""

    digest = hashlib.sha256()
    size = 0
    while block := handle.read(1024 * 1024):
        size += len(block)
        if maximum_bytes is not None and size > maximum_bytes:
            return size, digest.hexdigest(), True
        digest.update(block)
    return size, digest.hexdigest(), False


def _discard_incomplete_bundle(bundle: Path) -> None:
    """Remove only a newly-created, unverified bundle directory."""

    if not bundle.exists():
        return
    for path in sorted(bundle.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    bundle.rmdir()


def _regular_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    if root.is_symlink():
        raise StoragePolicyError(f"retention tree contains a symbolic link: {root}")
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise StoragePolicyError(f"retention tree contains a symbolic link: {path}")
        if path.is_file():
            yield path


def _hard_limit_bytes() -> int:
    raw = os.environ.get(LOCAL_HARD_LIMIT_ENV, "").strip()
    if not raw:
        return DEFAULT_LOCAL_HARD_LIMIT_BYTES
    try:
        value = int(raw)
    except ValueError as exc:
        raise StoragePolicyError(f"{LOCAL_HARD_LIMIT_ENV} must be an integer") from exc
    if value < 1024 * 1024:
        raise StoragePolicyError(f"{LOCAL_HARD_LIMIT_ENV} must be at least 1048576")
    return value


def audit_local_storage(store: ProofStateStore) -> dict[str, Any]:
    """Classify every local byte and report whether another session may start."""

    by_class = {"authoritative": 0, "cold_storage_eligible": 0, "other": 0}
    file_count = {key: 0 for key in by_class}
    largest: list[dict[str, Any]] = []
    if store.state_dir.exists():
        for path in _regular_files(store.state_dir):
            relative = path.relative_to(store.state_dir)
            top = relative.parts[0] if relative.parts else ""
            retention_class = (
                "cold_storage_eligible"
                if top in COLD_RETENTION_ROOTS
                else "authoritative"
                if top in AUTHORITATIVE_NAMES
                else "other"
            )
            size = int(path.stat().st_size)
            by_class[retention_class] += size
            file_count[retention_class] += 1
            largest.append(
                {"path": relative.as_posix(), "bytes": size, "retention_class": retention_class}
            )
    largest.sort(key=lambda row: (-int(row["bytes"]), str(row["path"])))
    total = sum(by_class.values())
    limit = _hard_limit_bytes()
    return {
        "storage_policy_version": STORAGE_POLICY_VERSION,
        "problem_id": store.problem_id,
        "state_dir": str(store.state_dir),
        "retention_classes": {
            "authoritative": "never pruned by storage policy",
            "cold_storage_eligible": "prunable only after signed external archival",
            "other": "retained; requires an explicit future classification",
        },
        "bytes_by_class": by_class,
        "files_by_class": file_count,
        "total_local_bytes": total,
        "hard_limit_bytes": limit,
        "within_hard_limit": total < limit,
        "largest_files": largest[:20],
    }


def enforce_local_storage_limit(store: ProofStateStore) -> dict[str, Any]:
    report = audit_local_storage(store)
    if not report["within_hard_limit"]:
        raise StoragePolicyError(
            f"local proof-state storage is {report['total_local_bytes']} bytes, at or above "
            f"the {report['hard_limit_bytes']}-byte hard limit; create and verify a signed "
            "cold-storage bundle before launching another model session"
        )
    return report


def _external_path(store: ProofStateStore, path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    state_dir = store.state_dir.resolve()
    if resolved == state_dir or resolved.is_relative_to(state_dir):
        raise StoragePolicyError(f"{label} must be outside the mutable proof-state directory")
    return resolved


def _checkpoint_with_private_key(
    store: ProofStateStore,
    checkpoint_path: Path,
    private_key_path: Path,
) -> tuple[dict[str, Any], str]:
    try:
        checkpoint_document = json.loads(
            read_bounded_text(
                checkpoint_path,
                max_bytes=MAX_CHECKPOINT_BYTES,
                label="audit checkpoint",
            )
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StoragePolicyError(f"cannot read audit checkpoint: {exc}") from exc
    with tempfile.NamedTemporaryFile(
        prefix="albilich-storage-public-", suffix=".pem"
    ) as public_handle:
        public_pem = run_openssl(
            ["pkey", "-in", str(private_key_path), "-pubout"]
        )
        public_handle.write(public_pem)
        public_handle.flush()
        verified = verify_signed_audit_checkpoint(
            store,
            checkpoint_path=checkpoint_path,
            public_key_path=Path(public_handle.name),
        )
    if not verified["valid"]:
        raise StoragePolicyError(
            "audit checkpoint is not a valid prefix of the current state: "
            + "; ".join(verified["errors"][:8])
        )
    expected_key = str(
        (checkpoint_document.get("signature") or {}).get("key_id_sha256") or ""
    )
    actual_key = hashlib.sha256(public_key_der_from_private(private_key_path)).hexdigest()
    if expected_key != actual_key:
        raise StoragePolicyError("archive private key does not match the audit-checkpoint key")
    payload = checkpoint_document.get("payload")
    if not isinstance(payload, dict):
        raise StoragePolicyError("audit checkpoint payload is malformed")
    return payload, actual_key


def _atomic_json(path: Path, document: Mapping[str, Any]) -> None:
    encoded = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def create_cold_storage_bundle(
    store: ProofStateStore,
    *,
    bundle_dir: Path,
    checkpoint_path: Path,
    private_key_path: Path,
    prune_local: bool = False,
) -> dict[str, Any]:
    """Archive eligible local files, sign the manifest, and optionally prune."""

    bundle = _external_path(store, bundle_dir, "cold-storage bundle")
    checkpoint = _external_path(store, checkpoint_path, "audit checkpoint")
    try:
        private_key = require_private_signing_key(
            store, private_key_path, label="archive private key"
        )
    except ValueError as exc:
        raise StoragePolicyError(str(exc)) from exc
    if bundle.exists():
        raise StoragePolicyError(f"cold-storage bundle path already exists: {bundle}")
    if not checkpoint.is_file():
        raise StoragePolicyError("audit checkpoint and private key must both exist")
    checkpoint_payload, key_id = _checkpoint_with_private_key(
        store, checkpoint, private_key
    )

    file_rows: list[dict[str, Any]] = []
    source_paths: list[Path] = []
    for top in COLD_RETENTION_ROOTS:
        for path in _regular_files(store.state_dir / top):
            relative = path.relative_to(store.state_dir).as_posix()
            source_paths.append(path)
            file_rows.append(
                {
                    "path": relative,
                    "bytes": int(path.stat().st_size),
                    "sha256": _sha256_file(path),
                    "retention_class": "cold_storage_eligible",
                }
            )
    if not source_paths:
        raise StoragePolicyError("there are no context capsules or workflow logs to archive")

    bundle.mkdir(parents=True)
    archive_path = bundle / "payload.tar.gz"
    pruning_started = False
    try:
        with tarfile.open(archive_path, "w:gz", compresslevel=9) as archive:
            for path, row in zip(source_paths, file_rows):
                archive.add(path, arcname=str(row["path"]), recursive=False)
        payload = {
            "cold_storage_bundle_version": COLD_STORAGE_BUNDLE_VERSION,
            "storage_policy_version": STORAGE_POLICY_VERSION,
            "problem_id": store.problem_id,
            "created_at": utc_now(),
            "archive_file": archive_path.name,
            "archive_sha256": _sha256_file(archive_path),
            "archive_bytes": int(archive_path.stat().st_size),
            "file_count": len(file_rows),
            "uncompressed_bytes": sum(int(row["bytes"]) for row in file_rows),
            "files": file_rows,
            "checkpoint_sha256": _sha256_file(checkpoint),
            "checkpoint_proof_revision": int(checkpoint_payload.get("proof_revision") or 0),
            "checkpoint_patch_head": str(checkpoint_payload.get("patch_journal_head") or ""),
            "checkpoint_event_head": str(checkpoint_payload.get("event_chain_head") or ""),
            "authoritative_material_pruned": False,
        }
        signature = sign_ed25519(canonical_signature_payload(payload), private_key)
        document = {
            "payload": payload,
            "signature": {
                "algorithm": SIGNATURE_ALGORITHM,
                "key_id_sha256": key_id,
                "value_base64": base64.b64encode(signature).decode("ascii"),
            },
        }
        manifest_path = bundle / "manifest.json"
        _atomic_json(manifest_path, document)
        verified = verify_cold_storage_bundle(bundle, public_key_path=None, private_key_path=private_key)
        if not verified["valid"]:
            raise StoragePolicyError(
                "new cold-storage bundle did not verify: " + "; ".join(verified["errors"])
            )
        pruned_files = 0
        pruned_bytes = 0
        if prune_local:
            for path, expected in zip(source_paths, file_rows):
                if not path.is_file() or _sha256_file(path) != expected["sha256"]:
                    raise StoragePolicyError(
                        f"refusing to prune a file changed after archival: {path}"
                    )
            pruning_started = True
            for path, expected in zip(source_paths, file_rows):
                path.unlink()
                pruned_files += 1
                pruned_bytes += int(expected["bytes"])
            for top in COLD_RETENTION_ROOTS:
                root = store.state_dir / top
                if root.exists():
                    for directory in sorted(
                        (path for path in root.rglob("*") if path.is_dir()),
                        key=lambda path: len(path.parts),
                        reverse=True,
                    ):
                        try:
                            directory.rmdir()
                        except OSError:
                            pass
        return {
            "valid": True,
            "bundle_dir": str(bundle),
            "manifest_path": str(manifest_path),
            "archive_path": str(archive_path),
            "file_count": len(file_rows),
            "uncompressed_bytes": payload["uncompressed_bytes"],
            "pruned_files": pruned_files,
            "pruned_bytes": pruned_bytes,
            "authoritative_material_pruned": False,
        }
    except (OSError, RuntimeError, TypeError, ValueError, tarfile.TarError, StoragePolicyError):
        # A failed bundle has no authority and should not masquerade as a
        # complete archive. Individual source files have not yet been pruned
        # unless all verification and the pre-prune hash pass succeeded.
        if not pruning_started:
            _discard_incomplete_bundle(bundle)
        raise


def _read_bundle_document(bundle: Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    errors: list[str] = []
    manifest_path = bundle / "manifest.json"
    try:
        document = json.loads(
            read_bounded_text(
                manifest_path,
                max_bytes=MAX_BUNDLE_MANIFEST_BYTES,
                label="archive manifest",
            )
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return {}, {}, [f"cannot read archive manifest: {exc}"]
    if not isinstance(document, dict):
        return {}, {}, ["archive manifest must be a JSON object"]
    payload = document.get("payload")
    signature = document.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature, dict):
        errors.append("archive manifest payload and signature must be objects")
        return {}, {}, errors
    return payload, signature, errors


def _cold_inventory_errors(payload: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    """Validate the signed inventory before any archive is decompressed."""

    errors: list[str] = []
    raw_rows = payload.get("files")
    if not isinstance(raw_rows, list):
        return {}, ["archive files inventory must be a list"]
    if len(raw_rows) > MAX_BUNDLE_FILE_COUNT:
        return {}, [f"archive file inventory exceeds {MAX_BUNDLE_FILE_COUNT} entries"]
    expected: dict[str, Mapping[str, Any]] = {}
    total_bytes = 0
    for index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, Mapping):
            errors.append(f"archive inventory row {index} is not an object")
            continue
        name = str(raw_row.get("path") or "")
        path = PurePosixPath(name)
        if (
            not name
            or path.is_absolute()
            or ".." in path.parts
            or path.as_posix() != name
            or not path.parts
            or path.parts[0] not in COLD_RETENTION_ROOTS
        ):
            errors.append(f"archive inventory path is not cold-storage eligible: {name!r}")
            continue
        if name in expected:
            errors.append(f"duplicate archive inventory path: {name}")
            continue
        if str(raw_row.get("retention_class") or "") != "cold_storage_eligible":
            errors.append(f"archive inventory path has wrong retention class: {name}")
        try:
            size = int(raw_row.get("bytes"))
        except (TypeError, ValueError, OverflowError):
            size = -1
        if size < 0:
            errors.append(f"archive inventory path has invalid byte count: {name}")
            size = 0
        digest = str(raw_row.get("sha256") or "").lower()
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            errors.append(f"archive inventory path has invalid SHA-256: {name}")
        expected[name] = raw_row
        total_bytes += size
    try:
        recorded_count = int(payload.get("file_count"))
        recorded_total = int(payload.get("uncompressed_bytes"))
    except (TypeError, ValueError, OverflowError):
        recorded_count = recorded_total = -1
    if recorded_count != len(raw_rows) or recorded_count != len(expected):
        errors.append("archive file inventory count is inconsistent")
    if recorded_total != total_bytes:
        errors.append("archive uncompressed byte count is inconsistent")
    if payload.get("authoritative_material_pruned") is not False:
        errors.append("cold-storage bundle must not claim authoritative material pruning")
    return expected, errors


def verify_cold_storage_bundle(
    bundle_dir: Path,
    *,
    public_key_path: Path | None,
    private_key_path: Path | None = None,
) -> dict[str, Any]:
    bundle = bundle_dir.expanduser().resolve()
    payload, signature_card, errors = _read_bundle_document(bundle)
    if not payload:
        return {"valid": False, "errors": errors}
    if int(payload.get("cold_storage_bundle_version") or 0) != COLD_STORAGE_BUNDLE_VERSION:
        errors.append("unsupported cold-storage bundle version")
    if str(signature_card.get("algorithm") or "") != SIGNATURE_ALGORITHM:
        errors.append("archive signature algorithm is not ed25519")
    signature_trusted = False
    try:
        signature = base64.b64decode(
            str(signature_card.get("value_base64") or ""), validate=True
        )
    except (TypeError, ValueError):
        signature = b""
        errors.append("archive signature is not valid base64")
    try:
        if public_key_path is not None:
            public_der = public_key_der(public_key_path.expanduser().resolve())
            verify_key = public_key_path.expanduser().resolve()
            valid_signature = verify_ed25519(
                canonical_signature_payload(payload), signature, verify_key
            )
        elif private_key_path is not None:
            public_der = public_key_der_from_private(private_key_path.expanduser().resolve())
            with tempfile.NamedTemporaryFile(
                prefix="albilich-storage-public-", suffix=".pem"
            ) as handle:
                public_pem = run_openssl(
                    ["pkey", "-in", str(private_key_path), "-pubout"]
                )
                handle.write(public_pem)
                handle.flush()
                valid_signature = verify_ed25519(
                    canonical_signature_payload(payload), signature, Path(handle.name)
                )
        else:
            raise StoragePolicyError("a public or private key is required for archive verification")
        if hashlib.sha256(public_der).hexdigest() != str(
            signature_card.get("key_id_sha256") or ""
        ):
            errors.append("archive public-key fingerprint does not match")
        elif not valid_signature:
            errors.append("archive Ed25519 signature is invalid")
        else:
            signature_trusted = True
    except (OSError, RuntimeError, ValueError, StoragePolicyError) as exc:
        errors.append(str(exc))

    # The manifest is untrusted until this point.  Never inspect a payload tar
    # selected by an invalid or unsupported signed document.
    if errors or not signature_trusted:
        return {
            "valid": False,
            "bundle_dir": str(bundle),
            "problem_id": str(payload.get("problem_id") or ""),
            "file_count": 0,
            "errors": errors or ["archive signature is not trusted"],
        }

    expected, inventory_errors = _cold_inventory_errors(payload)
    errors.extend(inventory_errors)

    archive_name = str(payload.get("archive_file") or "")
    if PurePosixPath(archive_name).name != archive_name:
        errors.append("archive filename is unsafe")
        archive_path = bundle / "invalid"
    else:
        archive_path = bundle / archive_name
    if archive_path.is_symlink() or not archive_path.is_file():
        errors.append("archive payload file is missing")
    else:
        try:
            recorded_archive_bytes = int(payload.get("archive_bytes"))
            actual_archive_bytes = int(archive_path.stat().st_size)
            actual_archive_sha256 = _sha256_file(archive_path)
        except (OSError, TypeError, ValueError, OverflowError) as exc:
            errors.append(f"cannot inspect archive payload file: {exc}")
        else:
            if actual_archive_bytes != recorded_archive_bytes:
                errors.append("archive payload byte count does not match the signed manifest")
            elif actual_archive_sha256 != str(payload.get("archive_sha256") or ""):
                errors.append("archive payload SHA-256 does not match the signed manifest")

    if archive_path.is_file() and not errors:
        try:
            observed_names: set[str] = set()
            with tarfile.open(archive_path, "r|gz") as archive:
                for member in archive:
                    path = PurePosixPath(member.name)
                    if (
                        member.issym()
                        or member.islnk()
                        or not member.isfile()
                        or path.is_absolute()
                        or ".." in path.parts
                    ):
                        errors.append(f"unsafe archive member: {member.name}")
                        break
                    if member.name in observed_names or member.name not in expected:
                        errors.append(f"unexpected or duplicate archive member: {member.name}")
                        break
                    observed_names.add(member.name)
                    row = expected[member.name]
                    expected_size = int(row.get("bytes") or 0)
                    if int(member.size) != expected_size:
                        errors.append(f"archive member size mismatch: {member.name}")
                        break
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        errors.append(f"cannot read archive member: {member.name}")
                        continue
                    observed_size, observed_sha256, oversized = _stream_digest(
                        extracted,
                        maximum_bytes=expected_size,
                    )
                    if oversized or observed_size != expected_size:
                        errors.append(f"archive member size mismatch: {member.name}")
                    if observed_sha256 != str(row.get("sha256") or ""):
                        errors.append(f"archive member SHA-256 mismatch: {member.name}")
                if observed_names != set(expected):
                    errors.append("archive members do not exactly match the signed inventory")
        except (OSError, tarfile.TarError) as exc:
            errors.append(f"cannot inspect archive payload: {exc}")
    return {
        "valid": not errors,
        "bundle_dir": str(bundle),
        "problem_id": str(payload.get("problem_id") or ""),
        "file_count": int(payload.get("file_count") or 0),
        "manifest_payload_sha256": hashlib.sha256(
            canonical_signature_payload(payload)
        ).hexdigest(),
        "errors": errors,
    }


def restore_cold_storage_bundle(
    store: ProofStateStore,
    *,
    bundle_dir: Path,
    public_key_path: Path,
) -> dict[str, Any]:
    verified = verify_cold_storage_bundle(
        bundle_dir, public_key_path=public_key_path
    )
    if not verified["valid"]:
        raise StoragePolicyError(
            "refusing to restore an invalid archive: " + "; ".join(verified["errors"])
        )
    bundle = bundle_dir.expanduser().resolve()
    payload, _, _ = _read_bundle_document(bundle)
    payload_sha256 = hashlib.sha256(
        canonical_signature_payload(payload)
    ).hexdigest()
    if payload_sha256 != str(verified.get("manifest_payload_sha256") or ""):
        raise StoragePolicyError("archive manifest changed after verification")
    if str(payload.get("problem_id") or "") != store.problem_id:
        raise StoragePolicyError("archive problem_id does not match the destination store")
    rows = {
        str(row["path"]): row
        for row in payload["files"]
        if isinstance(row, Mapping)
    }
    restored = 0
    archive_path = bundle / str(payload["archive_file"])
    if archive_path.is_symlink() or _sha256_file(archive_path) != str(
        payload.get("archive_sha256") or ""
    ):
        raise StoragePolicyError("archive payload changed after verification")
    observed_names: set[str] = set()
    with tarfile.open(archive_path, "r|gz") as archive:
        for member in archive:
            relative = PurePosixPath(member.name)
            if (
                member.issym()
                or member.islnk()
                or not member.isfile()
                or relative.is_absolute()
                or ".." in relative.parts
                or member.name in observed_names
                or member.name not in rows
            ):
                raise StoragePolicyError(
                    f"unsafe or unexpected archive member during restore: {member.name}"
                )
            observed_names.add(member.name)
            destination = store.state_dir.joinpath(*relative.parts).resolve()
            if not destination.is_relative_to(store.state_dir.resolve()):
                raise StoragePolicyError(f"archive member escapes proof-state directory: {member.name}")
            expected = rows[member.name]
            if destination.exists():
                if not destination.is_file() or _sha256_file(destination) != str(expected["sha256"]):
                    raise StoragePolicyError(
                        f"refusing to overwrite different local material: {destination}"
                    )
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".restore", dir=str(destination.parent)
            )
            try:
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise StoragePolicyError(f"cannot read archive member: {member.name}")
                digest = hashlib.sha256()
                observed_size = 0
                with os.fdopen(descriptor, "wb") as handle:
                    while block := extracted.read(1024 * 1024):
                        observed_size += len(block)
                        digest.update(block)
                        handle.write(block)
                    handle.flush()
                    os.fsync(handle.fileno())
                if observed_size != int(expected["bytes"]):
                    raise StoragePolicyError(
                        f"archive member size changed during restore: {member.name}"
                    )
                if digest.hexdigest() != str(expected["sha256"]):
                    raise StoragePolicyError(
                        f"archive member changed during restore: {member.name}"
                    )
                os.replace(temporary_name, destination)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
            restored += 1
    if observed_names != set(rows):
        raise StoragePolicyError("archive inventory changed during restore")
    return {"valid": True, "restored_files": restored, "bundle_dir": str(bundle)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit and archive Albilich local storage")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("problem_id")
    archive_parser = subparsers.add_parser("archive")
    archive_parser.add_argument("problem_id")
    archive_parser.add_argument("--bundle", type=Path, required=True)
    archive_parser.add_argument("--checkpoint", type=Path, required=True)
    archive_parser.add_argument("--private-key", type=Path, required=True)
    archive_parser.add_argument("--prune", action="store_true")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--bundle", type=Path, required=True)
    verify_parser.add_argument("--public-key", type=Path, required=True)
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("problem_id")
    restore_parser.add_argument("--bundle", type=Path, required=True)
    restore_parser.add_argument("--public-key", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            result = verify_cold_storage_bundle(
                args.bundle, public_key_path=args.public_key
            )
        else:
            store = ProofStateStore(args.problem_id)
            if args.command == "audit":
                result = audit_local_storage(store)
            elif args.command == "archive":
                result = create_cold_storage_bundle(
                    store,
                    bundle_dir=args.bundle,
                    checkpoint_path=args.checkpoint,
                    private_key_path=args.private_key,
                    prune_local=args.prune,
                )
            else:
                result = restore_cold_storage_bundle(
                    store,
                    bundle_dir=args.bundle,
                    public_key_path=args.public_key,
                )
    except (OSError, ValueError, StoragePolicyError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("valid", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())

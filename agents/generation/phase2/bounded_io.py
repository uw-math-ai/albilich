from __future__ import annotations

"""Race-aware bounded reads for operator and sidecar input files."""

import hashlib
import os
import stat
from pathlib import Path
from typing import Tuple


def _read_flags(source: Path, *, label: str) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    else:
        try:
            if source.is_symlink():
                raise ValueError(f"{label} must not be a symbolic link")
        except OSError as exc:
            raise ValueError(f"could not inspect {label}: {exc}") from exc
    return flags


def _identity(info: os.stat_result) -> Tuple[int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def read_bounded_bytes(
    path: Path | str,
    *,
    max_bytes: int,
    label: str = "input file",
) -> bytes:
    """Read one regular file without following a final symlink.

    The descriptor is checked before and after reading. A concurrent size,
    identity, or timestamp change is rejected instead of mixing two versions.
    """

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    source = Path(path)
    try:
        descriptor = os.open(source, _read_flags(source, label=label))
    except OSError as exc:
        raise ValueError(f"could not open {label}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"{label} must be a regular file")
        if before.st_size > max_bytes:
            raise ValueError(
                f"{label} exceeds the {max_bytes}-byte input limit"
            )
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if len(payload) > max_bytes:
        raise ValueError(f"{label} exceeds the {max_bytes}-byte input limit")
    if _identity(before) != _identity(after) or len(payload) != after.st_size:
        raise ValueError(f"{label} changed during bounded ingestion")
    return payload


def read_bounded_text(
    path: Path | str,
    *,
    max_bytes: int,
    label: str = "input file",
) -> str:
    payload = read_bounded_bytes(path, max_bytes=max_bytes, label=label)
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must be valid UTF-8") from exc


def stable_file_sha256_size(
    path: Path | str,
    *,
    max_bytes: int,
    label: str = "input file",
) -> tuple[str, int]:
    """Hash one bounded regular file through a stable non-symlink descriptor."""

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    source = Path(path)
    try:
        descriptor = os.open(source, _read_flags(source, label=label))
    except OSError as exc:
        raise ValueError(f"could not open {label}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"{label} must be a regular file")
        if before.st_size > max_bytes:
            raise ValueError(f"{label} exceeds the {max_bytes}-byte input limit")
        digest = hashlib.sha256()
        observed_size = 0
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            observed_size += len(block)
            if observed_size > max_bytes:
                raise ValueError(
                    f"{label} exceeds the {max_bytes}-byte input limit"
                )
            digest.update(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if _identity(before) != _identity(after) or observed_size != after.st_size:
        raise ValueError(f"{label} changed during bounded ingestion")
    return digest.hexdigest(), observed_size


def read_bytes_prefix(
    path: Path | str,
    *,
    max_bytes: int,
    label: str = "input file",
) -> tuple[bytes, bool, int]:
    """Read a stable byte-bounded prefix of one regular non-symlink file."""

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    source = Path(path)
    try:
        descriptor = os.open(source, _read_flags(source, label=label))
    except OSError as exc:
        raise ValueError(f"could not open {label}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"{label} must be a regular file")
        chunks: list[bytes] = []
        remaining = min(max_bytes + 1, before.st_size + 1)
        while remaining > 0:
            block = os.read(descriptor, min(1024 * 1024, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if _identity(before) != _identity(after):
        raise ValueError(f"{label} changed during bounded ingestion")
    payload = b"".join(chunks)
    return payload[:max_bytes], len(payload) > max_bytes, int(after.st_size)


def read_text_prefix(
    path: Path | str,
    *,
    max_chars: int,
    label: str = "input file",
    errors: str = "strict",
) -> tuple[str, bool, int]:
    """Read at most ``max_chars`` from a stable regular UTF-8 file.

    Unlike :func:`read_bounded_text`, an oversized file is allowed and reported
    as truncated. The whole file is never materialized in memory.
    """

    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    source = Path(path)
    try:
        descriptor = os.open(source, _read_flags(source, label=label))
    except OSError as exc:
        raise ValueError(f"could not open {label}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"{label} must be a regular file")
        with os.fdopen(descriptor, "r", encoding="utf-8", errors=errors) as handle:
            descriptor = -1
            try:
                text = handle.read(max_chars + 1)
            except UnicodeDecodeError as exc:
                raise ValueError(f"{label} must be valid UTF-8") from exc
            after = os.fstat(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if _identity(before) != _identity(after):
        raise ValueError(f"{label} changed during bounded ingestion")
    return text[:max_chars], len(text) > max_chars, int(after.st_size)


def read_text_tail(
    path: Path | str,
    *,
    max_bytes: int,
    label: str = "input file",
    errors: str = "replace",
) -> tuple[str, bool, int]:
    """Read a stable byte-bounded tail without materializing the file prefix."""

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    source = Path(path)
    try:
        descriptor = os.open(source, _read_flags(source, label=label))
    except OSError as exc:
        raise ValueError(f"could not open {label}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"{label} must be a regular file")
        omitted = before.st_size > max_bytes
        start = max(0, before.st_size - max_bytes)
        os.lseek(descriptor, start, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = min(max_bytes, before.st_size)
        while remaining > 0:
            block = os.read(descriptor, min(1024 * 1024, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if _identity(before) != _identity(after):
        raise ValueError(f"{label} changed during bounded ingestion")
    payload = b"".join(chunks)
    if omitted:
        # The first bytes may be the suffix of a UTF-8 code point or JSONL row.
        # Dropping through the first newline gives callers a clean record tail.
        newline = payload.find(b"\n")
        payload = payload[newline + 1 :] if newline >= 0 else b""
    try:
        text = payload.decode("utf-8", errors=errors)
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must be valid UTF-8") from exc
    return text, omitted, int(after.st_size)

from __future__ import annotations

import hashlib
import json
import os
import stat
import codecs
from pathlib import Path
from typing import Any, Dict, Optional

from .models import sha256_text


MAX_VERIFIED_ARTIFACT_READ_BYTES = 256 * 1024 * 1024


def artifact_hash(*, path: Optional[Path] = None, content: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
    if content is not None:
        return sha256_text(content)
    if path is not None:
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        elif path.is_symlink():
            raise ValueError(f"artifact must not be a symbolic link: {path}")
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise ValueError(f"could not open artifact {path}: {exc}") from exc
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError(f"artifact is not a regular file: {path}")
            digest = hashlib.sha256()
            observed_size = 0
            while True:
                block = os.read(descriptor, 1024 * 1024)
                if not block:
                    break
                observed_size += len(block)
                digest.update(block)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        if before_identity != after_identity or observed_size != after.st_size:
            raise ValueError(f"artifact changed while its digest was computed: {path}")
        return digest.hexdigest()
    return sha256_text(json.dumps(metadata or {}, sort_keys=True, ensure_ascii=False))


def artifact_summary(metadata: Dict[str, Any], fallback: str = "") -> str:
    for key in ("summary", "verdict", "outcome", "status", "title"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:500]
    return fallback[:500]


def read_verified_artifact_text_prefix(
    *,
    path: Path,
    expected_sha256: str,
    max_chars: int,
    max_bytes: int = MAX_VERIFIED_ARTIFACT_READ_BYTES,
) -> tuple[str, bool, int, int]:
    """Authenticate a stable artifact while retaining only a text prefix.

    The complete file is streamed through SHA-256, but at most
    ``max_chars + 1`` decoded characters are retained.  This lets context
    construction reject post-admission file changes without materializing a
    potentially large artifact in memory.
    """

    if max_chars <= 0:
        raise ValueError("artifact text limit must be positive")
    if max_bytes <= 0:
        raise ValueError("artifact byte limit must be positive")
    expected = str(expected_sha256 or "").strip().lower()
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise ValueError("artifact record has no valid SHA-256 digest")

    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    elif path.is_symlink():
        raise ValueError(f"artifact must not be a symbolic link: {path}")
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"could not open artifact {path}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"artifact is not a regular file: {path}")
        if before.st_size > max_bytes:
            raise ValueError(
                f"artifact exceeds the authenticated {max_bytes}-byte read limit: {path}"
            )
        digest = hashlib.sha256()
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        retained: list[str] = []
        retained_chars = 0
        total_chars = 0
        observed_size = 0
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            observed_size += len(block)
            digest.update(block)
            decoded = decoder.decode(block)
            total_chars += len(decoded)
            if retained_chars <= max_chars:
                fragment = decoded[: max_chars + 1 - retained_chars]
                retained.append(fragment)
                retained_chars += len(fragment)
        final_fragment = decoder.decode(b"", final=True)
        total_chars += len(final_fragment)
        if retained_chars <= max_chars:
            fragment = final_fragment[: max_chars + 1 - retained_chars]
            retained.append(fragment)
            retained_chars += len(fragment)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if before_identity != after_identity or observed_size != after.st_size:
        raise ValueError(f"artifact changed during authenticated context read: {path}")
    observed_digest = digest.hexdigest()
    if observed_digest != expected:
        raise ValueError(
            f"artifact SHA-256 mismatch during context construction: {path}"
        )
    text = "".join(retained)
    complete = total_chars <= max_chars
    return text[:max_chars], complete, int(after.st_size), total_chars

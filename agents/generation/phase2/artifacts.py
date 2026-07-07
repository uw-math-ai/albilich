from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .models import sha256_bytes, sha256_text


def artifact_hash(*, path: Optional[Path] = None, content: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
    if content is not None:
        return sha256_text(content)
    if path is not None and path.exists() and path.is_file():
        digest = sha256_bytes(path.read_bytes())
        return digest
    return sha256_text(json.dumps(metadata or {}, sort_keys=True, ensure_ascii=False))


def artifact_summary(metadata: Dict[str, Any], fallback: str = "") -> str:
    for key in ("summary", "verdict", "outcome", "status", "title"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:500]
    return fallback[:500]

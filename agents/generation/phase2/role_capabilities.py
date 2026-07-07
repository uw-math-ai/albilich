from __future__ import annotations

from typing import Any, Mapping, Optional

CAS_ENABLED_ROLES = frozenset({"researcher", "villain"})
# Researcher work modes that reserve the pass for search or pure thinking; CAS
# tooling is withheld so the online/offline/cas loop stays cleanly separated.
CAS_SUPPRESSED_WORK_MODES = frozenset({"online", "offline"})


def role_can_use_cas(role: str) -> bool:
    return role in CAS_ENABLED_ROLES


def session_cas_enabled(role: str, action: Optional[Mapping[str, Any]] = None) -> bool:
    """Whether one scheduled session should get CAS tooling.

    Both work-mode-scheduled mathematicians — the researcher (prover) and the
    villain (refuter) — get CAS in cas mode (or on a legacy unstamped action)
    and run without it in online/offline passes, keeping the loop's separation
    clean. Other roles keep the plain role gate.
    """
    if not role_can_use_cas(role):
        return False
    if role not in {"researcher", "villain"}:
        return True
    work_mode = str((action or {}).get("researcher_work_mode") or "").strip().lower()
    return work_mode not in CAS_SUPPRESSED_WORK_MODES

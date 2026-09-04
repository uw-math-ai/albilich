from __future__ import annotations

import os
from typing import Any, Mapping, Optional

CAS_ENABLED_ROLES = frozenset({"researcher", "adversarial_reviewer", "villain"})
CAS_ENABLED_ENV = "ALBILICH_CAS_ENABLED"
CAS_DISABLED_VALUES = frozenset({"0", "false", "no", "off"})
ADVISOR_ENABLED_ENV = "ALBILICH_ADVISOR_ENABLED"
_FALSE_ENV_VALUES = frozenset({"0", "false", "no", "off"})
# Researcher work modes that reserve the pass for search or pure thinking; CAS
# tooling is withheld so the online/offline/cas loop stays cleanly separated.
CAS_SUPPRESSED_WORK_MODES = frozenset({"online", "offline"})


def advisor_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    """Whether PhD-advisor sessions may be scheduled.

    The default preserves the normal scheduler.  Setting
    ``ALBILICH_ADVISOR_ENABLED=0`` performs the advisor ablation while leaving
    all other role and model settings unchanged.
    """
    source = os.environ if env is None else env
    value = str(source.get(ADVISOR_ENABLED_ENV, "1")).strip().lower()
    return value not in _FALSE_ENV_VALUES


def role_can_use_cas(role: str) -> bool:
    return role in CAS_ENABLED_ROLES


def cas_globally_enabled() -> bool:
    """Whether this workflow permits CAS scheduling and child access."""
    return os.environ.get(CAS_ENABLED_ENV, "1").strip().lower() not in CAS_DISABLED_VALUES


def session_cas_enabled(role: str, action: Optional[Mapping[str, Any]] = None) -> bool:
    """Whether one scheduled session should get CAS tooling.

    Both work-mode-scheduled mathematicians — the researcher (prover) and the
    adversarial reviewer (the legacy name was ``villain``) — get CAS in cas
    mode (or on a legacy unstamped action)
    and run without it in online/offline passes, keeping the loop's separation
    clean. Other roles keep the plain role gate.
    """
    # cas_globally_enabled() (ALBILICH_CAS_ENABLED=0) is the canonical global
    # CAS kill-switch — it doubles as the controlled-ablation toggle, leaving
    # research mode / scheduling identical while withholding all CAS tooling.
    if not cas_globally_enabled() or not role_can_use_cas(role):
        return False
    if role not in {"researcher", "adversarial_reviewer", "villain"}:
        return True
    work_mode = str((action or {}).get("researcher_work_mode") or "").strip().lower()
    return work_mode not in CAS_SUPPRESSED_WORK_MODES

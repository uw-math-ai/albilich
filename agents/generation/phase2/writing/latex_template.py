"""Deterministic LaTeX template normalizer for the ``final_paper`` deliverable.

The paper contract (writing/paper_contract.py) mandates a house preamble and
booktabs tables, but layout must not depend on model compliance: this module
rewrites whatever the writer shipped into the house template mechanically.
It is applied in patches._attach_artifact right after the escaping repair, so
the stored ``.tex`` (and everything downstream — the compile sidecar, the
lint sync, the editor packet) always sees the normalized document.

The normalizer maps a non-house document onto the house layout and leaves
an already-house document unchanged (idempotent); a hand-typeset
house-style paper is a fixed point.

Two passes:

- :func:`_normalize_preamble` — if the preamble lacks the house package set,
  the region between ``\\documentclass`` and the first theorem declaration /
  ``\\title`` is rewritten to the house template (geometry 1.25in margins,
  ams trio, newpx fonts, microtype, booktabs, xcolor + linkblue, hyperref
  with colored links loaded last, ``\\emergencystretch``), keeping any
  author-added packages we do not supply; ``\\numberwithin{equation}{section}``
  is ensured after the theorem declarations.
- :func:`_normalize_tables` — every ``tabular`` loses its vertical bars and
  ``\\hline`` rules and gains the canonical booktabs skeleton (``\\toprule``,
  header row, ``\\midrule``, body, ``\\bottomrule``), with the collapse rules
  that remove the artifacts a naive rule-for-rule substitution produces:
  never ``\\toprule`` immediately followed by ``\\midrule``, never
  ``\\midrule`` immediately before ``\\bottomrule``, never a bare trailing
  ``\\\\`` making an empty row before ``\\bottomrule``.
"""

from __future__ import annotations

import re
from typing import List

# --- preamble normalization ---------------------------------------------------

_DOCUMENTCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{[^}]*\}")
_BEGIN_DOCUMENT_RE = re.compile(r"\\begin\{document\}")
# The rewritten region ends where the theorem declarations (or the \title
# block, whichever comes first) begin.
_PREAMBLE_REGION_END_RE = re.compile(r"\\newtheorem\b|\\theoremstyle\b|\\title\b")
_USEPACKAGE_RE = re.compile(r"\\usepackage(?:\[(?P<opts>[^\]]*)\])?\{(?P<names>[^}]*)\}")
_LINKBLUE_RE = re.compile(r"\\definecolor\{linkblue\}\{RGB\}\{0,\s*0,\s*128\}")
_ANY_LINKBLUE_DEF_RE = re.compile(r"[ \t]*\\definecolor\{linkblue\}\{[^}]*\}\{[^}]*\}[ \t]*\n?")
_HYPERSETUP_RE = re.compile(r"[ \t]*\\hypersetup\{[^{}]*\}[ \t]*\n?", re.DOTALL)
_EMERGENCYSTRETCH_RE = re.compile(r"[ \t]*\\emergencystretch\s*=?\s*[0-9.]+[a-z]*[ \t]*\n?")
_NUMBERWITHIN_RE = re.compile(r"[ \t]*\\numberwithin\{equation\}\{section\}[ \t]*\n?")
_THEOREM_DECL_RE = re.compile(r"\\(?:newtheorem\*?\{[^}]*\}(?:\[[^\]]*\])?\{[^}]*\}|theoremstyle\{[^}]*\})")

# Packages the house template supplies itself; author \usepackage lines that
# load only these are dropped (re-supplied), others are kept.
_HOUSE_SUPPLIED_PACKAGES = {
    "geometry",
    "amsmath",
    "amssymb",
    "amsthm",
    "newpxtext",
    "newpxmath",
    "microtype",
    "booktabs",
    "xcolor",
    "hyperref",
}

_HOUSE_PREAMBLE_HEAD = [
    r"\usepackage[margin=1.25in]{geometry}",
    r"\usepackage{amsmath,amssymb,amsthm}",
    r"\usepackage{newpxtext,newpxmath}",
    r"\usepackage{microtype}",
    r"\usepackage{booktabs}",
    r"\usepackage{xcolor}",
    r"\definecolor{linkblue}{RGB}{0,0,128}",
]
# hyperref is loaded LAST (after any kept author packages), then the stretch.
_HOUSE_PREAMBLE_TAIL = [
    r"\usepackage[colorlinks=true,linkcolor=linkblue,citecolor=linkblue,urlcolor=linkblue]{hyperref}",
    r"\emergencystretch=1.5em",
]


def normalize_paper_template(tex: str) -> str:
    """Rewrite ``final_paper`` LaTeX source onto the house template.

    Deterministic and idempotent: an already-house document (house preamble,
    booktabs tables) comes back unchanged. Text outside the preamble region
    and outside ``tabular`` environments is never touched.
    """
    tex = _normalize_preamble(tex)
    tex = _normalize_tables(tex)
    return tex


def _preamble_region(tex: str) -> tuple[int, int] | None:
    """The (start, end) offsets of the rewriteable region: from the end of
    ``\\documentclass`` to the first theorem declaration / ``\\title`` (falling
    back to ``\\begin{document}``)."""
    dc = _DOCUMENTCLASS_RE.search(tex)
    if dc is None:
        return None
    end_match = _PREAMBLE_REGION_END_RE.search(tex, dc.end())
    if end_match is None:
        end_match = _BEGIN_DOCUMENT_RE.search(tex, dc.end())
    if end_match is None:
        return None
    return dc.end(), end_match.start()


def _region_is_house(region: str) -> bool:
    """True when the region already carries the full house package set with
    hyperref loaded last — the idempotence test for the preamble rewrite."""
    packages = _USEPACKAGE_RE.findall(region)
    loaded: List[str] = []
    geometry_margin = False
    hyperref_colored = "colorlinks" in region
    for opts, names in packages:
        for name in (part.strip() for part in names.split(",")):
            if name:
                loaded.append(name)
            if name == "geometry" and "margin=1.25in" in (opts or ""):
                geometry_margin = True
    required = _HOUSE_SUPPLIED_PACKAGES - {"hyperref"}
    if not required.issubset(set(loaded)):
        return False
    if "hyperref" not in loaded or loaded[-1] != "hyperref":
        return False
    return (
        geometry_margin
        and hyperref_colored
        and _LINKBLUE_RE.search(region) is not None
        and "\\emergencystretch" in region
    )


def _rewrite_usepackage(match: re.Match[str]) -> str:
    """Drop house-supplied packages from an author ``\\usepackage``; keep the
    line verbatim when it loads no house package (author additions survive)."""
    names = [part.strip() for part in match.group("names").split(",") if part.strip()]
    kept = [name for name in names if name not in _HOUSE_SUPPLIED_PACKAGES]
    if kept == names:
        return match.group(0)
    if not kept:
        return ""
    # Mixed line: the house part is re-supplied, so the kept packages are
    # reloaded bare (their options, if any, belonged to the house packages).
    return "\\usepackage{" + ",".join(kept) + "}"


def _normalize_preamble(tex: str) -> str:
    region_span = _preamble_region(tex)
    if region_span is None:
        return tex
    start, end = region_span
    region = tex[start:end]
    if not _region_is_house(region):
        # Strip everything the house template re-supplies; keep the rest
        # (author packages, macros) between the xcolor block and hyperref.
        kept = _USEPACKAGE_RE.sub(_rewrite_usepackage, region)
        for pattern in (_ANY_LINKBLUE_DEF_RE, _HYPERSETUP_RE, _EMERGENCYSTRETCH_RE, _NUMBERWITHIN_RE):
            kept = pattern.sub("", kept)
        kept_lines = [line.rstrip() for line in kept.splitlines() if line.strip()]
        new_region_lines = _HOUSE_PREAMBLE_HEAD + kept_lines + _HOUSE_PREAMBLE_TAIL
        new_region = "\n" + "\n".join(new_region_lines) + "\n"
        tex = tex[:start] + new_region + tex[end:]
    return _ensure_numberwithin(tex)


def _ensure_numberwithin(tex: str) -> str:
    """Ensure ``\\numberwithin{equation}{section}`` sits after the theorem
    declarations (matching the reference layout); already-satisfied documents
    are unchanged."""
    begin_doc = _BEGIN_DOCUMENT_RE.search(tex)
    if begin_doc is None:
        return tex
    preamble = tex[: begin_doc.start()]
    decls = list(_THEOREM_DECL_RE.finditer(preamble))
    command = "\\numberwithin{equation}{section}"
    if not decls:
        if command in preamble:
            return tex
        return preamble.rstrip("\n") + "\n" + command + "\n" + tex[begin_doc.start() :]
    last_decl_end = decls[-1].end()
    if command in preamble[last_decl_end:]:
        return tex
    # Remove any earlier occurrence, then re-insert after the line carrying
    # the last theorem declaration.
    preamble = _NUMBERWITHIN_RE.sub("", preamble)
    decls = list(_THEOREM_DECL_RE.finditer(preamble))
    line_end = preamble.find("\n", decls[-1].end())
    if line_end == -1:
        line_end = len(preamble)
    preamble = preamble[:line_end] + "\n" + command + preamble[line_end:]
    return preamble + tex[begin_doc.start() :]


# --- table normalization ------------------------------------------------------

_TABULAR_RE = re.compile(
    r"(?P<begin>\\begin\{tabular\}(?:\[[^\]]*\])?\{(?P<spec>[^}]*)\})"
    r"(?P<body>.*?)"
    r"(?P<end>\\end\{tabular\})",
    re.DOTALL,
)
_HLINE_RE = re.compile(r"\\hline|\\cline\{[^}]*\}")
_RULE_TOKEN_RE = re.compile(r"\\hline|\\cline\{[^}]*\}|\\toprule|\\midrule|\\bottomrule")
# Row separator: "\\" with an optional spacing argument ("\\[2pt]").
_ROW_SEP_RE = re.compile(r"\\\\(?:\[[^\]]*\])?")
# Collapse artifacts of a naive rule-by-rule substitution.
_TOPRULE_MIDRULE_RE = re.compile(r"\\toprule(?:\s*\\midrule)+")
_MIDRULE_BOTTOMRULE_RE = re.compile(r"(?:\\midrule\s*)+(\\bottomrule)")
_EMPTY_ROW_BOTTOMRULE_RE = re.compile(r"(\\\\(?:\[[^\]]*\])?)(?:\s*\\\\(?:\[[^\]]*\])?)+(\s*\\bottomrule)")


def _collapse_rule_artifacts(body: str) -> str:
    body = _TOPRULE_MIDRULE_RE.sub(r"\\toprule", body)
    body = _MIDRULE_BOTTOMRULE_RE.sub(r"\1", body)
    body = _EMPTY_ROW_BOTTOMRULE_RE.sub(r"\1\2", body)
    return body


def _rebuild_tabular_body(body: str) -> str:
    """Canonical booktabs skeleton: \\toprule, header row, \\midrule, body
    rows, \\bottomrule. Existing rules are discarded; rows are preserved."""
    stripped = _RULE_TOKEN_RE.sub("", body)
    rows = [row.strip() for row in _ROW_SEP_RE.split(stripped)]
    rows = [row for row in rows if row]
    if not rows:
        return body
    lines = ["\\toprule", rows[0] + r" \\"]
    if len(rows) > 1:
        lines.append("\\midrule")
        lines.extend(row + r" \\" for row in rows[1:])
    lines.append("\\bottomrule")
    return "\n" + "\n".join(lines) + "\n"


def _normalize_one_tabular(match: re.Match[str]) -> str:
    spec = match.group("spec").replace("|", "")
    body = match.group("body")
    already_booktabs = (
        "|" not in match.group("spec")
        and _HLINE_RE.search(body) is None
        and "\\toprule" in body
        and "\\bottomrule" in body
    )
    if already_booktabs:
        # Keep the author's row grouping; only collapse rule artifacts.
        body = _collapse_rule_artifacts(body)
    else:
        body = _collapse_rule_artifacts(_rebuild_tabular_body(body))
    begin = match.group("begin").replace("{" + match.group("spec") + "}", "{" + spec + "}")
    return begin + body + match.group("end")


def _normalize_tables(tex: str) -> str:
    return _TABULAR_RE.sub(_normalize_one_tabular, tex)

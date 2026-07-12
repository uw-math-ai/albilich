from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Iterable, List, Mapping

from .models import json_dumps, json_loads

VERIFIED_SIDE_LEMMA_STATUSES = {"informally_verified", "formally_verified"}
PARTIAL_RECEIPT_VERIFIED_HEADING = "## Verified Side Lemmas"
PARTIAL_RECEIPT_LEDGER_HEADING = "## Claim Status Ledger"
LATEX_TIMEOUT_SECONDS = 120


def build_partial_receipt_inventory(
    claims: Iterable[Mapping[str, Any]],
    *,
    artifacts: Iterable[Mapping[str, Any]] | None = None,
    max_statement_chars: int | None = None,
    max_proof_chars: int | None = None,
) -> Dict[str, Any]:
    """Build the claim inventory a stop writer must include in partial receipts."""
    artifact_lookup = _artifact_lookup(artifacts)
    cards = [
        _claim_status_card(
            claim,
            artifact_lookup=artifact_lookup,
            max_statement_chars=max_statement_chars,
            max_proof_chars=max_proof_chars,
        )
        for claim in claims
    ]
    verified_side_lemmas = [
        card
        for card in cards
        if card["claim_id"] != "root" and card["validation_status"] in VERIFIED_SIDE_LEMMA_STATUSES
    ]
    other_claims = [card for card in cards if card not in verified_side_lemmas]
    verified_side_lemmas.sort(key=_receipt_sort_key)
    other_claims.sort(key=_receipt_sort_key)
    return {
        "claim_count": len(cards),
        "verified_side_lemma_count": len(verified_side_lemmas),
        "other_claim_count": len(other_claims),
        "validation_status_counts": _counts(cards, "validation_status"),
        "lifecycle_status_counts": _counts(cards, "lifecycle_status"),
        "verified_side_lemmas": verified_side_lemmas,
        "other_claims": other_claims,
    }


def format_partial_receipt_appendix(
    claims: Iterable[Mapping[str, Any]],
    *,
    artifacts: Iterable[Mapping[str, Any]] | None = None,
    max_proof_chars: int | None = None,
) -> str:
    inventory = build_partial_receipt_inventory(
        claims,
        artifacts=artifacts,
        max_proof_chars=max_proof_chars,
    )
    lines: List[str] = [
        PARTIAL_RECEIPT_VERIFIED_HEADING,
        "",
        f"Count: {inventory['verified_side_lemma_count']}",
        "",
    ]
    if inventory["verified_side_lemmas"]:
        for claim in inventory["verified_side_lemmas"]:
            lines.extend(_format_claim_block(claim))
    else:
        lines.append("None.")
    lines.extend(
        [
            "",
            PARTIAL_RECEIPT_LEDGER_HEADING,
            "",
            f"Count: {inventory['other_claim_count']}",
            "",
        ]
    )
    if inventory["other_claims"]:
        for claim in inventory["other_claims"]:
            lines.extend(_format_claim_block(claim))
    else:
        lines.append("None.")
    lines.extend(
        [
            "",
            "## Claim Status Counts",
            "",
            f"- validation_status: {json_dumps(inventory['validation_status_counts'])}",
            f"- lifecycle_status: {json_dumps(inventory['lifecycle_status_counts'])}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def receipt_appendix_present(content: str) -> bool:
    return PARTIAL_RECEIPT_VERIFIED_HEADING in content and PARTIAL_RECEIPT_LEDGER_HEADING in content


def write_latex_pdf_sidecars(
    receipt_path: Path | str,
    content: str,
    *,
    title: str = "Albilich v1 Partial Receipt",
) -> Dict[str, str]:
    path = Path(receipt_path)
    tex_path = path.with_suffix(".tex")
    pdf_path = path.with_suffix(".pdf")
    tex_path.write_text(format_receipt_latex(content, title=title), encoding="utf-8")
    sidecars = {"latex_path": str(tex_path)}
    sidecars.update(_compile_latex(tex_path, pdf_path))
    return sidecars


write_receipt_latex_sidecars = write_latex_pdf_sidecars


def compile_latex_artifact(tex_path: Path | str, pdf_path: Path | str) -> Dict[str, str]:
    """Compile an artifact that already IS LaTeX source (e.g. a ``final_paper``).

    Unlike :func:`write_latex_pdf_sidecars` there is no markdown→LaTeX
    conversion: ``tex_path`` is compiled as-is with the shared pdflatex
    machinery. Returns the same sidecar dict shape (``pdf_status``,
    ``pdf_path``, ``latex_log_path`` on failure) plus ``latex_path``.
    """
    tex_path = Path(tex_path)
    sidecars = {"latex_path": str(tex_path)}
    sidecars.update(_compile_latex(tex_path, Path(pdf_path)))
    return sidecars


def format_receipt_latex(content: str, *, title: str = "Albilich v1 Partial Receipt") -> str:
    lines = _latex_document_preamble(title)
    lines.extend(_render_receipt_content_latex(content))
    lines.extend([r"\end{document}", ""])
    return "\n".join(lines)


def _latex_document_preamble(title: str) -> List[str]:
    return [
        r"\documentclass[11pt]{article}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{amsmath,amssymb,amsthm}",
        r"\usepackage[margin=0.85in]{geometry}",
        r"\usepackage{xcolor}",
        r"\usepackage{hyperref}",
        r"\usepackage{url}",
        r"\usepackage{enumitem}",
        r"\setlength{\parindent}{0pt}",
        r"\setlength{\parskip}{6pt}",
        r"\allowdisplaybreaks",
        r"\sloppy",
        r"\hypersetup{colorlinks=true,linkcolor=blue,urlcolor=blue}",
        r"\definecolor{albilichmeta}{gray}{0.35}",
        r"\definecolor{albilichrule}{gray}{0.78}",
        r"\newcommand{\receiptbullet}[1]{\par\noindent\hangindent=1.5em\hangafter=1\textbullet\ #1\par}",
        r"\newcommand{\claimheading}[2]{\par\bigskip\noindent{\large\bfseries #1}\par{\footnotesize\color{albilichmeta}#2}\par\smallskip\noindent{\color{albilichrule}\rule{\linewidth}{0.4pt}}\par\smallskip}",
        r"\newcommand{\fieldlabel}[1]{\par\smallskip\noindent{\bfseries #1.}\ }",
        r"\newcommand{\artifactheading}[2]{\par\medskip\noindent{\bfseries #1}\par{\footnotesize\color{albilichmeta}#2}\par}",
        r"\newenvironment{proofmaterial}{\par\smallskip\begingroup\small}{\par\endgroup}",
        r"\newenvironment{proofexcerpt}{\par\smallskip\begingroup\small\leftskip=1.25em\rightskip=0.5em}{\par\endgroup}",
        r"\begin{document}",
        rf"\title{{{_latex_inline(title, smart_math=False)}}}",
        r"\date{}",
        r"\maketitle",
        r"\tableofcontents",
        r"\newpage",
    ]


def _render_receipt_content_latex(content: str) -> List[str]:
    sections = _split_receipt_sections(content)
    has_named_sections = any(section["title"] for section in sections)
    lines: List[str] = []
    for section in sections:
        title = section["title"]
        body = section["lines"]
        if title is None:
            if has_named_sections and any(line.strip() for line in body):
                lines.append(r"\section{Run Assessment}")
            lines.extend(_render_freeform_lines(body, heading_level=2))
            continue
        lines.append(rf"\section{{{_latex_inline(title)}}}")
        if title in {PARTIAL_RECEIPT_VERIFIED_HEADING[3:], PARTIAL_RECEIPT_LEDGER_HEADING[3:]}:
            lines.extend(_render_claim_section_latex(body))
        else:
            lines.extend(_render_freeform_lines(body, heading_level=2))
    return lines


def _split_receipt_sections(content: str) -> List[Dict[str, Any]]:
    receipt_headings = {
        PARTIAL_RECEIPT_VERIFIED_HEADING,
        PARTIAL_RECEIPT_LEDGER_HEADING,
        "## Claim Status Counts",
    }
    has_receipt_headings = any(line.strip() in receipt_headings for line in content.splitlines())
    sections: List[Dict[str, Any]] = [{"title": None, "lines": []}]
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if has_receipt_headings and stripped in receipt_headings:
            sections.append({"title": stripped[3:].strip(), "lines": []})
        elif not has_receipt_headings and stripped.startswith("## "):
            sections.append({"title": stripped[3:].strip(), "lines": []})
        elif not has_receipt_headings and stripped.startswith("# "):
            sections.append({"title": stripped[2:].strip(), "lines": []})
        else:
            sections[-1]["lines"].append(raw_line.rstrip())
    return sections


CLAIM_HEADER_RE = re.compile(
    r"^- `(?P<claim_id>[^`]+)` validation=(?P<validation_status>\S+) "
    r"lifecycle=(?P<lifecycle_status>\S+) relation=(?P<relation_to_target>\S+) "
    r"kind=(?P<kind>\S+) depth=(?P<reduction_depth>\S+) root_impact=(?P<root_impact>\S+)"
)
ARTIFACT_HEADER_RE = re.compile(
    r"^- `(?P<artifact_id>[^`]+)` type=(?P<artifact_type>\S+) "
    r"producer=(?P<producer_role>\S+) revision=(?P<state_revision>.*)"
)


def _render_claim_section_latex(section_lines: List[str]) -> List[str]:
    preamble, claims = _parse_claim_section(section_lines)
    lines = _render_claim_section_preamble(preamble)
    if claims:
        for claim in claims:
            lines.extend(_render_claim_latex(claim))
    elif any(line.strip() == "None." for line in section_lines):
        lines.append("None.")
    return lines


def _render_claim_section_preamble(section_lines: List[str]) -> List[str]:
    lines: List[str] = []
    for raw_line in section_lines:
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("Count:"):
            lines.append(rf"\textbf{{{_latex_inline(stripped)}}}")
        else:
            lines.extend(_render_freeform_lines([raw_line], heading_level=2))
    return lines


def _parse_claim_section(section_lines: List[str]) -> tuple[List[str], List[Dict[str, Any]]]:
    preamble: List[str] = []
    claims: List[Dict[str, Any]] = []
    current_claim: Dict[str, Any] | None = None
    current_artifact: Dict[str, Any] | None = None
    in_artifact_content = False

    def flush_claim() -> None:
        nonlocal current_claim, current_artifact, in_artifact_content
        if current_claim is not None:
            claims.append(current_claim)
        current_claim = None
        current_artifact = None
        in_artifact_content = False

    for raw_line in section_lines:
        stripped = raw_line.strip()
        claim_match = CLAIM_HEADER_RE.match(stripped)
        if claim_match:
            flush_claim()
            current_claim = {
                **claim_match.groupdict(),
                "statement": "",
                "conditions": "",
                "parent_claims": "",
                "evidence_artifacts": "",
                "tags": "",
                "proof_artifacts": [],
                "extra_lines": [],
            }
            continue

        if current_claim is None:
            preamble.append(raw_line)
            continue

        if stripped.startswith("Statement:"):
            current_claim["statement"] = stripped[len("Statement:") :].strip()
            current_artifact = None
            in_artifact_content = False
        elif stripped.startswith("Conditions:"):
            current_claim["conditions"] = stripped[len("Conditions:") :].strip()
            current_artifact = None
            in_artifact_content = False
        elif stripped.startswith("Parent claims:"):
            current_claim["parent_claims"] = stripped[len("Parent claims:") :].strip()
            current_artifact = None
            in_artifact_content = False
        elif stripped.startswith("Evidence artifacts:"):
            current_claim["evidence_artifacts"] = stripped[len("Evidence artifacts:") :].strip()
            current_artifact = None
            in_artifact_content = False
        elif stripped.startswith("Tags:"):
            current_claim["tags"] = stripped[len("Tags:") :].strip()
            current_artifact = None
            in_artifact_content = False
        elif stripped.startswith("Proof material:"):
            current_artifact = None
            in_artifact_content = False
        else:
            artifact_match = ARTIFACT_HEADER_RE.match(stripped)
            if artifact_match:
                current_artifact = {
                    **artifact_match.groupdict(),
                    "summary": "",
                    "path": "",
                    "content_lines": [],
                    "extra_lines": [],
                }
                current_claim["proof_artifacts"].append(current_artifact)
                in_artifact_content = False
            elif current_artifact is not None and stripped.startswith("Summary:"):
                current_artifact["summary"] = stripped[len("Summary:") :].strip()
                in_artifact_content = False
            elif current_artifact is not None and stripped.startswith("Path:"):
                current_artifact["path"] = stripped[len("Path:") :].strip()
                in_artifact_content = False
            elif current_artifact is not None and stripped.startswith("Content:"):
                in_artifact_content = True
            elif current_artifact is not None and in_artifact_content:
                current_artifact["content_lines"].append(raw_line)
            elif current_artifact is not None and stripped:
                current_artifact["extra_lines"].append(stripped)
            elif stripped:
                current_claim["extra_lines"].append(stripped)

    flush_claim()
    return preamble, claims


def _render_claim_latex(claim: Mapping[str, Any]) -> List[str]:
    claim_id = str(claim.get("claim_id", ""))
    kind = _human_label(str(claim.get("kind", "claim")))
    status = (
        f"Certification: {_human_label(str(claim.get('validation_status', 'unknown')))}; "
        f"relation to target: {_human_label(str(claim.get('relation_to_target', 'unknown')))}"
    )
    lines = [
        rf"\claimheading{{{_latex_inline(kind + ' ' + claim_id, smart_math=False)}}}{{{_latex_inline(status, smart_math=False)}}}"
    ]
    statement = str(claim.get("statement", "")).strip()
    if statement:
        lines.append(r"\fieldlabel{Statement}")
        lines.extend(_render_freeform_lines(_expand_inline_markdown(statement).splitlines(), heading_level=4))
    conditions = str(claim.get("conditions", "")).strip()
    if conditions:
        lines.append(rf"\fieldlabel{{Conditions}}{_latex_inline(conditions)}")
    extra_lines = [str(line) for line in claim.get("extra_lines", []) if str(line).strip()]
    if extra_lines:
        lines.extend(_render_freeform_lines(extra_lines, heading_level=4))
    proof_artifacts = list(claim.get("proof_artifacts", []))
    if proof_artifacts:
        lines.append(r"\fieldlabel{Proof}")
        lines.append(r"\begin{proofmaterial}")
        for artifact in proof_artifacts:
            lines.extend(_render_artifact_latex(artifact))
        lines.append(r"\end{proofmaterial}")
    return lines


def _render_artifact_latex(artifact: Mapping[str, Any]) -> List[str]:
    artifact_meta = (
        f"{_human_label(str(artifact.get('artifact_type', 'artifact')))}; "
        f"{_human_label(str(artifact.get('producer_role', 'unknown')))}; "
        f"revision {artifact.get('state_revision', '')}"
    )
    lines = [
        rf"\artifactheading{{Evidence source}}{{{_latex_inline(artifact_meta, smart_math=False)}}}"
    ]
    summary = str(artifact.get("summary", "")).strip()
    if summary:
        lines.append(rf"\textbf{{Summary.}} {_latex_inline(summary)}")
    extra_lines = [str(line) for line in artifact.get("extra_lines", []) if str(line).strip()]
    if extra_lines:
        lines.extend(_render_freeform_lines(extra_lines, heading_level=5))
    content_lines = [str(line).rstrip() for line in artifact.get("content_lines", [])]
    if any(line.strip() for line in content_lines):
        lines.append(r"\begin{proofexcerpt}")
        lines.extend(_render_freeform_lines(content_lines, heading_level=5))
        lines.append(r"\end{proofexcerpt}")
    return lines


def _render_freeform_lines(raw_lines: Iterable[str], *, heading_level: int) -> List[str]:
    lines: List[str] = []
    paragraph: List[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            lines.append(_latex_inline(" ".join(paragraph)))
            paragraph.clear()

    for raw_line in raw_lines:
        for expanded_line in _expand_inline_markdown(raw_line.rstrip()).splitlines():
            stripped = expanded_line.strip()
            if not stripped:
                flush_paragraph()
                continue
            if stripped.startswith("### "):
                flush_paragraph()
                lines.append(_latex_section_command(stripped[4:].strip(), heading_level + 2))
            elif stripped.startswith("## "):
                flush_paragraph()
                lines.append(_latex_section_command(stripped[3:].strip(), heading_level + 1))
            elif stripped.startswith("# "):
                flush_paragraph()
                lines.append(_latex_section_command(stripped[2:].strip(), heading_level))
            elif stripped.startswith("- "):
                flush_paragraph()
                lines.append(rf"\receiptbullet{{{_latex_inline(stripped[2:].strip())}}}")
            else:
                ordered_match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
                if ordered_match:
                    flush_paragraph()
                    number, item = ordered_match.groups()
                    lines.append(rf"\receiptbullet{{{_latex_inline(number + '. ' + item)}}}")
                else:
                    paragraph.append(stripped)
    flush_paragraph()
    return lines


def _expand_inline_markdown(value: str) -> str:
    text = value
    text = re.sub(r"(?<!^)\s+(#{1,3}\s+)", r"\n\n\1", text)
    text = re.sub(r"\s+(\d+\.\s+)", r"\n\1", text)
    return text


def _latex_section_command(title: str, level: int) -> str:
    command = "section" if level <= 1 else "subsection" if level == 2 else "subsubsection"
    if level >= 4:
        return rf"\paragraph{{{_latex_inline(title)}}}"
    return rf"\{command}{{{_latex_inline(title)}}}"


def _human_label(value: str) -> str:
    return value.replace("_", " ").replace("-", " ")


def _claim_status_card(
    claim: Mapping[str, Any],
    *,
    artifact_lookup: Mapping[str, Mapping[str, Any]],
    max_statement_chars: int | None,
    max_proof_chars: int | None,
) -> Dict[str, Any]:
    statement = _one_line(_field(claim, "statement", ""))
    if max_statement_chars is not None:
        statement = _compact_text(statement, max_statement_chars)
    evidence_artifact_ids = _json_field(claim, "evidence_artifact_ids_json")
    claim_id = str(_field(claim, "claim_id", ""))
    validation_status = str(_field(claim, "validation_status", "unknown"))
    proof_artifacts = []
    if claim_id != "root" and validation_status in VERIFIED_SIDE_LEMMA_STATUSES:
        proof_artifacts = _proof_artifacts(evidence_artifact_ids, artifact_lookup, max_chars=max_proof_chars)
    return {
        "claim_id": claim_id,
        "kind": str(_field(claim, "kind", "claim")),
        "statement": statement,
        "validation_status": validation_status,
        "lifecycle_status": str(_field(claim, "lifecycle_status", "unknown")),
        "relation_to_target": _claim_relation(claim),
        "root_impact": _float_field(claim, "root_impact"),
        "reduction_depth": _int_field(claim, "reduction_depth"),
        "parent_ids": _json_field(claim, "parent_ids_json"),
        "conditions": _json_field(claim, "conditions_json"),
        "evidence_artifact_ids": evidence_artifact_ids,
        "proof_artifacts": proof_artifacts,
        "tags": _json_field(claim, "tags_json"),
    }


def _format_claim_block(claim: Mapping[str, Any]) -> List[str]:
    lines = [
        (
            f"- `{claim['claim_id']}` validation={claim['validation_status']} "
            f"lifecycle={claim['lifecycle_status']} relation={claim['relation_to_target']} "
            f"kind={claim['kind']} depth={claim['reduction_depth']} root_impact={claim['root_impact']}"
        ),
        f"  Statement: {claim['statement']}",
    ]
    if claim["conditions"]:
        lines.append(f"  Conditions: {json_dumps(claim['conditions'])}")
    if claim["parent_ids"]:
        lines.append(f"  Parent claims: {json_dumps(claim['parent_ids'])}")
    if claim["evidence_artifact_ids"]:
        lines.append(f"  Evidence artifacts: {json_dumps(claim['evidence_artifact_ids'])}")
    if claim.get("proof_artifacts"):
        lines.append("  Proof material:")
        for artifact in claim["proof_artifacts"]:
            lines.extend(_format_artifact_block(artifact))
    if claim["tags"]:
        lines.append(f"  Tags: {json_dumps(claim['tags'])}")
    return lines


def _format_artifact_block(artifact: Mapping[str, Any]) -> List[str]:
    lines = [
        (
            f"  - `{artifact['artifact_id']}` type={artifact['artifact_type']} "
            f"producer={artifact['producer_role']} revision={artifact['state_revision']}"
        )
    ]
    if artifact.get("content_summary"):
        lines.append(f"    Summary: {artifact['content_summary']}")
    if artifact.get("path"):
        lines.append(f"    Path: {artifact['path']}")
    if artifact.get("content"):
        lines.extend(["    Content:", ""])
        lines.append(str(artifact["content"]).rstrip())
        lines.append("")
    elif artifact.get("missing"):
        lines.append("    Content: [artifact not found in current proof state]")
    return lines


def _claim_relation(claim: Mapping[str, Any]) -> str:
    tags = {str(tag).lower() for tag in _json_field(claim, "tags_json")}
    for relation in ("stronger", "equivalent", "partial", "conditional", "weaker", "method", "orthogonal"):
        if relation in tags or f"relation:{relation}" in tags:
            return relation
    if _json_field(claim, "conditions_json"):
        return "conditional"
    return "partial"


def _receipt_sort_key(claim: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        claim["claim_id"] != "root",
        int(claim["reduction_depth"]),
        -float(claim["root_impact"]),
        claim["claim_id"],
    )


def _counts(cards: Iterable[Mapping[str, Any]], key: str) -> Dict[str, int]:
    return dict(sorted(Counter(str(card.get(key, "unknown")) for card in cards).items()))


def _artifact_lookup(artifacts: Iterable[Mapping[str, Any]] | None) -> Dict[str, Mapping[str, Any]]:
    lookup: Dict[str, Mapping[str, Any]] = {}
    for artifact in artifacts or []:
        artifact_id = str(_field(artifact, "artifact_id", ""))
        if artifact_id:
            lookup[artifact_id] = artifact
    return lookup


def _proof_artifacts(
    evidence_artifact_ids: Iterable[Any],
    artifact_lookup: Mapping[str, Mapping[str, Any]],
    *,
    max_chars: int | None,
) -> List[Dict[str, Any]]:
    proof_artifacts: List[Dict[str, Any]] = []
    for raw_id in evidence_artifact_ids:
        artifact_id = str(raw_id)
        artifact = artifact_lookup.get(artifact_id)
        if artifact is None:
            proof_artifacts.append(
                {
                    "artifact_id": artifact_id,
                    "artifact_type": "unknown",
                    "producer_role": "unknown",
                    "state_revision": "",
                    "content_summary": "",
                    "path": "",
                    "content": "",
                    "missing": True,
                }
            )
            continue
        proof_artifacts.append(
            {
                "artifact_id": artifact_id,
                "artifact_type": str(_field(artifact, "artifact_type", "")),
                "producer_role": str(_field(artifact, "producer_role", "")),
                "state_revision": _field(artifact, "state_revision", ""),
                "content_summary": _one_line(_field(artifact, "content_summary", "")),
                "path": str(_field(artifact, "path", "")),
                "content": _artifact_content(_field(artifact, "path", ""), max_chars=max_chars),
                "missing": False,
            }
        )
    return proof_artifacts


def _artifact_content(path_value: Any, *, max_chars: int | None) -> str:
    path = Path(str(path_value or ""))
    if not path.exists() or not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if max_chars is None:
        return text
    return _compact_text(text, max_chars)


def _field(row: Mapping[str, Any], key: str, default: Any = "") -> Any:
    if isinstance(row, Mapping):
        return row.get(key, default)
    try:
        return row[key]
    except (IndexError, KeyError, TypeError):
        return default


def _json_field(row: Mapping[str, Any], key: str) -> List[Any]:
    value = _field(row, key, "[]")
    parsed = json_loads(value)
    return parsed if isinstance(parsed, list) else [parsed]


def _float_field(row: Mapping[str, Any], key: str) -> float:
    try:
        return float(_field(row, key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _int_field(row: Mapping[str, Any], key: str) -> int:
    try:
        return int(_field(row, key, 0))
    except (TypeError, ValueError):
        return 0


def _one_line(value: Any) -> str:
    return " ".join(str(value or "").split())


def _compact_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 24)].rstrip() + " ... [truncated]"


def _compile_latex(tex_path: Path, pdf_path: Path) -> Dict[str, str]:
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        return {"pdf_status": "pdflatex_missing", "pdf_path": ""}
    with tempfile.TemporaryDirectory(prefix="albilich_receipt_latex_") as tmp:
        tmpdir = Path(tmp)
        result: subprocess.CompletedProcess[str] | None = None
        try:
            for _ in range(2):
                result = subprocess.run(
                    [
                        pdflatex,
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        "-output-directory",
                        str(tmpdir),
                        str(tex_path),
                    ],
                    cwd=str(tmpdir),
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=LATEX_TIMEOUT_SECONDS,
                    check=False,
                )
                if result.returncode != 0:
                    break
        except (OSError, subprocess.TimeoutExpired) as exc:
            log_path = tex_path.with_suffix(".latex.log")
            log_path.write_text(str(exc), encoding="utf-8")
            return {"pdf_status": "compile_error", "pdf_path": "", "latex_log_path": str(log_path)}
        output_pdf = tmpdir / f"{tex_path.stem}.pdf"
        if result and result.returncode == 0 and output_pdf.exists():
            shutil.copyfile(output_pdf, pdf_path)
            return {"pdf_status": "compiled", "pdf_path": str(pdf_path)}
        log_path = tex_path.with_suffix(".latex.log")
        log_path.write_text((result.stdout if result else "") or "", encoding="utf-8")
        return {"pdf_status": "compile_failed", "pdf_path": "", "latex_log_path": str(log_path)}


MATH_SYMBOL_RE = (
    r"(?:Z/[A-Za-z0-9]+Z|P\d+|\d+[A-Za-z]+|\d+|[a-z]Theta|"
    r"Theta|theta|delta|lambda|mu|[A-Za-z]{2,}\([^()\n]*\)|"
    r"(?:deg|det|gcd|rank|dim)(?![A-Za-z_])|"
    r"[A-Za-z]+(?:[_^](?:\{[^}]+\}|[A-Za-z0-9*\\]+))+(?:\([^()\n]*\))?|"
    r"[A-Za-z](?:\d+)?(?![A-Za-z_])|\\[A-Za-z]+"
    r"(?:\([^()\n]*\))?)"
)
MATH_PRODUCT_RE = rf"{MATH_SYMBOL_RE}(?:\s*(?:\*|tensor)?\s+{MATH_SYMBOL_RE}){{0,4}}"

MATH_SPAN_PATTERNS = [
    re.compile(rf"(?<![\w\\])\|{MATH_SYMBOL_RE}\|\s*(?:~=|>=|<=|=)\s*-?{MATH_PRODUCT_RE}"),
    re.compile(rf"(?<![\w\\]){MATH_SYMBOL_RE}(?:\s*(?:~=|=)\s*{MATH_SYMBOL_RE}){{1,4}}"),
    re.compile(
        rf"(?<![\w\\])(?:deg\s+)?{MATH_PRODUCT_RE}"
        rf"\s*(?:~=|>=|<=|=|->|<-|congruent to)\s*-?{MATH_PRODUCT_RE}"
        rf"(?:\s+(?:mod|modulo)\s+{MATH_SYMBOL_RE})?"
    ),
    re.compile(rf"(?<![\w\\])deg\s+{MATH_PRODUCT_RE}(?:\s+(?:mod|modulo)\s+{MATH_SYMBOL_RE})?"),
    re.compile(r"(?<![\w\\])(?:Br|Pic|Mor|Hom|Spec|det|deg|gcd|rank|dim|H)(?:_[A-Za-z0-9{}]+|\^[A-Za-z0-9{}]+)?\([^()\n]*\)"),
    re.compile(r"(?<![\w\\])SU_[A-Za-z0-9{}]+\([^()\n]*\)"),
    re.compile(r"(?<![\w\\])(?:[A-Za-z][A-Za-z0-9]*|\\[A-Za-z]+)(?:(?:[_^](?:\{[^}]+\}|[A-Za-z0-9*\\]+)))+(?:\([^()\s]*\))?"),
    re.compile(r"(?<![\w\\])(?:Z/[A-Za-z0-9]+Z|P\d+|Theta|delta|lambda|mu_[A-Za-z0-9{}]+)(?![\w\\])"),
]


def _latex_inline(value: str, *, smart_math: bool = True) -> str:
    text = _latex_ascii(value)
    pieces = re.split(r"(`[^`]*`|\$[^$]+\$|\\\((?:.|\n)*?\\\)|\\\[(?:.|\n)*?\\\])", text)
    rendered: List[str] = []
    for piece in pieces:
        if not piece:
            continue
        if len(piece) >= 2 and piece.startswith("`") and piece.endswith("`"):
            rendered.append(r"\texttt{" + _latex_escape(piece[1:-1]) + "}")
        elif _is_explicit_math_piece(piece):
            rendered.append(piece)
        elif smart_math:
            rendered.append(_latex_mixed_prose_math(piece))
        else:
            rendered.append(_latex_escape(piece))
    return "".join(rendered)


def _is_explicit_math_piece(value: str) -> bool:
    return (
        (len(value) >= 2 and value.startswith("$") and value.endswith("$"))
        or (value.startswith(r"\(") and value.endswith(r"\)"))
        or (value.startswith(r"\[") and value.endswith(r"\]"))
    )


def _latex_mixed_prose_math(value: str) -> str:
    spans = _math_spans(value)
    if not spans:
        return _latex_escape(value)
    rendered: List[str] = []
    cursor = 0
    for start, end in spans:
        if start > cursor:
            rendered.append(_latex_escape(value[cursor:start]))
        rendered.append(_latex_math(value[start:end]))
        cursor = end
    if cursor < len(value):
        rendered.append(_latex_escape(value[cursor:]))
    return "".join(rendered)


def _math_spans(value: str) -> List[tuple[int, int]]:
    candidates: List[tuple[int, int]] = []
    for pattern in MATH_SPAN_PATTERNS:
        for match in pattern.finditer(value):
            start, end = _trim_math_span(value, match.start(), match.end())
            if start < end and not _skip_math_candidate(value[start:end]):
                candidates.append((start, end))
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    spans: List[tuple[int, int]] = []
    covered_until = -1
    for start, end in candidates:
        if start < covered_until:
            continue
        spans.append((start, end))
        covered_until = end
    return spans


def _trim_math_span(value: str, start: int, end: int) -> tuple[int, int]:
    while start < end and value[start].isspace():
        start += 1
    trimmed = True
    while trimmed:
        trimmed = False
        for word in ("If", "if", "Then", "then", "and", "or", "one", "has", "so", "hence"):
            prefix = f"{word} "
            if value[start:end].startswith(prefix):
                start += len(prefix)
                trimmed = True
                break
    while end > start and value[end - 1] in ".,;:":
        end -= 1
    return start, end


def _skip_math_candidate(candidate: str) -> bool:
    text = candidate.strip()
    if not text:
        return True
    lowered = text.lower()
    if re.match(r"^(validation|lifecycle|relation|kind|depth|root_impact|revision|producer|type)=", lowered):
        return True
    if "-" in text and not any(marker in text for marker in ("->", "<-", ">=", "<=", "~=", "=")):
        return True
    return False


def _latex_math(value: str) -> str:
    text = _normalize_math_text(value.strip())
    return r"\ensuremath{" + text + "}"


def _normalize_math_text(value: str) -> str:
    text = value
    text = re.sub(r"\bcongruent to\b", r"\\equiv", text)
    text = text.replace("~=", r"\simeq ")
    text = text.replace(">=", r"\ge ")
    text = text.replace("<=", r"\le ")
    text = text.replace("->", r"\to ")
    text = text.replace("<-", r"\leftarrow ")
    text = re.sub(r"\bZ/([A-Za-z0-9]+)Z\b", r"\\mathbb{Z}/\1\\mathbb{Z}", text)
    text = re.sub(r"\bP(\d+)\b", r"\\mathbb{P}^{\1}", text)
    text = re.sub(r"\bO_C\b", r"\\mathcal{O}_C", text)
    text = re.sub(r"\bc(\d+)\b", r"c_{\1}", text)
    text = re.sub(r"\b([a-z])0\b", r"\1_0", text)
    text = re.sub(r"\bSU_([A-Za-z0-9{}]+)", r"\\operatorname{SU}_{\1}", text)
    for name in ("Br", "Pic", "Mor", "Hom", "Spec"):
        text = re.sub(rf"\b{name}\s*(?=[_^]|\()", rf"\\operatorname{{{name}}}", text)
    for name in ("det", "deg", "gcd", "dim"):
        text = re.sub(rf"(?<!\\)\b{name}\b", lambda _match, value=rf"\{name}": value, text)
    text = re.sub(r"(?<!\\)\brank\b", r"\\operatorname{rank}", text)
    text = re.sub(r"(?<!\\)\bmu_", lambda _match: r"\mu_", text)
    text = re.sub(r"(?<!\\)Theta", lambda _match: r"\Theta", text)
    text = re.sub(r"(?<!\\)theta", lambda _match: r"\theta", text)
    replacements = {
        "delta": r"\delta",
        "lambda": r"\lambda",
        "mu": r"\mu",
        "pi": r"\pi",
    }
    for word, latex in replacements.items():
        text = re.sub(rf"(?<!\\)\b{word}\b", lambda _match, value=latex: value, text)
    text = re.sub(r"\^([A-Za-z]{2,})", r"^{\\mathrm{\1}}", text)
    text = re.sub(r"(?<!\^)\*(?=[A-Za-z0-9(])", r"\\cdot ", text)
    text = re.sub(r"\bmodulo\b", r"\\bmod", text)
    text = re.sub(r"\bmod\b", r"\\bmod", text)
    text = re.sub(r"\btensor\b", r"\\otimes", text)
    text = re.sub(r"\s+x\s+", r" \\times ", text)
    return text


def _latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def _latex_ascii(value: str) -> str:
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "--",
        "\u2014": "---",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": "``",
        "\u201d": "''",
        "\u2026": "...",
        "\u2265": r"$\ge$",
        "\u2264": r"$\le$",
        "\u2192": r"$\to$",
        "\u2190": r"$\leftarrow$",
        "\u00d7": r"$\times$",
    }
    return "".join(replacements.get(char, char) for char in value)


def _latex_path(value: str) -> str:
    return _latex_ascii(value).replace("{", "").replace("}", "")

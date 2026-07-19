# Writing Harness Plugin: the Phase2 Writing Gate

How the math-writing harness is wired into the Albilich phase2 engine
(`agents/generation/phase2/`). It has two entry paths:

1. The publication gate follows an internally verified `final_proof` and
   authors a standalone LaTeX `final_paper`. Mathematical correctness review
   is out of scope here because the proof harness already verified the
   certificate.
2. `revise-paper` ingests an externally authored `.md` or `.tex` manuscript as
   a `revision_document` and runs writing-only revision. The submitted source
   is explicitly **not** proof evidence and receives no mathematical
   verification claim from this harness.

Both paths run deterministic checks followed by three independent audits, in
order: terminology, introduction, and whole-paper exposition. The
introduction has the highest quality-control standard. Uncertain terminology
never triggers an agent guess: it raises a blocking human-consultation item in
the steering dashboard. No document ships with an unresolved blocker or major
writing debt; exhausted automation pauses for human resolution.

## Source of truth

- **Rubric**: `math-writing-harness/rubric/` (five layer files `L1`-`L5` plus
  `SCHEMA.md`). Phase2 modifies it only to add the `L5-PAPER-*` bullets in the
  "Paper deliverable (final_paper)" subsection of `L5-formatting.md`. It is
  compiled at runtime by `agents/generation/phase2/writing/rubric.py`
  (`load_rubric`, `rules_for_critic`) into flat `Rule` records with `rule_id`,
  `severity` (`blocker|major|minor|nit`), `checkability`
  (`lint|llm|verify|meta`), and `owner_critic`.
- **Deterministic layer**: `agents/generation/phase2/writing/linter.py` —
  `run_residue_scan(text)` (the always-blocker generation-residue scan, rule
  `L1-CITE-03`), `run_all(text)` (every deterministic rule),
  `run_slop_lint(text)` (the anti-slop/house-rules layer: the deterministic
  subset of `L4-SLOP-01..12` plus `L4-HOUSE-03` plus the HARD house rules
  `L4-HOUSE-07` (section openers: every section's first paragraph carries a
  sentence beginning "In this section, we" / "In this appendix, we";
  References/Acknowledgment/bibliography exempt), `L4-HOUSE-08` (banned
  habitual "we" collocations: we recall / we record / we now show / we now
  prove / we now turn / we begin by / we start by / we note that / we observe
  that), `L4-HOUSE-09` (stub sections: a `\section` with fewer than 120 prose
  words — math/displays/tables/figures excluded from the count), and
  `L4-HOUSE-10` (fragmentation: >= 2 main-body stub sections or > 2.5 sections
  per 1000 prose words), all `major` so they force the deterministic revision
  through debts — never attach-rejections; plus `L4-HOUSE-11` (bullet
  narration: itemize/enumerate lists of 4+ prose items of 15+ words each, and
  list density above 1 list per 2 sections; `minor`); LaTeX-aware — math-mode
  content is never scanned; sources `AI-SLOP` + `HOUSE` in
  `math-writing-harness/references/fetched/`), and
  `run_paper_lint(text)` (the `final_paper`-only paper-register rules
  `L5-PAPER-01/02/03`, all blockers). All return
  `Finding(rule_id, severity, line, excerpt, message)`.
- **Paper and revision contracts**:
  `agents/generation/phase2/writing/paper_contract.py` —
  `PAPER_CONTRACT` (the verbatim writer directive for paper authoring: journal
  register, mandatory amsart structure, faithfulness-to-certificate rules, the
  register wall), `TERMINOLOGY_EDITOR_DIRECTIVE`,
  `INTRODUCTION_EDITOR_DIRECTIVE`, and `EDITOR_DIRECTIVE` (the final
  whole-paper re-audit, at most 12 located actionable findings). The shared
  `WRITING_STYLE_CORE` requires standard literature terminology, justified
  coinages, a coherent big-picture introduction, and a causal proof overview.
  Edit these standards only in this module.
- **External revision ingestion**:
  `agents/generation/phase2/writing/revision.py` — validates `.md`/`.tex`,
  copies the source into immutable run storage, records its original SHA-256
  and format, and labels its mathematical status
  `not_verified_by_writing_harness`.
- **This plugin** (the wiring, owned by phase2): scheduler gate, `writing_critic`
  role, patch guards, context isolation, and reporting.

## The gate's state machine

Scheduler entry points are `_writing_gate_action` for an internally generated
paper and `_external_writing_revision_action` for an ingested manuscript. The
certificate on the internal path remains private proof evidence: it is never
linted, reviewed, or revised by this gate. The external path has no
certificate and bypasses proof research, integration, and proof-status gates.

1. **Author or ingest.** On the internal path, root integration plus a
   `final_proof` and no `final_paper` dispatches one paper-authoring writer
   session under `PAPER_CONTRACT`. The resulting standalone LaTeX source is
   stored as `.tex` and compiled directly at attach time. On the external
   path, run
   `python -m agents.generation.phase2.cli revise-paper <file.md|file.tex>` and
   then execute the printed command with
   `--research-mode writing_revision --completion-policy publication_ready`.
   Ingestion creates `revision_document_root`, records the original file hash,
   and does not convert `.md` to `.tex` or vice versa.
2. **Deterministic checks.** Every document receives `run_all` plus
   `run_slop_lint`; findings become writing debts and stale deterministic
   debts close when no longer reproduced. Internal `final_paper` artifacts
   additionally receive `run_paper_lint` and the standalone LaTeX compile
   gate. External manuscripts may depend on a venue class, bibliography, or
   included files, so a sidecar compile outcome is informative but does not
   block revision. Open blocker/major debts dispatch a diff-minimal writer
   revision whose packet enumerates every debt as a located required-fix
   checklist. Deterministic-only revisions use a separate cap of two.
3. **Terminology audit.** The `terminology_editor` inventories technical
   names and checks them against the manuscript's citations, supplied
   literature, and bounded live search when enabled. Standard terminology is
   preferred. A coinage must be precisely defined and explain why the nearest
   standard term is inadequate. Ambiguous evidence produces a blocking
   `L3-TERM-03` debt containing the exact marker
   `HUMAN CONSULTATION REQUIRED:`.
4. **Introduction audit.** The `introduction_editor` treats the abstract and
   introduction as the highest-control prose in the manuscript. It requires
   one natural big-picture story, accurate scope, and a causal proof
   architecture that explains why the ingredients enter and how they combine.
   A theorem inventory, section list, or chronological work log is a major
   failure.
5. **Whole-paper audit.** The `editor` checks publishable exposition, repeats
   the introduction and terminology checks independently, and may file at
   most 12 located, actionable findings. Mathematical correctness review is
   out of scope: internal papers already have a verified certificate, while
   external documents make no verification claim. Each required lens is spent
   once across document revisions, but a document revised after the initial
   whole-paper pass receives a final editor confirmation before shipping. The count is the maximum of completed
   `review_writing` runs and corresponding `writing_review` artifacts, which
   prevents livelock if a critic omits one record.
6. **Revisions and human steering.** Review findings trigger focused,
   voice-preserving revisions. The review-driven cap is three, allowing one
   revision per independent audit without resetting completed lenses. An
   unanswered terminology marker returns terminal mode `await_human`, creates
   a deduplicated dashboard steering blocker, and resumes after the expert's
   answer. If automation is otherwise exhausted while a blocker or major debt
   remains, the scheduler also pauses for human quality resolution. It never
   silently ships unresolved major debt.
7. **Non-bypassable defects.** Generation residue (`L1-CITE-03`) and, for an
   internal paper, LaTeX compile failures continue forcing revisions past the
   normal caps.

Convergence (`stop_solved`) requires all three audits and no gating debt.
Internal-paper outcome identity remains defined by the `final_proof`.
External revision reports `writing_revision_complete`, relation to theorem
target `not_applicable`, and no proved statement.

## The paper deliverable

- Artifact type `final_paper`, **writer-only** (`ARTIFACT_PRODUCER_ROLES`).
  Its `content` is the entire article source; it must compile standalone with
  `pdflatex`.
- **Path-based delivery (preferred).** Authoring LaTeX inside a JSON `content`
  string invites backslash over-escaping, so the writer instead writes the
  complete `.tex` via shell to `state_dir/artifacts/staging/<artifact_id>.tex`
  (already inside the `artifacts/` root that `_validated_artifact_path`
  permits; the manifest names it as `writing_paper_packet.staging_dir` /
  `writing_revision_packet.staging_dir` and allows it in
  `local_search_policy.allowed_local_evidence_paths`) and attaches with
  `{"op": "attach_artifact", "artifact_type": "final_paper", "path": <staging
  path>}` and **no `content` field**. The patch guard loads the staged file
  (capped at `WRITER_PATH_ATTACH_MAX_BYTES`, 2 MB), runs the full writer guard
  chain on it exactly as for inline content, then copies it to the standard
  `artifacts/<artifact_id>.tex` location — the recorded artifact never points
  at the mutable staging file. This applies to all
  `WRITER_PATH_ATTACH_ARTIFACT_TYPES`; inline `content` remains an accepted
  fallback, and non-writer path attaches keep their guard-exempt semantics.
- Deterministic paper-register rules (`run_paper_lint`, rubric section
  "Paper deliverable (final_paper)" in `L5-formatting.md`):
  - `L5-PAPER-01` markdown residue in LaTeX (heading lines, triple-backtick
    fences, `* ` bullets, `[text](url)` links, `**bold**`), outside verbatim
    environments — blocker;
  - `L5-PAPER-02` internal system register before the first `\appendix`
    (`art_*` identifiers; word-boundary "manifest" (not "manifestly"),
    "ledger", "artifact", "proof-state", "verifier report", "writing debt",
    "state revision") — blocker; the Run archive paragraph of Appendix A is
    the only legitimate home;
  - `L5-PAPER-03` missing article structure (`\documentclass`,
    `\begin{abstract}`, a theorem environment, `\begin{proof}`, `\appendix`,
    a bibliography, `\end{document}`) — blocker.

Independent review pass/fail:

- **pass**: each critic attaches `artifact_type="writing_review"` with
  `verdict: "pass"`, its exact lens, the reviewed artifact id, and the state
  revision reviewed. The reviewed artifact may be `final_paper` or
  `revision_document`; legacy lens names remain valid for old runs.
- **fail**: the critic adds one located writing debt per actionable finding
  and may attach `writing_review` with `verdict: "fail"`. Terminology and
  introduction findings use the dedicated `L3-TERM-*` and `L3-INTRO-*` rules.
- Livelock protection is per lens: a completed `review_writing` run counts
  even if the critic attached no review artifact, and an artifact counts even
  if run metrics were omitted.

## External revision deliverable

- Artifact type `revision_document`, initially produced by `human_operator`
  at ingestion and writer-only for subsequent revisions.
- Each revision must name `metadata.revision_of_artifact_id`, preserve
  `metadata.original_sha256`, set `revision_mode: true`, and retain the exact
  `document_format` (`md` or `tex`). The store increments `revision_number`
  and forces `diff_minimal`, `voice_preserving`, and
  `mathematical_status: not_verified_by_writing_harness`.
- The writer attaches a complete document, preferably by a staged path. A
  format conversion or changed original hash is rejected transactionally.
- The revision packet contains the current source, immutable lineage, every
  open writing debt, the exact current file path as allowed evidence, and an
  explicit prohibition on strengthening claims or presenting the result as
  mathematically verified.

## Debt conventions

Findings are debts in the ordinary `debts` table:

| field | value |
| --- | --- |
| `owner_type` | `"artifact"` |
| `owner_id` | the gated `final_paper` or `revision_document` id (legacy stores may carry `final_proof`-owned debts) |
| `debt_type` | `"writing"` |
| `obligation` | `"<rule_id>: <message> (line N)"` (lint debts append a quoted excerpt) |
| `severity` | rubric → debt vocabulary mapping below |

Severity mapping (rubric `blocker|major|minor|nit` → `models.DEBT_SEVERITIES`):
`blocker → blocking` (highest), `major → major`, `minor → minor`,
`nit → minor` (lowest; `nit` has no debt-table equivalent). Only
`blocking`/`major` gate shipping; `minor` debts are ledger-only.

Writers of writing debts:

- **Deterministic lint** (scheduler-owned): written directly by the scheduler
  through the normal patch path with `actor_role="scheduler"` (the same path
  used for system-recorded run metrics), one idempotent sync patch per gate
  pass. Lint debt ids carry the `writing-lint-` prefix and a fingerprint of
  `(artifact, rule_id, line, message)`; only these are auto-closed as stale.
- **LaTeX compile** (scheduler-owned): `writing-compile-` prefix, blocking
  `L5-TEX-05`, one per failed `final_paper`, deterministic id from
  `(artifact, status)`. Self-healing like lint debts (re-added while the
  failure persists, resolved when the shipped revision compiles).
- **LLM critics**: ordinary `add_debt` operations in the critic's patch.
  Critic debts are never auto-closed; the writer resolves them via
  `update_debt` (which now persists `resolution_note` /
  `resolution_evidence_artifact_ids` into `resolution_evidence_json`).

## Lens isolation

Context isolation is enforced twice: in the manifest
(`context_builder._writing_review_packet` + `_apply_writing_lens_isolation`)
and in the session directive (`codex_runner._writing_critic_guidance`). All
lenses receive the full reviewed document in
`manifest.writing_review_packet` (container key `final_proof` — the legacy
field name; `packet.reviewed_artifact_type` says whether it holds the
certificate or the `final_paper`); the rest of the manifest is stripped
(claims/routes/inferences/debts/artifacts/graph_focus/proof_spine emptied,
research packets and ledgers removed).

The scheduler dispatches `terminology_editor`, `introduction_editor`, then
`editor`. The terminology and whole-paper lenses retain the citation ledger
(`manifest.retrieval_cards`, `manifest.theorem_library`) for literature-based
terminology and bibliography checks. The introduction lens receives the
document plus a compact claim/route summary on the internal path, but not the
literature ledger; its job is narrative architecture, not a second research
session. The final editor receives both. All three receive the full reviewed
document, whether `final_paper` or `revision_document`.

The legacy lenses (`confused_reader`: only the paper text;
`skeptical_editor`: paper + brief claim/route summary
(`packet.claim_route_summary`), pedant rules folded in on paper reviews;
`provenance_auditor`: paper + citation/artifact ledger + the certificate
content on paper reviews) keep their prompt branches and isolation rules and
remain valid `metadata.lens` vocabulary, so old review data and resumed runs
stay coherent — but the scheduler never dispatches them. When the reviewed
artifact is a `final_paper` (action `paper_review: true`), each legacy lens
directive additionally gets `PAPER_STANDARD_FOR_CRITICS` appended.

Each lens directive embeds a compact rule subset. The terminology lens gets
`L3-TERM-*`; the introduction lens gets the SELL/INTRO/STORY/SKIM families;
the final editor receives the broad editor/pedant set. Statements are capped
by `WRITING_CRITIC_RULE_LINE_CAP` and rubric parsing is cached per process.

Critics are instructed: report only genuine findings with `rule_id` and a
located obligation; one `add_debt` per finding; attach `writing_review`
`verdict=pass` when there is nothing at blocker/major (do not fail a paper
over taste); never edit the paper.

## Roles, modes, and guards

- `RUN_MODES` includes `"review_writing"` and the terminal pause mode
  `"await_human"`; `NON_VERIFYING_ROLES` includes
  `"writing_critic"` (`phase2/models.py`). `actor_role_for_action`:
  `review_writing → writing_critic`. Model tier: `"writing"` (same as the
  writer). Budget class: `review_writing` joins `write` in
  `budget.VERIFICATION_MODES` so post-integration closure can spend the
  reserve.
- Patch guards (`phase2/patches.py`):
  - `writing_review` may only be attached by `writing_critic`
    (`ARTIFACT_PRODUCER_ROLES`), and `writing_critic` may attach *only*
    `writing_review` (mirrors the strict-verifier restriction).
  - `final_paper` may only be attached by the `writer`
    (`ARTIFACT_PRODUCER_ROLES`).
  - `writing_review` metadata must carry `verdict ∈ {pass, fail}`, a known
    `lens`, and `artifact_reviewed` (a `final_proof`, `final_paper`, or
    `revision_document` id;
    mirrors the verification_report verdict guard).
  - `writing_critic` may not propose any claim/inference/route status
    transition.
  - Writer `final_proof`/`partial_proof_report`/`final_paper`/
    `revision_document` content is
    residue-scanned at patch time (`run_residue_scan`); any hit rejects the
    patch with the rule_id + line + excerpt listed.
  - `final_paper` content additionally runs `run_paper_lint` at patch time
    (`_guard_writer_paper_register`); any `L5-PAPER-01/02/03` finding rejects
    the attach outright with rule + line + excerpt listed — a document that
    trips these is not a paper, so no gate cycle is spent on it. Anti-slop
    findings (`run_slop_lint`) are deliberately **not** patch-time rejections:
    slop flows into writing debts via the gate's lint sync (majors force the
    single revision — that is the intended pressure).
  - `final_paper` content is normalized onto the house LaTeX template at
    attach time (`writing/latex_template.py`, `normalize_paper_template`,
    applied right after the escaping repair): a non-house preamble is
    rewritten to the house package set (geometry 1.25in, ams trio, newpx,
    microtype, booktabs, xcolor + linkblue, hyperref with colored links
    loaded last, `\emergencystretch`, `\numberwithin` after the theorem
    declarations; author-added packages are kept) and every `tabular` is
    converted to canonical booktabs rules (no vertical bars, no `\hline`;
    `\toprule` / header / `\midrule` / body / `\bottomrule`). Deterministic
    and idempotent — layout never depends on model compliance.
  - `final_paper` content is written with a `.tex` extension
    (`ARTIFACT_CONTENT_EXTENSIONS` in `_write_artifact_content`) and compiled
    directly by the attach sidecar (`receipt.compile_latex_artifact`); the
    other writer artifacts keep the markdown→LaTeX conversion sidecar
    (`write_latex_pdf_sidecars`).
  - Debts may be owned by artifacts (`_check_owner_exists` +
    `invariants.validate_conn` both understand `owner_type="artifact"`).

## Budget constants and how to tune

All in `phase2/scheduler.py` unless noted:

The revision budget is split into deterministic and review-driven buckets,
distinguished by the persisted dispatch `search_intent`. Each is counted
separately in `_writing_gate_state`. The bounded internal path uses at most
twelve LLM sessions: authoring, up to two deterministic repairs, up to three
audit-driven revisions, the three required audits, and whole-paper
confirmations after editor-driven revisions. The external path omits authoring.
Residue and internal-paper compile exceptions can exceed these caps because
neither defect may ship. Exhaustion never changes quality policy: it pauses
for human resolution.

| constant | default | meaning |
| --- | --- | --- |
| `MAX_WRITING_GATE_REVISION_CYCLES` | 3 | audit-driven revisions, allowing one focused pass per required lens |
| `MAX_WRITING_GATE_DETERMINISTIC_REVISION_CYCLES` | 2 | deterministic-defect revisions (all blocking debts `writing-lint-`/`writing-compile-`); never consumes the editor allowance |
| `PAPER_EDITOR_MAX_PASSES` | 1 | one required pass per lens, plus one editor pass on the latest revised document |
| `WRITING_GATE_REVIEW_LENSES` | terminology, introduction, editor | required audit order |
| `WRITING_GATE_EDITOR_LENS` | `editor` | compatibility name for the final whole-paper lens |
| `WRITING_GATE_PAPER_INTENT` | `writing_gate_paper` | search_intent of the paper-authoring write pass |
| `WRITING_GATE_BLOCKING_SEVERITIES` | `{blocking, major}` | debt severities that force a revision |
| `WRITING_LINT_SEVERITY_TO_DEBT` | blocker→blocking, major→major, minor/nit→minor | rubric→debt severity mapping |
| `WRITING_GATE_MAX_ARTIFACT_CHARS` | 400 000 | max gated-artifact chars fed to the linter |
| `WRITING_CRITIC_RULE_LINE_CAP` (codex_runner) | 120 | max rubric rules embedded per lens directive |
| `WRITING_PACKET_MAX_ARTIFACT_CHARS` (context_builder) | 200 000 | max document chars embedded in critic/revision/paper packets |

Tuning: raise `MAX_WRITING_GATE_REVISION_CYCLES` only when additional
automated repair is preferable to earlier human escalation. The audit
standards live in the three directives in `writing/paper_contract.py`; new deterministic rules
belong in the rubric + `writing/linter.py` and flow into the gate
automatically through `run_all` (or `run_slop_lint` for anti-slop rules —
debts only, never attach-rejections — or `run_paper_lint` for
`final_paper`-only register rules, which the patch guard also enforces); the
paper's register itself is tuned by editing `writing/paper_contract.py`.

## Reporting

`report.py` adds a "Writing review" section to the phase2 Markdown report:
one line per `writing_review` artifact (lens, verdict, reviewed artifact **and
its artifact type**, state revision), a `Final paper: <artifact_id>
(pdf_status)` line when a `final_paper` exists, open+resolved writing-debt
counts by severity, and the list of unresolved writing debts whenever any
remain. For external revision it also names the current revision document,
source format, revision number, immutable original hash, and
`not_verified_by_writing_harness` status. Internal outcome remains defined by
`final_proof`; external outcome uses the dedicated writing-revision classes.

## Tests

`agents/generation/tests/test_phase2_writing_gate.py`: internal scheduler
dispatch (certificate never linted/reviewed → paper authoring → terminology,
introduction, and whole-paper audits), audit/revision convergence, mandatory
human escalation instead of shipping unresolved major debt, the
residue/compile exceptions past the cap, lint→debt sync including stale closure
and paper-register rules, compile-debt sync and healing, livelock protection,
all patch guards (incl. the `final_paper` paper-register guard, `.tex`
storage, and the real pdflatex compile of the good-paper fixture),
lens-isolation manifest checks (incl. the editor's literature ledger, the
paper-authoring packet, and the legacy provenance auditor's certificate),
mode-guidance smoke tests (all required and legacy lenses), actor-role mapping, and
the report section.
`agents/generation/tests/test_phase2_writing_revision.py`: `.md`/`.tex`
ingestion, CLI wiring, nonverification labeling, ordered audits, review packet
isolation, terminology consultation and steering resume, immutable source
lineage, format preservation, and result classification.
`agents/generation/tests/test_writing_paper_lint.py`: unit coverage for
`run_paper_lint` (positive/negative cases per rule, verbatim exemption,
"manifestly" non-flag, appendix-scoped identifiers).

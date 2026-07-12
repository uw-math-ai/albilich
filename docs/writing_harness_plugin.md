# Writing Harness Plugin: the Phase2 Writing Gate

How the math-writing harness is wired into the albilich phase2 engine
(`agents/generation/phase2/`). The gate sits between "the root theorem is
integrated and a final proof was written" and "the run may conclude
`stop_solved`", and it is **lightweight**: mathematical correctness is
ASSUMED (the main harness verified the certificate), the internal
`final_proof` (the *certificate*) is never linted or reviewed here, and the
gate costs at most **4 LLM sessions in the worst case** — paper authoring (1),
deterministic-defect revision(s) (0–2, typically 0–1), one "editor" exposition
review (1), and at most one editor-debt revision (0–1). No run
concludes solved until the `final_paper` — a standalone LaTeX research
article — is deterministically clean (lint, paper-register rules, LaTeX
compile) and the single editor session has been spent.

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
  subset of `L4-SLOP-01..12` plus `L4-HOUSE-03` plus the two HARD house rules
  `L4-HOUSE-07` (section openers: every section's first paragraph carries a
  sentence beginning "In this section, we" / "In this appendix, we";
  References/Acknowledgment/bibliography exempt) and `L4-HOUSE-08` (banned
  habitual "we" collocations: we recall / we record / we now show / we now
  prove / we now turn / we begin by / we start by / we note that / we observe
  that), both `major` so they force the deterministic revision through debts —
  never attach-rejections; LaTeX-aware — math-mode
  content is never scanned; sources `AI-SLOP` + `HOUSE` in
  `math-writing-harness/references/fetched/`), and
  `run_paper_lint(text)` (the `final_paper`-only paper-register rules
  `L5-PAPER-01/02/03`, all blockers). All return
  `Finding(rule_id, severity, line, excerpt, message)`.
- **Paper contract**: `agents/generation/phase2/writing/paper_contract.py` —
  `PAPER_CONTRACT` (the verbatim writer directive for paper authoring: journal
  register, mandatory amsart structure, faithfulness-to-certificate rules, the
  register wall), `EDITOR_DIRECTIVE` (the single exposition-editor lens
  directive: correctness assumed, publishable-paper standard, at most 12
  located actionable findings), and `PAPER_STANDARD_FOR_CRITICS` (legacy;
  appended to the legacy lens directives when the reviewed artifact is a
  `final_paper`). This is the quality lever; edit the texts only there.
- **This plugin** (the wiring, owned by phase2): scheduler gate, `writing_critic`
  role, patch guards, context isolation, and reporting.

## The gate's state machine (lightweight, ≤4 LLM sessions worst case)

Scheduler entry point: `_writing_gate_action` in `phase2/scheduler.py`, called
only when the root claim is integrated, a `final_proof` exists, and the
post-integration librarian gate declined. The certificate is **internal**:
never linted, never reviewed, never revised by the gate (the patch-time
residue guard on writer artifacts still stands).

1. **Paper authoring (1 session).** Root integrated + `final_proof` exists +
   no `final_paper` → immediately dispatch `mode="write"` with
   `paper_authoring: true` (`search_intent="writing_gate_paper"`). The writer
   receives `manifest.writing_paper_packet` (certificate content, root
   statement, claim/route summary, literature ledger) plus the
   `PAPER_CONTRACT` and attaches exactly one `final_paper` whose `content` IS
   complete LaTeX source. The artifact is stored as `.tex` and compiled
   **directly** at attach time (`receipt.compile_latex_artifact`, no
   markdown→LaTeX conversion); `pdf_status` (+ `latex_log_path` on failure)
   is persisted into the artifact metadata.
2. **Deterministic syncs (free, every pass once a paper exists).**
   - **Lint sync** (in-process, no LLM): `run_all` **plus** `run_slop_lint`
     (anti-slop: slop majors like significance inflation, recap openers, and
     choreography force the revision; slop minors are ledger + editor-visible
     debts) **plus** `run_paper_lint`
     (markdown residue, internal register, article structure) on the latest
     `final_paper`'s LaTeX source; findings become writing debts; recorded
     lint debts that no longer reproduce are resolved as stale (see debt
     conventions). Slop findings are **debts, never attach-rejections** — the
     patch-time guard does not run `run_slop_lint`.
   - **LaTeX-compile sync** (reads the compile outcome the writer's sidecar
     persisted at attach time, no recompile): a paper whose `.tex` did not
     compile (`pdf_status ∈ {compile_failed, compile_error}`) gets a
     **blocking** `L5-TEX-05` writing debt carrying a pdflatex-log excerpt.
     `compiled` (or, with no `pdflatex`, an unassertable `pdflatex_missing`)
     clears any stale compile debt; the raw status is surfaced in the report
     either way.
   - Open blocker/major writing debts dispatch **a writer revision**
     (`mode="write"`, `writing_revision: true` + `paper_revision: true`):
     diff-minimal, the writer re-attaches the COMPLETE revised LaTeX source as
     a new `final_paper` and resolves debts via `update_debt`. The revision
     **budget is split by what forced the revision**: a dispatch whose blocking
     debts are ALL deterministic (debt-id prefixes `writing-lint-` /
     `writing-compile-`) is tagged
     `search_intent="writing_gate_revision_deterministic"` and counts against
     the deterministic cap (`MAX_WRITING_GATE_DETERMINISTIC_REVISION_CYCLES =
     2`); a dispatch addressing any editor/LLM debt is tagged
     `search_intent="writing_gate_revision"` and counts against the editor cap
     (`MAX_WRITING_GATE_REVISION_CYCLES = 1`). Deterministic-defect revisions
     therefore never consume the editor's revision allowance: a run whose only
     revision so far fixed a compile failure can still dispatch one
     editor-debt revision after an editor fail. (Legacy stores recorded every
     revision under `writing_gate_revision`, which resumes with the old,
     stricter accounting.)
3. **Editor review (1 session, total).** Deterministically clean → dispatch
   `mode="review_writing"` (actor: `writing_critic`,
   `critic_lens="editor"`, `paper_review: true`,
   `search_intent="writing_gate_review:editor"`), governed by
   `EDITOR_DIRECTIVE`: exposition only, correctness assumed, at most 12
   located actionable findings. There is **one editor session for the whole
   gate** (`PAPER_EDITOR_MAX_PASSES = 1`), counted as the max of completed
   editor `review_writing` runs and editor `writing_review` artifacts (so a
   critic that attached nothing, or forgot its run metrics, cannot re-open the
   pass — that is also the livelock protection). **Pass** (a `writing_review`
   with `verdict: "pass"`) → the gate opens (`stop_solved`). **Fail** (the
   editor's `add_debt` findings) → the single editor-debt revision, after
   which only the deterministic re-check runs — no second editor pass, no
   lens resets, no free verification pass.
4. **Exceptions past the revision caps.** Generation residue (`L1-CITE-03`)
   and LaTeX-compile failures (`writing-compile-` debts) keep forcing
   revisions regardless of budget — deterministic, cheap fixes that must
   never ship (residue is independently rejected at patch time, see guards).
   With the applicable cap spent and only other blocker/major debts open, the
   gate opens with those debts left recorded in the phase2 report's "Writing
   Review" section.

Convergence (`stop_solved`) fires **only after the gate opens**; the outcome
label is still defined by the `final_proof`.

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

Editor pass/fail:

- **pass**: the editor attaches `artifact_type="writing_review"` with metadata
  `{"verdict": "pass", "lens": "editor", "artifact_reviewed": <final_paper
  id>, "state_revision_reviewed": ...}` (the metadata guard accepts a
  `final_proof` or `final_paper` id as the reviewed artifact, and the legacy
  lens names remain valid vocabulary for old data).
- **fail**: the editor adds writing debts — at most 12, each a located,
  actionable local edit with a suggested rewrite — and may attach a
  `writing_review` with `verdict: "fail"`.
- Livelock protection: a completed editor `review_writing` run counts as the
  editor session even without a review artifact (e.g. a critic that only
  filed minor debts), so a misbehaving critic cannot pin the gate.

## Debt conventions

Findings are debts in the ordinary `debts` table:

| field | value |
| --- | --- |
| `owner_type` | `"artifact"` |
| `owner_id` | the gated `final_paper` id (stores from the legacy two-stage gate may carry `final_proof`-owned debts) |
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

**`editor` is the only lens the scheduler dispatches.** It sees the paper
plus the citation ledger (`manifest.retrieval_cards`,
`manifest.theorem_library`) so it can check that bibliography entries are
real, cited works; its directive is `EDITOR_DIRECTIVE` (correctness assumed
and out of scope; publishable-paper standard; at most 12 located, actionable
findings ranked by importance) and it embeds the skeptical_editor + pedant
rubric rules.

The legacy lenses (`confused_reader`: only the paper text;
`skeptical_editor`: paper + brief claim/route summary
(`packet.claim_route_summary`), pedant rules folded in on paper reviews;
`provenance_auditor`: paper + citation/artifact ledger + the certificate
content on paper reviews) keep their prompt branches and isolation rules and
remain valid `metadata.lens` vocabulary, so old review data and resumed runs
stay coherent — but the scheduler never dispatches them. When the reviewed
artifact is a `final_paper` (action `paper_review: true`), each legacy lens
directive additionally gets `PAPER_STANDARD_FOR_CRITICS` appended.

Each lens directive embeds its rubric rules compactly:
`rules_for_critic(load_rubric(...), lens)` filtered to
`checkability == "llm"`, statements truncated to ~160 chars, capped at
`WRITING_CRITIC_RULE_LINE_CAP = 120` rules (constants in
`phase2/codex_runner.py`; the rubric parse is cached per process).

Critics are instructed: report only genuine findings with `rule_id` and a
located obligation; one `add_debt` per finding; attach `writing_review`
`verdict=pass` when there is nothing at blocker/major (do not fail a paper
over taste); never edit the paper.

## Roles, modes, and guards

- `RUN_MODES` gains `"review_writing"`; `NON_VERIFYING_ROLES` gains
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
    `lens`, and `artifact_reviewed` (a `final_proof` or `final_paper` id;
    mirrors the verification_report verdict guard).
  - `writing_critic` may not propose any claim/inference/route status
    transition.
  - Writer `final_proof`/`partial_proof_report`/`final_paper` content is
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

The revision budget is split into two buckets, distinguished by the dispatch
`search_intent` persisted on the revision run (`writing_gate_revision` for
editor-debt revisions, `writing_gate_revision_deterministic` for revisions
whose blocking debts were all `writing-lint-`/`writing-compile-`); each bucket
is counted separately in `_writing_gate_state`. Total LLM sessions ≤ 4 in the
worst case: authoring + editor + deterministic revision + editor-debt revision
(the deterministic cap admits one further deterministic revision, and the
residue/compile exceptions can exceed any cap — both never ship regardless).

| constant | default | meaning |
| --- | --- | --- |
| `MAX_WRITING_GATE_REVISION_CYCLES` | 1 | the single editor-debt revision (any blocking editor/LLM debt) |
| `MAX_WRITING_GATE_DETERMINISTIC_REVISION_CYCLES` | 2 | deterministic-defect revisions (all blocking debts `writing-lint-`/`writing-compile-`); never consumes the editor allowance |
| `PAPER_EDITOR_MAX_PASSES` | 1 | one editor review session for the whole gate (no per-revision reset) |
| `WRITING_GATE_EDITOR_LENS` | `editor` | the single dispatched lens |
| `WRITING_GATE_PAPER_INTENT` | `writing_gate_paper` | search_intent of the paper-authoring write pass |
| `WRITING_GATE_BLOCKING_SEVERITIES` | `{blocking, major}` | debt severities that force a revision |
| `WRITING_LINT_SEVERITY_TO_DEBT` | blocker→blocking, major→major, minor/nit→minor | rubric→debt severity mapping |
| `WRITING_GATE_MAX_ARTIFACT_CHARS` | 400 000 | max gated-artifact chars fed to the linter |
| `WRITING_CRITIC_RULE_LINE_CAP` (codex_runner) | 120 | max rubric rules embedded per lens directive |
| `WRITING_PACKET_MAX_ARTIFACT_CHARS` (context_builder) | 60 000 | max document chars embedded in critic/revision/paper packets |

Tuning: raise `MAX_WRITING_GATE_REVISION_CYCLES` (and possibly
`PAPER_EDITOR_MAX_PASSES`) for high-stakes runs where writing quality matters
more than tokens; the editor's standard and finding cap live in
`EDITOR_DIRECTIVE` (`writing/paper_contract.py`); new deterministic rules
belong in the rubric + `writing/linter.py` and flow into the gate
automatically through `run_all` (or `run_slop_lint` for anti-slop rules —
debts only, never attach-rejections — or `run_paper_lint` for
`final_paper`-only register rules, which the patch guard also enforces); the
paper's register itself is tuned by editing `writing/paper_contract.py`.

## Reporting

`report.py` adds a "Writing review" section to the phase2 markdown report:
one line per `writing_review` artifact (lens, verdict, reviewed artifact **and
its artifact type**, state revision), a `Final paper: <artifact_id>
(pdf_status)` line when a `final_paper` exists, open+resolved writing-debt
counts by severity, and the list of unresolved writing debts whenever any
remain (which is exactly the budget-exhaustion residue the gate left
recorded). The outcome label is unchanged: `solved_final` is still defined by
the `final_proof`.

## Tests

`agents/generation/tests/test_phase2_writing_gate.py`: lightweight scheduler
dispatch (certificate never linted/reviewed → immediate paper authoring →
one editor review on the paper), editor pass/fail convergence and
`stop_solved` without a second review after the single revision, gate opening
with unresolved non-residue debts once the revision is spent, the
residue/compile exceptions past the cap, lint→debt sync incl. stale closure
and paper-register rules, compile-debt sync and healing, livelock protection,
all patch guards (incl. the `final_paper` paper-register guard, `.tex`
storage, and the real pdflatex compile of the good-paper fixture),
lens-isolation manifest checks (incl. the editor's literature ledger, the
paper-authoring packet, and the legacy provenance auditor's certificate),
mode-guidance smoke tests (editor + legacy lenses), actor-role mapping, and
the report section.
`agents/generation/tests/test_writing_paper_lint.py`: unit coverage for
`run_paper_lint` (positive/negative cases per rule, verbatim exemption,
"manifestly" non-flag, appendix-scoped identifiers).

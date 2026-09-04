# Publication workflow and writing harness

The internal publication path is an explicit scheduler loop with two agents.
It starts only after the research harness has integrated the root claim and the
writer has recorded an internal `final_proof` certificate.

The external `revise-paper` path remains a writing-only service for a supplied
manuscript. It uses the legacy bounded editorial lenses and makes no claim that
the submitted mathematics has been verified.

## Internal state machine

1. The scheduler dispatches the `writer` to author a complete standalone
   `final_paper` from the proof certificate and its evidence.
2. The deterministic paper register, prose linter, residue scan, and LaTeX
   compilation gate run on the complete source. Blocking defects return it to
   the writer before refereeing.
3. A clean current version is sent to the `referee`. This agent receives the
   complete paper, final proof certificate, integrated proof approach,
   inferences, evidence, citation records, and all prior referee rounds.
4. The referee attaches one `referee_report` beginning with exactly one
   decision token:

   - `[accept]` ends the publication loop.
   - `[revise]` opens one located editorial issue per finding. The writer receives
     the complete report, revises the latest paper, and preserves every correct
     and rule-compliant passage unless a finding requires structural repair.
   - `[major-proof-route-error]` is reserved for substantive mathematical
     evidence that the integrated proof approach itself is false. The scheduler records
     the report in proof-state SQL, challenges the root and its inferences,
     blocks the approach, opens a root proof obligation, and returns control to the
     research harness.

There is no artificial writer--referee round cap. A repairable local gap,
missing explanation, citation problem, or exposition defect is `[revise]`, not
a proof-route rejection. Acceptance is bound to the current paper artifact, so
a later version must be reviewed independently.

## Durable records

`phase2/writing/publication.py` validates and normalizes paper lineage and
referee decisions. `publication_reviews` in `proof_state.sqlite3` stores one
row per report with the round, reviewed paper, certificate, verdict, decision
token, finding count, optional route-falsification evidence, and escalation
time. The referee report remains an ordinary readable artifact.

Every new writer-produced `final_paper` receives:

- `publication_workflow: writer_referee`
- `paper_version`
- `revision_of_artifact_id`
- `addresses_referee_report_id`
- `certificate_artifact_id`

Legacy papers without this marker resume under the old bounded gate. This
preserves already-running databases without weakening new runs.

## Role boundaries

The writer may attach and revise the complete paper and resolve its editorial
issues. It may not strengthen the certified mathematics.

The referee may attach exactly one `referee_report`. On `[revise]`, it may also
add located editorial issues (stored under the legacy
`debt_type=writing` compatibility field) owned by the reviewed paper. It may
not edit artifacts or transition claims, proof approaches, or inferences. The scheduler alone
applies a route-error escalation after the report has been committed.

`actor_role_for_action` maps publication review to `referee`. Writer and
referee sessions use the strong-mathematics model tier and a large context
budget. They run in isolated evidence capsules containing
`phase2/writing/AGENTS.md`.

## Mathematical writing standard

`phase2/writing/AGENTS.md` is the compact authoritative agent instruction for
paper architecture, statement discipline, notation, prose, cross-references,
figures, the no-gaps policy for computation, independent verification, and the
mechanical final passes. It supplements rather than replaces the existing
deterministic gates.

The existing source of truth remains:

- `math-writing-harness/rubric/` for structured rules
- `phase2/writing/linter.py` for deterministic findings
- `phase2/writing/paper_contract.py` for the standalone paper contract
- `phase2/writing/latex_template.py` for house-template normalization

The required mechanical passes include sentence-start notation, glyph
consistency, banned jargon, statement-only auditing, overflow repair, TODO and
citation sweeps, unused statements, voice and topic-sentence audits,
document-part agents, `\Cref` consistency, and long-sentence repair.

## Paper delivery

`final_paper` is writer-only. Its content is the complete LaTeX article and
must compile standalone. The preferred path-based attach writes the source into
the manifest-listed staging directory and attaches it without embedding LaTeX
in JSON. Inline source remains a fallback.

The paper register rejects markdown residue, internal workflow language before
the appendix, and missing article structure. Attach-time normalization applies
the house preamble and table style. Compile status and PDF paths are persisted
in metadata.

Every claim in the paper must be proved in the text, cited precisely, or
established by displayed executed code. An ancillary file is never the sole
justification for a load-bearing result.

## Periodic HMT sidecar

The cumulative Human-Readable Mathematical Text snapshot remains independent
of the main research scheduler. It is generated at its configured integrated-
claim cadence, does not advance proof-state revision, does not consume the
main research loop, and cannot block research or publication. HMT and final
paper PDFs share the dashboard's in-page PDF reader.

## Dashboard and reports

The monitor derives a `publication_workflow` payload from paper lineage and
the SQL review table. It displays the active writer/referee role, every paper
version, each decision, located finding counts, and route-error escalation.
Paper buttons open PDFs in the existing same-window reader. Report buttons
open the readable referee artifact in the mathematical artifact reader.

The phase2 Markdown report contains the same version and decision history in
its writing-review section. Proof-approach rejections state the affected approach,
the falsified step, and whether the scheduler returned the run to research.

## External manuscript revision

`python -m agents.generation.phase2.cli revise-paper <file.md|file.tex>` creates
an immutable `revision_document` with its original SHA-256, source format, and
`mathematical_status=not_verified_by_writing_harness`. The legacy terminology,
introduction, and whole-paper lenses remain available only for this external
path and for pre-upgrade stored papers.

## Regression coverage

- `test_phase2_publication_loop.py` covers dispatch, isolated context,
  revisions, acceptance bound to a version, SQL persistence, role guards, and
  route-error return to research.
- `test_phase2_writing_gate.py` covers deterministic gates, legacy resume, and
  external revision.
- `test_phase2_monitor.py` covers publication payloads, PDF/report navigation,
  safe artifact endpoints, stable DOM replacement, and MathJax rendering.

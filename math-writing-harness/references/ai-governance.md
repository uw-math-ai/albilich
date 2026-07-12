# AI / Generative-Model Governance — Distilled

**This is load-bearing for your use case.** The harness's input is auto-research markdown
and its output is machine-drafted; current repository and publisher policy makes *human
verification and disclosure* mandatory, and makes certain failure modes (hallucinated
citations, residual prompts) disqualifying. Paraphrased; see `INDEX.md` for originals, and
**re-fetch these before shipping** — this area is moving fast (dates below are as of the
2026 sources gathered).

---

## `ARXIV-AI-2023` — baseline

- Generative-AI tools **cannot be listed as an author.** A program can't take
  responsibility for a paper's contents or agree to submission terms. Authors must instead
  disclose tool use in the paper per venue norms.

## `ARXIV-AI-2026` — enforcement (the one that bites)

- arXiv will impose an **immediate one-year ban** on authors where there is
  **"incontrovertible evidence" that they did not check LLM-generated content** — the cited
  examples include **hallucinated citations, fabricated references, and residual prompts or
  AI-system comments copied into the manuscript**, as well as plagiarized/biased/incorrect
  LLM-written content.
- After the ban, subsequent arXiv submissions must **first be accepted at a reputable
  peer-reviewed venue** before appearing on the repository.
- The policy does **not** prohibit LLM use; it enforces the principle that **authors remain
  fully responsible** for everything in the paper.
- Context: submission volume to the math/physics/CS preprint server crossed 30,000/month,
  driving the crackdown.

## `ARXIV-REVIEW` — review/survey/position papers (Oct 2025)

- arXiv's CS category tightened practice for **review, survey, and position** papers
  (a response to a flood of AI-generated surveys). If your harness produces survey-type
  output, expect extra scrutiny and encode it.

## `PUB-AI` — cross-publisher consensus

- **No AI authorship** anywhere (Elsevier, Springer Nature, Wiley, Taylor & Francis, SAGE
  all prohibit listing AI as author/co-author).
- **Disclosure is required**, but *where* and *how much* varies:
  - Common pattern: use AI only to **improve readability/language**, with human oversight,
    and disclose in a dedicated section (often Acknowledgments).
  - Some venues require naming the **specific system(s)**, the **section(s)** where AI was
    used, and a brief description of the **level** of use (e.g., the IEEE-style disclosure).
  - Basic grammar/"AI-assisted copy-editing" is sometimes exempt — do not assume it is.
- **Red-flag phrases that betray unedited AI output** and should be caught pre-submission:
  "as of my knowledge cutoff," "as an AI language model," leftover prompt scaffolding,
  placeholder citations. → the Provenance Auditor / a dedicated **residue scanner** must
  grep for these.

---

## Hard requirements this imposes on the harness

These are **non-negotiable invariants**, not style preferences:

1. **Faithfulness invariant.** The paper may never claim more than the source markdown
   supports. Gaps become explicit remarks/conjectures, never smoothed over. (Mirrors
   `PAK-STORY`: 100% correct on facts, results, implications, prior work, references.)
2. **Citation-existence invariant.** Every reference must resolve to a real work that
   actually supports the sentence citing it. **Provenance Auditor has veto power.** A
   hallucinated citation is a *ship-blocker*, not a warning.
3. **Residue-clean invariant.** No prompt fragments, AI self-references, knowledge-cutoff
   phrases, or placeholder text in the output. Dedicated deterministic scan every round and
   at the final gate.
4. **Human-responsibility gate.** The harness **must not** emit a silent final PDF for
   submission. It terminates at a human sign-off checkpoint accompanied by an audit report
   (claim graph, per-theorem verification status, citation audit, residue scan result) and
   **venue-appropriate disclosure text**.
5. **Disclosure generator.** Given a target-venue profile, generate the correct disclosure
   statement (system name(s), sections, level of use) for the human to review and place.

## Where these live in the pipeline

- Stage 1 Planner builds the **claim/dependency graph** that anchors invariant (1).
- Stage 3 Provenance Auditor enforces (2) and (3) with veto.
- A lightweight **Residue Scanner** (deterministic) runs (3) every round — cheap, first.
- Stage 5 Human Gate enforces (4) and runs the **Disclosure Generator** (5).

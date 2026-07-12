# Rubric Schema

The rubric is the machine-usable distillation of the whole corpus. Stage 0 of the harness
compiles `references/*.md` (and, optionally, freshly fetched originals) into a rule base in
this schema. Critics load the subset of rules relevant to their layer.

## Rule record

Each rule is one record with these fields:

```yaml
id: L4-CONRAD-07              # unique; <layer>-<source key>-<n>
layer: L4                     # L1..L5 (see below)
source: CONRAD               # provenance key from references/INDEX.md
statement: >                  # the rule, in imperative form
  Do not use the logic symbols (for-all, there-exists, and, or) as prose
  abbreviations outside a logic paper; write the words instead.
severity: minor              # blocker | major | minor | nit
scope: local                 # local (sentence/line) | global (document)
checkability: lint           # lint | llm | verify
detector: regex|prompt|tool  # how it is checked (see below)
good_example: "…imply a = 0 and b = 1."
bad_example:  "…imply a = 0 ∧ b = 1."
owner_critic: pedant         # which panel critic runs it
autofix: safe                # safe | assisted | manual
```

## Field semantics

**layer** — the five-layer stack; critics are ordered by it (correctness first):
- **L1 Mathematical correctness & faithfulness** → `L1-correctness.md`
- **L2 Logical exposition** (every claim justified, hypotheses used) → `L2-logic.md`
- **L3 Structure & narrative** (abstract/intro accuracy, factoring, story) → `L3-structure.md`
- **L4 Sentence-level style** → `L4-style.md`
- **L5 Formatting & venue compliance** → `L5-formatting.md`

**severity** — feeds the convergence score. Suggested weights:
`blocker = ∞` (cannot ship), `major = 8`, `minor = 3`, `nit = 1`.
Any **unresolved `blocker`** forces the run to "not done" regardless of total score.
All **L1 faithfulness / citation** rules are `blocker`.

**scope** —
- `local`: fixable by a minimal sentence/line patch (diff-minimal).
- `global`: may require restructuring; only the reviser's structural mode may act, and only
  after the meta-reviewer confirms the scope.

**checkability** — decides the detector and *the order rules run in each round*:
- `lint`: deterministic (regex, AST/LaTeX parse, numbering pass). **Cheap — run first,
  every round.**
- `llm`: judgment call, run by a critic LLM with few-shot examples from `bad_example`.
- `verify`: needs mathematical checking (symbolic/numeric/counterexample/optional
  autoformalization). **Most expensive — run last, only on survivors.**

**detector** —
- `regex`: literal/pattern match (fill in the pattern in implementation).
- `prompt`: the critic prompt template that evaluates the rule.
- `tool`: an external checker (CAS, numeric harness, proof assistant, citation resolver).

**owner_critic** — `pedant | skeptical_editor | referee | confused_reader |
provenance_auditor`. Keeps each critic's context minimal (see README on context isolation).

**autofix** —
- `safe`: reviser may apply automatically (e.g., `∧`→"and", "iff"→"if and only if").
- `assisted`: reviser proposes, meta-reviewer/human confirms.
- `manual`: surfaced in the audit report only (e.g., permissions, data deposition).

## Cost-ordering contract (per revision round)

1. Run **all `lint`** rules + the **Residue Scanner** (deterministic; near-free).
2. Run **`llm`** critics on what remains.
3. Run **`verify`** (Referee deep checks) only on claims not already cleared, escalating to
   `tool` (CAS/numeric/proof-assistant) only for `blocker`/`major` correctness items.

This ordering is the single biggest lever on cost — never spend the adversarial LLM/verify
budget on something a regex already caught.

## Compilation guidance (Stage 0)

- Emit **one record per atomic rule**. Split compound advice ("define notation *and* use it
  consistently") into separate records so detectors stay simple.
- Preserve **at least one Bad/Good pair per rule** — dual-purpose as few-shot + regression
  test (`eval/bad-good-pairs.md`).
- Tag each record with its `source` key so per-source and per-rule precision/recall can be
  measured.
- Where sources conflict (e.g., Milne's *anti*-advice vs. Conrad's direct advice), the
  anti-pattern is stored as an **inverted CHECK**, never as a positive rule.

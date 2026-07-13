# AI-SLOP — Signs of AI writing & how to fix them (fetched 2026-07-09; sources: Wikipedia "Signs of AI writing" / WikiProject AI Cleanup catalog (primary, fetched in full), Kobak et al. arXiv:2406.07016 excess-vocabulary study, connector/em-dash detection literature, local stop-slop skill catalog; ADAPTED FOR MATHEMATICAL PROSE — see the adaptation table at the end)

Detection context (Wikipedia): humans without LLM exposure detect AI text at chance; heavy users
reach ~90%. Kobak et al.: ≥13.5% of 2024 biomedical abstracts show LLM vocabulary influence (some
subcorpora 40%) — detectable by excess word frequency alone. The patterns below are the fingerprints.

## 1. AI vocabulary (lexical tells; Kobak "excess words" + Wikipedia lists)
Flag-on-sight words (rarely load-bearing in math prose; each occurrence is a candidate rewrite):
**delve, tapestry, testament ("stands as a testament"), showcase/showcasing, underscore(s),
pivotal, intricate/intricacies, interplay, meticulous(ly), boasts, vibrant, garner, foster(ing),
landscape (metaphorical), realm (metaphorical), journey (metaphorical), seamless(ly), multifaceted,
nuanced (as praise), holistic, robust (non-technical use), leverage (verb), commendable, resonate,
navigate (metaphorical), evolving/ever-evolving, groundbreaking, renowned, rich (non-technical),
profound, valuable insights, crucial, key (adjective), notably, comprehensive (as praise)**.
Why: statistical overuse post-2022; co-occurrence clusters human writing doesn't produce. NOTE:
in mathematics "robust", "key", "crucial" have legitimate sparse uses — flag by density, not ban.

## 2. Significance inflation (the worst offender in math papers)
- "stands/serves as", "is a testament/reminder", "plays a vital/significant/crucial/pivotal/key
  role", "underscores/highlights its importance", "reflects broader", "marking/shaping",
  "represents/marks a shift", "key turning point", "setting the stage for", "indelible mark".
- Why: LLMs favor generic importance-statements over specific facts. Math version: "This lemma
  plays a crucial role in our argument" instead of USING the lemma; "highlighting the deep
  connection between X and Y" instead of stating the connection as a theorem.
- Fix: replace every importance-claim with the specific mathematical fact that would justify it,
  or delete. (Cross-ref HALMOS §10: say where each statement stands; TAO: accurate description.)

## 3. Copula avoidance
- "serves as / stands as / marks / represents / boasts / features / offers / refers to" replacing
  plain "is/are/has". LLMs show ≥10% copula decline vs human baseline.
- Fix: restore "is". "The quotient serves as a classifying object" → "The quotient is a
  classifying object."

## 4. Structural tells
- **Negative parallelism**: "not only X but also Y", "not X, but Y", "it's not X — it's Y",
  negative listing ("It wasn't X. It wasn't Y. It was Z."). Didactic reversal drama; state Y.
- **Rule of three**: triads of adjectives/phrases manufactured for rhythm ("precise, elegant, and
  powerful"). Two honest items beat three padded ones.
- **Section-final summaries**: paragraphs opening "In summary", "Overall", "In conclusion",
  "Taken together" that recap what was just said. Math papers do not recap sections.
- **Connector spam**: "Moreover/Furthermore/Additionally" chains opening consecutive sentences or
  paragraphs; human writers vary or omit connectors. (In proofs the honest connectives are
  "hence/thus/therefore/so" tied to actual implication — KLR little words — not paragraph glue.)
- **Elegant variation**: repetition-penalty synonym chains — the same object renamed each mention
  ("the group … the algebraic structure … the object under study"). Violates one-name-one-object
  (HOUSE 7, PAK-CLEAR 33). Repetition is correct in math.
- **Em-dash overuse**: em dashes substituting for commas/periods at high density (one-pass
  generation lacks global punctuation judgment). Math prose: prefer commas, periods, or recast;
  AMS allows em dashes sparingly (AMS-STYLE 95).
- **Uniform rhythm**: every paragraph 3-5 sentences ending punchily; every sentence medium-length.
  Human proofs have long technical sentences next to short declarative ones.
- **Hedging stacks**: "may potentially", "could possibly suggest", "it seems plausible that" in
  contexts where mathematics demands a definite status (proved / cited / conjectured — HALMOS §10).
- **Vague-pronoun paragraph openers**: "This shows/means/suggests..." where "this" has no single
  antecedent (HOUSE 18; MAURER's "vague word" rule).

## 5. Task-narration & choreography (math-specific slop; = HOUSE anti-choreography)
- "We now proceed to...", "We first establish the following", "Having established X, we turn to
  Y", "With these preparations in place", "the necessary input", "it remains to check" as a
  paragraph-filler pattern, "the proof rests on three points", "we record the following".
- Why: the model narrates its own generation process. A paper explains mathematics; it does not
  live-blog its assembly. Fix per HOUSE 32: replace checklist transitions with the mathematical
  implication ("Since every factor is abelian, it suffices to compare pairs" beats "We now
  turn to the pair analysis").

## 6. Formatting tells (mostly covered by L5-PAPER lint)
- Markdown residue; bold-term-colon lists ("**Key idea:** ..."); title-case headings (AMS uses
  sentence case); emoji; curly quotes in source; heading-level jumps; tables where prose belongs;
  knowledge-cutoff disclaimers and placeholder text (residue scanner).

## 7. Citation tells (covered by L1-CITE but restated as slop)
- Vague authority ("Experts argue", "It is widely believed" without citation); citation clusters
  as decoration; invalid DOIs/identifiers; padded bibliographies with uncited entries.

## Adaptation table: general anti-slop rules that math prose OVERRIDES
| General rule (stop-slop/Wikipedia) | Math-paper ruling |
|---|---|
| Ban "In this section, we..." roadmaps | REQUIRED by HOUSE 19 (one per section opening) |
| Kill all adverbs | Keep sparse mathematical adverbs ("strictly", "uniformly", "locally"); kill emphasis adverbs (really/truly/crucially/importantly) |
| No em dashes at all | Sparse em dashes acceptable (AMS-STYLE 95); flag density |
| No three-item lists | Genuine mathematical triples (e.g. three cases) are fine; ban manufactured adjective triads |
| Avoid passive voice everywhere | Mathematical passive is conventional where the agent is irrelevant ("the group is generated by..."); ban only agent-hiding passives for novel acts (HOUSE 24) |
| No "we" | Math "we" = author+reader is standard (HALMOS §13); HOUSE 24-26 governs its discipline |
| Question-openers banned | Rhetorical questions are rare but legitimate in introductions posing the problem |

## Fix protocol (for the editor/reviser)
1. Delete or specify: every significance-claim either becomes a concrete mathematical statement or dies.
2. Restore copulas; restore repeated names; delete choreography sentences whole (they carry no content — removal never loses mathematics).
3. Break uniform rhythm by merging the narration sentence into the mathematical one.
4. Density check, not word-ban: one "crucial" survives; three do not.

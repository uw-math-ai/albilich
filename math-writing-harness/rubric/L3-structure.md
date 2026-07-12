# L3 — Structure & Narrative

Whether the paper is *organized and motivated* at the document level: honest abstract/intro,
good factoring into lemmas, a real story, no overselling. **Owner critic:** Skeptical
Editor. **Default severity:** `major` for overselling/faithfulness-of-framing, else `minor`.

Sources: `TAO`, `PAK-CLEAR`, `PAK-STORY`, `HALMOS`, `MILNE`, `SERRE`, `AMS-NOTICES`, `LEE`,
`ROTA`, `KLR`, `SU`, `MAURER`, `AMS-HB`.

---

## Honesty of framing (highest priority in L3)

- `L3-SELL-01` [llm] **Intro sells the key points AND describes results accurately** — "a
  paper should neither understate nor overstate its main results." Unsatisfactory aspects
  (strong hypotheses, weak conclusions) stated "honestly and openly." severity: `major`.
  (`TAO` 1-8) Cross-checked against L1-FAITH and L1-GLOBAL-04.
- `L3-SELL-02` [llm] **No vogue/vague words hiding claim strength** ("addresses the X
  problem" when it's unclear whether X is solved). severity: `major`. (`MILNE`)
- `L3-SELL-03` [llm] **Main result stated readably before the machinery** — first theorem on
  page 1-2 (Pak), milestone propositions early and prominent, "no punch line delayed until
  the very last page"; if the main result is too technical, state an easy-to-state corollary
  or special case instead ("cook them up if necessary" — the corollary is what passers-by
  retell). severity: `major`. (`PAK-CLEAR` 13, `TAO` 16, `MILNE`, `SERRE` 27)
- `L3-SELL-04` [llm] **Key points live in the introduction**, never buried in footnotes,
  remarks, or mid-paper lemmas; "if the referee fails to grasp the key points, the
  introduction lacks publication quality" — that is the author's defect, by definition.
  severity: `major`. (`TAO` 1-2)
- `L3-SELL-05` [llm] **Conjecture-motivation is candid.** Famous-conjecture framing requires
  "a candid evaluation of the extent to which your work truly represents progress toward
  that conjecture" — no false advertising, no name-dropping, no appeal-to-authority
  quotation strings. severity: `major`. (`TAO` 10, 61)
- `L3-SELL-06` [llm] **Informal statements are marked informal** and paired with a pointer to
  the precise version. severity: `major`. (`TAO` 5, 22)
- `L3-SELL-07` [llm] **Self-assessment is humble:** no superlatives of praise for one's own
  work, explicit or implicit; others' work may be "interesting/remarkable" but better to
  give reasons. severity: `minor`. (`KLR` 12)

## Introduction & front matter

- `L3-INTRO-01` [llm] **The introduction compares and contrasts with existing literature**:
  what's new, why interesting/surprising in context, which new difficulties are resolved,
  where simpler existing methods fail, counterexamples showing the result can't be cheaply
  improved. severity: `major`. (`TAO` 3-4)
- `L3-INTRO-02` [llm] **Only directly-relevant history in the intro** (the [A]→[B]→this-paper
  chain); the full "everybody his due" history goes to Final Remarks/endnotes. Rota's
  lengthy-introduction ideal is implemented by writing it and then splitting it. severity:
  `minor`. (`PAK-CLEAR` 12, 15, 18; `ROTA` 5)
- `L3-INTRO-03` [llm] **The intro states the problem for a reader who doesn't know it**, says
  why it matters (the hook), and previews the paper; last paragraph outlines the structure
  in words. severity: `minor`. (`LEE` 13, `PAK-CLEAR` 16, `MAURER` §5)
- `L3-INTRO-04` [llm] **The opening paragraph is the best paragraph, the first sentence the
  best sentence.** Worst opening form: "An x is y" ("An important method for internal
  sorting is quicksort" → "Quicksort is an important method for internal sorting,
  because…"); nothing less inspiring than "Let G = (V,E) be a loopless graph." The opening
  is the paper's one place to shine — no passive wimpiness. severity: `minor`. (`KLR` 24,
  33; `PAK-CLEAR` 17)
- `L3-INTRO-05` [llm] **Abstract: dry facts, standalone, budgeted.** Key results first;
  nothing personal; no details or connections beyond necessity; no \cite/\ref/custom macros
  (it circulates alone); length ≈ 0.3-0.5 lines per page (AMS: ≤150 words short papers,
  ≤300 long). Title and abstract "get to the point immediately." severity: `minor`→`major`
  (venue). (`PAK-CLEAR` 10, `AMS-HB` 7, `TAO` 6)
- `L3-INTRO-06` [llm] **Title is informative, first approximation to content.** Content over
  length ("All tennis balls are white" / "On white tennis balls" / "Not all tennis balls are
  white" each mean different things); no zero-information titles ("A proof of a theorem of
  Euler", "On some problems in group theory"); surveys say "survey" in the title; concepts
  defined only inside the paper don't belong in it. severity: `minor`. (`PAK-CLEAR` 8,
  `SERRE` 1, `MAURER` §4)
- `L3-INTRO-07` [llm] **Foreword pattern for long intros:** intros > ~4 pages get subsections
  with a nontechnical foreword (big picture, cross-field motivation, ≤1 page). severity:
  `nit`. (`PAK-CLEAR` 17)

## Organization

- `L3-ORG-01` [llm] **No stream-of-consciousness order** (results in discovery order is
  "generally a very bad idea"); organization is the expositor's main contribution —
  "minimize the resistance and maximize the insight of the reader." severity: `major`.
  (`TAO` 13, `HALMOS` §4)
- `L3-ORG-02` [llm] **Order is logically correct AND psychologically digestible**: told early
  what to expect, lemmas present when needed, no statement used before established (the
  1000-sheets topological sort); among valid orders pick the most efficient and pleasant.
  severity: `major`. (`HALMOS` §4, §8)
- `L3-ORG-03` [llm] **New section at each major turning point; closely related facts share a
  section; every section has a single unified subject** (title test: if you can't find a
  short title for it, it isn't one section). severity: `minor`. (`TAO` 15, `HALMOS` §7)
- `L3-ORG-04` [llm] **Each section opens with its purpose**: what it's about, how it fits,
  why it's there; key sections also state their milestone + a sketch of the section's plan.
  severity: `minor`. (`TAO` 23, `MAURER` §6)
- `L3-ORG-05` [llm] **Technical material is pushed back; early sections reward the reader
  with easy tangible progress** (learning-curve easing); peripheral results → remarks/
  footnotes/discussion; necessary-but-alien or dull-computation material → appendix.
  severity: `minor`. (`TAO` 14, 17)
- `L3-ORG-06` [llm] **Lemma placement:** statement and proof near first use; single-use
  technical notation localized inside the lemma's proof (information hiding). severity:
  `minor`. (`TAO` 17, 26, 44)
- `L3-ORG-07` [llm] **Section titles are descriptive** ("Proof of the decomposition lemma,"
  "An orthogonality argument") — never "Step 2" or "Some technicalities." severity: `nit`.
  autofix: assisted. (`TAO` 12)
- `L3-ORG-08` [llm] **Spiral-plan review:** each new concept reviews earlier material from
  the new viewpoint (Section 2's examples revisit Section 1's); subplots/clues prepare
  major definitions chapters ahead. Generation-mode planner directive, checked as: earlier
  sections set up what later sections need, with explicit back-references. severity: `nit`.
  (`HALMOS` §7-8)
- `L3-ORG-09` [llm] **Statements-first layouts keep notation available**: if all statements
  are collected in a long introduction, their notation must be defined by then — no
  "Theorem 3.1 in the introduction with notation not yet introduced." severity: `major`.
  (`SERRE` 27)
- `L3-ORG-10` [llm] **What to leave out matters as much as what to put in** — "too much
  detail can be as discouraging as none"; organize around the central, crucial examples and
  counterexamples; guide the reader on what the proof does NOT prove (counterexamples, next
  questions). severity: `minor`. (`HALMOS` §4, 12-13)

## Story

- `L3-STORY-01` [llm] **There is a story** — a lunch-retellable, tweet-length account of what
  the paper does and why it matters; the Introduction is built around it and everything
  irrelevant to it is discarded. severity: `minor`. (`PAK-STORY` 1-5, 13-14)
- `L3-STORY-02` [llm] **The story is impersonal** — about the area, retellable by strangers;
  no "I was drinking boba tea when I realized…". severity: `minor`. (`PAK-STORY` 2)
- `L3-STORY-03` [llm] **On facts/history/prior work the story is 100% correct** (framing may
  be shaped; facts may not). severity: `major`; overlaps L1-FAITH-03/04. (`PAK-STORY` 11-12)
- `L3-STORY-04` [llm] **Weak-story antipatterns flagged:** "shorter and more elegant proof"
  without naming the tool innovation; "special case now, full result in the next paper"
  (speculative); two-field straddle papers serving neither audience. A weak story = rewrite
  the framing, not necessarily the math. severity: `minor`. (`PAK-STORY` 7-10)
- `L3-STORY-05` [llm] **Story-within-a-story placement:** secondary-field connections and
  simplified-special-case expositions go in ONE self-contained section after the main
  results, before the proofs; never interleaved; never nested twice. severity: `nit`.
  (`PAK-STORY` 16-17)
- `L3-STORY-06` [llm] **One main point** per unit of exposition, stated and repeated ("make
  one point … make several points and the cows scatter"); the takeaway is explicit at start
  and restated at the end. severity: `minor`. (`ROTA` 1-2, `POONEN-SPK` 10)

## Motivation

- `L3-MOTIV-01` [llm] **Conditions/hypotheses are explained**, not dumped. severity: `major`.
  (`MILNE`, `TAO` 21)
- `L3-MOTIV-02` [llm] **The reader always knows the near-term and long-term objective** of
  the current passage, how the argument advances it, and why each step is plausible (or why
  surprising). severity: `major`. (`TAO` 20-21)
- `L3-MOTIV-03` [llm] **Audience contract honored throughout** (matches the Planner's
  declared audience). For general venues: no unexplained jargon; no "Recall that X" / "It is
  well known that X" / "Clearly X" register moves that exile non-specialists. severity:
  `minor`→`major` for general-audience venues. (`AMS-NOTICES` 5-6, `SU` 1, `HALMOS` §3)
- `L3-MOTIV-04` [llm] **Toy case before general machinery:** a less technical special case or
  worked example precedes the most general result; a worked special case may replace a
  general proof when more illuminating. severity: `minor`. (`TAO` 24, `POONEN-SPK` 12,
  `SU` 8)
- `L3-MOTIV-05` [llm] **Heuristic/motivational reasoning is present but segregated** —
  clearly marked informal, in remarks/footnotes, never interleaved with rigorous steps
  unmarked. severity: `major` (unmarked heuristics are L1-FAITH-05 territory). (`TAO` 22,
  51)
- `L3-MOTIV-06` [llm] **Examples keep you honest:** key concepts come with at least one solid
  example; "it is never a mistake to have too simple an example"; more examples than
  definitions and theorems in expository work. severity: `minor`. (`KLR` 30, `MAURER` §9,
  `SU` 8, `HALMOS` §4)

## Factoring & focus

- `L3-FACTOR-01` [llm] **Paper factored into lemma-sized pieces**; long proofs subdivided;
  each major milestone a self-contained, prominently-placed proposition. severity: `minor`.
  (`TAO` 16, 42-46, `POONEN` 6)
- `L3-FACTOR-02` [llm] **Lemma statements easy to USE, not easy to prove** — natural
  verifiable hypotheses, manifestly useful conclusions; push details into the lemma proof;
  two lemmas useful only together become one. severity: `minor`. (`TAO` 45-46)
- `L3-FACTOR-03` [llm] **Repeated argument ⇒ extract a lemma** ("never repeat a proof"; "by
  the same technique as Theorem 1" is the symptom). severity: `minor`. (`HALMOS` §12,
  `SU` 7)
- `L3-CUT-01` [llm] **Side examples that don't stand alone are cut or appendixed**, not
  co-submitted; page-long-and-uses-the-lemmas → end of paper; black-box technical
  calculation → separate paper/arXiv appendix. severity: `nit`. (`PAK-STORY` 15)
- `L3-EFFORT-01` [llm] **Results-to-effort at a local maximum; readability optimisation
  always wins.** Not padded, not cryptic; never shortened by deleting "examples, remarks,
  whitespace, motivation, and discussion"; don't over-optimize lemmas for hypothetical
  future users. severity: `minor`. (`TAO` 39-41)
- `L3-FOCUS-01` [llm] **The paper has one delineated subject that hangs together** — "two
  ways for a piece of writing not to have a subject (no ideas or too many)." severity:
  `minor`. (`HALMOS` §2, `ROTA` 1)

## Skimmability & multi-audience service

- `L3-SKIM-01` [llm] **First sentences carry the flow:** a skimmer reading only paragraph
  openers can follow the argument. severity: `minor`. (`SU` 7)
- `L3-SKIM-02` [llm] **Roadmap present** (section outline in the intro for anything but the
  shortest papers). severity: `nit`. (`POONEN` 7, `PAK-CLEAR` 16)
- `L3-SKIM-03` [llm] **The Matryoshka contract:** title-only, abstract-only, intro-only,
  results-jumping, and cover-to-cover readers are ALL served — each nesting level is
  self-consistent and accurate. severity: `minor`. (`PAK-CLEAR` 7, `AMS-NOTICES` 2-3)
- `L3-SKIM-04` [llm] **Endnotes pattern for overflow:** expanded history, speculative
  directions, per-paper credit descriptions go to Final Remarks as independent, importance-
  ordered subsections, forward-linked from the text ("for more on this, see §6.1").
  severity: `nit`. (`PAK-CLEAR` 18)
- `L3-SKIM-05` [llm] **Reference descriptions are individualized** — never "see [2–19] for
  some relevant work"; go paper by paper, most important first, describing each
  contribution; intro cites only the most relevant, main body cites nothing except lemmas
  used in proofs (precise reference at point of use). severity: `minor`. (`PAK-CLEAR`
  22-23)
- `L3-SKIM-06` [llm] **Acknowledgments follow the escalation pattern:** conversations by
  name (alphabetical) → specific contributions spelled out per person → institutions →
  funders; private information (unpublished conjectures) only with permission; err lavish.
  severity: `nit`. (`PAK-CLEAR` 19, `ROTA` 6, `SU` 13)

---

### Ordering note
L3 runs **before** L4 (style). There is no point polishing sentences in a section that a
structural critique will delete or move. The reviser applies L3 (structural) fixes, then the
paper re-enters L4. See README convergence loop and the frozen-decisions mechanism so L3
rewrites don't churn already-approved L4 style.

### Generation-mode planner notes (not checks)
- Write a rapid prototype first: skeleton of statements with fuzzy proofs, organize, then
  precision, then routine proofs; introduction written LAST (`TAO` 47-49).
- Write the intro's first draft FIRST to know what the paper is, then rewrite it completely
  after the paper stabilizes (`PAK-CLEAR` 12). These compose: draft-intro → skeleton → …
  → final-intro.
- Halmos spiral: expect to rewrite chapter 1 three or four times; "rewrite means write
  again — every word" (`HALMOS` §7).

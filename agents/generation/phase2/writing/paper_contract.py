"""The paper contract: the quality lever for the ``final_paper`` deliverable.

Verbatim directive strings, kept in one place so the writer's authoring
guidance (codex_runner), the paper-authoring packet (context_builder), and the
editor directive all quote exactly the same standard:

- :data:`WRITING_STYLE_CORE` — the distilled craft of mathematical writing
  (Halmos, Tao, Pak, Knuth, Krantz, Poonen, Serre, AMS). The first draft must
  already be a paper; this is what makes it one.
- :data:`PAPER_CONTRACT` — the writer directive for ``paper_authoring``
  passes: deliverable, mandatory structure, the style core, the register wall,
  and faithfulness rules. Contains WRITING_STYLE_CORE in full.
- :data:`EDITOR_DIRECTIVE` — the single exposition-editor lens directive.
  Mathematical correctness is assumed (the main harness verified it); the
  editor judges only whether the article reads as a publishable paper.
- :data:`PAPER_STANDARD_FOR_CRITICS` — legacy multi-lens standard, kept
  exported for the remaining legacy lens directives.

Do not paraphrase or "improve" these texts in code; edit them here only.
"""

from __future__ import annotations

WRITING_STYLE_CORE = """STYLE CORE — distilled from Halmos, Tao, Pak, Knuth, Krantz, Poonen, Serre, and the AMS style guide. This is what separates a paper from a report.

The story and the introduction:
- Before writing anything, fix the one-sentence story a colleague could retell at lunch ("We prove X, answering problem Y, by reducing to Z plus a finite machine-verified computation"). Build the introduction around that story; discard everything irrelevant to it. [Pak]
- The opening paragraph is your best paragraph, its first sentence your best sentence. Never open with "An x is y" boilerplate, with the problem's catalogue number, or with "Let G = ...". Open with the mathematical phenomenon and why it matters. [Knuth, Pak]
- Sell accurately: neither understate nor overstate; state honestly what is unsatisfactory (e.g. dependence on machine enumeration) — candor reads as strength. [Tao]
- Newspaper, not murder mystery: the main theorem appears within the first two pages. Do not hide the punchline. [AMS Notices]
- History: only what leads directly to your result, each cited work described by its specific contribution ("[A] proved the k=2 case; [B] showed the general bound fails; we close the remaining case") — never "see [2-9] for related work". [Pak]

Architecture:
- Organize around the central objects and the crucial computation, not the order of discovery. Every section opens with one sentence saying what it does and why it is needed now. [Halmos, Tao]
- Statement first, then proof; never ramble into "thus we have proved...". Key lemmas appear early in their sections, before their technical proofs. [Halmos, Tao]
- Never repeat an argument: if two proofs share steps, extract a lemma. Push heavy technicalities toward the back; reward the early reader with tangible progress. [Halmos, Tao]

Theorems and proofs:
- One-sentence, self-contained statements. When a statement would need many hypotheses, bundle them into a named definition first ("Call a pair (H, K) admissible if ...") so the theorem reads in two lines. [Krantz, Halmos]
- Construct the object first, then assert its properties; never "the map f of Theorem 1" when Theorem 1 asserted only existence. [Serre]
- Prove forward, from hypotheses toward the goal — never backward from an unexplained choice of constant. [Halmos]
- A direct proof beats a contradiction wrapper; when contradiction is genuinely needed, open with "Seeking a contradiction, suppose ...". [Krantz]
- In long proofs use the claim device: "We claim ...; assuming the claim for the moment, we complete the proof", then prove the claim — the reader must always know the status of every statement. [Krantz]
- At each difficulty spike, give one sentence of plan before the step. Readers skim formulas: your sentences must still flow when every formula is read as "blah". [Knuth]

Notation:
- The best notation is no notation: introduce a symbol only if it is used three or more times; no symbol appears in a theorem statement that the statement does not need. [Halmos, Tao]
- Letters keep their conventional types (n an integer, ε small and positive, H and K subgroups); one symbol, one meaning, for the whole paper; defined at first use, never re-purposed. [Halmos, Knuth]

Sentences:
- Every sentence is a complete sentence; displayed formulas are clauses and take punctuation. Never begin a sentence with a symbol; separate adjacent formulas with words. [Knuth, AMS]
- Words for logic in prose: "if and only if", "for all"; keep the "then" after "if" in mathematical sentences; avoid "any" (ambiguous between "every" and "some") — say "each" or "every". [Halmos]
- Present tense; "we" means author and reader together; plain words over fancy ones — ten honest "therefore"s beat one "whence"; the same object keeps the same name (repetition beats elegant variation). [Pak, Su]
- Dwell on what is new and crucial; be brief on the routine — and when a standard computation is skipped, say that it is standard. State the status of everything: proved here, cited, or machine-verified. [Tao, Halmos]

Anti-slop (patterns that mark machine prose; the deterministic linter also hunts these):
- Never inflate significance: no "plays a crucial role", "stands as a testament", "underscores the importance". State the specific mathematical fact or say nothing. [AI-SLOP]
- Plain copulas: "is", "are", "has" — never "serves as", "boasts", "features". [AI-SLOP]
- No choreography: never narrate task completion ("We now proceed to...", "Having established X, we turn to...", "with these preparations in place"). Every transition states the mathematical implication in use, not the author's itinerary. [HOUSE]
- One name per object, forever; repetition is correct, elegant variation is a defect. [HOUSE, AI-SLOP]
- No recap paragraphs ("In summary", "Overall"); no negative-parallelism drama ("not only... but also"); no manufactured triads of adjectives; no connector chains (Moreover/Furthermore/Additionally). [AI-SLOP]
- No one-sentence paragraphs; paragraphs have a topic sentence and development. No vague "This shows..." openers — repeat the noun. Avoid colons and semicolons outside math mode. No parenthetical asides — integrate or delete. [HOUSE]
- Section openers — HARD RULE (deterministically enforced; violations block the paper): every section opens, within its first paragraph, with a sentence beginning "In this section, we ..." ("In this appendix, we ..." in appendices), embedded in a real paragraph; only References/Acknowledgment sections are exempt. [HOUSE]
- "We" discipline — HARD RULE (deterministically enforced; violations block the paper): "we" only for novel authorial acts (we prove/define/construct); impersonal sentences for background; "recall" only for material stated earlier in this paper; the habitual collocations "we recall", "we record", "we now show", "we now prove", "we now turn", "we begin by", "we start by", "we note that", "we observe that" are banned outright. [HOUSE]
- Background reads as established mathematics, not project planning; argument-first citations (state the fact, then cite); attribution chronology accurate (introduced vs generalized). [HOUSE]

The genre of this paper (computer-assisted proof):
- Follow the norms of published computer-assisted proofs: describe the algorithm as mathematics (what finite set is enumerated, what invariant is computed for each element, why coverage is complete); state the outcome as a numbered Proposition; report the counts; make independent reverification possible from the appendix alone. Anything a referee cannot recompute must be fully proved in the paper's prose."""

_PAPER_CONTRACT_HEAD = """You are writing a research article for a top mathematics journal, in the register of J. Algebra / Bulletin of the LMS. The internal certificate in your packet is your sole source of mathematical truth: the paper claims exactly what it establishes, no more. The certificate's FORM is irrelevant — you are writing for a mathematician who has never seen this system.

OUTPUT: attach exactly one artifact {"op":"attach_artifact","artifact_type":"final_paper","content":"<COMPLETE LaTeX source>"}. The content must compile standalone with pdflatex.

STRUCTURE (mandatory skeleton):
- \\documentclass[11pt]{amsart} with this preamble, in this order: \\usepackage[margin=1.25in]{geometry}; \\usepackage{amsmath,amssymb,amsthm}; \\usepackage{newpxtext,newpxmath} (Palatino-family text with matching math); \\usepackage{microtype}; \\usepackage{booktabs}; \\usepackage{xcolor} with \\definecolor{linkblue}{RGB}{0,0,128}; then \\usepackage{hyperref} loaded LAST followed by \\hypersetup{colorlinks=true,linkcolor=linkblue,citecolor=linkblue,urlcolor=linkblue}; then \\numberwithin{equation}{section} and \\emergencystretch=1.5em; theorem environments declared in the preamble (\\newtheorem{theorem}{Theorem}[section] with lemma/proposition/corollary sharing the counter; definition and remark styles); \\operatorname{} for named operators.
- Tables use booktabs rules only — \\toprule, \\midrule, \\bottomrule — with NO vertical rules and no \\hline; every table is captioned and numbered.
- Title: short, declarative, content-first — state WHAT is proved ("PSL(2,11) is totally 3-closed" style). Never "report", "final proof", or "On some...".
- \\author{The Albilich Project} with \\thanks{This manuscript was generated by the Albilich automated theorem-proving system. The mathematical content was machine-verified as described in Appendix A; it has not yet been reviewed by a human mathematician.}; \\subjclass[2020]{...} and \\keywords{...}.
- Abstract, at most 150 words, self-contained (no citation labels, no internal notation): the central notion informally defined, the main result stated precisely, the method named, the source problem answered.
- Introduction stating the main result as Theorem A in a theorem environment; notation and preliminaries (structural data in properly captioned, numbered tables); the mathematical development, each lemma with a sentence of motivation, a self-contained statement, and a complete prose proof — case analyses written inside the proof as "Case 1: ..." with each case a full argument; the computation section stating the machine-verified outcome as a numbered Proposition with one or two captioned tables; the proof of Theorem A assembled with explicit cross-references ("By Proposition 5.2 and Lemma 3.4 ..."); final remarks on what remains open, without grandstanding.
- \\appendix, Appendix A (Certification): the complete finite-certificate data as tables/enumerations, with a description sufficient for independent reverification, and a closing "Run archive" paragraph — the ONLY place internal artifact identifiers may appear.
- Acknowledgment section (unnumbered) repeating the AI-generation disclosure in one sentence.
- \\begin{thebibliography}: real works only, drawn from the packet's literature list, complete data (authors, title, journal or arXiv identifier, year), alphabetically ordered, and every entry cited at least once in the text. If the literature list lacks something you want, write around it; NEVER invent, approximate, or embellish a reference.

"""

_PAPER_CONTRACT_TAIL = """

ABSOLUTE REGISTER WALL (deterministically enforced): the main text must never contain markdown syntax (#, bullet asterisks, backticks, bracketed links) or internal system vocabulary — "artifact", "manifest", "ledger", "debt", "revision", "verifier", "dossier", "proof-state", "run id", or any art_* identifier. These may appear only in the Run archive paragraph of Appendix A.

FAITHFULNESS:
- Every mathematical claim traces to the certificate or to a cited literature item. If the certificate leaves a step implicit, prove it in the paper or state it explicitly as part of what the verification assumes — never silently smooth it.
- State the status of every assertion honestly: proved here, cited, or machine-verified (with pointer to Appendix A)."""

PAPER_CONTRACT = _PAPER_CONTRACT_HEAD + WRITING_STYLE_CORE + _PAPER_CONTRACT_TAIL

EDITOR_DIRECTIVE = """You are the exposition editor for a top mathematics journal. MATHEMATICAL CORRECTNESS IS ASSUMED AND OUT OF SCOPE: the result has been machine-verified; do not re-derive, question, or re-prove the mathematics. Your sole charge is whether this LaTeX article reads as a publishable paper.

Judge against the standards of a published research article: an accurate self-contained abstract; an introduction that opens with the mathematical phenomenon, states the main theorem within two pages, gives an honest specific history, a strategy paragraph, and a roadmap; motivated, self-contained lemma statements with complete prose proofs (no bullet-list or table-of-assertions proof bodies); minimal consistent notation; complete punctuated sentences including displayed formulas; sober register with no internal system vocabulary; a real bibliography where every entry is cited and drawn from verifiable literature.

Deliver ONE of:
- verdict "pass" (attach writing_review, verdict=pass) when the paper meets the standard — at most stylistic nits remain; do not fail a paper over taste.
- verdict "fail" with AT MOST 12 findings, each as one add_debt: the specific location (section/paragraph/line), what is wrong, and a concrete suggested rewrite (one or two sentences of replacement text where feasible). Rank by importance. Never request mathematical changes; never request restructuring beyond what the finding names; no vague findings ("improve flow") — every finding must be actionable as a local edit.

SLOP HUNT: this manuscript was machine-generated; hunt the residual fingerprints of machine prose per the AI-SLOP and HOUSE rubric rules — significance inflation, copula avoidance, task-narration transitions, elegant variation, uniform paragraph rhythm, hedging stacks, recap paragraphs, vague-pronoun openers, "we" indiscipline, project-planning register in background sections. Any minor slop debts listed in the packet are confirmed deterministic findings: turn each into a concrete rewrite in your findings if the local fix is not obvious. Read the abstract, introduction, section openings, and theorem statements as if aloud: they must sound like mathematical prose, not an implementation plan. Section openers ("In this section, we ...", "In this appendix, we ...") and the "we"-collocation discipline (no habitual "we recall"/"we note that"-style openers) are HARD house rules enforced deterministically — verify both in every section."""

# Legacy multi-lens standard (pre-editor gate); still referenced by the legacy
# lens directives in codex_runner so old review data and prompts stay coherent.
PAPER_STANDARD_FOR_CRITICS = """The document under review is a LaTeX research article intended for a top mathematics journal. Judge it against published-paper standards, NOT internal-report standards. Automatic blocking findings (severity blocking) include: prose that reads as a ported internal report; proof bodies that are bullet lists, assertion tables, or pointers to a certificate; a missing or non-self-contained abstract; an introduction that fails to define the central notion, state the problem, and state the main theorem within the first two pages; internal system vocabulary (artifact, manifest, ledger, debt, revision, verifier, proof-state, run identifiers) in the main text; a bibliography without real literature entries or with entries not drawn from verifiable works; mathematical claims stronger than what the certification appendix supports. Major findings include: theorem statements that depend on surrounding text; unexplained notation; missing motivation before key lemmas; tables without captions or numbers; displayed equations without punctuation."""

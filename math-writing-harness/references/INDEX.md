# Master Index — Mathematical Writing Standards Corpus

This folder is a **knowledge base**, not an archive of the original documents. Each
source below is listed with its canonical URL so you (or a fetch step in the harness)
can retrieve the original. The `references/*.md` files contain **distilled, paraphrased**
rules derived from these sources, reorganized for machine use. The distillations are in
our own words; consult the originals for authoritative wording and full context.

Every rule in the `rubric/` folder cites back to one or more of these sources by the
short **KEY** given in brackets.

**Fetch status (2026-07-08):** all keys below have been fetched from their originals and
distilled verbatim-faithfully into `references/fetched/<KEY>.md` — these supersede the
paraphrased `references/*.md` files as the authoritative in-repo record. Exceptions:
`HIGHAM` (paywalled SIAM book — paraphrase only, flagged unverified); `MAURER`'s full
Short Guide manuscript (author restricts circulation — his published PRIMUS article and
public handout are fetched instead); `ARXIV-AI-2026` primaries (paywalled; distilled from
secondary coverage — re-verify before ship); `MSC` (classification scheme, not writing
advice); `PAK-BLOG` (confirmed subsumed by `PAK-CLEAR`). Publisher AI policies live in
`fetched/GOVERNANCE.md` and MUST be re-fetched before any actual submission.

---

## A. Canonical essays & books  → `canonical-essays.md`

| KEY | Author / Title | URL |
|-----|----------------|-----|
| `HALMOS` | P. R. Halmos, *How to Write Mathematics* (L'Enseignement Mathématique, 1970; AMS reprint 1973) | https://sites.stat.columbia.edu/liam/teaching/HalmosWrite.pdf · https://entropiesschool.sciencesconf.org/data/How_to_Write_Mathematics.pdf |
| `KLR` | D. Knuth, T. Larrabee, P. Roberts, *Mathematical Writing* (MAA Notes 14, 1989) — Stanford CS209 notes | https://jmlr.csail.mit.edu/reviewing-papers/knuth_mathematical_writing.pdf · https://www-cs-faculty.stanford.edu/~knuth/klr.html |
| `TAO` | T. Tao, *On writing* (blog hub + advice) | https://terrytao.wordpress.com/advice-on-writing-papers/ |
| `TAO-READ` | T. Tao, notes on "compilation errors," local vs. global errors in reading math | linked from the `TAO` hub |
| `PAK-CLEAR` | I. Pak, *How to Write a Clear Math Paper: Some 21st Century Tips* (J. Humanistic Math. 8(1), 2018) | https://www.math.ucla.edu/~pak/papers/how-to-write1.pdf |
| `PAK-STORY` | I. Pak, *How to Tell a Good Mathematical Story* (Notices AMS Early Career) | https://www.math.ucla.edu/~pak/papers/what-to-write2.pdf |
| `PAK-BLOG` | I. Pak, blog: "How to write math papers clearly" / "How to start a paper" | https://igorpak.wordpress.com/2017/07/12/how-to-write-math-papers-clearly/ |
| `ROTA` | G.-C. Rota, *Ten Lessons I Wish I Had Been Taught* (Notices AMS 44, 1997) | https://www.ams.org/notices/199701/comm-rota.pdf |
| `HIGHAM` | N. J. Higham, *Handbook of Writing for the Mathematical Sciences* (SIAM, 1998/2020) | (book) https://epubs.siam.org/doi/book/10.1137/1.9780898719550 |
| `KRANTZ` | S. Krantz, *A Primer of Mathematical Writing* | https://arxiv.org/abs/1612.04888 |

## B. Professors' rule sheets (most "rubric-ready")  → `professor-rulesheets.md`

| KEY | Author / Title | URL |
|-----|----------------|-----|
| `CONRAD` | K. Conrad, *Advice on Mathematical Writing* | https://kconrad.math.uconn.edu/blurbs/proofs/writingtips.pdf |
| `POONEN` | B. Poonen, *Practical Suggestions for Mathematical Writing* | https://math.mit.edu/~poonen/papers/writing.pdf |
| `POONEN-SPK` | B. Poonen, *Practical Suggestions for Mathematical Speaking* (relevant to exposition) | https://math.mit.edu/~poonen/papers/speaking.pdf |
| `SU` | F. E. Su, *Some Guidelines for Good Mathematical Writing* (MAA) | https://www.math.clemson.edu/~macaule/classes/m20_math4120/docs/good-math-writing.pdf · https://scholarship.claremont.edu/hmc_fac_pub/1145/ |
| `LEE` | K. P. Lee, *A Guide to Writing Mathematics* (UC Davis) | https://web.cs.ucdavis.edu/~amenta/w10/writingman.pdf |
| `MAURER` | S. Maurer, *Advice for Undergraduates on Special Aspects of Writing Mathematics* (PRIMUS) | https://mathstat.tcnj.edu/wp-content/uploads/sites/200/2011/08/Mauere_WRITE_PRIMUS.pdf |

## C. Anti-pattern catalogs (invert into critic checks)  → `antipatterns.md`

| KEY | Author / Title | URL |
|-----|----------------|-----|
| `MILNE` | J. S. Milne, *Tips for Authors* (sardonic — how to write badly) | https://www.jmilne.org/math/tips.html |
| `SERRE` | J.-P. Serre, *How to Write Mathematics Badly* (video lecture) | (video) widely mirrored; see `TAO` hub |
| `AARONSON` | S. Aaronson, *Ten Signs a Claimed Mathematical Breakthrough Is Wrong* | https://scottaaronson.blog/?p=304 |

## D. Institutional & journal standards  → `institutional-standards.md`

| KEY | Author / Title | URL |
|-----|----------------|-----|
| `AMS-HB` | AMS Author Handbook (Journals; Proceedings & Collections) | https://www.ams.org/arc/handbook/handbook-journals.pdf · https://www.ams.org/arc/handbook/handbook-proccoll.pdf |
| `AMS-STYLE` | AMS Style Guide (Journals) | https://www.ams.org/publications/authors/AMS-StyleGuide-online.pdf |
| `AMS-NOTICES` | AMS *Notices* Author Guidelines (audience/accessibility) | https://www.ams.org/publications/notices/authorguidelines |
| `MSC` | 2020 Mathematics Subject Classification | https://www.ams.org/msc |
| `WILEY` | Wiley *Journal of Mathematics* Author Guidelines | https://onlinelibrary.wiley.com/page/journal/1469/homepage/author-guidelines |
| `SPRINGER` | Springer submission guidelines (representative) | https://link.springer.com/journal/13162/submission-guidelines |

## D2. House rules & AI-pattern catalogs  → `fetched/HOUSE.md`, `fetched/AI-SLOP.md`

| KEY | Source | URL |
|-----|----------------|-----|
| `HOUSE` | Operator's WRITING_RULES.md (Exceptional Isomorphisms project; local, authoritative — outranks conflicting general advice) | (local file, imported 2026-07-09) |
| `AI-SLOP` | Wikipedia "Signs of AI writing" (WikiProject AI Cleanup) + Kobak et al. excess vocabulary + stop-slop catalog, adapted for mathematical prose | https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing · https://arxiv.org/abs/2406.07016 |

## E. AI / generative-model governance  → `ai-governance.md`

| KEY | Author / Title | URL |
|-----|----------------|-----|
| `ARXIV-AI-2023` | arXiv policy: generative AI cannot be an author | https://blog.arxiv.org/2023/01/31/arxiv-announces-new-policy-on-chatgpt-and-similar-tools/ |
| `ARXIV-AI-2026` | arXiv enforcement: 1-yr ban for unverified LLM content (hallucinated cites, residual prompts) | https://www.insidehighered.com/news/faculty/books-publishing/2026/05/22/ban-authors-who-submit-ai-content-welcome-unenforceable · https://www.timeshighereducation.com/news/ban-authors-submitting-ai-content-welcome-unenforceable |
| `ARXIV-REVIEW` | arXiv CS practice change for review/survey/position papers (Oct 2025) | https://blog.arxiv.org/2025/10/31/attention-authors-updated-practice-for-review-articles-and-position-papers-in-arxiv-cs-category/ |
| `PUB-AI` | Cross-publisher consensus: no AI authorship; disclosure required | https://www.monperrus.net/martin/generative-ai-scientific-writing · https://www.thesify.ai/blog/ai-policies-academic-publishing-2025 |

---

## How the harness consumes this folder

- **The Pedant** (style linter) loads `professor-rulesheets.md` + rubric `L4`.
- **The Skeptical Editor** loads `antipatterns.md` + `canonical-essays.md` (Tao/Pak on story & motivation) + rubric `L3`.
- **The Referee** loads `canonical-essays.md` (Tao local/global error taxonomy) + `antipatterns.md` (`AARONSON`) + rubric `L1`.
- **The Confused Reader** loads *nothing from here* — it must stay context-starved (see README).
- **The Provenance Auditor** loads `ai-governance.md` + rubric `L1`/`L5` citation rules.
- **Stage-0 rubric compilation** ingests all of B, C, D and the checkable parts of A.

# GOVERNANCE — AI-use policies from arXiv + publishers (fetched 2026-07-08; primary pages fetched except where noted; covers INDEX keys ARXIV-AI-2023, ARXIV-AI-2026, ARXIV-REVIEW, PUB-AI, WILEY, SPRINGER)

These are the L1/L5 ship-blocking constraints for any AI-assisted mathematical paper. Policies change; RE-FETCH BEFORE ANY SUBMISSION.

## ARXIV-AI-2023 — arXiv policy on generative AI (blog.arxiv.org, Jan 31 2023; fetched verbatim)
1. Disclosure: arXiv "continue[s] to require authors to report in their work any significant use of sophisticated tools, such as instruments and software; we now include in particular text-to-text generative AI among those that should be reported consistent with subject standards for methodology."
2. Responsibility: "by signing their name as an author of a paper, they each individually take full responsibility for all its contents, irrespective of how the contents were generated."
3. Authorship: "generative AI language tools should not be listed as an author."

## ARXIV-AI-2026 — enforcement escalation (May 2026; primary articles paywalled — from local distillation in ai-governance.md; re-verify before ship)
4. arXiv enforcement practice: authors submitting unverified LLM-generated content (hallucinated citations, residual prompt text) face a 1-year submission ban. → Hallucinated citations and prompt/instruction residue are EXISTENTIAL failures, not style nits.

## ARXIV-REVIEW — arXiv CS practice change for review/survey/position papers (blog.arxiv.org, Oct 31 2025; fetched)
5. Review/survey/position papers in arXiv CS now require PRIOR acceptance at a peer-reviewed journal or conference (workshop review does not qualify), with the reference + DOI in metadata. Reason, verbatim: "Generative AI / large language models have added to this flood by making papers — especially papers not introducing new research results — fast and easy to write"; "The majority of the review articles we receive are little more than annotated bibliographies, with no substantial discussion of open research issues." → An LLM-written survey that is an annotated bibliography without substantive discussion of open problems is a recognized, rejected genre.

## PUB-AI — cross-publisher consensus (monperrus survey, fetched; per-publisher primaries where fetched)
6. Universal floor across arXiv/ACM/IEEE/Elsevier/Springer/Wiley: (a) AI cannot be an author; (b) significant AI use must be disclosed; (c) human authors bear full responsibility for all content; (d) pure grammar/copy-editing assistance is exempt from disclosure.
7. IEEE (Apr 2024): "The AI system used shall be identified, and specific sections [containing AI-generated content] shall be identified and accompanied by a brief explanation" — in the acknowledgments. Grammar/editing tools exempt.
8. ACM: disclosure tiered by volume — "The level of disclosure should be commensurate with the proportion of new text or content generated": large sections → appendix with tools, versions, prompts, post-editing; small amounts → footnote + acknowledgment; minor editing → none.
9. Elsevier: AI "should not be listed as an author or co-author, or be cited as an author"; use limited to improving readability/language, with human oversight, disclosed in the manuscript.

## WILEY — Best Practice Guidelines, AI section (authors.wiley.com, fetched verbatim)
10. "AI Technology … cannot fulfil the role of an author and must not be listed as one."
11. "Authors should document all AI Technology used, including its purpose" and "must also disclose their use of AI Technologies when submitting." Spelling/grammar/general-editing tools exempt.
12. "Authors remain fully accountable for their submissions and any tools or sources they use" and "fully responsible for the accuracy of all content"; AI is "an additional tool in their writing process, not a replacement."
13. Rights: authors must not use AI tools that gain rights over the underlying content (incl. training rights) or restrict its use.

## SPRINGER — Springer Nature editorial policies (springernature.com, fetched)
14. "SN does not attribute authorship to AI."
15. "SN does not allow the inclusion of generative AI images in our publications."
16. "SN asks peer reviewers not to upload manuscripts into generative AI tools."
17. Nature Portfolio detail page (idp-gated; from local distillation): LLM use documented in Methods (or a suitable alternative section); AI-assisted copy editing that does not generate substantive content need not be declared.

## Venue-mechanics keys subsumed elsewhere
- MSC (ams.org/msc): 2020 Mathematics Subject Classification — full codes required in \subjclass (see AMS-HB rule 5); a classification scheme, not writing advice.
- HIGHAM (SIAM Handbook, 2020 3rd ed.): paywalled book, not fetchable; rely on the local paraphrase in institutional-standards.md and the overlap with AMS-STYLE/KLR; flagged as unverified-against-original.
- PAK-BLOG (2017 post): precursor of PAK-CLEAR with identical citation-ladder content; fetched and confirmed subsumed by PAK-CLEAR.md.

## Operative rubric consequences (blockers)
B1. Every citation must exist and be verifiable (hallucinated citation = ship-blocker + platform-ban risk).
B2. No prompt/instruction residue anywhere in the artifact (residual scaffolding = "unverified LLM content").
B3. AI-use disclosure block present and venue-appropriate (arXiv: report significant use; IEEE/ACM: section-level identification; Wiley/Elsevier: submission disclosure).
B4. No AI listed as author anywhere (byline, acknowledgments-as-author, metadata).
B5. Human responsibility gate: a named human has verified every claim ("full responsibility for all its contents").
B6. No generative-AI images for Springer venues.
B7. Survey/review genre: must contain substantive discussion of open research issues, not an annotated bibliography.

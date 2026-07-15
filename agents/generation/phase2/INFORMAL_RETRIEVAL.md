# Informal theorem retrieval (Matlas / TheoremSearch)

This is the minimal port of the v1.5 informal search tools. The two providers
are available only to `literature_researcher` sessions in `retrieve` mode.
Researchers, villains, advisors, and verifiers do not receive a search
capability; they consume persisted retrieval cards.

## Informal providers

- Matlas OpenAPI 0.1.0: `POST /api/search` (body `{"query", "num_results"}`,
  `num_results >= 10`) and `GET /api/health`.
- UW TheoremSearch OpenAPI 0.1.0: `POST /search` (body `{"query", "n_results"}`
  plus optional documented filters) and `GET /ping`.

There are deliberately no Lean, Mathlib, or formal-premise providers in this
module. Production endpoints are HTTPS-origin pinned to `https://matlas.ai` and
`https://api.theoremsearch.com`. The `RETHLAS_MATLAS_BASE_URL` and
`RETHLAS_THEOREMSEARCH_BASE_URL` environment variables may select only those
approved origins; they cannot redirect production retrieval to an arbitrary
host. Hermetic tests inject a different HTTPS origin explicitly through an
adapter constructor together with a fixture transport.

## Invocation

The orchestrator executes the tool calls while compiling a retrieve-mode
context (`context_builder._informal_theorem_search_task` calling
`retrieval.execute_informal_theorem_search`); the child session never holds
provider credentials or a raw network primitive. Live execution is off by
default and is enabled per action (`action["informal_search_enabled"]`) or per
run (`RETHLAS_INFORMAL_SEARCH=1|true|yes|on|live`). Optional action knobs:
`informal_search_providers`, `informal_search_limit`,
`informal_provider_filters`.

The retrieve packet always carries the tool contract at
`manifest.research_task.informal_theorem_search`; bounded candidates appear
under `results` when execution is enabled and a provider answers.

## Graceful degradation

Provider outage, misconfiguration, or a contract violation is recorded as an
inert per-provider status entry (and `results.status` stays observable); it
never raises into context compilation or the proof workflow. The retrieve
session then falls back to the existing local-search plus Codex web-search
flow.

## Provider-data boundary

The transport refuses non-HTTPS endpoints and cross-origin redirects, validates
the final response origin, and stops reading at 2,000,000 response bytes. Each
adapter emits at most 200 candidates. Provider-controlled strings are
normalized to NFC, stripped of control/bidirectional formatting characters,
whitespace normalized, and bounded; an overlong theorem statement or candidate
identifier is discarded rather than silently represented as an exact theorem.
All provider-derived text is labeled `untrusted_inert_provider_data` and must be
treated as quoted data, not instructions. A candidate becomes literature
evidence only after the literature reviewer inspects the cited primary source
and caches a retrieval card copying the candidate's `provider` and
`provider_candidate_id`.

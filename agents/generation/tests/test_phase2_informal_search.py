from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2 import context_builder
from agents.generation.phase2.codex_runner import _base_mode_guidance
from agents.generation.phase2.context_builder import _informal_theorem_search_task, _research_task
from agents.generation.phase2.retrieval import (
    INFORMAL_PROVIDER_NAMES,
    MATLAS_CONTRACT_VERSION,
    PROVIDER_TEXT_TRUST,
    THEOREMSEARCH_CONTRACT_VERSION,
    HttpJsonResponse,
    LiteratureSearchAuthorizationError,
    MatlasAdapter,
    ProviderContractError,
    ProviderRequestError,
    TheoremSearchAdapter,
    execute_informal_theorem_search,
    informal_candidate_card_operation,
    informal_provider_names_for_action,
    informal_search_enabled,
)


MATLAS_RESULT = {
    "type": "paper",
    "entity_name": "Theorem 4.2",
    "doi": "10.1000/example",
    "title": "An Informal Theorem",
    "authors": ["Ada Author", "Bernhard Author"],
    "journal": "Journal of Tests",
    "year": 2025,
    "statement": "Every widget satisfying H has property P.",
    "candidate_id": "matlas-candidate-1",
}

THEOREMSEARCH_RESULT = {
    "slogan_id": "slogan-1",
    "theorem_id": "theorem-1",
    "name": "Widget theorem",
    "body": "Every widget satisfying H has property P.",
    "slogan": "H-widgets have P",
    "theorem_type": "theorem",
    "label": "Theorem 4.2",
    "link": "https://arxiv.org/abs/2501.00001",
    "paper": {
        "title": "An Informal Theorem",
        "authors": ["Ada Author", "Bernhard Author"],
        "year": 2025,
        "arxiv_id": "2501.00001v2",
    },
    "similarity": 0.91,
    "score": 0.88,
    "has_metadata": True,
}


class FixtureTransport:
    def __init__(self) -> None:
        self.posts: list[tuple[str, Mapping[str, Any], float]] = []
        self.gets: list[str] = []

    def post_json(self, url: str, payload: Mapping[str, Any], *, timeout_seconds: float) -> HttpJsonResponse:
        self.posts.append((url, dict(payload), timeout_seconds))
        if "matlas" in url:
            return HttpJsonResponse(200, [dict(MATLAS_RESULT)], {"x-index-version": "matlas-fixture-2026-07"})
        return HttpJsonResponse(
            200,
            {"theorems": [dict(THEOREMSEARCH_RESULT)]},
            {"x-index-version": "theoremsearch-fixture-2026-07"},
        )

    def get_json(self, url: str, *, timeout_seconds: float) -> HttpJsonResponse:
        self.gets.append(url)
        return HttpJsonResponse(200, {"status": "ok"}, {})


class FailingTransport:
    def __init__(self) -> None:
        self.calls = 0

    def post_json(self, url: str, payload: Mapping[str, Any], *, timeout_seconds: float) -> HttpJsonResponse:
        self.calls += 1
        raise ProviderRequestError("fixture outage", error_code="fixture_outage")

    def get_json(self, url: str, *, timeout_seconds: float) -> HttpJsonResponse:
        raise ProviderRequestError("fixture outage", error_code="fixture_outage")


class MatlasAdapterContractTest(unittest.TestCase):
    def test_search_uses_openapi_contract_and_parses_candidates(self) -> None:
        transport = FixtureTransport()
        adapter = MatlasAdapter(base_url="https://matlas.test", transport=transport)
        result = adapter.search("widget theorem", limit=5, filters={}, timeout_seconds=5.0)
        self.assertEqual(adapter.contract_version, MATLAS_CONTRACT_VERSION)
        self.assertEqual(transport.posts[0][0], "https://matlas.test/api/search")
        # OpenAPI 0.1.0 requires at least ten results per request.
        self.assertEqual(transport.posts[0][1], {"query": "widget theorem", "num_results": 10})
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.exact_statement, MATLAS_RESULT["statement"])
        self.assertEqual(candidate.provider, "matlas")
        self.assertEqual(candidate.source_identifiers["provider_candidate_id"], "matlas-candidate-1")
        self.assertEqual(candidate.source_identifiers["provider_origin"], "https://matlas.test")
        self.assertEqual(candidate.raw_metadata["provider_text_trust"], PROVIDER_TEXT_TRUST)
        self.assertEqual(result.index_version, "matlas-fixture-2026-07")
        self.assertTrue(adapter.health(timeout_seconds=5.0))
        self.assertEqual(transport.gets[-1], "https://matlas.test/api/health")

    def test_contract_violation_raises(self) -> None:
        adapter = MatlasAdapter(base_url="https://matlas.test", transport=FixtureTransport())
        with self.assertRaises(ProviderContractError):
            adapter.parse_response({}, request_payload={"query": "x"})
        with self.assertRaises(ProviderContractError):
            adapter.parse_response([{"type": "paper"}], request_payload={"query": "x"})

    def test_environment_override_is_pinned_to_approved_origins(self) -> None:
        with mock.patch.dict(os.environ, {"RETHLAS_MATLAS_BASE_URL": "https://attacker.example"}):
            with self.assertRaises(ValueError):
                MatlasAdapter(transport=FixtureTransport())
        with mock.patch.dict(os.environ, {"RETHLAS_MATLAS_BASE_URL": "https://matlas.ai"}):
            adapter = MatlasAdapter(transport=FixtureTransport())
        self.assertEqual(adapter.base_url, "https://matlas.ai")


class TheoremSearchAdapterContractTest(unittest.TestCase):
    def test_search_uses_openapi_contract_and_parses_candidates(self) -> None:
        transport = FixtureTransport()
        adapter = TheoremSearchAdapter(base_url="https://theoremsearch.test", transport=transport)
        result = adapter.search(
            "widget theorem",
            limit=5,
            filters={"sources": ["arxiv"], "year_range": [2020, 2026]},
            timeout_seconds=5.0,
        )
        self.assertEqual(adapter.contract_version, THEOREMSEARCH_CONTRACT_VERSION)
        self.assertEqual(transport.posts[0][0], "https://theoremsearch.test/search")
        self.assertEqual(transport.posts[0][1]["n_results"], 5)
        self.assertEqual(transport.posts[0][1]["sources"], ["arxiv"])
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.provider, "theoremsearch")
        self.assertEqual(candidate.exact_statement, THEOREMSEARCH_RESULT["body"])
        self.assertEqual(candidate.source_identifiers["arxiv"], "2501.00001v2")
        self.assertEqual(candidate.source_identifiers["provider_origin"], "https://theoremsearch.test")
        self.assertEqual(result.index_version, "theoremsearch-fixture-2026-07")
        self.assertTrue(adapter.health(timeout_seconds=5.0))
        self.assertEqual(transport.gets[-1], "https://theoremsearch.test/ping")

    def test_unknown_filters_are_rejected(self) -> None:
        adapter = TheoremSearchAdapter(base_url="https://theoremsearch.test", transport=FixtureTransport())
        with self.assertRaises(ValueError):
            adapter.build_request("widget", limit=5, filters={"bogus_filter": 1})

    def test_contract_violation_raises(self) -> None:
        adapter = TheoremSearchAdapter(base_url="https://theoremsearch.test", transport=FixtureTransport())
        with self.assertRaises(ProviderContractError):
            adapter.parse_response([], request_payload={"query": "x"})

    def test_environment_override_is_pinned_to_approved_origins(self) -> None:
        with mock.patch.dict(os.environ, {"RETHLAS_THEOREMSEARCH_BASE_URL": "https://attacker.example"}):
            with self.assertRaises(ValueError):
                TheoremSearchAdapter(transport=FixtureTransport())


class ExecuteInformalTheoremSearchTest(unittest.TestCase):
    def _providers(self, matlas_transport: Any = None, theoremsearch_transport: Any = None) -> list[Any]:
        return [
            MatlasAdapter(base_url="https://matlas.test", transport=matlas_transport or FixtureTransport()),
            TheoremSearchAdapter(
                base_url="https://theoremsearch.test",
                transport=theoremsearch_transport or FixtureTransport(),
            ),
        ]

    def test_search_is_restricted_to_the_literature_researcher_role(self) -> None:
        with self.assertRaises(LiteratureSearchAuthorizationError):
            execute_informal_theorem_search("widget", actor_role="researcher", mode="prove", providers=self._providers())
        with self.assertRaises(LiteratureSearchAuthorizationError):
            execute_informal_theorem_search("widget", actor_role="villain", mode="refute", providers=self._providers())
        with self.assertRaises(LiteratureSearchAuthorizationError):
            execute_informal_theorem_search(
                "widget", actor_role="literature_researcher", mode="prove", providers=self._providers()
            )

    def test_both_providers_contribute_candidates(self) -> None:
        result = execute_informal_theorem_search("widget theorem", providers=self._providers(), limit=5)
        self.assertEqual(result["tool"], "informal_theorem_search")
        self.assertFalse(result["degraded"])
        statuses = {entry["provider"]: entry["status"] for entry in result["provider_status"]}
        self.assertEqual(statuses, {"matlas": "completed", "theoremsearch": "completed"})
        self.assertEqual({item["provider"] for item in result["candidates"]}, INFORMAL_PROVIDER_NAMES)
        for candidate in result["candidates"]:
            self.assertEqual(candidate["provider_text_trust"], PROVIDER_TEXT_TRUST)
        self.assertEqual(result["provider_content_policy"]["provider_text_trust"], PROVIDER_TEXT_TRUST)

    def test_single_provider_outage_degrades_gracefully(self) -> None:
        result = execute_informal_theorem_search(
            "widget theorem",
            providers=self._providers(matlas_transport=FailingTransport()),
            limit=5,
        )
        statuses = {entry["provider"]: entry for entry in result["provider_status"]}
        self.assertEqual(statuses["matlas"]["status"], "failed")
        self.assertEqual(statuses["matlas"]["error_code"], "fixture_outage")
        self.assertEqual(statuses["matlas"]["error"], "fixture outage")
        self.assertEqual(statuses["theoremsearch"]["status"], "completed")
        self.assertFalse(result["degraded"])
        self.assertEqual({item["provider"] for item in result["candidates"]}, {"theoremsearch"})

    def test_total_outage_reports_degraded_without_raising(self) -> None:
        result = execute_informal_theorem_search(
            "widget theorem",
            providers=self._providers(
                matlas_transport=FailingTransport(),
                theoremsearch_transport=FailingTransport(),
            ),
        )
        self.assertTrue(result["degraded"])
        self.assertEqual(result["candidates"], [])
        self.assertEqual({entry["status"] for entry in result["provider_status"]}, {"failed"})

    def test_empty_query_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            execute_informal_theorem_search("   ", providers=self._providers())

    def test_unknown_provider_names_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            execute_informal_theorem_search("widget", providers=["mathlib"])
        with self.assertRaises(ValueError):
            informal_provider_names_for_action({"informal_search_providers": "matlas,lean_premises"})
        self.assertEqual(
            informal_provider_names_for_action({"informal_search_providers": "theoremsearch"}),
            ("theoremsearch",),
        )


class InformalCandidateIngestionTest(unittest.TestCase):
    def test_candidate_becomes_unverified_retrieval_card_operation(self) -> None:
        result = execute_informal_theorem_search(
            "widget theorem",
            providers=[MatlasAdapter(base_url="https://matlas.test", transport=FixtureTransport())],
        )
        op = informal_candidate_card_operation(result["candidates"][0], query="widget theorem", target_id="claim-7")
        self.assertEqual(op["op"], "cache_retrieval_card")
        self.assertTrue(op["card_id"].startswith("retrieval-"))
        self.assertEqual(op["target_id"], "claim-7")
        self.assertEqual(op["exact_statement"], MATLAS_RESULT["statement"])
        self.assertEqual(op["source_identifiers"]["provider"], "matlas")
        self.assertEqual(op["applicability"]["provider"], "matlas")
        self.assertEqual(op["applicability"]["provider_candidate_id"], "matlas-candidate-1")
        self.assertEqual(op["applicability"]["theorem_matching_status"], "unverified_provider_candidate")
        self.assertFalse(op["applicability"]["implication_to_target_verified"])
        self.assertEqual(op["applicability"]["provider_text_trust"], PROVIDER_TEXT_TRUST)
        self.assertTrue(op["missing_hypotheses"])
        self.assertEqual(op["source_version"], "10.1000/example")

    def test_non_provider_candidates_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            informal_candidate_card_operation({"provider": "wikipedia", "exact_statement": "x"}, query="q")
        with self.assertRaises(ValueError):
            informal_candidate_card_operation({"provider": "matlas", "exact_statement": "  "}, query="q")


class RetrieveDirectiveContractTest(unittest.TestCase):
    def test_retrieve_directive_carries_both_tool_contracts(self) -> None:
        guidance = _base_mode_guidance("retrieve", "literature_researcher", "", {})
        self.assertIn("Matlas", guidance)
        self.assertIn("TheoremSearch", guidance)
        self.assertIn("POST /api/search", guidance)
        self.assertIn("POST /search", guidance)
        self.assertIn("informal_theorem_search", guidance)
        self.assertIn("untrusted inert quoted data", guidance)
        self.assertIn("provider_candidate_id", guidance)
        # Graceful degradation stays in the directive.
        self.assertIn("provider unavailability is recorded evidence", guidance)

    def test_other_roles_and_modes_do_not_receive_the_tools(self) -> None:
        for mode, role in [
            ("prove", "researcher"),
            ("reduce", "researcher"),
            ("refute", "villain"),
            ("verify", "strict_informal_verifier"),
            ("integrate", "integration_verifier"),
            ("write", "writer"),
            ("review_writing", "writing_critic"),
            ("triage_routes", "phd_advisor"),
            ("regulate_decomposition", "phd_advisor"),
            ("synthesize_sources", "literature_researcher"),
            ("audit_definitions", "literature_researcher"),
        ]:
            guidance = _base_mode_guidance(mode, role, "", {}).lower()
            self.assertNotIn("matlas", guidance, msg=f"{role}/{mode}")
            self.assertNotIn("theoremsearch", guidance, msg=f"{role}/{mode}")


class ResearchTaskInformalSearchTest(unittest.TestCase):
    TARGET = {"claim_id": "root", "statement": "Every widget satisfying H has property P."}

    def test_retrieve_task_always_carries_the_tool_contract(self) -> None:
        task = _research_task({"mode": "retrieve"}, self.TARGET, [], state={"artifacts": []})
        block = task["informal_theorem_search"]
        providers = {entry["name"]: entry for entry in block["tool_contract"]["providers"]}
        self.assertEqual(set(providers), INFORMAL_PROVIDER_NAMES)
        self.assertEqual(providers["matlas"]["search_endpoint"], "POST /api/search")
        self.assertEqual(providers["matlas"]["origin"], "https://matlas.ai")
        self.assertEqual(providers["theoremsearch"]["search_endpoint"], "POST /search")
        self.assertEqual(providers["theoremsearch"]["origin"], "https://api.theoremsearch.com")
        # Evidence policy: the tool results are permitted leads for this session.
        self.assertIn("approved search leads for this retrieve session", block["evidence_rule"])
        self.assertEqual(block["provider_content_policy"]["provider_text_trust"], PROVIDER_TEXT_TRUST)
        # Default is off: no live provider call during hermetic context builds.
        self.assertEqual(block["results"]["status"], "not_executed")

    def test_non_retrieve_actions_get_no_informal_search_block(self) -> None:
        self.assertEqual(_research_task({"mode": "prove"}, self.TARGET, [], state={"artifacts": []}), {})
        self.assertEqual(_research_task({"mode": "synthesize_sources"}, self.TARGET, [], state={"artifacts": []}), {})

    def test_enabled_action_embeds_candidates(self) -> None:
        executed = {
            "tool": "informal_theorem_search",
            "query": "widget theorem",
            "provider_status": [{"provider": "matlas", "status": "completed", "result_count": 1}],
            "candidates": [{"provider": "matlas", "exact_statement": "s", "provider_text_trust": PROVIDER_TEXT_TRUST}],
            "degraded": False,
        }
        with mock.patch.object(context_builder, "execute_informal_theorem_search", return_value=dict(executed)) as call:
            task = _research_task(
                {"mode": "retrieve", "informal_search_enabled": True, "requested_query": "widget theorem"},
                self.TARGET,
                [],
                state={"artifacts": []},
            )
        block = task["informal_theorem_search"]
        self.assertEqual(block["results"]["status"], "completed")
        self.assertEqual(block["results"]["candidates"][0]["provider"], "matlas")
        self.assertEqual(call.call_args.args, ("widget theorem",))
        self.assertEqual(call.call_args.kwargs["actor_role"], "literature_researcher")
        self.assertEqual(call.call_args.kwargs["mode"], "retrieve")

    def test_enabled_action_falls_back_to_target_statement_query(self) -> None:
        with mock.patch.object(
            context_builder, "execute_informal_theorem_search", return_value={"candidates": []}
        ) as call:
            _research_task(
                {"mode": "retrieve", "informal_search_enabled": True},
                self.TARGET,
                [],
                state={"artifacts": []},
            )
        self.assertEqual(call.call_args.args, (self.TARGET["statement"],))

    def test_tool_failure_degrades_without_breaking_context_compilation(self) -> None:
        with mock.patch.object(
            context_builder,
            "execute_informal_theorem_search",
            side_effect=ProviderRequestError("all providers down", error_code="transport_error"),
        ):
            task = _research_task(
                {"mode": "retrieve", "informal_search_enabled": True, "requested_query": "widget theorem"},
                self.TARGET,
                [],
                state={"artifacts": []},
            )
        block = task["informal_theorem_search"]
        self.assertEqual(block["results"]["status"], "failed")
        self.assertEqual(block["results"]["error"], "all providers down")
        self.assertIn("use the existing search flow", block["results"]["reason"])
        self.assertIn("never a session failure", block["fallback_rule"])

    def test_environment_toggle_enables_search(self) -> None:
        self.assertFalse(informal_search_enabled({}))
        self.assertFalse(informal_search_enabled({"informal_search_enabled": False}))
        with mock.patch.dict(os.environ, {"RETHLAS_INFORMAL_SEARCH": "live"}):
            self.assertTrue(informal_search_enabled({}))
            # An explicit per-action opt-out still wins over the environment.
            self.assertFalse(informal_search_enabled({"informal_search_enabled": False}))
        self.assertTrue(informal_search_enabled({"informal_search_enabled": True}))


if __name__ == "__main__":
    unittest.main()

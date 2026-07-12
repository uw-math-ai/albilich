from __future__ import annotations

"""Acceptance tests for the 2026-07-09 update-advice TODO 3 pilot:

The Danus-style fact graph is a GENERATED, READ-ONLY view over the SQLite
proof state. Node classification matches memory_policy's status classifier
exactly, candidate facts never appear in verified_only queries, dependency
chains follow inference premises, blocks edges come from active debts only,
branch clustering matches branch_summary's route-anchored branch definition,
the graph feeds branch summaries (with output parity) and multi-branch
packets, and the report renders a Fact Graph health section.
"""

import json
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.branch_summary import (
    branch_cluster_claim_ids,
    build_branch_summary,
    _clip,
)
from agents.generation.phase2.fact_graph import (
    BranchCluster,
    CandidateFact,
    DERIVED_EDGE_TYPES,
    EDGE_TYPES,
    Obstruction,
    STUB_EDGE_TYPES,
    SourceFact,
    VerifiedFact,
    _derive_contradicts_edges,
    _derive_generalizes_edges,
    _derive_specializes_edges,
    build_fact_graph,
)
from agents.generation.phase2.memory_policy import claim_memory_status
from agents.generation.phase2.models import SCHEMA_VERSION, utc_now
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.report import build_markdown_report
from agents.generation.phase2.scheduler import _branch_packet_card
from agents.generation.phase2.store import ProofStateStore


def _make_store(tmpdir: str, problem_id: str) -> ProofStateStore:
    store = ProofStateStore(problem_id, generation_root=Path(tmpdir) / "generation")
    store.init_problem("Target theorem.")
    return store


def _apply(store: ProofStateStore, operations: list[dict], *, actor_role: str = "researcher") -> None:
    outcome = apply_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": store.get_revision(),
            "actor_role": actor_role,
            "target_id": "root",
            "operations": operations,
            "rationale": "test setup",
        },
    )
    if not outcome.accepted:
        raise AssertionError(f"setup patch rejected: {outcome.errors}")


def _sql(store: ProofStateStore, statement: str, params: tuple = ()) -> None:
    with closing(store.connect()) as conn:
        conn.execute(statement, params)
        conn.commit()


def _seed_graph_problem(store: ProofStateStore) -> None:
    """One branch (route-main -> lemma-main) with a two-step verified ladder
    (lemma-main <- lemma-done <- lemma-base), one refuted claim on a failed
    route, one challenged claim, one superseded claim, one fingerprint twin,
    active + resolved debts, and duplicate retrieval cards."""
    _apply(
        store,
        [
            {"op": "attach_artifact", "artifact_id": "main-dossier", "artifact_type": "proof_dossier", "content": "Main dossier.", "metadata": {"target_id": "lemma-main", "route_id": "route-main"}},
            {"op": "attach_artifact", "artifact_id": "done-dossier", "artifact_type": "proof_dossier", "content": "Done dossier.", "metadata": {"target_id": "lemma-done", "route_id": "route-main"}},
            {"op": "add_claim", "claim_id": "lemma-main", "kind": "lemma", "statement": "The main comb construction lemma holds.", "parent_ids": ["root"], "evidence_artifact_ids": ["main-dossier"]},
            {"op": "add_claim", "claim_id": "lemma-done", "kind": "lemma", "statement": "The labelled comb base case holds.", "parent_ids": ["lemma-main"], "evidence_artifact_ids": ["done-dossier"]},
            {"op": "add_claim", "claim_id": "lemma-base", "kind": "lemma", "statement": "The comb normalization identity holds.", "parent_ids": ["lemma-done"]},
            {"op": "add_claim", "claim_id": "lemma-bad", "kind": "lemma", "statement": "Every comb degeneration is smoothable.", "parent_ids": ["root"]},
            {"op": "add_claim", "claim_id": "lemma-chal", "kind": "lemma", "statement": "The teeth remain very free after specialization.", "parent_ids": ["root"]},
            {"op": "add_claim", "claim_id": "lemma-old", "kind": "lemma", "statement": "An early draft statement, since replaced.", "parent_ids": ["root"]},
            {"op": "add_claim", "claim_id": "lemma-twin", "kind": "lemma", "statement": "The labelled comb base case holds (twin phrasing).", "parent_ids": ["root"]},
            {"op": "add_route", "route_id": "route-main", "conclusion_claim_id": "lemma-main", "strategy": "labelled comb constructions"},
            {"op": "add_route", "route_id": "route-dead", "conclusion_claim_id": "lemma-bad", "strategy": "brute smoothing"},
            {
                "op": "add_inference",
                "inference_id": "inf-main",
                "route_id": "route-main",
                "conclusion_claim_id": "lemma-main",
                "premise_claim_ids": ["lemma-done"],
                "validation_status": "plausible",
                "explanation": "The dossier reduces the main lemma to the base case.",
                "evidence_artifact_ids": ["main-dossier"],
            },
            {
                "op": "add_inference",
                "inference_id": "inf-base",
                "route_id": "route-main",
                "conclusion_claim_id": "lemma-done",
                "premise_claim_ids": ["lemma-base"],
                "validation_status": "plausible",
                "explanation": "The base case follows from the normalization identity.",
                "evidence_artifact_ids": ["done-dossier"],
            },
            {
                "op": "add_debt",
                "debt_id": "debt-main",
                "owner_type": "route",
                "owner_id": "route-main",
                "debt_type": "proof_obligation",
                "severity": "blocking",
                "status": "active",
                "obligation": "Close the remaining comb-labelling degeneration for the main lemma.",
                "suggested_next_target": "lemma-main",
            },
            {
                "op": "add_debt",
                "debt_id": "debt-claim",
                "owner_type": "claim",
                "owner_id": "lemma-main",
                "debt_type": "proof_obligation",
                "severity": "major",
                "status": "active",
                "obligation": "Check the boundary labelling in the main lemma.",
                "suggested_next_target": "lemma-main",
            },
            {
                "op": "add_debt",
                "debt_id": "debt-fixed",
                "owner_type": "claim",
                "owner_id": "lemma-done",
                "debt_type": "proof_obligation",
                "severity": "major",
                "status": "active",
                "obligation": "Verify the base case combinatorics.",
                "suggested_next_target": "lemma-done",
            },
        ],
    )
    _apply(
        store,
        [
            {
                "op": "cache_retrieval_card",
                "card_id": "card-lit",
                "target_id": "root",
                "exact_statement": "A survey theorem about comb constructions.",
                "source_identifiers": {"title": "Survey"},
                "source_version": "v1",
                "source_location": "Theorem 1",
                "hypotheses": [],
                "local_definitions": [],
                "missing_hypotheses": [],
                "applicability": {"classification": "method_match", "target_id": "root"},
            }
        ],
        actor_role="literature_researcher",
    )
    # Status shaping that patch ops gate behind evidence rules: direct SQL.
    for claim_id in ("lemma-done", "lemma-base"):
        _sql(store, "UPDATE claims SET validation_status = 'informally_verified' WHERE claim_id = ?", (claim_id,))
    _sql(store, "UPDATE claims SET validation_status = 'refuted' WHERE claim_id = 'lemma-bad'")
    _sql(store, "UPDATE claims SET validation_status = 'challenged' WHERE claim_id = 'lemma-chal'")
    _sql(store, "UPDATE claims SET lifecycle_status = 'superseded' WHERE claim_id = 'lemma-old'")
    _sql(
        store,
        "UPDATE claims SET fingerprint = (SELECT fingerprint FROM claims WHERE claim_id = 'lemma-done') WHERE claim_id = 'lemma-twin'",
    )
    _sql(store, "UPDATE routes SET status = 'abandoned' WHERE route_id = 'route-dead'")
    _sql(
        store,
        "UPDATE debts SET status = 'resolved', resolution_evidence_json = ? WHERE debt_id = 'debt-fixed'",
        (json.dumps({"resolution_evidence_artifact_ids": ["done-dossier"]}),),
    )
    # Duplicate retrieval card (same exact_statement): canonicalization fodder.
    _sql(
        store,
        """
        INSERT INTO retrieval_cards(
            card_id, normalized_query, source_version, exact_statement, source_identifiers_json,
            hypotheses_json, local_definitions_json, applicability_json, missing_hypotheses_json,
            source_location, content_hash, retrieved_at
        ) VALUES ('card-dup', 'q', 'v1', 'A survey theorem about comb constructions.', '{}',
                  '[]', '[]', '{"classification": "method_match"}', '[]', 'Theorem 1', 'dup-hash', ?)
        """,
        (utc_now(),),
    )
    _sql(
        store,
        """
        INSERT INTO theorem_library_entries(
            entry_id, statement, normalized_statement, source_identifiers_json, source_version,
            source_location, certification_type, relation_to_target, evidence_artifact_ids_json,
            tags_json, created_at, updated_at
        ) VALUES ('lib-1', 'A cited comb theorem.', 'a cited comb theorem.', '{"title": "Book"}', 'v1',
                  'Theorem 2.1', 'external_citation', 'supporting', '[]', '[]', ?, ?)
        """,
        (utc_now(), utc_now()),
    )


class FactGraphNodeTests(unittest.TestCase):
    def test_node_classification_matches_memory_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "fact-graph-nodes")
            _seed_graph_problem(store)
            state = store.get_state()
            graph = build_fact_graph(store, state=state)
            expected_types = {"verified": VerifiedFact, "candidate": CandidateFact}
            for claim in state["claims"]:
                status = claim_memory_status(claim)
                node = graph.nodes.get(f"claim:{claim['claim_id']}")
                if status in expected_types:
                    self.assertIsInstance(node, expected_types[status], claim["claim_id"])
                    self.assertEqual(node.memory_status, status)
                elif status in {"blocked", "failed"}:
                    self.assertIsInstance(node, Obstruction, claim["claim_id"])
                else:  # superseded claims leave the view
                    self.assertIsNone(node, claim["claim_id"])
            # Verified facts carry their proof artifacts and dependency list.
            done = graph.nodes["claim:lemma-done"]
            self.assertIsInstance(done, VerifiedFact)
            self.assertIn("done-dossier", done.proof_artifact_ids)
            self.assertEqual(done.dependency_ids, ["claim:lemma-base"])
            # Refuted vs challenged claims become the right obstruction kinds.
            self.assertEqual(graph.nodes["claim:lemma-bad"].obstruction_kind, "refuted_claim")
            self.assertEqual(graph.nodes["claim:lemma-chal"].obstruction_kind, "blocked_claim")
            # Debts: active vs resolved obstruction; failed route obstruction.
            self.assertTrue(graph.nodes["debt:debt-main"].active)
            self.assertFalse(graph.nodes["debt:debt-fixed"].active)
            self.assertEqual(graph.nodes["route:route-dead"].obstruction_kind, "failed_route")
            # Sources: retrieval card (candidate) and library entry (verified).
            card = graph.nodes["card:card-lit"]
            self.assertIsInstance(card, SourceFact)
            self.assertEqual(card.memory_status, "candidate")
            self.assertEqual(card.checked_metadata["classification"], "method_match")
            self.assertEqual(graph.nodes["library:lib-1"].memory_status, "verified")

    def test_candidate_facts_never_appear_in_verified_only_queries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "fact-graph-verified-only")
            _seed_graph_problem(store)
            graph = build_fact_graph(store)
            for cluster in graph.branch_clusters():
                for fact in graph.facts_for_branch(cluster.branch_id, verified_only=True, include_inferences=True):
                    self.assertIsInstance(fact, VerifiedFact)
                    self.assertEqual(fact.memory_status, "verified")
            # route-main's cluster is lemma-main <- lemma-done (inf-base lives
            # on its own auto route because it concludes lemma-done).
            verified_ids = {fact.source_id for fact in graph.facts_for_branch("route-main", verified_only=True)}
            self.assertEqual(verified_ids, {"lemma-done"})
            self.assertNotIn("lemma-main", verified_ids)  # candidate conclusion
            all_ids = {fact.source_id for fact in graph.facts_for_branch("route-main", verified_only=False)}
            self.assertIn("lemma-main", all_ids)

    def test_branch_clustering_matches_branch_summary_definition(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "fact-graph-clusters")
            _seed_graph_problem(store)
            state = store.get_state()
            graph = build_fact_graph(store, state=state)
            cluster = graph.nodes["branch:route-main"]
            self.assertIsInstance(cluster, BranchCluster)
            claims_by_id = {row["claim_id"]: row for row in state["claims"]}
            expected = [
                f"claim:{claim_id}"
                for claim_id in branch_cluster_claim_ids(state, "route-main")
                if claim_memory_status(claims_by_id[claim_id]) in {"verified", "candidate"}
            ]
            claim_fact_ids = [node_id for node_id in cluster.fact_ids if node_id.startswith("claim:")]
            self.assertEqual(claim_fact_ids, expected)
            self.assertIn("debt:debt-main", cluster.obstruction_ids)
            # Membership is visible from the node side too.
            self.assertIn("route-main", graph.nodes["claim:lemma-done"].branch_ids)


class FactGraphEdgeTests(unittest.TestCase):
    def _edges(self, graph, edge_type: str) -> set[tuple[str, str]]:
        return {(edge.source_id, edge.target_id) for edge in graph.edges if edge.edge_type == edge_type}

    def test_dependency_chain_follows_inference_premises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "fact-graph-chain")
            _seed_graph_problem(store)
            graph = build_fact_graph(store)
            self.assertEqual(graph.dependency_chain("claim:lemma-main"), ["claim:lemma-done", "claim:lemma-base"])
            self.assertEqual(graph.dependency_chain("lemma-main"), ["claim:lemma-done", "claim:lemma-base"])
            self.assertEqual(graph.dependency_chain("claim:lemma-base"), [])
            self.assertEqual(graph.dependency_chain("no-such-fact"), [])
            depends_on = self._edges(graph, "depends_on")
            self.assertIn(("claim:lemma-main", "claim:lemma-done"), depends_on)
            uses = self._edges(graph, "uses")
            self.assertIn(("inference:inf-main", "claim:lemma-done"), uses)
            self.assertIn(("inference:inf-base", "claim:lemma-base"), uses)

    def test_blocks_edges_come_from_active_debts_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "fact-graph-blocks")
            _seed_graph_problem(store)
            graph = build_fact_graph(store)
            blocks = self._edges(graph, "blocks")
            self.assertIn(("debt:debt-main", "branch:route-main"), blocks)
            self.assertIn(("debt:debt-claim", "claim:lemma-main"), blocks)
            blocking_sources = {source for source, _ in blocks}
            self.assertNotIn("debt:debt-fixed", blocking_sources)  # resolved debt never blocks
            for source in blocking_sources:
                node = graph.nodes[source]
                self.assertIsInstance(node, Obstruction)
                self.assertTrue(node.active)
                self.assertEqual(node.obstruction_kind, "active_debt")

    def test_repairs_same_as_and_supersedes_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "fact-graph-repairs")
            _seed_graph_problem(store)
            graph = build_fact_graph(store)
            # repairs: the fact whose proof artifact resolved the debt.
            self.assertIn(("claim:lemma-done", "debt:debt-fixed"), self._edges(graph, "repairs"))
            # same_as: fingerprint identity between materialized claims.
            same_as = self._edges(graph, "same_as")
            self.assertEqual(same_as, {("claim:lemma-done", "claim:lemma-twin")})
            # supersedes: canonical retrieval card over its duplicate.
            self.assertIn(("card:card-lit", "card:card-dup"), self._edges(graph, "supersedes"))

    def test_stubbed_edge_types_are_declared_but_never_derived(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "fact-graph-stubs")
            _seed_graph_problem(store)
            state = store.get_state()
            graph = build_fact_graph(store, state=state)
            self.assertEqual(STUB_EDGE_TYPES, {"generalizes", "specializes", "contradicts"})
            self.assertEqual(set(EDGE_TYPES), DERIVED_EDGE_TYPES | STUB_EDGE_TYPES)
            counts = graph.edge_counts_by_type()
            for edge_type in STUB_EDGE_TYPES:
                self.assertEqual(counts[edge_type], 0)
            for derive in (_derive_generalizes_edges, _derive_specializes_edges, _derive_contradicts_edges):
                self.assertEqual(derive(state), [])

    def test_stale_candidates_after_refutation_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "fact-graph-stale")
            _seed_graph_problem(store)
            revision_before = store.get_revision()
            graph = build_fact_graph(store)
            stale = graph.stale_candidates_after_refutation("claim:lemma-base")
            stale_ids = [fact.node_id for fact in stale]
            # Everything resting on lemma-base would need revisiting.
            self.assertIn("claim:lemma-done", stale_ids)
            self.assertIn("claim:lemma-main", stale_ids)
            self.assertIn("inference:inf-base", stale_ids)
            # Downstream-only facts are not dependents of themselves.
            self.assertNotIn("claim:lemma-base", stale_ids)
            # Read-only marking: nothing was written to the store.
            graph.branch_depth_report()
            graph.dependency_chain("lemma-main")
            self.assertEqual(store.get_revision(), revision_before)
            fresh = build_fact_graph(store)
            self.assertIsInstance(fresh.nodes["claim:lemma-done"], VerifiedFact)


class FactGraphFirstUseTests(unittest.TestCase):
    def test_branch_summary_parity_with_direct_queries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "fact-graph-parity")
            _seed_graph_problem(store)
            state = store.get_state()
            summary = build_branch_summary(store, "route-main", state=state)
            # The old direct queries, reproduced verbatim: classify the branch
            # cluster's claims through claim_memory_status in cluster order.
            claims_by_id = {row["claim_id"]: row for row in state["claims"]}
            expected_verified: list[str] = []
            expected_candidate: list[str] = []
            for claim_id in branch_cluster_claim_ids(state, "route-main"):
                claim = claims_by_id[claim_id]
                status = claim_memory_status(claim)
                line = f"{claim_id}: {_clip(claim.get('statement'))}"
                if status == "verified":
                    expected_verified.append(line)
                elif status == "candidate":
                    expected_candidate.append(line)
            self.assertEqual(summary["verified_facts"], expected_verified[:4])
            self.assertEqual(summary["candidate_facts"], expected_candidate[:4])

    def test_multi_branch_packet_carries_verified_fact_graph_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "fact-graph-packet")
            _seed_graph_problem(store)
            state = store.get_scheduler_state()
            packet = _branch_packet_card(state, "route-main", "lemma-main", "main_proof_spine")
            fact_view = packet["fact_graph"]
            self.assertEqual(fact_view["view"], "fact_graph.facts_for_branch(verified_only=True)")
            self.assertEqual(fact_view["verified_fact_count"], 1)
            rendered = " | ".join(fact_view["verified_facts"])
            self.assertIn("lemma-done", rendered)
            self.assertNotIn("lemma-main:", rendered)  # candidate facts never enter the settled list
            # Target-only packets (no anchor route) carry no fact-graph view.
            self.assertNotIn("fact_graph", _branch_packet_card(state, "", "lemma-main", "villain_toy_model"))

    def test_report_renders_fact_graph_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "fact-graph-report")
            _seed_graph_problem(store)
            report = build_markdown_report(store)
            self.assertIn("## Fact Graph", report)
            self.assertIn("verified_fact=", report)
            self.assertIn("depends_on=", report)
            self.assertIn("- Branch depth report:", report)
            self.assertIn("`route-main`", report)
            self.assertIn("contradicts", report)  # stubbed types are named, not counted

    def test_branch_depth_report_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "fact-graph-depth")
            _seed_graph_problem(store)
            graph = build_fact_graph(store)
            report = {row["branch_id"]: row for row in graph.branch_depth_report()}
            main = report["route-main"]
            self.assertEqual(main["classification"], "blocked")  # blocking debt wins
            self.assertTrue(main["blocked"])
            self.assertEqual(main["depth"], 1)  # lemma-main -> lemma-done inside the cluster
            self.assertEqual(main["verified_fact_count"], 1)
            # inf-base's auto route shares lemma-done with route-main: converging.
            auto = report["route-auto-lemma-done"]
            self.assertEqual(auto["classification"], "converging")
            self.assertTrue(auto["converging"])
            dead = report["route-dead"]
            self.assertEqual(dead["classification"], "shallow")
            self.assertFalse(dead["blocked"])


if __name__ == "__main__":
    unittest.main()

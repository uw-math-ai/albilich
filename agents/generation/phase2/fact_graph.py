from __future__ import annotations

"""Danus-style fact graph as a GENERATED, READ-ONLY view (2026-07-09 TODO 3).

This module never writes to the store. It materializes a graph view over the
existing SQLite proof state (claims, routes, inferences, debts, artifacts,
retrieval cards, theorem-library entries) so that parallel branch workers can
retrieve only the verified facts relevant to their branch and the advisor can
see which branches are deep, shallow, blocked, or converging. It is a lens,
not a second store: the SQLite proof state stays authoritative and every node
cites the row it was generated from.

Node vocabulary (update-advice TODO 3):

- ``VerifiedFact`` — a claim or inference accepted by a verifier
  (memory_status ``verified``), with its proof artifact ids and dependency
  list.
- ``CandidateFact`` — a useful but unverified claim/inference; NEVER usable
  as settled proof input.
- ``Obstruction`` — an active debt, failed route, or blocked/refuted claim
  (missing hypotheses and blockers live here); resolved debts stay as
  inactive obstructions so ``repairs`` edges have a target.
- ``SourceFact`` — a retrieval card or theorem-library entry with its checked
  metadata.
- ``BranchCluster`` — the route-anchored branch cluster (``branch_id`` IS the
  anchor ``route_id``, exactly the branch definition in branch_summary).

The verified/candidate boundary is exactly memory_policy's status classifier
(claim_memory_status / inference_memory_status): a row is a VerifiedFact iff
its memory_status is ``verified`` and a CandidateFact iff ``candidate``.
Superseded claims and refuted inferences leave the view entirely (edges are
only emitted between materialized nodes).

Edge vocabulary and derivation status:

- ``depends_on`` — conclusion claim -> premise/condition claim, from
  inference premises (derived).
- ``uses`` — inference -> its premise/condition claims; claim -> SourceFact
  named in the claim's source_ids (derived). Proof artifacts stay node
  attributes (``proof_artifact_ids``), not nodes.
- ``blocks`` — ACTIVE debt -> the claim/branch it is owned by (derived).
- ``repairs`` — fact -> resolved debt, from the debt's recorded resolution
  evidence (artifact ids matched against fact proof artifacts, or claim ids
  named directly) (derived).
- ``same_as`` — claims sharing a statement fingerprint (derived).
- ``supersedes`` — canonical debt/retrieval-card -> its canonicalized
  duplicates, from memory_policy's canonicalizers (derived).
- ``generalizes`` / ``specializes`` / ``contradicts`` — enum members with
  derivation stubs only: the proof state records no
  generalization/specialization/contradiction relation between statements
  today, so deriving them would be fabrication. See the ``_derive_*_edges``
  stubs for the data source each one is waiting on.

Pilot scope (doc steps 1-2 only): the graph feeds branch summaries, branch
packets for multi_branch_research context selection, and a report health
section. Doc steps 3-4 — fact promotion (CandidateFact -> VerifiedFact on
verifier approval) and revocation/staleness rules — are deliberately OUT OF
SCOPE until the dependency edges have proven reliable; until then
``stale_candidates_after_refutation`` only *returns* the dependents that
would need revisiting and never marks anything in the store.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple, Union

from .branch_summary import _active_branch_debts, branch_cluster_claim_ids
from .memory_policy import (
    canonicalize_debts,
    canonicalize_retrieval_cards,
    claim_memory_status,
    debt_memory_status,
    inference_memory_status,
    retrieval_card_memory_status,
    route_memory_status,
    theorem_library_memory_status,
)
from .models import json_loads
from .store import ProofStateStore

EDGE_TYPES = (
    "uses",
    "depends_on",
    "generalizes",
    "specializes",
    "blocks",
    "contradicts",
    "repairs",
    "same_as",
    "supersedes",
)
DERIVED_EDGE_TYPES = frozenset(
    {"uses", "depends_on", "blocks", "repairs", "same_as", "supersedes"}
)
# Enum members whose derivation is stubbed: no current proof-state column or
# artifact records these relations, so they are documented future work.
STUB_EDGE_TYPES = frozenset({"generalizes", "specializes", "contradicts"})

# Depth (longest depends_on chain) or verified-fact count at which a branch
# counts as "deep" in branch_depth_report.
DEEP_BRANCH_DEPTH = 2
DEEP_BRANCH_VERIFIED_COUNT = 3

_GOAL_CHARS = 260


@dataclass
class VerifiedFact:
    """A verifier-accepted claim or inference (memory_status ``verified``)."""

    node_id: str
    source_table: str  # "claims" | "inferences"
    source_id: str
    statement: str
    memory_status: str  # always "verified"
    proof_artifact_ids: List[str] = field(default_factory=list)
    dependency_ids: List[str] = field(default_factory=list)  # depends_on targets
    branch_ids: List[str] = field(default_factory=list)


@dataclass
class CandidateFact:
    """A useful but unverified claim/inference: NEVER settled proof input."""

    node_id: str
    source_table: str  # "claims" | "inferences"
    source_id: str
    statement: str
    memory_status: str  # always "candidate"
    proof_artifact_ids: List[str] = field(default_factory=list)
    dependency_ids: List[str] = field(default_factory=list)
    branch_ids: List[str] = field(default_factory=list)


@dataclass
class Obstruction:
    """An active debt, failed route, or blocked/refuted claim.

    Resolved debts stay in the view as inactive obstructions (``active`` is
    False) so ``repairs`` edges have a target; only ACTIVE debts emit
    ``blocks`` edges.
    """

    node_id: str
    source_table: str  # "debts" | "routes" | "claims"
    source_id: str
    description: str
    obstruction_kind: str  # active_debt | resolved_debt | failed_route | blocked_claim | refuted_claim
    severity: str
    owner_id: str
    active: bool
    memory_status: str
    branch_ids: List[str] = field(default_factory=list)


@dataclass
class SourceFact:
    """A retrieval card or theorem-library entry with its checked metadata."""

    node_id: str
    source_table: str  # "retrieval_cards" | "theorem_library_entries"
    source_id: str
    statement: str
    memory_status: str  # candidate | background | verified (memory_policy)
    checked_metadata: Dict[str, Any] = field(default_factory=dict)
    branch_ids: List[str] = field(default_factory=list)


@dataclass
class BranchCluster:
    """The route-anchored branch cluster: branch_id == anchor route_id."""

    node_id: str
    branch_id: str
    goal: str
    fact_ids: List[str] = field(default_factory=list)  # claim facts in cluster order, then route inferences
    obstruction_ids: List[str] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)


FactNode = Union[VerifiedFact, CandidateFact, Obstruction, SourceFact, BranchCluster]
Fact = Union[VerifiedFact, CandidateFact]

NODE_TYPE_LABELS = (
    (VerifiedFact, "verified_fact"),
    (CandidateFact, "candidate_fact"),
    (Obstruction, "obstruction"),
    (SourceFact, "source_fact"),
    (BranchCluster, "branch_cluster"),
)


@dataclass
class FactEdge:
    edge_type: str
    source_id: str
    target_id: str
    via: str = ""  # derivation witness (inference id, debt id, fingerprint, ...)


@dataclass
class FactGraph:
    """Read-only fact-graph view. Query helpers never touch the store."""

    nodes: Dict[str, FactNode] = field(default_factory=dict)
    edges: List[FactEdge] = field(default_factory=list)

    # -- shape ---------------------------------------------------------------

    def node_counts_by_type(self) -> Dict[str, int]:
        counts = {label: 0 for _, label in NODE_TYPE_LABELS}
        for node in self.nodes.values():
            for node_type, label in NODE_TYPE_LABELS:
                if isinstance(node, node_type):
                    counts[label] += 1
                    break
        return counts

    def edge_counts_by_type(self) -> Dict[str, int]:
        counts = {edge_type: 0 for edge_type in EDGE_TYPES}
        for edge in self.edges:
            counts[edge.edge_type] = counts.get(edge.edge_type, 0) + 1
        return counts

    def branch_clusters(self) -> List[BranchCluster]:
        return [node for node in self.nodes.values() if isinstance(node, BranchCluster)]

    # -- queries the doc motivates -------------------------------------------

    def facts_for_branch(
        self,
        branch_id: str,
        verified_only: bool = True,
        *,
        include_inferences: bool = False,
    ) -> List[Fact]:
        """Facts in one branch cluster, in cluster (branch_summary) order.

        ``verified_only=True`` (the default, and the only setting workers may
        treat as settled proof input) returns VerifiedFact nodes only;
        ``verified_only=False`` adds the CandidateFact nodes.
        """
        cluster = self.nodes.get(f"branch:{branch_id}")
        if not isinstance(cluster, BranchCluster):
            return []
        facts: List[Fact] = []
        for node_id in cluster.fact_ids:
            node = self.nodes.get(node_id)
            if not isinstance(node, (VerifiedFact, CandidateFact)):
                continue
            if not include_inferences and node.source_table == "inferences":
                continue
            if verified_only and not isinstance(node, VerifiedFact):
                continue
            facts.append(node)
        return facts

    def dependency_chain(self, fact_id: str) -> List[str]:
        """Transitive ``depends_on`` closure of one fact, in BFS order.

        Accepts a node id (``claim:L1``) or a bare claim/inference id. The
        starting node is not included.
        """
        start = self._resolve_node_id(fact_id)
        if start is None:
            return []
        forward = self._adjacency("depends_on")
        chain: List[str] = []
        seen: Set[str] = {start}
        frontier = [start]
        while frontier:
            next_frontier: List[str] = []
            for node_id in frontier:
                for dep_id in forward.get(node_id, []):
                    if dep_id in seen:
                        continue
                    seen.add(dep_id)
                    chain.append(dep_id)
                    next_frontier.append(dep_id)
            frontier = next_frontier
        return chain

    def stale_candidates_after_refutation(self, fact_id: str) -> List[Fact]:
        """Facts that transitively depend on ``fact_id``: the read-only
        would-need-revisiting set if that fact were refuted.

        Walks ``depends_on`` and ``uses`` edges in reverse and returns the
        VerifiedFact/CandidateFact dependents in BFS order. This MARKS nothing
        and writes nothing — revocation/staleness rules are doc step 4,
        deliberately out of scope until dependency edges are reliable.
        """
        start = self._resolve_node_id(fact_id)
        if start is None:
            return []
        reverse: Dict[str, List[str]] = {}
        for edge in self.edges:
            if edge.edge_type in {"depends_on", "uses"}:
                reverse.setdefault(edge.target_id, []).append(edge.source_id)
        stale: List[Fact] = []
        seen: Set[str] = {start}
        frontier = [start]
        while frontier:
            next_frontier: List[str] = []
            for node_id in frontier:
                for dependent_id in reverse.get(node_id, []):
                    if dependent_id in seen:
                        continue
                    seen.add(dependent_id)
                    next_frontier.append(dependent_id)
                    node = self.nodes.get(dependent_id)
                    if isinstance(node, (VerifiedFact, CandidateFact)):
                        stale.append(node)
            frontier = next_frontier
        return stale

    def branch_depth_report(self) -> List[Dict[str, Any]]:
        """Per-branch health for the advisor: deep / shallow / blocked /
        converging, with the numbers behind the label."""
        clusters = self.branch_clusters()
        fact_owners: Dict[str, int] = {}
        for cluster in clusters:
            for node_id in cluster.fact_ids:
                fact_owners[node_id] = fact_owners.get(node_id, 0) + 1
        forward = self._adjacency("depends_on")
        report: List[Dict[str, Any]] = []
        for cluster in clusters:
            facts = [
                node
                for node in (self.nodes.get(node_id) for node_id in cluster.fact_ids)
                if isinstance(node, (VerifiedFact, CandidateFact))
            ]
            verified_count = sum(1 for node in facts if isinstance(node, VerifiedFact))
            candidate_count = len(facts) - verified_count
            member_ids = {node.node_id for node in facts}
            depth = 0
            memo: Dict[str, int] = {}
            for node in facts:
                depth = max(depth, _longest_chain(node.node_id, forward, member_ids, memo, set()))
            obstructions = [
                node
                for node in (self.nodes.get(node_id) for node_id in cluster.obstruction_ids)
                if isinstance(node, Obstruction) and node.active
            ]
            blocked = any(node.severity == "blocking" for node in obstructions)
            converging = any(fact_owners.get(node_id, 0) > 1 for node_id in cluster.fact_ids)
            if blocked:
                classification = "blocked"
            elif converging:
                classification = "converging"
            elif depth >= DEEP_BRANCH_DEPTH or verified_count >= DEEP_BRANCH_VERIFIED_COUNT:
                classification = "deep"
            else:
                classification = "shallow"
            report.append(
                {
                    "branch_id": cluster.branch_id,
                    "classification": classification,
                    "depth": depth,
                    "verified_fact_count": verified_count,
                    "candidate_fact_count": candidate_count,
                    "active_obstruction_count": len(obstructions),
                    "blocked": blocked,
                    "converging": converging,
                }
            )
        return report

    # -- internals -------------------------------------------------------------

    def _resolve_node_id(self, fact_id: str) -> Optional[str]:
        text = str(fact_id or "")
        if text in self.nodes:
            return text
        for prefix in ("claim", "inference", "debt", "route", "card", "library", "branch"):
            candidate = f"{prefix}:{text}"
            if candidate in self.nodes:
                return candidate
        return None

    def _adjacency(self, edge_type: str) -> Dict[str, List[str]]:
        forward: Dict[str, List[str]] = {}
        for edge in self.edges:
            if edge.edge_type == edge_type:
                forward.setdefault(edge.source_id, []).append(edge.target_id)
        return forward


def _longest_chain(
    node_id: str,
    forward: Mapping[str, List[str]],
    member_ids: Set[str],
    memo: Dict[str, int],
    on_stack: Set[str],
) -> int:
    if node_id in memo:
        return memo[node_id]
    if node_id in on_stack:
        return 0  # defensive: dependency data should be acyclic
    on_stack.add(node_id)
    best = 0
    for dep_id in forward.get(node_id, []):
        if dep_id in member_ids:
            best = max(best, 1 + _longest_chain(dep_id, forward, member_ids, memo, on_stack))
    on_stack.discard(node_id)
    memo[node_id] = best
    return best


# ---------------------------------------------------------------------------
# Graph generation
# ---------------------------------------------------------------------------


def build_fact_graph(
    store: Optional[ProofStateStore],
    *,
    state: Optional[Mapping[str, Any]] = None,
) -> FactGraph:
    """Generate the read-only fact-graph view from the current proof state.

    ``state`` may be a full ``store.get_state()`` snapshot or the scheduler
    state; when omitted it is read (read-only) from ``store``.
    """
    if state is None:
        if store is None:
            raise ValueError("build_fact_graph needs a store or a state snapshot")
        state = store.get_state()

    graph = FactGraph()
    claims = [row for row in state.get("claims", []) if isinstance(row, Mapping)]
    inferences = [row for row in state.get("inferences", []) if isinstance(row, Mapping)]
    debts = [row for row in state.get("debts", []) if isinstance(row, Mapping)]
    routes = [row for row in state.get("routes", []) if isinstance(row, Mapping)]
    cards = [row for row in state.get("retrieval_cards", []) if isinstance(row, Mapping)]
    library = [row for row in state.get("theorem_library_entries", []) if isinstance(row, Mapping)]

    # Claim-level dependency map from inference premises/conditions. Refuted
    # inferences contribute neither nodes nor dependency edges: a refuted link
    # is not a dependency.
    live_inferences = [row for row in inferences if inference_memory_status(row) != "failed"]
    claim_dependencies: Dict[str, List[str]] = {}
    for row in live_inferences:
        conclusion_id = str(row.get("conclusion_claim_id") or "")
        deps = claim_dependencies.setdefault(conclusion_id, [])
        for claim_id in _inference_input_claim_ids(row):
            if claim_id and claim_id not in deps:
                deps.append(claim_id)

    # --- nodes: claims -----------------------------------------------------
    for row in claims:
        claim_id = str(row.get("claim_id") or "")
        status = claim_memory_status(row)
        node_id = f"claim:{claim_id}"
        statement = str(row.get("statement") or "")
        if status in {"verified", "candidate"}:
            fact_type = VerifiedFact if status == "verified" else CandidateFact
            graph.nodes[node_id] = fact_type(
                node_id=node_id,
                source_table="claims",
                source_id=claim_id,
                statement=statement,
                memory_status=status,
                proof_artifact_ids=_id_list(row, "evidence_artifact_ids"),
                dependency_ids=[f"claim:{dep}" for dep in claim_dependencies.get(claim_id, [])],
            )
        elif status in {"blocked", "failed"}:
            graph.nodes[node_id] = Obstruction(
                node_id=node_id,
                source_table="claims",
                source_id=claim_id,
                description=statement,
                obstruction_kind="refuted_claim" if status == "failed" else "blocked_claim",
                severity="",
                owner_id="",
                active=True,
                memory_status=status,
            )
        # superseded claims leave the view entirely.

    # --- nodes: inferences ---------------------------------------------------
    for row in inferences:
        status = inference_memory_status(row)
        if status not in {"verified", "candidate"}:
            continue  # refuted links vanish; challenged links surface as blocked claims/debts
        inference_id = str(row.get("inference_id") or "")
        node_id = f"inference:{inference_id}"
        fact_type = VerifiedFact if status == "verified" else CandidateFact
        graph.nodes[node_id] = fact_type(
            node_id=node_id,
            source_table="inferences",
            source_id=inference_id,
            statement=str(row.get("explanation") or ""),
            memory_status=status,
            proof_artifact_ids=_id_list(row, "evidence_artifact_ids"),
            dependency_ids=[f"claim:{dep}" for dep in _inference_input_claim_ids(row)],
        )

    # --- nodes: debts ---------------------------------------------------------
    for row in debts:
        debt_id = str(row.get("debt_id") or "")
        status = str(row.get("status") or "")
        if status == "active":
            kind, active = "active_debt", True
        elif status == "resolved":
            kind, active = "resolved_debt", False
        else:
            continue  # discarded debts leave the view
        graph.nodes[f"debt:{debt_id}"] = Obstruction(
            node_id=f"debt:{debt_id}",
            source_table="debts",
            source_id=debt_id,
            description=str(row.get("obligation") or ""),
            obstruction_kind=kind,
            severity=str(row.get("severity") or ""),
            owner_id=str(row.get("owner_id") or ""),
            active=active,
            memory_status=debt_memory_status(row),
        )

    # --- nodes: failed routes ---------------------------------------------------
    for row in routes:
        if route_memory_status(row) != "failed":
            continue
        route_id = str(row.get("route_id") or "")
        description = str(row.get("strategy") or row.get("label") or "")
        fingerprint = str(row.get("failure_fingerprint") or "")
        if fingerprint:
            description = f"{description} [failure fingerprint {fingerprint}]".strip()
        graph.nodes[f"route:{route_id}"] = Obstruction(
            node_id=f"route:{route_id}",
            source_table="routes",
            source_id=route_id,
            description=description,
            obstruction_kind="failed_route",
            severity="",
            owner_id=str(row.get("conclusion_claim_id") or ""),
            active=True,
            memory_status=route_memory_status(row),
        )

    # --- nodes: sources -----------------------------------------------------------
    for row in cards:
        card_id = str(row.get("card_id") or "")
        applicability = json_loads(row.get("applicability_json"), {})
        if not isinstance(applicability, Mapping):
            applicability = {}
        graph.nodes[f"card:{card_id}"] = SourceFact(
            node_id=f"card:{card_id}",
            source_table="retrieval_cards",
            source_id=card_id,
            statement=str(row.get("exact_statement") or ""),
            memory_status=retrieval_card_memory_status(row),
            checked_metadata={
                "classification": str(
                    applicability.get("classification") or applicability.get("relation") or ""
                ),
                "source_identifiers": json_loads(row.get("source_identifiers_json"), {}),
                "source_location": str(row.get("source_location") or ""),
                "missing_hypotheses": json_loads(row.get("missing_hypotheses_json"), []),
            },
        )
    for row in library:
        entry_id = str(row.get("entry_id") or "")
        graph.nodes[f"library:{entry_id}"] = SourceFact(
            node_id=f"library:{entry_id}",
            source_table="theorem_library_entries",
            source_id=entry_id,
            statement=str(row.get("statement") or ""),
            memory_status=theorem_library_memory_status(row),
            checked_metadata={
                "certification_type": str(row.get("certification_type") or ""),
                "relation_to_target": str(row.get("relation_to_target") or ""),
                "source_identifiers": json_loads(row.get("source_identifiers_json"), {}),
                "source_location": str(row.get("source_location") or ""),
            },
        )

    # --- nodes: branch clusters (one per route; branch_id == route_id) --------
    claims_by_id = {str(row.get("claim_id") or ""): row for row in claims}
    for row in routes:
        route_id = str(row.get("route_id") or "")
        if not route_id:
            continue
        cluster_claim_ids = branch_cluster_claim_ids(state, route_id)
        fact_ids = [
            f"claim:{claim_id}"
            for claim_id in cluster_claim_ids
            if isinstance(graph.nodes.get(f"claim:{claim_id}"), (VerifiedFact, CandidateFact))
        ]
        fact_ids.extend(
            f"inference:{inf.get('inference_id')}"
            for inf in live_inferences
            if str(inf.get("route_id") or "") == route_id
            and f"inference:{inf.get('inference_id')}" in graph.nodes
        )
        obstruction_ids = [
            f"claim:{claim_id}"
            for claim_id in cluster_claim_ids
            if isinstance(graph.nodes.get(f"claim:{claim_id}"), Obstruction)
        ]
        obstruction_ids.extend(
            f"debt:{debt.get('debt_id')}"
            for debt in _active_branch_debts(state, route_id, cluster_claim_ids)
            if f"debt:{debt.get('debt_id')}" in graph.nodes
        )
        if f"route:{route_id}" in graph.nodes:
            obstruction_ids.append(f"route:{route_id}")
        source_ids: List[str] = []
        for claim_id in cluster_claim_ids:
            for source_id in _id_list(claims_by_id.get(claim_id, {}), "source_ids"):
                node_id = _source_node_id(graph, source_id)
                if node_id and node_id not in source_ids:
                    source_ids.append(node_id)
        conclusion = claims_by_id.get(str(row.get("conclusion_claim_id") or ""), {})
        goal = " ".join(
            str(conclusion.get("statement") or row.get("strategy") or row.get("label") or "").split()
        )[:_GOAL_CHARS]
        graph.nodes[f"branch:{route_id}"] = BranchCluster(
            node_id=f"branch:{route_id}",
            branch_id=route_id,
            goal=goal,
            fact_ids=fact_ids,
            obstruction_ids=obstruction_ids,
            source_ids=source_ids,
        )
        for node_id in (*fact_ids, *obstruction_ids, *source_ids):
            node = graph.nodes.get(node_id)
            if node is not None and route_id not in node.branch_ids:
                node.branch_ids.append(route_id)

    # --- edges ------------------------------------------------------------------
    seen_edges: Set[Tuple[str, str, str]] = set()

    def add_edge(edge_type: str, source_id: str, target_id: str, via: str = "") -> None:
        if source_id not in graph.nodes or target_id not in graph.nodes or source_id == target_id:
            return
        key = (edge_type, source_id, target_id)
        if key in seen_edges:
            return
        seen_edges.add(key)
        graph.edges.append(FactEdge(edge_type, source_id, target_id, via))

    # uses / depends_on from inference premises.
    for row in live_inferences:
        inference_id = str(row.get("inference_id") or "")
        inference_node = f"inference:{inference_id}"
        conclusion_node = f"claim:{row.get('conclusion_claim_id')}"
        for claim_id in _inference_input_claim_ids(row):
            add_edge("uses", inference_node, f"claim:{claim_id}", via=inference_id)
            add_edge("depends_on", conclusion_node, f"claim:{claim_id}", via=inference_id)

    # uses from claim source links (retrieval cards / theorem-library entries).
    for row in claims:
        claim_node = f"claim:{row.get('claim_id')}"
        for source_id in _id_list(row, "source_ids"):
            node_id = _source_node_id(graph, source_id)
            if node_id:
                add_edge("uses", claim_node, node_id, via=str(row.get("claim_id") or ""))

    # blocks from ACTIVE debt ownership only.
    for row in debts:
        if str(row.get("status") or "") != "active":
            continue
        debt_node = f"debt:{row.get('debt_id')}"
        owner_id = str(row.get("owner_id") or "")
        for target in (f"claim:{owner_id}", f"branch:{owner_id}"):
            add_edge("blocks", debt_node, target, via=str(row.get("debt_id") or ""))

    # repairs from debt resolution evidence.
    facts_by_artifact: Dict[str, List[str]] = {}
    for node in graph.nodes.values():
        if isinstance(node, (VerifiedFact, CandidateFact)):
            for artifact_id in node.proof_artifact_ids:
                facts_by_artifact.setdefault(artifact_id, []).append(node.node_id)
    for row in debts:
        if str(row.get("status") or "") != "resolved":
            continue
        debt_node = f"debt:{row.get('debt_id')}"
        artifact_ids, claim_ids = _resolution_evidence_ids(row)
        for claim_id in claim_ids:
            add_edge("repairs", f"claim:{claim_id}", debt_node, via="resolution_evidence")
        for artifact_id in artifact_ids:
            for fact_node in facts_by_artifact.get(artifact_id, []):
                add_edge("repairs", fact_node, debt_node, via=f"artifact:{artifact_id}")

    # same_as from statement-fingerprint identity between materialized claims.
    fingerprint_groups: Dict[str, List[str]] = {}
    for row in claims:
        fingerprint = str(row.get("fingerprint") or "")
        node_id = f"claim:{row.get('claim_id')}"
        if fingerprint and node_id in graph.nodes:
            fingerprint_groups.setdefault(fingerprint, []).append(node_id)
    for fingerprint, node_ids in fingerprint_groups.items():
        if len(node_ids) < 2:
            continue
        canonical, *rest = sorted(node_ids)
        for node_id in rest:
            add_edge("same_as", canonical, node_id, via=f"fingerprint:{fingerprint}")

    # supersedes from the memory-policy canonicalizers (duplicate debts/cards).
    _, duplicate_debts = canonicalize_debts(debts)
    for report in duplicate_debts:
        canonical = f"debt:{report.get('canonical_debt_id')}"
        for debt_id in report.get("duplicate_debt_ids", []):
            add_edge("supersedes", canonical, f"debt:{debt_id}", via="canonicalize_debts")
    _, duplicate_cards = canonicalize_retrieval_cards(cards)
    for report in duplicate_cards:
        canonical = f"card:{report.get('canonical_card_id')}"
        for card_id in report.get("duplicate_card_ids", []):
            add_edge("supersedes", canonical, f"card:{card_id}", via="canonicalize_retrieval_cards")

    # Stubbed edge types: derivations return [] until a data source exists.
    for derive in (_derive_generalizes_edges, _derive_specializes_edges, _derive_contradicts_edges):
        for edge in derive(state):
            add_edge(edge.edge_type, edge.source_id, edge.target_id, edge.via)

    return graph


# ---------------------------------------------------------------------------
# Stubbed derivations (future work — do NOT fake these)
# ---------------------------------------------------------------------------


def _derive_generalizes_edges(state: Mapping[str, Any]) -> List[FactEdge]:
    """Future work: needs an explicit statement-relation record (e.g. a
    researcher/advisor patch op or claim tag naming the generalized claim).
    No current column encodes "A generalizes B", so nothing is derived."""
    return []


def _derive_specializes_edges(state: Mapping[str, Any]) -> List[FactEdge]:
    """Future work: inverse of ``generalizes``; same missing data source
    (nearby-lemma passes record special cases as free text today)."""
    return []


def _derive_contradicts_edges(state: Mapping[str, Any]) -> List[FactEdge]:
    """Future work: needs counterexample/refutation artifacts to name BOTH
    statements they separate (today a refutation only marks its own target
    claim refuted). Nothing is derived until that link is recorded."""
    return []


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------


def _id_list(row: Mapping[str, Any], key: str) -> List[str]:
    """String ids from ``row[key]`` (list) or ``row[key + '_json']``."""
    values = row.get(key)
    if not isinstance(values, list):
        values = json_loads(row.get(f"{key}_json"), [])
    if not isinstance(values, list):
        return []
    return [str(item) for item in values if str(item or "")]


def _inference_input_claim_ids(row: Mapping[str, Any]) -> List[str]:
    """Premise then condition claim ids of one inference row, deduplicated."""
    ids: List[str] = []
    for claim_id in (*_id_list(row, "premise_claim_ids"), *_id_list(row, "condition_claim_ids")):
        if claim_id not in ids:
            ids.append(claim_id)
    return ids


def _resolution_evidence_ids(row: Mapping[str, Any]) -> Tuple[List[str], List[str]]:
    """(artifact ids, claim ids) named by a debt's resolution evidence."""
    evidence = row.get("resolution_evidence")
    if not isinstance(evidence, Mapping):
        evidence = json_loads(row.get("resolution_evidence_json"), {})
        if not isinstance(evidence, Mapping):
            evidence = {}
    artifact_ids = _evidence_values(
        evidence, ("resolution_evidence_artifact_ids", "artifact_ids", "evidence_artifact_ids", "artifact_id")
    )
    claim_ids = _evidence_values(evidence, ("claim_ids", "claim_id"))
    return artifact_ids, claim_ids


def _evidence_values(evidence: Mapping[str, Any], keys: Iterable[str]) -> List[str]:
    values: List[str] = []
    for key in keys:
        raw = evidence.get(key)
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            text = str(item or "")
            if text and text not in values:
                values.append(text)
    return values


def _source_node_id(graph: FactGraph, source_id: str) -> str:
    for prefix in ("card", "library"):
        node_id = f"{prefix}:{source_id}"
        if node_id in graph.nodes:
            return node_id
    return ""

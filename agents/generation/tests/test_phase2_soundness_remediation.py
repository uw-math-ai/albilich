from __future__ import annotations

import ast
import base64
import copy
import hashlib
import inspect
import itertools
import json
import os
import random
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from agents.generation.phase2.authority import (
    PatchAuthority,
    reviewer_independence_class,
)
from agents.generation.phase2.assurance import claim_assurance_summary
from agents.generation.phase2.artifacts import artifact_hash
from agents.generation.phase2.audit import ingest_paper_audit
from agents.generation.phase2.audit_chain import backfill_event_chain, event_entry_hash
from agents.generation.phase2.audit_checkpoint import (
    canonical_signature_payload,
    create_signed_audit_checkpoint,
    public_key_der,
    sign_ed25519,
    verify_signed_audit_checkpoint,
)
from agents.generation.phase2.branch_summary import sync_branch_workbenches
from agents.generation.phase2.cas_reproduction import reproduce_computation
from agents.generation.phase2.codex_runner import (
    _codex_permission_profile_args,
    _materialize_evidence_capsule,
    _standardize_prompt_terminology,
    execute_session,
    run_metrics_operation,
)
from agents.generation.phase2.context_builder import (
    ContextTooLargeError,
    _context_entity_catalog,
    _public_context_vocabulary,
    build_context_manifest,
)
from agents.generation.phase2.decision_policy import (
    ActionCandidate,
    action_sha256,
    bind_dispatched_action,
    candidate_rows_sha256,
    candidate_set_sha256,
    decision_trace_errors,
    policy_trace_sha256,
    select_action_candidate,
)
from agents.generation.phase2.experiment_audit import (
    audit_experiment_archives,
    paired_problem_power_required_count,
    randomized_condition_order,
)
from agents.generation.phase2.executable_attestation import attest_executable
from agents.generation.phase2.formal_reproduction import (
    _agda_declares_target,
    _audit_assumptions,
    check_formal_artifact,
)
from agents.generation.phase2.invariants import validate_conn
from agents.generation.phase2.models import PatchOutcome, SCHEMA_VERSION, fingerprint_text
from agents.generation.phase2.randomized_assignment import (
    BLOCK_RANDOMIZED_SEED_DERIVATION_ALGORITHM,
    bind_randomized_assignment,
    randomized_arm_assignment,
    randomized_block_workflow_assignments,
    randomized_assignment_cohort_errors,
    randomized_assignment_errors,
    randomized_block_assignment_cohort_errors,
    randomized_block_seed,
    randomized_policy_arm,
)
from agents.generation.phase2.patches import (
    _legacy_v10_run_provenance_hash,
    _legacy_v11_run_provenance_hash,
    _legacy_v12_run_provenance_hash,
    _legacy_v13_run_provenance_hash,
    _legacy_v14_run_provenance_hash,
    _legacy_v14_state_journal_projection,
    _legacy_v9_run_provenance_hash,
    _state_projection_hash,
    apply_operator_patch,
    apply_patch,
    apply_system_patch,
)
from agents.generation.phase2.reference_solution import ingest_reference_solution
from agents.generation.phase2.research_intelligence import strategy_family
from agents.generation.phase2.research_strategy import strategy_operation_candidates
from agents.generation.phase2.replay import verify_patch_journal
from agents.generation.phase2.replay import verify_event_journal
from agents.generation.phase2 import graph_policy as graph_policy_module
from agents.generation.phase2 import action_contract as action_contract_module
from agents.generation.phase2 import budget as budget_module
from agents.generation.phase2 import decision_policy as decision_policy_module
from agents.generation.phase2 import parallel_admission as parallel_admission_module
from agents.generation.phase2 import parallel_relaxation as parallel_relaxation_module
from agents.generation.phase2 import policy_epoch_guard as policy_epoch_guard_module
from agents.generation.phase2 import research_policy as research_policy_module
from agents.generation.phase2 import research_strategy as research_strategy_module
from agents.generation.phase2 import retrieval as retrieval_module
from agents.generation.phase2 import scheduler as scheduler_module
from agents.generation.phase2 import store as store_module
from agents.generation.phase2 import workflow as workflow_module
from agents.generation.benchmarks import benchmark_scheduler as scheduler_benchmark_module
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.store import SCHEDULER_RECENT_RUN_LIMIT
from agents.generation.phase2.scheduler_provenance import (
    ONLINE_RETRIEVAL_COUNT_INTENTS,
    SCHEDULER_HISTORY_GUARD_NAMES,
    scheduler_provenance_errors,
    scheduler_provenance_summary,
)
from agents.generation.phase2.scheduler_registry import (
    CANDIDATE_GENERATOR_BOUND_DECISION_POLICY_VERSION,
    CANDIDATE_GENERATOR_GRAPH,
    CANDIDATE_GENERATOR_GRAPHS,
    CANDIDATE_GENERATOR_GRAPH_SHA256,
    CANDIDATE_GENERATOR_GRAPH_VERSION,
    CANDIDATE_GENERATOR_MANIFEST_VERSION,
    SUPPORTED_CANDIDATE_GENERATOR_GRAPH_VERSIONS,
    candidate_generator_graph_errors,
    candidate_generator_graph_sha256,
    candidate_generator_trace_errors,
    generator_producers_by_scope,
)
from agents.generation.phase2.scheduler import next_action
from agents.generation.phase2.writing.revision import ingest_writing_revision
from agents.generation.phase2.workflow import (
    _record_scheduler_dispatches,
    _session_contract_errors,
    run_workflow,
)
from agents.generation.tests._phase2_test_support import certify_and_integrate_claim


def _rebind_parallel_wave_snapshot(
    wave: dict[str, object],
    *,
    state_revision: int,
) -> None:
    """Recompute commitments after a synthetic wave advances its snapshot."""

    wave["state_revision"] = state_revision
    wave["proof_state_hash"] = hashlib.sha256(
        f"parallel-wave-state-{state_revision}".encode("utf-8")
    ).hexdigest()
    wave["candidate_set_sha256"] = (
        parallel_admission_module.parallel_candidate_set_sha256(
            wave["candidates"],
            policy_version=wave["policy_version"],
        )
    )
    wave["wave_id"] = parallel_admission_module.parallel_wave_id(
        candidate_set_sha256=wave["candidate_set_sha256"],
        candidate_set_scope=wave["candidate_set_scope"],
        state_revision=wave["state_revision"],
        proof_state_hash=wave["proof_state_hash"],
        run_provenance_hash=wave["run_provenance_hash"],
        configured_proof_search_workers=wave[
            "configured_proof_search_workers"
        ],
        total_wave_capacity=wave["total_wave_capacity"],
        class_capacities=wave["class_capacities"],
        aggregate_budget_enforced=wave["aggregate_budget_enforced"],
        initial_remaining_token_budget=wave[
            "initial_remaining_token_budget"
        ],
        initial_reserved_verification_budget=wave[
            "initial_reserved_verification_budget"
        ],
        candidate_generator_manifest_sha256=wave[
            "candidate_generator_manifest_sha256"
        ],
        admission_search=wave.get("admission_search"),
        policy_version=wave["policy_version"],
    )


def _restore_v14_proof_projection_seal(
    store: ProofStateStore,
    conn: sqlite3.Connection,
) -> None:
    """Make a current fixture carry the proof seal an actual v14 store had."""

    conn.execute(
        "UPDATE problem_state SET proof_state_hash = ?, run_provenance_hash = ? "
        "WHERE problem_id = ?",
        (
            _state_projection_hash(_legacy_v14_state_journal_projection(conn)),
            _legacy_v14_run_provenance_hash(conn),
            store.problem_id,
        ),
    )


def _strip_post_v9_scheduler_execution_fixture(
    store: ProofStateStore,
    conn: sqlite3.Connection,
) -> None:
    """Remove lifecycle rows that could not exist in a genuine v9 store."""

    store._drop_scheduler_history_guards(conn)
    conn.execute(
        "DELETE FROM scheduler_provenance_entries "
        "WHERE record_kind IN ('attempt', 'result')"
    )
    conn.execute(
        "DELETE FROM scheduler_source_entries "
        "WHERE record_kind IN ('attempt', 'result')"
    )
    conn.execute("DELETE FROM scheduler_dispatch_results")
    conn.execute("DELETE FROM scheduler_dispatch_attempts")
    execution_event_ids = [
        int(row["event_id"])
        for row in conn.execute(
            "SELECT event_id FROM events WHERE event_type IN "
            "('scheduler_dispatch_attempt_claimed', "
            "'scheduler_dispatch_result_recorded')"
        ).fetchall()
    ]
    if execution_event_ids:
        store._drop_event_history_guards(conn)
        placeholders = ", ".join("?" for _ in execution_event_ids)
        conn.execute(
            f"DELETE FROM event_source_entries WHERE event_id IN ({placeholders})",
            execution_event_ids,
        )
        conn.execute(
            f"DELETE FROM events WHERE event_id IN ({placeholders})",
            execution_event_ids,
        )
        backfill_event_chain(conn, problem_id=store.problem_id)


def _record_dispatched_test_wave(
    store: ProofStateStore,
    actions: Sequence[Mapping[str, object]],
    run_ids: Sequence[str],
    *,
    created_at: str = "",
    planning_audit_heads: Mapping[str, object] | None = None,
) -> PatchOutcome:
    """Exercise the production dispatch-before-execution telemetry path."""

    if not actions or len(actions) != len(run_ids):
        raise ValueError("test dispatch wave actions and run identifiers must align")
    try:
        dispatches, committed_heads = _record_scheduler_dispatches(
            store,
            actions,
            planning_audit_heads or store.audit_chain_heads(),
            execution_contract={
                "version": 1,
                "driver": "custom",
                "identity": "test:deterministic-dispatch",
                "recovery_capability": "none",
            },
        )
    except RuntimeError as exc:
        return PatchOutcome(False, store.get_revision(), "", [str(exc)])
    scheduled: list[dict[str, object]] = []
    for action, dispatch, run_id in zip(actions, dispatches, run_ids):
        plan = {
            "actor_role": dispatch["actor_role"],
            "mode": action.get("mode", ""),
            "target_id": action.get("target_id", ""),
            "route_id": action.get("route_id", ""),
            "state_revision": int(committed_heads["proof_revision"]),
            "scheduler_decision_state_revision": dispatch[
                "decision_state_revision"
            ],
            "scheduler_dispatch_id": dispatch["dispatch_id"],
            "dispatched_action_hash": dispatch["dispatched_action_hash"],
            "context_hash": f"context-{run_id}",
            "search_intent": action.get("search_intent", ""),
            "strategy_family": strategy_family(action),
            "model_profile": "default",
            "web_search": "disabled",
        }
        execution = {
            "run_id": run_id,
            "actor_role": dispatch["actor_role"],
            "status": "failed",
            "returncode": 1,
            "wall_time_seconds": 0.0,
            "peak_memory_mb": 0.0,
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "session_id": "",
            "patch": None,
            "patch_error": "",
            "output_artifact_ids": [],
            "model": "",
            "reasoning_effort": "",
            "sandbox": "",
            "web_search": "disabled",
            "failure_kind": "",
        }
        scheduled.append(
            {
                "action": dict(action),
                "session_plan": plan,
                "session_web_search": "disabled",
                "execution": execution,
                "is_companion": bool(dispatch["is_companion"]),
            }
        )
    workflow_module._record_scheduler_attempts(store, scheduled)
    for item in scheduled:
        workflow_module._record_scheduler_result(
            store,
            item,
            validation_errors=[],
        )
    outcome: PatchOutcome | None = None
    for action, dispatch, run_id, item in zip(
        actions, dispatches, run_ids, scheduled
    ):
        operation = run_metrics_operation(
            run_id=run_id,
            action=action,
            session_plan=item["session_plan"],
            usage_payload={"input_tokens": 0, "output_tokens": 0},
            status="failed",
        )
        operation["search_setting"] = "disabled"
        if created_at:
            operation["created_at"] = created_at
        outcome = apply_system_patch(
            store,
            {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": store.get_revision(),
                "actor_role": "scheduler",
                "target_id": str(action.get("target_id") or "root"),
                "operations": [operation],
                "rationale": "record completion of a durable test dispatch",
            },
            mode=str(action.get("mode") or ""),
            route_id=str(action.get("route_id") or ""),
        )
        if not outcome.accepted:
            return outcome
    assert outcome is not None
    return outcome


def _record_dispatched_test_run(
    store: ProofStateStore,
    action: Mapping[str, object],
    run_id: str,
    *,
    created_at: str = "",
    planning_audit_heads: Mapping[str, object] | None = None,
) -> PatchOutcome:
    return _record_dispatched_test_wave(
        store,
        [action],
        [run_id],
        created_at=created_at,
        planning_audit_heads=planning_audit_heads,
    )


class SchedulerDecisionTraceTests(unittest.TestCase):
    @staticmethod
    def _policy_contract_source(
        versions: tuple[int, ...], commitments: dict[int, str], *, active: int | None = None
    ) -> str:
        return (
            f"ACTIVE = {active if active is not None else versions[-1]!r}\n"
            f"SUPPORTED = {versions!r}\n"
            f"COMMITMENTS = MappingProxyType({commitments!r})\n"
        )

    def test_policy_epoch_history_is_strictly_append_only(self) -> None:
        parse = policy_epoch_guard_module.parse_policy_epoch_contract
        base = parse(
            self._policy_contract_source((3, 4), {3: "3" * 64, 4: "4" * 64}),
            active_name="ACTIVE",
            supported_name="SUPPORTED",
            commitments_name="COMMITMENTS",
        )
        appended = parse(
            self._policy_contract_source(
                (3, 4, 5), {3: "3" * 64, 4: "4" * 64, 5: "5" * 64}
            ),
            active_name="ACTIVE",
            supported_name="SUPPORTED",
            commitments_name="COMMITMENTS",
        )
        self.assertEqual(
            [],
            policy_epoch_guard_module.policy_epoch_history_errors(
                base, appended, label="test"
            ),
        )

        modified = parse(
            self._policy_contract_source((3, 4), {3: "a" * 64, 4: "4" * 64}),
            active_name="ACTIVE",
            supported_name="SUPPORTED",
            commitments_name="COMMITMENTS",
        )
        removed = parse(
            self._policy_contract_source((3,), {3: "3" * 64}, active=3),
            active_name="ACTIVE",
            supported_name="SUPPORTED",
            commitments_name="COMMITMENTS",
        )
        inserted = parse(
            self._policy_contract_source(
                (2, 3, 4), {2: "2" * 64, 3: "3" * 64, 4: "4" * 64}
            ),
            active_name="ACTIVE",
            supported_name="SUPPORTED",
            commitments_name="COMMITMENTS",
        )
        self.assertIn(
            "semantic commitment was modified",
            " ".join(
                policy_epoch_guard_module.policy_epoch_history_errors(
                    base, modified, label="test"
                )
            ),
        )
        self.assertIn(
            "was removed",
            " ".join(
                policy_epoch_guard_module.policy_epoch_history_errors(
                    base, removed, label="test"
                )
            ),
        )
        self.assertIn(
            "not an append-only extension",
            " ".join(
                policy_epoch_guard_module.policy_epoch_history_errors(
                    base, inserted, label="test"
                )
            ),
        )
        downgraded = parse(
            self._policy_contract_source(
                (3, 4), {3: "3" * 64, 4: "4" * 64}, active=3
            ),
            active_name="ACTIVE",
            supported_name="SUPPORTED",
            commitments_name="COMMITMENTS",
        )
        self.assertIn(
            "active policy was downgraded",
            " ".join(
                policy_epoch_guard_module.policy_epoch_history_errors(
                    base, downgraded, label="test"
                )
            ),
        )

    def test_policy_epoch_contract_parser_fails_closed(self) -> None:
        parse = policy_epoch_guard_module.parse_policy_epoch_contract
        malformed_sources = (
            self._policy_contract_source((4, 3), {3: "3" * 64, 4: "4" * 64}),
            self._policy_contract_source((3, 3), {3: "3" * 64}),
            self._policy_contract_source((3, 4), {3: "3" * 64}),
            self._policy_contract_source((3,), {3: "not-a-digest"}),
            self._policy_contract_source(
                (3, 5), {3: "3" * 64, 5: "5" * 64}, active=5
            ),
            self._policy_contract_source((3,), {3: "3" * 64}, active=4),
            self._policy_contract_source((3,), {3: "3" * 64})
            + "ACTIVE = 2\n",
        )
        for source in malformed_sources:
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse(
                    source,
                    active_name="ACTIVE",
                    supported_name="SUPPORTED",
                    commitments_name="COMMITMENTS",
                )

        self.assertIn(
            "nonzero Git base",
            " ".join(policy_epoch_guard_module.check_repository_policy_epochs("0" * 40)),
        )

        failed = subprocess.CompletedProcess(
            args=["git"], returncode=128, stdout="", stderr="failed"
        )
        with mock.patch.object(
            policy_epoch_guard_module.subprocess, "run", return_value=failed
        ), self.assertRaises(RuntimeError):
            policy_epoch_guard_module._git_show("base", Path("policy.py"))

        present = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="entry\0", stderr=""
        )
        with mock.patch.object(
            policy_epoch_guard_module.subprocess,
            "run",
            side_effect=[present, failed],
        ), self.assertRaises(RuntimeError):
            policy_epoch_guard_module._git_show("base", Path("policy.py"))

    def test_repository_policy_epoch_guard_uses_real_git_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = Path(tmpdir)
            policy_path = repository / "policy.py"

            def git(*args: str) -> str:
                result = subprocess.run(
                    ["git", *args],
                    cwd=repository,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return result.stdout.strip()

            git("init", "-q")
            git("config", "user.name", "Policy Guard Test")
            git("config", "user.email", "policy-guard@example.invalid")
            policy_path.write_text(
                self._policy_contract_source(
                    (3, 4), {3: "3" * 64, 4: "4" * 64}
                ),
                encoding="utf-8",
            )
            git("add", "policy.py")
            git("commit", "-qm", "base policy")
            base_ref = git("rev-parse", "HEAD")
            policy_files = (
                ("test", Path("policy.py"), "ACTIVE", "SUPPORTED", "COMMITMENTS"),
            )
            original_cwd = Path.cwd()
            try:
                os.chdir(repository)
                with mock.patch.object(
                    policy_epoch_guard_module, "POLICY_FILES", policy_files
                ):
                    policy_path.write_text(
                        self._policy_contract_source(
                            (3, 4, 5),
                            {3: "3" * 64, 4: "4" * 64, 5: "5" * 64},
                        ),
                        encoding="utf-8",
                    )
                    self.assertEqual(
                        [],
                        policy_epoch_guard_module.check_repository_policy_epochs(
                            base_ref
                        ),
                    )
                    policy_path.write_text(
                        self._policy_contract_source(
                            (3, 4, 5),
                            {3: "a" * 64, 4: "4" * 64, 5: "5" * 64},
                        ),
                        encoding="utf-8",
                    )
                    errors = (
                        policy_epoch_guard_module.check_repository_policy_epochs(
                            base_ref
                        )
                    )
            finally:
                os.chdir(original_cwd)
            self.assertIn("semantic commitment was modified", " ".join(errors))

    def test_scheduler_action_contract_is_versioned_and_exhaustive(self) -> None:
        self.assertEqual(
            [], action_contract_module.scheduler_action_contract_semantic_errors()
        )
        self.assertEqual(
            set(action_contract_module.ACTION_MODE_SPECS),
            set(action_contract_module.RUN_MODES),
        )
        self.assertEqual(
            set(action_contract_module.SUPPORTED_SCHEDULER_ACTION_CONTRACT_VERSIONS),
            set(action_contract_module.ACTION_MODE_SPECS_BY_VERSION),
        )
        self.assertEqual(
            action_contract_module.ACTION_MODE_SPECS,
            action_contract_module.ACTION_MODE_SPECS_BY_VERSION[
                action_contract_module.SCHEDULER_ACTION_CONTRACT_VERSION
            ],
        )
        self.assertEqual(
            {
                mode
                for mode, spec in action_contract_module.ACTION_MODE_SPECS.items()
                if spec.budget_class == "verification"
            },
            set(budget_module.VERIFICATION_MODES),
        )
        self.assertEqual(
            {
                mode
                for mode, spec in action_contract_module.ACTION_MODE_SPECS.items()
                if spec.budget_class == "management"
            },
            set(budget_module.RESEARCH_MANAGEMENT_MODES),
        )
        self.assertEqual(
            {
                mode
                for mode, spec in action_contract_module.ACTION_MODE_SPECS.items()
                if spec.role_class == "literature"
            },
            set(retrieval_module.LITERATURE_SEARCH_MODES),
        )
        for mode, spec in action_contract_module.ACTION_MODE_SPECS.items():
            self.assertEqual(
                [],
                action_contract_module.scheduler_action_contract_errors(
                    {"mode": mode}
                ),
            )
            executable_errors = (
                action_contract_module.scheduler_action_contract_errors(
                    {"mode": mode, "target_id": "root"},
                    require_target=True,
                    executable=True,
                )
            )
            self.assertEqual(not spec.executable, bool(executable_errors), mode)

        tree = ast.parse(inspect.getsource(scheduler_module))
        literal_modes: set[str] = set()
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_action"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                literal_modes.add(node.args[0].value)
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "mode"
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                    ):
                        literal_modes.add(value.value)
        self.assertEqual(
            set(), literal_modes - set(action_contract_module.RUN_MODES)
        )
        self.assertTrue(
            any(
                label == "scheduler action contract"
                for label, *_rest in policy_epoch_guard_module.POLICY_FILES
            )
        )
        _selected, trace = select_action_candidate(
            [
                ActionCandidate(
                    "action-contract-binding",
                    "test",
                    {"mode": "reduce", "target_id": "root"},
                    1.0,
                )
            ],
            candidate_set_complete=True,
        )
        self.assertEqual(
            action_contract_module.scheduler_action_contract_trace_binding(),
            {
                key: trace[key]
                for key in (
                    "scheduler_action_contract_version",
                    "scheduler_action_contract_sha256",
                )
            },
        )
        self.assertEqual(
            [],
            action_contract_module.scheduler_action_contract_trace_errors(
                trace, required=True
            ),
        )
        direct_proof = {
            "mode": "prove",
            "target_id": "root",
            "budget": {
                "allowed": True,
                "requested_tokens": 80,
                "request_limit_tokens": 80,
                "spendable_tokens": 80,
                "remaining_token_budget": 100,
                "reserved_verification_budget": 20,
                "reason": "ok",
            },
        }
        strict_verification = json.loads(json.dumps(direct_proof))
        strict_verification["route_id"] = "route-root"
        strict_verification["budget"]["spendable_tokens"] = 100
        self.assertEqual(
            "research",
            action_contract_module.scheduler_budget_class_for_action(
                direct_proof
            ),
        )
        self.assertEqual(
            "verification",
            action_contract_module.scheduler_budget_class_for_action(
                strict_verification
            ),
        )
        self.assertEqual(
            [],
            action_contract_module.scheduler_dispatch_action_errors(
                direct_proof
            ),
        )
        self.assertEqual(
            [],
            action_contract_module.scheduler_dispatch_action_errors(
                strict_verification
            ),
        )
        strict_verification["budget"]["spendable_tokens"] = 80
        self.assertTrue(
            action_contract_module.scheduler_dispatch_action_errors(
                strict_verification
            )
        )
        missing_limit = json.loads(json.dumps(direct_proof))
        del missing_limit["budget"]["request_limit_tokens"]
        self.assertTrue(
            any(
                "request_limit_tokens" in error
                for error in action_contract_module.scheduler_dispatch_action_errors(
                    missing_limit
                )
            )
        )

    def test_scheduler_action_contract_detects_mutation_and_invalid_selection(self) -> None:
        modified = dict(action_contract_module.ACTION_MODE_SPECS)
        modified.pop("regulate_decomposition")
        versioned = dict(action_contract_module.ACTION_MODE_SPECS_BY_VERSION)
        versioned[action_contract_module.SCHEDULER_ACTION_CONTRACT_VERSION] = (
            modified
        )
        with mock.patch.object(
            action_contract_module, "ACTION_MODE_SPECS_BY_VERSION", versioned
        ):
            errors = (
                action_contract_module.scheduler_action_contract_semantic_errors()
            )
        self.assertTrue(
            any("changed without a new version" in error for error in errors),
            errors,
        )
        with self.assertRaisesRegex(ValueError, "routing contract"):
            select_action_candidate(
                [
                    ActionCandidate(
                        "invalid-mode",
                        "test",
                        {"mode": "not_a_run_mode", "target_id": "root"},
                        1.0,
                    )
                ],
                candidate_set_complete=True,
            )
        self.assertTrue(
            action_contract_module.scheduler_action_contract_errors(
                {"mode": "reduce", "target_id": " root "},
                require_target=True,
                executable=True,
            )
        )
        _selected, trace = select_action_candidate(
            [
                ActionCandidate(
                    "action-contract-tamper",
                    "test",
                    {"mode": "reduce", "target_id": "root"},
                    1.0,
                )
            ],
            candidate_set_complete=True,
        )
        tampered_trace = dict(trace)
        tampered_trace["scheduler_action_contract_sha256"] = "0" * 64
        self.assertTrue(decision_trace_errors(tampered_trace))
        legacy_trace = dict(trace)
        legacy_trace.pop("scheduler_action_contract_version")
        legacy_trace.pop("scheduler_action_contract_sha256")
        self.assertEqual([], decision_trace_errors(legacy_trace))
        self.assertTrue(
            action_contract_module.scheduler_action_contract_trace_errors(
                legacy_trace, required=True
            )
        )

    def test_online_scheduler_boundary_has_no_accumulated_control_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "online-control-scan",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            statements: list[str] = []
            with store.connect() as conn:
                conn.execute("BEGIN")
                conn.set_trace_callback(statements.append)
                seal = store.current_state_seal(conn)
                state = store.get_scheduler_state(conn=conn)
                conn.set_trace_callback(None)
                conn.rollback()
            self.assertTrue(seal["valid"], seal)
            self.assertEqual(0, state["run_count"])
            normalized = [" ".join(statement.upper().split()) for statement in statements]
            forbidden = (
                "COUNT(*) AS N FROM RUNS",
                "COUNT(*) AS N FROM PATCHES",
                "COUNT(*) AS COUNT FROM EVENTS",
                "COUNT(DISTINCT APPLIED_REVISION)",
                "SELECT * FROM EVENTS ORDER BY EVENT_ID ASC",
            )
            self.assertEqual(
                [],
                [
                    statement
                    for statement in normalized
                    if any(pattern in statement for pattern in forbidden)
                ],
            )

    def test_session_delta_history_uses_its_bounded_partial_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "session-delta-query-plan",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            with store.connect() as conn:
                plan = " ".join(
                    str(row["detail"])
                    for row in conn.execute(
                        "EXPLAIN QUERY PLAN SELECT patch_id, applied_revision, "
                        "authority_json, state_delta_json FROM patches "
                        "INDEXED BY idx_patches_applied_session_revision "
                        "WHERE status = 'applied' AND authority_source = 'session' "
                        "ORDER BY applied_revision DESC, patch_id DESC LIMIT ?",
                        (store_module.SCHEDULER_SESSION_PATCH_LIMIT,),
                    )
                )
            self.assertIn("idx_patches_applied_session_revision", plan)

    def test_parallel_identity_encoding_is_collision_free_and_versioned(self) -> None:
        common = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "",
            "search_intent": "exact_theorem_search",
        }
        left = {
            **common,
            "proof_obligation_id": "alpha|beta",
            "debt_id": "gamma",
        }
        right = {
            **common,
            "proof_obligation_id": "alpha",
            "debt_id": "beta|gamma",
        }
        action_class = "literature"
        legacy_left = parallel_admission_module.parallel_action_identity(
            left,
            action_class=action_class,
            policy_version=3,
        )
        legacy_right = parallel_admission_module.parallel_action_identity(
            right,
            action_class=action_class,
            policy_version=3,
        )
        modern_left = parallel_admission_module.parallel_action_identity(
            left,
            action_class=action_class,
        )
        modern_right = parallel_admission_module.parallel_action_identity(
            right,
            action_class=action_class,
        )

        self.assertEqual(legacy_left, legacy_right)
        self.assertNotEqual(modern_left, modern_right)
        self.assertNotEqual(
            parallel_admission_module.parallel_candidate_id(modern_left),
            parallel_admission_module.parallel_candidate_id(modern_right),
        )
        _selected, trace = scheduler_module._admit_parallel_companion_candidates(
            {"mode": "prove", "target_id": "root", "route_id": ""},
            [left, right],
            problem={"parallel_branches": 3},
        )
        self.assertEqual(3, len(trace["candidates"]))
        self.assertEqual(
            parallel_admission_module.PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
            trace["policy_version"],
        )
        self.assertEqual("parallel_wave", trace["candidate_generator_scope_id"])
        self.assertEqual(
            ["caller_supplied"], trace["active_candidate_generator_ids"]
        )
        self.assertEqual([], parallel_admission_module.parallel_wave_admission_errors(trace))

    def test_parallel_policy_versions_have_immutable_semantic_vectors(self) -> None:
        self.assertEqual(
            [],
            parallel_admission_module.parallel_policy_semantic_errors(),
        )
        digests = parallel_admission_module.PARALLEL_POLICY_SEMANTIC_SHA256
        self.assertEqual(
            set(
                parallel_admission_module.SUPPORTED_PARALLEL_WAVE_POLICY_VERSIONS
            ),
            set(digests),
        )
        self.assertNotEqual(digests[5], digests[6])
        self.assertNotEqual(digests[6], digests[7])
        self.assertNotEqual(digests[7], digests[8])
        self.assertNotEqual(digests[8], digests[9])
        self.assertNotEqual(digests[9], digests[10])
        self.assertNotEqual(digests[10], digests[11])
        self.assertNotEqual(digests[11], digests[12])
        self.assertNotEqual(digests[12], digests[13])
        self.assertNotEqual(digests[13], digests[14])
        self.assertNotEqual(digests[14], digests[15])
        self.assertNotEqual(digests[15], digests[16])
        self.assertNotEqual(digests[16], digests[17])
        self.assertNotEqual(digests[17], digests[18])
        self.assertNotEqual(digests[18], digests[19])
        self.assertNotEqual(digests[19], digests[20])
        self.assertNotEqual(digests[20], digests[21])
        self.assertNotEqual(digests[21], digests[22])
        self.assertNotEqual(digests[22], digests[23])
        self.assertNotEqual(digests[23], digests[24])
        self.assertNotEqual(digests[24], digests[25])

    def test_parallel_v9_search_beats_the_greedy_prefix_under_same_capacity(self) -> None:
        primary = {
            "mode": "triage_routes",
            "target_id": "primary",
            "route_id": "",
        }
        candidates = [
            {
                "mode": "integrate",
                "target_id": "integration-target",
                "route_id": "integration-route",
            },
            {
                "mode": "prove",
                "target_id": "verification-a",
                "route_id": "verification-route-a",
            },
            {
                "mode": "prove",
                "target_id": "verification-b",
                "route_id": "verification-route-b",
            },
        ]

        selected, trace = scheduler_module._admit_parallel_companion_candidates(
            primary,
            candidates,
            problem={"parallel_branches": 2},
            durable_deferral_counts={},
            _parallel_policy_version=9,
        )

        self.assertEqual(9, trace["policy_version"])
        self.assertEqual(["prove", "prove"], [row["mode"] for row in selected])
        search = trace["admission_search"]
        self.assertEqual(
            "deterministic_beam_search_with_greedy_lower_bound",
            search["algorithm"],
        )
        self.assertEqual("exact", search["optimality"])
        self.assertFalse(search["model_self_scores_used"])
        self.assertTrue(search["dominates_or_equals_greedy_baseline"])
        self.assertEqual("beam_search", search["selected_policy"])
        self.assertLessEqual(
            search["states_expanded"],
            2
            * search["candidate_count"]
            * parallel_admission_module.PARALLEL_ADMISSION_SEARCH_BEAM_WIDTH,
        )
        self.assertEqual([], parallel_admission_module.parallel_wave_admission_errors(trace))

        legacy, _remaining = parallel_admission_module.parallel_admission_outcomes(
            trace["candidates"],
            total_capacity=trace["total_wave_capacity"],
            class_capacities=trace["class_capacities"],
            aggregate_budget_enforced=False,
            policy_version=8,
        )
        legacy_selected_modes = [
            row["mode"]
            for row in trace["candidates"][1:]
            if legacy[row["candidate_id"]].disposition == "selected"
        ]
        self.assertEqual(["integrate"], legacy_selected_modes)

    def test_parallel_v10_search_evidence_is_replayed_and_wave_bound(self) -> None:
        _selected, trace = scheduler_module._admit_parallel_companion_candidates(
            {"mode": "triage_routes", "target_id": "root", "route_id": ""},
            [
                {
                    "mode": "reduce",
                    "target_id": "lemma",
                    "route_id": "lemma-route",
                    "proof_obligation_id": "search-evidence",
                }
            ],
            problem={"parallel_branches": 3},
            durable_deferral_counts={},
        )
        tampered = json.loads(json.dumps(trace))
        tampered["admission_search"]["beam_width"] += 1

        errors = parallel_admission_module.parallel_wave_admission_errors(tampered)

        self.assertTrue(
            any("admission-search evidence" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("identifier does not bind" in error for error in errors),
            errors,
        )
        forged_bound = json.loads(json.dumps(trace))
        forged_bound["admission_search"]["upper_bound_objective_value"] = [
            0,
            0,
            0,
            0,
        ]
        forged_bound_errors = (
            parallel_admission_module.parallel_wave_admission_errors(
                forged_bound
            )
        )
        self.assertTrue(
            any(
                "admission-search evidence" in error
                for error in forged_bound_errors
            ),
            forged_bound_errors,
        )
        noncanonical = dict(trace)
        noncanonical["admission_search"] = dict(trace["admission_search"])
        noncanonical["admission_search"]["objective_value"] = [float("nan")]
        noncanonical_errors = (
            parallel_admission_module.parallel_wave_admission_errors(
                noncanonical
            )
        )
        self.assertTrue(
            any("not canonical JSON" in error for error in noncanonical_errors),
            noncanonical_errors,
        )

    def test_parallel_v11_joint_admission_uses_minimum_feasible_grants(self) -> None:
        def descriptor(
            index: int,
            *,
            action_class: str,
            mode: str,
            requested_tokens: int,
            primary: bool = False,
        ) -> dict[str, object]:
            action = {
                "mode": mode,
                "target_id": f"allocation-target-{index}",
                "route_id": f"allocation-route-{index}",
                "search_intent": "joint_allocation_probe",
            }
            identity = parallel_admission_module.parallel_action_identity(
                action,
                action_class=action_class,
                policy_version=11,
            )
            return {
                "candidate_id": (
                    "parallel:primary"
                    if primary
                    else parallel_admission_module.parallel_candidate_id(
                        identity, policy_version=11
                    )
                ),
                "admission_priority": (
                    1_000_000
                    if primary
                    else parallel_admission_module.parallel_admission_priority_for(
                        action_class, "joint_allocation_probe"
                    )
                ),
                "action_class": action_class,
                **action,
                "semantic_identity": list(identity),
                "consecutive_deferrals": 0,
                "deferral_limit": (
                    0
                    if primary
                    else parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                ),
                "budget_allowed": True,
                "requested_tokens": requested_tokens,
                "comparison_action_sha256": hashlib.sha256(
                    f"allocation-{index}".encode("ascii")
                ).hexdigest(),
            }

        rows = [
            descriptor(
                -1,
                action_class="advisory",
                mode="triage_routes",
                requested_tokens=0,
                primary=True,
            ),
            descriptor(
                0,
                action_class="research",
                mode="reduce",
                requested_tokens=30_000,
            ),
            descriptor(
                1,
                action_class="research",
                mode="reduce",
                requested_tokens=30_000,
            ),
        ]
        capacities = {
            "research_or_adversarial": 2,
            "verification": 1,
            "integration": 1,
            "literature": 1,
            "advisory": 1,
        }
        historical, _historical_remaining = (
            parallel_admission_module.parallel_admission_outcomes(
                rows,
                total_capacity=3,
                class_capacities=capacities,
                aggregate_budget_enforced=True,
                initial_remaining_token_budget=30_000,
                initial_reserved_verification_budget=0,
                policy_version=10,
            )
        )
        metadata: dict[str, object] = {}
        outcomes, remaining = parallel_admission_module.parallel_admission_outcomes(
            rows,
            total_capacity=3,
            class_capacities=capacities,
            aggregate_budget_enforced=True,
            initial_remaining_token_budget=30_000,
            initial_reserved_verification_budget=0,
            policy_version=11,
            search_metadata_out=metadata,
        )

        companion_ids = [str(row["candidate_id"]) for row in rows[1:]]
        self.assertEqual(
            1,
            sum(
                historical[candidate_id].disposition == "selected"
                for candidate_id in companion_ids
            ),
        )
        self.assertEqual(
            ["selected", "selected"],
            [outcomes[candidate_id].disposition for candidate_id in companion_ids],
        )
        self.assertEqual(
            [15_000, 15_000],
            [outcomes[candidate_id].admitted_tokens for candidate_id in companion_ids],
        )
        self.assertEqual(0, remaining)
        self.assertEqual(3, metadata["version"])
        self.assertEqual([0, 200, 2, 10_000], metadata["objective_value"])
        self.assertTrue(metadata["optimality_certified"])
        self.assertEqual(
            "minimum_feasible_grants_then_reserved_and_max_min_fair_top_up",
            metadata["allocation_strategy"],
        )

    def test_parallel_v11_budget_bound_contains_exhaustive_optimum(self) -> None:
        rng = random.Random(110011)
        capacities = {
            "research_or_adversarial": 2,
            "verification": 2,
            "integration": 1,
            "literature": 1,
            "advisory": 1,
        }

        def descriptor(
            index: int, action_class: str, *, primary: bool = False
        ) -> dict[str, object]:
            action = {
                "mode": "triage_routes" if primary else (
                    "prove" if action_class == "verification" else "reduce"
                ),
                "target_id": f"budget-bound-target-{index}",
                "route_id": f"budget-bound-route-{index}",
                "search_intent": "budget_bound_probe",
                "proof_obligation_id": f"budget-bound-obligation-{index}",
            }
            identity = parallel_admission_module.parallel_action_identity(
                action, action_class=action_class, policy_version=11
            )
            return {
                "candidate_id": (
                    "parallel:primary"
                    if primary
                    else parallel_admission_module.parallel_candidate_id(
                        identity, policy_version=11
                    )
                ),
                "admission_priority": (
                    1_000_000
                    if primary
                    else parallel_admission_module.parallel_admission_priority_for(
                        action_class, "budget_bound_probe"
                    )
                ),
                "action_class": action_class,
                **action,
                "semantic_identity": list(identity),
                "consecutive_deferrals": (
                    0 if primary else rng.choice((0, 0, 3, 5))
                ),
                "deferral_limit": (
                    0
                    if primary
                    else parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                ),
                "budget_allowed": True,
                "requested_tokens": (
                    0 if primary else rng.choice((0, 10_000, 20_000, 30_000))
                ),
                "comparison_action_sha256": hashlib.sha256(
                    f"budget-bound-{index}".encode("ascii")
                ).hexdigest(),
            }

        pruned = 0
        with mock.patch.object(
            parallel_admission_module,
            "PARALLEL_ADMISSION_SEARCH_BEAM_WIDTH",
            2,
        ):
            for trial_index in range(30):
                primary = descriptor(-trial_index - 1, "advisory", primary=True)
                candidates = [
                    descriptor(
                        trial_index * 8 + index,
                        rng.choice(("research", "verification")),
                    )
                    for index in range(8)
                ]
                results: list[
                    tuple[
                        int,
                        dict[str, parallel_admission_module.ParallelAdmissionOutcome],
                        dict[str, object],
                    ]
                ] = []
                for policy_version in (11, 13):
                    metadata: dict[str, object] = {}
                    outcomes, _remaining = (
                        parallel_admission_module.parallel_admission_outcomes(
                            [primary, *candidates],
                            total_capacity=4,
                            class_capacities=capacities,
                            aggregate_budget_enforced=True,
                            initial_remaining_token_budget=20_000,
                            initial_reserved_verification_budget=10_000,
                            policy_version=policy_version,
                            search_metadata_out=metadata,
                        )
                    )
                    results.append((policy_version, outcomes, metadata))

                def feasible(subset: tuple[dict[str, object], ...]) -> bool:
                    if len(subset) > 3:
                        return False
                    research_count = sum(
                        row["action_class"] == "research" for row in subset
                    )
                    verification_count = sum(
                        row["action_class"] == "verification" for row in subset
                    )
                    if research_count > 2 or verification_count > 2:
                        return False
                    minimums = [
                        0
                        if int(row["requested_tokens"]) == 0
                        else parallel_admission_module.MIN_STEP_BUDGET
                        for row in subset
                    ]
                    unprotected_minimum = sum(
                        minimum
                        for row, minimum in zip(subset, minimums)
                        if row["action_class"] == "research"
                    )
                    return (
                        unprotected_minimum <= 10_000
                        and sum(minimums) <= 20_000
                    )

                def objective(
                    subset: tuple[dict[str, object], ...]
                ) -> tuple[int, int, int, int]:
                    minimum_total = sum(
                        0
                        if int(row["requested_tokens"]) == 0
                        else parallel_admission_module.MIN_STEP_BUDGET
                        for row in subset
                    )
                    return (
                        sum(
                            int(row["consecutive_deferrals"]) + 1
                            for row in subset
                            if int(row["consecutive_deferrals"])
                            >= int(row["deferral_limit"])
                        ),
                        sum(int(row["admission_priority"]) for row in subset),
                        len(subset),
                        20_000 - minimum_total,
                    )

                feasible_subsets = [
                    subset
                    for size in range(4)
                    for subset in itertools.combinations(candidates, size)
                    if feasible(subset)
                ]
                exact = max(objective(subset) for subset in feasible_subsets)
                for policy_version, outcomes, metadata in results:
                    selected = tuple(
                        row
                        for row in candidates
                        if outcomes[str(row["candidate_id"])].disposition
                        == "selected"
                    )
                    selected_objective = objective(selected)
                    upper_bound = tuple(metadata["upper_bound_objective_value"])
                    self.assertTrue(feasible(selected))
                    self.assertEqual(
                        selected_objective, tuple(metadata["objective_value"])
                    )
                    self.assertLessEqual(selected_objective, exact)
                    self.assertLessEqual(exact, upper_bound)
                    if metadata["optimality_certified"]:
                        self.assertEqual(selected_objective, exact)
                    if policy_version == 13:
                        self.assertLessEqual(
                            upper_bound,
                            tuple(results[0][2]["upper_bound_objective_value"]),
                        )
                    pruned += int(bool(metadata["pruned"]))
        self.assertGreater(pruned, 0)

    def test_parallel_v13_resource_bound_contains_exhaustive_optimum(self) -> None:
        rng = random.Random(130013)
        capacities = {
            "research_or_adversarial": 2,
            "verification": 2,
            "integration": 1,
            "literature": 1,
            "advisory": 1,
        }
        modes = {
            "advisory": "triage_routes",
            "research": "reduce",
            "verification": "prove",
            "integration": "integrate",
            "literature": "retrieve",
        }

        def descriptor(
            index: int, action_class: str, *, primary: bool = False
        ) -> dict[str, object]:
            action = {
                "mode": modes[action_class],
                "target_id": f"resource-target-{rng.randrange(4)}",
                "route_id": f"resource-route-{rng.randrange(4)}",
                "search_intent": "resource_exhaustive_probe",
                "proof_obligation_id": f"resource-obligation-{index}",
            }
            identity = parallel_admission_module.parallel_action_identity(
                action, action_class=action_class, policy_version=13
            )
            return {
                "candidate_id": (
                    "parallel:primary"
                    if primary
                    else parallel_admission_module.parallel_candidate_id(
                        identity, policy_version=13
                    )
                ),
                "admission_priority": (
                    1_000_000
                    if primary
                    else rng.randrange(1, 50)
                ),
                "action_class": action_class,
                **action,
                "semantic_identity": list(identity),
                "consecutive_deferrals": (
                    0 if primary else rng.choice((0, 0, 3, 5))
                ),
                "deferral_limit": (
                    0
                    if primary
                    else parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                ),
                "budget_allowed": True if primary else rng.randrange(5) != 0,
                "requested_tokens": (
                    0 if primary else rng.choice((0, 5_000, 10_000, 20_000))
                ),
                "comparison_action_sha256": hashlib.sha256(
                    f"resource-exhaustive-{index}".encode("ascii")
                ).hexdigest(),
            }

        def capacity_class(row: dict[str, object]) -> str:
            return (
                "research_or_adversarial"
                if row["action_class"] in {"research", "adversarial"}
                else str(row["action_class"])
            )

        tightened_trials = 0
        certified_trials = 0
        with mock.patch.object(
            parallel_admission_module,
            "PARALLEL_ADMISSION_SEARCH_BEAM_WIDTH",
            3,
        ):
            for trial in range(50):
                primary = descriptor(-trial - 1, "advisory", primary=True)
                candidates = [
                    descriptor(
                        trial * 10 + index,
                        rng.choice(
                            (
                                "research",
                                "verification",
                                "integration",
                                "literature",
                            )
                        ),
                    )
                    for index in range(10)
                ]
                candidates.sort(
                    key=lambda row: (
                        parallel_admission_module.parallel_admission_order_key(
                            row, policy_version=13
                        )
                    )
                )
                total_tokens = rng.choice((10_000, 20_000, 30_000))
                reserved_tokens = rng.randrange(total_tokens // 10_000 + 1) * 10_000
                unreserved_tokens = total_tokens - reserved_tokens

                def feasible(subset: tuple[dict[str, object], ...]) -> bool:
                    if len(subset) > 3:
                        return False
                    counts = {key: 0 for key in capacities}
                    counts[capacity_class(primary)] += 1
                    identities = [tuple(primary["semantic_identity"])]
                    positive_count = 0
                    shared_positive_count = 0
                    for row in subset:
                        if row["budget_allowed"] is not True:
                            return False
                        request = int(row["requested_tokens"])
                        if request and request < parallel_admission_module.MIN_STEP_BUDGET:
                            return False
                        key = capacity_class(row)
                        if counts.get(key, 0) >= capacities.get(key, 0):
                            return False
                        identity = tuple(row["semantic_identity"])
                        if parallel_admission_module.parallel_identity_conflict_reason(
                            identity, identities
                        ):
                            return False
                        counts[key] = counts.get(key, 0) + 1
                        identities.append(identity)
                        if request:
                            positive_count += 1
                            if not parallel_admission_module._parallel_uses_protected_budget(
                                row
                            ):
                                shared_positive_count += 1
                    return (
                        positive_count * parallel_admission_module.MIN_STEP_BUDGET
                        <= total_tokens
                        and shared_positive_count
                        * parallel_admission_module.MIN_STEP_BUDGET
                        <= unreserved_tokens
                    )

                def objective(
                    subset: tuple[dict[str, object], ...]
                ) -> tuple[int, int, int, int]:
                    positive_count = sum(
                        int(row["requested_tokens"]) > 0 for row in subset
                    )
                    return (
                        sum(
                            int(row["consecutive_deferrals"]) + 1
                            for row in subset
                            if int(row["consecutive_deferrals"])
                            >= int(row["deferral_limit"])
                        ),
                        sum(int(row["admission_priority"]) for row in subset),
                        len(subset),
                        total_tokens
                        - positive_count
                        * parallel_admission_module.MIN_STEP_BUDGET,
                    )

                feasible_subsets = [
                    subset
                    for size in range(4)
                    for subset in itertools.combinations(candidates, size)
                    if feasible(subset)
                ]
                exact = max(objective(subset) for subset in feasible_subsets)
                canonical_ids = min(
                    tuple(str(row["candidate_id"]) for row in subset)
                    for subset in feasible_subsets
                    if objective(subset) == exact
                )
                metadata_by_version: dict[int, dict[str, object]] = {}
                for policy_version in (
                    12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25
                ):
                    metadata: dict[str, object] = {}
                    outcomes, _remaining = (
                        parallel_admission_module.parallel_admission_outcomes(
                            [primary, *candidates],
                            total_capacity=4,
                            class_capacities=capacities,
                            aggregate_budget_enforced=True,
                            initial_remaining_token_budget=total_tokens,
                            initial_reserved_verification_budget=reserved_tokens,
                            policy_version=policy_version,
                            search_metadata_out=metadata,
                        )
                    )
                    metadata_by_version[policy_version] = metadata
                    selected = tuple(
                        row
                        for row in candidates
                        if outcomes[str(row["candidate_id"])].disposition
                        == "selected"
                    )
                    selected_objective = objective(selected)
                    upper_bound = tuple(metadata["upper_bound_objective_value"])
                    self.assertTrue(feasible(selected))
                    self.assertEqual(
                        selected_objective, tuple(metadata["objective_value"])
                    )
                    self.assertLessEqual(selected_objective, exact)
                    self.assertLessEqual(exact, upper_bound)
                    if metadata["optimality_certified"]:
                        self.assertEqual(exact, selected_objective)
                    if policy_version >= 19:
                        self.assertEqual(
                            canonical_ids,
                            tuple(str(row["candidate_id"]) for row in selected),
                        )
                        self.assertTrue(metadata["canonical_selection_certified"])
                historical_bound = tuple(
                    metadata_by_version[12]["upper_bound_objective_value"]
                )
                current_bound = tuple(
                    metadata_by_version[13]["upper_bound_objective_value"]
                )
                clique_bound = tuple(
                    metadata_by_version[14]["upper_bound_objective_value"]
                )
                self.assertLessEqual(current_bound, historical_bound)
                self.assertLessEqual(clique_bound, current_bound)
                self.assertLessEqual(
                    tuple(metadata_by_version[15]["upper_bound_objective_value"]),
                    clique_bound,
                )
                self.assertLessEqual(
                    tuple(metadata_by_version[16]["upper_bound_objective_value"]),
                    tuple(metadata_by_version[15]["upper_bound_objective_value"]),
                )
                self.assertLessEqual(
                    tuple(metadata_by_version[17]["upper_bound_objective_value"]),
                    tuple(metadata_by_version[16]["upper_bound_objective_value"]),
                )
                self.assertLessEqual(
                    tuple(metadata_by_version[18]["upper_bound_objective_value"]),
                    tuple(metadata_by_version[17]["upper_bound_objective_value"]),
                )
                self.assertLessEqual(
                    tuple(metadata_by_version[19]["upper_bound_objective_value"]),
                    tuple(metadata_by_version[18]["upper_bound_objective_value"]),
                )
                self.assertLessEqual(
                    tuple(metadata_by_version[20]["upper_bound_objective_value"]),
                    tuple(metadata_by_version[19]["upper_bound_objective_value"]),
                )
                self.assertLessEqual(
                    tuple(metadata_by_version[21]["upper_bound_objective_value"]),
                    tuple(metadata_by_version[20]["upper_bound_objective_value"]),
                )
                self.assertLessEqual(
                    tuple(metadata_by_version[22]["upper_bound_objective_value"]),
                    tuple(metadata_by_version[21]["upper_bound_objective_value"]),
                )
                self.assertLessEqual(
                    tuple(metadata_by_version[23]["upper_bound_objective_value"]),
                    tuple(metadata_by_version[22]["upper_bound_objective_value"]),
                )
                self.assertLessEqual(
                    tuple(metadata_by_version[24]["upper_bound_objective_value"]),
                    tuple(metadata_by_version[23]["upper_bound_objective_value"]),
                )
                self.assertLessEqual(
                    tuple(metadata_by_version[25]["upper_bound_objective_value"]),
                    tuple(metadata_by_version[24]["upper_bound_objective_value"]),
                )
                tightened_trials += int(current_bound < historical_bound)
                certified_trials += int(
                    bool(metadata_by_version[13]["optimality_certified"])
                )
        self.assertGreater(tightened_trials, 0)
        self.assertGreater(certified_trials, 0)

    def test_parallel_v11_max_min_top_up_is_integer_total(self) -> None:
        grants, remaining = parallel_admission_module._max_min_token_top_up(
            {0: 10_000, 1: 10_000},
            {0: 10**400, 1: 10**400},
            [0, 1],
            10_001,
        )

        self.assertEqual({0: 15_001, 1: 15_000}, grants)
        self.assertEqual(0, remaining)
        with self.assertRaisesRegex(ValueError, "positions must be unique"):
            parallel_admission_module._max_min_token_top_up(
                {0: 0},
                {0: 1},
                [0, 0],
                1,
            )

    def test_parallel_v12_certifies_the_class_conflict_relaxation(self) -> None:
        modes = {
            "advisory": "triage_routes",
            "integration": "integrate",
            "verification": "prove",
            "literature": "retrieve",
            "research": "reduce",
        }

        def descriptor(
            index: int, action_class: str, *, primary: bool = False
        ) -> dict[str, object]:
            action = {
                "mode": modes[action_class],
                "target_id": f"class-bound-target-{index}",
                "route_id": f"class-bound-route-{index}",
                "search_intent": "class_bound_probe",
            }
            identity = parallel_admission_module.parallel_action_identity(
                action, action_class=action_class, policy_version=12
            )
            return {
                "candidate_id": (
                    "parallel:primary"
                    if primary
                    else parallel_admission_module.parallel_candidate_id(
                        identity, policy_version=12
                    )
                ),
                "admission_priority": (
                    1_000_000
                    if primary
                    else parallel_admission_module.parallel_admission_priority_for(
                        action_class, "class_bound_probe"
                    )
                ),
                "action_class": action_class,
                **action,
                "semantic_identity": list(identity),
                "consecutive_deferrals": (
                    0
                    if primary
                    else parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                ),
                "deferral_limit": (
                    0
                    if primary
                    else parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                ),
                "budget_allowed": True,
                "requested_tokens": 0,
                "comparison_action_sha256": hashlib.sha256(
                    f"class-bound-{index}".encode("ascii")
                ).hexdigest(),
            }

        primary = descriptor(-1, "advisory", primary=True)
        candidates = [
            descriptor(group * 10 + index, action_class)
            for group, action_class in enumerate(
                ("integration", "verification", "literature", "research")
            )
            for index in range(4)
        ]
        candidates.sort(
            key=lambda row: parallel_admission_module.parallel_admission_order_key(
                row, policy_version=12
            )
        )
        capacities = {
            "research_or_adversarial": 1,
            "verification": 2,
            "integration": 2,
            "literature": 1,
            "advisory": 1,
        }
        legacy_metadata: dict[str, object] = {}
        metadata: dict[str, object] = {}
        with mock.patch.object(
            parallel_admission_module,
            "PARALLEL_ADMISSION_SEARCH_BEAM_WIDTH",
            2,
        ):
            parallel_admission_module.parallel_admission_outcomes(
                [primary, *candidates],
                total_capacity=5,
                class_capacities=capacities,
                aggregate_budget_enforced=False,
                policy_version=11,
                search_metadata_out=legacy_metadata,
            )
            parallel_admission_module.parallel_admission_outcomes(
                [primary, *candidates],
                total_capacity=5,
                class_capacities=capacities,
                aggregate_budget_enforced=False,
                policy_version=12,
                search_metadata_out=metadata,
            )

        self.assertEqual([16, 1_700, 4, 0], metadata["objective_value"])
        self.assertEqual(
            metadata["objective_value"], metadata["upper_bound_objective_value"]
        )
        self.assertTrue(metadata["optimality_certified"])
        self.assertEqual("exact", metadata["optimality"])
        self.assertGreater(
            legacy_metadata["upper_bound_objective_value"],
            legacy_metadata["objective_value"],
        )
        self.assertEqual(
            "class_capacities_and_verification_integration_exclusion",
            metadata["upper_bound_relaxation"],
        )

    def test_parallel_v13_certifies_the_minimum_token_resource_bound(self) -> None:
        def descriptor(index: int, *, primary: bool = False) -> dict[str, object]:
            action_class = "advisory" if primary else "research"
            action = {
                "mode": "triage_routes" if primary else "reduce",
                "target_id": f"resource-bound-target-{index}",
                "route_id": f"resource-bound-route-{index}",
                "search_intent": "resource_bound_probe",
            }
            identity = parallel_admission_module.parallel_action_identity(
                action, action_class=action_class, policy_version=13
            )
            return {
                "candidate_id": (
                    "parallel:primary"
                    if primary
                    else parallel_admission_module.parallel_candidate_id(
                        identity, policy_version=13
                    )
                ),
                "admission_priority": (
                    1_000_000
                    if primary
                    else parallel_admission_module.parallel_admission_priority_for(
                        action_class, "resource_bound_probe"
                    )
                ),
                "action_class": action_class,
                **action,
                "semantic_identity": list(identity),
                "consecutive_deferrals": 0,
                "deferral_limit": (
                    0
                    if primary
                    else parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                ),
                "budget_allowed": True,
                "requested_tokens": 0 if primary else 20_000,
                "comparison_action_sha256": hashlib.sha256(
                    f"resource-bound-{index}".encode("ascii")
                ).hexdigest(),
            }

        primary = descriptor(-1, primary=True)
        candidates = [descriptor(index) for index in range(40)]
        candidates.sort(
            key=lambda row: parallel_admission_module.parallel_admission_order_key(
                row, policy_version=13
            )
        )
        capacities = {
            "research_or_adversarial": 6,
            "verification": 5,
            "integration": 5,
            "literature": 1,
            "advisory": 1,
        }
        metadata_by_version: dict[int, dict[str, object]] = {}
        for policy_version in (12, 13):
            metadata: dict[str, object] = {}
            outcomes, remaining = parallel_admission_module.parallel_admission_outcomes(
                [primary, *candidates],
                total_capacity=7,
                class_capacities=capacities,
                aggregate_budget_enforced=True,
                initial_remaining_token_budget=20_000,
                initial_reserved_verification_budget=0,
                policy_version=policy_version,
                search_metadata_out=metadata,
            )
            metadata_by_version[policy_version] = metadata
            self.assertEqual(0, remaining)
            self.assertEqual(
                2,
                sum(
                    outcome.disposition == "selected"
                    for outcome in outcomes.values()
                ),
            )

        historical = metadata_by_version[12]
        current = metadata_by_version[13]
        self.assertGreater(
            historical["upper_bound_objective_value"],
            historical["objective_value"],
        )
        self.assertEqual([0, 200, 2, 0], current["objective_value"])
        self.assertEqual(
            current["objective_value"], current["upper_bound_objective_value"]
        )
        self.assertTrue(current["optimality_certified"])
        self.assertEqual("exact", current["optimality"])
        self.assertEqual(5, current["version"])
        self.assertEqual(
            "class_capacities_verification_integration_exclusion_primary_"
            "conflicts_and_minimum_token_resources",
            current["upper_bound_relaxation"],
        )

    def test_parallel_v14_certifies_route_and_target_clique_bounds(self) -> None:
        def descriptor(
            index: int,
            *,
            action_class: str,
            route_id: str,
            target_id: str,
            primary: bool = False,
        ) -> dict[str, object]:
            action = {
                "mode": (
                    "triage_routes"
                    if primary
                    else "prove"
                    if action_class == "verification"
                    else "reduce"
                ),
                "target_id": target_id,
                "route_id": route_id,
                "search_intent": "clique_bound_probe",
            }
            identity = parallel_admission_module.parallel_action_identity(
                action, action_class=action_class, policy_version=14
            )
            return {
                "candidate_id": (
                    "parallel:primary"
                    if primary
                    else parallel_admission_module.parallel_candidate_id(
                        identity, policy_version=14
                    )
                ),
                "admission_priority": (
                    1_000_000
                    if primary
                    else parallel_admission_module.parallel_admission_priority_for(
                        action_class, "clique_bound_probe"
                    )
                ),
                "action_class": action_class,
                **action,
                "semantic_identity": list(identity),
                "consecutive_deferrals": (
                    0
                    if primary
                    else parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                ),
                "deferral_limit": (
                    0
                    if primary
                    else parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                ),
                "budget_allowed": True,
                "requested_tokens": 0,
                "comparison_action_sha256": hashlib.sha256(
                    f"clique-bound-{action_class}-{index}".encode("ascii")
                ).hexdigest(),
            }

        primary = descriptor(
            -1,
            action_class="advisory",
            route_id="primary-route",
            target_id="primary-target",
            primary=True,
        )
        capacities = {
            "research_or_adversarial": 6,
            "verification": 6,
            "integration": 6,
            "literature": 1,
            "advisory": 1,
        }
        fixtures = (
            (
                "research",
                lambda index: "shared-route",
                lambda index: f"route-target-{index}",
                [4, 100, 1, 0],
            ),
            (
                "verification",
                lambda index: f"target-route-{index}",
                lambda index: "shared-target",
                [4, 500, 1, 0],
            ),
        )
        for action_class, route_for, target_for, exact_value in fixtures:
            candidates = [
                descriptor(
                    index,
                    action_class=action_class,
                    route_id=route_for(index),
                    target_id=target_for(index),
                )
                for index in range(100)
            ]
            candidates.sort(
                key=lambda row: (
                    parallel_admission_module.parallel_admission_order_key(
                        row, policy_version=14
                    )
                )
            )
            metadata_by_version: dict[int, dict[str, object]] = {}
            for policy_version in (13, 14):
                metadata: dict[str, object] = {}
                parallel_admission_module.parallel_admission_outcomes(
                    [primary, *candidates],
                    total_capacity=7,
                    class_capacities=capacities,
                    aggregate_budget_enforced=False,
                    policy_version=policy_version,
                    search_metadata_out=metadata,
                )
                metadata_by_version[policy_version] = metadata

            historical = metadata_by_version[13]
            current = metadata_by_version[14]
            self.assertEqual(exact_value, current["objective_value"])
            self.assertEqual(
                current["objective_value"], current["upper_bound_objective_value"]
            )
            self.assertTrue(current["optimality_certified"])
            self.assertEqual("exact", current["optimality"])
            self.assertEqual(6, current["version"])
            self.assertLess(
                current["upper_bound_objective_value"],
                historical["upper_bound_objective_value"],
            )
            self.assertEqual(
                "class_capacities_verification_integration_exclusion_primary_"
                "conflicts_minimum_token_resources_route_cliques_and_"
                "certification_target_cliques",
                current["upper_bound_relaxation"],
            )

    def test_parallel_v14_bounded_group_suffix_matches_full_partition_oracle(
        self,
    ) -> None:
        rng = random.Random(140014)
        for _trial in range(100):
            selection_limit = rng.randrange(1, 7)
            rows = [
                None
                if rng.randrange(7) == 0
                else (
                    rng.randrange(5),
                    rng.randrange(1, 100),
                    ("group", str(rng.randrange(12))),
                )
                for _ in range(30)
            ]
            suffixes = parallel_relaxation_module.grouped_suffix_values(
                rows,
                selection_limit=selection_limit,
            )
            all_groups = sorted({row[2] for row in rows if row is not None})
            for position in range(len(rows) + 1):
                occupied = tuple(
                    rng.sample(
                        all_groups,
                        k=min(len(all_groups), rng.randrange(selection_limit + 1)),
                    )
                )
                slots = rng.randrange(selection_limit + 1)
                best_by_group: dict[tuple[str, str], tuple[int, int]] = {}
                for row in rows[position:]:
                    if row is None or row[2] in occupied:
                        continue
                    value = row[:2]
                    best_by_group[row[2]] = max(
                        value,
                        best_by_group.get(row[2], value),
                    )
                selected = sorted(best_by_group.values(), reverse=True)[:slots]
                expected = (
                    sum(value[0] for value in selected),
                    sum(value[1] for value in selected),
                    len(selected),
                )
                self.assertEqual(
                    expected,
                    parallel_relaxation_module.grouped_relaxed_value(
                        suffixes[position],
                        slots=slots,
                        occupied_groups=occupied,
                    ),
                )

    def test_parallel_v18_indexed_suffix_conflicts_match_pairwise_oracle(
        self,
    ) -> None:
        rng = random.Random(180128)
        classes = (
            "research",
            "adversarial",
            "verification",
            "integration",
            "literature",
            "advisory",
        )
        modes = (
            "reduce",
            "refute",
            "prove",
            "integrate",
            "retrieve",
            "triage_routes",
            "write",
            "formalize",
        )
        for _trial in range(200):
            identities = [
                (
                    rng.choice(classes),
                    rng.choice(modes),
                    "" if rng.randrange(5) == 0 else f"target-{rng.randrange(7)}",
                    "" if rng.randrange(5) == 0 else f"route-{rng.randrange(7)}",
                    "suffix_conflict_oracle",
                    "",
                    "{}",
                    f"{rng.randrange(20):064x}",
                )
                for _ in range(rng.randrange(1, 40))
            ]
            masks = parallel_admission_module._parallel_suffix_conflict_masks(
                identities
            )
            for left_position, left in enumerate(identities):
                self.assertEqual(
                    0,
                    masks[left_position] & ((1 << (left_position + 1)) - 1),
                )
                for right_position in range(left_position + 1, len(identities)):
                    expected = bool(
                        parallel_admission_module.parallel_identity_conflict_reason(
                            identities[right_position], [left]
                        )
                    )
                    self.assertEqual(
                        expected,
                        bool(masks[left_position] & (1 << right_position)),
                    )

    def test_parallel_v17_through_v25_close_distinct_search_gaps(
        self,
    ) -> None:
        modes = {
            "advisory": "triage_routes",
            "research": "reduce",
            "adversarial": "refute",
            "verification": "prove",
            "integration": "integrate",
            "literature": "retrieve",
        }

        def descriptor(
            index: int,
            action_class: str,
            target_id: str,
            route_id: str,
            deferrals: int,
            *,
            primary: bool = False,
        ) -> dict[str, object]:
            action = {
                "mode": modes[action_class],
                "target_id": target_id,
                "route_id": route_id,
                "search_intent": "intersected_clique_probe",
                "proof_obligation_id": f"intersected-obligation-{index}",
            }
            identity = parallel_admission_module.parallel_action_identity(
                action, action_class=action_class, policy_version=16
            )
            return {
                "candidate_id": (
                    "parallel:primary"
                    if primary
                    else parallel_admission_module.parallel_candidate_id(
                        identity, policy_version=16
                    )
                ),
                "admission_priority": (
                    1_000_000
                    if primary
                    else parallel_admission_module.parallel_admission_priority_for(
                        action_class, "intersected_clique_probe"
                    )
                ),
                "action_class": action_class,
                **action,
                "semantic_identity": list(identity),
                "consecutive_deferrals": 0 if primary else deferrals,
                "deferral_limit": (
                    0
                    if primary
                    else parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                ),
                "budget_allowed": True,
                "requested_tokens": 0,
                "comparison_action_sha256": hashlib.sha256(
                    f"intersected-clique-{index}".encode("ascii")
                ).hexdigest(),
            }

        primary = descriptor(
            -1,
            "advisory",
            "primary-target",
            "primary-route",
            0,
            primary=True,
        )
        specifications = (
            ("integration", "t3", "r2", 5),
            ("adversarial", "t2", "r1", 5),
            ("research", "t0", "r2", 5),
            ("verification", "t1", "r1", 3),
            ("verification", "t1", "r1", 3),
            ("verification", "t1", "r2", 3),
            ("adversarial", "t0", "r2", 3),
            ("research", "t0", "r1", 3),
            ("integration", "t3", "r1", 0),
            ("integration", "t3", "r1", 0),
            ("verification", "t3", "r3", 0),
            ("adversarial", "t2", "r1", 0),
        )
        candidates = [
            descriptor(index, *specification)
            for index, specification in enumerate(specifications)
        ]
        candidates.sort(key=parallel_admission_module.parallel_admission_order_key)
        capacities = {
            "research_or_adversarial": 3,
            "verification": 3,
            "integration": 3,
            "literature": 1,
            "advisory": 1,
        }
        metadata_by_version: dict[int, dict[str, object]] = {}
        with mock.patch.object(
            parallel_admission_module,
            "PARALLEL_ADMISSION_SEARCH_BEAM_WIDTH",
            4,
        ):
            for policy_version in (14, 15, 16):
                metadata: dict[str, object] = {}
                parallel_admission_module.parallel_admission_outcomes(
                    [primary, *candidates],
                    total_capacity=6,
                    class_capacities=capacities,
                    aggregate_budget_enforced=False,
                    policy_version=policy_version,
                    search_metadata_out=metadata,
                )
                metadata_by_version[policy_version] = metadata

        self.assertEqual(
            [18, 1_500, 5, 0],
            metadata_by_version[14]["upper_bound_objective_value"],
        )
        self.assertEqual(
            [18, 1_400, 5, 0],
            metadata_by_version[15]["upper_bound_objective_value"],
        )
        current = metadata_by_version[16]
        self.assertEqual([16, 1_000, 4, 0], current["objective_value"])
        self.assertEqual(
            current["objective_value"], current["upper_bound_objective_value"]
        )
        self.assertTrue(current["optimality_certified"])
        self.assertEqual("exact", current["optimality"])
        self.assertEqual(8, current["version"])
        self.assertEqual(
            "primary_conflicts_minimum_token_resources_and_class_"
            "certification_filtered_mixed_route_and_target_cliques",
            current["upper_bound_relaxation"],
        )

        residual_specifications = (
            ("integration", "t2", "r2", 5),
            ("verification", "t0", "r0", 5),
            ("adversarial", "t2", "r3", 5),
            ("adversarial", "t3", "r2", 5),
            ("research", "t1", "r3", 5),
            ("verification", "t1", "r1", 3),
            ("adversarial", "t0", "r3", 3),
            ("research", "t1", "r1", 3),
            ("research", "t1", "r2", 3),
            ("integration", "t3", "r1", 0),
            ("verification", "t3", "r3", 0),
            ("research", "t2", "r0", 0),
        )
        residual_candidates = [
            descriptor(index + 100, *specification)
            for index, specification in enumerate(residual_specifications)
        ]
        residual_candidates.sort(
            key=parallel_admission_module.parallel_admission_order_key
        )

        def capacity_class(row: dict[str, object]) -> str:
            return (
                "research_or_adversarial"
                if row["action_class"] in {"research", "adversarial"}
                else str(row["action_class"])
            )

        def feasible(subset: tuple[dict[str, object], ...]) -> bool:
            if len(subset) > 5:
                return False
            counts = {key: 0 for key in capacities}
            counts[capacity_class(primary)] += 1
            identities = [tuple(primary["semantic_identity"])]
            for row in subset:
                key = capacity_class(row)
                if counts.get(key, 0) >= capacities.get(key, 0):
                    return False
                identity = tuple(row["semantic_identity"])
                if parallel_admission_module.parallel_identity_conflict_reason(
                    identity, identities
                ):
                    return False
                counts[key] = counts.get(key, 0) + 1
                identities.append(identity)
            return True

        def objective(
            subset: tuple[dict[str, object], ...]
        ) -> tuple[int, int, int, int]:
            return (
                sum(
                    int(row["consecutive_deferrals"]) + 1
                    for row in subset
                    if int(row["consecutive_deferrals"])
                    >= int(row["deferral_limit"])
                ),
                sum(int(row["admission_priority"]) for row in subset),
                len(subset),
                0,
            )

        exact = max(
            objective(subset)
            for size in range(6)
            for subset in itertools.combinations(residual_candidates, size)
            if feasible(subset)
        )
        residual_metadata: dict[str, object] = {}
        with mock.patch.object(
            parallel_admission_module,
            "PARALLEL_ADMISSION_SEARCH_BEAM_WIDTH",
            4,
        ):
            parallel_admission_module.parallel_admission_outcomes(
                [primary, *residual_candidates],
                total_capacity=6,
                class_capacities=capacities,
                aggregate_budget_enforced=False,
                policy_version=16,
                search_metadata_out=residual_metadata,
            )
        self.assertEqual((24, 1_000, 4, 0), exact)
        self.assertEqual(list(exact), residual_metadata["objective_value"])
        self.assertEqual(
            [24, 1_500, 5, 0],
            residual_metadata["upper_bound_objective_value"],
        )
        self.assertFalse(residual_metadata["optimality_certified"])
        self.assertEqual("bounded_approximation", residual_metadata["optimality"])

        repeated_candidates = [
            descriptor(index + 1_000, *residual_specifications[index % 12])
            for index in range(48)
        ]
        repeated_candidates.sort(
            key=parallel_admission_module.parallel_admission_order_key
        )
        for specification_index in range(12):
            action_class, target_id, route_id, _deferrals = (
                residual_specifications[specification_index]
            )
            projection = (
                action_class,
                modes[action_class],
                target_id,
                route_id,
            )
            structural_class = [
                row
                for row in repeated_candidates
                if tuple(row["semantic_identity"][:4]) == projection
            ]
            self.assertEqual(4, len(structural_class))
            for left, right in itertools.combinations(structural_class, 2):
                self.assertTrue(
                    parallel_admission_module.parallel_identity_conflict_reason(
                        tuple(left["semantic_identity"]),
                        [tuple(right["semantic_identity"])],
                    )
                )

        repeated_metadata: dict[int, dict[str, object]] = {}
        repeated_outcomes: dict[
            int, dict[str, parallel_admission_module.ParallelAdmissionOutcome]
        ] = {}
        for policy_version in (16, 17):
            metadata = {}
            outcomes, _remaining = parallel_admission_module.parallel_admission_outcomes(
                [primary, *repeated_candidates],
                total_capacity=6,
                class_capacities=capacities,
                aggregate_budget_enforced=False,
                policy_version=policy_version,
                search_metadata_out=metadata,
            )
            repeated_metadata[policy_version] = metadata
            repeated_outcomes[policy_version] = outcomes

        self.assertEqual(
            [28, 1_500, 5, 0],
            repeated_metadata[16]["upper_bound_objective_value"],
        )
        self.assertFalse(repeated_metadata[16]["optimality_certified"])
        current = repeated_metadata[17]
        self.assertEqual(list(exact), current["objective_value"])
        self.assertEqual(
            current["objective_value"], current["upper_bound_objective_value"]
        )
        self.assertEqual("exact", current["optimality"])
        self.assertTrue(current["optimality_certified"])
        self.assertEqual(9, current["version"])
        self.assertTrue(current["future_equivalence_quotient_applied"])
        self.assertGreater(current["states_merged_by_future_equivalence"], 0)
        self.assertEqual(
            "primary_conflicts_minimum_token_resources_class_certification_"
            "filtered_mixed_route_target_cliques_and_future_conflict_equivalence",
            current["upper_bound_relaxation"],
        )
        selected_rows = [
            row
            for row in repeated_candidates
            if repeated_outcomes[17][str(row["candidate_id"])].disposition
            == "selected"
        ]
        for selected in selected_rows:
            projection = tuple(selected["semantic_identity"][:4])
            self.assertEqual(
                min(
                    str(row["candidate_id"])
                    for row in repeated_candidates
                    if tuple(row["semantic_identity"][:4]) == projection
                ),
                selected["candidate_id"],
            )

        neighborhood_specifications = (
            ("integration", "t11", "r3", 5),
            ("integration", "t4", "r10", 5),
            ("integration", "t6", "r4", 5),
            ("verification", "t11", "r4", 5),
            ("verification", "t9", "r5", 5),
            ("literature", "t0", "r1", 5),
            ("literature", "t11", "r2", 5),
            ("literature", "t2", "r7", 5),
            ("literature", "t2", "r8", 5),
            ("literature", "t5", "r0", 5),
            ("adversarial", "t11", "r2", 5),
            ("adversarial", "t3", "r10", 5),
            ("research", "t3", "r4", 5),
        )
        neighborhood_candidates = []
        for index, specification in enumerate(neighborhood_specifications):
            candidate = descriptor(index + 20_000, *specification)
            candidate["candidate_id"] = f"parallel:{index + 1:024x}"
            neighborhood_candidates.append(candidate)
        neighborhood_candidates.sort(
            key=parallel_admission_module.parallel_admission_order_key
        )
        neighborhood_capacities = {
            "research_or_adversarial": 5,
            "verification": 5,
            "integration": 5,
            "literature": 2,
            "advisory": 1,
        }

        def neighborhood_feasible(
            subset: tuple[dict[str, object], ...]
        ) -> bool:
            if len(subset) > 7:
                return False
            counts = {key: 0 for key in neighborhood_capacities}
            counts[capacity_class(primary)] += 1
            identities = [tuple(primary["semantic_identity"])]
            for row in subset:
                key = capacity_class(row)
                if counts.get(key, 0) >= neighborhood_capacities.get(key, 0):
                    return False
                identity = tuple(row["semantic_identity"])
                if parallel_admission_module.parallel_identity_conflict_reason(
                    identity, identities
                ):
                    return False
                counts[key] = counts.get(key, 0) + 1
                identities.append(identity)
            return True

        neighborhood_exact = max(
            objective(subset)
            for size in range(8)
            for subset in itertools.combinations(neighborhood_candidates, size)
            if neighborhood_feasible(subset)
        )
        neighborhood_metadata: dict[int, dict[str, object]] = {}
        for policy_version in (17, 18):
            metadata = {}
            parallel_admission_module.parallel_admission_outcomes(
                [primary, *neighborhood_candidates],
                total_capacity=8,
                class_capacities=neighborhood_capacities,
                aggregate_budget_enforced=False,
                policy_version=policy_version,
                search_metadata_out=metadata,
            )
            neighborhood_metadata[policy_version] = metadata

        self.assertEqual((36, 1_800, 6, 0), neighborhood_exact)
        self.assertEqual(
            [30, 2_600, 5, 0], neighborhood_metadata[17]["objective_value"]
        )
        self.assertEqual(
            [36, 1_900, 6, 0],
            neighborhood_metadata[17]["upper_bound_objective_value"],
        )
        self.assertFalse(neighborhood_metadata[17]["optimality_certified"])
        current = neighborhood_metadata[18]
        self.assertEqual(list(neighborhood_exact), current["objective_value"])
        self.assertEqual(
            current["objective_value"], current["upper_bound_objective_value"]
        )
        self.assertTrue(current["optimality_certified"])
        self.assertEqual("exact", current["optimality"])
        self.assertEqual(10, current["version"])
        self.assertEqual(128, current["beam_width"])
        self.assertEqual(
            "exact_suffix_conflict_neighborhood",
            current["future_equivalence_basis"],
        )
        self.assertGreater(current["states_merged_by_future_equivalence"], 0)

        production_specifications = (
            ("integration", "t2", "r3", 5),
            ("integration", "t3", "r6", 5),
            ("integration", "t8", "r9", 5),
            ("literature", "t1", "r8", 5),
            ("literature", "t2", "r5", 5),
            ("literature", "t5", "r5", 5),
            ("literature", "t7", "r1", 5),
            ("adversarial", "t8", "r7", 5),
            ("research", "t1", "r5", 5),
            ("research", "t11", "r5", 5),
            ("research", "t2", "r11", 5),
            ("research", "t3", "r4", 5),
        )
        production_candidates = []
        for index, specification in enumerate(production_specifications):
            candidate = descriptor(index + 30_000, *specification)
            candidate["candidate_id"] = f"parallel:{index + 1:024x}"
            production_candidates.append(candidate)
        production_candidates.sort(
            key=parallel_admission_module.parallel_admission_order_key
        )
        production_capacities = {
            "research_or_adversarial": 5,
            "verification": 5,
            "integration": 5,
            "literature": 1,
            "advisory": 1,
        }

        def production_feasible(
            subset: tuple[dict[str, object], ...]
        ) -> bool:
            if len(subset) > 6:
                return False
            counts = {key: 0 for key in production_capacities}
            counts[capacity_class(primary)] += 1
            identities = [tuple(primary["semantic_identity"])]
            for row in subset:
                key = capacity_class(row)
                if counts.get(key, 0) >= production_capacities.get(key, 0):
                    return False
                identity = tuple(row["semantic_identity"])
                if parallel_admission_module.parallel_identity_conflict_reason(
                    identity, identities
                ):
                    return False
                counts[key] = counts.get(key, 0) + 1
                identities.append(identity)
            return True

        production_exact = max(
            objective(subset)
            for size in range(7)
            for subset in itertools.combinations(production_candidates, size)
            if production_feasible(subset)
        )
        production_metadata: dict[int, dict[str, object]] = {}
        for policy_version in (17, 18):
            metadata = {}
            parallel_admission_module.parallel_admission_outcomes(
                [primary, *production_candidates],
                total_capacity=7,
                class_capacities=production_capacities,
                aggregate_budget_enforced=False,
                policy_version=policy_version,
                search_metadata_out=metadata,
            )
            production_metadata[policy_version] = metadata

        self.assertEqual((30, 2_300, 5, 0), production_exact)
        self.assertEqual(
            list(production_exact), production_metadata[17]["objective_value"]
        )
        self.assertEqual(
            [36, 1_500, 6, 0],
            production_metadata[17]["upper_bound_objective_value"],
        )
        self.assertFalse(production_metadata[17]["optimality_certified"])
        production_current = production_metadata[18]
        self.assertEqual(list(production_exact), production_current["objective_value"])
        self.assertEqual(
            production_current["objective_value"],
            production_current["upper_bound_objective_value"],
        )
        self.assertTrue(production_current["optimality_certified"])
        self.assertEqual("exact", production_current["optimality"])
        self.assertEqual(
            "exact_suffix_conflict_neighborhood",
            production_current["future_equivalence_basis"],
        )
        self.assertGreater(
            production_current["states_merged_by_future_equivalence"], 0
        )

        tie_specifications = (
            (
                "integration",
                "t1",
                "r0",
                0,
                "parallel:000000000000000000096fa5",
            ),
            (
                "integration",
                "t3",
                "r3",
                0,
                "parallel:00000000000000000002293f",
            ),
            (
                "adversarial",
                "t2",
                "r1",
                0,
                "parallel:0000000000000000000103c9",
            ),
            (
                "research",
                "t0",
                "r4",
                0,
                "parallel:00000000000000000008481e",
            ),
            (
                "research",
                "t4",
                "r4",
                0,
                "parallel:000000000000000000050279",
            ),
        )
        tie_candidates = []
        for index, (*specification, candidate_id) in enumerate(tie_specifications):
            candidate = descriptor(index + 40_000, *specification)
            candidate["candidate_id"] = candidate_id
            tie_candidates.append(candidate)
        tie_candidates.sort(
            key=parallel_admission_module.parallel_admission_order_key
        )
        feasible_tie_subsets = [
            subset
            for size in range(7)
            for subset in itertools.combinations(tie_candidates, size)
            if production_feasible(subset)
        ]
        tie_exact = max(objective(subset) for subset in feasible_tie_subsets)
        canonical_tie_ids = min(
            tuple(str(row["candidate_id"]) for row in subset)
            for subset in feasible_tie_subsets
            if objective(subset) == tie_exact
        )
        tie_metadata: dict[int, dict[str, object]] = {}
        for policy_version in (18, 19, 20, 21, 22, 23, 24, 25):
            metadata = {}
            parallel_admission_module.parallel_admission_outcomes(
                [primary, *tie_candidates],
                total_capacity=7,
                class_capacities=production_capacities,
                aggregate_budget_enforced=False,
                policy_version=policy_version,
                search_metadata_out=metadata,
            )
            tie_metadata[policy_version] = metadata

        self.assertEqual((0, 1_500, 4, 0), tie_exact)
        self.assertEqual(list(tie_exact), tie_metadata[18]["objective_value"])
        self.assertTrue(tie_metadata[18]["optimality_certified"])
        self.assertNotEqual(
            list(canonical_tie_ids), tie_metadata[18]["selected_companion_ids"]
        )
        self.assertEqual(
            list(canonical_tie_ids), tie_metadata[19]["selected_companion_ids"]
        )
        self.assertEqual(11, tie_metadata[19]["version"])
        self.assertTrue(tie_metadata[19]["optimality_certified"])
        self.assertTrue(tie_metadata[19]["canonical_selection_certified"])
        self.assertEqual(
            "lexicographically_minimum_selected_candidate_ids",
            tie_metadata[19]["canonical_tie_break"],
        )
        self.assertEqual(
            list(canonical_tie_ids), tie_metadata[20]["selected_companion_ids"]
        )
        self.assertEqual(12, tie_metadata[20]["version"])
        self.assertTrue(tie_metadata[20]["optimality_certified"])
        self.assertTrue(tie_metadata[20]["canonical_selection_certified"])
        self.assertEqual(
            "lexicographically_minimum_suffix_subsequence_at_objective_cardinality",
            tie_metadata[20]["canonical_lower_bound"],
        )
        self.assertEqual(
            list(canonical_tie_ids), tie_metadata[21]["selected_companion_ids"]
        )
        self.assertEqual(13, tie_metadata[21]["version"])
        self.assertTrue(tie_metadata[21]["optimality_certified"])
        self.assertTrue(tie_metadata[21]["canonical_selection_certified"])
        self.assertTrue(tie_metadata[21]["state_dominance_applied"])
        self.assertEqual(
            list(canonical_tie_ids), tie_metadata[22]["selected_companion_ids"]
        )
        self.assertEqual(14, tie_metadata[22]["version"])
        self.assertTrue(tie_metadata[22]["optimality_certified"])
        self.assertTrue(tie_metadata[22]["canonical_selection_certified"])
        self.assertEqual("not_needed", tie_metadata[22]["anytime_completion_status"])
        self.assertEqual(
            list(canonical_tie_ids), tie_metadata[23]["selected_companion_ids"]
        )
        self.assertEqual(15, tie_metadata[23]["version"])
        self.assertEqual(len(tie_candidates), tie_metadata[23]["search_candidate_count"])
        self.assertEqual(
            list(canonical_tie_ids), tie_metadata[24]["selected_companion_ids"]
        )
        self.assertEqual(16, tie_metadata[24]["version"])
        self.assertEqual(
            list(canonical_tie_ids), tie_metadata[25]["selected_companion_ids"]
        )
        self.assertEqual(17, tie_metadata[25]["version"])
        oversized_capacity_metadata: dict[str, object] = {}
        parallel_admission_module.parallel_admission_outcomes(
            [primary, *tie_candidates],
            total_capacity=10_000,
            class_capacities=production_capacities,
            aggregate_budget_enforced=False,
            policy_version=21,
            search_metadata_out=oversized_capacity_metadata,
        )
        self.assertEqual(
            len(tie_candidates),
            oversized_capacity_metadata["canonical_suffix_cardinality_limit"],
        )
        truncated_tie_metadata: dict[str, object] = {}
        with mock.patch.object(
            parallel_admission_module,
            "PARALLEL_ADMISSION_NEIGHBORHOOD_SEARCH_BEAM_WIDTH",
            1,
        ):
            parallel_admission_module.parallel_admission_outcomes(
                [primary, *tie_candidates],
                total_capacity=7,
                class_capacities=production_capacities,
                aggregate_budget_enforced=False,
                policy_version=19,
                search_metadata_out=truncated_tie_metadata,
            )
        self.assertTrue(truncated_tie_metadata["pruned"])
        self.assertFalse(truncated_tie_metadata["canonical_selection_certified"])
        suffix_bounded_tie_metadata: dict[str, object] = {}
        with mock.patch.object(
            parallel_admission_module,
            "PARALLEL_ADMISSION_NEIGHBORHOOD_SEARCH_BEAM_WIDTH",
            1,
        ):
            parallel_admission_module.parallel_admission_outcomes(
                [primary, *tie_candidates],
                total_capacity=7,
                class_capacities=production_capacities,
                aggregate_budget_enforced=False,
                policy_version=21,
                search_metadata_out=suffix_bounded_tie_metadata,
            )
        self.assertTrue(suffix_bounded_tie_metadata["pruned"])
        self.assertEqual(
            list(canonical_tie_ids),
            suffix_bounded_tie_metadata["selected_companion_ids"],
        )
        self.assertTrue(
            suffix_bounded_tie_metadata["canonical_selection_certified"]
        )

    def test_parallel_v21_dominance_closes_a_bounded_certificate_gap(self) -> None:
        modes = {
            "advisory": "triage_routes",
            "research": "reduce",
            "adversarial": "refute",
            "verification": "prove",
            "integration": "integrate",
            "literature": "retrieve",
        }
        specifications = (
            ("integration", "t1", "r6", 5, "5fd"),
            ("integration", "t5", "r3", 5, "5fb"),
            ("adversarial", "t0", "r0", 5, "5f8"),
            ("research", "t2", "r0", 5, "5f3"),
            ("research", "t6", "r7", 5, "5ff"),
            ("integration", "t3", "r6", 3, "5f9"),
            ("literature", "t1", "r3", 3, "5f2"),
            ("research", "t0", "r0", 3, "600"),
            ("research", "t5", "r7", 3, "5f6"),
            ("research", "t6", "r6", 3, "5f1"),
            ("integration", "t4", "r5", 0, "5fe"),
            ("integration", "t6", "r6", 0, "5f4"),
            ("integration", "t7", "r4", 0, "5fc"),
            ("verification", "t4", "r1", 0, "5f7"),
            ("literature", "t0", "r3", 0, "5f5"),
            ("research", "t5", "r2", 0, "5fa"),
        )

        def descriptor(
            action_class: str,
            target_id: str,
            route_id: str,
            deferrals: int,
            identifier: str,
        ) -> dict[str, object]:
            semantic_identity = (
                action_class,
                modes[action_class],
                target_id,
                route_id,
                "dominance_probe",
                "",
                "{}",
                identifier.zfill(64),
            )
            return {
                "candidate_id": f"parallel:{identifier.zfill(24)}",
                "admission_priority": (
                    parallel_admission_module.parallel_admission_priority_for(
                        action_class, "dominance_probe"
                    )
                ),
                "action_class": action_class,
                "mode": modes[action_class],
                "target_id": target_id,
                "route_id": route_id,
                "search_intent": "dominance_probe",
                "semantic_identity": list(semantic_identity),
                "consecutive_deferrals": deferrals,
                "deferral_limit": 3,
                "budget_allowed": True,
                "requested_tokens": 0,
                "comparison_action_sha256": identifier.zfill(64),
            }

        primary = descriptor("advisory", "primary", "", 0, "0")
        primary.update(
            candidate_id="parallel:primary",
            admission_priority=1_000_000,
            deferral_limit=0,
        )
        candidates = [descriptor(*specification) for specification in specifications]
        candidates.sort(key=parallel_admission_module.parallel_admission_order_key)
        capacities = {
            "research_or_adversarial": 5,
            "verification": 5,
            "integration": 5,
            "literature": 2,
            "advisory": 1,
        }

        def capacity_class(row: dict[str, object]) -> str:
            return (
                "research_or_adversarial"
                if row["action_class"] in {"research", "adversarial"}
                else str(row["action_class"])
            )

        def feasible(subset: tuple[dict[str, object], ...]) -> bool:
            if len(subset) > 6:
                return False
            counts = {key: 0 for key in capacities}
            counts[capacity_class(primary)] += 1
            identities = [tuple(primary["semantic_identity"])]
            for row in subset:
                key = capacity_class(row)
                if counts[key] >= capacities[key]:
                    return False
                identity = tuple(row["semantic_identity"])
                if parallel_admission_module.parallel_identity_conflict_reason(
                    identity, identities
                ):
                    return False
                counts[key] += 1
                identities.append(identity)
            return True

        def objective(
            subset: tuple[dict[str, object], ...]
        ) -> tuple[int, int, int, int]:
            return (
                sum(
                    int(row["consecutive_deferrals"]) + 1
                    for row in subset
                    if int(row["consecutive_deferrals"])
                    >= int(row["deferral_limit"])
                ),
                sum(int(row["admission_priority"]) for row in subset),
                len(subset),
                0,
            )

        feasible_subsets = [
            subset
            for size in range(7)
            for subset in itertools.combinations(candidates, size)
            if feasible(subset)
        ]
        exact_objective = max(map(objective, feasible_subsets))
        canonical_ids = min(
            tuple(str(row["candidate_id"]) for row in subset)
            for subset in feasible_subsets
            if objective(subset) == exact_objective
        )
        metadata_by_version: dict[int, dict[str, object]] = {}
        outcomes_by_version = {}
        with mock.patch.object(
            parallel_admission_module,
            "PARALLEL_ADMISSION_NEIGHBORHOOD_SEARCH_BEAM_WIDTH",
            4,
        ):
            for policy_version in (20, 21):
                metadata: dict[str, object] = {}
                outcomes, _remaining = (
                    parallel_admission_module.parallel_admission_outcomes(
                        [primary, *candidates],
                        total_capacity=7,
                        class_capacities=capacities,
                        aggregate_budget_enforced=False,
                        policy_version=policy_version,
                        search_metadata_out=metadata,
                    )
                )
                metadata_by_version[policy_version] = metadata
                outcomes_by_version[policy_version] = outcomes

        self.assertEqual((30, 2_200, 6, 0), exact_objective)
        self.assertEqual(
            list(exact_objective), metadata_by_version[20]["objective_value"]
        )
        self.assertEqual(
            [32, 1_500, 6, 0],
            metadata_by_version[20]["upper_bound_objective_value"],
        )
        self.assertFalse(metadata_by_version[20]["optimality_certified"])
        current = metadata_by_version[21]
        self.assertEqual(list(exact_objective), current["objective_value"])
        self.assertEqual(current["objective_value"], current["upper_bound_objective_value"])
        self.assertTrue(current["optimality_certified"])
        self.assertTrue(current["canonical_selection_certified"])
        self.assertTrue(current["state_dominance_applied"])
        self.assertGreater(current["states_pruned_by_dominance"], 0)
        selected_ids = tuple(
            str(row["candidate_id"])
            for row in candidates
            if outcomes_by_version[21][str(row["candidate_id"])].disposition
            == "selected"
        )
        self.assertEqual(canonical_ids, selected_ids)

        capped_candidates = [
            descriptor(
                "literature",
                f"capped-target-{index}",
                f"capped-route-{index}",
                0,
                f"{0x1000 + index:x}",
            )
            for index in range(40)
        ]
        capped_candidates.sort(
            key=parallel_admission_module.parallel_admission_order_key
        )
        capped_metadata: dict[str, object] = {}
        parallel_admission_module.parallel_admission_outcomes(
            [primary, *capped_candidates],
            total_capacity=10_000,
            class_capacities={key: 10_000 for key in capacities},
            aggregate_budget_enforced=False,
            policy_version=21,
            search_metadata_out=capped_metadata,
        )
        self.assertEqual(
            parallel_admission_module.PARALLEL_ADMISSION_CANONICAL_SUFFIX_MAX_CARDINALITY,
            capped_metadata["canonical_suffix_cardinality_limit"],
        )
        self.assertFalse(capped_metadata["canonical_suffix_cardinality_complete"])

    def test_parallel_v22_v24_v25_completion_improves_a_truncated_wave(self) -> None:
        modes = {
            "advisory": "triage_routes",
            "research": "reduce",
            "adversarial": "refute",
            "verification": "prove",
            "integration": "integrate",
            "literature": "retrieve",
        }
        specifications = (
            ("literature", "t0", "r5", 5, 800, "5b"),
            ("literature", "t1", "r3", 5, 600, "58"),
            ("research", "t6", "r3", 5, 500, "55"),
            ("verification", "t3", "r2", 3, 1_000, "59"),
            ("literature", "t2", "r7", 3, 700, "5e"),
            ("integration", "t4", "r4", 3, 600, "57"),
            ("research", "t2", "r5", 3, 500, "60"),
            ("adversarial", "t3", "r0", 3, 0, "5f"),
            ("adversarial", "t0", "r7", 0, 800, "5c"),
            ("integration", "t0", "r7", 0, 800, "52"),
            ("research", "t0", "r7", 0, 800, "5d"),
            ("research", "t6", "r0", 0, 800, "5a"),
            ("research", "t6", "r3", 0, 400, "56"),
            ("literature", "t3", "r0", 0, 300, "51"),
            ("research", "t7", "r4", 0, 100, "54"),
            ("verification", "t1", "r2", 0, 0, "53"),
        )

        def descriptor(
            action_class: str,
            target_id: str,
            route_id: str,
            deferrals: int,
            priority: int,
            identifier: str,
        ) -> dict[str, object]:
            identity = (
                action_class,
                modes[action_class],
                target_id,
                route_id,
                "anytime_completion_probe",
                "",
                "{}",
                identifier.zfill(64),
            )
            return {
                "candidate_id": f"parallel:{identifier.zfill(24)}",
                "admission_priority": priority,
                "action_class": action_class,
                "mode": modes[action_class],
                "target_id": target_id,
                "route_id": route_id,
                "search_intent": "anytime_completion_probe",
                "semantic_identity": list(identity),
                "consecutive_deferrals": deferrals,
                "deferral_limit": 3,
                "budget_allowed": True,
                "requested_tokens": 0,
                "comparison_action_sha256": identifier.zfill(64),
            }

        primary = descriptor("advisory", "primary", "", 0, 1_000_000, "0")
        primary.update(candidate_id="parallel:primary", deferral_limit=0)
        candidates = [descriptor(*specification) for specification in specifications]
        candidates.sort(key=parallel_admission_module.parallel_admission_order_key)
        capacities = {
            "research_or_adversarial": 5,
            "verification": 5,
            "integration": 5,
            "literature": 2,
            "advisory": 1,
        }

        def capacity_class(row: dict[str, object]) -> str:
            return (
                "research_or_adversarial"
                if row["action_class"] in {"research", "adversarial"}
                else str(row["action_class"])
            )

        def feasible(subset: tuple[dict[str, object], ...]) -> bool:
            if len(subset) > 6:
                return False
            counts = {key: 0 for key in capacities}
            counts[capacity_class(primary)] += 1
            identities = [tuple(primary["semantic_identity"])]
            for row in subset:
                key = capacity_class(row)
                if counts[key] >= capacities[key]:
                    return False
                identity = tuple(row["semantic_identity"])
                if parallel_admission_module.parallel_identity_conflict_reason(
                    identity, identities
                ):
                    return False
                counts[key] += 1
                identities.append(identity)
            return True

        def objective(
            subset: tuple[dict[str, object], ...]
        ) -> tuple[int, int, int, int]:
            return (
                sum(
                    int(row["consecutive_deferrals"]) + 1
                    for row in subset
                    if int(row["consecutive_deferrals"])
                    >= int(row["deferral_limit"])
                ),
                sum(int(row["admission_priority"]) for row in subset),
                len(subset),
                0,
            )

        feasible_subsets = [
            subset
            for size in range(7)
            for subset in itertools.combinations(candidates, size)
            if feasible(subset)
        ]
        exact_objective = max(map(objective, feasible_subsets))
        canonical_ids = min(
            tuple(str(row["candidate_id"]) for row in subset)
            for subset in feasible_subsets
            if objective(subset) == exact_objective
        )
        metadata_by_version: dict[int, dict[str, object]] = {}
        outcomes_by_version = {}
        with mock.patch.object(
            parallel_admission_module,
            "PARALLEL_ADMISSION_NEIGHBORHOOD_SEARCH_BEAM_WIDTH",
            1,
        ):
            for policy_version in (21, 22, 24, 25):
                metadata: dict[str, object] = {}
                outcomes, _remaining = (
                    parallel_admission_module.parallel_admission_outcomes(
                        [primary, *candidates],
                        total_capacity=7,
                        class_capacities=capacities,
                        aggregate_budget_enforced=False,
                        policy_version=policy_version,
                        search_metadata_out=metadata,
                    )
                )
                metadata_by_version[policy_version] = metadata
                outcomes_by_version[policy_version] = outcomes

        self.assertEqual((30, 3_000, 6, 0), exact_objective)
        self.assertEqual([26, 4_200, 6, 0], metadata_by_version[21]["objective_value"])
        self.assertEqual(
            [30, 3_000, 6, 0], metadata_by_version[21]["upper_bound_objective_value"]
        )
        self.assertFalse(metadata_by_version[21]["optimality_certified"])
        current = metadata_by_version[22]
        self.assertEqual(list(exact_objective), current["objective_value"])
        self.assertEqual(current["objective_value"], current["upper_bound_objective_value"])
        self.assertEqual([26, 4_200, 6, 0], current["beam_objective_value"])
        self.assertEqual([30, 3_000, 6, 0], current["beam_upper_bound_objective_value"])
        self.assertEqual("exact", current["anytime_completion_status"])
        self.assertTrue(current["anytime_completion_triggered"])
        self.assertTrue(current["anytime_improved_selection"])
        self.assertGreater(current["anytime_states_expanded"], 0)
        self.assertEqual(0, current["anytime_frontier_size"])
        self.assertTrue(current["optimality_certified"])
        self.assertTrue(current["canonical_selection_certified"])
        selected_ids = tuple(
            str(row["candidate_id"])
            for row in candidates
            if outcomes_by_version[22][str(row["candidate_id"])].disposition
            == "selected"
        )
        self.assertEqual(canonical_ids, selected_ids)

        frontier_completion = metadata_by_version[24]
        self.assertEqual(16, frontier_completion["version"])
        self.assertEqual(list(exact_objective), frontier_completion["objective_value"])
        self.assertTrue(frontier_completion["optimality_certified"])
        self.assertTrue(frontier_completion["canonical_selection_certified"])
        self.assertEqual(
            "pruned_beam_frontier",
            frontier_completion["anytime_completion_frontier_source"],
        )
        self.assertGreater(
            frontier_completion["beam_discarded_frontier_size"], 0
        )
        self.assertEqual(5, frontier_completion["beam_discarded_frontier_size"])
        self.assertEqual(6, frontier_completion["anytime_states_expanded"])
        self.assertLess(
            frontier_completion["anytime_states_expanded"],
            current["anytime_states_expanded"],
        )
        bounded_frontier = metadata_by_version[25]
        self.assertEqual(17, bounded_frontier["version"])
        self.assertEqual(
            frontier_completion["objective_value"],
            bounded_frontier["objective_value"],
        )
        self.assertEqual(
            frontier_completion["anytime_states_expanded"],
            bounded_frontier["anytime_states_expanded"],
        )
        self.assertEqual(
            bounded_frontier["beam_discarded_frontier_size"],
            bounded_frontier["beam_discarded_frontier_state_count"],
        )
        self.assertEqual(
            parallel_admission_module.PARALLEL_ADMISSION_COMPLETION_FRONTIER_STATE_LIMIT,
            bounded_frontier["beam_discarded_frontier_state_limit"],
        )
        self.assertFalse(
            bounded_frontier["beam_discarded_frontier_limit_reached"]
        )

        bounded_metadata: dict[str, object] = {}
        with (
            mock.patch.object(
                parallel_admission_module,
                "PARALLEL_ADMISSION_NEIGHBORHOOD_SEARCH_BEAM_WIDTH",
                1,
            ),
            mock.patch.object(
                parallel_admission_module,
                "PARALLEL_ADMISSION_ANYTIME_STATE_LIMIT",
                1,
            ),
        ):
            parallel_admission_module.parallel_admission_outcomes(
                [primary, *candidates],
                total_capacity=7,
                class_capacities=capacities,
                aggregate_budget_enforced=False,
                policy_version=22,
                search_metadata_out=bounded_metadata,
            )
        self.assertEqual("state_limit_reached", bounded_metadata["anytime_completion_status"])
        self.assertEqual(1, bounded_metadata["anytime_states_expanded"])
        self.assertGreater(bounded_metadata["anytime_frontier_size"], 0)
        self.assertLessEqual(
            exact_objective,
            tuple(bounded_metadata["upper_bound_objective_value"]),
        )
        if bounded_metadata["optimality_certified"]:
            self.assertEqual(
                exact_objective, tuple(bounded_metadata["objective_value"])
            )

        bounded_by_version: dict[int, dict[str, object]] = {}
        with (
            mock.patch.object(
                parallel_admission_module,
                "PARALLEL_ADMISSION_NEIGHBORHOOD_SEARCH_BEAM_WIDTH",
                1,
            ),
            mock.patch.object(
                parallel_admission_module,
                "PARALLEL_ADMISSION_ANYTIME_STATE_LIMIT",
                6,
            ),
        ):
            for policy_version in (23, 24, 25):
                metadata = {}
                parallel_admission_module.parallel_admission_outcomes(
                    [primary, *candidates],
                    total_capacity=7,
                    class_capacities=capacities,
                    aggregate_budget_enforced=False,
                    policy_version=policy_version,
                    search_metadata_out=metadata,
                )
                bounded_by_version[policy_version] = metadata
        self.assertEqual(
            "state_limit_reached",
            bounded_by_version[23]["anytime_completion_status"],
        )
        self.assertFalse(bounded_by_version[23]["optimality_certified"])
        self.assertEqual(
            "exact", bounded_by_version[24]["anytime_completion_status"]
        )
        self.assertTrue(bounded_by_version[24]["optimality_certified"])
        self.assertEqual(
            "exact", bounded_by_version[25]["anytime_completion_status"]
        )
        self.assertTrue(bounded_by_version[25]["optimality_certified"])

        overflow_metadata: dict[str, object] = {}
        with (
            mock.patch.object(
                parallel_admission_module,
                "PARALLEL_ADMISSION_NEIGHBORHOOD_SEARCH_BEAM_WIDTH",
                1,
            ),
            mock.patch.object(
                parallel_admission_module,
                "PARALLEL_ADMISSION_COMPLETION_FRONTIER_STATE_LIMIT",
                1,
            ),
        ):
            parallel_admission_module.parallel_admission_outcomes(
                [primary, *candidates],
                total_capacity=7,
                class_capacities=capacities,
                aggregate_budget_enforced=False,
                policy_version=25,
                search_metadata_out=overflow_metadata,
            )
        self.assertTrue(
            overflow_metadata["beam_discarded_frontier_limit_reached"]
        )
        self.assertGreater(
            overflow_metadata["beam_discarded_frontier_state_count"], 1
        )
        self.assertEqual(0, overflow_metadata["beam_discarded_frontier_size"])
        self.assertEqual(
            "root_restart_after_frontier_limit",
            overflow_metadata["anytime_completion_frontier_source"],
        )
        self.assertTrue(overflow_metadata["optimality_certified"])

    def test_parallel_v23_excludes_intrinsically_infeasible_search_states(self) -> None:
        modes = {
            "advisory": "triage_routes",
            "research": "reduce",
            "verification": "prove",
        }

        def descriptor(
            index: int,
            action_class: str,
            *,
            budget_allowed: bool = True,
            requested_tokens: int = 0,
        ) -> dict[str, object]:
            nonce = f"{index + 1:064x}"
            identity = (
                action_class,
                modes[action_class],
                f"intrinsic-target-{index}",
                f"intrinsic-route-{index}",
                "intrinsic_filter_probe",
                "",
                "{}",
                nonce,
            )
            return {
                "candidate_id": f"parallel:{index + 1:024x}",
                "admission_priority": 1_000_000 if index < 0 else 100 + index,
                "action_class": action_class,
                "mode": modes[action_class],
                "target_id": identity[2],
                "route_id": identity[3],
                "search_intent": "intrinsic_filter_probe",
                "semantic_identity": list(identity),
                "consecutive_deferrals": 0,
                "deferral_limit": 0 if index < 0 else 3,
                "budget_allowed": budget_allowed,
                "requested_tokens": requested_tokens,
                "comparison_action_sha256": nonce,
            }

        primary = descriptor(-1, "advisory")
        primary["candidate_id"] = "parallel:primary"
        eligible = [descriptor(index, "research") for index in range(16)]
        unauthorized = [
            descriptor(1_000 + index, "research", budget_allowed=False)
            for index in range(150)
        ]
        primary_conflict = descriptor(2_000, "research")
        primary_conflict["semantic_identity"] = list(primary["semantic_identity"])
        primary_conflict.update(
            action_class="advisory",
            mode="triage_routes",
            target_id=primary["target_id"],
            route_id=primary["route_id"],
        )
        full_class = descriptor(2_001, "advisory")
        subminimum = descriptor(2_002, "research", requested_tokens=5_000)
        unavailable_shared = descriptor(
            2_003, "research", requested_tokens=10_000
        )
        infeasible = [
            *unauthorized,
            primary_conflict,
            full_class,
            subminimum,
            unavailable_shared,
        ]
        capacities = {
            "research_or_adversarial": 20,
            "verification": 5,
            "integration": 5,
            "literature": 5,
            "advisory": 1,
        }

        def run(candidate_rows: list[dict[str, object]], version: int):
            metadata: dict[str, object] = {}
            outcomes, remaining = (
                parallel_admission_module.parallel_admission_outcomes(
                    [primary, *candidate_rows],
                    total_capacity=7,
                    class_capacities=capacities,
                    aggregate_budget_enforced=True,
                    initial_remaining_token_budget=10_000,
                    initial_reserved_verification_budget=10_000,
                    policy_version=version,
                    search_metadata_out=metadata,
                )
            )
            return outcomes, remaining, metadata

        base_outcomes, base_remaining, base_metadata = run(eligible, 23)
        padded_rows = [*infeasible[:75], *eligible, *infeasible[75:]]
        outcomes, remaining, metadata = run(padded_rows, 23)
        self.assertEqual(base_remaining, remaining)
        self.assertEqual(base_metadata["objective_value"], metadata["objective_value"])
        self.assertEqual(
            base_metadata["upper_bound_objective_value"],
            metadata["upper_bound_objective_value"],
        )
        self.assertEqual(base_metadata["states_expanded"], metadata["states_expanded"])
        self.assertEqual(base_metadata["beam_width"], metadata["beam_width"])
        self.assertEqual(128, metadata["beam_width"])
        self.assertEqual(len(padded_rows), metadata["candidate_count"])
        self.assertEqual(len(eligible), metadata["search_candidate_count"])
        self.assertEqual(
            len(infeasible), metadata["intrinsically_infeasible_candidate_count"]
        )
        self.assertEqual(
            [
                candidate_id
                for candidate_id, outcome in base_outcomes.items()
                if outcome.disposition == "selected"
            ],
            [
                candidate_id
                for candidate_id, outcome in outcomes.items()
                if outcome.disposition == "selected"
            ],
        )
        self.assertEqual(len(padded_rows) + 1, len(outcomes))
        for row in infeasible:
            self.assertEqual(
                "rejected", outcomes[str(row["candidate_id"])].disposition
            )

        _historical_outcomes, _historical_remaining, historical_metadata = run(
            padded_rows, 22
        )
        self.assertEqual(len(padded_rows), historical_metadata["candidate_count"])
        self.assertNotIn("search_candidate_count", historical_metadata)

    def test_dense_parallel_benchmark_hard_gates_exact_certificate(self) -> None:
        metric = scheduler_benchmark_module._dense_parallel_search_benchmark(
            iterations=1,
            warmup=0,
            candidate_count=40,
        )

        self.assertEqual([], metric["certificate_errors"])
        self.assertEqual(
            [], scheduler_benchmark_module._dense_parallel_certificate_errors(metric)
        )
        resource_metric = (
            scheduler_benchmark_module._dense_parallel_search_benchmark(
                iterations=1,
                warmup=0,
                candidate_count=40,
                resource_constrained=True,
            )
        )
        self.assertEqual([], resource_metric["certificate_errors"])
        self.assertEqual(
            resource_metric["search_evidence"]["objective_value"],
            resource_metric["search_evidence"]["upper_bound_objective_value"],
        )
        clique_metric = scheduler_benchmark_module._dense_parallel_search_benchmark(
            iterations=1,
            warmup=0,
            candidate_count=100,
            sibling_clique=True,
        )
        self.assertEqual([], clique_metric["certificate_errors"])
        self.assertEqual(
            [4, 100, 1, 0], clique_metric["search_evidence"]["objective_value"]
        )
        self.assertEqual(
            clique_metric["search_evidence"]["objective_value"],
            clique_metric["search_evidence"]["upper_bound_objective_value"],
        )
        equivalence_metric = (
            scheduler_benchmark_module._dense_parallel_search_benchmark(
                iterations=1,
                warmup=0,
                candidate_count=48,
                equivalent_conflicts=True,
            )
        )
        self.assertEqual([], equivalence_metric["certificate_errors"])
        equivalence_evidence = equivalence_metric["search_evidence"]
        self.assertEqual([24, 1_000, 4, 0], equivalence_evidence["objective_value"])
        self.assertEqual(
            equivalence_evidence["objective_value"],
            equivalence_evidence["upper_bound_objective_value"],
        )
        self.assertTrue(equivalence_evidence["future_equivalence_quotient_applied"])
        self.assertGreater(
            equivalence_evidence["states_merged_by_future_equivalence"], 0
        )
        neighborhood_metric = (
            scheduler_benchmark_module._dense_parallel_search_benchmark(
                iterations=1,
                warmup=0,
                candidate_count=12,
                suffix_neighborhood_conflicts=True,
            )
        )
        self.assertEqual([], neighborhood_metric["certificate_errors"])
        neighborhood_evidence = neighborhood_metric["search_evidence"]
        self.assertEqual([30, 2_300, 5, 0], neighborhood_evidence["objective_value"])
        self.assertEqual(
            neighborhood_evidence["objective_value"],
            neighborhood_evidence["upper_bound_objective_value"],
        )
        self.assertEqual(
            "exact_suffix_conflict_neighborhood",
            neighborhood_evidence["future_equivalence_basis"],
        )
        self.assertEqual(
            "lexicographically_minimum_suffix_subsequence_at_objective_cardinality",
            neighborhood_evidence["canonical_lower_bound"],
        )
        self.assertTrue(neighborhood_evidence["canonical_selection_certified"])
        self.assertTrue(neighborhood_evidence["state_dominance_applied"])
        self.assertGreater(neighborhood_evidence["states_pruned_by_dominance"], 0)
        neighborhood_limit = getattr(
            parallel_admission_module,
            "PARALLEL_ADMISSION_NEIGHBORHOOD_QUOTIENT_MAX_CANDIDATES",
        )
        oversized_metric = scheduler_benchmark_module._dense_parallel_search_benchmark(
            iterations=1,
            warmup=0,
            candidate_count=neighborhood_limit + 1,
        )
        self.assertEqual([], oversized_metric["certificate_errors"])
        self.assertEqual(
            "disabled",
            oversized_metric["search_evidence"]["future_equivalence_basis"],
        )
        self.assertFalse(
            oversized_metric["search_evidence"][
                "future_equivalence_quotient_applied"
            ]
        )
        for field, forged_value, expected_error in (
            (
                "optimality_certified",
                False,
                "dense parallel-search optimum is not certified",
            ),
            (
                "optimality",
                "bounded_approximation",
                "dense parallel-search optimality label is not exact",
            ),
            (
                "upper_bound_objective_value",
                [10**6, 10**6, 6, 0],
                "dense parallel-search objective does not meet its upper bound",
            ),
            (
                "canonical_selection_certified",
                "yes",
                "dense parallel-search canonicality flag is not boolean",
            ),
            (
                "canonical_lower_bound",
                "none",
                "dense parallel-search canonical lower-bound rule is invalid",
            ),
            (
                "states_pruned_by_canonical_bound",
                -1,
                "dense parallel-search canonical-bound prune count is not a nonnegative integer",
            ),
            (
                "canonical_suffix_cardinality_limit",
                10**6,
                "dense parallel-search canonical suffix limit is invalid",
            ),
            (
                "canonical_tie_break",
                "input_order",
                "dense parallel-search canonical tie rule is invalid",
            ),
            (
                "canonical_suffix_cardinality_cap",
                10**6,
                "dense parallel-search canonical suffix cap is invalid",
            ),
            (
                "canonical_suffix_cardinality_complete",
                False,
                "dense parallel-search canonical suffix table is incomplete",
            ),
            (
                "state_dominance",
                "heuristic",
                "dense parallel-search dominance rule is invalid",
            ),
            (
                "state_dominance_applied",
                "yes",
                "dense parallel-search dominance flag is not boolean",
            ),
            (
                "states_pruned_by_dominance",
                -1,
                "dense parallel-search dominance prune count is not a nonnegative integer",
            ),
            (
                "state_dominance_frontier_limit",
                10**6,
                "dense parallel-search dominance frontier limit is invalid",
            ),
            (
                "anytime_completion_triggered",
                "yes",
                "dense parallel-search anytime trigger is not boolean",
            ),
            (
                "anytime_completion_status",
                "complete",
                "dense parallel-search anytime status is invalid",
            ),
            (
                "anytime_state_limit",
                10**6,
                "dense parallel-search anytime state limit is invalid",
            ),
            (
                "anytime_states_expanded",
                -1,
                "dense parallel-search anytime expansion count is invalid",
            ),
            (
                "anytime_states_merged_by_future_equivalence",
                -1,
                "dense parallel-search anytime merge count is invalid",
            ),
            (
                "anytime_frontier_size",
                -1,
                "dense parallel-search anytime frontier size is invalid",
            ),
            (
                "anytime_improved_selection",
                "yes",
                "dense parallel-search anytime improvement flag is not boolean",
            ),
            (
                "beam_objective_value",
                [0],
                "dense parallel-search beam objective is invalid",
            ),
            (
                "beam_upper_bound_objective_value",
                [0],
                "dense parallel-search beam upper bound is invalid",
            ),
            (
                "search_candidate_count",
                10**6,
                "dense parallel-search searchable candidate count is invalid",
            ),
            (
                "intrinsically_infeasible_candidate_count",
                -1,
                "dense parallel-search infeasible candidate count is invalid",
            ),
            (
                "intrinsic_candidate_filter",
                "none",
                "dense parallel-search intrinsic candidate filter is invalid",
            ),
            (
                "anytime_completion_frontier_source",
                "root_restart",
                "dense parallel-search completion frontier source is invalid",
            ),
            (
                "beam_discarded_frontier_size",
                -1,
                "dense parallel-search discarded frontier size is invalid",
            ),
            (
                "beam_discarded_frontier_state_count",
                -1,
                "dense parallel-search discarded frontier count is invalid",
            ),
            (
                "beam_discarded_frontier_state_limit",
                -1,
                "dense parallel-search discarded frontier limit is invalid",
            ),
            (
                "beam_discarded_frontier_limit_reached",
                "yes",
                "dense parallel-search discarded frontier limit flag is invalid",
            ),
        ):
            forged = copy.deepcopy(metric)
            forged["search_evidence"][field] = forged_value
            self.assertIn(
                expected_error,
                scheduler_benchmark_module._dense_parallel_certificate_errors(forged),
            )
        forged_equivalence = copy.deepcopy(equivalence_metric)
        forged_equivalence["search_evidence"][
            "future_equivalence_quotient_applied"
        ] = False
        self.assertIn(
            "equivalent-conflict search did not apply its quotient",
            scheduler_benchmark_module._dense_parallel_certificate_errors(
                forged_equivalence
            ),
        )
        forged_neighborhood = copy.deepcopy(neighborhood_metric)
        forged_neighborhood["search_evidence"][
            "future_equivalence_basis"
        ] = "semantic_conflict_projection"
        self.assertIn(
            "suffix-neighborhood search used the wrong quotient basis",
            scheduler_benchmark_module._dense_parallel_certificate_errors(
                forged_neighborhood
            ),
        )
        forged_neighborhood = copy.deepcopy(neighborhood_metric)
        forged_neighborhood["search_evidence"][
            "canonical_selection_certified"
        ] = False
        self.assertIn(
            "dense parallel-search canonical selection is not certified",
            scheduler_benchmark_module._dense_parallel_certificate_errors(
                forged_neighborhood
            ),
        )
        contradictory = copy.deepcopy(neighborhood_metric)
        contradictory["search_evidence"][
            "discarded_upper_bound_objective_value"
        ] = list(contradictory["search_evidence"]["objective_value"])
        contradictory["search_evidence"][
            "discarded_canonical_lower_bound_candidate_ids"
        ] = []
        self.assertIn(
            "dense parallel-search discarded canonical bound beats selection",
            scheduler_benchmark_module._dense_parallel_certificate_errors(contradictory),
        )

    def test_parallel_v10_certifies_a_pruned_global_optimum(self) -> None:
        def descriptor(
            index: int, priority: int, *, primary: bool = False
        ) -> dict[str, object]:
            action_class = "advisory" if primary else "verification"
            action = {
                "mode": "triage_routes" if primary else "prove",
                "target_id": f"target-{index}",
                "route_id": f"route-{index}",
                "search_intent": "bound_certificate_probe",
                "proof_obligation_id": f"obligation-{index}",
            }
            identity = parallel_admission_module.parallel_action_identity(
                action, action_class=action_class, policy_version=10
            )
            return {
                "candidate_id": (
                    "parallel:primary"
                    if primary
                    else parallel_admission_module.parallel_candidate_id(
                        identity, policy_version=10
                    )
                ),
                "admission_priority": 1_000_000 if primary else priority,
                "action_class": action_class,
                **action,
                "semantic_identity": list(identity),
                "consecutive_deferrals": 0,
                "deferral_limit": 0 if primary else 3,
                "budget_allowed": True,
                "requested_tokens": 0,
                "comparison_action_sha256": f"{index % 16:x}" * 64,
            }

        rows = [
            descriptor(-1, 0, primary=True),
            *[descriptor(index, index + 1) for index in range(20)],
        ]
        metadata: dict[str, object] = {}
        outcomes, _remaining = (
            parallel_admission_module.parallel_admission_outcomes(
                rows,
                total_capacity=5,
                class_capacities={
                    "research_or_adversarial": 5,
                    "verification": 4,
                    "integration": 5,
                    "literature": 1,
                    "advisory": 1,
                },
                aggregate_budget_enforced=False,
                policy_version=10,
                search_metadata_out=metadata,
            )
        )
        selected_priority = sum(
            int(row["admission_priority"])
            for row in rows[1:]
            if outcomes[str(row["candidate_id"])].disposition == "selected"
        )
        self.assertTrue(metadata["pruned"])
        self.assertTrue(metadata["optimality_certified"])
        self.assertEqual(metadata["optimality"], "exact")
        self.assertEqual(metadata["upper_bound_objective_value"], [0, 74, 4, 0])
        self.assertEqual(metadata["objective_value"], [0, 74, 4, 0])
        self.assertEqual(selected_priority, 74)

    def test_parallel_v10_upper_bound_contains_exhaustive_optimum(self) -> None:
        rng = random.Random(10010)
        capacities = {
            "research_or_adversarial": 2,
            "verification": 2,
            "integration": 1,
            "literature": 1,
            "advisory": 1,
        }

        def descriptor(
            index: int, action_class: str, *, primary: bool = False
        ) -> dict[str, object]:
            action = {
                "mode": (
                    "triage_routes"
                    if primary
                    else "prove"
                    if action_class == "verification"
                    else "integrate"
                    if action_class == "integration"
                    else "reduce"
                ),
                "target_id": f"target-{rng.randrange(5)}",
                "route_id": f"route-{rng.randrange(5)}",
                "search_intent": "exhaustive_bound_probe",
                "proof_obligation_id": f"obligation-{index}",
            }
            identity = parallel_admission_module.parallel_action_identity(
                action, action_class=action_class, policy_version=10
            )
            return {
                "candidate_id": (
                    "parallel:primary"
                    if primary
                    else parallel_admission_module.parallel_candidate_id(
                        identity, policy_version=10
                    )
                ),
                "admission_priority": 1_000_000 if primary else rng.randrange(1, 50),
                "action_class": action_class,
                **action,
                "semantic_identity": list(identity),
                "consecutive_deferrals": 0 if primary else rng.choice((0, 0, 3, 5)),
                "deferral_limit": 0 if primary else 3,
                "budget_allowed": True,
                "requested_tokens": 0,
                "comparison_action_sha256": hashlib.sha256(
                    f"bound-{index}".encode("ascii")
                ).hexdigest(),
            }

        pruned_trials = 0
        approximate_trials = 0
        with mock.patch.object(
            parallel_admission_module,
            "PARALLEL_ADMISSION_SEARCH_BEAM_WIDTH",
            4,
        ):
            for trial in range(50):
                primary = descriptor(-trial - 1, "advisory", primary=True)
                candidates = [
                    descriptor(
                        trial * 10 + index,
                        rng.choice(("research", "verification", "integration")),
                    )
                    for index in range(10)
                ]

                def capacity_class(row: dict[str, object]) -> str:
                    return (
                        "research_or_adversarial"
                        if row["action_class"] in {"research", "adversarial"}
                        else str(row["action_class"])
                    )

                def feasible(subset: tuple[dict[str, object], ...]) -> bool:
                    if len(subset) > 3:
                        return False
                    counts = {key: 0 for key in capacities}
                    counts[capacity_class(primary)] += 1
                    admitted = [tuple(primary["semantic_identity"])]
                    for row in subset:
                        key = capacity_class(row)
                        if counts.get(key, 0) >= capacities.get(key, 0):
                            return False
                        identity = tuple(row["semantic_identity"])
                        if parallel_admission_module.parallel_identity_conflict_reason(
                            identity, admitted
                        ):
                            return False
                        counts[key] = counts.get(key, 0) + 1
                        admitted.append(identity)
                    return True

                def objective(
                    subset: tuple[dict[str, object], ...]
                ) -> tuple[int, int, int, int]:
                    return (
                        sum(
                            int(row["consecutive_deferrals"]) + 1
                            for row in subset
                            if int(row["consecutive_deferrals"])
                            >= int(row["deferral_limit"])
                        ),
                        sum(int(row["admission_priority"]) for row in subset),
                        len(subset),
                        0,
                    )

                exact = max(
                    objective(subset)
                    for size in range(4)
                    for subset in itertools.combinations(candidates, size)
                    if feasible(subset)
                )
                bounds_by_version: dict[int, tuple[int, int, int, int]] = {}
                for policy_version in (
                    10,
                    12,
                    13,
                    14,
                    15,
                    16,
                    17,
                    18,
                    19,
                    20,
                    21,
                    22,
                    23,
                    24,
                    25,
                ):
                    metadata: dict[str, object] = {}
                    outcomes, _remaining = (
                        parallel_admission_module.parallel_admission_outcomes(
                            [primary, *candidates],
                            total_capacity=4,
                            class_capacities=capacities,
                            aggregate_budget_enforced=False,
                            policy_version=policy_version,
                            search_metadata_out=metadata,
                        )
                    )
                    selected = tuple(
                        row
                        for row in candidates
                        if outcomes[str(row["candidate_id"])].disposition
                        == "selected"
                    )
                    selected_objective = objective(selected)
                    upper_bound = tuple(metadata["upper_bound_objective_value"])
                    bounds_by_version[policy_version] = upper_bound
                    self.assertLessEqual(selected_objective, exact)
                    self.assertLessEqual(exact, upper_bound)
                    if metadata["optimality_certified"]:
                        self.assertEqual(selected_objective, exact)
                    pruned_trials += int(bool(metadata["pruned"]))
                    approximate_trials += int(
                        metadata["optimality"] == "bounded_approximation"
                    )
                self.assertLessEqual(bounds_by_version[13], bounds_by_version[12])
                self.assertLessEqual(bounds_by_version[14], bounds_by_version[13])
                self.assertLessEqual(bounds_by_version[15], bounds_by_version[14])
                self.assertLessEqual(bounds_by_version[16], bounds_by_version[15])
                self.assertLessEqual(bounds_by_version[17], bounds_by_version[16])
                self.assertLessEqual(bounds_by_version[18], bounds_by_version[17])
                self.assertLessEqual(bounds_by_version[19], bounds_by_version[18])
                self.assertLessEqual(bounds_by_version[20], bounds_by_version[19])
                self.assertLessEqual(bounds_by_version[21], bounds_by_version[20])
                self.assertLessEqual(bounds_by_version[22], bounds_by_version[21])
                self.assertLessEqual(bounds_by_version[23], bounds_by_version[22])
                self.assertLessEqual(bounds_by_version[24], bounds_by_version[23])
                self.assertLessEqual(bounds_by_version[25], bounds_by_version[24])
        self.assertGreater(pruned_trials, 0)
        self.assertGreater(approximate_trials, 0)

    def test_parallel_v9_v17_through_v25_match_exhaustive_small_conflict_optima(
        self,
    ) -> None:
        rng = random.Random(90210)
        capacities = {
            "research_or_adversarial": 2,
            "verification": 2,
            "integration": 2,
            "literature": 1,
            "advisory": 1,
        }
        modes = {
            "research": "reduce",
            "adversarial": "refute",
            "verification": "prove",
            "integration": "integrate",
            "literature": "retrieve",
            "advisory": "triage_routes",
        }

        def descriptor(index: int, action_class: str, deferrals: int) -> dict[str, object]:
            action = {
                "mode": modes[action_class],
                "target_id": f"target-{rng.randrange(4)}",
                "route_id": f"route-{rng.randrange(4)}",
                "search_intent": "exhaustive_search_probe",
                "proof_obligation_id": f"obligation-{index}",
            }
            identity = parallel_admission_module.parallel_action_identity(
                action,
                action_class=action_class,
                policy_version=9,
            )
            return {
                "candidate_id": parallel_admission_module.parallel_candidate_id(
                    identity,
                    policy_version=9,
                ),
                "admission_priority": parallel_admission_module.parallel_admission_priority_for(
                    action_class,
                    "exhaustive_search_probe",
                ),
                "action_class": action_class,
                **action,
                "semantic_identity": list(identity),
                "consecutive_deferrals": deferrals,
                "deferral_limit": parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT,
                "budget_allowed": True,
                "requested_tokens": 0,
                "comparison_action_sha256": hashlib.sha256(
                    f"candidate-{index}".encode("ascii")
                ).hexdigest(),
            }

        for trial in range(100):
            primary = descriptor(-1, "advisory", 0)
            primary.update(
                candidate_id="parallel:primary",
                admission_priority=1_000_000,
                consecutive_deferrals=0,
                deferral_limit=0,
            )
            candidates = [
                descriptor(
                    trial * 6 + index,
                    rng.choice(tuple(modes)),
                    rng.choice((0, 0, 3, 4)),
                )
                for index in range(6)
            ]
            candidates.sort(
                key=lambda row: parallel_admission_module.parallel_admission_order_key(
                    row,
                    policy_version=9,
                )
            )
            def capacity_class(row: dict[str, object]) -> str:
                return (
                    "research_or_adversarial"
                    if row["action_class"] in {"research", "adversarial"}
                    else str(row["action_class"])
                )

            def feasible(subset: tuple[dict[str, object], ...]) -> bool:
                if len(subset) > 3:
                    return False
                counts = {key: 0 for key in capacities}
                counts[capacity_class(primary)] += 1
                admitted = [tuple(primary["semantic_identity"])]
                for row in subset:
                    key = capacity_class(row)
                    if counts.get(key, 0) >= capacities.get(key, 0):
                        return False
                    identity = tuple(row["semantic_identity"])
                    if parallel_admission_module.parallel_identity_conflict_reason(
                        identity,
                        admitted,
                    ):
                        return False
                    admitted.append(identity)
                    counts[key] = counts.get(key, 0) + 1
                return True

            def objective(subset: tuple[dict[str, object], ...]) -> tuple[int, int, int, int]:
                return (
                    sum(
                        int(row["consecutive_deferrals"]) + 1
                        for row in subset
                        if int(row["consecutive_deferrals"])
                        >= int(row["deferral_limit"])
                    ),
                    sum(int(row["admission_priority"]) for row in subset),
                    len(subset),
                    0,
                )

            feasible_subsets = [
                subset
                for size in range(4)
                for subset in itertools.combinations(candidates, size)
                if feasible(subset)
            ]
            exact_objective = max(map(objective, feasible_subsets))
            canonical_ids = min(
                tuple(str(row["candidate_id"]) for row in subset)
                for subset in feasible_subsets
                if objective(subset) == exact_objective
            )
            for policy_version in (9, 17, 18, 19, 20, 21, 22, 23, 24, 25):
                metadata: dict[str, object] = {}
                outcomes, _remaining = (
                    parallel_admission_module.parallel_admission_outcomes(
                        [primary, *candidates],
                        total_capacity=4,
                        class_capacities=capacities,
                        aggregate_budget_enforced=False,
                        policy_version=policy_version,
                        search_metadata_out=metadata,
                    )
                )
                selected = tuple(
                    row
                    for row in candidates
                    if outcomes[str(row["candidate_id"])].disposition == "selected"
                )
                self.assertEqual(
                    exact_objective,
                    objective(selected),
                    f"trial {trial}, policy {policy_version}",
                )
                self.assertEqual("exact", metadata["optimality"])
                if policy_version >= 19:
                    self.assertEqual(
                        canonical_ids,
                        tuple(str(row["candidate_id"]) for row in selected),
                    )
                    self.assertTrue(metadata["canonical_selection_certified"])

    def test_parallel_v9_never_regresses_below_v8_on_pruned_searches(self) -> None:
        rng = random.Random(77)
        action_classes = (
            "research",
            "adversarial",
            "verification",
            "integration",
            "literature",
        )
        modes = {
            "research": "reduce",
            "adversarial": "refute",
            "verification": "prove",
            "integration": "integrate",
            "literature": "retrieve",
        }
        capacities = {
            "research_or_adversarial": 5,
            "verification": 5,
            "integration": 5,
            "literature": 1,
            "advisory": 1,
        }

        def descriptor(index: int) -> dict[str, object]:
            action_class = rng.choice(action_classes)
            action = {
                "mode": modes[action_class],
                "target_id": f"target-{rng.randrange(20)}",
                "route_id": f"route-{rng.randrange(20)}",
                "search_intent": "greedy_lower_bound_probe",
                "proof_obligation_id": f"obligation-{index}",
            }
            identity = parallel_admission_module.parallel_action_identity(
                action, action_class=action_class, policy_version=9
            )
            return {
                "candidate_id": parallel_admission_module.parallel_candidate_id(
                    identity, policy_version=9
                ),
                "admission_priority": parallel_admission_module.parallel_admission_priority_for(
                    action_class, "greedy_lower_bound_probe"
                ),
                "action_class": action_class,
                **action,
                "semantic_identity": list(identity),
                "consecutive_deferrals": rng.choice((0, 0, 3, 4, 7)),
                "deferral_limit": parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT,
                "budget_allowed": True,
                "requested_tokens": 0,
                "comparison_action_sha256": hashlib.sha256(
                    f"large-{index}".encode("ascii")
                ).hexdigest(),
            }

        def objective(
            rows: list[dict[str, object]],
            outcomes: dict[str, object],
            remaining: int,
        ) -> tuple[int, int, int, int]:
            selected = [
                row
                for row in rows[1:]
                if outcomes[str(row["candidate_id"])].disposition
                == "selected"
            ]
            return (
                sum(
                    int(row["consecutive_deferrals"]) + 1
                    for row in selected
                    if int(row["consecutive_deferrals"])
                    >= int(row["deferral_limit"])
                ),
                sum(int(row["admission_priority"]) for row in selected),
                len(selected),
                remaining,
            )

        fallback_seen = False
        improvement_seen = False
        for trial in range(30):
            primary = descriptor(-trial - 1)
            primary.update(
                candidate_id="parallel:primary",
                action_class="advisory",
                mode="triage_routes",
                target_id="primary",
                route_id="",
                semantic_identity=[
                    "advisory",
                    "triage_routes",
                    "primary",
                    "",
                    "greedy_lower_bound_probe",
                    "",
                    "{}",
                    "0" * 64,
                ],
                admission_priority=1_000_000,
                consecutive_deferrals=0,
                deferral_limit=0,
            )
            candidates = [
                descriptor(trial * 100 + index) for index in range(100)
            ]
            candidates.sort(
                key=lambda row: parallel_admission_module.parallel_admission_order_key(
                    row, policy_version=9
                )
            )
            rows = [primary, *candidates]
            metadata: dict[str, object] = {}
            current, current_remaining = (
                parallel_admission_module.parallel_admission_outcomes(
                    rows,
                    total_capacity=7,
                    class_capacities=capacities,
                    aggregate_budget_enforced=False,
                    policy_version=9,
                    search_metadata_out=metadata,
                )
            )
            baseline, baseline_remaining = (
                parallel_admission_module.parallel_admission_outcomes(
                    rows,
                    total_capacity=7,
                    class_capacities=capacities,
                    aggregate_budget_enforced=False,
                    policy_version=8,
                )
            )
            current_objective = objective(rows, current, current_remaining)
            baseline_objective = objective(rows, baseline, baseline_remaining)
            self.assertGreaterEqual(current_objective, baseline_objective)
            self.assertEqual(
                list(baseline_objective),
                metadata["greedy_baseline_objective_value"],
            )
            self.assertEqual(list(current_objective), metadata["objective_value"])
            fallback_seen |= metadata["selected_policy"] == "greedy_lower_bound"
            improvement_seen |= current_objective > baseline_objective

        self.assertTrue(fallback_seen)
        self.assertTrue(improvement_seen)

    def test_parallel_v4_fairness_continues_from_a_v3_candidate_alias(self) -> None:
        current_id = "parallel:" + "4" * 24
        legacy_id = "parallel:" + "3" * 24
        historical_wave = {
            "wave_id": "a" * 64,
            "candidates": [
                {
                    "candidate_id": legacy_id,
                    "disposition": "rejected",
                    "reason": "total wave capacity reached",
                }
            ],
        }

        self.assertEqual(
            {current_id: 1},
            parallel_admission_module.parallel_candidate_deferral_counts(
                [
                    {
                        "decision_trace": {
                            "parallel_wave_admission": historical_wave
                        }
                    }
                ],
                [current_id],
                candidate_aliases={current_id: (legacy_id,)},
            ),
        )

    def test_parallel_deduplication_preserves_all_generator_sources(self) -> None:
        candidate = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "",
            "search_intent": "exact_theorem_search",
            "proof_obligation_id": "shared-output",
        }
        generated = [
            {**candidate, "_candidate_generator_id": "peer_verification"},
            {**candidate, "_candidate_generator_id": "verifier_capacity"},
        ]
        _selected, trace = scheduler_module._admit_parallel_companion_candidates(
            {"mode": "prove", "target_id": "root", "route_id": ""},
            generated,
            problem={"parallel_branches": 2},
        )

        self.assertEqual(2, len(trace["candidates"]))
        self.assertEqual(
            [
                {
                    "start_index": 0,
                    "candidate_count": 1,
                    "generator_ids": ["peer_verification", "verifier_capacity"],
                }
            ],
            trace["candidate_generator_assignment_runs"],
        )
        self.assertEqual(1, trace["candidate_generator_counts"]["peer_verification"])
        self.assertEqual(1, trace["candidate_generator_counts"]["verifier_capacity"])
        self.assertEqual(
            ["peer_verification", "verifier_capacity"],
            trace["evaluated_candidate_generator_ids"],
        )
        self.assertEqual(
            {
                spec.generator_id
                for spec in CANDIDATE_GENERATOR_GRAPH
                if spec.scope_id == "parallel_wave"
            }
            - {"peer_verification", "verifier_capacity"},
            set(trace["candidate_generator_skip_reasons"]),
        )
        self.assertEqual(
            [], parallel_admission_module.parallel_wave_admission_errors(trace)
        )

    def test_parallel_manifest_distinguishes_disabled_generators_from_zero_output(self) -> None:
        evaluation = scheduler_module._new_parallel_generator_evaluation()
        scheduler_module._skip_parallel_candidate_generators(
            evaluation,
            scheduler_module._PARALLEL_COMPANION_GENERATOR_IDS,
            "parallel_companions_disabled",
        )
        scheduler_module._skip_parallel_candidate_generators(
            evaluation,
            {"multi_branch"},
            "configured_parallelism_disabled",
        )
        selected, trace = scheduler_module._admit_parallel_companion_candidates(
            {"mode": "prove", "target_id": "root", "route_id": ""},
            [],
            problem={"parallel_branches": 0},
            _generator_evaluation=evaluation,
        )

        self.assertEqual([], selected)
        self.assertEqual([], trace["evaluated_candidate_generator_ids"])
        self.assertEqual(
            {
                spec.generator_id
                for spec in CANDIDATE_GENERATOR_GRAPH
                if spec.scope_id == "parallel_wave"
            },
            set(trace["candidate_generator_skip_reasons"]),
        )
        self.assertEqual(
            "parallel_companions_disabled",
            trace["candidate_generator_skip_reasons"]["peer_verification"],
        )
        self.assertEqual(
            "configured_parallelism_disabled",
            trace["candidate_generator_skip_reasons"]["multi_branch"],
        )
        self.assertEqual(
            "no_caller_supplied_candidates",
            trace["candidate_generator_skip_reasons"]["caller_supplied"],
        )
        self.assertEqual(
            [], parallel_admission_module.parallel_wave_admission_errors(trace)
        )

    def test_parallel_production_evaluation_fails_closed_when_a_family_is_unresolved(self) -> None:
        evaluation = scheduler_module._new_parallel_generator_evaluation()
        scheduler_module._skip_parallel_candidate_generators(
            evaluation,
            {"multi_branch"},
            "configured_parallelism_disabled",
        )

        with self.assertRaisesRegex(
            RuntimeError, "candidate-generator evaluation is incomplete"
        ):
            scheduler_module._admit_parallel_companion_candidates(
                {"mode": "prove", "target_id": "root", "route_id": ""},
                [],
                problem={"parallel_branches": 0},
                _generator_evaluation=evaluation,
            )

    def test_parallel_v3_alias_collision_cannot_age_two_v4_candidates(self) -> None:
        first_id = "parallel:" + "4" * 24
        second_id = "parallel:" + "5" * 24
        ambiguous_legacy_id = "parallel:" + "3" * 24
        historical_wave = {
            "wave_id": "a" * 64,
            "candidates": [
                {
                    "candidate_id": ambiguous_legacy_id,
                    "disposition": "rejected",
                    "reason": "total wave capacity reached",
                }
            ],
        }

        self.assertEqual(
            {first_id: 0, second_id: 0},
            parallel_admission_module.parallel_candidate_deferral_counts(
                [
                    {
                        "decision_trace": {
                            "parallel_wave_admission": historical_wave
                        }
                    }
                ],
                [first_id, second_id],
                candidate_aliases={
                    first_id: (ambiguous_legacy_id,),
                    second_id: (ambiguous_legacy_id,),
                },
            ),
        )

    def test_parallel_deferrals_count_each_wave_once_when_runs_interleave(self) -> None:
        candidate_id = "parallel:" + "c" * 24

        def historical_run(wave_id: str) -> dict[str, object]:
            return {
                "decision_trace": {
                    "parallel_wave_admission": {
                        "wave_id": wave_id,
                        "candidates": [
                            {
                                "candidate_id": candidate_id,
                                "disposition": "rejected",
                                "reason": "total wave capacity reached",
                            }
                        ],
                    }
                }
            }

        wave_a = "a" * 64
        wave_b = "b" * 64
        self.assertEqual(
            {candidate_id: 2},
            parallel_admission_module.parallel_candidate_deferral_counts(
                [
                    historical_run(wave_a),
                    historical_run(wave_b),
                    historical_run(wave_a),
                ],
                [candidate_id],
            ),
        )

    def test_parallel_fairness_does_not_age_inadmissible_candidates(self) -> None:
        candidate_id = "parallel:" + "d" * 24
        runs = [
            {
                "decision_trace": {
                    "parallel_wave_admission": {
                        "wave_id": hashlib.sha256(
                            f"inadmissible-{index}".encode("utf-8")
                        ).hexdigest(),
                        "candidates": [
                            {
                                "candidate_id": candidate_id,
                                "disposition": "rejected",
                                "reason": (
                                    "candidate budget does not authorize dispatch"
                                ),
                            }
                        ],
                    }
                }
            }
            for index in range(5)
        ]

        self.assertEqual(
            {candidate_id: 0},
            parallel_admission_module.parallel_candidate_deferral_counts(
                runs,
                [candidate_id],
            ),
        )

    def test_parallel_v4_bounds_starvation_across_admission_classes(self) -> None:
        primary = {"mode": "triage_routes", "target_id": "root", "route_id": ""}
        candidates = [
            {"mode": "integrate", "target_id": "a", "route_id": "route-a"},
            {"mode": "integrate", "target_id": "b", "route_id": "route-b"},
            {
                "mode": "retrieve",
                "target_id": "root",
                "route_id": "",
                "search_intent": "exact_theorem_search",
                "proof_obligation_id": "literature",
            },
            {
                "mode": "reduce",
                "target_id": "c",
                "route_id": "route-c",
                "search_intent": "lower-priority-research",
            },
        ]
        _selected, initial = scheduler_module._admit_parallel_companion_candidates(
            primary,
            candidates,
            problem={"parallel_branches": 2},
        )
        deferred = next(
            row
            for row in initial["candidates"]
            if row["search_intent"] == "lower-priority-research"
        )
        self.assertEqual("rejected", deferred["disposition"])
        recent_runs = []
        for index in range(
            parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
        ):
            historical = json.loads(json.dumps(initial))
            for row in historical["candidates"][1:]:
                if parallel_admission_module.parallel_outcome_is_fairness_eligible(
                    row
                ):
                    row["consecutive_deferrals"] = index
            _rebind_parallel_wave_snapshot(
                historical,
                state_revision=index + 1,
            )
            recent_runs.insert(
                0,
                {"decision_trace": {"parallel_wave_admission": historical}}
            )

        _selected, aged = scheduler_module._admit_parallel_companion_candidates(
            primary,
            candidates,
            problem={"parallel_branches": 2},
            recent_runs=recent_runs,
        )
        served = next(
            row
            for row in aged["candidates"]
            if row["candidate_id"] == deferred["candidate_id"]
        )
        self.assertEqual("selected", served["disposition"])
        self.assertEqual(
            parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT,
            served["consecutive_deferrals"],
        )
        self.assertEqual("selected_fairness_search", served["outcome_code"])
        self.assertIn("max-weight fairness", served["reason"])
        self.assertEqual(
            [],
            parallel_admission_module.parallel_wave_admission_errors(aged),
        )

    def test_parallel_v4_small_population_liveness_under_capacity_pressure(self) -> None:
        action_classes = ("research", "adversarial", "literature", "advisory")
        modes = {
            "research": "reduce",
            "adversarial": "refute",
            "literature": "retrieve",
            "advisory": "triage_routes",
        }
        primary_identity = parallel_admission_module.parallel_action_identity(
            {"mode": "triage_routes", "target_id": "primary"},
            action_class="advisory",
        )
        primary = {
            "candidate_id": "parallel:primary",
            "admission_priority": 1_000_000,
            "action_class": "advisory",
            "mode": "triage_routes",
            "target_id": "primary",
            "route_id": "",
            "search_intent": "",
            "semantic_identity": list(primary_identity),
            "consecutive_deferrals": 0,
            "deferral_limit": 0,
            "budget_allowed": True,
            "requested_tokens": 0,
            "comparison_action_sha256": "0" * 64,
        }
        capacities = {
            "research_or_adversarial": 8,
            "verification": 8,
            "integration": 8,
            "literature": 8,
            "advisory": 8,
        }
        for population in range(1, 7):
            with self.subTest(population=population):
                candidates = []
                for index in range(population):
                    action_class = action_classes[index % len(action_classes)]
                    search_intent = (
                        "exact_theorem_search"
                        if action_class == "literature"
                        else ""
                    )
                    action = {
                        "mode": modes[action_class],
                        "target_id": f"target-{index}",
                        "route_id": "",
                        "search_intent": search_intent,
                        "proof_obligation_id": f"obligation-{index}",
                    }
                    identity = parallel_admission_module.parallel_action_identity(
                        action, action_class=action_class
                    )
                    candidates.append(
                        {
                            "candidate_id": parallel_admission_module.parallel_candidate_id(
                                identity
                            ),
                            "admission_priority": parallel_admission_module.parallel_admission_priority_for(
                                action_class, search_intent
                            ),
                            "action_class": action_class,
                            "mode": action["mode"],
                            "target_id": action["target_id"],
                            "route_id": "",
                            "search_intent": search_intent,
                            "semantic_identity": list(identity),
                            "consecutive_deferrals": 0,
                            "deferral_limit": parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT,
                            "budget_allowed": True,
                            "requested_tokens": 0,
                            "comparison_action_sha256": hashlib.sha256(
                                str(index).encode("ascii")
                            ).hexdigest(),
                        }
                    )
                remaining = {row["candidate_id"] for row in candidates}
                max_rounds = (
                    parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                    + population
                    + 1
                )
                for _round in range(max_rounds):
                    ordered = sorted(
                        candidates,
                        key=parallel_admission_module.parallel_admission_order_key,
                    )
                    outcomes, _remaining_tokens = parallel_admission_module.parallel_admission_outcomes(
                        [primary, *ordered],
                        total_capacity=2,
                        class_capacities=capacities,
                        aggregate_budget_enforced=False,
                    )
                    for row in candidates:
                        outcome = outcomes[row["candidate_id"]]
                        disposition = outcome.disposition
                        reason = outcome.reason
                        if disposition == "selected":
                            remaining.discard(row["candidate_id"])
                            row["consecutive_deferrals"] = 0
                        elif parallel_admission_module._rejection_is_fairness_eligible(
                            reason
                        ):
                            row["consecutive_deferrals"] += 1
                    if not remaining:
                        break
                self.assertEqual(set(), remaining)

    def test_parallel_v6_bounds_service_for_stable_sibling_conflict_cliques(self) -> None:
        primary = {
            "mode": "triage_routes",
            "target_id": "primary",
            "route_id": "",
        }
        for population in range(2, 7):
            with self.subTest(population=population):
                candidates = [
                    {
                        "mode": "reduce",
                        "target_id": f"conflict-target-{index}",
                        "route_id": "shared-conflict-route",
                        "search_intent": "conflict_fairness_probe",
                        "proof_obligation_id": f"conflict-obligation-{index}",
                    }
                    for index in range(population)
                ]
                counts: dict[str, int] = {}
                served: set[str] = set()
                observed_queued_conflict = False
                max_rounds = (
                    parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                    + population
                )
                for _round in range(max_rounds):
                    _selected, trace = (
                        scheduler_module._admit_parallel_companion_candidates(
                            primary,
                            candidates,
                            problem={"parallel_branches": 5},
                            durable_deferral_counts=counts,
                        )
                    )
                    companion_rows = trace["candidates"][1:]
                    self.assertLessEqual(
                        sum(
                            row["disposition"] == "selected"
                            for row in companion_rows
                        ),
                        1,
                    )
                    next_counts: dict[str, int] = {}
                    for row in companion_rows:
                        candidate_id = row["candidate_id"]
                        if row["disposition"] == "selected":
                            served.add(candidate_id)
                            continue
                        if parallel_admission_module.parallel_outcome_is_fairness_eligible(
                            row
                        ):
                            self.assertEqual(
                                "sibling_conflict_queue", row["outcome_code"]
                            )
                            observed_queued_conflict |= row["reason"].startswith(
                                "queued behind conflicting companion: "
                            )
                            next_counts[candidate_id] = (
                                row["consecutive_deferrals"] + 1
                            )
                    counts = next_counts
                    if len(served) == population:
                        break

                self.assertTrue(observed_queued_conflict)
                self.assertEqual(population, len(served))

    def test_parallel_v8_ages_only_serializable_primary_conflicts(self) -> None:
        primary = {
            "mode": "reduce",
            "target_id": "root",
            "route_id": "primary-owned-route",
        }
        candidate = {
            "mode": "reduce",
            "target_id": "lemma",
            "route_id": "primary-owned-route",
            "proof_obligation_id": "blocked-by-primary",
        }

        selected, trace = scheduler_module._admit_parallel_companion_candidates(
            primary,
            [candidate],
            problem={"parallel_branches": 3},
            durable_deferral_counts={},
        )
        row = trace["candidates"][1]
        self.assertEqual([], selected)
        self.assertEqual(0, row["consecutive_deferrals"])
        self.assertEqual("primary_serialization_queue", row["outcome_code"])
        self.assertTrue(
            parallel_admission_module.parallel_outcome_is_fairness_eligible(row)
        )
        self.assertEqual(
            {row["candidate_id"]: 1},
            parallel_admission_module.parallel_candidate_deferral_counts(
                [{"decision_trace": {"parallel_wave_admission": trace}}],
                [row["candidate_id"]],
            ),
        )

        legacy_outcomes, _remaining = (
            parallel_admission_module.parallel_admission_outcomes(
                trace["candidates"],
                total_capacity=trace["total_wave_capacity"],
                class_capacities=trace["class_capacities"],
                aggregate_budget_enforced=False,
                policy_version=7,
            )
        )
        legacy = legacy_outcomes[row["candidate_id"]]
        self.assertEqual("primary_or_structural_conflict", legacy.outcome_code)

        structural_candidate = {
            "mode": "write",
            "target_id": "root",
            "route_id": "",
            "reason": "exclusive document action",
        }
        structural_selected, structural_trace = (
            scheduler_module._admit_parallel_companion_candidates(
                primary,
                [structural_candidate],
                problem={"parallel_branches": 3},
                durable_deferral_counts={},
            )
        )
        self.assertEqual([], structural_selected)
        structural_row = structural_trace["candidates"][1]
        self.assertEqual(
            "primary_or_structural_conflict", structural_row["outcome_code"]
        )
        self.assertFalse(
            parallel_admission_module.parallel_outcome_is_fairness_eligible(
                structural_row
            )
        )

    def test_overdue_same_tier_serial_conflict_becomes_wave_leader(self) -> None:
        primary_action = {
            "mode": "reduce",
            "target_id": "root",
            "route_id": "shared-route",
            "reason": "scheduled primary",
        }
        primary_action, primary_trace = select_action_candidate(
            [
                ActionCandidate(
                    "base:primary",
                    "base_policy",
                    primary_action,
                    ordinal_priority=1.0,
                )
            ],
            candidate_set_complete=True,
        )
        primary_action["decision_trace"] = primary_trace
        candidate = {
            "mode": "reduce",
            "target_id": "lemma",
            "route_id": "shared-route",
            "reason": "serialized candidate",
            "_candidate_generator_id": "multi_branch",
            "parallel_companion": True,
        }
        normalized_candidate = dict(candidate)
        normalized_candidate.pop("_candidate_generator_id")
        normalized_candidate.pop("parallel_companion")
        candidate_id = parallel_admission_module.parallel_candidate_id(
            scheduler_module._parallel_action_identity(normalized_candidate)
        )
        selected, promoted = scheduler_module._select_parallel_wave_leader(
            {
                "parallel_candidate_deferrals": {
                    candidate_id: parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                }
            },
            primary_action,
            [candidate],
        )

        self.assertTrue(promoted)
        self.assertEqual("lemma", selected["target_id"])
        self.assertNotIn("parallel_companion", selected)
        leader_trace = selected["decision_trace"]
        self.assertEqual("parallel_leader", leader_trace["candidate_generator_scope_id"])
        self.assertEqual(5, leader_trace["candidate_generator_graph_version"])
        self.assertEqual([], decision_trace_errors(leader_trace))

    def test_serial_primary_conflict_promotes_through_durable_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "durable-primary-serialization",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            candidate = scheduler_module._action(
                "reduce",
                "lemma",
                "shared-route",
                "serialized candidate",
                budget_module.plan_step_budget(
                    store.get_scheduler_state()["problem_state"],
                    "reduce",
                    10_000,
                ),
            )
            candidate_id = parallel_admission_module.parallel_candidate_id(
                scheduler_module._parallel_action_identity(candidate)
            )

            def new_primary() -> dict[str, object]:
                problem = store.get_scheduler_state()["problem_state"]
                planned = scheduler_module._action(
                    "reduce",
                    "root",
                    "shared-route",
                    "scheduled primary",
                    budget_module.plan_step_budget(problem, "reduce", 10_000),
                )
                action, trace = select_action_candidate(
                    [
                        ActionCandidate(
                            "base:durable-primary",
                            "base_policy",
                            planned,
                            ordinal_priority=1.0,
                        )
                    ],
                    candidate_set_complete=True,
                )
                action["decision_trace"] = bind_dispatched_action(action, trace)
                return action

            def record(action: Mapping[str, object], run_id: str) -> None:
                outcome = _record_dispatched_test_run(store, action, run_id)
                self.assertTrue(outcome.accepted, outcome.errors)

            for round_index in range(
                parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
            ):
                state = store.get_scheduler_state()
                primary = new_primary()
                _selected, wave = (
                    scheduler_module._admit_parallel_companion_candidates(
                        primary,
                        [candidate],
                        problem=state["problem_state"],
                        durable_deferral_counts=state[
                            "parallel_candidate_deferrals"
                        ],
                    )
                )
                row = wave["candidates"][1]
                self.assertEqual("primary_serialization_queue", row["outcome_code"])
                self.assertEqual(round_index, row["consecutive_deferrals"])
                record(
                    scheduler_module._bind_primary_parallel_wave_decision(
                        primary, wave
                    ),
                    f"serialization-{round_index}",
                )

            state = store.get_scheduler_state()
            self.assertEqual(
                parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT,
                state["parallel_candidate_deferrals"][candidate_id],
            )
            promoted, was_promoted = scheduler_module._select_parallel_wave_leader(
                state, new_primary(), [candidate]
            )
            self.assertTrue(was_promoted)
            self.assertEqual("lemma", promoted["target_id"])
            _companions, promoted_wave = (
                scheduler_module._admit_parallel_companion_candidates(
                    promoted,
                    [],
                    problem=state["problem_state"],
                    durable_deferral_counts=state[
                        "parallel_candidate_deferrals"
                    ],
                )
            )
            record(
                scheduler_module._bind_primary_parallel_wave_decision(
                    promoted, promoted_wave
                ),
                "serialization-promoted",
            )
            leader_trace = promoted["decision_trace"]
            scheduled_id = next(
                row["candidate_id"]
                for row in leader_trace["candidates"]
                if row["candidate_id"].startswith("parallel_leader:scheduled:")
            )
            self.assertEqual(
                1,
                store.get_scheduler_state()["decision_candidate_deferrals"][
                    scheduled_id
                ],
            )

    def test_parallel_leader_never_overrides_mandatory_or_higher_tier_primary(self) -> None:
        candidate = {
            "mode": "reduce",
            "target_id": "lemma",
            "route_id": "shared-route",
            "reason": "serialized candidate",
        }
        candidate_id = parallel_admission_module.parallel_candidate_id(
            scheduler_module._parallel_action_identity(candidate)
        )
        state = {
            "parallel_candidate_deferrals": {
                candidate_id: parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
            }
        }
        for primary_action, mandatory in (
            (
                {
                    "mode": "reduce",
                    "target_id": "root",
                    "route_id": "shared-route",
                    "reason": "mandatory primary",
                },
                True,
            ),
            (
                {
                    "mode": "prove",
                    "target_id": "root",
                    "route_id": "shared-route",
                    "reason": "verification primary",
                    "verify_ready_route_policy": True,
                },
                False,
            ),
        ):
            traced_primary, trace = select_action_candidate(
                [
                    ActionCandidate(
                        "base:primary",
                        "base_policy",
                        primary_action,
                        ordinal_priority=1.0,
                        mandatory_constraint=mandatory,
                        policy_tier=scheduler_module._base_action_policy_tier(
                            primary_action
                        ),
                    )
                ],
                candidate_set_complete=True,
            )
            traced_primary["decision_trace"] = trace
            selected, promoted = scheduler_module._select_parallel_wave_leader(
                state, traced_primary, [candidate]
            )
            self.assertFalse(promoted)
            self.assertEqual(primary_action["target_id"], selected["target_id"])

    def test_parallel_leader_ignores_nondispatchable_generator_rows(self) -> None:
        primary, trace = select_action_candidate(
            [
                ActionCandidate(
                    "base:primary",
                    "base_policy",
                    {
                        "mode": "reduce",
                        "target_id": "root",
                        "route_id": "shared-route",
                    },
                    ordinal_priority=1.0,
                )
            ],
            candidate_set_complete=True,
        )
        primary["decision_trace"] = bind_dispatched_action(primary, trace)
        for candidate in (
            {
                "mode": "not_a_run_mode",
                "target_id": "lemma",
                "route_id": "shared-route",
            },
            {
                "mode": "reduce",
                "target_id": "",
                "route_id": "shared-route",
            },
        ):
            candidate_id = parallel_admission_module.parallel_candidate_id(
                scheduler_module._parallel_action_identity(candidate)
            )
            selected, promoted = scheduler_module._select_parallel_wave_leader(
                {
                    "parallel_candidate_deferrals": {
                        candidate_id: (
                            parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
                        )
                    }
                },
                primary,
                [candidate],
            )
            self.assertFalse(promoted)
            self.assertEqual("root", selected["target_id"])

    def test_regulate_decomposition_is_committed_as_an_executable_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "regulate-decomposition-dispatch",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem(
                "The root theorem holds.",
                total_token_budget=100,
                reserved_verification_budget=20,
            )
            action, trace = select_action_candidate(
                [
                    ActionCandidate(
                        "base:regulate-decomposition",
                        "base_policy",
                        {
                            "mode": "regulate_decomposition",
                            "target_id": "root",
                            "route_id": "",
                            "budget": {
                                "allowed": True,
                                "requested_tokens": 80,
                                "request_limit_tokens": 80,
                                "spendable_tokens": 80,
                                "remaining_token_budget": 100,
                                "reserved_verification_budget": 20,
                                "reason": "ok",
                            },
                        },
                        ordinal_priority=1.0,
                    )
                ],
                candidate_set_complete=True,
            )
            action["decision_trace"] = bind_dispatched_action(action, trace)
            unbound_action = json.loads(json.dumps(action))
            unbound_action["decision_trace"].pop(
                "scheduler_action_contract_version"
            )
            unbound_action["decision_trace"].pop(
                "scheduler_action_contract_sha256"
            )
            with self.assertRaisesRegex(RuntimeError, "action-semantics binding"):
                _record_scheduler_dispatches(
                    store,
                    [unbound_action],
                    store.audit_chain_heads(),
                    execution_contract={
                        "version": 1,
                        "driver": "builtin_codex",
                        "identity": "codex:missing-action-contract-test",
                        "recovery_capability": "supervised_process",
                    },
                )
            overallocated_action = json.loads(json.dumps(action))
            overallocated_action["budget"]["requested_tokens"] = 81
            overallocated_action["decision_trace"] = bind_dispatched_action(
                overallocated_action,
                overallocated_action["decision_trace"],
            )
            with self.assertRaisesRegex(
                RuntimeError, "requested <= spendable"
            ):
                _record_scheduler_dispatches(
                    store,
                    [overallocated_action],
                    store.audit_chain_heads(),
                    execution_contract={
                        "version": 1,
                        "driver": "builtin_codex",
                        "identity": "codex:overallocated-action-test",
                        "recovery_capability": "supervised_process",
                    },
                )
            with mock.patch.object(
                workflow_module,
                "actor_role_for_action",
                return_value="researcher",
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "actor role disagrees"
                ):
                    _record_scheduler_dispatches(
                        store,
                        [action],
                        store.audit_chain_heads(),
                        execution_contract={
                            "version": 1,
                            "driver": "builtin_codex",
                            "identity": "codex:forged-role-test",
                            "recovery_capability": "supervised_process",
                        },
                    )
            dispatches, _heads = _record_scheduler_dispatches(
                store,
                [action],
                store.audit_chain_heads(),
                execution_contract={
                    "version": 1,
                    "driver": "builtin_codex",
                    "identity": "codex:mode-contract-test",
                    "recovery_capability": "supervised_process",
                },
            )
            self.assertEqual("regulate_decomposition", dispatches[0]["mode"])
            with store.connect() as conn:
                row = conn.execute(
                    "SELECT actor_role, mode, decision_trace_json "
                    "FROM scheduler_dispatches"
                ).fetchone()
            self.assertEqual("regulate_decomposition", row["mode"])
            self.assertEqual("phd_advisor", row["actor_role"])
            stored_trace = json.loads(row["decision_trace_json"])
            self.assertEqual(
                action_contract_module.SCHEDULER_ACTION_CONTRACT_VERSION,
                stored_trace["scheduler_action_contract_version"],
            )
            self.assertEqual(
                action_contract_module.SCHEDULER_ACTION_CONTRACT_SHA256[
                    action_contract_module.SCHEDULER_ACTION_CONTRACT_VERSION
                ],
                stored_trace["scheduler_action_contract_sha256"],
            )

    def test_dispatch_boundary_authenticates_complete_parallel_allocations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "dispatch-group-allocation-boundary",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem(
                "Prove a difficult theorem.",
                total_token_budget=500_000,
                reserved_verification_budget=100_000,
            )
            primary = next_action(store, web_search="live")
            companions = scheduler_module.parallel_companion_actions(
                store, primary, web_search="live"
            )
            self.assertTrue(companions)
            primary = scheduler_module._bind_primary_parallel_wave_decision(
                primary, companions[0]["parallel_wave_admission"]
            )
            actions = [primary, *companions]
            heads = store.audit_chain_heads()
            execution_contract = {
                "version": 1,
                "driver": "custom",
                "identity": "test:dispatch-allocation-boundary",
                "recovery_capability": "none",
            }

            with self.assertRaisesRegex(
                RuntimeError, "exactly its admitted parallel wave"
            ):
                _record_scheduler_dispatches(
                    store,
                    [primary],
                    heads,
                    execution_contract=execution_contract,
                )

            mutated = json.loads(json.dumps(actions))
            mutated[0]["reason"] = "altered after parallel admission"
            mutated[0]["decision_trace"] = bind_dispatched_action(
                mutated[0], mutated[0]["decision_trace"]
            )
            with self.assertRaisesRegex(
                RuntimeError, "disagrees with its admitted parallel-wave input"
            ):
                _record_scheduler_dispatches(
                    store,
                    mutated,
                    heads,
                    execution_contract=execution_contract,
                )

            false_snapshot = json.loads(json.dumps(actions))
            false_snapshot[0]["budget"].update(
                remaining_token_budget=600_000,
                spendable_tokens=500_000,
            )
            false_snapshot[0]["decision_trace"] = bind_dispatched_action(
                false_snapshot[0], false_snapshot[0]["decision_trace"]
            )
            with self.assertRaisesRegex(
                RuntimeError, "authenticated planning state"
            ):
                _record_scheduler_dispatches(
                    store,
                    false_snapshot,
                    heads,
                    execution_contract=execution_contract,
                )

            overcommitted = json.loads(json.dumps(actions))
            overcommitted[0]["budget"].update(
                requested_tokens=250_000,
                request_limit_tokens=250_000,
            )
            overcommitted[0]["decision_trace"] = bind_dispatched_action(
                overcommitted[0], overcommitted[0]["decision_trace"]
            )
            with self.assertRaisesRegex(
                RuntimeError, "protected verification resources"
            ):
                _record_scheduler_dispatches(
                    store,
                    overcommitted,
                    heads,
                    execution_contract=execution_contract,
                )

            dispatches, _committed_heads = _record_scheduler_dispatches(
                store,
                actions,
                heads,
                execution_contract=execution_contract,
            )
            self.assertEqual(len(actions), len(dispatches))
            with store.connect() as conn:
                self.assertEqual([], validate_conn(conn))

    def test_parallel_leader_cohort_has_bounded_service_after_bootstrap(self) -> None:
        candidates = [
            {
                "mode": "reduce",
                "target_id": f"lemma-{index}",
                "route_id": "shared-route",
                "reason": f"serialized candidate {index}",
                "proof_obligation_id": f"obligation-{index}",
            }
            for index in range(4)
        ]
        parallel_counts = {
            parallel_admission_module.parallel_candidate_id(
                scheduler_module._parallel_action_identity(candidate)
            ): parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
            for candidate in candidates
        }
        decision_counts: dict[str, int] = {}
        served: set[str] = set()
        max_rounds = 2 + len(candidates) * (
            parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT + 1
        )
        for _round in range(max_rounds):
            base_count = decision_counts.get("base:primary", 0)
            primary, primary_trace = select_action_candidate(
                [
                    ActionCandidate(
                        "base:primary",
                        "base_policy",
                        {
                            "mode": "reduce",
                            "target_id": "root",
                            "route_id": "shared-route",
                            "reason": "scheduled primary",
                        },
                        ordinal_priority=1.0,
                        consecutive_deferrals=base_count,
                        deferral_limit=scheduler_module.SCHEDULER_DEFERRAL_LIMIT,
                    )
                ],
                candidate_set_complete=True,
            )
            primary["decision_trace"] = primary_trace
            selected, promoted = scheduler_module._select_parallel_wave_leader(
                {
                    "parallel_candidate_deferrals": parallel_counts,
                    "decision_candidate_deferrals": decision_counts,
                },
                primary,
                candidates,
            )
            leader_trace = selected["decision_trace"]
            self.assertEqual([], decision_trace_errors(leader_trace))
            if promoted:
                served.add(str(selected["target_id"]))
            decision_counts = (
                decision_policy_module.decision_deferral_state_after_trace(
                    decision_counts, leader_trace
                )
            )
            if len(served) == len(candidates):
                break

        self.assertEqual(
            {str(candidate["target_id"]) for candidate in candidates}, served
        )

    def test_parallel_v6_does_not_age_unauthorized_sibling_conflict(self) -> None:
        primary = {
            "mode": "triage_routes",
            "target_id": "primary",
            "route_id": "",
        }
        verifier = {
            "mode": "prove",
            "target_id": "shared-claim",
            "route_id": "verification-route",
            "proof_obligation_id": "verification-obligation",
        }
        unauthorized_research = {
            "mode": "reduce",
            "target_id": "shared-claim",
            "route_id": "research-route",
            "proof_obligation_id": "research-obligation",
            "budget": {"allowed": False, "requested_tokens": 600},
        }

        selected, trace = scheduler_module._admit_parallel_companion_candidates(
            primary,
            [unauthorized_research, verifier],
            problem={"parallel_branches": 3},
            durable_deferral_counts={},
        )
        companion_rows = {
            row["mode"]: row for row in trace["candidates"][1:]
        }
        self.assertEqual(["prove"], [row["mode"] for row in selected])
        self.assertEqual("selected", companion_rows["prove"]["disposition"])
        rejected = companion_rows["reduce"]
        self.assertEqual("rejected", rejected["disposition"])
        self.assertEqual(
            "candidate budget does not authorize dispatch",
            rejected["reason"],
        )
        self.assertEqual("budget_unauthorized", rejected["outcome_code"])
        self.assertFalse(
            parallel_admission_module.parallel_outcome_is_fairness_eligible(
                rejected
            )
        )
        self.assertEqual(
            0,
            parallel_admission_module.parallel_candidate_deferral_counts(
                [trace],
                [rejected["candidate_id"]],
            )[rejected["candidate_id"]],
        )

    def test_parallel_fairness_is_durable_sealed_and_independent_of_trace_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "durable-parallel-fairness",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            problem = store.get_scheduler_state()["problem_state"]
            candidates = [
                scheduler_module._action(
                    "reduce",
                    target,
                    "shared-durable-conflict-route",
                    "test companion",
                    budget_module.plan_step_budget(problem, "reduce", 10_000),
                )
                for target in ("lemma-a", "lemma-b")
            ]
            deferred_candidate_id = ""

            def new_primary() -> dict[str, object]:
                problem = store.get_scheduler_state()["problem_state"]
                planned = scheduler_module._action(
                    "reduce",
                    "root",
                    "",
                    "durable fairness primary",
                    budget_module.plan_step_budget(problem, "reduce", 10_000),
                )
                action, trace = select_action_candidate(
                    [
                        ActionCandidate(
                            "base:durable-fairness",
                            "research",
                            planned,
                            1.0,
                        )
                    ],
                    candidate_set_complete=True,
                )
                action["decision_trace"] = bind_dispatched_action(action, trace)
                return action

            def record_primary(
                action: Mapping[str, object],
                run_id: str,
                *,
                companions: Sequence[Mapping[str, object]] = (),
                expect_accepted: bool = True,
            ) -> object:
                wave_actions = [action, *companions]
                outcome = _record_dispatched_test_wave(
                    store,
                    wave_actions,
                    [
                        run_id,
                        *[
                            f"{run_id}-companion-{index}"
                            for index in range(1, len(wave_actions))
                        ],
                    ],
                )
                if expect_accepted:
                    self.assertTrue(outcome.accepted, outcome.errors)
                return outcome

            state = store.get_scheduler_state()
            probe_primary = new_primary()
            _probe_selected, probe_wave = (
                scheduler_module._admit_parallel_companion_candidates(
                    probe_primary,
                    candidates,
                    problem=state["problem_state"],
                    durable_deferral_counts={},
                )
            )
            probe_rejected_id = str(
                next(
                    row
                    for row in probe_wave["candidates"]
                    if row["disposition"] == "rejected"
                )["candidate_id"]
            )
            poisoned_primary = new_primary()
            poisoned_selected, poisoned_wave = (
                scheduler_module._admit_parallel_companion_candidates(
                    poisoned_primary,
                    candidates,
                    problem=state["problem_state"],
                    durable_deferral_counts={probe_rejected_id: 2},
                )
            )
            poisoned_primary = scheduler_module._bind_primary_parallel_wave_decision(
                poisoned_primary, poisoned_wave
            )
            poisoned_companions = [
                scheduler_module._bind_parallel_wave_decision(
                    companion, poisoned_wave
                )
                for companion in poisoned_selected
            ]
            poisoned_outcome = record_primary(
                poisoned_primary,
                "poisoned-fairness-run",
                companions=poisoned_companions,
                expect_accepted=False,
            )
            self.assertFalse(poisoned_outcome.accepted)
            self.assertTrue(
                any("disagrees with authenticated" in error for error in poisoned_outcome.errors),
                poisoned_outcome.errors,
            )

            for round_index in range(
                parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT
            ):
                state = store.get_scheduler_state()
                primary = new_primary()
                selected, wave = scheduler_module._admit_parallel_companion_candidates(
                    primary,
                    candidates,
                    problem=state["problem_state"],
                    recent_runs=[],
                    durable_deferral_counts=state["parallel_candidate_deferrals"],
                )
                rejected = next(
                    row
                    for row in wave["candidates"]
                    if row["disposition"] == "rejected"
                )
                deferred_candidate_id = str(rejected["candidate_id"])
                self.assertEqual(round_index, rejected["consecutive_deferrals"])
                self.assertTrue(
                    rejected["reason"].startswith(
                        "queued behind conflicting companion: "
                    )
                )
                bound_primary = scheduler_module._bind_primary_parallel_wave_decision(
                    primary, wave
                )
                bound_companions = [
                    scheduler_module._bind_parallel_wave_decision(
                        companion, wave
                    )
                    for companion in selected
                ]
                record_primary(
                    bound_primary,
                    f"fairness-run-{round_index}",
                    companions=bound_companions,
                )
                persisted = store.get_scheduler_state()
                self.assertEqual(
                    round_index + 1,
                    persisted["parallel_candidate_deferrals"][deferred_candidate_id],
                )

            state = store.get_scheduler_state()
            primary = new_primary()
            _selected, served_wave = scheduler_module._admit_parallel_companion_candidates(
                primary,
                candidates,
                problem=state["problem_state"],
                recent_runs=[],
                durable_deferral_counts=state["parallel_candidate_deferrals"],
            )
            served = next(
                row
                for row in served_wave["candidates"]
                if row["candidate_id"] == deferred_candidate_id
            )
            self.assertEqual("selected", served["disposition"])
            self.assertEqual(
                parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT,
                served["consecutive_deferrals"],
            )

            # Simulate opening a v9 store: migration v10 reconstructs the
            # exact bounded suffix once, after which scheduling no longer
            # depends on loading trace history.
            with store.connect() as conn:
                _strip_post_v9_scheduler_execution_fixture(store, conn)
                legacy_v9_hash = _legacy_v9_run_provenance_hash(conn)
                _restore_v14_proof_projection_seal(store, conn)
                conn.execute("DROP TABLE scheduler_candidate_deferrals")
                conn.execute("DROP TABLE scheduler_fairness_meta")
                conn.execute("DROP TABLE scheduler_decision_deferrals")
                conn.execute("DROP TABLE scheduler_decision_fairness_meta")
                conn.execute("DELETE FROM schema_migrations WHERE version >= 10")
                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ?",
                    (legacy_v9_hash,),
                )
                conn.commit()
            migrated = store.get_scheduler_state()
            self.assertEqual(
                parallel_admission_module.PARALLEL_WAVE_DEFERRAL_LIMIT,
                migrated["parallel_candidate_deferrals"][deferred_candidate_id],
            )
            with store.connect() as conn:
                versions = [
                    int(row["version"])
                    for row in conn.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                ]
                self.assertEqual(list(range(1, 22)), versions)

            with store.connect() as conn:
                conn.execute(
                    "UPDATE scheduler_candidate_deferrals "
                    "SET consecutive_capacity_deferrals = "
                    "consecutive_capacity_deferrals + 1"
                )
                conn.commit()
            seal = store.current_state_seal()
            self.assertFalse(seal["valid"])
            self.assertTrue(
                any("run-selection provenance" in error for error in seal["errors"]),
                seal["errors"],
            )

    def test_stale_parallel_wave_telemetry_does_not_rewind_fairness(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "stale-parallel-telemetry",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            state = store.get_scheduler_state()
            initial_heads = store.audit_chain_heads()

            def primary() -> dict[str, object]:
                planned = scheduler_module._action(
                    "reduce",
                    "root",
                    "",
                    "stale-wave primary",
                    budget_module.plan_step_budget(
                        state["problem_state"], "reduce", 10_000
                    ),
                )
                action, trace = select_action_candidate(
                    [
                        ActionCandidate(
                            "base:stale-wave",
                            "research",
                            planned,
                            1.0,
                        )
                    ],
                    candidate_set_complete=True,
                )
                action["decision_trace"] = bind_dispatched_action(action, trace)
                return action

            def make_wave(
                prefix: str,
            ) -> tuple[dict[str, object], list[dict[str, object]]]:
                action = primary()
                selected, wave = scheduler_module._admit_parallel_companion_candidates(
                    action,
                    [
                        scheduler_module._action(
                            "reduce",
                            f"{prefix}-{suffix}",
                            "",
                            "stale-wave companion",
                            budget_module.plan_step_budget(
                                state["problem_state"], "reduce", 10_000
                            ),
                        )
                        for suffix in ("a", "b")
                    ],
                    problem=state["problem_state"],
                    durable_deferral_counts={},
                )
                return (
                    scheduler_module._bind_primary_parallel_wave_decision(
                        action, wave
                    ),
                    [
                        scheduler_module._bind_parallel_wave_decision(
                            companion, wave
                        )
                        for companion in selected
                    ],
                )

            first, first_companions = make_wave("first")
            stale, stale_companions = make_wave("stale")
            first_actions = [first, *first_companions]
            first_outcome = _record_dispatched_test_wave(
                store,
                first_actions,
                [
                    "first-wave-run",
                    *[
                        f"first-wave-companion-{index}"
                        for index in range(1, len(first_actions))
                    ],
                ],
                planning_audit_heads=initial_heads,
            )
            self.assertTrue(first_outcome.accepted, first_outcome.errors)
            after_first = store.get_scheduler_state()
            stale_actions = [stale, *stale_companions]
            stale_outcome = _record_dispatched_test_wave(
                store,
                stale_actions,
                [
                    "stale-wave-run",
                    *[
                        f"stale-wave-companion-{index}"
                        for index in range(1, len(stale_actions))
                    ],
                ],
                planning_audit_heads=initial_heads,
            )
            self.assertFalse(stale_outcome.accepted)
            self.assertIn("stale patch", " ".join(stale_outcome.errors))
            after_stale = store.get_scheduler_state()
            self.assertEqual(
                after_first["parallel_fairness_state"],
                after_stale["parallel_fairness_state"],
            )
            self.assertEqual(
                after_first["parallel_candidate_deferrals"],
                after_stale["parallel_candidate_deferrals"],
            )
            self.assertEqual(
                after_first["decision_fairness_state"],
                after_stale["decision_fairness_state"],
            )
            with store.connect() as conn:
                run_ids = {
                    str(row["run_id"])
                    for row in conn.execute(
                        "SELECT run_id FROM runs WHERE run_id IN (?, ?)",
                        ("first-wave-run", "stale-wave-run"),
                    )
                }
            self.assertEqual({"first-wave-run"}, run_ids)

    def test_generic_fairness_is_durable_and_stale_dispatches_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "durable-generic-fairness",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")

            def decision(
                stored_counts: Mapping[str, object],
            ) -> dict[str, object]:
                problem = store.get_scheduler_state()["problem_state"]
                counts = decision_policy_module.decision_candidate_deferral_counts_from_state(
                    stored_counts, ["generic:preferred", "generic:deferred"]
                )
                action, trace = select_action_candidate(
                    [
                        ActionCandidate(
                            "generic:preferred",
                            "research",
                            scheduler_module._action(
                                "prove",
                                "root",
                                "",
                                "preferred generic candidate",
                                budget_module.plan_step_budget(
                                    problem, "prove", 10_000
                                ),
                            ),
                            2.0,
                            consecutive_deferrals=counts["generic:preferred"],
                            deferral_limit=3,
                        ),
                        ActionCandidate(
                            "generic:deferred",
                            "research",
                            scheduler_module._action(
                                "reduce",
                                "lemma",
                                "",
                                "deferred generic candidate",
                                budget_module.plan_step_budget(
                                    problem, "reduce", 10_000
                                ),
                            ),
                            1.0,
                            consecutive_deferrals=counts["generic:deferred"],
                            deferral_limit=3,
                        ),
                    ],
                    candidate_set_complete=True,
                )
                action["decision_trace"] = bind_dispatched_action(action, trace)
                return action

            def record(
                action: Mapping[str, object],
                run_id: str,
                *,
                expect_accepted: bool = True,
                created_at: str = "",
                planned_revision: int | None = None,
            ) -> object:
                planning_heads = None
                if planned_revision is not None:
                    planning_heads = {
                        **store.audit_chain_heads(),
                        "proof_revision": planned_revision,
                    }
                outcome = _record_dispatched_test_run(
                    store,
                    action,
                    run_id,
                    created_at=created_at,
                    planning_audit_heads=planning_heads,
                )
                if expect_accepted:
                    self.assertTrue(outcome.accepted, outcome.errors)
                return outcome

            poisoned = decision({"generic:deferred": 2})
            poisoned_outcome = record(
                poisoned, "poisoned-generic-fairness", expect_accepted=False
            )
            self.assertFalse(poisoned_outcome.accepted)
            self.assertTrue(
                any(
                    "disagrees with authenticated" in error
                    for error in poisoned_outcome.errors
                ),
                poisoned_outcome.errors,
            )
            stale_same_snapshot = decision({})

            for round_index in range(3):
                state = store.get_scheduler_state()
                state_without_history = dict(state)
                state_without_history["recent_runs"] = []
                scheduler_counts = scheduler_module._candidate_deferral_counts(
                    state_without_history,
                    ["generic:preferred", "generic:deferred"],
                )
                self.assertEqual(
                    state["decision_candidate_deferrals"].get(
                        "generic:deferred", 0
                    ),
                    scheduler_counts["generic:deferred"],
                )
                action = decision(scheduler_counts)
                deferred_row = next(
                    row
                    for row in action["decision_trace"]["candidates"]
                    if row["candidate_id"] == "generic:deferred"
                )
                self.assertEqual(round_index, deferred_row["consecutive_deferrals"])
                self.assertEqual(
                    "rejected_by_ordinal_comparison", deferred_row["disposition"]
                )
                record(
                    action,
                    f"generic-fairness-{round_index}",
                    created_at=(
                        "2099-01-01T00:00:00+00:00"
                        if round_index == 0
                        else f"200{2 - round_index}-01-01T00:00:00+00:00"
                    ),
                )
                persisted = store.get_scheduler_state()
                self.assertEqual(
                    round_index + 1,
                    persisted["decision_candidate_deferrals"]["generic:deferred"],
                )

                if round_index == 0:
                    stale_outcome = record(
                        stale_same_snapshot,
                        "generic-fairness-stale-same-snapshot",
                        expect_accepted=False,
                        planned_revision=0,
                    )
                    self.assertFalse(stale_outcome.accepted)
                    self.assertEqual(
                        1,
                        store.get_scheduler_state()["decision_candidate_deferrals"][
                            "generic:deferred"
                        ],
                    )

            # Reconstruct v10 state from the most recent primary trace.
            with store.connect() as conn:
                _strip_post_v9_scheduler_execution_fixture(store, conn)
                legacy_v9_hash = _legacy_v9_run_provenance_hash(conn)
                _restore_v14_proof_projection_seal(store, conn)
                conn.execute("DROP TABLE scheduler_candidate_deferrals")
                conn.execute("DROP TABLE scheduler_fairness_meta")
                conn.execute("DROP TABLE scheduler_decision_deferrals")
                conn.execute("DROP TABLE scheduler_decision_fairness_meta")
                conn.execute("DELETE FROM schema_migrations WHERE version >= 10")
                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ?",
                    (legacy_v9_hash,),
                )
                conn.commit()
            migrated = store.get_scheduler_state()
            self.assertEqual(
                3,
                migrated["decision_candidate_deferrals"]["generic:deferred"],
            )

            served = decision(migrated["decision_candidate_deferrals"])
            self.assertEqual("reduce", served["mode"])
            served_row = next(
                row
                for row in served["decision_trace"]["candidates"]
                if row["candidate_id"] == "generic:deferred"
            )
            self.assertEqual("selected", served_row["disposition"])
            self.assertEqual(3, served_row["consecutive_deferrals"])

            with store.connect() as conn:
                conn.execute(
                    "UPDATE scheduler_decision_deferrals "
                    "SET consecutive_deferrals = consecutive_deferrals + 1"
                )
                conn.commit()
            seal = store.current_state_seal()
            self.assertFalse(seal["valid"])
            self.assertTrue(
                any("run-selection provenance" in error for error in seal["errors"]),
                seal["errors"],
            )

    def test_parallel_v5_wave_identity_binds_zero_output_evaluation_provenance(self) -> None:
        primary = {"mode": "prove", "target_id": "root", "route_id": ""}

        def empty_wave(*, peer_evaluated: bool) -> dict[str, object]:
            evaluation = scheduler_module._new_parallel_generator_evaluation()
            all_parallel_ids = {
                spec.generator_id
                for spec in CANDIDATE_GENERATOR_GRAPH
                if spec.scope_id == "parallel_wave"
            }
            scheduler_module._skip_parallel_candidate_generators(
                evaluation,
                all_parallel_ids - {"peer_verification", "caller_supplied"},
                "test_phase_exclusion",
            )
            if peer_evaluated:
                scheduler_module._evaluate_parallel_candidate_generators(
                    evaluation, {"peer_verification"}
                )
            else:
                scheduler_module._skip_parallel_candidate_generators(
                    evaluation,
                    {"peer_verification"},
                    "test_phase_exclusion",
                )
            _selected, trace = scheduler_module._admit_parallel_companion_candidates(
                primary,
                [],
                problem={"parallel_branches": 0},
                _generator_evaluation=evaluation,
            )
            return trace

        evaluated = empty_wave(peer_evaluated=True)
        skipped = empty_wave(peer_evaluated=False)

        self.assertEqual(
            evaluated["candidate_set_sha256"], skipped["candidate_set_sha256"]
        )
        self.assertNotEqual(
            evaluated["candidate_generator_manifest_sha256"],
            skipped["candidate_generator_manifest_sha256"],
        )
        self.assertNotEqual(evaluated["wave_id"], skipped["wave_id"])
        self.assertEqual(
            [], parallel_admission_module.parallel_wave_admission_errors(evaluated)
        )
        self.assertEqual(
            [], parallel_admission_module.parallel_wave_admission_errors(skipped)
        )

    def test_parallel_v4_v5_v6_traces_remain_valid_after_v7_identity_upgrade(self) -> None:
        primary = {"mode": "prove", "target_id": "root", "route_id": ""}
        candidate = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "",
            "search_intent": "exact_theorem_search",
            "proof_obligation_id": "legacy-v4-obligation",
        }
        _selected, trace = scheduler_module._admit_parallel_companion_candidates(
            primary,
            [candidate],
            problem={"parallel_branches": 3},
        )
        actions = [primary, candidate]
        for policy_version in (4, 5, 6):
            with self.subTest(policy_version=policy_version):
                legacy = json.loads(json.dumps(trace))
                legacy["policy_version"] = policy_version
                legacy.pop("admission_search", None)
                candidate_id_map: dict[str, str] = {}
                for row, action in zip(legacy["candidates"], actions):
                    old_candidate_id = row["candidate_id"]
                    identity = parallel_admission_module.parallel_action_identity(
                        action,
                        action_class=str(row["action_class"]),
                        policy_version=policy_version,
                    )
                    row["semantic_identity"] = list(identity)
                    if old_candidate_id != "parallel:primary":
                        row["candidate_id"] = (
                            parallel_admission_module.parallel_candidate_id(
                                identity,
                                policy_version=policy_version,
                            )
                        )
                    candidate_id_map[old_candidate_id] = row["candidate_id"]
                legacy_outcomes, legacy_remaining = (
                    parallel_admission_module.parallel_admission_outcomes(
                        legacy["candidates"],
                        total_capacity=legacy["total_wave_capacity"],
                        class_capacities=legacy["class_capacities"],
                        aggregate_budget_enforced=legacy[
                            "aggregate_budget_enforced"
                        ],
                        policy_version=policy_version,
                    )
                )
                for row in legacy["candidates"]:
                    outcome = legacy_outcomes[row["candidate_id"]]
                    row["disposition"] = outcome.disposition
                    row["reason"] = outcome.reason
                    row["outcome_code"] = outcome.outcome_code
                    row["admitted_tokens"] = outcome.admitted_tokens
                legacy["remaining_uncommitted_token_budget"] = (
                    legacy_remaining
                    if legacy["aggregate_budget_enforced"]
                    else None
                )
                legacy["selected_candidate_ids"] = [
                    candidate_id_map[candidate_id]
                    for candidate_id in legacy["selected_candidate_ids"]
                ]
                legacy["candidate_set_sha256"] = (
                    parallel_admission_module.parallel_candidate_set_sha256(
                        legacy["candidates"],
                        policy_version=policy_version,
                    )
                )
                legacy["wave_id"] = parallel_admission_module.parallel_wave_id(
                    candidate_set_sha256=legacy["candidate_set_sha256"],
                    candidate_set_scope=legacy["candidate_set_scope"],
                    state_revision=legacy["state_revision"],
                    proof_state_hash=legacy["proof_state_hash"],
                    run_provenance_hash=legacy["run_provenance_hash"],
                    configured_proof_search_workers=legacy[
                        "configured_proof_search_workers"
                    ],
                    total_wave_capacity=legacy["total_wave_capacity"],
                    class_capacities=legacy["class_capacities"],
                    aggregate_budget_enforced=legacy[
                        "aggregate_budget_enforced"
                    ],
                    initial_remaining_token_budget=legacy[
                        "initial_remaining_token_budget"
                    ],
                    initial_reserved_verification_budget=legacy[
                        "initial_reserved_verification_budget"
                    ],
                    candidate_generator_manifest_sha256=(
                        legacy["candidate_generator_manifest_sha256"]
                        if policy_version >= 5
                        else ""
                    ),
                    policy_version=policy_version,
                )

                self.assertEqual(
                    [],
                    parallel_admission_module.parallel_wave_admission_errors(
                        legacy
                    ),
                )

    def test_parallel_v3_trace_remains_valid_after_v4_upgrade(self) -> None:
        primary = {"mode": "prove", "target_id": "root", "route_id": ""}
        candidate = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "",
            "search_intent": "exact_theorem_search",
            "proof_obligation_id": "legacy-obligation",
        }
        _selected, trace = scheduler_module._admit_parallel_companion_candidates(
            primary,
            [candidate],
            problem={"parallel_branches": 3},
        )
        legacy = json.loads(json.dumps(trace))
        legacy["policy_version"] = 3
        legacy.pop("admission_search", None)
        actions = [primary, candidate]
        for row, action in zip(legacy["candidates"], actions):
            identity = parallel_admission_module.parallel_action_identity(
                action,
                action_class=str(row["action_class"]),
                policy_version=3,
            )
            row["semantic_identity"] = list(identity)
            if row["candidate_id"] != "parallel:primary":
                row["candidate_id"] = (
                    parallel_admission_module.parallel_candidate_id(
                        identity,
                        policy_version=3,
                    )
                )
        legacy_outcomes, _legacy_remaining = (
            parallel_admission_module.parallel_admission_outcomes(
                legacy["candidates"],
                total_capacity=legacy["total_wave_capacity"],
                class_capacities=legacy["class_capacities"],
                aggregate_budget_enforced=False,
                policy_version=3,
            )
        )
        for row in legacy["candidates"]:
            outcome = legacy_outcomes[row["candidate_id"]]
            row["disposition"] = outcome.disposition
            row["reason"] = outcome.reason
            row["outcome_code"] = outcome.outcome_code
            row["admitted_tokens"] = outcome.admitted_tokens
        legacy["selected_candidate_ids"] = [
            row["candidate_id"]
            for row in legacy["candidates"]
            if row["disposition"] in {"fixed_primary", "selected"}
        ]
        legacy["candidate_set_sha256"] = (
            parallel_admission_module.parallel_candidate_set_sha256(
                legacy["candidates"],
                policy_version=3,
            )
        )

        self.assertEqual(
            [],
            parallel_admission_module.parallel_wave_admission_errors(legacy),
        )
        primary_action, primary_trace = select_action_candidate(
            [
                ActionCandidate(
                    "base:legacy-wave",
                    "research",
                    primary,
                    1.0,
                )
            ],
            candidate_set_complete=True,
        )
        primary_action["decision_trace"] = bind_dispatched_action(
            primary_action, primary_trace
        )
        bound = scheduler_module._bind_primary_parallel_wave_decision(
            primary_action, legacy
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "legacy-v3-wave-telemetry",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            operation = run_metrics_operation(
                run_id="legacy-v3-wave-run",
                action=bound,
                session_plan={
                    "actor_role": "researcher",
                    "state_revision": 0,
                    "context_hash": "legacy-v3-wave-context",
                },
                usage_payload={"input_tokens": 0, "output_tokens": 0},
            )
            outcome = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [operation],
                    "rationale": "record a compatible in-flight v3 wave",
                },
                mode="prove",
            )
            self.assertFalse(outcome.accepted)
            self.assertIn(
                "prior durable scheduler dispatch",
                " ".join(outcome.errors),
            )

    def test_parallel_trace_validator_is_total_on_malformed_scalar_fields(self) -> None:
        primary = {"mode": "prove", "target_id": "root", "route_id": ""}
        candidate = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "",
            "search_intent": "exact_theorem_search",
            "proof_obligation_id": "malformed-trace-test",
        }
        _selected, valid = scheduler_module._admit_parallel_companion_candidates(
            primary,
            [candidate],
            problem={
                "parallel_branches": 3,
                "remaining_token_budget": 100_000,
                "reserved_verification_budget": 20_000,
            },
        )
        malformed_values = (None, True, False, "invalid", [], {}, -1, 1.5)
        for malformed in malformed_values:
            with self.subTest(top_level=repr(malformed)):
                self.assertIsInstance(
                    parallel_admission_module.parallel_wave_admission_errors(
                        malformed  # type: ignore[arg-type]
                    ),
                    list,
                )
        for field in tuple(valid):
            for malformed in malformed_values:
                with self.subTest(field=field, malformed=repr(malformed)):
                    trial = json.loads(json.dumps(valid))
                    trial[field] = malformed
                    errors = (
                        parallel_admission_module.parallel_wave_admission_errors(
                            trial
                        )
                    )
                    self.assertIsInstance(errors, list)
        for row_index in (0, 1):
            for field in tuple(valid["candidates"][row_index]):
                for malformed in malformed_values:
                    with self.subTest(
                        row=row_index,
                        field=field,
                        malformed=repr(malformed),
                    ):
                        trial = json.loads(json.dumps(valid))
                        trial["candidates"][row_index][field] = malformed
                        errors = (
                            parallel_admission_module.parallel_wave_admission_errors(
                                trial
                            )
                        )
                        self.assertIsInstance(errors, list)

    def test_parallel_dispatch_and_replay_share_one_policy_transition(self) -> None:
        primary = {"mode": "prove", "target_id": "root", "route_id": ""}
        candidate = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "",
            "search_intent": "exact_theorem_search",
            "proof_obligation_id": "shared-transition",
        }
        with mock.patch.object(
            scheduler_module,
            "parallel_admission_outcomes",
            wraps=parallel_admission_module.parallel_admission_outcomes,
        ) as dispatch_transition:
            _selected, trace = (
                scheduler_module._admit_parallel_companion_candidates(
                    primary,
                    [candidate],
                    problem={"parallel_branches": 3},
                )
            )
        self.assertEqual(1, dispatch_transition.call_count)

        with mock.patch.object(
            parallel_admission_module,
            "parallel_admission_outcomes",
            wraps=parallel_admission_module.parallel_admission_outcomes,
        ) as replay_transition:
            self.assertEqual(
                [],
                parallel_admission_module.parallel_wave_admission_errors(trace),
            )
        self.assertEqual(1, replay_transition.call_count)

    def test_parallel_wrapper_binds_the_exact_admitted_wave_row(self) -> None:
        primary_action, primary_trace = select_action_candidate(
            [
                ActionCandidate(
                    "base:primary",
                    "research",
                    {"mode": "reduce", "target_id": "root", "route_id": ""},
                    1.0,
                )
            ],
            candidate_set_complete=True,
        )
        primary_action["decision_trace"] = bind_dispatched_action(
            primary_action, primary_trace
        )
        selected, wave = scheduler_module._admit_parallel_companion_candidates(
            primary_action,
            [
                {
                    "mode": "retrieve",
                    "target_id": "root",
                    "route_id": "",
                    "search_intent": "exact_theorem_search",
                    "proof_obligation_id": "binding-test",
                }
            ],
            problem={"parallel_branches": 2},
        )
        companion = scheduler_module._bind_parallel_wave_decision(
            selected[0], wave
        )
        bound_primary = scheduler_module._bind_primary_parallel_wave_decision(
            primary_action, wave
        )
        self.assertEqual([], decision_trace_errors(companion["decision_trace"]))
        self.assertEqual([], decision_trace_errors(bound_primary["decision_trace"]))

        for field, malformed in (
            ("parallel_wave_candidate_id", "parallel:" + "f" * 24),
            ("parallel_wave_input_action_sha256", "0" * 64),
        ):
            with self.subTest(field=field):
                trial = json.loads(json.dumps(companion["decision_trace"]))
                trial[field] = malformed
                self.assertTrue(decision_trace_errors(trial))

        transplanted = json.loads(json.dumps(companion["decision_trace"]))
        transplanted["selected_candidate_id"] = "unrelated"
        transplanted["candidates"][0]["candidate_id"] = "unrelated"
        transplanted["candidate_set_sha256"] = candidate_rows_sha256(
            transplanted["candidates"]
        )
        self.assertTrue(
            any(
                "does not select its bound wave candidate" in error
                for error in decision_trace_errors(transplanted)
            )
        )

    def test_terminal_primary_cannot_claim_undispatched_companions(self) -> None:
        selected, trace = scheduler_module._admit_parallel_companion_candidates(
            {
                "mode": "stop_with_partial_results",
                "target_id": "root",
                "route_id": "",
                "budget": {"allowed": False, "requested_tokens": 0},
            },
            [
                {
                    "mode": "reduce",
                    "target_id": "lemma-a",
                    "route_id": "",
                }
            ],
            problem={"parallel_branches": 2},
        )

        self.assertEqual([], selected)
        self.assertEqual("rejected", trace["candidates"][1]["disposition"])
        self.assertEqual(
            "exclusive or terminal primary action cannot admit companions",
            trace["candidates"][1]["reason"],
        )
        self.assertEqual([], parallel_admission_module.parallel_wave_admission_errors(trace))

    def test_nonterminal_primary_requires_budget_authorization(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "not authorized by its budget"):
            scheduler_module._admit_parallel_companion_candidates(
                {
                    "mode": "reduce",
                    "target_id": "root",
                    "route_id": "",
                    "budget": {"allowed": False, "requested_tokens": 0},
                },
                [],
                problem={"parallel_branches": 2},
            )

    def test_parallel_wave_identifier_binds_snapshot_and_configuration(self) -> None:
        _selected, trace = scheduler_module._admit_parallel_companion_candidates(
            {"mode": "prove", "target_id": "root", "route_id": ""},
            [
                {
                    "mode": "retrieve",
                    "target_id": "root",
                    "route_id": "",
                    "search_intent": "exact_theorem_search",
                    "proof_obligation_id": "wave-binding",
                }
            ],
            problem={
                "parallel_branches": 3,
                "current_revision": 17,
                "proof_state_hash": "a" * 64,
                "run_provenance_hash": "b" * 64,
            },
        )
        self.assertEqual([], scheduler_module._parallel_wave_admission_errors(trace))
        for field, replacement in (
            ("state_revision", 18),
            ("proof_state_hash", "c" * 64),
            ("run_provenance_hash", "d" * 64),
            ("candidate_set_scope", "a different claimed generator scope"),
        ):
            with self.subTest(field=field):
                tampered = json.loads(json.dumps(trace))
                tampered[field] = replacement
                self.assertTrue(
                    any(
                        "does not bind its admission inputs" in error
                        for error in scheduler_module._parallel_wave_admission_errors(
                            tampered
                        )
                    )
                )

    def test_production_parallel_admission_requires_authenticated_snapshot(self) -> None:
        for field, value in (
            ("proof_state_hash", ""),
            ("run_provenance_hash", "not-a-digest"),
            ("current_revision", "0"),
        ):
            with self.subTest(field=field):
                problem_state = {
                    "current_revision": 0,
                    "proof_state_hash": "a" * 64,
                    "run_provenance_hash": "b" * 64,
                    field: value,
                }
                with self.assertRaisesRegex(
                    RuntimeError, "authenticated scheduler snapshot"
                ):
                    scheduler_module._admit_and_finalize_parallel_companions(
                        mock.sentinel.store,
                        {"mode": "reduce", "target_id": "root", "route_id": ""},
                        [],
                        _scheduler_state={"problem_state": problem_state},
                    )

    def test_typed_comparator_records_selection_and_every_supplied_rejection(self) -> None:
        base = {"mode": "prove", "target_id": "root"}
        forced = {"mode": "triage_routes", "target_id": "root"}
        selected, trace = select_action_candidate(
            [
                ActionCandidate("base", "proof", base, ordinal_priority=100.0),
                ActionCandidate(
                    "maintenance",
                    "maintenance",
                    forced,
                    ordinal_priority=1.0,
                    mandatory_constraint=True,
                ),
            ],
            candidate_set_complete=True,
        )
        self.assertEqual("triage_routes", selected["mode"])
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual(candidate_set_sha256([
            ActionCandidate("base", "proof", base, ordinal_priority=100.0),
            ActionCandidate(
                "maintenance",
                "maintenance",
                forced,
                ordinal_priority=1.0,
                mandatory_constraint=True,
            ),
        ]), trace["candidate_set_sha256"])
        self.assertEqual(
            {
                "candidate_id",
                "domain",
                "base_policy_trace_sha256",
                "policy_tier",
                "ordinal_priority",
                "comparison_action_sha256",
                "admissible",
                "mandatory_constraint",
                "admissibility_reason",
                "consecutive_deferrals",
                "deferral_limit",
                "disposition",
            },
            set(trace["candidates"][0]),
        )
        for redundant_field in (
            "mode",
            "target_id",
            "route_id",
            "scheduler_policy_id",
            "reason",
        ):
            self.assertNotIn(redundant_field, trace["candidates"][0])
        self.assertEqual("maintenance", trace["selected_candidate_id"])
        self.assertEqual(
            ["rejected_by_mandatory_constraint", "selected"],
            [row["disposition"] for row in trace["candidates"]],
        )
        self.assertTrue(
            all(len(row["comparison_action_sha256"]) == 64 for row in trace["candidates"])
        )
        enriched = {**selected, "host_enrichment": "recorded after comparison"}
        bound = bind_dispatched_action(enriched, trace)
        self.assertEqual(action_sha256(enriched), bound["dispatched_action_sha256"])
        self.assertTrue(bound["post_comparison_transformation"])

    def test_comparator_and_candidate_hash_are_generator_order_invariant(self) -> None:
        lower_id = ActionCandidate(
            "alpha", "research", {"mode": "prove", "target_id": "root"}, 4.0
        )
        higher_id = ActionCandidate(
            "omega", "research", {"mode": "reduce", "target_id": "root"}, 4.0
        )
        first, first_trace = select_action_candidate(
            [lower_id, higher_id], candidate_set_complete=True
        )
        second, second_trace = select_action_candidate(
            [higher_id, lower_id], candidate_set_complete=True
        )
        self.assertEqual("reduce", first["mode"])
        self.assertEqual(first, second)
        self.assertEqual(
            first_trace["candidate_set_sha256"],
            second_trace["candidate_set_sha256"],
        )
        self.assertEqual(64, len(first_trace["candidate_set_sha256"]))
        self.assertEqual(
            first_trace["candidate_set_sha256"],
            candidate_rows_sha256(first_trace["candidates"]),
        )
        inconsistent = json.loads(json.dumps(first_trace))
        inconsistent["selected_candidate_id"] = "alpha"
        self.assertTrue(decision_trace_errors(inconsistent))

    def test_every_materialized_nested_policy_trace_is_committed(self) -> None:
        first_action = {"mode": "prove", "target_id": "root"}
        second_action = {"mode": "reduce", "target_id": "lemma"}
        _, first_nested = select_action_candidate(
            [ActionCandidate("first:local", "local", first_action, 1.0)],
            candidate_set_complete=True,
        )
        _, second_nested = select_action_candidate(
            [ActionCandidate("second:local", "local", second_action, 1.0)],
            candidate_set_complete=True,
        )

        _, trace = select_action_candidate(
            [
                ActionCandidate("first", "stratum", first_action, 2.0),
                ActionCandidate("second", "stratum", second_action, 1.0),
            ],
            candidate_set_complete=True,
            nested_policy_traces={
                "first": first_nested,
                "second": second_nested,
            },
        )

        self.assertEqual(
            {"first", "second"}, set(trace["nested_policy_traces"])
        )
        self.assertNotIn("base_policy_trace", trace)
        self.assertEqual([], decision_trace_errors(trace))

        missing_unselected = json.loads(json.dumps(trace))
        missing_unselected["nested_policy_traces"].pop("second")
        self.assertTrue(decision_trace_errors(missing_unselected))

        tampered_unselected = json.loads(json.dumps(trace))
        tampered_unselected["nested_policy_traces"]["second"][
            "selected_candidate_id"
        ] = "forged"
        self.assertTrue(decision_trace_errors(tampered_unselected))

    def test_version_six_selected_nested_trace_remains_valid(self) -> None:
        action = {"mode": "prove", "target_id": "root"}
        _, nested = select_action_candidate(
            [ActionCandidate("inner", "local", action, 1.0)],
            candidate_set_complete=True,
        )
        _, trace = select_action_candidate(
            [ActionCandidate("outer", "stratum", action, 1.0)],
            candidate_set_complete=True,
            nested_policy_traces={"outer": nested},
        )
        trace["decision_policy_version"] = 6
        trace["base_policy_trace"] = nested
        trace.pop("nested_policy_traces")
        trace["candidate_set_sha256"] = candidate_rows_sha256(
            trace["candidates"], decision_policy_version=6
        )

        self.assertEqual([], decision_trace_errors(trace))

    def test_unselected_nested_stratum_contributes_deferral_history(self) -> None:
        first_action = {"mode": "prove", "target_id": "root"}
        second_action = {"mode": "reduce", "target_id": "lemma"}
        _, first_nested = select_action_candidate(
            [ActionCandidate("first:local", "local", first_action, 1.0)],
            candidate_set_complete=True,
        )
        _, second_nested = select_action_candidate(
            [ActionCandidate("second:local", "local", second_action, 1.0)],
            candidate_set_complete=True,
        )
        _, trace = select_action_candidate(
            [
                ActionCandidate("first", "stratum", first_action, 2.0),
                ActionCandidate("second", "stratum", second_action, 1.0),
            ],
            candidate_set_complete=True,
            nested_policy_traces={
                "first": first_nested,
                "second": second_nested,
            },
        )

        self.assertEqual(
            1,
            scheduler_module._consecutive_candidate_deferrals(
                {"recent_runs": [{"decision_trace": trace}]},
                "second:local",
            ),
        )

    def test_bounded_deferral_prevents_top_level_candidate_starvation(self) -> None:
        ordinarily_first = ActionCandidate(
            "high-priority",
            "research",
            {"mode": "prove", "target_id": "root"},
            100.0,
        )
        deferred = ActionCandidate(
            "continuously-admissible",
            "research",
            {"mode": "reduce", "target_id": "root"},
            1.0,
            consecutive_deferrals=3,
            deferral_limit=3,
        )
        selected, trace = select_action_candidate(
            [ordinarily_first, deferred], candidate_set_complete=True
        )
        self.assertEqual("reduce", selected["mode"])
        self.assertEqual("continuously-admissible", trace["selected_candidate_id"])
        self.assertEqual(
            "rejected_by_fairness_constraint", trace["candidates"][0]["disposition"]
        )

        mandatory = ActionCandidate(
            "hard-constraint",
            "verification",
            {"mode": "formalize", "target_id": "root"},
            0.0,
            mandatory_constraint=True,
        )
        selected, _ = select_action_candidate(
            [deferred, mandatory], candidate_set_complete=True
        )
        self.assertEqual("formalize", selected["mode"])

    def test_bounded_deferral_is_scoped_to_the_maximal_policy_tier(self) -> None:
        verification = ActionCandidate(
            "verification",
            "verification",
            {"mode": "prove", "target_id": "root"},
            1.0,
            policy_tier=300,
        )
        overdue_exploration = ActionCandidate(
            "overdue-exploration",
            "research",
            {"mode": "reduce", "target_id": "root"},
            1_000_000.0,
            policy_tier=100,
            consecutive_deferrals=20,
            deferral_limit=3,
        )
        selected, trace = select_action_candidate(
            [overdue_exploration, verification], candidate_set_complete=True
        )
        self.assertEqual("prove", selected["mode"])
        self.assertEqual("verification", trace["selected_candidate_id"])
        self.assertEqual(
            "rejected_by_policy_tier", trace["candidates"][0]["disposition"]
        )
        self.assertEqual([], decision_trace_errors(trace))

        peer = ActionCandidate(
            "verification-peer",
            "verification",
            {"mode": "formalize", "target_id": "root"},
            0.0,
            policy_tier=300,
            consecutive_deferrals=3,
            deferral_limit=3,
        )
        selected, trace = select_action_candidate(
            [verification, peer], candidate_set_complete=True
        )
        self.assertEqual("formalize", selected["mode"])
        self.assertEqual([], decision_trace_errors(trace))

    def test_hard_policy_exclusions_do_not_accumulate_fairness_counts(self) -> None:
        _, trace = select_action_candidate(
            [
                ActionCandidate(
                    "safety",
                    "repair",
                    {"mode": "audit_definitions", "target_id": "root"},
                    1.0,
                    policy_tier=100,
                    deferral_limit=3,
                ),
                ActionCandidate(
                    "exploration",
                    "research",
                    {"mode": "prove", "target_id": "root"},
                    100.0,
                    policy_tier=0,
                    deferral_limit=3,
                ),
            ],
            candidate_set_complete=True,
        )
        exploration = next(
            row
            for row in trace["candidates"]
            if row["candidate_id"] == "exploration"
        )
        self.assertEqual("rejected_by_policy_tier", exploration["disposition"])
        self.assertEqual(
            {},
            decision_policy_module.decision_deferral_state_after_trace({}, trace),
        )
        self.assertEqual(
            0,
            scheduler_module._consecutive_candidate_deferrals(
                {"recent_runs": [{"decision_trace": trace}]}, "exploration"
            ),
        )

    def test_generic_fairness_serves_a_stable_same_tier_cohort(self) -> None:
        deferral_limit = 3
        for population in range(1, 9):
            with self.subTest(population=population):
                counts: dict[str, int] = {}
                served: set[str] = set()
                for _round in range(deferral_limit + population):
                    candidates = [
                        ActionCandidate(
                            f"cohort:{index}",
                            "research",
                            {"mode": "prove", "target_id": f"lemma-{index}"},
                            float(population - index),
                            policy_tier=10,
                            consecutive_deferrals=counts.get(
                                f"cohort:{index}", 0
                            ),
                            deferral_limit=deferral_limit,
                        )
                        for index in range(population)
                    ]
                    _action, trace = select_action_candidate(
                        candidates, candidate_set_complete=True
                    )
                    served.add(str(trace["selected_candidate_id"]))
                    counts = decision_policy_module.decision_deferral_state_after_trace(
                        counts, trace
                    )
                self.assertEqual(
                    {f"cohort:{index}" for index in range(population)}, served
                )

    def test_base_policy_classifier_recognizes_recovery_contract_fields(self) -> None:
        for field in (
            "duplicate_work_guard",
            "route_triage_required",
            "frontier_pressure",
            "stream_stall_recovery_required",
            "no_content_guard",
            "no_content_research_guard",
            "strategy_advisor_required",
        ):
            self.assertEqual(
                scheduler_module.POLICY_TIER_RECOVERY,
                scheduler_module._base_action_policy_tier(
                    {"mode": "reduce", field: True}
                ),
                field,
            )

    def test_declarative_policy_registry_is_consistent_and_safety_dominates(self) -> None:
        self.assertEqual([], scheduler_module._action_policy_registry_errors())
        self.assertEqual(
            [],
            decision_policy_module.decision_policy_semantic_errors(),
        )
        self.assertEqual(
            set(decision_policy_module.SUPPORTED_DECISION_POLICY_VERSIONS),
            set(decision_policy_module.DECISION_POLICY_SEMANTIC_SHA256),
        )
        self.assertEqual(
            len(decision_policy_module.SUPPORTED_DECISION_POLICY_VERSIONS),
            len(set(decision_policy_module.DECISION_POLICY_SEMANTIC_SHA256.values())),
            "each generic policy epoch must have a distinct executable trace contract",
        )
        self.assertEqual(
            scheduler_module.POLICY_TIER_SAFETY,
            scheduler_module._base_action_policy_tier(
                {
                    "mode": "reduce",
                    "strategy_advisor_required": True,
                    "root_revision_required": True,
                }
            ),
        )

    def test_semantic_commitment_detects_replay_contract_mutation(self) -> None:
        with mock.patch.object(
            decision_policy_module,
            "CANDIDATE_GENERATOR_BOUND_DECISION_POLICY_VERSION",
            7,
        ):
            errors = decision_policy_module.decision_policy_semantic_errors()
        self.assertTrue(errors)
        self.assertTrue(
            any("changed without a new version" in error for error in errors),
            errors,
        )

    def test_parallel_wave_admission_rejects_same_claim_certification_race(self) -> None:
        primary = {
            "mode": "prove",
            "target_id": "lemma-a",
            "route_id": "route-a-1",
            "search_intent": "verify_ready_route",
        }
        candidates = [
            {
                "mode": "prove",
                "target_id": "lemma-a",
                "route_id": "route-a-2",
                "search_intent": "verify_ready_route",
            },
            {
                "mode": "prove",
                "target_id": "lemma-b",
                "route_id": "route-b",
                "search_intent": "verify_ready_route",
            },
        ]

        selected, trace = scheduler_module._admit_parallel_companion_candidates(
            primary,
            candidates,
            problem={"parallel_branches": 3},
        )

        self.assertEqual(["route-b"], [item["route_id"] for item in selected])
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual(64, len(trace["candidate_set_sha256"]))
        self.assertEqual(
            action_sha256(primary),
            trace["candidates"][0]["comparison_action_sha256"],
        )
        dispositions = {
            row["route_id"]: row["disposition"]
            for row in trace["candidates"][1:]
        }
        self.assertEqual("rejected", dispositions["route-a-2"])
        self.assertEqual("selected", dispositions["route-b"])
        self.assertIn(
            "same conclusion claim",
            next(
                row["reason"]
                for row in trace["candidates"]
                if row.get("route_id") == "route-a-2"
            ),
        )

    def test_parallel_exact_obligations_keep_distinct_stable_identities(self) -> None:
        primary = {"mode": "prove", "target_id": "root", "route_id": ""}
        candidates = [
            {
                "mode": "retrieve",
                "target_id": "root",
                "route_id": "",
                "search_intent": "exact_theorem_search",
                "debt_id": obligation_id,
                "proof_obligation_id": obligation_id,
            }
            for obligation_id in ("citation-a", "citation-b")
        ]

        _selected, trace = scheduler_module._admit_parallel_companion_candidates(
            primary, candidates, problem={"parallel_branches": 3}
        )
        reversed_selected, reversed_trace = (
            scheduler_module._admit_parallel_companion_candidates(
                primary, list(reversed(candidates)), problem={"parallel_branches": 3}
            )
        )
        candidate_ids = {
            row["candidate_id"] for row in trace["candidates"][1:]
        }
        reversed_ids = {
            row["candidate_id"] for row in reversed_trace["candidates"][1:]
        }

        self.assertEqual(2, len(candidate_ids))
        self.assertEqual(candidate_ids, reversed_ids)
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual(
            trace["candidate_set_sha256"],
            reversed_trace["candidate_set_sha256"],
        )
        self.assertEqual(
            trace["selected_candidate_ids"],
            reversed_trace["selected_candidate_ids"],
        )
        self.assertEqual(
            [item["proof_obligation_id"] for item in _selected],
            [item["proof_obligation_id"] for item in reversed_selected],
        )
        self.assertEqual(
            [], scheduler_module._parallel_wave_admission_errors(trace)
        )
        rejected = [
            row
            for row in trace["candidates"]
            if row["disposition"] == "rejected"
        ]
        self.assertEqual(1, len(rejected))
        self.assertIn("literature capacity", rejected[0]["reason"])

        tampered = json.loads(json.dumps(trace))
        tampered["candidates"][1]["admission_priority"] -= 1
        self.assertTrue(
            scheduler_module._parallel_wave_admission_errors(tampered)
        )
        tampered = json.loads(json.dumps(trace))
        tampered["selected_candidate_ids"] = ["parallel:primary"]
        self.assertTrue(
            scheduler_module._parallel_wave_admission_errors(tampered)
        )
        tampered = json.loads(json.dumps(trace))
        selected_row = next(
            row
            for row in tampered["candidates"][1:]
            if row["disposition"] == "selected"
        )
        rejected_row = next(
            row
            for row in tampered["candidates"][1:]
            if row["disposition"] == "rejected"
        )
        selected_row.update(
            disposition="rejected",
            reason="literature capacity reached",
            outcome_code="class_capacity_queue",
            admitted_tokens=0,
        )
        rejected_row.update(
            disposition="selected",
            reason=(
                "admitted by explicit priority with canonical "
                "semantic-identity tie-break"
            ),
            outcome_code="selected_priority",
            admitted_tokens=0,
        )
        tampered["selected_candidate_ids"] = [
            "parallel:primary",
            rejected_row["candidate_id"],
        ]
        self.assertTrue(
            any(
                "not policy-optimal" in error
                for error in scheduler_module._parallel_wave_admission_errors(
                    tampered
                )
            )
        )
        tampered = json.loads(json.dumps(trace))
        tampered["total_wave_capacity"] = "invalid"
        self.assertTrue(
            scheduler_module._parallel_wave_admission_errors(tampered)
        )

    def test_parallel_equal_priority_candidate_is_served_after_bounded_deferral(self) -> None:
        primary = {"mode": "prove", "target_id": "root", "route_id": ""}
        candidates = [
            {
                "mode": "retrieve",
                "target_id": "root",
                "route_id": "",
                "search_intent": "exact_theorem_search",
                "proof_obligation_id": obligation_id,
            }
            for obligation_id in ("citation-a", "citation-b")
        ]
        first_selected, first_trace = (
            scheduler_module._admit_parallel_companion_candidates(
                primary,
                candidates,
                problem={"parallel_branches": 3},
            )
        )
        first_obligation = first_selected[0]["proof_obligation_id"]
        deferred_obligation = next(
            item["proof_obligation_id"]
            for item in candidates
            if item["proof_obligation_id"] != first_obligation
        )
        deferred_candidate_id = next(
            row["candidate_id"]
            for row in first_trace["candidates"]
            if row["disposition"] == "rejected"
        )
        repeated_copy = {
            "decision_trace": {
                "parallel_wave_admission": first_trace
            }
        }
        self.assertEqual(
            {deferred_candidate_id: 1},
            scheduler_module._parallel_candidate_deferral_counts(
                [repeated_copy, {"decision_trace": {}}, repeated_copy] * 3,
                [deferred_candidate_id],
            ),
            "multiple session records from one wave must count once even across a sidecar run",
        )
        recent_runs = []
        for index in range(
            scheduler_module.PARALLEL_WAVE_DEFERRAL_LIMIT
        ):
            historical_trace = json.loads(json.dumps(first_trace))
            for row in historical_trace["candidates"][1:]:
                if parallel_admission_module.parallel_outcome_is_fairness_eligible(
                    row
                ):
                    row["consecutive_deferrals"] = index
            _rebind_parallel_wave_snapshot(
                historical_trace,
                state_revision=index + 1,
            )
            recent_runs.insert(
                0,
                {
                    "decision_trace": {
                        "parallel_wave_admission": historical_trace
                    }
                }
            )

        selected, trace = (
            scheduler_module._admit_parallel_companion_candidates(
                primary,
                candidates,
                problem={"parallel_branches": 3},
                recent_runs=recent_runs,
            )
        )

        self.assertEqual(
            deferred_obligation, selected[0]["proof_obligation_id"]
        )
        selected_row = next(
            row
            for row in trace["candidates"]
            if row["disposition"] == "selected"
        )
        self.assertEqual(
            scheduler_module.PARALLEL_WAVE_DEFERRAL_LIMIT,
            selected_row["consecutive_deferrals"],
        )
        self.assertEqual(
            "selected_fairness_search", selected_row["outcome_code"]
        )
        self.assertIn("max-weight fairness", selected_row["reason"])
        self.assertEqual(
            [], scheduler_module._parallel_wave_admission_errors(trace)
        )

        budget_variants = []
        for requested_tokens in (20_000, 30_000):
            _selected, variant_trace = (
                scheduler_module._admit_parallel_companion_candidates(
                    primary,
                    [
                        {
                            **candidates[0],
                            "budget": {
                                "allowed": True,
                                "requested_tokens": requested_tokens,
                            },
                        }
                    ],
                    problem={"parallel_branches": 3},
                )
            )
            budget_variants.append(variant_trace)
        self.assertEqual(
            budget_variants[0]["candidates"][1]["candidate_id"],
            budget_variants[1]["candidates"][1]["candidate_id"],
            "fairness identity must survive resource-allocation changes",
        )
        self.assertNotEqual(
            budget_variants[0]["candidate_set_sha256"],
            budget_variants[1]["candidate_set_sha256"],
            "the exact comparison action must still be committed",
        )

    def test_parallel_v7_identity_distinguishes_unregistered_action_fields(self) -> None:
        primary = {"mode": "prove", "target_id": "root", "route_id": ""}
        candidates = [
            {
                "mode": "retrieve",
                "target_id": "root",
                "route_id": "",
                "search_intent": "exact_theorem_search",
                "proof_obligation_id": "citation-a",
                "query": query,
            }
            for query in ("first incompatible query", "second incompatible query")
        ]

        selected, trace = scheduler_module._admit_parallel_companion_candidates(
            primary,
            candidates,
            problem={"parallel_branches": 3},
        )
        reverse_selected, reverse_trace = (
            scheduler_module._admit_parallel_companion_candidates(
                primary,
                list(reversed(candidates)),
                problem={"parallel_branches": 3},
            )
        )

        candidate_rows = trace["candidates"][1:]
        self.assertEqual(2, len({row["candidate_id"] for row in candidate_rows}))
        self.assertTrue(all(len(row["semantic_identity"]) == 8 for row in candidate_rows))
        self.assertEqual(
            [row["query"] for row in selected],
            [row["query"] for row in reverse_selected],
        )
        self.assertEqual(
            trace["selected_candidate_ids"],
            reverse_trace["selected_candidate_ids"],
        )
        operationally_decorated = {
            **candidates[0],
            "display_mode": "researcher_prove",
            "integration_parallel_safe": True,
            "parallel_companion": True,
            "parallel_companion_index": 4,
            "scheduler_policy_id": "derived-only",
        }
        self.assertEqual(
            parallel_admission_module.parallel_action_identity(
                candidates[0], action_class="literature"
            ),
            parallel_admission_module.parallel_action_identity(
                operationally_decorated, action_class="literature"
            ),
        )
        self.assertNotEqual(
            parallel_admission_module.parallel_action_identity(
                {**candidates[0], "reason": "search for theorem A"},
                action_class="literature",
            ),
            parallel_admission_module.parallel_action_identity(
                {**candidates[0], "reason": "search for theorem B"},
                action_class="literature",
            ),
            "prompt-bearing task text must participate in semantic identity",
        )
        v6_identity = parallel_admission_module.parallel_action_identity(
            candidates[0],
            action_class="literature",
            policy_version=6,
        )
        v6_candidate_id = parallel_admission_module.parallel_candidate_id(
            v6_identity,
            policy_version=6,
        )
        _migrated_selected, migrated_trace = (
            scheduler_module._admit_parallel_companion_candidates(
                primary,
                [candidates[0]],
                problem={"parallel_branches": 3},
                durable_deferral_counts={v6_candidate_id: 2},
            )
        )
        migrated_row = migrated_trace["candidates"][1]
        self.assertNotEqual(v6_candidate_id, migrated_row["candidate_id"])
        self.assertEqual(
            0,
            migrated_row["consecutive_deferrals"],
            "an ambiguous pre-v7 counter must not be assigned to a newly distinguished task",
        )
        with self.assertRaisesRegex(ValueError, "string names"):
            parallel_admission_module.parallel_action_identity(
                {**candidates[0], 1: "non-string-field"},
                action_class="literature",
            )

    def test_parallel_bottleneck_generator_materializes_every_exact_search(self) -> None:
        exact_searches = [
            {
                "mode": "retrieve",
                "target_id": "root",
                "route_id": "",
                "debt_id": obligation_id,
                "proof_obligation_id": obligation_id,
                "search_intent": "exact_theorem_search",
            }
            for obligation_id in ("citation-a", "citation-b")
        ]
        inactive = mock.Mock(return_value=None)
        forbidden_fallback = mock.Mock(
            side_effect=AssertionError(
                "lower-priority verification generators must be lazy"
            )
        )
        with mock.patch.multiple(
            scheduler_module,
            _support_lemma_precheck_actions=forbidden_fallback,
            _advisor_evidence_synthesis_action=inactive,
            _verifier_candidate_actions=forbidden_fallback,
            _verifier_blocked_citation_actions=mock.Mock(
                return_value=exact_searches
            ),
            _counterexample_companion_action=inactive,
        ):
            actions = scheduler_module._plan_parallel_companion_actions(
                mock.Mock(),
                {
                    "mode": "prove",
                    "target_id": "root",
                    "route_id": "",
                    "bottleneck_lock_required": True,
                },
                _scheduler_state={
                    "problem_state": {"parallel_branches": 3},
                    "claims": [],
                    "routes": [],
                    "inferences": [],
                    "debts": [],
                    "recent_runs": [],
                },
            )

        self.assertEqual(
            ["citation-a", "citation-b"],
            [action["proof_obligation_id"] for action in actions],
        )
        self.assertTrue(
            all(
                action["_candidate_generator_id"]
                == "exact_support_theorem_search"
                for action in actions
            )
        )
        forbidden_fallback.assert_not_called()

    def test_parallel_decomposition_preserves_every_productive_phase(self) -> None:
        support = {
            "mode": "prove",
            "target_id": "support-lemma",
            "route_id": "support-route",
        }
        decomposition = {
            "mode": "prove",
            "target_id": "decomposition-branch",
            "route_id": "",
            "search_intent": "parallel_decomposition_branch",
        }
        advisor = {
            "mode": "triage_routes",
            "target_id": "root",
            "route_id": "",
        }
        verifier = mock.Mock(
            side_effect=AssertionError(
                "peer verification must not run while support prechecks exist"
            )
        )
        with mock.patch.multiple(
            scheduler_module,
            _support_lemma_precheck_actions=mock.Mock(return_value=[support]),
            _verifier_candidate_actions=verifier,
            _advisor_evidence_synthesis_action=mock.Mock(return_value=advisor),
            _parallel_decomposition_companion_actions=mock.Mock(
                return_value=[decomposition]
            ),
        ):
            actions = scheduler_module._plan_parallel_companion_actions(
                mock.Mock(),
                {"mode": "prove", "target_id": "root", "route_id": ""},
                _scheduler_state={
                    "problem_state": {"parallel_branches": 4},
                    "claims": [],
                    "routes": [],
                    "inferences": [],
                    "debts": [],
                    "recent_runs": [],
                },
            )

        self.assertEqual(
            [
                "support_theorem_precheck",
                "parallel_decomposition",
                "advisor_synthesis",
            ],
            [action["_candidate_generator_id"] for action in actions],
        )
        self.assertEqual(
            ["support-lemma", "decomposition-branch", "root"],
            [action["target_id"] for action in actions],
        )
        verifier.assert_not_called()

    def test_parallel_retrieval_preserves_support_precheck_and_advisor(self) -> None:
        support = {
            "mode": "prove",
            "target_id": "support-lemma",
            "route_id": "support-route",
        }
        advisor = {
            "mode": "triage_routes",
            "target_id": "root",
            "route_id": "",
        }
        forbidden = mock.Mock(
            side_effect=AssertionError(
                "lower-priority retrieval companion must remain lazy"
            )
        )
        with mock.patch.multiple(
            scheduler_module,
            _support_lemma_precheck_actions=mock.Mock(return_value=[support]),
            _verifier_candidate_actions=forbidden,
            _advisor_evidence_synthesis_action=mock.Mock(return_value=advisor),
            _parallel_decomposition_companion_actions=mock.Mock(return_value=[]),
            _researcher_candidate_action=forbidden,
        ):
            actions = scheduler_module._plan_parallel_companion_actions(
                mock.Mock(),
                {"mode": "retrieve", "target_id": "root", "route_id": ""},
                _scheduler_state={
                    "problem_state": {"parallel_branches": 3},
                    "claims": [],
                    "routes": [],
                    "inferences": [],
                    "debts": [],
                    "recent_runs": [],
                },
            )

        self.assertEqual(
            ["support_theorem_precheck", "advisor_synthesis"],
            [action["_candidate_generator_id"] for action in actions],
        )
        forbidden.assert_not_called()

    def test_parallel_retrieval_preserves_ready_verifier_and_advisor(self) -> None:
        verifier = {
            "mode": "prove",
            "target_id": "ready-lemma",
            "route_id": "ready-route",
            "search_intent": "verify_ready_route",
        }
        advisor = {
            "mode": "triage_routes",
            "target_id": "root",
            "route_id": "",
        }
        researcher = mock.Mock(
            side_effect=AssertionError(
                "research generation must remain lazy while verification is ready"
            )
        )
        with mock.patch.multiple(
            scheduler_module,
            _support_lemma_precheck_actions=mock.Mock(return_value=[]),
            _verifier_candidate_actions=mock.Mock(return_value=[verifier]),
            _advisor_evidence_synthesis_action=mock.Mock(return_value=advisor),
            _parallel_decomposition_companion_actions=mock.Mock(return_value=[]),
            _researcher_candidate_action=researcher,
        ):
            actions = scheduler_module._plan_parallel_companion_actions(
                mock.Mock(),
                {"mode": "retrieve", "target_id": "root", "route_id": ""},
                _scheduler_state={
                    "problem_state": {"parallel_branches": 3},
                    "claims": [],
                    "routes": [],
                    "inferences": [],
                    "debts": [],
                    "recent_runs": [],
                },
            )

        self.assertEqual(
            ["peer_verification", "advisor_synthesis"],
            [action["_candidate_generator_id"] for action in actions],
        )
        researcher.assert_not_called()

    def test_parallel_verifier_generator_defers_capacity_to_admission(self) -> None:
        verifiers = [
            {
                "mode": "prove",
                "target_id": f"lemma-{suffix}",
                "route_id": f"route-{suffix}",
                "search_intent": "verify_ready_route",
            }
            for suffix in ("a", "b", "c")
        ]
        verifier_generator = mock.Mock(return_value=verifiers)
        with mock.patch.object(
            scheduler_module, "_verifier_candidate_actions", verifier_generator
        ):
            actions = scheduler_module._plan_parallel_companion_actions(
                mock.Mock(),
                {
                    "mode": "prove",
                    "target_id": "root",
                    "route_id": "route-root",
                    "search_intent": "verify_ready_route",
                },
                _scheduler_state={
                    "problem_state": {"parallel_branches": 2},
                    "claims": [],
                    "routes": [],
                    "inferences": [],
                    "debts": [],
                    "recent_runs": [],
                },
            )

        self.assertEqual(
            verifiers,
            [
                {
                    key: value
                    for key, value in action.items()
                    if key != "_candidate_generator_id"
                }
                for action in actions
            ],
        )
        self.assertTrue(
            all(
                action["_candidate_generator_id"] == "peer_verification"
                for action in actions
            )
        )
        self.assertNotIn("limit", verifier_generator.call_args.kwargs)

        with mock.patch.object(
            scheduler_module,
            "_verifier_candidate_actions",
            return_value=verifiers,
        ):
            zero_capacity_actions = (
                scheduler_module._plan_parallel_companion_actions(
                    mock.Mock(),
                    {
                        "mode": "prove",
                        "target_id": "root",
                        "route_id": "route-root",
                        "search_intent": "verify_ready_route",
                    },
                    _scheduler_state={
                        "problem_state": {"parallel_branches": 0},
                        "claims": [],
                        "routes": [],
                        "inferences": [],
                        "debts": [],
                        "recent_runs": [],
                    },
                )
            )
        self.assertEqual(
            verifiers,
            [
                {
                    key: value
                    for key, value in action.items()
                    if key != "_candidate_generator_id"
                }
                for action in zero_capacity_actions
            ],
            "capacity zero must produce rejected trace rows, not hide candidates",
        )

    def test_parallel_branch_normalization_is_total_on_nonfinite_input(self) -> None:
        self.assertEqual(
            0, scheduler_module.normalize_parallel_branches(float("inf"))
        )
        self.assertEqual(
            0, scheduler_module.normalize_parallel_branches(float("-inf"))
        )
        self.assertEqual(
            0, scheduler_module.normalize_parallel_branches(float("nan"))
        )

    def test_parallel_wave_total_and_role_capacities_are_explicit(self) -> None:
        primary = {"mode": "retrieve", "target_id": "root", "route_id": ""}
        candidates = [
            {"mode": "prove", "target_id": "lemma-a", "route_id": ""},
            {"mode": "refute", "target_id": "lemma-b", "route_id": ""},
            {"mode": "triage_routes", "target_id": "root", "route_id": ""},
            {
                "mode": "prove",
                "target_id": "lemma-c",
                "route_id": "route-c",
                "search_intent": "verify_ready_route",
            },
        ]

        selected, trace = scheduler_module._admit_parallel_companion_candidates(
            primary,
            candidates,
            problem={"parallel_branches": 2},
        )

        self.assertEqual(3, len(selected))
        self.assertEqual(4, trace["total_wave_capacity"])
        self.assertEqual(
            "total wave capacity reached",
            trace["candidates"][-1]["reason"],
        )

    def test_parallel_wave_token_grants_do_not_overcommit_the_allocation(self) -> None:
        primary = {
            "mode": "prove",
            "target_id": "root",
            "route_id": "",
            "budget": {"allowed": True, "requested_tokens": 60_000},
        }
        candidates = [
            {
                "mode": "refute",
                "target_id": "root",
                "route_id": "",
                "budget": {"allowed": True, "requested_tokens": 60_000},
            },
            {
                "mode": "prove",
                "target_id": "lemma",
                "route_id": "route-lemma",
                "search_intent": "verify_ready_route",
                "budget": {"allowed": True, "requested_tokens": 60_000},
            },
        ]

        selected, trace = scheduler_module._admit_parallel_companion_candidates(
            primary,
            candidates,
            problem={
                "parallel_branches": 3,
                "remaining_token_budget": 150_000,
                "reserved_verification_budget": 50_000,
            },
        )

        grants = {
            action["mode"]: action["budget"]["requested_tokens"]
            for action in selected
        }
        self.assertEqual({"refute": 40_000, "prove": 50_000}, grants)
        selected_by_mode = {action["mode"]: action for action in selected}
        self.assertTrue(
            selected_by_mode["refute"]["budget"]["wave_budget_adjusted"]
        )
        self.assertTrue(
            selected_by_mode["prove"]["budget"]["wave_budget_adjusted"]
        )
        self.assertEqual(150_000, trace["admitted_token_budget"])
        self.assertEqual(0, trace["remaining_uncommitted_token_budget"])
        self.assertTrue(trace["aggregate_budget_enforced"])

    def test_rejected_unprotected_work_returns_reserved_tokens_to_verification(self) -> None:
        primary = {
            "mode": "prove",
            "target_id": "root",
            "route_id": "route-root",
            "budget": {"allowed": True, "requested_tokens": 60_000},
        }
        candidates = [
            {
                "mode": "prove",
                "target_id": "lemma",
                "route_id": "route-lemma",
                "search_intent": "verify_ready_route",
                "budget": {"allowed": True, "requested_tokens": 60_000},
            },
            {
                "mode": "reduce",
                "target_id": "root",
                "route_id": "route-root",
                "search_intent": "conflicting_research",
                "budget": {"allowed": True, "requested_tokens": 40_000},
            },
        ]

        selected, trace = scheduler_module._admit_parallel_companion_candidates(
            primary,
            candidates,
            problem={
                "parallel_branches": 3,
                "remaining_token_budget": 150_000,
                "reserved_verification_budget": 50_000,
            },
        )

        self.assertEqual(1, len(selected))
        self.assertEqual(60_000, selected[0]["budget"]["requested_tokens"])
        self.assertNotIn("wave_budget_adjusted", selected[0]["budget"])
        self.assertEqual(30_000, trace["remaining_uncommitted_token_budget"])
        rejected = [
            row for row in trace["candidates"]
            if row["disposition"] == "rejected"
        ]
        self.assertEqual(1, len(rejected))
        self.assertIn("same proof route", rejected[0]["reason"])

    def test_parallel_v7_reserves_only_structurally_consumable_future_demand(self) -> None:
        primary = {
            "mode": "triage_routes",
            "target_id": "primary",
            "route_id": "",
            "budget": {"allowed": True, "requested_tokens": 0},
        }

        cases = {
            "unauthorized": {
                "candidate": {
                    "mode": "reduce",
                    "target_id": "other",
                    "route_id": "other-route",
                    "budget": {"allowed": False, "requested_tokens": 20_000},
                },
                "verifier_target": "lemma",
            },
            "conflicting": {
                "candidate": {
                    "mode": "reduce",
                    "target_id": "lemma",
                    "route_id": "research-route",
                    "budget": {"allowed": True, "requested_tokens": 20_000},
                },
                "verifier_target": "lemma",
            },
        }
        for label, case in cases.items():
            with self.subTest(label=label):
                verifier = {
                    "mode": "prove",
                    "target_id": case["verifier_target"],
                    "route_id": "verification-route",
                    "budget": {"allowed": True, "requested_tokens": 20_000},
                }
                selected, trace = (
                    scheduler_module._admit_parallel_companion_candidates(
                        primary,
                        [case["candidate"], verifier],
                        problem={
                            "parallel_branches": 2,
                            "remaining_token_budget": 20_000,
                            "reserved_verification_budget": 0,
                        },
                        durable_deferral_counts={},
                    )
                )
                self.assertEqual(["prove"], [row["mode"] for row in selected])
                self.assertEqual(20_000, selected[0]["budget"]["requested_tokens"])
                self.assertEqual(0, trace["remaining_uncommitted_token_budget"])
                self.assertEqual(
                    [],
                    parallel_admission_module.parallel_wave_admission_errors(trace),
                )
                if label == "conflicting":
                    legacy_outcomes, legacy_remaining = (
                        parallel_admission_module.parallel_admission_outcomes(
                            trace["candidates"],
                            total_capacity=trace["total_wave_capacity"],
                            class_capacities=trace["class_capacities"],
                            aggregate_budget_enforced=True,
                            initial_remaining_token_budget=20_000,
                            initial_reserved_verification_budget=0,
                            policy_version=6,
                        )
                    )
                    legacy_by_mode = {
                        row["mode"]: legacy_outcomes[row["candidate_id"]]
                        for row in trace["candidates"][1:]
                    }
                    self.assertEqual(
                        "aggregate_allocation_queue",
                        legacy_by_mode["prove"].outcome_code,
                    )
                    self.assertEqual("selected", legacy_by_mode["reduce"].disposition)
                    self.assertEqual(0, legacy_remaining)

    def test_parallel_v7_demand_projection_respects_wave_capacity(self) -> None:
        primary = {
            "mode": "triage_routes",
            "target_id": "primary",
            "route_id": "",
            "budget": {"allowed": True, "requested_tokens": 0},
        }
        verifier = {
            "mode": "prove",
            "target_id": "verification-target",
            "route_id": "verification-route",
            "budget": {"allowed": True, "requested_tokens": 10_000},
        }
        research = [
            {
                "mode": "reduce",
                "target_id": f"research-{index}",
                "route_id": f"research-route-{index}",
                "budget": {"allowed": True, "requested_tokens": 10_000},
            }
            for index in range(3)
        ]

        selected, trace = scheduler_module._admit_parallel_companion_candidates(
            primary,
            [*research, verifier],
            problem={
                "parallel_branches": 2,
                "remaining_token_budget": 30_000,
                "reserved_verification_budget": 0,
            },
            durable_deferral_counts={},
        )

        self.assertEqual(3, len(selected))
        self.assertEqual({"prove", "reduce"}, {row["mode"] for row in selected})
        self.assertEqual(0, trace["remaining_uncommitted_token_budget"])
        rejected = [
            row for row in trace["candidates"] if row["disposition"] == "rejected"
        ]
        self.assertEqual(1, len(rejected))
        self.assertEqual("total_capacity_queue", rejected[0]["outcome_code"])

    def test_parallel_wave_rejects_unauthorized_and_nonviable_budgets(self) -> None:
        primary = {
            "mode": "prove",
            "target_id": "root",
            "route_id": "",
            "budget": {"allowed": True, "requested_tokens": 60_000},
        }
        candidates = [
            {
                "mode": "prove",
                "target_id": "lemma",
                "route_id": "route-lemma",
                "search_intent": "verify_ready_route",
                "budget": {"allowed": True, "requested_tokens": 20_000},
            },
            {
                "mode": "reduce",
                "target_id": "other-lemma",
                "route_id": "route-other",
                "budget": {"allowed": False, "requested_tokens": 0},
            },
        ]

        selected, trace = (
            scheduler_module._admit_parallel_companion_candidates(
                primary,
                candidates,
                problem={
                    "parallel_branches": 3,
                    "remaining_token_budget": 65_000,
                    "reserved_verification_budget": 5_000,
                },
            )
        )

        self.assertEqual([], selected)
        reasons = {
            row["target_id"]: row["reason"]
            for row in trace["candidates"][1:]
        }
        self.assertIn("minimum useful step size", reasons["lemma"])
        self.assertEqual(
            "candidate budget does not authorize dispatch",
            reasons["other-lemma"],
        )
        self.assertEqual(
            [], scheduler_module._parallel_wave_admission_errors(trace)
        )

    def test_strict_verifier_can_use_the_protected_verification_reserve(self) -> None:
        problem = {
            "remaining_token_budget": 50_000,
            "reserved_verification_budget": 50_000,
        }

        budget = scheduler_module._strict_verifier_budget(problem, None)

        self.assertTrue(budget["allowed"])
        self.assertEqual(50_000, budget["requested_tokens"])
        self.assertEqual("strict_informal_verification", budget["policy"])

        provisional = budget_module.plan_step_budget(problem, "prove")
        self.assertFalse(provisional["allowed"])
        self.assertNotIn("_desired_tokens", provisional)
        self.assertEqual(200_000, provisional["request_limit_tokens"])
        verifier_action = scheduler_module._action(
            "prove",
            "root",
            "route-root",
            "strictly verify the completed route",
            provisional,
        )
        self.assertEqual("prove", verifier_action["mode"])
        self.assertTrue(verifier_action["budget"]["allowed"])
        self.assertEqual(50_000, verifier_action["budget"]["requested_tokens"])
        self.assertEqual(50_000, verifier_action["budget"]["spendable_tokens"])
        direct_action = scheduler_module._action(
            "prove",
            "root",
            "",
            "construct a direct proof",
            provisional,
        )
        self.assertEqual("stop_with_partial_results", direct_action["mode"])

    def test_strict_verifier_fails_closed_below_minimum_useful_budget(self) -> None:
        budget = scheduler_module._strict_verifier_budget(
            {
                "remaining_token_budget": 9_999,
                "reserved_verification_budget": 9_999,
            },
            None,
        )

        self.assertFalse(budget["allowed"])
        self.assertEqual(9_999, budget["requested_tokens"])
        self.assertIn("below the minimum useful", budget["reason"])

    def test_strict_verifier_usage_is_charged_against_the_protected_reserve(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "strict-verifier-reserve-accounting",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem(
                "The root theorem holds.",
                total_token_budget=100_000,
                reserved_verification_budget=80_000,
            )
            outcome = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "record_run_metrics",
                            "run_id": "strict-reserve-run",
                            "actor_role": "strict_informal_verifier",
                            "mode": "prove",
                            "target_id": "root",
                            "state_revision": 0,
                            "context_revision": 0,
                            "budget_requested": 30_000,
                            "total_tokens": 30_000,
                            "status": "completed",
                        }
                    ],
                    "rationale": "record strict verification usage",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with store.connect() as conn:
                problem = store.get_problem_row(conn)
                run = dict(
                    conn.execute(
                        "SELECT budget_overrun_tokens FROM runs WHERE run_id = ?",
                        ("strict-reserve-run",),
                    ).fetchone()
                )

        self.assertEqual(70_000, problem["remaining_token_budget"])
        self.assertEqual(0, run["budget_overrun_tokens"])

    def test_parallel_companions_use_one_loaded_scheduler_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "parallel-single-snapshot",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            primary = next_action(store, web_search="live")
            with mock.patch.object(
                store,
                "get_scheduler_state",
                wraps=store.get_scheduler_state,
            ) as state_read:
                companions = scheduler_module.parallel_companion_actions(
                    store,
                    primary,
                    web_search="live",
                )

        self.assertTrue(companions)
        self.assertEqual(1, state_read.call_count)
        for companion in companions:
            trace = companion["parallel_wave_admission"]
            self.assertEqual(
                "parallel_wave", trace["candidate_generator_scope_id"]
            )
            self.assertNotIn(
                "caller_supplied", trace["active_candidate_generator_ids"]
            )
            self.assertEqual(
                scheduler_module.PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
                trace["policy_version"],
            )
            decision = companion["decision_trace"]
            self.assertEqual([], decision_trace_errors(decision))
            self.assertEqual(trace, decision["parallel_wave_admission"])
            tampered_decision = json.loads(json.dumps(decision))
            tampered_decision["parallel_wave_admission"][
                "candidate_set_complete"
            ] = False
            self.assertTrue(
                any(
                    "parallel wave admission" in error
                    for error in decision_trace_errors(tampered_decision)
                )
            )
            operation = run_metrics_operation(
                run_id="parallel-provenance",
                action=companion,
                session_plan={
                    "actor_role": "researcher",
                    "state_revision": 0,
                },
                usage_payload={},
            )
            self.assertEqual("deterministic", operation["selection_design"])
            self.assertEqual(decision, operation["decision_trace"])

    def test_workflow_wave_composition_uses_one_scheduler_snapshot(self) -> None:
        captured_states: list[object] = []

        def capture_companions(
            *_args: object, **kwargs: object
        ) -> list[dict[str, object]]:
            captured_states.append(kwargs.get("_scheduler_state"))
            return []

        def capture_admission(
            _store: object,
            _primary: object,
            _candidates: object,
            **kwargs: object,
        ) -> tuple[list[dict[str, object]], dict[str, object]]:
            captured_states.append(kwargs.get("_scheduler_state"))
            return [], {}

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-parallel-single-snapshot",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            terminal = {
                "mode": "stop_solved",
                "target_id": "root",
                "route_id": "",
                "reason": "test terminal",
                "terminal_classification": "test",
            }
            with (
                mock.patch.object(
                    store,
                    "get_scheduler_state",
                    wraps=store.get_scheduler_state,
                ) as state_read,
                mock.patch.object(
                    workflow_module,
                    "_stable_next_action",
                    return_value=(terminal, store.audit_chain_heads()),
                ),
                mock.patch.object(
                    workflow_module,
                    "parallel_companion_actions",
                    side_effect=capture_companions,
                ),
                mock.patch.object(
                    workflow_module,
                    "multi_branch_research_actions",
                    side_effect=capture_companions,
                ),
                mock.patch.object(
                    workflow_module,
                    "_admit_and_finalize_parallel_companions",
                    side_effect=capture_admission,
                ),
                mock.patch.object(
                    workflow_module,
                    "_bind_primary_parallel_wave_decision",
                    side_effect=lambda action, _trace: dict(action),
                ),
            ):
                run_workflow(
                    store,
                    steps=1,
                    execute=False,
                    write_console=False,
                    parallel_librarian_verifier=True,
                    parallel_branches=3,
                )

        self.assertEqual(1, state_read.call_count)
        self.assertEqual(3, len(captured_states))
        self.assertIsNotNone(captured_states[0])
        self.assertTrue(
            all(state is captured_states[0] for state in captured_states)
        )

    def test_workflow_regenerates_every_companion_after_leader_promotion(self) -> None:
        companion_leaders: list[str] = []
        admitted: dict[str, object] = {}

        def companions(
            _store: object, leader: Mapping[str, Any], **_kwargs: object
        ) -> list[dict[str, object]]:
            route_id = str(leader.get("route_id") or "")
            companion_leaders.append(route_id)
            return [
                {
                    "mode": "reduce",
                    "target_id": f"companion-for-{route_id}",
                    "route_id": "",
                }
            ]

        def admission(
            _store: object,
            leader: Mapping[str, Any],
            candidates: Sequence[Mapping[str, Any]],
            **_kwargs: object,
        ) -> tuple[list[dict[str, object]], dict[str, object]]:
            admitted["leader"] = dict(leader)
            admitted["candidates"] = [dict(item) for item in candidates]
            return [], {}

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-parallel-leader-regeneration",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            original = {
                "mode": "reduce",
                "target_id": "root",
                "route_id": "original-route",
                "reason": "original leader",
            }
            promoted = {
                "mode": "reduce",
                "target_id": "root",
                "route_id": "promoted-route",
                "reason": "promoted leader",
            }
            with (
                mock.patch.object(
                    workflow_module,
                    "_stable_next_action",
                    return_value=(original, store.audit_chain_heads()),
                ),
                mock.patch.object(
                    workflow_module,
                    "parallel_companion_actions",
                    side_effect=companions,
                ),
                mock.patch.object(
                    workflow_module,
                    "multi_branch_research_actions",
                    return_value=[],
                ),
                mock.patch.object(
                    workflow_module,
                    "_select_parallel_wave_leader",
                    return_value=(promoted, True),
                ),
                mock.patch.object(
                    workflow_module,
                    "_admit_and_finalize_parallel_companions",
                    side_effect=admission,
                ),
                mock.patch.object(
                    workflow_module,
                    "_bind_primary_parallel_wave_decision",
                    side_effect=lambda action, _trace: dict(action),
                ),
            ):
                run_workflow(
                    store,
                    steps=1,
                    execute=False,
                    write_console=False,
                    parallel_librarian_verifier=True,
                    parallel_branches=0,
                )

        self.assertEqual(["original-route", "promoted-route"], companion_leaders)
        self.assertEqual("promoted-route", admitted["leader"]["route_id"])
        self.assertEqual(
            ["companion-for-promoted-route"],
            [item["target_id"] for item in admitted["candidates"]],
        )

    def test_production_parallel_planner_rejects_unclassified_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "parallel-unclassified-generator",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            primary = next_action(store, web_search="disabled")
            with mock.patch.object(
                scheduler_module,
                "_plan_parallel_companion_actions",
                return_value=[
                    {"mode": "reduce", "target_id": "root", "route_id": ""}
                ],
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "unclassified candidate"
                ):
                    scheduler_module.parallel_companion_actions(
                        store, primary, web_search="disabled"
                    )

    def test_parallel_integrations_choose_one_route_per_conclusion_claim(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "lemma",
                    "validation_status": "informally_verified",
                    "lifecycle_status": "active",
                    "evidence_artifact_ids_json": "[]",
                }
            ],
            "routes": [
                {
                    "route_id": "route-a",
                    "conclusion_claim_id": "lemma",
                    "status": "active",
                    "relation_to_parent": "sufficient",
                },
                {
                    "route_id": "route-b",
                    "conclusion_claim_id": "lemma",
                    "status": "active",
                    "relation_to_parent": "sufficient",
                },
            ],
            "inferences": [
                {
                    "inference_id": "inf-a",
                    "route_id": "route-a",
                    "conclusion_claim_id": "lemma",
                    "validation_status": "informally_verified",
                    "premise_claim_ids": [],
                    "evidence_artifact_ids_json": "[]",
                },
                {
                    "inference_id": "inf-b",
                    "route_id": "route-b",
                    "conclusion_claim_id": "lemma",
                    "validation_status": "informally_verified",
                    "premise_claim_ids": [],
                    "evidence_artifact_ids_json": "[]",
                },
            ],
            "debts": [],
            "artifacts": [],
        }

        candidates = scheduler_module._integration_candidates(state)

        self.assertEqual(["route-a"], [row["route_id"] for row in candidates])
        self.assertEqual(
            [], scheduler_module._integration_candidates(state, limit=0)
        )
        self.assertEqual(
            ["route-a", "route-b"],
            [
                row["route_id"]
                for row in scheduler_module._integration_candidates(
                    state, distinct_claims=False
                )
            ],
        )

    def test_sequential_integration_trace_contains_every_eligible_route(self) -> None:
        integration_candidates = [
            {
                "route_id": route_id,
                "conclusion_claim_id": claim_id,
                "integration_terminal_inference_ids": [f"inf-{route_id}"],
            }
            for route_id, claim_id in (
                ("route-a", "lemma-a"),
                ("route-b", "lemma-b"),
            )
        ]
        state = {
            "_integration_candidates": integration_candidates,
            "_integration_assurance_by_route": {
                route["route_id"]: {"satisfied": True}
                for route in integration_candidates
            },
            "recent_runs": [],
        }

        selected = scheduler_module._integration_gate_action(
            state,
            problem={"remaining_token_budget": 100_000},
            requested_tokens=None,
            research_mode="balanced",
            allow_integration=True,
        )

        self.assertEqual("route-a", selected["route_id"])
        trace = selected["_base_policy_trace"]
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual(
            {
                "base_integration:lemma-a:route-a",
                "base_integration:lemma-b:route-b",
            },
            {row["candidate_id"] for row in trace["candidates"]},
        )
        self.assertEqual([], decision_trace_errors(trace))

    def test_integration_candidates_do_not_reintegrate_an_integrated_claim(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "lemma",
                    "validation_status": "informally_verified",
                    "lifecycle_status": "integrated",
                    "evidence_artifact_ids_json": "[]",
                }
            ],
            "routes": [
                {
                    "route_id": "unused-alternative",
                    "conclusion_claim_id": "lemma",
                    "status": "active",
                    "relation_to_parent": "sufficient",
                }
            ],
            "inferences": [
                {
                    "inference_id": "inf-alternative",
                    "route_id": "unused-alternative",
                    "conclusion_claim_id": "lemma",
                    "validation_status": "informally_verified",
                    "premise_claim_ids": [],
                    "evidence_artifact_ids_json": "[]",
                }
            ],
            "debts": [],
            "artifacts": [],
        }

        self.assertEqual(
            [],
            scheduler_module._integration_candidates(
                state, distinct_claims=False
            ),
        )

    def test_integration_candidate_scan_indexes_obligations_and_artifacts_once(self) -> None:
        class CountingList(list):
            def __init__(self, values):
                super().__init__(values)
                self.iterations = 0

            def __iter__(self):
                self.iterations += 1
                return super().__iter__()

        count = 8
        artifacts = CountingList(
            [
                {
                    "artifact_id": f"verification-{index}",
                    "artifact_type": "verification_report",
                    "producer_role": "strict_informal_verifier",
                    "created_at": f"2026-01-01T00:00:{index:02d}+00:00",
                    "metadata_json": {
                        "verification_report": {
                            "checked_items": [f"claim-{index}"],
                            "critical_errors": [],
                            "gaps": [],
                            "blocking_gap": False,
                        }
                    },
                }
                for index in range(count)
            ]
        )
        obligations = CountingList(
            [
                {
                    "debt_id": f"minor-{index}",
                    "owner_id": f"claim-{index}",
                    "status": "active",
                    "severity": "minor",
                }
                for index in range(count)
            ]
        )
        state = {
            "claims": [
                {
                    "claim_id": f"claim-{index}",
                    "validation_status": "informally_verified",
                    "lifecycle_status": "active",
                    "evidence_artifact_ids_json": [f"verification-{index}"],
                }
                for index in range(count)
            ],
            "routes": [
                {
                    "route_id": f"route-{index}",
                    "conclusion_claim_id": f"claim-{index}",
                    "status": "active",
                    "relation_to_parent": "sufficient",
                }
                for index in range(count)
            ],
            "inferences": [
                {
                    "inference_id": f"inference-{index}",
                    "route_id": f"route-{index}",
                    "conclusion_claim_id": f"claim-{index}",
                    "validation_status": "informally_verified",
                    "premise_claim_ids": [],
                    "evidence_artifact_ids_json": [f"verification-{index}"],
                }
                for index in range(count)
            ],
            "debts": obligations,
            "artifacts": artifacts,
        }

        candidates = scheduler_module._integration_candidates(
            state, distinct_claims=False
        )

        self.assertEqual(count, len(candidates))
        self.assertEqual(1, obligations.iterations)
        self.assertEqual(1, artifacts.iterations)

    def test_standard_integration_assurance_is_projected_without_per_route_queries(self) -> None:
        candidates = [
            {"route_id": "standard-a", "conclusion_claim_id": "claim-a"},
            {"route_id": "standard-b", "conclusion_claim_id": "claim-b"},
            {"route_id": "enhanced", "conclusion_claim_id": "claim-c"},
        ]
        state = {
            "claim_assurance": [
                {
                    "claim_id": "claim-c",
                    "assurance_level": "heterogeneous_review",
                }
            ]
        }
        enhanced = {
            "claim_id": "claim-c",
            "route_id": "enhanced",
            "assurance_level": "heterogeneous_review",
            "satisfied": False,
            "independence_classes": ["model:a"],
            "review_artifact_ids": ["review-a"],
        }
        with mock.patch.object(
            scheduler_module,
            "claim_assurance_summary",
            return_value=enhanced,
        ) as authoritative:
            projected = scheduler_module._integration_assurance_projection(
                mock.Mock(), state, candidates
            )

        authoritative.assert_called_once_with(
            mock.ANY,
            claim_id="claim-c",
            route_id="enhanced",
        )
        self.assertTrue(projected["standard-a"]["satisfied"])
        self.assertTrue(projected["standard-b"]["satisfied"])
        self.assertEqual(enhanced, projected["enhanced"])

    def test_parallel_verifiers_choose_one_route_per_conclusion_claim(self) -> None:
        ready = [
            {
                "target_id": "lemma-a",
                "route_id": "route-a-1",
                "route_readiness": {"verifier_ready": True},
                "evidence_artifact_ids": ["proof-a-1"],
                "evidence_state_revision": 4,
            },
            {
                "target_id": "lemma-a",
                "route_id": "route-a-2",
                "route_readiness": {"verifier_ready": True},
                "evidence_artifact_ids": ["proof-a-2"],
                "evidence_state_revision": 5,
            },
            {
                "target_id": "lemma-b",
                "route_id": "route-b",
                "route_readiness": {"verifier_ready": True},
                "evidence_artifact_ids": ["proof-b"],
                "evidence_state_revision": 3,
            },
        ]
        with mock.patch.object(
            scheduler_module,
            "_verifier_ready_route_candidates",
            return_value=ready,
        ), mock.patch.object(
            scheduler_module,
            "plan_step_budget",
            return_value={"requested_tokens": 1},
        ):
            actions = scheduler_module._verifier_candidate_actions(
                {},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                limit=3,
            )
            none = scheduler_module._verifier_candidate_actions(
                {},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                limit=0,
            )

        self.assertEqual(
            ["route-a-1", "route-b"],
            [action["route_id"] for action in actions],
        )
        self.assertEqual([], none)

    def test_advisor_ablation_is_applied_before_wave_capacity_admission(self) -> None:
        generated = [
            {
                "mode": "prove",
                "target_id": "lemma-a",
                "route_id": "",
                "_candidate_generator_id": "researcher",
            },
            {
                "mode": "refute",
                "target_id": "lemma-b",
                "route_id": "",
                "_candidate_generator_id": "counterexample_search",
            },
            {
                "mode": "reduce",
                "target_id": "lemma-c",
                "route_id": "",
                "_candidate_generator_id": "research_strategy",
            },
            {
                "mode": "triage_routes",
                "target_id": "root",
                "route_id": "",
                "reason": "advisor pass",
                "_candidate_generator_id": "advisor_synthesis",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "parallel-advisor-ablation-admission",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            primary = {"mode": "retrieve", "target_id": "root", "route_id": ""}

            def generated_with_evaluation(*_args: object, **kwargs: object) -> list[dict[str, object]]:
                scheduler_module._evaluate_parallel_candidate_generators(
                    kwargs["_generator_evaluation"],
                    scheduler_module._PARALLEL_INTERNAL_GENERATOR_IDS,
                )
                return generated

            with mock.patch.dict(
                os.environ, {"ALBILICH_ADVISOR_ENABLED": "0"}
            ), mock.patch.object(
                scheduler_module,
                "_plan_parallel_companion_actions",
                side_effect=generated_with_evaluation,
            ):
                companions = scheduler_module.parallel_companion_actions(
                    store,
                    primary,
                    parallel_branches=3,
                    web_search="disabled",
                )

        self.assertEqual(3, len(companions))
        trace = companions[0]["parallel_wave_admission"]
        rejected_research = [
            row
            for row in trace["candidates"][1:]
            if row["action_class"] in {"research", "adversarial"}
            and row["disposition"] == "rejected"
        ]
        self.assertEqual(1, len(rejected_research))
        self.assertEqual(
            "research_or_adversarial capacity reached",
            rejected_research[0]["reason"],
        )

    def test_terminal_and_state_repair_actions_are_mandatory_gates(self) -> None:
        for action in (
            {"mode": "stop_solved"},
            {"mode": "stop_with_partial_results"},
            {"mode": "await_human"},
            {"mode": "integrate"},
            {"mode": "formalize"},
            {"mode": "validate_counterexample"},
            {"mode": "review_writing"},
            {"mode": "write", "final_output_required": True},
            {"mode": "retrieve", "post_integration_retrieval": True},
            {"mode": "weaken", "root_revision_required": True},
            {"mode": "reduce", "referee_route_error_research": True},
        ):
            with self.subTest(action=action):
                self.assertTrue(
                    scheduler_module._base_action_is_mandatory_gate(
                        action, steering_alignment={}
                    )
                )

    def test_solved_root_comparison_exposes_deferred_document_work(self) -> None:
        literature = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "",
            "post_integration_retrieval": True,
        }
        writing = {
            "mode": "write",
            "target_id": "root",
            "route_id": "root-route",
            "final_output_required": True,
        }
        terminal = {
            "mode": "stop_solved",
            "target_id": "root",
            "route_id": "root-route",
        }
        with (
            mock.patch.object(
                scheduler_module,
                "_final_proof_artifact",
                return_value={"artifact_id": "final-proof"},
            ),
            mock.patch.object(
                scheduler_module,
                "_post_integration_literature_action",
                return_value=literature,
            ),
            mock.patch.object(
                scheduler_module, "_writing_gate_action", return_value=writing
            ),
            mock.patch.object(
                scheduler_module,
                "_solved_root_terminal_action",
                return_value=terminal,
            ),
        ):
            selected = scheduler_module._solved_root_action(
                mock.Mock(),
                {
                    "final_artifacts": [],
                    "publication_reviews": [],
                },
                problem={"completion_policy": "publication_ready"},
                requested_tokens=None,
                research_mode="balanced",
                web_search="live",
            )

        trace = selected["_base_policy_trace"]
        rows = {row["candidate_id"]: row for row in trace["candidates"]}
        self.assertEqual("retrieve", selected["mode"])
        self.assertEqual("solved_root", trace["candidate_generator_scope_id"])
        self.assertEqual(
            [
                "document_delivery",
                "post_integration_literature",
                "terminal_completion",
            ],
            trace["active_candidate_generator_ids"],
        )
        self.assertEqual(
            "selected",
            rows["base_solved_root:post_integration_literature"][
                "disposition"
            ],
        )
        self.assertEqual(
            "rejected_inadmissible",
            rows["base_solved_root:document_delivery"]["disposition"],
        )
        self.assertEqual(
            "rejected_inadmissible",
            rows["base_solved_root:terminal_completion"]["disposition"],
        )
        self.assertEqual([], decision_trace_errors(trace))

    def test_solved_root_without_final_proof_has_single_explicit_phase(self) -> None:
        final_writing = {
            "mode": "write",
            "target_id": "root",
            "route_id": "root-route",
            "final_output_required": True,
        }
        with (
            mock.patch.object(
                scheduler_module, "_final_proof_artifact", return_value=None
            ),
            mock.patch.object(
                scheduler_module,
                "_final_proof_writing_action",
                return_value=final_writing,
            ),
        ):
            selected = scheduler_module._solved_root_action(
                mock.Mock(),
                {},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
            )

        trace = selected["_base_policy_trace"]
        self.assertEqual("write", selected["mode"])
        self.assertEqual(
            "base_solved_root:final_proof_writing",
            trace["selected_candidate_id"],
        )
        self.assertEqual(
            ["final_proof_writing"],
            trace["active_candidate_generator_ids"],
        )
        self.assertEqual([], decision_trace_errors(trace))

    def test_outer_strategy_cannot_preempt_an_invariant_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "mandatory-invariant-stop",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("A test statement.")
            stop = {
                "mode": "stop_with_partial_results",
                "target_id": "root",
                "route_id": "",
                "reason": "state invariant violation",
                "stop_reason_code": "state_invariant_violation",
            }
            with (
                mock.patch.object(
                    scheduler_module, "_plan_next_action", return_value=stop
                ),
                mock.patch.object(
                    scheduler_module,
                    "strategy_operation_candidates",
                    side_effect=AssertionError(
                        "terminal gate must bypass strategy generation"
                    ),
                ),
            ):
                action = scheduler_module.next_action(store)
        self.assertEqual("stop_with_partial_results", action["mode"])
        self.assertEqual(
            "base:mandatory_constraint",
            action["decision_trace"]["selected_candidate_id"],
        )

    def test_policy_tier_is_committed_by_candidate_hash(self) -> None:
        candidate = ActionCandidate(
            "candidate",
            "research",
            {"mode": "prove", "target_id": "root"},
            1.0,
            policy_tier=100,
        )
        _, trace = select_action_candidate([candidate], candidate_set_complete=True)
        tampered = json.loads(json.dumps(trace))
        tampered["candidates"][0]["policy_tier"] = 300
        self.assertTrue(decision_trace_errors(tampered))

    def test_version_four_trace_remains_valid_after_policy_tier_upgrade(self) -> None:
        candidate = ActionCandidate(
            "legacy-candidate",
            "research",
            {"mode": "prove", "target_id": "root"},
            1.0,
        )
        _, trace = select_action_candidate([candidate], candidate_set_complete=True)
        trace["decision_policy_version"] = 4
        for row in trace["candidates"]:
            row.pop("policy_tier")
        trace["candidate_set_sha256"] = candidate_rows_sha256(
            trace["candidates"], decision_policy_version=4
        )
        self.assertEqual([], decision_trace_errors(trace))
        legacy_action = {
            "mode": "prove",
            "target_id": "root",
            "route_id": "",
        }
        legacy_action["decision_trace"] = bind_dispatched_action(
            legacy_action, trace
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "version-four-decision-trace",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            operation = run_metrics_operation(
                run_id="legacy-deterministic-run",
                action=legacy_action,
                session_plan={
                    "actor_role": "researcher",
                    "state_revision": 0,
                    "context_hash": "legacy-context",
                },
                usage_payload={"input_tokens": 1, "output_tokens": 1},
            )
            outcome = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [operation],
                    "rationale": "retain valid v4 deterministic run provenance",
                },
                mode="prove",
            )
            self.assertFalse(outcome.accepted)
            self.assertIn(
                "prior durable scheduler dispatch", " ".join(outcome.errors)
            )
            with store.connect() as conn:
                self.assertEqual([], validate_conn(conn))

    def test_verification_stratum_materializes_simultaneous_policies(self) -> None:
        advisor = {
            "mode": "prove",
            "target_id": "root",
            "route_id": "route-advisor",
            "scheduler_policy_id": "advisor_strict_verifier_followup",
        }
        counterexample = {
            "mode": "validate_counterexample",
            "target_id": "root",
            "route_id": "",
            "candidate_counterexample_artifact_id": "candidate-root",
            "scheduler_policy_id": "counterexample_validation",
        }
        verifier_routes = [
            {
                "mode": "prove",
                "target_id": "lemma-a",
                "route_id": "route-a",
                "scheduler_policy_id": "verify_ready_route",
            },
            {
                "mode": "prove",
                "target_id": "lemma-b",
                "route_id": "route-b",
                "scheduler_policy_id": "verify_ready_route",
            },
        ]
        route_local_actions = {
            "_proof_evidence_handoff_actions": [
                {"mode": "prove", "target_id": "fresh-a", "route_id": "fresh-route-a"},
                {"mode": "prove", "target_id": "fresh-b", "route_id": "fresh-route-b"},
            ],
            "_verifier_loop_classification_actions": [
                {"mode": "triage_routes", "target_id": "loop-a", "route_id": "loop-route-a"},
                {"mode": "triage_routes", "target_id": "loop-b", "route_id": "loop-route-b"},
            ],
            "_support_lemma_precheck_actions": [
                {"mode": "retrieve", "target_id": "support-a", "route_id": "support-route-a"},
                {"mode": "retrieve", "target_id": "support-b", "route_id": "support-route-b"},
            ],
            "_threat_revalidation_actions": [
                {"mode": "prove", "target_id": "threat-a", "route_id": "threat-route-a"},
                {"mode": "prove", "target_id": "threat-b", "route_id": "threat-route-b"},
            ],
        }
        inactive = mock.Mock(return_value=None)
        with mock.patch.multiple(
            scheduler_module,
            _advisor_requested_strict_verifier_action=mock.Mock(return_value=advisor),
            **{
                name: mock.Mock(return_value=actions)
                for name, actions in route_local_actions.items()
            },
            _verifier_candidate_actions=mock.Mock(return_value=verifier_routes),
            _counterexample_validation_actions=mock.Mock(return_value=[counterexample]),
            _advisor_requested_validation_action=inactive,
            _advisor_requested_villain_action=inactive,
            _unrouted_proof_claim_actions=mock.Mock(return_value=[]),
        ):
            selected = scheduler_module._verification_handoff_action(
                mock.Mock(),
                {},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
            )
        self.assertIsNotNone(selected)
        self.assertEqual("route-advisor", selected["route_id"])
        trace = selected.pop("_base_policy_trace")
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual(
            [
                "base_verification:advisor_strict_verification",
                "base_verification:fresh_proof_evidence:fresh-route-a",
                "base_verification:fresh_proof_evidence:fresh-route-b",
                "base_verification:verifier_loop_classification:loop-route-a",
                "base_verification:verifier_loop_classification:loop-route-b",
                "base_verification:support_theorem_precheck:support-route-a",
                "base_verification:support_theorem_precheck:support-route-b",
                "base_verification:verifier_ready_route:route-a",
                "base_verification:verifier_ready_route:route-b",
                "base_verification:counterexample_validation:candidate-root",
                "base_verification:dependency_threat_revalidation:threat-route-a",
                "base_verification:dependency_threat_revalidation:threat-route-b",
            ],
            [row["candidate_id"] for row in trace["candidates"]],
        )
        self.assertEqual([], decision_trace_errors(trace))
        selected["base_policy_trace_sha256"] = policy_trace_sha256(trace)
        _, outer_trace = select_action_candidate(
            [
                ActionCandidate(
                    "base:sequential_planner",
                    "legacy_base_planner",
                    selected,
                    1.0,
                )
            ],
            candidate_set_complete=False,
            nested_policy_traces={"base:sequential_planner": trace},
        )
        self.assertEqual([], decision_trace_errors(outer_trace))
        missing_nested = json.loads(json.dumps(outer_trace))
        missing_nested["nested_policy_traces"].pop("base:sequential_planner")
        self.assertTrue(decision_trace_errors(missing_nested))

    def test_fresh_proof_handoff_materializes_every_ready_route(self) -> None:
        state = scheduler_module._enable_scheduler_planning_cache(
            {
                "problem_state": {"current_revision": 12},
                "claims": [
                    {
                        "claim_id": "root",
                        "parent_ids_json": "[]",
                        "lifecycle_status": "active",
                        "validation_status": "plausible",
                        "root_impact": 1.0,
                    },
                    {
                        "claim_id": "lemma-a",
                        "parent_ids_json": '["root"]',
                        "lifecycle_status": "active",
                        "validation_status": "plausible",
                        "root_impact": 0.8,
                    },
                ],
                "routes": [
                    {
                        "route_id": "route-root",
                        "conclusion_claim_id": "root",
                        "status": "active",
                        "relation_to_parent": "sufficient",
                        "evidence_artifact_ids_json": '["proof-root"]',
                    },
                    {
                        "route_id": "route-a",
                        "conclusion_claim_id": "lemma-a",
                        "status": "active",
                        "relation_to_parent": "sufficient",
                        "evidence_artifact_ids_json": '["proof-a"]',
                    },
                ],
                "inferences": [
                    {
                        "inference_id": "inf-root",
                        "route_id": "route-root",
                        "conclusion_claim_id": "root",
                        "premise_claim_ids": [],
                        "validation_status": "plausible",
                        "evidence_artifact_ids_json": '["proof-root"]',
                    },
                    {
                        "inference_id": "inf-a",
                        "route_id": "route-a",
                        "conclusion_claim_id": "lemma-a",
                        "premise_claim_ids": [],
                        "validation_status": "plausible",
                        "evidence_artifact_ids_json": '["proof-a"]',
                    },
                ],
                "research_artifacts": [
                    {
                        "artifact_id": "proof-root",
                        "artifact_type": "proof_dossier",
                        "state_revision": 11,
                        "metadata_json": '{"ready_for_verifier": true}',
                    },
                    {
                        "artifact_id": "proof-a",
                        "artifact_type": "proof_dossier",
                        "state_revision": 12,
                        "metadata_json": '{"proof_candidate": true}',
                    },
                ],
                "debts": [],
                "recent_runs": [],
            }
        )

        actions = scheduler_module._proof_evidence_handoff_actions(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )

        self.assertEqual(["route-root", "route-a"], [row["route_id"] for row in actions])
        self.assertTrue(
            all(row["automatic_researcher_verifier_handoff"] for row in actions)
        )

    def test_threat_revalidation_materializes_every_pending_route(self) -> None:
        threat = {
            "pending_revalidation_routes": [
                {"route_id": "route-a", "target_id": "lemma-a", "threat_revision": 8},
                {"route_id": "route-b", "target_id": "lemma-b", "threat_revision": 9},
            ],
            "source_artifact_ids": ["counterevidence"],
        }
        with mock.patch.object(
            scheduler_module, "threat_propagation_view", return_value=threat
        ):
            actions = scheduler_module._threat_revalidation_actions(
                {"claims": [], "routes": [], "inferences": [], "debts": []},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
            )

        self.assertEqual(["route-a", "route-b"], [row["route_id"] for row in actions])
        self.assertEqual(
            [["counterevidence"], ["counterevidence"]],
            [row["verifier_evidence_artifact_ids"] for row in actions],
        )

    def test_support_precheck_materializes_every_named_support_gap(self) -> None:
        verifier_candidates = [
            {"route_id": "route-a", "target_id": "lemma-a"},
            {"route_id": "route-b", "target_id": "lemma-b"},
        ]
        support_gaps = [
            {"label": "support-a", "query": "Theorem A"},
            {"label": "support-b", "query": "Theorem B"},
        ]
        with mock.patch.object(
            scheduler_module,
            "_verifier_ready_route_candidates",
            return_value=verifier_candidates,
        ), mock.patch.object(
            scheduler_module,
            "_route_named_support_gap",
            side_effect=support_gaps,
        ), mock.patch.object(
            scheduler_module,
            "_support_term_already_sourced",
            return_value=False,
        ):
            actions = scheduler_module._support_lemma_precheck_actions(
                {"claims": [], "routes": [], "inferences": [], "debts": []},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
            )

        self.assertEqual(["route-a", "route-b"], [row["route_id"] for row in actions])
        self.assertEqual(["support-a", "support-b"], [row["support_lemma_label"] for row in actions])

    def test_verifier_loop_classification_materializes_every_repeating_route(self) -> None:
        recent_runs = [
            {
                "run_id": f"verify-{route_id}-{attempt}",
                "route_id": route_id,
                "actor_role": "strict_informal_verifier",
                "mode": "prove",
                "status": "completed",
                "state_revision": 3,
            }
            for route_id in ("route-a", "route-b")
            for attempt in (1, 2)
        ]
        state = {
            "claims": [],
            "routes": [
                {
                    "route_id": route_id,
                    "conclusion_claim_id": target_id,
                    "status": "active",
                }
                for route_id, target_id in (
                    ("route-a", "lemma-a"),
                    ("route-b", "lemma-b"),
                )
            ],
            "inferences": [],
            "debts": [],
            "recent_runs": recent_runs,
        }
        with mock.patch.object(
            scheduler_module,
            "_active_route_gap_debt_ids",
            side_effect=lambda _state, route_id, _target_id: [f"gap-{route_id}"],
        ):
            actions = scheduler_module._verifier_loop_classification_actions(
                state,
                problem={},
                requested_tokens=None,
                research_mode="balanced",
            )

        self.assertEqual(["route-a", "route-b"], [row["route_id"] for row in actions])
        self.assertEqual(
            [["gap-route-a"], ["gap-route-b"]],
            [row["verifier_gap_debt_ids"] for row in actions],
        )

    def test_route_evidence_index_preserves_focus_order_and_snapshot_scope(self) -> None:
        state = scheduler_module._enable_scheduler_planning_cache(
            {
                "claims": [],
                "routes": [
                    {
                        "route_id": "route-a",
                        "evidence_artifact_ids_json": '["structure"]',
                    }
                ],
                "inferences": [
                    {
                        "inference_id": "focus",
                        "route_id": "route-a",
                        "evidence_artifact_ids_json": '["focus-source"]',
                    },
                    {
                        "inference_id": "other",
                        "route_id": "route-a",
                        "evidence_artifact_ids_json": '["new-proof"]',
                    },
                ],
                "research_artifacts": [
                    {
                        "artifact_id": "structure",
                        "artifact_type": "decomposition_plan",
                        "state_revision": 1,
                    },
                    {
                        "artifact_id": "focus-source",
                        "artifact_type": "retrieval_card",
                        "state_revision": 1,
                    },
                    {
                        "artifact_id": "new-proof",
                        "artifact_type": "proof_dossier",
                        "state_revision": 3,
                    },
                ],
                "debts": [],
            }
        )
        expected = ["focus-source", "new-proof", "structure"]
        self.assertEqual(
            expected,
            scheduler_module._route_evidence_artifact_ids(
                state, "route-a", focus_inference_id="focus"
            ),
        )
        state["inferences"].append(
            {
                "inference_id": "later",
                "route_id": "route-a",
                "evidence_artifact_ids_json": '["later-proof"]',
            }
        )
        self.assertEqual(
            expected,
            scheduler_module._route_evidence_artifact_ids(
                state, "route-a", focus_inference_id="focus"
            ),
        )
        scheduler_module._enable_scheduler_planning_cache(state)
        self.assertIn(
            "later-proof",
            scheduler_module._route_evidence_artifact_ids(state, "route-a"),
        )

    def test_counterexample_queue_materializes_every_pending_candidate(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "root",
                    "lifecycle_status": "active",
                    "validation_status": "challenged",
                    "statement": "Does every widget satisfy the proposed bound?",
                },
                {
                    "claim_id": "lemma-a",
                    "lifecycle_status": "active",
                    "validation_status": "challenged",
                    "statement": "Every small widget is blue.",
                },
            ],
            "research_artifacts": [
                {
                    "artifact_id": "candidate-root-old",
                    "artifact_type": "candidate_counterexample",
                    "state_revision": 3,
                    "metadata_json": '{"target_id": "root", "concrete_instance": "K"}',
                },
                {
                    "artifact_id": "candidate-lemma",
                    "artifact_type": "candidate_counterexample",
                    "state_revision": 5,
                    "metadata_json": '{"target_id": "lemma-a", "concrete_instance": "L"}',
                },
                {
                    "artifact_id": "candidate-root-new",
                    "artifact_type": "candidate_counterexample",
                    "state_revision": 6,
                    "metadata_json": '{"target_id": "root", "concrete_instance": "M"}',
                },
            ],
            "recent_runs": [],
        }

        actions = scheduler_module._counterexample_validation_actions(
            mock.Mock(),
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )

        self.assertEqual(
            ["candidate-root-new", "candidate-root-old", "candidate-lemma"],
            [row["candidate_counterexample_artifact_id"] for row in actions],
        )

    def test_validation_cooldown_is_scoped_to_exact_counterexample(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "root",
                    "lifecycle_status": "active",
                    "validation_status": "challenged",
                    "statement": "Every widget is blue.",
                }
            ],
            "research_artifacts": [
                {
                    "artifact_id": candidate_id,
                    "artifact_type": "candidate_counterexample",
                    "state_revision": 2,
                    "metadata_json": json.dumps(
                        {"target_id": "root", "concrete_instance": candidate_id}
                    ),
                }
                for candidate_id in ("candidate-a", "candidate-b")
            ],
            "recent_runs": [
                {
                    "mode": "validate_counterexample",
                    "target_id": "root",
                    "status": "completed",
                    "state_revision": 3,
                    "decision_trace": {
                        "candidates": [
                            {
                                "candidate_id": "base_verification:counterexample_validation:candidate-a",
                                "admissible": True,
                                "disposition": "selected",
                            },
                            {
                                "candidate_id": "base_verification:counterexample_validation:candidate-b",
                                "admissible": True,
                                "disposition": "rejected_by_ordinal_comparison",
                            },
                        ]
                    },
                }
            ],
        }

        actions = scheduler_module._counterexample_validation_actions(
            mock.Mock(),
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )

        self.assertEqual(
            ["candidate-b"],
            [row["candidate_counterexample_artifact_id"] for row in actions],
        )

    def test_counterexample_confirmation_does_not_use_substring_identity(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "root",
                    "lifecycle_status": "active",
                    "validation_status": "challenged",
                    "statement": "Does every widget satisfy the proposed bound?",
                }
            ],
            "research_artifacts": [
                {
                    "artifact_id": candidate_id,
                    "artifact_type": "candidate_counterexample",
                    "state_revision": 2,
                    "metadata_json": json.dumps(
                        {"target_id": "root", "concrete_instance": candidate_id}
                    ),
                }
                for candidate_id in ("candidate-1", "candidate-10")
            ]
            + [
                {
                    "artifact_id": "confirmed-10",
                    "artifact_type": "confirmed_counterexample",
                    "state_revision": 3,
                    "metadata_json": '{"target_claim_id": "root", "candidate_artifact_id": "candidate-10"}',
                }
            ],
            "recent_runs": [],
        }

        actions = scheduler_module._counterexample_validation_actions(
            mock.Mock(),
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )

        self.assertEqual(
            ["candidate-1"],
            [row["candidate_counterexample_artifact_id"] for row in actions],
        )

    def test_unrouted_proof_assembly_materializes_every_eligible_claim(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "lemma-a",
                    "lifecycle_status": "active",
                    "validation_status": "plausible",
                },
                {
                    "claim_id": "lemma-b",
                    "lifecycle_status": "active",
                    "validation_status": "untested",
                },
                {
                    "claim_id": "lemma-false-positive",
                    "lifecycle_status": "active",
                    "validation_status": "untested",
                },
            ],
            "routes": [],
            "inferences": [
                {
                    "inference_id": "inf-a",
                    "conclusion_claim_id": "lemma-a",
                    "evidence_artifact_ids_json": '["artifact-a"]',
                },
                {
                    "inference_id": "inf-b",
                    "conclusion_claim_id": "lemma-b",
                    "evidence_artifact_ids_json": '["artifact-b"]',
                },
                {
                    "inference_id": "inf-false-positive",
                    "conclusion_claim_id": "lemma-false-positive",
                    "evidence_artifact_ids_json": '["proof-looking-name"]',
                },
            ],
            "research_artifacts": [
                {
                    "artifact_id": "artifact-a",
                    "artifact_type": "proof_dossier",
                },
                {
                    "artifact_id": "artifact-b",
                    "artifact_type": "proof_blueprint",
                },
                {
                    "artifact_id": "proof-looking-name",
                    "artifact_type": "research_diagnostic",
                },
            ],
            "recent_runs": [
                {
                    "mode": "reduce",
                    "target_id": "lemma-a",
                    "status": "completed",
                    "search_intent": "route_proof_construction",
                }
            ],
        }

        actions = scheduler_module._unrouted_proof_claim_actions(
            mock.Mock(),
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )

        self.assertEqual(["lemma-a", "lemma-b"], [row["target_id"] for row in actions])

    def test_verifier_comparator_can_materialize_same_claim_route_alternatives(self) -> None:
        ready = [
            {
                "target_id": "root",
                "route_id": "route-a",
                "route_readiness": {},
                "evidence_artifact_ids": [],
                "evidence_state_revision": 0,
            },
            {
                "target_id": "root",
                "route_id": "route-b",
                "route_readiness": {},
                "evidence_artifact_ids": [],
                "evidence_state_revision": 0,
            },
        ]
        with mock.patch.object(
            scheduler_module,
            "_verifier_ready_route_candidates",
            return_value=ready,
        ):
            parallel_safe = scheduler_module._verifier_candidate_actions(
                {},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
            )
            comparison_complete = scheduler_module._verifier_candidate_actions(
                {},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                distinct_claims=False,
            )

        self.assertEqual(["route-a"], [row["route_id"] for row in parallel_safe])
        self.assertEqual(
            ["route-a", "route-b"],
            [row["route_id"] for row in comparison_complete],
        )

    def test_new_advisor_directive_supersedes_stale_cross_role_request(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "root",
                    "lifecycle_status": "active",
                    "validation_status": "plausible",
                }
            ],
            "research_artifacts": [
                {
                    "artifact_id": "old-villain-directive",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 1,
                    "metadata_json": '{"advisor_followup_required": true, "next_role": "villain", "next_target_id": "root"}',
                },
                {
                    "artifact_id": "new-verifier-directive",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 2,
                    "metadata_json": '{"advisor_followup_required": true, "next_role": "strict_informal_verifier", "next_target_id": "root"}',
                },
            ],
            "recent_runs": [],
        }

        action = scheduler_module._advisor_requested_villain_action(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )

        self.assertIsNone(action)

    def test_researcher_followup_does_not_consume_verifier_directive(self) -> None:
        report = {
            "artifact_id": "verifier-directive",
            "artifact_type": "advisor_report",
            "producer_role": "phd_advisor",
            "state_revision": 2,
            "metadata_json": '{"advisor_followup_required": true, "next_role": "strict_informal_verifier", "next_route_id": "route-root"}',
        }
        state = {
            "claims": [
                {
                    "claim_id": "root",
                    "lifecycle_status": "active",
                    "validation_status": "plausible",
                }
            ],
            "routes": [
                {
                    "route_id": "route-root",
                    "conclusion_claim_id": "root",
                    "status": "active",
                }
            ],
            "inferences": [],
            "research_artifacts": [report],
            "recent_runs": [
                {
                    "run_id": "researcher-followup",
                    "actor_role": "researcher",
                    "mode": "reduce",
                    "status": "completed",
                    "state_revision": 3,
                    "search_intent": scheduler_module.ADVISOR_FOLLOWUP_RESEARCH_INTENT,
                }
            ],
        }
        with mock.patch.object(
            scheduler_module, "paused_route_ids", return_value=set()
        ), mock.patch.object(
            scheduler_module,
            "_route_readiness_scorecard",
            return_value={"verifier_ready": True},
        ), mock.patch.object(
            scheduler_module,
            "_route_evidence_artifact_ids",
            return_value=[],
        ):
            action = scheduler_module._advisor_requested_strict_verifier_action(
                state,
                problem={},
                requested_tokens=None,
                research_mode="balanced",
            )

        self.assertIsNotNone(action)
        self.assertEqual("verifier-directive", action["advisor_report_id"])

    def test_unrelated_or_failed_run_does_not_consume_advisor_validation(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "root",
                    "lifecycle_status": "active",
                    "validation_status": "challenged",
                },
                {
                    "claim_id": "lemma-a",
                    "lifecycle_status": "active",
                    "validation_status": "challenged",
                },
            ],
            "research_artifacts": [
                {
                    "artifact_id": "advisor-validation",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 4,
                    "metadata_json": '{"advisor_followup_required": true, "next_role": "counterexample_validator", "next_target_id": "root", "candidate_counterexample_artifact_id": "candidate-root"}',
                },
                {
                    "artifact_id": "candidate-root",
                    "artifact_type": "candidate_counterexample",
                    "state_revision": 3,
                    "metadata_json": '{"target_id": "root", "concrete_instance": "K"}',
                },
            ],
            "recent_runs": [
                {
                    "mode": "validate_counterexample",
                    "target_id": "lemma-a",
                    "status": "completed",
                    "state_revision": 5,
                },
                {
                    "mode": "validate_counterexample",
                    "target_id": "root",
                    "status": "failed",
                    "state_revision": 6,
                },
            ],
        }

        action = scheduler_module._advisor_requested_validation_action(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )

        self.assertIsNotNone(action)
        self.assertEqual("candidate-root", action["candidate_counterexample_artifact_id"])

    def test_precondition_stratum_materializes_every_front_door_candidate(self) -> None:
        context_actions = [
            {
                "mode": "prove",
                "target_id": "root",
                "route_id": "",
                "context_request_ids": ["request-a"],
            },
            {
                "mode": "reduce",
                "target_id": "lemma-b",
                "route_id": "route-b",
                "context_request_ids": ["request-b"],
            },
        ]
        formalization_actions = [
            {
                "mode": "formalize",
                "target_id": "lemma-c",
                "route_id": "route-c",
                "formalization_proof_obligation_id": "formal-c",
            },
            {
                "mode": "formalize",
                "target_id": "lemma-d",
                "route_id": "route-d",
                "formalization_proof_obligation_id": "formal-d",
            },
        ]
        state = {"recent_runs": []}
        with mock.patch.object(
            scheduler_module,
            "_pending_context_request_actions",
            return_value=context_actions,
        ), mock.patch.object(
            scheduler_module,
            "is_writing_revision_state",
            return_value=True,
        ), mock.patch.object(
            scheduler_module,
            "_external_writing_revision_action",
            return_value={"mode": "write", "target_id": "root", "route_id": ""},
        ), mock.patch.object(
            scheduler_module,
            "_paper_audit_verification_only_action",
            return_value={"mode": "prove", "target_id": "root", "route_id": ""},
        ), mock.patch.object(
            scheduler_module,
            "_publication_route_error_research_action",
            return_value={"mode": "reduce", "target_id": "root", "route_id": ""},
        ), mock.patch.object(
            scheduler_module,
            "_requested_formalization_actions",
            return_value=formalization_actions,
        ):
            selected = scheduler_module._precondition_gate_action(
                mock.Mock(spec=ProofStateStore),
                state,
                problem={},
                requested_tokens=None,
                research_mode="balanced",
            )

        self.assertEqual(["request-a"], selected["context_request_ids"])
        trace = selected["_base_policy_trace"]
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual(
            [
                "base_context:request-a",
                "base_context:request-b",
                "base_precondition:external_writing_revision",
                "base_precondition:paper_audit",
                "base_precondition:publication_route_repair",
                "base_formalization:formal-c",
                "base_formalization:formal-d",
            ],
            [row["candidate_id"] for row in trace["candidates"]],
        )
        self.assertTrue(all(row["mandatory_constraint"] for row in trace["candidates"]))
        self.assertEqual([], decision_trace_errors(trace))

    def test_precondition_stratum_bounds_starvation_among_safety_peers(self) -> None:
        prior_trace = {
            "candidates": [
                {
                    "candidate_id": "base_context:request-a",
                    "admissible": True,
                    "disposition": "selected",
                },
                {
                    "candidate_id": "base_precondition:external_writing_revision",
                    "admissible": True,
                    "disposition": "rejected_by_ordinal_comparison",
                },
            ]
        }
        state = {
            "recent_runs": [
                {"decision_trace_json": json.dumps(prior_trace)} for _ in range(3)
            ]
        }
        with mock.patch.object(
            scheduler_module,
            "_pending_context_request_actions",
            return_value=[
                {
                    "mode": "prove",
                    "target_id": "root",
                    "route_id": "",
                    "context_request_ids": ["request-a"],
                }
            ],
        ), mock.patch.object(
            scheduler_module,
            "is_writing_revision_state",
            return_value=True,
        ), mock.patch.object(
            scheduler_module,
            "_external_writing_revision_action",
            return_value={"mode": "write", "target_id": "root", "route_id": ""},
        ), mock.patch.object(
            scheduler_module,
            "_paper_audit_verification_only_action",
            return_value=None,
        ), mock.patch.object(
            scheduler_module,
            "_publication_route_error_research_action",
            return_value=None,
        ), mock.patch.object(
            scheduler_module,
            "_requested_formalization_actions",
            return_value=[],
        ):
            selected = scheduler_module._precondition_gate_action(
                mock.Mock(spec=ProofStateStore),
                state,
                problem={},
                requested_tokens=None,
                research_mode="balanced",
            )

        self.assertEqual("write", selected["mode"])
        trace = selected["_base_policy_trace"]
        self.assertEqual(
            "base_precondition:external_writing_revision",
            trace["selected_candidate_id"],
        )
        self.assertEqual([], decision_trace_errors(trace))

    def test_open_problem_comparator_prioritizes_verification_over_text_cadence(
        self,
    ) -> None:
        state = {"recent_runs": []}
        periodic_text = {
            "mode": "write",
            "target_id": "root",
            "route_id": "",
            "periodic_hmt": True,
        }
        verification = {
            "mode": "prove",
            "target_id": "lemma",
            "route_id": "route-lemma",
            "verify_ready_route_policy": True,
        }
        _, verification_trace = select_action_candidate(
            [
                ActionCandidate(
                    "base_verification:route-lemma",
                    "verification_handoff",
                    verification,
                    1.0,
                    policy_tier=scheduler_module.POLICY_TIER_VERIFICATION,
                )
            ],
            candidate_set_complete=True,
        )
        verification["_base_policy_trace"] = verification_trace
        residual = {
            "mode": "reduce",
            "target_id": "root",
            "route_id": "",
        }
        with (
            mock.patch.object(
                scheduler_module,
                "_active_decomposition_plan_step",
                return_value=None,
            ),
            mock.patch.object(
                scheduler_module, "_active_main_trunk_pressure", return_value={}
            ),
            mock.patch.object(
                scheduler_module, "active_frontier_pressure", return_value={}
            ),
            mock.patch.object(
                scheduler_module, "_refuted_root_revision_action", return_value=None
            ),
            mock.patch.object(
                scheduler_module, "_integration_gate_action", return_value=None
            ),
            mock.patch.object(
                scheduler_module,
                "_post_integration_proof_spine_action",
                return_value=None,
            ),
            mock.patch.object(
                scheduler_module, "_periodic_hmt_action", return_value=periodic_text
            ),
            mock.patch.object(
                scheduler_module,
                "_verification_handoff_action",
                return_value=verification,
            ),
            mock.patch.object(
                scheduler_module, "_root_refinement_action", return_value=None
            ),
            mock.patch.object(
                scheduler_module, "_evidence_assimilation_action", return_value=None
            ),
            mock.patch.object(
                scheduler_module, "_circling_redirect_action", return_value=None
            ),
            mock.patch.object(
                scheduler_module, "_recovery_synthesis_action", return_value=None
            ),
            mock.patch.object(
                scheduler_module, "_obligation_routing_action", return_value=None
            ),
            mock.patch.object(
                scheduler_module, "_residual_work_action", return_value=residual
            ),
        ):
            action = scheduler_module._open_problem_action(
                mock.Mock(),
                state,
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
                allow_integration=True,
                include_periodic_hmt=True,
            )

        trace = action["_base_policy_trace"]
        self.assertEqual(
            "base_open_problem:verification_handoff",
            trace["selected_candidate_id"],
        )
        self.assertEqual(
            {
                "base_open_problem:periodic_mathematical_text",
                "base_open_problem:verification_handoff",
                "base_open_problem:residual_mathematical_work",
            },
            {row["candidate_id"] for row in trace["candidates"]},
        )
        self.assertEqual(
            verification_trace,
            trace["nested_policy_traces"][
                "base_open_problem:verification_handoff"
            ],
        )
        self.assertEqual([], decision_trace_errors(trace))

    def test_formalization_stratum_materializes_every_due_obligation(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "lemma-a",
                    "validation_status": "informally_verified",
                },
                {
                    "claim_id": "lemma-b",
                    "validation_status": "informally_verified",
                },
            ],
            "routes": [
                {
                    "route_id": "route-b-2",
                    "conclusion_claim_id": "lemma-b",
                    "status": "active",
                },
                {
                    "route_id": "route-b-1",
                    "conclusion_claim_id": "lemma-b",
                    "status": "active",
                },
            ],
            "debts": [
                {
                    "debt_id": "formal-b",
                    "owner_type": "claim",
                    "owner_id": "lemma-b",
                    "debt_type": "formalization_gap",
                    "severity": "blocking",
                    "status": "active",
                    "last_seen": "2026-02-01T00:00:00+00:00",
                },
                {
                    "debt_id": "formal-a",
                    "owner_type": "claim",
                    "owner_id": "lemma-a",
                    "debt_type": "formalization_gap",
                    "severity": "blocking",
                    "status": "active",
                    "last_seen": "2026-01-01T00:00:00+00:00",
                },
            ],
            "recent_runs": [],
        }
        selected = scheduler_module._formalization_request_action(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )
        self.assertEqual("lemma-a", selected["target_id"])
        trace = selected["_base_policy_trace"]
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual(
            ["base_formalization:formal-a", "base_formalization:formal-b"],
            [row["candidate_id"] for row in trace["candidates"]],
        )
        route_b = next(
            action
            for action in scheduler_module._requested_formalization_actions(
                state,
                problem={},
                requested_tokens=None,
                research_mode="balanced",
            )
            if action["target_id"] == "lemma-b"
        )
        self.assertEqual("route-b-1", route_b["route_id"])
        self.assertEqual([], decision_trace_errors(trace))

    def test_context_request_stratum_materializes_every_session_group(self) -> None:
        state = {
            "recent_runs": [],
            "context_requests": [
                {
                    "request_id": "request-a",
                    "status": "pending",
                    "requested_at": "2026-01-01T00:00:00+00:00",
                    "requester_role": "researcher",
                    "request_mode": "prove",
                    "original_target_id": "root",
                    "original_route_id": "route-root",
                    "requested_entity_type": "claim",
                    "requested_claim_id": "lemma-a",
                },
                {
                    "request_id": "request-empty",
                    "status": "pending",
                    "requested_at": "2026-01-02T00:00:00+00:00",
                    "requester_role": "researcher",
                    "request_mode": "prove",
                    "original_target_id": "root",
                    "original_route_id": "route-root",
                    "requested_entity_type": "claim",
                },
                {
                    "request_id": "request-b",
                    "status": "pending",
                    "requested_at": "2026-01-03T00:00:00+00:00",
                    "requester_role": "phd_advisor",
                    "request_mode": "reduce",
                    "original_target_id": "lemma-b",
                    "original_route_id": "route-b",
                    "requested_entity_type": "proof_obligation",
                    "requested_proof_obligation_id": "obligation-b",
                },
            ],
        }
        selected = scheduler_module._context_request_action(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )
        self.assertEqual(["request-a"], selected["context_request_ids"])
        self.assertEqual(
            [{"entity_id": "lemma-a", "entity_type": "claim"}],
            selected["requested_context_entities"],
        )
        trace = selected["_base_policy_trace"]
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual(
            ["base_context:request-a", "base_context:request-b"],
            [row["candidate_id"] for row in trace["candidates"]],
        )
        self.assertEqual([], decision_trace_errors(trace))

    def test_evidence_stratum_materializes_simultaneous_policies(self) -> None:
        exact_search = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "route-root",
            "debt_id": "citation-obligation-a",
            "scheduler_policy_id": "verifier_blocked_exact_theorem_search",
        }
        citation = {
            "mode": "prove",
            "target_id": "root",
            "route_id": "",
            "retrieval_card_id": "citation-card-a",
            "scheduler_policy_id": "citation_triage",
        }
        definition = {
            "mode": "audit_definitions",
            "target_id": "root",
            "route_id": "",
            "retrieval_card_id": "definition-card-a",
            "scheduler_policy_id": "definition_audit",
        }
        inactive = mock.Mock(return_value=None)
        no_actions = mock.Mock(return_value=[])
        with mock.patch.multiple(
            scheduler_module,
            _verifier_blocked_citation_actions=mock.Mock(return_value=[exact_search]),
            _source_adaptation_actions=no_actions,
            _proof_candidate_route_conversion_actions=no_actions,
            _executive_advisor_bottleneck_action=inactive,
            _near_solution_spine_synthesis_action=inactive,
            _stream_stall_recovery_action=inactive,
            _external_citation_actions=mock.Mock(return_value=[citation]),
            _definition_audit_actions=mock.Mock(return_value=[definition]),
        ):
            selected = scheduler_module._evidence_assimilation_action(
                {},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
                parent_implication_ready=False,
            )
        self.assertIsNotNone(selected)
        self.assertEqual("retrieve", selected["mode"])
        trace = selected.pop("_base_policy_trace")
        self.assertEqual(
            [
                "base_evidence:exact_support_theorem_search:citation-obligation-a",
                "base_evidence:external_citation_check:citation-card-a",
                "base_evidence:definition_audit:definition-card-a",
            ],
            [row["candidate_id"] for row in trace["candidates"]],
        )
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual([], decision_trace_errors(trace))

    def test_evidence_stratum_materializes_every_eligible_object(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "root",
                    "validation_status": "unverified",
                    "lifecycle_status": "open",
                }
            ],
            "routes": [],
            "inferences": [],
            "debts": [
                {
                    "debt_id": debt_id,
                    "owner_type": "claim",
                    "owner_id": "root",
                    "debt_type": "missing_reference",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": f"locate exact theorem {debt_id}",
                }
                for debt_id in ("citation-a", "citation-b")
            ],
            "research_artifacts": [
                {
                    "artifact_id": "source-old",
                    "artifact_type": "source_adaptation_notes",
                    "state_revision": 2,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "metadata_json": {"target_id": "root"},
                },
                {
                    "artifact_id": "source-new",
                    "artifact_type": "source_synthesis_report",
                    "state_revision": 3,
                    "created_at": "2026-01-02T00:00:00+00:00",
                    "metadata_json": {"target_id": "root"},
                },
                {
                    "artifact_id": "proof-old",
                    "artifact_type": "proof_dossier",
                    "state_revision": 4,
                    "content_summary": "verifier-ready proof candidate",
                    "metadata_json": {
                        "proof_candidate": True,
                        "target_id": "root",
                    },
                },
                {
                    "artifact_id": "proof-new",
                    "artifact_type": "proof_blueprint",
                    "state_revision": 5,
                    "content_summary": "verifier-ready proof candidate",
                    "metadata_json": {
                        "proof_candidate": True,
                        "target_id": "root",
                    },
                },
            ],
            "retrieval_cards": [
                {
                    "card_id": "external-a",
                    "applicability_json": {
                        "target_id": "root",
                        "classification": "direct_match",
                        "implication_to_target_verified": True,
                        "program_victory_candidate": True,
                    },
                    "missing_hypotheses_json": [],
                },
                {
                    "card_id": "external-b",
                    "applicability_json": {
                        "target_id": "root",
                        "classification": "stronger_match",
                        "implication_to_target_verified": True,
                        "program_victory_candidate": True,
                    },
                    "missing_hypotheses_json": [],
                },
                {
                    "card_id": "audit-a",
                    "applicability_json": {
                        "target_id": "root",
                        "classification": "conditional_match",
                    },
                    "missing_hypotheses_json": ["definition of regularity"],
                },
                {
                    "card_id": "audit-b",
                    "applicability_json": {
                        "target_id": "root",
                        "classification": "equivalent_reformulation",
                        "theorem_matching_status": "unverified",
                    },
                    "missing_hypotheses_json": [],
                },
            ],
            "recent_runs": [],
        }

        self.assertEqual(
            ["citation-a", "citation-b"],
            [
                action["debt_id"]
                for action in scheduler_module._verifier_blocked_citation_actions(
                    state,
                    problem={},
                    requested_tokens=None,
                    research_mode="balanced",
                    web_search="disabled",
                )
            ],
        )
        self.assertEqual(
            ["source-new", "source-old"],
            [
                action["source_artifact_id"]
                for action in scheduler_module._source_adaptation_actions(
                    state,
                    problem={},
                    requested_tokens=None,
                    research_mode="balanced",
                )
            ],
        )
        self.assertEqual(
            ["proof-new", "proof-old"],
            [
                action["proof_candidate_artifact_id"]
                for action in scheduler_module._proof_candidate_route_conversion_actions(
                    state,
                    problem={},
                    requested_tokens=None,
                    research_mode="balanced",
                )
            ],
        )
        self.assertEqual(
            ["external-a", "external-b"],
            [
                action["retrieval_card_id"]
                for action in scheduler_module._external_citation_actions(
                    state,
                    problem={},
                    requested_tokens=None,
                    research_mode="balanced",
                )
            ],
        )
        self.assertEqual(
            ["audit-a", "audit-b"],
            sorted(
                action["retrieval_card_id"]
                for action in scheduler_module._definition_audit_actions(
                    state,
                    problem={},
                    requested_tokens=None,
                    research_mode="balanced",
                )
            ),
        )

        selected = scheduler_module._evidence_assimilation_action(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
            web_search="disabled",
            parent_implication_ready=False,
        )
        trace = selected["_base_policy_trace"]
        candidate_ids = [row["candidate_id"] for row in trace["candidates"]]
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual(10, len(candidate_ids))
        self.assertEqual(10, len(set(candidate_ids)))
        self.assertEqual(
            {
                "base_evidence:exact_support_theorem_search:citation-a",
                "base_evidence:exact_support_theorem_search:citation-b",
                "base_evidence:source_adaptation:source-new",
                "base_evidence:source_adaptation:source-old",
                "base_evidence:proof_draft_route_conversion:proof-new",
                "base_evidence:proof_draft_route_conversion:proof-old",
                "base_evidence:external_citation_check:external-a",
                "base_evidence:external_citation_check:external-b",
                "base_evidence:definition_audit:audit-a",
                "base_evidence:definition_audit:audit-b",
            },
            set(candidate_ids),
        )
        self.assertEqual([], decision_trace_errors(trace))

    def test_exact_search_cooldown_is_scoped_to_the_exact_obligation(self) -> None:
        state = {
            "claims": [{"claim_id": "root", "validation_status": "unverified"}],
            "routes": [],
            "inferences": [],
            "debts": [
                {
                    "debt_id": obligation_id,
                    "owner_type": "claim",
                    "owner_id": "root",
                    "debt_type": "missing_reference",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": f"locate theorem {obligation_id}",
                }
                for obligation_id in ("citation-a", "citation-b")
            ],
            "recent_runs": [
                {
                    "search_intent": scheduler_module.EXACT_THEOREM_SEARCH_INTENT,
                    "target_id": "root",
                    "route_id": "",
                    "decision_trace": {
                        "candidates": [
                            {
                                "candidate_id": "base_evidence:exact_support_theorem_search:citation-a",
                                "admissible": True,
                                "disposition": "selected",
                            },
                            {
                                "candidate_id": "base_evidence:exact_support_theorem_search:citation-b",
                                "admissible": True,
                                "disposition": "rejected_by_ordinal_comparison",
                            },
                        ]
                    },
                }
            ],
        }
        actions = scheduler_module._verifier_blocked_citation_actions(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
            web_search="disabled",
        )
        self.assertEqual(["citation-b"], [action["debt_id"] for action in actions])

    def test_omitted_trace_identity_does_not_consume_peer_obligations(self) -> None:
        state = {
            "claims": [{"claim_id": "root", "validation_status": "unverified"}],
            "routes": [],
            "inferences": [],
            "debts": [
                {
                    "debt_id": obligation_id,
                    "owner_type": "claim",
                    "owner_id": "root",
                    "debt_type": "missing_reference",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": f"locate theorem {obligation_id}",
                }
                for obligation_id in ("citation-a", "citation-b")
            ],
            "recent_runs": [
                {
                    "search_intent": scheduler_module.EXACT_THEOREM_SEARCH_INTENT,
                    "target_id": "root",
                    "route_id": "",
                    "status": "completed",
                    "decision_trace_json": "{}",
                    "decision_trace_history_included": False,
                }
            ],
        }
        actions = scheduler_module._verifier_blocked_citation_actions(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
            web_search="disabled",
        )
        self.assertEqual(
            ["citation-a", "citation-b"],
            [action["debt_id"] for action in actions],
        )

    def test_evidence_completion_never_consumes_unselected_peer_objects(self) -> None:
        def completed_run(intent: str, selected_id: str, rejected_id: str) -> dict:
            return {
                "search_intent": intent,
                "target_id": "root",
                "route_id": "",
                "status": "completed",
                "decision_trace": {
                    "candidates": [
                        {
                            "candidate_id": selected_id,
                            "admissible": True,
                            "disposition": "selected",
                        },
                        {
                            "candidate_id": rejected_id,
                            "admissible": True,
                            "disposition": "rejected_by_ordinal_comparison",
                        },
                    ]
                },
            }

        state = {
            "claims": [{"claim_id": "root", "validation_status": "unverified"}],
            "routes": [],
            "inferences": [],
            "debts": [],
            "research_artifacts": [
                {
                    "artifact_id": source_id,
                    "artifact_type": "source_adaptation_notes",
                    "state_revision": revision,
                    "metadata_json": {"target_id": "root"},
                }
                for source_id, revision in (("source-old", 1), ("source-new", 2))
            ]
            + [
                {
                    "artifact_id": proof_id,
                    "artifact_type": "proof_dossier",
                    "state_revision": revision,
                    "content_summary": "verifier-ready proof candidate",
                    "metadata_json": {
                        "proof_candidate": True,
                        "target_id": "root",
                    },
                }
                for proof_id, revision in (("proof-old", 3), ("proof-new", 4))
            ],
            "retrieval_cards": [
                {
                    "card_id": card_id,
                    "applicability_json": {
                        "target_id": "root",
                        "classification": "direct_match",
                        "implication_to_target_verified": True,
                        "program_victory_candidate": True,
                    },
                    "missing_hypotheses_json": [],
                }
                for card_id in ("external-a", "external-b")
            ]
            + [
                {
                    "card_id": card_id,
                    "applicability_json": {
                        "target_id": "root",
                        "classification": "conditional_match",
                    },
                    "missing_hypotheses_json": ["definition mismatch"],
                }
                for card_id in ("audit-a", "audit-b")
            ],
            "recent_runs": [
                completed_run(
                    "source_adaptation_digest",
                    "base_evidence:source_adaptation:source-new",
                    "base_evidence:source_adaptation:source-old",
                ),
                completed_run(
                    scheduler_module.PROOF_CANDIDATE_ROUTE_CONVERSION_INTENT,
                    "base_evidence:proof_draft_route_conversion:proof-new",
                    "base_evidence:proof_draft_route_conversion:proof-old",
                ),
                completed_run(
                    "citation_triage",
                    "base_evidence:external_citation_check:external-a",
                    "base_evidence:external_citation_check:external-b",
                ),
                completed_run(
                    "definition_audit",
                    "base_evidence:definition_audit:audit-a",
                    "base_evidence:definition_audit:audit-b",
                ),
            ],
        }

        self.assertEqual(
            ["source-old"],
            [item["artifact_id"] for item in scheduler_module._pending_source_handoff_digests(state)],
        )
        self.assertEqual(
            ["proof-old"],
            [item["artifact_id"] for item in scheduler_module._unrouted_proof_candidates(state)],
        )
        citation_actions = scheduler_module._external_citation_actions(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )
        self.assertEqual(
            {
                "external-a": "citation_certification",
                "external-b": "citation_triage",
            },
            {
                item["retrieval_card_id"]: item["search_intent"]
                for item in citation_actions
            },
        )
        self.assertEqual(
            ["audit-b"],
            [
                item["card_id"]
                for item in scheduler_module._definition_audit_candidates(
                    state, target_id="root"
                )
            ],
        )

    def test_durable_evidence_results_suppress_only_their_exact_subjects(self) -> None:
        state = {
            "claims": [{"claim_id": "root", "validation_status": "unverified"}],
            "routes": [],
            "inferences": [],
            "debts": [],
            "recent_runs": [],
            "research_artifacts": [
                *[
                    {
                        "artifact_id": source_id,
                        "artifact_type": "source_adaptation_notes",
                        "state_revision": revision,
                        "metadata_json": {"target_id": "root"},
                    }
                    for source_id, revision in (("source-a", 1), ("source-b", 2))
                ],
                *[
                    {
                        "artifact_id": proof_id,
                        "artifact_type": "proof_dossier",
                        "state_revision": revision,
                        "content_summary": "verifier-ready proof candidate",
                        "metadata_json": {
                            "proof_candidate": True,
                            "target_id": "root",
                        },
                    }
                    for proof_id, revision in (("proof-a", 3), ("proof-b", 4))
                ],
                {
                    "artifact_id": "source-a-result",
                    "artifact_type": "research_notebook",
                    "state_revision": 5,
                    "metadata_json": {"adapted_source_artifact_id": "source-a"},
                },
                {
                    "artifact_id": "proof-a-classification",
                    "artifact_type": "research_diagnostic",
                    "state_revision": 6,
                    "metadata_json": {"proof_candidate_artifact_id": "proof-a"},
                },
                {
                    "artifact_id": "external-a-triage",
                    "artifact_type": "verification_report",
                    "state_revision": 7,
                    "metadata_json": {
                        "retrieval_card_id": "external-a",
                        "verdict": "citation_triage_fail",
                    },
                },
                {
                    "artifact_id": "audit-a-report",
                    "artifact_type": "definition_audit_report",
                    "state_revision": 8,
                    "metadata_json": {"retrieval_card_id": "audit-a"},
                },
            ],
            "retrieval_cards": [
                *[
                    {
                        "card_id": card_id,
                        "applicability_json": {
                            "target_id": "root",
                            "classification": "direct_match",
                            "implication_to_target_verified": True,
                            "program_victory_candidate": True,
                        },
                        "missing_hypotheses_json": [],
                    }
                    for card_id in ("external-a", "external-b")
                ],
                *[
                    {
                        "card_id": card_id,
                        "applicability_json": {
                            "target_id": "root",
                            "classification": "conditional_match",
                        },
                        "missing_hypotheses_json": ["definition mismatch"],
                    }
                    for card_id in ("audit-a", "audit-b")
                ],
            ],
        }

        self.assertEqual(
            ["source-b"],
            [item["artifact_id"] for item in scheduler_module._pending_source_handoff_digests(state)],
        )
        self.assertEqual(
            ["proof-b"],
            [item["artifact_id"] for item in scheduler_module._unrouted_proof_candidates(state)],
        )
        self.assertEqual(
            ["external-b"],
            [
                item["card_id"]
                for item in scheduler_module._external_citation_candidates(
                    state, target_id="root"
                )
            ],
        )
        self.assertEqual(
            ["audit-b"],
            [
                item["card_id"]
                for item in scheduler_module._definition_audit_candidates(
                    state, target_id="root"
                )
            ],
        )

    def test_nested_policy_deferrals_prevent_evidence_policy_starvation(self) -> None:
        exact_search = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "route-root",
            "debt_id": "citation-obligation-a",
            "scheduler_policy_id": "verifier_blocked_exact_theorem_search",
        }
        citation = {
            "mode": "prove",
            "target_id": "root",
            "route_id": "",
            "retrieval_card_id": "citation-card-a",
            "scheduler_policy_id": "citation_triage",
        }
        nested_trace = {
            "candidates": [
                {
                    "candidate_id": "base_evidence:exact_support_theorem_search:citation-obligation-a",
                    "admissible": True,
                    "disposition": "selected",
                },
                {
                    "candidate_id": "base_evidence:external_citation_check:citation-card-a",
                    "admissible": True,
                    "disposition": "rejected_by_ordinal_comparison",
                },
            ]
        }
        state = {
            "recent_runs": [
                {
                    "decision_trace": {
                        "selected_candidate_id": "base:sequential_planner",
                        "candidates": [],
                        "base_policy_trace": nested_trace,
                    }
                }
                for _ in range(scheduler_module.SCHEDULER_DEFERRAL_LIMIT)
            ]
        }
        inactive = mock.Mock(return_value=None)
        no_actions = mock.Mock(return_value=[])
        with mock.patch.multiple(
            scheduler_module,
            _verifier_blocked_citation_actions=mock.Mock(return_value=[exact_search]),
            _source_adaptation_actions=no_actions,
            _proof_candidate_route_conversion_actions=no_actions,
            _executive_advisor_bottleneck_action=inactive,
            _near_solution_spine_synthesis_action=inactive,
            _stream_stall_recovery_action=inactive,
            _external_citation_actions=mock.Mock(return_value=[citation]),
            _definition_audit_actions=no_actions,
        ):
            selected = scheduler_module._evidence_assimilation_action(
                state,
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
                parent_implication_ready=False,
            )
        self.assertEqual("citation_triage", selected["scheduler_policy_id"])
        trace = selected["_base_policy_trace"]
        citation_row = next(
            row
            for row in trace["candidates"]
            if row["candidate_id"]
            == "base_evidence:external_citation_check:citation-card-a"
        )
        self.assertEqual(
            scheduler_module.SCHEDULER_DEFERRAL_LIMIT,
            citation_row["consecutive_deferrals"],
        )
        self.assertEqual("selected", citation_row["disposition"])
        self.assertEqual([], decision_trace_errors(trace))

    def test_object_keyed_deferrals_prevent_same_queue_starvation(self) -> None:
        first = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "",
            "debt_id": "citation-a",
        }
        second = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "",
            "debt_id": "citation-b",
        }
        state = {
            "recent_runs": [
                {
                    "decision_trace": {
                        "candidates": [
                            {
                                "candidate_id": "base_evidence:exact_support_theorem_search:citation-a",
                                "admissible": True,
                                "disposition": "selected",
                            },
                            {
                                "candidate_id": "base_evidence:exact_support_theorem_search:citation-b",
                                "admissible": True,
                                "disposition": "rejected_by_ordinal_comparison",
                            },
                        ]
                    }
                }
                for _ in range(scheduler_module.SCHEDULER_DEFERRAL_LIMIT)
            ]
        }
        no_actions = mock.Mock(return_value=[])
        inactive = mock.Mock(return_value=None)
        with mock.patch.multiple(
            scheduler_module,
            _verifier_blocked_citation_actions=mock.Mock(
                return_value=[first, second]
            ),
            _source_adaptation_actions=no_actions,
            _proof_candidate_route_conversion_actions=no_actions,
            _executive_advisor_bottleneck_action=inactive,
            _near_solution_spine_synthesis_action=inactive,
            _stream_stall_recovery_action=inactive,
            _external_citation_actions=no_actions,
            _definition_audit_actions=no_actions,
        ):
            selected = scheduler_module._evidence_assimilation_action(
                state,
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
                parent_implication_ready=False,
            )
        self.assertEqual("citation-b", selected["debt_id"])
        trace = selected["_base_policy_trace"]
        selected_row = next(
            row
            for row in trace["candidates"]
            if row["candidate_id"].endswith(":citation-b")
        )
        self.assertEqual(
            scheduler_module.SCHEDULER_DEFERRAL_LIMIT,
            selected_row["consecutive_deferrals"],
        )
        self.assertEqual("selected", selected_row["disposition"])

    def test_nested_local_selection_is_deferred_when_parent_is_rejected(self) -> None:
        nested_trace = {
            "candidates": [
                {
                    "candidate_id": "base_evidence:exact_support_theorem_search",
                    "admissible": True,
                    "disposition": "selected",
                }
            ]
        }
        nested_digest = policy_trace_sha256(nested_trace)
        state = {
            "recent_runs": [
                {
                    "decision_trace": {
                        "selected_candidate_id": "research_strategy:proof_compression:default",
                        "candidates": [
                            {
                                "candidate_id": "base:sequential_planner",
                                "base_policy_trace_sha256": nested_digest,
                                "admissible": True,
                                "disposition": "rejected_by_policy_tier",
                            },
                            {
                                "candidate_id": "research_strategy:proof_compression:default",
                                "admissible": True,
                                "disposition": "selected",
                            },
                        ],
                        "base_policy_trace": nested_trace,
                    }
                }
            ]
        }
        self.assertEqual(
            1,
            scheduler_module._consecutive_candidate_deferrals(
                state, "base_evidence:exact_support_theorem_search"
            ),
        )

    def test_stratum_deferral_history_is_parsed_once_per_distinct_trace(self) -> None:
        generated = [
            (
                f"policy-{index}",
                {"mode": "prove", "target_id": f"claim-{index}"},
            )
            for index in range(12)
        ]
        trace_text = json.dumps(
            {
                "candidates": [
                    {
                        "candidate_id": f"batch:policy-{index}",
                        "admissible": True,
                        "disposition": "rejected_by_ordinal_comparison",
                    }
                    for index in range(12)
                ]
            }
        )
        state = {
            "recent_runs": [
                {"decision_trace_json": trace_text} for _ in range(3)
            ]
        }
        original_loads = json.loads
        with mock.patch.object(
            scheduler_module.json, "loads", wraps=original_loads
        ) as loads:
            counts = scheduler_module._generated_policy_deferrals(
                state, "batch", generated
            )
        self.assertEqual(1, loads.call_count)
        self.assertEqual({3}, set(counts.values()))

    def test_planning_snapshot_parses_deferral_history_once_across_strata(self) -> None:
        trace_text = json.dumps(
            {
                "candidates": [
                    {
                        "candidate_id": candidate_id,
                        "admissible": True,
                        "disposition": "rejected_by_ordinal_comparison",
                    }
                    for candidate_id in ("first:a", "second:b")
                ]
            }
        )
        state = scheduler_module._enable_scheduler_planning_cache(
            {
                "recent_runs": [
                    {"decision_trace_json": trace_text} for _ in range(3)
                ]
            }
        )
        original_loads = json.loads
        with mock.patch.object(
            scheduler_module.json, "loads", wraps=original_loads
        ) as loads:
            first = scheduler_module._generated_policy_deferrals(
                state,
                "first",
                [("a", {"mode": "prove", "target_id": "root"})],
            )
            second = scheduler_module._generated_policy_deferrals(
                state,
                "second",
                [("b", {"mode": "reduce", "target_id": "lemma"})],
            )
        self.assertEqual(1, loads.call_count)
        self.assertEqual({"first:a": 3}, first)
        self.assertEqual({"second:b": 3}, second)

    def test_parent_implication_suppresses_only_protected_evidence_policies(self) -> None:
        protected = mock.Mock(
            side_effect=AssertionError("protected policy must not be generated")
        )
        citation = {
            "mode": "prove",
            "target_id": "root",
            "route_id": "",
            "retrieval_card_id": "citation-card-a",
            "scheduler_policy_id": "citation_triage",
        }
        with mock.patch.multiple(
            scheduler_module,
            _verifier_blocked_citation_actions=protected,
            _source_adaptation_actions=protected,
            _proof_candidate_route_conversion_actions=protected,
            _executive_advisor_bottleneck_action=protected,
            _near_solution_spine_synthesis_action=protected,
            _stream_stall_recovery_action=protected,
            _external_citation_actions=mock.Mock(return_value=[citation]),
            _definition_audit_actions=mock.Mock(return_value=[]),
        ):
            selected = scheduler_module._evidence_assimilation_action(
                {},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
                parent_implication_ready=True,
            )
        self.assertEqual("prove", selected["mode"])
        self.assertEqual(
            "base_evidence:external_citation_check:citation-card-a",
            selected["_base_policy_trace"]["selected_candidate_id"],
        )

    def test_recovery_stratum_materializes_simultaneous_policies(self) -> None:
        advisor = {
            "mode": "reduce",
            "target_id": "root",
            "route_id": "route-root",
            "scheduler_policy_id": "advisor_followup_research",
        }
        branch = {
            "mode": "reduce",
            "target_id": "lemma-a",
            "route_id": "route-a",
            "scheduler_policy_id": "productive_branch_persistence",
        }
        duplicate = {
            "mode": "triage_routes",
            "target_id": "root",
            "route_id": "route-root",
            "scheduler_policy_id": "duplicate_work_guard",
        }
        synthesis = {
            "mode": "triage_routes",
            "target_id": "root",
            "route_id": "",
            "scheduler_policy_id": "global_synthesis",
        }
        inactive = mock.Mock(return_value=None)
        no_actions = mock.Mock(return_value=[])
        with mock.patch.multiple(
            scheduler_module,
            _bottleneck_lock_actions=no_actions,
            _advisor_followup_research_action=mock.Mock(return_value=advisor),
            _advisor_followup_can_preempt_bottleneck=mock.Mock(return_value=True),
            _first_blocking_debt=inactive,
            _branch_persistence_action=mock.Mock(return_value=branch),
            _duplicate_work_suppression_action=mock.Mock(return_value=duplicate),
            _retrieve_reduce_loop_advisor_action=inactive,
            _no_content_research_guard_action=inactive,
            _proof_architecture_pressure_action=inactive,
            _creative_proof_attack_action=inactive,
            _parallel_wave_synthesis_action=inactive,
            _global_synthesis_action=mock.Mock(return_value=synthesis),
            _no_result_search_synthesis_action=inactive,
            _central_obstruction_workbench_action=inactive,
        ):
            selected = scheduler_module._recovery_synthesis_action(
                {},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                parent_implication_ready=False,
            )
        self.assertEqual("advisor_followup_research", selected["scheduler_policy_id"])
        trace = selected.pop("_base_policy_trace")
        self.assertEqual(
            [
                "base_recovery:advisor_followup",
                "base_recovery:productive_branch_persistence",
                "base_recovery:duplicate_work_guard",
                "base_recovery:global_synthesis",
            ],
            [row["candidate_id"] for row in trace["candidates"]],
        )
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual([], decision_trace_errors(trace))

    def test_recovery_stratum_materializes_every_bottleneck_obligation(self) -> None:
        locks = [
            {
                "mode": "prove",
                "target_id": "root",
                "route_id": "",
                "debt_id": obligation_id,
                "proof_obligation_id": obligation_id,
                "scheduler_policy_id": "bottleneck_lock",
            }
            for obligation_id in ("obligation-a", "obligation-b")
        ]
        inactive = mock.Mock(return_value=None)
        central_duplicate = mock.Mock(
            return_value={
                "mode": "prove",
                "target_id": "root",
                "route_id": "",
                "debt_id": "obligation-a",
            }
        )
        with mock.patch.multiple(
            scheduler_module,
            _bottleneck_lock_actions=mock.Mock(return_value=locks),
            _advisor_followup_research_action=inactive,
            _branch_persistence_action=inactive,
            _duplicate_work_suppression_action=inactive,
            _retrieve_reduce_loop_advisor_action=inactive,
            _no_content_research_guard_action=inactive,
            _proof_architecture_pressure_action=inactive,
            _creative_proof_attack_action=inactive,
            _parallel_wave_synthesis_action=inactive,
            _global_synthesis_action=inactive,
            _no_result_search_synthesis_action=inactive,
            _central_obstruction_workbench_action=central_duplicate,
        ):
            selected = scheduler_module._recovery_synthesis_action(
                {"recent_runs": []},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                parent_implication_ready=False,
            )
        trace = selected["_base_policy_trace"]
        self.assertEqual(
            [
                "base_recovery:bottleneck_lock:obligation-a",
                "base_recovery:bottleneck_lock:obligation-b",
            ],
            [row["candidate_id"] for row in trace["candidates"]],
        )
        self.assertEqual(
            "base_recovery:bottleneck_lock:obligation-a",
            trace["selected_candidate_id"],
        )
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual([], decision_trace_errors(trace))
        central_duplicate.assert_not_called()

    def test_bottleneck_signal_generator_returns_every_eligible_obligation(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "root",
                    "statement": "Root theorem.",
                    "validation_status": "untested",
                    "lifecycle_status": "active",
                    "root_impact": 1.0,
                    "reduction_depth": 0,
                    "parent_ids": [],
                }
            ],
            "routes": [],
            "inferences": [],
            "research_artifacts": [],
            "retrieval_cards": [],
            "recent_runs": [],
            "debts": [
                {
                    "debt_id": obligation_id,
                    "owner_type": "claim",
                    "owner_id": "root",
                    "debt_type": "central_obstruction",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": f"Prove bridge {obligation_id}.",
                    "suggested_next_target": "root",
                    "repeated_count": 3,
                    "last_seen": last_seen,
                }
                for obligation_id, last_seen in (
                    ("obligation-b", "2026-01-01T00:00:00+00:00"),
                    ("obligation-a", "2026-01-02T00:00:00+00:00"),
                )
            ],
        }

        signals = scheduler_module._bottleneck_lock_signals(state)

        self.assertEqual(
            ["obligation-a", "obligation-b"],
            [signal["debt_id"] for signal in signals],
        )

    def test_recovery_bounded_deferral_is_bottleneck_specific(self) -> None:
        locks = [
            {
                "mode": "prove",
                "target_id": "root",
                "route_id": "",
                "debt_id": obligation_id,
                "proof_obligation_id": obligation_id,
            }
            for obligation_id in ("obligation-a", "obligation-b")
        ]
        history_trace = {
            "candidates": [
                {
                    "candidate_id": "base_recovery:bottleneck_lock:obligation-a",
                    "admissible": True,
                    "disposition": "selected",
                },
                {
                    "candidate_id": "base_recovery:bottleneck_lock:obligation-b",
                    "admissible": True,
                    "disposition": "rejected_by_ordinal_comparison",
                },
            ]
        }
        state = {
            "recent_runs": [
                {
                    "actor_role": "phd_advisor",
                    "mode": "triage_routes",
                    "decision_trace_json": history_trace,
                    "decision_trace_history_included": True,
                }
                for _ in range(scheduler_module.SCHEDULER_DEFERRAL_LIMIT)
            ]
        }
        inactive = mock.Mock(return_value=None)
        with mock.patch.multiple(
            scheduler_module,
            _bottleneck_lock_actions=mock.Mock(return_value=locks),
            _advisor_followup_research_action=inactive,
            _branch_persistence_action=inactive,
            _duplicate_work_suppression_action=inactive,
            _retrieve_reduce_loop_advisor_action=inactive,
            _no_content_research_guard_action=inactive,
            _proof_architecture_pressure_action=inactive,
            _creative_proof_attack_action=inactive,
            _parallel_wave_synthesis_action=inactive,
            _global_synthesis_action=inactive,
            _no_result_search_synthesis_action=inactive,
        ):
            selected = scheduler_module._recovery_synthesis_action(
                state,
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                parent_implication_ready=False,
            )
        trace = selected["_base_policy_trace"]
        self.assertEqual(
            "base_recovery:bottleneck_lock:obligation-b",
            trace["selected_candidate_id"],
        )
        selected_row = next(
            row
            for row in trace["candidates"]
            if row["candidate_id"].endswith("obligation-b")
        )
        self.assertEqual(
            scheduler_module.SCHEDULER_DEFERRAL_LIMIT,
            selected_row["consecutive_deferrals"],
        )
        self.assertEqual([], decision_trace_errors(trace))

    def test_obligation_routing_stratum_materializes_simultaneous_policies(self) -> None:
        literature = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "route-root",
            "search_request_artifact_id": "request-a",
            "scheduler_policy_id": "requested_literature_search",
        }
        route_decision = {
            "mode": "triage_routes",
            "target_id": "root",
            "route_id": "route-root",
            "route_decision_artifact_id": "decision-a",
            "scheduler_policy_id": "route_decision",
        }
        obligation = {
            "mode": "prove",
            "target_id": "lemma-a",
            "route_id": "route-a",
            "scheduler_policy_id": "blocking_obligation",
        }
        failed_plan = {
            "mode": "regulate_decomposition",
            "target_id": "root",
            "route_id": "route-root",
            "failed_decomposition_artifact_id": "failed-plan-a",
            "scheduler_policy_id": "failed_decomposition_regulation",
        }
        inactive = mock.Mock(return_value=None)
        no_actions = mock.Mock(return_value=[])
        with mock.patch.multiple(
            scheduler_module,
            _blocking_debt_candidates=mock.Mock(return_value=[{"debt_id": "obligation-a"}]),
            _obstruction_route_conversion_actions=no_actions,
            _blocking_debt_action=mock.Mock(return_value=obligation),
            _requested_literature_actions=mock.Mock(return_value=[literature]),
            _source_synthesis_action=inactive,
            _route_decision_triage_actions=mock.Mock(return_value=[route_decision]),
            _route_pause_replacement_action=inactive,
            _route_proof_construction_quota_actions=no_actions,
            _failed_decomposition_actions=mock.Mock(return_value=[failed_plan]),
            _blocked_decomposition_actions=no_actions,
        ):
            selected = scheduler_module._obligation_routing_action(
                {},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
                active_trunk_pressure={"over_trunk_cap": False},
                frontier_pressure={},
            )
        self.assertEqual("requested_literature_search", selected["scheduler_policy_id"])
        trace = selected.pop("_base_policy_trace")
        self.assertEqual(
            [
                "base_obligation:requested_literature_search:request-a",
                "base_obligation:route_decision:decision-a",
                "base_obligation:blocking_obligation:obligation-a",
                "base_obligation:failed_decomposition_regulation:failed-plan-a",
            ],
            [row["candidate_id"] for row in trace["candidates"]],
        )
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual([], decision_trace_errors(trace))

    def test_route_routing_cooldown_consumes_only_the_selected_object(self) -> None:
        routes = [
            {
                "route_id": f"route-{suffix}",
                "conclusion_claim_id": "root",
                "relation_to_parent": "sufficient",
                "status": "active",
            }
            for suffix in ("a", "b")
        ]
        artifacts = [
            {
                "artifact_id": f"decision-{suffix}",
                "artifact_type": "proof_dossier",
                "state_revision": 2,
                "metadata_json": json.dumps(
                    {
                        "target_id": "root",
                        "route_id": f"route-{suffix}",
                        "classification": "route_killing_obstruction",
                        "route_decision": "pause",
                    }
                ),
            }
            for suffix in ("a", "b")
        ]
        state = {
            "claims": [{"claim_id": "root", "root_impact": 1.0}],
            "routes": routes,
            "inferences": [],
            "debts": [],
            "research_artifacts": artifacts,
            "recent_runs": [
                {
                    "search_intent": "route_triage",
                    "target_id": "root",
                    "route_id": "route-a",
                    "status": "completed",
                    "decision_trace": {
                        "candidates": [
                            {
                                "candidate_id": "base_obligation:route_decision:decision-a",
                                "admissible": True,
                                "disposition": "selected",
                            },
                            {
                                "candidate_id": "base_obligation:route_decision:decision-b",
                                "admissible": True,
                                "disposition": "rejected_by_ordinal_comparison",
                            },
                        ]
                    },
                }
            ],
        }
        actions = scheduler_module._route_decision_triage_actions(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )
        self.assertEqual(
            ["decision-b"],
            [action["route_decision_artifact_id"] for action in actions],
        )

        omitted_state = dict(state)
        omitted_state["recent_runs"] = [
            {
                "search_intent": "route_triage",
                "target_id": "root",
                "route_id": "route-a",
                "status": "completed",
                "decision_trace_json": "{}",
                "decision_trace_history_included": False,
            }
        ]
        actions = scheduler_module._route_decision_triage_actions(
            omitted_state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )
        self.assertEqual(
            ["decision-a", "decision-b"],
            [action["route_decision_artifact_id"] for action in actions],
        )

    def test_obligation_routing_forces_service_after_bounded_peer_deferral(self) -> None:
        artifacts = [
            {
                "artifact_id": f"request-{suffix}",
                "artifact_type": "literature_search_request",
                "state_revision": 2 if suffix == "a" else 1,
                "created_at": f"2026-01-0{2 if suffix == 'a' else 1}T00:00:00Z",
                "content_summary": f"Find theorem {suffix}",
                "metadata_json": json.dumps(
                    {
                        "search_request_id": f"search-{suffix}",
                        "target_id": "root",
                        "query": f"exact theorem {suffix}",
                    }
                ),
            }
            for suffix in ("a", "b")
        ]
        prior_trace = {
            "candidates": [
                {
                    "candidate_id": "base_obligation:requested_literature_search:request-a",
                    "admissible": True,
                    "disposition": "selected",
                },
                {
                    "candidate_id": "base_obligation:requested_literature_search:request-b",
                    "admissible": True,
                    "disposition": "rejected_by_ordinal_comparison",
                },
            ]
        }
        state = scheduler_module._enable_scheduler_planning_cache(
            {
                "problem_state": {},
                "claims": [
                    {
                        "claim_id": "root",
                        "statement": "root",
                        "hypotheses": "",
                        "parent_ids_json": "[]",
                        "evidence_artifact_ids_json": "[]",
                        "root_impact": 1.0,
                        "reduction_depth": 0,
                        "validation_status": "untested",
                        "lifecycle_status": "active",
                    }
                ],
                "routes": [],
                "inferences": [],
                "debts": [],
                "research_artifacts": artifacts,
                "retrieval_cards": [],
                "recent_runs": [
                    {
                        "search_intent": "researcher_search_request",
                        "status": "completed",
                        "decision_trace": prior_trace,
                    }
                    for _ in range(scheduler_module.SCHEDULER_DEFERRAL_LIMIT)
                ],
            }
        )
        selected = scheduler_module._obligation_routing_action(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
            web_search="disabled",
            active_trunk_pressure={"over_trunk_cap": False},
            frontier_pressure={},
        )
        self.assertEqual("request-b", selected["search_request_artifact_id"])
        trace = selected["_base_policy_trace"]
        selected_row = next(
            row
            for row in trace["candidates"]
            if row["candidate_id"].endswith(":request-b")
        )
        self.assertEqual(
            scheduler_module.SCHEDULER_DEFERRAL_LIMIT,
            selected_row["consecutive_deferrals"],
        )
        self.assertEqual("selected", selected_row["disposition"])

    def test_new_decomposition_failure_is_not_hidden_by_an_old_response(self) -> None:
        def state_with_response(response_revision: int) -> dict:
            return scheduler_module._enable_scheduler_planning_cache(
                {
                    "research_artifacts": [
                        {
                            "artifact_id": "failed-plan-current",
                            "artifact_type": "failed_decomposition_plan",
                            "state_revision": 5,
                            "metadata_json": json.dumps(
                                {
                                    "target_id": "root",
                                    "decomposition_plan_id": "plan-reused",
                                }
                            ),
                        },
                        {
                            "artifact_id": "advisor-plan-response",
                            "artifact_type": "advisor_report",
                            "state_revision": response_revision,
                            "metadata_json": json.dumps(
                                {"decomposition_plan_id": "plan-reused"}
                            ),
                        },
                    ]
                }
            )

        self.assertEqual(
            ["failed-plan-current"],
            [
                row["artifact_id"]
                for row in scheduler_module._pending_key_failure_analyses(
                    state_with_response(4)
                )
            ],
        )
        self.assertEqual(
            [],
            scheduler_module._pending_key_failure_analyses(
                state_with_response(6)
            ),
        )

        def state_with_failed_plan(failure_revision: int) -> dict:
            return scheduler_module._enable_scheduler_planning_cache(
                {
                    "research_artifacts": [
                        {
                            "artifact_id": "plan-current",
                            "artifact_type": "decomposition_plan",
                            "state_revision": 5,
                            "metadata_json": json.dumps(
                                {
                                    "decomposition_plan_id": "plan-reused",
                                    "status": "active",
                                }
                            ),
                        },
                        {
                            "artifact_id": "plan-failure",
                            "artifact_type": "failed_decomposition_plan",
                            "state_revision": failure_revision,
                            "metadata_json": json.dumps(
                                {"decomposition_plan_id": "plan-reused"}
                            ),
                        },
                    ]
                }
            )

        self.assertEqual(
            ["plan-current"],
            [
                artifact_id
                for _row, _metadata, _plan_id, artifact_id in (
                    scheduler_module._active_decomposition_plan_records(
                        state_with_failed_plan(4)
                    )
                )
            ],
        )
        self.assertEqual(
            [],
            scheduler_module._active_decomposition_plan_records(
                state_with_failed_plan(6)
            ),
        )

    def test_literature_response_index_matches_only_nonempty_exact_ids(self) -> None:
        state = scheduler_module._enable_scheduler_planning_cache(
            {
                "research_artifacts": [
                    {
                        "artifact_id": "request-a",
                        "artifact_type": "literature_search_request",
                        "state_revision": 2,
                        "metadata_json": json.dumps(
                            {"search_request_id": "search-a"}
                        ),
                    },
                    {
                        "artifact_id": "request-b",
                        "artifact_type": "literature_search_request",
                        "state_revision": 1,
                        "metadata_json": "{}",
                    },
                    {
                        "artifact_id": "source-a",
                        "artifact_type": "source_adaptation_notes",
                        "state_revision": 3,
                        "metadata_json": json.dumps(
                            {"search_request_id": "search-a"}
                        ),
                    },
                ],
                "retrieval_cards": [
                    {"card_id": "unrelated", "applicability_json": "{}"}
                ],
            }
        )
        pending = scheduler_module._pending_literature_search_requests(state)
        self.assertEqual(["request-b"], [row["artifact_id"] for row in pending])
        self.assertFalse(
            scheduler_module._search_request_has_response(
                state, artifact_id="", request_id=""
            )
        )

    def test_routing_completion_is_exact_and_revision_aware(self) -> None:
        state = scheduler_module._enable_scheduler_planning_cache(
            {
                "claims": [{"claim_id": "root", "root_impact": 1.0}],
                "routes": [
                    {
                        "route_id": "route-root",
                        "conclusion_claim_id": "root",
                        "relation_to_parent": "sufficient",
                        "status": "active",
                    }
                ],
                "inferences": [],
                "debts": [],
                "recent_runs": [],
                "research_artifacts": [
                    {
                        "artifact_id": "decision-old",
                        "artifact_type": "proof_dossier",
                        "state_revision": 2,
                        "metadata_json": json.dumps(
                            {
                                "target_id": "root",
                                "route_id": "route-root",
                                "classification": "route_killing_obstruction",
                                "route_decision": "pause",
                            }
                        ),
                    },
                    {
                        "artifact_id": "decision-new",
                        "artifact_type": "proof_dossier",
                        "state_revision": 6,
                        "metadata_json": json.dumps(
                            {
                                "target_id": "root",
                                "route_id": "route-root",
                                "classification": "route_killing_obstruction",
                                "route_decision": "replace",
                            }
                        ),
                    },
                    {
                        "artifact_id": "triage-response",
                        "artifact_type": "route_triage_report",
                        "state_revision": 4,
                        "metadata_json": json.dumps(
                            {
                                "route_decision_artifact_ids": [
                                    "decision-old",
                                    "decision-new",
                                ]
                            }
                        ),
                    },
                    {
                        "artifact_id": "obstruction-old",
                        "artifact_type": "route_obstruction",
                        "state_revision": 3,
                        "metadata_json": json.dumps(
                            {"target_id": "root", "route_id": "route-root"}
                        ),
                    },
                    {
                        "artifact_id": "obstruction-new",
                        "artifact_type": "route_obstruction",
                        "state_revision": 7,
                        "metadata_json": json.dumps(
                            {"target_id": "root", "route_id": "route-root"}
                        ),
                    },
                    {
                        "artifact_id": "conversion-response",
                        "artifact_type": "proof_dossier",
                        "state_revision": 5,
                        "metadata_json": json.dumps(
                            {
                                "obstruction_cluster_id": "root:route-root",
                                "obstruction_claim_ids": [],
                                "obstruction_artifact_ids": [
                                    "obstruction-old",
                                    "obstruction-new",
                                ],
                                "obstruction_debt_ids": [],
                            }
                        ),
                    },
                ],
            }
        )
        route_actions = scheduler_module._route_decision_triage_actions(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )
        self.assertEqual(
            ["decision-new"],
            [action["route_decision_artifact_id"] for action in route_actions],
        )
        obstruction_signals = scheduler_module._unconverted_obstruction_signals(
            state
        )
        self.assertEqual(
            ["obstruction-new"],
            [signal.get("artifact_id") for signal in obstruction_signals],
        )
        self.assertNotIn(
            "conversion-response",
            [signal.get("artifact_id") for signal in obstruction_signals],
        )

    def test_obstruction_cooldown_uses_stable_exact_cluster_identity(self) -> None:
        state = {
            "claims": [],
            "routes": [],
            "inferences": [],
            "debts": [],
            "research_artifacts": [],
            "recent_runs": [],
        }
        # Build two independent target/route clusters sharing one policy.
        state["claims"] = [
            {"claim_id": "root", "root_impact": 1.0},
            *[
                {
                    "claim_id": f"lemma-{suffix}",
                    "parent_ids_json": '["root"]',
                    "root_impact": 0.8,
                }
                for suffix in ("a", "b")
            ],
        ]
        state["routes"] = [
            {
                "route_id": f"route-{suffix}",
                "conclusion_claim_id": f"lemma-{suffix}",
                "relation_to_parent": "sufficient",
                "status": "active",
            }
            for suffix in ("a", "b")
        ]
        state["research_artifacts"] = [
            {
                "artifact_id": f"obstruction-{suffix}",
                "artifact_type": "route_obstruction",
                "state_revision": 2,
                "metadata_json": json.dumps(
                    {
                        "target_id": f"lemma-{suffix}",
                        "route_id": f"route-{suffix}",
                    }
                ),
            }
            for suffix in ("a", "b")
        ]
        initial_actions = scheduler_module._obstruction_route_conversion_actions(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )
        cluster_ids = {
            action["obstruction_cluster_key"]: action["obstruction_cluster_id"]
            for action in initial_actions
        }
        state["recent_runs"] = [
            {
                "search_intent": scheduler_module.OBSTRUCTION_ROUTE_CONVERSION_INTENT,
                "target_id": "lemma-a",
                "route_id": "route-a",
                "status": "completed",
                "decision_trace": {
                    "candidates": [
                        {
                            "candidate_id": (
                                "base_obligation:obstruction_conversion:"
                                + cluster_ids["lemma-a:route-a"]
                            ),
                            "admissible": True,
                            "disposition": "selected",
                        },
                        {
                            "candidate_id": (
                                "base_obligation:obstruction_conversion:"
                                + cluster_ids["lemma-b:route-b"]
                            ),
                            "admissible": True,
                            "disposition": "rejected_by_ordinal_comparison",
                        },
                    ]
                },
            }
        ]
        actions = scheduler_module._obstruction_route_conversion_actions(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )
        self.assertEqual(
            ["lemma-b:route-b"],
            [action["obstruction_cluster_key"] for action in actions],
        )
        fresh_state = {
            **state,
            "research_artifacts": [
                *state["research_artifacts"],
                {
                    "artifact_id": "obstruction-a-new",
                    "artifact_type": "route_obstruction",
                    "state_revision": 3,
                    "metadata_json": json.dumps(
                        {"target_id": "lemma-a", "route_id": "route-a"}
                    ),
                },
            ],
        }
        refreshed_actions = scheduler_module._obstruction_route_conversion_actions(
            fresh_state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )
        self.assertEqual(
            ["lemma-a:route-a", "lemma-b:route-b"],
            sorted(action["obstruction_cluster_key"] for action in refreshed_actions),
        )
        refreshed_a = next(
            action
            for action in refreshed_actions
            if action["obstruction_cluster_key"] == "lemma-a:route-a"
        )
        self.assertNotEqual(
            cluster_ids["lemma-a:route-a"],
            refreshed_a["obstruction_cluster_id"],
        )

    def test_obligation_routing_enumerates_real_simultaneous_objects(self) -> None:
        claims = [
            {
                "claim_id": claim_id,
                "statement": claim_id,
                "hypotheses": "",
                "parent_ids_json": json.dumps([] if claim_id == "root" else ["root"]),
                "evidence_artifact_ids_json": "[]",
                "root_impact": 1.0 if claim_id == "root" else 0.8,
                "reduction_depth": 0 if claim_id == "root" else 1,
                "validation_status": "untested",
                "lifecycle_status": "active",
            }
            for claim_id in ("root", "lemma-a", "lemma-b")
        ]
        routes = [
            {
                "route_id": f"route-{suffix}",
                "conclusion_claim_id": f"lemma-{suffix}",
                "relation_to_parent": "sufficient",
                "status": "active",
                "evidence_artifact_ids_json": "[]",
            }
            for suffix in ("a", "b")
        ]
        obligations = [
            {
                "debt_id": f"obligation-{suffix}",
                "owner_type": "claim",
                "owner_id": f"lemma-{suffix}",
                "suggested_next_target": f"lemma-{suffix}",
                "debt_type": "gap",
                "severity": "blocking",
                "status": "active",
                "obligation": f"prove the distinct local lemma {suffix}",
                "source_artifact_ids_json": "[]",
                "repeated_count": 0,
                "last_seen": f"2026-01-0{1 if suffix == 'a' else 2}T00:00:00Z",
            }
            for suffix in ("a", "b")
        ]
        artifacts = []
        for ordinal, suffix in enumerate(("a", "b"), start=1):
            artifacts.extend(
                [
                    {
                        "artifact_id": f"request-{suffix}",
                        "artifact_type": "literature_search_request",
                        "state_revision": ordinal,
                        "created_at": f"2026-01-0{ordinal}T00:00:00Z",
                        "content_summary": f"Find theorem {suffix}",
                        "metadata_json": json.dumps(
                            {
                                "search_request_id": f"search-{suffix}",
                                "target_id": f"lemma-{suffix}",
                                "route_id": f"route-{suffix}",
                                "query": f"exact theorem {suffix}",
                            }
                        ),
                    },
                    {
                        "artifact_id": f"decision-{suffix}",
                        "artifact_type": "proof_dossier",
                        "state_revision": ordinal + 2,
                        "content_summary": f"Route {suffix} has a decisive obstruction.",
                        "metadata_json": json.dumps(
                            {
                                "target_id": f"lemma-{suffix}",
                                "route_id": f"route-{suffix}",
                                "classification": "route_killing_obstruction",
                                "route_decision": "pause",
                            }
                        ),
                    },
                    {
                        "artifact_id": f"obstruction-{suffix}",
                        "artifact_type": "route_obstruction",
                        "state_revision": ordinal + 4,
                        "content_summary": f"Independent obstruction {suffix}.",
                        "metadata_json": json.dumps(
                            {
                                "target_id": f"lemma-{suffix}",
                                "route_id": f"route-{suffix}",
                            }
                        ),
                    },
                    {
                        "artifact_id": f"failed-plan-{suffix}",
                        "artifact_type": "failed_decomposition_plan",
                        "state_revision": ordinal + 6,
                        "metadata_json": json.dumps(
                            {
                                "target_id": f"lemma-{suffix}",
                                "route_id": f"route-{suffix}",
                                "decomposition_plan_id": f"plan-{suffix}",
                            }
                        ),
                    },
                ]
            )
        state = scheduler_module._enable_scheduler_planning_cache(
            {
                "problem_state": {},
                "claims": claims,
                "routes": routes,
                "inferences": [],
                "debts": obligations,
                "research_artifacts": artifacts,
                "retrieval_cards": [],
                "recent_runs": [],
            }
        )

        expected_obstruction_candidate_ids = {
            "base_obligation:obstruction_conversion:"
            + action["obstruction_cluster_id"]
            for action in scheduler_module._obstruction_route_conversion_actions(
                state,
                problem={},
                requested_tokens=None,
                research_mode="balanced",
            )
        }
        selected = scheduler_module._obligation_routing_action(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
            web_search="disabled",
            active_trunk_pressure={"over_trunk_cap": False},
            frontier_pressure={},
        )
        self.assertIsNotNone(selected)
        trace = selected["_base_policy_trace"]
        candidate_ids = {row["candidate_id"] for row in trace["candidates"]}
        expected = {
            *{
                f"base_obligation:requested_literature_search:request-{suffix}"
                for suffix in ("a", "b")
            },
            *{
                f"base_obligation:route_decision:decision-{suffix}"
                for suffix in ("a", "b")
            },
            *expected_obstruction_candidate_ids,
            *{
                f"base_obligation:blocking_obligation:obligation-{suffix}"
                for suffix in ("a", "b")
            },
            *{
                f"base_obligation:route_proof_quota:route-{suffix}"
                for suffix in ("a", "b")
            },
            *{
                f"base_obligation:failed_decomposition_regulation:failed-plan-{suffix}"
                for suffix in ("a", "b")
            },
        }
        self.assertEqual(expected, candidate_ids)
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual([], decision_trace_errors(trace))

    def test_residual_work_stratum_materializes_active_policies_only(self) -> None:
        decomposition = {
            "mode": "prove",
            "target_id": "lemma-a",
            "route_id": "route-a",
            "scheduler_policy_id": "decomposition_step",
        }
        librarian = {
            "mode": "retrieve",
            "target_id": "root",
            "route_id": "",
            "scheduler_policy_id": "research_librarian",
        }
        compression = {
            "mode": "write",
            "target_id": "root",
            "route_id": "route-root",
            "scheduler_policy_id": "proof_compression",
        }
        inactive = mock.Mock(return_value=None)
        no_actions = mock.Mock(return_value=[])
        with mock.patch.multiple(
            scheduler_module,
            _decomposition_step_actions=mock.Mock(return_value=[decomposition]),
            _route_triage_actions=no_actions,
            _recursive_drift_stop_action=inactive,
            _research_librarian_action=mock.Mock(return_value=librarian),
            _root_alignment_actions=no_actions,
            _proof_compression_actions=mock.Mock(return_value=[compression]),
            _frontier_pressure_action=inactive,
            _next_unverified_claim_actions=no_actions,
        ):
            selected = scheduler_module._residual_work_action(
                {},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
                active_trunk_pressure={},
                frontier_pressure={},
            )
        self.assertEqual("decomposition_step", selected["scheduler_policy_id"])
        trace = selected.pop("_base_policy_trace")
        self.assertEqual(
            [
                "base_residual:decomposition_step:plan:lemma-a",
                "base_residual:research_librarian",
                "base_residual:proof_compression:route-root",
            ],
            [row["candidate_id"] for row in trace["candidates"]],
        )
        self.assertTrue(
            all("fallback" not in row["candidate_id"] for row in trace["candidates"])
        )
        self.assertEqual([], decision_trace_errors(trace))

    def test_residual_verification_preempts_routine_exploration(self) -> None:
        decomposition = {
            "mode": "prove",
            "target_id": "lemma-a",
            "route_id": "route-a",
        }
        root_alignment = {
            "mode": "integrate",
            "target_id": "root",
            "route_id": "route-root",
            "root_alignment_audit": True,
        }
        inactive = mock.Mock(return_value=None)
        no_actions = mock.Mock(return_value=[])
        with mock.patch.multiple(
            scheduler_module,
            _decomposition_step_actions=mock.Mock(return_value=[decomposition]),
            _route_triage_actions=no_actions,
            _recursive_drift_stop_action=inactive,
            _research_librarian_action=inactive,
            _root_alignment_actions=mock.Mock(return_value=[root_alignment]),
            _proof_compression_actions=no_actions,
            _frontier_pressure_action=inactive,
            _next_unverified_claim_actions=no_actions,
        ):
            selected = scheduler_module._residual_work_action(
                {},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
                active_trunk_pressure={},
                frontier_pressure={},
            )
        self.assertTrue(selected["root_alignment_audit"])
        trace = selected["_base_policy_trace"]
        self.assertEqual(
            "base_residual:root_alignment:route-root",
            trace["selected_candidate_id"],
        )
        self.assertEqual(
            "rejected_by_policy_tier", trace["candidates"][0]["disposition"]
        )
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual([], decision_trace_errors(trace))

    def test_residual_stratum_materializes_every_object_bound_candidate(self) -> None:
        decomposition = [
            {
                "mode": "prove",
                "target_id": f"lemma-{suffix}",
                "route_id": "",
                "decomposition_plan_artifact_id": f"plan-{suffix}",
            }
            for suffix in ("a", "b")
        ]
        triage = [
            {
                "mode": "triage_routes",
                "target_id": "root",
                "route_id": f"route-{suffix}",
                "route_triage_id": f"route-{suffix}",
            }
            for suffix in ("a", "b")
        ]
        alignments = [
            {
                "mode": "integrate",
                "target_id": "root",
                "route_id": f"align-{suffix}",
            }
            for suffix in ("a", "b")
        ]
        claims = [
            {
                "mode": "prove",
                "target_id": f"claim-{suffix}",
                "route_id": "",
            }
            for suffix in ("a", "b")
        ]
        inactive = mock.Mock(return_value=None)
        with mock.patch.multiple(
            scheduler_module,
            _decomposition_step_actions=mock.Mock(return_value=decomposition),
            _route_triage_actions=mock.Mock(return_value=triage),
            _recursive_drift_stop_action=inactive,
            _research_librarian_action=inactive,
            _root_alignment_actions=mock.Mock(return_value=alignments),
            _proof_compression_actions=mock.Mock(return_value=[]),
            _frontier_pressure_action=inactive,
            _next_unverified_claim_actions=mock.Mock(return_value=claims),
        ):
            selected = scheduler_module._residual_work_action(
                {"recent_runs": []},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
                active_trunk_pressure={},
                frontier_pressure={},
            )
        trace = selected["_base_policy_trace"]
        self.assertEqual(
            {
                "base_residual:decomposition_step:plan-a:lemma-a",
                "base_residual:decomposition_step:plan-b:lemma-b",
                "base_residual:route_triage:route-a",
                "base_residual:route_triage:route-b",
                "base_residual:root_alignment:align-a",
                "base_residual:root_alignment:align-b",
                "base_residual:unverified_claim:claim-a",
                "base_residual:unverified_claim:claim-b",
            },
            {row["candidate_id"] for row in trace["candidates"]},
        )
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual([], decision_trace_errors(trace))

    def test_ready_decomposition_steps_span_every_active_plan(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "root",
                    "lifecycle_status": "active",
                    "validation_status": "untested",
                    "reduction_depth": 0,
                    "root_impact": 1.0,
                },
                *[
                    {
                        "claim_id": f"lemma-{suffix}",
                        "lifecycle_status": "active",
                        "validation_status": "untested",
                        "reduction_depth": 1,
                        "root_impact": 0.8,
                        "parent_ids": ["root"],
                    }
                    for suffix in ("a", "b")
                ],
            ],
            "routes": [],
            "inferences": [],
            "debts": [],
            "recent_runs": [],
            "research_artifacts": [
                {
                    "artifact_id": f"plan-{suffix}",
                    "artifact_type": "decomposition_plan",
                    "state_revision": revision,
                    "metadata_json": {
                        "decomposition_plan_id": f"decomposition-{suffix}",
                        "parent_claim_id": "root",
                        "subgoal_claim_ids": [f"lemma-{suffix}"],
                    },
                }
                for suffix, revision in (("a", 1), ("b", 2))
            ],
        }

        steps = scheduler_module._decomposition_plan_ready_steps(
            state, include_parent=True
        )

        self.assertEqual(
            {("decomposition-a", "lemma-a"), ("decomposition-b", "lemma-b")},
            {
                (step["decomposition_plan_id"], step["target_id"])
                for step in steps
            },
        )

    def test_residual_fallback_has_a_complete_singleton_trace(self) -> None:
        inactive = mock.Mock(return_value=None)
        no_actions = mock.Mock(return_value=[])
        with mock.patch.multiple(
            scheduler_module,
            _decomposition_step_actions=no_actions,
            _route_triage_actions=no_actions,
            _recursive_drift_stop_action=inactive,
            _research_librarian_action=inactive,
            _root_alignment_actions=no_actions,
            _proof_compression_actions=no_actions,
            _frontier_pressure_action=inactive,
            _next_unverified_claim_actions=no_actions,
        ):
            selected = scheduler_module._residual_work_action(
                {"recent_runs": []},
                problem={},
                requested_tokens=None,
                research_mode="balanced",
                web_search="disabled",
                active_trunk_pressure={},
                frontier_pressure={},
            )
        trace = selected["_base_policy_trace"]
        self.assertEqual("base_residual:fallback", trace["selected_candidate_id"])
        self.assertTrue(trace["candidate_set_complete"])
        self.assertEqual("residual", trace["candidate_generator_scope_id"])
        self.assertEqual(
            ["fallback_retrieval"], trace["active_candidate_generator_ids"]
        )
        self.assertEqual(
            CANDIDATE_GENERATOR_MANIFEST_VERSION,
            trace["candidate_generator_manifest_version"],
        )
        self.assertEqual(
            CANDIDATE_GENERATOR_BOUND_DECISION_POLICY_VERSION,
            trace["decision_policy_version"],
        )
        self.assertEqual({}, trace["candidate_generator_skip_reasons"])
        self.assertEqual(
            sorted(
                spec.generator_id
                for spec in CANDIDATE_GENERATOR_GRAPH
                if spec.scope_id == "residual"
            ),
            trace["evaluated_candidate_generator_ids"],
        )
        self.assertEqual(1, trace["candidate_generator_counts"]["fallback_retrieval"])
        self.assertEqual(
            [
                {
                    "start_index": 0,
                    "candidate_count": 1,
                    "generator_ids": ["fallback_retrieval"],
                }
            ],
            trace["candidate_generator_assignment_runs"],
        )
        self.assertEqual(
            {
                "decomposition_step",
                "route_triage",
                "recursive_drift_stop",
                "research_librarian",
                "root_alignment",
                "proof_compression",
                "frontier_pressure",
                "unverified_claim",
                "fallback_retrieval",
            },
            {
                spec.generator_id
                for spec in CANDIDATE_GENERATOR_GRAPH
                if spec.scope_id == "residual"
            },
        )
        self.assertEqual([], decision_trace_errors(trace))
        tampered = json.loads(json.dumps(trace))
        tampered["candidate_generator_registry_sha256"] = "0" * 64
        self.assertTrue(
            any(
                "versioned declaration" in error
                for error in decision_trace_errors(tampered)
            )
        )

        forged = json.loads(json.dumps(trace))
        forged["candidate_generator_registry_sha256"] = "0" * 64
        canonical_manifest = json.dumps(
            {
                "graph_version": forged["candidate_generator_graph_version"],
                "scope_id": forged["candidate_generator_scope_id"],
                "registry_sha256": forged[
                    "candidate_generator_registry_sha256"
                ],
                "counts": forged["candidate_generator_counts"],
                "assignment_runs": forged[
                    "candidate_generator_assignment_runs"
                ],
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        forged["candidate_generator_manifest_sha256"] = hashlib.sha256(
            canonical_manifest.encode("utf-8")
        ).hexdigest()
        self.assertTrue(
            any(
                "versioned declaration" in error
                for error in decision_trace_errors(forged)
            )
        )

        embedded = json.loads(json.dumps(trace))
        embedded["candidate_generator_registry"] = [
            dict(vars(spec))
            for spec in CANDIDATE_GENERATOR_GRAPH
            if spec.scope_id == "residual"
        ]
        embedded["candidate_generator_registry"][0]["producer"] = "_omitted"
        self.assertTrue(
            any(
                "embedded candidate-generator registry" in error
                for error in decision_trace_errors(embedded)
            )
        )

        malformed_assignment = json.loads(json.dumps(trace))
        malformed_assignment["candidate_generator_assignment_runs"] = [
            {
                "start_index": 0,
                "candidate_count": 1,
                "generator_ids": [{}],
            }
        ]
        self.assertTrue(decision_trace_errors(malformed_assignment))

        unevaluated = json.loads(json.dumps(trace))
        unevaluated["evaluated_candidate_generator_ids"].remove(
            "fallback_retrieval"
        )
        unevaluated["candidate_generator_skip_reasons"][
            "fallback_retrieval"
        ] = "phase_excluded"
        self.assertTrue(
            any(
                "skipped candidate generator has a nonzero count" in error
                or "active candidate generators were not evaluated" in error
                for error in decision_trace_errors(unevaluated)
            )
        )

        omitted_manifest = json.loads(json.dumps(trace))
        for field in tuple(omitted_manifest):
            if field.startswith("candidate_generator") or field in {
                "active_candidate_generator_ids",
                "evaluated_candidate_generator_ids",
            }:
                omitted_manifest.pop(field)
        self.assertTrue(
            any(
                "requires current candidate-generator provenance" in error
                for error in decision_trace_errors(omitted_manifest)
            )
        )

        missing_scope = json.loads(json.dumps(trace))
        missing_scope.pop("candidate_generator_scope_id")
        self.assertTrue(
            any(
                "provenance is incomplete without a scope" in error
                for error in decision_trace_errors(missing_scope)
            )
        )

        with self.assertRaisesRegex(ValueError, "exceeded its exactly_one"):
            scheduler_module.bind_candidate_generator_registry(
                {"candidates": [{}, {}]},
                scope_id="top_level",
                active_generator_ids=["base_planner", "base_planner"],
                evaluated_generator_ids=[
                    spec.generator_id
                    for spec in CANDIDATE_GENERATOR_GRAPH
                    if spec.scope_id == "top_level"
                ],
                skipped_generator_reasons={},
            )

    def test_sequential_planner_has_no_duplicate_verifier_policy_branch(self) -> None:
        source = inspect.getsource(scheduler_module._plan_next_action)
        self.assertNotIn("_verifier_candidate_action(", source)

    def test_base_notification_generators_do_not_mutate_steering_state(self) -> None:
        state = {
            "routes": [],
            "recent_runs": [
                {
                    "actor_role": "researcher",
                    "target_id": "root",
                    "route_id": "",
                    "mode": "prove",
                }
                for _ in range(scheduler_module.CIRCLING_MIN_PASSES)
            ]
        }
        with mock.patch.object(
            scheduler_module.steering,
            "raise_authenticated_blocker",
            side_effect=AssertionError("candidate generation must be pure"),
        ):
            action = scheduler_module._circling_redirect_action(
                mock.Mock(),
                state,
                problem={"current_revision": 7},
                requested_tokens=None,
                research_mode="balanced",
                researcher_only=True,
            )
        self.assertIsNotNone(action)
        self.assertEqual("stall", action["human_blocker_request"]["kind"])
        self.assertNotIn("human_blocker_id", action)

    def test_selected_action_notification_is_published_after_comparison(self) -> None:
        action = {
            "mode": "triage_routes",
            "target_id": "root",
            "human_blocker_request": {
                "kind": "stall",
                "target_id": "root",
                "summary": "The current proof search is stalled.",
                "detail": "Choose a new route.",
                "options": ["change route"],
                "fingerprint": "stall:root",
                "revision": 4,
            },
        }
        with mock.patch.object(
            scheduler_module.steering,
            "raise_authenticated_blocker",
            return_value={"id": "blk-selected"},
        ) as publish:
            scheduler_module._publish_selected_action_notifications(
                mock.Mock(), action
            )
        publish.assert_called_once()
        self.assertEqual("blk-selected", action["human_blocker_id"])

    def test_required_human_notification_failure_is_explicit(self) -> None:
        action = {
            "mode": "await_human",
            "target_id": "root",
            "human_blocker_request": {
                "kind": "terminology",
                "target_id": "root",
                "summary": "A human decision is required.",
                "required": True,
            },
        }
        with mock.patch.object(
            scheduler_module.steering,
            "raise_authenticated_blocker",
            side_effect=OSError("notification store unavailable"),
        ):
            errors = scheduler_module._publish_selected_action_notifications(
                mock.Mock(), action
            )
        self.assertEqual(1, len(errors))
        self.assertTrue(action["human_blocker_notification_required"])
        self.assertIn("notification store unavailable", errors[0])
        self.assertNotIn("human_blocker_id", action)

    def test_optional_blockers_are_not_raised_inside_candidate_generators(self) -> None:
        for generator in (
            scheduler_module._circling_redirect_action,
            scheduler_module._refuted_root_revision_action,
            scheduler_module._root_refinement_action,
            scheduler_module._writing_human_consultation_action,
            scheduler_module._writing_quality_exhausted_action,
        ):
            with self.subTest(generator=generator.__name__):
                self.assertNotIn(
                    "raise_authenticated_blocker(", inspect.getsource(generator)
                )

    def test_candidate_generators_do_not_run_reconciliation_writes(self) -> None:
        for generator in (
            scheduler_module._publication_route_error_research_action,
            scheduler_module._writing_existing_document_gate_action,
            scheduler_module._publication_document_gate_action,
        ):
            source = inspect.getsource(generator)
            with self.subTest(generator=generator.__name__):
                self.assertNotIn("apply_system_patch(", source)
                self.assertNotIn("store.write_event(", source)
                self.assertNotIn("_sync_writing_lint_debts(", source)
                self.assertNotIn("_sync_writing_compile_debt(", source)

    def test_writing_reconciliation_failure_is_fail_closed(self) -> None:
        state = {"problem_state": {"current_revision": 4}}
        document = {
            "artifact_id": "manuscript-current",
            "artifact_type": "revision_document",
            "path": "/not/read/in-this-test",
        }
        with (
            mock.patch.object(
                scheduler_module, "is_writing_revision_state", return_value=True
            ),
            mock.patch.object(
                scheduler_module, "latest_revision_document", return_value=document
            ),
            mock.patch.object(
                scheduler_module, "_writing_artifact_content", return_value="text"
            ),
            mock.patch.object(
                scheduler_module,
                "_sync_writing_lint_debts",
                return_value=["synthetic reconciliation rejection"],
            ),
        ):
            failure = scheduler_module._reconcile_writing_gate_inputs(
                mock.Mock(), state, research_mode="balanced"
            )
        self.assertIsNotNone(failure)
        self.assertEqual("stop_with_partial_results", failure["mode"])
        self.assertEqual(
            "writing_gate_reconciliation_failed", failure["stop_reason_code"]
        )
        self.assertIn("synthetic reconciliation rejection", failure["errors"])

    def test_integration_assurance_is_not_reopened_inside_base_planning(self) -> None:
        source = inspect.getsource(scheduler_module._plan_next_action)
        self.assertNotIn("claim_assurance_summary(", source)
        self.assertNotIn("with store.connect()", source)

    def test_strategy_generator_materializes_simultaneous_alternatives(self) -> None:
        primary = {"mode": "reduce", "target_id": "root", "route_id": "route-1"}
        reference = {"pending_reconstruction": True}
        approach = {"approach_id": "a1", "target_id": "root"}
        bridge = {"statement": "Bridge lemma", "target_route_id": "route-1"}
        conjecture = {"statement": "Conjecture lemma"}
        conceptual = {"due": True, "target_id": "root", "reason": "switch invariant"}
        authorization = {"artifact_id": "auth", "metadata": {}}
        synthesis = {"due": True}
        with (
            mock.patch(
                "agents.generation.phase2.research_strategy.approach_brainstorming_trigger",
                return_value={"due": False},
            ),
            mock.patch(
                "agents.generation.phase2.research_strategy._protected_primary_action",
                return_value=False,
            ),
            mock.patch(
                "agents.generation.phase2.research_strategy.reference_solution_state",
                return_value=reference,
            ),
            mock.patch(
                "agents.generation.phase2.research_strategy.selected_approach_candidate",
                return_value=approach,
            ),
            mock.patch(
                "agents.generation.phase2.research_strategy.selected_bridge_candidate",
                return_value=bridge,
            ),
            mock.patch(
                "agents.generation.phase2.research_strategy.selected_conjecture_candidate",
                return_value=conjecture,
            ),
            mock.patch(
                "agents.generation.phase2.research_strategy._candidate_needs_experiment",
                return_value=False,
            ),
            mock.patch(
                "agents.generation.phase2.research_strategy.conceptual_invariant_trigger",
                return_value=conceptual,
            ),
            mock.patch(
                "agents.generation.phase2.research_strategy.active_invention_authorization",
                return_value=authorization,
            ),
            mock.patch(
                "agents.generation.phase2.research_strategy.advisor_synthesis_trigger",
                return_value=synthesis,
            ),
            mock.patch(
                "agents.generation.phase2.research_strategy._compression_would_help",
                return_value=True,
            ),
            mock.patch(
                "agents.generation.phase2.research_strategy._compression_is_fresh_for_trigger",
                return_value=False,
            ),
        ):
            candidates = strategy_operation_candidates(
                {"claims": []}, primary, steering_alignment={}
            )
        self.assertEqual(
            [
                "reference_solution_reconstruction",
                "approach_pilot",
                "bridge_promotion",
                "conjecture_proof",
                "conceptual_invariant_discovery",
                "definition_invention",
                "proof_compression",
            ],
            [row["operation"] for row in candidates],
        )
        self.assertEqual(
            [
                "reference_solution_reconstruction",
                "approach_pilot",
                "selected_bridge",
                "selected_conjecture",
                "conceptual_invariant",
                "definition_invention",
                "proof_compression",
            ],
            [row["_candidate_generator_id"] for row in candidates],
        )

    def test_context_entity_catalog_is_type_fair_and_revision_paged(self) -> None:
        state = {
            "problem_state": {"current_revision": 0},
            "claims": [
                {"claim_id": f"claim-{index:03d}"} for index in range(170)
            ],
            "routes": [{"route_id": f"route-{index}"} for index in range(2)],
            "inferences": [
                {"inference_id": f"inference-{index}"} for index in range(2)
            ],
            "debts": [{"debt_id": f"obligation-{index}"} for index in range(2)],
            "artifacts": [
                {
                    "artifact_id": f"artifact-{index}",
                    "artifact_type": "research_notebook",
                }
                for index in range(2)
            ],
            "retrieval_cards": [
                {"card_id": f"retrieval-{index}"} for index in range(2)
            ],
            "theorem_library_entries": [
                {"entry_id": f"library-{index}"} for index in range(2)
            ],
        }
        first = _context_entity_catalog(
            state,
            selected_claim_ids=(),
            selected_route_id="",
            selected_inference_ids=(),
            selected_obligation_ids=(),
            selected_artifact_ids=(),
            limit=8,
        )
        self.assertEqual(3, first["catalog_version"])
        self.assertGreater(first["page_count"], 1)
        self.assertEqual(8, first["listed_entity_count"])
        self.assertEqual(
            {
                "artifact",
                "claim",
                "inference",
                "proof_obligation",
                "retrieval_card",
                "route",
                "theorem_library_entry",
            },
            {row["entity_type"] for row in first["entries"]},
        )

        state["problem_state"]["current_revision"] = 1
        second = _context_entity_catalog(
            state,
            selected_claim_ids=(),
            selected_route_id="",
            selected_inference_ids=(),
            selected_obligation_ids=(),
            selected_artifact_ids=(),
            limit=8,
        )
        self.assertEqual(1, second["page_index"])
        self.assertNotEqual(first["entries"], second["entries"])
        self.assertEqual(
            first["full_handle_set_sha256"], second["full_handle_set_sha256"]
        )

    def test_typed_comparator_rejects_ambiguous_or_nonfinite_candidates(self) -> None:
        duplicate = [
            ActionCandidate("same", "proof", {"mode": "prove"}, 1.0),
            ActionCandidate("same", "proof", {"mode": "reduce"}, 2.0),
        ]
        with self.assertRaisesRegex(ValueError, "unique"):
            select_action_candidate(duplicate, candidate_set_complete=True)
        with self.assertRaisesRegex(ValueError, "finite"):
            select_action_candidate(
                [ActionCandidate("nan", "proof", {"mode": "prove"}, float("nan"))],
                candidate_set_complete=True,
            )

    def test_nested_candidate_identifiers_are_globally_unique(self) -> None:
        _, nested = select_action_candidate(
            [
                ActionCandidate(
                    "shared-candidate",
                    "nested",
                    {"mode": "reduce", "target_id": "lemma"},
                    1.0,
                )
            ],
            candidate_set_complete=True,
        )
        with self.assertRaisesRegex(ValueError, "unique across all nested"):
            select_action_candidate(
                [
                    ActionCandidate(
                        "shared-candidate",
                        "outer",
                        {"mode": "prove", "target_id": "root"},
                        1.0,
                    )
                ],
                candidate_set_complete=True,
                nested_policy_traces={"shared-candidate": nested},
            )

    def test_scheduler_trace_is_hash_chained_with_run_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "decision-trace", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            action = next_action(store)
            self.assertTrue(action.get("scheduler_policy_id"))
            trace = action.get("decision_trace")
            self.assertIsInstance(trace, dict)
            self.assertTrue(trace.get("selected_candidate_id"))
            self.assertTrue(trace.get("candidate_set_complete"))
            self.assertEqual(
                action_sha256(action),
                trace.get("dispatched_action_sha256"),
            )
            operation = run_metrics_operation(
                run_id="decision-run",
                action=action,
                session_plan={
                    "actor_role": "researcher",
                    "state_revision": store.get_revision(),
                    "context_hash": "context-hash",
                },
                usage_payload={"input_tokens": 1, "output_tokens": 1},
            )
            self.assertEqual("deterministic", operation["selection_design"])
            self.assertEqual(
                trace["candidate_set_sha256"], operation["candidate_set_hash"]
            )
            self.assertEqual(
                trace["decision_policy_version"],
                operation["selection_policy_version"],
            )
            tampered = json.loads(json.dumps(operation))
            tampered["run_id"] = "decision-run-tampered"
            tampered["decision_trace"]["candidates"][0]["ordinal_priority"] += 1
            rejected = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [tampered],
                    "rationale": "candidate trace tampering must fail",
                },
                mode=str(action.get("mode") or ""),
                route_id=str(action.get("route_id") or ""),
            )
            self.assertFalse(rejected.accepted)
            self.assertTrue(
                any("candidate-set hash" in error for error in rejected.errors),
                rejected.errors,
            )
            outcome = _record_dispatched_test_run(store, action, "decision-run")
            self.assertTrue(outcome.accepted, outcome.errors)
            with store.connect() as conn:
                row = conn.execute(
                    "SELECT selection_design, candidate_set_hash, selection_policy_version, "
                    "decision_trace_json FROM runs WHERE run_id='decision-run'"
                ).fetchone()
                self.assertEqual(trace, json.loads(row["decision_trace_json"]))
                self.assertEqual("deterministic", row["selection_design"])
                self.assertEqual(trace["candidate_set_sha256"], row["candidate_set_hash"])
                self.assertEqual(
                    trace["decision_policy_version"], row["selection_policy_version"]
                )
                self.assertEqual([], validate_conn(conn))

    def test_run_telemetry_cannot_relabel_a_durable_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "run-dispatch-telemetry-binding",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Prove a difficult theorem.")
            action = next_action(store, web_search="live")
            self.assertTrue(action.get("search_intent"))
            dispatches, committed_heads = _record_scheduler_dispatches(
                store,
                [action],
                store.audit_chain_heads(),
                execution_contract={
                    "version": 1,
                    "driver": "custom",
                    "identity": "test:run-telemetry-binding",
                    "recovery_capability": "none",
                },
            )
            dispatch = dispatches[0]
            session_plan = {
                "actor_role": dispatch["actor_role"],
                "mode": action["mode"],
                "target_id": action["target_id"],
                "route_id": action.get("route_id", ""),
                "state_revision": committed_heads["proof_revision"],
                "scheduler_decision_state_revision": dispatch[
                    "decision_state_revision"
                ],
                "scheduler_dispatch_id": dispatch["dispatch_id"],
                "dispatched_action_hash": dispatch[
                    "dispatched_action_hash"
                ],
                "context_hash": "context-bound-run",
                "search_intent": action["search_intent"],
                "strategy_family": strategy_family(action),
                "model_profile": "default",
                "web_search": "disabled",
            }
            execution = {
                "run_id": "bound-run",
                "actor_role": dispatch["actor_role"],
                "status": "failed",
                "returncode": 1,
                "wall_time_seconds": 0.0,
                "peak_memory_mb": 0.0,
                "usage": {},
                "session_id": "",
                "patch": None,
                "patch_error": "",
                "output_artifact_ids": [],
                "model": "",
                "reasoning_effort": "",
                "sandbox": "",
                "web_search": "disabled",
                "failure_kind": "",
            }
            scheduled = {
                "action": action,
                "session_plan": session_plan,
                "session_web_search": "disabled",
                "execution": execution,
                "is_companion": False,
            }
            workflow_module._record_scheduler_attempts(store, [scheduled])
            workflow_module._record_scheduler_result(
                store,
                scheduled,
                validation_errors=[],
            )
            operation = run_metrics_operation(
                run_id="bound-run",
                action=action,
                session_plan=session_plan,
                usage_payload={},
                status="failed",
            )
            operation["search_setting"] = "disabled"

            def persist(op: Mapping[str, object]) -> PatchOutcome:
                return apply_system_patch(
                    store,
                    {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": store.get_revision(),
                        "actor_role": "scheduler",
                        "target_id": str(action["target_id"]),
                        "operations": [op],
                        "rationale": "exercise run-to-dispatch telemetry binding",
                    },
                    mode=str(action["mode"]),
                    route_id=str(action.get("route_id") or ""),
                )

            inflated = json.loads(json.dumps(operation))
            inflated["budget_requested"] += 1
            rejected = persist(inflated)
            self.assertFalse(rejected.accepted)
            self.assertIn("requested allocation", " ".join(rejected.errors))

            relabelled = json.loads(json.dumps(operation))
            relabelled["search_intent"] = "unrelated_policy"
            rejected = persist(relabelled)
            self.assertFalse(rejected.accepted)
            self.assertIn("search intent", " ".join(rejected.errors))

            durable_result_tampers = {
                "run_id": "forged-run",
                "input_tokens": 1,
                "wall_time_seconds": 1.0,
                "session_id": "forged-session",
                "model_profile": "forged-profile",
                "model": "forged-model",
                "reasoning_effort": "forged-effort",
                "sandbox_setting": "forged-sandbox",
                "search_setting": "live",
                "prompt_context_hash": "forged-context",
                "strategy_family": "forged-strategy",
                "failure_kind": "forged-failure",
                "status": "completed",
                "output_artifact_ids": ["uncommitted-artifact"],
            }
            for field, value in durable_result_tampers.items():
                with self.subTest(field=field):
                    tampered_result = json.loads(json.dumps(operation))
                    tampered_result[field] = value
                    rejected = persist(tampered_result)
                    self.assertFalse(rejected.accepted, field)
                    self.assertIn(
                        "durable scheduler result",
                        " ".join(rejected.errors),
                    )

            accepted = persist(operation)
            self.assertTrue(accepted.accepted, accepted.errors)

    def test_dispatch_alone_cannot_claim_execution_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "dispatch-is-not-completion",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Prove a difficult theorem.")
            action = next_action(store, web_search="disabled")
            dispatches, committed_heads = _record_scheduler_dispatches(
                store,
                [action],
                store.audit_chain_heads(),
                execution_contract={
                    "version": 1,
                    "driver": "custom",
                    "identity": "test:no-result",
                    "recovery_capability": "none",
                },
            )
            dispatch = dispatches[0]
            operation = run_metrics_operation(
                run_id="unexecuted-run",
                action=action,
                session_plan={
                    "actor_role": dispatch["actor_role"],
                    "state_revision": committed_heads["proof_revision"],
                    "scheduler_decision_state_revision": dispatch[
                        "decision_state_revision"
                    ],
                    "scheduler_dispatch_id": dispatch["dispatch_id"],
                    "dispatched_action_hash": dispatch[
                        "dispatched_action_hash"
                    ],
                },
                usage_payload={},
                status="failed",
            )
            rejected = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "scheduler",
                    "target_id": str(action["target_id"]),
                    "operations": [operation],
                    "rationale": "a dispatch is not an executor result",
                },
                mode=str(action["mode"]),
                route_id=str(action.get("route_id") or ""),
            )
            self.assertFalse(rejected.accepted)
            self.assertIn("prior durable scheduler result", " ".join(rejected.errors))
            with store.connect() as conn:
                self.assertEqual(
                    0,
                    conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"],
                )

    def test_decision_trace_rejects_unknown_versions_and_is_total_on_scalars(self) -> None:
        _selected, valid = select_action_candidate(
            [
                ActionCandidate(
                    "candidate-a",
                    "research",
                    {"mode": "reduce", "target_id": "lemma-a"},
                    2.0,
                ),
                ActionCandidate(
                    "candidate-b",
                    "research",
                    {"mode": "reduce", "target_id": "lemma-b"},
                    1.0,
                ),
            ],
            candidate_set_complete=True,
            candidate_set_scope="both generated research alternatives",
        )
        for version in (8, "7", True, None):
            with self.subTest(version=repr(version)):
                trial = json.loads(json.dumps(valid))
                trial["decision_policy_version"] = version
                self.assertTrue(decision_trace_errors(trial))

        malformed_values = (None, True, False, "invalid", [], {}, -1, 1.5)
        for row_index in (0, 1):
            for field in tuple(valid["candidates"][row_index]):
                for malformed in malformed_values:
                    with self.subTest(
                        row=row_index,
                        field=field,
                        malformed=repr(malformed),
                    ):
                        trial = json.loads(json.dumps(valid))
                        trial["candidates"][row_index][field] = malformed
                        self.assertIsInstance(decision_trace_errors(trial), list)

    def test_decision_trace_derives_the_post_comparison_transformation_flag(self) -> None:
        selected, trace = select_action_candidate(
            [
                ActionCandidate(
                    "candidate-a",
                    "research",
                    {"mode": "reduce", "target_id": "lemma-a"},
                    1.0,
                )
            ],
            candidate_set_complete=True,
        )
        trace = bind_dispatched_action(selected, trace)
        self.assertEqual([], decision_trace_errors(trace))

        flipped = json.loads(json.dumps(trace))
        flipped["post_comparison_transformation"] = not flipped[
            "post_comparison_transformation"
        ]
        self.assertTrue(
            any(
                "transformation flag disagrees" in error
                for error in decision_trace_errors(flipped)
            )
        )
        missing = json.loads(json.dumps(trace))
        missing.pop("post_comparison_transformation")
        self.assertTrue(
            any(
                "must declare its transformation flag" in error
                for error in decision_trace_errors(missing)
            )
        )

    def test_decision_validators_fail_closed_on_noncanonical_nested_values(self) -> None:
        _selected, generic_trace = select_action_candidate(
            [
                ActionCandidate(
                    "candidate-a",
                    "research",
                    {"mode": "reduce", "target_id": "lemma-a"},
                    1.0,
                )
            ],
            candidate_set_complete=True,
        )
        for label, malformed in (
            ("nan", float("nan")),
            ("bytes", b"not-json"),
            ("object", object()),
        ):
            with self.subTest(validator="generic", value=label):
                trial = json.loads(json.dumps(generic_trace))
                trial["base_policy_trace"] = {"malformed": malformed}
                errors = decision_trace_errors(trial)
                self.assertTrue(errors)
                self.assertTrue(
                    any("canonical JSON" in error for error in errors), errors
                )

        cyclic: dict[str, object] = {}
        cyclic["base_policy_trace"] = cyclic
        trial = json.loads(json.dumps(generic_trace))
        trial["base_policy_trace"] = cyclic
        self.assertTrue(decision_trace_errors(trial))
        self.assertTrue(decision_trace_errors([]))  # type: ignore[arg-type]

        _selected, parallel_trace = (
            scheduler_module._admit_parallel_companion_candidates(
                {"mode": "prove", "target_id": "root", "route_id": ""},
                [{"mode": "reduce", "target_id": "lemma-a", "route_id": ""}],
                problem={"parallel_branches": 2},
            )
        )
        for label, malformed in (
            ("nan", float("nan")),
            ("bytes", b"not-json"),
            ("object", object()),
        ):
            with self.subTest(validator="parallel", value=label):
                trial = json.loads(json.dumps(parallel_trace))
                trial["candidates"][1]["semantic_identity"][6] = malformed
                errors = parallel_admission_module.parallel_wave_admission_errors(
                    trial
                )
                self.assertTrue(errors)
                self.assertTrue(
                    any("semantic identity" in error for error in errors), errors
                )

    def test_legacy_v4_trace_ignores_uncommitted_policy_tier_field(self) -> None:
        _selected, trace = select_action_candidate(
            [
                ActionCandidate(
                    "legacy-a",
                    "research",
                    {"mode": "reduce", "target_id": "a"},
                    2.0,
                ),
                ActionCandidate(
                    "legacy-b",
                    "research",
                    {"mode": "reduce", "target_id": "b"},
                    1.0,
                ),
            ],
            candidate_set_complete=True,
        )
        trace["decision_policy_version"] = 4
        trace["candidates"][0]["policy_tier"] = "uncommitted legacy noise"
        trace["candidates"][1].pop("policy_tier")
        trace["candidate_set_sha256"] = candidate_rows_sha256(
            trace["candidates"],
            decision_policy_version=4,
        )

        self.assertEqual([], decision_trace_errors(trace))

    def test_generic_dispatch_and_replay_share_one_comparison_transition(self) -> None:
        candidates = [
            ActionCandidate(
                "shared-a",
                "research",
                {"mode": "reduce", "target_id": "a"},
                2.0,
            ),
            ActionCandidate(
                "shared-b",
                "research",
                {"mode": "reduce", "target_id": "b"},
                1.0,
            ),
        ]
        with mock.patch.object(
            decision_policy_module,
            "decision_outcomes",
            wraps=decision_policy_module.decision_outcomes,
        ) as generation_transition:
            _selected, trace = select_action_candidate(
                candidates,
                candidate_set_complete=True,
            )
        self.assertEqual(1, generation_transition.call_count)

        with mock.patch.object(
            decision_policy_module,
            "decision_outcomes",
            wraps=decision_policy_module.decision_outcomes,
        ) as replay_transition:
            self.assertEqual([], decision_trace_errors(trace))
        self.assertEqual(1, replay_transition.call_count)

    def test_next_action_loads_one_scheduler_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "single-scheduler-projection", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            with mock.patch.object(
                store, "get_scheduler_state", wraps=store.get_scheduler_state
            ) as load:
                action = next_action(store, web_search="disabled")
            self.assertEqual(1, load.call_count)
            strategy_row = next(
                row
                for row in action["decision_trace"]["candidates"]
                if row["candidate_id"].startswith(
                    "research_strategy:approach_portfolio_brainstorming:"
                )
            )
            self.assertFalse(strategy_row["mandatory_constraint"])
            self.assertGreater(strategy_row["ordinal_priority"], 100_000)
            self.assertFalse(
                action["priority_assessment"]["rotation_tie_break_active"]
            )
            trace = action["decision_trace"]
            self.assertEqual("top_level", trace["candidate_generator_scope_id"])
            self.assertEqual(
                ["approach_portfolio", "base_planner"],
                trace["active_candidate_generator_ids"],
            )
            self.assertEqual([], decision_trace_errors(trace))

    def test_scheduler_replans_when_planning_changes_the_state_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "stable-scheduler-snapshot", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            original = scheduler_module._plan_next_action
            planning_calls = 0

            def mutate_once(*args, **kwargs):
                nonlocal planning_calls
                planning_calls += 1
                if planning_calls == 1:
                    snapshot = kwargs["_scheduler_state"]
                    outcome = apply_system_patch(
                        store,
                        {
                            "schema_version": SCHEMA_VERSION,
                            "problem_id": store.problem_id,
                            "base_revision": snapshot["problem_state"]["current_revision"],
                            "actor_role": "scheduler",
                            "target_id": "root",
                            "operations": [
                                {
                                    "op": "add_debt",
                                    "debt_id": "concurrent-planning-obligation",
                                    "owner_type": "claim",
                                    "owner_id": "root",
                                    "debt_type": "proof_gap",
                                    "severity": "minor",
                                    "status": "active",
                                    "obligation": "Check the stable-snapshot retry path.",
                                }
                            ],
                            "rationale": "simulate a concurrent state change during planning",
                        },
                    )
                    self.assertTrue(outcome.accepted, outcome.errors)
                return original(*args, **kwargs)

            with mock.patch.object(
                scheduler_module,
                "_plan_next_action",
                side_effect=mutate_once,
            ):
                action = next_action(store, web_search="disabled")

            self.assertEqual(2, planning_calls)
            self.assertEqual(1, store.get_revision())
            self.assertEqual([], decision_trace_errors(action["decision_trace"]))

    def test_direct_scheduler_replans_when_policy_head_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "stable-direct-policy-snapshot",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            original = scheduler_module._plan_next_action
            planning_calls = 0

            def change_policy_once(*args, **kwargs):
                nonlocal planning_calls
                planning_calls += 1
                if planning_calls == 1:
                    store.set_completion_policy(
                        "exploratory",
                        reason="change policy during direct scheduler planning",
                        source="test",
                    )
                return original(*args, **kwargs)

            with mock.patch.object(
                scheduler_module,
                "_plan_next_action",
                side_effect=change_policy_once,
            ):
                action = next_action(store, web_search="disabled")

            self.assertEqual(2, planning_calls)
            with store.connect() as conn:
                self.assertEqual(
                    "exploratory",
                    store.get_problem_row(conn)["completion_policy"],
                )
            self.assertEqual([], decision_trace_errors(action["decision_trace"]))

    def test_route_scoreboard_claim_index_builds_do_not_scale_with_routes(self) -> None:
        claims = [
            {
                "claim_id": "root",
                "parent_ids_json": "[]",
                "lifecycle_status": "active",
                "validation_status": "untested",
                "root_impact": 1.0,
                "reduction_depth": 0,
            }
        ]
        routes = []
        for index in range(100):
            claim_id = f"lemma-{index:03d}"
            claims.append(
                {
                    "claim_id": claim_id,
                    "parent_ids_json": json.dumps(["root"]),
                    "lifecycle_status": "active",
                    "validation_status": "untested",
                    "root_impact": 0.5,
                    "reduction_depth": 1,
                }
            )
            routes.append(
                {
                    "route_id": f"route-{index:03d}",
                    "conclusion_claim_id": claim_id,
                    "status": "active",
                    "relation_to_parent": "sufficient",
                }
            )
        state = {
            "claims": claims,
            "routes": routes,
            "inferences": [],
            "debts": [],
            "artifacts": [],
            "research_artifacts": [],
            "recent_runs": [],
        }
        original = graph_policy_module.claim_map
        with mock.patch.object(
            graph_policy_module,
            "claim_map",
            wraps=original,
        ) as claim_map_call:
            rows = graph_policy_module.route_scoreboard(state)

        self.assertEqual(100, len(rows))
        self.assertLessEqual(claim_map_call.call_count, 2)

    def test_scheduler_snapshot_reuses_graph_policy_views(self) -> None:
        state = {
            graph_policy_module.SCHEDULER_PLANNING_CACHE_KEY: {},
            "claims": [
                {
                    "claim_id": "root",
                    "parent_ids_json": "[]",
                    "lifecycle_status": "active",
                    "validation_status": "untested",
                    "root_impact": 1.0,
                    "reduction_depth": 0,
                },
                {
                    "claim_id": "lemma",
                    "parent_ids_json": '["root"]',
                    "lifecycle_status": "active",
                    "validation_status": "untested",
                    "root_impact": 0.5,
                    "reduction_depth": 1,
                },
            ],
            "routes": [
                {
                    "route_id": "route-lemma",
                    "conclusion_claim_id": "lemma",
                    "status": "active",
                    "relation_to_parent": "sufficient",
                }
            ],
            "inferences": [],
            "debts": [],
            "artifacts": [],
            "research_artifacts": [],
            "runs": [],
            "recent_runs": [],
        }
        original = graph_policy_module.claim_map
        with mock.patch.object(
            graph_policy_module,
            "claim_map",
            wraps=original,
        ) as claim_map_call:
            first_scoreboard = graph_policy_module.route_scoreboard(state)
            original_score = first_scoreboard[0]["score"]
            first_scoreboard[0]["score"] = -999.0
            second_scoreboard = graph_policy_module.route_scoreboard(state)
            first_paused = graph_policy_module.paused_route_ids(state)
            second_paused = graph_policy_module.paused_route_ids(state)
            first_index = graph_policy_module.build_graph_policy_index(state)
            second_index = graph_policy_module.build_graph_policy_index(state)

        self.assertEqual(original_score, second_scoreboard[0]["score"])
        self.assertEqual(first_paused, second_paused)
        self.assertIs(first_index, second_index)
        self.assertLessEqual(claim_map_call.call_count, 2)

    def test_route_scoreboard_populates_and_reuses_snapshot_cache(self) -> None:
        state = {
            graph_policy_module.SCHEDULER_PLANNING_CACHE_KEY: {},
            "claims": [
                {
                    "claim_id": "root",
                    "parent_ids_json": "[]",
                    "lifecycle_status": "active",
                    "validation_status": "untested",
                    "root_impact": 1.0,
                    "reduction_depth": 0,
                },
                {
                    "claim_id": "lemma",
                    "parent_ids_json": '["root"]',
                    "lifecycle_status": "active",
                    "validation_status": "untested",
                    "root_impact": 0.5,
                    "reduction_depth": 1,
                },
            ],
            "routes": [
                {
                    "route_id": "route-lemma",
                    "conclusion_claim_id": "lemma",
                    "status": "active",
                    "relation_to_parent": "sufficient",
                }
            ],
            "inferences": [],
            "debts": [],
            "artifacts": [],
            "research_artifacts": [],
            "recent_runs": [],
        }
        with mock.patch.object(
            graph_policy_module,
            "_route_score",
            wraps=graph_policy_module._route_score,
        ) as score:
            first = graph_policy_module.route_scoreboard(state)
            second = graph_policy_module.route_scoreboard(state)

        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertEqual(1, score.call_count)
        self.assertIn(
            "route_scoreboard",
            state[graph_policy_module.SCHEDULER_PLANNING_CACHE_KEY],
        )

    def test_scheduler_planning_cache_is_reset_at_operation_boundary(self) -> None:
        cache_key = graph_policy_module.SCHEDULER_PLANNING_CACHE_KEY
        state = {cache_key: {"stale": object()}}

        result = scheduler_module._enable_scheduler_planning_cache(state)

        self.assertIs(result, state)
        self.assertEqual({}, state[cache_key])

    def test_route_gap_scan_computes_active_route_once_per_target(self) -> None:
        state = {
            "inferences": [],
            "debts": [
                {
                    "debt_id": f"obligation-{index:03d}",
                    "status": "active",
                    "debt_type": "gap",
                    "owner_type": "claim",
                    "owner_id": "root",
                    "suggested_next_target": "root",
                }
                for index in range(100)
            ],
        }
        with mock.patch.object(
            scheduler_module,
            "_active_route_for_claim",
            return_value="route-root",
        ) as active_route:
            obligation_ids = scheduler_module._active_route_gap_debt_ids(
                state, "route-root", "root"
            )

        self.assertEqual(100, len(obligation_ids))
        active_route.assert_called_once_with(state, "root")

    def test_verifier_loop_scan_rejects_inactive_routes_before_graph_work(self) -> None:
        state = {
            "routes": [
                {
                    "route_id": f"route-{index:03d}",
                    "conclusion_claim_id": f"lemma-{index:03d}",
                    "status": "active",
                }
                for index in range(100)
            ],
            "recent_runs": [],
        }
        with mock.patch.object(
            scheduler_module,
            "_active_route_gap_debt_ids",
        ) as route_gap_scan:
            action = scheduler_module._verifier_loop_classification_action(
                state,
                problem={},
                requested_tokens=None,
                research_mode="balanced",
            )

        self.assertIsNone(action)
        route_gap_scan.assert_not_called()

    def test_active_frontier_pressure_builds_one_graph_index(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "root" if index == 0 else f"lemma-{index:03d}",
                    "parent_ids_json": "[]" if index == 0 else '["root"]',
                    "lifecycle_status": "active",
                    "validation_status": "untested",
                    "root_impact": 1.0 if index == 0 else 0.5,
                    "reduction_depth": 0 if index == 0 else 1,
                }
                for index in range(101)
            ],
            "routes": [],
            "debts": [],
            "runs": [],
            "recent_runs": [],
        }
        original = graph_policy_module.claim_map
        with mock.patch.object(
            graph_policy_module,
            "claim_map",
            wraps=original,
        ) as claim_map_call:
            pressure = graph_policy_module.active_frontier_pressure(state)

        self.assertEqual(100, pressure["active_unverified_claim_count"])
        self.assertLessEqual(claim_map_call.call_count, 2)

    def test_bulk_root_distances_handle_branches_cycles_and_disconnection(self) -> None:
        def claim_row(
            claim_id: str, parent_ids: list[str], fallback_depth: int
        ) -> dict[str, object]:
            return {
                "claim_id": claim_id,
                "parent_ids_json": json.dumps(parent_ids),
                "lifecycle_status": "active",
                "validation_status": "untested",
                "reduction_depth": fallback_depth,
            }

        state = {
            "claims": [
                claim_row("root", [], 0),
                claim_row("a", ["root"], 1),
                claim_row("b", ["a", "c"], 2),
                claim_row("c", ["b"], 3),
                claim_row("disconnected", ["missing"], 7),
                claim_row("self-cycle", ["self-cycle"], 5),
            ],
            "routes": [],
            "debts": [],
            "runs": [],
            "recent_runs": [],
        }

        with mock.patch.object(
            graph_policy_module,
            "_root_distance_from_claims",
            side_effect=AssertionError("per-claim search must not build the index"),
        ):
            index = graph_policy_module.build_graph_policy_index(state)

        self.assertEqual(
            {
                "root": 0,
                "a": 1,
                "b": 2,
                "c": 3,
                "disconnected": 7,
                "self-cycle": 5,
            },
            dict(index.root_distances),
        )

    def test_online_outcome_history_is_bounded_and_disclosed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "bounded-scheduler-history", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            rows = []
            for index in range(SCHEDULER_RECENT_RUN_LIMIT + 7):
                rows.append(
                    (
                        f"run-{index:04d}",
                        "researcher",
                        "retrieve" if index < 7 else "prove",
                        "root",
                        0,
                        0,
                        f"session-{index:04d}",
                        f"2026-01-01T00:{index // 60:02d}:{index % 60:02d}+00:00",
                    )
                )
            with store.connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO runs(
                        run_id, actor_role, mode, target_id, route_id,
                        state_revision, context_revision, session_id, model_profile,
                        model, reasoning_effort, search_setting, sandbox_setting,
                        budget_requested, input_tokens, cached_input_tokens,
                        output_tokens, reasoning_output_tokens, total_tokens,
                        wall_time_seconds, peak_memory_mb, status,
                        prompt_context_hash, output_artifact_ids_json,
                        error_artifact_id, created_at
                    ) VALUES (?, ?, ?, ?, '', ?, ?, ?, 'default', '', '', '', '',
                              0, 0, 0, 0, 0, 0, 0.0, 0.0, 'completed', '', '[]', '', ?)
                    """,
                    rows,
                )
            state = store.get_scheduler_state()
            self.assertEqual(SCHEDULER_RECENT_RUN_LIMIT, len(state["outcome_runs"]))
            self.assertEqual(
                SCHEDULER_RECENT_RUN_LIMIT + 7,
                state["outcome_history"]["population_count"],
            )
            self.assertFalse(state["outcome_history"]["complete"])
            self.assertEqual("disabled", state["outcome_history"]["ranking_effect"])
            self.assertEqual([], state["runs"])
            self.assertEqual(7, state["run_counts"]["retrieve_total"])
            self.assertEqual(7, state["run_counts"]["retrieve_untracked_total"])
            self.assertFalse(state["run_counts"]["retrieve_by_intent_complete"])
            self.assertEqual(
                list(ONLINE_RETRIEVAL_COUNT_INTENTS),
                state["run_counts"]["registered_retrieval_intents"],
            )

    def test_scheduler_trace_history_has_an_aggregate_byte_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "bounded-decision-trace-history",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            outcome = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "record_run_metrics",
                            "run_id": f"trace-run-{index}",
                            "actor_role": "researcher",
                            "mode": "prove",
                            "target_id": "root",
                            "state_revision": 0,
                            "context_revision": 0,
                            "status": "completed",
                            "decision_trace": {
                                "padding": "x" * 700,
                                "ordinal": index,
                            },
                        }
                        for index in range(4)
                    ],
                    "rationale": "seed oversized descriptive trace history",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with mock.patch.object(
                store_module,
                "SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT",
                1_000,
            ):
                state = store.get_scheduler_state()

        history = state["decision_trace_history"]
        self.assertEqual(4, history["recent_window_run_count"])
        self.assertEqual(1, history["included_trace_count"])
        self.assertFalse(history["recent_window_complete"])
        self.assertLessEqual(history["included_trace_bytes"], 1_000)
        self.assertNotEqual("{}", state["recent_runs"][0]["decision_trace_json"])
        self.assertTrue(
            state["recent_runs"][0]["decision_trace_history_included"]
        )
        self.assertTrue(
            all(
                row["decision_trace_json"] == "{}"
                and not row["decision_trace_history_included"]
                for row in state["recent_runs"][1:]
            )
        )


class MaintainabilityGuardTests(unittest.TestCase):
    def test_candidate_generator_graph_versions_are_immutable_and_replayable(self) -> None:
        expected = {
            1: (
                82,
                "c4c9a4e291a8d758e0f5b4e2bf30090ddd9e7c691b0f1465b7ab77edf2ae5014",
            ),
            2: (
                95,
                "d0ba9673715b1eb884fef044319a89cba69c7d2cb7056fca295af1d7a025db7f",
            ),
            3: (
                95,
                "d0ba9673715b1eb884fef044319a89cba69c7d2cb7056fca295af1d7a025db7f",
            ),
            4: (
                97,
                "a2180e790dac7451a332a4ff56847ce9b5feca4ceae25c17ce100436ab14df56",
            ),
            5: (
                97,
                "6d32e9ed485c235a8aa3aca8b24ca335588cd6cd07d88ef6f6a720f361a03b8d",
            ),
        }
        self.assertEqual(5, CANDIDATE_GENERATOR_GRAPH_VERSION)
        self.assertEqual(
            tuple(expected), SUPPORTED_CANDIDATE_GENERATOR_GRAPH_VERSIONS
        )
        self.assertEqual(set(expected), set(CANDIDATE_GENERATOR_GRAPHS))
        for version, graph in CANDIDATE_GENERATOR_GRAPHS.items():
            self.assertEqual(expected[version][0], len(graph))
            self.assertEqual(
                expected[version][1],
                candidate_generator_graph_sha256(graph),
            )
            self.assertEqual(
                expected[version][1],
                CANDIDATE_GENERATOR_GRAPH_SHA256[version],
            )
            self.assertEqual([], candidate_generator_graph_errors(graph))

        legacy_trace = {"candidates": [{}, {}]}
        scheduler_module.bind_candidate_generator_registry(
            legacy_trace,
            scope_id="parallel_wave",
            active_generator_ids=[],
            evaluated_generator_ids=["companion_plan"],
            skipped_generator_reasons={
                spec.generator_id: "not_invoked_in_parallel_wave"
                for spec in CANDIDATE_GENERATOR_GRAPHS[1]
                if spec.scope_id == "parallel_wave"
                and spec.generator_id != "companion_plan"
            },
            candidate_generator_assignments=[["companion_plan"]],
            graph_version=1,
        )
        self.assertEqual(1, legacy_trace["candidate_generator_graph_version"])
        self.assertEqual([], candidate_generator_trace_errors(legacy_trace))

        historical_trace = json.loads(json.dumps(legacy_trace))
        historical_trace.pop("candidate_generator_manifest_version")
        historical_trace.pop("evaluated_candidate_generator_ids")
        historical_trace.pop("candidate_generator_skip_reasons")
        legacy_manifest = {
            "graph_version": historical_trace[
                "candidate_generator_graph_version"
            ],
            "scope_id": historical_trace["candidate_generator_scope_id"],
            "registry_sha256": historical_trace[
                "candidate_generator_registry_sha256"
            ],
            "counts": historical_trace["candidate_generator_counts"],
            "assignment_runs": historical_trace[
                "candidate_generator_assignment_runs"
            ],
        }
        historical_trace["candidate_generator_manifest_sha256"] = hashlib.sha256(
            json.dumps(
                legacy_manifest,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual([], candidate_generator_trace_errors(historical_trace))

        _selected, historical_generic = select_action_candidate(
            [
                ActionCandidate(
                    "base_residual:fallback",
                    "residual_mathematical_work",
                    {"mode": "retrieve", "target_id": "root", "route_id": ""},
                    0.0,
                )
            ],
            candidate_set_complete=True,
        )
        scheduler_module.bind_candidate_generator_registry(
            historical_generic,
            scope_id="residual",
            active_generator_ids=["fallback_retrieval"],
            evaluated_generator_ids=[
                spec.generator_id
                for spec in CANDIDATE_GENERATOR_GRAPHS[2]
                if spec.scope_id == "residual"
            ],
            skipped_generator_reasons={},
            graph_version=2,
        )
        self.assertEqual(
            decision_policy_module.DECISION_POLICY_VERSION,
            historical_generic["decision_policy_version"],
        )
        self.assertEqual([], decision_trace_errors(historical_generic))

        downgraded_current = json.loads(json.dumps(legacy_trace))
        scheduler_module.bind_candidate_generator_registry(
            downgraded_current,
            scope_id="parallel_wave",
            active_generator_ids=[],
            evaluated_generator_ids=["peer_verification"],
            skipped_generator_reasons={
                spec.generator_id: "not_invoked_in_parallel_wave"
                for spec in CANDIDATE_GENERATOR_GRAPH
                if spec.scope_id == "parallel_wave"
                and spec.generator_id != "peer_verification"
            },
            candidate_generator_assignments=[["peer_verification"]],
        )
        downgraded_current.pop("candidate_generator_manifest_version")
        downgraded_current.pop("evaluated_candidate_generator_ids")
        downgraded_current.pop("candidate_generator_skip_reasons")
        downgraded_payload = {
            "graph_version": downgraded_current[
                "candidate_generator_graph_version"
            ],
            "scope_id": downgraded_current["candidate_generator_scope_id"],
            "registry_sha256": downgraded_current[
                "candidate_generator_registry_sha256"
            ],
            "counts": downgraded_current["candidate_generator_counts"],
            "assignment_runs": downgraded_current[
                "candidate_generator_assignment_runs"
            ],
        }
        downgraded_current["candidate_generator_manifest_sha256"] = hashlib.sha256(
            json.dumps(
                downgraded_payload,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        self.assertTrue(
            any(
                "requires manifest version 2" in error
                for error in candidate_generator_trace_errors(
                    downgraded_current
                )
            )
        )

    def test_candidate_generator_graph_matches_comparison_producers(self) -> None:
        scope_functions = {
            "precondition": "_precondition_gate_action",
            "solved_root": "_solved_root_action",
            "integration": "_integration_gate_action",
            "verification": "_verification_handoff_action",
            "evidence": "_evidence_assimilation_action",
            "recovery": "_recovery_synthesis_action",
            "obligation": "_obligation_routing_action",
            "residual": "_residual_work_action",
            "open_problem": "_open_problem_action",
            "parallel_leader": "_select_parallel_wave_leader",
        }
        tree = ast.parse(inspect.getsource(scheduler_module))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        registered = generator_producers_by_scope()
        registered_producers = set().union(*registered.values())

        def called_action_producers(node: ast.AST) -> frozenset[str]:
            names: set[str] = set()
            for child in ast.walk(node):
                if not isinstance(child, ast.Call) or not isinstance(
                    child.func, ast.Name
                ):
                    continue
                name = child.func.id
                if name in registered_producers or (
                    name.startswith("_")
                    and name != "_action"
                    and (name.endswith("_action") or name.endswith("_actions"))
                ):
                    names.add(name)
            return frozenset(names)

        self.assertEqual([], candidate_generator_graph_errors())
        self.assertEqual(
            {"top_level", "parallel_wave", *scope_functions}, set(registered)
        )
        for scope_id, function_name in scope_functions.items():
            self.assertIn(function_name, functions)
            self.assertEqual(
                registered[scope_id],
                called_action_producers(functions[function_name]),
                scope_id,
            )

        top_level_calls: set[str] = set()
        for module, function_name in (
            (scheduler_module, "next_action"),
            (research_strategy_module, "strategy_operation_candidates"),
        ):
            module_tree = ast.parse(inspect.getsource(module))
            function = next(
                node
                for node in module_tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == function_name
            )
            top_level_calls.update(
                child.func.id
                for child in ast.walk(function)
                if isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id in registered["top_level"]
            )
        self.assertEqual(registered["top_level"], frozenset(top_level_calls))

        parallel_calls: set[str] = set()
        for function in (
            scheduler_module.parallel_companion_actions,
            scheduler_module._plan_parallel_companion_actions,
            scheduler_module._admit_and_finalize_parallel_companions,
            run_workflow,
        ):
            function_tree = ast.parse(inspect.getsource(function))
            parallel_calls.update(
                child.func.id
                for child in ast.walk(function_tree)
                if isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id in registered["parallel_wave"]
            )
        self.assertEqual(registered["parallel_wave"], frozenset(parallel_calls))

    def test_retrieval_count_registry_covers_every_policy_intent(self) -> None:
        policy_tree = ast.parse(inspect.getsource(research_policy_module))
        literal_intents: set[str] = set()
        dynamic_calls: list[int] = []
        for node in ast.walk(policy_tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "_retrieve_run_count":
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            if "intent" not in keywords:
                continue
            value = keywords["intent"]
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                literal_intents.add(value.value)
            else:
                dynamic_calls.append(node.lineno)
        self.assertEqual([], dynamic_calls)
        self.assertEqual(set(ONLINE_RETRIEVAL_COUNT_INTENTS), literal_intents)

    def test_registered_stable_same_tier_generators_have_bounded_service(self) -> None:
        deferral_limit = scheduler_module.SCHEDULER_DEFERRAL_LIMIT
        scopes = sorted({spec.scope_id for spec in CANDIDATE_GENERATOR_GRAPH})
        for scope_id in scopes:
            generator_ids = [
                spec.generator_id
                for spec in CANDIDATE_GENERATOR_GRAPH
                if spec.scope_id == scope_id
            ]
            counts: dict[str, int] = {}
            served: set[str] = set()
            for _round in range(deferral_limit + len(generator_ids)):
                candidates = [
                    ActionCandidate(
                        candidate_id=f"property:{scope_id}:{generator_id}",
                        domain=scope_id,
                        action={"mode": "reduce", "target_id": generator_id},
                        ordinal_priority=float(len(generator_ids) - index),
                        policy_tier=100,
                        consecutive_deferrals=counts.get(
                            f"property:{scope_id}:{generator_id}", 0
                        ),
                        deferral_limit=deferral_limit,
                    )
                    for index, generator_id in enumerate(generator_ids)
                ]
                _selected, trace = select_action_candidate(
                    candidates, candidate_set_complete=True
                )
                served.add(str(trace["selected_candidate_id"]))
                counts = decision_policy_module.decision_deferral_state_after_trace(
                    counts, trace
                )
            self.assertEqual(
                {
                    f"property:{scope_id}:{generator_id}"
                    for generator_id in generator_ids
                },
                served,
                scope_id,
            )

    def test_parallel_policy_validation_has_no_scheduler_dependency_cycle(self) -> None:
        parallel_tree = ast.parse(inspect.getsource(parallel_admission_module))
        parallel_imports = {
            str(node.module or "")
            for node in ast.walk(parallel_tree)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertFalse(
            {"scheduler", "decision_policy"} & parallel_imports,
            parallel_imports,
        )
        relaxation_tree = ast.parse(inspect.getsource(parallel_relaxation_module))
        relaxation_imports = {
            str(node.module or "")
            for node in ast.walk(relaxation_tree)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertFalse(
            {"parallel_admission", "scheduler", "decision_policy"}
            & relaxation_imports,
            relaxation_imports,
        )
        decision_tree = ast.parse(inspect.getsource(decision_policy_module))
        scheduler_imports = [
            node
            for node in ast.walk(decision_tree)
            if isinstance(node, ast.ImportFrom)
            and str(node.module or "").endswith("scheduler")
        ]
        self.assertEqual([], scheduler_imports)

    def test_scheduler_has_no_unreachable_sibling_statements(self) -> None:
        path = Path(__file__).resolve().parents[1] / "phase2" / "scheduler.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations: list[int] = []

        def visit_block(statements: list[ast.stmt]) -> None:
            terminated = False
            for statement in statements:
                if terminated:
                    violations.append(statement.lineno)
                if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                    terminated = True
                for field in ("body", "orelse", "finalbody"):
                    nested = getattr(statement, field, None)
                    if isinstance(nested, list):
                        visit_block(nested)
                handlers = getattr(statement, "handlers", [])
                for handler in handlers:
                    visit_block(handler.body)

        visit_block(tree.body)
        self.assertEqual([], violations)

    def test_every_broad_exception_boundary_is_explicit(self) -> None:
        package = Path(__file__).resolve().parents[1] / "phase2"
        violations: list[str] = []
        for path in sorted(package.rglob("*.py")):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if "except Exception" in line or "except BaseException" in line:
                    if "intentional-boundary:" not in line:
                        violations.append(f"{path.relative_to(package)}:{line_number}")
        self.assertEqual([], violations)

    def test_completed_design_notes_are_not_labelled_as_pending_todos(self) -> None:
        package = Path(__file__).resolve().parents[1] / "phase2"
        violations: list[str] = []
        for path in sorted(package.rglob("*.py")):
            if path.name == "linter.py":
                continue
            if "TODO" in path.read_text(encoding="utf-8"):
                violations.append(str(path.relative_to(package)))
        self.assertEqual([], violations)


class HostEvidenceBoundaryTests(unittest.TestCase):
    def _store(self, tmpdir: str, problem_id: str) -> ProofStateStore:
        store = ProofStateStore(problem_id, generation_root=Path(tmpdir) / "generation")
        store.init_problem("The root theorem holds.")
        return store

    def test_patch_boundary_rejects_unbounded_and_nonfinite_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "bounded-patch-structure")
            too_many = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "human_operator",
                    "target_id": "root",
                    "operations": [
                        {"op": "cancel_context_request", "request_id": f"request-{index}"}
                        for index in range(513)
                    ],
                },
            )
            self.assertFalse(too_many.accepted)
            self.assertIn("limit is 512", " ".join(too_many.errors))
            self.assertEqual(0, store.get_revision())

            nonfinite = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "human_operator",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "nonfinite-metadata",
                            "artifact_type": "research_notebook",
                            "content": "No mathematical assertion.",
                            "metadata": {"score": float("nan")},
                        }
                    ],
                },
            )
            self.assertFalse(nonfinite.accepted)
            self.assertIn("non-finite number", " ".join(nonfinite.errors))
            self.assertEqual(0, store.get_revision())

    def test_snapshot_is_sealed_atomic_and_does_not_follow_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "atomic-sealed-snapshot")
            snapshot = store.write_snapshot()
            self.assertEqual(0, snapshot["problem_state"]["current_revision"])
            parsed = json.loads(store.snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(store.problem_id, parsed["problem_state"]["problem_id"])

            store.snapshot_path.unlink()
            protected = Path(tmpdir) / "protected.txt"
            protected.write_text("operator material\n", encoding="utf-8")
            store.snapshot_path.symlink_to(protected)
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                store.write_snapshot()
            self.assertEqual("operator material\n", protected.read_text(encoding="utf-8"))

    def test_artifact_hash_never_substitutes_metadata_for_a_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing-artifact.md"
            with self.assertRaisesRegex(ValueError, "could not open artifact"):
                artifact_hash(path=missing)

    def test_public_vocabulary_preserves_mathematical_evidence_and_paths(self) -> None:
        exact_text = (
            "In this quoted example, debt, ledger, villain, dossier, and battery "
            "are terms in the submitted source and must remain byte-exact."
        )
        exact_path = "/tmp/a-proof-dossier-ledger.txt"
        public = _public_context_vocabulary(
            {
                "debts": [
                    {
                        "debt_id": "debt-quoted-term",
                        "obligation": exact_text,
                    }
                ],
                "artifacts": [
                    {
                        "artifact_id": "draft-1",
                        "artifact_type": "proof_dossier",
                        "content": exact_text,
                        "path": exact_path,
                    }
                ],
                "instruction": (
                    "Read the proof dossier and debt ledger; then run the test battery "
                    "and ask the villain to review it. Use the Rethlas defeat loop, "
                    "paperwork throttle, and proof-pressure scheduler."
                ),
                "rethlas_defeat_loop_required": True,
                "paperwork_throttle_required": True,
                "proof_pressure_scheduler_required": True,
                "verification_report": {
                    "checked_items": [exact_text],
                    "critical_errors": [exact_text],
                    "gaps": [exact_text],
                    "summary": exact_text,
                },
            }
        )
        self.assertIn("proof_obligations", public)
        self.assertEqual(
            "debt-quoted-term",
            public["proof_obligations"][0]["proof_obligation_id"],
        )
        self.assertEqual(exact_text, public["proof_obligations"][0]["obligation"])
        self.assertEqual(exact_text, public["artifacts"][0]["content"])
        self.assertEqual(exact_path, public["artifacts"][0]["path"])
        self.assertEqual("proof_draft", public["artifacts"][0]["artifact_type"])
        report = public["verification_report"]
        self.assertEqual([exact_text], report["checked_items"])
        self.assertEqual([exact_text], report["critical_errors"])
        self.assertEqual([exact_text], report["gaps"])
        self.assertEqual(exact_text, report["summary"])
        directive = _public_context_vocabulary(
            {
                "directed_villain_mode": "cas",
                "directed_villain_mode_reason": "test the smallest examples",
            }
        )
        self.assertEqual("cas", directive["directed_adversarial_review_mode"])
        self.assertNotIn("directed_villain_mode", directive)
        self.assertTrue(public["decisive_proof_obligation_cycle_required"])
        self.assertTrue(public["mathematical_output_focus_required"])
        self.assertTrue(public["proof_strategy_review_required"])
        for legacy_key in (
            "rethlas_defeat_loop_required",
            "paperwork_throttle_required",
            "proof_pressure_scheduler_required",
        ):
            self.assertNotIn(legacy_key, public)
        instruction = public["instruction"]
        for legacy_word in (
            "debt",
            "ledger",
            "villain",
            "dossier",
            "battery",
            "Rethlas",
            "paperwork throttle",
            "proof-pressure scheduler",
        ):
            self.assertNotIn(legacy_word, instruction)

    def test_prompt_vocabulary_removes_internal_scheduler_metaphors(self) -> None:
        public = _standardize_prompt_terminology(
            "Use workflow_action.rethlas_defeat_loop_required, the paperwork "
            "throttle, and the proof-pressure scheduler."
        )
        self.assertIn("decisive_proof_obligation_cycle_required", public)
        self.assertIn("mathematical-output focus", public)
        self.assertIn("proof-strategy review", public)
        self.assertNotIn("rethlas", public.lower())
        self.assertNotIn("paperwork throttle", public)
        self.assertNotIn("proof-pressure scheduler", public)

    def test_concurrent_event_only_appends_remain_one_linear_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "concurrent-event-chain")
            barrier = threading.Barrier(3)
            failures: list[str] = []

            def append(index: int) -> None:
                try:
                    with store.connect() as conn:
                        barrier.wait(timeout=5)
                        store.write_event(
                            conn,
                            store.get_revision(conn),
                            "concurrent_test_event",
                            {"index": index},
                        )
                        conn.commit()
                except BaseException as exc:  # intentional-boundary: surface worker failures in the parent test
                    failures.append(f"{type(exc).__name__}: {exc}")

            threads = [
                threading.Thread(target=append, args=(index,)) for index in (1, 2)
            ]
            for thread in threads:
                thread.start()
            barrier.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=10)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual([], failures)
            verified = verify_event_journal(store)
            self.assertTrue(verified["valid"], verified["errors"])

    def test_context_state_and_policy_head_share_one_database_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "context-policy-snapshot")
            old_heads = store.audit_chain_heads()
            original_snapshot = store.snapshot_from_conn
            policy_changed = {"done": False}

            def interleaved_snapshot(conn, *, include_audit_journal=True):
                state = original_snapshot(
                    conn,
                    include_audit_journal=include_audit_journal,
                )
                if not policy_changed["done"]:
                    policy_changed["done"] = True
                    store.set_completion_policy(
                        "exploratory",
                        reason="interleave a policy write after the state read",
                        source="test",
                    )
                return state

            with mock.patch.object(
                store,
                "snapshot_from_conn",
                side_effect=interleaved_snapshot,
            ):
                manifest = build_context_manifest(store, max_chars=120_000)

            new_heads = store.audit_chain_heads()
            self.assertTrue(policy_changed["done"])
            self.assertNotEqual(
                old_heads["policy_event_head"],
                new_heads["policy_event_head"],
            )
            # The packet is consistently the old snapshot. A later session
            # patch carrying this old head will fail against the new policy;
            # it is never an old packet authorized by the new head.
            self.assertEqual(
                old_heads["policy_event_head"],
                manifest["audit_chain_heads"]["policy_event_head"],
            )
            self.assertNotEqual(
                "exploratory",
                manifest["completion_policy"]["policy"],
            )
            self.assertEqual([], manifest.get("patches", []))
            self.assertTrue(verify_event_journal(store)["valid"])

    def test_reference_solution_input_is_bounded_before_parsing(self) -> None:
        import agents.generation.phase2.reference_solution as reference_module

        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "bounded-reference-ingestion")
            document = Path(tmpdir) / "oversized.md"
            document.write_bytes(b"x" * 33)
            with mock.patch.object(
                reference_module,
                "MAX_REFERENCE_DOCUMENT_BYTES",
                32,
            ):
                with self.assertRaisesRegex(ValueError, "input limit"):
                    ingest_reference_solution(store, document)
            self.assertEqual(store.get_revision(), 0)

    def test_reference_solution_hash_and_text_come_from_one_stable_read(self) -> None:
        import agents.generation.phase2.reference_solution as reference_module

        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "single-read-reference-ingestion")
            document = Path(tmpdir) / "reference.md"
            document.write_text("# Proof\n\nThe asserted implication follows.\n", encoding="utf-8")
            original_reader = reference_module.read_bounded_bytes
            with mock.patch.object(
                reference_module,
                "read_bounded_bytes",
                wraps=original_reader,
            ) as reader:
                result = ingest_reference_solution(store, document)
            self.assertTrue(result["created"])
            self.assertEqual(1, reader.call_count)

    @unittest.skipUnless(
        shutil.which("pdflatex")
        and shutil.which("bwrap")
        and shutil.which("prlimit"),
        "isolated pdflatex toolchain is unavailable",
    )
    def test_latex_compiler_cannot_read_an_unmounted_host_file(self) -> None:
        from agents.generation.phase2.receipt import compile_latex_artifact

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            secret = root / "host-secret.tex"
            secret_text = "ALBILICH_UNMOUNTED_LATEX_SECRET_7d6f"
            secret.write_text(secret_text, encoding="utf-8")
            source = root / "attempt.tex"
            source.write_text(
                "\\documentclass{article}\n"
                "\\begin{document}\n"
                f"\\input{{{secret}}}\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            result = compile_latex_artifact(
                source,
                source.with_suffix(".pdf"),
            )
            diagnostic_path = Path(str(result.get("latex_log_path") or ""))
            diagnostic = (
                diagnostic_path.read_text(encoding="utf-8")
                if diagnostic_path.is_file()
                else ""
            )

            self.assertNotEqual(result["pdf_status"], "compiled")
            self.assertNotIn(secret_text, diagnostic)

    def test_public_proof_draft_alias_is_stored_as_legacy_artifact_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "proof-draft-alias")
            outcome = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "public-proof-draft",
                            "artifact_type": "proof_draft",
                            "content": "A complete mathematical proof draft.",
                        }
                    ],
                    "rationale": "exercise the public artifact-type alias",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with store.connect() as conn:
                row = conn.execute(
                    "SELECT artifact_type FROM artifacts WHERE artifact_id = ?",
                    ("public-proof-draft",),
                ).fetchone()
            self.assertEqual("proof_dossier", row["artifact_type"])

    def test_public_adversarial_review_directive_alias_reaches_scheduler_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "adversarial-review-directive-alias")
            outcome = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "phd_advisor",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "advisor-public-directive",
                            "artifact_type": "advisor_report",
                            "content": "Compute the smallest unresolved examples next.",
                            "metadata": {
                                "directed_adversarial_review_mode": "cas",
                                "directed_adversarial_review_mode_reason": "test the smallest examples",
                                "directed_adversarial_review_mode_steps": 2,
                            },
                        }
                    ],
                    "rationale": "exercise public advisor directive aliases",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with store.connect() as conn:
                row = conn.execute(
                    "SELECT metadata_json FROM artifacts WHERE artifact_id = ?",
                    ("advisor-public-directive",),
                ).fetchone()
            metadata = json.loads(row["metadata_json"])
            self.assertEqual("cas", metadata["directed_villain_mode"])
            self.assertEqual(2, metadata["directed_villain_mode_steps"])
            self.assertNotIn("directed_adversarial_review_mode", metadata)

    def test_enhanced_assurance_rejects_same_provider_family(self) -> None:
        self.assertEqual(
            "openai:gpt",
            reviewer_independence_class("codex", "gpt-5.4"),
        )
        self.assertEqual(
            "openai:gpt",
            reviewer_independence_class("codex", "gpt-6.0"),
        )
        errors = _session_contract_errors(
            action={
                "mode": "prove",
                "target_id": "root",
                "route_id": "route-root",
                "assurance_review_required": True,
                "observed_reviewer_independence_classes": ["openai:gpt"],
            },
            session_plan={
                "actor_role": "strict_informal_verifier",
                "mode": "prove",
                "target_id": "root",
                "route_id": "route-root",
                "state_revision": 1,
                "context_hash": "host-context",
                "context_path": "",
                "model": "gpt-5.6",
            },
            execution={
                "actor_role": "strict_informal_verifier",
                "backend": "codex",
                "model": "gpt-5.6",
            },
            patch={
                "actor_role": "strict_informal_verifier",
                "target_id": "root",
                "base_revision": 1,
            },
        )
        self.assertIn(
            "enhanced assurance review reused reviewer family 'openai:gpt'",
            " ".join(errors),
        )

    def test_enhanced_assurance_blocks_same_family_before_child_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "prelaunch-assurance-gate")
            context_path = store.state_dir / "context.json"
            context_path.write_text("{}\n", encoding="utf-8")
            action = {
                "mode": "prove",
                "target_id": "root",
                "route_id": "route-root",
                "assurance_review_required": True,
                "observed_reviewer_independence_classes": ["openai:gpt"],
            }
            session_plan = {
                "actor_role": "strict_informal_verifier",
                "context_path": str(context_path),
            }
            with mock.patch(
                "agents.generation.phase2.codex_runner.subprocess.Popen"
            ) as popen:
                result = execute_session(
                    store,
                    action,
                    session_plan,
                    model="gpt-5.6-sol",
                    enforce_backend_contract=False,
                )
            popen.assert_not_called()
            self.assertEqual("blocked", result["status"])
            self.assertEqual(
                "heterogeneous_backend_required", result["failure_kind"]
            )
            self.assertEqual(0, result["usage"]["total_tokens"])

    def test_child_cannot_supply_host_certificate_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "forged-host-certificate")
            outcome = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "forged-verification",
                            "artifact_type": "verification_report",
                            "content": "A caller-supplied certificate must not be accepted.",
                            "metadata": {
                                "verdict": "informally_verified",
                                "verification_report": {
                                    "critical_errors": [],
                                    "gaps": [],
                                    "blocking_gap": False,
                                },
                                "host_certificate_bindings": {
                                    "claim:root": {"binding_version": 1}
                                },
                            },
                        }
                    ],
                    "rationale": "attempt to forge host evidence",
                },
            )
            self.assertFalse(outcome.accepted)
            self.assertIn("host_certificate_bindings", " ".join(outcome.errors))

    def test_child_cannot_forge_host_owned_artifact_types(self) -> None:
        for artifact_type in (
            "audit_subject",
            "branch_workbench",
            "reference_solution",
            "run_interruption_event",
        ):
            with self.subTest(artifact_type=artifact_type), tempfile.TemporaryDirectory() as tmpdir:
                store = self._store(tmpdir, f"forged-{artifact_type}")
                outcome = apply_operator_patch(
                    store,
                    {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": 0,
                        "actor_role": "researcher",
                        "target_id": "root",
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": f"forged-{artifact_type}",
                                "artifact_type": artifact_type,
                                "content": "Untrusted host-owned content.",
                            }
                        ],
                        "rationale": "attempt to forge a host-owned artifact",
                    },
                )
                self.assertFalse(outcome.accepted)
                self.assertIn("cannot attach", " ".join(outcome.errors))

    def test_unchecked_formal_source_cannot_certify_a_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "unchecked-formal-certificate")
            outcome = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "formal_backend",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "unchecked-formal-result",
                            "artifact_type": "formal_backend_result",
                            "content": "This is not checked formal source.",
                            "metadata": {
                                "formal_check_request": {
                                    "backend": "unknown",
                                    "source": "theorem root : True := by trivial",
                                }
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root",
                            "status_type": "validation",
                            "new_status": "formally_verified",
                            "evidence_artifact_ids": ["unchecked-formal-result"],
                        },
                    ],
                    "rationale": "attempt certification without an allowlisted checker",
                },
            )
            self.assertFalse(outcome.accepted)
            self.assertIn("host-executed, successful formal_backend_result", " ".join(outcome.errors))

    def test_session_cannot_mutate_an_undisclosed_entity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "operation-scope")
            created = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "undisclosed-artifact",
                            "artifact_type": "research_notebook",
                            "content": "A record outside the later session packet.",
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "undisclosed-claim",
                            "claim_type": "lemma",
                            "statement": "An undisclosed auxiliary statement.",
                        }
                    ],
                    "rationale": "test fixture",
                },
            )
            self.assertTrue(created.accepted, created.errors)
            authority = PatchAuthority(
                source="session",
                actor_role="researcher",
                mode="refute",
                target_id="root",
                context_revision=1,
                context_hash="host-context-hash",
                authorized_existing_ids=("root",),
            )
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "undisclosed-claim",
                            "status_type": "validation",
                            "new_status": "challenged",
                            "rationale": "guessed identifier",
                        }
                    ],
                    "rationale": "attempt an out-of-scope mutation",
                },
                authority=authority,
            )
            self.assertFalse(outcome.accepted)
            self.assertIn("out-of-scope target_id", " ".join(outcome.errors))

            nested_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "new-artifact",
                            "artifact_type": "research_notebook",
                            "content": "Attempt to cite a guessed hidden record.",
                            "metadata": {
                                "source_artifact_ids": ["undisclosed-artifact"]
                            },
                        }
                    ],
                    "rationale": "attempt a nested out-of-scope reference",
                },
                authority=authority,
            )
            self.assertFalse(nested_outcome.accepted)
            self.assertIn(
                "metadata.source_artifact_ids",
                " ".join(nested_outcome.errors),
            )

            unclassified = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "new-artifact-2",
                            "artifact_type": "research_notebook",
                            "content": "A future operation field must be classified.",
                            "new_dependency_claim_id": "undisclosed-claim",
                        }
                    ],
                    "rationale": "exercise fail-closed schema-derived scope",
                },
                authority=authority,
            )
            self.assertFalse(unclassified.accepted)
            self.assertIn(
                "unclassified identifier field 'new_dependency_claim_id'",
                " ".join(unclassified.errors),
            )

            empty_disclosure_authority = PatchAuthority(
                source="session",
                actor_role="researcher",
                mode="refute",
                target_id="root",
                context_revision=1,
                context_hash="host-context-with-empty-disclosure-set",
                authorized_existing_ids=(),
            )
            empty_disclosure_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "undisclosed-claim",
                            "status_type": "validation",
                            "new_status": "challenged",
                            "rationale": "an empty disclosure set must not disable scope checks",
                        }
                    ],
                    "rationale": "exercise fail-closed empty disclosure scope",
                },
                authority=empty_disclosure_authority,
            )
            self.assertFalse(empty_disclosure_outcome.accepted)
            self.assertIn(
                "out-of-scope target_id",
                " ".join(empty_disclosure_outcome.errors),
            )

    def test_omitted_entity_request_cold_starts_an_exact_dependency_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "context-entity-request")
            seeded = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "omitted-lemma",
                            "kind": "lemma",
                            "statement": "The exact omitted lemma has conclusion Q.",
                        }
                    ],
                    "rationale": "seed an object outside the later session allowlist",
                },
            )
            self.assertTrue(seeded.accepted, seeded.errors)
            request_authority = PatchAuthority(
                source="session",
                actor_role="researcher",
                mode="reduce",
                target_id="root",
                context_revision=1,
                context_hash="focused-packet-without-omitted-lemma",
                # The compact catalog disclosed this identifier as a handle,
                # but not its mathematical content. Requests for guessed,
                # undisclosed identifiers are rejected by the scope checker.
                authorized_existing_ids=("root", "omitted-lemma"),
            )
            requested = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "request_context_entity",
                            "request_id": "request-omitted-lemma",
                            "requested_entity_type": "claim",
                            "requested_entity_id": "omitted-lemma",
                        }
                    ],
                    "rationale": "retrieve one exact omitted object",
                },
                authority=request_authority,
            )
            self.assertTrue(requested.accepted, requested.errors)

            action = next_action(store)
            self.assertTrue(action["context_retrieval"])
            self.assertTrue(action["force_cold_start"])
            self.assertEqual(
                [{"entity_id": "omitted-lemma", "entity_type": "claim"}],
                action["requested_context_entities"],
            )
            manifest = build_context_manifest(
                store, action=action, max_chars=120_000
            )
            packet = manifest["requested_context_packet"]
            self.assertTrue(packet["complete_local_dependency_packet"])
            self.assertEqual(
                "The exact omitted lemma has conclusion Q.",
                next(
                    row["statement"]
                    for row in packet["claims"]
                    if row["claim_id"] == "omitted-lemma"
                ),
            )

            delivery_authority = PatchAuthority(
                source="session",
                actor_role="researcher",
                mode="reduce",
                target_id="root",
                context_revision=2,
                context_hash="exact-request-packet",
                context_request_ids=("request-omitted-lemma",),
                authorized_existing_ids=("root", "omitted-lemma"),
            )
            used = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "uses-omitted-lemma",
                            "kind": "lemma",
                            "statement": "A new lemma informed by the requested object.",
                            "parent_ids": ["omitted-lemma"],
                        }
                    ],
                    "rationale": "continue after exact context delivery",
                },
                authority=delivery_authority,
            )
            self.assertTrue(used.accepted, used.errors)
            request_row = store.get_state()["context_requests"][0]
            self.assertEqual("fulfilled", request_row["status"])
            self.assertTrue(verify_patch_journal(store)["valid"])

            second_request_authority = PatchAuthority(
                source="session",
                actor_role="researcher",
                mode="reduce",
                target_id="root",
                context_revision=3,
                context_hash="second-focused-packet",
                authorized_existing_ids=("root", "omitted-lemma"),
            )
            second_request = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 3,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "request_context_entity",
                            "request_id": "request-to-cancel",
                            "requested_entity_type": "claim",
                            "requested_entity_id": "omitted-lemma",
                        }
                    ],
                    "rationale": "exercise explicit cancellation",
                },
                authority=second_request_authority,
            )
            self.assertTrue(second_request.accepted, second_request.errors)
            cancelled = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 4,
                    "actor_role": "operator",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "cancel_context_request",
                            "request_id": "request-to-cancel",
                        }
                    ],
                    "rationale": "the operator no longer needs this packet",
                },
            )
            self.assertTrue(cancelled.accepted, cancelled.errors)
            requests = {
                row["request_id"]: row for row in store.get_state()["context_requests"]
            }
            self.assertEqual("cancelled", requests["request-to-cancel"]["status"])
            with store.connect() as conn:
                self.assertEqual([], validate_conn(conn))

    def test_exact_context_request_fails_instead_of_truncating_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "context-request-overflow")
            seeded = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "large-requested-artifact",
                            "artifact_type": "research_notebook",
                            "content": "mathematical detail\n" * 2_000,
                        }
                    ],
                    "rationale": "seed a deliberately oversized requested artifact",
                },
            )
            self.assertTrue(seeded.accepted, seeded.errors)
            authority = PatchAuthority(
                source="session",
                actor_role="researcher",
                mode="reduce",
                target_id="root",
                context_revision=1,
                context_hash="small-focused-packet",
                authorized_existing_ids=("root", "large-requested-artifact"),
            )
            requested = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "request_context_entity",
                            "request_id": "request-large-artifact",
                            "requested_entity_type": "artifact",
                            "requested_entity_id": "large-requested-artifact",
                        }
                    ],
                    "rationale": "request exact artifact content",
                },
                authority=authority,
            )
            self.assertTrue(requested.accepted, requested.errors)
            action = next_action(store)
            with self.assertRaises(ContextTooLargeError):
                build_context_manifest(store, action=action, max_chars=4_000)

    def test_high_assurance_claim_requires_distinct_review_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "heterogeneous-review-gate")
            seeded = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "root-route",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "A complete direct proof.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "root-inference",
                            "route_id": "root-route",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The direct proof establishes the root theorem.",
                        },
                    ],
                    "rationale": "seed the proof route",
                },
            )
            self.assertTrue(seeded.accepted, seeded.errors)
            designated = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "human_operator",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "set_claim_assurance",
                            "claim_id": "root",
                            "assurance_level": "heterogeneous_review",
                            "rationale": "The root result will be used as a high-impact conclusion.",
                        }
                    ],
                    "rationale": "require independent review",
                },
            )
            self.assertTrue(designated.accepted, designated.errors)

            def verify_with_family(
                artifact_id: str,
                reviewer_class: str,
                backend: str,
                model: str,
                *,
                evidence_targets: list[dict[str, str]] | None = None,
            ) -> None:
                revision = store.get_revision()
                targets = evidence_targets or [
                    {
                        "target_type": "claim",
                        "target_id": "root",
                        "route_id": "root-route",
                    },
                    {
                        "target_type": "inference",
                        "target_id": "root-inference",
                        "route_id": "root-route",
                    },
                ]
                authority = PatchAuthority(
                    source="session",
                    actor_role="strict_informal_verifier",
                    mode="prove",
                    target_id="root",
                    route_id="root-route",
                    context_revision=revision,
                    context_hash=f"context-{artifact_id}",
                    session_id=f"session-{artifact_id}",
                    run_id=f"run-{artifact_id}",
                    reviewer_identity=f"{backend}:{model}",
                    reviewer_independence_class=reviewer_class,
                    reviewer_backend=backend,
                    reviewer_model=model,
                    authorized_existing_ids=(
                        "root",
                        "root-route",
                        "root-inference",
                    ),
                )
                outcome = apply_patch(
                    store,
                    {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": revision,
                        "actor_role": "strict_informal_verifier",
                        "target_id": "root",
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": artifact_id,
                                "artifact_type": "verification_report",
                                "content": (
                                    f"Independent complete review {artifact_id}: "
                                    "no errors and no gaps."
                                ),
                                "metadata": {
                                    "verdict": "informally_verified",
                                    "verification_report": {
                                        "checked_items": ["the complete direct proof"],
                                        "critical_errors": [],
                                        "gaps": [],
                                        "blocking_gap": False,
                                    },
                                    "evidence_targets": targets,
                                },
                            },
                            *[
                                {
                                    "op": "propose_status_transition",
                                    "target_type": target["target_type"],
                                    "target_id": target["target_id"],
                                    "status_type": "validation",
                                    "new_status": "informally_verified",
                                    "evidence_artifact_ids": [artifact_id],
                                }
                                for target in targets
                            ],
                        ],
                        "rationale": "independent strict review",
                    },
                    authority=authority,
                )
                self.assertTrue(outcome.accepted, outcome.errors)

            # Coverage may not be pooled across reviewer families: these two
            # reports jointly touch the route, but neither family completed a
            # review of the claim and every route inference.
            verify_with_family(
                "openai-claim-only",
                "openai:gpt",
                "codex",
                "gpt-5.4",
                evidence_targets=[
                    {
                        "target_type": "claim",
                        "target_id": "root",
                        "route_id": "root-route",
                    }
                ],
            )
            verify_with_family(
                "anthropic-inference-only",
                "anthropic:claude",
                "claude",
                "claude-opus-4",
                evidence_targets=[
                    {
                        "target_type": "inference",
                        "target_id": "root-inference",
                        "route_id": "root-route",
                    }
                ],
            )
            with store.connect() as conn:
                conn.execute("BEGIN")
                split_summary = claim_assurance_summary(
                    conn,
                    claim_id="root",
                    route_id="root-route",
                )
            self.assertFalse(split_summary["satisfied"])
            self.assertEqual([], split_summary["independence_classes"])
            self.assertEqual(
                ["anthropic:claude", "openai:gpt"],
                split_summary["partial_independence_classes"],
            )

            verify_with_family(
                "openai-review-1", "openai:gpt", "codex", "gpt-5.4"
            )
            action = next_action(store)
            self.assertTrue(action.get("assurance_review_required"), action)
            self.assertEqual(
                ["openai:gpt"],
                action["observed_reviewer_independence_classes"],
            )

            def integrate(artifact_id: str):
                return apply_operator_patch(
                    store,
                    {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": store.get_revision(),
                        "actor_role": "integration_verifier",
                        "target_id": "root",
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": artifact_id,
                                "artifact_type": "integration_report",
                                "content": "The route proves exactly the immutable root theorem.",
                                "metadata": {
                                    "integrates": True,
                                    "route_id": "root-route",
                                    "claim_id": "root",
                                    "root_alignment": {
                                        "relation_to_root": "exact",
                                        "target_statement": "The root theorem holds.",
                                        "proved_statement": "The root theorem holds.",
                                        "implication_verified": True,
                                        "hidden_assumptions": False,
                                        "extra_assumptions": [],
                                    },
                                },
                            },
                            {
                                "op": "propose_status_transition",
                                "target_type": "claim",
                                "target_id": "root",
                                "status_type": "lifecycle",
                                "new_status": "integrated",
                                "route_id": "root-route",
                                "evidence_artifact_ids": [artifact_id],
                            },
                        ],
                        "rationale": "attempt high-assurance integration",
                    },
                )

            blocked = integrate("integration-before-independent-review")
            self.assertFalse(blocked.accepted)
            self.assertIn("independent review requirement", " ".join(blocked.errors))

            verify_with_family(
                "openai-review-2", "openai:gpt", "codex", "gpt-5.6"
            )
            still_blocked = integrate("integration-after-same-family-review")
            self.assertFalse(still_blocked.accepted)

            verify_with_family(
                "anthropic-review", "anthropic:claude", "claude", "claude-opus-4"
            )
            with store.connect() as conn:
                conn.execute("BEGIN")
                complete_summary = claim_assurance_summary(
                    conn,
                    claim_id="root",
                    route_id="root-route",
                )
            self.assertTrue(complete_summary["satisfied"], complete_summary)
            integrated = integrate("integration-after-heterogeneous-review")
            self.assertTrue(integrated.accepted, integrated.errors)
            self.assertTrue(verify_patch_journal(store)["valid"])

    def test_evidence_capsule_rejects_symbolic_link_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source.txt"
            source.write_text("approved-looking content\n", encoding="utf-8")
            link = root / "linked-source.txt"
            link.symlink_to(source)
            manifest = {
                "artifacts": [{"artifact_id": "linked", "path": str(link)}],
                "local_search_policy": {
                    "allowed_local_evidence_paths": [str(link)]
                },
            }
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                _materialize_evidence_capsule(
                    manifest, root / "contexts" / "context.json"
                )

    def test_evidence_capsule_rejects_bytes_that_do_not_match_the_artifact_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source.txt"
            source.write_text("changed after registration\n", encoding="utf-8")
            manifest = {
                "artifacts": [
                    {
                        "artifact_id": "changed",
                        "path": str(source),
                        "sha256": hashlib.sha256(b"original bytes\n").hexdigest(),
                    }
                ],
                "local_search_policy": {
                    "allowed_local_evidence_paths": [str(source)]
                },
            }
            with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
                _materialize_evidence_capsule(
                    manifest, root / "contexts" / "context.json"
                )

    @unittest.skipUnless(shutil.which("codex"), "Codex CLI is unavailable")
    def test_installed_codex_sandbox_cannot_read_outside_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            capsule = root / "capsule"
            capsule.mkdir()
            (capsule / "inside.txt").write_text("inside\n", encoding="utf-8")
            outside = root / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            profile_args = _codex_permission_profile_args(
                "codex", "albilich-evidence-capsule"
            )
            permission_assignment = profile_args[2]
            completed = subprocess.run(
                [
                    shutil.which("codex") or "codex",
                    "sandbox",
                    "-C",
                    str(capsule),
                    "-c",
                    permission_assignment,
                    "-P",
                    "albilich-evidence-capsule",
                    "/bin/sh",
                    "-c",
                    'test -r inside.txt && test ! -r "$1"',
                    "sandbox-boundary-test",
                    str(outside),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr.decode("utf-8", errors="replace"),
            )


class IndependentReproductionTests(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("python3") and shutil.which("bwrap") and shutil.which("prlimit"),
        "networkless reproduction dependencies are unavailable",
    )
    def test_python_computation_is_rerun_in_the_host_sandbox(self) -> None:
        expected = hashlib.sha256(b"42\n").hexdigest()
        result = reproduce_computation(
            {
                "reproduction_request": {
                    "language": "python",
                    "program": "print(6 * 7)",
                    "deterministic": True,
                    "observed_stdout_sha256": expected,
                    "timeout_seconds": 10,
                }
            }
        )
        self.assertEqual(result["status"], "reproduced", result)
        self.assertTrue(result["reproduced"])
        self.assertFalse(result["proof_authority"])
        self.assertEqual(result["actual_stdout_sha256"], expected)
        self.assertEqual(result["reproduction_repeats"], 2)
        self.assertTrue(result["stable_across_repeats"])
        self.assertTrue(result["executable_attestation"]["valid"])
        self.assertEqual(
            64, len(result["executable_attestation"]["executable_sha256"])
        )

    def test_unknown_backend_version_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = Path(tmpdir) / "checker"
            executable.write_text(
                "#!/bin/sh\nprintf 'Example Checker 99.0.0\\n'\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            result = attest_executable(
                str(executable),
                version_args=["--version"],
                minimum_version=(1, 0),
                maximum_version=(2, 0),
            )
            self.assertFalse(result["valid"])
            self.assertEqual("99.0.0", result["parsed_version"])

    def test_checker_attestation_rejects_writable_and_self_modifying_binaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            writable = Path(tmpdir) / "writable-checker"
            writable.write_text(
                "#!/bin/sh\nprintf 'Checker 1.2.0\\n'\n",
                encoding="utf-8",
            )
            writable.chmod(0o775)
            writable_result = attest_executable(
                str(writable),
                version_args=["--version"],
                minimum_version=(1, 0),
                maximum_version=(2, 0),
            )
            self.assertFalse(writable_result["valid"])
            self.assertIn("group- or world-writable", writable_result["error"])

            self_modifying = Path(tmpdir) / "self-modifying-checker"
            self_modifying.write_text(
                "#!/bin/sh\n"
                "printf 'Checker 1.2.0\\n'\n"
                "printf '# changed during probe\\n' >> \"$0\"\n",
                encoding="utf-8",
            )
            self_modifying.chmod(0o755)
            changed_result = attest_executable(
                str(self_modifying),
                version_args=["--version"],
                minimum_version=(1, 0),
                maximum_version=(2, 0),
            )
            self.assertFalse(changed_result["valid"])
            self.assertTrue(changed_result["executable_unchanged_after_probe"])

    @unittest.skipUnless(
        shutil.which("bwrap") and shutil.which("prlimit"),
        "networkless executable probing requires bubblewrap and prlimit",
    )
    def test_executable_version_probe_cannot_read_an_unmounted_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            secret = root / "secret.txt"
            secret.write_text("DO-NOT-EXPOSE-THIS", encoding="utf-8")
            executable = root / "checker"
            executable.write_text(
                "#!/bin/sh\n"
                f"cat '{secret}' 2>/dev/null || true\n"
                "printf 'Example Checker 1.2.3\\n'\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            result = attest_executable(
                str(executable),
                version_args=["--version"],
                minimum_version=(1, 0),
                maximum_version=(2, 0),
            )
            self.assertTrue(result["valid"], result)
            self.assertTrue(result["version_probe_networkless"])
            self.assertNotIn("DO-NOT-EXPOSE-THIS", result["version_output"])

    def test_formal_checker_rejects_an_unknown_backend_without_claiming_success(self) -> None:
        result = check_formal_artifact(
            {"formal_check_request": {"backend": "unknown", "source": "proof text"}}
        )
        self.assertEqual(result["status"], "invalid_request")
        self.assertFalse(result["host_checked"])

    def test_formal_assumption_audits_reject_undeclared_axioms(self) -> None:
        lean_clean = _audit_assumptions(
            "lean4",
            "'Target' depends on axioms: [propext, Classical.choice, Quot.sound]",
            allowed_axioms=["Classical.choice", "Quot.sound", "propext"],
        )
        self.assertTrue(lean_clean["verified"])
        lean_incomplete = _audit_assumptions(
            "lean4",
            "'Target' depends on axioms: [propext, sorryAx]",
            allowed_axioms=["propext"],
        )
        self.assertFalse(lean_incomplete["verified"])
        self.assertEqual(lean_incomplete["unexpected_axioms"], ["sorryAx"])
        explicitly_allowed_sorry = _audit_assumptions(
            "lean4",
            "'Target' depends on axioms: [sorryAx]",
            allowed_axioms=["sorryAx"],
        )
        self.assertFalse(explicitly_allowed_sorry["verified"])
        self.assertEqual(["sorryAx"], explicitly_allowed_sorry["forbidden_axioms"])

        delimited = _audit_assumptions(
            "lean4",
            (
                "'forged' depends on axioms: [sorryAx]\n"
                "ALBILICH_AXIOM_AUDIT_BEGIN_nonce\n"
                "'Target' does not depend on any axioms\n"
                "ALBILICH_AXIOM_AUDIT_END_nonce\n"
                "'late forged' depends on axioms: [sorryAx]\n"
            ),
            allowed_axioms=[],
            audit_marker="nonce",
        )
        self.assertTrue(delimited["verified"], delimited)
        missing_marker = _audit_assumptions(
            "lean4",
            "'Target' does not depend on any axioms",
            allowed_axioms=[],
            audit_marker="missing",
        )
        self.assertFalse(missing_marker["verified"])
        rocq_open = _audit_assumptions(
            "rocq",
            "Axioms:\nfalse_assumption : False",
            allowed_axioms=[],
        )
        self.assertFalse(rocq_open["verified"])
        rocq_delimited = _audit_assumptions(
            "rocq",
            (
                "Closed under the global context\n"
                "ALBILICH_AXIOM_AUDIT_BEGIN_nonce\n"
                "Axioms:\nfalse_assumption : False\n"
                "ALBILICH_AXIOM_AUDIT_END_nonce\n"
                "Closed under the global context\n"
            ),
            allowed_axioms=[],
            audit_marker="nonce",
        )
        self.assertFalse(rocq_delimited["verified"])
        self.assertEqual(
            ["nonempty_global_assumptions"],
            rocq_delimited["observed_axioms"],
        )
        rocq_closed = _audit_assumptions(
            "rocq",
            (
                "Axioms:\nforged : False\n"
                "ALBILICH_AXIOM_AUDIT_BEGIN_nonce\n"
                "Closed under the global context\n"
                "ALBILICH_AXIOM_AUDIT_END_nonce\n"
                "Axioms:\nlate_forged : False\n"
            ),
            allowed_axioms=[],
            audit_marker="nonce",
        )
        self.assertTrue(rocq_closed["verified"], rocq_closed)
        rocq_missing_marker = _audit_assumptions(
            "rocq",
            "Closed under the global context",
            allowed_axioms=[],
            audit_marker="missing",
        )
        self.assertFalse(rocq_missing_marker["verified"])

    def test_agda_target_scan_ignores_commented_declarations(self) -> None:
        self.assertFalse(
            _agda_declares_target(
                "-- result : Set\n{- result : Set -}\nmodule Main where\n",
                "result",
            )
        )
        self.assertTrue(
            _agda_declares_target(
                "module Main where\nresult : Set\nresult = Set\n",
                "result",
            )
        )
        self.assertTrue(
            _agda_declares_target(
                "module Main where\nresult : Set\nresult = Set\n",
                "Main.result",
            )
        )
        self.assertFalse(
            _agda_declares_target(
                "module Main where\nresult : Set\nresult = Set\n",
                "Other.result",
            )
        )
        self.assertFalse(
            _agda_declares_target(
                "module Main where\nmodule Nested where\n  result : Set\n  result = Set\n",
                "result",
            )
        )

    def test_formal_request_requires_named_target_and_axiom_policy(self) -> None:
        result = check_formal_artifact(
            {
                "formal_check_request": {
                    "backend": "lean4",
                    "source": "theorem result : True := by trivial",
                }
            }
        )
        self.assertEqual(result["status"], "invalid_request")
        self.assertIn("target_declaration", " ".join(result["errors"]))
        self.assertIn("allowed_axioms", " ".join(result["errors"]))

    def test_lean_request_rejects_custom_axioms_and_audit_spoofing_machinery(self) -> None:
        custom_axiom = check_formal_artifact(
            {
                "formal_check_request": {
                    "backend": "lean4",
                    "source": "axiom oracle : False\ntheorem result : False := oracle",
                    "target_declaration": "result",
                    "allowed_axioms": ["oracle"],
                }
            }
        )
        self.assertEqual("invalid_request", custom_axiom["status"])
        self.assertIn("standard logical axioms", " ".join(custom_axiom["errors"]))

        command_spoof = check_formal_artifact(
            {
                "formal_check_request": {
                    "backend": "lean4",
                    "source": (
                        "macro \"#print\" \"axioms\" ident : command => "
                        "`(#eval IO.println \"does not depend on any axioms\")\n"
                        "theorem result : True := by trivial"
                    ),
                    "target_declaration": "result",
                    "allowed_axioms": [],
                }
            }
        )
        self.assertEqual("invalid_request", command_spoof["status"])
        self.assertIn("syntax or elaborators", " ".join(command_spoof["errors"]))

        comments_are_inert = check_formal_artifact(
            {
                "formal_check_request": {
                    "backend": "lean4",
                    "source": (
                        "-- macro and #eval in a comment\n"
                        "theorem result : True := by trivial"
                    ),
                    "target_declaration": "result",
                    "allowed_axioms": [],
                }
            }
        )
        self.assertNotEqual("invalid_request", comments_are_inert["status"])

    @unittest.skipUnless(
        shutil.which("bwrap") and shutil.which("prlimit"),
        "formal sandbox dependencies are unavailable",
    )
    def test_lean_adapter_runs_a_separate_attested_kernel_checker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_dir = Path(tmpdir)
            lean = tool_dir / "lean"
            lean.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"--version\" ]; then\n"
                "  printf 'Lean (version 4.33.1)\\n'\n"
                "  exit 0\n"
                "fi\n"
                "output=''\n"
                "source=''\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = \"-o\" ]; then output=$2; shift 2; else source=$1; shift; fi\n"
                "done\n"
                "printf 'simulated olean bytes\\n' > \"$output\"\n"
                "begin=$(/bin/sed -n 's/.*\"\\(ALBILICH_AXIOM_AUDIT_BEGIN_[0-9a-f]*\\)\".*/\\1/p' \"$source\")\n"
                "end=$(/bin/sed -n 's/.*\"\\(ALBILICH_AXIOM_AUDIT_END_[0-9a-f]*\\)\".*/\\1/p' \"$source\")\n"
                "printf '%s\\n' \"$begin\"\n"
                "printf \"'result' does not depend on any axioms\\n\"\n"
                "printf '%s\\n' \"$end\"\n",
                encoding="utf-8",
            )
            lean.chmod(0o755)
            path = f"{tool_dir}:{os.environ.get('PATH', '')}"
            request = {
                "formal_check_request": {
                    "backend": "lean4",
                    "source": "theorem result : True := by trivial",
                    "target_declaration": "result",
                    "allowed_axioms": [],
                }
            }
            with mock.patch.dict(os.environ, {"PATH": path}):
                unavailable = check_formal_artifact(request)
            self.assertEqual("independent_checker_unavailable", unavailable["status"])
            self.assertFalse(unavailable["host_checked"])

            checker = tool_dir / "lean4checker"
            checker.write_text(
                "#!/bin/sh\ntest -s \"$1\"\n",
                encoding="utf-8",
            )
            checker.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": path}):
                checked = check_formal_artifact(request)
            self.assertEqual("checked", checked["status"], checked)
            self.assertTrue(checked["host_checked"], checked)
            self.assertTrue(
                checked["independent_checker_attestation"]["valid"]
            )
            self.assertTrue(checked["independent_checker_unchanged_after_check"])

    def test_formal_status_requires_prior_review_and_exact_host_subject_binding(self) -> None:
        def formal_patch(store: ProofStateStore, artifact_id: str) -> tuple[PatchAuthority, dict]:
            revision = store.get_revision()
            authority = PatchAuthority(
                source="session",
                actor_role="formal_backend",
                mode="formalize",
                target_id="root",
                context_revision=revision,
                context_hash=f"formal-context-{revision}",
                session_id=f"formal-session-{revision}",
                run_id=f"formal-run-{artifact_id}",
                reviewer_identity="formal:test",
                reviewer_independence_class="formal:test",
                reviewer_backend="lean4",
                authorized_existing_ids=("root",),
            )
            patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": revision,
                "actor_role": "formal_backend",
                "target_id": "root",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": artifact_id,
                        "artifact_type": "formal_backend_result",
                        "content": "The host checked the supplied formal source.",
                        "metadata": {
                            "target_type": "claim",
                            "target_id": "root",
                            "formal_check_request": {
                                "backend": "lean4",
                                "source": "theorem result : True := by trivial",
                                "target_declaration": "result",
                                "allowed_axioms": [],
                            },
                        },
                    },
                    {
                        "op": "propose_status_transition",
                        "target_type": "claim",
                        "target_id": "root",
                        "status_type": "validation",
                        "new_status": "formally_verified",
                        "evidence_artifact_ids": [artifact_id],
                    },
                ],
                "rationale": "exercise formal target binding",
            }
            return authority, patch

        with tempfile.TemporaryDirectory() as tmpdir:
            unreviewed = ProofStateStore(
                "unreviewed-formal-target",
                generation_root=Path(tmpdir) / "generation-a",
            )
            unreviewed.init_problem("The root theorem holds.")
            authority, patch = formal_patch(unreviewed, "formal-unreviewed")
            with mock.patch(
                "agents.generation.phase2.patches.check_formal_artifact",
                return_value={"status": "checked", "host_checked": True},
            ):
                rejected = apply_patch(unreviewed, patch, authority=authority)
            self.assertFalse(rejected.accepted)
            self.assertIn("already passed strict informal verification", " ".join(rejected.errors))

            reviewed = ProofStateStore(
                "reviewed-formal-target",
                generation_root=Path(tmpdir) / "generation-b",
            )
            reviewed.init_problem("The root theorem holds.")
            certify_and_integrate_claim(reviewed, claim_id="root")
            authority, patch = formal_patch(reviewed, "formal-reviewed")
            with mock.patch(
                "agents.generation.phase2.patches.check_formal_artifact",
                return_value={"status": "checked", "host_checked": True},
            ):
                accepted = apply_patch(reviewed, patch, authority=authority)
            self.assertTrue(accepted.accepted, accepted.errors)
            with reviewed.connect() as conn:
                row = conn.execute(
                    "SELECT metadata_json FROM artifacts WHERE artifact_id = ?",
                    ("formal-reviewed",),
                ).fetchone()
            binding = json.loads(row["metadata_json"])["host_formal_target_binding"]
            self.assertEqual("root", binding["target_id"])
            self.assertEqual(64, len(binding["subject_digest"]))

            request = apply_operator_patch(
                reviewed,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": reviewed.problem_id,
                    "base_revision": reviewed.get_revision(),
                    "actor_role": "human_operator",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_proof_obligation",
                            "proof_obligation_id": "formalize-root-again",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "obligation_type": "formalization_gap",
                            "severity": "minor",
                            "status": "active",
                            "obligation": "Recheck the formal encoding after its next revision.",
                        }
                    ],
                    "rationale": "request an explicit formal verification pass",
                },
            )
            self.assertTrue(request.accepted, request.errors)
            action = next_action(reviewed)
            self.assertEqual("formalize", action["mode"])
            self.assertEqual("root", action["target_id"])
            self.assertTrue(action["formalization_requested"])


class ReplayAndCertificateTamperTests(unittest.TestCase):
    def test_event_history_is_append_only_after_hash_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "event-history-guards",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            with store.connect() as conn:
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError,
                    "event history is append-only",
                ):
                    conn.execute(
                        "UPDATE events SET payload_json = '{}' "
                        "WHERE event_id = (SELECT MAX(event_id) FROM events)"
                    )
                conn.rollback()
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError,
                    "event history is append-only",
                ):
                    conn.execute(
                        "DELETE FROM events WHERE event_id = "
                        "(SELECT MAX(event_id) FROM events)"
                    )
                conn.rollback()

                event_ids = [
                    int(row["event_id"])
                    for row in conn.execute(
                        "SELECT event_id FROM events ORDER BY event_id"
                    ).fetchall()
                ]
                source_ids = [
                    int(row["event_id"])
                    for row in conn.execute(
                        "SELECT event_id FROM event_source_entries ORDER BY sequence"
                    ).fetchall()
                ]
                self.assertEqual(event_ids, source_ids)
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError,
                    "event source history is append-only",
                ):
                    conn.execute(
                        "DELETE FROM event_source_entries WHERE sequence = 1"
                    )
                conn.rollback()

                conn.execute(
                    "INSERT INTO events(revision, event_type, payload_json, "
                    "created_at, previous_event_hash, event_hash) "
                    "VALUES (0, 'raw_fixture', '{}', ?, '', '')",
                    ("2026-01-01T00:00:00+00:00",),
                )
                raw_insert_seal = store.current_event_seal(conn)
                self.assertFalse(raw_insert_seal["valid"], raw_insert_seal)
                self.assertTrue(
                    any(
                        "recorded event-chain length" in error
                        for error in raw_insert_seal["errors"]
                    ),
                    raw_insert_seal,
                )
                conn.rollback()

                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DROP TRIGGER guard_events_update")
                conn.execute(
                    "CREATE TRIGGER guard_events_update BEFORE UPDATE ON events "
                    "BEGIN SELECT 1; END"
                )
                conn.commit()
            altered_seal = store.current_event_seal()
            altered_replay = verify_event_journal(store)
            self.assertFalse(altered_seal["valid"])
            self.assertTrue(
                any("missing or altered" in error for error in altered_seal["errors"]),
                altered_seal,
            )
            self.assertFalse(altered_replay["valid"])
            self.assertTrue(
                any("missing or altered" in error for error in altered_replay["errors"]),
                altered_replay,
            )
            with store.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DROP TRIGGER guard_events_update")
                store._ensure_event_history_guards(conn)
                conn.commit()
            self.assertTrue(store.current_event_seal()["valid"])
            self.assertTrue(verify_event_journal(store)["valid"])

    def _certified_store(self, tmpdir: str, problem_id: str) -> ProofStateStore:
        store = ProofStateStore(problem_id, generation_root=Path(tmpdir) / "generation")
        store.init_problem("The root theorem holds.")
        certify_and_integrate_claim(store, claim_id="root")
        return store

    def test_journal_replay_accepts_a_genuine_chain_and_detects_state_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._certified_store(tmpdir, "journal-state-tamper")
            clean = verify_patch_journal(store)
            self.assertTrue(clean["valid"], clean)
            self.assertEqual(clean["patch_count"], clean["verified_patch_count"])
            self.assertEqual(
                clean["patch_count"], clean["forward_verified_patch_count"]
            )
            with store.connect() as conn:
                conn.execute("UPDATE claims SET statement = 'Tampered theorem.' WHERE claim_id = 'root'")
                conn.commit()
                invariant_errors = validate_conn(conn)
            self.assertTrue(any("host-bound certificate" in error for error in invariant_errors))
            tampered = verify_patch_journal(store)
            self.assertFalse(tampered["valid"])
            self.assertTrue(any("current proof state" in error for error in tampered["errors"]))

    def test_full_replay_binds_the_native_revision_zero_state_seal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "genesis-replay-seal", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            self.assertTrue(verify_patch_journal(store)["valid"])
            with store.connect() as conn:
                conn.execute(
                    "UPDATE claims SET root_impact = 0.25 WHERE claim_id = 'root'"
                )
                conn.commit()

            replay = verify_patch_journal(store)
            self.assertFalse(replay["valid"], replay)
            self.assertTrue(
                any("recorded current-state seal" in error for error in replay["errors"]),
                replay,
            )

    def test_current_state_seal_blocks_context_and_mutation_after_direct_sql_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._certified_store(tmpdir, "current-state-seal-boundary")
            with store.connect() as conn:
                conn.execute(
                    "UPDATE claims SET root_impact = 0.875 WHERE claim_id = 'root'"
                )
                conn.commit()

            seal = store.current_state_seal()
            self.assertFalse(seal["valid"], seal)
            self.assertTrue(
                any("current-state seal" in error for error in seal["errors"]),
                seal,
            )
            with self.assertRaisesRegex(RuntimeError, "proof-state seal is invalid"):
                build_context_manifest(store, max_chars=120_000)

            outcome = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "human_operator",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_proof_obligation",
                            "proof_obligation_id": "must-not-apply-after-tamper",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "obligation_type": "proof_gap",
                            "severity": "major",
                            "status": "active",
                            "obligation": "This operation must be rejected at the seal boundary.",
                        }
                    ],
                    "rationale": "exercise the incremental integrity boundary",
                },
            )
            self.assertFalse(outcome.accepted)
            self.assertTrue(
                any("proof-state seal is invalid" in error for error in outcome.errors),
                outcome.errors,
            )

    def test_journal_replay_detects_a_modified_recorded_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._certified_store(tmpdir, "journal-delta-tamper")
            with store.connect() as conn:
                store._drop_patch_history_guards(conn)
                conn.execute(
                    "UPDATE patches SET state_delta_json = '[]' WHERE applied_revision = 2"
                )
                store._ensure_patch_history_guards(conn)
                conn.commit()
            result = verify_patch_journal(store)
            self.assertFalse(result["valid"])
            self.assertTrue(any("before-hash mismatch" in error for error in result["errors"]))

    def test_journal_entry_hash_binds_rationale_and_authority_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._certified_store(tmpdir, "journal-annotation-tamper")
            with store.connect() as conn:
                store._drop_patch_history_guards(conn)
                conn.execute(
                    "UPDATE patches SET rationale='rewritten explanation', "
                    "authority_json='{}' WHERE applied_revision=1"
                )
                store._ensure_patch_history_guards(conn)
                conn.commit()
            result = verify_patch_journal(store)
            self.assertFalse(result["valid"])
            self.assertTrue(
                any("journal-entry hash mismatch" in error for error in result["errors"]),
                result,
            )

    def test_event_chain_detects_payload_tampering_and_tail_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "event-chain-tamper", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            store.set_completion_policy("exploratory", reason="test", source="test")
            clean = verify_event_journal(store)
            self.assertTrue(clean["valid"], clean)
            with store.connect() as conn:
                store._drop_event_history_guards(conn)
                conn.execute(
                    "UPDATE events SET payload_json='{}' "
                    "WHERE event_type='completion_policy'"
                )
                store._ensure_event_history_guards(conn)
                conn.commit()
            tampered = verify_event_journal(store)
            self.assertFalse(tampered["valid"])
            self.assertTrue(
                any("entry hash mismatch" in error for error in tampered["errors"]),
                tampered,
            )
            current_seal = store.current_state_seal()
            self.assertFalse(current_seal["valid"], current_seal)
            self.assertTrue(
                any("event journal" in error for error in current_seal["errors"]),
                current_seal,
            )

            with tempfile.TemporaryDirectory() as second_tmpdir:
                second = ProofStateStore(
                    "event-chain-tail-delete",
                    generation_root=Path(second_tmpdir) / "generation",
                )
                second.init_problem("The root theorem holds.")
                second.set_completion_policy(
                    "exploratory", reason="test", source="test"
                )
                with second.connect() as conn:
                    second._drop_event_history_guards(conn)
                    conn.execute(
                        "DELETE FROM event_source_entries WHERE event_id = "
                        "(SELECT MAX(event_id) FROM events)"
                    )
                    conn.execute(
                        "DELETE FROM events WHERE event_id=(SELECT MAX(event_id) FROM events)"
                    )
                    second._ensure_event_history_guards(conn)
                    conn.commit()
                deleted = verify_event_journal(second)
                self.assertFalse(deleted["valid"])
                self.assertTrue(
                    any("chain length mismatch" in error for error in deleted["errors"]),
                    deleted,
                )
                self.assertFalse(second.current_state_seal()["valid"])

    def test_current_event_seal_reports_malformed_policy_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "malformed-policy-event", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            store.set_parallel_branches(3, reason="test", source="test")
            with store.connect() as conn:
                store._drop_event_history_guards(conn)
                conn.execute(
                    "UPDATE events SET payload_json = ? "
                    "WHERE event_type = 'parallel_branch_mode'",
                    (json.dumps({"to": [], "mode": "multi_branch_research"}),),
                )
                store._ensure_event_history_guards(conn)
                conn.commit()

            seal = store.current_event_seal()
            self.assertFalse(seal["valid"], seal)
            self.assertTrue(
                any("worker count is not an integer" in error for error in seal["errors"]),
                seal,
            )

    def test_current_seals_return_invalid_for_malformed_database_integers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            event_store = ProofStateStore(
                "malformed-event-integer",
                generation_root=Path(tmpdir) / "event-generation",
            )
            event_store.init_problem("The root theorem holds.")
            with event_store.connect() as conn:
                event_store._drop_event_history_guards(conn)
                conn.execute(
                    "UPDATE events SET revision = 'not-an-integer' "
                    "WHERE event_id = (SELECT MAX(event_id) FROM events)"
                )
                event_store._ensure_event_history_guards(conn)
                conn.commit()
            event_seal = event_store.current_event_seal()
            self.assertFalse(event_seal["valid"], event_seal)
            self.assertTrue(
                any("entry is malformed" in error for error in event_seal["errors"]),
                event_seal,
            )
            event_replay = verify_event_journal(event_store)
            self.assertFalse(event_replay["valid"], event_replay)
            self.assertTrue(
                any("proof revision is not an integer" in error for error in event_replay["errors"]),
                event_replay,
            )

            state_store = ProofStateStore(
                "malformed-state-integer",
                generation_root=Path(tmpdir) / "state-generation",
            )
            state_store.init_problem("The root theorem holds.")
            with state_store.connect() as conn:
                conn.execute(
                    "UPDATE problem_state SET current_revision = 'not-an-integer'"
                )
                conn.commit()
            state_seal = state_store.current_state_seal()
            self.assertFalse(state_seal["valid"], state_seal)
            self.assertTrue(
                any("current proof revision is not an integer" in error for error in state_seal["errors"]),
                state_seal,
            )
            patch_replay = verify_patch_journal(state_store)
            self.assertFalse(patch_replay["valid"], patch_replay)
            self.assertTrue(
                any("current proof revision is not an integer" in error for error in patch_replay["errors"]),
                patch_replay,
            )

    def test_policy_events_require_schema_even_when_hashes_are_self_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "policy-event-schema", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            with store.connect() as conn:
                with self.assertRaisesRegex(ValueError, "requires a valid string field"):
                    store.write_event(conn, 0, "completion_policy", {})
                with self.assertRaisesRegex(ValueError, "run_control_event_id"):
                    store.write_event(
                        conn,
                        0,
                        "run_control_policy",
                        {"to": "running"},
                    )
                with self.assertRaisesRegex(ValueError, "does not identify"):
                    store.write_event(
                        conn,
                        0,
                        "run_control_policy",
                        {"to": "running", "run_control_event_id": 999_999},
                    )
                conn.rollback()

            store.set_completion_policy("exploratory", reason="test", source="test")
            with store.connect() as conn:
                store._drop_event_history_guards(conn)
                conn.execute(
                    "UPDATE events SET payload_json = '{}' "
                    "WHERE event_type = 'completion_policy'"
                )
                row = dict(
                    conn.execute(
                        "SELECT * FROM events WHERE event_type = 'completion_policy'"
                    ).fetchone()
                )
                digest = event_entry_hash(row)
                conn.execute(
                    "UPDATE events SET event_hash = ? "
                    "WHERE event_type = 'completion_policy'",
                    (digest,),
                )
                conn.execute(
                    "UPDATE problem_state SET event_chain_head = ?, policy_event_head = ?",
                    (digest, digest),
                )
                store._ensure_event_history_guards(conn)
                conn.commit()

            seal = store.current_event_seal()
            self.assertFalse(seal["valid"], seal)
            self.assertTrue(
                any("requires a valid string field" in error for error in seal["errors"]),
                seal,
            )
            replay = verify_event_journal(store)
            self.assertFalse(replay["valid"], replay)
            self.assertTrue(
                any("requires a valid string field" in error for error in replay["errors"]),
                replay,
            )

    def test_session_patch_fails_if_policy_changes_after_context_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "stale-policy-session", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            policy_head = store.audit_chain_heads()["policy_event_head"]
            authority = PatchAuthority(
                source="session",
                actor_role="researcher",
                mode="prove",
                target_id="root",
                context_revision=0,
                context_hash="context-before-policy-change",
                policy_event_head=policy_head,
                authorized_existing_ids=("root",),
            )
            store.set_completion_policy(
                "exploratory", reason="operator changed policy", source="test"
            )
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "stale-policy-claim",
                            "kind": "lemma",
                            "statement": "This patch used stale policy context.",
                        }
                    ],
                    "rationale": "must be rejected",
                },
                authority=authority,
            )
            self.assertFalse(outcome.accepted)
            self.assertIn("policy changed", " ".join(outcome.errors))

    def test_run_control_change_invalidates_an_in_flight_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "stale-run-control-session",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            policy_head = store.audit_chain_heads()["policy_event_head"]
            authority = PatchAuthority(
                source="session",
                actor_role="researcher",
                mode="prove",
                target_id="root",
                context_revision=0,
                context_hash="context-before-pause",
                policy_event_head=policy_head,
                authorized_existing_ids=("root",),
            )
            store.set_run_status(
                "pause_requested",
                reason="operator paused while the child was running",
                source="test",
            )
            journal = verify_event_journal(store)
            self.assertTrue(journal["valid"], journal)
            self.assertNotEqual(
                policy_head,
                store.audit_chain_heads()["policy_event_head"],
            )
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "claim-from-paused-session",
                            "kind": "lemma",
                            "statement": "This result arrived after the operator paused the run.",
                        }
                    ],
                    "rationale": "must be rejected as stale policy context",
                },
                authority=authority,
            )
            self.assertFalse(outcome.accepted)
            self.assertIn("policy changed", " ".join(outcome.errors))

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is unavailable")
    def test_external_ed25519_checkpoint_survives_append_and_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            private_key = root / "private.pem"
            public_key = root / "public.pem"
            subprocess.run(
                [
                    shutil.which("openssl") or "openssl",
                    "genpkey",
                    "-algorithm",
                    "ED25519",
                    "-out",
                    str(private_key),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [
                    shutil.which("openssl") or "openssl",
                    "pkey",
                    "-in",
                    str(private_key),
                    "-pubout",
                    "-out",
                    str(public_key),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            store = ProofStateStore(
                "external-audit-checkpoint", generation_root=root / "generation"
            )
            store.init_problem("The root theorem holds.")
            checkpoint = root / "external" / "checkpoint.json"
            created = create_signed_audit_checkpoint(
                store,
                output_path=checkpoint,
                private_key_path=private_key,
            )
            self.assertTrue(created["valid"])
            self.assertEqual(64, len(created["payload"]["run_provenance_hash"]))
            appended = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "after-checkpoint",
                            "kind": "lemma",
                            "statement": "A later append is allowed.",
                        }
                    ],
                    "rationale": "append after external checkpoint",
                },
            )
            self.assertTrue(appended.accepted, appended.errors)
            verified = verify_signed_audit_checkpoint(
                store,
                checkpoint_path=checkpoint,
                public_key_path=public_key,
            )
            self.assertTrue(verified["valid"], verified)

            document = json.loads(checkpoint.read_text(encoding="utf-8"))
            document["payload"]["proof_state_hash"] = "f" * 64
            checkpoint.write_text(
                json.dumps(document, sort_keys=True), encoding="utf-8"
            )
            tampered = verify_signed_audit_checkpoint(
                store,
                checkpoint_path=checkpoint,
                public_key_path=public_key,
            )
            self.assertFalse(tampered["valid"])
            self.assertTrue(
                any("signature is invalid" in error for error in tampered["errors"]),
                tampered,
            )

            document["payload"]["checkpoint_version"] = []
            checkpoint.write_text(
                json.dumps(document, sort_keys=True), encoding="utf-8"
            )
            with mock.patch(
                "agents.generation.phase2.audit_checkpoint.verify_patch_journal",
                side_effect=AssertionError("untrusted checkpoint triggered replay"),
            ):
                malformed = verify_signed_audit_checkpoint(
                    store,
                    checkpoint_path=checkpoint,
                    public_key_path=public_key,
                )
            self.assertFalse(malformed["valid"])
            self.assertFalse(malformed["signature_valid"])

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is unavailable")
    def test_audit_checkpoint_rejects_publicly_readable_private_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ProofStateStore(
                "checkpoint-private-key-permissions",
                generation_root=root / "generation",
            )
            store.init_problem("The root theorem holds.")
            private_key = root / "unsafe-private.pem"
            subprocess.run(
                [
                    shutil.which("openssl") or "openssl",
                    "genpkey",
                    "-algorithm",
                    "ED25519",
                    "-out",
                    str(private_key),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            private_key.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "group or other permissions"):
                create_signed_audit_checkpoint(
                    store,
                    output_path=root / "checkpoint.json",
                    private_key_path=private_key,
                )

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is unavailable")
    def test_audit_checkpoint_does_not_follow_an_output_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ProofStateStore(
                "checkpoint-output-symlink",
                generation_root=root / "generation",
            )
            store.init_problem("The root theorem holds.")
            private_key = root / "private.pem"
            subprocess.run(
                [
                    shutil.which("openssl") or "openssl",
                    "genpkey",
                    "-algorithm",
                    "ED25519",
                    "-out",
                    str(private_key),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            protected = root / "protected.txt"
            protected.write_text("operator-owned material\n", encoding="utf-8")
            output = root / "checkpoint.json"
            output.symlink_to(protected)

            with self.assertRaisesRegex(ValueError, "must not be a symbolic link"):
                create_signed_audit_checkpoint(
                    store,
                    output_path=output,
                    private_key_path=private_key,
                )
            self.assertEqual(
                "operator-owned material\n", protected.read_text(encoding="utf-8")
            )

    def test_journal_replay_detects_artifact_file_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._certified_store(tmpdir, "journal-artifact-tamper")
            with store.connect() as conn:
                row = conn.execute(
                    "SELECT artifact_id, path FROM artifacts WHERE path != '' "
                    "ORDER BY state_revision LIMIT 1"
                ).fetchone()
            self.assertIsNotNone(row)
            Path(str(row["path"])).write_text("tampered artifact bytes\n", encoding="utf-8")
            result = verify_patch_journal(store)
            self.assertFalse(result["valid"])
            self.assertTrue(
                any("file hash mismatch" in error for error in result["errors"]),
                result,
            )

    def test_journal_replay_detects_deleted_history_and_leading_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._certified_store(tmpdir, "journal-history-deletion")
            with store.connect() as conn:
                store._drop_patch_history_guards(conn)
                conn.execute("DELETE FROM patches WHERE applied_revision = 1")
                store._ensure_patch_history_guards(conn)
                conn.commit()
            missing_prefix = verify_patch_journal(store)
            self.assertFalse(missing_prefix["valid"])
            self.assertTrue(
                any("do not cover" in error for error in missing_prefix["errors"]),
                missing_prefix,
            )
            with store.connect() as conn:
                store._drop_patch_history_guards(conn)
                conn.execute("DELETE FROM patches")
                store._ensure_patch_history_guards(conn)
                conn.commit()
            missing_all = verify_patch_journal(store)
            self.assertFalse(missing_all["valid"])
            self.assertTrue(
                any("do not cover" in error for error in missing_all["errors"]),
                missing_all,
            )

    def test_branch_workbench_versions_are_journaled_and_replayable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "journal-branch-workbench", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            seed = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "branch-lemma",
                            "kind": "lemma",
                            "statement": "The branch lemma holds.",
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "branch/route",
                            "conclusion_claim_id": "branch-lemma",
                            "strategy": "reduce to a finite auxiliary statement",
                        },
                    ],
                    "rationale": "create a replay-test branch",
                },
            )
            self.assertTrue(seed.accepted, seed.errors)
            first = sync_branch_workbenches(store)
            self.assertEqual(len(first["updated"]), 1)
            debt = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "researcher",
                    "target_id": "branch-lemma",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "branch-obligation",
                            "owner_type": "route",
                            "owner_id": "branch/route",
                            "debt_type": "proof_obligation",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Prove the finite auxiliary statement.",
                            "suggested_next_target": "branch-lemma",
                        }
                    ],
                    "rationale": "change the branch workbench content",
                },
            )
            self.assertTrue(debt.accepted, debt.errors)
            second = sync_branch_workbenches(store)
            self.assertEqual(len(second["updated"]), 1)
            self.assertNotEqual(first["updated"], second["updated"])
            replay = verify_patch_journal(store)
            self.assertTrue(replay["valid"], replay)


class MigrationAndHostMutationSafetyTests(unittest.TestCase):
    @staticmethod
    def _record_failed_scheduler_lifecycle(
        store: ProofStateStore,
        *,
        run_id: str,
    ) -> None:
        def executor(*, session_plan, **_kwargs):
            return {
                "run_id": run_id,
                "actor_role": session_plan["actor_role"],
                "status": "failed",
                "returncode": 1,
                "wall_time_seconds": 0.0,
                "usage": {"input_tokens": 1, "total_tokens": 1},
                "session_id": "",
                "patch": None,
                "patch_error": "synthetic failure",
                "failure_kind": "test",
            }

        run_workflow(
            store,
            steps=1,
            execute=True,
            parallel_librarian_verifier=False,
            parallel_branches=0,
            write_on_stop=False,
            write_console=False,
            executor=executor,
        )

    @staticmethod
    def _simulate_v10_fairness_schema(conn: sqlite3.Connection) -> None:
        columns_by_table = {
            "scheduler_candidate_deferrals": (
                "candidate_id, consecutive_capacity_deferrals, last_wave_id, "
                "policy_version, updated_run_id"
            ),
            "scheduler_fairness_meta": (
                "singleton, last_wave_id, last_state_revision, policy_version, "
                "updated_run_id"
            ),
            "scheduler_decision_deferrals": (
                "candidate_id, consecutive_deferrals, last_decision_id, "
                "policy_version, updated_run_id"
            ),
            "scheduler_decision_fairness_meta": (
                "singleton, last_decision_id, last_state_revision, "
                "policy_version, updated_run_id"
            ),
        }
        for table, columns in columns_by_table.items():
            conn.execute(f"ALTER TABLE {table} RENAME TO {table}_v11_fixture")
            conn.execute(
                f"CREATE TABLE {table} AS SELECT {columns} "
                f"FROM {table}_v11_fixture"
            )
            conn.execute(f"DROP TABLE {table}_v11_fixture")
        conn.execute("DELETE FROM schema_migrations WHERE version >= 11")

    def test_v11_migration_rebuilds_fairness_provenance_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v10-dispatch-migration",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            action = {
                "mode": "prove",
                "target_id": "root",
                "route_id": "",
                "budget": {"requested_tokens": 0},
            }
            seeded = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        run_metrics_operation(
                            run_id="v10-fairness-source",
                            action=action,
                            session_plan={
                                "actor_role": "researcher",
                                "state_revision": 0,
                            },
                            usage_payload={},
                        )
                    ],
                    "rationale": "seed nonempty v10 fairness provenance",
                },
            )
            self.assertTrue(seeded.accepted, seeded.errors)
            with store.connect() as conn:
                conn.execute(
                    "INSERT INTO scheduler_decision_fairness_meta("
                    "singleton, last_decision_id, last_state_revision, "
                    "policy_version, updated_run_id, updated_dispatch_id) "
                    "VALUES (1, ?, 0, 8, ?, NULL)",
                    ("v10-fairness-source", "v10-fairness-source"),
                )
                _restore_v14_proof_projection_seal(store, conn)
                self._simulate_v10_fairness_schema(conn)
                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ?",
                    (_legacy_v10_run_provenance_hash(conn),),
                )
                conn.commit()

            with store.connect() as conn:
                conn.execute("BEGIN")
                versions = [
                    int(row["version"])
                    for row in conn.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                ]
                for table in (
                    "scheduler_candidate_deferrals",
                    "scheduler_fairness_meta",
                    "scheduler_decision_deferrals",
                    "scheduler_decision_fairness_meta",
                ):
                    columns = {
                        str(row["name"])
                        for row in conn.execute(f"PRAGMA table_info({table})")
                    }
                    self.assertIn("updated_dispatch_id", columns)
                migrated_meta = conn.execute(
                    "SELECT updated_run_id, updated_dispatch_id "
                    "FROM scheduler_decision_fairness_meta"
                ).fetchone()
                self.assertEqual(
                    "v10-fairness-source", migrated_meta["updated_run_id"]
                )
                self.assertIsNone(migrated_meta["updated_dispatch_id"])
                self.assertTrue(store.current_state_seal(conn)["valid"])
            self.assertEqual(list(range(1, 22)), versions)

    def test_v11_migration_rejects_tampered_v10_scheduler_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v10-dispatch-migration-tamper",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            outcome = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "record_run_metrics",
                            "run_id": "v10-sealed-run",
                            "actor_role": "researcher",
                            "mode": "prove",
                            "target_id": "root",
                            "selection_design": "observational",
                            "status": "completed",
                        }
                    ],
                    "rationale": "create v10 migration provenance",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with store.connect() as conn:
                _restore_v14_proof_projection_seal(store, conn)
                self._simulate_v10_fairness_schema(conn)
                store._drop_scheduler_history_guards(conn)
                legacy_hash = _legacy_v10_run_provenance_hash(conn)
                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ?",
                    (legacy_hash,),
                )
                conn.execute(
                    "UPDATE runs SET decision_trace_json = '{\"tampered\":true}' "
                    "WHERE run_id = 'v10-sealed-run'"
                )
                conn.commit()

            with self.assertRaisesRegex(
                RuntimeError, "differs from its v10 current-state seal"
            ):
                store.connect()

    def test_v12_migration_rejects_tampered_v11_dispatch_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v11-recovery-payload-migration-tamper",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            action = next_action(store, web_search="disabled")
            _record_scheduler_dispatches(
                store,
                [action],
                store.audit_chain_heads(),
                execution_contract={
                    "version": 1,
                    "driver": "builtin_codex",
                    "identity": "codex:migration-test",
                    "recovery_capability": "supervised_process",
                },
            )
            with store.connect() as conn:
                store._drop_scheduler_history_guards(conn)
                legacy_hash = _legacy_v11_run_provenance_hash(conn)
                _restore_v14_proof_projection_seal(store, conn)
                conn.execute("DELETE FROM schema_migrations WHERE version >= 12")
                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ?",
                    (legacy_hash,),
                )
                conn.execute(
                    "UPDATE scheduler_dispatches SET dispatched_action_hash = ?",
                    ("0" * 64,),
                )
                conn.commit()

            with self.assertRaisesRegex(
                RuntimeError, "differs from its v11 current-state seal"
            ):
                store.connect()

    def test_v13_migration_rejects_tampered_v12_dispatch_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v12-result-record-migration-tamper",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            action = next_action(store, web_search="disabled")
            _record_scheduler_dispatches(
                store,
                [action],
                store.audit_chain_heads(),
                execution_contract={
                    "version": 1,
                    "driver": "builtin_codex",
                    "identity": "codex:migration-test",
                    "recovery_capability": "supervised_process",
                },
            )
            with store.connect() as conn:
                store._drop_scheduler_history_guards(conn)
                legacy_hash = _legacy_v12_run_provenance_hash(conn)
                _restore_v14_proof_projection_seal(store, conn)
                conn.execute("DELETE FROM schema_migrations WHERE version >= 13")
                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ?",
                    (legacy_hash,),
                )
                conn.execute(
                    "UPDATE scheduler_dispatches SET execution_contract_json = '{}'"
                )
                conn.commit()

            with self.assertRaisesRegex(
                RuntimeError, "differs from its v12 current-state seal"
            ):
                store.connect()

    def test_v13_migration_rejects_version_downgrade_with_execution_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v13-execution-record-version-downgrade",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")

            def executor(*, session_plan, **_kwargs):
                return {
                    "run_id": "v13-recorded-run",
                    "actor_role": session_plan["actor_role"],
                    "status": "failed",
                    "returncode": 1,
                    "wall_time_seconds": 0.0,
                    "usage": {"input_tokens": 1, "total_tokens": 1},
                    "session_id": "",
                    "patch": None,
                    "patch_error": "synthetic failure",
                    "failure_kind": "test",
                }

            run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                write_on_stop=False,
                write_console=False,
                executor=executor,
            )
            with store.connect() as conn:
                _restore_v14_proof_projection_seal(store, conn)
                conn.execute("DELETE FROM schema_migrations WHERE version >= 13")
                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ?",
                    (_legacy_v12_run_provenance_hash(conn),),
                )
                conn.commit()

            with self.assertRaisesRegex(
                RuntimeError, "execution records.*labelled v12"
            ):
                store.connect()

    def test_store_rejects_noncontiguous_migration_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "noncontiguous-migration-history",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            with store.connect() as conn:
                conn.execute("DELETE FROM schema_migrations WHERE version = 12")
                conn.commit()
            with self.assertRaisesRegex(RuntimeError, "not contiguous"):
                store.connect()

    def test_v14_migration_rejects_tampered_v13_result_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v13-result-run-reservation-tamper",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")

            def executor(*, session_plan, **_kwargs):
                return {
                    "run_id": "v13-result-run",
                    "actor_role": session_plan["actor_role"],
                    "status": "failed",
                    "returncode": 1,
                    "wall_time_seconds": 0.0,
                    "usage": {"input_tokens": 1, "total_tokens": 1},
                    "session_id": "",
                    "patch": None,
                    "patch_error": "synthetic failure",
                    "failure_kind": "test",
                }

            run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                write_on_stop=False,
                write_console=False,
                executor=executor,
            )
            with store.connect() as conn:
                store._drop_scheduler_history_guards(conn)
                legacy_hash = _legacy_v13_run_provenance_hash(conn)
                _restore_v14_proof_projection_seal(store, conn)
                conn.execute("DELETE FROM schema_migrations WHERE version >= 14")
                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ?",
                    (legacy_hash,),
                )
                conn.execute(
                    "UPDATE scheduler_dispatch_results SET result_hash = ?",
                    ("0" * 64,),
                )
                conn.commit()

            with self.assertRaisesRegex(
                RuntimeError, "differs from its v13 current-state seal"
            ):
                store.connect()

    def test_v14_migration_reserves_existing_v13_result_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v13-result-run-reservation-upgrade",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")

            def executor(*, session_plan, **_kwargs):
                return {
                    "run_id": "legacy-v13-result-run",
                    "actor_role": session_plan["actor_role"],
                    "status": "failed",
                    "returncode": 1,
                    "wall_time_seconds": 0.0,
                    "usage": {"input_tokens": 1, "total_tokens": 1},
                    "session_id": "",
                    "patch": None,
                    "patch_error": "synthetic failure",
                    "failure_kind": "test",
                }

            run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                write_on_stop=False,
                write_console=False,
                executor=executor,
            )
            with store.connect() as conn:
                legacy_hash = _legacy_v13_run_provenance_hash(conn)
                _restore_v14_proof_projection_seal(store, conn)
                conn.execute(
                    "ALTER TABLE scheduler_dispatch_results "
                    "RENAME TO scheduler_dispatch_results_v14"
                )
                conn.execute(
                    "CREATE TABLE scheduler_dispatch_results ("
                    "result_id TEXT PRIMARY KEY, "
                    "dispatch_id TEXT NOT NULL UNIQUE "
                    "REFERENCES scheduler_dispatches(dispatch_id), "
                    "attempt_id TEXT NOT NULL UNIQUE "
                    "REFERENCES scheduler_dispatch_attempts(attempt_id), "
                    "session_plan_json TEXT NOT NULL, "
                    "execution_json TEXT NOT NULL, "
                    "validation_errors_json TEXT NOT NULL, "
                    "result_hash TEXT NOT NULL, completed_at TEXT NOT NULL, "
                    "event_id INTEGER NOT NULL UNIQUE REFERENCES events(event_id))"
                )
                conn.execute(
                    "INSERT INTO scheduler_dispatch_results("
                    "result_id, dispatch_id, attempt_id, session_plan_json, "
                    "execution_json, validation_errors_json, result_hash, "
                    "completed_at, event_id) SELECT result_id, dispatch_id, "
                    "attempt_id, session_plan_json, execution_json, "
                    "validation_errors_json, result_hash, completed_at, event_id "
                    "FROM scheduler_dispatch_results_v14"
                )
                conn.execute("DROP TABLE scheduler_dispatch_results_v14")
                conn.execute("DELETE FROM schema_migrations WHERE version >= 14")
                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ?",
                    (legacy_hash,),
                )
                conn.commit()

            with store.connect() as conn:
                columns = {
                    str(row["name"])
                    for row in conn.execute(
                        "PRAGMA table_info(scheduler_dispatch_results)"
                    )
                }
                result = conn.execute(
                    "SELECT run_id FROM scheduler_dispatch_results"
                ).fetchone()
                versions = [
                    int(row["version"])
                    for row in conn.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                ]
                conn.execute("BEGIN")
                self.assertTrue(store.current_state_seal(conn)["valid"])
            self.assertIn("run_id", columns)
            self.assertEqual("legacy-v13-result-run", result["run_id"])
            self.assertEqual(list(range(1, 22)), versions)

    def test_v15_migration_backfills_authenticated_scheduler_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v14-provenance-backfill",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            self._record_failed_scheduler_lifecycle(
                store,
                run_id="v14-backfill-run",
            )
            with store.connect() as conn:
                legacy_hash = _legacy_v14_run_provenance_hash(conn)
                _restore_v14_proof_projection_seal(store, conn)
                store._drop_scheduler_history_guards(conn)
                conn.execute("DROP TABLE scheduler_provenance_entries")
                conn.execute("DELETE FROM schema_migrations WHERE version >= 15")
                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ?",
                    (legacy_hash,),
                )
                conn.commit()

            with store.connect() as conn:
                source_count = sum(
                    int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                    for table in (
                        "runs",
                        "scheduler_dispatches",
                        "scheduler_dispatch_attempts",
                        "scheduler_dispatch_results",
                    )
                )
                entry_count = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM scheduler_provenance_entries"
                    ).fetchone()[0]
                )
                versions = [
                    int(row["version"])
                    for row in conn.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                ]
                guard_count = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger' "
                        "AND name IN ("
                        + ",".join("?" for _ in SCHEDULER_HISTORY_GUARD_NAMES)
                        + ")",
                        SCHEDULER_HISTORY_GUARD_NAMES,
                    ).fetchone()[0]
                )
                projection_baseline = conn.execute(
                    "SELECT * FROM projection_audit_baselines "
                    "WHERE problem_id = ?",
                    (store.problem_id,),
                ).fetchone()
                self.assertEqual([], scheduler_provenance_errors(conn))
                self.assertEqual([], validate_conn(conn))
                conn.execute("BEGIN")
                self.assertTrue(store.current_state_seal(conn)["valid"])
                conn.rollback()
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError,
                    "projection audit baseline is append-only",
                ):
                    conn.execute(
                        "UPDATE projection_audit_baselines "
                        "SET prior_state_hash = ? WHERE problem_id = ?",
                        ("0" * 64, store.problem_id),
                    )
                conn.rollback()

                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "DROP TRIGGER guard_projection_audit_baselines_update"
                )
                conn.execute(
                    "CREATE TRIGGER guard_projection_audit_baselines_update "
                    "BEFORE UPDATE ON projection_audit_baselines "
                    "BEGIN SELECT 1; END"
                )
                conn.commit()
                conn.execute("BEGIN")
                altered_baseline_seal = store.current_state_seal(conn)
                conn.rollback()
                altered_baseline_replay = verify_patch_journal(store)
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "DROP TRIGGER guard_projection_audit_baselines_update"
                )
                store._ensure_projection_baseline_guards(conn)
                conn.commit()
            self.assertEqual(source_count, entry_count)
            self.assertEqual(len(SCHEDULER_HISTORY_GUARD_NAMES), guard_count)
            self.assertEqual(list(range(1, 22)), versions)
            self.assertIsNotNone(projection_baseline)
            self.assertNotEqual(
                projection_baseline["prior_state_hash"],
                projection_baseline["baseline_state_hash"],
            )
            self.assertFalse(altered_baseline_seal["valid"])
            self.assertTrue(
                any(
                    "projection-audit-baseline guard" in error
                    for error in altered_baseline_seal["errors"]
                ),
                altered_baseline_seal,
            )
            self.assertFalse(altered_baseline_replay["valid"])
            self.assertTrue(
                any(
                    "projection-audit-baseline guard" in error
                    for error in altered_baseline_replay["errors"]
                ),
                altered_baseline_replay,
            )
            replay = verify_patch_journal(store)
            self.assertTrue(replay["valid"], replay["errors"])
            self.assertEqual(
                int(projection_baseline["baseline_revision"]),
                replay["journal_start_revision"],
            )
            post_baseline = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "researcher",
                    "target_id": "post-baseline-lemma",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "post-baseline-lemma",
                            "kind": "lemma",
                            "statement": "A lemma added after projection migration.",
                            "parent_ids": ["root"],
                            "root_impact": 0.5,
                            "reduction_depth": 1,
                        }
                    ],
                    "rationale": "exercise the replayable post-baseline suffix",
                },
            )
            self.assertTrue(post_baseline.accepted, post_baseline.errors)
            suffix_replay = verify_patch_journal(store)
            self.assertTrue(suffix_replay["valid"], suffix_replay["errors"])
            self.assertEqual(1, suffix_replay["verified_patch_count"])
            self.assertEqual(1, suffix_replay["forward_verified_patch_count"])

    def test_v15_migration_rejects_tampered_v14_scheduler_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v14-provenance-tamper",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            self._record_failed_scheduler_lifecycle(
                store,
                run_id="v14-tamper-run",
            )
            with store.connect() as conn:
                legacy_hash = _legacy_v14_run_provenance_hash(conn)
                _restore_v14_proof_projection_seal(store, conn)
                store._drop_scheduler_history_guards(conn)
                conn.execute("DROP TABLE scheduler_provenance_entries")
                conn.execute("DELETE FROM schema_migrations WHERE version >= 15")
                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ?",
                    (legacy_hash,),
                )
                conn.execute(
                    "UPDATE scheduler_dispatch_results SET result_hash = ?",
                    ("0" * 64,),
                )
                conn.commit()

            with self.assertRaisesRegex(
                RuntimeError,
                "differs from its v14 current-state seal",
            ):
                store.connect()

    def test_v15_migration_rejects_tampered_v14_proof_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v14-proof-projection-tamper",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            created = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "lemma",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "lemma",
                            "kind": "lemma",
                            "statement": "A valid intermediate lemma.",
                            "parent_ids": ["root"],
                            "root_impact": 0.5,
                            "reduction_depth": 1,
                        }
                    ],
                    "rationale": "create a v14 proof projection fixture",
                },
            )
            self.assertTrue(created.accepted, created.errors)
            with store.connect() as conn:
                _restore_v14_proof_projection_seal(store, conn)
                conn.execute("DELETE FROM schema_migrations WHERE version >= 15")
                conn.execute(
                    "UPDATE claims SET statement = ? WHERE claim_id = 'lemma'",
                    ("A different intermediate lemma.",),
                )
                conn.commit()

            with self.assertRaisesRegex(
                RuntimeError,
                "v14 patch history fails authenticated chain validation",
            ):
                store.connect()

    def test_v15_migration_rejects_tampered_interior_v14_patch_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v14-interior-patch-tamper",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            patch_ids: list[str] = []
            for index in range(2):
                outcome = apply_operator_patch(
                    store,
                    {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": store.get_revision(),
                        "actor_role": "researcher",
                        "target_id": f"lemma-{index}",
                        "operations": [
                            {
                                "op": "add_claim",
                                "claim_id": f"lemma-{index}",
                                "kind": "lemma",
                                "statement": f"Valid intermediate lemma {index}.",
                                "parent_ids": ["root"],
                                "root_impact": 0.5,
                                "reduction_depth": 1,
                            }
                        ],
                        "rationale": f"create legacy patch {index}",
                    },
                )
                self.assertTrue(outcome.accepted, outcome.errors)
                patch_ids.append(outcome.patch_id)

            # Control history makes v15 establish a projection baseline at the
            # current revision. Without a pre-baseline chain audit, an edited
            # interior v14 entry would be hidden behind that baseline.
            self._record_failed_scheduler_lifecycle(
                store,
                run_id="v14-interior-history-run",
            )
            with store.connect() as conn:
                store._drop_patch_history_guards(conn)
                store._drop_scheduler_history_guards(conn)
                _restore_v14_proof_projection_seal(store, conn)
                conn.execute("DELETE FROM schema_migrations WHERE version >= 15")
                conn.execute(
                    "UPDATE patches SET rationale = ? WHERE patch_id = ?",
                    ("tampered interior rationale", patch_ids[0]),
                )
                conn.commit()

            with self.assertRaisesRegex(
                RuntimeError,
                "v14 patch history fails authenticated chain validation",
            ):
                store.connect()

    def test_v15_guards_and_full_audit_detect_history_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v15-provenance-guards",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            self._record_failed_scheduler_lifecycle(
                store,
                run_id="v15-guarded-run",
            )
            with store.connect() as conn:
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError,
                    "scheduler history is append-only",
                ):
                    conn.execute(
                        "UPDATE scheduler_dispatch_results SET result_hash = ?",
                        ("0" * 64,),
                    )
                conn.rollback()

                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DROP TRIGGER guard_runs_update")
                conn.execute(
                    "CREATE TRIGGER guard_runs_update BEFORE UPDATE ON runs "
                    "BEGIN SELECT 1; END"
                )
                conn.commit()
                altered_guard_errors = scheduler_provenance_errors(conn)
                altered_guard_invariants = validate_conn(conn)
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DROP TRIGGER guard_runs_update")
                store._ensure_scheduler_history_guards(conn)
                conn.commit()

                # Simulate a privileged database actor dropping and restoring
                # schema guards. Online checks trust the restored guards;
                # explicit audit independently recomputes every commitment.
                conn.execute("BEGIN IMMEDIATE")
                store._drop_scheduler_history_guards(conn)
                conn.execute(
                    "UPDATE scheduler_dispatch_results SET result_hash = ?",
                    ("0" * 64,),
                )
                store._ensure_scheduler_history_guards(conn)
                conn.commit()
                provenance_errors = scheduler_provenance_errors(conn)
                invariant_errors = validate_conn(conn)
                conn.execute("BEGIN")
                self.assertTrue(store.current_state_seal(conn)["valid"])
                conn.rollback()
            self.assertTrue(
                any("guard_runs_update" in error for error in altered_guard_errors),
                altered_guard_errors,
            )
            self.assertTrue(
                any("guard_runs_update" in error for error in altered_guard_invariants),
                altered_guard_invariants,
            )
            self.assertTrue(
                any("provenance entry" in error for error in provenance_errors),
                provenance_errors,
            )
            self.assertTrue(
                any("scheduler provenance entry" in error for error in invariant_errors),
                invariant_errors,
            )

    def test_v16_patch_journal_is_append_only_and_guards_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v16-patch-guards",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            outcome = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "lemma",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "lemma",
                            "kind": "lemma",
                            "statement": "A valid intermediate lemma.",
                            "parent_ids": ["root"],
                            "root_impact": 0.5,
                            "reduction_depth": 1,
                        }
                    ],
                    "rationale": "create an authenticated patch row",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with store.connect() as conn:
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError,
                    "patch history is append-only",
                ):
                    conn.execute(
                        "UPDATE patches SET rationale = ? WHERE patch_id = ?",
                        ("rewritten", outcome.patch_id),
                    )
                conn.rollback()
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError,
                    "patch history is append-only",
                ):
                    conn.execute(
                        "DELETE FROM patches WHERE patch_id = ?",
                        (outcome.patch_id,),
                    )
                conn.rollback()

                source = conn.execute(
                    "SELECT * FROM patches WHERE patch_id = ?",
                    (outcome.patch_id,),
                ).fetchone()
                columns = tuple(source.keys())
                forged = dict(source)
                forged["patch_id"] = "forged-duplicate-revision"
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError,
                    "patch history insertion is invalid",
                ):
                    conn.execute(
                        f"INSERT INTO patches({', '.join(columns)}) VALUES ("
                        + ", ".join("?" for _ in columns)
                        + ")",
                        tuple(forged[column] for column in columns),
                    )
                conn.rollback()

                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DROP TRIGGER guard_patches_update")
                conn.execute(
                    "CREATE TRIGGER guard_patches_update BEFORE UPDATE ON patches "
                    "BEGIN SELECT 1; END"
                )
                conn.commit()
                conn.execute("BEGIN")
                altered_seal = store.current_state_seal(conn)
                conn.rollback()
                altered_replay = verify_patch_journal(store)
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DROP TRIGGER guard_patches_update")
                store._ensure_patch_history_guards(conn)
                conn.commit()
            self.assertFalse(altered_seal["valid"])
            self.assertTrue(
                any("guard_patches_update" in error for error in altered_seal["errors"]),
                altered_seal,
            )
            self.assertFalse(altered_replay["valid"])
            self.assertTrue(
                any(
                    "guard_patches_update" in error
                    for error in altered_replay["errors"]
                ),
                altered_replay,
            )
            self.assertTrue(store.current_state_seal()["valid"])
            self.assertTrue(verify_patch_journal(store)["valid"])

    def test_v16_migration_rejects_a_tampered_v15_patch_journal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v15-patch-tamper",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            outcome = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "lemma",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "lemma",
                            "kind": "lemma",
                            "statement": "A valid intermediate lemma.",
                            "parent_ids": ["root"],
                            "root_impact": 0.5,
                            "reduction_depth": 1,
                        }
                    ],
                    "rationale": "create the v15 replay fixture",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with store.connect() as conn:
                store._drop_patch_history_guards(conn)
                conn.execute("DELETE FROM schema_migrations WHERE version >= 16")
                conn.execute(
                    "UPDATE patches SET rationale = ? WHERE patch_id = ?",
                    ("tampered after v15", outcome.patch_id),
                )
                conn.commit()

            with self.assertRaisesRegex(
                RuntimeError,
                "v15 patch journal fails full replay",
            ):
                store.connect()

    def test_v19_compact_scheduler_history_replaces_online_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v17-source-sequence",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            self._record_failed_scheduler_lifecycle(
                store,
                run_id="v17-sequenced-run",
            )
            citation_run = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "record_run_metrics",
                            "run_id": "v19-citation-run",
                            "actor_role": "researcher",
                            "mode": "retrieve",
                            "target_id": "root",
                            "search_intent": "citation_pass",
                            "selection_design": "observational",
                            "status": "completed",
                        }
                    ],
                    "rationale": "exercise registered retrieval statistics",
                },
            )
            self.assertTrue(citation_run.accepted, citation_run.errors)
            with store.connect() as conn:
                source_rows = [
                    tuple(row)
                    for row in conn.execute(
                        "SELECT sequence, record_kind, record_id "
                        "FROM scheduler_source_entries ORDER BY sequence"
                    ).fetchall()
                ]
                provenance_rows = [
                    tuple(row)
                    for row in conn.execute(
                        "SELECT sequence, record_kind, record_id "
                        "FROM scheduler_provenance_entries ORDER BY sequence"
                    ).fetchall()
                ]
                summary = scheduler_provenance_summary(conn)
                self.assertEqual(source_rows, provenance_rows)
                self.assertNotIn("record_counts", summary)
                self.assertEqual(len(source_rows), summary["source_entry_count"])
                self.assertEqual(len(provenance_rows), summary["entry_count"])
                statistics = {
                    (str(row["statistic_kind"]), str(row["statistic_key"])): int(
                        row["value"]
                    )
                    for row in conn.execute(
                        "SELECT statistic_kind, statistic_key, value "
                        "FROM scheduler_statistics"
                    ).fetchall()
                }
                self.assertEqual(2, statistics[("total_run", "")])
                self.assertEqual(2, statistics[("outcome_run", "")])
                self.assertEqual(2, statistics[("retrieve_total", "")])
                self.assertEqual(
                    1,
                    statistics[("retrieve_intent", "citation_pass")],
                )

                conn.execute(
                    "UPDATE scheduler_statistics SET value = value + 1 "
                    "WHERE statistic_kind = 'total_run' AND statistic_key = ''"
                )
                statistic_seal = store.current_state_seal(conn)
                self.assertFalse(statistic_seal["valid"], statistic_seal)
                self.assertTrue(
                    any(
                        "run-selection provenance" in error
                        for error in statistic_seal["errors"]
                    ),
                    statistic_seal,
                )
                conn.rollback()

                with self.assertRaisesRegex(
                    sqlite3.IntegrityError,
                    "no matching source insertion",
                ):
                    conn.execute(
                        "INSERT INTO scheduler_provenance_entries("
                        "sequence, record_kind, record_id, payload_hash, "
                        "previous_hash, entry_hash) VALUES (?, 'run', ?, ?, ?, ?)",
                        (
                            len(provenance_rows) + 1,
                            "unmatched-run",
                            "0" * 64,
                            "0" * 64,
                            "0" * 64,
                        ),
                    )
                conn.rollback()

                source = conn.execute(
                    "SELECT * FROM runs WHERE run_id = ?",
                    ("v17-sequenced-run",),
                ).fetchone()
                columns = tuple(source.keys())
                uncommitted = dict(source)
                uncommitted["run_id"] = "raw-uncommitted-run"
                uncommitted["scheduler_dispatch_id"] = None
                conn.execute(
                    f"INSERT INTO runs({', '.join(columns)}) VALUES ("
                    + ", ".join("?" for _ in columns)
                    + ")",
                    tuple(uncommitted[column] for column in columns),
                )
                seal = store.current_state_seal(conn)
                self.assertFalse(seal["valid"], seal)
                self.assertTrue(
                    any("run-selection provenance" in error for error in seal["errors"]),
                    seal,
                )
                conn.rollback()

                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DROP TRIGGER capture_runs_scheduler_source_insert")
                conn.execute(
                    "CREATE TRIGGER capture_runs_scheduler_source_insert "
                    "AFTER INSERT ON runs BEGIN SELECT 1; END"
                )
                conn.commit()
                altered_errors = scheduler_provenance_errors(conn)
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DROP TRIGGER capture_runs_scheduler_source_insert")
                store._ensure_scheduler_history_guards(conn)
                conn.commit()
            self.assertTrue(
                any(
                    "capture_runs_scheduler_source_insert" in error
                    for error in altered_errors
                ),
                altered_errors,
            )
            with store.connect() as conn:
                self.assertEqual([], scheduler_provenance_errors(conn))
                conn.execute("BEGIN")
                self.assertTrue(store.current_state_seal(conn)["valid"])

    def test_v10_migration_rejects_tampered_v9_run_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "v9-run-provenance-migration",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            outcome = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "record_run_metrics",
                            "run_id": "v9-sealed-run",
                            "actor_role": "researcher",
                            "mode": "prove",
                            "target_id": "root",
                            "selection_design": "observational",
                            "status": "completed",
                        }
                    ],
                    "rationale": "create v9 migration provenance",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with store.connect() as conn:
                store._drop_scheduler_history_guards(conn)
                legacy_v9_hash = _legacy_v9_run_provenance_hash(conn)
                _restore_v14_proof_projection_seal(store, conn)
                conn.execute("DROP TABLE scheduler_candidate_deferrals")
                conn.execute("DROP TABLE scheduler_fairness_meta")
                conn.execute("DROP TABLE scheduler_decision_deferrals")
                conn.execute("DROP TABLE scheduler_decision_fairness_meta")
                conn.execute("DELETE FROM schema_migrations WHERE version >= 10")
                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ?",
                    (legacy_v9_hash,),
                )
                conn.execute(
                    "UPDATE runs SET decision_trace_json = ? "
                    "WHERE run_id = 'v9-sealed-run'",
                    ('{"tampered": true}',),
                )
                conn.commit()

            with self.assertRaisesRegex(
                RuntimeError, "differs from its v9 current-state seal"
            ):
                store.connect()

    def test_legacy_certification_is_demoted_with_atomic_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "legacy-migration-safety", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            attached = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "legacy-report",
                            "artifact_type": "research_notebook",
                            "content": "Legacy evidence.",
                        }
                    ],
                    "rationale": "migration fixture",
                },
            )
            self.assertTrue(attached.accepted, attached.errors)

            # Simulate the data semantics and migration registry of a v1 store.
            # Use sqlite3 directly so merely opening the fixture does not run
            # the migration before the legacy rows are in place.
            with closing(sqlite3.connect(store.db_path)) as conn, conn:
                conn.execute(
                    "UPDATE claims SET validation_status='informally_verified', "
                    "lifecycle_status='integrated' WHERE claim_id='root'"
                )
                conn.execute(
                    "UPDATE artifacts SET metadata_json='{}' WHERE artifact_id='legacy-report'"
                )
                conn.execute("DELETE FROM schema_migrations WHERE version >= 2")
                conn.execute("UPDATE problem_state SET schema_version=1")
                conn.commit()

            with store.connect() as conn:
                root = conn.execute(
                    "SELECT validation_status, lifecycle_status FROM claims WHERE claim_id='root'"
                ).fetchone()
                artifact = conn.execute(
                    "SELECT metadata_json FROM artifacts WHERE artifact_id='legacy-report'"
                ).fetchone()
                versions = [
                    int(row["version"])
                    for row in conn.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    ).fetchall()
                ]
                migration_event = conn.execute(
                    "SELECT payload_json FROM events WHERE event_type='schema_migrated' "
                    "ORDER BY event_id DESC LIMIT 1"
                ).fetchone()
            self.assertEqual("challenged", root["validation_status"])
            self.assertEqual("active", root["lifecycle_status"])
            artifact_metadata = json.loads(artifact["metadata_json"])
            self.assertTrue(artifact_metadata["legacy_revision_semantics"])
            self.assertEqual(list(range(1, 22)), versions)
            self.assertIsNotNone(migration_event)
            backup_path = Path(json.loads(migration_event["payload_json"])["backup_path"])
            self.assertTrue(backup_path.is_file())
            with closing(sqlite3.connect(backup_path)) as backup, backup:
                old_root = backup.execute(
                    "SELECT validation_status, lifecycle_status FROM claims WHERE claim_id='root'"
                ).fetchone()
            self.assertEqual(("informally_verified", "integrated"), old_root)

            # Migration does not invent v3 deltas for the old semantic
            # transition. Instead, it establishes a new replay baseline whose
            # prior-history label and immutable backup remain explicit.
            replay = verify_patch_journal(store)
            self.assertTrue(replay["valid"], replay)
            self.assertEqual(1, replay["journal_start_revision"])
            self.assertEqual(0, replay["patch_count"])
            self.assertEqual(1, replay["legacy_patch_count"])
            self.assertEqual(
                "legacy_pre_v3_nonreplayable_before_signed_migration_baseline",
                replay["prior_history_status"],
            )
            if shutil.which("openssl"):
                private_key = Path(tmpdir) / "migration-private.pem"
                public_key = Path(tmpdir) / "migration-public.pem"
                subprocess.run(
                    [
                        shutil.which("openssl") or "openssl",
                        "genpkey",
                        "-algorithm",
                        "ED25519",
                        "-out",
                        str(private_key),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                subprocess.run(
                    [
                        shutil.which("openssl") or "openssl",
                        "pkey",
                        "-in",
                        str(private_key),
                        "-pubout",
                        "-out",
                        str(public_key),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                checkpoint_path = Path(tmpdir) / "migration-checkpoint.json"
                checkpoint = create_signed_audit_checkpoint(
                    store,
                    output_path=checkpoint_path,
                    private_key_path=private_key,
                )
                self.assertEqual(
                    replay["prior_history_status"],
                    checkpoint["payload"]["prior_history_status"],
                )
                self.assertEqual(1, checkpoint["payload"]["journal_start_revision"])
                verified = verify_signed_audit_checkpoint(
                    store,
                    checkpoint_path=checkpoint_path,
                    public_key_path=public_key,
                )
                self.assertTrue(verified["valid"], verified)

                real_backup = backup_path.with_suffix(".real.sqlite3")
                backup_path.rename(real_backup)
                backup_path.symlink_to(real_backup)
                symlinked = verify_patch_journal(store)
                self.assertFalse(symlinked["valid"])
                self.assertIn("non-symlink", " ".join(symlinked["errors"]))
                backup_path.unlink()
                real_backup.rename(backup_path)

                backup_path.write_bytes(backup_path.read_bytes() + b"tamper")
                tampered = verify_signed_audit_checkpoint(
                    store,
                    checkpoint_path=checkpoint_path,
                    public_key_path=public_key,
                )
                self.assertFalse(tampered["valid"])
                self.assertIn("backup SHA-256", " ".join(tampered["errors"]))

    def test_failed_migration_rolls_back_and_retains_backup(self) -> None:
        class FailingMigrationStore(ProofStateStore):
            def _migrate_in_transaction(
                self,
                conn: sqlite3.Connection,
                **_kwargs,
            ) -> None:
                conn.execute(
                    "UPDATE problem_state SET status='migration-should-rollback' "
                    "WHERE problem_id=?",
                    (self.problem_id,),
                )
                raise RuntimeError("injected migration failure")

        with tempfile.TemporaryDirectory() as tmpdir:
            generation_root = Path(tmpdir) / "generation"
            store = ProofStateStore(
                "migration-rollback", generation_root=generation_root
            )
            store.init_problem("The root theorem holds.")
            with closing(sqlite3.connect(store.db_path)) as conn, conn:
                conn.execute("DELETE FROM schema_migrations WHERE version >= 2")
                conn.execute("UPDATE problem_state SET schema_version=1, status='active'")
                conn.commit()

            failing = FailingMigrationStore(
                "migration-rollback", generation_root=generation_root
            )
            with self.assertRaisesRegex(RuntimeError, "injected migration failure"):
                failing.connect()
            with closing(sqlite3.connect(store.db_path)) as conn, conn:
                row = conn.execute(
                    "SELECT schema_version, status FROM problem_state WHERE problem_id=?",
                    (store.problem_id,),
                ).fetchone()
            self.assertEqual((1, "active"), row)
            backups = list((store.state_dir / "migration_backups").glob("*.sqlite3"))
            self.assertEqual(1, len(backups))

    def test_operator_input_ingestions_are_journaled_and_replayable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audit_document = root / "audit.md"
            audit_document.write_text("# A theorem\n\nProof. The argument is submitted.\n", encoding="utf-8")
            audit_store = ProofStateStore(
                "journal-audit-ingest", generation_root=root / "audit-generation"
            )
            ingest_paper_audit(audit_store, audit_document)
            audit_replay = verify_patch_journal(audit_store)
            self.assertTrue(audit_replay["valid"], audit_replay)

            revision_document = root / "revision.md"
            revision_document.write_text("# Draft\n\nA mathematical manuscript.\n", encoding="utf-8")
            revision_store = ProofStateStore(
                "journal-revision-ingest", generation_root=root / "revision-generation"
            )
            ingest_writing_revision(revision_store, revision_document)
            revision_replay = verify_patch_journal(revision_store)
            self.assertTrue(revision_replay["valid"], revision_replay)

            reference_document = root / "reference.tex"
            reference_document.write_text(
                "\\section{Reference argument}\nThe supplied argument is advisory.\n",
                encoding="utf-8",
            )
            reference_store = ProofStateStore(
                "journal-reference-ingest", generation_root=root / "reference-generation"
            )
            reference_store.init_problem("Prove the theorem independently.")
            ingest_reference_solution(reference_store, reference_document)
            reference_replay = verify_patch_journal(reference_store)
            self.assertTrue(reference_replay["valid"], reference_replay)

    def test_hard_stop_artifact_is_journaled_and_replayable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "journal-hard-stop", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            result = store.request_stop(hard=True, reason="replay test", source="test")
            self.assertTrue(result.get("interruption_artifact_id"))
            replay = verify_patch_journal(store)
            self.assertTrue(replay["valid"], replay)


class TypedRelationTests(unittest.TestCase):
    def test_fk_backed_relations_mirror_legacy_json_and_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "typed-relations", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")
            outcome = apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "lemma-typed",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "typed-note",
                            "artifact_type": "research_notebook",
                            "content": "A bounded derivation of the auxiliary lemma.",
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "lemma-typed",
                            "kind": "lemma",
                            "statement": "The auxiliary lemma holds.",
                            "parent_ids": ["root"],
                            "evidence_artifact_ids": ["typed-note"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-typed",
                            "conclusion_claim_id": "lemma-typed",
                            "label": "Direct auxiliary argument",
                            "strategy": "Use the derivation in the attached notebook.",
                            "evidence_artifact_ids": ["typed-note"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inference-typed",
                            "route_id": "route-typed",
                            "conclusion_claim_id": "lemma-typed",
                            "premise_claim_ids": [],
                            "condition_claim_ids": ["root"],
                            "explanation": "The root hypotheses imply the auxiliary statement.",
                            "evidence_artifact_ids": ["typed-note"],
                        },
                        {
                            "op": "add_proof_obligation",
                            "proof_obligation_id": "obligation-typed",
                            "owner_type": "claim",
                            "owner_id": "lemma-typed",
                            "obligation": "Check the last implication independently.",
                            "obligation_type": "gap",
                            "severity": "major",
                            "source_artifact_ids": ["typed-note"],
                        },
                    ],
                    "rationale": "exercise every typed graph relation",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with store.connect() as conn:
                canonical = conn.execute(
                    "SELECT proof_obligation_id, obligation_type FROM proof_obligations "
                    "WHERE proof_obligation_id = 'obligation-typed'"
                ).fetchone()
                self.assertEqual(canonical["proof_obligation_id"], "obligation-typed")
                self.assertEqual(canonical["obligation_type"], "gap")
                with self.assertRaises(sqlite3.OperationalError):
                    conn.execute(
                        "UPDATE proof_obligations SET status='resolved' "
                        "WHERE proof_obligation_id='obligation-typed'"
                    )
                self.assertEqual(
                    conn.execute(
                        "SELECT parent_claim_id FROM claim_parent_relations "
                        "WHERE claim_id = 'lemma-typed'"
                    ).fetchone()[0],
                    "root",
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT condition_claim_id FROM inference_condition_claims "
                        "WHERE inference_id = 'inference-typed'"
                    ).fetchone()[0],
                    "root",
                )
                owner = conn.execute(
                    "SELECT owner_claim_id, owner_route_id FROM proof_obligation_owners "
                    "WHERE proof_obligation_id = 'obligation-typed'"
                ).fetchone()
                self.assertEqual(owner["owner_claim_id"], "lemma-typed")
                self.assertIsNone(owner["owner_route_id"])
                self.assertEqual(validate_conn(conn), [])
                conn.execute(
                    "DELETE FROM claim_parent_relations WHERE claim_id = 'lemma-typed'"
                )
                conn.commit()
            with store.connect() as conn:
                errors = validate_conn(conn)
            self.assertTrue(
                any("claim_parent_relations disagrees" in error for error in errors),
                errors,
            )


class AssignmentProvenanceTests(unittest.TestCase):
    def test_v21_migration_repairs_randomized_assignment_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "randomized-index-migration",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            with closing(sqlite3.connect(store.db_path)) as conn, conn:
                conn.execute(
                    "DROP INDEX "
                    + store_module.RANDOMIZED_ASSIGNMENT_UNIT_INDEX
                )
                conn.execute(
                    "CREATE UNIQUE INDEX "
                    + store_module.RANDOMIZED_ASSIGNMENT_UNIT_INDEX
                    + " ON scheduler_dispatches(dispatch_id)"
                )
                conn.execute(
                    "DROP INDEX "
                    + store_module.SCHEDULER_SOURCE_KIND_SEQUENCE_INDEX
                )
                conn.execute(
                    "CREATE INDEX "
                    + store_module.SCHEDULER_SOURCE_KIND_SEQUENCE_INDEX
                    + " ON scheduler_source_entries(sequence)"
                )
                conn.execute(
                    "DELETE FROM schema_migrations WHERE version IN (20, 21)"
                )
                conn.commit()

            with store.connect() as conn:
                versions = [
                    int(row["version"])
                    for row in conn.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    ).fetchall()
                ]
                self.assertEqual(list(range(1, 22)), versions)
                self.assertEqual(
                    [], store_module.randomized_assignment_index_errors(conn)
                )
                self.assertEqual(
                    [], store_module.scheduler_dispatch_tail_index_errors(conn)
                )
                conn.execute("BEGIN")
                self.assertTrue(store.current_state_seal(conn)["valid"])

    def test_run_telemetry_cannot_assert_incomplete_randomization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "assignment-provenance", generation_root=Path(tmpdir) / "generation"
            )
            store.init_problem("The root theorem holds.")

            rejected = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "record_run_metrics",
                            "run_id": "invalid-randomized-run",
                            "actor_role": "researcher",
                            "mode": "prove",
                            "target_id": "root",
                            "selection_design": "randomized",
                            "assignment_probability": 0.5,
                            "status": "completed",
                        }
                    ],
                    "rationale": "exercise the randomized-assignment guard",
                },
            )
            self.assertFalse(rejected.accepted)
            self.assertIn("candidate-set hash", " ".join(rejected.errors))

            forged = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "record_run_metrics",
                            "run_id": "forged-randomized-run",
                            "actor_role": "researcher",
                            "mode": "prove",
                            "target_id": "root",
                            "selection_design": "randomized",
                            "assignment_probability": 0.5,
                            "exploration_stratum": "root-proof-near-tie-v1",
                            "candidate_set_hash": "a" * 64,
                            "selection_policy_version": 1,
                            "status": "completed",
                        }
                    ],
                    "rationale": "record complete assignment provenance",
                },
            )
            self.assertFalse(forged.accepted)
            self.assertIn("decision trace", " ".join(forged.errors))

            action = next_action(store)
            trace = action["decision_trace"]
            policy_version = int(trace["decision_policy_version"])
            arms = [
                randomized_policy_arm("control-policy", policy_version - 1),
                randomized_policy_arm("treatment-policy", policy_version),
            ]
            assignment = None
            for unit_index in range(100):
                candidate_assignment = randomized_arm_assignment(
                    experiment_id="scheduler-policy-calibration-v1",
                    preregistration_sha256="b" * 64,
                    registration_receipt_sha256="c" * 64,
                    assignment_unit_id=f"root-proof-{unit_index}",
                    exploration_stratum="root-proof-near-tie-v1",
                    entropy_source="public-beacon-round-1",
                    entropy_sha256="d" * 64,
                    arms=arms,
                )
                if candidate_assignment["selected_policy_version"] == policy_version:
                    assignment = candidate_assignment
                    break
            self.assertIsNotNone(assignment)
            certificate = bind_randomized_assignment(
                assignment,
                candidate_set_sha256=trace["candidate_set_sha256"],
                dispatched_action_sha256=trace["dispatched_action_sha256"],
            )
            action["decision_trace"] = {
                **trace,
                "randomized_assignment": certificate,
            }
            accepted = _record_dispatched_test_wave(
                store,
                [action],
                ["valid-randomized-run"],
            )
            self.assertTrue(accepted.accepted, accepted.errors)
            with store.connect() as conn:
                row = conn.execute(
                    "SELECT selection_design, assignment_probability, exploration_stratum, "
                    "candidate_set_hash, scheduler_dispatch_id "
                    "FROM runs WHERE run_id = 'valid-randomized-run'"
                ).fetchone()
            self.assertEqual(row["selection_design"], "randomized")
            self.assertEqual(float(row["assignment_probability"]), 0.5)
            self.assertEqual(row["exploration_stratum"], "root-proof-near-tie-v1")
            self.assertEqual(
                row["candidate_set_hash"], trace["candidate_set_sha256"]
            )
            self.assertTrue(row["scheduler_dispatch_id"])
            with store.connect() as conn:
                self.assertEqual(validate_conn(conn), [])
                query_plan = [
                    str(plan_row[3])
                    for plan_row in conn.execute(
                        "EXPLAIN QUERY PLAN SELECT dispatch_group_id "
                        "FROM scheduler_dispatches "
                        "WHERE selection_design = 'randomized' "
                        "AND dispatch_position = 0 "
                        "AND json_extract(decision_trace_json, "
                        "'$.randomized_assignment.experiment_id') = ? "
                        "AND json_extract(decision_trace_json, "
                        "'$.randomized_assignment.assignment_unit_id') = ? "
                        "LIMIT 1",
                        (
                            certificate["experiment_id"],
                            certificate["assignment_unit_id"],
                        ),
                    ).fetchall()
                ]
                self.assertTrue(
                    any(
                        store_module.RANDOMIZED_ASSIGNMENT_UNIT_INDEX in detail
                        for detail in query_plan
                    ),
                    query_plan,
                )
                design_query_plan = [
                    str(plan_row[3])
                    for plan_row in conn.execute(
                        "EXPLAIN QUERY PLAN SELECT decision_trace_json "
                        "FROM scheduler_dispatches "
                        "WHERE selection_design = 'randomized' "
                        "AND dispatch_position = 0 "
                        "AND json_extract(decision_trace_json, "
                        "'$.randomized_assignment.experiment_id') = ? LIMIT 1",
                        (certificate["experiment_id"],),
                    ).fetchall()
                ]
                self.assertTrue(
                    any(
                        store_module.RANDOMIZED_ASSIGNMENT_UNIT_INDEX in detail
                        for detail in design_query_plan
                    ),
                    design_query_plan,
                )
                tail_query_plan = [
                    str(plan_row[3])
                    for plan_row in conn.execute(
                        "EXPLAIN QUERY PLAN SELECT d.dispatch_group_id "
                        "FROM scheduler_source_entries AS s "
                        "JOIN scheduler_dispatches AS d "
                        "ON d.dispatch_id = s.record_id "
                        "WHERE s.record_kind = 'dispatch' "
                        "ORDER BY s.sequence DESC LIMIT 1"
                    ).fetchall()
                ]
                self.assertTrue(
                    any(
                        store_module.SCHEDULER_SOURCE_KIND_SEQUENCE_INDEX
                        in detail
                        for detail in tail_query_plan
                    ),
                    tail_query_plan,
                )
                conn.execute("BEGIN")
                conn.execute(
                    "DROP INDEX "
                    + store_module.RANDOMIZED_ASSIGNMENT_UNIT_INDEX
                )
                missing_index_errors = validate_conn(conn)
                conn.rollback()
                self.assertTrue(
                    any(
                        "randomized-assignment uniqueness index" in error
                        for error in missing_index_errors
                    ),
                    missing_index_errors,
                )
                conn.execute("BEGIN")
                conn.execute(
                    "DROP INDEX "
                    + store_module.SCHEDULER_SOURCE_KIND_SEQUENCE_INDEX
                )
                missing_tail_index_errors = validate_conn(conn)
                conn.rollback()
                self.assertTrue(
                    any(
                        "scheduler dispatch-tail index" in error
                        for error in missing_tail_index_errors
                    ),
                    missing_tail_index_errors,
                )
                conn.execute("BEGIN")
                store._drop_patch_history_guards(conn)
                conn.execute(
                    "DELETE FROM patches WHERE patch_id = ?", (accepted.patch_id,)
                )
                orphan_errors = validate_conn(conn)
                conn.rollback()
            self.assertTrue(
                any(
                    "has no hash-chained record_run_metrics operation" in error
                    for error in orphan_errors
                ),
                orphan_errors,
            )
            duplicate_action = next_action(store)
            duplicate_trace = duplicate_action["decision_trace"]
            duplicate_action["decision_trace"] = {
                **duplicate_trace,
                "randomized_assignment": bind_randomized_assignment(
                    assignment,
                    candidate_set_sha256=duplicate_trace[
                        "candidate_set_sha256"
                    ],
                    dispatched_action_sha256=duplicate_trace[
                        "dispatched_action_sha256"
                    ],
                ),
            }
            with self.assertRaisesRegex(RuntimeError, "duplicated"):
                _record_scheduler_dispatches(
                    store,
                    [duplicate_action],
                    store.audit_chain_heads(),
                    execution_contract={
                        "version": 1,
                        "driver": "custom",
                        "identity": "test:duplicate-randomized-unit",
                        "recovery_capability": "none",
                    },
                )
            changed_design_assignment = None
            for unit_index in range(100):
                candidate_assignment = randomized_arm_assignment(
                    experiment_id="scheduler-policy-calibration-v1",
                    preregistration_sha256="b" * 64,
                    registration_receipt_sha256="c" * 64,
                    assignment_unit_id=f"changed-design-{unit_index}",
                    exploration_stratum="root-proof-near-tie-v1",
                    entropy_source="public-beacon-round-1",
                    entropy_sha256="e" * 64,
                    arms=arms,
                )
                if (
                    candidate_assignment["selected_policy_version"]
                    == policy_version
                ):
                    changed_design_assignment = candidate_assignment
                    break
            self.assertIsNotNone(changed_design_assignment)
            changed_design_action = next_action(store)
            changed_design_trace = changed_design_action["decision_trace"]
            changed_design_action["decision_trace"] = {
                **changed_design_trace,
                "randomized_assignment": bind_randomized_assignment(
                    changed_design_assignment,
                    candidate_set_sha256=changed_design_trace[
                        "candidate_set_sha256"
                    ],
                    dispatched_action_sha256=changed_design_trace[
                        "dispatched_action_sha256"
                    ],
                ),
            }
            with self.assertRaisesRegex(RuntimeError, "design changes"):
                _record_scheduler_dispatches(
                    store,
                    [changed_design_action],
                    store.audit_chain_heads(),
                    execution_contract={
                        "version": 1,
                        "driver": "custom",
                        "identity": "test:changed-randomized-design",
                        "recovery_capability": "none",
                    },
                )

    def test_randomized_assignment_replay_rejects_every_bound_field_tamper(self) -> None:
        assignment = randomized_arm_assignment(
            experiment_id="scheduler-policy-calibration-v1",
            preregistration_sha256="1" * 64,
            registration_receipt_sha256="2" * 64,
            assignment_unit_id="problem-17-repeat-2",
            exploration_stratum="open-proof-search",
            entropy_source="public-beacon-round-42",
            entropy_sha256="3" * 64,
            arms=[
                randomized_policy_arm("policy-a", 4),
                randomized_policy_arm("policy-b", 7),
                randomized_policy_arm("policy-c", 8),
            ],
        )
        repeated = randomized_arm_assignment(
            experiment_id="scheduler-policy-calibration-v1",
            preregistration_sha256="1" * 64,
            registration_receipt_sha256="2" * 64,
            assignment_unit_id="problem-17-repeat-2",
            exploration_stratum="open-proof-search",
            entropy_source="public-beacon-round-42",
            entropy_sha256="3" * 64,
            arms=[
                randomized_policy_arm("policy-a", 4),
                randomized_policy_arm("policy-b", 7),
                randomized_policy_arm("policy-c", 8),
            ],
        )
        self.assertEqual(assignment, repeated)
        certificate = bind_randomized_assignment(
            assignment,
            candidate_set_sha256="4" * 64,
            dispatched_action_sha256="5" * 64,
        )
        self.assertEqual(randomized_assignment_errors(certificate), [])
        self.assertTrue(
            randomized_assignment_cohort_errors([certificate, certificate])
        )
        mutations = {
            "assignment_unit_id": "problem-17-repeat-3",
            "accepted_draw_counter": certificate["accepted_draw_counter"] + 1,
            "accepted_draw_sha256": "6" * 64,
            "selected_arm_id": "forged-arm",
            "selected_policy_version": 100,
            "assignment_probability": float("nan"),
            "candidate_set_sha256": "7" * 64,
            "dispatched_action_sha256": "8" * 64,
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                mutated = json.loads(json.dumps(certificate))
                mutated[field] = value
                self.assertTrue(randomized_assignment_errors(mutated))
        strict_type_mutations = {
            "protocol_version": True,
            "accepted_draw_counter": False,
            "selected_policy_version": True,
        }
        for field, value in strict_type_mutations.items():
            with self.subTest(strict_type_field=field):
                mutated = json.loads(json.dumps(certificate))
                mutated[field] = value
                mutated["certificate_sha256"] = hashlib.sha256(
                    json.dumps(
                        {
                            key: item
                            for key, item in mutated.items()
                            if key != "certificate_sha256"
                        },
                        sort_keys=True,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest()
                self.assertTrue(randomized_assignment_errors(mutated))

    def test_workflow_assignment_protocol_tracks_contiguous_exposures(self) -> None:
        assignment = randomized_arm_assignment(
            experiment_id="parallel-admission-workflow-v2",
            preregistration_sha256="1" * 64,
            registration_receipt_sha256="2" * 64,
            assignment_unit_id="held-out-problem-7-repeat-1",
            exploration_stratum="complete-proof-attempt",
            entropy_source="public-beacon-round-200",
            entropy_sha256="3" * 64,
            arms=[
                randomized_policy_arm(
                    "parallel-v8", 8, policy_family="parallel_admission"
                ),
                randomized_policy_arm(
                    "parallel-v9", 9, policy_family="parallel_admission"
                ),
            ],
            assignment_scope="workflow",
        )
        first = bind_randomized_assignment(
            assignment,
            candidate_set_sha256="4" * 64,
            dispatched_action_sha256="5" * 64,
            exposure_index=0,
        )
        second = bind_randomized_assignment(
            assignment,
            candidate_set_sha256="6" * 64,
            dispatched_action_sha256="7" * 64,
            exposure_index=1,
        )
        third = bind_randomized_assignment(
            assignment,
            candidate_set_sha256="8" * 64,
            dispatched_action_sha256="9" * 64,
            exposure_index=2,
        )
        self.assertEqual(randomized_assignment_cohort_errors([first, second]), [])
        self.assertTrue(
            randomized_assignment_cohort_errors([first, first])
        )
        self.assertTrue(
            randomized_assignment_cohort_errors([first, third])
        )

    def test_registered_block_order_assigns_every_condition_without_postselection(self) -> None:
        arms = [
            randomized_policy_arm(
                "parallel-v10", 10, policy_family="parallel_admission"
            ),
            randomized_policy_arm(
                "parallel-v9", 9, policy_family="parallel_admission"
            ),
        ]
        assignments = randomized_block_workflow_assignments(
            experiment_id="parallel-admission-matched-blocks",
            preregistration_sha256="1" * 64,
            registration_receipt_sha256="2" * 64,
            assignment_schedule_sha256="3" * 64,
            randomization_receipt_sha256="4" * 64,
            randomness_source="nist-randomness-beacon",
            randomness_event_id="pulse-42",
            randomness_sha256="5" * 64,
            problem_id="held-out-problem-4",
            problem_sha256="d" * 64,
            repeat_index=2,
            exploration_stratum="complete-proof-attempt",
            assignment_unit_ids={
                "parallel-v9": "problem-4-repeat-2-v9",
                "parallel-v10": "problem-4-repeat-2-v10",
            },
            arms=arms,
        )
        self.assertEqual(len(assignments), 2)
        self.assertEqual(
            {assignment["selected_arm_id"] for assignment in assignments},
            {"parallel-v9", "parallel-v10"},
        )
        self.assertEqual(
            [assignment["execution_order"] for assignment in assignments],
            [0, 1],
        )
        self.assertEqual(
            len({assignment["block_assignment_sha256"] for assignment in assignments}),
            1,
        )
        self.assertEqual(
            len({assignment["assignment_input_sha256"] for assignment in assignments}),
            2,
        )
        self.assertTrue(
            all(
                assignment["random_seed"]
                == randomized_block_seed(
                    randomness_sha256="5" * 64,
                    problem_id="held-out-problem-4",
                    repeat_index=2,
                )
                for assignment in assignments
            )
        )
        with self.assertRaises(ValueError):
            randomized_condition_order(
                ["parallel-v10", "parallel-v9"],
                problem_id="held-out-problem-4",
                repeat_index=2,
                random_seed=1 << 256,
            )
        certificates = [
            bind_randomized_assignment(
                assignment,
                candidate_set_sha256=f"{4 + index:x}" * 64,
                dispatched_action_sha256=f"{6 + index:x}" * 64,
                exposure_index=0,
            )
            for index, assignment in enumerate(assignments)
        ]
        for certificate in certificates:
            self.assertEqual(
                randomized_assignment_errors(
                    certificate,
                    parallel_admission_policy_version=certificate[
                        "selected_policy_version"
                    ],
                ),
                [],
            )
        self.assertEqual(
            randomized_assignment_cohort_errors(certificates), []
        )
        self.assertEqual(
            randomized_block_assignment_cohort_errors(certificates), []
        )
        self.assertTrue(
            randomized_block_assignment_cohort_errors(certificates[:1])
        )
        tampered = json.loads(json.dumps(certificates[0]))
        tampered["execution_order"] = 1
        tampered["certificate_sha256"] = hashlib.sha256(
            json.dumps(
                {
                    key: value
                    for key, value in tampered.items()
                    if key != "certificate_sha256"
                },
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        self.assertTrue(randomized_assignment_errors(tampered))

    def test_registered_block_condition_governs_every_workflow_wave(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "held-out-problem-1",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Prove the registered held-out theorem.")
            problem_sha256 = hashlib.sha256(
                "Prove the registered held-out theorem.".encode("utf-8")
            ).hexdigest()
            assignment = randomized_block_workflow_assignments(
                experiment_id="parallel-admission-matched-runtime",
                preregistration_sha256="a" * 64,
                registration_receipt_sha256="b" * 64,
                assignment_schedule_sha256="c" * 64,
                randomization_receipt_sha256="d" * 64,
                randomness_source="nist-randomness-beacon",
                randomness_event_id="pulse-7",
                randomness_sha256="e" * 64,
                problem_id="held-out-problem-1",
                problem_sha256=problem_sha256,
                repeat_index=1,
                exploration_stratum="complete-proof-attempt",
                assignment_unit_ids={
                    "parallel-v9": "trial-v9",
                    "parallel-v10": "trial-v10",
                },
                arms=[
                    randomized_policy_arm(
                        "parallel-v10", 10, policy_family="parallel_admission"
                    ),
                    randomized_policy_arm(
                        "parallel-v9", 9, policy_family="parallel_admission"
                    ),
                ],
            )[0]
            wrong_store = ProofStateStore(
                "different-held-out-problem",
                generation_root=Path(tmpdir) / "wrong-generation",
            )
            wrong_store.init_problem("Prove a different theorem.")
            with self.assertRaisesRegex(
                ValueError, "problem does not match the proof store"
            ):
                run_workflow(
                    wrong_store,
                    steps=1,
                    execute=False,
                    write_console=False,
                    parallel_admission_assignment=assignment,
                )
            same_id_wrong_content_store = ProofStateStore(
                "held-out-problem-1",
                generation_root=Path(tmpdir) / "wrong-content-generation",
            )
            same_id_wrong_content_store.init_problem(
                "A different theorem hidden behind the registered identifier."
            )
            with self.assertRaisesRegex(
                ValueError, "problem commitment does not match the proof store"
            ):
                run_workflow(
                    same_id_wrong_content_store,
                    steps=1,
                    execute=False,
                    write_console=False,
                    parallel_admission_assignment=assignment,
                )
            execution_count = 0

            def executor(*, session_plan, **_kwargs):
                nonlocal execution_count
                execution_count += 1
                return {
                    "run_id": f"matched-block-run-{execution_count}",
                    "actor_role": session_plan["actor_role"],
                    "status": "failed",
                    "returncode": 1,
                    "wall_time_seconds": 0.01,
                    "usage": {"input_tokens": 1, "total_tokens": 1},
                    "session_id": "",
                    "patch": None,
                    "patch_error": "synthetic nonterminal failure",
                    "failure_kind": "test",
                }

            run_workflow(
                store,
                steps=2,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                stop_on_rejection=False,
                write_on_stop=False,
                write_console=False,
                executor=executor,
                parallel_admission_assignment=assignment,
            )
            with store.connect() as conn:
                traces = [
                    json.loads(row["decision_trace_json"])
                    for row in conn.execute(
                        "SELECT decision_trace_json FROM scheduler_dispatches "
                        "WHERE dispatch_position = 0 ORDER BY rowid"
                    )
                ]
                self.assertEqual(validate_conn(conn), [])
            self.assertEqual(
                [
                    trace["randomized_assignment"]["exposure_index"]
                    for trace in traces
                ],
                [0, 1],
            )
            self.assertEqual(
                {
                    trace["parallel_wave_admission"]["policy_version"]
                    for trace in traces
                },
                {assignment["selected_policy_version"]},
            )

    def test_workflow_assignment_covers_all_waves_and_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-randomized-assignment",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem(
                "Prove a theorem through several successive proof attempts.",
                total_token_budget=500_000,
                reserved_verification_budget=100_000,
            )
            assignment = randomized_arm_assignment(
                experiment_id="parallel-admission-whole-workflow",
                preregistration_sha256="a" * 64,
                registration_receipt_sha256="b" * 64,
                assignment_unit_id="problem-1-repeat-1",
                exploration_stratum="complete-proof-attempt",
                entropy_source="public-beacon-round-201",
                entropy_sha256="c" * 64,
                arms=[
                    randomized_policy_arm(
                        "parallel-v8", 8, policy_family="parallel_admission"
                    ),
                    randomized_policy_arm(
                        "parallel-v9", 9, policy_family="parallel_admission"
                    ),
                ],
                assignment_scope="workflow",
            )
            execution_count = 0

            def executor(*, session_plan, **_kwargs):
                nonlocal execution_count
                execution_count += 1
                return {
                    "run_id": f"workflow-assignment-run-{execution_count}",
                    "actor_role": session_plan["actor_role"],
                    "status": "failed",
                    "returncode": 1,
                    "wall_time_seconds": 0.01,
                    "usage": {"input_tokens": 1, "total_tokens": 1},
                    "session_id": "",
                    "patch": None,
                    "patch_error": "synthetic nonterminal failure",
                    "failure_kind": "test",
                }

            run_workflow(
                store,
                steps=3,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                stop_on_rejection=False,
                write_on_stop=False,
                write_console=False,
                executor=executor,
                parallel_admission_assignment=assignment,
            )
            # A new process invocation can reconstruct the immutable assignment
            # from the latest certificate and continues with the next exposure.
            run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                stop_on_rejection=False,
                write_on_stop=False,
                write_console=False,
                executor=executor,
            )
            with store.connect() as conn:
                rows = conn.execute(
                    "SELECT decision_trace_json FROM scheduler_dispatches "
                    "WHERE dispatch_position = 0 ORDER BY rowid"
                ).fetchall()
                exposure_query_plan = [
                    str(plan_row[3])
                    for plan_row in conn.execute(
                        "EXPLAIN QUERY PLAN SELECT decision_trace_json "
                        "FROM scheduler_dispatches "
                        "WHERE selection_design = 'randomized' "
                        "AND dispatch_position = 0 "
                        "AND json_extract(decision_trace_json, "
                        "'$.randomized_assignment.experiment_id') = ? "
                        "AND json_extract(decision_trace_json, "
                        "'$.randomized_assignment.assignment_unit_id') = ? "
                        "ORDER BY COALESCE(json_extract(decision_trace_json, "
                        "'$.randomized_assignment.exposure_index'), -1) DESC "
                        "LIMIT 1",
                        (
                            assignment["experiment_id"],
                            assignment["assignment_unit_id"],
                        ),
                    ).fetchall()
                ]
                self.assertEqual(validate_conn(conn), [])
            self.assertTrue(
                any(
                    store_module.RANDOMIZED_ASSIGNMENT_UNIT_INDEX in detail
                    for detail in exposure_query_plan
                ),
                exposure_query_plan,
            )
            certificates = [
                json.loads(row["decision_trace_json"])["randomized_assignment"]
                for row in rows
            ]
            self.assertEqual(
                [certificate["exposure_index"] for certificate in certificates],
                [0, 1, 2, 3],
            )
            self.assertEqual(
                {certificate["assignment_input_sha256"] for certificate in certificates},
                {assignment["assignment_input_sha256"]},
            )
            self.assertEqual(
                {certificate["selected_policy_version"] for certificate in certificates},
                {assignment["selected_policy_version"]},
            )
            self.assertEqual(randomized_assignment_cohort_errors(certificates), [])
            deterministic_action = next_action(store)
            with self.assertRaisesRegex(
                RuntimeError, "must govern every subsequent dispatch wave"
            ):
                _record_scheduler_dispatches(
                    store,
                    [deterministic_action],
                    store.audit_chain_heads(),
                    execution_contract={
                        "version": 1,
                        "driver": "custom",
                        "identity": "test:assignment-omission",
                        "recovery_capability": "none",
                    },
                )

    def test_workflow_executes_the_assigned_parallel_admission_epoch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "parallel-policy-assignment",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem(
                "Prove a theorem requiring several independent arguments.",
                total_token_budget=500_000,
                reserved_verification_budget=100_000,
            )
            assignment = randomized_arm_assignment(
                experiment_id="parallel-admission-v8-v9",
                preregistration_sha256="1" * 64,
                registration_receipt_sha256="2" * 64,
                assignment_unit_id="held-out-problem-1-repeat-1",
                exploration_stratum="initial-proof-search",
                entropy_source="public-beacon-round-100",
                entropy_sha256="3" * 64,
                arms=[
                    randomized_policy_arm(
                        "parallel-v8", 8, policy_family="parallel_admission"
                    ),
                    randomized_policy_arm(
                        "parallel-v9", 9, policy_family="parallel_admission"
                    ),
                ],
            )
            result = run_workflow(
                store,
                steps=1,
                execute=False,
                parallel_branches=3,
                write_console=False,
                parallel_admission_assignment=assignment,
            )
            action = result["steps"][0]["action"]
            trace = action["decision_trace"]
            self.assertEqual(
                trace["parallel_wave_admission"]["policy_version"],
                assignment["selected_policy_version"],
            )
            self.assertEqual(
                trace["randomized_assignment"]["selected_arm_id"],
                assignment["selected_arm_id"],
            )
            self.assertEqual(randomized_assignment_errors(
                trace["randomized_assignment"],
                candidate_set_sha256=trace["candidate_set_sha256"],
                dispatched_action_sha256=trace["dispatched_action_sha256"],
                parallel_admission_policy_version=trace[
                    "parallel_wave_admission"
                ]["policy_version"],
            ), [])
            actions = [
                action,
                *result["steps"][0].get("parallel_actions", []),
            ]
            outcome = _record_dispatched_test_wave(
                store,
                actions,
                [f"parallel-policy-run-{index}" for index in range(len(actions))],
                planning_audit_heads=result["steps"][0][
                    "planning_audit_heads"
                ],
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with store.connect() as conn:
                self.assertEqual(validate_conn(conn), [])
                designs = conn.execute(
                    "SELECT DISTINCT selection_design FROM scheduler_dispatches"
                ).fetchall()
            self.assertEqual(
                [row["selection_design"] for row in designs], ["randomized"]
            )

    def test_workflow_assignment_reaches_both_parallel_policy_arms(self) -> None:
        arms = [
            randomized_policy_arm(
                "parallel-v8", 8, policy_family="parallel_admission"
            ),
            randomized_policy_arm(
                "parallel-v9", 9, policy_family="parallel_admission"
            ),
        ]
        assignments: dict[int, dict[str, object]] = {}
        for unit_index in range(100):
            assignment = randomized_arm_assignment(
                experiment_id="parallel-admission-v8-v9-arm-coverage",
                preregistration_sha256="1" * 64,
                registration_receipt_sha256="2" * 64,
                assignment_unit_id=f"held-out-unit-{unit_index}",
                exploration_stratum="arm-coverage",
                entropy_source="public-beacon-round-101",
                entropy_sha256="3" * 64,
                arms=arms,
            )
            assignments.setdefault(
                int(assignment["selected_policy_version"]), assignment
            )
            if set(assignments) == {8, 9}:
                break
        self.assertEqual(set(assignments), {8, 9})
        for expected_version in (8, 9):
            with self.subTest(policy_version=expected_version), tempfile.TemporaryDirectory() as tmpdir:
                store = ProofStateStore(
                    f"parallel-policy-arm-{expected_version}",
                    generation_root=Path(tmpdir) / "generation",
                )
                store.init_problem("Prove the assigned theorem.")
                result = run_workflow(
                    store,
                    steps=1,
                    execute=False,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_console=False,
                    parallel_admission_assignment=assignments[expected_version],
                )
                wave = result["steps"][0]["action"]["decision_trace"][
                    "parallel_wave_admission"
                ]
                self.assertEqual(wave["policy_version"], expected_version)
                self.assertEqual(
                    "admission_search" in wave, expected_version >= 9
                )

    def test_current_seal_rejects_direct_run_provenance_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "assignment-provenance-seal",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("The root theorem holds.")
            accepted = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "record_run_metrics",
                            "run_id": "sealed-observational-run",
                            "actor_role": "researcher",
                            "mode": "prove",
                            "target_id": "root",
                            "selection_design": "observational",
                            "decision_trace": {"selected_candidate_id": "base"},
                            "status": "completed",
                        }
                    ],
                    "rationale": "record host selection provenance",
                },
            )
            self.assertTrue(accepted.accepted, accepted.errors)
            self.assertTrue(store.current_state_seal()["valid"])
            with store.connect() as conn:
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError,
                    "scheduler history is append-only",
                ):
                    conn.execute(
                        "UPDATE runs SET decision_trace_json = '{}' "
                        "WHERE run_id = 'sealed-observational-run'"
                    )
                conn.rollback()
            seal = store.current_state_seal()
            self.assertTrue(seal["valid"], seal)


class ExactIdentityAndArchiveTests(unittest.TestCase):
    def _audit_protocol_root(self, root: Path) -> dict[str, object]:
        public_key = root.parent / "trusted-registration-public.pem"
        key_id = hashlib.sha256(public_key_der(public_key)).hexdigest()
        randomization_public_key = (
            root.parent / "trusted-randomization-public.pem"
        )
        randomization_key_id = hashlib.sha256(
            public_key_der(randomization_public_key)
        ).hexdigest()
        trace_public_key = root.parent / "trusted-trace-public.pem"
        trace_key_id = hashlib.sha256(
            public_key_der(trace_public_key)
        ).hexdigest()
        grader_keys = {}
        for grader_identity in ("expert-a", "expert-b"):
            grader_key = root.parent / f"trusted-{grader_identity}-public.pem"
            grader_keys[
                hashlib.sha256(public_key_der(grader_key)).hexdigest()
            ] = grader_key
        return audit_experiment_archives(
            root,
            trusted_registration_keys={key_id: public_key},
            trusted_randomization_keys={
                randomization_key_id: randomization_public_key
            },
            trusted_trace_keys={trace_key_id: trace_public_key},
            trusted_grader_keys=grader_keys,
        )

    def _refresh_protocol_hashes(self, root: Path) -> None:
        archive = root / "protocol-case"
        protocol_path = archive / "protocol_manifest.json"
        manifest = json.loads(protocol_path.read_text(encoding="utf-8"))
        manifest["file_sha256"] = {
            relative: hashlib.sha256((archive / relative).read_bytes()).hexdigest()
            for relative in manifest["file_sha256"]
        }
        protocol_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        checksum_lines = [
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(archive).as_posix()}"
            for path in sorted(archive.rglob("*"))
            if path.is_file() and path.name != "SHA256SUMS"
        ]
        (archive / "SHA256SUMS").write_text(
            "\n".join(checksum_lines) + "\n", encoding="utf-8"
        )

    def _protocol_archive(
        self,
        tmpdir: str,
        *,
        valid: bool,
        evidence_scope: str = "case_study",
        general_protocol_version: int = 5,
    ) -> Path:
        root = Path(tmpdir) / "experiments"
        archive = root / "protocol-case"
        archive.mkdir(parents=True)
        registration_private_key = Path(tmpdir) / "registration-private.pem"
        registration_public_key = Path(tmpdir) / "trusted-registration-public.pem"
        randomization_private_key = Path(tmpdir) / "randomization-private.pem"
        randomization_public_key = (
            Path(tmpdir) / "trusted-randomization-public.pem"
        )
        trace_private_key = Path(tmpdir) / "trace-private.pem"
        trace_public_key = Path(tmpdir) / "trusted-trace-public.pem"
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "Ed25519",
                "-out",
                str(registration_private_key),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "Ed25519",
                "-out",
                str(trace_private_key),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        trace_private_key.chmod(0o600)
        subprocess.run(
            [
                "openssl",
                "pkey",
                "-in",
                str(trace_private_key),
                "-pubout",
                "-out",
                str(trace_public_key),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "Ed25519",
                "-out",
                str(randomization_private_key),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        randomization_private_key.chmod(0o600)
        subprocess.run(
            [
                "openssl",
                "pkey",
                "-in",
                str(randomization_private_key),
                "-pubout",
                "-out",
                str(randomization_public_key),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        grader_key_paths: dict[str, tuple[Path, Path]] = {}
        for grader_identity in ("expert-a", "expert-b"):
            grader_private_key = Path(tmpdir) / f"{grader_identity}-private.pem"
            grader_public_key = Path(tmpdir) / f"trusted-{grader_identity}-public.pem"
            subprocess.run(
                [
                    "openssl",
                    "genpkey",
                    "-algorithm",
                    "Ed25519",
                    "-out",
                    str(grader_private_key),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            grader_private_key.chmod(0o600)
            subprocess.run(
                [
                    "openssl",
                    "pkey",
                    "-in",
                    str(grader_private_key),
                    "-pubout",
                    "-out",
                    str(grader_public_key),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            grader_key_paths[grader_identity] = (
                grader_private_key,
                grader_public_key,
            )
        registration_private_key.chmod(0o600)
        subprocess.run(
            [
                "openssl",
                "pkey",
                "-in",
                str(registration_private_key),
                "-pubout",
                "-out",
                str(registration_public_key),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        problem = b"Prove that every object in the stated class has property P.\n"
        answer = (
            b"The decisive reference answer uses a forty-character-long hidden "
            b"classification argument that must never enter the prompt.\n"
        )
        files: dict[str, bytes] = {
            "problem.md": problem,
            "problem_prompt.md": (
                problem if valid else b"Prove a materially different theorem.\n"
            ),
            "prompt.txt": (
                b"Solve the exact problem in problem_prompt.md.\n"
                if valid
                else b"Solve it using this answer: " + answer
            ),
            "environment.json": b'{"python":"3.12"}\n',
            "runs.jsonl": b'{"run_id":"run-1"}\n',
            "events.jsonl": b'{"event":"start"}\n',
            "snapshot.json": b'{"problem_id":"case"}\n',
            "answer.txt": answer,
        }
        run_labels: dict[str, object] = {
            "run-1": "solved" if valid else "unsolved"
        }
        grade: dict[str, object] = {
            "independent": valid,
            "grader_identity": "external-grader" if valid else "",
            "run_labels": run_labels,
        }
        general_files: dict[str, str] = {}
        if evidence_scope in {"general_performance", "novelty_and_performance"}:
            trials: list[dict[str, object]] = []
            run_labels = {}
            conditions = (
                ["parallel-v17", "parallel-v18"]
                if general_protocol_version >= 6
                else ["albilich-v3", "control-v2"]
            )
            fixture_randomness_source = "fixture-public-randomness"
            fixture_randomness_event_id = "fixture-pulse-2026-01-02"
            fixture_randomness_sha256 = "f" * 64

            def fixture_run_id(
                problem_index: int, repeat_index: int, condition: str
            ) -> str:
                if general_protocol_version < 6:
                    return (
                        f"general-{problem_index}-{repeat_index}-"
                        f"{condition.replace('-', '_')}"
                    )
                opaque = hashlib.sha256(
                    (
                        f"fixture-blinded-unit:{problem_index}:"
                        f"{repeat_index}:{condition}"
                    ).encode("utf-8")
                ).hexdigest()[:24]
                return f"unit-{opaque}"

            assignment_schedule_blocks: list[dict[str, object]] = []
            for problem_index in range(10):
                problem_relative = f"trial_problems/problem-{problem_index}.md"
                prompt_relative = f"trial_prompts/problem-{problem_index}.txt"
                problem_bytes = (
                    f"Held-out problem {problem_index}: prove property P_{problem_index}.\n"
                ).encode()
                prompt_bytes = (
                    f"Solve the problem in {problem_relative} under the fixed protocol.\n"
                ).encode()
                files[problem_relative] = problem_bytes
                files[prompt_relative] = prompt_bytes
                for repeat_index in range(1, 4):
                    block_seed = (
                        randomized_block_seed(
                            randomness_sha256=fixture_randomness_sha256,
                            problem_id=f"held-out-{problem_index}",
                            repeat_index=repeat_index,
                        )
                        if general_protocol_version >= 6
                        else 1000 + problem_index * 10 + repeat_index
                    )
                    condition_order = randomized_condition_order(
                        conditions,
                        problem_id=f"held-out-{problem_index}",
                        repeat_index=repeat_index,
                        random_seed=block_seed,
                    )
                    execution_order = {
                        condition: index
                        for index, condition in enumerate(condition_order)
                    }
                    assignment_schedule_blocks.append(
                        (
                            {
                                "problem_id": f"held-out-{problem_index}",
                                "problem_sha256": hashlib.sha256(
                                    problem_bytes
                                ).hexdigest(),
                                "prompt_sha256": hashlib.sha256(
                                    prompt_bytes
                                ).hexdigest(),
                                "repeat_index": repeat_index,
                                "assignment_unit_ids": {
                                    condition: fixture_run_id(
                                        problem_index,
                                        repeat_index,
                                        condition,
                                    )
                                    for condition in conditions
                                },
                                "token_budget": 100000,
                                "stopping_rule": (
                                    "fixed token budget or certified terminal state"
                                ),
                            }
                            if general_protocol_version >= 6
                            else {
                                "problem_id": f"held-out-{problem_index}",
                                "repeat_index": repeat_index,
                                "random_seed": block_seed,
                                "condition_order": condition_order,
                            }
                        )
                    )
                    for condition in conditions:
                        run_id = fixture_run_id(
                            problem_index,
                            repeat_index,
                            condition,
                        )
                        event_relative = f"trial_events/{run_id}.jsonl"
                        snapshot_relative = f"trial_snapshots/{run_id}.json"
                        result_relative = f"trial_results/{run_id}.json"
                        grading_artifact_relative = (
                            f"trial_grading_artifacts/{run_id}.json"
                        )
                        event_bytes = (
                            json.dumps({"run_id": run_id, "event": "start"})
                            + "\n"
                            + json.dumps({"run_id": run_id, "event": "completed"})
                            + "\n"
                        ).encode()
                        snapshot_bytes = (
                            json.dumps(
                                {
                                    "run_id": run_id,
                                    "problem_id": f"held-out-{problem_index}",
                                    "current_revision": 1,
                                    "state_hash": hashlib.sha256(
                                        f"state:{run_id}".encode()
                                    ).hexdigest(),
                                },
                                sort_keys=True,
                            )
                            + "\n"
                        ).encode()
                        result_bytes = (
                            json.dumps(
                                {"run_id": run_id, "status": "completed"},
                                sort_keys=True,
                            )
                            + "\n"
                        ).encode()
                        grading_artifact_bytes = (
                            json.dumps(
                                {
                                    "artifact_version": 1,
                                    "evaluation_id": run_id,
                                    "solution": (
                                        "A complete candidate proof of the stated "
                                        "held-out proposition."
                                    ),
                                },
                                sort_keys=True,
                            )
                            + "\n"
                        ).encode()
                        files[event_relative] = event_bytes
                        files[snapshot_relative] = snapshot_bytes
                        files[result_relative] = result_bytes
                        files[grading_artifact_relative] = grading_artifact_bytes
                        trials.append(
                            {
                                "run_id": run_id,
                                "problem_id": f"held-out-{problem_index}",
                                "condition": condition,
                                "repeat_index": repeat_index,
                                "random_seed": block_seed,
                                "execution_order": execution_order[condition],
                                "problem_file": problem_relative,
                                "prompt_file": prompt_relative,
                                "problem_sha256": hashlib.sha256(problem_bytes).hexdigest(),
                                "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
                                "event_log_file": event_relative,
                                "event_log_sha256": hashlib.sha256(event_bytes).hexdigest(),
                                "proof_snapshot_file": snapshot_relative,
                                "proof_snapshot_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
                                "result_file": result_relative,
                                "result_sha256": hashlib.sha256(result_bytes).hexdigest(),
                                "grading_artifact_file": grading_artifact_relative,
                                "grading_artifact_sha256": hashlib.sha256(
                                    grading_artifact_bytes
                                ).hexdigest(),
                                "token_budget": 100000,
                                "stopping_rule": "fixed token budget or certified terminal state",
                            }
                        )
                        if evidence_scope == "novelty_and_performance":
                            run_labels[run_id] = {
                                "correctness": "correct",
                                "usefulness": "useful",
                                "novelty": "independently_novel",
                                "non_rediscovery": True,
                                "eventual_proof_contribution": "contributed",
                            }
                        else:
                            run_labels[run_id] = "solved"
            files["trial_manifest.json"] = (
                json.dumps({"trials": trials}, sort_keys=True) + "\n"
            ).encode()
            files["assignment_schedule.json"] = (
                json.dumps(
                    {
                        "algorithm": "sha256_fisher_yates_rejection_v1",
                        **(
                            {
                                "block_seed_derivation_algorithm": (
                                    BLOCK_RANDOMIZED_SEED_DERIVATION_ALGORITHM
                                ),
                                "randomness_source": fixture_randomness_source,
                                "randomness_event_id": fixture_randomness_event_id,
                            }
                            if general_protocol_version >= 6
                            else {}
                        ),
                        "blocks": assignment_schedule_blocks,
                    },
                    sort_keys=True,
                )
                + "\n"
            ).encode()
            condition_definitions: list[dict[str, object]] = []
            environment_sha256 = hashlib.sha256(
                files["environment.json"]
            ).hexdigest()
            for condition in conditions:
                condition_spec_file = f"conditions/{condition}.json"
                files[condition_spec_file] = (
                    json.dumps(
                        (
                            {
                                "condition_id": condition,
                                "condition_kind": "parallel_admission_policy",
                                "policy_family": "parallel_admission",
                                "selection_policy_version": int(
                                    condition.removeprefix("parallel-v")
                                ),
                                "policy_semantics_sha256": (
                                    parallel_admission_module.PARALLEL_POLICY_SEMANTIC_SHA256[
                                        int(condition.removeprefix("parallel-v"))
                                    ]
                                ),
                            }
                            if general_protocol_version >= 6
                            else {
                                "condition_id": condition,
                                "model": "fixture-model",
                                "configuration": condition,
                            }
                        ),
                        sort_keys=True,
                    )
                    + "\n"
                ).encode()
                condition_definitions.append(
                    {
                        "condition_id": condition,
                        "condition_spec_file": condition_spec_file,
                        "condition_spec_sha256": hashlib.sha256(
                            files[condition_spec_file]
                        ).hexdigest(),
                        "environment_sha256": environment_sha256,
                    }
                )
            files["selection_rule.json"] = (
                json.dumps(
                    {
                        "conditions": condition_definitions,
                        "blocking": ["problem_id", "repeat_index"],
                        "execution_order_algorithm": "sha256_fisher_yates_rejection_v1",
                    },
                    sort_keys=True,
                )
                + "\n"
            ).encode()
            files["analysis_plan.json"] = (
                json.dumps(
                    {
                        "primary_endpoint": "success_rate_difference",
                        "unit_of_analysis": "problem",
                        "method": "sha256 problem-cluster bootstrap percentile v1",
                        "bootstrap_seed_sha256": "e" * 64,
                        "bootstrap_replicates": 1000,
                        "quantile_rule": "outer_order_statistics_v1",
                    },
                    sort_keys=True,
                )
                + "\n"
            ).encode()
            files["rubric.json"] = (
                json.dumps(
                    {
                        "rubric_version": 1,
                        "primary_label": "solved",
                        "requires_root_correctness": True,
                    },
                    sort_keys=True,
                )
                + "\n"
            ).encode()
            rubric_sha256 = hashlib.sha256(files["rubric.json"]).hexdigest()
            files["grader_protocol.json"] = (
                json.dumps(
                    {
                        "blinded_to_condition": True,
                        "generator_excluded": True,
                        "selector_excluded": True,
                        "minimum_independent_graders": 2,
                        "rubric_sha256": rubric_sha256,
                        **(
                            {
                                "condition_key_withheld_from_graders": True,
                                "labels_finalized_before_trace_review": True,
                                "trace_auditor_excluded_from_grading": True,
                                "blinded_grading_artifact_only": True,
                            }
                            if general_protocol_version >= 6
                            else {}
                        ),
                    },
                    sort_keys=True,
                )
                + "\n"
            ).encode()
            files["preregistration.json"] = (
                json.dumps(
                    {
                        "registered_before_execution": True,
                        "held_out_problem_selection": True,
                        "conditions": conditions,
                        "primary_endpoints": ["success_rate_difference"],
                        "primary_contrasts": [
                            {
                                "endpoint": "success_rate_difference",
                                "treatment_condition": (
                                    conditions[1]
                                    if general_protocol_version >= 6
                                    else conditions[0]
                                ),
                                "control_condition": (
                                    conditions[0]
                                    if general_protocol_version >= 6
                                    else conditions[1]
                                ),
                                "estimand": "problem_mean_success_difference",
                            }
                        ],
                        "selection_rule_sha256": hashlib.sha256(
                            files["selection_rule.json"]
                        ).hexdigest(),
                        "analysis_plan_sha256": hashlib.sha256(
                            files["analysis_plan.json"]
                        ).hexdigest(),
                        "assignment_schedule_sha256": hashlib.sha256(
                            files["assignment_schedule.json"]
                        ).hexdigest(),
                        "grader_protocol_sha256": hashlib.sha256(
                            files["grader_protocol.json"]
                        ).hexdigest(),
                        "rubric_sha256": rubric_sha256,
                        "target_problem_count": 10,
                        "repeated_trials_per_condition": 3,
                        **(
                            {
                                "experiment_kind": "parallel_admission_scheduler_calibration",
                                "scheduler_assignment_protocol_version": 3,
                                "scheduler_experiment_id": "fixture-parallel-admission-calibration",
                                "scheduler_exploration_stratum": "complete-proof-attempt",
                                "randomness_source": fixture_randomness_source,
                                "randomness_event_id": fixture_randomness_event_id,
                                "block_seed_derivation_algorithm": (
                                    BLOCK_RANDOMIZED_SEED_DERIVATION_ALGORITHM
                                ),
                                "randomization_authority_separate": True,
                            }
                            if general_protocol_version >= 6
                            else {}
                        ),
                        "power_analysis": (
                            {
                                "method": "normal_approximation_paired_problem_means_v1",
                                "analysis_unit": "problem",
                                "alternative": "two_sided",
                                "alpha": 0.05,
                                "desired_power": 0.8,
                                "minimum_detectable_effect": 0.2,
                                "assumed_problem_mean_difference_standard_deviation": 0.2,
                                "standard_deviation_basis": "preregistered_design_assumption",
                                "required_problem_count": 8,
                            }
                            if general_protocol_version >= 5
                            else {
                                "method": "declared_paired_simulation_v1",
                                "alpha": 0.05,
                                "desired_power": 0.8,
                                "minimum_detectable_effect": 0.2,
                                "required_problem_count": 1,
                            }
                        ),
                    },
                    sort_keys=True,
                )
                + "\n"
            ).encode()
            registration_payload = {
                "receipt_version": 1,
                "issued_at": "2026-01-01T00:00:00Z",
                "preregistration_sha256": hashlib.sha256(
                    files["preregistration.json"]
                ).hexdigest(),
                "selection_rule_sha256": hashlib.sha256(
                    files["selection_rule.json"]
                ).hexdigest(),
                "analysis_plan_sha256": hashlib.sha256(
                    files["analysis_plan.json"]
                ).hexdigest(),
                "assignment_schedule_sha256": hashlib.sha256(
                    files["assignment_schedule.json"]
                ).hexdigest(),
                "grader_protocol_sha256": hashlib.sha256(
                    files["grader_protocol.json"]
                ).hexdigest(),
                "rubric_sha256": rubric_sha256,
            }
            registration_signature = sign_ed25519(
                canonical_signature_payload(registration_payload),
                registration_private_key,
            )
            registration_key_id = hashlib.sha256(
                public_key_der(registration_public_key)
            ).hexdigest()
            files["registration_receipt.json"] = (
                json.dumps(
                    {
                        "payload": registration_payload,
                        "signature": {
                            "algorithm": "ed25519",
                            "key_id_sha256": registration_key_id,
                            "value_base64": base64.b64encode(
                                registration_signature
                            ).decode("ascii"),
                        },
                    },
                    sort_keys=True,
                )
                + "\n"
            ).encode()
            if general_protocol_version >= 6:
                randomization_payload = {
                    "receipt_version": 1,
                    "issued_at": "2026-01-02T00:00:00Z",
                    "registration_receipt_sha256": hashlib.sha256(
                        files["registration_receipt.json"]
                    ).hexdigest(),
                    "assignment_schedule_sha256": hashlib.sha256(
                        files["assignment_schedule.json"]
                    ).hexdigest(),
                    "randomness_source": fixture_randomness_source,
                    "randomness_event_id": fixture_randomness_event_id,
                    "randomness_sha256": fixture_randomness_sha256,
                    "block_seed_derivation_algorithm": (
                        BLOCK_RANDOMIZED_SEED_DERIVATION_ALGORITHM
                    ),
                }
                randomization_signature = sign_ed25519(
                    canonical_signature_payload(randomization_payload),
                    randomization_private_key,
                )
                randomization_key_id = hashlib.sha256(
                    public_key_der(randomization_public_key)
                ).hexdigest()
                files["randomization_receipt.json"] = (
                    json.dumps(
                        {
                            "payload": randomization_payload,
                            "signature": {
                                "algorithm": "ed25519",
                                "key_id_sha256": randomization_key_id,
                                "value_base64": base64.b64encode(
                                    randomization_signature
                                ).decode("ascii"),
                            },
                        },
                        sort_keys=True,
                    )
                    + "\n"
                ).encode()
                scheduler_arms = [
                    randomized_policy_arm(
                        condition,
                        int(condition.removeprefix("parallel-v")),
                        policy_family="parallel_admission",
                    )
                    for condition in conditions
                ]
                fixture_trials_by_block: dict[
                    tuple[str, int], list[dict[str, object]]
                ] = {}
                for trial in trials:
                    fixture_trials_by_block.setdefault(
                        (
                            str(trial["problem_id"]),
                            int(trial["repeat_index"]),
                        ),
                        [],
                    ).append(trial)
                for (
                    problem_id,
                    repeat_index,
                ), block_trials in fixture_trials_by_block.items():
                    trial_by_condition = {
                        str(trial["condition"]): trial
                        for trial in block_trials
                    }
                    block_assignments = randomized_block_workflow_assignments(
                        experiment_id="fixture-parallel-admission-calibration",
                        preregistration_sha256=hashlib.sha256(
                            files["preregistration.json"]
                        ).hexdigest(),
                        registration_receipt_sha256=hashlib.sha256(
                            files["registration_receipt.json"]
                        ).hexdigest(),
                        assignment_schedule_sha256=hashlib.sha256(
                            files["assignment_schedule.json"]
                        ).hexdigest(),
                        randomization_receipt_sha256=(
                            hashlib.sha256(
                                files["randomization_receipt.json"]
                            ).hexdigest()
                        ),
                        randomness_source=fixture_randomness_source,
                        randomness_event_id=fixture_randomness_event_id,
                        randomness_sha256=fixture_randomness_sha256,
                        problem_id=problem_id,
                        problem_sha256=str(block_trials[0]["problem_sha256"]),
                        repeat_index=repeat_index,
                        exploration_stratum="complete-proof-attempt",
                        assignment_unit_ids={
                            condition: str(
                                trial_by_condition[condition]["run_id"]
                            )
                            for condition in conditions
                        },
                        arms=scheduler_arms,
                    )
                    for assignment in block_assignments:
                        trial = trial_by_condition[
                            str(assignment["selected_arm_id"])
                        ]
                        run_id = str(trial["run_id"])
                        runtime_store = ProofStateStore(
                            problem_id,
                            generation_root=(
                                Path(tmpdir)
                                / "scheduler-calibration-runtime"
                                / run_id
                            ),
                        )
                        runtime_store.init_problem(
                            files[str(trial["problem_file"])].decode("utf-8"),
                            total_token_budget=int(trial["token_budget"]),
                            reserved_verification_budget=0,
                        )
                        planned = run_workflow(
                            runtime_store,
                            steps=1,
                            execute=False,
                            parallel_librarian_verifier=False,
                            parallel_branches=0,
                            write_console=False,
                            parallel_admission_assignment=assignment,
                        )
                        planned_action = planned["steps"][0]["action"]
                        decision_trace = dict(planned_action["decision_trace"])
                        dispatched_action = {
                            str(key): value
                            for key, value in planned_action.items()
                            if str(key) != "decision_trace"
                        }
                        scheduler_relative = (
                            f"trial_scheduler_assignments/{run_id}.json"
                        )
                        scheduler_dispatches = [
                            {
                                "decision_trace": decision_trace,
                                "dispatched_action": dispatched_action,
                            }
                        ]
                        scheduler_bytes = (
                            json.dumps(
                                {
                                    "trace_version": 2,
                                    "run_id": run_id,
                                    "dispatches": scheduler_dispatches,
                                    "finalization": {
                                        "finalization_version": 1,
                                        "complete": True,
                                        "dispatch_count": len(
                                            scheduler_dispatches
                                        ),
                                        "last_exposure_index": 0,
                                        "assignment_input_sha256": decision_trace[
                                            "randomized_assignment"
                                        ]["assignment_input_sha256"],
                                        "dispatches_sha256": hashlib.sha256(
                                            canonical_signature_payload(
                                                scheduler_dispatches
                                            )
                                        ).hexdigest(),
                                        "event_log_sha256": trial[
                                            "event_log_sha256"
                                        ],
                                        "proof_snapshot_sha256": trial[
                                            "proof_snapshot_sha256"
                                        ],
                                        "result_sha256": trial[
                                            "result_sha256"
                                        ],
                                    },
                                },
                                sort_keys=True,
                            )
                            + "\n"
                        ).encode()
                        files[scheduler_relative] = scheduler_bytes
                        trial["scheduler_assignment_file"] = scheduler_relative
                        trial["scheduler_assignment_sha256"] = hashlib.sha256(
                            scheduler_bytes
                        ).hexdigest()
                files["trial_manifest.json"] = (
                    json.dumps({"trials": trials}, sort_keys=True) + "\n"
                ).encode()
                files["blinded_grading_manifest.json"] = (
                    json.dumps(
                        {
                            "manifest_version": 1,
                            "evaluations": [
                                {
                                    "evaluation_id": str(trial["run_id"]),
                                    "problem_sha256": trial["problem_sha256"],
                                    "grading_artifact_sha256": trial[
                                        "grading_artifact_sha256"
                                    ],
                                }
                                for trial in sorted(
                                    trials,
                                    key=lambda item: str(item["run_id"]),
                                )
                            ],
                        },
                        sort_keys=True,
                    )
                    + "\n"
                ).encode()
            files["analysis.json"] = (
                json.dumps(
                    {
                        "confidence_intervals": {
                            "success_rate_difference": {
                                "estimate": 0.0,
                                "lower": 0.0,
                                "upper": 0.0,
                                "n_problems": 10,
                                "n_trials": 60,
                                "unit_of_analysis": "problem",
                                "dependence_adjustment": "problem-cluster bootstrap",
                                "method": "sha256 problem-cluster bootstrap percentile v1",
                            }
                        }
                    },
                    sort_keys=True,
                )
                + "\n"
            ).encode()
            grade["run_labels"] = run_labels
            grade["grader_labels"] = {
                "expert-a": dict(run_labels),
                "expert-b": dict(run_labels),
            }
            receipt_sha256 = hashlib.sha256(
                files["registration_receipt.json"]
            ).hexdigest()
            grade["graders"] = []
            for grader_identity in ("expert-a", "expert-b"):
                grader_private_key, grader_public_key = grader_key_paths[
                    grader_identity
                ]
                grader_payload = {
                    "signature_version": (
                        2 if general_protocol_version >= 6 else 1
                    ),
                    "grader_identity": grader_identity,
                    "run_labels_sha256": hashlib.sha256(
                        canonical_signature_payload(
                            grade["grader_labels"][grader_identity]
                        )
                    ).hexdigest(),
                    "rubric_sha256": rubric_sha256,
                    "registration_receipt_sha256": receipt_sha256,
                    **(
                        {
                            "blinded_grading_attested": True,
                            "blinded_grading_manifest_sha256": hashlib.sha256(
                                files["blinded_grading_manifest.json"]
                            ).hexdigest(),
                        }
                        if general_protocol_version >= 6
                        else {}
                    ),
                }
                grader_signature = sign_ed25519(
                    canonical_signature_payload(grader_payload),
                    grader_private_key,
                )
                grade["graders"].append(
                    {
                        "grader_identity": grader_identity,
                        "independent": True,
                        "generator": False,
                        "selector": False,
                        "signature": {
                            "algorithm": "ed25519",
                            "key_id_sha256": hashlib.sha256(
                                public_key_der(grader_public_key)
                            ).hexdigest(),
                            "value_base64": base64.b64encode(
                                grader_signature
                            ).decode("ascii"),
                        },
                    }
                )
            general_files = {
                "preregistration_file": "preregistration.json",
                "selection_rule_file": "selection_rule.json",
                "analysis_plan_file": "analysis_plan.json",
                "assignment_schedule_file": "assignment_schedule.json",
                "registration_receipt_file": "registration_receipt.json",
                "trial_manifest_file": "trial_manifest.json",
                "statistical_analysis_file": "analysis.json",
                "grader_protocol_file": "grader_protocol.json",
                "rubric_file": "rubric.json",
                    **(
                        {
                            "randomization_receipt_file": "randomization_receipt.json",
                            "scheduler_trace_audit_file": "scheduler_trace_audit.json",
                            "blinded_grading_manifest_file": (
                                "blinded_grading_manifest.json"
                            ),
                        }
                        if general_protocol_version >= 6
                    else {}
                ),
            }
            trial_by_run_id = {
                str(trial["run_id"]): trial for trial in trials
            }
            files["runs.jsonl"] = b"".join(
                (
                    json.dumps(
                        {
                            **{
                                field: trial_by_run_id[run_id][field]
                                for field in (
                                    "run_id",
                                    "problem_id",
                                    "condition",
                                    "repeat_index",
                                    "random_seed",
                                    "execution_order",
                                    "problem_sha256",
                                    "prompt_sha256",
                                    "token_budget",
                                    "event_log_sha256",
                                    "proof_snapshot_sha256",
                                    "result_sha256",
                                )
                            },
                            **(
                                {
                                    "scheduler_assignment_sha256": trial_by_run_id[
                                        run_id
                                    ]["scheduler_assignment_sha256"],
                                    "grading_artifact_sha256": trial_by_run_id[
                                        run_id
                                    ]["grading_artifact_sha256"],
                                }
                                if general_protocol_version >= 6
                                else {}
                            ),
                            "status": "completed",
                        },
                        sort_keys=True,
                    )
                    + "\n"
                ).encode()
                for run_id in run_labels
            )

        scoreboard = {
            "labels": dict(grade["run_labels"])
        }
        if not valid:
            scoreboard["labels"]["run-1"] = "solved"
        files["grade.json"] = (json.dumps(grade, sort_keys=True) + "\n").encode()
        if (
            evidence_scope in {"general_performance", "novelty_and_performance"}
            and general_protocol_version >= 6
        ):
            scheduler_trace_audit_payload = {
                "receipt_version": 1,
                "issued_at": "2026-01-03T00:00:00Z",
                "registration_receipt_sha256": hashlib.sha256(
                    files["registration_receipt.json"]
                ).hexdigest(),
                "randomization_receipt_sha256": hashlib.sha256(
                    files["randomization_receipt.json"]
                ).hexdigest(),
                "trial_manifest_sha256": hashlib.sha256(
                    files["trial_manifest.json"]
                ).hexdigest(),
                "blinded_grading_manifest_sha256": hashlib.sha256(
                    files["blinded_grading_manifest.json"]
                ).hexdigest(),
                "independent_grade_sha256": hashlib.sha256(
                    files["grade.json"]
                ).hexdigest(),
                "scheduler_trace_completeness_attested": True,
                "labels_finalized_before_trace_review_attested": True,
                "trace_auditor_excluded_from_grading": True,
                "reviewed_run_count": len(trials),
            }
            scheduler_trace_audit_signature = sign_ed25519(
                canonical_signature_payload(scheduler_trace_audit_payload),
                trace_private_key,
            )
            files["scheduler_trace_audit.json"] = (
                json.dumps(
                    {
                        "payload": scheduler_trace_audit_payload,
                        "signature": {
                            "algorithm": "ed25519",
                            "key_id_sha256": hashlib.sha256(
                                public_key_der(trace_public_key)
                            ).hexdigest(),
                            "value_base64": base64.b64encode(
                                scheduler_trace_audit_signature
                            ).decode("ascii"),
                        },
                    },
                    sort_keys=True,
                )
                + "\n"
            ).encode()
        files["scoreboard.json"] = (json.dumps(scoreboard, sort_keys=True) + "\n").encode()
        for relative, content in files.items():
            destination = archive / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        file_sha256 = {
            relative: hashlib.sha256(content).hexdigest()
            for relative, content in files.items()
        }
        visible = ["problem_prompt.md", "prompt.txt"]
        if not valid:
            visible.append("answer.txt")
        manifest = {
            "protocol_version": (
                general_protocol_version
                if evidence_scope
                in {"general_performance", "novelty_and_performance"}
                else 3
            ),
            "evidence_scope": evidence_scope,
            "problem_selection_rule": "First preregistered problem.",
            "problem_file": "problem.md",
            "problem_sha256": hashlib.sha256(problem).hexdigest(),
            "prompt_files": ["prompt.txt"],
            "prompt_problem_file": "problem_prompt.md",
            "environment_file": "environment.json",
            "random_seed": 7,
            "model": "fixture-model",
            "stopping_rule": "one run",
            "run_log_file": "runs.jsonl",
            "event_log_file": "events.jsonl",
            "proof_snapshot_file": "snapshot.json",
            "independent_grade_file": "grade.json",
            "scoreboard_file": "scoreboard.json",
            "agent_visible_files": visible,
            "reference_answer_files": ["answer.txt"],
            "file_sha256": file_sha256,
            **general_files,
        }
        protocol_path = archive / "protocol_manifest.json"
        protocol_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        checksum_lines = []
        for path in sorted(archive.rglob("*")):
            if not path.is_file():
                continue
            if path.name == "SHA256SUMS":
                continue
            checksum_lines.append(
                f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(archive).as_posix()}"
            )
        (archive / "SHA256SUMS").write_text(
            "\n".join(checksum_lines) + "\n", encoding="utf-8"
        )
        (root / "archive_status.json").write_text(
            json.dumps(
                {
                    "registry_version": 1,
                    "archives": {"protocol-case": "protocol_validated"},
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return root

    def test_paired_problem_power_count_is_recomputed(self) -> None:
        self.assertEqual(
            8,
            paired_problem_power_required_count(
                alpha=0.05,
                desired_power=0.8,
                minimum_detectable_effect=0.2,
                assumed_standard_deviation=0.2,
            ),
        )
        invalid_parameters = (
            {"alpha": True},
            {"desired_power": float("nan")},
            {"minimum_detectable_effect": 0.0},
            {"assumed_standard_deviation": 1.1},
        )
        baseline = {
            "alpha": 0.05,
            "desired_power": 0.8,
            "minimum_detectable_effect": 0.2,
            "assumed_standard_deviation": 0.2,
        }
        for mutation in invalid_parameters:
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    paired_problem_power_required_count(
                        **{**baseline, **mutation}
                    )

    def test_general_evidence_rejects_a_fabricated_power_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
            )
            preregistration_path = (
                root / "protocol-case" / "preregistration.json"
            )
            preregistration = json.loads(
                preregistration_path.read_text(encoding="utf-8")
            )
            preregistration["power_analysis"]["required_problem_count"] = 1
            preregistration_path.write_text(
                json.dumps(preregistration, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            self.assertIn(
                "required_problem_count does not match the registered "
                "paired-problem calculation",
                " ".join(result["errors"]),
            )

    def test_protocol_v4_replays_with_its_historical_power_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
                general_protocol_version=4,
            )
            result = self._audit_protocol_root(root)
            self.assertTrue(result["valid"], result["errors"])
            archive = result["archives"]["protocol-case"]
            self.assertTrue(archive["general_performance_evidence"])

    def test_protocol_v6_joins_scheduler_conditions_to_runtime_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
                general_protocol_version=6,
            )
            result = self._audit_protocol_root(root)
            self.assertTrue(result["valid"], result["errors"])
            archive = result["archives"]["protocol-case"]
            self.assertTrue(archive["general_performance_evidence"])

    def test_protocol_v6_trace_audit_binds_finalized_grade_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
                general_protocol_version=6,
            )
            grade_path = root / "protocol-case" / "grade.json"
            grade = json.loads(grade_path.read_text(encoding="utf-8"))
            grade_path.write_text(
                json.dumps(grade, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            self.assertIn(
                "scheduler trace audit independent_grade_sha256 does not match independent_grade_file",
                " ".join(result["errors"]),
            )

    def test_protocol_v6_rejects_a_forged_scheduler_condition(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
                general_protocol_version=6,
            )
            archive = root / "protocol-case"
            trial_manifest_path = archive / "trial_manifest.json"
            trial_manifest = json.loads(
                trial_manifest_path.read_text(encoding="utf-8")
            )
            trial = trial_manifest["trials"][0]
            scheduler_path = archive / trial["scheduler_assignment_file"]
            scheduler_assignment = json.loads(
                scheduler_path.read_text(encoding="utf-8")
            )
            certificate = scheduler_assignment["dispatches"][0][
                "decision_trace"
            ]["randomized_assignment"]
            certificate["selected_policy_version"] = 999
            decision_trace = scheduler_assignment["dispatches"][0][
                "decision_trace"
            ]
            decision_trace["parallel_wave_admission"]["policy_version"] = (
                9
                if decision_trace["parallel_wave_admission"]["policy_version"]
                == 10
                else 10
            )
            certificate["certificate_sha256"] = hashlib.sha256(
                json.dumps(
                    {
                        key: value
                        for key, value in certificate.items()
                        if key != "certificate_sha256"
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest()
            scheduler_path.write_text(
                json.dumps(scheduler_assignment, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            scheduler_sha256 = hashlib.sha256(
                scheduler_path.read_bytes()
            ).hexdigest()
            trial["scheduler_assignment_sha256"] = scheduler_sha256
            trial_manifest_path.write_text(
                json.dumps(trial_manifest, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            runs_path = archive / "runs.jsonl"
            run_rows = [
                json.loads(line)
                for line in runs_path.read_text(encoding="utf-8").splitlines()
            ]
            for row in run_rows:
                if row["run_id"] == trial["run_id"]:
                    row["scheduler_assignment_sha256"] = scheduler_sha256
            runs_path.write_text(
                "".join(
                    json.dumps(row, sort_keys=True) + "\n" for row in run_rows
                ),
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            joined_errors = " ".join(result["errors"])
            self.assertIn("scheduler assignment exposure", joined_errors)
            self.assertIn("invalid decision trace", joined_errors)
            self.assertIn("executed the wrong parallel policy", joined_errors)
            self.assertIn(
                "scheduler trace audit trial_manifest_sha256 does not match trial_manifest_file",
                joined_errors,
            )

    def test_protocol_v6_requires_a_trusted_randomization_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
                general_protocol_version=6,
            )
            registration_key = root.parent / "trusted-registration-public.pem"
            registration_key_id = hashlib.sha256(
                public_key_der(registration_key)
            ).hexdigest()
            grader_keys = {}
            for grader_identity in ("expert-a", "expert-b"):
                grader_key = (
                    root.parent / f"trusted-{grader_identity}-public.pem"
                )
                grader_keys[
                    hashlib.sha256(public_key_der(grader_key)).hexdigest()
                ] = grader_key
            trace_key = root.parent / "trusted-trace-public.pem"
            trace_key_id = hashlib.sha256(
                public_key_der(trace_key)
            ).hexdigest()
            result = audit_experiment_archives(
                root,
                trusted_registration_keys={
                    registration_key_id: registration_key
                },
                trusted_trace_keys={trace_key_id: trace_key},
                trusted_grader_keys=grader_keys,
            )
            self.assertFalse(result["valid"])
            self.assertIn(
                "randomization receipt key is not present in the out-of-band trust set",
                " ".join(result["errors"]),
            )

    def test_protocol_v6_requires_a_role_separated_trace_auditor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
                general_protocol_version=6,
            )
            registration_key = root.parent / "trusted-registration-public.pem"
            registration_key_id = hashlib.sha256(
                public_key_der(registration_key)
            ).hexdigest()
            randomization_key = (
                root.parent / "trusted-randomization-public.pem"
            )
            randomization_key_id = hashlib.sha256(
                public_key_der(randomization_key)
            ).hexdigest()
            grader_keys = {}
            for grader_identity in ("expert-a", "expert-b"):
                grader_key = (
                    root.parent / f"trusted-{grader_identity}-public.pem"
                )
                grader_keys[
                    hashlib.sha256(public_key_der(grader_key)).hexdigest()
                ] = grader_key
            result = audit_experiment_archives(
                root,
                trusted_registration_keys={
                    registration_key_id: registration_key
                },
                trusted_randomization_keys={
                    randomization_key_id: randomization_key
                },
                trusted_grader_keys=grader_keys,
            )
            self.assertFalse(result["valid"])
            self.assertIn(
                "scheduler trace audit key is not present in the out-of-band trust set",
                " ".join(result["errors"]),
            )

    def test_protocol_v6_rejects_forged_randomness_and_derived_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
                general_protocol_version=6,
            )
            receipt_path = root / "protocol-case" / "randomization_receipt.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["payload"]["randomness_sha256"] = "0" * 64
            receipt_path.write_text(
                json.dumps(receipt, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            joined_errors = " ".join(result["errors"])
            self.assertIn("randomization receipt Ed25519 signature is invalid", joined_errors)
            self.assertIn("seed does not derive from the registered randomness", joined_errors)
            self.assertIn(
                "scheduler assignment does not match its registered condition",
                joined_errors,
            )

    def test_protocol_v6_rejects_a_locally_rewritten_trace_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
                general_protocol_version=6,
            )
            archive = root / "protocol-case"
            trial_manifest_path = archive / "trial_manifest.json"
            trial_manifest = json.loads(
                trial_manifest_path.read_text(encoding="utf-8")
            )
            trial = trial_manifest["trials"][0]
            scheduler_path = archive / trial["scheduler_assignment_file"]
            scheduler_document = json.loads(
                scheduler_path.read_text(encoding="utf-8")
            )
            scheduler_document["finalization"]["complete"] = False
            scheduler_path.write_text(
                json.dumps(scheduler_document, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            scheduler_sha256 = hashlib.sha256(
                scheduler_path.read_bytes()
            ).hexdigest()
            trial["scheduler_assignment_sha256"] = scheduler_sha256
            trial_manifest_path.write_text(
                json.dumps(trial_manifest, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            runs_path = archive / "runs.jsonl"
            run_rows = [
                json.loads(line)
                for line in runs_path.read_text(encoding="utf-8").splitlines()
            ]
            for row in run_rows:
                if row["run_id"] == trial["run_id"]:
                    row["scheduler_assignment_sha256"] = scheduler_sha256
            runs_path.write_text(
                "".join(
                    json.dumps(row, sort_keys=True) + "\n" for row in run_rows
                ),
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            joined_errors = " ".join(result["errors"])
            self.assertIn("scheduler trace finalization is inconsistent", joined_errors)
            self.assertIn(
                "scheduler trace audit trial_manifest_sha256 does not match trial_manifest_file",
                joined_errors,
            )

    def test_protocol_v6_schedule_prevents_postselected_run_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
                general_protocol_version=6,
            )
            manifest_path = root / "protocol-case" / "trial_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["trials"][0]["run_id"] = "postselected-replacement-run"
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            joined_errors = " ".join(result["errors"])
            self.assertIn(
                "assignment schedule does not exactly match the registered trial blocks",
                joined_errors,
            )
            self.assertIn(
                "scheduler trace audit trial_manifest_sha256 does not match trial_manifest_file",
                joined_errors,
            )

    def test_protocol_v6_rejects_condition_leakage_to_blinded_graders(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
                general_protocol_version=6,
            )
            archive = root / "protocol-case"
            trial_manifest = json.loads(
                (archive / "trial_manifest.json").read_text(encoding="utf-8")
            )
            grading_artifact_path = archive / trial_manifest["trials"][0][
                "grading_artifact_file"
            ]
            grading_artifact = json.loads(
                grading_artifact_path.read_text(encoding="utf-8")
            )
            grading_artifact["solution"] += " Executed under parallel-v18."
            grading_artifact_path.write_text(
                json.dumps(grading_artifact, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            self.assertIn(
                "blinded grading artifact reveals its condition",
                " ".join(result["errors"]),
            )

    def test_unknown_protocol_version_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(tmpdir, valid=True)
            protocol_path = root / "protocol-case" / "protocol_manifest.json"
            manifest = json.loads(protocol_path.read_text(encoding="utf-8"))
            manifest["protocol_version"] = 999
            protocol_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            self.assertIn(
                "protocol_version is unsupported", " ".join(result["errors"])
            )

    def test_mathematical_fingerprints_preserve_operators_and_long_suffixes(self) -> None:
        self.assertNotEqual(fingerprint_text("x < y"), fingerprint_text("x > y"))
        common = "a" * 700
        self.assertNotEqual(
            fingerprint_text(common + " + b"),
            fingerprint_text(common + " - b"),
        )

    def test_checked_in_experiment_archives_are_registered_and_not_overclaimed(self) -> None:
        experiments_root = Path(__file__).resolve().parents[3] / "experiments"
        result = audit_experiment_archives(experiments_root)
        self.assertTrue(result["valid"], result["errors"])
        self.assertTrue(result["archives"])
        for archive in result["archives"].values():
            if archive["status"] == "historical_unvalidated":
                self.assertFalse(archive["general_performance_evidence"])

    def test_historical_archive_fixture_is_registered_and_not_overclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "historical-case"
            archive.mkdir()
            evidence = b"Synthetic historical evidence fixture.\n"
            (archive / "evidence.txt").write_bytes(evidence)
            (archive / "SHA256SUMS").write_text(
                f"{hashlib.sha256(evidence).hexdigest()}  evidence.txt\n",
                encoding="utf-8",
            )
            (root / "archive_status.json").write_text(
                json.dumps({
                    "registry_version": 1,
                    "archives": {"historical-case": "historical_unvalidated"},
                }),
                encoding="utf-8",
            )
            result = audit_experiment_archives(root)
            self.assertTrue(result["valid"], result["errors"])
            self.assertEqual(set(result["archives"]), {"historical-case"})
            self.assertFalse(
                result["archives"]["historical-case"]["general_performance_evidence"]
            )

    def test_empty_archive_registry_contains_no_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "archive_status.json").write_text(
                json.dumps({"registry_version": 1, "archives": {}}),
                encoding="utf-8",
            )
            self.assertEqual(
                audit_experiment_archives(root),
                {"valid": True, "errors": [], "archives": {}},
            )

    def test_protocol_validated_case_study_is_not_general_performance_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._audit_protocol_root(
                self._protocol_archive(tmpdir, valid=True)
            )
            self.assertTrue(result["valid"], result["errors"])
            archive = result["archives"]["protocol-case"]
            self.assertTrue(archive["protocol_validated"])
            self.assertFalse(
                archive["general_performance_evidence"]
            )

    def test_protocol_archive_rejects_symbolic_link_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(tmpdir, valid=True)
            archive = root / "protocol-case"
            prompt = archive / "prompt.txt"
            prompt.unlink()
            prompt.symlink_to("problem.md")
            self._refresh_protocol_hashes(root)

            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            self.assertTrue(
                any("symbolic link" in error for error in result["errors"]),
                result["errors"],
            )

    def test_general_and_novelty_evidence_require_complete_repeated_designs(self) -> None:
        for evidence_scope, novelty_expected in (
            ("general_performance", False),
            ("novelty_and_performance", True),
        ):
            with self.subTest(evidence_scope=evidence_scope), tempfile.TemporaryDirectory() as tmpdir:
                result = self._audit_protocol_root(
                    self._protocol_archive(
                        tmpdir,
                        valid=True,
                        evidence_scope=evidence_scope,
                    )
                )
                self.assertTrue(result["valid"], result["errors"])
                archive = result["archives"]["protocol-case"]
                self.assertTrue(archive["general_performance_evidence"])
                self.assertEqual(novelty_expected, archive["novelty_evidence"])

    def test_general_evidence_requires_an_out_of_band_registration_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
            )
            result = audit_experiment_archives(root)
            self.assertFalse(result["valid"])
            self.assertIn(
                "not present in the out-of-band trust set",
                " ".join(result["errors"]),
            )

    def test_general_evidence_requires_out_of_band_grader_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
            )
            registration_key = root.parent / "trusted-registration-public.pem"
            registration_key_id = hashlib.sha256(
                public_key_der(registration_key)
            ).hexdigest()
            result = audit_experiment_archives(
                root,
                trusted_registration_keys={
                    registration_key_id: registration_key
                },
            )
            self.assertFalse(result["valid"])
            self.assertIn(
                "independent grader expert-a key is not present in the out-of-band trust set",
                " ".join(result["errors"]),
            )

    def test_general_evidence_rejects_a_forged_grader_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
            )
            archive = root / "protocol-case"
            grade_path = archive / "grade.json"
            grade = json.loads(grade_path.read_text(encoding="utf-8"))
            grade["graders"][0]["signature"]["value_base64"] = (
                base64.b64encode(b"forged-signature").decode("ascii")
            )
            grade_path.write_text(
                json.dumps(grade, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            self.assertIn(
                "independent grader expert-a Ed25519 signature is invalid",
                " ".join(result["errors"]),
            )

    def test_one_run_cannot_be_relabelled_as_general_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(tmpdir, valid=True)
            archive = root / "protocol-case"
            protocol_path = archive / "protocol_manifest.json"
            manifest = json.loads(protocol_path.read_text(encoding="utf-8"))
            manifest["evidence_scope"] = "general_performance"
            protocol_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            checksum_path = archive / "SHA256SUMS"
            checksum_lines = []
            for raw in checksum_path.read_text(encoding="utf-8").splitlines():
                _, separator, relative = raw.partition("  ")
                self.assertTrue(separator)
                target = archive / relative
                checksum_lines.append(
                    f"{hashlib.sha256(target.read_bytes()).hexdigest()}  {relative}"
                )
            checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            self.assertFalse(
                result["archives"]["protocol-case"]["general_performance_evidence"]
            )
            self.assertIn("preregistration_file must name a file", " ".join(result["errors"]))

    def test_registered_trial_prompts_are_scanned_for_reference_answer_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
            )
            archive = root / "protocol-case"
            prompt_path = archive / "trial_prompts" / "problem-0.txt"
            prompt_path.write_bytes(
                prompt_path.read_bytes() + (archive / "answer.txt").read_bytes()
            )
            prompt_sha = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
            trial_path = archive / "trial_manifest.json"
            trial_manifest = json.loads(trial_path.read_text(encoding="utf-8"))
            for trial in trial_manifest["trials"]:
                if trial["prompt_file"] == "trial_prompts/problem-0.txt":
                    trial["prompt_sha256"] = prompt_sha
            trial_path.write_text(
                json.dumps(trial_manifest, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            run_path = archive / "runs.jsonl"
            run_rows = [json.loads(line) for line in run_path.read_text(encoding="utf-8").splitlines()]
            for row in run_rows:
                if row["problem_id"] == "held-out-0":
                    row["prompt_sha256"] = prompt_sha
            run_path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in run_rows),
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            self.assertIn(
                "reference answer content appears in a registered trial prompt",
                " ".join(result["errors"]),
            )

    def test_general_evidence_binds_actual_selection_and_analysis_plans(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
            )
            archive = root / "protocol-case"
            selection_rule = archive / "selection_rule.json"
            selection_rule.write_text(
                json.dumps({"conditions": ["unregistered-replacement"]}) + "\n",
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            self.assertIn(
                "selection_rule_sha256 does not match selection_rule_file",
                " ".join(result["errors"]),
            )

    def test_general_evidence_rejects_incomplete_matched_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
            )
            archive = root / "protocol-case"
            removed_run_id = "general-0-1-control_v2"
            trial_path = archive / "trial_manifest.json"
            trial_manifest = json.loads(trial_path.read_text(encoding="utf-8"))
            trial_manifest["trials"] = [
                trial
                for trial in trial_manifest["trials"]
                if trial["run_id"] != removed_run_id
            ]
            trial_path.write_text(
                json.dumps(trial_manifest, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            run_path = archive / "runs.jsonl"
            run_rows = [
                json.loads(line)
                for line in run_path.read_text(encoding="utf-8").splitlines()
            ]
            run_path.write_text(
                "".join(
                    json.dumps(row, sort_keys=True) + "\n"
                    for row in run_rows
                    if row["run_id"] != removed_run_id
                ),
                encoding="utf-8",
            )
            for relative in ("grade.json", "scoreboard.json"):
                path = archive / relative
                document = json.loads(path.read_text(encoding="utf-8"))
                if relative == "grade.json":
                    document["run_labels"].pop(removed_run_id)
                    for labels in document["grader_labels"].values():
                        labels.pop(removed_run_id)
                else:
                    document["labels"].pop(removed_run_id)
                path.write_text(
                    json.dumps(document, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            analysis_path = archive / "analysis.json"
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            analysis["confidence_intervals"]["success_rate_difference"][
                "n_trials"
            ] = 59
            analysis_path.write_text(
                json.dumps(analysis, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            self.assertIn(
                "does not contain every preregistered condition exactly once",
                " ".join(result["errors"]),
            )

    def test_general_evidence_recomputes_the_preregistered_point_estimate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
            )
            archive = root / "protocol-case"
            analysis_path = archive / "analysis.json"
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            analysis["confidence_intervals"]["success_rate_difference"].update(
                estimate=0.5,
                lower=0.3,
                upper=0.7,
            )
            analysis_path.write_text(
                json.dumps(analysis, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            self.assertIn(
                "does not match the registered outcomes",
                " ".join(result["errors"]),
            )

    def test_general_evidence_replays_preregistered_block_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._protocol_archive(
                tmpdir,
                valid=True,
                evidence_scope="general_performance",
            )
            archive = root / "protocol-case"
            trial_path = archive / "trial_manifest.json"
            trial_manifest = json.loads(trial_path.read_text(encoding="utf-8"))
            target_run_id = "general-0-1-albilich_v3"
            for trial in trial_manifest["trials"]:
                if trial["run_id"] == target_run_id:
                    trial["execution_order"] = 1 - trial["execution_order"]
            trial_path.write_text(
                json.dumps(trial_manifest, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            run_path = archive / "runs.jsonl"
            run_rows = [
                json.loads(line)
                for line in run_path.read_text(encoding="utf-8").splitlines()
            ]
            for row in run_rows:
                if row["run_id"] == target_run_id:
                    row["execution_order"] = 1 - row["execution_order"]
            run_path.write_text(
                "".join(
                    json.dumps(row, sort_keys=True) + "\n" for row in run_rows
                ),
                encoding="utf-8",
            )
            self._refresh_protocol_hashes(root)
            result = self._audit_protocol_root(root)
            self.assertFalse(result["valid"])
            self.assertIn(
                "execution order does not match its preregistered randomization",
                " ".join(result["errors"]),
            )

    def test_protocol_validated_archive_rejects_mismatch_leakage_and_self_grade(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._audit_protocol_root(
                self._protocol_archive(tmpdir, valid=False)
            )
            self.assertFalse(result["valid"])
            errors = " ".join(result["errors"])
            self.assertIn("prompt problem does not exactly match", errors)
            self.assertIn("reference answer was agent-visible", errors)
            self.assertIn("independent grade must set independent=true", errors)
            self.assertIn("scoreboard label lacks an identical independent grade", errors)


if __name__ == "__main__":
    unittest.main()

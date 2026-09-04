from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.codex_runner import AggregateProcessTreeRSSGovernor
from agents.generation.phase2.dispatch_execution import (
    CUSTOM_EXECUTOR_AGGREGATE_RSS_CAPABILITY,
    CUSTOM_EXECUTOR_CONCURRENCY_ATTRIBUTE,
    CUSTOM_EXECUTOR_PARALLEL_CAPABILITY,
    CUSTOM_EXECUTOR_RESOURCE_ATTRIBUTE,
    execution_contract_errors,
    execution_resource_result_errors,
)
from agents.generation.phase2.invariants import validate_conn
from agents.generation.phase2.patches import apply_operator_patch as apply_patch, apply_system_patch
from agents.generation.phase2.parallel_exchange import authenticated_parallel_signals
from agents.generation.phase2.replay import verify_patch_journal
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.steering import (
    authenticated_snapshot as steering_snapshot,
    mark_authenticated_consumed,
    submit_operator_steering,
)
from agents.generation.phase2.workflow import (
    CUSTOM_EXECUTOR_IDENTITY_ATTRIBUTE,
    CUSTOM_EXECUTOR_RECOVERY_ATTRIBUTE,
    CUSTOM_EXECUTOR_RECOVERY_CAPABILITY,
    _ConsoleWriteThrottle,
    _WorkflowAlreadyExecuting,
    _WorkflowExecutionLock,
    _blocked_by_pending_priority_barrier,
    _merge_priority,
    _partition_recovery_results,
    _record_parallel_signals,
    _record_execution_metrics,
    _rebase_parallel_patch_if_safe,
    _remaining_wall_seconds,
    _recoverable_parallel_stale_patch,
    _stable_next_action,
    _stop_writer_safety_blocker,
    run_workflow,
)


class WorkflowOutageBreakerTests(unittest.TestCase):
    def test_capability_declared_custom_executor_runs_parallel_under_shared_rss(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-parallel-custom-capability",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            governor = AggregateProcessTreeRSSGovernor(100.0)
            rendezvous = threading.Barrier(2, timeout=5)
            participants: list[str] = []
            participants_lock = threading.Lock()

            def executor(
                *,
                action,
                stop_event,
                aggregate_rss_governor,
                **_kwargs,
            ):
                participant = str(action["target_id"])
                self.assertIs(governor, aggregate_rss_governor)
                aggregate_rss_governor.observe(
                    participant,
                    10.0,
                    stop_event=stop_event,
                )
                rendezvous.wait()
                with participants_lock:
                    participants.append(participant)
                aggregate_rss_governor.release(participant)
                return {"status": "completed", "failure_kind": ""}

            setattr(
                executor,
                CUSTOM_EXECUTOR_CONCURRENCY_ATTRIBUTE,
                CUSTOM_EXECUTOR_PARALLEL_CAPABILITY,
            )
            setattr(
                executor,
                CUSTOM_EXECUTOR_RESOURCE_ATTRIBUTE,
                CUSTOM_EXECUTOR_AGGREGATE_RSS_CAPABILITY,
            )
            contract = workflow_mod._workflow_execution_contract(
                executor=executor,
                model_profile="default",
                model="fake",
                reasoning_effort="low",
                codex_bin="codex",
                sandbox="read-only",
                web_search="disabled",
                research_mode="balanced",
                timeout_sec=5,
                max_context_chars=8_000,
                max_aggregate_child_rss_mb=100.0,
            )
            self.assertEqual(
                CUSTOM_EXECUTOR_PARALLEL_CAPABILITY,
                contract["concurrency_capability"],
            )
            self.assertEqual(
                "local_supervisor",
                contract["aggregate_process_tree_rss_enforcement"],
            )
            self.assertEqual([], execution_contract_errors(contract))
            scheduled = [
                {
                    "action": {"mode": "prove", "target_id": "primary"},
                    "session_plan": {},
                    "session_web_search": "",
                    "is_companion": False,
                },
                {
                    "action": {"mode": "refute", "target_id": "companion"},
                    "session_plan": {},
                    "session_web_search": "",
                    "is_companion": True,
                },
            ]
            results = workflow_mod._execute_scheduled_sessions(
                store,
                scheduled,
                model="fake",
                reasoning_effort="low",
                model_profile="default",
                codex_bin="codex",
                sandbox="read-only",
                timeout_sec=5,
                executor=executor,
                aggregate_rss_governor=governor,
            )

            self.assertEqual(2, len(results))
            self.assertEqual({"primary", "companion"}, set(participants))

    def test_parallel_custom_capability_requires_cancellation_and_rss_contracts(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        def executor(*, store, action, session_plan):
            return {}

        setattr(
            executor,
            CUSTOM_EXECUTOR_CONCURRENCY_ATTRIBUTE,
            CUSTOM_EXECUTOR_PARALLEL_CAPABILITY,
        )
        with self.assertRaisesRegex(ValueError, "stop_event"):
            workflow_mod._custom_executor_supports_parallel(executor)

    def test_unverified_external_executor_ignores_unused_local_rss_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"ALBILICH_MAX_AGGREGATE_CHILD_RSS_MB": "invalid"},
        ):
            store = ProofStateStore(
                "workflow-external-rss-config-isolation",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")

            result = run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                write_on_stop=False,
                write_console=False,
                executor=lambda **_kwargs: self._failed_execution(
                    "external-rss-config-isolation"
                ),
            )

            self.assertEqual(
                "failed",
                result["steps"][0]["action_results"][0]["status"],
            )

    def test_execution_contract_v2_distinguishes_local_and_external_limits(self) -> None:
        builtin = {
            "version": 2,
            "driver": "builtin_codex",
            "identity": "codex:/opt/codex:sha256",
            "recovery_capability": "supervised_process",
            "concurrency_capability": "thread_safe_cancellable_v1",
            "aggregate_process_tree_rss_enforcement": "local_supervisor",
            "max_aggregate_child_process_tree_rss_mb": 1024.0,
        }
        external = {
            "version": 2,
            "driver": "custom",
            "identity": "",
            "recovery_capability": "none",
            "concurrency_capability": "serial",
            "aggregate_process_tree_rss_enforcement": (
                "external_executor_unverified"
            ),
            "max_aggregate_child_process_tree_rss_mb": None,
        }
        local_custom = {
            **external,
            "concurrency_capability": "thread_safe_cancellable_v1",
            "aggregate_process_tree_rss_enforcement": "local_supervisor",
            "max_aggregate_child_process_tree_rss_mb": 1024.0,
        }
        self.assertEqual([], execution_contract_errors(builtin))
        self.assertEqual([], execution_contract_errors(external))
        self.assertEqual([], execution_contract_errors(local_custom))
        valid_resource_result = {
            "observed_aggregate_peak_memory_mb": 800.0,
            "resource_limits": {
                "max_aggregate_child_process_tree_rss_mb": 1024.0,
            },
        }
        self.assertEqual(
            [],
            execution_resource_result_errors(builtin, valid_resource_result),
        )
        self.assertEqual(
            [],
            execution_resource_result_errors(external, {}),
        )
        self.assertEqual(
            [],
            execution_resource_result_errors(
                local_custom,
                valid_resource_result,
            ),
        )
        self.assertTrue(
            execution_resource_result_errors(
                builtin,
                {
                    **valid_resource_result,
                    "resource_limits": {
                        "max_aggregate_child_process_tree_rss_mb": 2048.0,
                    },
                },
            )
        )
        self.assertTrue(
            execution_resource_result_errors(
                builtin,
                {
                    **valid_resource_result,
                    "observed_aggregate_peak_memory_mb": float("nan"),
                },
            )
        )
        self.assertEqual(
            [],
            execution_contract_errors(
                {
                    "version": 1,
                    "driver": "custom",
                    "recovery_capability": "none",
                }
            ),
        )
        invalid_contracts = (
            {**builtin, "max_aggregate_child_process_tree_rss_mb": None},
            {
                **external,
                "aggregate_process_tree_rss_enforcement": "local_supervisor",
            },
            {
                **external,
                "recovery_capability": "idempotent_by_scheduler_dispatch_id",
            },
            {
                **external,
                "concurrency_capability": "thread_safe_cancellable_v1",
            },
            {**builtin, "version": True},
        )
        for contract in invalid_contracts:
            with self.subTest(contract=contract):
                self.assertTrue(execution_contract_errors(contract))

    def test_parallel_builtin_sessions_share_aggregate_rss_cancellation(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-shared-aggregate-rss",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            governor = AggregateProcessTreeRSSGovernor(100.0)
            rendezvous = threading.Barrier(2, timeout=5)
            observed: list[tuple[str, bool, bool]] = []
            observed_lock = threading.Lock()

            def supervised_session(
                _store,
                action,
                _session_plan,
                *,
                stop_event,
                aggregate_rss_governor,
                **_kwargs,
            ):
                participant = str(action["target_id"])
                self.assertIs(governor, aggregate_rss_governor)
                _total, tripped_at_observation = aggregate_rss_governor.observe(
                    participant,
                    60.0,
                    stop_event=stop_event,
                )
                rendezvous.wait()
                with observed_lock:
                    observed.append(
                        (
                            participant,
                            tripped_at_observation,
                            stop_event.is_set(),
                        )
                    )
                aggregate_rss_governor.release(participant)
                return {"status": "completed", "failure_kind": ""}

            scheduled = [
                {
                    "action": {"mode": "prove", "target_id": "primary"},
                    "session_plan": {},
                    "session_web_search": "",
                    "is_companion": False,
                },
                {
                    "action": {"mode": "refute", "target_id": "companion"},
                    "session_plan": {},
                    "session_web_search": "",
                    "is_companion": True,
                },
            ]
            with patch.object(
                workflow_mod,
                "execute_session",
                side_effect=supervised_session,
            ):
                results = workflow_mod._execute_scheduled_sessions(
                    store,
                    scheduled,
                    model="fake",
                    reasoning_effort="low",
                    model_profile="default",
                    codex_bin="codex",
                    sandbox="read-only",
                    timeout_sec=5,
                    executor=None,
                    aggregate_rss_governor=governor,
                )

            self.assertEqual(2, len(results))
            self.assertEqual({"primary", "companion"}, {item[0] for item in observed})
            self.assertTrue(any(item[1] for item in observed))
            self.assertTrue(all(item[2] for item in observed))
            self.assertEqual(0, governor.snapshot()["participant_count"])
            self.assertTrue(governor.snapshot()["tripped"])

    @staticmethod
    def _failed_execution(run_id: str) -> dict:
        return {
            "run_id": run_id,
            "status": "failed",
            "returncode": 1,
            "wall_time_seconds": 0.01,
            "peak_memory_mb": 1.0,
            "usage": {"input_tokens": 1, "total_tokens": 1},
            "session_id": "",
            "patch": None,
            "patch_error": "simulated child failure",
            "failure_kind": "test_failure",
            "output_artifact_ids": [],
            "model": "fake",
            "reasoning_effort": "low",
            "sandbox": "workspace-write",
            "web_search": "disabled",
        }

    def test_branch_workbench_startup_error_aborts_before_executor_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-branch-sync-fail-closed",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            launches: list[dict] = []

            def executor(**kwargs):
                launches.append(dict(kwargs))
                return self._failed_execution("must-not-launch")

            with patch(
                "agents.generation.phase2.workflow.sync_branch_workbenches",
                side_effect=ValueError("malformed branch state"),
            ):
                with self.assertRaisesRegex(ValueError, "malformed branch state"):
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

            self.assertEqual([], launches)
            self.assertEqual("stopped", store.get_run_status())
            with store.connect() as conn:
                aborted = conn.execute(
                    "SELECT payload_json FROM events "
                    "WHERE event_type = 'workflow_aborted' "
                    "ORDER BY event_id DESC LIMIT 1"
                ).fetchone()
            self.assertIsNotNone(aborted)
            self.assertEqual(
                "ValueError",
                json.loads(aborted["payload_json"])["exception_type"],
            )

    def test_unlinked_dispatch_is_recovered_without_a_second_decision(self) -> None:
        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-dispatch-recovery",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")

            def crashing_executor(**_kwargs):
                raise SimulatedOrchestratorCrash

            setattr(
                crashing_executor,
                CUSTOM_EXECUTOR_RECOVERY_ATTRIBUTE,
                CUSTOM_EXECUTOR_RECOVERY_CAPABILITY,
            )
            setattr(
                crashing_executor,
                CUSTOM_EXECUTOR_IDENTITY_ATTRIBUTE,
                "dispatch-recovery-test-backend",
            )

            with self.assertRaises(SimulatedOrchestratorCrash):
                run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                    executor=crashing_executor,
                )
            with store.connect() as conn:
                original = conn.execute(
                    "SELECT dispatch_id, dispatched_action_json "
                    "FROM scheduler_dispatches"
                ).fetchone()
                self.assertIsNotNone(original["dispatched_action_json"])

            calls: list[str] = []

            def recovering_executor(*, session_plan, **_kwargs):
                calls.append(str(session_plan["scheduler_dispatch_id"]))
                return self._failed_execution("recovered-run")

            setattr(
                recovering_executor,
                CUSTOM_EXECUTOR_RECOVERY_ATTRIBUTE,
                CUSTOM_EXECUTOR_RECOVERY_CAPABILITY,
            )
            setattr(
                recovering_executor,
                CUSTOM_EXECUTOR_IDENTITY_ATTRIBUTE,
                "dispatch-recovery-test-backend",
            )
            result = run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                write_on_stop=False,
                write_console=False,
                executor=recovering_executor,
            )
            self.assertTrue(result["steps"][0]["dispatch_recovery"])
            self.assertEqual([original["dispatch_id"]], calls)
            with store.connect() as conn:
                self.assertEqual(
                    1,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM scheduler_dispatches"
                    ).fetchone()["n"],
                )
                run = conn.execute(
                    "SELECT scheduler_dispatch_id FROM runs "
                    "WHERE run_id = 'recovered-run'"
                ).fetchone()
                self.assertEqual(original["dispatch_id"], run["scheduler_dispatch_id"])
            self.assertTrue(verify_patch_journal(store)["valid"])

    def test_returned_result_is_recovered_without_reinvoking_executor(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-returned-result-recovery",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            calls = 0

            def executor(**_kwargs):
                nonlocal calls
                calls += 1
                return self._failed_execution("returned-before-crash")

            original_record = workflow_mod._record_scheduler_result

            def record_then_crash(*args, **kwargs):
                original_record(*args, **kwargs)
                raise SimulatedOrchestratorCrash

            with patch.object(
                workflow_mod,
                "_record_scheduler_result",
                side_effect=record_then_crash,
            ):
                with self.assertRaises(SimulatedOrchestratorCrash):
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
            self.assertEqual(1, calls)
            with store.connect() as conn:
                self.assertEqual(
                    1,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM scheduler_dispatch_attempts"
                    ).fetchone()["n"],
                )
                self.assertEqual(
                    1,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM scheduler_dispatch_results"
                    ).fetchone()["n"],
                )
                self.assertEqual(
                    0, conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
                )
                reserved_run_id = str(
                    conn.execute(
                        "SELECT run_id FROM scheduler_dispatch_results"
                    ).fetchone()["run_id"]
                )

            competing = apply_system_patch(
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
                            "run_id": reserved_run_id,
                            "actor_role": "scheduler",
                            "mode": "prove",
                            "target_id": "root",
                            "selection_design": "observational",
                            "status": "failed",
                        }
                    ],
                    "rationale": "attempt to take a reserved result run id",
                },
            )
            self.assertFalse(competing.accepted)
            self.assertTrue(
                any("reserved by a different" in error for error in competing.errors),
                competing.errors,
            )

            replacement_calls = 0

            def must_not_run(**_kwargs):
                nonlocal replacement_calls
                replacement_calls += 1
                return self._failed_execution("duplicate")

            result = run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                write_on_stop=False,
                write_console=False,
                executor=must_not_run,
            )
            self.assertEqual(0, replacement_calls)
            self.assertTrue(result["steps"][0]["dispatch_recovery"])
            self.assertIn(
                "result-", result["steps"][0]["scheduler_result_ids"][0]
            )
            with store.connect() as conn:
                self.assertEqual(
                    1, conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
                )
            self.assertTrue(verify_patch_journal(store)["valid"])

    def test_parallel_result_transaction_reserves_duplicate_run_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-result-run-id-reservation",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")

            def duplicate_run_id_executor(*, session_plan, **_kwargs):
                return {
                    **self._failed_execution("executor-shared-run-id"),
                    "actor_role": session_plan["actor_role"],
                }

            result = run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=True,
                parallel_branches=5,
                write_on_stop=False,
                write_console=False,
                stop_on_rejection=False,
                executor=duplicate_run_id_executor,
                research_mode="hard_problem",
                web_search="live",
            )
            action_results = result["steps"][0]["action_results"]
            self.assertGreater(len(action_results), 1)
            with store.connect() as conn:
                receipts = conn.execute(
                    "SELECT run_id, execution_json FROM scheduler_dispatch_results "
                    "ORDER BY rowid"
                ).fetchall()
                runs = conn.execute("SELECT run_id FROM runs").fetchall()
            receipt_run_ids = [str(row["run_id"]) for row in receipts]
            self.assertEqual(len(action_results), len(receipt_run_ids))
            self.assertEqual(len(receipt_run_ids), len(set(receipt_run_ids)))
            self.assertEqual(
                set(receipt_run_ids),
                {str(row["run_id"]) for row in runs},
            )
            self.assertEqual(1, receipt_run_ids.count("executor-shared-run-id"))
            remapped = [
                json.loads(str(row["execution_json"]))
                for row in receipts
                if str(row["run_id"]) != "executor-shared-run-id"
            ]
            self.assertTrue(remapped)
            self.assertTrue(
                all(
                    item.get("executor_run_id") == "executor-shared-run-id"
                    and str(item.get("run_id") or "").startswith("run-dispatch-")
                    for item in remapped
                ),
                remapped,
            )
            self.assertTrue(verify_patch_journal(store)["valid"])

    def test_result_receipt_body_tampering_fails_audit_and_recovery(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-result-receipt-tamper",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            original_record = workflow_mod._record_scheduler_result

            def record_then_crash(*args, **kwargs):
                original_record(*args, **kwargs)
                raise SimulatedOrchestratorCrash

            with patch.object(
                workflow_mod,
                "_record_scheduler_result",
                side_effect=record_then_crash,
            ):
                with self.assertRaises(SimulatedOrchestratorCrash):
                    run_workflow(
                        store,
                        steps=1,
                        execute=True,
                        parallel_librarian_verifier=False,
                        parallel_branches=0,
                        write_on_stop=False,
                        write_console=False,
                        executor=lambda **_kwargs: self._failed_execution(
                            "tamper-target"
                        ),
                    )
            with store.connect() as conn:
                store._drop_scheduler_history_guards(conn)
                conn.execute(
                    "UPDATE scheduler_dispatch_results SET execution_json = ?",
                    (json.dumps({"run_id": "substituted-result"}),),
                )
                store._ensure_scheduler_history_guards(conn)
                conn.commit()
            with store.connect() as conn:
                conn.execute("BEGIN")
                errors = validate_conn(conn)
                conn.rollback()
            self.assertTrue(
                any("scheduler result" in error for error in errors), errors
            )
            replay = verify_patch_journal(store)
            self.assertFalse(replay["valid"])
            calls = 0

            def must_not_run(**_kwargs):
                nonlocal calls
                calls += 1
                return self._failed_execution("must-not-run")

            with self.assertRaisesRegex(RuntimeError, "receipt fails recovery"):
                run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                    executor=must_not_run,
                )
            self.assertEqual(0, calls)

    def test_recovery_rejects_changed_path_artifact_after_result_persistence(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-result-path-identity",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            staging = store.state_dir / "artifacts" / "staging"
            staging.mkdir(parents=True, exist_ok=True)
            source = staging / "durable-path-result.txt"
            original_bytes = b"version one\n"
            substituted_bytes = b"version two\n"
            self.assertEqual(len(original_bytes), len(substituted_bytes))
            source.write_bytes(original_bytes)

            def executor(*, action, session_plan, **_kwargs):
                role = str(session_plan["actor_role"])
                return {
                    **self._failed_execution("path-result-before-crash"),
                    "actor_role": role,
                    "status": "completed",
                    "returncode": 0,
                    "patch_error": "",
                    "patch": {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": session_plan["state_revision"],
                        "actor_role": role,
                        "target_id": str(action.get("target_id") or "root"),
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": "durable-path-result",
                                "artifact_type": "research_notebook",
                                "path": str(source),
                            }
                        ],
                        "rationale": "exercise staged-source receipt identity",
                    },
                }

            original_record = workflow_mod._record_scheduler_result

            def record_then_crash(*args, **kwargs):
                original_record(*args, **kwargs)
                raise SimulatedOrchestratorCrash

            with patch.object(
                workflow_mod, "action_patch_contract_errors", return_value=[]
            ), patch.object(
                workflow_mod,
                "_record_scheduler_result",
                side_effect=record_then_crash,
            ):
                with self.assertRaises(SimulatedOrchestratorCrash):
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

            source.write_bytes(substituted_bytes)
            replacement_calls = 0

            def must_not_run(**_kwargs):
                nonlocal replacement_calls
                replacement_calls += 1
                return self._failed_execution("duplicate")

            with patch.object(
                workflow_mod, "action_patch_contract_errors", return_value=[]
            ):
                recovered = run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                    executor=must_not_run,
                )
            self.assertEqual(0, replacement_calls)
            outcome = recovered["steps"][0]["patch_outcome"]
            self.assertFalse(outcome["accepted"])
            self.assertTrue(
                any("content changed since result persistence" in error for error in outcome["errors"]),
                outcome,
            )
            with store.connect() as conn:
                self.assertIsNone(
                    conn.execute(
                        "SELECT 1 FROM artifacts WHERE artifact_id = ?",
                        ("durable-path-result",),
                    ).fetchone()
                )
            self.assertTrue(verify_patch_journal(store)["valid"])

    def test_returned_proof_patch_is_applied_after_crash_status_events(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-returned-proof-recovery",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")

            def executor(*, action, session_plan, **_kwargs):
                role = str(session_plan["actor_role"])
                return {
                    **self._failed_execution("proof-returned-before-crash"),
                    "actor_role": role,
                    "status": "completed",
                    "returncode": 0,
                    "patch_error": "",
                    "patch": {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": session_plan["state_revision"],
                        "actor_role": role,
                        "target_id": str(action.get("target_id") or "root"),
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": "proof-returned-before-crash",
                                "artifact_type": "research_notebook",
                                "content": "A result durably returned before restart.",
                            }
                        ],
                        "rationale": "exercise post-return crash recovery",
                    },
                }

            original_record = workflow_mod._record_scheduler_result

            def record_then_crash(*args, **kwargs):
                original_record(*args, **kwargs)
                raise SimulatedOrchestratorCrash

            with patch.object(
                workflow_mod, "action_patch_contract_errors", return_value=[]
            ), patch.object(
                workflow_mod,
                "_record_scheduler_result",
                side_effect=record_then_crash,
            ):
                with self.assertRaises(SimulatedOrchestratorCrash):
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

            replacement_calls = 0

            def must_not_run(**_kwargs):
                nonlocal replacement_calls
                replacement_calls += 1
                return self._failed_execution("duplicate")

            with patch.object(
                workflow_mod, "action_patch_contract_errors", return_value=[]
            ):
                recovered = run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                    executor=must_not_run,
                )
            self.assertEqual(0, replacement_calls)
            self.assertTrue(recovered["steps"][0]["patch_outcome"]["accepted"])
            with store.connect() as conn:
                self.assertIsNotNone(
                    conn.execute(
                        "SELECT 1 FROM artifacts WHERE artifact_id = ?",
                        ("proof-returned-before-crash",),
                    ).fetchone()
                )
            self.assertTrue(verify_patch_journal(store)["valid"])

    def test_durable_result_does_not_override_operator_policy_change(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-result-policy-change",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            original_head = str(store.audit_chain_heads()["policy_event_head"])
            store.set_completion_policy(
                "partial_ok",
                reason="operator changed completion semantics",
                source="test",
            )
            recovered_head, errors = (
                workflow_mod._durable_result_recovery_policy_head(
                    store,
                    original_policy_head=original_head,
                )
            )
            self.assertEqual("", recovered_head)
            self.assertTrue(
                any("scheduler policy changed" in error for error in errors),
                errors,
            )

    def test_recovery_receipt_cannot_bypass_unreturned_verifier(self) -> None:
        receipt = {
            "action": {"mode": "prove", "search_intent": "parallel_direct_solve"},
            "session_plan": {
                "actor_role": "researcher",
                "scheduler_dispatch_id": "dispatch-companion",
            },
            "is_companion": True,
        }
        actions = [
            {"mode": "validate", "target_id": "root"},
            dict(receipt["action"]),
        ]
        dispatches = [
            {
                "dispatch_id": "dispatch-verifier",
                "actor_role": "strict_informal_verifier",
                "is_companion": False,
            },
            {
                "dispatch_id": "dispatch-companion",
                "actor_role": "researcher",
                "is_companion": True,
            },
        ]
        replayable, unreturned = _partition_recovery_results(
            [receipt], actions, dispatches
        )
        self.assertEqual([], replayable)
        self.assertEqual("dispatch-verifier", unreturned[0][1]["dispatch_id"])

        verifier_receipt = {
            "action": actions[0],
            "session_plan": {
                "actor_role": "strict_informal_verifier",
                "scheduler_dispatch_id": "dispatch-verifier",
            },
            "is_companion": False,
        }
        replayable, unreturned = _partition_recovery_results(
            [verifier_receipt], actions, dispatches
        )
        self.assertEqual([verifier_receipt], replayable)
        self.assertEqual("dispatch-companion", unreturned[0][1]["dispatch_id"])

    def test_completed_result_is_persisted_before_live_merge_barrier(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-pre-barrier-result-persistence",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")

            def declared_executor(**_kwargs):
                raise AssertionError("patched session runner should own this test")

            setattr(
                declared_executor,
                CUSTOM_EXECUTOR_RECOVERY_ATTRIBUTE,
                CUSTOM_EXECUTOR_RECOVERY_CAPABILITY,
            )
            setattr(
                declared_executor,
                CUSTOM_EXECUTOR_IDENTITY_ATTRIBUTE,
                "pre-barrier-test-backend",
            )

            def one_return_then_crash(
                _store, scheduled, *, result_callback, **_kwargs
            ):
                self.assertGreater(len(scheduled), 1)
                completed = {
                    **scheduled[-1],
                    "execution": {
                        **self._failed_execution("buffered-before-crash"),
                        "actor_role": scheduled[-1]["session_plan"]["actor_role"],
                    },
                }
                result_callback(completed)
                raise SimulatedOrchestratorCrash

            with patch.object(
                workflow_mod,
                "_execute_scheduled_sessions",
                side_effect=one_return_then_crash,
            ), patch.object(
                workflow_mod,
                "_blocked_by_pending_priority_barrier",
                return_value=True,
            ):
                with self.assertRaises(SimulatedOrchestratorCrash):
                    run_workflow(
                        store,
                        steps=1,
                        execute=True,
                        parallel_librarian_verifier=True,
                        parallel_branches=5,
                        write_on_stop=False,
                        write_console=False,
                        executor=declared_executor,
                        research_mode="hard_problem",
                        web_search="live",
                    )
            with store.connect() as conn:
                self.assertEqual(
                    1,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM scheduler_dispatch_results"
                    ).fetchone()["n"],
                )
                self.assertEqual(
                    0, conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
                )
            self.assertTrue(verify_patch_journal(store)["valid"])

    def test_accepted_result_patch_is_not_applied_twice_after_crash(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-accepted-result-recovery",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            calls = 0

            def executor(*, action, session_plan, **_kwargs):
                nonlocal calls
                calls += 1
                role = str(session_plan["actor_role"])
                return {
                    **self._failed_execution("accepted-before-crash"),
                    "actor_role": role,
                    "status": "completed",
                    "returncode": 0,
                    "patch_error": "",
                    "patch": {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": session_plan["state_revision"],
                        "actor_role": role,
                        "target_id": str(action.get("target_id") or "root"),
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": "durable-returned-artifact",
                                "artifact_type": "research_notebook",
                                "content": "A durable returned result.",
                            }
                        ],
                        "rationale": "exercise result recovery",
                    },
                }

            with patch.object(
                workflow_mod, "action_patch_contract_errors", return_value=[]
            ), patch.object(
                workflow_mod,
                "_record_execution_metrics",
                side_effect=SimulatedOrchestratorCrash,
            ):
                with self.assertRaises(SimulatedOrchestratorCrash):
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
            self.assertEqual(1, calls)
            with store.connect() as conn:
                accepted_patch = conn.execute(
                    "SELECT patch_id FROM patches WHERE patch_id LIKE "
                    "'dispatch-output-%' AND status = 'applied'"
                ).fetchone()
                self.assertIsNotNone(accepted_patch)
                self.assertEqual(
                    1,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM artifacts "
                        "WHERE artifact_id = 'durable-returned-artifact'"
                    ).fetchone()["n"],
                )
                self.assertEqual(
                    0, conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
                )

            replacement_calls = 0

            def must_not_run(**_kwargs):
                nonlocal replacement_calls
                replacement_calls += 1
                return self._failed_execution("duplicate")

            recovered = run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                write_on_stop=False,
                write_console=False,
                executor=must_not_run,
            )
            self.assertEqual(0, replacement_calls)
            self.assertTrue(
                recovered["steps"][0]["patch_outcome"][
                    "recovered_from_accepted_patch"
                ]
            )
            with store.connect() as conn:
                self.assertEqual(
                    1,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM artifacts "
                        "WHERE artifact_id = 'durable-returned-artifact'"
                    ).fetchone()["n"],
                )
                self.assertEqual(
                    1, conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
                )
            self.assertTrue(verify_patch_journal(store)["valid"])

    def test_unlinked_dispatch_refuses_custom_executor_without_idempotency(self) -> None:
        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-dispatch-recovery-refusal",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")

            def crashing_executor(**_kwargs):
                raise SimulatedOrchestratorCrash

            with self.assertRaises(SimulatedOrchestratorCrash):
                run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                    executor=crashing_executor,
                )

            calls = 0

            def unsafe_executor(**_kwargs):
                nonlocal calls
                calls += 1
                return self._failed_execution("must-not-run")

            result = run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                write_on_stop=False,
                write_console=False,
                executor=unsafe_executor,
            )
            self.assertEqual(0, calls)
            self.assertEqual("await_human", result["steps"][0]["action"]["mode"])
            self.assertEqual(
                "execution_configuration_required",
                result["steps"][0]["terminal_classification"],
            )
            with store.connect() as conn:
                self.assertEqual(
                    0, conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
                )
                self.assertEqual(
                    1,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM scheduler_dispatches"
                    ).fetchone()["n"],
                )

    def test_recovery_refuses_a_different_custom_executor_identity(self) -> None:
        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-dispatch-executor-mismatch",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")

            def original_executor(**_kwargs):
                raise SimulatedOrchestratorCrash

            setattr(
                original_executor,
                CUSTOM_EXECUTOR_RECOVERY_ATTRIBUTE,
                CUSTOM_EXECUTOR_RECOVERY_CAPABILITY,
            )
            setattr(
                original_executor,
                CUSTOM_EXECUTOR_IDENTITY_ATTRIBUTE,
                "original-backend",
            )
            with self.assertRaises(SimulatedOrchestratorCrash):
                run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                    executor=original_executor,
                )

            calls = 0

            def replacement_executor(**_kwargs):
                nonlocal calls
                calls += 1
                return self._failed_execution("must-not-run")

            setattr(
                replacement_executor,
                CUSTOM_EXECUTOR_RECOVERY_ATTRIBUTE,
                CUSTOM_EXECUTOR_RECOVERY_CAPABILITY,
            )
            setattr(
                replacement_executor,
                CUSTOM_EXECUTOR_IDENTITY_ATTRIBUTE,
                "different-backend",
            )
            result = run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                write_on_stop=False,
                write_console=False,
                executor=replacement_executor,
            )
            self.assertEqual(0, calls)
            self.assertEqual("await_human", result["steps"][0]["action"]["mode"])
            self.assertIn(
                "configuration differs", result["steps"][0]["stop_reason"]
            )

    def test_builtin_supervisor_recovers_its_exact_committed_action(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-builtin-dispatch-recovery",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            with patch.object(
                workflow_mod, "execute_session", side_effect=SimulatedOrchestratorCrash
            ):
                with self.assertRaises(SimulatedOrchestratorCrash):
                    run_workflow(
                        store,
                        steps=1,
                        execute=True,
                        parallel_librarian_verifier=False,
                        parallel_branches=0,
                        write_on_stop=False,
                        write_console=False,
                    )
            with store.connect() as conn:
                dispatch_id = conn.execute(
                    "SELECT dispatch_id FROM scheduler_dispatches"
                ).fetchone()["dispatch_id"]
            def recovered_builtin_session(*_args, **kwargs):
                governor = kwargs["aggregate_rss_governor"]
                return {
                    **self._failed_execution("builtin-recovered-run"),
                    "observed_aggregate_peak_memory_mb": 0.0,
                    "resource_limits": {
                        "max_aggregate_child_process_tree_rss_mb": (
                            governor.limit_mb
                        ),
                    },
                }

            with patch.object(
                workflow_mod,
                "execute_session",
                side_effect=recovered_builtin_session,
            ):
                result = run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                )
            self.assertTrue(result["steps"][0]["dispatch_recovery"])
            with store.connect() as conn:
                run = conn.execute(
                    "SELECT scheduler_dispatch_id FROM runs "
                    "WHERE run_id = 'builtin-recovered-run'"
                ).fetchone()
                self.assertEqual(dispatch_id, run["scheduler_dispatch_id"])

    def test_kernel_rejects_a_new_wave_while_a_dispatch_is_unlinked(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-no-overlapping-dispatch-groups",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")

            def crashing_executor(**_kwargs):
                raise SimulatedOrchestratorCrash

            with self.assertRaises(SimulatedOrchestratorCrash):
                run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                    executor=crashing_executor,
                )
            action, heads = _stable_next_action(
                store, research_mode="balanced", web_search="disabled"
            )
            with self.assertRaisesRegex(RuntimeError, "earlier dispatch group"):
                workflow_mod._record_scheduler_dispatches(
                    store,
                    [action],
                    heads,
                    execution_contract={
                        "version": 1,
                        "driver": "builtin_codex",
                        "identity": "codex:test",
                        "recovery_capability": "supervised_process",
                    },
                )
            with store.connect() as conn:
                self.assertEqual(
                    1,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM scheduler_dispatches"
                    ).fetchone()["n"],
                )

    def test_full_invariants_recompute_the_stored_recovery_action(self) -> None:
        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-recovery-action-integrity",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")

            with self.assertRaises(SimulatedOrchestratorCrash):
                run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                    executor=lambda **_kwargs: (_ for _ in ()).throw(
                        SimulatedOrchestratorCrash()
                    ),
                )
            with store.connect() as conn:
                conn.execute("BEGIN")
                store._drop_scheduler_history_guards(conn)
                conn.execute(
                    "UPDATE scheduler_dispatches SET dispatched_action_json = '{}'"
                )
                store._ensure_scheduler_history_guards(conn)
                errors = validate_conn(conn)
                replay = verify_patch_journal(store, conn=conn)
                conn.rollback()
            self.assertTrue(
                any("invalid recovery action" in error for error in errors), errors
            )
            self.assertFalse(replay["valid"])
            self.assertTrue(
                any("invalid recovery action" in error for error in replay["errors"]),
                replay["errors"],
            )

    def test_execution_lock_rejects_a_second_orchestrator_but_not_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-exclusive-execution",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            with _WorkflowExecutionLock(store):
                planned = run_workflow(
                    store,
                    steps=1,
                    execute=False,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_console=False,
                )
                self.assertFalse(planned["executed"])
                with self.assertRaises(_WorkflowAlreadyExecuting):
                    run_workflow(
                        store,
                        steps=1,
                        execute=True,
                        parallel_librarian_verifier=False,
                        parallel_branches=0,
                        write_on_stop=False,
                        write_console=False,
                        executor=lambda **_kwargs: self._failed_execution("locked"),
                    )

    def test_partial_parallel_wave_recovers_only_unlinked_companions(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-partial-wave-recovery",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            calls = 0

            def partial_executor(*, session_plan, **_kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise SimulatedOrchestratorCrash
                return self._failed_execution("completed-before-crash")

            setattr(
                partial_executor,
                CUSTOM_EXECUTOR_RECOVERY_ATTRIBUTE,
                CUSTOM_EXECUTOR_RECOVERY_CAPABILITY,
            )
            setattr(
                partial_executor,
                CUSTOM_EXECUTOR_IDENTITY_ATTRIBUTE,
                "partial-wave-test-backend",
            )

            with self.assertRaises(SimulatedOrchestratorCrash):
                run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=True,
                    parallel_branches=5,
                    write_on_stop=False,
                    write_console=False,
                    executor=partial_executor,
                    research_mode="hard_problem",
                    web_search="live",
                )
            with store.connect() as conn:
                dispatch_count = conn.execute(
                    "SELECT COUNT(*) AS n FROM scheduler_dispatches"
                ).fetchone()["n"]
                linked_before = conn.execute(
                    "SELECT scheduler_dispatch_id FROM runs"
                ).fetchone()["scheduler_dispatch_id"]
            self.assertGreater(dispatch_count, 1)

            recovered_ids: list[str] = []

            def recovery_executor(*, session_plan, **_kwargs):
                dispatch_id = str(session_plan["scheduler_dispatch_id"])
                recovered_ids.append(dispatch_id)
                return self._failed_execution(f"recovered-{dispatch_id}")

            setattr(
                recovery_executor,
                CUSTOM_EXECUTOR_RECOVERY_ATTRIBUTE,
                CUSTOM_EXECUTOR_RECOVERY_CAPABILITY,
            )
            setattr(
                recovery_executor,
                CUSTOM_EXECUTOR_IDENTITY_ATTRIBUTE,
                "partial-wave-test-backend",
            )
            recovered_group_sizes: list[int] = []
            original_apply = workflow_mod._apply_scheduled_results

            def capture_recovered_group_size(*args, **kwargs):
                recovered_group_sizes.extend(
                    int(item.get("parallel_group_size") or 0)
                    for item in args[1]
                )
                return original_apply(*args, **kwargs)

            with patch.object(
                workflow_mod,
                "_apply_scheduled_results",
                side_effect=capture_recovered_group_size,
            ):
                result = run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=True,
                    parallel_branches=5,
                    write_on_stop=False,
                    write_console=False,
                    executor=recovery_executor,
                    research_mode="hard_problem",
                    web_search="live",
                )
            self.assertTrue(result["steps"][0]["dispatch_recovery"])
            self.assertTrue(
                all(row["is_companion"] for row in result["steps"][0]["action_results"])
            )
            self.assertNotIn(linked_before, recovered_ids)
            self.assertEqual(dispatch_count - 1, len(recovered_ids))
            self.assertEqual(
                [dispatch_count] * (dispatch_count - 1),
                recovered_group_sizes,
            )
            with store.connect() as conn:
                self.assertEqual(
                    dispatch_count,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM scheduler_dispatches"
                    ).fetchone()["n"],
                )
                self.assertEqual(
                    dispatch_count,
                    conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"],
                )
            self.assertTrue(verify_patch_journal(store)["valid"])

    def test_dispatch_and_fairness_are_durable_before_executor_entry(self) -> None:
        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-durable-dispatch",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")

            def crashing_executor(*, store, action, session_plan, **_kwargs):
                with store.connect() as conn:
                    dispatch = conn.execute(
                        "SELECT * FROM scheduler_dispatches WHERE dispatch_id = ?",
                        (session_plan["scheduler_dispatch_id"],),
                    ).fetchone()
                    self.assertIsNotNone(dispatch)
                    self.assertEqual(
                        session_plan["scheduler_decision_state_revision"],
                        dispatch["decision_state_revision"],
                    )
                    self.assertGreater(
                        session_plan["state_revision"],
                        dispatch["decision_state_revision"],
                    )
                    self.assertEqual(
                        session_plan["scheduler_dispatch_id"],
                        conn.execute(
                            "SELECT updated_dispatch_id "
                            "FROM scheduler_decision_fairness_meta"
                        ).fetchone()["updated_dispatch_id"],
                    )
                    self.assertEqual(
                        0,
                        conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()[
                            "n"
                        ],
                    )
                raise SimulatedOrchestratorCrash

            with self.assertRaises(SimulatedOrchestratorCrash):
                run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                    executor=crashing_executor,
                )

            with store.connect() as conn:
                conn.execute("BEGIN")
                dispatch = conn.execute(
                    "SELECT dispatch_id FROM scheduler_dispatches"
                ).fetchone()
                self.assertIsNotNone(dispatch)
                self.assertEqual(
                    dispatch["dispatch_id"],
                    conn.execute(
                        "SELECT updated_dispatch_id "
                        "FROM scheduler_decision_fairness_meta"
                    ).fetchone()["updated_dispatch_id"],
                )
                self.assertEqual(
                    0,
                    conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"],
                )
                self.assertTrue(store.current_state_seal(conn)["valid"])
            replay = verify_patch_journal(store)
            self.assertTrue(replay["valid"], replay.get("errors"))
            with store.connect() as conn:
                store._drop_scheduler_history_guards(conn)
                conn.execute(
                    "UPDATE scheduler_dispatches SET dispatched_action_hash = ?",
                    ("0" * 64,),
                )
                store._ensure_scheduler_history_guards(conn)
                conn.commit()
            seal = store.current_state_seal()
            self.assertTrue(seal["valid"])
            with store.connect() as conn:
                conn.execute("BEGIN")
                invariant_errors = validate_conn(conn)
                conn.rollback()
            self.assertTrue(
                any(
                    "scheduler provenance entry" in error
                    or "disagrees with its decision trace" in error
                    for error in invariant_errors
                ),
                invariant_errors,
            )

    def test_completed_telemetry_links_to_dispatch_without_reapplying_fairness(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-dispatch-completion-link",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")

            def executor(*, store, action, session_plan, **_kwargs):
                return {
                    "run_id": "linked-run",
                    "status": "failed",
                    "returncode": 1,
                    "wall_time_seconds": 0.01,
                    "peak_memory_mb": 1.0,
                    "usage": {"input_tokens": 1, "total_tokens": 1},
                    "session_id": "",
                    "patch": None,
                    "patch_error": "simulated child failure",
                    "failure_kind": "test_failure",
                    "output_artifact_ids": [],
                    "model": "fake",
                    "reasoning_effort": "low",
                    "sandbox": "workspace-write",
                    "web_search": "disabled",
                }

            result = run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                write_on_stop=False,
                write_console=False,
                executor=executor,
            )
            self.assertTrue(
                result["steps"][0]["metrics_outcome"]["accepted"],
                result["steps"][0]["metrics_outcome"].get("errors"),
            )
            with store.connect() as conn:
                run = conn.execute(
                    "SELECT scheduler_dispatch_id, state_revision, context_revision, "
                    "decision_state_revision "
                    "FROM runs WHERE run_id = 'linked-run'"
                ).fetchone()
                dispatch = conn.execute(
                    "SELECT dispatch_id, decision_state_revision "
                    "FROM scheduler_dispatches"
                ).fetchone()
                fairness = conn.execute(
                    "SELECT updated_run_id, updated_dispatch_id "
                    "FROM scheduler_decision_fairness_meta"
                ).fetchone()
                self.assertEqual(dispatch["dispatch_id"], run["scheduler_dispatch_id"])
                self.assertEqual(
                    dispatch["decision_state_revision"],
                    run["decision_state_revision"],
                )
                self.assertEqual(run["context_revision"], run["state_revision"])
                self.assertGreater(
                    run["context_revision"], run["decision_state_revision"]
                )
                self.assertIsNone(fairness["updated_run_id"])
                self.assertEqual(dispatch["dispatch_id"], fairness["updated_dispatch_id"])
                self.assertIn(
                    "scheduler_dispatches",
                    {
                        str(row["table"])
                        for row in conn.execute("PRAGMA foreign_key_list(runs)")
                    },
                )

    def test_durable_result_authenticates_run_metrics(self) -> None:
        import agents.generation.phase2.workflow as workflow_module

        original_metrics_operation = workflow_module.run_metrics_operation

        def executor(*, session_plan, **_kwargs):
            return {
                "run_id": "authenticated-result-run",
                "status": "failed",
                "returncode": 1,
                "wall_time_seconds": 0.125,
                "peak_memory_mb": 2.5,
                "observed_aggregate_peak_memory_mb": 4.0,
                # Exercise the conservative total-only normalization as well
                # as the individual metric commitments.
                "usage": {"total_tokens": 7},
                "session_id": "session-authenticated",
                "patch": None,
                "patch_error": "synthetic authenticated failure",
                "failure_kind": "test_failure",
                "output_artifact_ids": ["uncommitted-output-must-not-be-linked"],
                "model": "model-authenticated",
                "reasoning_effort": "low",
                "sandbox": "workspace-write",
                "web_search": "disabled",
                "resource_limits": {
                    "max_aggregate_child_process_tree_rss_mb": 10.0,
                    "enforcement": "synthetic external test executor",
                },
            }

        tamper_cases = {
            "run_id": lambda op: op.update(run_id="forged-run-id"),
            "input_tokens": lambda op: op.update(
                input_tokens=int(op["input_tokens"]) + 1
            ),
            "wall_time_seconds": lambda op: op.update(
                wall_time_seconds=float(op["wall_time_seconds"]) + 1.0
            ),
            "session_id": lambda op: op.update(session_id="forged-session"),
            "model_profile": lambda op: op.update(model_profile="forged-profile"),
            "model": lambda op: op.update(model="forged-model"),
            "prompt_context_hash": lambda op: op.update(
                prompt_context_hash="forged-context"
            ),
            "strategy_family": lambda op: op.update(
                strategy_family="forged-strategy"
            ),
            "status": lambda op: op.update(status="completed"),
        }
        for field, mutate in tamper_cases.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmpdir:
                store = ProofStateStore(
                    f"durable-result-{field}",
                    generation_root=Path(tmpdir) / "generation",
                )
                store.init_problem("Target theorem.")

                def tampered_metrics_operation(**kwargs):
                    operation = original_metrics_operation(**kwargs)
                    mutate(operation)
                    return operation

                with patch.object(
                    workflow_module,
                    "run_metrics_operation",
                    side_effect=tampered_metrics_operation,
                ):
                    result = run_workflow(
                        store,
                        steps=1,
                        execute=True,
                        parallel_librarian_verifier=False,
                        parallel_branches=0,
                        write_on_stop=False,
                        write_console=False,
                        executor=executor,
                        web_search="disabled",
                    )
                metrics = result["steps"][0]["metrics_outcome"]
                self.assertFalse(metrics["accepted"], metrics)
                self.assertIn(field.replace("_", " ").split()[0], " ".join(metrics["errors"]))
                with store.connect() as conn:
                    self.assertEqual(
                        0,
                        conn.execute(
                            "SELECT COUNT(*) AS n FROM runs"
                        ).fetchone()["n"],
                    )

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "durable-result-valid",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            result = run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                write_on_stop=False,
                write_console=False,
                executor=executor,
                web_search="disabled",
            )
            metrics = result["steps"][0]["metrics_outcome"]
            self.assertTrue(metrics["accepted"], metrics.get("errors"))
            with store.connect() as conn:
                run = conn.execute(
                    "SELECT input_tokens, total_tokens, output_artifact_ids_json "
                    "FROM runs"
                ).fetchone()
                self.assertEqual(7, run["input_tokens"])
                self.assertEqual(7, run["total_tokens"])
                self.assertEqual([], json.loads(run["output_artifact_ids_json"]))
                durable_result = json.loads(
                    conn.execute(
                        "SELECT execution_json FROM scheduler_dispatch_results"
                    ).fetchone()["execution_json"]
                )
                self.assertEqual(
                    4.0,
                    durable_result["observed_aggregate_peak_memory_mb"],
                )
                self.assertEqual(
                    10.0,
                    durable_result["resource_limits"][
                        "max_aggregate_child_process_tree_rss_mb"
                    ],
                )
                execution_contract = json.loads(
                    conn.execute(
                        "SELECT execution_contract_json FROM scheduler_dispatches"
                    ).fetchone()["execution_contract_json"]
                )
                self.assertEqual(2, execution_contract["version"])
                self.assertEqual(
                    "external_executor_unverified",
                    execution_contract[
                        "aggregate_process_tree_rss_enforcement"
                    ],
                )
                self.assertEqual(
                    "serial",
                    execution_contract["concurrency_capability"],
                )
                self.assertIsNone(
                    execution_contract[
                        "max_aggregate_child_process_tree_rss_mb"
                    ]
                )

    def test_attempt_and_result_reject_session_plan_substitution(self) -> None:
        import agents.generation.phase2.workflow as workflow_module

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "session-plan-substitution",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            action, heads = _stable_next_action(
                store,
                research_mode="balanced",
                web_search="disabled",
            )
            dispatches, committed_heads = workflow_module._record_scheduler_dispatches(
                store,
                [action],
                heads,
                execution_contract={
                    "version": 1,
                    "driver": "custom",
                    "identity": "test:session-plan-binding",
                    "recovery_capability": "none",
                },
            )
            dispatch = dispatches[0]
            plan = {
                "actor_role": dispatch["actor_role"],
                "mode": dispatch["mode"],
                "target_id": dispatch["target_id"],
                "route_id": dispatch["route_id"],
                "state_revision": committed_heads["proof_revision"],
                "scheduler_decision_state_revision": dispatch[
                    "decision_state_revision"
                ],
                "scheduler_dispatch_id": dispatch["dispatch_id"],
                "dispatched_action_hash": dispatch["dispatched_action_hash"],
            }
            item = {
                "action": action,
                "session_plan": {**plan, "target_id": "substituted-target"},
                "is_companion": False,
            }
            with self.assertRaisesRegex(RuntimeError, "session plan target_id"):
                workflow_module._record_scheduler_attempts(store, [item])
            with store.connect() as conn:
                self.assertEqual(
                    0,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM scheduler_dispatch_attempts"
                    ).fetchone()["n"],
                )

            item["session_plan"] = dict(plan)
            workflow_module._record_scheduler_attempts(store, [item])
            item["session_plan"] = {**plan, "route_id": "substituted-route"}
            item["execution"] = {
                "run_id": "must-not-persist",
                "status": "failed",
                "usage": {},
                "patch": None,
            }
            with self.assertRaisesRegex(RuntimeError, "changed its claimed session plan"):
                workflow_module._record_scheduler_result(
                    store,
                    item,
                    validation_errors=[],
                )
            with store.connect() as conn:
                self.assertEqual(
                    0,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM scheduler_dispatch_results"
                    ).fetchone()["n"],
                )

    def test_attempt_rejects_context_changed_before_executor_entry(self) -> None:
        import agents.generation.phase2.workflow as workflow_module

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "prelaunch-context-substitution",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            action, heads = _stable_next_action(
                store,
                research_mode="balanced",
                web_search="disabled",
            )
            dispatches, _ = workflow_module._record_scheduler_dispatches(
                store,
                [action],
                heads,
                execution_contract={
                    "version": 1,
                    "driver": "custom",
                    "identity": "test:context-binding",
                    "recovery_capability": "none",
                    "model_profile": "default",
                    "max_context_chars": 12_000,
                },
            )
            dispatch = dispatches[0]
            item = workflow_module._prepare_scheduled_session(
                store,
                action,
                research_mode="balanced",
                web_search="disabled",
                max_context_chars=12_000,
                model_profile="default",
                is_companion=False,
            )
            item["session_plan"].update(
                {
                    "scheduler_decision_state_revision": dispatch[
                        "decision_state_revision"
                    ],
                    "scheduler_dispatch_id": dispatch["dispatch_id"],
                    "dispatched_action_hash": dispatch[
                        "dispatched_action_hash"
                    ],
                }
            )
            context_path = Path(item["session_plan"]["context_path"])
            packet = json.loads(context_path.read_text(encoding="utf-8"))
            packet["substituted_after_planning"] = True
            context_path.write_text(json.dumps(packet), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "context content"):
                workflow_module._record_scheduler_attempts(store, [item])
            with store.connect() as conn:
                self.assertEqual(
                    0,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM scheduler_dispatch_attempts"
                    ).fetchone()["n"],
                )

    def test_stale_dispatch_transaction_replans_before_launch(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-stale-dispatch-replan",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            original = workflow_mod._record_scheduler_dispatches
            dispatch_attempts = 0
            executor_calls = 0

            def transient_stale(*args, **kwargs):
                nonlocal dispatch_attempts
                dispatch_attempts += 1
                if dispatch_attempts == 1:
                    raise workflow_mod._StaleSchedulerDispatch("simulated race")
                return original(*args, **kwargs)

            def executor(*, store, action, session_plan, **_kwargs):
                nonlocal executor_calls
                executor_calls += 1
                return {
                    "run_id": "stale-replan-run",
                    "status": "failed",
                    "returncode": 1,
                    "wall_time_seconds": 0.01,
                    "peak_memory_mb": 1.0,
                    "usage": {"input_tokens": 1, "total_tokens": 1},
                    "session_id": "",
                    "patch": None,
                    "patch_error": "simulated child failure",
                    "failure_kind": "test_failure",
                    "output_artifact_ids": [],
                    "model": "fake",
                    "reasoning_effort": "low",
                    "sandbox": "workspace-write",
                    "web_search": "disabled",
                }

            with patch.object(
                workflow_mod,
                "_record_scheduler_dispatches",
                side_effect=transient_stale,
            ):
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
            self.assertEqual(2, dispatch_attempts)
            self.assertEqual(1, executor_calls)
            with store.connect() as conn:
                self.assertEqual(
                    1,
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM scheduler_dispatches"
                    ).fetchone()["n"],
                )

    def test_parallel_wave_is_fully_committed_before_first_executor(self) -> None:
        class SimulatedOrchestratorCrash(BaseException):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-parallel-durable-dispatch",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")

            def crashing_executor(*, store, action, session_plan, **_kwargs):
                with store.connect() as conn:
                    rows = conn.execute(
                        "SELECT dispatch_group_id, dispatch_position, "
                        "decision_trace_json FROM scheduler_dispatches "
                        "ORDER BY dispatch_position"
                    ).fetchall()
                    self.assertGreater(len(rows), 1)
                    self.assertEqual(list(range(len(rows))), [
                        int(row["dispatch_position"]) for row in rows
                    ])
                    self.assertEqual(
                        1, len({str(row["dispatch_group_id"]) for row in rows})
                    )
                    wave_ids = {
                        json.loads(row["decision_trace_json"])[
                            "parallel_wave_admission"
                        ]["wave_id"]
                        for row in rows
                    }
                    self.assertEqual(1, len(wave_ids))
                    self.assertIn(
                        session_plan["scheduler_dispatch_id"],
                        {
                            str(row["dispatch_id"])
                            for row in conn.execute(
                                "SELECT dispatch_id FROM scheduler_dispatches"
                            )
                        },
                    )
                raise SimulatedOrchestratorCrash

            with self.assertRaises(SimulatedOrchestratorCrash):
                run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=True,
                    parallel_branches=5,
                    write_on_stop=False,
                    write_console=False,
                    executor=crashing_executor,
                    research_mode="hard_problem",
                    web_search="live",
                )

    def test_accepted_alignment_portfolio_completes_steering_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-steering-alignment", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            message = submit_operator_steering(
                store, "The new example changes the root lower bound."
            )
            mark_authenticated_consumed(store, [message["id"]])

            def candidate(index: int) -> dict:
                methods = (
                    "filtration induction",
                    "spectral decomposition",
                    "geometric degeneration",
                    "categorical duality",
                    "extremal counterexample",
                    "probabilistic construction",
                )
                representations = (
                    "successive quotients",
                    "exceptional eigenspace",
                    "boundary fibre",
                    "adjoint morphism",
                    "minimal obstruction",
                    "conditional expectation",
                )
                return {
                    "approach_id": f"aligned-{index}",
                    "title": f"Aligned approach {index}",
                    "method_family": methods[index],
                    "independent_starting_point": f"Begin with the {representations[index]} rather than the existing route.",
                    "mechanism": f"Exploit {methods[index]} through the {representations[index]}.",
                    "mathematical_objects": [f"object-{index}"],
                    "representation_or_invariant": representations[index],
                    "root_consequence": f"Mechanism {index} gives an exact updated root consequence.",
                    "steering_impact": "The new lower bound changes the sharp target for this mechanism.",
                    "bridge_statement": f"Exact aligned bridge {index}.",
                    "contribution_level": 5 if index < 2 else 3,
                    "contribution_kind": "root_closing" if index < 2 else "major_case",
                    "evidence": "The processed human steer changes the baseline.",
                    "likely_failure_mode": f"Failure mode {index}.",
                    "decisive_test": f"Run decisive test {index}.",
                    "estimated_cost": "medium",
                    "originality_status": "new_combination",
                    "originality_rationale": f"Mechanism {index} changes both the starting point and representation.",
                    "comparison_to_existing_work": f"Existing route {index} lacks this updated sharp-bound reduction.",
                    "confidence": "medium",
                    "confidence_basis": "The bridge remains unproved.",
                    "status": "selected" if index < 2 else "idea",
                    "semantic_signature": {
                        "mechanism": f"mechanism-{index}",
                        "representation": f"representation-{index}",
                        "proof_direction": "forward" if index % 2 == 0 else "adversarial",
                        "theorem_family": f"family-{index}",
                        "root_obligation": f"obligation-{index}",
                        "failure_mode": f"failure-{index}",
                    },
                }

            def executor(*, store: ProofStateStore, action: dict, session_plan: dict, **_: object) -> dict:
                self.assertTrue(action["exclusive_wave_required"])
                portfolio_id = "portfolio-aligned-after-steer"
                return {
                    "run_id": "alignment-refresh-run",
                    "actor_role": "researcher",
                    "status": "completed",
                    "returncode": 0,
                    "wall_time_seconds": 1.0,
                    "peak_memory_mb": 1.0,
                    "usage": {"input_tokens": 20, "output_tokens": 10, "reasoning_output_tokens": 0, "total_tokens": 30},
                    "session_id": "alignment-session",
                    "patch": {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": session_plan["state_revision"],
                        "actor_role": "researcher",
                        "target_id": "root",
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": portfolio_id,
                                "artifact_type": "approach_portfolio",
                                "content": "A steer-aligned global approach portfolio.",
                                "metadata": {
                                    "strategy_schema_version": 1,
                                    "portfolio_contract_version": 3,
                                    "portfolio_kind": "initial",
                                    "brainstorming_summary": "Six distinct mechanisms were recomputed after the steer.",
                                    "alignment_source_steering_ids": [message["id"]],
                                    "alignment_evidence_artifact_ids": [],
                                    "alignment_summary": "The sharp target changed.",
                                    "root_effect_recomputed": True,
                                    "approaches": [candidate(index) for index in range(6)],
                                    "selected_approach_ids": ["aligned-0", "aligned-1"],
                                    "selection_rationale": "The first two candidates are complementary and dominate the remaining four decisive tests.",
                                    "research_questions": [],
                                },
                            }
                        ],
                    },
                    "patch_error": "",
                    "output_artifact_ids": [portfolio_id],
                    "final_message_path": "",
                    "log_path": "",
                    "model": "fake",
                    "reasoning_effort": "xhigh",
                    "sandbox": "workspace-write",
                    "web_search": "disabled",
                }

            result = run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=True,
                parallel_branches=5,
                write_on_stop=False,
                write_console=False,
                executor=executor,
                research_mode="hard_problem",
                web_search="disabled",
            )

            row = steering_snapshot(store)["recent_inbox"][0]

        self.assertTrue(result["steps"][0]["patch_outcome"]["accepted"])
        self.assertTrue(
            result["steps"][0]["metrics_outcome"]["accepted"],
            result["steps"][0]["metrics_outcome"].get("errors"),
        )
        self.assertNotIn("parallel_actions", result["steps"][0])
        self.assertEqual(row["approach_alignment_status"], "completed")
        self.assertEqual(row["approach_alignment_artifact_id"], "portfolio-aligned-after-steer")

    def test_console_write_throttle_coalesces_heartbeats_but_allows_forced_snapshots(self) -> None:
        throttle = _ConsoleWriteThrottle(15.0)

        self.assertTrue(throttle.should_write(now=100.0))
        self.assertFalse(throttle.should_write(now=110.0))
        self.assertTrue(throttle.should_write(force=True, now=111.0))
        self.assertFalse(throttle.should_write(now=120.0))
        self.assertTrue(throttle.should_write(now=126.0))

    def test_scheduler_retries_when_policy_changes_during_planning(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-stable-planning-snapshot-test",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            calls = {"count": 0}

            def interleaved_planner(*_: object, **__: object) -> dict:
                calls["count"] += 1
                if calls["count"] == 1:
                    store.set_completion_policy(
                        "exploratory",
                        reason="change policy during the first planning attempt",
                        source="test",
                    )
                return {"mode": "prove", "target_id": "root"}

            with patch.object(
                workflow_mod,
                "next_action",
                side_effect=interleaved_planner,
            ):
                action, heads = _stable_next_action(
                    store,
                    research_mode="hard_problem",
                    web_search="disabled",
                )

            self.assertEqual(calls["count"], 2)
            self.assertEqual(action["mode"], "prove")
            self.assertEqual(heads, store.audit_chain_heads())

    def test_heterogeneous_backend_block_stops_for_operator_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-heterogeneous-backend-block-test",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            calls = {"count": 0}

            def executor(*, action: dict, session_plan: dict, **_: object) -> dict:
                calls["count"] += 1
                return {
                    "run_id": "blocked-reviewer-family",
                    "actor_role": session_plan["actor_role"],
                    "status": "blocked",
                    "returncode": -1,
                    "wall_time_seconds": 0.0,
                    "peak_memory_mb": 0.0,
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "reasoning_output_tokens": 0,
                        "total_tokens": 0,
                    },
                    "session_id": "",
                    "patch": None,
                    "patch_error": (
                        "enhanced assurance requires a reviewer from a different "
                        "provider/model family"
                    ),
                    "failure_kind": "heterogeneous_backend_required",
                    "output_artifact_ids": [],
                    "final_message_path": "",
                    "log_path": "",
                    "model": "fake",
                    "reasoning_effort": "xhigh",
                    "sandbox": "workspace-write",
                    "web_search": "disabled",
                }

            result = run_workflow(
                store,
                steps=3,
                execute=True,
                parallel_librarian_verifier=False,
                parallel_branches=0,
                write_on_stop=False,
                write_console=False,
                executor=executor,
            )

            self.assertEqual(calls["count"], 1)
            self.assertEqual(len(result["steps"]), 1)
            self.assertEqual(
                result["steps"][0]["terminal_classification"],
                "backend_selection_required",
            )
            self.assertEqual(
                result["steps"][0]["execution_phase"],
                "awaiting_operator_configuration",
            )
            self.assertIn("model provider", result["steps"][0]["operator_action_required"])
            self.assertEqual(store.get_run_status(), "awaiting_human")

    def test_backend_outage_backs_off_and_refunds_steps(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-outage-breaker-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            calls = {"count": 0}

            def executor(*, store: ProofStateStore, action: dict, session_plan: dict, **_: object) -> dict:
                calls["count"] += 1
                if calls["count"] <= 2:
                    return {
                        "run_id": f"outage-{calls['count']}",
                        "actor_role": "researcher",
                        "status": "failed",
                        "returncode": 1,
                        "wall_time_seconds": 5.0,
                        "peak_memory_mb": 1.0,
                        "usage": {"input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0, "total_tokens": 0},
                        "session_id": "",
                        "patch": None,
                        "patch_error": "stream disconnected before completion: error sending request",
                        "output_artifact_ids": [],
                        "final_message_path": "",
                        "log_path": "",
                        "model": "fake",
                        "reasoning_effort": "xhigh",
                        "sandbox": "workspace-write",
                        "web_search": "disabled",
                    }
                return {
                    "run_id": f"recovered-{calls['count']}",
                    "actor_role": "researcher",
                    "status": "completed",
                    "returncode": 0,
                    "wall_time_seconds": 3.0,
                    "peak_memory_mb": 1.0,
                    "usage": {"input_tokens": 20, "output_tokens": 5, "reasoning_output_tokens": 0, "total_tokens": 25},
                    "session_id": f"session-{calls['count']}",
                    "patch": {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": session_plan["state_revision"],
                        "actor_role": "researcher",
                        "target_id": action.get("target_id", "root"),
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": f"post-outage-dossier-{calls['count']}",
                                "artifact_type": "proof_dossier",
                                "content": f"Recovered pass {calls['count']} after the outage cleared.",
                                "metadata": {"target_id": action.get("target_id", "root")},
                            }
                        ],
                    },
                    "patch_error": "",
                    "output_artifact_ids": [f"post-outage-dossier-{calls['count']}"],
                    "final_message_path": "",
                    "log_path": "",
                    "model": "fake",
                    "reasoning_effort": "xhigh",
                    "sandbox": "workspace-write",
                    "web_search": "disabled",
                }

            old_base = workflow_mod.OUTAGE_BACKOFF_BASE_SECONDS
            workflow_mod.OUTAGE_BACKOFF_BASE_SECONDS = 0
            try:
                result = run_workflow(
                    store,
                    steps=2,
                    execute=True,
                    parallel_librarian_verifier=False,
                    write_on_stop=False,
                    write_console=False,
                    executor=executor,
                )
            finally:
                workflow_mod.OUTAGE_BACKOFF_BASE_SECONDS = old_base

            outage_entries = [e for e in result["steps"] if e.get("outage_suspected")]
            self.assertEqual(len(outage_entries), 2)
            self.assertEqual(outage_entries[0]["outage_streak"], 1)
            self.assertEqual(outage_entries[1]["outage_streak"], 2)
            completed = [
                e
                for e in result["steps"]
                if isinstance(e.get("execution"), dict) and e["execution"].get("status") == "completed"
            ]
            # The two outage waves were refunded: the full 2-step budget still ran.
            self.assertEqual(len(completed), 2)
            self.assertEqual(calls["count"], 4)


class WorkflowParallelRebaseTests(unittest.TestCase):
    def test_init_creates_parallel_exchange_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-parallel-exchange-init-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            path = store.state_dir / "parallel_exchange.jsonl"

            self.assertTrue(path.exists())
            self.assertEqual("", path.read_text(encoding="utf-8"))

    def test_scheduler_state_recent_runs_preserve_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-recent-run-id-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
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
                            "run_id": "run-visible-in-scheduler-state",
                            "actor_role": "researcher",
                            "mode": "prove",
                            "target_id": "root",
                            "state_revision": 0,
                            "context_revision": 0,
                            "search_intent": "parallel_direct_solve",
                            "input_tokens": 1,
                            "output_tokens": 2,
                            "reasoning_output_tokens": 0,
                            "total_tokens": 3,
                            "wall_time_seconds": 1.0,
                            "peak_memory_mb": 10.0,
                            "status": "completed",
                        }
                    ],
                    "rationale": "record run metrics",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            recent = store.get_scheduler_state()["recent_runs"]

        self.assertEqual(recent[0]["run_id"], "run-visible-in-scheduler-state")
        self.assertEqual(recent[0]["search_intent"], "parallel_direct_solve")

    def test_failed_execution_metrics_persist_failure_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-failed-run-artifact-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = _record_execution_metrics(
                store,
                action={"mode": "prove", "target_id": "root"},
                session_plan={
                    "actor_role": "researcher",
                    "state_revision": 0,
                    "context_hash": "ctx",
                    "search_intent": "parallel_direct_solve",
                },
                execution={
                    "run_id": "run:stale/retry",
                    "actor_role": "researcher",
                    "status": "timeout",
                    "returncode": -15,
                    "wall_time_seconds": 12.0,
                    "peak_memory_mb": 3.0,
                    "usage": {"input_tokens": 1, "output_tokens": 2, "reasoning_output_tokens": 0, "total_tokens": 3},
                    "patch_error": "Codex stream retry stalled before a patch was produced.",
                    "log_path": "/tmp/codex.log",
                    "final_message_path": "/tmp/final_patch.json",
                },
                status="timeout",
                model="gpt-test",
                reasoning_effort="xhigh",
                sandbox="workspace-write",
                web_search="disabled",
            )

            self.assertTrue(outcome["accepted"], outcome["errors"])
            with closing(store.connect()) as conn:
                run = conn.execute("SELECT error_artifact_id FROM runs WHERE run_id = ?", ("run:stale/retry",)).fetchone()
                self.assertIsNotNone(run)
                artifact_id = run["error_artifact_id"]
                self.assertTrue(artifact_id.startswith("session_failure_run_stale_retry"))
                artifact = conn.execute(
                    "SELECT artifact_type, path, content_summary FROM artifacts WHERE artifact_id = ?",
                    (artifact_id,),
                ).fetchone()
                self.assertIsNotNone(artifact)
                self.assertEqual(artifact["artifact_type"], "session_failure_report")
                self.assertIn("Codex stream retry stalled", artifact["content_summary"])
                content = Path(artifact["path"]).read_text(encoding="utf-8")
                self.assertIn("run:stale/retry", content)
                self.assertIn("Codex stream retry stalled", content)

    def test_recoverable_researcher_stale_retry_does_not_stop_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-stale-retry-recovery-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            calls = {"count": 0}

            def executor(*, store: ProofStateStore, action: dict, session_plan: dict, **_: object) -> dict:
                calls["count"] += 1
                if calls["count"] == 1:
                    return {
                        "run_id": "researcher-stale-retry",
                        "actor_role": "researcher",
                        "status": "timeout",
                        "returncode": -15,
                        "wall_time_seconds": 12.0,
                        "peak_memory_mb": 4.0,
                        "usage": {"input_tokens": 10, "output_tokens": 0, "reasoning_output_tokens": 0, "total_tokens": 10},
                        "session_id": "session-stale",
                        "patch": None,
                        "patch_error": "Transport ended before a patch was produced.",
                        "failure_kind": "stale_stream",
                        "output_artifact_ids": [],
                        "final_message_path": "",
                        "log_path": "",
                        "model": "fake",
                        "reasoning_effort": "xhigh",
                        "sandbox": "workspace-write",
                        "web_search": "disabled",
                    }
                return {
                    "run_id": "researcher-recovered",
                    "actor_role": "researcher",
                    "status": "completed",
                    "returncode": 0,
                    "wall_time_seconds": 3.0,
                    "peak_memory_mb": 4.0,
                    "usage": {"input_tokens": 20, "output_tokens": 5, "reasoning_output_tokens": 0, "total_tokens": 25},
                    "session_id": "session-recovered",
                    "patch": {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": session_plan["state_revision"],
                        "actor_role": "researcher",
                        "target_id": action.get("target_id", "root"),
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": "recovered-proof-dossier",
                                "artifact_type": "proof_dossier",
                                "content": "Recovered researcher pass with a concrete mathematical artifact.",
                                "metadata": {"target_id": action.get("target_id", "root")},
                            }
                        ],
                    },
                    "patch_error": "",
                    "output_artifact_ids": ["recovered-proof-dossier"],
                    "final_message_path": "",
                    "log_path": "",
                    "model": "fake",
                    "reasoning_effort": "xhigh",
                    "sandbox": "workspace-write",
                    "web_search": "disabled",
                }

            old = os.environ.get("ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS")
            os.environ["ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS"] = "1"
            try:
                result = run_workflow(
                    store,
                    steps=2,
                    execute=True,
                    parallel_librarian_verifier=False,
                    write_on_stop=False,
                    write_console=False,
                    executor=executor,
                )
            finally:
                if old is None:
                    os.environ.pop("ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS", None)
                else:
                    os.environ["ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS"] = old

            self.assertEqual(calls["count"], 2)
            self.assertTrue(result["steps"][0]["recoverable_failure"])
            self.assertEqual(result["steps"][0]["execution_phase"], "recovering_after_stale_retry")
            self.assertEqual(result["steps"][1]["execution"]["status"], "completed")
            with closing(store.connect()) as conn:
                self.assertIsNotNone(
                    conn.execute("SELECT 1 FROM artifacts WHERE artifact_id = ?", ("recovered-proof-dossier",)).fetchone()
                )

    def test_recoverable_verifier_stale_retry_does_not_stop_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-verifier-stale-retry-recovery-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
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
                            "op": "attach_artifact",
                            "artifact_id": "route-proof-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "A complete proof packet ready for strict verification.",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root-proof",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the assembled proof dossier.",
                            "evidence_artifact_ids": ["route-proof-dossier"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root-proof",
                            "route_id": "route-root-proof",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The proof packet implies the target.",
                            "evidence_artifact_ids": ["route-proof-dossier"],
                        },
                    ],
                    "rationale": "seed verifier-ready route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            calls = {"count": 0}

            def executor(*, store: ProofStateStore, action: dict, session_plan: dict, **_: object) -> dict:
                calls["count"] += 1
                self.assertEqual(action.get("route_id"), "route-root-proof")
                if calls["count"] == 1:
                    return {
                        "run_id": "verifier-stale-retry",
                        "actor_role": "strict_informal_verifier",
                        "status": "timeout",
                        "returncode": -15,
                        "wall_time_seconds": 12.0,
                        "peak_memory_mb": 4.0,
                        "usage": {"input_tokens": 10, "output_tokens": 0, "reasoning_output_tokens": 0, "total_tokens": 10},
                        "session_id": "session-stale-verifier",
                        "patch": None,
                        "patch_error": "Codex stream retry stalled with no further log/token progress before a patch was produced.",
                        "failure_kind": "stale_stream",
                        "output_artifact_ids": [],
                        "final_message_path": "",
                        "log_path": "",
                        "model": "fake",
                        "reasoning_effort": "xhigh",
                        "sandbox": "workspace-write",
                        "web_search": "disabled",
                    }
                return {
                    "run_id": "verifier-recovered",
                    "actor_role": "strict_informal_verifier",
                    "status": "completed",
                    "returncode": 0,
                    "wall_time_seconds": 3.0,
                    "peak_memory_mb": 4.0,
                    "usage": {"input_tokens": 20, "output_tokens": 5, "reasoning_output_tokens": 0, "total_tokens": 25},
                    "session_id": "session-recovered-verifier",
                    "patch": {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": session_plan["state_revision"],
                        "actor_role": "strict_informal_verifier",
                        "target_id": action.get("target_id", "root"),
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": "recovered-verification-report",
                                "artifact_type": "verification_report",
                                "content": "Recovered strict verification pass produced a report.",
                                "metadata": {
                                    "target_id": action.get("target_id", "root"),
                                    "verdict": "gap_found",
                                    "proof_interface_check_version": 2,
                                    "quantifiers_preserved": True,
                                    "hypotheses_matched": True,
                                    "cases_exhaustive": True,
                                    "reduction_direction_valid": True,
                                    "finite_scope_not_overclaimed": True,
                                    "dependencies_assemble": False,
                                },
                            }
                        ],
                    },
                    "patch_error": "",
                    "output_artifact_ids": ["recovered-verification-report"],
                    "final_message_path": "",
                    "log_path": "",
                    "model": "fake",
                    "reasoning_effort": "xhigh",
                    "sandbox": "workspace-write",
                    "web_search": "disabled",
                }

            old = os.environ.get("ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS")
            os.environ["ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS"] = "1"
            try:
                result = run_workflow(
                    store,
                    steps=2,
                    execute=True,
                    parallel_librarian_verifier=False,
                    write_on_stop=False,
                    write_console=False,
                    executor=executor,
                )
            finally:
                if old is None:
                    os.environ.pop("ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS", None)
                else:
                    os.environ["ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS"] = old

            self.assertEqual(calls["count"], 2)
            self.assertTrue(result["steps"][0]["recoverable_failure"])
            self.assertEqual(result["steps"][0]["execution_phase"], "recovering_after_stale_retry")
            self.assertEqual(result["steps"][1]["execution"]["status"], "completed")
            with closing(store.connect()) as conn:
                self.assertIsNotNone(
                    conn.execute("SELECT 1 FROM artifacts WHERE artifact_id = ?", ("recovered-verification-report",)).fetchone()
                )

    def test_stop_writer_does_not_treat_blocked_route_as_verifier_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-stop-writer-blocked-route-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
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
                            "op": "attach_artifact",
                            "artifact_id": "candidate-note",
                            "artifact_type": "research_notebook",
                            "content": "A candidate route exists, but the bridge lemma is explicitly blocked.",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-blocked-candidate",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use a bridge lemma that is still blocked.",
                            "evidence_artifact_ids": ["candidate-note"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-blocked-candidate",
                            "route_id": "route-blocked-candidate",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The route would prove the target if the bridge lemma were supplied.",
                            "evidence_artifact_ids": ["candidate-note"],
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-blocked-bridge",
                            "owner_type": "route",
                            "owner_id": "route-blocked-candidate",
                            "debt_type": "blocking_bridge_lemma",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Prove the bridge lemma before strict verification.",
                            "suggested_next_target": "root",
                            "source_artifact_ids": ["candidate-note"],
                        },
                    ],
                    "rationale": "seed blocked route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            blocker = _stop_writer_safety_blocker(store, research_mode="balanced", web_search="disabled")

        self.assertNotEqual(
            blocker.get("reason"),
            "verifier-ready route evidence exists, but no strict verifier run is recorded",
        )
        self.assertEqual(blocker.get("verifier_ready_routes", []), [])

    def test_stop_writer_ignores_blocked_route_proof_dossier_candidate_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-stop-writer-blocked-dossier-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "stale-local-route",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "blocked-route-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "Do not verify this stale route; return to the root bottleneck.",
                            "metadata": {
                                "target_id": "stale-local-route",
                                "artifact_roi": "route_blocked_or_abandoned",
                                "next_decisive_action": "Return to root.",
                            },
                        }
                    ],
                    "rationale": "seed blocked route note",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            blocker = _stop_writer_safety_blocker(store, research_mode="balanced", web_search="disabled")

        self.assertNotIn(
            "blocked-route-dossier",
            {item.get("artifact_id") for item in blocker.get("proof_candidate_artifacts", [])},
        )

    def test_additive_parallel_research_patch_rebases_after_companion_lands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-parallel-rebase-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            first = apply_patch(
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
                            "artifact_id": "refute-note",
                            "artifact_type": "research_notebook",
                            "content": "A diagnostic counterexample search found no obstruction.",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-refute-diagnostic",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "diagnostic",
                            "strategy": "stress test",
                            "evidence_artifact_ids": ["refute-note"],
                        },
                    ],
                    "rationale": "diagnostic branch landed first",
                },
            )
            self.assertTrue(first.accepted, first.errors)
            current_revision = store.get_revision()

            stale_research_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": 0,
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": "proof-dossier",
                        "artifact_type": "proof_dossier",
                        "content": "A constructive route with local lemmas.",
                    },
                    {
                        "op": "add_claim",
                        "claim_id": "claim-local-lemma",
                        "kind": "lemma",
                        "statement": "A local lemma implies the target under a construction hypothesis.",
                        "validation_status": "plausible",
                        "parent_ids": ["root"],
                        "evidence_artifact_ids": ["proof-dossier"],
                    },
                    {
                        "op": "add_route",
                        "route_id": "route-local-lemma",
                        "conclusion_claim_id": "claim-local-lemma",
                        "relation_to_parent": "sufficient",
                        "strategy": "prove the local lemma",
                        "evidence_artifact_ids": ["proof-dossier"],
                    },
                    {
                        "op": "add_route",
                        "route_id": "route-root-constructive",
                        "conclusion_claim_id": "root",
                        "relation_to_parent": "sufficient",
                        "strategy": "assemble the construction",
                        "evidence_artifact_ids": ["proof-dossier"],
                    },
                    {
                        "op": "add_inference",
                        "inference_id": "inf-root-constructive",
                        "route_id": "route-root-constructive",
                        "conclusion_claim_id": "root",
                        "premise_claim_ids": ["claim-local-lemma"],
                        "validation_status": "plausible",
                        "explanation": "The local lemma is one ingredient in a constructive route.",
                        "evidence_artifact_ids": ["proof-dossier"],
                    },
                    {
                        "op": "add_debt",
                        "debt_id": "debt-construction-source",
                        "owner_type": "route",
                        "owner_id": "route-root-constructive",
                        "debt_type": "citation_or_construction_gap",
                        "severity": "blocking",
                        "status": "active",
                        "obligation": "Supply the construction theorem.",
                        "suggested_next_target": "claim-local-lemma",
                    },
                ],
                "rationale": "constructive branch produced fresh additive research state",
            }

            action = {
                "mode": "reduce",
                "target_id": "root",
                "search_intent": "parallel_independent_solve",
                "parallel_companion": True,
            }
            rebased = _rebase_parallel_patch_if_safe(stale_research_patch, current_revision, action=action)
            self.assertEqual(rebased["base_revision"], current_revision)
            accepted = apply_patch(store, rebased)
            self.assertTrue(accepted.accepted, accepted.errors)

            with closing(store.connect()) as conn:
                self.assertIsNotNone(store.get_route(conn, "route-root-constructive"))
                artifact = store.get_artifact(conn, "proof-dossier")
                self.assertIsNotNone(artifact)
                self.assertEqual(artifact["state_revision"], store.get_revision())

    def test_parallel_route_proof_patch_rebases_existing_selected_route_inference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-route-proof-rebase-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            setup = apply_patch(
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
                            "route_id": "route-existing",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "existing route",
                        }
                    ],
                    "rationale": "setup route",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)
            landed = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "parallel-obstruction",
                            "artifact_type": "route_obstruction",
                            "content": "parallel branch landed first",
                        }
                    ],
                    "rationale": "parallel companion landed first",
                },
            )
            self.assertTrue(landed.accepted, landed.errors)

            stale_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": 1,
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [
                    {
                        "operation": "attach_artifact",
                        "artifact": {
                            "artifact_id": "route-proof",
                            "artifact_type": "proof_dossier",
                            "content": "proof for selected route",
                        },
                    },
                    {
                        "operation": "add_inference",
                        "inference": {
                            "inference_id": "inf-route-existing",
                            "route_id": "route-existing",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "untested",
                            "explanation": "selected route inference",
                        },
                    },
                ],
                "rationale": "route proof construction",
            }

            rebased = _rebase_parallel_patch_if_safe(
                stale_patch,
                store.get_revision(),
                action={
                    "mode": "reduce",
                    "target_id": "root",
                    "route_id": "route-existing",
                    "search_intent": "route_proof_construction",
                },
                parallel_group=True,
            )
            outcome = apply_patch(store, rebased)

            self.assertTrue(outcome.accepted, outcome.errors)
            self.assertEqual(2, rebased["base_revision"])
            self.assertEqual("attach_artifact", rebased["operations"][0]["op"])
            self.assertEqual("add_inference", rebased["operations"][1]["op"])

    def test_parallel_route_conversion_patch_rebases_existing_route_without_action_route_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-route-conversion-rebase-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            setup = apply_patch(
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
                            "claim_id": "claim-existing",
                            "kind": "lemma",
                            "statement": "Existing claim awaiting route conversion.",
                            "validation_status": "plausible",
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-existing-claim",
                            "conclusion_claim_id": "claim-existing",
                            "relation_to_parent": "sufficient",
                            "strategy": "existing route awaiting an inference",
                        },
                    ],
                    "rationale": "setup existing claim route",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)
            landed = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "phd_advisor",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "advisor-synthesis",
                            "artifact_type": "advisor_report",
                            "content": "Advisor landed before route conversion.",
                        }
                    ],
                    "rationale": "advisor companion landed first",
                },
            )
            self.assertTrue(landed.accepted, landed.errors)

            stale_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": 1,
                "actor_role": "researcher",
                "target_id": "claim-existing",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": "route-conversion-dossier",
                        "artifact_type": "proof_dossier",
                        "content": "Proof dossier converting the existing route.",
                    },
                    {
                        "op": "add_inference",
                        "inference_id": "inf-route-existing-claim",
                        "route_id": "route-existing-claim",
                        "conclusion_claim_id": "claim-existing",
                        "premise_claim_ids": [],
                        "validation_status": "untested",
                        "explanation": "Route conversion inference for the existing claim route.",
                        "evidence_artifact_ids": ["route-conversion-dossier"],
                    },
                ],
                "rationale": "route conversion produced an inference for an existing route",
            }

            rebased = _rebase_parallel_patch_if_safe(
                stale_patch,
                store.get_revision(),
                action={
                    "mode": "prove",
                    "target_id": "claim-existing",
                    "search_intent": "proof_candidate_route_conversion",
                },
                parallel_group=True,
            )
            outcome = apply_patch(store, rebased)

            self.assertTrue(outcome.accepted, outcome.errors)
            self.assertEqual(2, rebased["base_revision"])
            with closing(store.connect()) as conn:
                self.assertIsNotNone(
                    conn.execute(
                        "SELECT 1 FROM inferences WHERE inference_id = ?",
                        ("inf-route-existing-claim",),
                    ).fetchone()
                )

    def test_literature_patch_with_target_debt_rebases_after_companion_lands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-literature-debt-rebase-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            first = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "parallel-obstruction-note",
                            "artifact_type": "research_diagnostic",
                            "content": "A parallel branch found an obstruction to one route.",
                        }
                    ],
                    "rationale": "companion branch landed first",
                },
            )
            self.assertTrue(first.accepted, first.errors)
            current_revision = store.get_revision()

            stale_literature_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": 0,
                "actor_role": "literature_researcher",
                "target_id": "root",
                "operations": [
                    {
                        "op": "cache_retrieval_card",
                        "card_id": "retrieval-partial-match",
                        "target_id": "root",
                        "exact_statement": "A nearby theorem proves a weaker invariable-generation target.",
                        "source_identifiers": {"title": "Nearby theorem"},
                        "source_version": "source v1",
                        "source_location": "Theorem 1",
                        "applicability": {"classification": "partial_match"},
                        "missing_hypotheses": ["Bridge the weaker theorem to the target."],
                    },
                    {
                        "op": "attach_artifact",
                        "artifact_id": "retrieval-adaptation",
                        "artifact_type": "source_adaptation_notes",
                        "content": "The source is useful but leaves one target-level bridge.",
                    },
                    {
                        "op": "add_debt",
                        "debt_id": "debt-literature-bridge",
                        "owner_type": "claim",
                        "owner_id": "root",
                        "debt_type": "gap",
                        "severity": "high",
                        "status": "active",
                        "obligation": "Bridge the partial literature theorem to the target.",
                        "source_artifact_ids": ["retrieval-adaptation"],
                        "suggested_next_target": "root",
                    },
                ],
                "rationale": "literature branch found a partial source and a target debt",
            }

            rebased = _rebase_parallel_patch_if_safe(
                stale_literature_patch,
                current_revision,
                action={"mode": "retrieve", "target_id": "root", "search_intent": "literature_scoping"},
            )
            self.assertEqual(rebased["base_revision"], current_revision)
            accepted = apply_patch(store, rebased)
            self.assertTrue(accepted.accepted, accepted.errors)

            with closing(store.connect()) as conn:
                card = conn.execute("SELECT card_id FROM retrieval_cards WHERE card_id = 'retrieval-partial-match'").fetchone()
                debt = conn.execute("SELECT status FROM debts WHERE debt_id = 'debt-literature-bridge'").fetchone()
                artifact = store.get_artifact(conn, "retrieval-adaptation")

            self.assertIsNotNone(card)
            self.assertIsNotNone(debt)
            self.assertEqual(debt["status"], "active")
            self.assertIsNotNone(artifact)
            self.assertEqual(artifact["state_revision"], store.get_revision())

    def test_advisor_artifact_patch_rebases_after_primary_lands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-advisor-artifact-rebase-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            first = apply_patch(
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
                            "artifact_id": "primary-proof-note",
                            "artifact_type": "proof_dossier",
                            "content": "The primary child landed first.",
                        }
                    ],
                    "rationale": "primary child landed first",
                },
            )
            self.assertTrue(first.accepted, first.errors)
            current_revision = store.get_revision()

            stale_advisor_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": 0,
                "actor_role": "phd_advisor",
                "target_id": "root",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": "advisor-proof-shape",
                        "artifact_type": "advisor_report",
                        "target_id": "root",
                        "content": "The advisor records a proof-shape triage note.",
                    },
                    {
                        "op": "attach_artifact",
                        "artifact_id": "advisor-route-triage",
                        "artifact_type": "route_triage_report",
                        "target_id": "root",
                        "content": "The advisor records route triage.",
                    },
                ],
                "rationale": "advisor companion finished after primary child",
            }

            rebased = _rebase_parallel_patch_if_safe(
                stale_advisor_patch,
                current_revision,
                action={
                    "mode": "triage_routes",
                    "target_id": "root",
                    "route_id": "route-root",
                    "search_intent": "advisor_evidence_synthesis",
                    "parallel_companion": True,
                },
                parallel_group=True,
            )
            self.assertEqual(rebased["base_revision"], current_revision)
            accepted = apply_patch(store, rebased)
            self.assertTrue(accepted.accepted, accepted.errors)

            with closing(store.connect()) as conn:
                artifact = store.get_artifact(conn, "advisor-proof-shape")
            self.assertIsNotNone(artifact)
            self.assertEqual(artifact["state_revision"], store.get_revision())

    def test_status_transition_parallel_research_patch_does_not_rebase(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-parallel-rebase-test",
            "base_revision": 0,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {
                    "op": "propose_status_transition",
                    "target_type": "claim",
                    "target_id": "root",
                    "status_type": "validation",
                    "new_status": "informally_verified",
                    "evidence_artifact_ids": ["proof-dossier"],
                }
            ],
        }
        rebased = _rebase_parallel_patch_if_safe(
            patch,
            3,
            action={
                "mode": "reduce",
                "target_id": "root",
                "search_intent": "parallel_independent_solve",
                "parallel_companion": True,
            },
        )
        self.assertEqual(rebased["base_revision"], 0)

    def test_additive_primary_patch_rebases_when_launched_in_parallel_group(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-parallel-primary-rebase-test",
            "base_revision": 4,
            "actor_role": "researcher",
            "target_id": "claim-target",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "target-proof-dossier",
                    "artifact_type": "proof_dossier",
                    "content": "A target-local proof repair note.",
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-target-repair",
                    "owner_type": "claim",
                    "owner_id": "claim-target",
                    "debt_type": "gap",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Repair the target-local proof.",
                    "suggested_next_target": "claim-target",
                },
            ],
            "rationale": "primary direct repair finished after a companion",
        }

        rebased_without_group = _rebase_parallel_patch_if_safe(
            patch,
            5,
            action={"mode": "prove", "target_id": "claim-target", "search_intent": "direct_solve_debt_repair"},
        )
        rebased_with_group = _rebase_parallel_patch_if_safe(
            patch,
            5,
            action={"mode": "prove", "target_id": "claim-target", "search_intent": "direct_solve_debt_repair"},
            parallel_group=True,
        )

        self.assertEqual(rebased_without_group["base_revision"], 4)
        self.assertEqual(rebased_with_group["base_revision"], 5)

    def test_additive_local_repair_patch_rebases_with_root_handoff_debt(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-parallel-root-handoff-rebase-test",
            "base_revision": 12,
            "actor_role": "researcher",
            "target_id": "claim-stale-local-route",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "local-statement-repair-note",
                    "artifact_type": "proof_dossier",
                    "content": "Repair the local stale statement and return to the root bottleneck.",
                    "metadata": {
                        "target_id": "claim-stale-local-route",
                        "next_decisive_action": "return to root bottleneck",
                    },
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-stale-local-wording",
                    "owner_type": "claim",
                    "owner_id": "claim-stale-local-route",
                    "debt_type": "proof_obligation",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Retire the stale local wording before returning to root.",
                    "suggested_next_target": "root",
                    "evidence_artifact_ids": ["local-statement-repair-note"],
                },
            ],
            "rationale": "primary local repair finished after an advisor companion",
        }

        rebased_without_group = _rebase_parallel_patch_if_safe(
            patch,
            14,
            action={"mode": "prove", "target_id": "claim-stale-local-route", "search_intent": "advisor_followup_research"},
        )
        rebased_with_group = _rebase_parallel_patch_if_safe(
            patch,
            14,
            action={"mode": "prove", "target_id": "claim-stale-local-route", "search_intent": "advisor_followup_research"},
            parallel_group=True,
        )

        self.assertEqual(rebased_without_group["base_revision"], 12)
        self.assertEqual(rebased_with_group["base_revision"], 14)

    def test_additive_root_patch_rebases_debt_on_existing_root_claim(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-root-existing-claim-debt-rebase-test",
            "base_revision": 22,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "root-h2-capacity-note",
                    "artifact_type": "proof_dossier",
                    "content": "A root-local H2 capacity synthesis.",
                },
                {
                    "op": "add_claim",
                    "claim_id": "claim_root_h2_capacity_test",
                    "kind": "lemma",
                    "statement": "H2 capacity criterion.",
                    "parent_ids": ["root"],
                },
                {
                    "op": "add_route",
                    "route_id": "route_root_h2_capacity_test",
                    "conclusion_claim_id": "claim_root_h2_capacity_test",
                    "strategy": "Use the H2 capacity note.",
                    "evidence_artifact_ids": ["root-h2-capacity-note"],
                },
                {
                    "op": "add_inference",
                    "inference_id": "inf_root_h2_capacity_test",
                    "route_id": "route_root_h2_capacity_test",
                    "conclusion_claim_id": "claim_root_h2_capacity_test",
                    "premise_claim_ids": [],
                    "validation_status": "plausible",
                    "explanation": "The note proves the local criterion.",
                    "evidence_artifact_ids": ["root-h2-capacity-note"],
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-root-existing-h2-claim",
                    "owner_type": "claim",
                    "owner_id": "claim_root_irreducible_h2_frattini_lift_bridge_rev115",
                    "debt_type": "sharpened_blocker",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Decide the root-local H2 capacity alternative.",
                    "suggested_next_target": "root",
                },
            ],
        }

        rebased_without_group = _rebase_parallel_patch_if_safe(
            patch,
            24,
            action={"mode": "prove", "target_id": "root", "search_intent": "advisor_followup_research"},
        )
        rebased_with_group = _rebase_parallel_patch_if_safe(
            patch,
            24,
            action={"mode": "prove", "target_id": "root", "search_intent": "advisor_followup_research"},
            parallel_group=True,
        )

        self.assertEqual(rebased_without_group["base_revision"], 22)
        self.assertEqual(rebased_with_group["base_revision"], 24)

    def test_additive_root_patch_rebases_debt_on_existing_root_route(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-root-existing-route-debt-rebase-test",
            "base_revision": 30,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "root-central-multiplier-note",
                    "artifact_type": "proof_dossier",
                    "content": "A root-local central multiplier synthesis.",
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-root-central-multiplier",
                    "owner_type": "route",
                    "owner_id": "route_root_frattini_h2_head_capacity_criterion_rev122",
                    "debt_type": "proof_obligation",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Decide the central multiplier reservoir test.",
                    "suggested_next_target": "root",
                    "evidence_artifact_ids": ["root-central-multiplier-note"],
                },
            ],
        }

        rebased_without_group = _rebase_parallel_patch_if_safe(
            patch,
            32,
            action={"mode": "prove", "target_id": "root", "search_intent": "advisor_followup_research"},
        )
        rebased_with_group = _rebase_parallel_patch_if_safe(
            patch,
            32,
            action={"mode": "prove", "target_id": "root", "search_intent": "advisor_followup_research"},
            parallel_group=True,
        )

        self.assertEqual(rebased_without_group["base_revision"], 30)
        self.assertEqual(rebased_with_group["base_revision"], 32)

    def test_additive_root_patch_rebases_existing_root_route_debt_without_suggested_target(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-root-existing-route-debt-no-suggested-target-rebase-test",
            "base_revision": 40,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "root-simple-multiplier-note",
                    "artifact_type": "proof_dossier",
                    "content": "A root-local simple multiplier synthesis.",
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-root-simple-multiplier",
                    "owner_id": "route_root_frattini_h2_head_capacity_criterion_rev122",
                    "debt_type": "proof_obligation",
                    "status": "active",
                    "obligation": "Decide the simple multiplier reservoir test.",
                    "evidence_artifact_ids": ["root-simple-multiplier-note"],
                },
            ],
        }

        rebased_without_group = _rebase_parallel_patch_if_safe(
            patch,
            42,
            action={"mode": "prove", "target_id": "root", "search_intent": "advisor_followup_research"},
        )
        rebased_with_group = _rebase_parallel_patch_if_safe(
            patch,
            42,
            action={"mode": "prove", "target_id": "root", "search_intent": "advisor_followup_research"},
            parallel_group=True,
        )

        self.assertEqual(rebased_without_group["base_revision"], 40)
        self.assertEqual(rebased_with_group["base_revision"], 42)

    def test_additive_parallel_route_update_rebases_for_selected_route(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-route-update-rebase-test",
            "base_revision": 7,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {"op": "attach_artifact", "artifact_id": "route-decision", "artifact_type": "proof_dossier", "content": "Route decision."},
                {
                    "op": "update_route",
                    "route_id": "route-root-selected",
                    "status": "blocked",
                    "failure_fingerprint": "selected route obstruction",
                    "evidence_artifact_ids": ["route-decision"],
                },
            ],
            "rationale": "selected route obstruction conversion",
        }

        rebased = _rebase_parallel_patch_if_safe(
            patch,
            9,
            action={"mode": "reduce", "target_id": "root", "route_id": "route-root-selected", "search_intent": "obstruction_route_conversion"},
            parallel_group=True,
        )

        self.assertEqual(rebased["base_revision"], 9)

    def test_parallel_patch_with_uncreated_inference_route_does_not_rebase(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-missing-route-no-rebase-test",
            "base_revision": 7,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {"op": "attach_artifact", "artifact_id": "route-decision", "artifact_type": "proof_dossier", "content": "Route decision."},
                {"op": "add_claim", "claim_id": "route-obstruction", "kind": "lemma", "statement": "Obstruction.", "parent_ids": ["root"], "root_impact": 0.8},
                {
                    "op": "add_inference",
                    "inference_id": "inf-route-obstruction",
                    "route_id": "route-never-created",
                    "conclusion_claim_id": "route-obstruction",
                    "premise_claim_ids": [],
                    "validation_status": "untested",
                    "explanation": "Missing route should prevent safe rebase.",
                    "evidence_artifact_ids": ["route-decision"],
                },
                {"op": "update_route", "route_id": "route-root-selected", "status": "blocked"},
            ],
            "rationale": "malformed obstruction conversion",
        }

        rebased = _rebase_parallel_patch_if_safe(
            patch,
            9,
            action={"mode": "reduce", "target_id": "root", "route_id": "route-root-selected", "search_intent": "obstruction_route_conversion"},
            parallel_group=True,
        )

        self.assertEqual(rebased["base_revision"], 7)

    def test_parallel_challenge_with_same_patch_artifact_rebases(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-parallel-challenge-rebase-test",
            "base_revision": 12,
            "actor_role": "villain",
            "target_id": "root",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "villain-obstruction",
                    "artifact_type": "research_diagnostic",
                    "content": "A target-local obstruction challenges the active route.",
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-villain-obstruction",
                    "owner_type": "claim",
                    "owner_id": "root",
                    "debt_type": "gap",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Resolve the obstruction.",
                    "suggested_next_target": "root",
                },
                {
                    "op": "update_claim",
                    "claim_id": "root",
                    "updates": {"validation_status": "challenged"},
                    "evidence_artifact_ids": ["villain-obstruction"],
                },
            ],
            "rationale": "parallel villain found an additive challenge",
        }

        rebased = _rebase_parallel_patch_if_safe(
            patch,
            14,
            action={
                "mode": "refute",
                "target_id": "root",
                "search_intent": "parallel_counterexample_search",
                "parallel_companion": True,
            },
        )

        self.assertEqual(rebased["base_revision"], 14)
        transition = next(op for op in rebased["operations"] if op["op"] == "propose_status_transition")
        self.assertEqual(transition["new_status"], "challenged")

    def test_primary_stale_after_parallel_sibling_applies_is_recoverable(self) -> None:
        primary = {
            "is_companion": False,
            "status": "patch_rejected",
            "patch_outcome": {
                "accepted": False,
                "errors": ["stale patch: base_revision 475 != current_revision 477"],
            },
        }
        companion = {
            "is_companion": True,
            "status": "completed",
            "patch_outcome": {"accepted": True, "errors": []},
        }

        self.assertTrue(_recoverable_parallel_stale_patch([primary, companion], primary))

    def test_lone_stale_patch_is_not_parallel_recoverable(self) -> None:
        primary = {
            "is_companion": False,
            "status": "patch_rejected",
            "patch_outcome": {
                "accepted": False,
                "errors": ["stale patch: base_revision 475 != current_revision 477"],
            },
        }

        self.assertFalse(_recoverable_parallel_stale_patch([primary], primary))

    def test_constructive_parallel_branch_merges_before_counterexample_stress(self) -> None:
        constructive = {
            "is_companion": True,
            "action": {"search_intent": "parallel_direct_solve"},
            "session_plan": {"actor_role": "researcher"},
        }
        stress = {
            "is_companion": True,
            "action": {"search_intent": "parallel_counterexample_search"},
            "session_plan": {"actor_role": "researcher"},
        }
        self.assertLess(_merge_priority(constructive), _merge_priority(stress))

    def test_live_apply_barrier_waits_for_pending_primary_or_verifier(self) -> None:
        literature = {
            "is_companion": True,
            "action": {"search_intent": "literature_scoping"},
            "session_plan": {"actor_role": "literature_researcher"},
        }
        pending_verifier = {
            "is_companion": False,
            "action": {"search_intent": ""},
            "session_plan": {"actor_role": "strict_informal_verifier"},
        }
        pending_researcher = {
            "is_companion": False,
            "action": {"search_intent": "direct_solve"},
            "session_plan": {"actor_role": "researcher"},
        }

        self.assertTrue(_blocked_by_pending_priority_barrier(literature, [pending_verifier]))
        self.assertTrue(_blocked_by_pending_priority_barrier(literature, [pending_researcher]))

    def test_live_apply_barrier_allows_safe_advisor_before_pending_researcher(self) -> None:
        advisor = {
            "is_companion": True,
            "action": {"mode": "triage_routes", "target_id": "root", "search_intent": "advisor_evidence_synthesis"},
            "session_plan": {"actor_role": "phd_advisor"},
            "execution": {
                "patch": {
                    "actor_role": "phd_advisor",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "advisor-next-step",
                            "artifact_type": "advisor_report",
                            "content": "Verify the bridge next.",
                        }
                    ],
                }
            },
        }
        pending_researcher = {
            "is_companion": False,
            "action": {"search_intent": "direct_solve"},
            "session_plan": {"actor_role": "researcher"},
        }
        pending_verifier = {
            "is_companion": False,
            "action": {"search_intent": "verify_ready_route"},
            "session_plan": {"actor_role": "strict_informal_verifier"},
        }

        self.assertFalse(_blocked_by_pending_priority_barrier(advisor, [pending_researcher]))
        self.assertTrue(_blocked_by_pending_priority_barrier(advisor, [pending_verifier]))

    def test_parallel_signals_are_written_to_authenticated_exchange(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-parallel-signal-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            _record_parallel_signals(
                store,
                {
                    "actor_role": "researcher",
                    "target_id": "root",
                    "parallel_signals": [
                        {
                            "run_id": "unknown",
                            "signal_type": "useful_lemma",
                            "relation": "supports",
                            "summary": "Lemma A may close the construction branch.",
                            "evidence": "artifact:proof-dossier",
                            "confidence": "high",
                        }
                    ],
                },
                action={"mode": "prove", "target_id": "root"},
                execution={"run_id": "run-signal", "actor_role": "researcher"},
            )
            payload = authenticated_parallel_signals(store)[0]

        self.assertEqual(payload["run_id"], "run-signal")
        self.assertEqual(payload["signal_type"], "useful_lemma")
        self.assertEqual(payload["relation"], "supports")
        self.assertEqual(payload["target_id"], "root")

    def test_parallel_signal_problem_id_run_id_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-parallel-problem-id-signal-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            _record_parallel_signals(
                store,
                {
                    "problem_id": store.problem_id,
                    "actor_role": "literature_researcher",
                    "target_id": "root",
                    "parallel_signals": [
                        {
                            "run_id": store.problem_id,
                            "signal_type": "source_found",
                            "summary": "A source may help.",
                        }
                    ],
                },
                action={"mode": "retrieve", "target_id": "root"},
                execution={"run_id": "run-retrieve-root", "actor_role": "literature_researcher"},
            )
            payload = authenticated_parallel_signals(store)[0]

        self.assertEqual(payload["run_id"], "run-retrieve-root")
        self.assertEqual(payload["signal_type"], "source_found")

    def test_parallel_signal_timestamp_is_workflow_stamped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-parallel-signal-time-test",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            with patch(
                "agents.generation.phase2.workflow.utc_now",
                return_value="2026-07-12T06:08:17+00:00",
            ):
                _record_parallel_signals(
                    store,
                    {
                        "actor_role": "villain",
                        "target_id": "root",
                        "parallel_signals": [
                            {
                                "created_at": "2099-01-01T00:00:00Z",
                                "signal_type": "obstruction_found",
                                "summary": "A bounded search found no witness.",
                            }
                        ],
                    },
                    action={"mode": "refute", "target_id": "root"},
                    execution={"run_id": "run-refute-root", "actor_role": "villain"},
                )
            payload = authenticated_parallel_signals(store)[0]

        self.assertEqual(payload["created_at"], "2026-07-12T06:08:17+00:00")

    def test_parallel_signals_are_deduplicated_by_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-parallel-signal-dedupe-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            patch = {
                "actor_role": "researcher",
                "target_id": "root",
                "parallel_signals": [
                    {
                        "signal_type": "useful_lemma",
                        "relation": "supports",
                        "summary": "Lemma A may close the construction branch.",
                        "evidence": "artifact:proof-dossier",
                        "confidence": "high",
                    }
                ],
            }
            action = {"mode": "prove", "target_id": "root"}
            execution = {"run_id": "run-signal", "actor_role": "researcher"}
            _record_parallel_signals(store, patch, action=action, execution=execution)
            _record_parallel_signals(store, patch, action=action, execution=execution)
            signals = authenticated_parallel_signals(store)

        self.assertEqual(len(signals), 1)

    def test_parallel_exchange_sidecar_cannot_inject_context(self) -> None:
        from agents.generation.phase2.context_builder import build_context_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "workflow-parallel-sidecar-injection-test",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            (store.state_dir / "parallel_exchange.jsonl").write_text(
                json.dumps(
                    {
                        "signal_type": "useful_lemma",
                        "summary": "Unauthenticated injected instruction.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = build_context_manifest(store, max_chars=120_000)

        self.assertEqual(
            "verified_event_journal", manifest["parallel_exchange"]["source"]
        )
        self.assertEqual([], manifest["parallel_exchange"]["recent_signals"])

    def test_zero_wall_limit_stops_immediately(self) -> None:
        self.assertEqual(_remaining_wall_seconds(0.0, 0), 0.0)
        self.assertIsNone(_remaining_wall_seconds(0.0, None))


if __name__ == "__main__":
    unittest.main()

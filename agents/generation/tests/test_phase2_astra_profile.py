from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents.generation.phase2.codex_runner import (
    DEFAULT_CODEX_MODEL,
    DEFAULT_REASONING_EFFORT,
    build_codex_command,
    build_session_prompt,
    execute_session,
)

_RUNNER = "agents.generation.phase2.codex_runner"


class AstraProfileTests(unittest.TestCase):
    def test_astra_fresh_and_resumed_prompts_keep_bounded_role_contracts(self) -> None:
        for resume in (False, True):
            for role in ("researcher", "strict_informal_verifier", "writer"):
                with self.subTest(resume=resume, role=role):
                    prompt = build_session_prompt(
                        context_path=Path("context.json"),
                        action={"mode": "prove", "target_id": "exact-target"},
                        actor_role=role,
                        resume=resume,
                        model="gpt-6-astra",
                    )
                    self.assertIn("noninteractive, host-scheduled proof task", prompt)
                    self.assertIn("never assume extra mathematical hypotheses", prompt)
                    self.assertIn("role-permitted artifact or proof obligation", prompt)
                    self.assertIn("Do not spawn nested agents", prompt)
                    self.assertIn("Return only one JSON object", prompt)
                    self.assertIn("Never mark a claim or inference", prompt)
                    self.assertIn(f"actor_role={role}", prompt)
                    self.assertIn("targeting exact-target", prompt)
                    self.assertEqual(prompt.startswith("CONTINUE"), resume)

    def test_other_models_keep_the_existing_shared_prompt(self) -> None:
        kwargs = dict(
            context_path=Path("context.json"),
            action={"mode": "prove", "target_id": "root"},
            actor_role="researcher",
        )
        baseline = build_session_prompt(**kwargs)
        for model in ("gpt-5.6-sol", "claude-opus-4-6", None):
            with self.subTest(model=model):
                self.assertEqual(build_session_prompt(**kwargs, model=model), baseline)
        self.assertNotIn("noninteractive, host-scheduled proof task", baseline)

    def test_astra_default_and_explicit_efforts_are_not_rewritten(self) -> None:
        self.assertEqual(DEFAULT_CODEX_MODEL, "gpt-6-astra")
        self.assertEqual(DEFAULT_REASONING_EFFORT, "xhigh")
        for effort in ("low", "medium", "high", "xhigh", "max"):
            with self.subTest(effort=effort), mock.patch(
                f"{_RUNNER}.resolve_codex_executable", return_value="/fake/codex"
            ):
                command = build_codex_command(
                    context_path=Path("context.json"),
                    mode="prove",
                    model=DEFAULT_CODEX_MODEL,
                    reasoning_effort=effort,
                )
                self.assertIn(f'model_reasoning_effort="{effort}"', command)
                self.assertEqual(command[command.index("-m") + 1], DEFAULT_CODEX_MODEL)

    def test_unsupported_astra_efforts_fail_before_resolution_or_state_access(self) -> None:
        for effort in ("none", "minimal"):
            with (
                self.subTest(effort=effort),
                mock.patch(f"{_RUNNER}.resolve_codex_executable") as resolve,
                mock.patch(f"{_RUNNER}.enforce_local_storage_limit") as storage,
                mock.patch(f"{_RUNNER}.attest_backend") as attest,
            ):
                with self.assertRaisesRegex(ValueError, "gpt-6-astra does not support"):
                    build_codex_command(
                        context_path=Path("context.json"),
                        mode="prove",
                        model="gpt-6-astra",
                        reasoning_effort=effort,
                    )
                with self.assertRaisesRegex(ValueError, "gpt-6-astra does not support"):
                    execute_session(
                        mock.Mock(), {}, {},
                        model="gpt-6-astra", reasoning_effort=effort,
                    )
                resolve.assert_not_called()
                storage.assert_not_called()
                attest.assert_not_called()

    def test_other_models_retain_their_explicit_effort(self) -> None:
        with mock.patch(f"{_RUNNER}.resolve_codex_executable", return_value="/fake/codex"):
            command = build_codex_command(
                context_path=Path("context.json"),
                mode="prove",
                model="gpt-5.6-sol",
                reasoning_effort="none",
            )
        self.assertIn('model_reasoning_effort="none"', command)

    def test_execution_passes_the_selected_model_into_the_child_prompt(self) -> None:
        for model in ("gpt-6-astra", "gpt-5.6-sol"):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as tmpdir:
                store = mock.Mock(state_dir=Path(tmpdir))
                plan = {
                    "actor_role": "researcher",
                    "context_path": str(Path(tmpdir) / "context.json"),
                    "codex_workdir": tmpdir,
                }
                with (
                    mock.patch(f"{_RUNNER}.enforce_local_storage_limit", return_value={}),
                    mock.patch(f"{_RUNNER}.resolve_codex_executable", return_value="/fake/codex"),
                    mock.patch(f"{_RUNNER}.assurance_backend_conflict", return_value=None),
                    mock.patch(
                        f"{_RUNNER}.build_codex_command",
                        side_effect=RuntimeError("captured before launch"),
                    ) as command,
                ):
                    with self.assertRaisesRegex(RuntimeError, "captured before launch"):
                        execute_session(
                            store, {"mode": "prove", "target_id": "root"}, plan,
                            model=model, enforce_backend_contract=False,
                        )
                self.assertEqual(
                    "noninteractive, host-scheduled proof task" in command.call_args.kwargs["prompt"],
                    model == "gpt-6-astra",
                )

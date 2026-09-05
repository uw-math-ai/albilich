from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import patch

from agents.generation.phase2 import cli
from agents.generation.phase2.backend_contract import BackendContractError


class CliPreflightTests(unittest.TestCase):
    def test_bad_runtime_fails_before_store_initialization(self) -> None:
        for command in (["attempt", "example"], ["run", "example", "--execute"]):
            with contextlib.ExitStack() as stack:
                stack.enter_context(self.subTest(command=command))
                stack.enter_context(patch.object(
                    cli, "attest_backend", side_effect=BackendContractError("missing helper")
                ))
                store = stack.enter_context(patch.object(cli, "_store"))
                stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                with self.assertRaises(SystemExit) as raised:
                    cli.main(command)
                self.assertEqual(2, raised.exception.code)
                store.assert_not_called()

    def test_default_astra_xhigh_and_explicit_override(self) -> None:
        for flags, expected in (([], "gpt-6-astra"), (["--model", "gpt-5.6-sol"], "gpt-5.6-sol")):
            with contextlib.ExitStack() as stack:
                stack.enter_context(self.subTest(flags=flags))
                attest = stack.enter_context(patch.object(cli, "attest_backend"))
                for name in (
                    "_store", "_ensure_initialized_if_problem_file",
                    "_apply_completion_policy", "_apply_cas_assets", "_print",
                ):
                    stack.enter_context(patch.object(cli, name))
                stack.enter_context(patch.object(
                    cli, "_maybe_start_run_dashboard", return_value=({}, None)
                ))
                workflow = stack.enter_context(patch.object(cli, "run_workflow", return_value={}))
                cli.main(["attempt", "example", "--dry-run", *flags])
                attest.assert_not_called()
                self.assertEqual(expected, workflow.call_args.kwargs["model"])
                self.assertEqual("xhigh", workflow.call_args.kwargs["reasoning_effort"])


if __name__ == "__main__":
    unittest.main()

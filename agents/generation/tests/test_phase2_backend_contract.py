from __future__ import annotations

import shutil
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from agents.generation.phase2.backend_contract import (
    BackendContractError,
    _codex_companion_paths,
    attest_backend,
    attested_backend_unchanged,
    parse_backend_version,
    validate_launch_command,
)
from agents.generation.phase2.claude_runner import build_claude_command
from agents.generation.phase2.codex_runner import (
    DEFAULT_SANDBOX,
    _codex_child_exec_args,
    build_codex_command,
)


class BackendContractTests(unittest.TestCase):
    def test_npm_companions_follow_platform_package_or_legacy_vendor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "agents.generation.phase2.backend_contract.platform.machine", return_value="aarch64"
        ), patch("agents.generation.phase2.backend_contract.sys.platform", "linux"):
            root = Path(tmpdir) / "@openai" / "codex"
            wrapper = root / "bin" / "codex.js"
            for vendor in (root / "vendor", root.parent / "codex-linux-arm64" / "vendor"):
                native = vendor / "aarch64-unknown-linux-musl" / "bin" / "codex"
                native.parent.mkdir(parents=True, exist_ok=True)
                native.write_text("native CLI", encoding="utf-8")
                self.assertEqual([native, native.with_name("codex-code-mode-host")], _codex_companion_paths(wrapper))
                native.unlink()

    def test_codex_153_requires_and_rechecks_code_mode_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "codex"
            binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            binary.chmod(0o755)
            helper = binary.with_name("codex-code-mode-host")
            def probe(argv):
                if argv[-1] == "--version":
                    return "codex-cli 0.153.0"
                return "--config --disable --ignore-user-config --output-last-message --strict-config"
            with patch("agents.generation.phase2.backend_contract._probe", side_effect=probe):
                with self.assertRaisesRegex(BackendContractError, "codex-code-mode-host"):
                    attest_backend(str(binary), "codex")
                helper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                helper.chmod(0o755)
                attestation = attest_backend(str(binary), "codex")
                self.assertTrue(attested_backend_unchanged(attestation))
                helper.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
                self.assertFalse(attested_backend_unchanged(attestation))
                self.assertNotEqual(attestation["attestation_sha256"], attest_backend(str(binary), "codex")["attestation_sha256"])
                helper.unlink()
                with self.assertRaisesRegex(BackendContractError, "codex-code-mode-host"):
                    attest_backend(str(binary), "codex")

    def test_version_parser_rejects_nonsemantic_output(self) -> None:
        self.assertEqual(parse_backend_version("codex", "codex-cli 0.152.7"), (0, 152, 7))
        with self.assertRaises(BackendContractError):
            parse_backend_version("claude", "Claude Code current")

    def test_untested_version_fails_before_capability_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "codex"
            binary.write_text(
                "#!/bin/sh\nprintf 'codex-cli 0.151.9\\n'\n",
                encoding="utf-8",
            )
            binary.chmod(0o755)
            with self.assertRaisesRegex(BackendContractError, "untested codex CLI version"):
                attest_backend(str(binary), "codex")

            binary.write_text(
                "#!/bin/sh\nprintf 'codex-cli 0.154.0\\n'\n",
                encoding="utf-8",
            )
            binary.chmod(0o755)
            with self.assertRaisesRegex(BackendContractError, "untested codex CLI version"):
                attest_backend(str(binary), "codex")

    def test_writable_or_unbounded_probe_executable_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            writable = Path(tmpdir) / "writable-claude"
            writable.write_text(
                "#!/bin/sh\nprintf '2.1.4 (Claude Code)\\n'\n",
                encoding="utf-8",
            )
            writable.chmod(0o775)
            with self.assertRaisesRegex(BackendContractError, "group- or world-writable"):
                attest_backend(str(writable), "claude")

            noisy = Path(tmpdir) / "noisy-claude"
            noisy.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"--version\" ]; then "
                "printf '2.1.4 (Claude Code)\\n'; "
                "else head -c 1200000 /dev/zero; fi\n",
                encoding="utf-8",
            )
            noisy.chmod(0o755)
            with self.assertRaises(BackendContractError):
                attest_backend(str(noisy), "claude")

    def test_capability_attested_claude_command_and_argv_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "claude"
            help_flags = " ".join(
                (
                    "--add-dir",
                    "--disallowedTools",
                    "--output-format",
                    "--permission-mode",
                    "--setting-sources",
                    "--settings",
                    "--strict-mcp-config",
                    "--tools",
                    "--verbose",
                )
            )
            binary.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"--version\" ]; then printf '2.1.4 (Claude Code)\\n'; "
                f"else printf '%s\\n' '{help_flags}'; fi\n",
                encoding="utf-8",
            )
            binary.chmod(0o755)
            attestation = attest_backend(str(binary), "claude")
            command = build_claude_command(
                prompt="return one patch",
                claude_bin=str(binary),
            )
            validate_launch_command("claude", command, attestation)
            unsafe = [*command[:-1], "--no-sandbox", command[-1]]
            with self.assertRaisesRegex(BackendContractError, "unsafe backend launch"):
                validate_launch_command("claude", unsafe, attestation)

    def test_cache_and_launch_guard_detect_metadata_preserving_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "claude"
            help_flags = " ".join(
                (
                    "--add-dir",
                    "--disallowedTools",
                    "--output-format",
                    "--permission-mode",
                    "--setting-sources",
                    "--settings",
                    "--strict-mcp-config",
                    "--tools",
                    "--verbose",
                )
            )
            template = (
                "#!/bin/sh\n"
                "if [ \"$1\" = \"--version\" ]; then printf '2.1.{patch} (Claude Code)\\n'; "
                f"else printf '%s\\n' '{help_flags}'; fi\n"
            )
            binary.write_text(template.format(patch=4), encoding="utf-8")
            binary.chmod(0o755)
            attestation = attest_backend(str(binary), "claude")
            original_stat = binary.stat()

            binary.write_text(template.format(patch=5), encoding="utf-8")
            binary.chmod(0o755)
            os.utime(
                binary,
                ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
            )
            self.assertEqual(binary.stat().st_size, original_stat.st_size)
            self.assertFalse(attested_backend_unchanged(attestation))

            refreshed = attest_backend(str(binary), "claude")
            self.assertEqual(refreshed["version"], "2.1.5")
            self.assertNotEqual(
                refreshed["executable_sha256"],
                attestation["executable_sha256"],
            )
            command = build_claude_command(
                prompt="return one patch",
                claude_bin=str(binary),
            )
            with self.assertRaisesRegex(BackendContractError, "changed before launch"):
                validate_launch_command("claude", command, attestation)

    @unittest.skipUnless(shutil.which("codex"), "Codex CLI is not installed")
    def test_installed_codex_boundary_is_attested(self) -> None:
        attestation = attest_backend("codex", "codex")
        command = build_codex_command(
            context_path=Path("/tmp/albilich-contract/context.json"),
            mode="prove",
            codex_bin=str(attestation["executable_path"]),
            sandbox=DEFAULT_SANDBOX,
            codex_workdir=Path("/tmp/albilich-contract"),
            output_last_message=Path("/tmp/albilich-contract/final.json"),
            extra_args=_codex_child_exec_args(),
        )
        validate_launch_command("codex", command, attestation)
        self.assertIn(attestation["version"].split(".")[:2], (["0", "152"], ["0", "153"]))
        self.assertEqual(len(attestation["attestation_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()

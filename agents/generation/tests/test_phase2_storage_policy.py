from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.generation.phase2.audit_checkpoint import (
    canonical_signature_payload,
    create_signed_audit_checkpoint,
    sign_ed25519,
)
from agents.generation.phase2.storage_policy import (
    LOCAL_HARD_LIMIT_ENV,
    StoragePolicyError,
    audit_local_storage,
    create_cold_storage_bundle,
    enforce_local_storage_limit,
    restore_cold_storage_bundle,
    verify_cold_storage_bundle,
)
from agents.generation.phase2.store import ProofStateStore


@unittest.skipUnless(shutil.which("openssl"), "OpenSSL is required")
class StoragePolicyTests(unittest.TestCase):
    def _keys(self, root: Path) -> tuple[Path, Path]:
        private_key = root / "audit-private.pem"
        public_key = root / "audit-public.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private_key)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            [
                "openssl",
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
        return private_key, public_key

    def test_signed_archive_prunes_only_eligible_files_and_restores_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ProofStateStore("storage-roundtrip", generation_root=root / "generation")
            store.init_problem("The root theorem holds.")
            context = store.state_dir / "contexts" / "rev0" / "context.json"
            log = store.state_dir / "workflow_runs" / "run-1" / "codex.log"
            console = store.state_dir / "albilich_run_console.json"
            artifact = store.state_dir / "artifacts" / "proof.txt"
            context.parent.mkdir(parents=True)
            log.parent.mkdir(parents=True)
            artifact.parent.mkdir(parents=True)
            context.write_bytes(b'{"bounded":"context"}\n')
            log.write_bytes(b"raw session log\n")
            console.write_bytes(b'{"derived":"console"}\n')
            artifact.write_bytes(b"authoritative mathematical artifact\n")
            original = {
                context.relative_to(store.state_dir): context.read_bytes(),
                log.relative_to(store.state_dir): log.read_bytes(),
                console.relative_to(store.state_dir): console.read_bytes(),
            }

            private_key, public_key = self._keys(root)
            checkpoint = root / "checkpoint.json"
            create_signed_audit_checkpoint(
                store, output_path=checkpoint, private_key_path=private_key
            )
            bundle = root / "cold-storage"
            archived = create_cold_storage_bundle(
                store,
                bundle_dir=bundle,
                checkpoint_path=checkpoint,
                private_key_path=private_key,
                prune_local=True,
            )
            self.assertTrue(archived["valid"])
            self.assertEqual(archived["pruned_files"], 3)
            self.assertFalse(context.exists())
            self.assertFalse(log.exists())
            self.assertFalse(console.exists())
            self.assertTrue(artifact.is_file())
            verified = verify_cold_storage_bundle(
                bundle, public_key_path=public_key
            )
            self.assertTrue(verified["valid"], verified["errors"])

            restored = restore_cold_storage_bundle(
                store, bundle_dir=bundle, public_key_path=public_key
            )
            self.assertEqual(restored["restored_files"], 3)
            for relative, content in original.items():
                self.assertEqual((store.state_dir / relative).read_bytes(), content)

            with (bundle / "payload.tar.gz").open("ab") as handle:
                handle.write(b"tamper")
            invalid = verify_cold_storage_bundle(
                bundle, public_key_path=public_key
            )
            self.assertFalse(invalid["valid"])
            self.assertIn("archive payload byte count", " ".join(invalid["errors"]))

    def test_hard_limit_blocks_new_sessions_without_deleting_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ProofStateStore("storage-limit", generation_root=root / "generation")
            store.init_problem("The root theorem holds.")
            large_log = store.state_dir / "workflow_runs" / "run" / "large.log"
            large_log.parent.mkdir(parents=True)
            large_log.write_bytes(b"x" * (1024 * 1024 + 64))
            with patch.dict(os.environ, {LOCAL_HARD_LIMIT_ENV: str(1024 * 1024)}):
                report = audit_local_storage(store)
                self.assertFalse(report["within_hard_limit"])
                with self.assertRaises(StoragePolicyError):
                    enforce_local_storage_limit(store)
            self.assertTrue(store.db_path.is_file())
            self.assertTrue(large_log.is_file())

    def test_failed_preprune_verification_removes_only_the_incomplete_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ProofStateStore(
                "storage-preprune-failure", generation_root=root / "generation"
            )
            store.init_problem("The root theorem holds.")
            context = store.state_dir / "contexts" / "context.json"
            context.parent.mkdir(parents=True)
            context.write_bytes(b"context bytes\n")
            private_key, _ = self._keys(root)
            checkpoint = root / "checkpoint.json"
            create_signed_audit_checkpoint(
                store, output_path=checkpoint, private_key_path=private_key
            )
            bundle = root / "incomplete-bundle"
            with patch(
                "agents.generation.phase2.storage_policy.verify_cold_storage_bundle",
                return_value={"valid": False, "errors": ["injected verification failure"]},
            ):
                with self.assertRaisesRegex(
                    StoragePolicyError, "injected verification failure"
                ):
                    create_cold_storage_bundle(
                        store,
                        bundle_dir=bundle,
                        checkpoint_path=checkpoint,
                        private_key_path=private_key,
                        prune_local=True,
                    )
            self.assertFalse(bundle.exists())
            self.assertEqual(b"context bytes\n", context.read_bytes())

    def test_invalid_signature_fails_before_tar_processing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ProofStateStore("storage-untrusted", generation_root=root / "generation")
            store.init_problem("The root theorem holds.")
            context = store.state_dir / "contexts" / "context.json"
            context.parent.mkdir(parents=True)
            context.write_bytes(b"context bytes\n")
            private_key, public_key = self._keys(root)
            checkpoint = root / "checkpoint.json"
            create_signed_audit_checkpoint(
                store, output_path=checkpoint, private_key_path=private_key
            )
            bundle = root / "bundle"
            create_cold_storage_bundle(
                store,
                bundle_dir=bundle,
                checkpoint_path=checkpoint,
                private_key_path=private_key,
            )
            manifest_path = bundle / "manifest.json"
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            document["signature"]["value_base64"] = base64.b64encode(b"invalid").decode()
            manifest_path.write_text(json.dumps(document), encoding="utf-8")

            with patch(
                "agents.generation.phase2.storage_policy.tarfile.open"
            ) as archive_open:
                result = verify_cold_storage_bundle(
                    bundle, public_key_path=public_key
                )
            self.assertFalse(result["valid"])
            archive_open.assert_not_called()

    def test_signed_bundle_cannot_target_authoritative_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ProofStateStore("storage-scope", generation_root=root / "generation")
            store.init_problem("The root theorem holds.")
            context = store.state_dir / "contexts" / "context.json"
            context.parent.mkdir(parents=True)
            context.write_bytes(b"context bytes\n")
            private_key, public_key = self._keys(root)
            checkpoint = root / "checkpoint.json"
            create_signed_audit_checkpoint(
                store, output_path=checkpoint, private_key_path=private_key
            )
            bundle = root / "bundle"
            create_cold_storage_bundle(
                store,
                bundle_dir=bundle,
                checkpoint_path=checkpoint,
                private_key_path=private_key,
            )
            manifest_path = bundle / "manifest.json"
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            document["payload"]["files"][0]["path"] = "proof_state.sqlite3"
            signature = sign_ed25519(
                canonical_signature_payload(document["payload"]), private_key
            )
            document["signature"]["value_base64"] = base64.b64encode(signature).decode()
            manifest_path.write_text(json.dumps(document), encoding="utf-8")

            result = verify_cold_storage_bundle(
                bundle, public_key_path=public_key
            )
            self.assertFalse(result["valid"])
            self.assertIn("not cold-storage eligible", " ".join(result["errors"]))


if __name__ == "__main__":
    unittest.main()

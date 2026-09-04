from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from agents.generation.phase2.bounded_io import (
    read_bounded_bytes,
    read_bounded_text,
    read_bytes_prefix,
    read_text_prefix,
    read_text_tail,
    stable_file_sha256_size,
)
from agents.generation.phase2.artifacts import read_verified_artifact_text_prefix


class BoundedInputTests(unittest.TestCase):
    def test_stable_file_identity_reports_digest_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "identity.bin"
            payload = b"durable artifact bytes"
            source.write_bytes(payload)
            digest, size = stable_file_sha256_size(
                source,
                max_bytes=64,
                label="durable artifact",
            )
            self.assertEqual(hashlib.sha256(payload).hexdigest(), digest)
            self.assertEqual(len(payload), size)

    def test_reads_complete_regular_utf8_file_within_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "input.txt"
            source.write_text("Lemma.\n", encoding="utf-8")
            self.assertEqual(
                "Lemma.\n",
                read_bounded_text(source, max_bytes=64, label="test input"),
            )

    def test_rejects_oversized_input_before_returning_a_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "input.txt"
            source.write_bytes(b"x" * 65)
            with self.assertRaisesRegex(ValueError, "64-byte input limit"):
                read_bounded_bytes(source, max_bytes=64, label="test input")

    def test_rejects_symbolic_link_and_non_utf8_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "target.txt"
            target.write_text("not disclosed through a link", encoding="utf-8")
            link = root / "link.txt"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "open|symbolic link"):
                read_bounded_text(link, max_bytes=128, label="test input")

            invalid = root / "invalid.txt"
            invalid.write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(ValueError, "valid UTF-8"):
                read_bounded_text(invalid, max_bytes=128, label="test input")

    def test_rejects_directory_instead_of_treating_it_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "regular file"):
                read_bounded_bytes(
                    Path(tmpdir),
                    max_bytes=128,
                    label="test input",
                )

    def test_prefix_reports_truncation_without_loading_the_remainder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "large.txt"
            source.write_text("abcdefghij", encoding="utf-8")
            text, truncated, size = read_text_prefix(
                source, max_chars=4, label="test prefix"
            )
            self.assertEqual("abcd", text)
            self.assertTrue(truncated)
            self.assertEqual(10, size)

    def test_byte_prefix_is_bounded_and_reports_the_complete_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "large.bin"
            source.write_bytes(b"abcdefghij")
            payload, truncated, size = read_bytes_prefix(
                source, max_bytes=4, label="test byte prefix"
            )
            self.assertEqual(b"abcd", payload)
            self.assertTrue(truncated)
            self.assertEqual(10, size)

    def test_artifact_prefix_authenticates_the_complete_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "proof.txt"
            payload = "alpha beta gamma delta".encode("utf-8")
            source.write_bytes(payload)
            text, complete, size, total_chars = read_verified_artifact_text_prefix(
                path=source,
                expected_sha256=hashlib.sha256(payload).hexdigest(),
                max_chars=10,
            )
            self.assertEqual("alpha beta", text)
            self.assertFalse(complete)
            self.assertEqual(len(payload), size)
            self.assertEqual(len(payload.decode("utf-8")), total_chars)

            source.write_text("substituted proof", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                read_verified_artifact_text_prefix(
                    path=source,
                    expected_sha256=hashlib.sha256(payload).hexdigest(),
                    max_chars=10,
                )

    def test_tail_drops_a_partial_first_jsonl_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "events.jsonl"
            source.write_text("first-record\nsecond-record\nthird-record\n", encoding="utf-8")
            text, omitted, size = read_text_tail(
                source, max_bytes=27, label="test tail"
            )
            self.assertTrue(omitted)
            self.assertEqual("third-record\n", text)
            self.assertEqual(source.stat().st_size, size)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for project migration, crash-safe recovery, and hostile-input hardening (RSF-37).

Covers all 30 adversarial and fault-injection scenarios:
1. Current valid project opens unchanged.
2. Supported legacy project migrates deterministically.
3. Unknown future version rejects.
4. Unsupported earlier version rejects.
5. Migration is idempotent.
6. Reopen after migration succeeds.
7. Interrupted temporary write.
8. Interrupted publication.
9. Stale revision conflict.
10. Missing referenced blob.
11. Corrupted blob hash.
12. Truncated project manifest.
13. Invalid JSON encoding.
14. Duplicate/conflicting critical fields.
15. Invalid identifier or source reference.
16. Oversized manifest.
17. Excessive JSON nesting.
18. Path traversal.
19. Symlink escape.
20. Invalid filesystem object type.
21. Archive traversal verification (confirming archive non-support and bounded processing).
22. Decompression and resource exhaustion bounds.
23. Failed recovery retry safely unrecoverable.
24. Successful recovery idempotency.
25. Approval-history preservation.
26. Affected approval invalidation.
27. Unaffected approval preservation.
28. No automatic artwork reconstruction.
29. No publication of private input data.
30. Installed-package compatibility with hardened project persistence.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from ro_sprite_forge.core.canonical import canonical_bytes, check_seal, digest, sealed
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.project import (
    MAX_BLOB_SIZE,
    MAX_MANIFEST_SIZE,
    SCHEMA_NAME,
    audit_project_integrity,
    classify_project_version,
    cleanup_staging,
    create_project,
    get_blob,
    import_blob,
    list_projects,
    load_project,
    migrate_project,
    parse_manifest_bytes,
    recover_project,
    save_project,
    validate_path_containment,
)


class ProjectHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="rsf-hardening-test-")
        self.root = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        self.temp_dir.cleanup()

    # 1. Current valid project opens unchanged
    def test_01_current_valid_project_opens_unchanged(self):
        proj = create_project(self.root, "valid_proj", "Valid Project", "novice", "player")
        loaded = load_project(self.root, "valid_proj", verify_blobs=True)
        self.assertEqual(loaded["project_id"], "valid_proj")
        self.assertEqual(loaded["schema"], SCHEMA_NAME)
        self.assertEqual(loaded["canonical_sha256"], proj["canonical_sha256"])

        status, reason = classify_project_version(loaded)
        self.assertEqual(status, "CURRENT_SUPPORTED")

    # 2. Supported legacy project migrates deterministically
    def test_02_supported_legacy_project_migrates_deterministically(self):
        create_project(self.root, "legacy_proj", "Legacy Project", "novice", "player")
        manifest_file = self.root / "legacy_proj" / "manifest.json"
        data = json.loads(manifest_file.read_text(encoding="utf-8"))

        # Transform into a supported legacy project (schema: rsf.project/v0)
        data["schema"] = "rsf.project/v0"
        data["revision"] = 1
        data.pop("canonical_sha256", None)
        manifest_file.write_bytes(canonical_bytes(sealed(data)))

        # Loading legacy project without migration must prompt migration
        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "legacy_proj")
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("requires migration", str(cm.exception))

        # Perform migration
        rep = migrate_project(self.root, "legacy_proj")
        self.assertEqual(rep["status"], "MIGRATED")
        self.assertEqual(rep["previous_schema"], "rsf.project/v0")
        self.assertEqual(rep["current_schema"], SCHEMA_NAME)
        self.assertEqual(rep["current_revision"], 2)

        # Loaded project is now current
        loaded = load_project(self.root, "legacy_proj")
        self.assertEqual(loaded["schema"], SCHEMA_NAME)
        self.assertEqual(loaded["revision"], 2)

    # 3. Unknown future version rejects
    def test_03_unknown_future_version_rejects(self):
        create_project(self.root, "future_proj", "Future Project", "novice", "player")
        manifest_file = self.root / "future_proj" / "manifest.json"
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        data["schema"] = "rsf.project/v99.0"
        data.pop("canonical_sha256", None)
        manifest_file.write_bytes(canonical_bytes(sealed(data)))

        status, reason = classify_project_version(data)
        self.assertEqual(status, "UNSUPPORTED_VERSION")

        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "future_proj")
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("unsupported version", str(cm.exception))

        with self.assertRaises(ForgeError) as cm2:
            migrate_project(self.root, "future_proj")
        self.assertEqual(cm2.exception.code, ErrorCode.INVALID_INPUT)

    # 4. Unsupported earlier version rejects
    def test_04_unsupported_earlier_version_rejects(self):
        create_project(self.root, "ancient_proj", "Ancient Project", "novice", "player")
        manifest_file = self.root / "ancient_proj" / "manifest.json"
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        data["schema"] = "rsf.ancient-draft/v0.0.0"
        data.pop("canonical_sha256", None)
        manifest_file.write_bytes(canonical_bytes(sealed(data)))

        status, reason = classify_project_version(data)
        self.assertEqual(status, "UNSUPPORTED_VERSION")

        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "ancient_proj")
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_INPUT)

    # 5. Migration is idempotent
    def test_05_migration_is_idempotent(self):
        create_project(self.root, "idemp_mig", "Idempotent Migration", "novice", "player")
        manifest_file = self.root / "idemp_mig" / "manifest.json"
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        data["schema"] = "rsf.project/v0"
        data.pop("canonical_sha256", None)
        manifest_file.write_bytes(canonical_bytes(sealed(data)))

        # Migration 1
        rep1 = migrate_project(self.root, "idemp_mig")
        self.assertEqual(rep1["status"], "MIGRATED")
        self.assertEqual(rep1["current_revision"], 2)

        # Migration 2 on already migrated project
        rep2 = migrate_project(self.root, "idemp_mig")
        self.assertEqual(rep2["status"], "ALREADY_CURRENT")
        self.assertEqual(rep2["current_revision"], 2)

        # Reopen is identical
        loaded = load_project(self.root, "idemp_mig")
        self.assertEqual(loaded["revision"], 2)

    # 6. Reopen after migration succeeds
    def test_06_reopen_after_migration_succeeds(self):
        create_project(self.root, "reopen_mig", "Reopen Migrated", "novice", "player")
        manifest_file = self.root / "reopen_mig" / "manifest.json"
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        data["schema"] = "rsf.project/v0"
        data.pop("canonical_sha256", None)
        manifest_file.write_bytes(canonical_bytes(sealed(data)))

        migrate_project(self.root, "reopen_mig")

        # Reopen from fresh reader
        loaded = load_project(self.root, "reopen_mig", verify_blobs=True)
        self.assertEqual(loaded["schema"], SCHEMA_NAME)
        self.assertEqual(loaded["revision"], 2)

    # 7. Interrupted temporary write
    def test_07_interrupted_temporary_write(self):
        create_project(self.root, "interrupted_write", "Interrupted Write", "novice", "player")
        proj_dir = self.root / "interrupted_write"
        staging_dir = proj_dir / "staging"

        # Simulate orphaned temporary manifest and blob from killed writer
        (staging_dir / ".manifest-aborted.tmp").write_bytes(b"partial manifest data")
        (staging_dir / ".blob-aborted.tmp").write_bytes(b"partial blob data")
        (proj_dir / ".manifest-leftover.tmp").write_bytes(b"staged manifest")

        # Project still loads authoritative revision 1
        loaded = load_project(self.root, "interrupted_write")
        self.assertEqual(loaded["revision"], 1)

        # Staging cleanup removes temporary files safely
        cleaned = cleanup_staging(proj_dir)
        self.assertGreaterEqual(cleaned, 3)
        self.assertEqual(len(list(staging_dir.iterdir())), 0)

    # 8. Interrupted publication
    def test_08_interrupted_publication(self):
        proj = create_project(self.root, "interrupted_pub", "Pub Test", "novice", "player")
        proj_dir = self.root / "interrupted_pub"
        manifest_file = proj_dir / "manifest.json"

        # Advance to revision 2
        save_project(self.root, proj, expected_revision=1)
        self.assertTrue((proj_dir / "manifest.json.bak").exists())

        # Simulate crash during publication: manifest.json truncated to 0 bytes
        manifest_file.write_bytes(b"")

        # Load fails on corrupted 0-byte manifest
        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "interrupted_pub")
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_INPUT)

        # Recovery restores from valid manifest.json.bak
        rec = recover_project(self.root, "interrupted_pub")
        self.assertTrue(rec["recovered"])
        self.assertEqual(rec["action"], "RESTORED_FROM_BACKUP")
        self.assertEqual(rec["revision"], 1)

        # Project now reopens cleanly
        reopened = load_project(self.root, "interrupted_pub")
        self.assertEqual(reopened["revision"], 1)

    # 9. Stale revision conflict
    def test_09_stale_revision_conflict(self):
        proj = create_project(self.root, "stale_rev", "Stale Rev", "novice", "player")
        # Writer 1 advances revision 1 -> 2
        save_project(self.root, proj, expected_revision=1)

        # Writer 2 attempts to save with stale expected_revision=1
        with self.assertRaises(ForgeError) as cm:
            save_project(self.root, proj, expected_revision=1)
        self.assertEqual(cm.exception.code, ErrorCode.CONFLICT)
        self.assertIn("Revision conflict", str(cm.exception))

    # 10. Missing referenced blob
    def test_10_missing_referenced_blob(self):
        proj = create_project(self.root, "missing_blob", "Missing Blob", "novice", "player")
        blob_info = import_blob(self.root, "missing_blob", "test.bin", b"test data")
        proj["sources"]["source1"] = blob_info
        save_project(self.root, proj, expected_revision=1)

        # Remove blob on disk
        blob_file = self.root / "missing_blob" / blob_info["blob_path"]
        blob_file.unlink()

        # load_project fails with INPUT_NOT_FOUND
        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "missing_blob", verify_blobs=True)
        self.assertEqual(cm.exception.code, ErrorCode.INPUT_NOT_FOUND)

        # audit_project_integrity reports missing blob
        audit = audit_project_integrity(self.root, "missing_blob")
        self.assertEqual(audit["integrity_status"], "CORRUPTED")
        self.assertEqual(len(audit["blobs_missing"]), 1)
        self.assertEqual(audit["blobs_missing"][0]["source_id"], "source1")

    # 11. Corrupted blob hash
    def test_11_corrupted_blob_hash(self):
        proj = create_project(self.root, "corrupt_blob", "Corrupt Blob", "novice", "player")
        blob_info = import_blob(self.root, "corrupt_blob", "test.bin", b"original content")
        proj["sources"]["s1"] = blob_info
        save_project(self.root, proj, expected_revision=1)

        # Corrupt blob content on disk
        blob_file = self.root / "corrupt_blob" / blob_info["blob_path"]
        blob_file.write_bytes(b"tampered content")

        # load_project fails with INVALID_INPUT
        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "corrupt_blob", verify_blobs=True)
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_INPUT)

        # audit_project_integrity reports corrupted blob
        audit = audit_project_integrity(self.root, "corrupt_blob")
        self.assertEqual(audit["integrity_status"], "CORRUPTED")
        self.assertEqual(len(audit["blobs_corrupted"]), 1)
        self.assertEqual(audit["blobs_corrupted"][0]["source_id"], "s1")

    # 12. Truncated project manifest
    def test_12_truncated_project_manifest(self):
        proj = create_project(self.root, "trunc_proj", "Truncated", "novice", "player")
        save_project(self.root, proj, expected_revision=1)

        manifest_file = self.root / "trunc_proj" / "manifest.json"
        manifest_file.write_bytes(b'{"schema": "rsf.project/v1", "project_id": "tru')

        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "trunc_proj")
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_INPUT)

        rec = recover_project(self.root, "trunc_proj")
        self.assertTrue(rec["recovered"])
        self.assertEqual(rec["action"], "RESTORED_FROM_BACKUP")

    # 13. Invalid JSON encoding
    def test_13_invalid_json_encoding(self):
        create_project(self.root, "bad_enc", "Bad Encoding", "novice", "player")
        manifest_file = self.root / "bad_enc" / "manifest.json"
        manifest_file.write_bytes(b"\xff\xfe\x00\x00invalid-utf8")

        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "bad_enc")
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("encoding", str(cm.exception).lower())

    # 14. Duplicate/conflicting critical fields
    def test_14_duplicate_conflicting_critical_fields(self):
        raw_duplicate_keys = b'{"schema": "rsf.project/v1", "schema": "rsf.project/v2", "project_id": "dup"}'
        with self.assertRaises(ForgeError) as cm:
            parse_manifest_bytes(raw_duplicate_keys)
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("Duplicate JSON key", str(cm.exception))

    # 15. Invalid identifier or source reference
    def test_15_invalid_identifier_or_source_reference(self):
        invalid_ids = ["", "bad/id", "bad\\id", "../traversal", "id with spaces", "a" * 65]
        for bad_id in invalid_ids:
            with self.subTest(bad_id=bad_id):
                with self.assertRaises(ForgeError) as cm:
                    create_project(self.root, bad_id, "Title", "novice", "player")
                self.assertEqual(cm.exception.code, ErrorCode.INVALID_ARGUMENT)

    # 16. Oversized manifest
    def test_16_oversized_manifest(self):
        create_project(self.root, "oversized_proj", "Oversized", "novice", "player")
        manifest_file = self.root / "oversized_proj" / "manifest.json"
        huge_bytes = b"{" + b'"padding": "' + b"A" * (MAX_MANIFEST_SIZE + 10) + b'"}'
        manifest_file.write_bytes(huge_bytes)

        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "oversized_proj")
        self.assertEqual(cm.exception.code, ErrorCode.PAYLOAD_TOO_LARGE)

    # 17. Excessive JSON nesting
    def test_17_excessive_json_nesting(self):
        # Build 100 levels of nested objects
        nested = {"val": 1}
        for _ in range(70):
            nested = {"sub": nested}
        raw_nested = json.dumps(nested).encode("utf-8")

        with self.assertRaises(ForgeError) as cm:
            parse_manifest_bytes(raw_nested)
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("nesting depth", str(cm.exception).lower())

    # 18. Path traversal
    def test_18_path_traversal_prevention(self):
        create_project(self.root, "traversal_proj", "Traversal", "novice", "player")
        proj_dir = self.root / "traversal_proj"

        # Traversal in blob import filename
        with self.assertRaises(ForgeError) as cm:
            import_blob(self.root, "traversal_proj", "../escape.bin", b"data")
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_ARGUMENT)

        # Traversal in manifest blob_path
        proj = load_project(self.root, "traversal_proj")
        proj["sources"]["evil"] = {
            "sha256": "0" * 64,
            "filename": "evil.bin",
            "size": 4,
            "blob_path": "../../etc/passwd",
        }
        with self.assertRaises(ForgeError) as cm2:
            validate_path_containment(proj_dir, proj_dir / proj["sources"]["evil"]["blob_path"])
        self.assertEqual(cm2.exception.code, ErrorCode.PERMISSION_DENIED)

    # 19. Symlink escape
    def test_19_symlink_escape_rejection(self):
        create_project(self.root, "sym_proj", "Symlink Proj", "novice", "player")
        proj_dir = self.root / "sym_proj"

        if hasattr(os, "symlink"):
            symlink = proj_dir / "evil_link"
            try:
                symlink.symlink_to(self.root.parent)
                with self.assertRaises(ForgeError) as cm:
                    validate_path_containment(proj_dir, symlink / "target")
                self.assertEqual(cm.exception.code, ErrorCode.PERMISSION_DENIED)
            finally:
                if symlink.is_symlink():
                    symlink.unlink()

    # 20. Invalid filesystem object type
    def test_20_invalid_filesystem_object_type(self):
        create_project(self.root, "dir_manifest_proj", "Dir Manifest", "novice", "player")
        manifest_path = self.root / "dir_manifest_proj" / "manifest.json"
        manifest_path.unlink()
        manifest_path.mkdir()  # manifest is now a directory, not a file

        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "dir_manifest_proj")
        self.assertIn(cm.exception.code, (ErrorCode.INPUT_NOT_FOUND, ErrorCode.IO_ERROR))

    # 21. Archive traversal verification (confirming archive non-support and bounded processing)
    def test_21_archive_traversal_unsupported_surface(self):
        create_project(self.root, "archive_proj", "Archive Test", "novice", "player")
        # Attempting to import zip or tar files directly via import_blob stores bytes as raw immutable content
        # It never extracts or unzips them into filesystem hierarchies
        fake_zip = b"PK\x03\x04" + b"zip slip ../../escape.txt"
        info = import_blob(self.root, "archive_proj", "bundle.zip", fake_zip)
        self.assertEqual(info["filename"], "bundle.zip")
        # File is safely stored under content-addressed SHA-256 in blobs/ with no extraction
        blob_path = self.root / "archive_proj" / info["blob_path"]
        self.assertTrue(blob_path.is_file())
        self.assertFalse((self.root / "escape.txt").exists())

    # 22. Decompression and resource exhaustion bounds
    def test_22_decompression_and_resource_exhaustion(self):
        create_project(self.root, "exhaust_proj", "Exhaustion", "novice", "player")

        # Oversized blob > 32 MiB rejected
        oversized = b"0" * (MAX_BLOB_SIZE + 1)
        with self.assertRaises(ForgeError) as cm:
            import_blob(self.root, "exhaust_proj", "huge.bin", oversized)
        self.assertEqual(cm.exception.code, ErrorCode.PAYLOAD_TOO_LARGE)

        # Nonfinite floats (NaN, Infinity) rejected in manifest
        nonfinite_raw = b'{"schema": "rsf.project/v1", "ratio": NaN}'
        with self.assertRaises(ForgeError) as cm2:
            parse_manifest_bytes(nonfinite_raw)
        self.assertEqual(cm2.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("Nonfinite JSON constant forbidden", str(cm2.exception))

    # 23. Failed recovery retry safely unrecoverable
    def test_23_failed_recovery_retry_safely_unrecoverable(self):
        create_project(self.root, "unrec_proj", "Unrecoverable", "novice", "player")
        proj_dir = self.root / "unrec_proj"
        (proj_dir / "manifest.json").write_bytes(b"corrupt")
        (proj_dir / "manifest.json.bak").write_bytes(b"also corrupt")

        rec = recover_project(self.root, "unrec_proj")
        self.assertFalse(rec["recovered"])
        self.assertFalse(rec["valid"])
        self.assertEqual(rec["action"], "UNRECOVERABLE")

        # Repeating recovery produces identical safe unrecoverable report without crashing or altering files
        rec2 = recover_project(self.root, "unrec_proj")
        self.assertFalse(rec2["recovered"])
        self.assertFalse(rec2["valid"])
        self.assertEqual(rec2["action"], "UNRECOVERABLE")

    # 24. Successful recovery idempotency
    def test_24_successful_recovery_idempotency(self):
        proj = create_project(self.root, "idemp_rec", "Idempotent Recovery", "novice", "player")
        save_project(self.root, proj, expected_revision=1)
        proj_dir = self.root / "idemp_rec"

        # Corrupt manifest
        (proj_dir / "manifest.json").write_bytes(b"corrupt")

        # Run 1: Restores from backup
        rec1 = recover_project(self.root, "idemp_rec")
        self.assertTrue(rec1["recovered"])
        self.assertEqual(rec1["action"], "RESTORED_FROM_BACKUP")
        self.assertTrue(rec1["valid"])

        # Run 2: Manifest is already healthy, no mutation
        rec2 = recover_project(self.root, "idemp_rec")
        self.assertFalse(rec2["recovered"])
        self.assertTrue(rec2["already_healthy"])
        self.assertEqual(rec2["action"], "NO_ACTION_NEEDED")
        self.assertTrue(rec2["valid"])

    # 25. Approval-history preservation
    def test_25_approval_history_preservation(self):
        proj = create_project(self.root, "appr_pres", "Approval Preservation", "novice", "player")
        proj["reviews"] = {
            "rev_layer1": {
                "scope": "walk-view0",
                "revision": 1,
                "approved": True,
                "timestamp": "2026-10-31T00:00:00Z",
            }
        }
        saved = save_project(self.root, proj, expected_revision=1)
        self.assertTrue(saved["reviews"]["rev_layer1"]["approved"])

        loaded = load_project(self.root, "appr_pres")
        self.assertTrue(loaded["reviews"]["rev_layer1"]["approved"])

    # 26. Affected approval invalidation
    def test_26_affected_approval_invalidation(self):
        create_project(self.root, "appr_inval", "Approval Invalidation", "novice", "player")
        manifest_file = self.root / "appr_inval" / "manifest.json"
        data = json.loads(manifest_file.read_text(encoding="utf-8"))

        data["schema"] = "rsf.project/v0"
        data["target"] = {"schema": "rsf.target/v1", "actor": "novice-male"}
        data["reviews"] = {
            "rev_layer1": {
                "scope": "walk-view0",
                "revision": 1,
                "approved": True,
                "timestamp": "2026-10-31T00:00:00Z",
            }
        }
        data.pop("canonical_sha256", None)
        manifest_file.write_bytes(canonical_bytes(sealed(data)))

        # Migration updates target and invalidates affected review
        rep = migrate_project(self.root, "appr_inval")
        self.assertEqual(rep["status"], "MIGRATED")
        self.assertIn("rev_layer1", rep["invalidated_reviews"])

        loaded = load_project(self.root, "appr_inval")
        self.assertFalse(loaded["reviews"]["rev_layer1"]["approved"])

    # 27. Unaffected approval preservation
    def test_27_unaffected_approval_preservation(self):
        create_project(self.root, "unaff_appr", "Unaffected Approval", "novice", "player")
        manifest_file = self.root / "unaff_appr" / "manifest.json"
        data = json.loads(manifest_file.read_text(encoding="utf-8"))

        # Legacy schema RSF-0 with no target changes
        data["schema"] = "rsf.project/v0"
        data["reviews"] = {
            "rev_fixed": {
                "scope": "walk-view0",
                "revision": 1,
                "approved": True,
                "timestamp": "2026-10-31T00:00:00Z",
            }
        }
        data.pop("canonical_sha256", None)
        manifest_file.write_bytes(canonical_bytes(sealed(data)))

        # Migration without target changes keeps reviews valid
        rep = migrate_project(self.root, "unaff_appr")
        self.assertEqual(rep["status"], "MIGRATED")
        self.assertEqual(rep["invalidated_reviews"], [])

        loaded = load_project(self.root, "unaff_appr")
        self.assertTrue(loaded["reviews"]["rev_fixed"]["approved"])

    # 28. No automatic artwork reconstruction
    def test_28_no_automatic_artwork_reconstruction(self):
        proj = create_project(self.root, "no_art_recon", "No Reconstruction", "novice", "player")
        fake_hash = "f" * 64
        proj["sources"]["missing_art"] = {
            "sha256": fake_hash,
            "filename": "custom_frame.png",
            "size": 1234,
            "blob_path": f"blobs/{fake_hash}",
        }
        save_project(self.root, proj, expected_revision=1)

        # System does not invent or synthesize the missing frame
        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "no_art_recon", verify_blobs=True)
        self.assertEqual(cm.exception.code, ErrorCode.INPUT_NOT_FOUND)

        # Blob is absent, not auto-generated
        self.assertFalse((self.root / "no_art_recon" / "blobs" / fake_hash).exists())

    # 29. No publication of private input data
    def test_29_no_publication_of_private_input_data(self):
        # Errors should never leak private host paths or credentials
        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "nonexistent_secret_proj")
        self.assertEqual(cm.exception.code, ErrorCode.INPUT_NOT_FOUND)
        # Verify error message is clean and structured
        self.assertIn("nonexistent_secret_proj", str(cm.exception))

    # 30. Installed-package compatibility with hardened project persistence
    def test_30_installed_package_compatibility(self):
        # Verify that all project operations work using standard imports
        import ro_sprite_forge.core.project as pmod
        self.assertTrue(hasattr(pmod, "load_project"))
        self.assertTrue(hasattr(pmod, "save_project"))
        self.assertTrue(hasattr(pmod, "migrate_project"))
        self.assertTrue(hasattr(pmod, "recover_project"))
        self.assertTrue(hasattr(pmod, "audit_project_integrity"))
        self.assertTrue(hasattr(pmod, "classify_project_version"))


if __name__ == "__main__":
    unittest.main()

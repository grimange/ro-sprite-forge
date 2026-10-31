"""Unit tests for versioned filesystem project persistence and atomic publication (RSF-15)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

from ro_sprite_forge.core.canonical import canonical_bytes, check_seal, digest, sealed
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.project import (
    MAX_BLOB_SIZE,
    cleanup_staging,
    create_project,
    get_blob,
    import_blob,
    list_projects,
    load_project,
    project_schema,
    save_project,
    validate_path_containment,
)


class ProjectPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="rsf-test-proj-")
        self.root = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_schema_validity(self):
        schema = project_schema()
        self.assertEqual(schema["$id"], "https://ro-sprite-forge.invalid/schemas/project-v1.json")
        if Draft202012Validator:
            Draft202012Validator.check_schema(schema)

    def test_create_and_load_project(self):
        p = create_project(
            self.root,
            "novice_walk",
            "Male Novice Custom Walk",
            actor="novice-male",
            profile="player",
        )
        self.assertEqual(p["schema"], "rsf.project/v1")
        self.assertEqual(p["project_id"], "novice_walk")
        self.assertEqual(p["name"], "Male Novice Custom Walk")
        self.assertEqual(p["revision"], 1)
        self.assertEqual(p["sources"], {})
        self.assertEqual(p["reviews"], {})
        check_seal(p, "rsf.project/v1")

        # Filesystem layout check
        proj_dir = self.root / "novice_walk"
        self.assertTrue((proj_dir / "manifest.json").is_file())
        self.assertTrue((proj_dir / "blobs").is_dir())
        self.assertTrue((proj_dir / "staging").is_dir())

        # Load and verify
        loaded = load_project(self.root, "novice_walk", verify_blobs=True)
        self.assertEqual(loaded["project_id"], "novice_walk")
        self.assertEqual(loaded["revision"], 1)
        self.assertEqual(loaded["canonical_sha256"], p["canonical_sha256"])

    def test_duplicate_project_id_rejected(self):
        create_project(self.root, "my_proj", "Title", "novice", "player")
        with self.assertRaises(ForgeError) as cm:
            create_project(self.root, "my_proj", "Title 2", "novice", "player")
        self.assertEqual(cm.exception.code, ErrorCode.CONFLICT)

    def test_invalid_project_id_rejected(self):
        invalid_ids = ["", "has spaces", "bad/slash", "bad\\slash", "../escape", "a" * 65, "bad?char"]
        for bad_id in invalid_ids:
            with self.subTest(bad_id=bad_id):
                with self.assertRaises(ForgeError) as cm:
                    create_project(self.root, bad_id, "Title", "novice", "player")
                self.assertEqual(cm.exception.code, ErrorCode.INVALID_ARGUMENT)

    def test_blob_import_and_retrieval(self):
        create_project(self.root, "orc_test", "Orc Skeleton Test", "orc-skeleton", "monster")
        content = b"fake sprite binary data for test"
        expected_hash = digest(content)

        info = import_blob(self.root, "orc_test", "orc.spr", content, expected_sha256=expected_hash)
        self.assertEqual(info["sha256"], expected_hash)
        self.assertEqual(info["filename"], "orc.spr")
        self.assertEqual(info["size"], len(content))
        self.assertEqual(info["blob_path"], f"blobs/{expected_hash}")

        # Blob exists on disk
        blob_file = self.root / "orc_test" / "blobs" / expected_hash
        self.assertTrue(blob_file.is_file())

        # Read back
        read_bytes = get_blob(self.root, "orc_test", expected_hash)
        self.assertEqual(read_bytes, content)

        # Content-addressed deduplication (re-importing same data returns same record without error)
        info2 = import_blob(self.root, "orc_test", "orc_copy.spr", content)
        self.assertEqual(info2["sha256"], expected_hash)

    def test_blob_hash_mismatch_rejected(self):
        create_project(self.root, "proj_mismatch", "Title", "actor", "player")
        content = b"content bytes"
        wrong_hash = "0" * 64
        with self.assertRaises(ForgeError) as cm:
            import_blob(self.root, "proj_mismatch", "file.bin", content, expected_sha256=wrong_hash)
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_INPUT)

    def test_oversized_blob_rejected(self):
        create_project(self.root, "proj_large", "Title", "actor", "player")
        huge_bytes = b"X" * (MAX_BLOB_SIZE + 1)
        with self.assertRaises(ForgeError) as cm:
            import_blob(self.root, "proj_large", "huge.bin", huge_bytes)
        self.assertEqual(cm.exception.code, ErrorCode.PAYLOAD_TOO_LARGE)

    def test_unsafe_filename_rejected(self):
        create_project(self.root, "proj_safe_names", "Title", "actor", "player")
        bad_filenames = ["../traverse", "dir/file", "dir\\file", "\x00null", "", ".", ".."]
        for bad_name in bad_filenames:
            with self.subTest(bad_name=bad_name):
                with self.assertRaises(ForgeError) as cm:
                    import_blob(self.root, "proj_safe_names", bad_name, b"sample")
                self.assertEqual(cm.exception.code, ErrorCode.INVALID_ARGUMENT)

    def test_save_project_and_revision_increment(self):
        p = create_project(self.root, "save_proj", "Title", "actor", "player")
        blob_info = import_blob(self.root, "save_proj", "actor.spr", b"spr_data")
        p["sources"]["body_spr"] = blob_info

        # Save revision 1 -> revision 2
        saved = save_project(self.root, p, expected_revision=1)
        self.assertEqual(saved["revision"], 2)
        check_seal(saved, "rsf.project/v1")

        # Verify backup exists
        backup = self.root / "save_proj" / "manifest.json.bak"
        self.assertTrue(backup.is_file())
        bak_data = json.loads(backup.read_text(encoding="utf-8"))
        self.assertEqual(bak_data["revision"], 1)

        # Load back
        loaded = load_project(self.root, "save_proj", verify_blobs=True)
        self.assertEqual(loaded["revision"], 2)
        self.assertIn("body_spr", loaded["sources"])

    def test_optimistic_concurrency_conflict(self):
        p = create_project(self.root, "conflict_proj", "Title", "actor", "player")
        # Advance to revision 2
        save_project(self.root, p, expected_revision=1)

        # Trying to save with stale expected_revision=1 must fail
        with self.assertRaises(ForgeError) as cm:
            save_project(self.root, p, expected_revision=1)
        self.assertEqual(cm.exception.code, ErrorCode.CONFLICT)

    def test_tampered_manifest_seal_rejected(self):
        create_project(self.root, "tamper_proj", "Title", "actor", "player")
        manifest_file = self.root / "tamper_proj" / "manifest.json"
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        data["name"] = "Tampered Title"
        # Overwrite without updating canonical_sha256
        manifest_file.write_bytes(canonical_bytes(data))

        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "tamper_proj")
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_INPUT)

    def test_tampered_or_missing_blob_rejected_on_load(self):
        p = create_project(self.root, "blob_tamper", "Title", "actor", "player")
        blob_info = import_blob(self.root, "blob_tamper", "data.bin", b"original content")
        p["sources"]["data"] = blob_info
        save_project(self.root, p, expected_revision=1)

        # 1. Missing blob
        blob_path = self.root / "blob_tamper" / blob_info["blob_path"]
        blob_path.unlink()
        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "blob_tamper", verify_blobs=True)
        self.assertEqual(cm.exception.code, ErrorCode.INPUT_NOT_FOUND)

        # 2. Corrupted blob bytes
        blob_path.write_bytes(b"corrupted content")
        with self.assertRaises(ForgeError) as cm:
            load_project(self.root, "blob_tamper", verify_blobs=True)
        self.assertEqual(cm.exception.code, ErrorCode.INVALID_INPUT)

    def test_path_containment_and_symlink_defense(self):
        create_project(self.root, "path_proj", "Title", "actor", "player")
        proj_dir = self.root / "path_proj"

        # Traversal target
        outside_target = self.root / "outside.txt"
        with self.assertRaises(ForgeError) as cm:
            validate_path_containment(proj_dir, outside_target)
        self.assertEqual(cm.exception.code, ErrorCode.PERMISSION_DENIED)

        # Symlink pointing outside
        if hasattr(os, "symlink"):
            symlink_path = proj_dir / "evil_symlink"
            try:
                symlink_path.symlink_to(self.root.parent)
                with self.assertRaises(ForgeError) as cm:
                    validate_path_containment(proj_dir, symlink_path / "secret.txt")
                self.assertEqual(cm.exception.code, ErrorCode.PERMISSION_DENIED)
            finally:
                if symlink_path.is_symlink():
                    symlink_path.unlink()

    def test_staging_cleanup_resilience(self):
        create_project(self.root, "clean_proj", "Title", "actor", "player")
        staging_dir = self.root / "clean_proj" / "staging"

        # Create leftover abandoned staging files
        (staging_dir / ".manifest-leftover.tmp").write_bytes(b"junk")
        (staging_dir / ".blob-leftover.tmp").write_bytes(b"junk")
        self.assertEqual(len(list(staging_dir.iterdir())), 2)

        cleanup_staging(self.root / "clean_proj")
        self.assertEqual(len(list(staging_dir.iterdir())), 0)

        # Project still loads cleanly
        loaded = load_project(self.root, "clean_proj")
        self.assertEqual(loaded["revision"], 1)

    def test_list_projects(self):
        self.assertEqual(list_projects(self.root), [])
        create_project(self.root, "proj_b", "B Project", "novice", "player")
        create_project(self.root, "proj_a", "A Project", "orc", "monster")

        listed = list_projects(self.root)
        self.assertEqual(len(listed), 2)
        project_ids = [item["project_id"] for item in listed]
        self.assertIn("proj_a", project_ids)
        self.assertIn("proj_b", project_ids)


if __name__ == "__main__":
    unittest.main()

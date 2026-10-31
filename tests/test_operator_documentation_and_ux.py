"""Tests for operator documentation integrity, error catalog coverage, and workbench UX ergonomics (RSF-38)."""

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from ro_sprite_forge import cli
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.project import (
    create_project,
    load_project,
    recover_project,
    save_project,
)



import ro_sprite_forge


def _find_docs_dir() -> Path:
    for cand in [
        Path(__file__).resolve().parent.parent / "docs" / "operator",
        Path.cwd() / "docs" / "operator",
    ]:
        if cand.is_dir():
            return cand.resolve()
    return (Path(__file__).resolve().parent.parent / "docs" / "operator").resolve()


DOCS_DIR = _find_docs_dir()
STATIC_DIR = Path(ro_sprite_forge.__file__).resolve().parent / "static"


class TestOperatorDocumentation(unittest.TestCase):
    """Verify operator documentation files exist and have intact references."""

    EXPECTED_DOCS = [
        "README.md",
        "QUICKSTART.md",
        "PRODUCTION_GUIDE.md",
        "COMPATIBILITY_AND_ACTIONS.md",
        "PERSISTENCE_AND_RECOVERY.md",
        "ERROR_CATALOG.md",
        "TUTORIAL.md",
    ]

    def test_all_expected_docs_exist_and_non_empty(self):
        for doc_name in self.EXPECTED_DOCS:
            doc_path = DOCS_DIR / doc_name
            self.assertTrue(doc_path.exists(), f"Missing operator document: {doc_path}")
            self.assertGreater(doc_path.stat().st_size, 500, f"Document {doc_name} is too small")

    def test_markdown_links_resolve_within_operator_docs(self):
        """Check all intra-documentation markdown links in docs/operator/*.md."""
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        for doc_name in self.EXPECTED_DOCS:
            doc_path = DOCS_DIR / doc_name
            content = doc_path.read_text(encoding="utf-8")
            for match in link_pattern.finditer(content):
                target = match.group(2)
                # Ignore external web links and mailto
                if target.startswith("http://") or target.startswith("https://") or target.startswith("mailto:"):
                    continue
                # Split off anchor fragments if present
                file_target = target.split("#")[0]
                if file_target:
                    target_path = (DOCS_DIR / file_target).resolve()
                    self.assertTrue(
                        target_path.exists(),
                        f"Broken link '{target}' in {doc_name} -> cannot find {target_path}",
                    )


class TestErrorCatalogCompleteness(unittest.TestCase):
    """Verify error catalog documents all formal error codes and key diagnostic identifiers."""

    def test_all_formal_error_codes_documented(self):
        catalog_path = DOCS_DIR / "ERROR_CATALOG.md"
        content = catalog_path.read_text(encoding="utf-8")
        for err_code in ErrorCode:
            self.assertIn(
                f"### `{err_code.value}`",
                content,
                f"Formal ErrorCode '{err_code.value}' is not documented in ERROR_CATALOG.md",
            )

    def test_key_diagnostic_identifiers_documented(self):
        catalog_path = DOCS_DIR / "ERROR_CATALOG.md"
        content = catalog_path.read_text(encoding="utf-8")
        required_diagnostics = [
            "UNDERSPECIFIED_LAYER_TOPOLOGY",
            "SOURCE_HASH_MISMATCH",
            "UNBOUND_PRODUCTION_COMPOSITION",
            "VIDEO_SELECTION_NOT_EXACT",
            "VIDEO_TOOL_UNAVAILABLE",
            "MISMATCHED_FRAME_COUNT",
            "MIGRATION_REQUIRED",
            "UNSUPPORTED_VERSION",
            "STALE_REVISION_CONFLICT",
            "UNRECOVERABLE",
            "PARTIAL_DIAGNOSTIC",
            "STALE_REVIEW",
            "M0_PARTIAL_NATIVE_UNVERIFIED",
            "ANCHOR_MISSING",
        ]
        for diag in required_diagnostics:
            self.assertIn(
                f"### `{diag}`",
                content,
                f"Required diagnostic identifier '{diag}' is not documented in ERROR_CATALOG.md",
            )


class TestCliCommandConsistency(unittest.TestCase):
    """Verify documented CLI commands exist in cli.py."""

    def test_documented_cli_commands_exist(self):
        parser = cli.build_parser()
        # Extract subparser command choices
        subparser_actions = [
            action for action in parser._actions if isinstance(action, cli.argparse._SubParsersAction)
        ]
        self.assertGreater(len(subparser_actions), 0, "No subparsers found in CLI parser")
        registered_commands = subparser_actions[0].choices.keys()

        documented_commands = [
            "inspect",
            "plan",
            "resolve",
            "ledger",
            "coverage",
            "preview",
            "compile",
            "verify",
            "roundtrip",
            "serve",
        ]
        for cmd in documented_commands:
            self.assertIn(
                cmd,
                registered_commands,
                f"Command '{cmd}' is documented in QUICKSTART.md but missing from cli.py choices",
            )


class TestWorkbenchErgonomicsAndAccessibility(unittest.TestCase):
    """Verify static assets incorporate integer nearest-neighbor zoom, checkerboard background, and keyboard controls."""

    def test_index_html_has_zoom_and_background_controls(self):
        html_path = STATIC_DIR / "index.html"
        content = html_path.read_text(encoding="utf-8")

        self.assertIn('id="preview-zoom"', content)
        self.assertIn('id="preview-bg"', content)
        self.assertIn('id="preview-viewport"', content)
        self.assertIn("checker-dark", content)
        self.assertIn("checker-light", content)
        self.assertIn("solid-white", content)
        self.assertIn("[A] Approve displayed scope", content)
        self.assertIn("[R] Reject displayed scope", content)
        self.assertIn("[Esc] Cancel", content)

    def test_workbench_css_has_pixelated_and_responsive_rules(self):
        css_path = STATIC_DIR / "workbench.css"
        content = css_path.read_text(encoding="utf-8")

        self.assertIn("image-rendering: pixelated", content)
        self.assertIn(".preview-viewport", content)
        self.assertIn(".preview-viewport.bg-checker-dark", content)
        self.assertIn(".preview-viewport.bg-checker-light", content)
        self.assertIn(".preview-viewport.bg-solid-white", content)
        self.assertIn("@media (max-width: 1280px)", content)
        self.assertIn("@media (max-width: 1024px)", content)

    def test_workbench_js_has_keyboard_and_zoom_handlers(self):
        js_path = STATIC_DIR / "workbench.js"
        content = js_path.read_text(encoding="utf-8")

        self.assertIn("applyAnimZoom", content)
        self.assertIn("setPreviewBackground", content)
        self.assertIn("cyclePreviewBackground", content)
        self.assertIn("ArrowLeft", content)
        self.assertIn("ArrowRight", content)
        self.assertIn("approve-review", content)
        self.assertIn("reject-review", content)


class TestRecoveryProvenanceReporting(unittest.TestCase):
    """Verify recover_project reports full provenance including backup and restored manifest hashes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_recovery_provenance_healthy_project(self):
        create_project(self.base_dir, "test-healthy", "Healthy Proj", "player", "male_novice")
        manifest_path = self.base_dir / "test-healthy" / "manifest.json"
        raw_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

        report = recover_project(self.base_dir, "test-healthy")
        self.assertTrue(report["valid"])
        self.assertTrue(report["already_healthy"])
        self.assertIsNone(report["backup_manifest_hash"])
        self.assertEqual(report["restored_manifest_hash"], raw_hash)

    def test_recovery_provenance_restored_from_backup(self):
        create_project(self.base_dir, "test-corrupt", "Corrupt Proj", "player", "male_novice")
        proj_dir = self.base_dir / "test-corrupt"
        manifest_path = proj_dir / "manifest.json"
        data = load_project(self.base_dir, "test-corrupt")
        data["name"] = "Updated Name"
        save_project(self.base_dir, data, expected_revision=data["revision"])  # Creates manifest.json.bak

        bak_path = proj_dir / "manifest.json.bak"
        self.assertTrue(bak_path.exists())
        bak_hash = hashlib.sha256(bak_path.read_bytes()).hexdigest()

        # Corrupt manifest.json
        manifest_path.write_bytes(b"CORRUPTED_BYTES_%%!")

        report = recover_project(self.base_dir, "test-corrupt")
        self.assertTrue(report["valid"])
        self.assertTrue(report["recovered"])
        self.assertEqual(report["action"], "RESTORED_FROM_BACKUP")
        self.assertEqual(report["restored_from"], "manifest.json.bak")
        self.assertEqual(report["backup_manifest_hash"], bak_hash)
        self.assertEqual(report["restored_manifest_hash"], bak_hash)


class TestSyntheticTutorialWorkflow(unittest.TestCase):
    """Test the complete synthetic tutorial workflow programmatically."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_tutorial_walkthrough(self):
        # Step 1: Create project
        create_project(
            self.base_dir,
            "novice-walk-tutorial",
            "Male Novice Walk Tutorial",
            "player",
            "male_novice",
        )
        proj_dir = self.base_dir / "novice-walk-tutorial"
        self.assertTrue(proj_dir.exists())

        # Step 2: Update manifest
        manifest = load_project(self.base_dir, "novice-walk-tutorial")
        init_rev = manifest["revision"]
        manifest["name"] = "Male Novice Walk Slice (Updated)"
        saved = save_project(self.base_dir, manifest, expected_revision=init_rev)
        self.assertEqual(saved["revision"], init_rev + 1)

        # Step 3: Simulate accidental corruption & recovery
        manifest_path = proj_dir / "manifest.json"
        manifest_path.write_bytes(b"{bad json")

        recovery = recover_project(self.base_dir, "novice-walk-tutorial")
        self.assertTrue(recovery["valid"])
        self.assertEqual(recovery["action"], "RESTORED_FROM_BACKUP")
        self.assertEqual(recovery["restored_from"], "manifest.json.bak")
        self.assertIsNotNone(recovery["backup_manifest_hash"])
        self.assertEqual(recovery["backup_manifest_hash"], recovery["restored_manifest_hash"])


if __name__ == "__main__":
    unittest.main()

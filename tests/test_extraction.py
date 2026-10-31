"""Comprehensive test suite for Spritesheet Extraction and Rectangle Validation (RSF-20)."""

import base64
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

from PIL import Image

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, reference
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.extraction import (
    MAX_EXTRACTION_ITEMS,
    compute_recipe_sha256,
    expand_grid_spec,
    extract_rectangle_pixels,
    extract_spritesheet,
    validate_rectangle_spec,
)
from ro_sprite_forge.core.ingestion import analyze_transparency, validate_png
from ro_sprite_forge.core.project import (
    create_project,
    get_blob,
    load_project,
    save_project,
)
from ro_sprite_forge.service.server import create_server, make_standard_actor_doc
from ro_sprite_forge.service.workbench import mutate, source_catalog, workspace


def _make_test_png(
    width: int,
    height: int,
    mode: str = "RGBA",
    color: tuple | int | None = None,
    *,
    pattern: str | None = None,
) -> bytes:
    """Helper to synthesize test PNG bytes in memory."""
    if color is None:
        if mode in ("L", "P"):
            color = 128 if mode == "L" else 1
        elif mode == "LA":
            color = (128, 255)
        else:
            color = (255, 0, 0, 255)
    im = Image.new(mode, (width, height), color)
    if pattern == "checkerboard" and mode == "RGBA":
        for y in range(height):
            for x in range(width):
                if (x + y) % 2 == 0:
                    im.putpixel((x, y), (0, 255, 0, 255))
                else:
                    im.putpixel((x, y), (0, 0, 255, 128))
    elif pattern == "quadrants" and mode == "RGBA":
        hw = width // 2
        hh = height // 2
        for y in range(height):
            for x in range(width):
                if x < hw and y < hh:
                    im.putpixel((x, y), (255, 0, 0, 255))
                elif x >= hw and y < hh:
                    im.putpixel((x, y), (0, 255, 0, 255))
                elif x < hw and y >= hh:
                    im.putpixel((x, y), (0, 0, 255, 255))
                else:
                    im.putpixel((x, y), (255, 255, 0, 0))  # transparent
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    return bio.getvalue()


class RectangleValidationTests(unittest.TestCase):
    """Unit tests for validate_rectangle_spec."""

    def test_01_valid_rectangle_within_bounds(self):
        spec = {"id": "frame-0", "x": 10, "y": 20, "width": 32, "height": 48, "ordinal": 0}
        res = validate_rectangle_spec(spec, 128, 128)
        self.assertEqual(res["id"], "frame-0")
        self.assertEqual(res["x"], 10)
        self.assertEqual(res["y"], 20)
        self.assertEqual(res["width"], 32)
        self.assertEqual(res["height"], 48)
        self.assertEqual(res["ordinal"], 0)

    def test_02_single_pixel_at_origin(self):
        spec = {"id": "px-origin", "x": 0, "y": 0, "width": 1, "height": 1}
        res = validate_rectangle_spec(spec, 64, 64, default_ordinal=0)
        self.assertEqual(res["x"], 0)
        self.assertEqual(res["y"], 0)
        self.assertEqual(res["width"], 1)
        self.assertEqual(res["height"], 1)

    def test_03_single_pixel_at_bottom_right(self):
        spec = {"id": "px-br", "x": 63, "y": 63, "width": 1, "height": 1}
        res = validate_rectangle_spec(spec, 64, 64, default_ordinal=1)
        self.assertEqual(res["x"], 63)
        self.assertEqual(res["y"], 63)

    def test_04_full_image_crop(self):
        spec = {"id": "full", "x": 0, "y": 0, "width": 100, "height": 200}
        res = validate_rectangle_spec(spec, 100, 200, default_ordinal=0)
        self.assertEqual(res["width"], 100)
        self.assertEqual(res["height"], 200)

    def test_05_negative_coordinate_rejected(self):
        with self.assertRaises(ForgeError) as ctx:
            validate_rectangle_spec({"id": "neg-x", "x": -1, "y": 0, "width": 10, "height": 10}, 100, 100)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("INVALID_RECTANGLE_COORDINATES", ctx.exception.message)

        with self.assertRaises(ForgeError) as ctx:
            validate_rectangle_spec({"id": "neg-y", "x": 0, "y": -5, "width": 10, "height": 10}, 100, 100)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)

    def test_06_zero_or_negative_dimensions_rejected(self):
        with self.assertRaises(ForgeError) as ctx:
            validate_rectangle_spec({"id": "zero-w", "x": 0, "y": 0, "width": 0, "height": 10}, 100, 100)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("INVALID_RECTANGLE_DIMENSIONS", ctx.exception.message)

        with self.assertRaises(ForgeError) as ctx:
            validate_rectangle_spec({"id": "neg-h", "x": 0, "y": 0, "width": 10, "height": -2}, 100, 100)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)

    def test_07_out_of_bounds_crop_rejected(self):
        with self.assertRaises(ForgeError) as ctx:
            validate_rectangle_spec({"id": "oob-w", "x": 90, "y": 0, "width": 15, "height": 10}, 100, 100)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("RECTANGLE_OUT_OF_BOUNDS", ctx.exception.message)

        with self.assertRaises(ForgeError) as ctx:
            validate_rectangle_spec({"id": "oob-h", "x": 0, "y": 95, "width": 10, "height": 10}, 100, 100)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("RECTANGLE_OUT_OF_BOUNDS", ctx.exception.message)

    def test_08_invalid_id_rejected(self):
        with self.assertRaises(ForgeError) as ctx:
            validate_rectangle_spec({"id": "", "x": 0, "y": 0, "width": 10, "height": 10}, 100, 100)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("INVALID_RECTANGLE_ID", ctx.exception.message)

        with self.assertRaises(ForgeError) as ctx:
            validate_rectangle_spec({"id": "bad id with spaces!", "x": 0, "y": 0, "width": 10, "height": 10}, 100, 100)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)

    def test_09_invalid_ordinal_rejected(self):
        with self.assertRaises(ForgeError) as ctx:
            validate_rectangle_spec({"id": "bad-ord", "x": 0, "y": 0, "width": 10, "height": 10, "ordinal": -1}, 100, 100)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("INVALID_RECTANGLE_ORDINAL", ctx.exception.message)


class GridExpansionTests(unittest.TestCase):
    """Unit tests for expand_grid_spec."""

    def test_01_uniform_grid_expansion(self):
        grid = {
            "cell_width": 32,
            "cell_height": 32,
            "cols": 4,
            "rows": 2,
        }
        rects = expand_grid_spec(grid, 128, 64)
        self.assertEqual(len(rects), 8)
        self.assertEqual(rects[0]["id"], "cell_r0_c0")
        self.assertEqual(rects[0]["x"], 0)
        self.assertEqual(rects[0]["y"], 0)
        self.assertEqual(rects[0]["ordinal"], 0)
        self.assertEqual(rects[7]["id"], "cell_r1_c3")
        self.assertEqual(rects[7]["x"], 96)
        self.assertEqual(rects[7]["y"], 32)
        self.assertEqual(rects[7]["ordinal"], 7)

    def test_02_grid_with_offset_and_spacing(self):
        grid = {
            "cell_width": 20,
            "cell_height": 20,
            "columns": 2,
            "rows": 2,
            "offset_x": 10,
            "offset_y": 15,
            "spacing_x": 5,
            "spacing_y": 5,
            "cell_id_prefix": "frame",
        }
        rects = expand_grid_spec(grid, 100, 100)
        self.assertEqual(len(rects), 4)
        self.assertEqual(rects[0]["id"], "frame_r0_c0")
        self.assertEqual(rects[0]["x"], 10)
        self.assertEqual(rects[0]["y"], 15)
        self.assertEqual(rects[1]["x"], 35)
        self.assertEqual(rects[2]["y"], 40)

    def test_03_grid_out_of_bounds_rejected(self):
        grid = {
            "cell_width": 32,
            "cell_height": 32,
            "cols": 4,
            "rows": 2,
            "offset_x": 10,
        }
        with self.assertRaises(ForgeError) as ctx:
            expand_grid_spec(grid, 128, 64)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("GRID_OUT_OF_BOUNDS", ctx.exception.message)

    def test_04_grid_with_explicit_cells(self):
        grid = {
            "cell_width": 32,
            "cell_height": 32,
            "cols": 4,
            "rows": 2,
            "cells": [
                {"row": 1, "col": 2, "id": "special-cell", "ordinal": 0},
                {"row": 0, "col": 0, "id": "first-cell", "ordinal": 1},
            ],
        }
        rects = expand_grid_spec(grid, 128, 64)
        self.assertEqual(len(rects), 2)
        self.assertEqual(rects[0]["id"], "special-cell")
        self.assertEqual(rects[0]["x"], 64)
        self.assertEqual(rects[0]["y"], 32)
        self.assertEqual(rects[0]["ordinal"], 0)


class ExtractionExecutionTests(unittest.TestCase):
    """Unit tests for extract_spritesheet execution, determinism and error paths."""

    def test_01_extract_spritesheet_determinism(self):
        png = _make_test_png(128, 128, pattern="quadrants")
        rects = [
            {"id": "q0", "x": 0, "y": 0, "width": 64, "height": 64, "ordinal": 0},
            {"id": "q1", "x": 64, "y": 0, "width": 64, "height": 64, "ordinal": 1},
            {"id": "q2", "x": 0, "y": 64, "width": 64, "height": 64, "ordinal": 2},
            {"id": "q3", "x": 64, "y": 64, "width": 64, "height": 64, "ordinal": 3},
        ]
        res1 = extract_spritesheet(png, "quad-extract", "Quad Extraction", rects)
        res2 = extract_spritesheet(png, "quad-extract", "Quad Extraction", rects)

        self.assertEqual(res1["manifest"]["canonical_sha256"], res2["manifest"]["canonical_sha256"])
        self.assertEqual(res1["manifest"]["collection_sha256"], res2["manifest"]["collection_sha256"])
        self.assertEqual(len(res1["extracted_items"]), 4)

        q3_item = res1["manifest"]["items"][3]
        self.assertEqual(q3_item["id"], "q3")
        self.assertEqual(q3_item["transparency_kind"], "FULLY_TRANSPARENT")
        self.assertTrue(q3_item["has_transparency"])

    def test_02_content_addressed_deduplication_preserves_distinct_recipes(self):
        png = _make_test_png(128, 64, color=(255, 0, 0, 255))
        rects = [
            {"id": "left", "x": 0, "y": 0, "width": 64, "height": 64, "ordinal": 0},
            {"id": "right", "x": 64, "y": 0, "width": 64, "height": 64, "ordinal": 1},
        ]
        res = extract_spritesheet(png, "identical-crops", "Identical Crops", rects)
        items = res["manifest"]["items"]

        self.assertEqual(items[0]["extracted_sha256"], items[1]["extracted_sha256"])
        self.assertNotEqual(items[0]["recipe_sha256"], items[1]["recipe_sha256"])
        self.assertNotEqual(items[0]["id"], items[1]["id"])

        distinct_extracted_blobs = {it["extracted_sha256"] for it in res["extracted_items"]}
        self.assertEqual(len(distinct_extracted_blobs), 1)

    def test_03_duplicate_rectangle_id_rejected(self):
        png = _make_test_png(64, 64)
        rects = [
            {"id": "dup", "x": 0, "y": 0, "width": 32, "height": 32, "ordinal": 0},
            {"id": "dup", "x": 32, "y": 0, "width": 32, "height": 32, "ordinal": 1},
        ]
        with self.assertRaises(ForgeError) as ctx:
            extract_spritesheet(png, "dup-id", "Dup ID", rects)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("DUPLICATE_RECTANGLE_ID", ctx.exception.message)

    def test_04_duplicate_ordinal_rejected(self):
        png = _make_test_png(64, 64)
        rects = [
            {"id": "r1", "x": 0, "y": 0, "width": 32, "height": 32, "ordinal": 0},
            {"id": "r2", "x": 32, "y": 0, "width": 32, "height": 32, "ordinal": 0},
        ]
        with self.assertRaises(ForgeError) as ctx:
            extract_spritesheet(png, "dup-ord", "Dup Ord", rects)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("DUPLICATE_RECTANGLE_ORDINAL", ctx.exception.message)

    def test_05_ordinal_gap_rejected(self):
        png = _make_test_png(64, 64)
        rects = [
            {"id": "r0", "x": 0, "y": 0, "width": 32, "height": 32, "ordinal": 0},
            {"id": "r2", "x": 32, "y": 0, "width": 32, "height": 32, "ordinal": 2},
        ]
        with self.assertRaises(ForgeError) as ctx:
            extract_spritesheet(png, "ord-gap", "Ord Gap", rects)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("RECTANGLE_ORDINAL_GAP", ctx.exception.message)

    def test_06_expected_sheet_sha256_mismatch_rejected(self):
        png = _make_test_png(64, 64)
        rects = [{"id": "r0", "x": 0, "y": 0, "width": 32, "height": 32, "ordinal": 0}]
        wrong_hash = "0" * 64
        with self.assertRaises(ForgeError) as ctx:
            extract_spritesheet(png, "ext-hash", "Hash Test", rects, expected_sheet_sha256=wrong_hash)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("SOURCE_HASH_MISMATCH", ctx.exception.message)

    def test_07_atomicity_any_out_of_bounds_aborts_all(self):
        png = _make_test_png(64, 64)
        rects = [
            {"id": "r0", "x": 0, "y": 0, "width": 32, "height": 32, "ordinal": 0},
            {"id": "r1", "x": 0, "y": 0, "width": 32, "height": 32, "ordinal": 1},
            {"id": "r2-oob", "x": 50, "y": 50, "width": 32, "height": 32, "ordinal": 2},
        ]
        with self.assertRaises(ForgeError) as ctx:
            extract_spritesheet(png, "atomic-test", "Atomic Test", rects)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("RECTANGLE_OUT_OF_BOUNDS", ctx.exception.message)


class WorkbenchExtractionIntegrationTests(unittest.TestCase):
    """Integration tests for workbench mutate('extract-spritesheet') and source tray."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.tmpdir.name)
        self.project_id = "test-p1"
        self.profile = frozen_runtime_profile("player")
        self.actor_doc = make_standard_actor_doc(self.project_id, self.profile, parts=["body"])
        self.actor = load_actor(self.actor_doc)

        views = [
            {
                "view": v,
                "frame_count": 2,
                "topology": {"kind": "explicit", "layers": ["base"]},
            }
            for v in range(8)
        ]
        target = {
            "schema": "rsf.target/v2",
            "id": f"{self.project_id}-target",
            "revision": 1,
            "previous_sha256": None,
            "actor": reference(self.actor),
            "runtime_profile": reference(self.profile),
            "scope": "scoped",
            "parts": ["body"],
            "compatibility": {"status": "UNVERIFIED", "declarations": []},
            "actions": [
                {
                    "id": "Walk",
                    "requirement": "REQUIRED",
                    "parts": [{"part": "body", "views": views}],
                }
            ],
        }
        self.project = create_project(self.projects_dir, self.project_id, "Extraction Test", self.actor_doc["id"], "player", target=target)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_01_extract_spritesheet_via_upload(self):
        png = _make_test_png(128, 64, pattern="quadrants")
        b64 = base64.b64encode(png).decode("ascii")

        payload = {
            "expected_revision": 1,
            "extraction_id": "walk-sheet",
            "sheet_filename": "walk_sheet.png",
            "sheet_data_base64": b64,
            "grid": {
                "cell_width": 64,
                "cell_height": 64,
                "cols": 2,
                "rows": 1,
            },
        }

        res = mutate(self.projects_dir, self.project, "extract-spritesheet", payload)
        self.assertEqual(res["operation"], "extract-spritesheet")
        self.assertEqual(res["extracted_count"], 2)

        proj = res["project"]
        self.assertIn("extractions", proj)
        self.assertEqual(len(proj["extractions"]), 1)
        ext = proj["extractions"][0]
        self.assertEqual(ext["id"], "walk-sheet")
        self.assertEqual(ext["item_count"], 2)

        sheet_sha = ext["source_sha256"]
        self.assertIsNotNone(get_blob(self.projects_dir, self.project_id, sheet_sha))
        for item in ext["items"]:
            self.assertIsNotNone(get_blob(self.projects_dir, self.project_id, item["extracted_sha256"]))

        catalog = source_catalog(self.projects_dir, proj)
        extracted_entries = [e for e in catalog if e.get("extraction_id") == "walk-sheet"]
        self.assertEqual(len(extracted_entries), 2)
        for entry in extracted_entries:
            self.assertEqual(entry["source"]["origin"], "AUTHORED")
            self.assertEqual(entry["availability"], "AVAILABLE")
            self.assertEqual(entry["validation"], "VALID")
            self.assertEqual(entry["source_sheet_sha256"], sheet_sha)
            self.assertIn("rect_id", entry)
            self.assertIn("crop_rect", entry)

        self.assertEqual(len(proj.get("ledger", {}).get("assignments", [])), 0)
        self.assertEqual(len(proj.get("review_events", [])), 0)

    def test_02_extract_spritesheet_from_existing_staged_blob(self):
        png = _make_test_png(64, 64)
        from ro_sprite_forge.core.project import import_blob
        blob_res = import_blob(self.projects_dir, self.project_id, "preloaded.png", png)
        sheet_sha = blob_res["sha256"]

        payload = {
            "expected_revision": 1,
            "extraction_id": "preloaded-ext",
            "sheet_sha256": sheet_sha,
            "rectangles": [
                {"id": "c0", "x": 0, "y": 0, "width": 32, "height": 32, "ordinal": 0},
                {"id": "c1", "x": 32, "y": 0, "width": 32, "height": 32, "ordinal": 1},
            ],
        }
        res = mutate(self.projects_dir, self.project, "extract-spritesheet", payload)
        self.assertEqual(res["extracted_count"], 2)
        proj = res["project"]
        self.assertEqual(len(proj["extractions"]), 1)

    def test_03_repeated_extraction_is_idempotent(self):
        png = _make_test_png(64, 64)
        b64 = base64.b64encode(png).decode("ascii")
        payload1 = {
            "expected_revision": 1,
            "extraction_id": "idempotent-ext",
            "sheet_filename": "sheet.png",
            "sheet_data_base64": b64,
            "rectangles": [
                {"id": "c0", "x": 0, "y": 0, "width": 32, "height": 32, "ordinal": 0},
            ],
        }
        res1 = mutate(self.projects_dir, self.project, "extract-spritesheet", payload1)

        payload2 = copy.deepcopy(payload1)
        payload2["expected_revision"] = res1["project"]["revision"]
        res2 = mutate(self.projects_dir, res1["project"], "extract-spritesheet", payload2)
        self.assertEqual(len(res2["project"]["extractions"]), 1)
        self.assertEqual(res2["project"]["extractions"][0]["canonical_sha256"], res1["project"]["extractions"][0]["canonical_sha256"])


class ServerExtractionHttpTests(unittest.TestCase):
    """End-to-end HTTP tests for extraction routes and protection guards."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.tmpdir.name)
        self.server = create_server(self.projects_dir, host="127.0.0.1", port=0)
        self.port = self.server.actual_port
        self.base_url = f"http://127.0.0.1:{self.port}"

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        self.project_id = "http-p1"
        self.profile = frozen_runtime_profile("player")
        self.actor_doc = make_standard_actor_doc(self.project_id, self.profile, parts=["body"])
        create_project(self.projects_dir, self.project_id, "HTTP Extraction Test", self.actor_doc["id"], "player")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmpdir.cleanup()

    def _http_request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Host": f"127.0.0.1:{self.port}",
            "Origin": f"http://127.0.0.1:{self.port}",
            "X-CSRF-Token": self.server.security.csrf_token,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                body_bytes = resp.read()
                return status, json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except urllib.error.HTTPError as exc:
            body_bytes = exc.read()
            return exc.code, json.loads(body_bytes.decode("utf-8")) if body_bytes else {}

    def test_01_http_extract_spritesheet_endpoint(self):
        png = _make_test_png(64, 64)
        b64 = base64.b64encode(png).decode("ascii")
        payload = {
            "expected_revision": 1,
            "extraction_id": "http-ext",
            "sheet_filename": "sheet.png",
            "sheet_data_base64": b64,
            "rectangles": [
                {"id": "cell-0", "x": 0, "y": 0, "width": 32, "height": 32, "ordinal": 0},
                {"id": "cell-1", "x": 32, "y": 0, "width": 32, "height": 32, "ordinal": 1},
            ],
        }
        status, data = self._http_request("POST", f"/api/projects/{self.project_id}/extract-spritesheet", payload)
        self.assertEqual(status, 200)
        self.assertEqual(data["extracted_count"], 2)

        # GET /api/projects/{id}/extractions
        status, exts_data = self._http_request("GET", f"/api/projects/{self.project_id}/extractions")
        self.assertEqual(status, 200)
        self.assertEqual(len(exts_data["extractions"]), 1)
        self.assertEqual(exts_data["extractions"][0]["id"], "http-ext")

    def test_02_http_extract_out_of_bounds_rejected(self):
        png = _make_test_png(64, 64)
        b64 = base64.b64encode(png).decode("ascii")
        payload = {
            "expected_revision": 1,
            "extraction_id": "oob-ext",
            "sheet_filename": "sheet.png",
            "sheet_data_base64": b64,
            "rectangles": [
                {"id": "cell-oob", "x": 50, "y": 50, "width": 32, "height": 32, "ordinal": 0},
            ],
        }
        status, data = self._http_request("POST", f"/api/projects/{self.project_id}/extract-spritesheet", payload)
        self.assertEqual(status, 422)
        self.assertIn("RECTANGLE_OUT_OF_BOUNDS", data["error"]["message"])

    def test_03_http_put_project_rejects_tampering_with_extractions(self):
        manifest = load_project(self.projects_dir, self.project_id, verify_blobs=False)
        tampered = copy.deepcopy(manifest)
        tampered["extractions"] = [{"id": "fake", "schema": "rsf.spritesheet-extraction/v1"}]

        status, data = self._http_request(
            "PUT",
            f"/api/projects/{self.project_id}",
            {"expected_revision": manifest["revision"], "project": tampered},
        )
        self.assertEqual(status, 422)
        self.assertIn("Use validated extract-spritesheet operations to manage extractions", data["error"]["message"])


if __name__ == "__main__":
    unittest.main()

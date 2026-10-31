"""Comprehensive test suite for Non-Destructive Image Transformation Recipes (RSF-21)."""

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
from ro_sprite_forge.core.project import (
    create_project,
    get_blob,
    import_blob,
    load_project,
    save_project,
)
from ro_sprite_forge.core.transformations import (
    apply_transformation_recipe,
    compute_recipe_sha256,
    execute_operation,
    validate_operation,
    validate_recipe,
)
from ro_sprite_forge.service.server import create_server, make_standard_actor_doc
from ro_sprite_forge.service.workbench import mutate, record_review, review_proposal, source_catalog, workspace


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

    if pattern == "asymmetric_gradient" and mode == "RGBA":
        # Pixel values strictly dependent on (x, y) coordinates
        for y in range(height):
            for x in range(width):
                im.putpixel((x, y), (x * 4 % 256, y * 8 % 256, (x + y) * 2 % 256, 255))
    elif pattern == "magenta_background" and mode == "RGBA":
        for y in range(height):
            for x in range(width):
                if x < width // 2 and y < height // 2:
                    im.putpixel((x, y), (0, 255, 0, 255))  # Foreground green
                else:
                    im.putpixel((x, y), (255, 0, 255, 255))  # Background magenta
    elif pattern == "indexed_palette" and mode == "P":
        palette = [0, 0, 0,  255, 0, 0,  0, 255, 0,  0, 0, 255] + [0] * (252 * 3)
        im.putpalette(palette)
        for y in range(height):
            for x in range(width):
                im.putpixel((x, y), (x + y) % 4)

    bio = io.BytesIO()
    im.save(bio, format="PNG")
    return bio.getvalue()


class OperationValidationTests(unittest.TestCase):
    """Unit tests for validate_operation and validate_recipe."""

    def test_01_valid_crop_operation(self):
        op = {"op": "crop", "x": 10, "y": 20, "width": 30, "height": 40}
        clean = validate_operation(op, 100, 100)
        self.assertEqual(clean["op"], "crop")
        self.assertEqual(clean["x"], 10)
        self.assertEqual(clean["width"], 30)

    def test_02_crop_out_of_bounds_rejected(self):
        op = {"op": "crop", "x": 80, "y": 0, "width": 30, "height": 20}
        with self.assertRaises(ForgeError) as ctx:
            validate_operation(op, 100, 100)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("CROP_OUT_OF_BOUNDS", ctx.exception.message)

    def test_03_crop_zero_dimension_rejected(self):
        with self.assertRaises(ForgeError) as ctx:
            validate_operation({"op": "crop", "x": 0, "y": 0, "width": 0, "height": 10})
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("INVALID_CROP_PARAM", ctx.exception.message)

    def test_04_flip_operation_validation(self):
        op = {"op": "flip", "direction": "vertical"}
        clean = validate_operation(op)
        self.assertEqual(clean["direction"], "vertical")

        with self.assertRaises(ForgeError) as ctx:
            validate_operation({"op": "flip", "direction": "diagonal"})
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("INVALID_FLIP_PARAM", ctx.exception.message)

    def test_05_scale_operation_validation(self):
        op = {"op": "scale", "width": 64, "height": 64, "filter": "nearest"}
        clean = validate_operation(op)
        self.assertEqual(clean["width"], 64)
        self.assertEqual(clean["filter"], "nearest")

        with self.assertRaises(ForgeError) as ctx:
            validate_operation({"op": "scale", "width": -5, "height": 10})
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)

    def test_06_matte_key_validation(self):
        op = {"op": "matte_key", "color": [255, 0, 255], "tolerance": 5, "replacement_alpha": 0}
        clean = validate_operation(op)
        self.assertEqual(clean["color"], [255, 0, 255])
        self.assertEqual(clean["tolerance"], 5)

        with self.assertRaises(ForgeError) as ctx:
            validate_operation({"op": "matte_key", "color": [256, 0, 0]})
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)

    def test_07_unsupported_operation_rejected(self):
        with self.assertRaises(ForgeError) as ctx:
            validate_operation({"op": "ai_generative_fill"})
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("UNSUPPORTED_OPERATION", ctx.exception.message)


class TransformationExecutionTests(unittest.TestCase):
    """Synthetic pixel tests verifying deterministic transformation semantics."""

    def test_01_crop_extracts_exact_pixels_and_discloses_loss(self):
        png = _make_test_png(64, 64, pattern="asymmetric_gradient")
        recipe = {
            "id": "test-crop",
            "name": "Crop Test",
            "source_sha256": digest(png),
            "operations": [{"op": "crop", "x": 10, "y": 15, "width": 20, "height": 25}],
        }
        res = apply_transformation_recipe(png, recipe)
        self.assertEqual(res["metadata"]["width"], 20)
        self.assertEqual(res["metadata"]["height"], 25)
        self.assertIn("CROPPED_DISCARDED_PIXELS", res["metadata"]["loss_report"])

        # Compare pixel at (0, 0) of output against (10, 15) of input
        orig_im = Image.open(io.BytesIO(png))
        out_im = Image.open(io.BytesIO(res["output_bytes"]))
        self.assertEqual(out_im.getpixel((0, 0)), orig_im.getpixel((10, 15)))
        self.assertEqual(out_im.getpixel((19, 24)), orig_im.getpixel((29, 39)))

    def test_02_horizontal_flip_exact_reflection(self):
        png = _make_test_png(32, 32, pattern="asymmetric_gradient")
        recipe = {
            "id": "test-fliph",
            "name": "Flip H",
            "source_sha256": digest(png),
            "operations": [{"op": "flip", "direction": "horizontal"}],
        }
        res = apply_transformation_recipe(png, recipe)
        orig_im = Image.open(io.BytesIO(png))
        out_im = Image.open(io.BytesIO(res["output_bytes"]))
        # Output (x, y) should equal Input (width - 1 - x, y)
        self.assertEqual(out_im.getpixel((0, 5)), orig_im.getpixel((31, 5)))
        self.assertEqual(out_im.getpixel((10, 20)), orig_im.getpixel((21, 20)))

    def test_03_vertical_flip_exact_reflection(self):
        png = _make_test_png(32, 32, pattern="asymmetric_gradient")
        recipe = {
            "id": "test-flipv",
            "name": "Flip V",
            "source_sha256": digest(png),
            "operations": [{"op": "flip", "direction": "vertical"}],
        }
        res = apply_transformation_recipe(png, recipe)
        orig_im = Image.open(io.BytesIO(png))
        out_im = Image.open(io.BytesIO(res["output_bytes"]))
        # Output (x, y) should equal Input (x, height - 1 - y)
        self.assertEqual(out_im.getpixel((7, 0)), orig_im.getpixel((7, 31)))

    def test_04_nearest_neighbor_upscale_preserves_pixel_blocks(self):
        png = _make_test_png(16, 16, pattern="asymmetric_gradient")
        recipe = {
            "id": "test-scale2x",
            "name": "Scale 2x",
            "source_sha256": digest(png),
            "operations": [{"op": "scale", "width": 32, "height": 32, "filter": "nearest"}],
        }
        res = apply_transformation_recipe(png, recipe)
        orig_im = Image.open(io.BytesIO(png))
        out_im = Image.open(io.BytesIO(res["output_bytes"]))
        self.assertEqual(out_im.width, 32)
        self.assertEqual(out_im.height, 32)
        # Each original pixel occupies a 2x2 block in the output
        p00 = orig_im.getpixel((0, 0))
        self.assertEqual(out_im.getpixel((0, 0)), p00)
        self.assertEqual(out_im.getpixel((1, 0)), p00)
        self.assertEqual(out_im.getpixel((0, 1)), p00)
        self.assertEqual(out_im.getpixel((1, 1)), p00)

    def test_05_downscale_discloses_loss(self):
        png = _make_test_png(32, 32)
        recipe = {
            "id": "test-downscale",
            "name": "Downscale",
            "source_sha256": digest(png),
            "operations": [{"op": "scale", "width": 16, "height": 16, "filter": "nearest"}],
        }
        res = apply_transformation_recipe(png, recipe)
        self.assertIn("DOWNSCALED_DISCARDED_PIXELS", res["metadata"]["loss_report"])

    def test_06_interpolated_scaling_discloses_interpolation(self):
        png = _make_test_png(32, 32)
        recipe = {
            "id": "test-bilinear",
            "name": "Bilinear Scale",
            "source_sha256": digest(png),
            "operations": [{"op": "scale", "width": 48, "height": 48, "filter": "bilinear"}],
        }
        res = apply_transformation_recipe(png, recipe)
        self.assertIn("INTERPOLATED_RESAMPLING", res["metadata"]["loss_report"])

    def test_07_offset_placement_on_canvas_with_transparent_padding(self):
        png = _make_test_png(16, 16, color=(255, 0, 0, 255))
        recipe = {
            "id": "test-offset",
            "name": "Offset Placement",
            "source_sha256": digest(png),
            "operations": [
                {"op": "offset", "offset_x": 8, "offset_y": 8, "canvas_width": 32, "canvas_height": 32, "overflow": "clip"}
            ],
        }
        res = apply_transformation_recipe(png, recipe)
        out_im = Image.open(io.BytesIO(res["output_bytes"]))
        self.assertEqual(out_im.width, 32)
        self.assertEqual(out_im.height, 32)
        # Background margin is fully transparent
        self.assertEqual(out_im.getpixel((0, 0))[3], 0)
        self.assertEqual(out_im.getpixel((7, 7))[3], 0)
        # Placed image is opaque red
        self.assertEqual(out_im.getpixel((8, 8)), (255, 0, 0, 255))
        self.assertEqual(out_im.getpixel((23, 23)), (255, 0, 0, 255))
        self.assertEqual(out_im.getpixel((24, 24))[3], 0)

    def test_08_matte_background_keying_replaces_color_with_alpha(self):
        png = _make_test_png(32, 32, pattern="magenta_background")
        recipe = {
            "id": "test-keying",
            "name": "Matte Keying",
            "source_sha256": digest(png),
            "operations": [
                {"op": "matte_key", "color": [255, 0, 255], "tolerance": 0, "replacement_alpha": 0}
            ],
        }
        res = apply_transformation_recipe(png, recipe)
        out_im = Image.open(io.BytesIO(res["output_bytes"]))
        # Magenta background (bottom-right) should be keyed to alpha 0
        self.assertEqual(out_im.getpixel((30, 30))[3], 0)
        # Green foreground (top-left) should be untouched
        self.assertEqual(out_im.getpixel((5, 5)), (0, 255, 0, 255))
        self.assertIn("ALPHA_CHANNEL_KEYED", res["metadata"]["loss_report"])

    def test_09_palette_to_rgba_conversion_discloses_palette_indices_discarded(self):
        png = _make_test_png(32, 32, mode="P", pattern="indexed_palette")
        recipe = {
            "id": "test-pal-to-rgba",
            "name": "Palette to RGBA",
            "source_sha256": digest(png),
            "operations": [{"op": "color_mode", "target_mode": "RGBA"}],
        }
        res = apply_transformation_recipe(png, recipe)
        out_im = Image.open(io.BytesIO(res["output_bytes"]))
        self.assertEqual(out_im.mode, "RGBA")
        self.assertIn("PALETTE_INDICES_DISCARDED", res["metadata"]["loss_report"])

    def test_10_order_sensitivity_crop_then_flip_vs_flip_then_crop(self):
        # On an asymmetric gradient, Crop then Flip must differ from Flip then Crop
        png = _make_test_png(64, 64, pattern="asymmetric_gradient")
        sha = digest(png)

        recipe_cf = {
            "id": "crop-then-flip",
            "name": "Crop Then Flip",
            "source_sha256": sha,
            "operations": [
                {"op": "crop", "x": 0, "y": 0, "width": 32, "height": 32},
                {"op": "flip", "direction": "horizontal"},
            ],
        }
        recipe_fc = {
            "id": "flip-then-crop",
            "name": "Flip Then Crop",
            "source_sha256": sha,
            "operations": [
                {"op": "flip", "direction": "horizontal"},
                {"op": "crop", "x": 0, "y": 0, "width": 32, "height": 32},
            ],
        }
        res_cf = apply_transformation_recipe(png, recipe_cf)
        res_fc = apply_transformation_recipe(png, recipe_fc)

        # The resulting images must be strictly different
        self.assertNotEqual(res_cf["derived_sha256"], res_fc["derived_sha256"])
        self.assertNotEqual(res_cf["output_bytes"], res_fc["output_bytes"])

    def test_11_repeated_execution_is_strictly_idempotent(self):
        png = _make_test_png(32, 32, pattern="asymmetric_gradient")
        recipe = {
            "id": "idempotent-test",
            "name": "Idempotent Test",
            "source_sha256": digest(png),
            "operations": [
                {"op": "crop", "x": 4, "y": 4, "width": 24, "height": 24},
                {"op": "flip", "direction": "horizontal"},
                {"op": "scale", "width": 48, "height": 48, "filter": "nearest"},
            ],
        }
        res1 = apply_transformation_recipe(png, recipe)
        res2 = apply_transformation_recipe(png, recipe)

        # Output bytes, derived SHA-256, and recipe SHA-256 are bit-for-bit identical
        self.assertEqual(res1["derived_sha256"], res2["derived_sha256"])
        self.assertEqual(res1["recipe_sha256"], res2["recipe_sha256"])
        self.assertEqual(res1["output_bytes"], res2["output_bytes"])
        self.assertEqual(res1["recipe"]["canonical_sha256"], res2["recipe"]["canonical_sha256"])


class WorkbenchTransformationIntegrationTests(unittest.TestCase):
    """Integration tests for workbench mutate('apply-transform') and review invalidation."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.tmpdir.name)
        self.project_id = "test-transform-p1"
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
        self.target = {
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
        self.project = create_project(
            self.projects_dir,
            self.project_id,
            "Transformation Test",
            self.actor_doc["id"],
            "player",
            target=self.target,
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_01_apply_transform_stages_derived_candidate_without_auto_approval(self):
        png = _make_test_png(64, 64, pattern="asymmetric_gradient")
        blob_res = import_blob(self.projects_dir, self.project_id, "source_frame.png", png)
        src_sha = blob_res["sha256"]

        recipe = {
            "id": "derive-walk-0",
            "name": "Derive Walk 0",
            "source_sha256": src_sha,
            "operations": [
                {"op": "crop", "x": 0, "y": 0, "width": 32, "height": 32},
                {"op": "flip", "direction": "horizontal"},
            ],
        }
        res = mutate(
            self.projects_dir,
            self.project,
            "apply-transform",
            {"expected_revision": 1, "recipe": recipe},
        )
        self.assertEqual(res["operation"], "apply-transform")
        derived_sha = res["derived_sha256"]
        proj = res["project"]

        # 1. Derived image staged as blob
        blob_bytes = get_blob(self.projects_dir, self.project_id, derived_sha)
        self.assertIsNotNone(blob_bytes)

        # 2. Derived candidate appears in source_catalog with extraction/recipe metadata
        catalog = source_catalog(self.projects_dir, proj)
        derived_entry = next((e for e in catalog if e["source"]["sha256"] == derived_sha), None)
        self.assertIsNotNone(derived_entry)
        self.assertEqual(derived_entry["source"]["origin"], "AUTHORED")
        self.assertEqual(derived_entry["availability"], "AVAILABLE")
        self.assertEqual(derived_entry["validation"], "VALID")
        self.assertEqual(derived_entry["recipe_id"], "derive-walk-0")
        self.assertEqual(derived_entry["source_sha256"], src_sha)

        # 3. Recipe recorded in manifest['recipes']
        self.assertIn("recipes", proj)
        self.assertEqual(len(proj["recipes"]), 1)
        self.assertEqual(proj["recipes"][0]["id"], "derive-walk-0")

        # 4. Zero auto-assignment & zero auto-approval
        self.assertEqual(len(proj.get("ledger", {}).get("assignments", [])), 0)
        self.assertEqual(len(proj.get("review_events", [])), 0)

    def test_02_replacing_assigned_source_with_derived_invalidates_affected_approval_only(self):
        # Stage two original sources A and B via stage-png
        png_a = _make_test_png(32, 32, color=(255, 0, 0, 255))
        png_b = _make_test_png(32, 32, color=(0, 255, 0, 255))
        b64_a = base64.b64encode(png_a).decode("ascii")
        b64_b = base64.b64encode(png_b).decode("ascii")
        mut_a = mutate(self.projects_dir, self.project, "stage-png", {"expected_revision": 1, "filename": "frame_a.png", "data_base64": b64_a})
        mut_b = mutate(self.projects_dir, mut_a["project"], "stage-png", {"expected_revision": 2, "filename": "frame_b.png", "data_base64": b64_b})
        proj_staged = mut_b["project"]

        sha_a = digest(png_a)
        sha_b = digest(png_b)

        # Assign A to Walk slot/view 0 frame 0 layer 0, and B to frame 1 layer 0
        w = workspace(self.projects_dir, proj_staged)
        req_0 = w["requirements"]["layers"][0]["id"]
        req_1 = w["requirements"]["layers"][1]["id"]

        mut1 = mutate(
            self.projects_dir,
            proj_staged,
            "assign",
            {
                "expected_revision": 3,
                "mappings": [
                    {"requirement_id": req_0, "kind": "DIRECT_SOURCE", "source": f"blob-{sha_a}", "source_revision": 1, "recipe": []},
                    {"requirement_id": req_1, "kind": "DIRECT_SOURCE", "source": f"blob-{sha_b}", "source_revision": 1, "recipe": []},
                ],
            },
        )
        proj_with_assignments = mut1["project"]

        # Create two separate approved reviews for req_0 and req_1
        proposal_0 = review_proposal(
            self.projects_dir,
            proj_with_assignments,
            {"expected_revision": proj_with_assignments["revision"], "requirements": [req_0]},
        )
        rev_res_0 = record_review(
            self.projects_dir,
            proj_with_assignments,
            {
                "expected_revision": proj_with_assignments["revision"],
                "decision": "APPROVED",
                "proposal": proposal_0["proposal"],
            },
        )
        proj_rev_0 = rev_res_0["project"]

        proposal_1 = review_proposal(
            self.projects_dir,
            proj_rev_0,
            {"expected_revision": proj_rev_0["revision"], "requirements": [req_1]},
        )
        rev_res_1 = record_review(
            self.projects_dir,
            proj_rev_0,
            {
                "expected_revision": proj_rev_0["revision"],
                "decision": "APPROVED",
                "proposal": proposal_1["proposal"],
            },
        )
        proj_both_approved = rev_res_1["project"]

        # Verify both reviews are currently APPROVED
        w_approved = workspace(self.projects_dir, proj_both_approved)
        approved_states = {o["requirement_id"]: o["state"] for o in w_approved["reviews"]["occurrences"]}
        self.assertEqual(approved_states[req_0], "APPROVED")
        self.assertEqual(approved_states[req_1], "APPROVED")

        # Now apply a transformation to source A and replace the assignment of req_0
        recipe_a = {
            "id": "transformed-a",
            "name": "Transformed A",
            "source_sha256": sha_a,
            "operations": [{"op": "flip", "direction": "horizontal"}],
        }
        mut_replace = mutate(
            self.projects_dir,
            proj_both_approved,
            "apply-transform",
            {
                "expected_revision": proj_both_approved["revision"],
                "recipe": recipe_a,
                "destination_requirement_id": req_0,
            },
        )
        proj_after_replace = mut_replace["project"]

        # Verify review staleness:
        # req_0 composition changed -> review is STALE!
        # req_1 was untouched -> review remains APPROVED!
        w_final = workspace(self.projects_dir, proj_after_replace)
        final_states = {o["requirement_id"]: o["state"] for o in w_final["reviews"]["occurrences"]}
        self.assertEqual(final_states[req_0], "STALE")
        self.assertEqual(final_states[req_1], "APPROVED")


class ServerTransformationHttpTests(unittest.TestCase):
    """End-to-end HTTP tests for transformation preview, mutation and safety guards."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.tmpdir.name)
        self.server = create_server(self.projects_dir, host="127.0.0.1", port=0)
        self.port = self.server.actual_port
        self.base_url = f"http://127.0.0.1:{self.port}"

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        self.project_id = "http-transform-p1"
        self.profile = frozen_runtime_profile("player")
        self.actor_doc = make_standard_actor_doc(self.project_id, self.profile, parts=["body"])
        create_project(self.projects_dir, self.project_id, "HTTP Transform Test", self.actor_doc["id"], "player")

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

    def test_01_transform_preview_and_apply_endpoints(self):
        png = _make_test_png(32, 32, pattern="asymmetric_gradient")
        blob_res = import_blob(self.projects_dir, self.project_id, "source.png", png)
        src_sha = blob_res["sha256"]

        recipe = {
            "id": "http-recipe-1",
            "name": "HTTP Recipe 1",
            "source_sha256": src_sha,
            "operations": [
                {"op": "crop", "x": 0, "y": 0, "width": 16, "height": 16},
                {"op": "flip", "direction": "horizontal"},
            ],
        }

        # 1. Preview transformation (does not mutate project)
        status, prev = self._http_request("POST", f"/api/projects/{self.project_id}/transform-preview", {"recipe": recipe})
        self.assertEqual(status, 200)
        self.assertEqual(prev["output_dimensions"], [16, 16])
        self.assertIn("before_base64", prev)
        self.assertIn("after_base64", prev)
        self.assertIn("CROPPED_DISCARDED_PIXELS", prev["loss_report"])

        # 2. Apply transformation (mutates project)
        status, res = self._http_request(
            "POST",
            f"/api/projects/{self.project_id}/apply-transform",
            {"expected_revision": 1, "recipe": recipe},
        )
        self.assertEqual(status, 200)
        self.assertEqual(res["operation"], "apply-transform")
        derived_sha = res["derived_sha256"]

        # 3. GET /api/projects/{id}/recipes
        status, recipes_data = self._http_request("GET", f"/api/projects/{self.project_id}/recipes")
        self.assertEqual(status, 200)
        self.assertEqual(len(recipes_data["recipes"]), 1)
        self.assertEqual(recipes_data["recipes"][0]["id"], "http-recipe-1")

    def test_02_put_project_rejects_tampering_with_recipes(self):
        manifest = load_project(self.projects_dir, self.project_id, verify_blobs=False)
        tampered = copy.deepcopy(manifest)
        tampered["recipes"] = [{"id": "fake", "schema": "rsf.image-recipe/v1"}]

        status, data = self._http_request(
            "PUT",
            f"/api/projects/{self.project_id}",
            {"expected_revision": manifest["revision"], "project": tampered},
        )
        self.assertEqual(status, 422)
        self.assertIn("Use validated apply-transform operations to manage recipes", data["error"]["message"])


if __name__ == "__main__":
    unittest.main()

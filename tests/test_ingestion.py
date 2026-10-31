"""Comprehensive test suite for Deterministic PNG Sequence Ingestion and Staging (RSF-19)."""

import base64
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, reference
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.ingestion import (
    MAX_DIMENSION,
    MAX_PIXELS,
    analyze_transparency,
    validate_png,
    validate_sequence,
)
from ro_sprite_forge.core.project import (
    MAX_BLOB_SIZE,
    create_project,
    get_blob,
    load_project,
)
from ro_sprite_forge.service.server import create_server, make_standard_actor_doc
from ro_sprite_forge.service.workbench import mutate, source_catalog, workspace


def _craft_png_ihdr(width: int, height: int) -> bytes:
    import zlib
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x00\x00\x00\x00"
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data).to_bytes(4, "big")
    ihdr = (13).to_bytes(4, "big") + b"IHDR" + ihdr_data + ihdr_crc
    raw_scanlines = b"\x00" * ((min(width, 100) + 1) * min(height, 100))
    idat_data = zlib.compress(raw_scanlines)
    idat_crc = zlib.crc32(b"IDAT" + idat_data).to_bytes(4, "big")
    idat = len(idat_data).to_bytes(4, "big") + b"IDAT" + idat_data + idat_crc
    iend = (0).to_bytes(4, "big") + b"IEND" + zlib.crc32(b"IEND").to_bytes(4, "big")
    return sig + ihdr + idat + iend


def _make_test_png(
    width: int,
    height: int,
    mode: str = "RGBA",
    color: tuple | int | None = None,
    *,
    transparency_pattern: str | None = None,
) -> bytes:
    """Helper to synthesize test PNG bytes cleanly in memory."""
    if color is None:
        if mode in ("L", "P"):
            color = 128 if mode == "L" else 1
        elif mode == "LA":
            color = (128, 255)
        else:
            color = (255, 0, 0, 255)
    im = Image.new(mode, (width, height), color)
    if transparency_pattern == "partial" and mode == "RGBA":
        for y in range(height // 2):
            for x in range(width):
                im.putpixel((x, y), (255, 0, 0, 0))
    elif transparency_pattern == "fully_transparent" and mode == "RGBA":
        for y in range(height):
            for x in range(width):
                im.putpixel((x, y), (0, 0, 0, 0))
    elif transparency_pattern == "partial_la" and mode == "LA":
        for y in range(height // 2):
            for x in range(width):
                im.putpixel((x, y), (128, 0))
    elif mode == "P" and transparency_pattern == "palette_trans":
        # Palette with transparency index 0, and image containing both 0 and 1
        im = Image.new("P", (width, height), 1)
        im.putpalette([0, 0, 0, 255, 0, 0, 0, 255, 0] + [0] * (253 * 3))
        im.putpixel((0, 0), 0)  # Make one pixel index 0 (transparent)
        bio = io.BytesIO()
        im.save(bio, format="PNG", transparency=0)
        return bio.getvalue()

    bio = io.BytesIO()
    im.save(bio, format="PNG")
    return bio.getvalue()


class IngestionValidationTests(unittest.TestCase):
    """Part G §18: All 28 synthetic scenarios for PNG validation and sequence staging."""

    def test_01_valid_rgba_png_partial_transparency(self):
        png = _make_test_png(32, 32, mode="RGBA", transparency_pattern="partial")
        meta = validate_png(png, filename="frame-01.png")
        self.assertEqual(meta["width"], 32)
        self.assertEqual(meta["height"], 32)
        self.assertEqual(meta["mode"], "RGBA")
        self.assertEqual(meta["transparency_kind"], "PARTIALLY_TRANSPARENT")
        self.assertTrue(meta["has_transparency"])
        self.assertEqual(meta["sha256"], digest(png))

    def test_02_valid_rgba_png_opaque(self):
        png = _make_test_png(32, 32, mode="RGBA", color=(100, 150, 200, 255))
        meta = validate_png(png)
        self.assertEqual(meta["transparency_kind"], "OPAQUE")
        self.assertFalse(meta["has_transparency"])

    def test_03_valid_rgba_png_fully_transparent(self):
        png = _make_test_png(32, 32, mode="RGBA", transparency_pattern="fully_transparent")
        meta = validate_png(png)
        self.assertEqual(meta["transparency_kind"], "FULLY_TRANSPARENT")
        self.assertTrue(meta["has_transparency"])

    def test_04_valid_rgb_png(self):
        png = _make_test_png(24, 24, mode="RGB", color=(255, 128, 0))
        meta = validate_png(png)
        self.assertEqual(meta["mode"], "RGB")
        self.assertEqual(meta["transparency_kind"], "OPAQUE")
        self.assertFalse(meta["has_transparency"])

    def test_05_valid_grayscale_l_png(self):
        png = _make_test_png(16, 16, mode="L", color=128)
        meta = validate_png(png)
        self.assertEqual(meta["mode"], "L")
        self.assertEqual(meta["transparency_kind"], "OPAQUE")
        self.assertFalse(meta["has_transparency"])

    def test_06_valid_grayscale_la_png(self):
        png = _make_test_png(16, 16, mode="LA", color=(128, 255), transparency_pattern="partial_la")
        meta = validate_png(png)
        self.assertEqual(meta["mode"], "LA")
        self.assertEqual(meta["transparency_kind"], "PARTIALLY_TRANSPARENT")
        self.assertTrue(meta["has_transparency"])

    def test_07_valid_indexed_p_png_with_transparency(self):
        png = _make_test_png(20, 20, mode="P", transparency_pattern="palette_trans")
        meta = validate_png(png)
        self.assertEqual(meta["mode"], "P")
        self.assertEqual(meta["transparency_kind"], "PARTIALLY_TRANSPARENT")
        self.assertTrue(meta["has_transparency"])

    def test_08_valid_indexed_p_png_opaque(self):
        im = Image.new("P", (16, 16), 1)
        im.putpalette([0, 0, 0, 255, 255, 255] + [0] * (254 * 3))
        bio = io.BytesIO()
        im.save(bio, format="PNG")
        png = bio.getvalue()

        meta = validate_png(png)
        self.assertEqual(meta["mode"], "P")
        self.assertEqual(meta["transparency_kind"], "OPAQUE")
        self.assertFalse(meta["has_transparency"])

    def test_09_non_square_png(self):
        png = _make_test_png(120, 35, mode="RGBA")
        meta = validate_png(png)
        self.assertEqual(meta["width"], 120)
        self.assertEqual(meta["height"], 35)

    def test_10_single_pixel_png(self):
        png = _make_test_png(1, 1, mode="RGBA")
        meta = validate_png(png)
        self.assertEqual(meta["width"], 1)
        self.assertEqual(meta["height"], 1)

    def test_11_boundary_dimensions_4096(self):
        png = _make_test_png(4096, 1, mode="L", color=0)
        meta = validate_png(png)
        self.assertEqual(meta["width"], 4096)
        self.assertEqual(meta["height"], 1)

    def test_12_dimension_exceeded_rejected(self):
        crafted = _craft_png_ihdr(4097, 10)
        with self.assertRaises(ForgeError) as ctx:
            validate_png(crafted)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("DIMENSION_EXCEEDED", ctx.exception.message)

    def test_13_decode_budget_exceeded_rejected(self):
        crafted = _craft_png_ihdr(8000, 8000)
        with self.assertRaises(ForgeError) as ctx:
            validate_png(crafted)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertTrue(
            any(
                code in ctx.exception.message
                for code in ("DECOMPRESSION_BOMB", "DECODE_BUDGET_EXCEEDED", "DIMENSION_EXCEEDED")
            )
        )

    def test_14_invalid_png_signature_rejected(self):
        garbage = b"GIF89a\x01\x00\x01\x00\x80\x00\x00"
        with self.assertRaises(ForgeError) as ctx:
            validate_png(garbage)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("INVALID_PNG_SIGNATURE", ctx.exception.message)

    def test_15_corrupted_png_truncated_rejected(self):
        png = _make_test_png(64, 64, mode="RGBA")
        truncated = png[:25]  # Cut off mid-chunk
        with self.assertRaises(ForgeError) as ctx:
            validate_png(truncated)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)

    def test_16_corrupted_png_bad_chunks_rejected(self):
        png = _make_test_png(64, 64, mode="RGBA")
        corrupted = png[:16] + b"\x00\x00\x00\x00\xff\xff" + png[22:]
        with self.assertRaises(ForgeError) as ctx:
            validate_png(corrupted)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)

    def test_17_payload_too_large_rejected(self):
        huge_dummy = b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_BLOB_SIZE + 1)
        with self.assertRaises(ForgeError) as ctx:
            validate_png(huge_dummy)
        self.assertEqual(ctx.exception.code, ErrorCode.PAYLOAD_TOO_LARGE)

    def test_18_expected_hash_mismatch_rejected(self):
        png = _make_test_png(16, 16, mode="RGBA")
        wrong_hash = "0" * 64
        with self.assertRaises(ForgeError) as ctx:
            validate_png(png, expected_sha256=wrong_hash)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("SOURCE_HASH_MISMATCH", ctx.exception.message)

    def test_19_valid_sequence_validation(self):
        png0 = _make_test_png(16, 16, mode="RGBA", color=(10, 0, 0, 255))
        png1 = _make_test_png(16, 16, mode="RGBA", color=(20, 0, 0, 255))
        png2 = _make_test_png(16, 16, mode="RGBA", color=(30, 0, 0, 255))
        frames = [
            {"ordinal": 0, "sha256": digest(png0), "filename": "walk_0.png", "width": 16, "height": 16},
            {"ordinal": 1, "sha256": digest(png1), "filename": "walk_1.png", "width": 16, "height": 16},
            {"ordinal": 2, "sha256": digest(png2), "filename": "walk_2.png", "width": 16, "height": 16},
        ]
        seq = validate_sequence("walk-south", "Walk South", frames)
        self.assertEqual(seq["schema"], "rsf.sequence/v1")
        self.assertEqual(seq["id"], "walk-south")
        self.assertEqual(seq["frame_count"], 3)
        self.assertEqual(len(seq["frames"]), 3)
        self.assertIn("canonical_sha256", seq)
        self.assertIn("sequence_sha256", seq)

    def test_20_sequence_reordering_changes_sequence_sha256(self):
        h0 = "a" * 64
        h1 = "b" * 64
        h2 = "c" * 64
        order_a = [
            {"ordinal": 0, "sha256": h0, "filename": "f0.png"},
            {"ordinal": 1, "sha256": h1, "filename": "f1.png"},
            {"ordinal": 2, "sha256": h2, "filename": "f2.png"},
        ]
        # Swap ordinals 1 and 2
        order_b = [
            {"ordinal": 0, "sha256": h0, "filename": "f0.png"},
            {"ordinal": 1, "sha256": h2, "filename": "f2.png"},
            {"ordinal": 2, "sha256": h1, "filename": "f1.png"},
        ]
        seq_a = validate_sequence("seq-a", "Seq A", order_a)
        seq_b = validate_sequence("seq-b", "Seq B", order_b)
        self.assertNotEqual(seq_a["sequence_sha256"], seq_b["sequence_sha256"])
        self.assertNotEqual(seq_a["canonical_sha256"], seq_b["canonical_sha256"])

    def test_21_sequence_duplicate_ordinal_rejected(self):
        frames = [
            {"ordinal": 0, "sha256": "a" * 64, "filename": "f0.png"},
            {"ordinal": 1, "sha256": "b" * 64, "filename": "f1.png"},
            {"ordinal": 1, "sha256": "c" * 64, "filename": "f2.png"},
        ]
        with self.assertRaises(ForgeError) as ctx:
            validate_sequence("seq-dup", "Dup Ordinal", frames)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("DUPLICATE_FRAME_ORDINAL", ctx.exception.message)

    def test_22_sequence_gap_rejected(self):
        frames = [
            {"ordinal": 0, "sha256": "a" * 64, "filename": "f0.png"},
            {"ordinal": 1, "sha256": "b" * 64, "filename": "f1.png"},
            {"ordinal": 3, "sha256": "c" * 64, "filename": "f3.png"},  # missing 2
        ]
        with self.assertRaises(ForgeError) as ctx:
            validate_sequence("seq-gap", "Gap Ordinal", frames)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("FRAME_ORDINAL_GAP", ctx.exception.message)

    def test_23_sequence_negative_or_invalid_ordinal_rejected(self):
        frames = [
            {"ordinal": -1, "sha256": "a" * 64, "filename": "f0.png"},
        ]
        with self.assertRaises(ForgeError) as ctx:
            validate_sequence("seq-neg", "Neg Ordinal", frames)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("INVALID_FRAME_ORDINAL", ctx.exception.message)

    def test_24_sequence_empty_or_too_large_rejected(self):
        with self.assertRaises(ForgeError) as ctx:
            validate_sequence("seq-empty", "Empty", [])
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("EMPTY_SEQUENCE", ctx.exception.message)

        too_many = [{"ordinal": i, "sha256": "a" * 64, "filename": f"f{i}.png"} for i in range(1025)]
        with self.assertRaises(ForgeError) as ctx:
            validate_sequence("seq-huge", "Huge", too_many)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("SEQUENCE_TOO_LARGE", ctx.exception.message)


class IngestionWorkbenchIntegrationTests(unittest.TestCase):
    """Integration of sequence staging with workbench mutations, project store, and catalog."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="rsf19-test-")
        self.projects_dir = Path(self.temp_dir.name)
        self.project_id = "test-ingest"
        self.profile = frozen_runtime_profile("player")
        self.actor_doc = make_standard_actor_doc(self.project_id, self.profile, parts=["body"])
        self.actor = load_actor(self.actor_doc)
        self.project = create_project(
            self.projects_dir,
            self.project_id,
            "Ingestion Test Project",
            self.actor_doc["id"],
            "player",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_25_duplicate_image_content_in_sequence(self):
        png_a = _make_test_png(24, 24, mode="RGBA", color=(50, 50, 50, 255))
        b64_a = base64.b64encode(png_a).decode()

        frames = [
            {"ordinal": 0, "filename": "frame0.png", "data_base64": b64_a},
            {"ordinal": 1, "filename": "frame1.png", "data_base64": b64_a},  # Identical content
        ]
        res = mutate(
            self.projects_dir,
            self.project,
            "stage-sequence",
            {"expected_revision": 1, "sequence_id": "seq-dup-content", "name": "Dup Content", "frames": frames},
        )
        # Should succeed; blob stored once idempotently
        self.assertEqual(res["project"]["revision"], 2)
        blobs_dir = self.projects_dir / self.project_id / "blobs"
        self.assertEqual(len(list(blobs_dir.iterdir())), 1)
        self.assertEqual(len(res["sequences"]), 1)
        self.assertEqual(res["sequences"][0]["frame_count"], 2)

    def test_26_immutability_and_idempotency(self):
        png = _make_test_png(16, 16, mode="RGBA", color=(100, 200, 50, 255))
        b64 = base64.b64encode(png).decode()
        expected_sha = digest(png)

        # Stage frame once
        res1 = mutate(
            self.projects_dir,
            self.project,
            "stage-png",
            {"expected_revision": 1, "filename": "frame.png", "data_base64": b64},
        )
        self.assertEqual(res1["project"]["revision"], 2)
        blob_bytes = get_blob(self.projects_dir, self.project_id, expected_sha)
        self.assertEqual(blob_bytes, png)

        # Re-staging same blob in a sequence at revision 2
        frames = [{"ordinal": 0, "filename": "frame.png", "data_base64": b64}]
        res2 = mutate(
            self.projects_dir,
            res1["project"],
            "stage-sequence",
            {"expected_revision": 2, "sequence_id": "seq-idem", "name": "Idempotent", "frames": frames},
        )
        self.assertEqual(res2["project"]["revision"], 3)
        # Blob remains byte-identical and unchanged
        self.assertEqual(get_blob(self.projects_dir, self.project_id, expected_sha), png)

    def test_27_transaction_atomicity_on_failure(self):
        png_good = _make_test_png(16, 16, mode="RGBA")
        b64_good = base64.b64encode(png_good).decode()
        b64_bad = base64.b64encode(b"not-a-png-file").decode()

        frames = [
            {"ordinal": 0, "filename": "good.png", "data_base64": b64_good},
            {"ordinal": 1, "filename": "bad.png", "data_base64": b64_bad},
        ]
        with self.assertRaises(ForgeError) as ctx:
            mutate(
                self.projects_dir,
                self.project,
                "stage-sequence",
                {"expected_revision": 1, "sequence_id": "atomic-seq", "name": "Atomic Fail", "frames": frames},
            )
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)

        # Reload on-disk manifest: revision must remain 1, sequences empty
        reloaded = load_project(self.projects_dir, self.project_id, verify_blobs=False)
        self.assertEqual(reloaded["revision"], 1)
        self.assertEqual(reloaded.get("sequences", []), [])

    def test_28_no_auto_assignment_and_no_auto_approval(self):
        png = _make_test_png(32, 32, mode="RGBA", transparency_pattern="partial")
        b64 = base64.b64encode(png).decode()

        frames = [{"ordinal": 0, "filename": "walk_0.png", "data_base64": b64}]
        res = mutate(
            self.projects_dir,
            self.project,
            "stage-sequence",
            {"expected_revision": 1, "sequence_id": "walk-s", "name": "Walk South", "frames": frames},
        )
        manifest = res["project"]

        # 1. No assignments created
        self.assertEqual(manifest.get("ledger", {}).get("assignments", []), [])

        # 2. No review events created
        self.assertEqual(manifest.get("review_events", []), [])

        # 3. Candidate appears in source_catalog as AVAILABLE, VALID, origin='AUTHORED'
        catalog = source_catalog(self.projects_dir, manifest)
        self.assertEqual(len(catalog), 1)
        entry = catalog[0]
        self.assertEqual(entry["availability"], "AVAILABLE")
        self.assertEqual(entry["validation"], "VALID")
        self.assertEqual(entry["preview"], "AVAILABLE")
        self.assertEqual(entry["source"]["origin"], "AUTHORED")
        self.assertEqual(entry["source"]["kind"], "IMAGE")
        self.assertEqual(entry["transparency_kind"], "PARTIALLY_TRANSPARENT")


class IngestionHttpApiTests(unittest.TestCase):
    """Test HTTP API endpoints for sequence and PNG staging."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="rsf19-http-")
        self.projects_dir = Path(self.temp_dir.name)
        self.server = create_server(self.projects_dir, host="127.0.0.1", port=0)
        self.port = self.server.server_port
        self.server_thread = None
        import threading
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

        self.project_id = "http-proj"
        create_project(self.projects_dir, self.project_id, "HTTP Test Project", "test-actor", "player")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp_dir.cleanup()

    def _request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
        import urllib.request
        url = f"http://127.0.0.1:{self.port}{path}"
        req_headers = {"Origin": f"http://127.0.0.1:{self.port}", "Host": f"127.0.0.1:{self.port}"}
        if headers:
            req_headers.update(headers)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        if body is not None:
            req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                payload = json.loads(resp.read().decode("utf-8"))
                return status, payload
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_stage_sequence_via_http(self):
        # 1. Fetch CSRF token
        status, csrf = self._request("GET", "/api/csrf-token")
        self.assertEqual(status, 200)
        token = csrf["csrf_token"]

        # 2. Stage sequence
        png = _make_test_png(24, 24, mode="RGBA")
        b64 = base64.b64encode(png).decode()
        payload = {
            "expected_revision": 1,
            "sequence_id": "api-walk",
            "name": "API Walk Sequence",
            "frames": [
                {"ordinal": 0, "filename": "step0.png", "data_base64": b64},
                {"ordinal": 1, "filename": "step1.png", "data_base64": b64},
            ],
        }
        status, res = self._request(
            "POST",
            f"/api/projects/{self.project_id}/stage-sequence",
            body=payload,
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(status, 200)
        self.assertEqual(res["project"]["revision"], 2)
        self.assertEqual(len(res["sequences"]), 1)

        # 3. GET /api/projects/{id}/sequences
        status, seqs = self._request("GET", f"/api/projects/{self.project_id}/sequences")
        self.assertEqual(status, 200)
        self.assertEqual(len(seqs["sequences"]), 1)
        self.assertEqual(seqs["sequences"][0]["id"], "api-walk")

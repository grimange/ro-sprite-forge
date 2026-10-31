"""Comprehensive unit, integration, and oracle test suite for RSF-23:
Deterministic ACT 2.4 / SPR 2.1 Writer, Metadata-Preserving Replacements,
and Copy-on-Write Shared-Reference Isolation.
"""

from __future__ import annotations

import base64
import copy
import io
import json
from pathlib import Path
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from PIL import Image

from ro_sprite_forge.cli import main as cli_main
from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.compiler import (
    compile_resources,
    plan_compilation,
    publish_compilation,
    validate_compilation_manifest,
    verify_pair_with_rust_oracle,
)
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, load_target, reference
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.ledger import assignment_binding, load_ledger, resolve_ledger
from ro_sprite_forge.core.profiles import get_profile
from ro_sprite_forge.core.project import create_project, get_blob, load_project
from ro_sprite_forge.core.topology import resolve_topology
from ro_sprite_forge.core.transformations import apply_transformation_recipe, validate_recipe
from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.formats.spr import (
    IndexedImage,
    RgbaImage,
    SprDocument,
    encode_rle,
    read_spr,
    write_spr,
)
from ro_sprite_forge.service.server import create_server, make_standard_actor_doc
from ro_sprite_forge.service.workbench import (
    compile_plan,
    mutate,
    record_review,
    review_proposal,
    workspace,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RUST_ORACLE_BIN = REPO_ROOT / "tools" / "rust-oracle" / "target" / "debug" / "rsf-rust-oracle"


def _make_png(width: int, height: int, rgba_tuple: tuple[int, int, int, int] = (255, 0, 0, 255), *, gradient: bool = False) -> bytes:
    im = Image.new("RGBA", (width, height), rgba_tuple)
    if gradient:
        for y in range(height):
            for x in range(width):
                im.putpixel(
                    (x, y),
                    (
                        (rgba_tuple[0] + x * 17) % 256,
                        (rgba_tuple[1] + y * 31) % 256,
                        (rgba_tuple[2] + (x + y) * 13) % 256,
                        rgba_tuple[3],
                    ),
                )
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    return bio.getvalue()


def _png_to_rgba_bytes(png_data: bytes) -> tuple[int, int, bytes]:
    with Image.open(io.BytesIO(png_data)) as im:
        rgba = im.convert("RGBA")
        return rgba.width, rgba.height, rgba.tobytes()


def _make_test_palette() -> bytes:
    """Create a 1024-byte SPR 2.1 palette with known colors at indices 1..10."""
    pal = bytearray(1024)
    known = [
        (0, 0, 0, 0),          # 0: transparent key
        (255, 0, 0, 255),      # 1: pure red
        (0, 255, 0, 255),      # 2: pure green
        (0, 0, 255, 255),      # 3: pure blue
        (255, 255, 0, 255),    # 4: yellow
        (0, 255, 255, 255),    # 5: cyan
        (255, 0, 255, 255),    # 6: magenta
        (255, 255, 255, 255),  # 7: white
        (128, 64, 32, 255),    # 8: brown
    ]
    for idx, (r, g, b, a) in enumerate(known):
        pal[idx * 4 : idx * 4 + 4] = bytes((r, g, b, a))
    for idx in range(len(known), 256):
        pal[idx * 4 : idx * 4 + 4] = bytes((idx, (idx * 3) % 256, (idx * 7) % 256, 255))
    return bytes(pal)


def _build_synthetic_monster_act_spr() -> tuple[bytes, bytes]:
    """Build a synthetic 40-slot Monster ACT 2.4 / SPR 2.1 pair with:
    - Shared SPR image 0 referenced by Walk slot 8 frame 0, Walk slot 8 frame 1, and Attack slot 16 frame 3!
    - Uniquely referenced SPR image 1 at Walk slot 8 frame 2.
    - Multilayer Death motion at slot 32 frame 0 with 3 visible layers + 1 hidden clip (sprite=-1).
    - Non-trivial offsets, scale_x, scale_y, angle, mirror, color tint/alpha, anchors, sound events, delays, reserved bytes.
    """
    pal = _make_test_palette()
    # Image 0 (Indexed 4x4, index 1 = red): shared across Walk frame 0, Walk frame 1, Attack frame 3
    img0_pixels = bytes([1] * 16)
    img0_rle = encode_rle(img0_pixels)
    # Image 1 (Indexed 4x4, index 2 = green): uniquely used by Walk slot 8 frame 2
    img1_pixels = bytes([2] * 16)
    img1_rle = encode_rle(img1_pixels)
    # Image 2 (Indexed 4x4, index 3 = blue): used by other slots/frames and Death layer 0
    img2_pixels = bytes([3] * 16)
    img2_rle = encode_rle(img2_pixels)
    # Image 3 (Indexed 4x4, index 4 = yellow): used by Death layer 1
    img3_pixels = bytes([4] * 16)
    img3_rle = encode_rle(img3_pixels)
    # Image 4 (Indexed 4x4, index 5 = cyan): used by Death layer 2
    img4_pixels = bytes([5] * 16)
    img4_rle = encode_rle(img4_pixels)
    # Truecolor Pool 1 Image 0 (4x4 RGBA)
    rgba0 = bytes([200, 100, 50, 255] * 16)

    spr_doc = SprDocument(
        indexed_images=[
            IndexedImage(4, 4, img0_pixels, len(img0_rle), img0_rle),
            IndexedImage(4, 4, img1_pixels, len(img1_rle), img1_rle),
            IndexedImage(4, 4, img2_pixels, len(img2_rle), img2_rle),
            IndexedImage(4, 4, img3_pixels, len(img3_rle), img3_rle),
            IndexedImage(4, 4, img4_pixels, len(img4_rle), img4_rle),
        ],
        rgba_images=[
            RgbaImage(4, 4, rgba0),
        ],
        palette=pal,
    )
    spr_bytes = write_spr(spr_doc)

    # 40 slots (5 groups * 8 views):
    # Group 0 (slots 0..7): Idle
    # Group 1 (slots 8..15): Walk
    # Group 2 (slots 16..23): Attack
    # Group 3 (slots 24..31): Hurt
    # Group 4 (slots 32..39): Die
    actions = []
    delays = []
    for slot in range(40):
        delays.append(4.0 + (slot * 0.25))
        if slot == 8:
            # Walk view 0: 4 frames
            motions = [
                # Frame 0: uses shared sprite 0
                {
                    "bounds": (-16, -32, 16, 0, 0, 0, 0, 0),
                    "clips": [
                        {
                            "x": -3,
                            "y": -14,
                            "sprite": 0,
                            "mirror": 0,
                            "color": 0xFFFAF0FF,
                            "scale_x": 1.25,
                            "scale_y": 0.75,
                            "angle": 15,
                            "pool": 0,
                        }
                    ],
                    "event": 0,
                    "anchors": [{"opaque": 0x01020304, "x": 2, "y": -20, "attribute": 1}],
                },
                # Frame 1: ALSO uses shared sprite 0!
                {
                    "bounds": (-16, -32, 16, 0, 0, 0, 0, 0),
                    "clips": [
                        {
                            "x": 1,
                            "y": -15,
                            "sprite": 0,
                            "mirror": 1,
                            "color": 0xFFFFFFC8,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                            "angle": 0,
                            "pool": 0,
                        }
                    ],
                    "event": -1,
                    "anchors": [{"opaque": 0, "x": 0, "y": -18, "attribute": 0}],
                },
                # Frame 2: uniquely uses sprite 1
                {
                    "bounds": (-16, -32, 16, 0, 0, 0, 0, 0),
                    "clips": [
                        {
                            "x": 0,
                            "y": -12,
                            "sprite": 1,
                            "mirror": 0,
                            "color": 0xFFFFFFFF,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                            "angle": 0,
                            "pool": 0,
                        }
                    ],
                    "event": 1,
                    "anchors": [],
                },
                # Frame 3: uses Pool 1 truecolor sprite 0
                {
                    "bounds": (-16, -32, 16, 0, 0, 0, 0, 0),
                    "clips": [
                        {
                            "x": 4,
                            "y": -10,
                            "sprite": 0,
                            "mirror": 0,
                            "color": 0xFFFFFFFF,
                            "scale_x": 1.5,
                            "scale_y": 1.5,
                            "angle": 45,
                            "pool": 1,
                        }
                    ],
                    "event": -1,
                    "anchors": [],
                },
            ]
        elif slot == 16:
            # Attack view 0: 4 frames; frame 3 ALSO uses shared sprite 0!
            motions = []
            for f_idx in range(4):
                spr_idx = 0 if f_idx == 3 else 2
                motions.append({
                    "bounds": (-20, -40, 20, 0, 0, 0, 0, 0),
                    "clips": [
                        {
                            "x": f_idx * 2,
                            "y": -16,
                            "sprite": spr_idx,
                            "mirror": 0,
                            "color": 0xFF8080FF,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                            "angle": 90 if f_idx == 3 else 0,
                            "pool": 0,
                        }
                    ],
                    "event": 0 if f_idx == 2 else -1,
                    "anchors": [{"opaque": 0xAABBCCDD, "x": -4, "y": -24, "attribute": 2}],
                })
        elif slot == 32:
            # Die view 0: multilayer frame 0 with 3 visible layers (sprites 2, 3, 4) and 1 hidden clip (sprite -1)
            motions = [
                {
                    "bounds": (-24, -24, 24, 24, 0, 0, 0, 0),
                    "clips": [
                        {
                            "x": -8,
                            "y": -4,
                            "sprite": 2,
                            "mirror": 0,
                            "color": 0xFFFFFFFF,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                            "angle": 0,
                            "pool": 0,
                        },
                        {
                            "x": 0,
                            "y": 0,
                            "sprite": -1,
                            "mirror": 0,
                            "color": 0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                            "angle": 0,
                            "pool": 0,
                        },
                        {
                            "x": 2,
                            "y": -6,
                            "sprite": 3,
                            "mirror": 1,
                            "color": 0xC8DCFFB4,
                            "scale_x": 1.125,
                            "scale_y": 0.875,
                            "angle": 30,
                            "pool": 0,
                        },
                        {
                            "x": 10,
                            "y": 4,
                            "sprite": 4,
                            "mirror": 0,
                            "color": 0xFFFFFFFF,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                            "angle": 270,
                            "pool": 0,
                        },
                    ],
                    "event": 1,
                    "anchors": [{"opaque": 0x11223344, "x": 5, "y": -5, "attribute": 3}],
                }
            ]
        else:
            motions = [
                {
                    "bounds": (0, 0, 0, 0, 0, 0, 0, 0),
                    "clips": [
                        {
                            "x": 0,
                            "y": 0,
                            "sprite": 2,
                            "mirror": 0,
                            "color": 0xFFFFFFFF,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                            "angle": 0,
                            "pool": 0,
                        }
                    ],
                    "event": -1,
                    "anchors": [],
                }
            ]
        actions.append(motions)

    ev0 = b"step.wav" + b"\x00" * 32
    ev1 = b"hit.wav" + b"\x00" * 33
    act_doc = {
        "reserved": "deadbeef010203040506",
        "actions": actions,
        "events": [ev0.hex(), ev1.hex()],
        "delays": delays,
    }
    act_bytes = write_act(act_doc)
    return act_bytes, spr_bytes


def _find_layer_id(reqs: dict, action: str, view: int, frame: int, ordinal: int = 0, part: str = "body") -> str:
    for l in reqs["layers"]:
        if (
            l["part"] == part
            and l["action"] == action
            and l["view"] == view
            and l["frame"] == frame
            and l["ordinal"] == ordinal
        ):
            return l["id"]
    raise AssertionError(f"Layer not found for ({part}, {action}, {view}, {frame}, {ordinal})")


def _setup_monster_contracts(act_bytes: bytes, spr_bytes: bytes, *, include_die: bool = False):
    """Build resolved requirements for the synthetic monster pair."""
    profile = frozen_runtime_profile("monster")
    inv = inventory(act_bytes, spr_bytes, actor="synth-monster", part="body", profile=get_profile("monster"))
    actor_doc = make_standard_actor_doc("synth-monster", profile, parts=["body"])
    actor_doc["resources"] = [
        {
            "part": "body",
            "inventory_sha256": inv["canonical_sha256"],
            "act_sha256": inv["sources"]["act"]["sha256"],
            "spr_sha256": inv["sources"]["spr"]["sha256"],
        }
    ]
    actor = load_actor(actor_doc)

    actions_spec = []
    for action_name, group_idx in (("Idle", 0), ("Walk", 1), ("Attack", 2), ("Hurt", 3), ("Die", 4)):
        if action_name == "Walk":
            views_spec = [
                {
                    "view": 0,
                    "frame_count": 4,
                    "topology": {
                        "kind": "inherited",
                        "inventory_sha256": inv["canonical_sha256"],
                        "slot": group_idx * 8 + 0,
                    },
                }
            ] + [
                {
                    "view": v,
                    "frame_count": 1,
                    "topology": {
                        "kind": "inherited",
                        "inventory_sha256": inv["canonical_sha256"],
                        "slot": group_idx * 8 + v,
                    },
                }
                for v in range(1, 8)
            ]
            req_state = "REQUIRED"
        elif action_name == "Die" and include_die:
            views_spec = [
                {
                    "view": v,
                    "frame_count": 1,
                    "topology": {
                        "kind": "inherited",
                        "inventory_sha256": inv["canonical_sha256"],
                        "slot": group_idx * 8 + v,
                    },
                }
                for v in range(8)
            ]
            req_state = "REQUIRED"
        else:
            views_spec = []
            req_state = "OUT_OF_SCOPE"
        actions_spec.append({
            "id": action_name,
            "requirement": req_state,
            "parts": [{"part": "body", "views": views_spec}] if views_spec else [],
        })

    target = load_target(
        {
            "schema": "rsf.target/v2",
            "id": "synth-monster-target",
            "revision": 1,
            "previous_sha256": None,
            "actor": reference(actor),
            "runtime_profile": reference(profile),
            "scope": "scoped",
            "parts": ["body"],
            "compatibility": {"status": "UNVERIFIED", "declarations": []},
            "actions": actions_spec,
        },
        actor=actor,
        profile=profile,
    )
    reqs = resolve_topology(target, actor=actor, profile=profile, inventories=(inv,))
    return actor, profile, target, inv, reqs


def _build_approved_ledger(
    reqs: dict,
    assignments_spec: list[dict],
    sources_spec: dict[str, bytes],
    *,
    source_origins: dict[str, str] | None = None,
) -> dict:
    """Create a resolved ledger where every specified assignment has a valid bound operator review."""
    layers_by_id = {l["id"]: l for l in reqs["layers"]}
    origins = source_origins or {}
    sources_list = []
    for sid, raw_bytes in sorted(sources_spec.items()):
        sources_list.append({
            "id": sid,
            "revision": 1,
            "sha256": digest(raw_bytes),
            "kind": "IMAGE",
            "origin": origins.get(sid, "AUTHORED"),
            "external_ref": f"{sid}.png",
            "image": None,
            "provenance": None,
        })

    # First pass: load without review to compute canonical composition_sha256
    raw_assignments = []
    for spec in assignments_spec:
        rid = spec["requirement_id"]
        aid = spec.get("id") or ("assignment-" + digest(rid.encode()))
        raw_assignments.append({
            "id": aid,
            "revision": spec.get("revision", 1),
            "requirement_id": rid,
            "binding": assignment_binding(layers_by_id[rid]),
            "kind": spec["kind"],
            "source": spec.get("source"),
            "dependency": spec.get("dependency"),
            "recipe": spec.get("recipe", []),
            "review": None,
        })

    base_doc = {
        "schema": "rsf.assignment-ledger/v1",
        "id": "synth-ledger",
        "revision": 1,
        "previous_sha256": None,
        "target": reqs["target"],
        "requirements_sha256": reqs["canonical_sha256"],
        "sources": sources_list,
        "assignments": raw_assignments,
        "attachments": [],
    }
    loaded_unreviewed = load_ledger(base_doc, requirements=reqs)
    resolved_unreviewed = resolve_ledger(loaded_unreviewed, requirements=reqs, source_bytes=sources_spec)
    basis_by_rid = {a["requirement_id"]: a["composition_sha256"] for a in resolved_unreviewed["assignments"]}

    for a_item, spec in zip(base_doc["assignments"], assignments_spec):
        rev_state = spec.get("review_state", "APPROVED")
        if rev_state is not None:
            a_item["review"] = {
                "state": rev_state,
                "authority": "OPERATOR",
                "operator": "test-operator",
                "evidence_sha256": "e" * 64,
                "basis_sha256": spec.get("override_basis_sha256") or basis_by_rid[a_item["requirement_id"]],
                "policy": "UNCHANGED_REFERENCE" if rev_state == "NOT_REQUIRED" else "VISUAL_DECISION",
            }
    return base_doc


class SprCodecRoundtripAndRleTests(unittest.TestCase):
    """Test cases 1 & 2: ACT and SPR byte-preserving round-trip and RLE encoding/decoding."""

    def test_01_act_and_spr_noop_byte_preserving_roundtrip(self):
        act_bytes, spr_bytes = _build_synthetic_monster_act_spr()
        self.assertEqual(write_act(read_act(act_bytes)), act_bytes)
        self.assertEqual(write_spr(read_spr(spr_bytes)), spr_bytes)

        comp = compile_resources(
            act_bytes,
            spr_bytes,
            compilation_mode="preserve",
            oracle_executable=RUST_ORACLE_BIN if RUST_ORACLE_BIN.is_file() else None,
        )
        self.assertEqual(comp["act_bytes"], act_bytes)
        self.assertEqual(comp["spr_bytes"], spr_bytes)
        self.assertTrue(comp["manifest"]["verification"]["noop_byte_equal"])
        self.assertEqual(comp["manifest"]["verification"]["native_korangar"], "UNVERIFIED")
        if RUST_ORACLE_BIN.is_file():
            self.assertEqual(comp["manifest"]["verification"]["rust_oracle"], "PASS")

    def test_02_spr_preserves_non_minimal_original_rle_bytes_on_unchanged_sprites(self):
        pal = _make_test_palette()
        # Construct non-minimal RLE for 4 zero pixels: two separate runs of 2 zeros (00 02 00 02)
        # instead of minimal 00 04
        non_minimal_rle = b"\x00\x02\x00\x02"
        spr_bytes = (
            b"SP\x01\x02"
            + struct.pack("<HH", 1, 0)
            + struct.pack("<HHH", 2, 2, len(non_minimal_rle))
            + non_minimal_rle
            + pal
        )
        parsed = read_spr(spr_bytes)
        self.assertEqual(parsed.indexed_images[0].pixels, b"\x00\x00\x00\x00")
        reencoded = write_spr(parsed)
        self.assertEqual(reencoded, spr_bytes)

    def test_03_encode_rle_handles_long_zero_runs_over_255(self):
        pixels = b"\x00" * 600 + b"\x05\x00\x07"
        rle = encode_rle(pixels)
        # 600 = 255 + 255 + 90 -> 3 pairs (6 bytes) + 1 byte (0x05) + 2 bytes (0x00, 0x01) + 1 byte (0x07) = 10 bytes
        self.assertEqual(rle, b"\x00\xff\x00\xff\x00\x5a\x05\x00\x01\x07")
        pal = _make_test_palette()
        doc = SprDocument(
            indexed_images=[IndexedImage(603, 1, pixels, len(rle), rle)],
            rgba_images=[],
            palette=pal,
        )
        out_bytes = write_spr(doc)
        dec = read_spr(out_bytes)
        self.assertEqual(dec.indexed_images[0].pixels, pixels)


class ReplacementMatrixTests(unittest.TestCase):
    """Covers the 28-point replacement, shared-reference isolation, metadata, and negative test matrix."""

    def setUp(self):
        self.act_bytes, self.spr_bytes = _build_synthetic_monster_act_spr()
        self.actor, self.profile, self.target, self.inv, self.reqs = _setup_monster_contracts(
            self.act_bytes, self.spr_bytes, include_die=True
        )

    def test_04_uniquely_referenced_image_replacement_in_place_and_append(self):
        # Walk view 0 frame 2 layer 0 uniquely references indexed sprite 1
        rid = _find_layer_id(self.reqs, "Walk", 0, 2, 0)
        # Color (0, 0, 255, 255) is palette index 3 in _make_test_palette()
        src_png = _make_png(4, 4, (0, 0, 255, 255))
        sources = {"src-unique": src_png}
        ledger_doc = _build_approved_ledger(
            self.reqs,
            [{"requirement_id": rid, "kind": "DIRECT_SOURCE", "source": {"id": "src-unique", "revision": 1}}],
            sources,
        )

        # Under preserve_pool + auto, uniquely referenced sprite 1 is replaced IN_PLACE_UNSHARED
        res_in_place = compile_resources(
            self.act_bytes,
            self.spr_bytes,
            requirements=self.reqs,
            ledger=ledger_doc,
            source_bytes=sources,
            replacement_requirement_ids=[rid],
            replacement_policy="preserve_pool",
            isolation_strategy="auto",
            oracle_executable=RUST_ORACLE_BIN if RUST_ORACLE_BIN.is_file() else None,
        )
        rep = res_in_place["manifest"]["replacements"][0]
        self.assertEqual(rep["resolution_mode"], "IN_PLACE_UNSHARED")
        self.assertEqual(rep["original_image"]["pool"], 0)
        self.assertEqual(rep["original_image"]["index"], 1)
        self.assertEqual(rep["output_image"]["pool"], 0)
        self.assertEqual(rep["output_image"]["index"], 1)

        # Under always_append, even a uniquely referenced sprite is appended (COPY_ON_WRITE_APPEND)
        res_append = compile_resources(
            self.act_bytes,
            self.spr_bytes,
            requirements=self.reqs,
            ledger=ledger_doc,
            source_bytes=sources,
            replacement_requirement_ids=[rid],
            replacement_policy="preserve_pool",
            isolation_strategy="always_append",
        )
        rep_app = res_append["manifest"]["replacements"][0]
        self.assertEqual(rep_app["resolution_mode"], "COPY_ON_WRITE_APPEND")
        self.assertEqual(rep_app["output_image"]["pool"], 0)
        self.assertEqual(rep_app["output_image"]["index"], 5)  # appended after 0..4

    def test_05_shared_image_reference_isolation_preserves_walk_frame1_and_attack_frame3(self):
        """Mandatory §19 test:
        SPR image 0 (pure red) is referenced by:
        - Walk slot 8 frame 0 clip 0
        - Walk slot 8 frame 1 clip 0
        - Attack slot 16 frame 3 clip 0
        Replace ONLY Walk slot 8 frame 0 clip 0 with a new 8x8 cyan/magenta gradient PNG.
        Verify:
        1. Walk slot 8 frame 0 resolves to the new 8x8 replacement image via COPY_ON_WRITE_APPEND.
        2. Walk slot 8 frame 1 and Attack slot 16 frame 3 still reference original SPR image (0, 0)
           and decode to the exact original 4x4 pure red pixels!
        """
        rid_walk_f0 = _find_layer_id(self.reqs, "Walk", 0, 0, 0)
        new_png = _make_png(8, 8, (10, 200, 150, 255), gradient=True)
        _, _, expected_new_rgba = _png_to_rgba_bytes(new_png)
        sources = {"src-walk-f0": new_png}
        ledger_doc = _build_approved_ledger(
            self.reqs,
            [{"requirement_id": rid_walk_f0, "kind": "DIRECT_SOURCE", "source": {"id": "src-walk-f0", "revision": 1}}],
            sources,
        )

        orig_spr = read_spr(self.spr_bytes)
        orig_img0_rgba = orig_spr.indexed_images[0].to_rgba(orig_spr.palette)

        res = compile_resources(
            self.act_bytes,
            self.spr_bytes,
            requirements=self.reqs,
            ledger=ledger_doc,
            source_bytes=sources,
            replacement_requirement_ids=[rid_walk_f0],
            replacement_policy="explicit_rgba",
            isolation_strategy="auto",
            oracle_executable=RUST_ORACLE_BIN if RUST_ORACLE_BIN.is_file() else None,
        )

        manifest = res["manifest"]
        rep = manifest["replacements"][0]
        self.assertEqual(rep["resolution_mode"], "COPY_ON_WRITE_APPEND")
        self.assertEqual(rep["shared_consumers_count"], 3)
        self.assertEqual(rep["unaffected_consumers_count"], 2)
        self.assertEqual(rep["original_image"]["pool"], 0)
        self.assertEqual(rep["original_image"]["index"], 0)
        self.assertEqual(rep["output_image"]["pool"], 1)
        self.assertEqual(rep["output_image"]["index"], 1)  # Appended after existing rgba_images[0]

        out_act = read_act(res["act_bytes"])
        out_spr = read_spr(res["spr_bytes"])

        # 1. Walk slot 8 frame 0 clip 0 points to (pool=1, sprite=1) with 8x8 replacement pixels
        c_walk0 = out_act["actions"][8][0]["clips"][0]
        self.assertEqual((c_walk0["pool"], c_walk0["sprite"]), (1, 1))
        self.assertEqual((out_spr.rgba_images[1].width, out_spr.rgba_images[1].height), (8, 8))
        self.assertEqual(out_spr.rgba_images[1].rgba, expected_new_rgba)
        # Metadata on Walk slot 8 frame 0 clip 0 preserved!
        self.assertEqual((c_walk0["x"], c_walk0["y"]), (-3, -14))
        self.assertEqual(c_walk0["color"], 0xFFFAF0FF)
        self.assertEqual((c_walk0["scale_x"], c_walk0["scale_y"]), (1.25, 0.75))
        self.assertEqual(c_walk0["angle"], 15)

        # 2. Walk slot 8 frame 1 clip 0 still points to (pool=0, sprite=0) with original 4x4 red pixels!
        c_walk1 = out_act["actions"][8][1]["clips"][0]
        self.assertEqual((c_walk1["pool"], c_walk1["sprite"]), (0, 0))
        self.assertEqual(out_spr.indexed_images[0].to_rgba(out_spr.palette), orig_img0_rgba)

        # 3. Attack slot 16 frame 3 clip 0 still points to (pool=0, sprite=0) with original 4x4 red pixels!
        c_atk3 = out_act["actions"][16][3]["clips"][0]
        self.assertEqual((c_atk3["pool"], c_atk3["sprite"]), (0, 0))
        self.assertEqual(c_atk3["angle"], 90)
        self.assertEqual(out_spr.indexed_images[0].to_rgba(out_spr.palette), orig_img0_rgba)

    def test_06_multiple_replacements_and_intentional_shared_replacement_deduplication(self):
        """Tests cases 6 & 7:
        Replace Walk view 0 frames 0, 1, 2, 3 in one compilation:
        - Frame 0 and Frame 1 intentionally share the SAME source image (via EXPLICIT_REUSE without transforms)
          -> Frame 1 uses REUSED_COMPILATION_ENTRY without duplicating the SPR image!
        - Frame 2 uses EXPLICIT_REUSE with mirror_x -> gets horizontally flipped pixels!
        - Frame 3 replaces a Pool 1 truecolor clip.
        """
        r0 = _find_layer_id(self.reqs, "Walk", 0, 0, 0)
        r1 = _find_layer_id(self.reqs, "Walk", 0, 1, 0)
        r2 = _find_layer_id(self.reqs, "Walk", 0, 2, 0)
        r3 = _find_layer_id(self.reqs, "Walk", 0, 3, 0)

        asym_png = _make_png(6, 4, (50, 100, 150, 255), gradient=True)
        png3 = _make_png(6, 6, (200, 50, 100, 255))
        sources = {"src-asym": asym_png, "src-f3": png3}

        aid0 = "assignment-walk0"
        assignments_spec = [
            {"id": aid0, "requirement_id": r0, "kind": "DIRECT_SOURCE", "source": {"id": "src-asym", "revision": 1}},
            {"requirement_id": r1, "kind": "EXPLICIT_REUSE", "dependency": {"id": aid0, "revision": 1}, "recipe": []},
            {
                "requirement_id": r2,
                "kind": "EXPLICIT_REUSE",
                "dependency": {"id": aid0, "revision": 1},
                "recipe": [{"id": "m1", "op": "mirror_x", "version": 1, "parameters": {}}],
            },
            {"requirement_id": r3, "kind": "DIRECT_SOURCE", "source": {"id": "src-f3", "revision": 1}},
        ]
        ledger_doc = _build_approved_ledger(self.reqs, assignments_spec, sources)

        res = compile_resources(
            self.act_bytes,
            self.spr_bytes,
            requirements=self.reqs,
            ledger=ledger_doc,
            source_bytes=sources,
            replacement_requirement_ids=[r0, r1, r2, r3],
            replacement_policy="explicit_rgba",
            isolation_strategy="auto",
            oracle_executable=RUST_ORACLE_BIN if RUST_ORACLE_BIN.is_file() else None,
        )
        reps = {x["requirement_id"]: x for x in res["manifest"]["replacements"]}
        # r0 and r1 share the exact same output SPR entry!
        self.assertEqual(reps[r0]["resolution_mode"], "COPY_ON_WRITE_APPEND")
        self.assertEqual(reps[r1]["resolution_mode"], "REUSED_COMPILATION_ENTRY")
        self.assertEqual(reps[r0]["output_image"], reps[r1]["output_image"])

        # r2 has executed_ledger_ops == ["mirror_x"] and horizontally flipped pixels
        self.assertEqual(reps[r2]["executed_ledger_ops"], ["mirror_x"])
        self.assertNotEqual(reps[r2]["output_image"]["index"], reps[r0]["output_image"]["index"])
        with Image.open(io.BytesIO(asym_png)) as im:
            expected_flipped = im.convert("RGBA").transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes()
        out_spr = read_spr(res["spr_bytes"])
        self.assertEqual(out_spr.rgba_images[reps[r2]["output_image"]["index"]].rgba, expected_flipped)

        # r3 replaced uniquely referenced Pool 1 sprite 0 in-place!
        self.assertEqual(reps[r3]["resolution_mode"], "IN_PLACE_UNSHARED")
        self.assertEqual((reps[r3]["output_image"]["pool"], reps[r3]["output_image"]["index"]), (1, 0))

    def test_07_multilayer_ordering_and_hidden_clip_preservation(self):
        """Tests cases 10 & 11:
        Die slot 32 frame 0 has 4 ACT clips:
        - clip 0: visible layer 0 (sprite 2)
        - clip 1: hidden clip (sprite -1)
        - clip 2: visible layer 1 (sprite 3)
        - clip 3: visible layer 2 (sprite 4)
        Replace ONLY visible layer 1 (clip 2) and verify:
        - Layer count and order (4 clips) are preserved without flattening.
        - Clip 0 (layer 0), clip 1 (hidden sprite -1), and clip 3 (layer 2) are untouched.
        - Clip 2 (layer 1) is updated at clip_ordinal=2 while retaining its x, y, mirror, color, scale, angle!
        """
        rid_die_l1 = _find_layer_id(self.reqs, "Die", 0, 0, 1)
        new_png = _make_png(10, 12, (123, 45, 67, 200))
        sources = {"src-die-l1": new_png}
        ledger_doc = _build_approved_ledger(
            self.reqs,
            [{"requirement_id": rid_die_l1, "kind": "DIRECT_SOURCE", "source": {"id": "src-die-l1", "revision": 1}}],
            sources,
        )

        res = compile_resources(
            self.act_bytes,
            self.spr_bytes,
            requirements=self.reqs,
            ledger=ledger_doc,
            source_bytes=sources,
            replacement_requirement_ids=[rid_die_l1],
            replacement_policy="explicit_rgba",
            oracle_executable=RUST_ORACLE_BIN if RUST_ORACLE_BIN.is_file() else None,
        )
        rep = res["manifest"]["replacements"][0]
        self.assertEqual(rep["layer_ordinal"], 1)
        self.assertEqual(rep["clip_ordinal"], 2)

        orig_act = read_act(self.act_bytes)
        out_act = read_act(res["act_bytes"])
        orig_clips = orig_act["actions"][32][0]["clips"]
        out_clips = out_act["actions"][32][0]["clips"]
        self.assertEqual(len(out_clips), 4)
        self.assertEqual(out_clips[0], orig_clips[0])
        self.assertEqual(out_clips[1], orig_clips[1])  # hidden sprite -1 preserved
        self.assertEqual(out_clips[3], orig_clips[3])
        # Clip 2 retained all placement/tint/transform metadata
        for k in ("x", "y", "mirror", "color", "scale_x", "scale_y", "angle"):
            self.assertEqual(out_clips[2][k], orig_clips[2][k])
        self.assertEqual(res["manifest"]["preservation_summary"]["hidden_clips_preserved"], 1)

    def test_08_indexed_lossless_palette_matching_and_rejection_of_lossy_inputs(self):
        """Tests case 17:
        - Valid palette-compatible PNG (using transparent alpha=0 and palette color (0, 255, 0, 255) = index 2)
          succeeds under indexed_exact / preserve_pool.
        - PNG with semitransparent alpha (128) is rejected with UNSUPPORTED_INDEXED_CONVERSION.
        - PNG with off-palette RGB color (1, 2, 3) is rejected with UNSUPPORTED_INDEXED_CONVERSION.
        """
        rid = _find_layer_id(self.reqs, "Walk", 0, 0, 0)
        # Valid indexed image: top half transparent (0,0,0,0), bottom half pure green (0,255,0,255) = index 2
        im = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        for y in range(2, 4):
            for x in range(4):
                im.putpixel((x, y), (0, 255, 0, 255))
        bio = io.BytesIO()
        im.save(bio, format="PNG")
        valid_indexed_png = bio.getvalue()

        sources = {"src-idx": valid_indexed_png}
        ledger_doc = _build_approved_ledger(
            self.reqs,
            [{"requirement_id": rid, "kind": "DIRECT_SOURCE", "source": {"id": "src-idx", "revision": 1}}],
            sources,
        )
        res = compile_resources(
            self.act_bytes,
            self.spr_bytes,
            requirements=self.reqs,
            ledger=ledger_doc,
            source_bytes=sources,
            replacement_requirement_ids=[rid],
            replacement_policy="indexed_exact",
            oracle_executable=RUST_ORACLE_BIN if RUST_ORACLE_BIN.is_file() else None,
        )
        rep = res["manifest"]["replacements"][0]
        self.assertEqual(rep["output_image"]["pool"], 0)
        self.assertIn("ENCODED_LOSSLESS_INDEXED_RLE", rep["representational_notes"])
        out_spr = read_spr(res["spr_bytes"])
        self.assertEqual(
            out_spr.indexed_images[rep["output_image"]["index"]].pixels,
            b"\x00" * 8 + b"\x02" * 8,
        )

        # Semitransparent alpha rejected under indexed_exact
        semi_png = _make_png(4, 4, (0, 255, 0, 128))
        sources_semi = {"src-semi": semi_png}
        ledger_semi = _build_approved_ledger(
            self.reqs,
            [{"requirement_id": rid, "kind": "DIRECT_SOURCE", "source": {"id": "src-semi", "revision": 1}}],
            sources_semi,
        )
        with self.assertRaises(ForgeError) as ctx:
            compile_resources(
                self.act_bytes,
                self.spr_bytes,
                requirements=self.reqs,
                ledger=ledger_semi,
                source_bytes=sources_semi,
                replacement_requirement_ids=[rid],
                replacement_policy="indexed_exact",
            )
        self.assertIn("UNSUPPORTED_INDEXED_CONVERSION", ctx.exception.message)

        # Off-palette RGB color rejected under preserve_pool (when original clip is pool 0)
        off_png = _make_png(4, 4, (1, 2, 3, 255))
        sources_off = {"src-off": off_png}
        ledger_off = _build_approved_ledger(
            self.reqs,
            [{"requirement_id": rid, "kind": "DIRECT_SOURCE", "source": {"id": "src-off", "revision": 1}}],
            sources_off,
        )
        with self.assertRaises(ForgeError) as ctx2:
            compile_resources(
                self.act_bytes,
                self.spr_bytes,
                requirements=self.reqs,
                ledger=ledger_off,
                source_bytes=sources_off,
                replacement_requirement_ids=[rid],
                replacement_policy="preserve_pool",
            )
        self.assertIn("UNSUPPORTED_INDEXED_CONVERSION", ctx2.exception.message)

    def test_09_rsf21_derived_image_compiled_once_without_double_transformation(self):
        """Tests case 19:
        Stage an RSF-21 derived image (crop 8x8 -> 4x4 + horizontal flip) and compile it.
        Verify:
        - The compiled SPR contains the exact derived 4x4 pixels (NOT flipped or cropped a second time).
        - manifest['replacements'][0]['derived_processing']['reapplied_in_compiler'] is False.
        - Provenance records recipe_id, recipe_sha256, and source_sha256.
        """
        raw_sheet = _make_png(8, 8, (10, 20, 30, 255), gradient=True)
        raw_sha = digest(raw_sheet)
        recipe = validate_recipe({
            "id": "crop-flip-walk0",
            "name": "Crop and Flip Walk 0",
            "source_sha256": raw_sha,
            "operations": [
                {"op": "crop", "x": 0, "y": 0, "width": 4, "height": 4},
                {"op": "flip", "direction": "horizontal"},
            ],
        })
        trans = apply_transformation_recipe(raw_sheet, recipe, expected_source_sha256=raw_sha)
        derived_bytes = trans["output_bytes"]
        derived_sha = trans["derived_sha256"]
        _, _, expected_derived_rgba = _png_to_rgba_bytes(derived_bytes)

        rid = _find_layer_id(self.reqs, "Walk", 0, 0, 0)
        sid = f"blob-{derived_sha}"
        sources = {sid: derived_bytes}
        source_meta = {
            derived_sha: {
                "recipe_id": recipe["id"],
                "recipe_sha256": trans["recipe_sha256"],
                "source_sha256": raw_sha,
            }
        }
        ledger_doc = _build_approved_ledger(
            self.reqs,
            [{"requirement_id": rid, "kind": "DIRECT_SOURCE", "source": {"id": sid, "revision": 1}}],
            sources,
        )

        res = compile_resources(
            self.act_bytes,
            self.spr_bytes,
            requirements=self.reqs,
            ledger=ledger_doc,
            source_bytes=sources,
            source_metadata=source_meta,
            replacement_requirement_ids=[rid],
            replacement_policy="explicit_rgba",
        )
        rep = res["manifest"]["replacements"][0]
        self.assertEqual(rep["derived_processing"]["recipe_id"], "crop-flip-walk0")
        self.assertEqual(rep["derived_processing"]["recipe_sha256"], trans["recipe_sha256"])
        self.assertEqual(rep["derived_processing"]["source_sha256"], raw_sha)
        self.assertFalse(rep["derived_processing"]["reapplied_in_compiler"])

        out_spr = read_spr(res["spr_bytes"])
        self.assertEqual(out_spr.rgba_images[rep["output_image"]["index"]].rgba, expected_derived_rgba)

    def test_10_deterministic_repeated_compilation_and_atomic_publication(self):
        """Tests cases 21 & atomic output publication without overwriting."""
        rid = _find_layer_id(self.reqs, "Walk", 0, 0, 0)
        src_png = _make_png(6, 6, (90, 180, 240, 255), gradient=True)
        sources = {"src-det": src_png}
        ledger_doc = _build_approved_ledger(
            self.reqs,
            [{"requirement_id": rid, "kind": "DIRECT_SOURCE", "source": {"id": "src-det", "revision": 1}}],
            sources,
        )

        res1 = compile_resources(
            self.act_bytes,
            self.spr_bytes,
            requirements=self.reqs,
            ledger=ledger_doc,
            source_bytes=sources,
            replacement_requirement_ids=[rid],
            compilation_id="det-test",
            replacement_policy="explicit_rgba",
        )
        res2 = compile_resources(
            self.act_bytes,
            self.spr_bytes,
            requirements=self.reqs,
            ledger=ledger_doc,
            source_bytes=sources,
            replacement_requirement_ids=[rid],
            compilation_id="det-test",
            replacement_policy="explicit_rgba",
        )
        self.assertEqual(res1["act_bytes"], res2["act_bytes"])
        self.assertEqual(res1["spr_bytes"], res2["spr_bytes"])
        self.assertEqual(canonical_bytes(res1["manifest"]), canonical_bytes(res2["manifest"]))
        validate_compilation_manifest(res1["manifest"])

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "compiled-out"
            pub = publish_compilation(out_dir, res1)
            self.assertTrue(Path(pub["act_path"]).is_file())
            self.assertTrue(Path(pub["spr_path"]).is_file())
            self.assertTrue(Path(pub["manifest_path"]).is_file())

            # Second publication to same directory must fail closed without overwriting
            with self.assertRaises(ForgeError) as ctx:
                publish_compilation(out_dir, res2)
            self.assertEqual(ctx.exception.code, ErrorCode.INVALID_OUTPUT)

    def test_11_negative_guards_review_revision_format_and_immutability(self):
        """Tests case 20: comprehensive fail-closed negative checks and source immutability."""
        rid = _find_layer_id(self.reqs, "Walk", 0, 0, 0)
        src_png = _make_png(4, 4, (255, 0, 0, 255))
        sources = {"src-neg": src_png}
        orig_act_sha = digest(self.act_bytes)
        orig_spr_sha = digest(self.spr_bytes)

        # 1. Unapproved artwork (UNVERIFIED) rejected
        ledger_unverified = _build_approved_ledger(
            self.reqs,
            [{"requirement_id": rid, "kind": "DIRECT_SOURCE", "source": {"id": "src-neg", "revision": 1}, "review_state": None}],
            sources,
        )
        with self.assertRaises(ForgeError) as ctx:
            compile_resources(
                self.act_bytes, self.spr_bytes, requirements=self.reqs, ledger=ledger_unverified, source_bytes=sources, replacement_requirement_ids=[rid]
            )
        self.assertIn("UNAPPROVED_REPLACEMENT_ARTWORK", ctx.exception.message)

        # 2. Rejected artwork (REJECTED) rejected
        ledger_rejected = _build_approved_ledger(
            self.reqs,
            [{"requirement_id": rid, "kind": "DIRECT_SOURCE", "source": {"id": "src-neg", "revision": 1}, "review_state": "REJECTED"}],
            sources,
        )
        with self.assertRaises(ForgeError) as ctx:
            compile_resources(
                self.act_bytes, self.spr_bytes, requirements=self.reqs, ledger=ledger_rejected, source_bytes=sources, replacement_requirement_ids=[rid]
            )
        self.assertIn("REJECTED_REPLACEMENT_ARTWORK", ctx.exception.message)

        # 3. Stale review approval rejected
        ledger_stale = _build_approved_ledger(
            self.reqs,
            [
                {
                    "requirement_id": rid,
                    "kind": "DIRECT_SOURCE",
                    "source": {"id": "src-neg", "revision": 1},
                    "review_state": "APPROVED",
                    "override_basis_sha256": "0" * 64,
                }
            ],
            sources,
        )
        with self.assertRaises(ForgeError) as ctx:
            compile_resources(
                self.act_bytes, self.spr_bytes, requirements=self.reqs, ledger=ledger_stale, source_bytes=sources, replacement_requirement_ids=[rid]
            )
        self.assertIn("STALE_REVIEW_APPROVAL", ctx.exception.message)

        # 4. Incomplete actor rejected under production_export mode
        ledger_ok = _build_approved_ledger(
            self.reqs,
            [{"requirement_id": rid, "kind": "DIRECT_SOURCE", "source": {"id": "src-neg", "revision": 1}}],
            sources,
        )
        with self.assertRaises(ForgeError) as ctx:
            compile_resources(
                self.act_bytes,
                self.spr_bytes,
                requirements=self.reqs,
                ledger=ledger_ok,
                source_bytes=sources,
                replacement_requirement_ids=[rid],
                compilation_mode="production_export",
            )
        self.assertIn("PRODUCTION_EXPORT_NOT_READY", ctx.exception.message)

        # 5. Shared image mutation rejected under in_place_only
        with self.assertRaises(ForgeError) as ctx:
            compile_resources(
                self.act_bytes,
                self.spr_bytes,
                requirements=self.reqs,
                ledger=ledger_ok,
                source_bytes=sources,
                replacement_requirement_ids=[rid],
                replacement_policy="preserve_pool",
                isolation_strategy="in_place_only",
            )
        self.assertIn("SHARED_IMAGE_MUTATION_FORBIDDEN", ctx.exception.message)

        # 6. Stale target or ledger revision rejected
        with self.assertRaises(ForgeError) as ctx:
            compile_resources(
                self.act_bytes,
                self.spr_bytes,
                requirements=self.reqs,
                ledger=ledger_ok,
                source_bytes=sources,
                replacement_requirement_ids=[rid],
                expected_target_revision=99,
            )
        self.assertIn("STALE_TARGET_REVISION", ctx.exception.message)

        with self.assertRaises(ForgeError) as ctx:
            compile_resources(
                self.act_bytes,
                self.spr_bytes,
                requirements=self.reqs,
                ledger=ledger_ok,
                source_bytes=sources,
                replacement_requirement_ids=[rid],
                expected_ledger_revision=99,
            )
        self.assertIn("STALE_LEDGER_REVISION", ctx.exception.message)

        # 7. Source hash mismatch / missing source rejected
        with self.assertRaises(ForgeError) as ctx:
            compile_resources(
                self.act_bytes,
                self.spr_bytes,
                requirements=self.reqs,
                ledger=ledger_ok,
                source_bytes={"src-neg": b"corrupted"},
                replacement_requirement_ids=[rid],
            )
        self.assertIn("SOURCE_HASH_MISMATCH", ctx.exception.message)

        with self.assertRaises(ForgeError) as ctx:
            compile_resources(
                self.act_bytes,
                self.spr_bytes,
                requirements=self.reqs,
                ledger=ledger_ok,
                source_bytes={},
                replacement_requirement_ids=[rid],
            )
        self.assertIn("MISSING_REPLACEMENT_SOURCE", ctx.exception.message)

        # 8. Corrupted ACT/SPR input rejected
        with self.assertRaises(ForgeError):
            compile_resources(
                b"AC\x05\x02corrupt",
                self.spr_bytes,
                requirements=self.reqs,
                ledger=ledger_ok,
                source_bytes=sources,
                replacement_requirement_ids=[rid],
            )

        # Verify original input bytes were never mutated
        self.assertEqual(digest(self.act_bytes), orig_act_sha)
        self.assertEqual(digest(self.spr_bytes), orig_spr_sha)


class CliAndHttpServiceCompilationTests(unittest.TestCase):
    """Tests case 23: CLI `ro-sprite-forge compile` and HTTP `/compile-plan`, `/compile`, `/compilations`."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.act_bytes, self.spr_bytes = _build_synthetic_monster_act_spr()
        self.actor, self.profile, self.target, self.inv, self.reqs = _setup_monster_contracts(
            self.act_bytes, self.spr_bytes
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_12_cli_compile_and_plan_only(self):
        act_path = self.root / "orig.act"
        spr_path = self.root / "orig.spr"
        req_path = self.root / "reqs.json"
        led_path = self.root / "ledger.json"
        src_path = self.root / "frame0.png"

        rid = _find_layer_id(self.reqs, "Walk", 0, 0, 0)
        png_bytes = _make_png(6, 6, (40, 120, 220, 255))
        sources = {"src-cli": png_bytes}
        ledger_doc = _build_approved_ledger(
            self.reqs,
            [{"requirement_id": rid, "kind": "DIRECT_SOURCE", "source": {"id": "src-cli", "revision": 1}}],
            sources,
        )

        act_path.write_bytes(self.act_bytes)
        spr_path.write_bytes(self.spr_bytes)
        req_path.write_bytes(canonical_bytes(self.reqs))
        led_path.write_bytes(canonical_bytes(ledger_doc))
        src_path.write_bytes(png_bytes)

        plan_out = self.root / "plan.json"
        rc_plan = cli_main([
            "compile",
            "--act", str(act_path),
            "--spr", str(spr_path),
            "--requirements", str(req_path),
            "--ledger", str(led_path),
            "--source", f"src-cli={src_path}",
            "--requirement-id", rid,
            "--policy", "explicit_rgba",
            "--plan-only",
            "--manifest", str(plan_out),
        ])
        self.assertEqual(rc_plan, 0)
        plan_data = json.loads(plan_out.read_text())
        self.assertTrue(plan_data["ready_to_compile"])
        self.assertEqual(len(plan_data["selected_replacements"]), 1)

        out_dir = self.root / "compiled-pkg"
        cli_args = [
            "compile",
            "--act", str(act_path),
            "--spr", str(spr_path),
            "--requirements", str(req_path),
            "--ledger", str(led_path),
            "--source", f"src-cli={src_path}",
            "--requirement-id", rid,
            "--compilation-id", "cli-walk0",
            "--policy", "explicit_rgba",
            "--output-dir", str(out_dir),
        ]
        if RUST_ORACLE_BIN.is_file():
            cli_args.extend(["--oracle", str(RUST_ORACLE_BIN)])
        rc_comp = cli_main(cli_args)
        self.assertEqual(rc_comp, 0)

        manifest_file = out_dir / "compilation-manifest.json"
        self.assertTrue(manifest_file.is_file())
        manifest_data = json.loads(manifest_file.read_text())
        self.assertEqual(manifest_data["id"], "cli-walk0")
        self.assertEqual(manifest_data["verification"]["decode_after_write"], "PASS")
        self.assertEqual(manifest_data["verification"]["native_korangar"], "UNVERIFIED")
        # Original files untouched
        self.assertEqual(act_path.read_bytes(), self.act_bytes)
        self.assertEqual(spr_path.read_bytes(), self.spr_bytes)

    def test_13_http_service_compile_plan_and_compile_endpoints(self):
        projects_dir = self.root / "projects"
        server = create_server(projects_dir, host="127.0.0.1", port=0)
        port = server.actual_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            def req_http(method: str, path: str, body: dict | None = None):
                url = f"http://127.0.0.1:{port}{path}"
                data = json.dumps(body).encode("utf-8") if body is not None else None
                headers = {
                    "Host": f"127.0.0.1:{port}",
                    "Origin": f"http://127.0.0.1:{port}",
                    "X-CSRF-Token": server.security.csrf_token,
                }
                if body is not None:
                    headers["Content-Type"] = "application/json"
                r = urllib.request.Request(url, data=data, headers=headers, method=method)
                try:
                    with urllib.request.urlopen(r) as resp:
                        return resp.status, json.loads(resp.read().decode("utf-8"))
                except urllib.error.HTTPError as exc:
                    try:
                        return exc.code, json.loads(exc.read().decode("utf-8"))
                    finally:
                        exc.close()

            pid = "http-compile-proj"
            create_project(projects_dir, pid, "HTTP Compile Project", "monster", "monster")

            # 1. Import monster ACT/SPR pair
            st, res = req_http(
                "POST",
                f"/api/projects/{pid}/import-pair",
                {
                    "expected_revision": 1,
                    "id": "monster-base",
                    "part": "body",
                    "act_base64": base64.b64encode(self.act_bytes).decode("ascii"),
                    "spr_base64": base64.b64encode(self.spr_bytes).decode("ascii"),
                },
            )
            self.assertEqual(st, 200)
            inv = res["project"]["resources"][0]["inventory"]
            inv_ref = {
                "part": "body",
                "canonical_sha256": inv["canonical_sha256"],
                "act_sha256": inv["sources"]["act"]["sha256"],
                "spr_sha256": inv["sources"]["spr"]["sha256"],
            }

            # 2. Declare target with Walk view 0..7 explicit single-layer topology
            target_doc = {
                "schema": "rsf.target/v2",
                "id": "monster-walk-target",
                "revision": 1,
                "previous_sha256": None,
                "scope": "scoped",
                "parts": ["body"],
                "compatibility": {"status": "UNVERIFIED", "declarations": []},
                "actions": [
                    {
                        "id": act_name,
                        "requirement": "REQUIRED" if act_name == "Walk" else "OUT_OF_SCOPE",
                        "parts": [
                            {
                                "part": "body",
                                "views": [
                                    {
                                        "view": v,
                                        "frame_count": 4 if v == 0 else 1,
                                        "topology": {"kind": "explicit", "layers": ["body"]},
                                    }
                                    for v in range(8)
                                ],
                            }
                        ]
                        if act_name == "Walk"
                        else [],
                    }
                    for act_name in ("Idle", "Walk", "Attack", "Hurt", "Die")
                ],
            }
            st, res = req_http("POST", f"/api/projects/{pid}/target", {"expected_revision": 2, "target": target_doc})
            self.assertEqual(st, 200)
            http_reqs = res["requirements"]

            # 3. Stage a replacement PNG and assign to Walk view 0 frame 0 layer 0
            png_bytes = _make_png(6, 6, (10, 220, 90, 255), gradient=True)
            png_sha = digest(png_bytes)
            st, res = req_http(
                "POST",
                f"/api/projects/{pid}/stage-png",
                {
                    "expected_revision": 3,
                    "filename": "walk0.png",
                    "data_base64": base64.b64encode(png_bytes).decode("ascii"),
                },
            )
            self.assertEqual(st, 200)

            rid = _find_layer_id(http_reqs, "Walk", 0, 0, 0)
            st, res = req_http(
                "POST",
                f"/api/projects/{pid}/assign",
                {
                    "expected_revision": 4,
                    "mappings": [
                        {
                            "requirement_id": rid,
                            "kind": "DIRECT_SOURCE",
                            "source": f"blob-{png_sha}",
                            "source_revision": 1,
                            "recipe": [],
                        }
                    ],
                },
            )
            self.assertEqual(st, 200)

            # 4. Before approval, compile-plan reports blocker UNAPPROVED_REPLACEMENT_ARTWORK
            st, plan_unapproved = req_http(
                "POST",
                f"/api/projects/{pid}/compile-plan",
                {"expected_revision": 5, "resource_id": "monster-base"},
            )
            self.assertEqual(st, 200)
            self.assertFalse(plan_unapproved["ready_to_compile"])
            self.assertTrue(any("UNAPPROVED_REPLACEMENT_ARTWORK" in b for b in plan_unapproved["blockers"]))

            # 5. Approve the assignment via review-proposal + review
            st, prop = req_http(
                "POST",
                f"/api/projects/{pid}/review-proposal",
                {"expected_revision": 5, "requirements": [rid]},
            )
            self.assertEqual(st, 200)
            st, rev = req_http(
                "POST",
                f"/api/projects/{pid}/review",
                {"expected_revision": 5, "decision": "APPROVED", "proposal": prop["proposal"]},
            )
            self.assertEqual(st, 200)

            # 6. Now compile-plan is READY!
            st, plan_ready = req_http(
                "POST",
                f"/api/projects/{pid}/compile-plan",
                {"expected_revision": 6, "resource_id": "monster-base", "replacement_policy": "explicit_rgba"},
            )
            self.assertEqual(st, 200)
            self.assertTrue(plan_ready["ready_to_compile"])

            # 7. Execute compile and register candidate resource 'monster-compiled'
            st, comp_res = req_http(
                "POST",
                f"/api/projects/{pid}/compile",
                {
                    "expected_revision": 6,
                    "compilation_id": "walk0-compile",
                    "replacement_policy": "explicit_rgba",
                    "resource_id": "monster-base",
                    "register_resource_id": "monster-compiled",
                    "oracle_executable": str(RUST_ORACLE_BIN) if RUST_ORACLE_BIN.is_file() else None,
                },
            )
            self.assertEqual(st, 200)
            self.assertEqual(comp_res["operation"], "compile")
            cm = comp_res["compilation"]
            self.assertEqual(cm["id"], "walk0-compile")
            self.assertFalse(cm["status"]["export_ready"])
            self.assertTrue(cm["status"]["experimental_bounded_output"])
            self.assertEqual(cm["verification"]["native_korangar"], "UNVERIFIED")

            # 8. GET /api/projects/{pid}/compilations returns the persisted compilation manifest
            st, comps_list = req_http("GET", f"/api/projects/{pid}/compilations")
            self.assertEqual(st, 200)
            self.assertEqual(len(comps_list["compilations"]), 1)
            self.assertEqual(comps_list["compilations"][0]["id"], "walk0-compile")

            # 9. PUT /api/projects/{pid} rejects tampering with compilations
            manifest = load_project(projects_dir, pid, verify_blobs=False)
            tampered = copy.deepcopy(manifest)
            tampered["compilations"] = []
            st, err = req_http("PUT", f"/api/projects/{pid}", {"expected_revision": manifest["revision"], "project": tampered})
            self.assertEqual(st, 422)
            self.assertIn("Use validated compile operations to manage compilations", err["error"]["message"])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

"""Audited private fixture tests for RSF-23: Deterministic ACT/SPR Writer & Compiler.

Tests Male Novice bounded Walk replacement and Orc Skeleton multilayer compilation
with independent Rust oracle verification on private assets.
"""

from __future__ import annotations

import io
from pathlib import Path
import sys
import unittest

from PIL import Image

_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.compiler import compile_resources
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, load_target, reference
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.ledger import assignment_binding, load_ledger, resolve_ledger
from ro_sprite_forge.core.profiles import get_profile
from ro_sprite_forge.core.topology import resolve_topology
from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.formats.spr import read_spr
from test_audited_fixtures import AUDITED_HASHES, find_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
RUST_ORACLE_BIN = REPO_ROOT / "tools" / "rust-oracle" / "target" / "debug" / "rsf-rust-oracle"


def _make_test_png(width: int, height: int, rgba: tuple[int, int, int, int] = (255, 0, 128, 255)) -> bytes:
    im = Image.new("RGBA", (width, height), rgba)
    for y in range(height):
        for x in range(width):
            im.putpixel((x, y), ((rgba[0] + x * 7) % 256, (rgba[1] + y * 13) % 256, rgba[2], 255))
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    return bio.getvalue()


class PrivateCompilerFixturesTests(unittest.TestCase):
    def resource(self, name: str) -> bytes:
        p = find_fixture(name)
        if p is None:
            self.skipTest(f"Private fixture unavailable: {name}")
        raw = p.read_bytes()
        self.assertEqual(digest(raw), AUDITED_HASHES[name], f"Fixture {name} corrupted")
        return raw

    def test_novice_bounded_walk_replacement_with_oracle_and_head_preservation(self):
        """Male Novice body (104 slots, 456 frames) + head (15 sprites).
        Replace Walk view 0 frame 0 layer 0:
        - Exactly 1 modified slot (slot 8), 103 untouched action slots!
        - Head resources preserved 100% byte-for-byte identical.
        - Verified with independent Rust oracle (PASS).
        - Classic retained art explicitly outside new-art completeness.
        """
        body_act = self.resource("novice_body_act")
        body_spr = self.resource("novice_body_spr")
        head_act = self.resource("novice_head_act")
        head_spr = self.resource("novice_head_spr")

        profile = frozen_runtime_profile("player")
        inv_body = inventory(body_act, body_spr, actor="novice-male", part="body", profile=get_profile("player"))
        inv_head = inventory(head_act, head_spr, actor="novice-male", part="head", profile=get_profile("player"))

        actor = load_actor({
            "schema": "rsf.actor/v1",
            "id": "novice-male",
            "revision": 1,
            "previous_sha256": None,
            "category": "player",
            "parts": ["body", "head"],
            "resources": [
                {
                    "part": "body",
                    "inventory_sha256": inv_body["canonical_sha256"],
                    "act_sha256": inv_body["sources"]["act"]["sha256"],
                    "spr_sha256": inv_body["sources"]["spr"]["sha256"],
                },
                {
                    "part": "head",
                    "inventory_sha256": inv_head["canonical_sha256"],
                    "act_sha256": inv_head["sources"]["act"]["sha256"],
                    "spr_sha256": inv_head["sources"]["spr"]["sha256"],
                },
            ],
            "runtime_profile": reference(profile),
            "gameplay_job": "novice",
            "visual": {"body_family": "novice", "sex": "male", "body_variant": "default", "costume": "default"},
            "action_profile": "classic-novice",
            "compatibility": {"status": "UNVERIFIED", "declarations": []},
        })

        # Target: Walk action (group 1, slots 8..15) with inherited body topology
        target = load_target(
            {
                "schema": "rsf.target/v2",
                "id": "novice-walk-target",
                "revision": 1,
                "previous_sha256": None,
                "actor": reference(actor),
                "runtime_profile": reference(profile),
                "scope": "scoped",
                "parts": ["body"],
                "compatibility": {"status": "UNVERIFIED", "declarations": []},
                "actions": [
                    {
                        "id": "Walk",
                        "requirement": "REQUIRED",
                        "parts": [
                            {
                                "part": "body",
                                "views": [
                                    {
                                        "view": v,
                                        "frame_count": 8,
                                        "topology": {
                                            "kind": "inherited",
                                            "inventory_sha256": inv_body["canonical_sha256"],
                                            "slot": 8 + v,
                                        },
                                    }
                                    for v in range(8)
                                ],
                            }
                        ],
                    }
                ]
                + [
                    {"id": act_name, "requirement": "OUT_OF_SCOPE", "parts": []}
                    for act_name in (
                        "Idle",
                        "Sit",
                        "PickUp",
                        "Attack",
                        "ReadyFight",
                        "Hurt",
                        "Freeze",
                        "Die",
                        "Freeze2",
                        "Attack2",
                        "Attack3",
                        "Special",
                    )
                ],
            },
            actor=actor,
            profile=profile,
        )
        reqs = resolve_topology(target, actor=actor, profile=profile, inventories=(inv_body, inv_head))

        # Find Walk view 0 frame 0 layer 0 requirement
        walk_v0_f0 = next(
            l["id"]
            for l in reqs["layers"]
            if l["part"] == "body" and l["action"] == "Walk" and l["view"] == 0 and l["frame"] == 0
        )

        replacement_png = _make_test_png(24, 32, (10, 180, 220, 255))
        png_sha = digest(replacement_png)
        sources = {"walk-f0-art": replacement_png}

        # Build ledger with approved operator review
        layer_obj = next(l for l in reqs["layers"] if l["id"] == walk_v0_f0)
        base_ledger = {
            "schema": "rsf.assignment-ledger/v1",
            "id": "novice-ledger",
            "revision": 1,
            "previous_sha256": None,
            "target": reqs["target"],
            "requirements_sha256": reqs["canonical_sha256"],
            "sources": [
                {
                    "id": "walk-f0-art",
                    "revision": 1,
                    "sha256": png_sha,
                    "kind": "IMAGE",
                    "origin": "AUTHORED",
                    "external_ref": "walk-f0.png",
                    "image": None,
                    "provenance": None,
                }
            ],
            "assignments": [
                {
                    "id": "assignment-walk0",
                    "revision": 1,
                    "requirement_id": walk_v0_f0,
                    "binding": assignment_binding(layer_obj),
                    "kind": "DIRECT_SOURCE",
                    "source": {"id": "walk-f0-art", "revision": 1},
                    "dependency": None,
                    "recipe": [],
                    "review": None,
                }
            ],
            "attachments": [],
        }
        loaded = load_ledger(base_ledger, requirements=reqs)
        resolved_unrev = resolve_ledger(loaded, requirements=reqs, source_bytes=sources)
        basis = resolved_unrev["assignments"][0]["composition_sha256"]
        base_ledger["assignments"][0]["review"] = {
            "state": "APPROVED",
            "authority": "OPERATOR",
            "operator": "test-operator",
            "evidence_sha256": "f" * 64,
            "basis_sha256": basis,
            "policy": "VISUAL_DECISION",
        }

        oracle_path = RUST_ORACLE_BIN if RUST_ORACLE_BIN.is_file() else None
        res = compile_resources(
            body_act,
            body_spr,
            requirements=reqs,
            ledger=base_ledger,
            source_bytes=sources,
            replacement_requirement_ids=[walk_v0_f0],
            compilation_id="novice-walk-compile",
            part="body",
            compilation_mode="bounded_replacement",
            replacement_policy="explicit_rgba",
            head_act_bytes=head_act,
            head_spr_bytes=head_spr,
            oracle_executable=oracle_path,
        )

        manifest = res["manifest"]
        self.assertEqual(manifest["preservation_summary"]["total_action_slots"], 104)
        self.assertEqual(manifest["preservation_summary"]["modified_action_slots"], [8])
        self.assertEqual(manifest["preservation_summary"]["untouched_action_slots"], 103)
        self.assertEqual(manifest["preservation_summary"]["modified_clips"], 1)
        self.assertTrue(manifest["preservation_summary"]["head_resources_preserved_unchanged"])
        self.assertTrue(manifest["preservation_summary"]["classic_retained_outside_completeness"])
        self.assertFalse(manifest["status"]["production_authorized"])
        self.assertFalse(manifest["status"]["export_ready"])
        self.assertTrue(manifest["status"]["experimental_bounded_output"])
        self.assertEqual(manifest["verification"]["decode_after_write"], "PASS")
        self.assertEqual(manifest["verification"]["metadata_preservation"], "PASS")
        self.assertEqual(manifest["verification"]["targeted_pixel_verification"], "PASS")
        self.assertEqual(manifest["verification"]["shared_reference_isolation"], "PASS")
        self.assertEqual(manifest["verification"]["native_korangar"], "UNVERIFIED")
        if oracle_path:
            self.assertEqual(manifest["verification"]["rust_oracle"], "PASS")

        # Head resources returned byte-for-byte identical
        self.assertEqual(res["head_act_bytes"], head_act)
        self.assertEqual(res["head_spr_bytes"], head_spr)

        # Output body ACT has unmodified slot 0 (Idle) identical to original body ACT
        dec_act = read_act(res["act_bytes"])
        orig_act = read_act(body_act)
        self.assertEqual(dec_act["actions"][0], orig_act["actions"][0])
        self.assertEqual(dec_act["delays"], orig_act["delays"])
        self.assertEqual(dec_act["events"], orig_act["events"])
        self.assertEqual(dec_act["reserved"], orig_act["reserved"])

        # Output SPR has 110 original indexed images intact and 1 new RGBA image appended in Pool 1
        dec_spr = read_spr(res["spr_bytes"])
        self.assertEqual(dec_spr.indexed_count, 110)
        self.assertEqual(dec_spr.rgba_count, 1)

    def test_orc_skeleton_multilayer_compilation_with_oracle(self):
        """Orc Skeleton (40 slots, 512 motions, 1,776 visible layers, 12-layer Death frame).
        Replace Walk view 0 frame 0 layer 0:
        - 1 modified slot, 39 untouched slots.
        - Multilayer Death action (slot 32) retained with all layers intact without flattening.
        - Verified with independent Rust oracle (PASS).
        """
        orc_act = self.resource("orc_skeleton_act")
        orc_spr = self.resource("orc_skeleton_spr")

        profile = frozen_runtime_profile("monster")
        inv_orc = inventory(orc_act, orc_spr, actor="orc-skeleton", part="body", profile=get_profile("monster"))

        actor = load_actor({
            "schema": "rsf.actor/v1",
            "id": "orc-skeleton",
            "revision": 1,
            "previous_sha256": None,
            "category": "monster",
            "parts": ["body"],
            "resources": [
                {
                    "part": "body",
                    "inventory_sha256": inv_orc["canonical_sha256"],
                    "act_sha256": inv_orc["sources"]["act"]["sha256"],
                    "spr_sha256": inv_orc["sources"]["spr"]["sha256"],
                }
            ],
            "runtime_profile": reference(profile),
            "gameplay_job": "orc_skeleton",
            "visual": {"body_family": "skeleton", "sex": None, "body_variant": "default", "costume": "default"},
            "action_profile": "monster-orc",
            "compatibility": {"status": "UNVERIFIED", "declarations": []},
        })

        target = load_target(
            {
                "schema": "rsf.target/v2",
                "id": "orc-walk-target",
                "revision": 1,
                "previous_sha256": None,
                "actor": reference(actor),
                "runtime_profile": reference(profile),
                "scope": "scoped",
                "parts": ["body"],
                "compatibility": {"status": "UNVERIFIED", "declarations": []},
                "actions": [
                    {
                        "id": "Walk",
                        "requirement": "REQUIRED",
                        "parts": [
                            {
                                "part": "body",
                                "views": [
                                    {
                                        "view": v,
                                        "frame_count": len(inv_orc["actions"][8 + v]["frames"]),
                                        "topology": {
                                            "kind": "inherited",
                                            "inventory_sha256": inv_orc["canonical_sha256"],
                                            "slot": 8 + v,
                                        },
                                    }
                                    for v in range(8)
                                ],
                            }
                        ],
                    },
                    {"id": "Idle", "requirement": "OUT_OF_SCOPE", "parts": []},
                    {"id": "Attack", "requirement": "OUT_OF_SCOPE", "parts": []},
                    {"id": "Hurt", "requirement": "OUT_OF_SCOPE", "parts": []},
                    {"id": "Die", "requirement": "OUT_OF_SCOPE", "parts": []},
                ],
            },
            actor=actor,
            profile=profile,
        )
        reqs = resolve_topology(target, actor=actor, profile=profile, inventories=(inv_orc,))

        walk_v0_f0 = next(
            l["id"]
            for l in reqs["layers"]
            if l["part"] == "body" and l["action"] == "Walk" and l["view"] == 0 and l["frame"] == 0 and l["ordinal"] == 0
        )
        replacement_png = _make_test_png(32, 32, (180, 20, 20, 255))
        png_sha = digest(replacement_png)
        sources = {"orc-walk0-art": replacement_png}

        layer_obj = next(l for l in reqs["layers"] if l["id"] == walk_v0_f0)
        base_ledger = {
            "schema": "rsf.assignment-ledger/v1",
            "id": "orc-ledger",
            "revision": 1,
            "previous_sha256": None,
            "target": reqs["target"],
            "requirements_sha256": reqs["canonical_sha256"],
            "sources": [
                {
                    "id": "orc-walk0-art",
                    "revision": 1,
                    "sha256": png_sha,
                    "kind": "IMAGE",
                    "origin": "AUTHORED",
                    "external_ref": "orc-walk0.png",
                    "image": None,
                    "provenance": None,
                }
            ],
            "assignments": [
                {
                    "id": "assignment-orc-walk0",
                    "revision": 1,
                    "requirement_id": walk_v0_f0,
                    "binding": assignment_binding(layer_obj),
                    "kind": "DIRECT_SOURCE",
                    "source": {"id": "orc-walk0-art", "revision": 1},
                    "dependency": None,
                    "recipe": [],
                    "review": None,
                }
            ],
            "attachments": [],
        }
        loaded = load_ledger(base_ledger, requirements=reqs)
        resolved_unrev = resolve_ledger(loaded, requirements=reqs, source_bytes=sources)
        basis = resolved_unrev["assignments"][0]["composition_sha256"]
        base_ledger["assignments"][0]["review"] = {
            "state": "APPROVED",
            "authority": "OPERATOR",
            "operator": "test-operator",
            "evidence_sha256": "e" * 64,
            "basis_sha256": basis,
            "policy": "VISUAL_DECISION",
        }

        oracle_path = RUST_ORACLE_BIN if RUST_ORACLE_BIN.is_file() else None
        res = compile_resources(
            orc_act,
            orc_spr,
            requirements=reqs,
            ledger=base_ledger,
            source_bytes=sources,
            replacement_requirement_ids=[walk_v0_f0],
            compilation_id="orc-walk-compile",
            part="body",
            compilation_mode="bounded_replacement",
            replacement_policy="explicit_rgba",
            oracle_executable=oracle_path,
        )

        manifest = res["manifest"]
        self.assertEqual(manifest["preservation_summary"]["total_action_slots"], 40)
        self.assertEqual(manifest["preservation_summary"]["modified_action_slots"], [8])
        self.assertEqual(manifest["preservation_summary"]["untouched_action_slots"], 39)
        self.assertEqual(manifest["verification"]["decode_after_write"], "PASS")
        if oracle_path:
            self.assertEqual(manifest["verification"]["rust_oracle"], "PASS")

        # Crucial check: verify Death slot (slot 32) and its 12-layer frame are untouched without flattening
        dec_act = read_act(res["act_bytes"])
        orig_act = read_act(orc_act)
        self.assertEqual(dec_act["actions"][32], orig_act["actions"][32])
        # Frame 21 in action 32 has exactly 12 clips
        self.assertEqual(len(dec_act["actions"][32][21]["clips"]), 12)
        self.assertEqual(dec_act["actions"][32][21]["clips"], orig_act["actions"][32][21]["clips"])


if __name__ == "__main__":
    unittest.main()

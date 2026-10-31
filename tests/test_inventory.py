"""Synthetic contract tests: identities, counts, semantics and finite work orders."""

import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.inventory import CONTENT_DOMAIN, inventory
from ro_sprite_forge.core.profiles import get_profile, REVISION
from ro_sprite_forge.core.requirements import requirements
from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.report_io import publish, read_json
from test_codecs import make_synthetic_act, make_synthetic_spr


def resources(*, slots=16, frames=2, layers=2):
    return (make_synthetic_act(action_count=slots, motions_per_action=frames, clips_per_motion=layers),
            make_synthetic_spr([(1, 1, bytes([i + 1])) for i in range(max(2, layers))]))


def target(*, layers=None, scope="scoped", count=6):
    views = [{"view": view} for view in range(8)]
    for view in views:
        if count is not None:
            view["frame_count"] = count
        if layers is not None:
            view["topology"] = {"kind": "explicit", "layers": layers}
    return {"schema": "rsf.target/v1", "actor": "replacement", "part": "body", "scope": scope,
            "actions": [{"action": "Walk", "requirement": "required", "views": views}]}


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.act, self.spr = resources()
        self.profile = get_profile("player")
        self.observed = inventory(self.act, self.spr, actor="synthetic", profile=self.profile)

    def test_multilayer_counts_order_metadata(self):
        s = self.observed["summary"]
        self.assertEqual((s["action_slots"], s["frame_occurrences"], s["layer_occurrences"], s["visible_layer_references"]), (16, 32, 64, 64))
        a = self.observed["actions"][8]
        self.assertEqual((a["semantic_action"], a["mapped_view"], a["raw_delay"]), ("Walk", 0, 4.0))
        f = a["frames"][0]
        self.assertEqual(f["bounds_raw"], list(range(1, 9)))
        self.assertEqual(f["anchors"], [{"opaque": 0, "x": 5, "y": -10, "attribute": 0}])
        self.assertEqual(f["event_index"], 0)
        self.assertEqual([x["raw"]["sprite"] for x in f["layers"]], [0, 1])
        self.assertEqual(f["layers"][1]["raw"]["mirror"], 1)
        self.assertEqual(f["layers"][1]["raw"]["color"], 0xFFFFFFFF)
        self.assertEqual(len(self.observed["raw_metadata"]["events_hex"][0]), 80)

    def test_sentinel_layers_are_not_visible_references(self):
        act = read_act(self.act)
        act["actions"][0][0]["clips"][0]["sprite"] = -1
        result = inventory(write_act(act), self.spr)
        self.assertEqual(result["summary"]["layer_occurrences"], 64)
        self.assertEqual(result["summary"]["visible_layer_references"], 63)
        self.assertIsNone(result["actions"][0]["frames"][0]["layers"][0]["image_id"])

    def test_pools_identity_equivalence_reuse_unused(self):
        # Indexed palette entry 1 decodes to this exact RGBA value.
        rgba = bytes((1, 254, 2, 255))
        spr = make_synthetic_spr([(1, 1, b"\1"), (1, 1, b"\1"), (1, 1, b"\2")], [(1, 1, rgba)])
        act = read_act(make_synthetic_act(action_count=1, motions_per_action=1, clips_per_motion=3))
        clips = act["actions"][0][0]["clips"]
        clips[1]["sprite"] = 0  # repeated identity
        clips[2].update(pool=1, sprite=0)  # equal content, different pool and identity
        report = inventory(write_act(act), spr)
        s = report["summary"]
        self.assertEqual((s["stored_images"], s["referenced_images"], s["unused_images"]), (4, 2, 2))
        self.assertEqual((s["distinct_stored_contents"], s["distinct_referenced_contents"]), (2, 1))
        self.assertEqual([i["reference_count"] for i in report["images"]], [2, 0, 0, 1])
        expected = digest(CONTENT_DOMAIN + struct.pack("<II", 1, 1) + rgba)
        self.assertEqual(report["images"][0]["decoded_content_sha256"], expected)
        self.assertNotEqual(report["images"][0]["id"], report["images"][3]["id"])
        self.assertEqual(len(report["content_classes"][0]["image_ids"]) + len(report["content_classes"][1]["image_ids"]), 4)

    def test_content_dimensions_and_alpha_are_significant(self):
        spr = make_synthetic_spr([], [(1, 2, b"\0" * 8), (2, 1, b"\0" * 8),
                                     (1, 2, b"\1\0\0\0" + b"\0" * 4)])
        act = make_synthetic_act(clips_per_motion=0)
        self.assertEqual(inventory(act, spr)["summary"]["distinct_stored_contents"], 3)

    def test_palette_kept_separate_from_content(self):
        palette = bytearray(1024)
        spr = make_synthetic_spr([(1, 1, b"\0")], palette=bytes(palette))
        palette[:4] = b"\xff\x11\x22\x33"
        other = make_synthetic_spr([(1, 1, b"\0")], palette=bytes(palette))
        act = make_synthetic_act(clips_per_motion=1)
        first, second = inventory(act, spr), inventory(act, other)
        self.assertEqual(first["images"][0]["decoded_content_sha256"], second["images"][0]["decoded_content_sha256"])
        self.assertNotEqual(first["raw_metadata"]["palette_sha256"], second["raw_metadata"]["palette_sha256"])

    def test_stable_ids_source_identity_and_parts(self):
        repeated = inventory(self.act, self.spr, actor="synthetic", profile=self.profile)
        self.assertEqual(canonical_bytes(self.observed), canonical_bytes(repeated))
        self.assertEqual(self.observed["sources"]["act"]["sha256"], digest(self.act))
        frame_id = self.observed["actions"][8]["frames"][1]["layers"][1]["id"]
        self.assertEqual(frame_id, "synthetic/korangar-player-v1/body/action/Walk/slot8/view0/frame1/layer1")
        head = inventory(self.act, self.spr, actor="synthetic", part="head", profile=self.profile)
        self.assertNotEqual(frame_id, head["actions"][8]["frames"][1]["layers"][1]["id"])

    def test_unknown_semantics_do_not_invent_views(self):
        observed = inventory(self.act, self.spr)
        self.assertIsNone(observed["actions"][8]["semantic_action"])
        self.assertIsNone(observed["actions"][8]["mapped_view"])
        self.assertEqual(observed["actions"][8]["slot"], 8)
        extra = inventory(*resources(slots=105), profile=self.profile)
        self.assertIsNone(extra["actions"][104]["semantic_action"])

    def test_malformed_reference_delay_event_and_scale(self):
        mutations = [lambda a: a["actions"][0][0]["clips"][0].update(sprite=50),
                     lambda a: a["actions"][0][0]["clips"][0].update(pool=3),
                     lambda a: a["actions"][0][0]["clips"][0].update(sprite=-2),
                     lambda a: a["actions"][0][0]["clips"][0].update(scale_x=float("nan")),
                     lambda a: a["actions"][0][0].update(event=999),
                     lambda a: a["delays"].__setitem__(0, float("inf"))]
        for mutate in mutations:
            a = read_act(self.act)
            mutate(a)
            with self.subTest(mutate=mutate), self.assertRaises(ForgeError) as caught:
                inventory(write_act(a), self.spr)
            self.assertEqual(caught.exception.code, ErrorCode.INVALID_INPUT)

    def test_core_modules_need_no_ui_or_pillow(self):
        code = "import sys; from ro_sprite_forge.core import inventory, profiles, requirements; assert not any(x in sys.modules for x in ('PIL','argparse','subprocess','socket','ro_sprite_forge.cli'))"
        result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class ProfileTests(unittest.TestCase):
    def test_part_relationships_are_category_specific(self):
        player = get_profile("player")
        self.assertEqual(player["parts"]["order"], ["body", "head"])
        self.assertIn("body anchor[0] minus head anchor[0]", player["parts"]["head_registration"])
        for category in ("npc", "monster"):
            profile = get_profile(category)
            self.assertEqual(profile["parts"]["order"], ["body"])
            self.assertIsNone(profile["parts"]["head_registration"])
        self.assertIsNone(get_profile("unverified")["parts"])

    def test_pinned_categories_mapping_and_reachability(self):
        player, monster, npc = [get_profile(c) for c in ("player", "monster", "npc")]
        self.assertEqual([len(p["actions"]) for p in (player, monster, npc)], [13, 5, 5])
        self.assertEqual(player["revision"], REVISION)
        self.assertNotEqual(player["canonical_sha256"], monster["canonical_sha256"])
        self.assertNotEqual(npc["canonical_sha256"], monster["canonical_sha256"])
        self.assertEqual(player["actions"][10]["selection_path"], "UNVERIFIED")
        self.assertEqual(player["actions"][11]["action"], "Attack3")
        self.assertEqual(monster["actions"][2]["action"], "Attack1")
        self.assertEqual(monster["native_evidence"], "UNVERIFIED")
        self.assertIn("%", monster["resolution"]["resolved_slot"])
        self.assertEqual(len(player["source_evidence"]), 4)

    def test_frozen_record_cannot_silently_change(self):
        p = get_profile("player")
        p["actions"][0]["action"] = "Invented"
        with self.assertRaises(ForgeError):
            inventory(*resources(), profile=p)
        self.assertEqual(get_profile("player")["actions"][0]["action"], "Idle")


class RequirementsTests(unittest.TestCase):
    def setUp(self):
        self.profile = get_profile("player")
        self.observed = inventory(*resources(frames=6), profile=self.profile)

    def plan(self, declared):
        return requirements(self.observed, self.profile, declared)

    def test_eight_by_six_one_and_two_layer_work_orders(self):
        for roles, expected in ((["body"], 48), (["body", "head"], 96)):
            report = self.plan(target(layers=roles))
            self.assertEqual(report["totals"]["required_frames"], 48)
            self.assertEqual(report["totals"]["required_layers_known"], expected)
            self.assertEqual(report["status"]["work_order"], "EXACT")
            self.assertFalse(report["status"]["full_profile_specified"])
            self.assertEqual(report["status"]["artwork_coverage"], "UNASSIGNED")
            self.assertEqual(report["status"]["production_readiness"], "NOT_READY")
            self.assertEqual(report["status"]["native_evidence"], "UNVERIFIED")

    def test_missing_frame_counts_and_topology_are_separate(self):
        for declared, codes in ((target(), {"UNDERSPECIFIED_LAYER_TOPOLOGY"}),
                                (target(layers=["body"], count=None), {"UNDERSPECIFIED_FRAME_COUNT"}),
                                (target(count=None), {"UNDERSPECIFIED_FRAME_COUNT", "UNDERSPECIFIED_LAYER_TOPOLOGY"})):
            report = self.plan(declared)
            self.assertEqual({d["code"] for d in report["diagnostics"]}, codes)
            self.assertFalse(report["status"]["declared_scope_specified"])
            self.assertEqual(report["totals"]["required_layers_known"], 0)
            self.assertFalse(any(w["frames"] for w in report["work"]))

    def test_explicit_inheritance_records_hash_and_slot(self):
        declared = target()
        for view in declared["actions"][0]["views"]:
            view["topology"] = {"kind": "inherited", "inventory_sha256": self.observed["canonical_sha256"], "slot": 8 + view["view"]}
        report = self.plan(declared)
        self.assertEqual(report["totals"]["required_layers_known"], 96)
        self.assertEqual(report["work"][0]["topology"]["inventory_sha256"], self.observed["canonical_sha256"])
        declared["actions"][0]["views"][0]["topology"]["slot"] = 0
        with self.assertRaises(ForgeError):
            self.plan(declared)

    def test_per_frame_ordered_topology(self):
        declared = target()
        for view in declared["actions"][0]["views"]:
            view["topology"] = {"kind": "explicit", "frames": [["body", "weapon"], ["body"], [], ["body"], ["head", "body"], ["body"]]}
        report = self.plan(declared)
        self.assertEqual(report["totals"]["required_layers_known"], 56)
        self.assertEqual([l["role"] for l in report["work"][0]["frames"][4]["layers"]], ["head", "body"])

    def test_scoped_full_and_optional_out_of_scope(self):
        declared = target(layers=["body"], scope="full")
        self.assertFalse(self.plan(declared)["status"]["full_profile_specified"])
        for entry in self.profile["actions"]:
            if entry["action"] != "Walk":
                declaration = copy.deepcopy(declared["actions"][0])
                declaration["action"] = entry["action"]
                declared["actions"].append(declaration)
        self.assertTrue(self.plan(declared)["status"]["full_profile_specified"])
        declared["actions"][0]["requirement"] = "optional"
        self.assertEqual(self.plan(declared)["totals"]["optional_frames"], 48)
        declared["actions"][0].update(requirement="out_of_scope", views=[])
        self.assertFalse(self.plan(declared)["status"]["full_profile_specified"])

    def test_unknown_semantics_are_provisional_runtime_not_guessed(self):
        declared = target(layers=["body"])
        declared["actions"][0]["action"] = "CustomAction"
        report = self.plan(declared)
        self.assertIsNone(report["work"][0]["slot"])
        self.assertEqual(report["work"][0]["runtime_mapping"], "UNVERIFIED")
        self.assertEqual(report["work"][0]["observed_resource"], "ABSENT")
        self.assertEqual(report["status"]["native_evidence"], "UNVERIFIED")

    def test_order_independent_canonical_target_and_output(self):
        declared = target(layers=["body"])
        first = self.plan(declared)
        declared["actions"][0]["views"].reverse()
        self.assertEqual(canonical_bytes(first), canonical_bytes(self.plan(declared)))

    def test_contract_rejects_ambiguous_or_unbounded_input(self):
        mutations = [lambda t: t.update(scope="all"),
                     lambda t: t["actions"].append(copy.deepcopy(t["actions"][0])),
                     lambda t: t["actions"][0]["views"][0].update(frame_count=True),
                     lambda t: t["actions"][0]["views"][0].update(frame_count=4097),
                     lambda t: t["actions"][0]["views"][0].update(topology={"kind": "explicit", "layers": ["body", "body"]}),
                     lambda t: t.update(typo=True)]
        for mutate in mutations:
            declared = target(layers=["body"])
            mutate(declared)
            with self.subTest(mutate=mutate), self.assertRaises(ForgeError):
                self.plan(declared)

    def test_hash_and_profile_mismatch_rejected(self):
        bad = copy.deepcopy(self.observed)
        bad["summary"]["frame_occurrences"] = 999
        with self.assertRaises(ForgeError):
            requirements(bad, self.profile, target())
        with self.assertRaises(ForgeError):
            requirements(self.observed, get_profile("monster"), target())

    def test_empty_views_are_provisional_not_complete(self):
        declared = target()
        declared["actions"][0]["views"] = []
        report = self.plan(declared)
        self.assertEqual(report["status"]["work_order"], "UNDERSPECIFIED")
        self.assertEqual({d["code"] for d in report["diagnostics"]}, {"UNDERSPECIFIED_FRAME_COUNT", "UNDERSPECIFIED_LAYER_TOPOLOGY"})
        declared["actions"][0]["requirement"] = "out_of_scope"
        with self.assertRaises(ForgeError):
            self.plan(declared)


class ReportIOTests(unittest.TestCase):
    def test_strict_json_and_atomic_no_clobber(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "report.json"
            publish(str(path), {"valid": True})
            before = path.read_bytes()
            with self.assertRaises(ForgeError):
                publish(str(path), {"fake": True})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(d).iterdir()), [path])
            for data in (b'{"a":1,"a":2}', b'{"x":NaN}', b'[]', b'\xff'):
                path.write_bytes(data)
                with self.assertRaises(ForgeError):
                    read_json(str(path))

    def test_cli_functional_outputs_are_path_independent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            act, spr = resources()
            for name, data in (("a.act", act), ("a.spr", spr), ("renamed.act", act), ("renamed.spr", spr)):
                (root / name).write_bytes(data)
            def cli(*args):
                p = subprocess.run([sys.executable, "-I", "-m", "ro_sprite_forge", *map(str, args)], cwd=root, capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stdout, "")
            for name, source in (("first.json", "a"), ("second.json", "renamed")):
                cli("inspect", "--act", root / f"{source}.act", "--spr", root / f"{source}.spr", "--json", root / name, "--runtime-profile", "player", "--actor", "synthetic")
            self.assertEqual((root / "first.json").read_bytes(), (root / "second.json").read_bytes())
            (root / "profile.json").write_bytes(canonical_bytes(get_profile("player")))
            (root / "target.json").write_bytes(canonical_bytes(target(layers=["body"])))
            cli("plan", "--inventory", root / "first.json", "--profile", root / "profile.json", "--target", root / "target.json", "--output", root / "work.json")
            report = read_json(str(root / "work.json"))
            self.assertEqual(report["totals"]["required_frames"], 48)
            self.assertEqual(report["status"]["production_readiness"], "NOT_READY")
            self.assertEqual((root / "a.act").read_bytes(), act)
            self.assertEqual((root / "a.spr").read_bytes(), spr)

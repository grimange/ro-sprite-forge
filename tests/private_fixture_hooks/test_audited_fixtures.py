"""Private fixture regression tests for audited male Novice and Orc Skeleton assets.

These tests run only when private reference assets are available at their external,
untracked local paths. No private assets are stored in the repository or shipped in wheels.
"""

import hashlib
import os
from pathlib import Path
import unittest

from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.formats.preview import actor_preview
from ro_sprite_forge.formats.spr import read_spr

AUDITED_HASHES = {
    "novice_body_act": "a82086ba005506a16ee0740ebd1d33c43de8cc4ee1a622ea933ff9e0502c1c77",
    "novice_body_spr": "7f4efe357b0f80e71ba2dcdb93d1c110988b1b8f382e1dbfc722e3a2cf85a533",
    "novice_head_act": "96cb4c7daada65ead29ade650c34da1cba93937d3b360c5468506c3d056219de",
    "novice_head_spr": "dfc548c5cfd9aeb66616c5912df78773c2798834f9412a309a5a2b4f5868ac95",
    "orc_skeleton_act": "31e1e75241bc534422e468ae134892c7b234d66022456b87b0423df5858370e2",
    "orc_skeleton_spr": "a39f864209d63ae75bd62438da61775c510d7c55a78344b3065fb5918a55ce8f",
}


def find_fixture(name: str) -> Path | None:
    env_var = f"RSF_FIXTURE_{name.upper()}"
    if env_var in os.environ and Path(os.environ[env_var]).is_file():
        return Path(os.environ[env_var])

    candidates = {
        "novice_body_act": [
            Path("/home/ra/Documents/Living-world-Ragnarok/ops/local/novice-mature-sprite-pipeline-e1/reference/novice_male_body.act"),
            Path("/tmp/ro-sprite-forge-audit-e1/novice.act"),
        ],
        "novice_body_spr": [
            Path("/home/ra/Documents/Living-world-Ragnarok/ops/local/novice-mature-sprite-pipeline-e1/reference/novice_male_body.spr"),
            Path("/tmp/ro-sprite-forge-audit-e1/novice.spr"),
        ],
        "novice_head_act": [
            Path("/home/ra/Documents/Living-world-Ragnarok/ops/local/novice-mature-sprite-pipeline-e1/reference/novice_male_head.act"),
        ],
        "novice_head_spr": [
            Path("/home/ra/Documents/Living-world-Ragnarok/ops/local/novice-mature-sprite-pipeline-e1/reference/novice_male_head.spr"),
        ],
        "orc_skeleton_act": [
            Path("/tmp/ro-sprite-forge-audit-e1/orc_skeleton.act"),
        ],
        "orc_skeleton_spr": [
            Path("/tmp/ro-sprite-forge-audit-e1/orc_skeleton.spr"),
        ],
    }
    for candidate in candidates.get(name, []):
        if candidate.is_file():
            return candidate
    return None


class AuditedPrivateFixtureTests(unittest.TestCase):
    def test_novice_body_act_and_spr(self):
        act_path = find_fixture("novice_body_act")
        spr_path = find_fixture("novice_body_spr")
        if not act_path or not spr_path:
            self.skipTest("Audited male Novice body fixtures not available")

        act_bytes = act_path.read_bytes()
        self.assertEqual(hashlib.sha256(act_bytes).hexdigest(), AUDITED_HASHES["novice_body_act"])
        act = read_act(act_bytes)
        self.assertEqual(len(act["actions"]), 104)
        self.assertEqual(sum(len(a) for a in act["actions"]), 456)
        self.assertEqual(write_act(act), act_bytes, "Novice body ACT must round-trip byte-for-byte")

        spr_bytes = spr_path.read_bytes()
        self.assertEqual(hashlib.sha256(spr_bytes).hexdigest(), AUDITED_HASHES["novice_body_spr"])
        spr = read_spr(spr_bytes)
        self.assertEqual(spr.indexed_count, 110)
        self.assertEqual(spr.rgba_count, 0)
        self.assertEqual(len(spr.images), 110)

    def test_novice_head_act_and_spr(self):
        act_path = find_fixture("novice_head_act")
        spr_path = find_fixture("novice_head_spr")
        if not act_path or not spr_path:
            self.skipTest("Audited male Novice head fixtures not available")

        act_bytes = act_path.read_bytes()
        self.assertEqual(hashlib.sha256(act_bytes).hexdigest(), AUDITED_HASHES["novice_head_act"])
        act = read_act(act_bytes)
        self.assertEqual(len(act["actions"]), 104)
        self.assertEqual(sum(len(a) for a in act["actions"]), 456)
        self.assertEqual(write_act(act), act_bytes, "Novice head ACT must round-trip byte-for-byte")

        spr_bytes = spr_path.read_bytes()
        self.assertEqual(hashlib.sha256(spr_bytes).hexdigest(), AUDITED_HASHES["novice_head_spr"])
        spr = read_spr(spr_bytes)
        self.assertEqual(spr.indexed_count, 15)
        self.assertEqual(spr.rgba_count, 0)

    def test_novice_body_head_anchor_preview(self):
        body_act_path = find_fixture("novice_body_act")
        body_spr_path = find_fixture("novice_body_spr")
        head_act_path = find_fixture("novice_head_act")
        head_spr_path = find_fixture("novice_head_spr")
        if not all([body_act_path, body_spr_path, head_act_path, head_spr_path]):
            self.skipTest("Full Novice quartet not available for preview test")

        body_act = read_act(body_act_path.read_bytes())
        head_act = read_act(head_act_path.read_bytes())
        body_spr = read_spr(body_spr_path.read_bytes())
        head_spr = read_spr(head_spr_path.read_bytes())

        # Test Idle view 7, motion 0 (slot 7, motion 0)
        bm = body_act["actions"][7][0]
        hm = head_act["actions"][7][0]
        preview = actor_preview(body_spr.images[1], head_spr.images[1], bm, hm)
        self.assertEqual(preview.size, (256, 256))

    def test_orc_skeleton_act_and_spr(self):
        act_path = find_fixture("orc_skeleton_act")
        spr_path = find_fixture("orc_skeleton_spr")
        if not act_path or not spr_path:
            self.skipTest("Audited Orc Skeleton fixtures not available")

        act_bytes = act_path.read_bytes()
        self.assertEqual(hashlib.sha256(act_bytes).hexdigest(), AUDITED_HASHES["orc_skeleton_act"])
        act = read_act(act_bytes)
        self.assertEqual(len(act["actions"]), 40)
        self.assertEqual(sum(len(a) for a in act["actions"]), 512)
        total_visible_refs = sum(
            1 for action in act["actions"] for motion in action for clip in motion["clips"] if clip["sprite"] >= 0
        )
        self.assertEqual(total_visible_refs, 1776, "Orc Skeleton has exactly 1,776 visible layer references")
        self.assertEqual(write_act(act), act_bytes, "Orc Skeleton ACT must round-trip byte-for-byte")

        spr_bytes = spr_path.read_bytes()
        self.assertEqual(hashlib.sha256(spr_bytes).hexdigest(), AUDITED_HASHES["orc_skeleton_spr"])
        spr = read_spr(spr_bytes)
        self.assertEqual(spr.indexed_count, 57)
        self.assertEqual(spr.rgba_count, 0)
        self.assertEqual(len(spr.images), 57)


if __name__ == "__main__":
    unittest.main()

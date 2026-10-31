"""Optional real-resource inventory acceptance; never bundled in distributions."""

from collections import Counter
import unittest

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.profiles import get_profile
from ro_sprite_forge.formats.act import read_act
from test_audited_fixtures import AUDITED_HASHES, find_fixture


class PrivateInventoryTests(unittest.TestCase):
    def load(self, name, category, part="body"):
        paths = [find_fixture(f"{name}_{extension}") for extension in ("act", "spr")]
        if not all(paths):
            self.skipTest(f"NOT_RUN: private {name} resources unavailable")
        data = [path.read_bytes() for path in paths]
        for extension, value in zip(("act", "spr"), data):
            self.assertEqual(digest(value), AUDITED_HASHES[f"{name}_{extension}"])
        kwargs = {"actor": "novice-male" if name.startswith("novice") else "orc-skeleton",
                  "part": part, "profile": get_profile(category)}
        first, second = inventory(*data, **kwargs), inventory(*data, **kwargs)
        self.assertEqual(canonical_bytes(first), canonical_bytes(second))
        original = read_act(data[0])
        for slot, action in enumerate(first["actions"]):
            self.assertEqual(action["slot"], slot)
            self.assertEqual(action["mapped_view"], slot % 8)
            self.assertEqual(len(action["frames"]), len(original["actions"][slot]))
            for frame, motion in zip(action["frames"], original["actions"][slot]):
                self.assertEqual([layer["raw"] for layer in frame["layers"]], motion["clips"])
        print(f"PRIVATE_INVENTORY {name} {first['summary']} CANONICAL {first['canonical_sha256']} FILE {digest(canonical_bytes(first))}")
        return first

    def test_audited_novice_body_inventory(self):
        result = self.load("novice_body", "player")
        s = result["summary"]
        self.assertEqual([s[k] for k in ("numeric_action_groups", "action_slots", "frame_occurrences", "referenced_images", "distinct_referenced_contents")], [13, 104, 456, 110, 108])
        self.assertEqual([len(a["frames"]) for a in result["actions"]], [n for n in (3, 8, 3, 3, 6, 5, 3, 1, 1, 1, 9, 8, 6) for _ in range(8)])
        self.assertEqual(s["unused_images"], 0)
        self.assertTrue(all(len(f["layers"]) == 1 for a in result["actions"] for f in a["frames"]))
        duplicates = [[int(identity.rsplit("/i", 1)[1]) for identity in c["image_ids"]] for c in result["content_classes"] if len(c["image_ids"]) > 1]
        self.assertEqual(sorted(duplicates), [[50, 52], [93, 94]])

    def test_novice_head_keeps_separate_identity(self):
        head = self.load("novice_head", "player", "head")
        body = self.load("novice_body", "player", "body")
        self.assertEqual(head["summary"]["stored_images"], 15)
        self.assertEqual(head["summary"]["frame_occurrences"], 456)
        self.assertEqual(body["summary"]["frame_occurrences"], 456)
        self.assertTrue({i["id"] for i in head["images"]}.isdisjoint({i["id"] for i in body["images"]}))

    def test_audited_orc_multilayer_inventory(self):
        result = self.load("orc_skeleton", "monster")
        s = result["summary"]
        self.assertEqual([s[k] for k in ("numeric_action_groups", "action_slots", "frame_occurrences", "visible_layer_references", "referenced_images", "stored_images", "unused_images")], [5, 40, 512, 1776, 55, 57, 2])
        self.assertEqual([len(a["frames"]) for a in result["actions"]], [n for n in (15, 6, 12, 9, 22) for _ in range(8)])
        distribution = Counter(sum(l["visible"] for l in f["layers"]) for a in result["actions"] for f in a["frames"])
        self.assertEqual(distribution, {1: 368, 2: 32, 12: 112})
        self.assertEqual([int(i.rsplit("/i", 1)[1]) for i in result["unused_image_ids"]], [36, 39])

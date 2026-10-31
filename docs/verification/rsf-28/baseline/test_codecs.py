"""Comprehensive tests for standalone SPR 2.1 and ACT 2.4 codecs.

Tests valid synthetic structures, byte-exact preservation, defensive bounded safety,
and malicious/malformed input rejection without requiring private Ragnarok assets.
"""

import hashlib
import io
import struct
import unittest
from pathlib import Path

from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.formats.act import (
    ACT_MAGIC,
    ACT_SUPPORTED_VERSION,
    read_act,
    write_act,
)
from ro_sprite_forge.formats.errors import CodecError
from ro_sprite_forge.formats.preview import actor_preview, only_clip, place, png_bytes
from ro_sprite_forge.formats.reader import BinaryReader, sha
from ro_sprite_forge.formats.spr import (
    SPR_MAGIC,
    SPR_SUPPORTED_VERSION,
    IndexedImage,
    RgbaImage,
    SprDocument,
    read_spr,
    write_rgba_spr,
)


def make_synthetic_act(
    *,
    action_count: int = 1,
    motions_per_action: int = 2,
    clips_per_motion: int = 2,
    anchors_per_motion: int = 1,
    event_count: int = 1,
    reserved: bytes = b"\x00" * 10,
    delays: list[float] | None = None,
) -> bytes:
    """Build a valid synthetic ACT 2.4 binary payload."""
    out = bytearray(ACT_MAGIC + ACT_SUPPORTED_VERSION + struct.pack("<H", action_count))
    out += reserved
    for a_idx in range(action_count):
        out += struct.pack("<I", motions_per_action)
        for m_idx in range(motions_per_action):
            bounds = [1, 2, 3, 4, 5, 6, 7, 8]
            out += struct.pack("<8iI", *bounds, clips_per_motion)
            for c_idx in range(clips_per_motion):
                # x, y, sprite, mirror, color, scale_x, scale_y, angle, pool
                out += struct.pack(
                    "<iiiIIffiI",
                    10 + c_idx,
                    20 + c_idx,
                    c_idx,
                    c_idx % 2,
                    0xFFFFFFFF,
                    1.0,
                    1.0,
                    0,
                    0,
                )
            event_id = 0 if m_idx == 0 and event_count > 0 else -1
            out += struct.pack("<iI", event_id, anchors_per_motion)
            for an_idx in range(anchors_per_motion):
                # opaque, x, y, attribute
                out += struct.pack("<IiiI", 0, 5, -10, 0)
    out += struct.pack("<I", event_count)
    for e_idx in range(event_count):
        text = f"event_{e_idx}.wav".encode("ascii").ljust(40, b"\x00")
        out += text
    if delays is None:
        delays = [4.0] * action_count
    out += struct.pack("<" + "f" * action_count, *delays)
    return bytes(out)


def encode_rle(pixels: bytes) -> bytes:
    """Encode 1-byte-per-pixel data using SPR 2.1 zero-run RLE."""
    out = bytearray()
    i = 0
    n = len(pixels)
    while i < n:
        byte = pixels[i]
        if byte != 0:
            out.append(byte)
            i += 1
        else:
            run = 0
            while i < n and pixels[i] == 0 and run < 255:
                run += 1
                i += 1
            out.append(0)
            out.append(run)
    return bytes(out)


def make_synthetic_spr(
    indexed_specs: list[tuple[int, int, bytes]] | None = None,
    rgba_specs: list[tuple[int, int, bytes]] | None = None,
    palette: bytes | None = None,
) -> bytes:
    """Build a valid synthetic SPR 2.1 binary payload."""
    if indexed_specs is None:
        indexed_specs = []
    if rgba_specs is None:
        rgba_specs = []
    if palette is None:
        # Default 256 colors: entry 0 transparent (0,0,0,0), entries 1..255 colors
        palette_buf = bytearray(1024)
        for c in range(1, 256):
            palette_buf[c * 4] = c
            palette_buf[c * 4 + 1] = 255 - c
            palette_buf[c * 4 + 2] = (c * 2) % 256
            palette_buf[c * 4 + 3] = 255
        palette = bytes(palette_buf)

    ni = len(indexed_specs)
    nr = len(rgba_specs)
    out = bytearray(SPR_MAGIC + SPR_SUPPORTED_VERSION + struct.pack("<HH", ni, nr))

    for w, h, pixels in indexed_specs:
        encoded = encode_rle(pixels)
        out += struct.pack("<HHH", w, h, len(encoded))
        out += encoded

    for w, h, rgba_bytes in rgba_specs:
        out += struct.pack("<HH", w, h)
        # Store as bottom-up ABGR
        abgr = b"".join(
            rgba_bytes[y * w * 4 : (y + 1) * w * 4][x : x + 4][::-1]
            for y in range(h - 1, -1, -1)
            for x in range(0, w * 4, 4)
        )
        out += abgr

    out += palette
    return bytes(out)


class ActCodecTests(unittest.TestCase):
    def test_synthetic_act_round_trip(self):
        original = make_synthetic_act(action_count=2, motions_per_action=3, clips_per_motion=2)
        act = read_act(original)
        self.assertEqual(len(act["actions"]), 2)
        self.assertEqual(len(act["actions"][0]), 3)
        self.assertEqual(len(act["actions"][0][0]["clips"]), 2)
        self.assertEqual(len(act["events"]), 1)
        self.assertEqual(len(act["delays"]), 2)
        reconstructed = write_act(act)
        self.assertEqual(reconstructed, original, "ACT binary round-trip must be byte-exact")

    def test_multilayer_and_transform_preservation(self):
        original = make_synthetic_act(action_count=1, motions_per_action=1, clips_per_motion=3)
        act = read_act(original)
        clips = act["actions"][0][0]["clips"]
        self.assertEqual(len(clips), 3)
        for i, clip in enumerate(clips):
            self.assertEqual(clip["sprite"], i)
            self.assertEqual(clip["mirror"], i % 2)
            self.assertEqual(clip["scale_x"], 1.0)
            self.assertEqual(clip["scale_y"], 1.0)
            self.assertEqual(clip["color"], 0xFFFFFFFF)

    def test_act_rejects_truncated_headers(self):
        for length in (0, 1, 2, 3, 10, 15):
            with self.subTest(length=length):
                with self.assertRaises(CodecError) as caught:
                    read_act(b"AC\x04\x02"[:length])
                self.assertEqual(caught.exception.code, ErrorCode.INVALID_INPUT)

    def test_act_rejects_invalid_magic_and_versions(self):
        cases = [
            (b"XX\x04\x02" + b"\x00" * 20, "invalid magic header"),
            (b"AC\x01\x02" + b"\x00" * 20, "only ACT 2.4 is supported"),  # Version 2.1
            (b"AC\x05\x02" + b"\x00" * 20, "only ACT 2.4 is supported"),  # Version 2.5
            (b"AC\x00\x02" + b"\x00" * 20, "only ACT 2.4 is supported"),  # Version 2.0
        ]
        for data, fragment in cases:
            with self.subTest(data=data[:4]):
                with self.assertRaises(CodecError) as caught:
                    read_act(data)
                self.assertIn(fragment, str(caught.exception))

    def test_act_rejects_out_of_bounds_counts(self):
        # Action count 0
        bad_count = ACT_MAGIC + ACT_SUPPORTED_VERSION + struct.pack("<H", 0) + b"\x00" * 10
        with self.assertRaises(CodecError):
            read_act(bad_count)

        # Action count > 4096
        excess_actions = ACT_MAGIC + ACT_SUPPORTED_VERSION + struct.pack("<H", 4097) + b"\x00" * 10
        with self.assertRaises(CodecError):
            read_act(excess_actions)

    def test_act_rejects_trailing_garbage(self):
        valid = make_synthetic_act()
        with self.assertRaises(CodecError) as caught:
            read_act(valid + b"\xde\xad\xbe\xef")
        self.assertIn("trailing ACT data", str(caught.exception))

    def test_write_act_validation(self):
        act = read_act(make_synthetic_act(action_count=2))
        act["delays"].append(4.0)  # Mismatched delay count
        with self.assertRaises(CodecError):
            write_act(act)


class SprCodecTests(unittest.TestCase):
    def test_synthetic_indexed_spr_decoding(self):
        # 4x2 indexed sprite: 4 zeros, 4 color 1s
        pixels = bytes([0, 0, 0, 0, 1, 1, 1, 1])
        data = make_synthetic_spr(indexed_specs=[(4, 2, pixels)])
        spr = read_spr(data)
        self.assertEqual(spr.indexed_count, 1)
        self.assertEqual(spr.rgba_count, 0)
        self.assertEqual(spr.total_count, 1)
        self.assertEqual(len(spr.indexed_images), 1)

        img = spr.indexed_images[0]
        self.assertEqual(img.width, 4)
        self.assertEqual(img.height, 2)
        self.assertEqual(img.pixels, pixels, "Raw indexed pixels must be preserved exactly")

        # Verify unpacking compatibility: images, ni = read_spr(data)
        images, ni = spr
        self.assertEqual(len(images), 1)
        self.assertEqual(ni, 1)

        # Transparent pixel has alpha 0; non-zero pixel has alpha 255
        pil_img = images[0]
        self.assertEqual(pil_img.size, (4, 2))
        self.assertEqual(pil_img.getpixel((0, 0))[3], 0)
        self.assertEqual(pil_img.getpixel((0, 1))[3], 255)

    def test_synthetic_rgba_spr_decoding(self):
        # 2x2 RGBA image
        rgba_pixels = bytes([
            255, 0, 0, 255,  0, 255, 0, 255,
            0, 0, 255, 255,  255, 255, 0, 128,
        ])
        data = make_synthetic_spr(rgba_specs=[(2, 2, rgba_pixels)])
        spr = read_spr(data)
        self.assertEqual(spr.indexed_count, 0)
        self.assertEqual(spr.rgba_count, 1)
        self.assertEqual(len(spr.rgba_images), 1)

        rgba_img = spr.rgba_images[0]
        self.assertEqual(rgba_img.width, 2)
        self.assertEqual(rgba_img.height, 2)
        self.assertEqual(rgba_img.rgba, rgba_pixels)

        images, ni = spr
        self.assertEqual(ni, 0)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(images[0].getpixel((1, 1)), (255, 255, 0, 128))

    def test_multi_pool_spr(self):
        # Mixed pool: 1 indexed image and 1 RGBA image in the same SPR file
        indexed_pixels = bytes([0, 1, 2, 3])
        rgba_pixels = bytes([10, 20, 30, 255])
        data = make_synthetic_spr(
            indexed_specs=[(2, 2, indexed_pixels)],
            rgba_specs=[(1, 1, rgba_pixels)],
        )
        spr = read_spr(data)
        self.assertEqual(spr.indexed_count, 1)
        self.assertEqual(spr.rgba_count, 1)
        self.assertEqual(spr.total_count, 2)
        images, ni = spr
        self.assertEqual(ni, 1)
        self.assertEqual(len(images), 2)

    def test_write_rgba_spr(self):
        from PIL import Image

        img = Image.new("RGBA", (4, 4), (100, 150, 200, 255))
        payload = write_rgba_spr([img])
        spr = read_spr(payload)
        self.assertEqual(spr.indexed_count, 0)
        self.assertEqual(spr.rgba_count, 1)
        self.assertEqual(spr.images[0].size, (4, 4))
        self.assertEqual(spr.images[0].getpixel((0, 0)), (100, 150, 200, 255))

    def test_spr_rejects_truncated_headers(self):
        for length in (0, 1, 2, 3, 7):
            with self.subTest(length=length):
                with self.assertRaises(CodecError):
                    read_spr(b"SP\x01\x02\x00\x00\x00\x00"[:length])

    def test_spr_rejects_invalid_magic_and_versions(self):
        cases = [
            (b"XX\x01\x02\x00\x00\x00\x00", "invalid magic header"),
            (b"SP\x00\x02\x00\x00\x00\x00", "only SPR 2.1 is supported"),  # SPR 2.0
            (b"SP\x02\x02\x00\x00\x00\x00", "only SPR 2.1 is supported"),  # SPR 2.2
            (b"SP\x01\x01\x00\x00\x00\x00", "only SPR 2.1 is supported"),  # SPR 1.1
        ]
        for data, fragment in cases:
            with self.subTest(data=data[:4]):
                with self.assertRaises(CodecError) as caught:
                    read_spr(data)
                self.assertIn(fragment, str(caught.exception))

    def test_spr_rle_overrun_and_underrun(self):
        # 2x2 image expects 4 pixels.
        # Overrun: zero run of 5 pixels
        overrun_rle = bytes([0, 5])
        header = SPR_MAGIC + SPR_SUPPORTED_VERSION + struct.pack("<HH", 1, 0)
        img_hdr = struct.pack("<HHH", 2, 2, len(overrun_rle))
        palette = b"\x00" * 1024
        with self.assertRaises(CodecError) as caught:
            read_spr(header + img_hdr + overrun_rle + palette)
        self.assertIn("SPR RLE overrun", str(caught.exception))

        # Underrun: only 2 pixels supplied
        underrun_rle = bytes([1, 1])
        img_hdr_under = struct.pack("<HHH", 2, 2, len(underrun_rle))
        with self.assertRaises(CodecError) as caught:
            read_spr(header + img_hdr_under + underrun_rle + palette)
        self.assertIn("SPR RLE underrun", str(caught.exception))

    def test_spr_rejects_trailing_garbage(self):
        pixels = bytes([0, 0, 0, 0])
        valid = make_synthetic_spr(indexed_specs=[(2, 2, pixels)])
        with self.assertRaises(CodecError) as caught:
            read_spr(valid + b"trailing")
        self.assertIn("trailing SPR data", str(caught.exception))

    def test_spr_rejects_invalid_dimensions(self):
        # 0x0 dimension
        header = SPR_MAGIC + SPR_SUPPORTED_VERSION + struct.pack("<HH", 1, 0)
        img_hdr = struct.pack("<HHH", 0, 0, 0)
        with self.assertRaises(CodecError):
            read_spr(header + img_hdr + b"\x00" * 1024)


class PreviewAndPlacementTests(unittest.TestCase):
    def test_only_clip_validation(self):
        # Exactly one visible clip (sprite >= 0)
        valid_motion = {"clips": [{"sprite": -1}, {"sprite": 0}, {"sprite": -1}]}
        clip = only_clip(valid_motion)
        self.assertEqual(clip["sprite"], 0)

        # Zero visible clips -> CodecError
        with self.assertRaises(CodecError):
            only_clip({"clips": [{"sprite": -1}]})

        # Two visible clips -> CodecError
        with self.assertRaises(CodecError):
            only_clip({"clips": [{"sprite": 0}, {"sprite": 1}]})

    def test_png_bytes_determinism(self):
        from PIL import Image

        img = Image.new("RGBA", (8, 8), (50, 100, 150, 200))
        b1 = png_bytes(img)
        b2 = png_bytes(img)
        self.assertEqual(b1, b2, "png_bytes output must be deterministic")
        self.assertTrue(b1.startswith(b"\x89PNG\r\n\x1a\n"))


class ProvenanceVerificationTests(unittest.TestCase):
    def test_provenance_document_and_hashes(self):
        repo_root = Path(__file__).resolve().parents[1]
        provenance_file = repo_root / "docs/provenance/LWR_CODEC_PROVENANCE.md"
        self.assertTrue(provenance_file.is_file(), "Provenance document must exist")
        content = provenance_file.read_text(encoding="utf-8")
        expected_sha = "55aefdc8ba7bb5aaf4619983d72cb26c2865154961116c8ad075c65378142c46"
        self.assertIn(expected_sha, content)

        # If the audited local source file is accessible, verify its hash directly
        source_path = Path("/home/ra/Documents/Living-world-Ragnarok/tools/character_production/ro_reference.py")
        if source_path.is_file():
            actual_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
            self.assertEqual(actual_sha, expected_sha, "Upstream source hash must match recorded provenance")

    def test_public_repo_contains_no_proprietary_art(self):
        repo_root = Path(__file__).resolve().parents[1]
        for path in repo_root.glob("**/*"):
            if path.is_file() and not any(p in path.parts for p in (".git", ".venv", "tests/private_fixture_hooks")):
                self.assertFalse(
                    path.suffix.lower() in (".act", ".spr", ".grf"),
                    f"Public source tree must not contain proprietary Ragnarok files: {path}",
                )


if __name__ == "__main__":
    unittest.main()

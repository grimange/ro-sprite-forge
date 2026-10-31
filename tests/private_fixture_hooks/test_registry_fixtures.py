"""Private fixture integration tests for RSF-32 registered job/body profiles.

Verifies real discovered ACT 2.4 and SPR 2.1 resources from local lawful archives
against the registry, codecs, byte preservation, and independent Rust oracle.
Skips gracefully if local private GRF archive is not available.
"""

import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zlib

from ro_sprite_forge.core.registry import get_default_registry, verify_source_hashes
from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.formats.spr import read_spr

DEFAULT_GRF_PATH = Path('/home/ra/Documents/lwr-m1b-workspace/gravity-data/kro-210607/data.grf')
RUST_ORACLE_PATH = Path('tools/rust-oracle/target/debug/rsf-rust-oracle')


def _find_grf() -> Path | None:
    env_grf = os.environ.get('RSF_DATA_GRF')
    if env_grf and Path(env_grf).is_file():
        return Path(env_grf)
    if DEFAULT_GRF_PATH.is_file():
        return DEFAULT_GRF_PATH
    return None


def _extract_from_grf(grf_path: Path, target_name: str) -> tuple[bytes, bytes] | None:
    """Extract (act_bytes, spr_bytes) for a given entry prefix without extension."""
    with open(grf_path, 'rb') as f:
        hdr = f.read(46)
        tbl_off, seed, nfiles, ver = struct.unpack('<IIII', hdr[30:46])
        f.seek(tbl_off + 46)
        csize, usize = struct.unpack('<II', f.read(8))
        table = zlib.decompress(f.read(csize))

        i = 0
        acts, sprs = {}, {}
        while i < len(table):
            end = table.index(b'\0', i)
            name = table[i:end].decode('cp949', 'replace')
            i = end + 1
            c, a, real, flags, off = struct.unpack('<IIIBI', table[i:i + 17])
            i += 17
            if flags == 1:
                nl = name.lower()
                if nl.endswith('.act'):
                    acts[nl[:-4]] = (c, off)
                elif nl.endswith('.spr'):
                    sprs[nl[:-4]] = (c, off)

        key = target_name.lower()
        if key not in acts or key not in sprs:
            return None

        c_act, off_act = acts[key]
        f.seek(off_act + 46)
        act_b = zlib.decompress(f.read(c_act))

        c_spr, off_spr = sprs[key]
        f.seek(off_spr + 46)
        spr_b = zlib.decompress(f.read(c_spr))

    return act_b, spr_b


class PrivateRegistryFixtureTests(unittest.TestCase):
    def setUp(self):
        self.grf_path = _find_grf()
        if not self.grf_path:
            self.skipTest('Local GRF archive not available for private fixture verification.')
        self.registry = get_default_registry()

    def _test_pair(self, profile_id: str, grf_entry_prefix: str, has_anchors: bool = True):
        p = self.registry.get_profile(profile_id)
        pair = _extract_from_grf(self.grf_path, grf_entry_prefix)
        if not pair:
            self.skipTest(f'Fixture {grf_entry_prefix} not found in {self.grf_path}')

        act_b, spr_b = pair

        # 1. Source hash verification
        self.assertTrue(verify_source_hashes(p, act_b, spr_b))

        # 2. ACT decoding and round-trip preservation
        self.assertEqual(act_b[:4], b'AC\x04\x02')  # ACT 2.4
        act = read_act(act_b)
        self.assertEqual(len(act['actions']), p['topology']['slot_count'])
        total_motions = sum(len(a) for a in act['actions'])
        self.assertEqual(total_motions, p['topology']['motion_count'])
        written_act = write_act(act)
        self.assertEqual(written_act, act_b, 'ACT byte-exact preservation required')

        # 3. SPR decoding
        spr = read_spr(spr_b)
        self.assertEqual(spr.indexed_count, p['image_pool']['indexed_count'])
        self.assertEqual(spr.rgba_count, p['image_pool']['rgba_count'])

        # 4. Independent Rust oracle
        if RUST_ORACLE_PATH.is_file():
            with tempfile.NamedTemporaryFile(suffix='.act', delete=False) as fa, \
                 tempfile.NamedTemporaryFile(suffix='.spr', delete=False) as fs:
                fa.write(act_b)
                fs.write(spr_b)
                fa_path, fs_path = fa.name, fs.name

            try:
                res = subprocess.run([str(RUST_ORACLE_PATH), fa_path, fs_path], capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, f'Rust oracle failed on {profile_id}: {res.stderr}')
            finally:
                os.unlink(fa_path)
                os.unlink(fs_path)

    def test_genetic_female_body_real_fixture(self):
        self._test_pair(
            'genetic-female-body-v1',
            r'data\sprite\인간족\몸통\여\costume_1\제네릭_여_1',
            has_anchors=True,
        )

    def test_dragon_knight_male_shield_real_fixture(self):
        self._test_pair(
            'dragon-knight-male-shield-v1',
            r'data\sprite\방패\dragon_knight\dragon_knight_남_쉴드',
            has_anchors=False,
        )

    def test_falcon_companion_real_fixture(self):
        self._test_pair(
            'falcon-companion-v1',
            r'data\sprite\몬스터\매',
            has_anchors=False,
        )


if __name__ == '__main__':
    unittest.main()

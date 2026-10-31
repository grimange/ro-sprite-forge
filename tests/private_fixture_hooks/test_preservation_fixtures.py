"""Optional hash-pinned resource preservation; no private outputs in the checkout."""

from pathlib import Path
import tempfile
import unittest

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.preservation import roundtrip_pair
from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.report_io import publish_resources
from test_audited_fixtures import AUDITED_HASHES, find_fixture


class PrivatePreservationTests(unittest.TestCase):
    def check_pair(self, name):
        paths = [find_fixture(f'{name}_{ext}') for ext in ('act','spr')]
        if not all(paths):
            self.skipTest(f'NOT_RUN: hash-pinned {name} fixtures unavailable')
        sources = [p.read_bytes() for p in paths]
        for ext, data in zip(('act','spr'), sources):
            self.assertEqual(digest(data), AUDITED_HASHES[f'{name}_{ext}'])
        for mode in ('preserve','act-semantic'):
            a,s,report = roundtrip_pair(*sources,mode=mode)
            self.assertEqual((a,s),tuple(sources))
            self.assertEqual(read_act(a),read_act(sources[0]))
            self.assertEqual(canonical_bytes(report),canonical_bytes(roundtrip_pair(*sources,mode=mode)[2]))
            with tempfile.TemporaryDirectory(prefix='rsf4-private-') as tmp:
                outputs = [Path(tmp)/f'output.{ext}' for ext in ('act','spr')]
                publish_resources(tuple((str(p),data) for p,data in zip(outputs,(a,s))))
                self.assertEqual([p.read_bytes() for p in outputs],sources)
            self.assertEqual([p.read_bytes() for p in paths],sources)
            print('PRIVATE_PRESERVATION',name,mode,report['resources'],report['summary'])
        return report

    def test_novice_body(self):
        r=self.check_pair('novice_body')
        self.assertEqual([r['summary'][k] for k in ('action_slots','frame_occurrences','referenced_images','distinct_referenced_contents')],[104,456,110,108])

    def test_novice_head(self):
        r=self.check_pair('novice_head')
        self.assertEqual(r['summary']['stored_images'],15)

    def test_orc_multilayer_and_unused(self):
        r=self.check_pair('orc_skeleton')
        self.assertEqual([r['summary'][k] for k in ('frame_occurrences','visible_layer_references','referenced_images','stored_images','unused_images')],[512,1776,55,57,2])
        # Existing private inventory hook independently asserts unused identities 36/39.

"""Optional hash-pinned timeline/bounds checks, using original private bytes."""
import gzip
import json
from pathlib import Path
import unittest

from ro_sprite_forge.core.animation import AnimationInspector
from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.timeline import AnimationTimeline
from ro_sprite_forge.formats.act import read_act
from test_audited_fixtures import AUDITED_HASHES, find_fixture


class AuditedAnimationTests(unittest.TestCase):
    def resource(self, name):
        p = find_fixture(name)
        if p is None:
            self.skipTest('Private fixture unavailable: '+name)
        raw=p.read_bytes()
        self.assertEqual(digest(raw), AUDITED_HASHES[name])
        return raw

    def novice(self):
        return AnimationInspector(self.resource('novice_body_act'),self.resource('novice_body_spr'),category='player',
            head_act_bytes=self.resource('novice_head_act'),head_spr_bytes=self.resource('novice_head_spr'))

    def orc(self):
        return AnimationInspector(self.resource('orc_skeleton_act'),self.resource('orc_skeleton_spr'),category='monster')

    def test_all_archived_native_frame_selections(self):
        # Durable accepted native observations, not a new native run or Python-generated expectation.
        native=json.loads(gzip.decompress((Path(__file__).resolve().parents[2]/'docs/evidence/rsf6/native-report.json.gz').read_bytes()))
        timelines={
            'novice': AnimationTimeline(read_act(self.resource('novice_body_act')),category='player'),
            'orc': AnimationTimeline(read_act(self.resource('orc_skeleton_act')),category='monster')}
        samples=0
        for case in native['cases']:
            t=timelines[case['actor']]
            action='Attack1' if case['requested_action']=='Attack' else case['requested_action']
            s=t.select(action=action,direction=case['requested_direction'],camera_direction=case['camera_view'])
            self.assertEqual(s['resolved_slot'],case['resolved_slot'])
            self.assertEqual(s['fallback'],case['fallback'])
            self.assertEqual(s['source_delay'],case['source_delay'])
            for sample in case['sequence']:
                result=t.seek(s,sample['tick'],movement_speed=150 if action=='Walk' else None,duration_ms=case['duration'])
                self.assertEqual(result['frame'],sample['frame'],(case['actor'],action,s['view'],sample['tick']))
                samples+=1
        self.assertEqual((len(native['cases']),samples),(160,1664))

    def test_novice_walk_and_attack_sequences(self):
        e=self.novice(); walk=e.timeline.select(action='Walk');attack=e.timeline.select(action='Attack1')
        self.assertEqual(walk['frame_count'],8)
        self.assertEqual(walk['source_delay'],3.)
        self.assertEqual([e.timeline.seek(walk,i*60,movement_speed=150)['frame'] for i in range(10)],list(range(8))+[0,1])
        self.assertEqual(attack['frame_count'],5)
        self.assertEqual([e.timeline.seek(attack,i*200,duration_ms=1000)['frame'] for i in range(7)],[0,1,2,3,4,4,4])

    def test_orc_walk_and_terminal_death_sequences(self):
        e=self.orc();walk=e.timeline.select(action='Walk');die=e.timeline.select(action='Die')
        self.assertEqual(walk['frame_count'],6)
        interval=e.timeline.seek(walk,0,movement_speed=150)['frame_duration_ms']
        self.assertEqual([e.timeline.seek(walk,int((i+.1)*interval),movement_speed=150)['frame'] for i in range(8)],list(range(6))+[0,1])
        interval=e.timeline.seek(die,0)['frame_duration_ms']
        self.assertEqual([e.timeline.seek(die,int((i+.1)*interval))['frame'] for i in range(24)],list(range(22))+[21,21])

    def test_novice_body_head_anchor_and_independent_identity(self):
        e=self.novice();r=e.inspect(e.timeline.select(action='Walk',frame=3))['report']
        self.assertEqual(len(r['layers']),2)
        self.assertEqual([l['part'] for l in r['layers']],['body','head'])
        self.assertEqual(r['sources']['body_act'],AUDITED_HASHES['novice_body_act'])
        self.assertEqual(r['sources']['head_act'],AUDITED_HASHES['novice_head_act'])
        b,h=r['source_frames']
        self.assertEqual(b['frame'],h['frame'])
        ba,ha=b['anchors'][0],h['anchors'][0]
        self.assertEqual(r['layers'][1]['geometry']['anchor_shift'],[ba['x']-ha['x'],ba['y']-ha['y']])

    def test_orc_twelve_layer_death_bounds(self):
        e=self.orc();r=e.inspect(e.timeline.select(action='Die',frame=21),auto_fit=True)['report']
        self.assertEqual([l['image_index'] for l in r['layers']],[44,45,46,47,46,47,47,42,40,41,43,47])
        self.assertEqual([l['layer_ordinal'] for l in r['layers']],list(range(12)))
        self.assertTrue(all(l['geometry']['clipping']=='INSIDE' for l in r['layers']))
        self.assertEqual(r['sources']['body_act'],AUDITED_HASHES['orc_skeleton_act'])
        self.assertIsNotNone(r['frame_bounds']['visible'])
        # Native parts retain identity/offset/order. Native unrotated billboard bounds
        # intentionally differ from Pillow's expanded rotated diagnostic rectangles.
        native=json.loads(gzip.decompress((Path(__file__).resolve().parents[2]/'docs/evidence/rsf6/native-report.json.gz').read_bytes()))
        prepared=next(p for p in native['prepared'] if p['actor']=='orc')['actions'][32][21]['parts']
        self.assertEqual([p['image'] for p in prepared],[l['image_index'] for l in r['layers']])
        self.assertEqual([p['offset'] for p in prepared],[l['geometry']['source_offset'] for l in r['layers']])

    def test_private_determinism_and_source_immutability(self):
        names=list(AUDITED_HASHES)
        before={n:digest(self.resource(n)) for n in names}
        e=self.orc();s=e.timeline.select(action='Die',frame=21)
        a=e.inspect(s,auto_fit=True);b=e.inspect(s,auto_fit=True)
        self.assertEqual(canonical_bytes(a['report']),canonical_bytes(b['report']))
        self.assertEqual(a['png_bytes'],b['png_bytes'])
        self.assertEqual(before,{n:digest(self.resource(n)) for n in names})

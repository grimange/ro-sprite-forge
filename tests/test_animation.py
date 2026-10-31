"""Independent arithmetic/geometry expectations for timeline and inspection."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from PIL import Image

from ro_sprite_forge.cli import main
from ro_sprite_forge.core.animation import AnimationInspector, inspection_schema
from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed
from ro_sprite_forge.core.contracts import frozen_runtime_profile
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.core.timeline import AnimationTimeline
from ro_sprite_forge.formats.act import write_act
from ro_sprite_forge.formats.spr import write_rgba_spr


def clip(**kw):
    return dict(x=0, y=0, sprite=0, pool=1, mirror=0, color=0xffffffff,
                scale_x=1., scale_y=1., angle=0) | kw


def motion(clips=None, anchors=None):
    return dict(bounds=[0]*8, clips=[clip()] if clips is None else clips,
                anchors=anchors or [], event=-1)


def act(count=4, slots=40):
    return dict(reserved='00'*10, actions=[[motion() for _ in range(count)] for _ in range(slots)],
                delays=[2.]*slots, events=[])


def inspector(doc=None, image=None, **kw):
    image = image if image is not None else Image.new('RGBA', (4, 2), 'red')
    return AnimationInspector(write_act(doc or act()), write_rgba_spr([image]), **kw)


def inspect(doc=None, image=None, **kw):
    engine = inspector(doc, image)
    return engine.inspect(engine.timeline.select(slot=0), canvas_size=(16, 16), origin=(8, 8), **kw)['report']


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.doc = act()
        self.t = AnimationTimeline(self.doc, category='monster')
        self.walk = self.t.select(action='Walk')

    def test_manual_forward_backward_and_boundaries(self):
        self.assertEqual(self.t.step(self.walk, 1)['frame'], 1)
        self.assertEqual(self.t.step(self.walk, -1)['frame'], 0)
        last = self.t.step(self.walk, 50)
        self.assertEqual(last['frame'], 3)
        self.assertEqual(self.t.step(last, -1)['frame'], 2)
        self.assertEqual(last['timing_status'], 'NOT_EVALUATED')

    def test_explicit_loop_wrap(self):
        self.assertEqual(self.t.step(self.walk, -1, loop=True)['frame'], 3)
        self.assertEqual(self.t.step(self.walk, 9, loop=True)['frame'], 1)

    def test_walk_context_and_loop_boundaries(self):
        # raw delay 2 * (150*100/150/5) = 40 ms; four frames
        for tick, expected in [(0,0),(39,0),(40,1),(159,3),(160,0),(520,1)]:
            with self.subTest(tick=tick):
                result = self.t.seek(self.walk, tick, movement_speed=150)
                self.assertEqual(result['frame'], expected)
                self.assertEqual(result['frame_duration_ms'], 40.)
                self.assertTrue(result['looping'])
        self.assertEqual(self.t.seek(self.walk, 160)['timing_status'], 'UNVERIFIED')

    def test_explicit_speed(self):
        self.assertEqual(self.t.seek(self.walk, 40, speed=2., movement_speed=150)['frame'], 2)
        self.assertEqual(self.t.seek(self.walk, 40, speed=.5, movement_speed=150)['frame'], 0)

    def test_external_attack_duration(self):
        s = self.t.select(action='Attack1')
        for tick, expected in [(0,0),(250,1),(749,2),(750,3),(1000,3),(2000,3)]:
            r = self.t.seek(s, tick, duration_ms=1000)
            self.assertEqual(r['frame'], expected)
            self.assertFalse(r['looping'])
        self.assertEqual(self.t.seek(s, 500)['timing_status'], 'UNVERIFIED')

    def test_terminal_hold_is_not_completion(self):
        s = self.t.select(action='Die')
        r = self.t.seek(s, 300)
        self.assertEqual(r['frame'], 3)
        self.assertFalse(r['terminal_hold'])
        self.assertFalse(r['native_completion'])
        self.assertTrue(self.t.seek(s, 400)['terminal_hold'])
        self.assertFalse(self.t.seek(s, 400)['native_completion'])
        self.assertTrue(self.t.seek(s, 500)['native_completion'])

    def test_completion_uses_view_zero(self):
        self.doc['actions'][33] = [motion(), motion()]
        t = AnimationTimeline(self.doc, category='monster')
        s = t.select(action='Die', view=1)
        r = t.seek(s, 300)
        self.assertTrue(r['terminal_hold'])
        self.assertFalse(r['native_completion']) # view 0 still has four frames

    def test_player_idle_frozen_monster_idle_loops(self):
        p = AnimationTimeline(act(slots=104), category='player')
        self.assertEqual(p.seek(p.select(action='Idle'), 200)['frame'], 0)
        self.assertEqual(self.t.seek(self.t.select(action='Idle'), 200)['frame'], 2)

    def test_single_frame_and_different_lengths(self):
        self.doc['actions'][8] = [motion()]
        t = AnimationTimeline(self.doc, category='monster')
        self.assertEqual(t.seek(t.select(action='Walk'), 999, movement_speed=150)['frame'], 0)
        self.assertEqual(t.select(action='Die')['frame_count'], 4)

    def test_pickup_delay(self):
        t = AnimationTimeline(act(slots=104), category='player')
        r = t.seek(t.select(action='Pickup'), 50)
        self.assertEqual(r['frame'], 1)
        self.assertEqual(r['frame_duration_ms'], 50.)

    def test_unknown_timing_and_diagnostic_override(self):
        t = AnimationTimeline(act(slots=104), category='player')
        s = t.select(action='Sit')
        self.assertEqual(t.seek(s, 200)['timing_status'], 'UNVERIFIED')
        r = t.seek(s, 200, diagnostic_frame_ms=50, diagnostic_loop=False)
        self.assertEqual(r['frame'], 3)
        self.assertEqual(r['timing_status'], 'DIAGNOSTIC')
        self.assertIsNone(r['native_completion'])
        self.assertIn('DIAGNOSTIC', r['diagnostics'][-1])

    def test_direction_camera_and_no_fallback(self):
        s = self.t.select(action='Walk', direction=7, camera_direction=2)
        self.assertEqual(s['resolved_slot'], 9)
        r = self.t.seek(s, 40, movement_speed=150)
        self.assertEqual((r['direction'], r['camera_direction'], r['view']), (7,2,1))
        self.assertEqual(self.t.step(s, 1)['direction'], 7)
        for kwargs in [dict(action='Attack3'),dict(slot=40),dict(slot=9,view=0),dict(action='Invented'),dict(slot=0,frame=4)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ForgeError): self.t.select(**kwargs)

    def test_invalid_timing(self):
        for kwargs in [dict(elapsed_ms=-1),dict(elapsed_ms=1.5),dict(elapsed_ms=True),dict(elapsed_ms=1,speed=0),
                       dict(elapsed_ms=1,speed=float('nan')),dict(elapsed_ms=1,movement_speed=0),
                       dict(elapsed_ms=1,diagnostic_frame_ms=-1),dict(elapsed_ms=2**32),
                       dict(elapsed_ms=1,speed=10**1000),dict(elapsed_ms=10,speed=10**308),
                       dict(elapsed_ms=1,diagnostic_frame_ms=10**1000)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ForgeError): self.t.seek(self.walk, **kwargs)
        with self.assertRaises(ForgeError): self.t.seek(self.t.select(action='Attack1'), 2**32-1, duration_ms=1)
        with self.assertRaises(ForgeError): self.t.seek(self.t.select(action='Hurt'), 1, duration_ms=0)

    def test_zero_delay_unresolved_not_replaced(self):
        self.doc['delays'][8] = 0
        t = AnimationTimeline(self.doc, category='monster')
        s = t.select(action='Walk')
        self.assertEqual(s['source_delay'], 0)
        with self.assertRaises(ForgeError): t.seek(s, 10, movement_speed=150)
        self.assertEqual(t.seek(s, 10, diagnostic_frame_ms=10)['timing_status'], 'DIAGNOSTIC')

    def test_float32_boundary_from_native_arithmetic(self):
        # f32(1/3) * 50 = 16.66666794, f32(50 / factor) rounds to 2.99999976.
        self.doc['delays'][0] = 1/3
        t = AnimationTimeline(self.doc, category='monster')
        self.assertEqual(t.seek(t.select(action='Idle'), 50)['frame_time'], 2)

    def test_input_snapshot_and_stale_selection(self):
        original = canonical_bytes(self.doc)
        a = self.t.seek(self.walk, 40, movement_speed=150)
        self.doc['actions'][8][0]['clips'][0]['x'] = 999
        self.assertEqual(a, self.t.seek(self.walk, 40, movement_speed=150))
        newer = AnimationTimeline(self.doc, category='monster')
        with self.assertRaises(ForgeError): newer.step(self.walk, 1)
        with self.assertRaises(ForgeError): self.t.step(sealed({'schema':'rsf.timeline-selection/v1'}), 1)
        self.assertNotEqual(original, canonical_bytes(self.doc))

    def test_unknown_category_and_profile_mismatch(self):
        t = AnimationTimeline(act())
        self.assertIsNone(t.select(slot=0)['action'])
        self.assertEqual(t.seek(t.select(slot=0), 50)['timing_status'], 'UNVERIFIED')
        with self.assertRaises(ForgeError): AnimationTimeline(act(), category='monster', profile=frozen_runtime_profile('player'))

    def test_resealed_selection_metadata_is_reconstructed(self):
        engine = inspector(category='monster')
        manual = engine.timeline.select(action='Walk')
        timed = engine.timeline.seek(manual, 80, movement_speed=150)
        diagnostic = engine.timeline.seek(manual, 80, diagnostic_frame_ms=20, diagnostic_loop=False)
        for original in (manual, timed, diagnostic):
            # Authentic output remains usable after serialization and for later steps/seeks.
            engine.inspect(json.loads(canonical_bytes(original)))
            engine.timeline.step(original, 1)
            engine.timeline.seek(original, 120, movement_speed=150)
            for field, bad in [('action','Die'), ('timing_status','SUPPORTED'),
                               ('timing_rule','PLAYER_IDLE_FRAME_ZERO'), ('frame_time',999),
                               ('fallback','SILENT'), ('category','player'),
                               ('timing_version','99.0.0'), ('context',{'unexpected':1})]:
                if original[field] == bad:
                    continue
                forged = sealed({k:v for k,v in original.items() if k != 'canonical_sha256'} | {field:bad})
                with self.subTest(mode=original['mode'],field=field), self.assertRaises(ForgeError):
                    engine.inspect(forged)


class GeometryTests(unittest.TestCase):
    def test_report_data_is_detached_from_sources_and_selection(self):
        d = act()
        d['actions'][0][0]['anchors'] = [dict(opaque=0,x=4,y=5,attribute=0)]
        d['events'] = ['00'*40]
        engine = inspector(d)
        selection = engine.timeline.select(slot=0)
        baseline = canonical_bytes(engine.inspect(selection)['report'])
        report = engine.inspect(selection)['report']
        report['source_frames'][0]['anchors'][0]['x'] = 999
        report['source_frames'][0]['raw_events'].append('ff'*40)
        report['selection']['diagnostics'].append('mutated')
        self.assertEqual(canonical_bytes(engine.inspect(selection)['report']), baseline)
        self.assertEqual(selection['diagnostics'], [])
        detached = engine.inspect(selection)['report']
        selection['frame'] = 2
        self.assertEqual(detached['selection']['frame'], 0)

    def test_auto_fit_large_signed_offsets_uses_real_extent(self):
        for offset in (-2000000,2000000):
            d = act();d['actions'][0][0]['clips'] = [clip(x=offset,y=-offset)]
            engine = inspector(d)
            r = engine.inspect(engine.timeline.select(slot=0),auto_fit=True)['report']
            self.assertEqual(r['canvas']['dimensions'], {'width':36,'height':34})
            self.assertEqual(r['layers'][0]['geometry']['transformed_bounds'], [16,16,20,18])
            self.assertEqual(r['layers'][0]['geometry']['clipping'], 'INSIDE')

    def test_opaque_even_registration(self):
        r = inspect()
        g = r['layers'][0]['geometry']
        self.assertEqual(g['transformed_bounds'], [7,8,11,10])
        self.assertEqual(g['integer_center'], [1,0])
        self.assertEqual(g['visible_bounds'], [7,8,11,10])
        self.assertEqual(r['frame_bounds']['transformed'], [7,8,11,10])

    def test_transparent_pixel_bounds_and_mirror(self):
        img = Image.new('RGBA', (4,2), (99,0,0,0)); img.putpixel((0,0),(255,255,255,255))
        d = act(); d['actions'][0][0]['clips'][0]['mirror'] = 1
        g = inspect(d,img)['layers'][0]['geometry']
        self.assertEqual(g['stages']['source']['alpha'], [0,0,1,1])
        self.assertEqual(g['stages']['mirrored']['alpha'], [3,0,4,1])
        self.assertEqual(g['visible_bounds'], [10,8,11,9])

    def test_scaled_and_rotated_extent(self):
        d = act(); d['actions'][0][0]['clips'] = [clip(scale_x=2.,scale_y=3.,angle=90)]
        g = inspect(d)['layers'][0]['geometry']
        self.assertEqual(g['stages']['scaled']['extent'], [0,0,8,6])
        self.assertEqual(g['stages']['rotated']['extent'], [0,0,6,8])
        self.assertEqual(g['transformed_bounds'], [6,5,12,13])

    def test_arbitrary_rotation_bounds_match_actual_alpha(self):
        d = act(); d['actions'][0][0]['clips'] = [clip(angle=45)]
        engine = inspector(d)
        result = engine.inspect(engine.timeline.select(slot=0), canvas_size=(32,32), origin=(16,16))
        self.assertEqual(result['report']['frame_bounds']['visible'], list(result['image'].getchannel('A').getbbox()))
        self.assertEqual(result['report']['layers'][0]['geometry']['stages']['rotated']['extent'], [0,0,6,6])

    def test_multilayer_negative_positive_offsets(self):
        d = act(); d['actions'][0][0]['clips'] = [clip(x=-3,y=-2),clip(x=4,y=3)]
        r = inspect(d)
        self.assertEqual([l['layer_ordinal'] for l in r['layers']], [0,1])
        self.assertEqual(r['frame_bounds']['transformed'], [4,6,15,13])
        self.assertEqual(r['layers'][1]['geometry']['registration'], [12,11])

    def test_clipping_outside_and_transparency_are_distinct(self):
        d = act(); d['actions'][0][0]['clips'] = [clip(x=-8),clip(x=50),clip(color=0)]
        r = inspect(d)
        self.assertEqual([l['geometry']['clipping'] for l in r['layers']], ['PARTIAL','OUTSIDE','INSIDE'])
        self.assertEqual(r['layers'][0]['geometry']['visible_bounds'], [0,8,3,10])
        self.assertEqual(r['layers'][0]['geometry']['clipped_regions'], [[-1,8,0,10]])
        self.assertIsNone(r['layers'][1]['geometry']['visible_bounds'])
        self.assertTrue(r['layers'][2]['geometry']['transparent'])
        self.assertFalse(r['empty_frame'])

    def test_empty_and_sentinel_frames(self):
        for clips, empty in [([],True),([clip(sprite=-1)],True)]:
            d = act(); d['actions'][0][0]['clips'] = clips
            r = inspect(d)
            self.assertEqual(r['empty_frame'], empty)
            self.assertTrue(r['fully_transparent'])
            self.assertIsNone(r['frame_bounds']['transformed'])
        self.assertTrue(any('RAW_MOTION' in n for n in r['selection']['diagnostics']) is False) # sentinel isn't zero-clip

    def test_anchor_shared_frame_and_raw_delays(self):
        body, head = act(), act()
        body['actions'][0][1]['anchors'] = [dict(opaque=0,x=4,y=-3,attribute=0)]
        head['actions'][0][1]['anchors'] = [dict(opaque=0,x=1,y=2,attribute=0)]
        head['delays'][0] = 7.
        spr = write_rgba_spr([Image.new('RGBA',(4,2),'red')])
        e = AnimationInspector(write_act(body),spr,category='player',head_act_bytes=write_act(head),head_spr_bytes=spr)
        r = e.inspect(e.timeline.select(slot=0,frame=1),canvas_size=(16,16),origin=(8,8))['report']
        self.assertEqual([f['frame'] for f in r['source_frames']], [1,1])
        self.assertEqual([f['raw_delay'] for f in r['source_frames']], [2.,7.])
        self.assertEqual(r['layers'][1]['geometry']['anchor_shift'], [3,-5])
        self.assertEqual(r['layers'][1]['geometry']['transformed_bounds'], [10,3,14,5])
        self.assertNotEqual(r['sources']['body_act'], r['sources']['head_act'])

    def test_multiple_head_anchors_are_not_single_anchor_rule(self):
        body, head = act(), act()
        anchor = dict(opaque=0,x=4,y=5,attribute=0)
        body['actions'][0][0]['anchors'] = [anchor]
        head['actions'][0][0]['anchors'] = [dict(anchor,x=1),dict(anchor,x=2)]
        spr = write_rgba_spr([Image.new('RGBA',(4,2),'red')])
        e = AnimationInspector(write_act(body),spr,category='player',head_act_bytes=write_act(head),head_spr_bytes=spr)
        r = e.inspect(e.timeline.select(slot=0))['report']
        self.assertEqual(r['layers'][1]['geometry']['anchor_shift'], [0,0])

    def test_nonplayer_attachment_rejected(self):
        raw = write_act(act()); spr = write_rgba_spr([Image.new('RGBA',(1,1),'red')])
        with self.assertRaises(ForgeError): AnimationInspector(raw,spr,category='monster',head_act_bytes=raw,head_spr_bytes=spr)
        with self.assertRaises(ForgeError): AnimationInspector(raw,spr,head_act_bytes=raw)

    def test_missing_exact_head_frame_rejected(self):
        body, head = act(), act(count=1)
        spr = write_rgba_spr([Image.new('RGBA',(1,1),'red')])
        e = AnimationInspector(write_act(body),spr,category='player',head_act_bytes=write_act(head),head_spr_bytes=spr)
        with self.assertRaises(ForgeError): e.inspect(e.timeline.select(slot=0,frame=1))

    def test_budgets_invalid_canvas_transform_and_references(self):
        e = inspector()
        for dims in [(0,16),(-1,10),(999999,999999),(1.5,2)]:
            with self.subTest(dims=dims),self.assertRaises(ForgeError): e.inspect(e.timeline.select(slot=0),canvas_size=dims)
        for kw in [dict(scale_x=1e10),dict(sprite=999),dict(pool=9)]:
            d = act();d['actions'][0][0]['clips']=[clip(**kw)]
            with self.subTest(kw=kw),self.assertRaises(ForgeError): inspect(d)

    def test_canonical_identity_immutability_and_no_approval(self):
        doc = act(); before = copy.deepcopy(doc)
        e = inspector(doc)
        s = e.timeline.select(slot=0)
        a = e.inspect(s); b = e.inspect(s)
        self.assertEqual(canonical_bytes(a['report']),canonical_bytes(b['report']))
        self.assertEqual(a['png_bytes'],b['png_bytes'])
        self.assertEqual(a['report']['preview_png_sha256'],digest(a['png_bytes']))
        self.assertEqual(doc,before)
        self.assertEqual(a['report']['review'],'UNVERIFIED')
        self.assertEqual(a['report']['artwork_coverage'],'NOT_EVALUATED')
        self.assertEqual(a['report']['fidelity']['native_pixel_parity'],'UNVERIFIED')
        self.assertNotIn('/tmp', canonical_bytes(a['report']).decode())

    def test_schema_closed_valid_and_rejects_fake_approval(self):
        try: from jsonschema import Draft202012Validator
        except ImportError: self.skipTest('Optional jsonschema not installed')
        schema=inspection_schema(); Draft202012Validator.check_schema(schema)
        validator=Draft202012Validator(schema)
        r=inspect(); validator.validate(r)
        for path,value in [('review','APPROVED'),('schema','rsf.animation-inspection/v9'),('unexpected',1)]:
            b=copy.deepcopy(r); b[path]=value
            self.assertTrue(list(validator.iter_errors(b)))


class AnimationCliTests(unittest.TestCase):
    def test_cli_manual_timed_output_and_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=root/'input.act'; s=root/'input.spr'; out=root/'report.json'; png=root/'frame.png'
            a.write_bytes(write_act(act())); s.write_bytes(write_rgba_spr([Image.new('RGBA',(4,2),'red')]))
            before=(a.read_bytes(),s.read_bytes())
            args=['animation','--act',str(a),'--spr',str(s),'--category','monster','--action','Walk',
                  '--time-ms','160','--movement-speed','150','--json',str(out),'--output',str(png)]
            self.assertEqual(main(args),0)
            r=json.loads(out.read_bytes()); self.assertEqual(r['selection']['frame'],0)
            self.assertEqual(r['preview_png_sha256'],digest(png.read_bytes()))
            self.assertEqual(before,(a.read_bytes(),s.read_bytes()))
            out.unlink();png.unlink()
            import os
            link = os.link
            calls = []
            def failing_link(src, dst):
                calls.append(dst)
                if len(calls) == 2:
                    raise OSError('failure')
                return link(src, dst)
            with patch('ro_sprite_forge.report_io.os.link',side_effect=failing_link):
                # Publication staging failure must never leave a success report.
                with redirect_stderr(io.StringIO()): self.assertNotEqual(main(args),0)
            self.assertFalse(out.exists());self.assertFalse(png.exists())
            self.assertFalse(list(root.glob('.rsf-resource-*')))

    def test_cli_bad_inputs_nonzero_and_no_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a=root/'a';s=root/'s';out=root/'out'
            a.write_bytes(write_act(act()));s.write_bytes(write_rgba_spr([Image.new('RGBA',(1,1),'red')]))
            base=['animation','--act',str(a),'--spr',str(s),'--json',str(out)]
            for flags in [['--frame','99'],['--canvas-size','bad'],['--canvas-size','0,1'],['--time-ms','-1'],
                          ['--speed','2'],['--head-act',str(a)],['--slot','9'],['--time-ms','1','--loop']]:
                with self.subTest(flags=flags),redirect_stderr(io.StringIO()):self.assertNotEqual(main(base+flags),0)
                self.assertFalse(out.exists())

    def test_cli_stdout_step_and_diagnostic_timing(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a=root/'a';s=root/'s'
            a.write_bytes(write_act(act()));s.write_bytes(write_rgba_spr([Image.new('RGBA',(1,1),'red')]))
            base=['animation','--act',str(a),'--spr',str(s)]
            stdout=io.StringIO()
            with redirect_stdout(stdout):self.assertEqual(main(base+['--step','-1','--loop']),0)
            self.assertEqual(json.loads(stdout.getvalue())['selection']['frame'],3)
            stdout=io.StringIO()
            with redirect_stdout(stdout):self.assertEqual(main(base+['--time-ms','25','--diagnostic-frame-ms','10']),0)
            self.assertEqual(json.loads(stdout.getvalue())['selection']['timing_status'],'DIAGNOSTIC')

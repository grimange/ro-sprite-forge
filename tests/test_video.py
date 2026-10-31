"""RSF-28: independently known pixels/PTS, bounded tools, immutable staging.

Fixtures are generated locally from five RGB patterns, not proprietary video.
Real FFmpeg integration is optional; process/core tests still run without tools.
"""
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ro_sprite_forge.adapters import video
from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.core.project import create_project, load_project, get_blob, save_project
from ro_sprite_forge.service.media import stage_video

TOOLS = all(shutil.which(n, path=os.defpath) for n in ('ffmpeg', 'ffprobe'))
try:
    from PIL import Image
    PILLOW = True
except ImportError:
    PILLOW = False


def make_media(directory):
    """Lossless FFV1 fixture, exact RGB reference independent of decoder output."""
    directory = Path(directory)
    expected = []
    for n in range(5):
        image = Image.new('RGB', (16, 16), (n * 40 + 10, 200 - n * 30, 25 + n * 35))
        for x in range(n + 1):
            image.putpixel((x, n), (255, n * 10, 255 - n * 20))
        expected.append(image.convert('RGBA').tobytes())
        image.save(directory / f'input-{n:02d}.png')
    common = ['/usr/bin/ffmpeg', '-nostdin', '-v', 'error', '-bitexact', '-f', 'image2',
              '-framerate', '25', '-i', str(directory/'input-%02d.png')]
    tail = ['-c:v', 'ffv1', '-threads', '1', '-pix_fmt', 'bgr0', '-fflags', '+bitexact']
    commands = []
    for name, filters in (
        ('cfr', []),
        ('vfr', ['-vf', 'settb=1/1000,setpts=if(eq(N\\,0)\\,0\\,if(eq(N\\,1)\\,40\\,if(eq(N\\,2)\\,120\\,if(eq(N\\,3)\\,160\\,300))))',
                 '-fps_mode', 'passthrough', '-enc_time_base', '1/1000']),
    ):
        command = common + filters + tail + [str(directory/f'{name}.mkv')]
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        commands.append(command)
    return expected, commands


class SafetyTests(unittest.TestCase):
    def test_missing_tools_are_explicit_and_core_starts_no_process(self):
        with patch.object(video.shutil, 'which', return_value=None):
            cap = video.capabilities()
            self.assertFalse(cap['available'])
            self.assertIn('VIDEO_TOOL_UNAVAILABLE', cap['ffmpeg']['diagnostic'])
            with self.assertRaisesRegex(ForgeError, 'VIDEO_TOOL_UNAVAILABLE'):
                video.inspect_video(b'fake')
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('ordinary core started process')):
            import ro_sprite_forge.cli
            with tempfile.TemporaryDirectory() as tmp:
                create_project(tmp, 'ordinary', 'Ordinary', 'actor', 'player')
                load_project(tmp, 'ordinary')
            if PILLOW:
                from ro_sprite_forge.core.ingestion import validate_png
                out = io.BytesIO()
                Image.new('RGBA', (1,1)).save(out, format='PNG')
                validate_png(out.getvalue())

    def test_missing_ffmpeg_after_probe(self):
        original = video.shutil.which
        with patch.object(video.shutil, 'which', side_effect=lambda name, **kw: None if name=='ffmpeg' else original(name, **kw)):
            if not shutil.which('ffprobe', path=os.defpath): self.skipTest('FFprobe absent')
            with self.assertRaisesRegex(ForgeError, 'VIDEO_TOOL_UNAVAILABLE: ffmpeg'):
                video.extract_candidates(b'fake', stream_index=None, mode='ordinal', values=[0])

    def test_malformed_selection_never_starts_tools(self):
        cases = [('ordinal', [], 'COUNT'), ('ordinal', [0]*65, 'COUNT'),
                 ('ordinal', [0,0], 'DUPLICATE'), ('ordinal', ['0; touch /tmp/pwn'], 'INVALID_SELECTION'),
                 ('ordinal', [True], 'INVALID_SELECTION'), ('ordinal', [2**54], 'INVALID_SELECTION'),
                 ('filter', [0], 'UNSUPPORTED_SELECTION')]
        with patch.object(video, '_tool', side_effect=AssertionError('tool called')):
            for mode, values, error in cases:
                with self.subTest(values=values), self.assertRaisesRegex(ForgeError, error):
                    video.extract_candidates(b'video', stream_index=None, mode=mode, values=values)

    def test_source_hash_empty_size_before_process(self):
        with patch.object(video, '_tool', side_effect=AssertionError('tool called')):
            with self.assertRaisesRegex(ForgeError, 'HASH_MISMATCH'):
                video.inspect_video(b'video', expected_sha256='0'*64)
            with self.assertRaisesRegex(ForgeError, 'SIZE_EXCEEDED_OR_EMPTY'):
                video.inspect_video(b'')
            with patch.object(video, 'MAX_BLOB_SIZE', 2), self.assertRaisesRegex(ForgeError, 'SIZE_EXCEEDED'):
                video.inspect_video(b'abc')

    def test_local_file_restrictions_and_safe_name(self):
        for p in ('https://host/video', '../video', 'file:///etc/passwd', 'a\x00b'):
            with self.assertRaisesRegex(ForgeError, 'LOCAL_FILE_REQUIRED'):
                video.read_local_video(p)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = base/'$(touch HACK); odd name.mkv'
            path.write_bytes(b'video')
            self.assertEqual(video.read_local_video(path), b'video')
            (base/'link').symlink_to(path)
            with self.assertRaisesRegex(ForgeError, 'SYMLINK_REJECTED'):
                video.read_local_video(base/'link')
            with self.assertRaisesRegex(ForgeError, 'LOCAL_FILE_REQUIRED'):
                video.read_local_video(base)
            self.assertFalse((base/'HACK').exists())

    def test_exact_missing_ambiguous_pts_are_not_invented(self):
        frames = {'frames':[dict(ordinal=0,pts=None),dict(ordinal=1,pts=40),dict(ordinal=2,pts=40)]}
        self.assertIsNone(video._resolve(frames,'ordinal',[0])[0]['pts'])
        for val in [0,40,41]:
            with self.assertRaisesRegex(ForgeError, 'SELECTION_NOT_EXACT'):
                video._resolve(frames,'pts',[val])
        self.assertIsNone(video._rational('N/A'))
        self.assertIsNone(video._rational('0/0'))
        self.assertEqual(video._rational('2/2000'), dict(numerator=2,denominator=2000))

    def test_runner_nonzero_output_cap_timeout_and_no_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            real_popen = subprocess.Popen
            with patch.object(subprocess, 'Popen', wraps=real_popen) as called:
                out,_ = video._run(sys.executable,['-c','import sys; print(sys.argv[1])','$(touch HACK);'],base)
                self.assertEqual(out.strip(),b'$(touch HACK);')
                self.assertFalse(called.call_args.kwargs['shell'])
                self.assertFalse((base/'HACK').exists())
            with self.assertRaisesRegex(ForgeError, 'PROCESS_FAILED: exit=7'):
                video._run(sys.executable,['-c','raise SystemExit(7)'],base)
            with patch.object(video,'MAX_CAPTURE',1024), self.assertRaisesRegex(ForgeError,'OUTPUT_EXCEEDED'):
                video._run(sys.executable,['-c','import sys; sys.stderr.write("x"*4096)'],base)
            with self.assertRaisesRegex(ForgeError,'PROCESS_TIMEOUT'):
                video._run(sys.executable,['-c','import time; time.sleep(10)'],base,timeout=.15)

    def test_timeout_kills_child_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            code = 'import os,time; p=os.fork(); open("pid-"+str(os.getpid()),"w").write(str(os.getpid())); time.sleep(20)'
            with self.assertRaisesRegex(ForgeError,'PROCESS_TIMEOUT'):
                video._run(sys.executable,['-c',code],base,timeout=.3)
            files = list(base.glob('pid-*'))
            self.assertEqual(len(files),2)
            for f in files:
                status = Path('/proc')/f.read_text()/'stat'
                # A dead grandchild may remain an init-owned zombie briefly; no live process.
                try:
                    is_dead = (not status.exists()) or (status.read_text().split()[2] == 'Z')
                except (FileNotFoundError, ProcessLookupError):
                    is_dead = True
                self.assertTrue(is_dead)

    def test_temp_disk_budget(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(video,'MAX_BLOB_SIZE',1), patch.object(video,'MAX_OUTPUT',1):
            with self.assertRaisesRegex(ForgeError,'TEMP_BUDGET_EXCEEDED'):
                video._run(sys.executable,['-c','import time; open("large","wb").write(b"x"*8192); time.sleep(1)'],Path(tmp))


@unittest.skipUnless(TOOLS and PILLOW, 'Optional FFmpeg/FFprobe and Pillow unavailable')
class MediaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='rsf-video-fixture-')
        cls.base = Path(cls.fixture.name)
        cls.expected, cls.commands = make_media(cls.base)
        cls.cfr = (cls.base/'cfr.mkv').read_bytes()
        cls.vfr = (cls.base/'vfr.mkv').read_bytes()
        cls.extracted = video.extract_candidates(cls.vfr,stream_index=0,mode='pts',values=[300,0,120])

    @classmethod
    def tearDownClass(cls): cls.fixture.cleanup()

    def test_cfr_actual_metadata(self):
        info = video.inspect_video(self.cfr)
        self.assertEqual([f['pts'] for f in info['frames']],[0,40,80,120,160])
        self.assertEqual(info['time_base'],dict(numerator=1,denominator=1000))
        self.assertEqual(info['timing'],'REGULAR_PTS_OBSERVED')
        self.assertEqual(info['streams'][0]['codec_name'],'ffv1')
        self.assertEqual(info['streams'][0]['r_frame_rate'],dict(numerator=25,denominator=1))
        self.assertEqual(info['source']['sha256'],digest(self.cfr))
        self.assertIsNone(info['streams'][0]['nb_frames'])
        self.assertEqual(info['decoded_frame_count'],5)

    def test_vfr_exact_pts_request_order_and_known_pixels(self):
        manifest = self.extracted['manifest']
        info = manifest['inspection']
        self.assertEqual([f['pts'] for f in info['frames']],[0,40,120,160,300])
        self.assertEqual(info['timing'],'IRREGULAR_PTS')
        self.assertEqual([i['ordinal'] for i in manifest['items']],[4,0,2])
        self.assertEqual([i['pts'] for i in manifest['items']],[300,0,120])
        for n, data, item in zip([4,0,2], self.extracted['pngs'],manifest['items']):
            with Image.open(io.BytesIO(data)) as image:
                self.assertEqual(image.mode,'RGBA')
                self.assertEqual(image.tobytes(),self.expected[n])
            self.assertEqual(item['rgba_sha256'],digest(self.expected[n]))
            self.assertEqual(item['png_sha256'],digest(data))
        self.assertEqual(manifest['visual_review'],'UNVERIFIED')
        self.assertFalse(manifest['automatic_assignment'])
        self.assertEqual(manifest['request']['synchronization'],'PASSTHROUGH')

    def test_ordinal_selection_matches_pts_without_using_fps(self):
        got = video.extract_candidates(self.vfr,stream_index=None,mode='ordinal',values=[4,0,2])
        self.assertEqual(got['pngs'],self.extracted['pngs'])
        self.assertEqual([i['pts'] for i in got['manifest']['items']],[300,0,120])

    def test_repeated_extraction_different_temp_roots_byte_identity(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(tempfile,'tempdir',tmp):
            repeated = video.extract_candidates(self.vfr,stream_index=0,mode='pts',values=[300,0,120])
            self.assertEqual(list(Path(tmp).iterdir()),[])
        self.assertEqual(repeated,self.extracted)
        self.assertEqual(canonical_bytes(repeated['manifest']),canonical_bytes(self.extracted['manifest']))

    def test_out_of_range_and_inexact_timestamp(self):
        for mode, value in [('pts',80),('pts',301),('ordinal',5),('ordinal',-1)]:
            with self.subTest(mode=mode,value=value), self.assertRaisesRegex(ForgeError,'SELECTION_NOT_EXACT'):
                video.extract_candidates(self.vfr,stream_index=0,mode=mode,values=[value])

    def test_bad_stream_invalid_video_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(tempfile,'tempdir',tmp):
            with self.assertRaisesRegex(ForgeError,'INVALID_STREAM'):
                video.inspect_video(self.cfr,stream_index=5)
            with self.assertRaisesRegex(ForgeError,'PROCESS_FAILED'):
                video.inspect_video(b'this is not video')
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_decode_pixel_frame_duration_budgets(self):
        for limit,value,diagnostic in [('MAX_FRAMES',2,'DECODE_BUDGET'),('MAX_DECODE_PIXELS',100,'DECODE_BUDGET'),('MAX_SECONDS',0,'DURATION_EXCEEDED')]:
            with self.subTest(limit=limit), patch.object(video,limit,value), self.assertRaisesRegex(ForgeError,diagnostic):
                video.inspect_video(self.cfr)
        with patch.object(video,'_dimensions',side_effect=ForgeError('INVALID_INPUT','VIDEO_DIMENSION_EXCEEDED')):
            with self.assertRaisesRegex(ForgeError,'DIMENSION_EXCEEDED'): video.inspect_video(self.cfr)

    def test_multiple_streams_require_explicit_selection(self):
        path = self.base/'multi.mkv'
        command = ['/usr/bin/ffmpeg','-nostdin','-v','error','-i',str(self.base/'cfr.mkv'),'-i',str(self.base/'vfr.mkv'),
                   '-map','0:v','-map','1:v','-c','copy','-y',str(path)]
        subprocess.run(command,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
        raw = path.read_bytes()
        with self.assertRaisesRegex(ForgeError,'STREAM_SELECTION_REQUIRED'): video.inspect_video(raw)
        info = video.inspect_video(raw,stream_index=1)
        self.assertEqual(len(info['streams']),2)
        self.assertEqual(info['stream_selection'],'EXPLICIT')
        self.assertEqual([f['pts'] for f in info['frames']],[0,40,120,160,300])
        got = video.extract_candidates(raw,stream_index=1,mode='ordinal',values=[4])
        with Image.open(io.BytesIO(got['pngs'][0])) as image: self.assertEqual(image.tobytes(),self.expected[4])

    def test_unsupported_codec_and_hdr_rejected(self):
        real = video._run
        for change, message in [({'codec_name':'rawvideo'},'UNSUPPORTED_DECODER'),({'color_transfer':'smpte2084'},'UNSUPPORTED_HDR'),({'pix_fmt':'yuv420p10le'},'UNSUPPORTED_DECODER')]:
            def altered(exe,args,directory,**kw):
                out,err = real(exe,args,directory,**kw)
                if '-of' in args and 'json' in args:
                    d = json.loads(out); d['streams'][0].update(change); out = json.dumps(d).encode()
                return out,err
            with self.subTest(change=change), patch.object(video,'_run',side_effect=altered), self.assertRaisesRegex(ForgeError,message):
                video.inspect_video(self.cfr)

    def test_wrong_output_count_corruption_and_native_pts_mismatch(self):
        real = video._run
        for kind,message in [('missing','OUTPUT_COUNT_MISMATCH'),('corrupt','PNG'),('pts','EXTRACTED_SELECTION_MISMATCH')]:
            def altered(exe,args,directory,**kw):
                out,err = real(exe,args,directory,**kw)
                if args and args[0]=='-nostdin':
                    files = sorted(directory.glob('frame-*.png'))
                    if kind=='missing': files[0].unlink()
                    if kind=='corrupt': files[0].write_bytes(b'invalid PNG')
                    if kind=='pts':
                        import re
                        err = re.sub(rb'(\bn:\s*0\s+pts:\s*)0\b',rb'\g<1>999',err)
                return out,err
            with self.subTest(kind=kind), patch.object(video,'_run',side_effect=altered), self.assertRaisesRegex(ForgeError,message):
                video.extract_candidates(self.cfr,stream_index=0,mode='ordinal',values=[0,2])

    def test_b_frame_presentation_order_uses_actual_pts(self):
        path=self.base/'reordered.mkv'
        command=['/usr/bin/ffmpeg','-nostdin','-v','error','-framerate','25','-i',str(self.base/'input-%02d.png'),
                 '-c:v','mpeg4','-bf','2','-q:v','2','-pix_fmt','yuv420p','-threads','1','-y',str(path)]
        subprocess.run(command,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
        raw=path.read_bytes()
        info=video.inspect_video(raw)
        self.assertIn('B',[f['picture_type'] for f in info['frames']])
        self.assertEqual([f['pts'] for f in info['frames']],[0,40,80,120,160])
        got=video.extract_candidates(raw,stream_index=0,mode='pts',values=[160,40,0])
        self.assertEqual([i['ordinal'] for i in got['manifest']['items']],[4,1,0])
        # Lossy MPEG4 is timing coverage; exact pixels are checked on lossless FFV1.
        self.assertEqual([i['pts'] for i in got['manifest']['items']],[160,40,0])

    def test_real_unsupported_codec(self):
        path=self.base/'unsupported.avi'
        subprocess.run(['/usr/bin/ffmpeg','-nostdin','-v','error','-i',str(self.base/'cfr.mkv'),
                        '-c:v','rawvideo','-pix_fmt','bgr24','-threads','1','-y',str(path)],
                       check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
        with self.assertRaisesRegex(ForgeError,'UNSUPPORTED_DECODER_OR_PIXEL_FORMAT'):
            video.inspect_video(path.read_bytes())

    def test_corrupt_committed_source_fails_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_project(tmp,'media','Media','actor','player')
            with patch('ro_sprite_forge.service.media.extract_candidates',return_value=self.extracted):
                staged=stage_video(tmp,'media',self.vfr,expected_revision=1,stream_index=0,mode='pts',values=[300,0,120])
            source=staged['sources'][digest(self.vfr)]
            blob=Path(tmp)/'media'/source['blob_path']
            blob.write_bytes(b'corrupted')
            with self.assertRaises(ForgeError): load_project(tmp,'media')

    def test_schema_closed_and_required_provenance(self):
        try: from jsonschema import Draft202012Validator
        except ImportError: self.skipTest('Optional jsonschema unavailable')
        from importlib.resources import files
        schema = json.loads(files('ro_sprite_forge').joinpath('schemas/video-candidates-v1.json').read_text())
        validator = Draft202012Validator(schema)
        validator.validate(self.extracted['manifest'])
        for field,value in [('automatic_assignment',True),('visual_review','APPROVED'),('unexpected',1)]:
            bad = copy.deepcopy(self.extracted['manifest']); bad[field]=value
            self.assertTrue(list(validator.iter_errors(bad)))

    def test_immutable_staging_reopen_idempotency_and_source_tray(self):
        from ro_sprite_forge.service.workbench import source_catalog
        with tempfile.TemporaryDirectory() as tmp:
            initial = create_project(tmp,'media','Media','actor','player')
            before = canonical_bytes(initial)
            raw = bytes(self.vfr)
            staged = stage_video(tmp,'media',raw,expected_revision=initial['revision'],stream_index=0,mode='pts',values=[300,0,120])
            self.assertEqual(raw,self.vfr)
            self.assertEqual(staged['revision'],initial['revision']+1)
            reopened = load_project(tmp,'media')
            self.assertEqual(reopened,staged)
            self.assertEqual(reopened['video_imports'],[self.extracted['manifest']])
            self.assertEqual(get_blob(tmp,'media',digest(raw)),raw)
            self.assertEqual([f['sha256'] for f in staged['sequences'][0]['frames']],
                             [i['png_sha256'] for i in self.extracted['manifest']['items']])
            catalog = source_catalog(tmp,staged)
            self.assertEqual(len(catalog),3)
            for record in catalog:
                self.assertEqual(record['source']['origin'],'UNVERIFIED')
                self.assertEqual(record['validation'],'VALID')
            for field in ('ledger','review_history','reviews','resources'):
                self.assertEqual(staged.get(field),initial.get(field))
            with patch('ro_sprite_forge.service.media.extract_candidates',return_value=self.extracted):
                again = stage_video(tmp,'media',raw,expected_revision=staged['revision'],stream_index=0,mode='pts',values=[300,0,120])
            self.assertEqual(again,staged)
            self.assertNotEqual(before,canonical_bytes(staged))

    def test_failed_batch_stale_and_publication_keep_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            initial = create_project(tmp,'media','Media','actor','player')
            manifest_file = Path(tmp)/'media'/'manifest.json'
            before = manifest_file.read_bytes()
            with self.assertRaisesRegex(ForgeError,'STALE_PROJECT_REVISION'):
                stage_video(tmp,'media',self.vfr,expected_revision=0,stream_index=0,mode='ordinal',values=[0])
            for failure in ['extract','png','save','race']:
                def extraction(*args,**kwargs):
                    if failure=='extract': raise ForgeError('INVALID_INPUT','VIDEO_PROCESS_FAILED')
                    result = copy.deepcopy(self.extracted)
                    if failure=='png': result['pngs'][1]=b'corrupt'
                    if failure=='race':
                        current = load_project(tmp,'media'); current['name']='Concurrent'; save_project(tmp,current,current['revision'])
                    return result
                with self.subTest(failure=failure), patch('ro_sprite_forge.service.media.extract_candidates',side_effect=extraction):
                    if failure=='save':
                        with patch('ro_sprite_forge.service.media.save_project',side_effect=ForgeError('IO_ERROR','COMMIT_FAILED')), self.assertRaisesRegex(ForgeError,'COMMIT_FAILED'):
                            stage_video(tmp,'media',self.vfr,expected_revision=1,stream_index=0,mode='pts',values=[300,0,120])
                    else:
                        with self.assertRaises(ForgeError): stage_video(tmp,'media',self.vfr,expected_revision=1,stream_index=0,mode='pts',values=[300,0,120])
                if failure!='race': self.assertEqual(manifest_file.read_bytes(),before)
            self.assertNotIn('video_imports',load_project(tmp,'media'))

    def test_cli_preview_inspect_stage_and_safe_filename(self):
        from contextlib import redirect_stdout, redirect_stderr
        from ro_sprite_forge.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = base/'$(touch HACK); candidate.mkv'; path.write_bytes(self.vfr)
            stdout = io.StringIO()
            with redirect_stdout(stdout): self.assertEqual(main(['video-inspect','--video',str(path)]),0)
            self.assertEqual(json.loads(stdout.getvalue())['source']['sha256'],digest(self.vfr))
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(main(['video-extract','--video',str(path),'--ordinal','4','--ordinal','0','--output-dir',str(base/'preview')]),0)
            self.assertEqual((base/'preview'/'candidate-0000.png').read_bytes(),self.extracted['pngs'][0])
            self.assertFalse((base/'HACK').exists())
            create_project(base/'projects','media','Media','actor','player')
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['video-stage','--video',str(path),'--ordinal','4','--projects-dir',str(base/'projects'),
                                       '--project-id','media','--expected-revision','1']),0)
            self.assertEqual(len(load_project(base/'projects','media')['video_imports'][0]['items']),1)
            with redirect_stderr(io.StringIO()):
                self.assertNotEqual(main(['video-extract','--video',str(path),'--pts','80','--output-dir',str(base/'bad')]),0)
            self.assertFalse((base/'bad').exists())


if __name__ == '__main__': unittest.main()

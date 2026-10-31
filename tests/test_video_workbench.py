"""RSF-29 real HTTP + independently constructed pixels, exact decimal transport."""
import base64
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from ro_sprite_forge.adapters import video
from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.errors import ForgeError, ErrorCode
from ro_sprite_forge.core.project import create_project, load_project, get_blob, save_project
from ro_sprite_forge.service import media
from ro_sprite_forge.service.server import create_server, MAX_REQUEST_BODY_SIZE
from test_video import make_media, TOOLS, PILLOW


class WireTests(unittest.TestCase):
    def test_large_pts_exact_decimal_transport_and_rejection(self):
        pts = 9007199254740993
        record = dict(pts=pts, time_base=dict(numerator=1, denominator=10000000000000001), unknown=None)
        encoded = media.wire_record(record)
        self.assertEqual(json.loads(json.dumps(encoded))['pts'], '9007199254740993')
        self.assertEqual(encoded['time_base']['denominator'], '10000000000000001')
        self.assertIsNone(encoded['unknown'])
        with self.assertRaisesRegex(ForgeError, 'INTEGER_OUT_OF_RANGE'):
            media.exact_integer(encoded['pts'])
        self.assertEqual(record['pts'], pts)

    def test_canonical_integer_boundary_and_invalid_inputs(self):
        for v in ('9007199254740991', '-9007199254740991', '0'):
            self.assertEqual(media.exact_integer(v), int(v))
        for v in ('00','-0','+1','1.0','1e3',' 1','1;echo BAD',1,True,None):
            with self.subTest(v=v), self.assertRaisesRegex(ForgeError, 'INVALID_SELECTION'):
                media.exact_integer(v)

    def test_browser_safe_preserves_booleans_and_small_ints(self):
        self.assertEqual(media.browser_safe([True,1,2**53+1,None]), [True,1,str(2**53+1),None])

    def test_media_does_not_start_process_on_import(self):
        with patch.object(video.subprocess, 'Popen', side_effect=AssertionError('unrequested process')):
            self.assertEqual(media.wire_record({'a':1}), {'a':'1'})
            from ro_sprite_forge.service.server import STATIC_DIR
            self.assertTrue((STATIC_DIR/'video.js').exists())


@unittest.skipUnless(TOOLS and PILLOW, 'Optional FFmpeg/FFprobe/Pillow unavailable')
class VideoHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='rsf29-http-')
        cls.base = Path(cls.temp.name); cls.root=cls.base/'projects'
        cls.expected, _ = make_media(cls.base)
        cls.raw=(cls.base/'vfr.mkv').read_bytes()
        cls.server=create_server(cls.root)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.serial=0

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()

    def setUp(self):
        type(self).serial+=1;self.pid='media-'+str(self.serial)
        self.original=create_project(self.root,self.pid,'Video','player','player')
        self.payload=dict(expected_revision=self.original['revision'], data_base64=base64.b64encode(self.raw).decode(),
            expected_sha256=digest(self.raw),stream_index='0',mode='pts',values=['300','0','120'])

    def req(self,operation='',data=None,method=None,path=None,headers=None):
        route=path or '/api/projects/'+self.pid+('/'+operation if operation else '')
        h={'Content-Type':'application/json','X-CSRF-Token':self.server.security.csrf_token}
        if headers is not None: h=headers
        request=urllib.request.Request(self.server.url+route, data=None if data is None else json.dumps(data).encode(),
            headers=h,method=method or ('POST' if data is not None else 'GET'))
        try:
            with urllib.request.urlopen(request,timeout=40) as r:return r.status,json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:return e.code,json.loads(e.read())

    def ok(self,operation='',data=None,**kw):
        status,result=self.req(operation,data,**kw);self.assertEqual(status,200,result);return result

    def preview(self):return self.ok('video-preview',self.payload)
    def stage(self):
        p=self.preview();return self.ok('video-stage',dict(self.payload,preview_sha256=p['manifest']['canonical_sha256']))
    def unchanged(self):self.assertEqual(load_project(self.root,self.pid),self.original)
    def bad(self,operation,data,message,status=422):
        code,result=self.req(operation,data);self.assertEqual(code,status,result);self.assertIn(message,result['error']['message']);self.unchanged()

    def test_capability_and_absence_without_breaking_core(self):
        self.assertTrue(self.ok(path='/api/video-capabilities')['available'])
        with patch.object(video.shutil,'which',return_value=None):
            cap=self.ok(path='/api/video-capabilities');self.assertFalse(cap['available'])
            self.assertIn('VIDEO_TOOL_UNAVAILABLE',cap['ffmpeg']['diagnostic'])
            self.bad('video-metadata',self.payload,'VIDEO_TOOL_UNAVAILABLE')
            self.assertEqual(self.ok(path='/api/health')['status'],'ok')
            self.assertEqual(self.ok()['project_id'],self.pid)

    def test_metadata_only_never_requests_frames(self):
        original=video._run;calls=[]
        def run(exe,args,*a,**kw):calls.append(args);return original(exe,args,*a,**kw)
        with patch.object(video,'_run',side_effect=run): info=self.ok('video-metadata',self.payload)
        self.assertFalse(any('-show_frames' in a for a in calls))
        self.assertEqual(info['source']['sha256'],digest(self.raw))
        self.assertEqual(info['streams'][0]['index'],'0');self.assertEqual(info['streams'][0]['codec_name'],'ffv1')
        self.unchanged()

    def test_vfr_frames_exact_time_base_and_ordinals(self):
        info=self.ok('video-frames',self.payload)
        self.assertEqual([f['pts'] for f in info['frames']],['0','40','120','160','300'])
        self.assertEqual([f['ordinal'] for f in info['frames']],list(map(str,range(5))))
        self.assertEqual(info['time_base'],dict(numerator='1',denominator='1000'))
        self.assertEqual(info['timing'],'IRREGULAR_PTS');self.unchanged()

    def test_audio_first_absolute_stream_index(self):
        import subprocess
        output=self.base/(self.pid+'.mkv')
        subprocess.run(['/usr/bin/ffmpeg','-nostdin','-v','error','-f','lavfi','-i','anullsrc=r=8000:cl=mono',
            '-i',str(self.base/'vfr.mkv'),'-map','0:a','-map','1:v','-c:a','pcm_s16le','-c:v','copy','-t','0.4',str(output)],check=True,capture_output=True,timeout=15)
        raw=output.read_bytes();p=dict(self.payload,data_base64=base64.b64encode(raw).decode(),expected_sha256=digest(raw),stream_index='1')
        info=self.ok('video-metadata',p);self.assertEqual(info['streams'][0]['index'],'1')
        result=self.ok('video-preview',p);self.assertEqual(result['manifest']['request']['stream'],'1')
        self.bad('video-frames',dict(p,stream_index='0'),'INVALID_STREAM')

    def test_multivideo_stream_metadata_then_explicit_choice(self):
        import subprocess
        output=self.base/(self.pid+'-multi.mkv')
        subprocess.run(['/usr/bin/ffmpeg','-nostdin','-v','error','-i',str(self.base/'vfr.mkv'),'-map','0:v','-map','0:v','-c','copy',str(output)],check=True,capture_output=True,timeout=15)
        raw=output.read_bytes();p=dict(self.payload,data_base64=base64.b64encode(raw).decode(),expected_sha256=digest(raw))
        self.assertEqual([s['index'] for s in self.ok('video-metadata',p)['streams']],['0','1'])
        self.bad('video-frames',dict(p,stream_index=''),'INVALID_SELECTION')
        self.assertEqual(self.ok('video-frames',dict(p,stream_index='1'))['selected_stream'],'1')

    def test_nonchronological_preview_actual_pngs_without_commit(self):
        from PIL import Image
        result=self.preview();manifest=result['manifest']
        self.assertEqual([i['ordinal'] for i in manifest['items']],['4','0','2'])
        self.assertEqual([i['requested'] for i in manifest['items']],['300','0','120'])
        self.assertEqual([i['pts'] for i in manifest['items']],['300','0','120'])
        for expected,encoded,item in zip([4,0,2],result['pngs'],manifest['items']):
            raw=base64.b64decode(encoded)
            with Image.open(io.BytesIO(raw)) as image:self.assertEqual(image.convert('RGBA').tobytes(),self.expected[expected])
            self.assertEqual(digest(raw),item['png_sha256'])
        self.unchanged();self.assertEqual(list((self.root/self.pid/'blobs').rglob('*')),[])

    def test_ordinal_mode_exact_requested_and_resolved(self):
        result=self.ok('video-preview',dict(self.payload,mode='ordinal',values=['4','0','2']))
        self.assertEqual([i['pts'] for i in result['manifest']['items']],['300','0','120'])
        self.assertEqual([i['requested'] for i in result['manifest']['items']],['4','0','2'])

    def test_reorder_changes_collection_only_not_pngs_or_pts(self):
        first=self.preview()['manifest'];second=self.ok('video-preview',dict(self.payload,values=['120','300','0']))['manifest']
        self.assertNotEqual(first['canonical_sha256'],second['canonical_sha256'])
        def identity(m):return {i['pts']:i['png_sha256'] for i in m['items']}
        self.assertEqual(identity(first),identity(second));self.unchanged()

    def test_stage_idempotent_save_reopen_and_source_tray(self):
        result=self.stage();m=load_project(self.root,self.pid)
        self.assertEqual([i['pts'] for i in m['video_imports'][0]['items']],[300,0,120])
        self.assertEqual(get_blob(self.root,self.pid,digest(self.raw)),self.raw)
        before=canonical_bytes(m)
        p=dict(self.payload,expected_revision=m['revision'],preview_sha256=result['collection']['canonical_sha256'])
        self.ok('video-stage',p);self.assertEqual(canonical_bytes(load_project(self.root,self.pid)),before)
        workspace=self.ok('workspace');self.assertEqual(len(workspace['sources']),3)
        self.assertFalse(m.get('ledger'));self.assertFalse(m.get('review_events'));self.assertEqual(m['video_imports'][0]['visual_review'],'UNVERIFIED')
        save=self.ok(data={'project':self.ok(),'expected_revision':m['revision']},method='PUT')
        self.assertEqual(load_project(self.root,self.pid)['video_imports'],m['video_imports'])
        self.assertEqual(save['revision'],m['revision']+1)

    def test_staged_video_can_be_selected_by_identity(self):
        self.stage();m=load_project(self.root,self.pid)
        imports=self.ok('video-imports');self.assertEqual(imports['sources'][0]['sha256'],digest(self.raw))
        p=dict(self.payload,expected_revision=m['revision'],source_sha256=digest(self.raw));del p['data_base64']
        self.assertEqual(self.ok('video-preview',p)['manifest'],self.preview_with_revision(m['revision'])['manifest'])

    def preview_with_revision(self,r):return self.ok('video-preview',dict(self.payload,expected_revision=r))

    def test_stale_revision_rejected_before_decoder(self):
        with patch.object(video,'_tool',side_effect=AssertionError('decoded stale request')):
            self.bad('video-preview',dict(self.payload,expected_revision=999),'STALE_PROJECT_REVISION',409)

    def test_changed_preview_identity_rejected_before_publication(self):
        self.bad('video-stage',dict(self.payload,preview_sha256='0'*64),'PREVIEW_IDENTITY_CHANGED')
        self.bad('video-stage',self.payload,'PREVIEW_REQUIRED')

    def test_source_hash_and_invalid_preview_failures(self):
        self.bad('video-preview',dict(self.payload,expected_sha256='0'*64),'SOURCE_HASH_MISMATCH')
        self.bad('video-preview',dict(self.payload,data_base64='!!'),'INVALID_BASE64')
        self.bad('video-preview',dict(self.payload,source_sha256=digest(self.raw)),'AMBIGUOUS_SOURCE')
        self.bad('video-preview',dict(self.payload,url='https://example.com/video'),'LOCAL_BYTES_REQUIRED')

    def test_invalid_exact_selection_and_stream(self):
        for changes,diag in [({'values':['41']},'SELECTION_NOT_EXACT'),({'mode':'ordinal','values':['5']},'SELECTION_NOT_EXACT'),
            ({'values':['-1']},'SELECTION_NOT_EXACT'),({'values':['0','0']},'DUPLICATE_SELECTION'),
            ({'stream_index':'9'},'INVALID_STREAM'),({'values':[]},'COUNT_EXCEEDED_OR_EMPTY'),
            ({'values':[300]},'INVALID_SELECTION'),({'mode':'nearest'},'UNSUPPORTED_SELECTION')]:
            with self.subTest(changes=changes):self.bad('video-preview',dict(self.payload,**changes),diag)

    def test_large_pts_request_never_rounds_or_commits(self):
        with patch.object(video,'_tool',side_effect=AssertionError('unsupported value reached decoder')):
            self.bad('video-preview',dict(self.payload,values=['9007199254740993']),'INTEGER_OUT_OF_RANGE')
        # Synthetic decoded metadata is wire-tested separately from actual media.
        with patch.object(video,'inspect_video',return_value={'frames':[{'pts':9007199254740993}], 'time_base':{'numerator':1,'denominator':1000}}):
            self.assertEqual(self.ok('video-frames',self.payload)['frames'][0]['pts'],'9007199254740993')

    def test_int64_metadata_survives_generic_http_save_reopen(self):
        self.stage();m=load_project(self.root,self.pid);record=m['video_imports'][0]
        # Isolated synthetic unknown metadata: accepted schema integer, not selected PTS.
        record['inspection']['frames'][0]['packet_dts']=9007199254740993
        from ro_sprite_forge.core.canonical import sealed
        record['inspection']=sealed({k:v for k,v in record['inspection'].items() if k!='canonical_sha256'})
        m['video_imports'][0]=sealed({k:v for k,v in record.items() if k!='canonical_sha256'})
        m=save_project(self.root,m,m['revision'])
        transported=self.ok();self.assertEqual(transported['video_imports'][0]['inspection']['frames'][0]['packet_dts'],'9007199254740993')
        self.ok(data={'project':transported,'expected_revision':m['revision']},method='PUT')
        reopened=load_project(self.root,self.pid)
        self.assertEqual(reopened['video_imports'][0]['inspection']['frames'][0]['packet_dts'],9007199254740993)

    def test_video_provenance_cannot_be_fabricated_via_generic_save(self):
        p=copy.deepcopy(self.original);p['video_imports']=[{}]
        code,result=self.req(data={'project':p,'expected_revision':p['revision']},method='PUT')
        self.assertEqual(code,422,result);self.assertIn('video provenance is immutable',result['error']['message']);self.unchanged()

    def test_extraction_failure_does_not_commit(self):
        with patch.object(video,'extract_candidates',side_effect=ForgeError(ErrorCode.INVALID_INPUT,'VIDEO_PROCESS_FAILED')):
            self.bad('video-preview',self.payload,'VIDEO_PROCESS_FAILED')
        with patch.object(media,'extract_candidates',side_effect=ForgeError(ErrorCode.INVALID_INPUT,'VIDEO_PROCESS_FAILED')):
            self.bad('video-stage',dict(self.payload,preview_sha256='0'*64),'VIDEO_PROCESS_FAILED')

    def test_csrf_origin_and_host_security(self):
        for h in ({'Content-Type':'application/json'}, {'X-CSRF-Token':self.server.security.csrf_token,'Origin':'https://evil.test'}):
            code,result=self.req('video-metadata',self.payload,headers=h);self.assertEqual(code,403,result)
        self.unchanged()

    def test_http_size_and_selection_count_bounds(self):
        with patch('ro_sprite_forge.service.server.MAX_REQUEST_BODY_SIZE',100):
            code,result=self.req('video-preview',self.payload);self.assertEqual(code,413,result)
        self.bad('video-preview',dict(self.payload,values=list(map(str,range(65)))),'COUNT_EXCEEDED_OR_EMPTY')

    def test_png_workflow_works_when_video_tools_absent(self):
        raw=(self.base/'input-00.png').read_bytes()
        with patch.object(video.shutil,'which',return_value=None):
            self.ok('stage-png',dict(expected_revision=self.original['revision'],filename='operator.png',data_base64=base64.b64encode(raw).decode()))
        self.assertEqual(len(self.ok('workspace')['sources']),1)

    def test_assignment_and_runtime_timing_do_not_change_video_provenance(self):
        from ro_sprite_forge.service.workbench import mutate, workspace, preview
        from test_workbench import make_target_doc
        from test_inventory import resources
        self.stage();m=load_project(self.root,self.pid)
        target=make_target_doc(self.pid,frame_count=3)
        for view in target['actions'][0]['parts'][0]['views']:view['topology']['layers']=['body']
        m=mutate(self.root,m,'target',dict(expected_revision=m['revision'],target=target))['project']
        act,spr=resources(slots=40,frames=3)
        m=mutate(self.root,m,'import-pair',dict(expected_revision=m['revision'],id='body',part='body',act_base64=base64.b64encode(act).decode(),spr_base64=base64.b64encode(spr).decode()))['project']
        w=workspace(self.root,m);sha=m['video_imports'][0]['items'][0]['png_sha256']
        m=mutate(self.root,m,'assign',dict(expected_revision=m['revision'],mappings=[dict(requirement_id=w['requirements']['layers'][0]['id'],kind='DIRECT_SOURCE',source='blob-'+sha,source_revision=1,recipe=[])]))['project']
        before=canonical_bytes(m['video_imports']);original_timing=m['target']
        results=[preview(self.root,m,dict(resource='body',slot=8,view=0,frame=0,elapsed_ms=150,context=dict(movement_speed=s))) for s in [100,250]]
        self.assertNotEqual(results[0]['report']['selection']['frame_time'],results[1]['report']['selection']['frame_time'])
        self.assertEqual(canonical_bytes(load_project(self.root,self.pid)['video_imports']),before)
        self.assertEqual(m['target'],original_timing);self.assertIsNone(m['ledger']['assignments'][0]['review'])

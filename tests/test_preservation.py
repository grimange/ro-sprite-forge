"""Independent ACT 2.4 golden layout and controlled one-field binary mutations."""

import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.core.preservation import roundtrip_pair
from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.formats.spr import read_spr
from ro_sprite_forge.report_io import publish_resources


def golden():
    # Constructed without either production writer or their field-name constants.
    header = b'AC\x04\x02\x02\x00' + bytes(range(10))
    bounds = struct.pack('<8i', -1, 2, -3, 4, -5, 6, -7, 8)
    c0 = struct.pack('<iiiIIffiI', 12, -23, 0, 0, 0x12345678, 1.25, 0.5, -30, 0)
    c1 = struct.pack('<iiiIIffiI', -42, 17, 0, 1, 0x87654321, 2.0, -1.0, 90, 1)
    c2 = struct.pack('<iiiIIffiI', 5, 6, 1, 0, 0xFFFFFFFF, 1.0, 1.0, 0, 0)
    hidden = struct.pack('<iiiIIffiI', 7, 8, -1, 7, 0, 1.0, 1.0, 360, 99)
    anchor = struct.pack('<IiiI', 0xDEADBEEF, -9, 10, 0xCAFEBABE)
    m0 = bounds + struct.pack('<I', 2) + c0 + c1 + struct.pack('<iI', 0, 1) + anchor
    m1 = bounds + struct.pack('<I', 1) + c2 + struct.pack('<iI', -1, 1) + anchor
    m2 = bounds + struct.pack('<I', 1) + hidden + struct.pack('<iI', 1, 0)
    events = bytes(range(40)) + bytes(range(40, 80))  # Includes opaque bytes after NUL.
    data = header + struct.pack('<I', 2) + m0 + m1 + struct.pack('<I', 1) + m2
    data += struct.pack('<I', 2) + events + struct.pack('<ff', 4.0, 6.25)
    assert len(data) == 424
    return data


def expected():
    def clip(x, y, sprite, mirror, color, sx, sy, angle, pool):
        return dict(x=x,y=y,sprite=sprite,mirror=mirror,color=color,scale_x=sx,scale_y=sy,angle=angle,pool=pool)
    def motion(clips, event, anchors):
        return dict(bounds=[-1,2,-3,4,-5,6,-7,8],clips=clips,event=event,anchors=anchors)
    anchor = dict(opaque=0xDEADBEEF,x=-9,y=10,attribute=0xCAFEBABE)
    return dict(reserved=bytes(range(10)).hex(), actions=[[
        motion([clip(12,-23,0,0,0x12345678,1.25,0.5,-30,0),clip(-42,17,0,1,0x87654321,2.,-1.,90,1)],0,[anchor.copy()]),
        motion([clip(5,6,1,0,0xFFFFFFFF,1.,1.,0,0)],-1,[anchor.copy()])],
        [motion([clip(7,8,-1,7,0,1.,1.,360,99)],1,[])]],
        events=[bytes(range(40)).hex(),bytes(range(40,80)).hex()],delays=[4.,6.25])


def sprite(kind='mixed'):
    # Three indexed identities (last unused), raw zero-run variants and nonzero palette.
    indexed = b''.join(struct.pack('<HHH',2,1,3)+bytes([i,0,0]) for i in (1,2,3))
    rgba = struct.pack('<HH',1,1)+bytes([255,3,2,1])
    if kind == 'indexed':
        return b'SP\x01\x02'+struct.pack('<HH',3,0)+indexed+bytes(range(256))*4
    if kind == 'truecolor':
        return b'SP\x01\x02'+struct.pack('<HH',0,1)+rgba+bytes(range(256))*4
    return b'SP\x01\x02'+struct.pack('<HH',3,1)+indexed+rgba+bytes(range(256))*4


class SemanticTests(unittest.TestCase):
    def test_independent_golden_complete_fields(self):
        self.assertEqual(read_act(golden()), expected())
        self.assertEqual(write_act(expected()), golden())
        self.assertEqual(write_act(read_act(golden())), golden())

    def test_single_field_mutations_independent_offsets(self):
        # Literal offsets from golden record layout, independent of production reader.
        cases = [
            (('actions',0,0,'clips',1,'x'),92,'i',-51),
            (('actions',0,0,'clips',1,'y'),96,'i',-19),
            (('actions',0,0,'clips',1,'mirror'),104,'I',0),
            (('actions',0,0,'clips',1,'color'),108,'I',0x01020304),
            (('actions',0,0,'clips',1,'scale_x'),112,'f',3.5),
            (('actions',0,0,'clips',1,'scale_y'),116,'f',0.25),
            (('actions',0,0,'clips',1,'angle'),120,'i',-120),
            (('actions',0,0,'clips',0,'sprite'),64,'i',1),
            (('actions',0,0,'clips',0,'pool'),88,'I',1),
            (('actions',0,0,'bounds',0),20,'i',-100),
            (('actions',0,0,'anchors',0,'x'),140,'i',-81),
            (('actions',0,0,'anchors',0,'y'),144,'i',-82),
            (('actions',0,0,'anchors',0,'opaque'),136,'I',42),
            (('actions',0,0,'anchors',0,'attribute'),148,'I',43),
            (('actions',0,0,'event'),128,'i',1),
            (('delays',1),420,'f',2.5),
            (('events',1),376,'40s',b'new.wav\x00'+bytes(range(32))),
            (('reserved',),6,'10s',bytes(range(10,20))),
        ]
        for path, offset, fmt, value in cases:
            with self.subTest(path=path):
                model = copy.deepcopy(expected())
                node = model
                for key in path[:-1]: node = node[key]
                node[path[-1]] = value.hex() if fmt.endswith('s') else value
                independently_patched = bytearray(golden())
                struct.pack_into('<'+fmt, independently_patched, offset, value)
                output = write_act(model)
                self.assertEqual(output, independently_patched)  # EVERY unrelated byte.
                self.assertEqual(struct.unpack_from('<'+fmt,output,offset)[0],value)
                reparsed = read_act(output)
                self.assertEqual(reparsed,model)
                self.assertEqual(write_act(model),output)
                self.assertEqual(roundtrip_pair(output,sprite())[0],output)

    def test_layout_changing_anchor_insertion(self):
        model = expected()
        model['actions'][0][0]['anchors'].append(dict(opaque=11,x=-12,y=13,attribute=14))
        output = write_act(model)
        patched = bytearray(golden())
        struct.pack_into('<I',patched,132,2)
        patched[152:152] = struct.pack('<IiiI',11,-12,13,14)
        self.assertEqual(output,patched)
        self.assertEqual(read_act(output),model)
        self.assertEqual(roundtrip_pair(output,sprite())[0],output)

    def test_every_truncation_rejected(self):
        for end in range(len(golden())):
            with self.subTest(end=end),self.assertRaises(ForgeError):read_act(golden()[:end])

    def test_writer_rejects_malformed_edits(self):
        cases = []
        for value in ('00', 'zz', '00'*41):
            doc=expected();doc['events'][0]=value;cases.append(doc)
        for field,value in [('x',2**31),('scale_x',float('nan')),('scale_y',1e100),('sprite',-2)]:
            doc=expected();doc['actions'][0][0]['clips'][0][field]=value;cases.append(doc)
        doc=expected();doc['actions'][0][0]['event']=2;cases.append(doc)
        doc=expected();doc['delays'][0]=0;cases.append(doc)
        doc=expected();doc['unknown']='not silently dropped';cases.append(doc)
        doc=expected();doc['actions'][0][0]['clips'][0]['unknown']=1;cases.append(doc)
        doc=expected();doc['actions'][0][0]['anchors']*=65;cases.append(doc)
        for doc in cases:
            with self.subTest(doc=doc), self.assertRaises(ForgeError): write_act(doc)


class PreservationTests(unittest.TestCase):
    def test_modes_and_indexed_mixed_unused_representation(self):
        for mode in ('preserve','act-semantic'):
            a,s,r=roundtrip_pair(golden(),sprite(),mode=mode)
            self.assertEqual((a,s),(golden(),sprite()))
            self.assertEqual(r['summary']['stored_images'],4)
            self.assertEqual(r['summary']['unused_images'],1)
            self.assertEqual(r['summary']['visible_layer_references'],3)
            self.assertEqual(canonical_bytes(r),canonical_bytes(roundtrip_pair(golden(),sprite(),mode=mode)[2]))
        for kind in ('indexed','truecolor'):
            # Empty clips valid for both pools; verify original palette even for RGBA.
            model=expected()
            for action in model['actions']:
                for m in action:m['clips']=[]
            raw=write_act(model)
            self.assertEqual(roundtrip_pair(raw,sprite(kind))[:2],(raw,sprite(kind)))
            self.assertEqual(read_spr(sprite(kind)).palette,bytes(range(256))*4)

    def test_unsupported_and_invalid_inputs(self):
        for mode in ('rgba','indexed-write','remap'):
            with self.assertRaises(ForgeError): roundtrip_pair(golden(),sprite(),mode=mode)
        for a,s in ((golden()[:-1],sprite()),(golden(),sprite()[:-1]),(golden()+b'x',sprite())):
            with self.assertRaises(ForgeError):roundtrip_pair(a,s)
        for field,value in (('sprite',99),('pool',9)):
            doc=expected();doc['actions'][0][0]['clips'][0][field]=value
            with self.assertRaises(ForgeError):roundtrip_pair(write_act(doc),sprite())

    def test_publication_failure_cleanup_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=root/'a';s=root/'s';s.write_bytes(b'existing')
            with self.assertRaises(ForgeError):publish_resources(((str(a),golden()),(str(s),sprite())))
            self.assertFalse(a.exists());self.assertEqual(s.read_bytes(),b'existing')
            self.assertEqual(sorted(p.name for p in root.iterdir()),['s'])
            with patch('ro_sprite_forge.report_io.read_bytes',return_value=b'bad'):
                with self.assertRaises(ForgeError):publish_resources(((str(a),golden()),))
            self.assertFalse(a.exists())

    def test_cli_modes_hashes_source_immutability_and_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=root/'source.act';s=root/'source.spr'
            a.write_bytes(golden());s.write_bytes(sprite())
            def run(*args):
                return subprocess.run([sys.executable,'-I','-m','ro_sprite_forge',*map(str,args)],capture_output=True,text=True,cwd=tmp)
            first=run('verify','--act',a,'--spr',s)
            self.assertEqual(first.returncode,0,first.stderr)
            self.assertEqual(json.loads(first.stdout)['checks']['rust_oracle'],'NOT_RUN')
            for i,mode in enumerate(('preserve','act-semantic','preserve')):
                oa=root/f'{i}.act';os=root/f'{i}.spr'
                result=run('roundtrip','--act',a,'--spr',s,'--output-act',oa,'--output-spr',os,'--mode',mode)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual((oa.read_bytes(),os.read_bytes()),(golden(),sprite()))
                report=json.loads(result.stdout)
                self.assertEqual(report['resources']['act']['input_sha256'],digest(golden()))
                self.assertEqual(report['resources']['spr']['output_sha256'],digest(sprite()))
            bad=run('roundtrip','--act',a,'--spr',s,'--output-act',a,'--output-spr',root/'absent')
            self.assertEqual(bad.returncode,3);self.assertFalse((root/'absent').exists())
            bad=run('roundtrip','--act',a,'--spr',s,'--output-act',root/'bad.act','--output-spr',root/'bad.spr','--mode','rgba')
            self.assertEqual(bad.returncode,2);self.assertFalse((root/'bad.act').exists())
            self.assertEqual((a.read_bytes(),s.read_bytes()),(golden(),sprite()))
            a.write_bytes(golden()[:-1])
            bad=run('roundtrip','--act',a,'--spr',s,'--output-act',root/'bad.act','--output-spr',root/'bad.spr')
            self.assertEqual(bad.returncode,3);self.assertEqual(bad.stdout,'')
            self.assertFalse((root/'bad.act').exists());self.assertFalse((root/'bad.spr').exists())

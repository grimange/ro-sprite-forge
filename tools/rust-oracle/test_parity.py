"""Executable public cross-language tests, no private art required."""
import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests'))
from test_preservation import golden, sprite, expected
from parity import compare, differences, python_report, sha

ORACLE = Path(__file__).parent/'target/debug/rsf-rust-oracle'

class ParityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Path(self.tmp.name)/'source.act';self.s=Path(self.tmp.name)/'source.spr'
    def run_pair(self,a,s):
        self.a.write_bytes(a);self.s.write_bytes(s)
        return compare(ORACLE.resolve(),self.a,self.s)
    def reject(self,a,s):
        self.a.write_bytes(a);self.s.write_bytes(s)
        with self.assertRaises(Exception):python_report(a,s)
        r=subprocess.run([str(ORACLE.resolve()),str(self.a),str(self.s)],capture_output=True)
        self.assertEqual(r.returncode,3,r.stderr)
        self.assertFalse(r.stdout)
    def test_golden_fields_and_determinism(self):
        a,s=golden(),sprite();r=self.run_pair(a,s)
        self.assertEqual(r['result'],'AGREEMENT',r['mismatches'])
        self.assertEqual(r,self.run_pair(a,s))
        self.assertEqual(self.a.read_bytes(),a);self.assertEqual(self.s.read_bytes(),s)
        p=python_report(a,s)
        self.assertEqual(p['act']['events'],expected()['events'])
        self.assertEqual(r['python_summary']['unused'],[[0,2]])
    def test_minimal_and_single_pools(self):
        minimal=b'AC\x04\x02\x01\0'+bytes(10)+bytes(8)+struct.pack('<f',1)
        for kind in ('indexed','truecolor','mixed'):
            self.assertEqual(self.run_pair(minimal,sprite(kind))['result'],'AGREEMENT')
    def test_truecolor_orientation_alpha(self):
        a=b'AC\x04\x02\x01\0'+bytes(10)+bytes(8)+struct.pack('<f',1)
        # Bottom row then top row, ABGR. Hidden RGB under alpha zero preserved.
        s=b'SP\x01\x02'+struct.pack('<HHHH',0,1,2,2)+bytes(range(16))+bytes(1024)
        p=python_report(a,s)
        self.assertEqual(p['spr']['images'][0]['rgba'],bytes([11,10,9,8,15,14,13,12,3,2,1,0,7,6,5,4]).hex())
        self.assertEqual(self.run_pair(a,s)['result'],'AGREEMENT')
    def test_all_truncated_act(self):
        for n in range(len(golden())):
            with self.subTest(n=n):self.reject(golden()[:n],sprite())
    def test_truncated_spr(self):
        for n in range(len(sprite())):
            with self.subTest(n=n):self.reject(golden(),sprite()[:n])
    def test_independent_invalid_fields(self):
        # Literal golden offsets; invalid by declared format/pair contract.
        for offset,fmt,value in [(2,'B',5),(4,'H',0),(16,'I',4097),(52,'I',1025),
                                 (64,'i',3),(88,'I',2),(128,'i',2),(132,'I',65),
                                 (76,'I',0x7f800000),(416,'f',0.)]:
            a=bytearray(golden());struct.pack_into('<'+fmt,a,offset,value)
            self.reject(a,sprite())
        self.reject(golden()+b'x',sprite());self.reject(golden(),sprite()+b'x')
    def test_invalid_spr(self):
        for raw in [b'SP\x02\x02'+bytes(1028), b'SP\x01\x02'+struct.pack('<HH',4097,0),
                    b'SP\x01\x02'+struct.pack('<HHHHH',1,0,0,1,0)+bytes(1024),
                    b'SP\x01\x02'+struct.pack('<HHHHH',1,0,65535,65535,0)+bytes(1024),
                    b'SP\x01\x02'+struct.pack('<HHHHH',1,0,1,1,1)+b'\0'+bytes(1024),
                    b'SP\x01\x02'+struct.pack('<HHHHH',1,0,1,1,2)+b'\0\2'+bytes(1024),
                    b'SP\x01\x02'+struct.pack('<HHHHH',1,0,2,1,1)+b'\1'+bytes(1024)]:
            self.reject(golden(),raw)
    def test_shared_image_reference(self):
        a=bytearray(golden());struct.pack_into('<i',a,196,0)
        # Second motion clip starts at188, sprite field at196: share first image.
        r=self.run_pair(bytes(a),sprite())
        self.assertEqual(r['result'],'AGREEMENT')
        self.assertEqual(r['rust_summary']['referenced'],2)
        self.assertEqual(r['rust_summary']['unused'],[[0,1],[0,2]])

    def test_aggregate_pixel_budget(self):
        # 65 independently valid 1M-pixel RLE images exceed the 64M pair budget.
        encoded = b'\0\xff'*4112 + b'\0\x10'
        self.assertEqual(4112*255+16,1048576)
        image=struct.pack('<HHH',1024,1024,len(encoded))+encoded
        s=b'SP\x01\x02'+struct.pack('<HH',65,0)+image*65+bytes(1024)
        self.reject(golden(),s)

    def test_valid_raw_field_mutations(self):
        for offset,fmt,value in [(56,'i',-999),(60,'i',999),(68,'I',7),(72,'I',0x01020304),
                                 (76,'I',0x80000000),(80,'f',0.25),(84,'i',-360),
                                 (64,'i',1),(88,'I',1),(20,'i',-123),
                                 (136,'I',7),(140,'i',-88),(144,'i',77),(148,'I',42),
                                 (128,'i',1),(420,'f',2.5)]:
            a=bytearray(golden());struct.pack_into('<'+fmt,a,offset,value)
            self.assertEqual(self.run_pair(bytes(a),sprite())['result'],'AGREEMENT')

    def test_mismatch_locations_and_omissions(self):
        p=python_report(golden(),sprite());r=copy.deepcopy(p)
        r['act']['actions'][0][0]['clips'][1]['x']+=1
        d=differences(p,r);self.assertEqual(d[0]['location'],'$.act.actions[0][0].clips[1].x')
        del r['act']['events'];self.assertTrue(any(v.get('missing') for v in differences(p,r)))
        r=copy.deepcopy(p);r['act']['actions'][0][0]['clips'].reverse();self.assertTrue(differences(p,r))

if __name__=='__main__':unittest.main(verbosity=2)

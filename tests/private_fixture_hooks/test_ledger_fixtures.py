"""Private imported topology never silently becomes replacement artwork."""
import unittest
from ro_sprite_forge.core.canonical import canonical_bytes
from ro_sprite_forge.core.ledger import load_ledger, resolve_ledger
from ro_sprite_forge.core.topology import resolve_topology
from test_topology_fixtures import reference_requirements


class PrivateLedgerTests(unittest.TestCase):
    def check(self, category, pairs, frames, layers):
        a,p,t,inventories=reference_requirements(category,pairs)
        before=[canonical_bytes(i) for i in inventories]
        req=resolve_topology(t,actor=a,profile=p,inventories=tuple(inventories))
        ledger=load_ledger({'schema':'rsf.assignment-ledger/v1','id':'audited-unassigned',
            'revision':1,'previous_sha256':None,'target':req['target'],
            'requirements_sha256':req['canonical_sha256'],'sources':[],'assignments':[],
            'attachments':[]},requirements=req)
        report=resolve_ledger(ledger,requirements=req)
        self.assertEqual(len(req['frames']),frames);self.assertEqual(len(req['layers']),layers)
        self.assertEqual(report['counts']['unassigned'],layers)
        self.assertEqual(report['counts']['validated_replacement_occurrences'],0)
        self.assertEqual(report['counts']['approved_source_art_roots'],0)
        self.assertTrue(all(o['visual_review']=='UNVERIFIED' for o in report['occurrences']))
        self.assertEqual(before,[canonical_bytes(i) for i in inventories])
        self.assertEqual(canonical_bytes(report),canonical_bytes(resolve_ledger(ledger,requirements=req)))
        return report

    def test_novice_body_and_head_remain_separate_unassigned(self):
        r=self.check('player',[('body','novice_body'),('head','novice_head')],912,912)
        self.assertEqual({o['binding']['part'] for o in r['occurrences']},{'body','head'})

    def test_orc_multilayer_ids_preserved_no_implicit_art(self):
        r=self.check('monster',[('body','orc_skeleton')],512,1776)
        self.assertEqual(len({o['requirement_id'] for o in r['occurrences']}),1776)

"""Private fixture coverage evaluation: imported reference never becomes replacement art."""
import unittest

from ro_sprite_forge.core.canonical import canonical_bytes
from ro_sprite_forge.core.coverage import evaluate_coverage, format_work_order
from ro_sprite_forge.core.topology import resolve_topology
from test_topology_fixtures import reference_requirements


class PrivateCoverageTests(unittest.TestCase):
    def check_coverage(self, category, pairs, frames, layers):
        a, p, t, inventories = reference_requirements(category, pairs)
        before = [canonical_bytes(i) for i in inventories]
        req = resolve_topology(t, actor=a, profile=p, inventories=tuple(inventories))
        cov = evaluate_coverage(req, target=t)

        self.assertEqual(len(req['frames']), frames)
        self.assertEqual(len(req['layers']), layers)
        self.assertEqual(cov['counts']['structural']['required_frames'], frames)
        self.assertEqual(cov['counts']['structural']['required_layers'], layers)
        self.assertEqual(cov['counts']['assignments']['unassigned'], layers)
        self.assertEqual(cov['counts']['assignments']['direct'], 0)
        self.assertEqual(cov['counts']['assignments']['explicit_reuse'], 0)
        self.assertEqual(cov['counts']['assignments']['validated_replacement_occurrences'], 0)
        self.assertEqual(cov['counts']['assignments']['approved_source_art_roots'], 0)
        self.assertEqual(cov['counts']['work_order_categories']['supply_artwork'], layers)
        self.assertEqual(len(cov['unresolved_items']), layers)
        self.assertEqual(cov['status']['structural_specification'], 'COMPLETE_FOR_FULL_PROFILE')
        self.assertEqual(cov['status']['assignment_coverage'], 'UNASSIGNED')
        self.assertEqual(cov['status']['accepted_artwork_coverage'], 'INCOMPLETE')
        self.assertEqual(cov['status']['completeness'], 'INCOMPLETE')
        self.assertFalse(cov['status']['export_ready'])

        # Text work order generation
        txt = format_work_order(cov)
        self.assertIn(f"Unassigned Occurrences:    {layers}", txt)

        # Immutability check
        self.assertEqual(before, [canonical_bytes(i) for i in inventories])
        self.assertEqual(
            canonical_bytes(cov),
            canonical_bytes(evaluate_coverage(req, target=t)),
        )
        return cov

    def test_novice_body_and_head_coverage_remains_unassigned(self):
        """Novice body and head have 912 frames/layers but zero replacement artwork."""
        cov = self.check_coverage(
            'player',
            [('body', 'novice_body'), ('head', 'novice_head')],
            912,
            912,
        )
        parts = {item['part'] for item in cov['unresolved_items']}
        self.assertEqual(parts, {'body', 'head'})

    def test_orc_skeleton_multilayer_coverage_remains_unassigned(self):
        """Orc skeleton has 512 frames and 1776 visible layers, 0 replacement artwork."""
        cov = self.check_coverage(
            'monster',
            [('body', 'orc_skeleton')],
            512,
            1776,
        )
        self.assertEqual(cov['counts']['structural']['required_layers'], 1776)
        self.assertEqual(cov['counts']['assignments']['unassigned'], 1776)
        self.assertEqual(cov['counts']['work_order_categories']['supply_artwork'], 1776)

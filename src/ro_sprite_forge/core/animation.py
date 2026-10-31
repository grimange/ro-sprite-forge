"""Source-bound animation inspection using the existing preview compositor."""
from __future__ import annotations

import copy

from ro_sprite_forge.core.canonical import canonical_bytes, check, digest, sealed
from ro_sprite_forge.core.timeline import AnimationTimeline, TIMING_VERSION
from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.formats.spr import read_spr
from ro_sprite_forge.formats.preview import composite_frame, GEOMETRY_VERSION, RENDERER_VERSION

INSPECTION_SCHEMA = 'rsf.animation-inspection/v1'


def _union(rectangles):
    values = [r for r in rectangles if r is not None]
    return ([min(r[0] for r in values), min(r[1] for r in values),
             max(r[2] for r in values), max(r[3] for r in values)] if values else None)


class AnimationInspector:
    """Read original bytes once. All selection and rendering is observational.

    Source bytes, profile and timing/geometry versions bind the diagnostic identity.
    No artwork ledger, coverage, approval or resource is modified.
    """

    def __init__(self, act_bytes: bytes, spr_bytes: bytes, *, category='unverified',
                 head_act_bytes: bytes | None = None, head_spr_bytes: bytes | None = None,
                 profile=None):
        check((head_act_bytes is None) == (head_spr_bytes is None), 'Supply both head ACT and SPR.')
        check(head_act_bytes is None or category == 'player',
              'ATTACHMENT_UNSUPPORTED: only the pinned Player body/head relationship is supported.')
        self._act = read_act(act_bytes)
        self._spr = read_spr(spr_bytes)
        self._head_act = read_act(head_act_bytes) if head_act_bytes is not None else None
        self._head_spr = read_spr(head_spr_bytes) if head_spr_bytes is not None else None
        self._hashes = {'body_act': digest(act_bytes), 'body_spr': digest(spr_bytes)}
        if head_act_bytes is not None:
            self._hashes.update(head_act=digest(head_act_bytes), head_spr=digest(head_spr_bytes))
        self.timeline = AnimationTimeline(self._act, category=category, profile=profile)
        self._category = category

    def inspect(self, selection: dict, *, canvas_size=(256, 256), origin=(128, 192),
                auto_fit=False) -> dict:
        selection = copy.deepcopy(selection)
        self.timeline._selection(selection)
        check(type(auto_fit) is bool, 'auto_fit: expected boolean.')
        check(isinstance(origin, (tuple, list)) and len(origin) == 2 and
              all(type(n) is int and abs(n) <= 2**31 - 1 for n in origin), 'Invalid canvas origin.')
        check(isinstance(canvas_size, (tuple, list)) and len(canvas_size) == 2, 'Invalid canvas dimensions.')
        slot, frame = selection['resolved_slot'], selection['frame']
        facts = []
        clips = []
        limitations = list(selection['diagnostics'])
        for part, act in (('body', self._act), ('head', self._head_act)):
            if act is None:
                continue
            check(slot < len(act['actions']) and frame < len(act['actions'][slot]),
                  f'{part}: missing exact action {slot}/motion {frame}; no attachment fallback.')
            motion = act['actions'][slot][frame]
            facts.append({'part': part, 'slot': slot, 'frame': frame,
                          'raw_delay': act['delays'][slot], 'motion_bounds': list(motion['bounds']),
                          'anchors': copy.deepcopy(motion['anchors']), 'event_index': motion['event'],
                          'raw_events': copy.deepcopy(act['events']),
                          'omitted_layer_ordinals': [i for i, c in enumerate(motion['clips']) if c['sprite'] < 0]})
            clips.extend((part, ordinal, c) for ordinal, c in enumerate(motion['clips']) if c['sprite'] >= 0)
            if any(not m['clips'] for m in act['actions'][slot]):
                limitations.append(f'{part}: native zero-clip prepared-frame compaction parity is UNVERIFIED.')
            for c in motion['clips']:
                if c['scale_x'] <= 0 or c['scale_y'] <= 0 or c['mirror'] not in (0, 1):
                    limitations.append(f'{part}: nonpositive scale/nonboolean mirror preview is diagnostic; native parity UNVERIFIED.')
        if self._head_act is not None:
            limitations.append('Head uses body timing and the same raw motion ordinal; independent head delays are not evaluated.')
        result = composite_frame(self._act, self._spr, slot, frame,
                                 head_act_data=self._head_act, head_spr_doc=self._head_spr,
                                 canvas_size=tuple(canvas_size), origin=tuple(origin), auto_fit=auto_fit,
                                 source_hashes=self._hashes)
        report = result['report']
        layers = []
        check(len(clips) == len(report['layers']), 'Diagnostic/rendered layer count mismatch.')
        for (part, ordinal, clip), rendered, geometry in zip(clips, report['layers'], result['geometry']):
            layers.append({'part': part, 'layer_ordinal': ordinal, 'image_pool': clip['pool'],
                           'image_index': clip['sprite'], 'source_transform': dict(clip),
                           'rendered': rendered, 'geometry': geometry})
        limitations.extend(report['unsupported_semantics'])
        # The CPU output is verified in its declared scope, not a replica of GPU WBOIT.
        limitations.append('CPU Pillow ordered alpha composition; GPU WBOIT, native action-wide billboard bounds and cross-GPU pixel parity are not verified.')
        inspection = sealed({
            'schema': INSPECTION_SCHEMA,
            'semantics': {'renderer': RENDERER_VERSION, 'geometry': GEOMETRY_VERSION,
                          'timing': TIMING_VERSION, 'coordinates': 'screen x-right/y-down; half-open rectangles; integer center (size-1)//2'},
            'sources': dict(self._hashes), 'selection': selection,
            'source_frames': facts, 'layers': layers,
            'canvas': {'origin': report['origin'], 'dimensions': report['dimensions'],
                       'bounds': [0, 0, report['dimensions']['width'], report['dimensions']['height']],
                       'auto_fit': auto_fit},
            'frame_bounds': {'transformed': _union(g['transformed_bounds'] for g in result['geometry']),
                             'unclipped_visible': _union(g['unclipped_visible_bounds'] for g in result['geometry']),
                             'visible': _union(g['visible_bounds'] for g in result['geometry'])},
            'empty_frame': not clips, 'fully_transparent': not any(g['unclipped_visible_bounds'] for g in result['geometry']),
            'fidelity': {'geometry': 'VERIFIED', 'native_pixel_parity': 'UNVERIFIED',
                         'overall': 'PARTIAL', 'limitations': list(dict.fromkeys(limitations))},
            'preview_png_sha256': report['png_sha256'],
            'review': 'UNVERIFIED', 'artwork_coverage': 'NOT_EVALUATED',
        })
        return {'report': inspection, 'png_bytes': result['png_bytes'], 'image': result['image']}


def inspection_schema() -> dict:
    """Closed Draft 2020-12 diagnostic schema, available in installed wheels."""
    import json
    from importlib.resources import files
    return json.loads(files('ro_sprite_forge').joinpath('schemas/animation-inspection-v1.json').read_text())

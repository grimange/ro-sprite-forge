"""Check RSF-27 native observations against resources, staged pixels and captures.

This is an evidence checker, not a renderer or resource resolver. Pool resolution
uses the audited codec/preview helper; selection rules reuse the RSF-6 checker.
Only binary-alpha upload bytes are compared here. General GPU parity is unverified.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image
from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.formats.spr import read_spr
from ro_sprite_forge.formats.preview import _resolve_image_from_spr
from verify import NativeMismatch, equal, close, close_vector, check_selection


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def upload_identity(image):
    """Independently known opaque/transparent native upload expectation."""
    pixels = bytearray(image.convert('RGBA').tobytes())
    for offset in range(0, len(pixels), 4):
        alpha = pixels[offset + 3]
        if alpha not in (0, 255):
            raise NativeMismatch('UNSUPPORTED_UPLOAD_COMPARISON: partial alpha')
        if alpha == 0:
            pixels[offset:offset + 3] = b'\0\0\0'
    return dict(width=image.width, height=image.height, upload_rgba_sha256=sha(pixels))


def check_capture(capture, directory, layers):
    name = capture['file']
    equal(Path(name).name, name, 'capture/local_filename')
    path = directory / name
    equal(sha(path.read_bytes()), capture['png_sha256'], 'capture/hash')
    with Image.open(path) as image:
        equal(image.size, (512, 512), 'capture/dimensions')
        raw = image.convert('RGBA').tobytes()
        count = sum(any(raw[i:i + 3]) for i in range(0, len(raw), 4))
    equal(count, capture['non_background_pixels'], 'capture/visible_pixels')
    if count <= 0:
        raise NativeMismatch('EMPTY_NATIVE_RENDER')
    equal(capture['drawn_layers'], layers, 'capture/layers')
    equal(capture['passes'], ['opaque', 'transparent', 'wboit_resolve'], 'capture/passes')


def verify(inputs, provenance, report, directory):
    equal(report['schema'], 'rsf.native-walk/v1', 'schema')
    equal(report['revision'], '3f3d88a583203f09d079712f43343c1041258ffd', 'pin')
    equal(report['mode'], 'isolated_native_presentation', 'mode')
    equal(report['pixel_parity'], 'UNVERIFIED', 'pixel_parity')
    equal(provenance['export_label'], 'PARTIAL_DIAGNOSTIC', 'classification')
    equal(provenance['production_authorized'], False, 'production_authority')
    build_raw = Path(provenance['build_manifest_path']).read_bytes()
    equal(sha(build_raw), provenance['build_manifest_sha256'], 'build/manifest_hash')
    equal(json.loads(build_raw), provenance['build'], 'build/canonical_identity')
    equal(provenance['build']['output_sha256']['act'], provenance['modified']['act_sha256'], 'build/act')
    equal(provenance['build']['output_sha256']['spr'], provenance['modified']['spr_sha256'], 'build/spr')
    sources = {}
    for blob in provenance['source_blobs']:
        path = Path(blob['path'])
        equal(sha(path.read_bytes()), blob['sha256'], 'STAGED_SOURCE_HASH')
        with Image.open(path) as image:
            sources[blob['sha256']] = dict(width=image.width, height=image.height,
                                          upload_rgba_sha256=sha(image.convert('RGBA').tobytes()))
    specs = {a['id']: a for a in inputs['walk']['actors']}
    actors = {a['actor']: a for a in report['actors']}
    equal(len(actors), len(report['actors']), 'duplicate_actor')
    equal(set(actors), set(specs), 'actor_coverage')
    documents, hashes = {}, {}
    for identifier, spec in inputs['files'].items():
        raw = Path(spec['path']).read_bytes()
        hashes[identifier] = sha(raw)
        equal(hashes[identifier], spec['sha256'], 'SOURCE_HASH/' + identifier)
        name, extension = identifier.rsplit('\\', 1)[1].rsplit('.', 1)
        documents.setdefault(name, {})[extension] = read_act(raw) if extension == 'act' else read_spr(raw)
        if name in ('original', 'modified'):
            equal(hashes[identifier], provenance[name][extension + '_sha256'], 'PAIR_IDENTITY/' + name + '/' + extension)
    total_layers, total_frames = 0, 0
    for actor, observed in actors.items():
        spec = specs[actor]
        equal(observed['kind'], spec['kind'], actor + '/kind')
        equal(observed['parts'], spec['parts'], actor + '/parts')
        equal(observed['cache_reused'], True, actor + '/cache')
        loaded = observed['loaded']
        required = {f'data\\sprite\\{n}.{e}' for n in spec['parts'] for e in ('act', 'spr')}
        equal(len(loaded), len(required), actor + '/load_count')
        equal({r['path'] for r in loaded}, required, actor + '/loaded_paths')
        for item in loaded:
            equal(item['status'], 'LOADED_CORRECT_RESOURCE', 'native/load_status')
            equal(item['sha256'], hashes[item['path']], 'native/consumed_hash')
            equal(item['length'], Path(inputs['files'][item['path']]['path']).stat().st_size, 'native/consumed_length')
        acts = [documents[n]['act'] for n in spec['parts']]
        sprites = [documents[n]['spr'] for n in spec['parts']]
        equal(len(observed['pools']), len(sprites), actor + '/pool_parts')
        for pool, sprite in zip(observed['pools'], sprites):
            equal(pool['indexed_count'], sprite.indexed_count, actor + '/indexed_count')
            equal(pool['truecolor_count'], len(sprite.rgba_images), actor + '/truecolor_count')
            expected_uploads = [upload_identity(image.to_pil(sprite.palette)) for image in sprite.indexed_images]
            expected_uploads += [upload_identity(image.to_pil()) for image in sprite.rgba_images]
            equal(pool['textures'], expected_uploads, actor + '/native_upload_pixels')
        equal(observed['delays'], acts[0]['delays'], actor + '/delays')
        equal(len(observed['prepared']), len(acts[0]['actions']), actor + '/slots')
        for slot, frames in enumerate(observed['prepared']):
            motions = [[m for m in a['actions'][slot] if m['clips']] for a in acts]
            equal(len(frames), len(motions[0]), actor + '/motion_count')
            for index, frame in enumerate(frames):
                expected = []
                for part, part_motions in enumerate(motions):
                    if index >= len(part_motions):
                        continue
                    motion = part_motions[index]
                    for layer in motion['clips']:
                        if layer['sprite'] == -1:
                            continue
                        image, error = _resolve_image_from_spr(sprites[part], layer['sprite'], layer['pool'])
                        equal(error, None, 'image_resolution')
                        global_index = layer['sprite'] + (sprites[part].indexed_count if layer['pool'] == 1 else 0)
                        x, y = layer['x'], layer['y']
                        if spec['kind'] == 'player' and part == 1 and len(motion['anchors']) == 1:
                            equal(len(motions[0]), len(acts[0]['actions'][slot]), 'parent_motion_mapping')
                            parent = acts[0]['actions'][slot][index]['anchors'][0]
                            anchor = motion['anchors'][0]
                            x += parent['x'] - anchor['x']
                            y += parent['y'] - anchor['y']
                        expected.append(dict(part=part, image=global_index, offset=[x, y],
                            size=[math.ceil(image.width * layer['scale_x']), math.ceil(image.height * layer['scale_y'])],
                            mirror=bool(layer['mirror']), angle=layer['angle'] / 180 * math.pi,
                            color=[((layer['color'] >> shift) & 255) / 255 for shift in (0, 8, 16, 24)]))
                equal(len(frame['parts']), len(expected), actor + '/layer_count')
                for layer, required in zip(frame['parts'], expected):
                    for field in ('part', 'image', 'offset', 'size', 'mirror'):
                        equal(layer[field], required[field], actor + '/layer/' + field)
                    close(layer['angle'], required['angle'], actor + '/layer/angle')
                    close_vector(layer['color'], required['color'], actor + '/layer/color')
                total_layers += len(expected)
                total_frames += 1
    expected_cases = {(name, action, camera, direction) for name, spec in specs.items()
                      for action in spec['actions'] for camera in (0, 4) for direction in range(8)}
    equal(len(report['cases']), len(expected_cases), 'case_count')
    equal({(c['actor'], c['requested_action'], c['camera_view'], c['requested_direction']) for c in report['cases']}, expected_cases, 'case_coverage')
    captures, selected_frames, selected_layers = 0, 0, 0
    for case in report['cases']:
        actor = actors[case['actor']]
        check_selection(case, 'novice' if actor['kind'] == 'player' else 'orc', actor['delays'], [len(a) for a in actor['prepared']])
        for sample in case['sequence']:
            layers = actor['prepared'][sample['resolved_slot']][sample['frame']]['parts']
            equal(sample['layers'], len(layers), 'native/draw_count')
            expected = [dict(part=p['part'], image=p['image'], upload=actor['pools'][p['part']]['textures'][p['image']]) for p in layers]
            equal(sample['selected'], expected, 'native/selected_texture')
            if sample['capture'] is not None:
                check_capture(sample['capture'], directory, len(layers))
                captures += 1
            selected_frames += 1
            selected_layers += len(layers)
        equal(sum(s['capture'] is not None for s in case['sequence']),
              case['frames_in_slot'] if case['camera_view'] == 0 and case['requested_direction'] == 0 else 0, 'capture_coverage')
    # Compare known staged PNG pixels, independent of the writer's PASS fields.
    modified = actors['modified']
    original_act = documents['original']['act']
    for expected in provenance['expected']:
        slot, frame, raw_layer = (expected[k] for k in ('slot', 'frame', 'raw_layer'))
        clips = original_act['actions'][slot][frame]['clips']
        visible = sum(c['sprite'] >= 0 for c in clips[:raw_layer])
        layer = modified['prepared'][slot][frame]['parts'][visible]
        upload = modified['pools'][layer['part']]['textures'][layer['image']]
        required = dict(width=expected['width'], height=expected['height'], upload_rgba_sha256=expected['decoded_rgba_sha256'])
        equal(required, sources[expected['source_png_sha256']], 'replacement/source_pixels')
        equal(upload, required, 'replacement/staged_pixels')
    # Every unaffected draw selection and every preserved capture must match.
    baseline_cases = {(c['requested_action'], c['camera_view'], c['requested_direction']): c for c in report['cases'] if c['actor'] == 'original'}
    changed = {(r['slot'], r['frame']) for r in provenance['expected']}
    preserved_samples = 0
    for case in (c for c in report['cases'] if c['actor'] == 'modified'):
        baseline = baseline_cases[(case['requested_action'], case['camera_view'], case['requested_direction'])]
        for before, after in zip(baseline['sequence'], case['sequence']):
            if (after['resolved_slot'], after['frame']) not in changed:
                equal(after['selected'], before['selected'], 'unaffected/selected')
                if after['capture']:
                    equal(after['capture']['png_sha256'], before['capture']['png_sha256'], 'unaffected/render')
                preserved_samples += 1
            elif after['capture']:
                if after['capture']['png_sha256'] == before['capture']['png_sha256']:
                    raise NativeMismatch('REPLACEMENT_NOT_RENDERED: baseline capture unchanged')
    expected_negatives = {(name, case) for name, spec in specs.items() if spec['kind'] == 'monster'
                          for case in ('truncated_walk_modulo', 'unsupported_critical_attack')}
    expected_negatives.add((None, 'unsupported_direction_8'))
    equal(len(report['negative_cases']), len(expected_negatives), 'negative_count')
    equal({(n.get('actor'), n['case']) for n in report['negative_cases']}, expected_negatives, 'negative_coverage')
    for negative in report['negative_cases']:
        equal(negative['accepted_as_exact'], False, 'fallback/accepted')
        if negative['case'] != 'unsupported_direction_8':
            equal(negative['resolved_slot'], 0, 'fallback/resolved')
            equal(negative['status'], 'FALLBACK_OBSERVED', 'fallback/status')
        else:
            equal(negative['native_masked_direction'], 0, 'direction/masking')
            equal(negative['status'], 'ACTION_UNSUPPORTED', 'direction/status')
    return dict(result='NATIVE_CHECKS_PASSED',
                cases=len(expected_cases), prepared_frames=total_frames, prepared_layers=total_layers,
                selected_frames=selected_frames, selected_layers=selected_layers, captures=captures,
                preserved_samples=preserved_samples, targeted_occurrences=len(provenance['expected']),
                resource_hashes=hashes, levels=dict(A='PASS', B='PASS', C='PASS', D='UNVERIFIED'),
                scope='isolated native presentation; binary-alpha upload identity; no artistic approval')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inputs', type=Path)
    parser.add_argument('provenance', type=Path)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    result = verify(json.loads(args.inputs.read_text()), json.loads(args.provenance.read_text()),
                    json.loads(args.report.read_text()), args.report.parent)
    result['native_report_sha256'] = sha(args.report.read_bytes())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

"""RSF-17 transport adapter. Canonical decisions remain in the accepted Python core."""
from __future__ import annotations
import base64
import copy
import io
from pathlib import Path

from ro_sprite_forge.core.canonical import check, digest, canonical_bytes
from ro_sprite_forge.core.contracts import load_target, reference
from ro_sprite_forge.core.errors import ForgeError, ErrorCode
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.profiles import get_profile
from ro_sprite_forge.core.ledger import load_ledger, resolve_ledger, assignment_binding, compare_ledgers
from ro_sprite_forge.core.coverage import evaluate_coverage
from ro_sprite_forge.core.project import load_project, save_project, import_blob, get_blob, MAX_BLOB_SIZE
from ro_sprite_forge.core.animation import AnimationInspector
from ro_sprite_forge.core.comparison import compare_frames
from ro_sprite_forge.formats.spr import read_spr
from ro_sprite_forge.formats.preview import png_bytes


def _context(root, manifest):
    from ro_sprite_forge.service.server import _resolve_project_requirements
    return _resolve_project_requirements(Path(root) / manifest['project_id'], manifest)


def _bytes(root, manifest, sha):
    return get_blob(root, manifest['project_id'], sha)


def _image(root, manifest, source, sprites=None):
    """Reconstruct precisely selected imported pixels, never substitute another image."""
    from PIL import Image
    if source['kind'] == 'IMPORTED_IMAGE':
        p = source['provenance']
        invs = [r['inventory'] for r in manifest.get('resources', [])]
        check(any(i['canonical_sha256'] == p['inventory_sha256'] and
                  i['sources']['act']['sha256'] == p['act_sha256'] and
                  i['sources']['spr']['sha256'] == p['spr_sha256'] for i in invs),
              'SOURCE_PROVENANCE_MISMATCH')
        if sprites is None: sprites = {}
        key = p['spr_sha256']
        if key not in sprites: sprites[key] = read_spr(_bytes(root, manifest, key))
        spr = sprites[key]
        pool, index = source['image']['pool'], source['image']['index']
        members = spr.indexed_images if pool == 'indexed' else spr.rgba_images
        check(index < len(members), 'Invalid source image index.')
        im = members[index]
        raw = im.to_rgba(spr.palette) if pool == 'indexed' else im.rgba
        return png_bytes(Image.frombytes('RGBA', (im.width, im.height), raw))
    check(source['sha256'] is not None, 'Source bytes UNVERIFIED: no declared hash.')
    return _bytes(root, manifest, source['sha256'])


def source_catalog(root, manifest):
    sources = {}
    declared = {s['id']: s for s in manifest.get('ledger', {}).get('sources', [])}
    sprites, content = {}, {}
    for r in manifest.get('resources', []):
        inv = r['inventory']
        for image in inv['images']:
            identity = 'spr-' + digest(canonical_bytes([inv['canonical_sha256'], image['pool'], image['index']]))
            src = dict(id=identity, revision=1, sha256=None, kind='IMPORTED_IMAGE',
                       origin='CLASSIC_REFERENCE', external_ref=r['id'],
                       image={'pool': 'indexed' if image['pool'] == 0 else 'truecolor', 'index': image['index']},
                       provenance={'inventory_sha256': inv['canonical_sha256'],
                                   'act_sha256': inv['sources']['act']['sha256'],
                                   'spr_sha256': inv['sources']['spr']['sha256']})
            # Hash is the deterministic decoded PNG identity; original representation hashes stay in inventory.
            try:
                raw = _image(root, manifest, src, sprites)
            except ForgeError:
                # Keep original immutable identity visible even if the resource is unavailable.
                raw = None
            src['sha256'] = digest(raw) if raw is not None else declared.get(identity, {}).get('sha256')
            content[identity] = raw
            sources[identity] = dict(source=src, part=r['part'], image_identity=image['id'],
                                     availability='AVAILABLE', validation='VALID', preview='AVAILABLE')
    for src in manifest.get('ledger', {}).get('sources', []):
        if src['id'] not in sources:
            sources[src['id']] = dict(source=src, part=None, image_identity=None,
                                     availability='UNVERIFIED', validation='UNVERIFIED', preview='UNVERIFIED')
    for sha, blob in manifest.get('sources', {}).items():
        if sha not in sources and blob['filename'].lower().endswith(('.png', '.jpg', '.jpeg')):
            origin = blob.get('origin', 'AUTHORED')
            src = dict(id='blob-'+sha, revision=1, sha256=sha, kind='IMAGE', origin=origin,
                       external_ref=blob.get('filename', 'blob-'+sha), image=None, provenance=None)
            entry = dict(source=src, part=None, image_identity=None,
                         availability='UNVERIFIED', validation='UNVERIFIED', preview='UNVERIFIED')
            for meta_k in ('width', 'height', 'mode', 'transparency_kind', 'has_transparency', 'sequence_id', 'ordinal', 'extraction_id', 'recipe_sha256', 'source_sheet_sha256', 'rect_id', 'crop_rect', 'recipe_id', 'source_sha256', 'loss_report'):
                if meta_k in blob:
                    entry[meta_k] = blob[meta_k]
            sources.setdefault(src['id'], entry)
    for record in sources.values():
        try:
            raw = content.get(record['source']['id'])
            if raw is None: raw = _image(root, manifest, record['source'], sprites)
            check(digest(raw) == record['source']['sha256'], 'SOURCE_HASH_MISMATCH')
            record['availability'], record['validation'] = 'AVAILABLE', 'VALID'
            try:
                from PIL import Image
                with Image.open(io.BytesIO(raw)) as im:
                    check(im.width * im.height <= 16*1024*1024, 'Image budget exceeded.')
                    im.verify()
                record['preview'] = 'AVAILABLE'
                if 'width' not in record:
                    record['width'] = im.width
                    record['height'] = im.height
                    record['mode'] = im.mode
            except Exception:
                record['preview'] = 'UNVERIFIED'
        except ForgeError as exc:
            record['availability'] = 'MISSING' if exc.code == ErrorCode.INPUT_NOT_FOUND else 'UNVERIFIED'
            record['validation'] = 'INVALID' if exc.code != ErrorCode.INPUT_NOT_FOUND else 'UNVERIFIED'
            record['diagnostic'] = exc.message
    return [sources[k] for k in sorted(sources)]


def source_evidence(root, manifest):
    result, sprites = {}, {}
    for src in manifest.get('ledger', {}).get('sources', []):
        try: result[src['id']] = _image(root, manifest, src, sprites)
        except ForgeError as exc:
            # A failed integrity check is not usable evidence. The catalog retains
            # its precise error; the ledger cannot count unavailable bytes as valid.
            result[src['id']] = None
    return result


def workspace(root, manifest):
    req, target = _context(root, manifest)
    report = None
    coverage = None
    if req is not None:
        evidence = source_evidence(root, manifest)
        if manifest.get('ledger'):
            ledger = load_ledger(manifest['ledger'], requirements=req)
            report = resolve_ledger(ledger, requirements=req, source_bytes=evidence)
        reviews, reviewed_report = review_context(root,manifest,req,report)
        coverage = evaluate_coverage(req, ledger=reviewed_report or manifest.get('ledger'), source_bytes=evidence, target=target)
        report = reviewed_report
    return dict(project=manifest, requirements=req, ledger=report, coverage=coverage,
                reviews=reviews if req is not None else None,
                sources=source_catalog(root, manifest),
                sequences=manifest.get('sequences', []),
                extractions=manifest.get('extractions', []),
                recipes=manifest.get('recipes', []),
                compilations=manifest.get('compilations', []),
                resources=[dict(id=r['id'], part=r['part'], summary=r['inventory']['summary'],
                                sources=r['inventory']['sources'], actions=[dict(slot=a['slot'],
                                action=a['semantic_action'],view=a['mapped_view'],frames=len(a['frames']))
                                for a in r['inventory']['actions']]) for r in manifest.get('resources', [])])


def _inspector(root, manifest, resource_id, head_id=None):
    resources = {r['id']: r for r in manifest.get('resources', [])}
    check(resource_id in resources, 'RESOURCE_NOT_SELECTED_OR_MISSING')
    r = resources[resource_id]
    kwargs = {}
    if head_id:
        check(head_id in resources and resources[head_id]['part'] == 'head' and r['part'] == 'body',
              'Invalid body/head resource relationship.')
        h = resources[head_id]
        kwargs = dict(head_act_bytes=_bytes(root,manifest,h['act']),head_spr_bytes=_bytes(root,manifest,h['spr']))
    return AnimationInspector(_bytes(root, manifest,r['act']),_bytes(root, manifest,r['spr']),
                              category=manifest['profile'], **kwargs)


def _selection(inspector, data):
    return inspector.timeline.select(slot=data['slot'], view=data['view'], frame=data.get('frame', 0))


def preview(root, manifest, data):
    ins = _inspector(root,manifest,data.get('resource'),data.get('head'))
    selection = _selection(ins,data)
    if data.get('step') is not None:
        selection = ins.timeline.step(selection,data['step'],loop=False)
    if data.get('elapsed_ms') is not None:
        context = data.get('context', {})
        check(type(context) is dict and set(context) <= {'movement_speed','duration_ms','diagnostic_frame_ms','diagnostic_loop'},
              'Invalid timing context.')
        elapsed = data['elapsed_ms']
        speed = data.get('speed',1)
        if data.get('resume_frame') is not None:
            # Derive the resume position with the canonical Python timing policy.
            import math
            frame = data['resume_frame']
            ins.timeline.select(slot=data['slot'],view=data['view'],frame=frame)
            origin = ins.timeline.seek(selection,0,speed=speed,**context)
            if origin['timing_status'] in ('SUPPORTED','DIAGNOSTIC'):
                offset = math.ceil(frame * origin['frame_duration_ms'] / speed)
                # f32 runtime division can round a boundary down by one tick.
                for _ in range(4):
                    probe = ins.timeline.seek(selection,offset,speed=speed,**context)
                    if probe['frame'] == frame: break
                    offset += 1
                check(probe['frame'] == frame, 'Selected frame has no supported timed resume position.')
                check(type(elapsed) is int and elapsed >= 0, 'elapsed_ms: expected nonnegative integer.')
                elapsed += offset
        selection = ins.timeline.seek(selection,elapsed,speed=speed,**context)
    result = ins.inspect(selection)
    return dict(report=result['report'], png_base64=base64.b64encode(result['png_bytes']).decode())


def comparison(root, manifest, data):
    check(data.get('candidate'), 'CANDIDATE_NOT_SELECTED')
    ref = _inspector(root,manifest,data.get('resource'),data.get('head'))
    cand = _inspector(root,manifest,data['candidate'],data.get('candidate_head'))
    result = compare_frames(ref,cand,_selection(ref,data),_selection(cand,data),
                            mode=data.get('mode','SIDE_BY_SIDE'))
    return dict(report=result['report'],png_base64=base64.b64encode(result['png_bytes']).decode())


def mutate(root, manifest, operation, data):
    """Validate whole proposal before publishing one optimistic project revision."""
    expected = data.get('expected_revision')
    if type(expected) is not int or expected != manifest['revision']:
        raise ForgeError(ErrorCode.CONFLICT,'Project revision conflict. Reload before retrying.')
    updated = copy.deepcopy(manifest)
    pid = manifest['project_id']
    if operation == 'target':
        from ro_sprite_forge.service.server import _get_project_actor_and_profile
        check(not manifest.get('ledger',{}).get('assignments'), 'Target has assignments: explicit rebinding required; no silent remapping.')
        doc = copy.deepcopy(data['target'])
        updated['target'] = doc
        actor,profile = _get_project_actor_and_profile(updated,Path(root)/pid)
        doc['actor'],doc['runtime_profile'] = reference(actor),reference(profile)
        previous = None
        if manifest.get('target'):
            previous = load_target(manifest['target'],actor=actor,profile=profile)
        target = load_target(doc,actor=actor,profile=profile,previous=previous)
        updated['target'] = target.to_dict()
        _context(root, updated)
    elif operation == 'import-pair':
        check(type(data.get('id')) is str and 0 < len(data['id']) <= 64 and data['id'].replace('-','').replace('_','').isalnum(), 'Invalid resource ID.')
        check(data.get('part') in ('body','head'), 'Resource part must be explicit body or head.')
        check(data['id'] not in {r['id'] for r in manifest.get('resources',[])}, 'Duplicate resource ID; choose a new immutable resource identity.')
        try:
            act = base64.b64decode(data['act_base64'],validate=True)
            spr = base64.b64decode(data['spr_base64'],validate=True)
        except (ValueError,TypeError,KeyError) as exc:
            raise ForgeError(ErrorCode.INVALID_INPUT,'Supply valid ACT and SPR base64 bytes.') from exc
        check(len(act) <= MAX_BLOB_SIZE and len(spr) <= MAX_BLOB_SIZE, 'Resource exceeds blob budget.')
        inv = inventory(act,spr,actor=manifest['actor'],part=data['part'],profile=get_profile(manifest['profile']))
        resources = updated.setdefault('resources',[])
        check(len(resources) < 16, 'At most 16 explicitly imported resource pairs per project.')
        for raw,ext in ((act,'act'),(spr,'spr')):
            blob = import_blob(root,pid,data['id']+'.'+ext,raw)
            updated['sources'][blob['sha256']] = blob
        resources.append(dict(id=data['id'],part=data['part'],act=digest(act),spr=digest(spr),inventory=inv))
    elif operation == 'assign':
        req,_ = _context(root,manifest)
        check(req is not None,'Declare target topology before assigning artwork.')
        mappings = data.get('mappings')
        check(type(mappings) is list and 0 < len(mappings) <= 256,'Batch must contain 1–256 explicit mappings.')
        layers = {l['id']:l for l in req['layers']}
        catalog = {s['source']['id']:s for s in source_catalog(root,manifest)}
        previous = load_ledger(manifest['ledger'],requirements=req) if manifest.get('ledger') else None
        doc = previous.to_dict() if previous else dict(schema='rsf.assignment-ledger/v1',id=pid+'-ledger',revision=1,
                previous_sha256=None,target=req['target'],requirements_sha256=req['canonical_sha256'],sources=[],assignments=[],attachments=[])
        doc.pop('canonical_sha256',None)
        if previous:
            doc.update(revision=previous.to_dict()['revision']+1,previous_sha256=previous.canonical_sha256)
        assignments = {a['requirement_id']:a for a in doc['assignments']}
        sources = {s['id']:s for s in doc['sources']}
        seen = set()
        for m in mappings:
            check(type(m) is dict and set(m) <= {'requirement_id','kind','source','dependency','recipe','source_revision'},'Invalid mapping fields.')
            rid = m.get('requirement_id')
            check(type(rid) is str and rid in layers, 'NONEXISTENT_REQUIREMENT: '+str(rid))
            check(rid not in seen,'DUPLICATE_ASSIGNMENT: '+rid)
            seen.add(rid)
            old = assignments.get(rid)
            item = dict(id=old['id'] if old else 'assignment-'+digest(rid.encode()),revision=old['revision']+1 if old else 1,
                        requirement_id=rid,binding=assignment_binding(layers[rid]),kind=m.get('kind'),source=None,
                        dependency=None,recipe=m.get('recipe',[]),review=None)
            if item['kind'] == 'DIRECT_SOURCE':
                sid = m.get('source')
                check(type(sid) is str and sid in catalog, 'MISSING_SOURCE: '+str(sid))
                record = catalog[sid]
                check(record['availability'] == 'AVAILABLE' and record['validation'] == 'VALID','SOURCE_UNAVAILABLE_OR_HASH_MISMATCH: '+sid)
                src = record['source']
                check(m.get('source_revision') == src['revision'],'STALE_SOURCE_REVISION')
                sources[sid] = src
                item['source'] = dict(id=sid,revision=src['revision'])
            elif item['kind'] == 'EXPLICIT_REUSE':
                item['dependency'] = m.get('dependency')
            assignments[rid] = item
        # Follow established dependency order; only untouched dependent records advance.
        # Explicit batch edges must still name the exact requested revision.
        if previous:
            by_id = {a['id']:a for a in assignments.values()}
            from ro_sprite_forge.core.ledger import _order
            old_doc = previous.to_dict()
            for aid in _order({a['id']:a for a in old_doc['assignments']}):
                item = by_id[aid]
                dep = item.get('dependency')
                if dep and item['requirement_id'] not in seen and dep['id'] in by_id:
                    new_rev = by_id[dep['id']]['revision']
                    if dep['revision'] != new_rev:
                        item['dependency'] = dict(dep,revision=new_rev)
                        item['revision'] += 1
                        item['review'] = None
        doc.update(sources=list(sources.values()),assignments=list(assignments.values()))
        loaded = load_ledger(doc,requirements=req,previous=previous)
        updated['ledger'] = loaded.to_dict()
        evidence = source_evidence(root,updated)
        resolved = resolve_ledger(loaded,requirements=req,source_bytes=evidence)
        for a in resolved['assignments']:
            if a['requirement_id'] in seen and a['kind'] != 'UNASSIGNED':
                check(a['validation'] == 'VALID' and a['effective_source'] is not None,'Invalid or unavailable reuse source.')
        # Coverage evaluation is part of transaction validation, never after publication.
        evaluate_coverage(req,loaded,source_bytes=evidence)
    elif operation == 'stage-sequence':
        from ro_sprite_forge.core.ingestion import validate_png, validate_sequence
        seq_id = data.get('sequence_id')
        seq_name = data.get('name')
        raw_frames = data.get('frames')
        check(type(raw_frames) is list and len(raw_frames) > 0, 'Sequence must contain at least 1 frame.')
        validated_frames = []
        for f in raw_frames:
            check(type(f) is dict, 'Frame must be a dict.')
            ordinal = f.get('ordinal')
            filename = f.get('filename')
            check(type(ordinal) is int and ordinal >= 0, 'Frame ordinal must be nonnegative integer.')
            check(type(filename) is str and len(filename) > 0, 'Frame filename required.')
            if 'data_base64' in f:
                try:
                    raw_bytes = base64.b64decode(f['data_base64'], validate=True)
                except Exception as exc:
                    raise ForgeError(ErrorCode.INVALID_INPUT, f'Invalid base64 in frame {ordinal}: {exc}') from exc
                meta = validate_png(raw_bytes, filename=filename, expected_sha256=f.get('expected_sha256'))
                blob = import_blob(root, pid, filename, raw_bytes, expected_sha256=meta['sha256'])
            elif 'sha256' in f:
                sha = f['sha256']
                raw_bytes = get_blob(root, pid, sha)
                meta = validate_png(raw_bytes, filename=filename, expected_sha256=sha)
                blob = dict(sha256=sha, filename=filename, size=len(raw_bytes), blob_path=f'blobs/{sha}')
            else:
                raise ForgeError(ErrorCode.INVALID_INPUT, f'Frame {ordinal} requires data_base64 or sha256.')

            meta_record = dict(
                sha256=blob['sha256'],
                filename=filename,
                size=blob['size'],
                blob_path=blob['blob_path'],
                origin='AUTHORED',
                kind='IMAGE',
                width=meta['width'],
                height=meta['height'],
                mode=meta['mode'],
                transparency_kind=meta['transparency_kind'],
                has_transparency=meta['has_transparency'],
                sequence_id=seq_id,
                ordinal=ordinal,
            )
            updated.setdefault('sources', {})[blob['sha256']] = meta_record
            validated_frames.append(dict(
                ordinal=ordinal,
                sha256=blob['sha256'],
                filename=filename,
                width=meta['width'],
                height=meta['height'],
                mode=meta['mode'],
                transparency_kind=meta['transparency_kind'],
                has_transparency=meta['has_transparency'],
            ))
        seq_manifest = validate_sequence(seq_id, seq_name, validated_frames)
        sequences = updated.setdefault('sequences', [])
        existing_idx = next((i for i, s in enumerate(sequences) if s['id'] == seq_id), None)
        if existing_idx is not None:
            sequences[existing_idx] = seq_manifest
        else:
            check(len(sequences) < 64, 'Maximum 64 sequences per project.')
            sequences.append(seq_manifest)

    elif operation == 'stage-png':
        from ro_sprite_forge.core.ingestion import validate_png
        filename = data.get('filename')
        check(type(filename) is str and len(filename) > 0, 'Filename required.')
        try:
            raw_bytes = base64.b64decode(data['data_base64'], validate=True)
        except Exception as exc:
            raise ForgeError(ErrorCode.INVALID_INPUT, f'Invalid base64 payload: {exc}') from exc
        meta = validate_png(raw_bytes, filename=filename, expected_sha256=data.get('expected_sha256'))
        blob = import_blob(root, pid, filename, raw_bytes, expected_sha256=meta['sha256'])
        meta_record = dict(
            sha256=blob['sha256'],
            filename=filename,
            size=blob['size'],
            blob_path=blob['blob_path'],
            origin='AUTHORED',
            kind='IMAGE',
            width=meta['width'],
            height=meta['height'],
            mode=meta['mode'],
            transparency_kind=meta['transparency_kind'],
            has_transparency=meta['has_transparency'],
            sequence_id=None,
            ordinal=None,
        )
        updated.setdefault('sources', {})[blob['sha256']] = meta_record
    elif operation == 'extract-spritesheet':
        from ro_sprite_forge.core.extraction import extract_spritesheet, expand_grid_spec
        from ro_sprite_forge.core.ingestion import validate_png
        extraction_id = data.get('extraction_id')
        name = data.get('name') or data.get('extraction_name') or extraction_id or 'Spritesheet Extraction'
        check(type(extraction_id) is str and 0 < len(extraction_id) <= 64, 'Valid extraction_id required.')
        check(type(name) is str and 0 < len(name) <= 128, 'Valid extraction name required.')

        sheet_sha = data.get('sheet_sha256')
        sheet_filename = data.get('sheet_filename')
        if 'sheet_data_base64' in data:
            try:
                sheet_bytes = base64.b64decode(data['sheet_data_base64'], validate=True)
            except Exception as exc:
                raise ForgeError(ErrorCode.INVALID_INPUT, f'Invalid sheet base64: {exc}') from exc
            sheet_meta = validate_png(sheet_bytes, filename=sheet_filename, expected_sha256=sheet_sha)
            sheet_blob = import_blob(root, pid, sheet_filename or 'spritesheet.png', sheet_bytes, expected_sha256=sheet_meta['sha256'])
            sheet_sha = sheet_blob['sha256']
            sheet_filename = sheet_blob['filename']
            updated.setdefault('sources', {})[sheet_sha] = dict(
                sha256=sheet_sha,
                filename=sheet_filename,
                size=sheet_blob['size'],
                blob_path=sheet_blob['blob_path'],
                origin='AUTHORED',
                kind='IMAGE',
                width=sheet_meta['width'],
                height=sheet_meta['height'],
                mode=sheet_meta['mode'],
                transparency_kind=sheet_meta['transparency_kind'],
                has_transparency=sheet_meta['has_transparency'],
                sequence_id=None,
                ordinal=None,
            )
        elif sheet_sha:
            sheet_bytes = get_blob(root, pid, sheet_sha)
            sheet_meta = validate_png(sheet_bytes, filename=sheet_filename, expected_sha256=sheet_sha)
        else:
            raise ForgeError(ErrorCode.INVALID_INPUT, 'Supply sheet_sha256 or sheet_data_base64.')

        if 'grid' in data:
            rectangles = expand_grid_spec(data['grid'], sheet_meta['width'], sheet_meta['height'])
        elif 'rectangles' in data:
            rectangles = data['rectangles']
        else:
            raise ForgeError(ErrorCode.INVALID_INPUT, 'Supply rectangles or grid specification.')

        extraction_res = extract_spritesheet(
            sheet_bytes,
            extraction_id,
            name,
            rectangles,
            expected_sheet_sha256=sheet_sha,
            sheet_filename=sheet_filename,
        )

        for item in extraction_res['extracted_items']:
            raw_crop = item['_raw_bytes']
            blob = import_blob(root, pid, item['filename'], raw_crop, expected_sha256=item['extracted_sha256'])
            crop_meta = dict(
                sha256=blob['sha256'],
                filename=item['filename'],
                size=blob['size'],
                blob_path=blob['blob_path'],
                origin='AUTHORED',
                kind='IMAGE',
                width=item['width'],
                height=item['height'],
                mode=item['mode'],
                transparency_kind=item['transparency_kind'],
                has_transparency=item['has_transparency'],
                extraction_id=extraction_id,
                recipe_sha256=item['recipe_sha256'],
                source_sheet_sha256=sheet_sha,
                rect_id=item['id'],
                crop_rect=[item['x'], item['y'], item['width'], item['height']],
                ordinal=item['ordinal'],
            )
            updated.setdefault('sources', {})[blob['sha256']] = crop_meta

        extractions = updated.setdefault('extractions', [])
        existing_idx = next((i for i, ext in enumerate(extractions) if ext['id'] == extraction_id), None)
        if existing_idx is not None:
            extractions[existing_idx] = extraction_res['manifest']
        else:
            check(len(extractions) < 64, 'Maximum 64 extraction manifests per project.')
            extractions.append(extraction_res['manifest'])
    elif operation == 'apply-transform':
        from ro_sprite_forge.core.transformations import apply_transformation_recipe, validate_recipe
        recipe_data = data.get('recipe')
        check(type(recipe_data) is dict, 'Recipe object required.')
        clean_recipe = validate_recipe(recipe_data)
        src_sha = clean_recipe['source_sha256']

        # Read source bytes
        raw_source = get_blob(root, pid, src_sha)
        trans_res = apply_transformation_recipe(raw_source, clean_recipe, expected_source_sha256=src_sha)
        derived_sha = trans_res['derived_sha256']
        recipe_sha = trans_res['recipe_sha256']
        out_bytes = trans_res['output_bytes']

        # Import derived blob
        derived_filename = f"{clean_recipe['id']}.png"
        blob = import_blob(root, pid, derived_filename, out_bytes, expected_sha256=derived_sha)

        # Record source entry in manifest
        meta = trans_res['metadata']
        updated.setdefault('sources', {})[derived_sha] = dict(
            sha256=derived_sha,
            filename=derived_filename,
            size=len(out_bytes),
            blob_path=blob['blob_path'],
            origin='AUTHORED',
            kind='IMAGE',
            width=meta['width'],
            height=meta['height'],
            mode=meta['mode'],
            transparency_kind=meta['transparency_kind'],
            has_transparency=meta['has_transparency'],
            recipe_id=clean_recipe['id'],
            recipe_sha256=recipe_sha,
            source_sha256=src_sha,
            loss_report=meta['loss_report'],
        )

        # Record recipe in manifest['recipes']
        recipes = updated.setdefault('recipes', [])
        existing_idx = next((i for i, r in enumerate(recipes) if r['id'] == clean_recipe['id']), None)
        if existing_idx is not None:
            recipes[existing_idx] = trans_res['recipe']
        else:
            check(len(recipes) < 64, 'Maximum 64 recipe manifests per project.')
            recipes.append(trans_res['recipe'])

        # Optional destination assignment replacement
        dest_req = data.get('destination_requirement_id')
        if dest_req:
            intermediate_saved = save_project(root, updated, expected)
            assign_data = {
                'expected_revision': intermediate_saved['revision'],
                'mappings': [{
                    'requirement_id': dest_req,
                    'kind': 'DIRECT_SOURCE',
                    'source': f'blob-{derived_sha}',
                    'source_revision': 1,
                    'recipe': [],
                }]
            }
            res = mutate(root, intermediate_saved, 'assign', assign_data)
            res['operation'] = 'apply-transform'
            res['recipe'] = trans_res['recipe']
            res['derived_sha256'] = derived_sha
            res['loss_report'] = trans_res['metadata']['loss_report']
            return res
    elif operation == 'compile':
        from ro_sprite_forge.core.compiler import compile_resources, publish_compilation
        from ro_sprite_forge.core.project import validate_path_containment
        comp_id = data.get('compilation_id')
        check(type(comp_id) is str and 0 < len(comp_id) <= 64 and comp_id.replace('-', '').replace('_', '').isalnum(), 'Valid compilation_id required.')
        compilations = updated.setdefault('compilations', [])
        check(all(c['id'] != comp_id for c in compilations), f"DUPLICATE_COMPILATION_ID: compilation '{comp_id}' already exists.")
        check(len(compilations) < 64, 'Maximum 64 compilations per project.')

        inputs = _resolve_compile_inputs(root, updated, data)
        comp_res = compile_resources(
            inputs['act_bytes'],
            inputs['spr_bytes'],
            requirements=inputs['requirements'],
            ledger=inputs['ledger_declaration'],
            reviewed_ledger=inputs['reviewed_report'],
            source_bytes=inputs['evidence'],
            source_metadata=updated.get('sources', {}),
            project_id=pid,
            replacement_requirement_ids=inputs['replacement_requirement_ids'],
            compilation_id=comp_id,
            part=inputs['part'],
            compilation_mode=inputs['compilation_mode'],
            replacement_policy=inputs['replacement_policy'],
            isolation_strategy=inputs['isolation_strategy'],
            expected_act_sha256=inputs['res']['act'],
            expected_spr_sha256=inputs['res']['spr'],
            expected_target_revision=data.get('expected_target_revision'),
            expected_ledger_revision=data.get('expected_ledger_revision'),
            head_act_bytes=inputs['head_act_bytes'],
            head_spr_bytes=inputs['head_spr_bytes'],
            expected_head_act_sha256=inputs['head_res']['act'] if inputs['head_res'] else None,
            expected_head_spr_sha256=inputs['head_res']['spr'] if inputs['head_res'] else None,
            output_prefix=inputs['output_prefix'],
            oracle_executable=data.get('oracle_executable'),
        )

        proj_dir = Path(root) / pid
        comp_dir = validate_path_containment(proj_dir, proj_dir / 'compilations' / comp_id)
        published_paths = publish_compilation(comp_dir, comp_res)
        compilations.append(comp_res['manifest'])

        # Optionally register the compiled pair as a new candidate resource without mutating the original resource
        cand_id = data.get('register_resource_id')
        if cand_id:
            check(type(cand_id) is str and 0 < len(cand_id) <= 64 and cand_id.replace('-', '').replace('_', '').isalnum(), 'Invalid register_resource_id.')
            resources = updated.setdefault('resources', [])
            check(cand_id not in {r['id'] for r in resources}, 'Duplicate resource ID; choose a new immutable resource identity.')
            check(len(resources) < 16, 'At most 16 explicitly imported resource pairs per project.')
            inv = inventory(comp_res['act_bytes'], comp_res['spr_bytes'], actor=updated['actor'], part=inputs['part'], profile=get_profile(updated['profile']))
            for raw, ext in ((comp_res['act_bytes'], 'act'), (comp_res['spr_bytes'], 'spr')):
                blob = import_blob(root, pid, f"{cand_id}.{ext}", raw)
                updated['sources'][blob['sha256']] = blob
            resources.append(dict(id=cand_id, part=inputs['part'], act=digest(comp_res['act_bytes']), spr=digest(comp_res['spr_bytes']), inventory=inv))
    else:
        raise ForgeError(ErrorCode.INVALID_ARGUMENT,'Unknown workbench mutation.')
    result = workspace(root,updated)
    if operation == 'assign' and previous:
        old_report = resolve_ledger(previous, requirements=req, source_bytes=source_evidence(root,manifest))
        result['impact'] = compare_ledgers(old_report,resolved)
    if operation == 'compile':
        result['operation'] = 'compile'
        result['compilation'] = comp_res['manifest']
        result['published_paths'] = published_paths
    if operation == 'extract-spritesheet':
        result['operation'] = 'extract-spritesheet'
        result['extraction'] = extraction_res['manifest']
        result['extracted_count'] = len(extraction_res['extracted_items'])
    if operation == 'apply-transform':
        result['operation'] = 'apply-transform'
        result['recipe'] = trans_res['recipe']
        result['derived_sha256'] = derived_sha
        result['loss_report'] = trans_res['metadata']['loss_report']
    if operation == 'compile':
        result['operation'] = 'compile'
        result['compilation'] = comp_res['manifest']
        result['published_paths'] = published_paths
    saved = save_project(root,updated,expected)
    result['project'] = saved
    return result


def _resolve_compile_inputs(root, manifest, data):
    part = data.get('part', 'body')
    check(part in ('body', 'head'), 'Invalid compilation part.')
    resources = manifest.get('resources', [])
    res_id = data.get('resource_id')
    if res_id:
        res = next((r for r in resources if r['id'] == res_id), None)
        check(res is not None, f"RESOURCE_NOT_SELECTED_OR_MISSING: resource '{res_id}' not found.")
        check(res['part'] == part, f"PART_MISMATCH: resource '{res_id}' has part {res['part']!r}, expected {part!r}.")
    else:
        matching = [r for r in resources if r['part'] == part]
        check(len(matching) == 1, 'RESOURCE_NOT_SELECTED_OR_MISSING: specify resource_id explicitly.')
        res = matching[0]

    head_res = None
    head_act_bytes = None
    head_spr_bytes = None
    head_id = data.get('head_resource_id')
    if head_id:
        head_res = next((r for r in resources if r['id'] == head_id), None)
        check(head_res is not None and head_res['part'] == 'head', 'HEAD_RESOURCE_NOT_FOUND_OR_INVALID')
        head_act_bytes = _bytes(root, manifest, head_res['act'])
        head_spr_bytes = _bytes(root, manifest, head_res['spr'])

    act_bytes = _bytes(root, manifest, res['act'])
    spr_bytes = _bytes(root, manifest, res['spr'])
    req, _ = _context(root, manifest)
    evidence = source_evidence(root, manifest) if req is not None else {}
    _, reviewed_report = review_context(root, manifest, req) if req is not None else (None, None)

    return {
        'part': part,
        'res': res,
        'head_res': head_res,
        'act_bytes': act_bytes,
        'spr_bytes': spr_bytes,
        'head_act_bytes': head_act_bytes,
        'head_spr_bytes': head_spr_bytes,
        'requirements': req,
        'ledger_declaration': manifest.get('ledger'),
        'reviewed_report': reviewed_report,
        'evidence': evidence,
        'replacement_requirement_ids': data.get('replacement_requirement_ids'),
        'compilation_mode': data.get('compilation_mode', 'bounded_replacement'),
        'replacement_policy': data.get('replacement_policy', 'preserve_pool'),
        'isolation_strategy': data.get('isolation_strategy', 'auto'),
        'output_prefix': data.get('output_prefix') or res['id'],
    }


def compile_plan(root, manifest, data):
    """Build an inspectable pre-compilation plan without writing resources."""
    from ro_sprite_forge.core.compiler import plan_compilation
    inputs = _resolve_compile_inputs(root, manifest, data)
    return plan_compilation(
        inputs['act_bytes'],
        inputs['spr_bytes'],
        requirements=inputs['requirements'],
        ledger=inputs['ledger_declaration'],
        reviewed_ledger=inputs['reviewed_report'],
        source_bytes=inputs['evidence'],
        source_metadata=manifest.get('sources', {}),
        project_id=manifest['project_id'],
        replacement_requirement_ids=inputs['replacement_requirement_ids'],
        part=inputs['part'],
        compilation_mode=inputs['compilation_mode'],
        replacement_policy=inputs['replacement_policy'],
        isolation_strategy=inputs['isolation_strategy'],
        output_prefix=inputs['output_prefix'],
    )


def transform_preview(root, manifest, data):
    """Execute transformation recipe in-memory and return before/after preview without committing."""
    from ro_sprite_forge.core.transformations import apply_transformation_recipe, validate_recipe
    recipe_data = data.get('recipe')
    check(type(recipe_data) is dict, 'Recipe object required.')
    clean_recipe = validate_recipe(recipe_data)
    src_sha = clean_recipe['source_sha256']
    raw_source = get_blob(root, manifest['project_id'], src_sha)
    trans_res = apply_transformation_recipe(raw_source, clean_recipe, expected_source_sha256=src_sha)

    return {
        "recipe_id": clean_recipe["id"],
        "recipe_sha256": trans_res["recipe_sha256"],
        "source_sha256": src_sha,
        "derived_sha256": trans_res["derived_sha256"],
        "before_base64": base64.b64encode(raw_source).decode("ascii"),
        "after_base64": base64.b64encode(trans_res["output_bytes"]).decode("ascii"),
        "input_dimensions": trans_res["execution_record"]["input_dimensions"],
        "output_dimensions": trans_res["execution_record"]["output_dimensions"],
        "input_mode": trans_res["execution_record"]["input_mode"],
        "output_mode": trans_res["execution_record"]["output_mode"],
        "transparency_kind": trans_res["metadata"]["transparency_kind"],
        "has_transparency": trans_res["metadata"]["has_transparency"],
        "loss_report": trans_res["metadata"]["loss_report"],
        "operations": clean_recipe["operations"],
    }


def source_preview(root, manifest, data):
    """Preview a selected source or executable mirror-only reuse chain.

    Other ledger recipes retain their validation but never pretend execution.
    """
    from PIL import Image
    from ro_sprite_forge.formats.preview import transform_layer_image
    catalog = {r['source']['id']:r for r in source_catalog(root,manifest)}
    chain = []
    lineage = []
    if data.get('assignment'):
        req,_ = _context(root,manifest)
        ledger = load_ledger(manifest.get('ledger'),requirements=req)
        report = resolve_ledger(ledger,requirements=req,source_bytes=source_evidence(root,manifest))
        rows = {a['id']:a for a in report['assignments']}
        check(data['assignment'] in rows,'MISSING_ASSIGNMENT')
        assignment = rows[data['assignment']]
        check(assignment['effective_source'] is not None,'MISSING_SOURCE')
        src = assignment['effective_source']
        chain,lineage = assignment['transform_chain'],assignment['lineage']
    else:
        check(data.get('source') in catalog,'MISSING_SOURCE')
        src = catalog[data['source']]['source']
    raw = _image(root,manifest,src)
    check(digest(raw) == src['sha256'],'SOURCE_HASH_MISMATCH')
    try:
        with Image.open(io.BytesIO(raw)) as im:
            check(im.width * im.height <= 16*1024*1024,'Image budget exceeded.')
            image = im.convert('RGBA')
    except (OSError, ValueError) as exc:
        raise ForgeError(ErrorCode.INVALID_INPUT, 'SOURCE_NOT_PREVIEWABLE: image decoding failed.') from exc
    before = png_bytes(image)
    executed = all(s['operation']['op'] == 'mirror_x' for s in chain)
    if executed:
        for step in chain:
            image,_ = transform_layer_image(image,{'mirror':1})
    return dict(source=src,lineage=lineage,transform_chain=chain,
                execution='EXECUTED' if executed else 'TRANSFORMATION_NOT_EXECUTED',
                fidelity='PARTIAL',limitations=['Source inspection does not establish artistic or native acceptance.'],
                before_base64=base64.b64encode(before).decode(),
                png_base64=base64.b64encode(png_bytes(image)).decode() if executed else None)


def review_context(root, manifest, req=None, report=None):
    """Evaluate persisted decisions from current bytes, never client status flags."""
    from ro_sprite_forge.core.review import evaluate_reviews, apply_reviews
    if req is None: req,_ = _context(root,manifest)
    if req is None: return None, None
    if report is None and manifest.get('ledger'):
        report = resolve_ledger(load_ledger(manifest['ledger'],requirements=req),requirements=req,
                                source_bytes=source_evidence(root,manifest))
    evidence = {}
    reviewed_ids={m['requirement_id'] for e in manifest.get('review_events',[]) for m in e['members']}
    for a in (report or {}).get('assignments',[]):
        if a['requirement_id'] not in reviewed_ids: continue
        try:
            p = source_preview(root,manifest,dict(assignment=a['id']))
            evidence[a['requirement_id']] = _preview_evidence(p)
        except ForgeError:
            evidence[a['requirement_id']] = None
    status = evaluate_reviews(manifest['project_id'],manifest.get('review_events',[]),req,report,evidence)
    return status, apply_reviews(report,status,manifest.get('ledger'),req,source_evidence(root,manifest))


def _preview_evidence(p):
    return digest(canonical_bytes({k:v for k,v in p.items() if k not in ('before_base64','png_base64')} |
                  dict(png_sha256=digest(base64.b64decode(p['png_base64'])) if p['png_base64'] else None)))


def review_proposal(root, manifest, data):
    from ro_sprite_forge.core.review import bases, SEMANTICS, LIMITATIONS
    expected = data.get('expected_revision')
    if type(expected) is not int or expected != manifest['revision']:
        raise ForgeError(ErrorCode.CONFLICT,'Project revision conflict. Reload and inspect the current composition.')
    req,_ = _context(root,manifest)
    check(req is not None and manifest.get('ledger'), 'Assign artwork before requesting review.')
    ids = data.get('requirements')
    check(type(ids) is list and 0 < len(ids) <= 256 and all(type(r) is str for r in ids) and len(set(ids)) == len(ids),
          'Review scope requires 1–256 unique explicit requirement IDs.')
    report = resolve_ledger(load_ledger(manifest['ledger'],requirements=req),requirements=req,
                            source_bytes=source_evidence(root,manifest))
    rows = {a['requirement_id']:a for a in report['assignments']}
    layer_map = {l['id']:l for l in req['layers']}
    basis = bases(req, report)
    members=[]; previews=[]
    for rid in sorted(ids):
        check(rid in layer_map and rid in basis, 'UNASSIGNED_OR_NONEXISTENT_REVIEW_REQUIREMENT: '+rid)
        a = rows[rid]
        check(a['availability'] in ('AVAILABLE','REUSED') and a['validation'] == 'VALID', 'REVIEW_SOURCE_UNAVAILABLE_OR_INVALID: '+rid)
        p = source_preview(root,manifest,dict(assignment=a['id']))
        members.append(dict(requirement_id=rid,basis_sha256=basis[rid],evidence_sha256=_preview_evidence(p)))
        frame=next(f for f in req['frames'] if f['id']==layer_map[rid]['frame_id'])
        slot=next(s for s in req['slots'] if s['id']==frame['slot_id'])
        previews.append(dict(requirement=layer_map[rid],frame=frame,slot=slot,assignment=a,preview=p))
    # Every member is shown. No hidden group expansion or inferred art.
    from ro_sprite_forge.core.canonical import sealed
    payload = dict(schema='rsf.review-proposal/v1',project_id=manifest['project_id'],project_revision=manifest['revision'],
                   target=req['target'],members=members,preview_semantics=SEMANTICS,limitations=LIMITATIONS,
                   approvable=all(p['preview']['execution']=='EXECUTED' for p in previews),
                   exemption_allowed=all(p['assignment']['source_origin']=='CLASSIC_REFERENCE' and not p['assignment']['transform_chain'] for p in previews))
    return dict(proposal=sealed(payload),previews=previews)


def record_review(root, manifest, data):
    from ro_sprite_forge.core.review import make_event
    # Reconstruct evidence from current persisted bytes and current ledger.
    check(type(data.get('proposal')) is dict, 'Review proposal is required.')
    supplied=data['proposal']
    actual=review_proposal(root,manifest,dict(expected_revision=data.get('expected_revision'),
                                            requirements=[m['requirement_id'] for m in supplied.get('members',[])]))['proposal']
    check(actual == supplied, 'STALE_REVIEW_BASIS: reload and inspect the exact current scope.')
    decision=data.get('decision'); policy=data.get('policy')
    if decision=='APPROVED': check(actual['approvable'], 'TRANSFORMATION_NOT_EXECUTED: intended composition cannot be approved from this preview.')
    if decision=='NOT_REQUIRED': check(actual['exemption_allowed'] and data.get('structural_only') is True,
                                       'NOT_REQUIRED is restricted to unchanged classic references under explicit structural-only policy.')
    updated=copy.deepcopy(manifest)
    events=updated.setdefault('review_events',[])
    check(len(events)<4096,'Review history budget exceeded.')
    events.append(make_event(manifest['project_id'],manifest['revision'],actual['target'],decision,
                             actual['members'],len(events)+1,policy))
    result=workspace(root,updated)
    result['project']=save_project(root,updated,manifest['revision'])
    return result

"""Optional video-to-source staging using existing immutable project APIs."""
from __future__ import annotations

import copy
import base64
import re

from ro_sprite_forge.adapters.video import extract_candidates
from ro_sprite_forge.core.canonical import check, digest
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.ingestion import validate_png, validate_sequence
from ro_sprite_forge.core.project import get_blob, import_blob, load_project, save_project


def browser_safe(value):
    """Lossless JSON transport for integers outside JavaScript's exact range."""
    if type(value) is int and abs(value) > 2**53 - 1:
        return str(value)
    if isinstance(value, dict):
        return {k: browser_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [browser_safe(v) for v in value]
    return value


def wire_record(value):
    """Media DTO: all integers use canonical decimal strings; storage stays integer."""
    if type(value) is int:
        return str(value)
    if isinstance(value, dict):
        return {k: wire_record(v) for k, v in value.items()}
    if isinstance(value, list):
        return [wire_record(v) for v in value]
    return value


def exact_integer(value):
    # Strings are mandatory on this media boundary. Reject noncanonical/unsafe
    # values before converting, including JSON numbers already rounded by a client.
    check(isinstance(value, str) and len(value) <= 17 and
          re.fullmatch(r'0|-?[1-9][0-9]*', value) is not None, 'VIDEO_INVALID_SELECTION')
    result = int(value)
    check(abs(result) <= 2**53 - 1, 'VIDEO_SELECTION_INTEGER_OUT_OF_RANGE')
    return result


def media_operation(root, project_id, operation, data):
    """HTTP adapter only; decoding and publication remain RSF-28 authorities."""
    from ro_sprite_forge.adapters import video
    current = load_project(root, project_id)
    check(type(data.get('expected_revision')) is int, 'VIDEO_REVISION_REQUIRED')
    if data['expected_revision'] != current['revision']:
        raise ForgeError(ErrorCode.CONFLICT, 'VIDEO_STALE_PROJECT_REVISION')
    expected = data.get('expected_sha256')
    check(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected) is not None,
          'VIDEO_SOURCE_HASH_REQUIRED')
    check(not any(k in data for k in ('path', 'url', 'filename', 'arguments', 'filter')), 'VIDEO_LOCAL_BYTES_REQUIRED')
    if 'source_sha256' in data:
        check('data_base64' not in data, 'VIDEO_AMBIGUOUS_SOURCE')
        sha = data['source_sha256']
        check(sha == expected and current['sources'].get(sha, {}).get('kind') == 'VIDEO', 'VIDEO_INVALID_SOURCE')
        raw = get_blob(root, project_id, sha)
    else:
        try:
            encoded = data['data_base64']
            check(isinstance(encoded, str) and len(encoded) <= (video.MAX_BLOB_SIZE + 2)//3*4,
                  'VIDEO_SIZE_EXCEEDED_OR_EMPTY')
            raw = base64.b64decode(encoded, validate=True)
        except (KeyError, ValueError, TypeError) as exc:
            raise ForgeError(ErrorCode.INVALID_INPUT, 'VIDEO_INVALID_BASE64') from exc
    if operation == 'video-metadata':
        return wire_record(video.probe_video(raw, expected_sha256=expected))
    stream = exact_integer(data.get('stream_index'))
    if operation == 'video-frames':
        return wire_record(video.inspect_video(raw, stream_index=stream, expected_sha256=expected))
    mode = data.get('mode')
    values = data.get('values')
    check(type(values) is list and 0 < len(values) <= video.MAX_CANDIDATES, 'VIDEO_SELECTION_COUNT_EXCEEDED_OR_EMPTY')
    values = [exact_integer(v) for v in values]
    if operation == 'video-preview':
        result = video.extract_candidates(raw, stream_index=stream, mode=mode, values=values, expected_sha256=expected)
        return dict(manifest=wire_record(result['manifest']),
                    pngs=[base64.b64encode(p).decode('ascii') for p in result['pngs']])
    check(operation == 'video-stage', 'VIDEO_UNSUPPORTED_OPERATION')
    preview_sha = data.get('preview_sha256')
    check(isinstance(preview_sha, str) and re.fullmatch('[0-9a-f]{64}', preview_sha) is not None,
          'VIDEO_PREVIEW_REQUIRED')
    updated = stage_video(root, project_id, raw, expected_revision=data['expected_revision'],
                          stream_index=stream, mode=mode, values=values,
                          expected_sha256=expected, expected_preview_sha256=preview_sha)
    return dict(revision=updated['revision'], collection=wire_record(next(
        r for r in updated['video_imports'] if r['canonical_sha256'] == preview_sha)))


def stage_video(root, project_id: str, raw: bytes, *, expected_revision: int,
                stream_index: int | None, mode: str, values: list[int],
                expected_sha256: str | None = None, expected_preview_sha256: str | None = None) -> dict:
    """Validate the complete batch before publishing a single project revision.

    Extraction is private and temporary. A save conflict/error may leave unreferenced
    content-addressed blobs, as with existing PNG ingestion, but no partial collection
    is committed. Previously referenced blobs, assignments and reviews are untouched.
    """
    current = load_project(root, project_id)
    if type(expected_revision) is not int or current['revision'] != expected_revision:
        raise ForgeError(ErrorCode.CONFLICT, 'VIDEO_STALE_PROJECT_REVISION')
    result = extract_candidates(raw, stream_index=stream_index, mode=mode, values=values,
                                expected_sha256=expected_sha256)
    record, pngs = result['manifest'], result['pngs']
    if expected_preview_sha256 is not None:
        check(record['canonical_sha256'] == expected_preview_sha256, 'VIDEO_PREVIEW_IDENTITY_CHANGED')
    # The only producer is the bounded extraction API; validate every PNG again at
    # the persistence boundary before any source reference can be committed.
    check(len(record['items']) == len(pngs), 'VIDEO_OUTPUT_COUNT_MISMATCH')
    for item, png in zip(record['items'], pngs):
        validate_png(png, expected_sha256=item['png_sha256'])
    # Extraction can take time. Even an idempotent request must honor the caller's
    # revision and observe any intervening project update.
    current = load_project(root, project_id)
    if current['revision'] != expected_revision:
        raise ForgeError(ErrorCode.CONFLICT, 'VIDEO_STALE_PROJECT_REVISION')
    sha = record['canonical_sha256']
    if any(v['canonical_sha256'] == sha for v in current.get('video_imports', [])):
        return current
    check(len(current.get('video_imports', [])) < 64, 'VIDEO_COLLECTION_LIMIT_EXCEEDED')
    check(len(current.get('sequences', [])) < 64, 'Maximum 64 sequences per project.')
    updated = copy.deepcopy(current)
    source_sha = digest(raw)
    blob = import_blob(root, project_id, f'video-{source_sha}.media', raw, expected_sha256=source_sha)
    updated['sources'].setdefault(source_sha, dict(**blob, kind='VIDEO', origin='UNVERIFIED'))
    frames = []
    sequence_id = 'video-' + sha[:56]
    for item, png in zip(record['items'], pngs):
        filename = 'video-frame-' + item['png_sha256'][:32] + '.png'
        blob = import_blob(root, project_id, filename, png, expected_sha256=item['png_sha256'])
        meta = validate_png(png, filename)
        updated['sources'].setdefault(blob['sha256'], dict(**blob, kind='IMAGE', origin='UNVERIFIED',
            **{k:meta[k] for k in ('width','height','mode','transparency_kind','has_transparency')}))
        frames.append(dict(ordinal=item['order'], sha256=blob['sha256'], filename=filename,
            **{k:meta[k] for k in ('width','height','mode','transparency_kind','has_transparency')}))
    sequence = validate_sequence(sequence_id, 'Video candidates ' + sha[:16], frames)
    updated.setdefault('sequences', []).append(sequence)
    updated.setdefault('video_imports', []).append(record)
    # Re-read newly persisted content before the manifest commit. save_project
    # independently checks the current revision under its established project lock.
    for expected in [source_sha, *(item['png_sha256'] for item in record['items'])]:
        get_blob(root, project_id, expected)
    return save_project(root, updated, expected_revision)

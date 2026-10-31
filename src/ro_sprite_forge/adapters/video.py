"""Optional, bounded local FFmpeg adapter; candidate PTS never implies ACT timing.

Only self-contained MOV/MP4, Matroska/WebM and AVI containers and the declared
8-bit SDR decoder set are supported. System executables are resolved from
os.defpath, never from a project, request or working directory.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from typing import Callable

from ro_sprite_forge.core.canonical import canonical_bytes, check, digest, sealed
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.ingestion import validate_png
from ro_sprite_forge.core.project import MAX_BLOB_SIZE

POLICY = 'rsf.video-rgba-presentation/v1'
MAX_FRAMES = 4096
MAX_CANDIDATES = 64
MAX_DECODE_PIXELS = 256 * 1024 * 1024
MAX_SECONDS = 120
MAX_CAPTURE = 2 * 1024 * 1024
MAX_OUTPUT = 64 * 1024 * 1024
TIMEOUT = 30
CODECS = ('ffv1', 'png', 'h264', 'vp8', 'vp9', 'mpeg4')
PIXFMTS = ('rgba', 'bgra', 'rgb24', 'bgr24', 'bgr0', 'rgb0', 'gray',
           'yuv420p', 'yuv422p', 'yuv444p', 'yuvj420p', 'yuvj422p', 'yuvj444p', 'yuva420p')
INPUT_OPTIONS = ['-max_alloc', '67108864', '-protocol_whitelist', 'file',
                 '-format_whitelist', 'matroska,webm,mov,avi', '-threads', '1']


def fail(reason: str, message: str = '') -> None:
    raise ForgeError(ErrorCode.INVALID_INPUT, reason + (': ' + message if message else ''))


def read_local_video(path: str | Path) -> bytes:
    """Operator-supplied regular file, read once with a hard cap; no URL or symlink."""
    p = Path(path)
    if '\x00' in str(path) or '://' in str(path) or '..' in p.parts or ':' in str(path):
        fail('VIDEO_LOCAL_FILE_REQUIRED')
    if any(q.is_symlink() for q in (p, *p.parents)):
        fail('VIDEO_SYMLINK_REJECTED')
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            fail('VIDEO_LOCAL_FILE_REQUIRED')
        with os.fdopen(fd, 'rb') as f:
            raw = f.read(MAX_BLOB_SIZE + 1)
    except OSError as exc:
        raise ForgeError(ErrorCode.IO_ERROR, 'VIDEO_READ_FAILED') from exc
    _source(raw, None)
    return raw


def _source(raw: bytes, expected: str | None) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BLOB_SIZE:
        fail('VIDEO_SOURCE_SIZE_EXCEEDED_OR_EMPTY')
    sha = digest(raw)
    if expected is not None and expected != sha:
        fail('VIDEO_SOURCE_HASH_MISMATCH')
    return dict(sha256=sha, size=len(raw))


def _run(executable: str, args: list[str], directory: Path, *,
         timeout: float = TIMEOUT, on_line: Callable[[str], None] | None = None) -> tuple[bytes, bytes]:
    """Bound pipes/disk/runtime while draining; kill/reap the entire isolated group."""
    if sys.platform != 'linux':
        fail('VIDEO_PLATFORM_UNSUPPORTED', 'bounded child limits require Linux')
    worker = str(Path(__file__).with_name('_media_exec.py'))
    command = [sys.executable, '-I', worker, executable, *args]
    buffers = {1: bytearray(), 2: bytearray()}
    pending = bytearray()
    proc = None
    started = time.monotonic()
    try:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=directory, env={'PATH': os.defpath, 'LC_ALL': 'C', 'TZ': 'UTC'},
            shell=False, start_new_session=True, close_fds=True)
        with selectors.DefaultSelector() as sel:
            sel.register(proc.stdout, selectors.EVENT_READ, 1)
            sel.register(proc.stderr, selectors.EVENT_READ, 2)
            while sel.get_map():
                if time.monotonic() - started > timeout:
                    fail('VIDEO_PROCESS_TIMEOUT')
                # Files are ours in a private temporary directory; child cannot choose paths.
                if sum(p.stat().st_size for p in directory.iterdir() if p.is_file()) > MAX_BLOB_SIZE + MAX_OUTPUT:
                    fail('VIDEO_TEMP_BUDGET_EXCEEDED')
                for key, _ in sel.select(0.02):
                    chunk = os.read(key.fileobj.fileno(), 16384)
                    if not chunk:
                        sel.unregister(key.fileobj)
                        continue
                    target = buffers[key.data]
                    target.extend(chunk)
                    if len(target) > MAX_CAPTURE:
                        fail('VIDEO_PROCESS_OUTPUT_EXCEEDED')
                    if key.data == 1 and on_line:
                        pending.extend(chunk)
                        while b'\n' in pending:
                            line, _, rest = pending.partition(b'\n')
                            pending[:] = rest
                            on_line(line.decode('utf-8', errors='strict'))
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                fail('VIDEO_PROCESS_TIMEOUT')
            try:
                code = proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                fail('VIDEO_PROCESS_TIMEOUT')
            if on_line and pending:
                on_line(pending.decode('utf-8', errors='strict'))
            if code:
                fail('VIDEO_PROCESS_FAILED', f'exit={code}; ' + buffers[2][-2048:].decode('utf-8', errors='replace'))
    except UnicodeError as exc:
        raise ForgeError(ErrorCode.INVALID_INPUT, 'VIDEO_INVALID_PROCESS_OUTPUT') from exc
    except OSError as exc:
        raise ForgeError(ErrorCode.IO_ERROR, 'VIDEO_PROCESS_START_FAILED') from exc
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            if proc.stdout: proc.stdout.close()
            if proc.stderr: proc.stderr.close()
    return bytes(buffers[1]), bytes(buffers[2])


def _tool(name: str, directory: Path) -> tuple[str, dict]:
    exe = shutil.which(name, path=os.defpath)
    if not exe:
        fail('VIDEO_TOOL_UNAVAILABLE', name)
    out, _ = _run(exe, ['-version'], directory)
    raw_exe = Path(exe).read_bytes()
    return exe, dict(version=out.decode('utf-8').splitlines()[0],
                     version_report_sha256=digest(out), executable_sha256=digest(raw_exe))


def capabilities() -> dict:
    result = dict(policy=POLICY, platform=sys.platform, codecs=list(CODECS),
                  containers=['mov/mp4', 'matroska/webm', 'avi'], output='PNG RGBA8; no autorotation, scaling, FPS conversion or interpolation',
                  limits=dict(input_bytes=MAX_BLOB_SIZE, candidates=MAX_CANDIDATES, decoded_frames=MAX_FRAMES,
                              decoded_pixels=MAX_DECODE_PIXELS, seconds=MAX_SECONDS, process_seconds=TIMEOUT,
                              capture_bytes=MAX_CAPTURE, output_bytes=MAX_OUTPUT))
    with tempfile.TemporaryDirectory(prefix='rsf-video-') as tmp:
        for name in ('ffprobe', 'ffmpeg'):
            try:
                _, identity = _tool(name, Path(tmp))
                result[name] = dict(available=True, **identity)
            except ForgeError as exc:
                result[name] = dict(available=False, diagnostic=exc.message)
    result['available'] = sys.platform == 'linux' and all(result[n]['available'] for n in ('ffprobe', 'ffmpeg'))
    return result


def _integer(value):
    if value is None or value == 'N/A': return None
    try:
        return int(value)
    except (ValueError, TypeError):
        fail('VIDEO_INVALID_METADATA', 'expected integer')


def _rational(value):
    if value is None or value == 'N/A' or value == '0/0': return None
    try:
        parts = str(value).split('/')
        n, d = (int(parts[0]), int(parts[1])) if len(parts) == 2 else (Fraction(str(value)).numerator, Fraction(str(value)).denominator)
        if d <= 0: raise ValueError()
        return dict(numerator=n, denominator=d)
    except (ValueError, ZeroDivisionError):
        fail('VIDEO_INVALID_METADATA', 'expected rational')


def _fraction(value: dict) -> Fraction:
    return Fraction(value['numerator'], value['denominator'])


def _dimensions(width, height):
    if type(width) is not int or type(height) is not int or not 0 < width <= 4096 or not 0 < height <= 4096:
        fail('VIDEO_DIMENSION_EXCEEDED')


def _probe_metadata(directory: Path, probe: str):
    entries = ('format=format_name,start_time,duration:stream=index,codec_type,codec_name,width,height,coded_width,coded_height,'
               'pix_fmt,time_base,start_pts,duration_ts,r_frame_rate,avg_frame_rate,nb_frames,color_transfer,color_space,color_range')
    out, _ = _run(probe, ['-v', 'error', *INPUT_OPTIONS, '-show_entries', entries,
                          '-of', 'json', 'source.media'], directory)
    try:
        doc = json.loads(out)
        streams = doc['streams']
        fmt = doc['format']
        if not isinstance(streams, list) or len(streams) > 16: fail('VIDEO_STREAM_LIMIT_EXCEEDED')
        video_streams = [s for s in streams if s['codec_type'] == 'video']
        if not video_streams: fail('VIDEO_NO_VIDEO_STREAM')
    except (KeyError, ValueError, TypeError) as exc:
        raise ForgeError(ErrorCode.INVALID_INPUT, 'VIDEO_INVALID_METADATA') from exc
    return fmt, video_streams


def _inspect(raw: bytes, stream_index: int | None, directory: Path, probe: str, tool: dict) -> dict:
    fmt, video_streams = _probe_metadata(directory, probe)
    try:
        choices = [s['index'] for s in video_streams]
        if stream_index is None:
            if len(choices) != 1: fail('VIDEO_STREAM_SELECTION_REQUIRED')
            stream_index = choices[0]
        if type(stream_index) is not int or stream_index not in choices: fail('VIDEO_INVALID_STREAM')
        s = next(s for s in video_streams if s['index'] == stream_index)
        if s.get('codec_name') not in CODECS or s.get('pix_fmt') not in PIXFMTS:
            fail('VIDEO_UNSUPPORTED_DECODER_OR_PIXEL_FORMAT')
        if s.get('color_transfer') in ('smpte2084', 'arib-std-b67'):
            fail('VIDEO_UNSUPPORTED_HDR')
        _dimensions(s['width'], s['height'])
        tb = _rational(s.get('time_base'))
        if tb is None or _fraction(tb) <= 0: fail('VIDEO_MISSING_TIME_BASE')
        duration = _rational(fmt.get('duration'))
        if duration and _fraction(duration) > MAX_SECONDS: fail('VIDEO_DURATION_EXCEEDED')
    except (KeyError, ValueError, TypeError) as exc:
        raise ForgeError(ErrorCode.INVALID_INPUT, 'VIDEO_INVALID_METADATA') from exc
    frames = []
    pixels = 0
    def frame_line(line):
        nonlocal pixels
        if not line.strip(): return
        fields = dict(part.split('=', 1) for part in line.split('|') if '=' in part)
        if 'width' not in fields: return
        w, h = _integer(fields['width']), _integer(fields['height'])
        _dimensions(w, h)
        if (w, h) != (s['width'], s['height']): fail('VIDEO_DYNAMIC_DIMENSIONS_UNSUPPORTED')
        pixels += w * h
        if len(frames) >= MAX_FRAMES or pixels > MAX_DECODE_PIXELS: fail('VIDEO_DECODE_BUDGET_EXCEEDED')
        pts = _integer(fields.get('pts'))
        if pts is not None and frames and frames[0]['pts'] is not None:
            if abs((pts - frames[0]['pts']) * _fraction(tb)) > MAX_SECONDS: fail('VIDEO_DURATION_EXCEEDED')
        frames.append(dict(ordinal=len(frames), pts=pts, best_effort_timestamp=_integer(fields.get('best_effort_timestamp')),
                           packet_dts=_integer(fields.get('pkt_dts')), picture_type=fields.get('pict_type')))
    _run(probe, ['-v', 'error', *INPUT_OPTIONS, '-select_streams', str(stream_index), '-show_frames',
         '-show_entries', 'frame=pts,best_effort_timestamp,pkt_dts,width,height,pict_type',
         '-of', 'compact=p=0:nk=0', 'source.media'], directory, on_line=frame_line)
    if not frames: fail('VIDEO_NO_DECODED_FRAMES')
    pts_list = [f['pts'] for f in frames]
    intervals = [b-a for a,b in zip(pts_list, pts_list[1:]) if a is not None and b is not None]
    timing = 'UNKNOWN' if any(p is None for p in pts_list) or len(intervals) < 2 else (
        'IRREGULAR_PTS' if len(set(intervals)) > 1 else 'REGULAR_PTS_OBSERVED')
    # Preserve metadata strings/rationals exactly where meaningful; no filenames/tags in identity.
    clean_streams = _clean_streams(video_streams)
    return sealed(dict(schema='rsf.video-inspection/v1', source=_source(raw, None), policy=POLICY,
        ffprobe=tool, container=dict(format=fmt.get('format_name'), start=_rational(fmt.get('start_time')), duration=duration),
        streams=clean_streams, selected_stream=stream_index, stream_selection='ONLY_VIDEO_STREAM' if len(choices)==1 else 'EXPLICIT',
        time_base=tb, timing=timing, decoded_frame_count=len(frames), frames=frames))


def _clean_streams(video_streams):
    clean_streams = []
    for item in video_streams:
        clean = {k:item.get(k) for k in ('index','codec_name','width','height','coded_width','coded_height','pix_fmt','color_transfer','color_space','color_range')}
        clean.update({k:_rational(item.get(k)) for k in ('time_base','r_frame_rate','avg_frame_rate')})
        clean.update({k:_integer(item.get(k)) for k in ('start_pts','duration_ts','nb_frames')})
        clean_streams.append(clean)
    return clean_streams


def probe_video(raw: bytes, *, expected_sha256: str | None = None) -> dict:
    """Container/stream metadata only: no frame decode until explicit inspection."""
    _source(raw, expected_sha256)
    with tempfile.TemporaryDirectory(prefix='rsf-video-') as tmp:
        directory = Path(tmp)
        (directory/'source.media').write_bytes(raw)
        probe, tool = _tool('ffprobe', directory)
        fmt, streams = _probe_metadata(directory, probe)
        return dict(source=_source(raw, None), policy=POLICY, ffprobe=tool,
                    container=dict(format=fmt.get('format_name'), start=_rational(fmt.get('start_time')),
                                   duration=_rational(fmt.get('duration'))), streams=_clean_streams(streams))


def inspect_video(raw: bytes, *, stream_index: int | None = None, expected_sha256: str | None = None) -> dict:
    _source(raw, expected_sha256)
    with tempfile.TemporaryDirectory(prefix='rsf-video-') as tmp:
        directory = Path(tmp)
        (directory/'source.media').write_bytes(raw)
        probe, tool = _tool('ffprobe', directory)
        return _inspect(raw, stream_index, directory, probe, tool)


def _selection(mode: str, values: list[int]) -> None:
    if mode not in ('ordinal', 'pts'): fail('VIDEO_UNSUPPORTED_SELECTION')
    if type(values) is not list or not 0 < len(values) <= MAX_CANDIDATES: fail('VIDEO_SELECTION_COUNT_EXCEEDED_OR_EMPTY')
    if any(type(v) is not int or abs(v) > 2**53-1 for v in values): fail('VIDEO_INVALID_SELECTION')
    if len(set(values)) != len(values): fail('VIDEO_DUPLICATE_SELECTION')


def _resolve(inspection: dict, mode: str, values: list[int]) -> list[dict]:
    _selection(mode, values)
    frames = inspection['frames']
    selected = []
    for value in values:
        found = [f for f in frames if f['ordinal' if mode=='ordinal' else 'pts'] == value]
        if len(found) != 1: fail('VIDEO_SELECTION_NOT_EXACT', f'{mode}={value}; matches={len(found)}')
        selected.append(found[0])
    return selected


def extract_candidates(raw: bytes, *, stream_index: int | None, mode: str,
                       values: list[int], expected_sha256: str | None = None) -> dict:
    """Preview API: returns validated PNG bytes and sealed provenance, no persistence."""
    _source(raw, expected_sha256)
    # Reject malformed requests before starting any process.
    _selection(mode, values)
    with tempfile.TemporaryDirectory(prefix='rsf-video-') as tmp:
        directory = Path(tmp)
        (directory/'source.media').write_bytes(raw)
        probe, probe_id = _tool('ffprobe', directory)
        ffmpeg, decoder_id = _tool('ffmpeg', directory)
        inspection = _inspect(raw, stream_index, directory, probe, probe_id)
        selected = _resolve(inspection, mode, values)
        unique = sorted(f['ordinal'] for f in selected)
        expression = '+'.join(f'eq(n\\,{n})' for n in unique)
        args = ['-nostdin', '-hide_banner', '-loglevel', 'info', '-xerror', '-cpuflags', '0', '-filter_threads', '1',
                '-copyts', *INPUT_OPTIONS, '-hwaccel', 'none', '-noautorotate', '-i', 'source.media',
                '-map', '0:'+str(inspection['selected_stream']), '-an', '-sn', '-dn',
                '-vf', 'showinfo=checksum=0,select='+expression+',format=rgba',
                '-fps_mode', 'passthrough', '-frames:v', str(len(unique)), '-c:v', 'png', '-threads:v', '1',
                '-bitexact', '-compression_level', '9', '-pred', 'mixed', '-start_number', '0', 'frame-%04d.png']
        _, err = _run(ffmpeg, args, directory)
        # Native filter observations bind PNG order to actual presentation ordinals/PTS.
        text = err.decode('utf-8', errors='replace')
        time_bases = re.findall(r'config in time_base:\s*(\d+)/(\d+)', text)
        if not time_bases or any(Fraction(int(n),int(d)) != _fraction(inspection['time_base']) for n,d in time_bases):
            fail('VIDEO_EXTRACTION_TIME_BASE_MISMATCH')
        observed = {int(n):None if p == 'NOPTS' else int(p) for n,p in
                    re.findall(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+|NOPTS)', text)}
        for f in selected:
            # For missing source PTS do not pass through a generated timestamp as source identity.
            actual = observed.get(f['ordinal'], 'MISSING')
            expected = f['pts'] if f['pts'] is not None else f['best_effort_timestamp']
            if actual != expected: fail('VIDEO_EXTRACTED_SELECTION_MISMATCH')
        files = sorted(directory.glob('frame-*.png'))
        if len(files) != len(unique): fail('VIDEO_OUTPUT_COUNT_MISMATCH')
        payloads = {}
        total = 0
        for ordinal, path in zip(unique, files):
            data = path.read_bytes()
            total += len(data)
            if total > MAX_OUTPUT: fail('VIDEO_OUTPUT_BUDGET_EXCEEDED')
            meta = validate_png(data)
            stream = next(s for s in inspection['streams'] if s['index']==inspection['selected_stream'])
            if (meta['width'],meta['height']) != (stream['width'],stream['height']) or meta['mode'] != 'RGBA':
                fail('VIDEO_OUTPUT_REPRESENTATION_MISMATCH')
            payloads[ordinal] = data
        items = []
        for order, (requested, frame) in enumerate(zip(values, selected)):
            data = payloads[frame['ordinal']]
            meta = validate_png(data)
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                pixel_hash = digest(image.tobytes())
            items.append(dict(order=order, requested=requested, ordinal=frame['ordinal'], pts=frame['pts'],
                best_effort_timestamp=frame['best_effort_timestamp'], time_base=inspection['time_base'],
                png_sha256=digest(data), rgba_sha256=pixel_hash, width=meta['width'], height=meta['height'],
                size=len(data), mode=meta['mode'], transparency_kind=meta['transparency_kind'], has_transparency=meta['has_transparency']))
        manifest = sealed(dict(schema='rsf.video-candidates/v1', policy=POLICY, inspection=inspection,
            ffmpeg=decoder_id, request=dict(stream=inspection['selected_stream'], mode=mode, values=values,
            ordering='REQUEST_ORDER', timestamp_policy='EXACT_SOURCE_PTS_ONLY', decoder_threads=1,
            synchronization='PASSTHROUGH', autorotate=False, output='RGBA8_PNG_BITEXACT'),
            items=items, visual_review='UNVERIFIED', automatic_assignment=False))
        return dict(manifest=manifest, pngs=[payloads[f['ordinal']] for f in selected])

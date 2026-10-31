# RSF-28 optional local candidate-frame adapter

Implementation and self-verification are complete locally; independent QA and live
acceptance are recorded separately below when obtained. This task adds candidate
sources to the existing image pipeline. M6 remains open for later tasks. No artwork
assignment, approval, ACT timing, pose inference or M5 implementation is changed.

## Contract and scope

The live RSF-28 task has four acceptance criteria, captured verbatim in
`kaneo-start.json`. Codex account `aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn` claimed
an unassigned task, verified RSF-26 Accepted, and read back ownership plus Ready and
In Progress before source changes. Plan v1.1 SHA-256 is
`5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e`.

The adapter supports local regular files/immutable byte input, self-contained
MOV/MP4, Matroska/WebM and AVI, and the explicitly listed FFV1/PNG/H264/VP8/VP9/MPEG4
8-bit SDR decoder/pixel-format subset. Other codecs, HDR, changing dimensions,
missing time base and ambiguous streams fail explicitly. It enumerates video
streams; one video stream is selected deterministically, multiple video streams
require an absolute stream index. Audio is ignored.

`video-inspect` reports actual container/stream metadata, nullable unknown values,
exact rational time base/rates, decoded presentation ordinals, integer source PTS,
best-effort timestamps, packet DTS and picture type. Observed regular intervals do
not certify a stream is universally CFR. Irregular PTS is reported explicitly.
Frame count is measured within the bounded decode; unavailable metadata counts
stay null. Container duration is not treated as authoritative frame timing.

`video-extract` writes a preview bundle of PNGs and `video-candidates.json` through
the accepted atomic bundle publisher. `video-stage` explicitly commits candidates
to an existing project after extraction. The API also returns PNG bytes for preview.
No workbench controls or HTTP routes changed. Existing source tray discovers the
committed PNGs; existing explicit assignment/review workflows remain authoritative.
Browser tests are NOT_RUN because no browser-facing control changed.

## Selection and timestamp semantics

Selections are either unique zero-based **presentation ordinals**, or unique exact
integer **source PTS** in the inspected stream time base. Request order determines
candidate collection order; every item also retains its original presentation
ordinal. Inexact, absent, ambiguous and out-of-range timestamp requests fail rather
than selecting a nearby frame. Duplicate selections are rejected. Missing source
PTS stays null; ordinal selection requires native decode observations to agree with
available source/best-effort timing. No nominal-FPS arithmetic is used.

FFmpeg's native `showinfo` instrumentation before `select` binds actual decoder
presentation ordinal/PTS/time base to output PNG order. Both must agree with
FFprobe. `-copyts`, `-fps_mode passthrough`, generated validated-integer selection,
software decoding, one decoder/filter/output thread, disabled CPU-specific
optimizations, no autorotation and explicit RGBA8 PNG/bitexact settings avoid
implicit FPS conversion, interpolation, scaling or crop filters. Dimensions and
RGBA output are verified after extraction. Display-order B-frame coverage is
separate from exact lossless pixel checks. Video time is never assigned to ACT.

The FFprobe/showinfo semantics follow the primary documentation:
[FFprobe frame reports](https://ffmpeg.org/ffprobe.html),
[FFmpeg filtering diagnostics](https://ffmpeg.org/ffmpeg-filters.html#showinfo),
[FFmpeg synchronization options](https://ffmpeg.org/ffmpeg.html).

## Optional dependencies and execution bounds

The package retains zero mandatory Python dependencies; no media executable is
resolved or started on core import, PNG ingestion, project load or ordinary SPR/ACT
work. Explicit video operations resolve FFprobe/FFmpeg from the fixed system
`os.defpath`, record binary SHA-256/version-report SHA-256 and report typed missing
capabilities. Pillow is used through the existing optional PNG validator.

Subprocess calls use argument arrays, `shell=False`, closed stdin, a private cwd,
a fresh session/process group and a fixed locale/environment. A child-only helper
sets Linux RLIMIT_AS/CPU/FSIZE/NOFILE/CORE, avoiding preexec_fn in threaded callers.
URLs, traversal and symlink file inputs are rejected. Only whitelisted local file
protocol/container demuxers are enabled; request values cannot supply filters,
commands, executable paths or output destinations to FFmpeg. Only generated
`source.media` and `frame-%04d.png` names reach it.

Limits: source 32 MiB, 16 streams, dimensions 4096 each, 4096 inspected frames,
256 Mi decoded pixels, 120 seconds, 64 candidates, 64 MiB total output, 30 seconds
per process, 2 MiB per captured pipe. Temporary usage is monitored while running;
per-file output is capped at 32 MiB, process address space at 1 GiB, CPU at 30s,
open descriptors at 64 and core dumps disabled. These are Linux bounds, not a
claim of an OS security sandbox. Other platforms return an unsupported diagnostic.
All failure/timeout/callback paths kill the process group, reap the child and close
pipes. Tests verify no live grandchild after timeout; an init-owned zombie may
briefly remain outside this process's reaping authority.

## Provenance and storage

`rsf.video-candidates/v1` records source hash/size, complete bounded inspection,
toolchain identities, versioned extraction policy, requested/actual selections,
ordered PNG and RGBA pixel hashes, dimensions and technical transparency status.
Canonical records contain no paths, wall-clock times, random names or cwd. The
closed standalone JSON Schema is also embedded in `rsf.project/v1`.

All PNGs are revalidated with RSF-19 before any manifest publication, then imported
through existing content-addressed blobs and ordered sequence validation. Video
bytes are retained as an immutable source blob. Optimistic revision is checked
before and after extraction; existing project save checks it again under its lock.
Identical imports reuse source/output blobs and the existing collection without
advancing project revision. Distinct requests preserve distinct collection records.
Save/reopen validates referenced blob hashes. Candidate origin/review remains
UNVERIFIED; no assignments or approval records are created.

Extraction is all-or-fail before staging. Save conflicts/errors can leave
unreferenced immutable blobs, as existing PNG ingestion does; no partial collection
is committed. This is not a claim of whole-filesystem crash atomicity. Corrupt
committed sources fail reopening, and a failed preview never publishes a bundle.

## Reproduction and evidence

```bash
.venv/bin/python -m unittest discover -s tests -p test_video.py -v
.venv/bin/python docs/verification/rsf-28/reproduce.py --output /tmp/rsf28-reproduced
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v
.venv/bin/python scripts/check_video_schema.py
.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14
```

Use a fresh reproduction directory. `commands.json` lists every regression command,
actual exit status and log. `reproduction.log` and retained `synthetic/results.json`
record the actual FFmpeg generation commands and clean CLI extraction/staging
invocations. Synthetic RGB frames are constructed independently with Pillow; exact
RGBA equality is required on FFV1. CFR PTS is 0/40/80/120/160; VFR is
0/40/120/160/300, both in 1/1000 units. Request [300,0,120] must yield original
ordinals [4,0,2]. MPEG4 B-frames test presentation ordering; no lossless pixel claim
is made for lossy codecs. Multi-stream, unsupported rawvideo, corrupt PNG/count/PTS,
malformed media, source hashes, selection injection, timeout/pipe/disk budgets,
immutable staging and failed/racing commits have focused regressions.

Test environment: Python 3.14.4, Ubuntu 26.04.1 Linux x86_64, FFmpeg and FFprobe
8.0.1-3ubuntu2. Python 3.12/3.13 are NOT_RUN (not installed). Native/Rust GPU
corridors are NOT_RUN for this adapter because no format/compiler/native code
changed. Existing public/private compiler regressions are run. M5-S, M5-I and
bounded M5-N retain their prior accepted scope; this task grants no new native,
artistic or production acceptance.

Results, independent QA verdict and final tracker read-back are appended at completion.

## Coordinator results at QA handoff

- Focused: 26 PASS; full public: 478 PASS, exit 0.
- Private: 40 PASS, one existing legacy native-report skip, exit 0.
- Schemas: all 11 PASS, exit 0 each (10 existing plus video).
- Installed distribution: 468 PASS, 10 optional skips out of 478, exit 0;
  stdlib-only smoke PASS; repeated clean wheels identical; private art excluded.
- Two clean CLI extractions: identical canonical manifests and PNG bytes, zero
  lossless RGBA mismatches. Original source and staged/reopened source hashes match.
- No browser/native GPU rerun; Python 3.12/3.13 unavailable as noted above.

Initial public regression failed only on the accepted RSF-27 synthetic evidence
files. The artifact guard now permits four exact path/hash pairs; modified or
unlisted ACT/SPR/GRF files remain rejected. The four accepted binaries are unchanged.
An initial new schema checker incorrectly compared standalone $schema/$id
annotations with their embedded form; comparison now excludes only those annotations,
while validating both complete schemas. Initial failing logs are retained.

Synthetic VFR source SHA-256:
`51f0173b6b4dfd615acf3cb9d55e8131dd87c28b8e528098668b9fefd4c53a9d`.
Canonical extraction SHA-256:
`8f92a9dfd224fdf3275a835caa14a8e04f5b03bf367d026520c28e2aa55a44e3`.
The three PNG hashes and independent expected RGBA hashes are in
`synthetic/results.json`. These claims apply to the recorded FFmpeg 8.0.1 Linux
build; arbitrary decoder versions/backends are not claimed byte-identical.

Independent review is pending at this handoff; no self-acceptance is claimed.

## Independent completion

The separate repository-configured forge_qa_reviewer returned **QA_PASS** after
independent focused/public/private/schema/distribution execution and fresh CLI
reproduction. Additional reviewer fixtures confirmed partial-alpha RGBA integrity
and an audio-first container's absolute video stream index. See QA_REPORT.md for
commands, results, live criteria, hash validation and limitations. No implementation
correction was required by QA. The initial evidence seal mismatch was refreshed
and independently verified before PASS. The reviewed implementation seal is
0f48666f07fa98ea39f5f58810d54cc5631cdf2b57e8b2be7742573aef4e91a5;
completion evidence is sealed separately without changing reviewed source files.

Kaneo final acceptance/readback and the next eligible task are retained in
kaneo-final-readback.json and next-task-readback.json. RSF-28 is a bounded candidate
adapter, not full M6 closure. M5-S/I/bounded-N retain accepted scope; no artwork,
production export or new native rendering acceptance is conferred here.

Final MCP readback confirms Accepted (done), Codex ownership preserved, all four
criteria checked and independent QA comment a9hq03kbtuwiegqklvhfj7c2 present. No
pending writes. Workflow: Backlog -> Ready -> In Progress -> QA Review -> Accepted.
Next live eligible task is RSF-29, vky1aihwa7vdpeqvv40r33ig, Backlog/unassigned;
its RSF-28 and RSF-18 blockers are Accepted. It has not been started.

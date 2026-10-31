# RSF-29 operator video-frame selection evidence

Implementation complete; independent **QA_PASS** for all four live criteria.
Task `vky1aihwa7vdpeqvv40r33ig`; Codex account
`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`. Initial task, dependency, identity and
Ready → In Progress readbacks are retained in `kaneo-start.json`.

## Implementation and authority

The existing workbench now inspects uploaded/staged videos, explicitly selects absolute
streams, lists bounded presentation frames, previews actual PNGs, accepts ordered exact
ordinal/PTS selections, and stages confirmed collections into the existing source tray.
Metadata-only probing reuses RSF-28 normalization without frame decoding. Extraction,
PNG validation, content-addressed storage, assignment, review, recipes and animation
timing retain their accepted implementations. Changed paths and before/after SHA-256
values are in `implementation-manifest.json`; pre-edit copies are available at
`/tmp/rsf29-baseline`. Git already contained extensive untracked accepted work; no commit,
reset, push or history rewrite was performed. The egg-info SOURCES and PKG-INFO changes are generated
package metadata from distribution verification.

HTTP operations: GET `/api/video-capabilities`, GET project `/video-imports`, POST
project `/video-metadata`, `/video-frames`, `/video-preview`, `/video-stage`.
These preserve loopback Host/Origin checks, CSRF, the 48 MiB request limit, 32 MiB
video limit and current project revision. No paths, remote URLs, filtergraphs or
executable arguments are accepted. Preview writes no committed project or blob state.
Staging re-extracts and requires the preview's canonical identity before publication.
Failure may leave unreferenced immutable blobs under the existing persistence contract;
it never commits an incomplete collection as successful.

Media DTO integers use decimal strings; canonical persisted records retain integers.
Large integers in general project responses are also stringified losslessly, with an
immutable-record restoration check on PUT. RSF-28's supported selection range remains
±(2^53−1). `9007199254740993` is displayed exactly as source metadata and rejected
as a selection before decoding. Tests also preserve time-base denominator
`10000000000000001` and exact int64 metadata through HTTP save/reopen. This is an
explicit supported-range restriction, not a claim to extract frames above that bound.

## Known pixels, ordering and canonical provenance

Accepted synthetic VFR video SHA-256:
`51f0173b6b4dfd615acf3cb9d55e8131dd87c28b8e528098668b9fefd4c53a9d`.
Actual PTS `[0,40,120,160,300]`, time base `1/1000`. Requested `[300,0,120]`
resolves to ordinals `[4,0,2]`, collection
`8f92a9dfd224fdf3275a835caa14a8e04f5b03bf367d026520c28e2aa55a44e3`.
Reordering to `[300,120,0]` changes the collection identity to
`9e03b30d55141d79f361c1f36290f9f2ade7434ab0b6d81809c0c64ec04d646c`
while preserving each frame's PNG identity and original source PTS.

PNG hashes for ordinals 4, 0, 2:

- `1c5c3e4c120ee8a2861bf12636a1b96344f578171f7543869ea4a8b437883382`
- `dde9003e6bd1bca8db19eaeb40b24733bbbf4dac8a934f0314cbc4b96f780ef9`
- `3e00777e379eecd20d3385f45bcd00b3d85d525d45c50318cbc0634f3f6f8989`

Browser canvas RGBA hashes matched independently known synthetic pixels. Repeated
preview/staging preserved canonical identity and an idempotent staging revision.
Source filename/session paths and browser timing evidence are not canonical hash inputs.

## Coordinator verification

Environment: Ubuntu 26.04.1 x86_64; Python 3.14.4, Pillow 12.1.1, jsonschema 4.19.2;
FFmpeg/FFprobe 8.0.1-3ubuntu2; Chromium 156.0.8078.73. Python 3.12 and 3.13 are
NOT_RUN (interpreters unavailable). All following commands exited 0:

| Command | Result | Evidence |
| --- | --- | --- |
| `.venv/bin/python -m unittest discover -s tests -p test_video_workbench.py -v` | 26 PASS | `focused.log` |
| `.venv/bin/python -m unittest discover -s tests -p test_video.py -v` | 26 PASS | `existing-video.log` |
| `.venv/bin/python -m unittest discover -s tests -v` | 504 PASS | `public.log` |
| `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 40 PASS, 1 legacy native-report skip (41 run) | `private.log` |
| Eleven `scripts/check_*schema*.py` scripts, each via `.venv/bin/python` | 11 PASS | `schemas.log` (exact commands/statuses) |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | distribution PASS; 504 run, 10 optional skips | `distribution.log` |

Distribution verification records the sdist identity and checks reproducible wheel bytes, installed-package
imports and tests, static asset inclusion and private-resource exclusion. Artifact
SHA-256 values are in the log. Final sdist SHA-256:
`48d6f448c8122d04cfce9c7cd8dbf12ccc6a18dd96acb8f4e03ae90a2d024ec4`;
wheel SHA-256: `c04263a2e178182f6bd1a4aca07414286423ba172d0c6e2909cf6c8deaa05ef4`.
The independent reviewer built the same wheel hash. Compiler/codec/native source hashes remain unchanged.
Rust and native GPU suites were NOT_RUN for RSF-29 because this slice changes no
compiler, codec or native code; accepted M5 structural, independent and bounded native
evidence retains its original scope.

Actual Playwright MCP `browser_run_code_unsafe` executed
`tests/browser/rsf29-mcp.js`, then `tests/browser/rsf29-workflow-mcp.js` against
`http://127.0.0.1:8193`, a synthetic project root `/tmp/rsf29-browser-projects`.
Both returned successfully. Exact assertions, hashes, timing reports and expected
negative HTTP console errors are in `browser-primary.json` and `browser-workflow.json`.
There were no unexpected console errors or failed network requests.

Executed journeys A–G include metadata/stream inspection; keyboard-operated VFR
selection; known-pixel previews; nonchronological ordering/reorder; preview without
mutation; confirmed staging/idempotency/reopen; invalid PTS/ordinal/stream; stale revision;
explicit assignment, PNG ingestion and animation preview. The audio-first fixture
resolves absolute stream 1. An intercepted synthetic wire response verifies oversized
PTS/time-base display and disabled unsupported selection. Capability absence in the
browser is simulated; backend absence is tested independently. Invalid-container
failure is a real FFprobe execution. Screenshots are synthetic-only.

The existing runtime inspector changes movement_speed from 100 to 250, changing
Walk slot 8 frame duration from 53.33333206176758 to 133.33334350585938 ms while
the complete video provenance stays unchanged. Source PTS and candidate order do not
author ACT timing. Existing manual crop, placement and alpha-key recipes display real
before/after images, stage a derived image, and invalidate only the affected synthetic
review after explicit reassignment. Isolated synthetic operator decisions exercise
invalidation; video extraction itself creates no assignment or artistic approval.

## QA and milestone boundaries

Independent QA: **QA_PASS**, configured `forge_qa_reviewer` in separate context
`/root/rsf24_qa`. The reviewer independently reran focused/public/private/schema/package
checks, actual Chromium primary/workflow journeys in a fresh context, and an additional
mathematically constructed pixel probe. MCP's shared browser profile was locked; the
reviewer used installed Playwright with actual Chrome. Full scope, commands, honest
simulated-negative qualifications and verdict are in `independent/QA_REPORT.md`.
No mandatory source defect was found. A missing generated PKG-INFO inventory entry was
corrected and independently rechecked; all 13 changed paths and 121 unchanged baseline
files match. Implementation manifest SHA-256:
`805b5d8241f2b14b93ec5e92ea9627d37a0b8062b2338919793b1df2e7c7d51e`.

Kaneo final readback: **Accepted (`done`)**, Codex owner
`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`, all four checklist items checked. Verified
transitions: Ready → In Progress → QA Review → Accepted. Independent QA comment
`q78j7iljh03uawfrqp3a5ppl` and implementation handoff
`v1jkub3n2wh5k9omc2lp0ogs` were read back. Final task, comments and next-task dependency
receipts are in `kaneo-final.json`; no tracker writes remain pending or uncertain.

M6 is still in progress; RSF-28 and RSF-29 are Accepted. Next dependency-eligible task
retrieved live: **RSF-30 — [M6] Video-derived Walk assignment through the existing
compiler**, internal ID `kd4gq1ex5zq2k32rn38yso35`, Backlog (`to-do`), unassigned.
Its sole incoming blocking dependency is RSF-29, now Accepted. Recommended implementer:
Codex GPT-6 High, using the existing media/assignment/compiler contracts, Python tests,
FFmpeg, Rust oracle, applicable workbench/browser checks and separate forge_qa_reviewer.
No later task has started. M0–M5 gates retain accepted scope; this task grants no new
native pixel-fidelity or artistic approval claim.

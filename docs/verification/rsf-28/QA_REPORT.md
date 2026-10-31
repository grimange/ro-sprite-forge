# RSF-28 independent QA

Verdict: **QA_PASS**. Reviewer: repository-configured `forge_qa_reviewer`, separate
agent context `/root/rsf24_qa`. Coordinator transcribes this report from the
reviewer's final response; all executions below were independently performed by
the reviewer. The reviewer did not edit implementation/evidence, update Kaneo,
take ownership, or grant artistic/native approval.

Reviewed implementation manifest SHA-256:
`0f48666f07fa98ea39f5f58810d54cc5631cdf2b57e8b2be7742573aef4e91a5`.
All 10 implementation paths and 46 evidence files matched. Baseline comparison:
173 files, 169 unchanged; declared CLI, project schema, artifact-guard test and
generated package file-list differences matched. A prior evidence-only stale
VERIFICATION.md seal was refreshed and independently revalidated before PASS.
No mandatory implementation defect remains open.

## Independent commands

All commands exited 0:

| Command | Result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests -p test_video.py -v` | 26 PASS |
| `.venv/bin/python docs/verification/rsf-28/reproduce.py --output /tmp/rsf28-independent-qa-1` | Identical manifests/PNG bytes; zero lossless pixel mismatches |
| `.venv/bin/python -m unittest discover -s tests -q` | 478 PASS |
| `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -q` | 40 PASS, one existing legacy native-report skip |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | DISTRIBUTION_CHECK_PASS; 468 PASS, ten optional skips; STDLIB_CORE_PASS |
| All eleven `scripts/check_*schema*.py`, individually using `.venv/bin/python` | All PASS |
| Independent custom RGBA/audio-first probes | Exact RGBA and absolute stream selection PASS |
| Independent schema/artifact-guard probes | Existing schema semantics and rejection controls PASS |
| Final manifest/baseline hash validation | Every declared hash/difference matched |

Schema checkers: animation, comparison, compilation, contract, coverage,
extraction, ingestion, ledger, review, transformation, video.

## Mandatory live acceptance

1. Source hash, actual stream metadata/rates/VFR, decoder settings and
   display-order PTS identities: PASS. Exact rational bases, nullable unknown
   metadata, integer PTS, tool hashes, CFR/VFR/B-frame/multistream cases checked.
2. Optional dependencies: PASS. Missing-tool diagnostics, ordinary core/image
   workflows prohibiting subprocess creation, installed stdlib core smoke checked.
3. Safe bounded subprocess/staging: PASS. Explicit argv, fixed executables,
   shell=False, private process group and child-only limits reviewed. Injection,
   local paths, timeout/group cleanup, pipe/disk/decode budgets executed.
4. Reproducible frames and failure integrity: PASS. Fresh CLI extraction/staging,
   corrupt output/count/PTS, stale revision and failed publication checks passed.

## Independently known image and timestamp expectations

Actual VFR PTS `[0,40,120,160,300]`, time base 1/1000; request order
`[300,0,120]` resolved to presentation ordinals `[4,0,2]`. Source SHA-256:
`51f0173b6b4dfd615acf3cb9d55e8131dd87c28b8e528098668b9fefd4c53a9d`.
Canonical extraction identity:
`8f92a9dfd224fdf3275a835caa14a8e04f5b03bf367d026520c28e2aa55a44e3`.
FFV1 pixels matched independently constructed RGB-to-RGBA expectations exactly.
Two clean extractions matched canonical manifests and every PNG byte; staging and
reopen preserved source hashes, order and immutable blobs.

Additional reviewer-generated 17x13 PNG-in-MOV partial-alpha fixture preserved
every RGBA byte in request order `[2,0,1]`, including alpha 0,128,255. An audio-first
container selected its sole video at absolute stream index 1 and reproduced the
requested VFR PNG bytes. These additional cases did not rely on the submitted
test helper for their expected RGBA content.

The reviewer independently tested the artifact guard: exact accepted RSF-27
path/hash pairs pass; modified content, unlisted ACT and uppercase GRF reject.
Removing only video_imports from the current project schema yields the previous
parsed schema exactly. Existing schema semantics are unchanged.

All PNGs are revalidated before publication. Revision checks run before/after
extraction and existing locked save commits the project. Failed publication may
leave unreferenced immutable blobs, but cannot commit a partial collection.
Idempotency, source-tray discovery and unchanged assignment/review records passed.
Candidates remain UNVERIFIED with automatic_assignment false; ACT timing is not
inferred from video. Timeout checks found no live child/grandchild; an init-owned
zombie is distinguished from a live process.

## Scope and limitations

Python 3.14.4, Pillow 12.1.1, recorded FFmpeg/FFprobe 8.0.1-3ubuntu2 Linux build.
Python 3.12/3.13 NOT_RUN (unavailable). Other operating systems, arbitrary decoder
versions and universal cross-backend byte identity are not certified.
Browser/native graphics checks NOT_RUN: no controls, codecs, compiler or native
corridor changed. No new Rust/native gate claim. Accepted M5 scope is preserved;
M6 remains open. Live reviewer readback saw QA Review owned by verified Codex
account aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn. Coordinator performs final acceptance
and evidence readback only after this independent QA_PASS.

## Evidence retention

Independent reproduction results, manifests/PNGs and additional reviewer-generated
synthetic fixtures are archived in independent/. Focused/public/private/schema/
distribution output and the inline custom probe output were captured in the
reviewer tool transcript; separate reviewer log files/scripts were not retained.
Coordinator log files are labeled separately and are not represented as reviewer
logs. The reviewed handoff manifest is preserved byte-for-byte as
reviewed-implementation-manifest.json. Completion documentation/tracker snapshots
are added to implementation-manifest.json after the reviewed source seal.

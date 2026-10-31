# RSF-27 — Exact native Walk proof

Coordinator checks PASS. The final independent verdict and reviewed manifest are in
QA_REVIEW.md; final live tracker state is recorded separately. Implementer: Codex,
`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`. Task: `yuc7bv78trwofm1c8a0iilaf`.
Live blocking dependency RSF-26 and related native foundation RSF-6 were Accepted.

## Result and scope

The existing RSF-6 isolated native presentation corridor executes pinned Korangar
resource loaders, animation state/selection/preparation, entity drawing and shaders
against a freshly compiled RSF-26 synthetic monster. This is actual Vulkan rendering
and GPU readback, with native observations checked against independent expectations.
It is not an ordinary gameplay session. No production compiler or external checkout
was modified. Levels A (load), B (exact selection) and C (rendering) PASS; Level D
(reference pixel parity) remains UNVERIFIED. Same-backend repeated PNG byte identity
is measured separately and does not establish universal GPU parity.

The output remains `PARTIAL_DIAGNOSTIC`, with its required bundle marker. Three exact
Walk layer occurrences have assigned test artwork; wider artwork coverage remains
incomplete. All eight reachable Walk views select exactly, including preserved classic
images in untargeted views. No fallback or modulo case is counted as exact success.
Synthetic review declarations exist only inside isolated test fixtures. Native
technical evidence creates no artistic approval and grants no production authority.

## Environment and executable identity

| Boundary | Observed value |
|---|---|
| Korangar source | `3f3d88a583203f09d079712f43343c1041258ffd` |
| Native executable SHA-256 | `27986612b7cb3af691f6f0b2853721d03c11089e66bdc921ee9d460f441f391d` |
| Executable | `/tmp/rsf27-native-target/debug/rsf-korangar-native` |
| Isolated stage | `/tmp/rsf27-native-sealed` |
| Source manifest SHA-256 | `37fe70d34bcb9a2b873b13cd84166624d20acc5155d0215f2019a557dc6df740` |
| Cargo.lock SHA-256 | `2e99ed42a9c4c435feae537d0095a2d63d87e2c643002e2a09d88dc147bc9f59` |
| Rust | `1.95.0-nightly (905b92696 2026-01-31)`, nightly-2026-02-01 |
| Shader compiler / GPU API | Slang 2025.18.2 / wgpu 29.0.3, Vulkan |
| OS | Ubuntu 26.04.1 LTS; Linux 7.0.0-42 x86_64; glibc 2.43 |
| Adapter | CPU llvmpipe, LLVM 21.1.8; Mesa 26.0.8-1ubuntu0.3 |
| ICD | `/usr/share/vulkan/icd.d/lvp_icd.json` |
| Python / Pillow | 3.14.4 / 12.1.1 |

prepare.py reads immutable upstream Git objects into a new directory. All 89 upstream
input hashes and generated source hashes are recorded. The only added upstream-boundary
instrumentation observes the already produced upload byte vector at texture creation;
it does not change native pixels, selection or drawing. Existing GRF/filesystem,
audio-registration and gameplay-camera isolation adapters remain explicit. The native
process never consumes Python's expected image mapping or the Rust oracle report.

## Immutable authoring and compiled identities

The fixture declares all eight Walk views and ordered inherited topology before PNG
staging. It uses the canonical requirements and assignment ledger, two staged asymmetric
PNGs, an explicitly derived horizontal flip, and composition-bound synthetic review
events. Existing canonical CLI compilation then runs twice, with different invocation
directories, hash seeds and source argument ordering. No new writer or resolver exists.

| Artifact | SHA-256 |
|---|---|
| Original ACT | `255df7d22edd06fc323b5e02fa85ac3973c74e674f6ef3e1508d56fa4013a52d` |
| Original SPR | `670ac543acfa7323e2be20ec7cf093d78d4337d20186649256da3c30d92d213d` |
| Compiled ACT | `43fffe83c1333772126a51e171a5d33d3b03ab1706f670f869099b1633b7617b` |
| Compiled SPR | `0d49b375c22b5cd738c8a448d564409e4bfdbf90a1a6593a62ec4db3756a6a81` |
| Canonical build-manifest bytes | `3a7832608569ed9248bf42e1d3f0274ba0548937c76897e3450918aa219d1bd1` |
| Canonical build identity | `62406d13935ba379dab8dfbe29dc2c8b028719677bb04eb8d9c0dd97f25bbf52` |
| Source PNG, 6×5 | `9ebd553142628e4ec32c158217ef39a2ab1607a95da08ecdd8ec6050e4a521a7` |
| Derived PNG, 3×7 | `0a28aa8e1f4aed0a096fa8be088152203eab30b8b6c70ec7af2888ccd01b621b` |
| Independent Rust output report | `eabc545fafc479a158a97df46e1637fafc2f43f0e273a83752ab73827eb078ed` |

The actual ACT hash above has 64 hex digits; the shortened ACT hash in the operator
brief is superseded by the accepted RSF-26 artifact and measured bytes. Public synthetic
original/compiled binaries and canonical manifest are retained in synthetic-resources/.
provenance.json links requirement IDs, ledger/review revisions, source blob hashes,
raw layer occurrences, compiler policy and independently decoded before/after contents.
Fresh reproduction recreates paths; paths are evidence, not canonical build inputs.

## Native loading, effective images and exact selection

The file-loader adapter records SHA-256 of the actual bytes returned to the native
decoder, logical name and length. The hashed input/provenance map records the physical
paths. The modified logical resources are
`data\\sprite\\modified.act` and `data\\sprite\\modified.spr`. Cold per-actor native
caches and repeated cache lookups are checked. Native decoded versions/counts agree
with ACT 2.4 / SPR 2.1. A wrong original pair can render but is rejected against the
canonical compiled pair's hashes; a screenshot alone never authorizes success.

SPR stores indexed images first and truecolor images second. ACT pool 0/1 indices are
pool-relative; native flattened texture ordinal is indexed index or indexed_count +
truecolor index. Original pools are 5 indexed + 1 truecolor; output is 5 + 3. Original
indexed RLE, palettes and pixels remain unchanged. `explicit_rgba` appends two exact
truecolor entries and changes only three selected consumers using copy-on-write.

| Selected occurrence (slot 8, Walk view 0) | Native effective output |
|---|---|
| Frame 0, raw layer 0 | truecolor pool index 1, global texture 6, 6×5 |
| Frame 2, raw layer 2 (hidden raw 0, unaffected visible raw 1) | same replacement texture 6 |
| Frame 3, raw layer 0 | truecolor pool index 2, global texture 7, 3×7 derived source |
| Untargeted frame 1 | original indexed texture 0, also retained by Attack |

Texture 6 native upload SHA is
`3b7e5d92bb8ceb813251ceb9ea4c7178c248addb9524f4d60ef1f0ce23e8f209`;
texture 7 is `55b94c9be323d54da5ca92627c785204825feabc581a75a4af9b204c7fd8ca65`.
These identify bytes observed at native texture creation, not screenshots. Independent
Pillow decoding of the staged PNGs yields those exact dimensions/pixels. The checker
supports exact upload comparison for binary alpha; partial-alpha comparison is rejected
explicitly. Native alpha processing itself is unchanged.

Actual native state setters request Walk, directions 0–7 and camera directions 0/4.
Resolved Walk slots are exactly 8–15 after the pinned camera-relative direction mapping.
No positive fallback is observed. The four-frame synthetic view-0 loop is
`0 → 1 → 2 → 3 → 0 → 1`, observed through native get_frame at controlled ticks
12, 132, 252, 372, 491, 612 (delay 6, native Walk interval 120). Other views use their
actual frame counts. The test does not pretend that this fixture has six Walk frames.
Native draw instructions are checked against the actual selected texture Arc, ordered
parts, geometry, mirror, color and depth order. Independently decoded ACT expectations
also check prepared geometry, color and anchors. Event preservation is checked by the
independent Rust whole-ACT comparison; native event fields are recorded, but the native
checker does not independently assert those event fields. Audio output is NOT_TESTED.

## Coverage and rendered evidence

| Measured boundary | Count |
|---|---:|
| Native cases, original/modified/Orc/Novice | 176 (64/64/32/16) |
| Prepared frames / ordered layers | 1,060 / 2,796 |
| Observed selected frames / drawn layer occurrences | 1,080 / 4,144 |
| GPU readback captures | 56 |
| Preserved before/after selection samples | 196 |
| Targeted raw layer occurrences | 3 |
| Mandatory selection/content mismatches | 0 |

The independent Rust original/compiled comparison checks all synthetic occurrences:
3 targeted, 51 unaffected and 6 hidden clips, with zero mismatches; it also compares
whole ACT metadata outside the authorized pool/reference changes. Native evidence
adds actual selection and drawing, rather than relabeling Rust decoding as playback.

Public synthetic captures are in synthetic-captures/. Frame 0's modified native capture
hash is `8b859ced743297db9c6402c563036c49063f9385815770f9d403d120345ca307`
(105 nonblack pixels); its original control has 48. Untargeted frame 1 has 56 nonblack
pixels and identical original/modified capture hash
`b339a8ce1b44007efe9521a4bdffa8dd2bd6a06bbd3e73c7a9d3c36b2bfbeaed`.
Other targeted captures visibly change and use the independently identified textures.
Captures are 512×512, fixed camera/background, actual opaque/transparent/WBOIT native
drawers. No tolerance-based reference pixel-parity claim is made.

Orc coverage prepares all 40 slots / 512 frames / 1,776 visible layers; native Walk and
Die execute all eight views with both cameras. View-0 Die slot 32 includes 22 frames,
with 12 ordered layers in frames 8–21; every selected ordered layer and transformed
placement is checked. Novice prepares 104 slots / 456 frames / 912 body+head layers;
all eight Walk views execute with both cameras. Separate body/head resources and
attachment relationships are preserved. Fresh private tests additionally compile a
bounded Novice body replacement and preserve the other 103 slots and original head.
No private asset or capture is published; 36 private captures are under ignored
`.cache/rsf27-native-private/`. Technical reports contain metadata/hashes, not pixels.

## Negative controls and immutability

Eight native executions test original-pair substitution, wrong ACT with modified SPR,
missing resource, missing mount, hash mismatch, invalid frame, unsupported action and
invalid pool index. The first two render successfully but independent provenance
checking rejects `PAIR_IDENTITY_MISMATCH`. Remaining cases exit 101 before successful
report publication, with `MISSING_MODIFIED_RESOURCE`, `RESOURCE_MOUNT_FAILED`,
`RESOURCE_MISMATCH`, `INVALID_REQUESTED_FRAME`, `ACTION_UNSUPPORTED` or the existing
native `index out of bounds` diagnostic respectively. Bounds failure is accurately
reported as a native panic, not a newly invented typed codec error.

Nine report-tampering controls reject wrong loaded hash, wrong texture, wrong frame,
wrong slot, fallback claimed exact, unsupported view, corrupt capture hash, missing
capture and missing negative evidence. Native negative observations additionally
record shortened action-array modulo fallback, critical-action fallback and direction
masking; none are accepted as exact requested-slot proof. All 17 controls PASS.

Original ACT/SPR, staged PNGs and private resource hashes are identical before/after.
Existing export/cache tests still reject stale authority, unbound production composition,
incomplete coverage and corrupt cache. Nothing bypasses `UNBOUND_PRODUCTION_COMPOSITION`.
The source baseline has 146 files: 143 unchanged, with only existing main.rs, prepare.py
and README.md changed. New tool files are enumerated in implementation-manifest.json.
No production writer, resolver, build engine, schema or previous test was changed.

## Commands, regressions and reproduction

commands.json, reproduction-commands.json and individual logs preserve actual invocation,
status and counts. The complete clean rerun (private fixture paths are optional) is:

```bash
PYTHONPATH=src .venv/bin/python docs/verification/rsf-27/reproduce.py \
  --output /tmp/rsf27-reproduced \
  --stage /tmp/rsf27-native-sealed \
  --executable /tmp/rsf27-native-target/debug/rsf-korangar-native --private
```

Use a fresh output path. To rebuild the executable, follow tools/korangar-native/README.md
with the pinned toolchain; source-manifest.json and shader-manifest.json seal this build.
Native invocation uses DISPLAY/WAYLAND_DISPLAY unset and the recorded Vulkan ICD.
Two coordinator native reports, two independent reviewer native reports, and full clean
pipeline reproductions agree. Native report SHA-256 is
`af20687d42dcd9dda8bc9b9288daf81b498723e9676837f666009bf1a6db46c5`;
all 56 corresponding captures compare byte-identically on this backend. Gzip retention
does not change the underlying report hash.

| Check | Actual result |
|---|---|
| Full public unittest suite | 452 PASS, exit 0 |
| Private fixture suite | 40 PASS, one existing old native-report skip, exit 0 |
| Independent Rust parity | 11 PASS, exit 0 |
| Native checker/tool tests | 17 PASS, exit 0 |
| Pinned native Rust tests | 4 PASS, exit 0 |
| JSON Schema checkers | all 10 PASS, exit 0 each |
| Isolated wheel / reproducible distribution | 443 PASS, 9 optional skips of 452; exit 0 |
| Native positive runs / independent checker | exit 0; zero mandatory mismatches |
| Native negative/tampering controls | 17 detected, source integrity PASS |
| Clean end-to-end reproduction | six commands exit 0, identical reports/captures |

An initial sandboxed public test run could not open local HTTP sockets; the authorized
rerun with socket access passed. The wheel checks also used authorized socket access.
The installed wheel's nine optional skips are three schema-dependent and six Rust-
dependent tests; private art is excluded. No package files changed. Python 3.12/3.13
are NOT_RUN because unavailable. Rust formatting is NOT_RUN because the pinned image
lacks rustfmt. Browser tests are NOT_RUN because no operator controls changed. Hardware
GPU, ordinary gameplay, audible sound and universal/reference pixel parity are untested.

## Acceptance separation

M5_GATE_PACKET.md maps each authoritative M5 criterion to accepted RSF-23–26 evidence
and this task's own native proof. The technical native decision is based on independently
reproduced exact resource/selection/rendering results. No real-art operator approval is
granted or implied. Engineering milestone acceptance does not promote this diagnostic
bundle, complete wider artwork, or start M6. Final acceptance requires QA_PASS and live
tracker read-back; the coordinator does not self-certify.

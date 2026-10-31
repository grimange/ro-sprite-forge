# RSF-26 — Walk compilation and independent multilayer regression

Coordinator verification PASS; independent QA verdict is recorded separately in QA_REVIEW.md.
Implementer: Codex `aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`.
Task `tju1c32n1jrxitklr5hnj6la`; dependencies RSF-25 and RSF-5 were live Accepted before work.
KANEO_START.json preserves the verified claim/In Progress read-back; final tracker evidence is separate.

## Scope and source preservation

Added `tests/test_walk_compilation.py`,
`tests/private_fixture_hooks/test_walk_compilation_fixtures.py` and this evidence directory.
No production source, codec, resolver, writer, build/cache engine, UI or existing test changed.
All 90 baseline source/test/schema/Rust file hashes still match (baseline-hashes.json,
preservation.json). Existing files are untracked in this checkout, so a Git diff alone
cannot establish the task boundary. The implementation manifest enumerates new files.
No commit/push, proprietary asset copy, actual artistic approval or native execution.

Plan v1.1 SHA-256 verified:
`5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e`.
Pinned Korangar revision `3f3d88a583203f09d079712f43343c1041258ffd` was inspected:
animation loader `korangar/src/loaders/animation/mod.rs` applies the indexed count
offset to truecolor references; sprite loader decodes indexed palette entries and
bottom-up ABGR truecolor; world animation selects actual action/view slots.
Frozen player/monster profiles resolve Walk view 0 to slot 8, all Walk views to 8–15.
The monster Attack action identity is `Attack1`; Death is profile action `Die`.

## Independent comparison model

SPR 2.1 stores indexed images first, truecolor images second, with separate counts.
ACT 2.4 `pool=0/1` references are relative to that pool. The runtime texture ordinal
is `sprite` for indexed and `indexed_count + sprite` for truecolor. Hidden `sprite=-1`
clips are retained and excluded from visible-image selection.

The new test-side comparator invokes the independent Rust executable directly on
both original and compiled bytes. It bounds-checks each pool-relative reference,
selects Rust-decoded RGBA pixels, and compares targeted dimensions/pixels to Pillow
decoding of the known staged PNG. Every unaffected visible occurrence must preserve
pixels, dimensions and its entire Rust clip report. Only selected pool/sprite fields
are normalized before comparing the **whole** ACT report. Thus ordered layer counts,
positions, float32 scale/delay bits, rotation, mirror, color DWORDs, reserved header,
eight-int bounds, raw sound/event names/references and anchors are compared.
Palette bytes and all original indexed image records/raw RLE payloads are also equal.
The comparator's sensitivity test rejects unchanged-reference pixel corruption,
metadata drift and layer-order drift. It does not consume compiler PASS/remapping
summaries as expected results and is not a new production index resolver.

Rust independently decodes binary fields and pixels. The runtime selection formula
is applied by the test from pinned source evidence; Rust is not Korangar playback.
Compiler Python/Rust canonical structural parity is additionally exercised and required.

## Synthetic staged Walk baseline

The legally redistributable synthetic monster has 40 slots, 46 frames, 54 visible
layer occurrences and six hidden clips. The target declares all eight Walk views,
observed frame counts and ordered inherited topology **before** source staging.
It stages two asymmetric PNGs, unused spritesheet/crops, and an explicitly requested
horizontal-flip derived source. The derived pixels are independently checked.
Assignments and composition-bound review events are created only as isolated test
operator declarations. CLI input uses the same ephemeral review projection as RSF-18.
This confers no approval on real artwork.

Selected slot 8 occurrences: frame 0/raw layer 0, frame 2/visible ordinal 1 (raw layer 2
after a hidden clip), and frame 3/raw layer 0. The first two intentionally share one
source; the third uses the derived source. Full comparison: **3 targeted, 51 unaffected,
6 hidden; zero mismatches**. Independent single-target cases preserve the other Walk
consumer and unrelated Attack1 consumer of the same original indexed image.

Original counts 5 indexed + 1 truecolor. `explicit_rgba` selects supported lossless
truecolor append; existing indexed records remain unchanged. A separate `preserve_pool`
case appends one exact original-palette indexed entry and one truecolor entry. An
unaffected Idle truecolor consumer proves the effective image remains correct when
the indexed count changes. No automatic quantization, palette optimization or conversion.

See synthetic-snapshot.json for requirements, ledger, reviews, source identities and
coverage; golden-build.json for canonical composition/toolchain/remapping identity;
synthetic-effective-mapping.json for all occurrence hashes; golden-compilation.json
for decode-after-write, bounded status and Rust verification.

## Determinism

Two separate CLI processes use different working/output directories, invocation IDs,
output prefixes, PYTHONHASHSEED values (19/38) and reversed source argument ordering.
Both run the existing pipeline with `--policy explicit_rgba --oracle ... --cache-dir ...`.
Both compile before the second publication validates/reuses the one immutable cache entry.
ACT, SPR, canonical build bytes, effective mappings and independent Rust report hashes match.
Invocation-specific compilation reports are not canonical binary inputs.

| Output | SHA-256 (both runs) |
|---|---|
| ACT | `43fffe83c1333772126a51e171a5d33d3b03ab1706f670f869099b1633b7617b` |
| SPR | `0d49b375c22b5cd738c8a448d564409e4bfdbf90a1a6593a62ec4db3756a6a81` |
| Canonical build file | `3a7832608569ed9248bf42e1d3f0274ba0548937c76897e3450918aa219d1bd1` |
| Independent output Rust report | `eabc545fafc479a158a97df46e1637fafc2f43f0e273a83752ab73827eb078ed` |

Input and output identities, exact CLI argv/exit statuses are in clean-builds.json;
the command below regenerates binaries in disposable locations and evidence at a chosen path.

## Private audited regressions

Private inputs remain at their external audited fixture locations; only hashes and
non-artwork contract/occurrence evidence are recorded here. Each source is hash-pinned
before compilation and reread afterward. Both cases select actual Walk view 0/frame 0/
visible layer 0 using resolved requirements and compile a 24×32 synthetic PNG through
`explicit_rgba`. Both use Rust original/output comparison and Python/Rust parity.

| Resource | Complete before/after comparison | Result |
|---|---|---|
| Male Novice body | 104 slots, 456 frames; 1 targeted + 455 unaffected; other 103 slots identical | PASS, 0 mismatches |
| Novice separate head | ACT/SPR bytes, independently decoded head report and attachment metadata preserved | PASS |
| Orc Skeleton | 40 slots, 512 frames; 1 targeted + 1,775 unaffected; other 39 slots identical | PASS, 0 mismatches |
| Orc Death | All 112 frames with 12 ordered layers (slots 32–39, frames 8–21), every clip/placement/timing/anchor intact | PASS |

Orc reconstruction explicitly calls `write_act(read_act(...))` and `write_spr(read_spr(...))`,
requires exact bytes, and independently compares all 1,776 visible occurrences; a separate
preserve-mode compilation proves no-op byte identity. Thus serializer reconstruction
is not inferred merely from a compiler returning original bytes.
Novice/Orc input/output hashes and target/assignment snapshots are in novice-regression.json
and orc-regression.json. Raw RLE, palette and separate head sources remain preserved.
Classic retained resources do not count as newly authored coverage.

## Export/cache/failure regressions

New tests create a valid production-authorized synthetic fixture and cache, then attempt
missing/corrupt current sources, removed approval, stale composition basis, incomplete
assignments and stale ledger revision. Each raises ForgeError before output publication
and leaves existing cache bytes unchanged. A corrupted cached SPR is rejected with
`CORRUPT_BUILD_CACHE`, without publishing a successful bundle.

The staged workbench test first publishes a valid diagnostic history entry. Missing or
corrupt source blobs, stale project revision, nonexistent selected occurrence and unsupported
policy fail without a new bundle, changing previous resources, reviews, assignments,
derived/sheet blobs or the prior published entry. Deliberately corrupted test blobs are
restored before reopening the unchanged project, not silently substituted by the compiler.

Existing accepted tests rerun in the full public suite provide precise diagnostic checks:

| Invariant | Executable coverage |
|---|---|
| Unbound explicit/per-frame composition, even changed ACT placement/delay | test_canonical_builds.test_production_rejects_unbound_explicit_composition: `UNBOUND_PRODUCTION_COMPOSITION`; diagnostic compilation remains available |
| Missing/unapproved/stale/incomplete production inputs | test_canonical_builds.test_full_production_rejects_missing_invalid_stale_and_unapproved |
| Invalid pool/index, exact failing occurrence | test_image_pool_remapping.test_invalid_reference_reports_exact_occurrence |
| Hash/source/review/revision errors, shared mutation | test_compiler.test_11_negative_guards_review_revision_format_and_immutability: `SOURCE_HASH_MISMATCH`, `MISSING_REPLACEMENT_SOURCE`, `STALE_REVIEW_APPROVAL`, `STALE_LEDGER_REVISION`, `SHARED_IMAGE_MUTATION_FORBIDDEN` |
| Unsupported/lossy palette conversion | test_compiler.test_08_indexed_lossless_palette_matching_and_rejection_of_lossy_inputs; test_image_pool_remapping.test_plan_rejects_unrepresentable_conversion |
| Tampered/inconsistent pair, interrupted publication, prior output preservation | test_image_pool_remapping.test_publication_rejects_tampered_pair_and_preserves_existing_files; test_canonical_builds bundle/interruption/process-kill/bad-pairs tests |
| Conflicting assignments, unsupported dimensions/format/pool/count limits | compiler, ledger, codecs and image-pool full-suite regressions |

Bounded output is `PARTIAL_DIAGNOSTIC`, `production_authorized=false`, with the required
bundle marker. Current source/approval/export checks remain mandatory before cache use.
No test declares a scoped/single-view candidate to be a complete runtime-profile actor.

## Commands and actual coordinator results

Run from repository root; all commands below exited **0**. commands.json records arguments,
counts and log names; schemas.json records every individual checker command/stdout/exit.

```sh
.venv/bin/python -m unittest discover -s tests -p test_walk_compilation.py -v
.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p test_walk_compilation_fixtures.py -v
.venv/bin/python -m unittest discover -s tests -p test_canonical_builds.py -v
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v
.venv/bin/python tools/rust-oracle/test_parity.py
.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14
.venv/bin/python docs/verification/rsf-26/reproduce.py --output-dir /tmp/rsf26-recheck
```

Focused new tests: **7 public + 3 private PASS**; accepted canonical baseline: **14 PASS**.
Full public: **452 PASS**. Private: **41 discovered, 40 PASS, 1 existing native-report skip**
(`/tmp/rsf6-native-run-final-1` unavailable). Independent Rust parity: **11 PASS**.
All **10 schema checkers PASS**. Isolated wheel: **452 discovered, 443 PASS, 9 optional skips**
(3 schema-validator tests, 6 repository-Rust-dependent tests); repository run covers all.
Distribution check builds two byte-identical wheels, verifies installed stdlib-only core,
and excludes private fixture hooks and ACT/SPR/GRF from sdist/wheel.
Wheel SHA-256: `12296d11a0e2f729492a98d3c0c9460c579e5b1d4fc7303edf035bb8a5736bec`.
SDist SHA-256: `fb760871f08208881ab6f3cb9c0f42fbb5ff1b39288940da3d0818ac873cb6a8`.

Python **3.14.4**, Pillow **12.1.1**, jsonschema **4.19.2**. Python 3.12/3.13 are
**NOT_RUN** (interpreters unavailable; python-matrix.json). No UI changes; browser
journeys **NOT_RUN**, as no operator-facing control changed. Native Korangar **NOT_RUN**.
Full public/distribution commands required local HTTP socket permission and ran with that
scoped sandbox escalation; tests remain local/offline.

## Gates and next boundary

**M5-S PASS** within declared bounded structural/preservation scope.
**M5-I PASS** within independently decoded Rust structure/pixel scope.
**M5-N UNVERIFIED**: no native resource loading, requested/resolved slot or rendering proof.
M5 remains open. Human artistic approval remains exclusive to the operator.
The next dependency-eligible task must be fetched live after RSF-26 acceptance;
it is not started by this task.

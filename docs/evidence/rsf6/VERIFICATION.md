# Current acceptance

RSF-6 is Accepted following independent QA_PASS and the explicit operator decision in OPERATOR_ACCEPTANCE.md. M0-S/I/N=PASS; M0_VERIFIED. The technical record below is preserved as issued before that decision; pending-decision statements are historical.

# RSF-6 native Korangar verification

Task `lyjs5izms0mcj700m7o25dam`, M0. Implementation self-tests pass; independent
QA_PASS is recorded in QA_REVIEW.md; the live task's operator native decision is pending. This record does
not grant operator acceptance. M0-S and M0-I remain PASS; actual native checks
pass in the isolated presentation scope below. Formal M0-N/M0 closure awaits
the operator native decision; independent technical QA_PASS is complete. No M1 work started.

## Source and executable identity

Plan SHA-256: `5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e`.
Korangar <https://github.com/vE5li/korangar>, revision
`3f3d88a583203f09d079712f43343c1041258ffd`. Normal checkout HEAD matches;
its two existing unrelated ops/lwr policy changes were neither used nor changed.
The stage reads immutable Git objects. No normal client/LWR/rAthena edits.

Native debug executable SHA-256:
`38fa19a03469325d42570328d31128db5a0a37f821321f8428efb4df84d2ac76`.
Cargo.lock SHA-256:
`2e99ed42a9c4c435feae537d0095a2d63d87e2c643002e2a09d88dc147bc9f59`.
141 locked packages, wgpu29.0.3, local upstream byte/format/macro/container/loader
crates0.1.0. Rust nightly-2026-02-01, rustc1.95.0-nightly
(905b9269674ced4b5239f485609a3bf0ab02d01b, 2026-01-31), Cargo1.95.0-nightly
(fe2f314ae, 2026-01-30), host x86_64-unknown-linux-gnu. Python3.14.4.
Linux7.0.0-42-generic x86_64. Build is unoptimized debug with debug symbols;
no claim of cross-path executable reproducibility.

`source-manifest.json` SHA-256
`5b3066f7b0ec11e729455d0e36c9471397efc5f31b4f5eab1e090e54ed21ad2c`
records89 immutable upstream inputs plus every generated build file, including
the maintained adapters and accepted RSF-5 format subset. Upstream MIT notice
is retained in the isolated stage. `tools/korangar-native/README.md` documents
all extraction/adaptation boundaries and the repeatable recipe.

Slang2025.18.2 from the existing offline builder
`lwr-m1b-korangar-builder:nightly-2026-02-01` compiled unchanged pinned shaders
with upstream SPIR-V/column-major/GL-layout/O3 flags. Both compiler calls exit0;
expected `spvImageGatherExtended` profile-extension warnings are visible.
Entity SPIR-V SHA-256 `27f65d9d3e302c7ddbb7104576fab61c1f797e71daf19228eb4cb64a4fe6f2ec`;
WBOIT resolve `2665d9ace894a006dbf2513d3f1eb6928ba0e6d816d7db4eb8b5c002f352e73e`.

## Executed native path

No display server or hardware GPU is available. Actual headless Vulkan runs on
llvmpipe LLVM21.1.8, Mesa26.0.8-1ubuntu0.3. `native-environment.json` records
the adapter separately from canonical native observations. The old gameplay
binary was not used because its source/build identity was unproven.

The isolated native executable invokes pinned SpriteLoader, ActionLoader,
AnimationLoader, AnimationState, AnimationData::get_frame/render, Camera defaults,
Texture upload, ForwardEntityDrawer opaque/transparent passes and the original
PostProcessingWboitResolveDrawer. Actual GPU readback produces private512×512PNGs.
This is a native presentation harness, not ordinary gameplay reachability.
The controlled FileLoader adapter replaces the archive boundary and hashes
the actual returned bytes. Each actor starts with cold caches; repeated sprite
lookup is checked to use the same cached resource without another file load.

Adapters supply a fixed orthographic camera, native ABI-compatible ambient-only
render context/attachments and sound-name registration. They do not implement
another sprite renderer or substitute Python frame selection. Native shaders,
ordered instructions and animation algorithms remain upstream. Audio playback,
scene shadows/lighting, hardware GPU behavior and combat/gameplay are NOT_TESTED.

## Loaded resources

All six intended source hashes equal hashes of bytes delivered to native loaders.
Virtual identifiers are `data\sprite\<part>.<act|spr>`; filesystem paths stay in
the private loader map. Novice body/head remain separate pools and resources.

| Part | ACT SHA-256 | SPR SHA-256 |
| --- | --- | --- |
| novice_body | a82086ba005506a16ee0740ebd1d33c43de8cc4ee1a622ea933ff9e0502c1c77 | 7f4efe357b0f80e71ba2dcdb93d1c110988b1b8f382e1dbfc722e3a2cf85a533 |
| novice_head | 96cb4c7daada65ead29ade650c34da1cba93937d3b360c5468506c3d056219de | dfc548c5cfd9aeb66616c5912df78773c2798834f9412a309a5a2b4f5868ac95 |
| orc_skeleton | 31e1e75241bc534422e468ae134892c7b234d66022456b87b0423df5858370e2 | a39f864209d63ae75bd62438da61775c510d7c55a78344b3065fb5918a55ce8f |

Original file hashes are checked again by the independent Python verifier after
native execution. All97 accepted source files still match the accepted manifest.
Fresh existing private preservation tests and Rust parity confirm all three pairs.
Orc retains512 motions,1776 visible layers,55/57 images, unused indices36,39.
Novice head has912 raw layer records,456 visible references; sentinel layers
are not counted as visible or drawn.

## Exact slots, motions, layers and timing

160 positive cases: two actors × Idle/Walk/Attack/Hurt/Die × two opposite camera
directions(0,4) × all eight entity directions(0…7). Native returned-frame pointer
identity establishes actual action slot/frame; every sample records it. Camera
default mapping supplies `(entity_direction + camera_direction) & 7`. The expected
frozen action groups are checked independently after the native run.

| Action | Player group / slots | Monster group / slots |
| --- | --- | --- |
| Idle | 0 / 0–7 | 0 / 0–7 |
| Walk | 1 / 8–15 | 1 / 8–15 |
| Attack | 5 / 40–47 | 2 / 16–23 |
| Hurt | 6 / 48–55 | 3 / 24–31 |
| Die | 8 / 64–71 | 4 / 32–39 |

All positive cases report REQUESTED_SLOT_VERIFIED and fallback NONE. There are
1664 sampled native frame selections. Every slot is stepped through motion
count+2 samples, checking loop/terminal behavior. Source delay×20 controls Walk;
delay×50 controls untimed actions. Attack/Hurt use1000 controlled ticks. Player
Idle freezes frame0 under pinned rules. These are controlled simulation ticks,
not wall-clock timing measurements. Samples avoid floating-point boundaries.

Example camera0/entity-direction7: Novice Walk slot15 frames0…7,0,1;
Attack slot47 frames0…4,4,4; Hurt slot55 frames0…2,2,2; Die slot71 frame0.
Orc Walk slot15 frames0…5,0,1; Attack slot23 frames0…11,11,11;
Hurt slot31 frames0…8,8,8; Die slot39 frames0…21,21,21.
Opposite camera4 with direction7 resolves view3, verifying wrap at the boundary.

The Python post-run checker reads original ACT/SPR and compares2688 prepared
visible layer occurrences:456body+456head+1776Orc, including every ordered
image identity, pool-derived index, offsets, scale-derived size, mirror, rotation,
tint and multipart anchor adjustment. Native render assertions also check exact
texture identity, frame-part affine transform, mirror and per-layer depth order.
Novice body/head share the native prepared frame selection and native anchor
merge. Orc death exercises up to12 ordered layers.84 capture observations
(78 unique PNGs; repeated frozen Idle frames share filenames) traverse the native
GPU passes; all captures contain non-background pixels. Captures remain private.

## Failure detection and determinism

Five native negative cases are mandatory and checked independently:

- Critical monster Attack3 resolves group0: FALLBACK_DETECTED.
- Shortened isolated action set requests39, selects7 through modulo: FALLBACK_DETECTED.
- Deliberately wrong expected view6 versus observed7: NATIVE_FAILURE.
- Unavailable ACT/SPR and mismatched expected hash enter native fallback loaders:
  MISSING/RESOURCE_MISMATCH/LOADED_CORRECT_RESOURCE trace, FALLBACK_DETECTED.
- Direction8 native masking to0: ACTION_UNSUPPORTED, never accepted as success.

These negative outcomes are expected diagnostics, not positive action acceptance.
Native positive input preflight checks required files/hashes before creating output.
Reports are emitted only after all native assertions pass; interrupted runs can
leave private diagnostic captures but no successful native report.

Two complete native runs produce byte-identical canonical observations and
capture hashes in this exact environment. Native report SHA-256:
`80b023d2b5cdc9a8bc59a8d643d425a6b4b2c7716d311727e0bbbc4f6a61c72e`.
`native-report.json.gz` retains that complete technical trace without image data.
`native-result.json` records independent comparison results. No screenshot-hash
reproducibility claim is made across GPUs, drivers or platforms.

## Actual commands and exit statuses

Build stage `/tmp/rsf6-native-release`; shared target `/tmp/rsf6-native-v2/target`.
Rust environment: RUSTUP_HOME=/tmp/rsf5-rustup, CARGO_HOME=/tmp/rsf5-cargo,
CARGO_TARGET_DIR as above; cargo=/tmp/rsf5-cargo/bin/cargo.
These paths are reproduction aids, not inputs to canonical report identity.

| Command | Exit / result |
| --- | --- |
| `.venv/bin/python tools/korangar-native/prepare.py --checkout /home/ra/Documents/korangar --output /tmp/rsf6-native-release` | 0,89 upstream inputs |
| `.venv/bin/python tools/korangar-native/compile_shaders.py /tmp/rsf6-native-release --builder-image lwr-m1b-korangar-builder:nightly-2026-02-01` | 0,2 shaders |
| `cargo build --offline --locked --manifest-path /tmp/rsf6-native-release/Cargo.toml` | 0 |
| `cargo fmt --check --manifest-path /tmp/rsf6-native-release/Cargo.toml -- --config skip_children=true` | 0, maintained root; native imported formatting retained |
| `rustfmt --check --edition 2024 --config skip_children=true tools/korangar-native/graphics.rs` | 0 |
| `cargo clippy --offline --locked --all-targets --manifest-path /tmp/rsf6-native-release/Cargo.toml -- -D warnings` | 0 |
| `cargo test --offline --locked --manifest-path /tmp/rsf6-native-release/Cargo.toml` | 0,4 tests including upstream combat timing test |
| `env -u DISPLAY -u WAYLAND_DISPLAY VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json /tmp/rsf6-native-v2/target/debug/rsf-korangar-native /tmp/rsf6-final-inputs.json /tmp/rsf6-native-run-final-{1,2}` (two separate runs, cwd build stage) | both0,160cases/5 negatives each |
| `PYTHONPATH=src .venv/bin/python tools/korangar-native/verify.py /tmp/rsf6-final-inputs.json /tmp/rsf6-native-run-final-1/native-report.json` | 0,NATIVE_CHECKS_PASSED |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tools/korangar-native -v` | 0,9 tests |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v` | 0,69 tests |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 0,10 tests, no skips |
| `PYTHONPATH=src .venv/bin/python tools/rust-oracle/private_parity.py` | 0,all3 AGREEMENT, zero mismatches |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | 0,DISTRIBUTION_CHECK_PASS,installed69 tests |

Existing distribution checker confirms normal Python package isolation. No new
Rust runtime dependency, private assets or captures enter wheel/sdist. Full
Python3.12–3.13 matrix and other platforms are NOT_RUN in RSF-6; accepted evidence
is retained rather than claimed as fresh execution.

## Repository and handoff

HEAD `f1bb19bb130beea8b89cf6c029209e93fb241d5a` is unchanged. Previously accepted
implementation remains untracked.97-file accepted snapshot hashes:
`accepted-manifest.json` c862ae770baf0a8c94c64e9fadc2a0ab254112bc3f8e74f1dafc0d4217367a0f;
`accepted-source.tar.gz` 5bbae7227df21bfb449cf573f43c94200e43b193921da471f39044315637c931.
Archive preservation was used; no baseline or implementation commit, push,
reset or cleanup. Changes are confined to tools/korangar-native and this packet.
AGENTS/.agents and other local AI settings remain untracked/ignored and unforced.

Live RSF-4/5 Accepted dependencies were confirmed before claim. RSF-6 moved
Backlog→Ready→In Progress and was read back. QA Review transition was read back; separate reviewer QA_PASS is recorded.
Final acceptance awaits the operator native decision. Live RSF-7 is
`[M1] Versioned actor, target and runtime-profile contracts`, statusBacklog/to-do,
blocking dependencies RSF-4 and5 bothAccepted; RSF-6 is related, not a blocker.
It is dependency-eligible but has not been started or authorized as new work.

Unchanged reference art has visual_review=NOT_REQUIRED. The live RSF-6 task
separately requires an operator native decision, which this packet does not
invent. See QA_REVIEW.md and final gate record for subsequent decisions.

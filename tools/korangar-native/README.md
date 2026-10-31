# Pinned native presentation verification

RSF-27 adds an optional compiled-Walk mode to this same corridor. See
`docs/verification/rsf-27/VERIFICATION.md` for the tested boundaries and evidence.
`walk_fixture.py` reproduces the RSF-26 synthetic authoring/build inputs;
`walk.rs` observes the native loaded bytes, prepared layers and texture uploads;
`verify_walk.py` independently compares resources, staged PNG pixels, selections
and actual captures; `walk_controls.py` executes negative native controls.

```bash
PYTHONPATH=src .venv/bin/python tools/korangar-native/walk_fixture.py /tmp/walk-input
# Add --private only when the audited optional private fixtures are available.
# Build this harness with prepare.py / compile_shaders.py / locked Cargo below.
cd /tmp/rsf-native-build
env -u DISPLAY -u WAYLAND_DISPLAY VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json \
  target/debug/rsf-korangar-native /tmp/walk-input/inputs.json /tmp/walk-native
cd /path/to/ro-sprite-forge
PYTHONPATH=src .venv/bin/python tools/korangar-native/verify_walk.py \
  /tmp/walk-input/inputs.json /tmp/walk-input/provenance.json /tmp/walk-native/native-report.json
```

The full bounded rerun is `docs/verification/rsf-27/reproduce.py`. Native
`upload_rgba_sha256` identifies the premultiplied upload byte vector observed at
texture creation, while capture hashes identify GPU readback PNGs. They are
different evidence boundaries. The checker deliberately supports exact upload
comparison only for binary alpha; it rejects partial alpha rather than claiming
untested conversion parity. The renderer itself retains the pinned native alpha
processing. The compiled resource remains `PARTIAL_DIAGNOSTIC`; synthetic test
review declarations grant no approval to real artwork. All eight reachable Walk
views are checked; fallback observations never count as exact success. Universal
GPU pixel parity, gameplay reachability and audible sound are untested.

RSF-6 uses Korangar revision `3f3d88a583203f09d079712f43343c1041258ffd`
from <https://github.com/vE5li/korangar>. This external verification tool is
optional and is excluded from the normal Python distribution. It requires no
server, LWR runtime, GRF archive, window system, or running game client.

`prepare.py` reads immutable Git objects, creates a **new isolated directory**,
and records SHA-256 for every upstream input and generated file. It imports the
native action/sprite/animation loaders, animation state/selection/preparation,
multipart anchors, camera direction and billboard methods, texture creation,
entity drawer, WBOIT resolve drawer, shader sources and buffer ABI. Those
algorithms execute in the native process; Python does not choose its frames.
The formats/bytes/macros subset is the already audited RSF-5 vendor source.
The upstream MIT license is copied into the stage.

The isolation adapters replace the GRF filesystem boundary, audio registration,
gameplay camera placement, and large lighting/render-graph context. UI derives
and unused gameplay modules are omitted; ABI fields/methods are made visible to
the small context. Native selection, multipart preparation, ordered draw
instructions, entity shaders and opaque/transparent/WBOIT draw code are not
reimplemented. `graphics.rs` supplies native-compatible uniforms/attachments and
GPU readback. Use the source manifest and extraction script to inspect this
boundary. The oracle report is never an input to the native process.

## Reproduce

Use private paths outside this repository for all fixture maps and captures.
The output directory must not already exist. The examples use the installed
offline toolchain and builder from the recorded environment; substitute your
own compatible locations explicitly.

```bash
.venv/bin/python tools/korangar-native/prepare.py \
  --checkout /path/to/pinned-korangar --output /tmp/rsf-native-build
.venv/bin/python tools/korangar-native/compile_shaders.py /tmp/rsf-native-build \
  --builder-image lwr-m1b-korangar-builder:nightly-2026-02-01
# Alternatively: --slangc /path/to/slangc (tested Slang 2025.18.2).
export RUSTUP_HOME=/tmp/rsf5-rustup CARGO_HOME=/tmp/rsf5-cargo
/tmp/rsf5-cargo/bin/cargo build --offline --locked \
  --manifest-path /tmp/rsf-native-build/Cargo.toml
PYTHONPATH=src .venv/bin/python tools/korangar-native/fixtures.py /tmp/native-inputs.json
cd /tmp/rsf-native-build
env -u DISPLAY -u WAYLAND_DISPLAY \
  VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json \
  target/debug/rsf-korangar-native /tmp/native-inputs.json /tmp/native-observations
cd /path/to/ro-sprite-forge
PYTHONPATH=src .venv/bin/python tools/korangar-native/verify.py \
  /tmp/native-inputs.json /tmp/native-observations/native-report.json
```

Nightly Rust 2026-02-01, wgpu 29.0.3 and all transitive dependencies are locked.
The original upstream shader flags compile SPIR-V; Slang reports its expected
`spvImageGatherExtended` profile extension warning. No shader warning is hidden.
The current recipe requests a fallback Vulkan adapter for headless software
rendering. The tested backend is llvmpipe; other backends are unverified.

```bash
cargo fmt --check --manifest-path /tmp/rsf-native-build/Cargo.toml -- --config skip_children=true
rustfmt --check --edition 2024 --config skip_children=true tools/korangar-native/graphics.rs
cargo clippy --offline --locked --all-targets --manifest-path /tmp/rsf-native-build/Cargo.toml -- -D warnings
cargo test --offline --locked --manifest-path /tmp/rsf-native-build/Cargo.toml
PYTHONPATH=src .venv/bin/python -m unittest discover -s tools/korangar-native -v
```

Formatting checks cover maintained Rust adapters. Imported native declarations
retain upstream formatting and are not rewritten for formatting-only changes.

## Evidence and limits

The file-loader boundary hashes the actual byte vector returned to the native
decoder. Cold per-actor caches and a repeated cached lookup are checked. The
positive staging check fails before creating output when input hashes differ.
Negative copies exercise missing paths, hash mismatch and native substitution.
The observation records requested actions/directions, the slot and frame found
by pointer identity in the native returned frame, draw layers, source delay,
controlled ticks, and private PNG hashes. Python independently checks original
ACT/SPR structures and frozen runtime rules after execution.

There are 160 positive cases: two actors, five actions, two opposite camera
directions, eight entity directions. Every selected slot is sampled through
its motion count plus loop/terminal steps. Representative front-camera frames
for views 0, 4 and 7 traverse actual native GPU draw passes and readback.
Player Idle intentionally freezes frame zero under the pinned native rules.
Walk uses source delay ×20; other untimed actions use ×50; Attack/Hurt use
the supplied 1000-tick duration. Deterministic stepping verifies frame order,
not wall-clock performance.

Native critical monster attack resolves to group zero, truncated animation
sets wrap by modulo, and direction 8 is masked to zero. These are explicit
negative observations and cannot count as exact-slot success. An intentionally
wrong view expectation also fails. Missing/hash-mismatched resources trigger
the native loader's fallback, using private copies under fallback identifiers.

This harness establishes bounded native presentation, not gameplay reachability,
combat correctness, hardware GPU parity, full scene lighting/shadows, audible
events, or cross-platform pixel determinism. Actual source bytes remain unchanged.
Captured reference art stays private; public evidence contains only technical
observations and hashes. New-art visual approval is not applicable.

See `docs/evidence/rsf6/VERIFICATION.md` for actual commands, hashes, QA and gates.

# RSF-4 verification packet

Implementation handoff, pending independent QA. RSF-4 / M0, plan SHA-256
`5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e` verified.

## Baseline and reviewed scope

HEAD remains `f1bb19b` (initial commit). Previously accepted RSF-1–3 files were
uncommitted. The prior accepted 55-file hash manifest was under vanished `/tmp`
paths and cannot be compared with current files confidently. No baseline commit
was made. Authorized fallback: `baseline-source.tar.gz` preserves 57 pre-edit
public source/documentation/configuration files; `baseline-manifest.json` SHA-256
`52ac320d3b744ace01a78243bb7b55756fa34ad343faa9b3d78fc1373c0b6e77`.
No private art, secrets, virtualenv, caches or local AI configuration is in it.

`changed-paths.txt` lists ten changed/added paths relative to that snapshot.
`baseline-diff.patch` provides the actual diff despite the untracked working tree.
`implementation-manifest.json` SHA-256
`629cf9ed05de3b43c8163caa86f06c1e3b0b6b92eac0d4e54fac2d72e01be0db`
binds the complete public implementation snapshot. No implementation commit,
history rewrite, push, external source edit or private asset import occurred.

## Behavior and independent semantic expectations

See `docs/architecture/RSF4_PRESERVATION.md` for supported policies and publication
limits. Raw preservation retains ACT and all SPR representation bytes separately
from ACT serializer validation. Existing inventory checks pair-local indices and
raw event references. Unknown edits and unsupported conversion requests fail.

The writer defect found was missing record/count/type/range validation: for
example a one-byte event could be emitted where a 40-byte record is required.
Pre-serialization validation now rejects malformed edits with typed errors.
The parser, SPR decoder, runtime profiles and requirements engine are unchanged.

A separately hand-constructed binary golden ACT and independently declared model
verify all supported fields. Eighteen one-field changes are checked at literal
binary offsets and against the entire independently patched source bytes;
this includes modifying one layer of a two-layer frame, mixed pools, coordinates,
mirror, both scales, rotation, color, reference, bounds, delay, anchor fields,
event index/raw event data and reserved header. An anchor insertion independently
splices 16 bytes and changes its count, checking all later records after shifting.
Every one of the golden ACT's 424 truncated prefixes is rejected. Existing codec
malformed-count/decompression tests remain in the full suite.

`mutation-hashes.json` records original hashes and 18 expected documents/output
hashes. Repeated serialization and canonical reports are deterministic. Every
unrelated byte is preserved in fixed-layout mutation tests. Supported finite
parsed ACT values roundtrip byte-exactly; arbitrary new Python floats are rounded
to float32. Unsupported nonfinite values are documented, not silently accepted.
Raw pass-through does not imply a general indexed serializer exists.

## Commands and actual results

Environment: Linux 7.0.0-42-generic x86_64; Python 3.14.4. Available additional
Python: Blender-bundled 3.13.13, successfully created a clean venv. Python 3.12
is unavailable. No network was used. Current tools: build 1.6.1,
pyproject-hooks 1.3.3, setuptools 78.1.1, wheel 0.46.3, packaging 25.0,
Pillow 12.1.1. The frontend/hook versions differ from requirements-build.txt;
the serialization/build backend versions remain pinned. The old offline
wheelhouse is gone. A local test-only cp314 Pillow 12.1.1 wheel was repackaged
from the installed OS package into `/tmp/rsf4-wheelhouse` for isolated tests.
It is not shipped as a Forge artifact or claimed to be the earlier wheelhouse.

| Command | Exit | Observation / log |
|---|---:|---|
| `.venv/bin/python -m unittest discover -s tests -q` before edits | 0 | 60 accepted-foundation tests |
| `.venv/bin/python -m unittest discover -s tests -v` | 0 | 69 tests, no skips; public-tests.log |
| `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 0 | 10 tests: 7 passed, 3 Orc skips; private-tests.log |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | 0 | 69 tests from isolated installed wheels, repeated wheel equality, archive asset exclusion, stdlib-only inventory/requirements/preservation smoke; distribution.log |
| `SOURCE_DATE_EPOCH=1704067200 .venv/bin/python -m build --wheel --no-isolation --outdir /tmp/rsf4-dist` | 0 | Direct build for additional 3.13 checks; build-wheel.log |
| `/tmp/rsf4-blender-python313/bin/python -m pip install --no-index --no-deps /tmp/rsf4-dist/ro_sprite_forge-0.1.0-py3-none-any.whl` | 0 | Clean installed package; python313-tests.log |
| `/tmp/rsf4-blender-python313/bin/python -I -m unittest discover -s /home/ra/Documents/ro-sprite-forge/tests -p test_preservation.py -v` | 0 | 9 tests without Pillow |
| Same 3.13 command, `-p test_foundation.py` | 0 | 16 tests |
| Same 3.13 command, `-p test_inventory.py` | 0 | 24 tests |

Full Python 3.12 matrix: NOT_RUN (interpreter unavailable). Full optional-preview
Python 3.13 matrix: NOT_RUN (no cp313 Pillow 12.1.1 wheel available offline).
The installed 3.13 stdlib suites above ran 49 tests. No missing check is a PASS.

Distribution checker built sdist SHA-256
`5cad5ba3b29ff9bef1e0712eaf664c77e7db098b4456f4498be0b31b86eb5625`
and two identical extracted-source wheels SHA-256
`f2372f1d1523f65f74bc0e07dd06097094e6f9323e44fb7212107bffeb80a209`.
Direct-source wheel used for 3.13 SHA-256
`e4e9368ef0ad78368b8b7ee7fe025e6817d3468b69d6c38a34aa6025694eee9b`;
these are different build routes, not a claim of equal direct/extracted wheels.

## Resource evidence

Both policies preserve the following input/output SHA-256 values identically:

| Resource | Input = output SHA-256 |
|---|---|
| Synthetic golden ACT | `75c87b11243b3855b122d17eda926b59f2214a89147397a8e6ecc7672423ca8c` |
| Synthetic mixed SPR | `9bb523b13f2318d56639bea53a14c9f7116c199960c3c9cc637c816777a24a1d` |
| Synthetic indexed SPR | `57a162cc555f39c21eadc89a1cc3fa2224fdee82e17be685fb6d7a350743a2b9` |
| Synthetic truecolor SPR | `9d35ecd341e0611c639a43bb168dc71a6a516e0cd2ef524fd59830f135f7508a` |
| Novice body ACT | `a82086ba005506a16ee0740ebd1d33c43de8cc4ee1a622ea933ff9e0502c1c77` |
| Novice body indexed SPR | `7f4efe357b0f80e71ba2dcdb93d1c110988b1b8f382e1dbfc722e3a2cf85a533` |
| Novice head ACT | `96cb4c7daada65ead29ade650c34da1cba93937d3b360c5468506c3d056219de` |
| Novice head indexed SPR | `dfc548c5cfd9aeb66616c5912df78773c2798834f9412a309a5a2b4f5868ac95` |

Novice body computed 13 groups/104 slots/456 motions/110 referenced identities/
108 distinct referenced contents. Head identity remains separate: 104 slots,
456 motions, 15 images. Both private policies serialize, publish, read back,
compare all ACT semantics and recheck unchanged sources. Private artifacts use
external temporary directories only.

Orc: NOT_RUN in this session. Hash-pinned ACT/SPR files formerly in `/tmp` are
missing. Existing hooks preserve the assertions 5/40/512/1776/55 of 57 and unused
indices 36/39, but historical RSF-3 success is not a fresh preservation run.
Synthetic multilayer/mixed-pool/unused-identity tests pass independently.

## Gates and remaining work

M0-S = INCOMPLETE: supported package, synthetic preservation/independent binary
semantics, malformed-input limits and Novice evidence pass; fresh exact Orc
inventory/preservation is unavailable. Restoring the pinned private pair and
rerunning private hooks is required for a fresh full structural-gate claim.
M0-I = NOT_RUN (RSF-5). M0-N = NOT_RUN / native UNVERIFIED (RSF-6).
Overall M0 remains UNVERIFIED, not M0_PASS or M0_PARTIAL_NATIVE_UNVERIFIED.
Artwork UNASSIGNED; operator visual approval NOT_RUN.

Independent reviewer verdict and final Kaneo read-back will be appended after
review. RSF-4's live criteria allow optional private fixtures and require recording
NOT_RUN blockers; this packet does not waive any full M0 gate.

Baseline archive SHA-256:
`b4cf3764c7a9c270bf40031f1b4d465bfd73e81a7122f06b79c7153b9cb5e535`.
All implementation-manifest entries were rechecked after handoff and match.
Every Python source file in the direct 3.13 wheel matches the working source.
Actual Git HEAD identity is
`f1bb19bb130beea8b89cf6c029209e93fb241d5a`, authored by
Ronniel Allan Castañito (existing initial commit); no new Git identity was created.

Live next-task lookup: RSF-5 (`dpexmlk6wggb1xri9yefzjnq`),
**[M0] Independent Rust decoding and structural parity gate**, Backlog (`to-do`).
Its only incoming blocking dependency is RSF-3, Accepted (`done`). It is dependency
eligible, not claimed or started. No RSF-5/6 records were changed.

Independent reviewer rerun observed a different sdist archive SHA-256:
`e00f9eb6c05a5c465f0bdfbde1d59d21df384f488c4605021c2028ea674f0245`.
The implementation manifest was unchanged and both rerun extracted-source wheel
hashes equal `f2372f1d1523f65f74bc0e07dd06097094e6f9323e44fb7212107bffeb80a209`.
The installed setuptools tarball path does not normalize gzip/tar timestamps.
Reproducibility is established for ACT/SPR outputs and the tested repeated wheels,
not for sdist archive bytes. Both sdist hashes above are actual distinct observed
archives; neither is substituted for the other or claimed to be reproducible.

Final independent verdict: **QA_PASS**, configured `forge_qa_reviewer` in separate
context `/root/rsf4_independent_qa`. No mandatory findings. See `QA_REVIEW.md` and
copied `qa-*.log` files for independent results. All five live RSF-4 criteria are
supported; full M0 gate states above remain unchanged.

Final Kaneo synchronization: task `iemlbfn503r9pvc50xd8vbnd` (RSF-4) was
updated to `done`, board column Accepted (`vnkxm3fyt0tmewq1rdokfops`).
The subsequent authenticated `get_task` read-back confirmed that exact status
and all five acceptance checklist items checked. Final evidence comment:
`l7ric1862b16yg0jsnxgdxqm`, created `2026-10-29T21:48:19.234Z`.
No Kaneo synchronization operations remain pending. RSF-5 and RSF-6 were not modified.

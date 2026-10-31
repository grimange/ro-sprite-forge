# RSF-5 independent Rust decoding evidence

Task RSF-5 (`dpexmlk6wggb1xri9yefzjnq`), M0. Implemented, independently
QA_PASS, Accepted; all four live acceptance criteria checked and read back.
RSF-3 and RSF-4 Accepted; sole inbound RSF-5 blocker RSF-3 satisfied.
Ready → In Progress → QA Review → Accepted transitions succeeded. No RSF-6 changes/native run.
Plan SHA-256 verified: `5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e`.

## Snapshot and scope

Git HEAD `f1bb19bb130beea8b89cf6c029209e93fb241d5a` unchanged. No commit,
push, reset or clean. Accepted source remains untracked. RSF-4 61-file manifest
matches every current accepted source file before and after implementation.
The authorized durable snapshot approach continues; no baseline commit was needed.
`baseline-manifest.json` is that exact accepted manifest, SHA-256
`629cf9ed05de3b43c8163caa86f06c1e3b0b6b92eac0d4e54fac2d72e01be0db`.
`accepted-source.tar.gz` preserves those files, SHA-256
`31dda8aaabbc78fb6c3e478ad729ac9c60eb6b4f8b7bf715ac5b0a0513163106`.
RSF-4 archive/manifests remain unchanged. Only new tools/rust-oracle and this evidence
packet are added. No production Python, tests or packaging configuration changes.

`implementation-manifest.json` pins 36 new oracle source/config files (excluding
build/cache directories), SHA-256
`39e724b1004406fc471c5259a10539f6586f512d7eb0fe4f07ff308fd1e4da94`.
Private ACT/SPR/GRF assets are outside the repository and distributions.

## Decoder identity and method

See tools/rust-oracle/PROVENANCE.md and vendor/source-hashes.json. Pinned upstream
Korangar revision `3f3d88a583203f09d079712f43343c1041258ffd`, verified actual HEAD
and git-show source bytes. All copied Rust files are unchanged; reduced lib module
list and standalone manifests isolate ACT/SPR dependencies. MIT notice retained.
No client/LWR/rAthena source changes. Local byte/macro crates remain version0.1.0.

Rust nightly-2026-02-01: rustc1.95.0-nightly (905b92696 2026-01-31),
cargo1.95.0-nightly (fe2f314ae 2026-01-30), Linux x86_64. Missing toolchain was
installed from official static.rust-lang.org into /tmp/rsf5-rustup and
/tmp/rsf5-cargo. Registry dependencies fetched once, then verification offline/locked.
Cargo.lock SHA-256 `ea679f9b9a3b4c6916b3514023c299c88f08e48567d996ca98c736a6e7db8a3a`.
Debug executable SHA-256 `e3acc98fe5a1d40df8aff6c373152cecd002ffae0b17a5017d4019866baa1d7b`.

The Rust executable independently reads both original binaries. Bounded Rust
preflight protects upstream allocations/RLE and retains raw40-byte events;
Korangar ActionsData/SpriteData then decode the full original resources. Rust
validates references, finite scales, positive delays and event bounds. Python's
separate report uses accepted readers and paired inventory validation. Neither
report is rewritten to match the other. Float32 values become exact unsigned bit
patterns; palette and indexed pixels remain distinct from normalized RGBA.
Complete recursive comparison includes unknown/missing/extra fields and sequence
order. Source versions/hashes, all ACT records, pools/dimensions/palette/index/RGBA
content are compared. JSON paths identify exact mismatched structural locations.
Independent raw reports canonicalize through sorted compact ASCII JSON + LF only
for hashing; raw serde transport bytes are not confused with canonical bytes.

## Orc recovery and supplementary RSF-4 evidence

Bounded search followed existing private hooks, RSF-2/3 provenance, audit §6 and
known local archive. Exact original monster entries were recovered from
/home/ra/Documents/lwr-m1b-workspace/gravity-data/kro-210607/data.grf.
No similarly named NPC entry substituted. Existing Archive class was AST-selected
from LWR ops/local/lwr-visual-identity-foundation-e1/study_references.py and called
without importing its rendering/main code; existing Node GameFileDecrypt.js decoded
the archive entries. Only extracted audited bytes were written to private
/tmp/ro-sprite-forge-audit-e1/orc_skeleton.act and .spr, after hash verification.
No extraction/decryption implementation was copied into the public project.

Recovery source hashes:
- study_references.py: `76594f46bf61bdb45b186e45e36cb937614c0f8cd558ef9bcf1b345b2fbd8c90`
- GameFileDecrypt.js: `5057933b3870328362e168c4ce92e3d4ad487272eec40255e505e1bd494a9d87`
- Orc ACT87004bytes: `31e1e75241bc534422e468ae134892c7b234d66022456b87b0423df5858370e2`
- Orc SPR119327bytes: `a39f864209d63ae75bd62438da61775c510d7c55a78344b3065fb5918a55ce8f`

Existing private fixture suite now passes all10 tests, zero skips. Both preserve
and act-semantic modes retain the exact original ACT/SPR hashes for Novice body,
Novice head and Orc. Original input bytes are checked again after publication.
Orc inventory computes5groups40slots512motions1776visible layers55references/
57stored; unused pool0 indices36,39. Layer order/transforms/all images retained.
This is supplementary RSF-4 evidence; RSF-4 was not reopened or modified.

## Executed commands and results

All commands below exit0. Rust commands use RUSTUP_HOME=/tmp/rsf5-rustup,
CARGO_HOME=/tmp/rsf5-cargo, cargo=/tmp/rsf5-cargo/bin/cargo, manifest
`tools/rust-oracle/Cargo.toml`. Python is .venv/bin/python3.14.4.

| Command | Result | Durable log |
| --- | --- | --- |
| cargo build --offline --locked | Compiled | build documented above |
| cargo fmt --check | PASS | rust-fmt.log |
| cargo clippy --offline --locked --all-targets -- -D warnings | PASS | rust-clippy.log |
| cargo test --offline --locked | 3 passed | rust-tests.log |
| .venv/bin/python tools/rust-oracle/test_parity.py | 11 passed | parity-tests.log |
| .venv/bin/python tools/rust-oracle/private_parity.py | all3 AGREEMENT, repeated reports equal | private-parity.json |
| .venv/bin/python -m unittest discover -s tests -v | 69 passed | python-tests.log |
| .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v | 10 passed, no skips | private-preservation.log |
| .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14 | DISTRIBUTION_CHECK_PASS, installed69 | distribution.log |

Synthetic tests include independently built minimal/golden ACT, indexed-only,
truecolor-only, mixed-pool, shared refs/unused images, ordered multilayers,
transforms including negative/signed-zero bits, raw events, anchors, delays,
nonzero palette and 2x2 truecolor row/channel/alpha expectations. All424 ACT
prefixes and all1067 SPR prefixes rejected by both implementations. Explicit
version/count/ref/event/anchor/nonfinite/delay corruption and RLE underrun,
overrun/dangling-zero, invalid dimensions and 65M aggregate-pixel budget fail
in both decoders. Valid mutations and full report comparisons retain all fields.
Mismatch/omitted-key/layer-reorder probes demonstrate comparator failures.
No malformed input is called agreed merely because both reports omitted it.

No Python runtime or network is invoked by the Rust decoder. Installed Python
stdlib-only smoke/package checks pass without Rust involvement. Production runtime
dependencies remain empty. Tools are outside the Python distribution; private art
is excluded. The existing test-only Pillow12.1.1 offline wheelhouse provenance and
build frontend limitations remain as documented in RSF-4 (OS-repacked cp314 test
wheel, not an official downloaded wheel; build frontend1.6.1/pyproject-hooks1.3.3).
Python3.12 and full3.13 matrix NOT_RUN in this assignment; no supported-interpreter
matrix or cross-platform Rust reproducibility claim is made.

## Private parity and identities

private-parity.json SHA-256
`493f0e5046df32cbd77aa4e8185c0dabaa3a966d59e852e394abc1764d802be3`.
It records exact input hashes, equal canonical Python/Rust report hashes, computed
summaries and empty mismatch arrays for all3 pairs, with deterministic rerun checks.
It contains no raw artwork/pixel dumps. The full raw reports are generated transiently
for comparison; only hashes/structural counts are retained here.

## Final independent QA and tracker synchronization

Configured forge_qa_reviewer `/root/rsf5_independent_qa`, separate read-only context,
returned QA_PASS on the final 36-file manifest. The reviewer independently reran
Rust fmt/Clippy/tests, public/private Python, cross-language parity and installed
distribution checks: all exit0, counts reproduced exactly. All three private
canonical reports match saved hashes. Upstream21 source files and MIT license
match the pinned Git objects. Extra25 valid raw-field/opaque-event probes and15
malformed semantic probes passed. No corrective findings; no implementation changes
were requested by QA. See QA_REVIEW.md and durable qa-*.log files.

Coordinator then checked all four evidenced live criteria and transitioned RSF-5
to Accepted (`done`, column `vnkxm3fyt0tmewq1rdokfops`). Final task read-back is
kaneo-final-readback.json. Final QA evidence comment ID
`kzf5uq21y468hvmtvhehx23b`; implementation handoff comment
`s7y4j6j7sv59gu7439sx0v1t`. No pending Kaneo operations. RSF-4 was not reopened.

Final gate interpretation:
- M0-S PASS: previously accepted structural/semantic/package evidence plus fresh
  successful restored-Orc preservation, inventory and private regression checks.
- M0-I PASS: independent original-byte decoding, full structural parity, corruption
  rejection and all three required audited fixture pairs verified.
- M0-N NOT_RUN / UNVERIFIED: native Korangar execution belongs to RSF-6.
- Overall M0 is not fully accepted. No native environment blocker was established,
  so the formal environment-blocked M0_PARTIAL_NATIVE_UNVERIFIED classification
  is not asserted here. The review's shorthand partial-native label does not
  establish that missing prerequisite. Artwork UNASSIGNED; visual approval NOT_RUN.

Live next task: RSF-6 (`lyjs5izms0mcj700m7o25dam`),
`[M0] Pinned Korangar exact-slot verification and M0 gate packet`, Backlog/to-do.
Its blocking tasks RSF-4 and RSF-5 are both Accepted, so it is dependency-eligible.
RSF-6 was read only; no native verification or task transition was started.

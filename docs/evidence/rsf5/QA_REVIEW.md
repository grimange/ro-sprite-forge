# RSF-5 independent QA

Verdict: **QA_PASS**. Reviewer: repository-configured `forge_qa_reviewer`,
`/root/rsf5_independent_qa`, separate read-only context. Coordinator preserved this
report from the reviewer's final response. Reviewer changed no implementation,
evidence, Git or Kaneo records. No acceptance-blocking defects or corrective findings.

Reviewed36-file implementation manifest SHA-256:
`39e724b1004406fc471c5259a10539f6586f512d7eb0fe4f07ff308fd1e4da94`.
All61 accepted Python baseline files retain their preserved hashes. All21 copied
upstream Rust source files and retained MIT license exactly match Git objects at
`3f3d88a583203f09d079712f43343c1041258ffd`.

The reviewer verified that the Rust executable independently decodes original
ACT/SPR bytes, without Python invocation. Bounded preflight precedes upstream
allocations. Supplemental decoding retains complete40-byte event records. ACT
comparison includes ordered actions/motions/layers, bounds, transformations,
references, events, anchors, reserved bytes and exact delay bit patterns. SPR
comparison retains raw indexed pixels and palette separately from normalized
RGBA, including truecolor row/channel ordering and RGB under zero alpha. The
comparator detects omitted/extra fields, lengths, ordering and exact value changes
with structural mismatch locations.

## Independently executed commands

All exit0. Rust uses RUSTUP_HOME=/tmp/rsf5-rustup,
CARGO_HOME=/tmp/rsf5-cargo, /tmp/rsf5-cargo/bin/cargo;
nightly-2026-02-01, rustc1.95.0-nightly, Linux x86_64.

| Command | Result |
| --- | --- |
| cargo fmt --manifest-path tools/rust-oracle/Cargo.toml --check | PASS |
| cargo clippy --offline --locked --manifest-path tools/rust-oracle/Cargo.toml --all-targets -- -D warnings | PASS |
| cargo test --offline --locked --manifest-path tools/rust-oracle/Cargo.toml | 3 passed |
| .venv/bin/python tools/rust-oracle/test_parity.py | 11 passed |
| .venv/bin/python tools/rust-oracle/private_parity.py | All3 pairs agree; repeated reports equal |
| .venv/bin/python -m unittest discover -s tests -v | 69 passed |
| .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v | 10 passed, no skips |
| .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14 | DISTRIBUTION_CHECK_PASS; installed69 tests pass |

Additional independent probes:25 valid cases covering nontext raw event bytes,
reserved bytes, integer limits, float32 subnormal/extreme values and transforms;
15 invalid pool/index/event/scale/delay cases rejected by both decoders. Rust
returns exit3 and no successful report for malformed inputs. These supplemental
ad hoc probes were reviewer-executed; the commands above are the checked-in
reproducible regression suite.

## Private fixtures

All three complete canonical reports independently reproduce saved evidence:

| Pair | Observed structure | Equal Python/Rust report SHA-256 |
| --- | --- | --- |
| Novice body | 13groups,104slots,456motions,110referenced identities,108content classes | b3e0b850e243e43c4a2a3962dc86b750e260c921c485f7b63a7b94565ee2ed30 |
| Novice head | Separate identity;104slots,456motions,15referenced images | 93f6625b59edfef897dbf35258eaf442ef9d4f4a9cceb2d4ee7c772661c2246e |
| Orc Skeleton | 5groups,40slots,512motions,1776visible layers,55referenced/57stored; unused pool0 indices36,39 | caa22f4f574e71b0ae1fac45223bf9c4024f23fb2408908d67e573490379edc4 |

Orc ACT hash `31e1e75241bc534422e468ae134892c7b234d66022456b87b0423df5858370e2`
and SPR hash `a39f864209d63ae75bd62438da61775c510d7c55a78344b3065fb5918a55ce8f`
match audited original pins. The existing private suite independently passes raw
preservation and ACT-semantic modes, publication, source immutability, ordered
multilayer retention and unused-image retention. This supplies missing supplementary
RSF-4 Orc evidence. Installed Python remains independent of Rust at runtime.

All four live RSF-5 acceptance criteria are supported. Reviewer observed QA Review
with unchecked criteria before coordinator synchronization; final Accepted state
and four checked criteria are separately recorded in kaneo-final-readback.json.

## Gates and limits

Reviewer supports M0-S PASS, M0-I PASS and M0-N NOT_RUN / UNVERIFIED. No native
execution, human visual approval, full Python3.12/3.13 matrix or other-platform
reproducibility was verified. No RSF-6 implementation was started.

Reviewer used `M0_PARTIAL_NATIVE_UNVERIFIED` as an overall shorthand. Coordinator
qualification: the repository reserves that formal label for an established native
environment blocker. No such blocker was tested here; overall M0 remains incomplete
with native verification unexecuted, and M0_PASS is not claimed.

Independent raw command logs were copied unchanged from /tmp/rsf5-qa-*.log into
this directory as qa-*.log. Source files were unchanged after review.

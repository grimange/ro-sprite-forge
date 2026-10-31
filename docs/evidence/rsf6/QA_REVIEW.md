# Independent RSF-6 QA — QA_PASS

Reviewer: repository-configured `forge_qa_reviewer`, separate context
`/root/rsf6_independent_qa`. Reviewer made no implementation/evidence edits,
commits or Kaneo writes. Coordinator transcribed this verdict. Scope:
tools/korangar-native and docs/evidence/rsf6; complete accepted untracked source
was available. Live task, board, dependencies, AGENTS, forge-qa, QA template,
plan §4.7/M0, source and actual evidence were independently inspected.

**QA_PASS for the bounded technical implementation; no blocking findings remain.**
Formal RSF-6 acceptance and overall M0 closure await the live task's operator
native decision. This verdict does not supply that decision or aesthetic approval.

## Independently executed verification

| Check | Actual result |
| --- | --- |
| Fresh prepare into /tmp/rsf6-qa-stage-review-20261030 | Exit0;89 immutable upstream inputs; byte-identical source manifest |
| Accepted97, final10 implementation,89 upstream and120 generated file hashes | All match; accepted archive verified |
| Native build, maintained fmt/rustfmt, Clippy -D warnings | All exit0 |
| Native cargo test | Exit0;4 tests pass |
| Native Python observation verifier | Exit0;NATIVE_CHECKS_PASSED |
| Native Python verifier tests after hardening | Exit0;9 tests pass |
| Public Python suite | Exit0;69 tests pass |
| Private fixture suite | Exit0;10 tests pass, no skips |
| Rust oracle synthetic parity suite | Exit0;11 tests pass, including corruption/truncation cases |
| Rust oracle private parity | Exit0;all3 AGREEMENT, zero mismatches |
| Installed distribution checker | Exit0;DISTRIBUTION_CHECK_PASS;installed69 pass |

Rust uses documented offline/locked environment and manifest
/tmp/rsf6-native-release/Cargo.toml. Python commands and flags are those in
VERIFICATION.md; reviewer additionally ran tools/rust-oracle/test_parity.py.
Formatting scope retains immutable upstream formatting as documented.

Fresh native execution, cwd /tmp/rsf6-native-release:

```bash
env -u DISPLAY -u WAYLAND_DISPLAY \
  VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json \
  /tmp/rsf6-native-v2/target/debug/rsf-korangar-native \
  /tmp/rsf6-final-inputs.json /tmp/rsf6-qa-native-review-20261030
PYTHONPATH=src .venv/bin/python tools/korangar-native/verify.py \
  /tmp/rsf6-final-inputs.json /tmp/rsf6-qa-native-review-20261030/native-report.json
```

Both exit0. Actual software Vulkan execution reproduces160 positive cases,
1664 frame selections,2688 independently compared prepared visible layers,
84 capture observations and5 expected negative cases. Fresh report is
byte-identical to both implementer runs:
`80b023d2b5cdc9a8bc59a8d643d425a6b4b2c7716d311727e0bbbc4f6a61c72e`.
Executable matches `38fa19a03469325d42570328d31128db5a0a37f821321f8428efb4df84d2ac76`.
Fresh source manifest matches `5b3066f7b0ec11e729455d0e36c9471397efc5f31b4f5eab1e090e54ed21ad2c`.
Final implementation manifest matches `87ee5ec5bc511eae9919b36dff9840396fd514ebae3e1dd5001fd33cd6d9fc77`.

Pinned native loaders, state transitions, pointer-identified selection, multipart
preparation, draw instructions, entity drawer/shaders and WBOIT resolve genuinely
execute. Adapters supply the file boundary, sound registration, camera placement,
render context and readback. Python checks after execution, not native selection.
All six delivered-byte hashes match audited originals. Separate body/head pools,
anchors and ordered layer identities/transforms remain intact. Orc's1776 visible
references,55/57images and Novice's110 identities/108contents remain distinct.

Reviewer independently checked actual PNG hashes, dimensions and non-background
counts for all84 observations/78 unique captures, and viewed private Novice Idle
and Orc Die captures for technical presentation only.

## Negative probes and correction verification

Independently altered actual native reports reject wrong slot, asserted fallback,
missing sequence sample, missing color channels, duplicate prepared/resource
actors and missing mandatory negative evidence. Wrong positive source hash exits101
RESOURCE_MISMATCH before output exists. Five native fallback/unsupported/mismatch
diagnostics remain excluded from positive exact-slot results.

During evidence preparation the implementer closed a report-integrity edge:
zip-based tint comparison needed an explicit vector-length check. Duplicate
actor records are also rejected before dictionary collapse. Reviewer independently
retested final9 unit tests and mutated reports; no blocking findings remain.
No native format/runtime defect or unexplained rendering regression was found.

## Gates and limitations

- M0-S PASS: accepted evidence preserved; relevant tests independently rerun.
- M0-I PASS: synthetic corruption checks and all private parity rerun.
- M0-N technical evidence PASS within isolated native presentation scope.
- Operator native decision PENDING; overall M0 acceptance not granted by reviewer.
- visual_review=NOT_REQUIRED for unchanged reference artwork.

Reviewer did not rerun Slang shader compilation; both executed SPIR-V hashes
match recorded manifest and pinned source provenance was checked. Actual native
GPU draw execution was reproduced. Gameplay reachability, audio, hardware GPU,
full-scene lighting/shadows, cross-platform pixel parity and Python3.12–3.13
matrix remain NOT_TESTED/NOT_RUN. No M1 work authorized or started.

HEAD remains f1bb19bb130beea8b89cf6c029209e93fb241d5a; no commit/push.
RSF-6 was read as QA Review, RSF-4/5 Accepted. Coordinator should record technical
QA_PASS and obtain the explicitly required operator native decision.

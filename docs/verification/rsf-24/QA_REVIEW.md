# RSF-24 independent QA

Verdict: **QA_PASS** for the bounded RSF-24 implementation. No mandatory technical finding
remains open. Reviewer: `/root/rsf24_qa`, separate repository `forge_qa_reviewer` context.
This record is transcribed by the coordinator from the reviewer's final report. The reviewer
made no implementation edits, commits, Kaneo writes or ownership changes.

The reviewer read the live four acceptance criteria, AGENTS.md, applicable QA instructions,
relevant plan sections, pinned Korangar loading/selection source, bounded diff and final
evidence. The plan hash matches the supplied baseline.

## Independently executed checks

| Check | Result |
|---|---|
| `.venv/bin/python -m unittest discover -s tests -p test_image_pool_remapping.py -v` | 13 PASS; nine Rust-checked pool/policy combinations |
| `.venv/bin/python -m unittest discover -s tests` | 431 PASS, exit 0 |
| Initial complete private suite before Orc recovery | 20 PASS, 18 skipped |
| `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p test_compiler_fixtures.py -v` after recovery | 2 PASS: Novice and Orc, exit 0 |
| `.venv/bin/python tools/rust-oracle/test_parity.py` | 11 PASS, exit 0 |
| Ten `scripts/check_*schema*.py` commands | 10 PASS, exit 0 |
| Actual generated bounded-manifest JSON Schema validation | PASS |
| Independent Rust mapping probe | 48 occurrences: 2 targeted, 46 unaffected; asymmetric RGBA/alpha pixels, complete effective references and metadata preserved |
| Independent Chromium control inspection | `preserve_pool` default and explicit RGBA selection verified; no operator records changed |
| Implementation-manifest integrity | All listed source and evidence SHA-256 hashes match |

Recovered Orc ACT and SPR independently match audited hashes:

- ACT: `31e1e75241bc534422e468ae134892c7b234d66022456b87b0423df5858370e2`
- SPR: `a39f864209d63ae75bd62438da61775c510d7c55a78344b3065fb5918a55ce8f`

## Findings and independent retest

1. Omitted policy selected RGBA implicitly. Implementer changed core, CLI, API and UI defaults
   to `preserve_pool`; explicit RGBA selection is required. Independent repro now passes.
2. Actual bounded manifests failed the runtime-profile schema; writer 1.1 accepted missing
   remapping evidence. Actual generated manifests now validate; missing evidence is rejected.
3. Publication accepted corrupted or absent optional head output bytes. Complete pair,
   presence, lengths, hashes and decoded inventory now validate. Original repros reject with
   `COMPILATION_PAIR_MISMATCH` and publish no files.

All findings were fixed by the implementer and independently retested by the reviewer.
Maximum valid index and append overflow regression passes. Unsupported exact indexed
conversions reject fractional alpha, absent palette colors and hidden-RGB loss with
requirement-specific diagnostics.

The reviewer verified actual pool-relative ACT semantics against the pinned runtime.
Indexed append shifts runtime truecolor texture positions while preserving effective
pool/index identities. Pixel and complete unaffected-reference assertions establish
preservation independently of unchanged raw ACT integers. Original duplicate/unused entries,
raw RLE, palette data, ordered multilayer metadata and no-op bytes remain preserved.

## Scope and execution limits

The reviewer inspected and hash-checked coordinator evidence for installed-distribution
verification, the final full private suite (37 PASS, one earlier-native-report-dependent skip),
three-build golden reproduction and ten final Chromium journeys. These were not claimed as
independently rerun. Independent Chromium policy assertions succeeded before a subsequent
browser-close MCP call hung for 996 seconds and was interrupted. The coordinator's isolated
Chromium wrapper completed all ten journeys against the fresh final-code server.

Python 3.12/3.13: NOT_RUN, unavailable. Native playback/rendering: UNVERIFIED.
The sole remaining private skip concerns an earlier native report outside this task's boundary.
No aesthetic approval, production authorization or full M5 acceptance is granted.

Reviewed implementation-manifest SHA-256:
`c23f28b4fce4191dd9e15dc9c19414c59739226fda8535ca8902f4fea022f859`.

M5-S: PASS for bounded RSF-24 structural/preservation scope.
M5-I: PASS. M5-N: UNVERIFIED.

At reviewer read-back the task was still QA Review (`in-review`), Codex-owned, with unchecked
criteria pending coordinator synchronization. Final authoritative read-back is recorded
separately in KANEO_READBACK.json.

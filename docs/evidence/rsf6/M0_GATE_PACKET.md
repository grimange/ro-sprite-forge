# Current M0 verdict — M0_VERIFIED

Explicit operator acceptance is recorded in OPERATOR_ACCEPTANCE.md and live Kaneo RSF-6, now Accepted. **M0-S=PASS; M0-I=PASS; M0-N=PASS; overall M0_VERIFIED.** All limitations below remain applicable. The operator separately authorizes RSF-7.

The following packet is retained as the historical decision scope submitted for acceptance. Its pending-decision language is superseded by the explicit decision above.

# M0 gate packet — operator native decision pending

RSF-6 technical implementation and self-verification are complete. Independent
QA_PASS is recorded separately in QA_REVIEW.md. This packet requests no new
artwork approval and starts no M1 work.

| Gate | Evidence | Current acceptance |
| --- | --- | --- |
| M0-S | Accepted RSF-4 plus RSF-5 recovered Orc preservation evidence; fresh69 public/10 private tests and installed-distribution checks pass | PASS |
| M0-I | Accepted RSF-5 independent binary decoding; all3 audited source pairs freshly agree with no mismatches | PASS |
| M0-N | Real pinned native presentation, loaded-byte hashes,160 exact action/view cases,1664 frames,2688 independently checked prepared layers,84 native capture observations,5 negative cases | Technical checks PASS; final native acceptance awaits operator decision; independent QA_PASS complete |
| Overall M0 | Structural, independent and native authorities are separate | NOT_YET_ACCEPTED |

## Decision scope

Accept the **bounded native presentation verification of unchanged audited male
Novice body/head and Orc Skeleton resources**, using the pinned Korangar native
loaders, animation selection/preparation and entity GPU drawing paths.

- Pinned upstream: `3f3d88a583203f09d079712f43343c1041258ffd`.
- Executable SHA-256: `38fa19a03469325d42570328d31128db5a0a37f821321f8428efb4df84d2ac76`.
- Build source manifest: `5b3066f7b0ec11e729455d0e36c9471397efc5f31b4f5eab1e090e54ed21ad2c`.
- Native trace: `80b023d2b5cdc9a8bc59a8d643d425a6b4b2c7716d311727e0bbbc4f6a61c72e`.
- Platform: Linux x86_64, software Vulkan llvmpipe/Mesa26.0.8.
- Artwork: unchanged private references; visual_review=NOT_REQUIRED.

Acceptance does not assert ordinary gameplay reachability, audible events,
hardware GPU parity, full scene lighting/shadows, new-art aesthetic approval,
or cross-platform pixel determinism. M1 implementation requires a separate
operator request. Known native fallback/modulo behavior is diagnosed and is
excluded from exact-slot positive results.

The complete technical observations are in native-report.json.gz; summaries,
all six loaded resource hashes, source provenance, actual commands and limits
are in VERIFICATION.md and native-result.json. Private captures remain outside
the repository at `/tmp/rsf6-native-run-final-1` and `-2`; reproducible recipes
and their hashes are durable here. Representative capture names:
`novice-Idle-0-0.png`, `orc-Die-0-21.png`.

The live Kaneo task explicitly requires an **operator native decision**.
The repository Kaneo skill/workflow retains that decision for the operator.
No agent or successful test run supplies it automatically.

After QA_PASS and operator acceptance, the coordinator may record M0-N=PASS,
M0_VERIFIED and move RSF-6 to Accepted. Until then the task stays in QA Review;
this is an acceptance decision pending, not an environment-blocked native run.

# RSF-31 Implementation and Verification Plan

## Objective
Implement comprehensive diagnostics, exact candidate-frame identity, and repeatability verification for variable-frame-rate (VFR) and constant-frame-rate (CFR) media within the established RO Sprite Forge media pipeline:
1. Exact presentation-frame identity for supported CFR and VFR sources.
2. Correct requested-versus-resolved PTS reporting.
3. Rational time-base preservation.
4. Correct handling of duplicate, missing and ambiguous timestamps.
5. Explicit nonchronological frame-selection ordering.
6. Candidate PNG pixel correctness against known synthetic patterns.
7. Deterministic extraction and canonical provenance under a pinned toolchain.
8. Appropriate diagnostics for unsupported or invalid selections.
9. Preservation of video versus ACT timing separation.
10. Consistent assignment/coverage accounting (RSF-30 reconciliation).

## Scope & Constraints
- Retain all accepted M0–M5 systems and M6 accepted tasks (RSF-28, RSF-29, RSF-30).
- No second video decoder, optical-flow interpolation, auto pose/direction inference, AI background removal, or new compiler architecture.
- Pinned FFmpeg/FFprobe toolchain (`8.0.1-3ubuntu2`) with bitexact RGB/RGBA extraction.
- Preserved separation between media presentation timestamps (PTS) and ACT runtime delays.
- Full reconciliation of RSF-30 scoped coverage arithmetic ($12\text{ required} = 3\text{ assigned} + 9\text{ unassigned}$).
- Verification-first: robust 25-scenario automated verification suite in `tests/test_vfr_diagnostics.py`.

## 25 Focused Test Scenarios
1. `test_01_cfr_exact_frame_identity`: CFR inspection, sequential PTS [0, 40, 80, 120, 160], display order, and exact decoded RGB pixels.
2. `test_02_vfr_exact_frame_identity`: VFR inspection, irregular intervals [40, 80, 40, 140], no nominal-FPS approximation.
3. `test_03_nonchronological_pts_selection`: Selection PTS [300, 0, 120] -> ordinals [4, 0, 2], nonchronological order preserved.
4. `test_04_presentation_order_and_b_frames`: MPEG4 container with B-frames, presentation order vs decode order distinction.
5. `test_05_duplicate_pts_diagnostics`: Synthetic fixture with duplicate PTS 40 fails closed on exact PTS request (`matches=2`); ordinal selection succeeds.
6. `test_06_missing_pts_diagnostics`: Absent PTS (e.g. 80 in VFR fixture) fails closed (`matches=0`); None PTS rejected.
7. `test_07_invalid_ordinal_rejection`: Negative, out-of-range, and non-integer ordinals fail closed before tool execution.
8. `test_08_out_of_range_selection_rejection`: Values exceeding integer bounds, empty selections, quota violations, and duplicates rejected immediately.
9. `test_09_rational_time_base_preservation`: Exact integer numerator/denominator pairs (e.g. 1/1000, 1/90000, 1001/30000) preserved without floats.
10. `test_10_large_metadata_integer_precision`: Values exceeding JS safe integer limit ($2^{53}-1$) safely preserved as strings in wire records.
11. `test_11_known_pixel_candidate_verification`: Decoded candidate PNGs match independently known synthetic pixels with 0 mismatch.
12. `test_12_selection_output_count_consistency`: Requesting K items produces exactly K PNGs and K manifest items.
13. `test_13_idempotent_reimport`: Re-staging identical video and selection does not produce duplicate imports or bump revision.
14. `test_14_candidate_order_identity`: Selection order changes collection manifest hash while preserving individual PNG candidate hashes.
15. `test_15_exact_source_sha256_verification`: Mismatched expected source hash fails closed before inspection or tool execution.
16. `test_16_repeated_clean_ffmpeg_execution`: Clean repeated FFmpeg extractions yield bit-exact PNGs and canonical manifest hashes.
17. `test_17_canonical_manifest_byte_identity`: Manifest canonical bytes are bit-exact and validate against JSON Schema.
18. `test_18_toolchain_provenance`: Full toolchain provenance (FFmpeg/FFprobe version, executable SHA-256) preserved in manifest.
19. `test_19_failed_extraction_cleanup`: Extraction failures clean up temporary directories completely.
20. `test_20_failed_publication_preservation`: Failed staging leaves project manifest and revision unincremented.
21. `test_21_optional_dependency_absence`: Core features work without FFmpeg/FFprobe; media functions report typed error.
22. `test_22_no_auto_assignment_or_approval`: Staging video candidates never creates assignments or approves artwork automatically.
23. `test_23_video_act_timing_separation`: Video source PTS does not alter ACT animation delays; timing authorities remain separate.
24. `test_24_rsf30_coverage_reconciliation`: Reconcile RSF-30 coverage arithmetic: 12 required = 3 assigned + 9 unassigned.
25. `test_25_existing_video_walk_compilation_regression`: Video candidate assignment -> preview -> compile -> Rust oracle PASS.

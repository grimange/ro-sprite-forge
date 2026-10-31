# RSF-30 Implementation and Verification Plan

## Objective
Demonstrate the end-to-end integration proving video is an optional, immutable artwork source for the established Walk workflow:
Video -> Explicit frame selection -> Immutable PNG candidates -> Explicit Walk assignment -> Animation preview -> Canonical compilation -> Modified ACT/SPR -> Independent structural verification.

## Scope & Constraints
- Retain existing M0–M5 systems and M6-01 / M6-02 components (RSF-28, RSF-29).
- No new video-specific compiler, custom timing algorithm, or automatic artistic approval.
- Video timing (PTS, rational time base, presentation ordinal) remains strictly independent from ACT animation timing (delays, movement speed, loop semantics).
- Exact Walk requirements use the canonical RSF-9 ledger with explicit ordered topology.
- Scoped Walk coverage remains diagnostic (`PARTIAL_DIAGNOSTIC`); missing views and frames remain reported as missing.
- Verification uses Python codecs, independent Rust oracle (`rsf-rust-oracle`), and clean repeated CLI builds.
- Native Korangar GPU status is truthfully reported as UNVERIFIED for these new video-derived outputs, preserving M5's bounded native acceptance.

## Test Strategy
- `test_01`: Synthetic VFR video PTS [0, 40, 120, 160, 300] inspection and exact PTS selection [300, 0, 120] -> ordinals [4, 0, 2].
- `test_02`: Immutable staging into content-addressed blob store and source catalog entry.
- `test_03`: Formal bounded Walk target declaration and scoped completeness checks.
- `test_04`: Explicit Walk assignment ledger mappings, provenance, and save/reopen survival.
- `test_05`: Compositor preview renders actual video-derived candidate pixels.
- `test_06`: Separation of authorities: video PTS vs ACT runtime playback timing under varying movement_speed; reverse independence.
- `test_07`: Operator review proposal and approval; scoped review invalidation upon source modification.
- `test_08`: Diagnostic compilation and independent Rust oracle verification against golden pixels; unaffected frames preserved bit-for-bit.
- `test_09`: Deterministic repeated CLI compilations with varied environment/prefixes.
- `test_10`: Comprehensive fail-closed negative scenarios (corrupt video hash, invalid PTS, corrupt blob, production export rejection).

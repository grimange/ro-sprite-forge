# Bounded Walk vertical-slice checklist — M4/M5

**Operator-defined target:** actor, runtime profile, Walk action, views/directions,
frame counts PER view, explicit/inherited ordered layer topology and layer roles.
**Scope:** FULL_PROFILE / WALK_ALL_VIEWS / DECLARED_PROTOTYPE_SCOPE.
**Unmapped actions:** listed explicitly with runtime support UNVERIFIED/UNSUPPORTED.

- [ ] Finite requirements produced **before** artwork assignment (no guessed topology).
- [ ] Exact frame-occurrence AND layer-occurrence counts produced.
- [ ] Human-provided PNGs imported with SHA-256/provenance, ordered mapping and transforms.
- [ ] Unassigned and classic fallback occurrences shown separately.
- [ ] Reference/candidate preview shows actual supported transforms/timing; limitations labeled.
- [ ] Exact composition revision approved by real human operator.
- [ ] Deterministic SPR/ACT compiled with no unapproved required substitutions.
- [ ] Independent Rust decode verifies structure and corrupted-input negatives.
- [ ] Pinned Korangar loads output and resolves **requested Walk action/view/ACT slot**.
- [ ] Native fallback state and observed layers/timing captured, not inferred from load.
- [ ] Separate reviewer QA on one actual diff; tracker updated based on live board.

If only one Walk direction is supplied, mark only that declared scope complete; never
claim complete eight-direction Walk or full actor. No native M6 video adapter required:
PNG files extracted externally can be used directly in M4.

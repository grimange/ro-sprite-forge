# Execution Plan — RSF-39 Final Synthetic End-to-End Acceptance and Native Release Verification

**Task:** RSF-39 — [M8] Synthetic end-to-end tutorial and separate native release acceptance  
**Kaneo Task ID:** `bcez9nz3cvf77pewx0q7zgz9`  
**Milestone:** M8 — Release Readiness  
**Implementer:** Antigravity (AGY), Principal Release Acceptance Engineer / Native Game Asset Integration & Verification Specialist  
**Independent QA Reviewer:** `forge-qa-reviewer`  

---

## 1. Objectives & Corridors

RSF-39 is the final acceptance and closure milestone of the RO Sprite Forge implementation plan. It coordinates and executes the complete acceptance chain across 13 decoupled dimensions:
1. **Distribution Corridor:** Clean rebuild of sdist and wheel from current source snapshot; isolated clean-room installation into temporary virtual environment outside the git repo; stdlib core verification without optional dependencies.
2. **Synthetic Tutorial Corridor:** Full execution of `docs/operator/TUTORIAL.md` on synthetic monster/character target: topology declaration before art, finite requirements resolution, work order export, PNG sequence ingestion, assignment, preview with integer zoom on checkerboard, explicit operator review, diagnostic vs production build classification, deterministic ACT/SPR compilation.
3. **Approval Invalidation & Rebuild Corridor:** Reopening/replacing one source frame; verifying affected approvals transition to `STALE` while unrelated approvals are preserved; re-approving and demonstrating deterministic rebuild.
4. **Independent Rust Oracle Corridor:** Running the independent Rust decoder oracle (`rsf-rust-oracle`) on compiled ACT/SPR assets; verifying structural parity, layer counts, frame bounds, and pixel values.
5. **Native Korangar Release Corridor:** Running the bounded native verification harness (`tools/korangar-native/verify_walk.py`) against pinned Korangar source (`3f3d88a583203f09d079712f43343c1041258ffd`); verifying requested $\to$ resolved action/view/slot, loaded artifact hash, fallback status, texture upload, and readback properties within the accepted corridor.
6. **Real Playwright Browser Interaction Corridor:** Full headless browser interaction test suite via Playwright with Google Chrome:
   - Frame stepping (`ArrowLeft` / `ArrowRight`)
   - Play/Pause toggle (`Space`)
   - Integer nearest-neighbor zoom (1×, 2×, 3×, 4×, 8×, and `+`/`-`/`0` shortcuts)
   - Background modes (5 modes, `B` shortcut cycle)
   - Review dialog (`A` approve, `R` reject, `Esc` cancel)
   - Typing safety (no shortcut interception in inputs/textareas)
   - Responsive desktop viewports (1920×1080, 1280×800, 1024×768)
   - Loopback, Origin, and CSRF security verification
7. **Documentation & Recovery Reconciliation Corridor:** Reconcile schema migration version terminology (v1 $\to$ v2 vs historical v0/v0.1); verify timestamp canonical identity behavior under differing clocks; test recovery provenance reporting (`backup_manifest_hash`, `restored_manifest_hash`).
8. **Python Support & CI Matrix Corridor:** Reconcile Python 3.12, 3.13, and 3.14 compatibility matrix; document local verification and CI configuration.
9. **Full Regression Execution:** Focused RSF-39 suite, public unit tests, private fixture hooks, schema checkers, and clean distribution checks.
10. **Independent QA Review:** Handoff to `forge-qa-reviewer` for independent read-only audit and verification to achieve `QA_PASS`.
11. **M8 Milestone & Plan Closure:** Complete evaluation of M8 release readiness and final implementation plan completion status.

---

## 2. Planned Steps & Artifacts

- `docs/verification/rsf-39/kaneo-start.json`: Claim and start record.
- `docs/verification/rsf-39/environment.json`: System and tool version record.
- `docs/verification/rsf-39/commands.json`: Exact command specifications.
- `scripts/verify_rsf39_release_acceptance.py`: End-to-end acceptance script.
- `tests/test_playwright_workbench.py`: Dedicated Playwright browser interaction test suite.
- `tests/test_synthetic_release_tutorial.py`: Comprehensive synthetic adoption & invalidation test suite.
- `docs/verification/rsf-39/dist/`: Rebuilt release wheel and sdist.
- `docs/verification/rsf-39/screenshots/`: Browser screenshots at 1920×1080, 1280×800, 1024×768.
- `docs/verification/rsf-39/implementation-manifest.json`: List of all changed/added files with SHA-256.
- `docs/verification/rsf-39/evidence-manifest.json`: Verification command outputs and logs.
- `docs/verification/rsf-39/REPORT.md`: Comprehensive release acceptance report.

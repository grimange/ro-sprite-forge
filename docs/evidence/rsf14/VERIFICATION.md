# RSF-14 Verification Evidence Packet

## Task Identity
- **Task ID**: `xgamjmnrz75c5xjbgfwtndqv` (Ticket: `RSF-14`)
- **Title**: `[M2] Independent preview parity and fidelity evidence`
- **Milestone**: M2
- **Author / Implementer**: Codex / Antigravity Implementation Session
- **Status**: Implemented, verified locally, ready for independent QA Review

---

## Deliverables & Component Architecture

1. **Packaged Draft 2020-12 Schema** (`src/ro_sprite_forge/schemas/preview-parity-report-v1.json`):
   - Schema ID: `rsf.preview-parity-report/v1`
   - Defines strict structure for native reference provenance (Korangar commit, SPIR-V shader hashes, native report hash), source asset hashes, tested scope, objective geometric/transform/anchor/stepping comparisons, canonical difference explanations, and required `sealed` cryptographic digest.
2. **Deterministic Parity Verification Script** (`scripts/verify_preview_parity.py`):
   - Compares Python preview compositor frame geometry and layer preparation against pinned Korangar native report (`docs/evidence/rsf6/native-report.json.gz`).
   - Evaluates all 160 native cases, 1,664 frame selections, and 2,688 prepared layers across Novice (104 slots, 456 motions, 912 visible layers) and Orc Skeleton (40 slots, 512 motions, 1,776 visible layers).
   - Generates and schema-validates the sealed canonical evidence file `docs/evidence/rsf14/preview-parity-report.json`.
3. **Audited Private Fixture Regression Suite** (`tests/private_fixture_hooks/test_parity_evidence.py`):
   - Integrates RSF-14 parity verification directly into continuous testing hooks.
   - Verifies 0-pixel delta for Novice multipart body-to-head anchor positioning across all 456 motion occurrences.
   - Verifies Orc Skeleton multilayer ordering, mirror flags, and angle rotation, including the 22-frame Death South action (Action 32, up to 12 layers per frame, total 176 layers).
   - Verifies all 160 native test cases and 1,664 frame stepping selections.
   - Validates report schema compliance and cryptographic seal.
4. **Architectural & Mathematical Fidelity Specification** (`docs/architecture/RSF14_FIDELITY.md`):
   - Mathematical comparison between Python CPU Pillow order-preserving alpha-over ($A \text{ over } B$) and Korangar GPU Weighted Blended Order-Independent Transparency (WBOIT) using `Rgba16Float` accumulation, `R8Unorm` revealage, and resolve post-processing.
   - Technical differences explained: CPU alpha-over vs GPU WBOIT, 2D integer canvas centering vs 3D perspective camera billboard projection, and raw motion ordinals vs Korangar zero-clip compaction.
   - Invalidation rules: any source hash modification or semantics change invalidates affected parity reports.
   - Authority boundaries: technical verification (`geometry: "VERIFIED"`, `technical_difference_only: true`) vs operator aesthetic authority (`artistic_approval: "UNVERIFIED"`, `native_pixel_parity: "UNVERIFIED"`, `overall: "PARTIAL"`).

---

## Acceptance Criteria Traceability

| Acceptance Criterion | Implementation Evidence | Result |
| :--- | :--- | :--- |
| **1. Compare transforms, ordering, alpha, timing, and anchors against native captures** | Evaluated 160 cases, 1,664 frame selections, and 2,688 prepared layers (912 Novice + 1,776 Orc Skeleton) against `docs/evidence/rsf6/native-report.json.gz`. | **PASS** (0 mismatches across all 2,688 prepared layers) |
| **2. Document exact sources, hashes, scope, differences, and reproducible artifacts** | Fully documented in `docs/architecture/RSF14_FIDELITY.md` and sealed canonical report `docs/evidence/rsf14/preview-parity-report.json` with SHA-256 provenance for all fixtures, SPIR-V shaders, and native captures. | **PASS** |
| **3. Absent/partial parity keeps affected preview PARTIAL/UNVERIFIED** | Formally declared in report and schema: `overall: "PARTIAL"`, `native_pixel_parity: "UNVERIFIED"`, `artistic_approval: "UNVERIFIED"`, `technical_difference_only: true`. Provisional art review never becomes verified visual runtime acceptance. | **PASS** |
| **4. Preview parity does not replace native evidence or operator aesthetic approval; semantics changes invalidate affected scope** | Explicit invalidation rules specified in `RSF14_FIDELITY.md`. Algorithmic PASS strictly separated from human artistic approval and native Korangar slot proof. | **PASS** |

---

## Verification Results Summary

| Verification Gate | Command | Result | Details |
| :--- | :--- | :--- | :--- |
| **Parity Verification Script** | `.venv/bin/python scripts/verify_preview_parity.py` | **PASS** | `PREVIEW_PARITY_VERIFICATION_PASS` (160 cases, 1,664 selections, 2,688 layers, 0 mismatches) |
| **Parity Unit Tests** | `.venv/bin/python -m unittest tests/private_fixture_hooks/test_parity_evidence.py` | **PASS** | 4/4 passing (6.107s) |
| **Full Public Test Suite** | `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` | **PASS** | 245/245 passing (3.666s) |
| **Audited Private Fixtures** | `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py'` | **PASS** | 36/36 passing (12.176s) |
| **Package & Wheel Distribution** | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | **PASS** | `DISTRIBUTION_CHECK_PASS` (245 tests in isolated wheel install) |

---

## Artifact Hashes

- `src/ro_sprite_forge/schemas/preview-parity-report-v1.json`: `411d5f7012d2972557276bbfe6be114d326f366bcac961e37d34e40eb52722d1`
- `scripts/verify_preview_parity.py`: `9f04f8a9d5376d676c51102d39ffbfa9b7032c95bb65d57d81400456acd87eca`
- `tests/private_fixture_hooks/test_parity_evidence.py`: `f92d6defc7d84a3a18dfa897e5f228246d2080c96519cedc811840bbd9a97b6b`
- `docs/architecture/RSF14_FIDELITY.md`: `3d42cd374eca73a63f8d0f61ea6dee223fcb6c6aceb303ac3f45435884bdadae`
- `docs/evidence/rsf14/preview-parity-report.json`: `053a0a64c4f39ca0a463218d2783e2c9abaebf166c5e33e5838dc5b775180173`

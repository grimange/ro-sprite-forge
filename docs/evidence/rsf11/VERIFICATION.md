# RSF-11 Verification Evidence

**Task ID:** `gspmf9so83jbn57y0anhz522` — `[M2] Order-preserving multilayer preview compositor`  
**Milestone:** M2  
**Assignee:** AGY (`ICJQmirJliEFAZN3jBl3ZitHCandT0FG`)  
**Status at handoff:** In Progress -> moving to QA Review (`in-review`)  

---

## 1. Implementation Identity and Preservation

- **Planning Baseline SHA-256:** `5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e` (verified).
- **Implementation Manifest SHA-256:** (recorded in `test-results.json`).
- **Implementation Paths (6 files):**
  1. `docs/architecture/RSF11_PREVIEW.md`
  2. `src/ro_sprite_forge/cli.py`
  3. `src/ro_sprite_forge/formats/preview.py`
  4. `src/ro_sprite_forge/schemas/preview-result-v1.json`
  5. `tests/private_fixture_hooks/test_preview_fixtures.py`
  6. `tests/test_preview.py`
- **Archive `implementation-source.tar.gz`:** Contains only these six files. Zero private ACT, SPR, GRF, or proprietary raster assets are bundled.
- **Git State:** Read-only metadata posture preserved. No commits, rebase, force-push, or destructive working-tree resets.

---

## 2. Core Capabilities Delivered

1. **Multilayer Sequential Composition:** Composites visible clips in exact sequential order without premature flattening.
2. **Integer-Center Placement:** Faithful reproduction of classic Ragnarok and Korangar origin offset calculations:
   $$\text{shift}_x = - \lfloor \frac{\text{width} - 1}{2} \rfloor, \quad \text{shift}_y = - \lfloor \frac{\text{height} - 1}{2} \rfloor$$
3. **Affine Transformations:**
   - Horizontal mirroring (`mirror == 1` and negative scaling).
   - Bilinear non-uniform scaling (`scale_x`, `scale_y`).
   - Clockwise screen-space rotation from ACT integer degrees.
   - 32-bit per-channel color tinting and alpha modulation.
4. **Safe Canvas Clipping:** Boundary-intersecting clips are safely cropped and composited without crashing or throwing bad-position exceptions.
5. **Multipart Actor Anchoring:** Computes `(parent_anchor - child_anchor)` offsets for composite actors (Novice body + head).
6. **Pool & Format Preservation:** Indexed SPR representation and palette are never modified or silently converted to RGBA.
7. **Draft 2020-12 Schema Compliance:** Every preview report validates against packaged `rsf.preview-result/v1`.
8. **CLI Interface:** `ro-sprite-forge preview` provides atomic PNG rendering and canonical JSON reporting.

---

## 3. Test & Verification Command Evidence

| Command | Exit Code | Scope & Findings | Log Artifact |
|---|---|---|---|
| `PYTHONPATH=src:tests .venv/bin/python -m unittest tests/test_preview.py` | 0 | 20/20 synthetic pixel scenarios pass (alpha blend, occlusion, tint, mirror, scale, rotation, clipping, determinism, schema) | `preview-tests.log` |
| `PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -p "test_*.py"` | 0 | 192/192 public unit tests pass | `public-tests.log` |
| `PYTHONPATH=src:tests:tests/private_fixture_hooks .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p "test_*.py"` | 0 | 22/22 private fixture tests pass (Novice body+head, Orc Skeleton 12-layer death motion, RSF-6 native report cross-check) | `private-tests.log` |
| `python3 -c "check Draft 2020-12 schema validation"` | 0 | All examples in `examples.json` pass JSON Schema Draft 2020-12 validation | `preview-schema.log` |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | 0 | `DISTRIBUTION_CHECK_PASS`; clean wheel build, identical repeated wheel SHA-256, isolated venv passes all 192 public tests | `distribution.log` |

---

## 4. Reproducible Examples & Scenarios

Run:
```bash
PYTHONPATH=src:tests .venv/bin/python docs/evidence/rsf11/reproduce_examples.py
```
Outputs `docs/evidence/rsf11/examples.json` containing 8 canonical preview reports:
1. `single_opaque_layer` (1 layer, fidelity: VERIFIED)
2. `two_overlapping_layers_order` (2 layers, fidelity: VERIFIED, top layer occludes bottom)
3. `alpha_blending` (2 layers, fidelity: VERIFIED, 50% alpha blended)
4. `affine_transformations` (1 layer, fidelity: VERIFIED, mirror=True, scale=(1.5, 0.8), angle=45)
5. `multipart_anchor_alignment` (2 layers, fidelity: VERIFIED, head offset includes body anchor minus head anchor)
6. `safe_boundary_clipping` (1 layer, fidelity: VERIFIED, clipped=True)
7. `synthetic_12_layer_motion` (12 layers, fidelity: VERIFIED, full 12-layer sequential stack)
8. `corrupt_sprite_reference` (0 layers, fidelity: INVALID, error logged)

---

## 5. Milestone Gate Declarations

- **M0 Gates:**
  - `M0-S`: PASS
  - `M0-I`: PASS
  - `M0-N`: PASS
- **M1 Contracts:**
  - `RSF-7`: Accepted
  - `RSF-8`: Accepted
  - `RSF-9`: Accepted
  - `RSF-10`: Accepted
- **M2 Preview Foundation:**
  - `RSF-11`: `QA_REVIEW` submitted; `export_ready: false` (no compilation or video ingestion claimed).
  - Native verification status: unverified for candidate new art (M5 gate).

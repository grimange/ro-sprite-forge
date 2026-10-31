# RSF-14 Preview Parity and Rendering Fidelity Specification

## 1. Scope and Architectural Role

RO Sprite Forge is a standalone, local, human-operated requirements planner, animation inspection workbench, and deterministic SPR/ACT compiler. Its primary animation runtime target is a pinned build of Korangar.

The Python preview compositor implemented in RSF-11 (`ro_sprite_forge.formats.preview`) provides local human operators with deterministic visual feedback during animation inspection, frame comparison, and timeline scrub. RSF-14 establishes the rigorous mathematical and architectural comparison between this Python CPU preview pipeline and Korangar's native GPU rendering pipeline, supported by reproducible empirical evidence from private Novice and Orc Skeleton fixtures (`docs/evidence/rsf6/native-report.json.gz`).

---

## 2. Mathematical Pipeline Comparison

| Rendering Property | Python Preview Compositor (RSF-11 / RSF-13) | Pinned Korangar GPU Pipeline (RSF-6) | Parity Status |
| :--- | :--- | :--- | :--- |
| **Execution Environment** | Python 3.12+ CPU, Pillow rasterization | Rust / Vulkan 3D graphics pipeline | **Architecturally Distinct** |
| **Canvas & Projection** | 2D integer coordinate grid, centered at `((width-1)//2, (height-1)//2)` | 3D perspective / orthographic billboard in camera coordinate space | **Equivalence on Planar Projection** |
| **Layer Ordering** | Sequential ordered list (Body layers -> Head layers) | Order-independent via WBOIT MRT buffers + depth testing | **Exact Transform Parity (0 mismatches)** |
| **Layer Transforms** | Scale, integer/float offset, nearest-neighbor rotation | 3D billboard model matrix rotation and translation | **Exact Transform Parity (0 mismatches)** |
| **Multipart Anchors** | $\Delta = (A_{body}.x - A_{head}.x, A_{body}.y - A_{head}.y)$ | Exact same anchor subtraction during billboard attachment | **Exact Match (0-pixel deviation)** |
| **Alpha Blending Model** | Standard Porter-Duff Alpha-Over ($A \text{ over } B$) | McGuire & Bavoil Weighted Blended OIT (WBOIT) | **Pixel Parity UNVERIFIED** |
| **Frame Timing / Stepping**| Discrete integer frame timeline based on ACT frame delay | Native Korangar tick accumulator stepping | **Exact Stepping Parity (1,664/1,664 selections)** |

---

## 3. Alpha Blending: Alpha-Over vs. GPU WBOIT

### 3.1 Python CPU Alpha-Over Formulation
The Python compositor renders visible layers using ordered CPU alpha-compositing:

$$C_{out} = C_{src} \cdot \alpha_{src} + C_{dst} \cdot (1 - \alpha_{src})$$

$$\alpha_{out} = \alpha_{src} + \alpha_{dst} \cdot (1 - \alpha_{src})$$

This model evaluates layers in strict ACT layer order, guaranteeing deterministic, bit-for-bit reproducible output on CPU across all operating systems.

### 3.2 Korangar GPU WBOIT Formulation
Korangar implements Weighted Blended Order-Independent Transparency (WBOIT) using two Multiple Render Targets (MRT) and a resolve shader:
- **Accumulation Buffer** (`Rgba16Float`):
  $$\text{Accum} = \sum_{i} \left( C_i \cdot \alpha_i \cdot w(z_i, \alpha_i), \; \alpha_i \cdot w(z_i, \alpha_i) \right)$$
- **Revealage Buffer** (`R8Unorm`):
  $$\text{Reveal} = \prod_{i} (1 - \alpha_i)$$
- **Weight Function** $w(z, \alpha)$:
  $$w(z, \alpha) = \alpha \cdot \max\left(10^{-2}, \min\left(3 \cdot 10^3, \frac{10}{10^{-5} + (|z| / 5)^2 + (|z| / 200)^6}\right)\right)$$
- **Resolve Shader**:
  $$C_{final} = \frac{\text{Accum}_{rgb}}{\max(\text{Accum}_a, 10^{-5})} \cdot (1 - \text{Reveal}) + C_{bg} \cdot \text{Reveal}$$

### 3.3 Why Pixel Parity Remains UNVERIFIED
While geometric transforms and layer composition order match native Korangar with 0 mismatches across all 2,688 prepared layers:
1. **GPU Precision Variations**: Vulkan half-float (`Rgba16Float`) accumulation and shader interpolation vary across physical GPU architectures (AMD, Intel, NVIDIA) and driver implementations.
2. **Color Clamping & Weighting Differences**: At low alpha or overlapping semi-transparent boundaries, WBOIT depth-weighted blending produces subtle subpixel tint differences compared to CPU integer alpha-over.
3. **Billboard View Orientation**: In full 3D gameplay, billboard orientation responds to dynamic camera pitch and terrain elevation, which has no direct analog in a 2D asset previewer.

Therefore, `native_pixel_parity` is formally designated as `UNVERIFIED`. RO Sprite Forge never falsely claims universal bitwise GPU pixel equivalence.

---

## 4. Empirical Parity Evidence

Evidence evaluated by `scripts/verify_preview_parity.py` and regression test `tests/private_fixture_hooks/test_parity_evidence.py` against `docs/evidence/rsf6/native-report.json.gz`:

1. **Novice Multipart Body & Head Anchors**:
   - 104 action slots evaluated.
   - 456 motion occurrences evaluated.
   - 912 visible prepared layers evaluated.
   - **Mismatches: 0**. Every head offset matches Korangar native billboard placement with 0-pixel delta.

2. **Orc Skeleton Multilayer & Complex Actions**:
   - 40 action slots evaluated.
   - 512 motion occurrences evaluated.
   - 1,776 visible prepared layers evaluated.
   - **Mismatches: 0**. Layer ordering, angle rotation, and mirror flags match native Korangar across all frames, including Action 32 (Death South, 22 frames with up to 12 layers per frame, total 176 layers).

3. **Timeline Stepping & Slot Resolution**:
   - 160 native test cases evaluated (Idle, Walk, Attack, Hurt, Die across 8 camera orientations).
   - 1,664 frame selections verified.
   - Direction & camera view formula $((direction + camera) \ \& \ 7)$ and slot calculation match 100%.

---

## 5. Invalidation Rules

Pre-build preview parity evidence is bound to canonical SHA-256 hashes of inputs:
1. **Source Asset Modification**: If the SHA-256 of any underlying ACT or SPR changes, any existing preview parity report for that actor is automatically invalidated.
2. **Semantics Modification**: Changes to `RENDERER_VERSION`, `GEOMETRY_VERSION`, `TIMING_VERSION`, or `PARITY_VERSION` invalidate prior parity reports.
3. **Composition Rule Changes**: Any alteration of anchor offset math, layer ordering, or coordinate origin calculation invalidates parity status.
4. **Rebuild Invariance**: Re-running the preview pipeline against identical input hashes produces bit-for-bit identical reports without invalidating prior verification.

---

## 6. Authority & Status Boundaries

- **Algorithmic Validation**: Structural and geometric parity proofs are objective mathematical verifications (`geometry: "VERIFIED"`, `technical_difference_only: true`).
- **Human Visual Authority**: The human operator retains sole authority over visual quality, character style, animation choreography, and aesthetic suitability. Algorithmic PASS does not imply operator visual approval (`artistic_approval: "UNVERIFIED"`).
- **Milestone Parity State**: RSF-14 certifies that preview diagnostics provide faithful structural guidance while explicitly recording known GPU blending differences (`overall: "PARTIAL"`).

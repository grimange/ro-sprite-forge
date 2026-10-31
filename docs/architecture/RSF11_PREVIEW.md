# RSF-11 — [M2] Order-Preserving Multilayer Preview Compositor

## 1. Executive Summary

RO Sprite Forge is a requirements-first animation planner and deterministic asset compiler. Prior to compiling new artwork into binary ACT/SPR containers, human operators must be able to inspect actual rendered frames faithfully representing imported and assigned sprite layers.

**RSF-11** implements the M2 core preview engine: a portable, pure-Python 2D multilayer compositor that accurately reproduces Ragnarok ACT 2.4 and SPR 2.1 frame composition.

Key achievements:
- **Order-Preserving Composition:** Layers are composited in exact sequential ACT occurrence order without premature flattening.
- **Affine Transformation Pipeline:** Preserves horizontal mirroring, independent non-uniform scale, integer rotation angles, and per-channel 32-bit color tint and alpha modulation.
- **Integer-Center Registration:** Enforces classic Ragnarok and Korangar pixel-center placement `((width - 1) // 2, (height - 1) // 2)`.
- **Multipart Anchor Alignment:** Supports composite actors (e.g. Novice body + head) through anchor offset shifting `(parent_anchor - child_anchor)`.
- **Pool & Byte Separation:** Source indexed sprites, palettes, and truecolor pools remain strictly separated and untouched; preview rendering never mutates source representations or silently converts indexed pools to RGBA.
- **Safe Clipping Policy:** Dynamically crops layers intersecting canvas boundaries, preventing position exceptions while reporting boundary clipping.
- **Formal Fidelity Contract:** Output adheres to versioned Draft 2020-12 schema `rsf.preview-result/v1`, classifying results as `VERIFIED`, `PARTIAL`, `UNVERIFIED`, or `INVALID`.

---

## 2. Non-Negotiable Core Invariants

1. **Human Visual Authority:** The preview engine does NOT score visual quality, grade artistic beauty, repair anatomy, or automatically approve animation. Rendering is purely mathematical presentation for human review.
2. **Untouched Source Bytes:** Reading an SPR document for preview never alters `IndexedImage.pixels`, `palette`, or `RgbaImage.rgba`. Unchanged assets remain 100% byte-exact upon compilation.
3. **No Hidden Flattening:** Multilayer motions (such as Orc Skeleton's 12-layer death sequence) are rendered layer-by-layer; layer metadata, bounds, and ordering are explicitly enumerated in the output report.
4. **Deterministic Binary Output:** For identical inputs, preview PNG bytes and SHA-256 hashes are bitwise identical across runs and environments.

---

## 3. Transformation Pipeline & Placement Geometry

### 3.1 Integer-Center Registration
In classic Ragnarok ACT resources and the pinned Korangar native entity renderer, sprite clip offsets `(clip.x, clip.y)` are defined relative to an integer-centered origin:

$$\text{shift}_x = - \lfloor \frac{\text{width} - 1}{2} \rfloor, \quad \text{shift}_y = - \lfloor \frac{\text{height} - 1}{2} \rfloor$$

$$\text{canvas}_x = \text{origin}_x + \text{clip}_x + \text{shift}_{\text{anchor}, x} + \text{shift}_x$$
$$\text{canvas}_y = \text{origin}_y + \text{clip}_y + \text{shift}_{\text{anchor}, y} + \text{shift}_y$$

This integer-division formula matches Korangar's native loader:
`vector2_i32_to_f32(-((frame_part.size - Vector2::new(1, 1)) / 2))`

### 3.2 Affine Transformations per Layer
Each visible clip (`sprite >= 0`) executes transformations in exact sequence:
1. **Mirroring:** If `clip.mirror == 1`, flip horizontally (`Image.Transpose.FLIP_LEFT_RIGHT`). Negative `scale_x` or `scale_y` also triggers respective directional flips.
2. **Scaling:** Scaled dimensions are computed using ceiling rounding:
   $$\text{target}_w = \max(1, \lceil \text{width} \cdot |\text{scale}_x| \rceil), \quad \text{target}_h = \max(1, \lceil \text{height} \cdot |\text{scale}_y| \rceil)$$
   Scaled using bilinear resampling (or nearest where configured).
3. **Color Modulation & Tint:** ACT color is a 32-bit unsigned integer unpacked as:
   $$R_{\text{tint}} = \text{color} \& \text{0xFF}, \quad G_{\text{tint}} = (\text{color} \gg 8) \& \text{0xFF}$$
   $$B_{\text{tint}} = (\text{color} \gg 16) \& \text{0xFF}, \quad A_{\text{tint}} = (\text{color} \gg 24) \& \text{0xFF}$$
   Each channel is modulated via integer lookup tables:
   $$C' = \lfloor \frac{C \cdot C_{\text{tint}}}{255} \rfloor$$
4. **Rotation:** ACT stores angles in degrees (0..359). In screen space where $+Y$ points downward, positive ACT angle rotates clockwise on screen. In PIL, this corresponds to:
   $$\text{pil\_angle} = - (\text{angle} \pmod{360})$$
   Cardinal angles (90°, 180°, 270°) utilize lossless transpose operations; arbitrary angles use center-expanded rotation with bilinear filtering.

### 3.3 Multipart Anchor Offset
For composite actors (e.g. Player character consisting of body part 0 and head part 1):
- Part 0 (body) defines anchor point $A_{\text{body}} = (x_b, y_b)$.
- Part 1 (head) defines anchor point $A_{\text{head}} = (x_h, y_h)$.
- The child attachment shift applied to all child clips is:
  $$\Delta_{\text{anchor}} = (x_b - x_h, y_b - y_h)$$

---

## 4. Schema Contract: `rsf.preview-result/v1`

Preview results are exported as canonical JSON validated against Draft 2020-12 schema `src/ro_sprite_forge/schemas/preview-result-v1.json`.

Essential fields:
- `schema`: `"rsf.preview-result/v1"`
- `renderer_version`: `"1.0.0"`
- `fidelity`: `"VERIFIED" | "PARTIAL" | "UNVERIFIED" | "INVALID"`
- `dimensions`: `{"width": int, "height": int}`
- `origin`: `{"x": int, "y": int}`
- `bounds`: `{"min_x", "min_y", "max_x", "max_y", "width", "height"}` or `null`
- `layers_rendered`: Count of visible layers composited
- `layers`: Array of per-layer records detailing sprite index, pool, offset, scale, angle, color, rendered size, and clipping
- `unsupported_semantics`: List of flagged features outside supported scope
- `errors`: Diagnostic error messages
- `png_sha256`: SHA-256 hex digest of deterministic PNG bytes
- `source_hashes`: Hash map of input ACT and SPR resources

---

## 5. CLI Interface

The preview engine is exposed via `ro-sprite-forge preview`:

```bash
# Render single frame preview to PNG and canonical JSON report
ro-sprite-forge preview \
  --act private_fixtures/orc_skeleton.act \
  --spr private_fixtures/orc_skeleton.spr \
  --action 32 --frame 21 \
  --output orc_death_21.png \
  --json orc_death_21.json

# Render multipart Novice body + head with anchor alignment
ro-sprite-forge preview \
  --act reference/novice_male_body.act \
  --spr reference/novice_male_body.spr \
  --head-act reference/novice_male_head.act \
  --head-spr reference/novice_male_head.spr \
  --action 0 --frame 0 \
  --output novice_idle.png \
  --stdout-json
```

---

## 6. Verification and Acceptance Matrix

| Verification Vector | Implementation | Status |
|---|---|---|
| Synthetic 20 Pixel Scenarios | `tests/test_preview.py` | PASS (20/20) |
| Novice Body + Head Anchor Composition | `tests/private_fixture_hooks/test_preview_fixtures.py` | PASS |
| Orc Skeleton 12-Layer Death Motion | `tests/private_fixture_hooks/test_preview_fixtures.py` | PASS |
| Native RSF-6 Structural Parity | `tests/private_fixture_hooks/test_preview_fixtures.py` | PASS |
| Source Byte Preservation | `tests/test_preservation.py` | PASS |
| Deterministic PNG Serialization | Identical SHA-256 verification | PASS |
| JSON Schema Draft 2020-12 | `src/ro_sprite_forge/schemas/preview-result-v1.json` | PASS |
| Full Public Test Suite | `tests/test_*.py` | PASS (192/192) |
| Full Private Test Suite | `tests/private_fixture_hooks/test_*.py` | PASS (22/22) |

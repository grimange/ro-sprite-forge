# RSF-21 Architecture: Explicit Non-Destructive Image Transformation Recipes

## 1. Overview & Core Invariants

RSF-21 implements reversible, non-destructive image transformation recipes for staged candidates in RO Sprite Forge (Milestone M4).

### Key Architectural Invariants
1. **Operator-Controlled Transformations**: Every transform operation is explicitly requested by the human operator. There is zero automated background removal, zero AI edge reconstruction, zero pose inference, and zero automatic aesthetic filtering.
2. **Strict Immutability of Source Blobs**: Original source bytes remain bit-for-bit unchanged in immutable content-addressed storage (`blobs/{sha256}`).
3. **Reversible Recipe Representation**: Transformations are declared as versioned, serializable recipes (`rsf.image-recipe/v1`) capturing the exact source digest, ordered operations, and parameters.
4. **Deterministic Derived Staging**: Executing a recipe yields a deterministically encoded PNG blob in `blobs/{derived_sha256}`. Re-executing the identical recipe on identical source bytes produces the exact same hash.
5. **Full Loss & Mutation Disclosure**: Whenever operations discard information (downscaling, color quantization, cropping, background keying, discarding palette indices), the exact loss categories are recorded in `loss_report`.
6. **Scoped Review Invalidation**: Derived candidates are never automatically approved. Assigning a derived image to an actor layer modifies that layer's composition digest, immediately invalidating any prior visual approval for that occurrence (`STALE`), while leaving unrelated approved layers untouched.

---

## 2. Transformation Operations & Semantics

The transformation engine (`ro_sprite_forge.core.transformations`) supports the following discrete operation classes:

| Operation | Parameters | Description | Loss Disclosures |
|---|---|---|---|
| `crop` | `x`, `y`, `width`, `height` | Extracts a rectangular sub-region within image bounds. | `CROPPED_DISCARDED_PIXELS` (if smaller than canvas) |
| `flip` | `direction`: `'horizontal'` \| `'vertical'` | Flips the image along the horizontal or vertical axis. | None (lossless isometric reflection) |
| `scale` | `width`, `height`, `filter`: `'nearest'` \| `'bilinear'` \| `'bicubic'` \| `'box'` | Rescales dimensions. Pixel art uses `'nearest'` to preserve discrete pixel blocks. | `DOWNSCALED_DISCARDED_PIXELS`, `INTERPOLATED_RESAMPLING` (if non-nearest) |
| `offset` | `offset_x`, `offset_y`, `overflow`: `'clip'` \| `'expand'` | Translates pixels within or onto an expanded transparent canvas. | `CANVAS_CLIPPED_PIXELS` (if clipped) |
| `matte_key` | `color`: `[r, g, b]`, `tolerance`: `0..255`, `replacement_alpha`: `0..255` | Converts color matte (e.g. magenta `[255, 0, 255]`) into transparent alpha. | `ALPHA_CHANNEL_KEYED` |
| `color_mode` | `target_mode`: `'RGBA'` \| `'P'`, `dither`: `bool` | Converts image mode. Mode `'P'` to `'RGBA'` or vice versa. | `PALETTE_INDICES_DISCARDED` (P $\to$ RGBA), `COLOR_QUANTIZATION_LOSSY` (RGBA $\to$ P) |

### Order-Sensitivity
Operations are executed in strictly sequential order. Because 2D image affine transformations and crops do not commute in general, `Crop -> Flip` produces different pixels and a different cryptographic digest than `Flip -> Crop`. The canonical recipe digest (`recipe_sha256`) includes the ordered array of operations.

---

## 3. Schema & Canonical Digests

### Recipe Schema (`rsf.image-recipe/v1`)
Stored in `project.recipes`:
```json
{
  "schema": "rsf.image-recipe/v1",
  "id": "walk-crop-flip",
  "name": "Walk Frame Crop & Flip",
  "source_sha256": "3a7b...",
  "operations": [
    { "op": "crop", "x": 0, "y": 0, "width": 40, "height": 40 },
    { "op": "flip", "direction": "horizontal" }
  ],
  "canonical_sha256": "f901..."
}
```

### Transformation Record (`rsf.transformation-record/v1`)
Embedded in the transformation execution result and cataloged in `project.sources[derived_sha256]`:
```json
{
  "schema": "rsf.transformation-record/v1",
  "recipe": { ... },
  "source_sha256": "3a7b...",
  "derived_sha256": "81ce...",
  "recipe_sha256": "f901...",
  "metadata": {
    "input_dimensions": [64, 64],
    "output_dimensions": [40, 40],
    "input_mode": "RGBA",
    "output_mode": "RGBA",
    "transparency_kind": "ALPHA_CHANNEL",
    "has_transparency": true,
    "loss_report": ["CROPPED_DISCARDED_PIXELS"]
  }
}
```

---

## 4. Operator Workbench & Workflow Integration

1. **Inspection Before Staging**: The operator selects an input source, defines operations, and clicks **Inspect before / after**. The service computes an in-memory preview via `POST /api/projects/{id}/transform-preview` showing side-by-side comparison, technical facts, and loss disclosures.
2. **Explicit Staging**: The operator clicks **Stage derived candidate**. The service executes the recipe, stores the resulting PNG blob in `blobs/`, registers the derived candidate in `project.sources`, and preserves the recipe in `project.recipes`.
3. **Optional Assignment**: If a destination requirement ID is specified, the derived blob is mapped directly to that layer requirement.
4. **Approval Staleness**: If an assigned source is replaced with a derived candidate, the RSF-18 review evaluator marks the existing review for that requirement as `STALE` (`COMPOSITION_CHANGED_OR_REQUIREMENT_UNAVAILABLE`), requiring explicit operator re-inspection. Unrelated requirements remain untouched.

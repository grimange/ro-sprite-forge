# RSF-19 Deterministic PNG-Sequence Ingestion and Staging

RO Sprite Forge M4 ingestion imports ordered PNG sequences and single PNG frames into
content-addressed project blob storage without automatic assignment, inferred choreography,
pose generation, or silent visual approval.

## Technical Validation and Boundaries

The ingestion engine in `core/ingestion.py` enforces strict format and security limits:
- **PNG Magic Signature**: verifies `\x89PNG\r\n\x1a\n`. Non-PNG inputs are rejected with `INVALID_PNG_SIGNATURE`.
- **Dimensions & Budget**: width and height must each be $\le 4096$, and total pixels must be $\le 16$ megapixels ($16,777,216$ pixels). Exceeding limits raises `DIMENSION_EXCEEDED` or `DECODE_BUDGET_EXCEEDED`.
- **Payload Limits**: bounded to $32\text{ MiB}$ per image blob (`PAYLOAD_TOO_LARGE`).
- **Decompression Bomb Defense**: limits decompression allocations to prevent denial-of-service bombs (`DECOMPRESSION_BOMB`).
- **Stream Verification**: Pillow `verify()` checks internal chunk consistency before pixel parsing. Truncated or corrupted streams raise `CORRUPTED_PNG_DATA`.
- **Transparency Classification**: RGBA, LA, P, RGB, and L modes are analyzed into orthogonal categories:
  - `OPAQUE`: all pixels fully opaque (alpha = 255).
  - `FULLY_TRANSPARENT`: all pixels transparent (alpha = 0).
  - `PARTIALLY_TRANSPARENT`: mixture of alpha values or palette color-key transparency.

## Sequence Ordering and Identity

- Frames are identified by explicit zero-based contiguous ordinals: $0, 1, \dots, N-1$.
- Sequences with duplicate ordinals raise `DUPLICATE_FRAME_ORDINAL`.
- Gaps in ordinals raise `FRAME_ORDINAL_GAP`.
- Negative or non-integer ordinals raise `INVALID_FRAME_ORDINAL`.
- Empty sequences raise `EMPTY_SEQUENCE`; sequences $> 1024$ frames raise `SEQUENCE_TOO_LARGE`.
- **Canonical Sequence Digest**:
  $$\text{sequence\_sha256} = \text{digest}(\text{canonical\_bytes}([\text{frame}[\text{sha256}] \text{ for frame in sorted\_frames}]))$$
  Reordering frames strictly alters the sequence SHA-256 while leaving each individual source blob hash unchanged.
- Content-addressed idempotency: identical frame contents used across multiple ordinals or sequences are stored once under their canonical SHA-256 blob path.

## Workbench & Ledger Integration

- Staged candidates appear in `manifest["sources"]` and `source_catalog(root, manifest)` with:
  - `kind = "IMAGE"`
  - `origin = "AUTHORED"`
  - `availability = "AVAILABLE"`, `validation = "VALID"`
- Technical metadata (`width`, `height`, `mode`, `transparency_kind`, `has_transparency`, `sequence_id`, `ordinal`) is preserved.
- Staged sequences are recorded under `manifest["sequences"]` with schema `rsf.sequence/v1`.
- **Zero Auto-Assignment**: Ingestion leaves `manifest["ledger"]["assignments"]` untouched.
- **Zero Auto-Approval**: Ingestion leaves `manifest["review_events"]` untouched.
- The operator selects frames from the source tray to assign them via the existing assignment workflow (`#art-source` $\to$ `#assign-selected`).

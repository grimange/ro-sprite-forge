# RSF-24 image pool and representation contract

Audited runtime: Korangar revision `3f3d88a583203f09d079712f43343c1041258ffd`,
`korangar/src/loaders/animation/mod.rs` lines 85–103, and
`korangar/src/loaders/sprite/mod.rs` lines 98–169, inspected using `git show`.
No external source changed. Plan SHA-256 matches the operator's baseline.

SPR 2.1: SP / minor1 major2 / uint16 indexed count / uint16 truecolor count;
indexed entries first (uint16 width, height, encoded length, zero-run RLE),
then truecolor entries (uint16 width, height, bottom-up ABGR bytes), then 1024 palette bytes.
The audited Python and independent Rust readers normalize truecolor to top-down RGBA.
Indexed zero normalizes to transparent black; other indices use palette RGB and alpha255.
Raw palette bytes, including unused fourth bytes, remain preserved.

ACT 2.4 layer `pool` is 0=indexed or 1=truecolor and `sprite` is **pool-relative**.
Sprite -1 is hidden. Runtime concatenates indexed textures then truecolor textures:
texture index = sprite + (indexed count if pool==1 else 0).
Appending indexed entries shifts truecolor texture positions, while their ACT integers
and effective pool-local identity remain unchanged. Appending truecolor is neutral for
existing indices. Original pool entries keep order, including duplicates and unused entries.
No removal/compaction or deduplication of original entries occurs.

Occurrence identity is numeric slot/frame/raw clip ordinal; requirements supply semantic
action/view and visible layer ordinal separately. Complete before/after evidence includes
pool/index identity, runtime texture position, decoded content digest and metadata digest.
Identical pixels do not imply identical stored image identity.

Existing policy names are retained. Omitted core/CLI/API policy and the workbench default
use `preserve_pool`; RGBA requires explicit selection:

- `preserve_pool`: replacement retains the selected original pool. Indexed replacements
  require exact palette RGB and binary transparency; truecolor retains all RGBA bytes.
- `explicit_rgba`: opt-in replacement in truecolor. Indexed consumers report loss of the
  replacement's palette/index representation; original palette and entries remain retained.
- `indexed_exact`: exact mapping to the existing palette, smallest nonzero index for
  duplicate opaque RGB, zero for transparent black. Reject absent RGB, fractional alpha,
  and RGB hidden beneath zero alpha. No quantization, palette edits or silent loss.

Policies apply per compile request, not per pixel or inferred preview representation.
`preserve_pool` supports different output representations in one mixed-pool compilation.
Writer semantics version 1.1.0 identifies these changes. Existing 1.0.0 project records
remain readable. RLE uses the existing canonical encoder only for changed/new images.
Unchanged images preserve raw RLE including nonminimal zero runs.

Replacement order is sorted (slot, frame, clip ordinal). Exact encoded-content reuse is
restricted to replacement entries in the same pool. Auto may replace an unshared entry
in place; shared entries append unless every consumer is selected with identical content.
`always_append` forces copy-on-write; `in_place_only` rejects unsafe sharing/conversion.
Only selected ACT consumers change references. Decode-after-write checks every visible
consumer and all supported ACT metadata, timing, anchors and layer order.

Pre-write plans validate through the same compiler in memory without publishing resources;
unsupported conversions become blockers. Plans include the exact remapping and replacements.
This intentionally avoids a second planner or encoder. Compilation always revalidates inputs.

Rust independently decodes pool counts, ACT references, palette, index data and RGBA and
rejects invalid pool-local indices. It does not emit a runtime texture-selection report.
The public golden matrix independently selects from Rust's ordered decoded images using
the pinned texture formula and compares selected PNG pixels plus complete unaffected mapping.
This is structural/pixel evidence; native playback remains UNVERIFIED.

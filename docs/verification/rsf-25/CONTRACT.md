# RSF-25 canonical build and export contract

The existing compiler, ACT 2.4 writer and SPR 2.1 writer remain authoritative.
Writer semantics advance from 1.1.0 to 1.2.0; legacy 1.0/1.1 manifests remain readable.
The versioned compilation-manifest/v1 schema requires the new build/status fields only
for 1.2.0. No image-pool or binary-format ordering is changed.

## Canonical inputs and ordering

Canonical JSON uses sorted object keys, compact ASCII encoding, finite Python numeric
representations and one terminal LF. Arrays with semantic order retain that order.
Resolved requirements use action ID, part, view, frame and declared layer ordinal;
ACT serialization always retains numeric slot order, motion order, **all ordered clips**
(including hidden clips), event order and attachment-anchor order. Replacement planning
sorts by numeric slot, frame and physical clip ordinal. SPR retains original indexed
entries, then original truecolor entries, with canonical occurrence appends within each
pool. Exact replacement reuse stays within its representation pool. Original duplicate
and unused entries retain their identities. See accepted RSF-24 SEMANTICS.md for pool
resolution and representation policies.

ACT is little endian: header slot count uint16, counts uint32, eight int32 bounds;
clips use `iiiIIffiI`, anchors `IiiI`, event references int32, raw event records 40 bytes,
delays float32. Scale/delay encoding is IEEE 754 binary32, nearest with ties to even;
there is no decimal rounding. Finite/range/positive-delay validation remains in the
writer. Existing decoded float32 values round-trip, including signed zero in scales.
SPR uses uint16 counts/dimensions/RLE lengths, unchanged raw indexed zero-run RLE,
the original 1024 palette bytes, or bottom-up ABGR8 truecolor payloads. Indexed exact
replacement uses existing palette indices (first exact compatible match); index zero
means transparent black, and nonzero indices mean opaque palette RGB. No quantization,
palette optimization, color management, gamma conversion or resampling is introduced.

Modified compilation requires Pillow **12.1.1**. The build pins the observed CPython
implementation/version and zlib build/runtime versions, the fixed decoder/encoder,
palette/color-space/numeric/ordering semantics and file-level implementation SHA-256s.
Different toolchains receive different build identities. Staged recipes are never
executed again; the final staged source hash is consumed, and existing derived-source
provenance stays in the compilation manifest. Compiler ledger mirror operations remain
explicit. Preserve mode needs no Pillow and retains byte-exact no-op behavior.

## Identity, composition and evidence

`manifest.build` is sealed `rsf.canonical-build/v1`. `build.input_sha256` hashes only
canonical inputs: original body/head resource hashes, target/profile/requirements
identity, ledger revision, selected pre-build composition members, output policy and
writer/toolchain identities. The approved aggregate composition digest combines existing
RSF-18 operator composition bases and RSF-9 assignment bases; it exists independently of
future output hashes. Those bases retain the accepted contract's exact declaration
semantics. Physical locations of input files, output names, invocation IDs, project IDs,
wall time, hostname, random values and verification/native evidence are not added to
build inputs. Declared contract identities remain semantic inputs; relocating files
does not rewrite their declarations or their approvals.

The sealed build also records remapping and actual output hashes. It is published as
`build-manifest.json`, byte-identical across equivalent builds. The outer existing
`compilation-manifest.json` links it to invocation ID, resource filenames and Rust/native
verification results. Its seal can therefore differ across invocations with different
names or evidence; it is not the reproducibility key. No native data feeds build identity.

Reviewed ledger projections must match freshly resolved assignment/composition/source
observations. Inherited topology must reference the actual original ACT/SPR hashes;
changed original registration/timing cannot consume the old approved basis. All selected
PNG bytes are hash-checked and decoded even on a cache hit. Equivalent rebuilds do not
create or invalidate human approval. Tests use synthetic approval records only.

## Export gates

Production requires exact specified topology, COMPLETE_FOR_FULL_PROFILE coverage,
approved valid authored required assignments, all required occurrences selected in the
supported compiled part, and successful decoding, conversion and preservation checks.
Targets requiring multiple parts cannot claim production through a single-part compile.
Optional selected occurrences receive the same source/review/structure checks.
Scoped completeness remains distinct from full-profile completeness.

Production also requires resource-bound inherited topology for every selected occurrence.
Explicit/per-frame/template role declarations do not bind the original ACT registration,
timing and anchors in the accepted approval contract; they fail with
UNBOUND_PRODUCTION_COMPOSITION even when full-profile artwork coverage is complete.
They remain supported for bounded diagnostics. This compiler does not invent approval
of preserved metadata or extend the operator review contract automatically.

Bounded output has `status.export_label=PARTIAL_DIAGNOSTIC`, authorization/export flags
false and an explicit PARTIAL_DIAGNOSTIC.txt bundle marker. Preserve mode is labeled
PRESERVED_REFERENCE. Production is labeled PRODUCTION only after its gates pass; this
means complete approved compilation, never native rendering acceptance. Native Korangar
remains UNVERIFIED, and no milestone or subjective artwork approval is granted by builds.
The CLI requires `--output-dir` for production; legacy separate-file output is diagnostic.

## Atomic publication and cache

Publication validates the sealed manifest, body/head pair presence, lengths, hashes and
decoded inventories before filesystem mutation. A complete sibling staging directory is
written and fsynced; Linux `renameat2(RENAME_NOREPLACE)` commits it atomically. Parent
directory fsync follows. Existing nonempty directories and symlink destinations are
rejected. An existing empty output directory may be removed immediately before commit;
concurrent writers cannot overwrite one another. No original or staged artwork is edited.
Unsupported atomic primitives fail explicitly rather than falling back to file-by-file
production publication. A killed process can leave a hidden `.rsf-staging-*` directory;
it cannot leave a partial final bundle. No automatic destructive cleanup is performed.

Optional `compile --cache-dir DIR --output-dir OUT` stores immutable verified bundles
under `DIR/<build.input_sha256>`. Cache entries contain only fixed resource names and the
canonical build manifest. A hit compares the complete file set, types, lengths and bytes
against the newly verified result; corruption fails closed and is never overwritten.
The cache is a verified artifact store, not a shortcut around current approvals, source
validation, compilation or requested oracle checks. Cache and final output are separate
atomic commits: output failure may leave a complete valid cache entry, never partial
production output. Machine-specific logs stay in this verification packet.

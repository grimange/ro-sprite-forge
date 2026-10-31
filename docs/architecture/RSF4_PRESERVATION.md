# RSF-4 preservation and verification contract

`roundtrip --act INPUT --spr INPUT --output-act NEW --output-spr NEW`
validates the supported ACT 2.4 / SPR 2.1 resource pair, then publishes original
bytes. `--mode preserve` is the default. `--mode act-semantic` separately runs the
ACT writer on the decoded document; SPR still retains its original bytes.
`verify --act INPUT --spr INPUT` performs the same structural, reference and Python
semantic checks without publishing files. Both commands print canonical
`rsf.verification/v1` JSON to stdout. No timestamps or paths enter its hash.
The legacy `verify --project DIR --scope full|declared` remains NOT_IMPLEMENTED;
RSF-4 has no project authoring/assignment contract. Conversions and pool remapping
are unsupported and rejected; the existing low-level truecolor writer is not an
indexed writer and is never used by preservation.

Each resource identity is its input SHA-256. The report binds the ACT and SPR
hashes together and records output hashes. A caller must compare those identities
with its intended source pair; structurally compatible but unintended art cannot
be identified from binary structure alone. Pair validation uses the existing
inventory engine, including pool-local image references and event references.
Unused stored identities, original palette, raw indexed RLE, pool order, and all
ACT bytes survive pass-through. No composition or PNG is involved.

The ACT serializer validates the complete supported dictionary before encoding:
header reserved bytes, action/motion/layer order, bounds, all nine layer fields,
raw 40-byte events, all four anchor fields, and per-action delays. Unknown keys
and malformed edits fail explicitly instead of being silently dropped. Counts,
integer ranges, finite float32 values, positive representable delays and event
references are bounded. A standalone ACT writer cannot check image references
against an absent SPR; paired verification performs that check.

For supported parsed finite float32 records, ACT serialization is byte-exact;
no known supported semantic-preserving binary difference is required. Caller
supplied Python floats are rounded to float32 during encoding, so arbitrary
Python precision is not a byte-preservation promise. Nonfinite scales/delays and
nonpositive/underflowing delays are outside paired semantic support. Raw parsing
and validated paired operations have different contracts. There is no implicit
indexed-to-RGBA conversion, nor a decoded-pixel equivalence claim for conversion.

The verification report's PASS covers its declared Python structural/preservation
checks. `independent_binary_tests=NOT_RUN` explicitly means the CLI did not execute
the independent synthetic golden-layout suite; the durable task evidence records
that separate suite. Rust is NOT_RUN and native is UNVERIFIED. No artwork or human
visual approval is inferred.

Inputs are read with the existing 128 MiB adapter limit. Outputs must be distinct,
new paths with existing parents; existing files and symlinks are never replaced.
All output bytes are staged before publishing, each file appears atomically, and
both are read back before success. Exceptions remove outputs created by this
operation without removing pre-existing files. Two arbitrary filesystem paths
cannot form a crash-atomic transaction: process termination/power loss during
publication can leave an incomplete pair, with no success report. This is not a
production build/approval protocol.

`tests/test_preservation.py` independently constructs a 424-byte two-action,
three-motion, multilayer ACT with mixed pools and nonzero opaque records. Expected
semantics are supplied separately from both codecs. Eighteen single-field edits
are checked with literal byte offsets and `struct.pack_into`; complete byte
comparison proves unrelated bytes remain unchanged. An inserted anchor tests a
layout-changing edit against independently spliced bytes. Every truncation is
rejected. Original indexed, mixed and truecolor SPR bytes, including nonzero
palettes and unused identities, are tested separately from ACT serialization.

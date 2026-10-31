# RSF-3 finite inventory and target contracts

These M0 contracts implement plan v1.1 §§3.1–3.4, 4.3–4.4 and M0.
All frame/layer ordinals and ACT slots are zero-based. The four authorities remain
separate: observed resources, frozen runtime semantics, declared target, assignments.
Assignments are not implemented here; original resource images never count as approved art.

## Canonical reports

`rsf.inventory/v1`, `rsf.runtime-profile/v1`, `rsf.target/v1` and
`rsf.requirements/v1` identify the contract versions. Inventory and requirements
reports embed `canonical_sha256`: SHA-256 of the report without that field,
serialized as ASCII-escaped UTF-8 JSON, sorted object keys, compact separators,
finite numbers and a final LF. The complete file has a separate SHA-256.
Floats use Python's shortest round-tripping representation; source ACT floats are
decoded binary32 values, not rounded display strings. Source hashes cover exact bytes.
No paths, times, random IDs or local checkout identities enter reports.

Inventory sequences follow numeric ACT slots, frame/layer ordinals and numeric
pool/index order. Content classes sort by hash. Requirements normalize action/view
declaration ordering, while ordered layers retain their declared order.
Occurrence IDs encode actor/profile/part/action/numeric slot/view/frame/layer.
Namespaces accept 1–80 ASCII letters, digits, dots, underscores and hyphens.
The same canonical source and namespace produce the same IDs after renaming files.
Body and head are separate inventories; their frame totals must not be added and
presented as the body's audited occurrence count.

The inventory records all raw clip fields (position, scale, angle, mirror, tint,
pool and image index), eight raw bounds integers, anchors and opaque registration
fields, events as original 40-byte hex records, reserved bytes and raw delays.
It makes no new geometric interpretation of opaque bounds. Sprite -1 is an
invisible layer occurrence, retained in order but excluded from visible references.
Invalid visible references, event indices, nonfinite scales or nonpositive/nonfinite
delays fail with INVALID_INPUT. A resource slot count need not be a multiple of eight;
`numeric_action_groups` includes a partial final group and is not a runtime support claim.

Image identity is pool/index within actor/profile/part, independent of content.
`decoded_content_sha256` hashes `b"rsf.decoded-rgba/v1\0"`, then width and height as
two unsigned little-endian 32-bit integers, then top-down RGBA bytes. Indexed zero
becomes transparent black; other palette entries use RGB with alpha 255. Truecolor
retains exact decoded RGBA, including hidden RGB under alpha zero. Dimensions matter;
no perceptual similarity or inferred mirroring is used. Raw palette and representation
hashes remain separate. Classes include unused images; referenced-content totals do not.

`plan` requires the exact frozen profile embedded in the input inventory, including
source hashes and profile digest. The seal checks report integrity, not authenticity;
reports are local operator inputs, not signed security credentials.

## Bounded target

Example `target.json`, explicitly declaring eight Walk views with six body layers each:

```json
{
  "schema": "rsf.target/v1",
  "actor": "new-actor",
  "part": "body",
  "scope": "scoped",
  "actions": [
    {"action":"Walk","requirement":"required","views":[
      {"view":0,"frame_count":6,"topology":{"kind":"explicit","layers":["body"]}},
      {"view":1,"frame_count":6,"topology":{"kind":"explicit","layers":["body"]}},
      {"view":2,"frame_count":6,"topology":{"kind":"explicit","layers":["body"]}},
      {"view":3,"frame_count":6,"topology":{"kind":"explicit","layers":["body"]}},
      {"view":4,"frame_count":6,"topology":{"kind":"explicit","layers":["body"]}},
      {"view":5,"frame_count":6,"topology":{"kind":"explicit","layers":["body"]}},
      {"view":6,"frame_count":6,"topology":{"kind":"explicit","layers":["body"]}},
      {"view":7,"frame_count":6,"topology":{"kind":"explicit","layers":["body"]}}
    ]}
  ]
}
```

This yields 48 required frames and 48 layer occurrences. `layers:["body","head"]`
yields 96 ordered layers. This is a synthetic work order, not a job production quota.
For changing topology, replace `layers` with `frames`, an array of ordered role
arrays whose length equals `frame_count`. Explicit empty role arrays declare blank
frames; an absent topology never means one layer.

For explicit inheritance, use `{"kind":"inherited","inventory_sha256":"<canonical_sha256>","slot":8}`
on Walk view 0, with an independently declared matching `frame_count`. Inheritance
uses visible source layers in original order, retains original ordinal in generated
role names and records the exact inventory hash and ACT slot. It never silently
inherits frame counts, image assignments or human approval. A different part may be
used as a template only by this explicit hash/slot declaration.

Actions have `requirement` required, optional or out_of_scope. Views are unique
integers 0–7. Out-of-scope actions may list views but cannot declare frame/topology
work. Optional work is counted separately. Missing frame counts emit
UNDERSPECIFIED_FRAME_COUNT; missing topology emits UNDERSPECIFIED_LAYER_TOPOLOGY.
Provisional reports retain known counts but do not expand an exact work order.
The status `work_order:EXACT` describes specification only. Unknown semantic names
retain an explicitly UNVERIFIED numeric slot/runtime mapping; no gameplay action is added.

Limits: 128 actions, eight views per action, 4096 frames per action/view,
1024 roles per frame, 65,536 total frames and 262,144 total layers. Unknown fields,
duplicate actions/views/roles, JSON keys, NaN/Infinity and mismatched hashes fail closed.
Each file read is bounded to 128 MiB. Existing RSF-2 codec allocation limits apply.

`full_profile_specified` requires full scope, exact declarations, and every frozen
profile action/view pair. It does not depend on whether the original files happen
to contain those slots. A Walk-only target stays scoped even when all its declared
requirements are exact. `artwork_coverage:UNASSIGNED`, `production_readiness:NOT_READY`,
`visual_approval:UNREVIEWED` and `native_evidence:UNVERIFIED` remain independent.
Source-verified action mapping is separate from source-verified selection paths.
Neither establishes runtime/native acceptance. M0-S/I/N remain later separate gates.

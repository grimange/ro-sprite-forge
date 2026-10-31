# RSF-8 ordered topology resolution

`ro_sprite_forge.core.topology.resolve_topology(target, actor=actor,
profile=profile, inventories=(...))` expands the accepted immutable Actor/v1,
Runtime-profile/v2 and Target/v2 contracts into `rsf.resolved-requirements/v1`.
`topology_work_order(result)` returns a readable per-frame/layer checklist.

The filesystem adapter is:

```sh
ro-sprite-forge resolve --actor actor.json --profile profile.json \
  --target target.json --inventory body-inventory.json \
  --inventory head-inventory.json --output requirements.json --work-order
```

Omit `--inventory` for explicit declarations: artwork and binary resources are
not needed. Output publication uses the existing bounded JSON reader and atomic,
no-overwrite publisher. Malformed declarations/references fail with existing
`ForgeError(INVALID_INPUT)` and a JSON pointer; no approved resource is produced.
Provisional reports are valid diagnostic artifacts, never export-ready assets.
Existing M0 `plan` inputs, outputs and occurrence identities remain unchanged.

## Authorities and mappings

Explicit uniform roles apply to each declared frame; `per_frame` role arrays
apply ordinal-for-ordinal. Empty arrays and zero frames are explicit valid
structures. No missing count is inferred from a role array or a reference.

Inventory inheritance requires the target's exact selected digest and numeric
slot, associated actor part and ACT/SPR hashes. Source count must exactly match
the declared target count. The only frame mapping is one-to-one by ordinal;
there is no duplication, resampling, wrapping, trimming or interpolation.
Supported runtime semantics also require the numeric slot to equal the pinned
profile's group/view mapping. With unknown semantics, the explicitly selected
source slot remains numeric, the target runtime slot is null and semantics and
gameplay reachability remain UNVERIFIED. Selection is not proof of reachability.

Every inherited frame records reference type, namespace/part, inventory digest,
ACT/SPR identities, source slot/frame, mapping completeness and observed source
motion/delay. Ordered source layers, raw transforms, anchors, bounds and events
remain observations. Only visible source layers become artwork requirements;
invisible placeholder records remain in `constraints.source_motion.layers`.
`source_layer_ordinal` preserves the original position even with placeholders.
Unknown source roles stay null, with numeric ordinals identifying each layer.
Observed image references never become assigned replacement artwork.

Explicit declarations without anchor/registration/reuse constraints remain
UNSPECIFIED/UNDECLARED; no automatic attachment or reuse policy is invented.
Inherited source metadata are marked REFERENCE_OBSERVATIONS, not inferred
artistic or runtime approvals. Player-only body/head rules remain in the pinned
profile; NPC/monster never receive that relationship from this resolver.

Only immutable inventories can be inherited. Target-to-target and template-to-
template references are rejected by the closed schema, so there is no cycle
resolver or generic reference graph.

## Named template compatibility

Target/v2 gains one optional topology alternative; all previously valid shapes
retain their meaning, hashes and loaders. Older RSF-7 clients reject the new
shape instead of silently reinterpreting it. No stored record is migrated.

`single_layer_template(role)` returns an explicit `kind:template` declaration
with `id:single-layer`, `version:1`, the chosen role, a content hash and
`scope_confirmed:true`. Inserting it under one target action/part/view explicitly
confirms that exact scope. The digest hashes the canonical immutable content
`{schema:rsf.topology-template/v1,id:single-layer,version:1,layers:[role]}`.
Versions, names, roles, hash and confirmation are validated. False/missing scope
confirmation fails; nothing selects this template by default. The role parameter
belongs to the hashed definition. This bounded template is not a generic schema
migration or authoring framework.

## Counts, identities and completeness

Slots, frames and visible layer occurrences are separate arrays. Required and
optional counts are separate. Each includes known frames/layers, explicit and
inherited resolved frames/layers, underspecified slots/frames, unknown-frame-
count slots and nullable exact slot/layer counts. Empty action parts or part
views are counted as unexpanded declarations, not fabricated zero-work scopes. Missing declarations preserve
UNDERSPECIFIED_FRAME_COUNT or UNDERSPECIFIED_LAYER_TOPOLOGY. An unavailable
selected inventory also retains INHERITANCE_SOURCE_UNAVAILABLE. Incorrect
versions, seals, parts, source identities, slots and frame counts fail at precise
input paths, rather than substituting another reference.

IDs use target ID/revision, part, action, verified slot (or UNVERIFIED), view,
frame and ordered layer ordinal. Layer IDs additionally hash that frame's roles,
authority and applicable reference constraints. A topology change updates the
affected frame's layer IDs; it does not rewrite unrelated frame IDs or imported
inventories. The report separately pins the complete actor/target/profile
revisions and digests. There are no timestamps, random IDs or filesystem paths.

Complete declared scope can produce an EXACT structural checklist. A scoped
Walk never implies full-profile specification. Missing information cannot yield
COMPLETE_FOR_DECLARED_SCOPE. Artwork stays UNASSIGNED, unique artwork effort
UNKNOWN_UNTIL_ASSIGNMENTS, visual/native evidence UNVERIFIED, and asset
export_ready is always false. Artwork ledger, transforms, reuse approval and
visual review belong to later tasks.

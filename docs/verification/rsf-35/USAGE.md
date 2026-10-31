# Offline custom actions

Use the existing `rsf.target/v2` action structure. An action ID such as `Wave`
is stable; its optional display label is not its runtime identity. Add this
optional declaration to the action alongside its existing explicit parts/views
and frame/layer topology:

```json
{
  "offline": {
    "schema": "rsf.offline-action/v1",
    "label": "Wave",
    "timing": {
      "authority": "EXPLICIT_DIAGNOSTIC_INTERVAL",
      "frame_ms": 80,
      "loop": true
    },
    "compilation": "UNSUPPORTED"
  }
}
```

Load the target through `core.contracts.load_target`, resolve it through
`core.topology.resolve_topology`, and use the existing ledger, coverage and
review APIs. Missing topology stays unresolved. There is no default direction,
frame count, layer count, artwork, approval or native slot.

`core.custom_actions.action_support(target, actor=actor, profile=profile)`
returns separate authoring, preview prerequisites, timing, runtime mapping,
compilation and native evidence dimensions. Known profile actions retain their
existing mappings. Offline actions report `RUNTIME_ACTION_MAPPING_UNAVAILABLE`,
runtime `UNSUPPORTED` and native `UNVERIFIED`.

`preview_offline_action(target, actor=actor, profile=profile, ledger=ledger,
source_bytes=sources, action_id='Wave', view=0, frame=2)` renders actual assigned
PNG pixels through the existing compositor. Pass `elapsed_ms` to inspect the
explicit diagnostic clock. It returns the existing compositor result plus sealed
`offline` selection/provenance metadata. Timing does not alter native ACT delays.
Only the existing supported `mirror_x` assignment operation is executable here;
unsupported operations fail explicitly. Preview does not approve artwork.

`offline_registry_entry` creates a hash-bound capability reference for an
enrolled profile. Supply these references as `offline_actions` to the existing
`create_registry`. Old registry documents and canonical identity remain valid.
The record cannot claim a runtime slot or native verification.

For a format-permitted diagnostic compilation, declare
`BOUND_EXISTING_SLOT_DIAGNOSTIC` and inherit an exact original inventory slot for
each declared view. This explicitly authorizes bounded replacement in existing
storage. The existing compiler still requires current assignments, source hashes
and applicable review. The plan distinguishes `diagnostic_storage_slot` from
`runtime_slot: null`. No action is appended, no native dispatcher is added, and
the result remains `PARTIAL_DIAGNOSTIC`. A custom-action production request fails
with `RUNTIME_ACTION_MAPPING_UNAVAILABLE`. Explicit standalone topology without
original storage binding cannot compile under this policy.

Action-local composition identity binds topology, sources, timing and profile.
Relevant changes stale dependent decisions while unrelated action decisions can
remain applicable. Historical reviews persist. Full target and ledger revision
checks still apply when loading or compiling project state.

Reproduce the synthetic four-frame Wave and bound Guard/Dodge cases:

```sh
PYTHONPATH=src:tests .venv/bin/python docs/verification/rsf-35/reproduce.py /tmp/rsf35-reproduction
PYTHONPATH=src:tests .venv/bin/python -m unittest test_custom_actions -v
```

These are Python API workflows. This task adds no browser controls, CLI action
dispatcher or gameplay behavior. Source-backed profile support does not establish
native execution of a newly declared action.

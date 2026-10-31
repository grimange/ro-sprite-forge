# RSF-10 coverage evaluation and exported missing-art work orders

`ro_sprite_forge.core.coverage.evaluate_coverage(requirements, ledger=None, *, source_bytes=None, target=None)` combines resolved structural requirements (`rsf.resolved-requirements/v1`) with artwork assignments (`rsf.assignment-ledger/v1` or `rsf.resolved-ledger/v1`) to compute deterministic coverage and actionable missing-art work orders (`rsf.coverage-report/v1`). `format_work_order(report, ...)` emits human-readable text.

The filesystem CLI interfaces are:

```sh
ro-sprite-forge coverage --requirements requirements.json --ledger ledger.json \
  --source art-a=source.png --output coverage.json --work-order-output work-order.txt

ro-sprite-forge missing --requirements requirements.json --ledger ledger.json \
  --output missing-work-order.txt --filter unresolved
```

`--ledger` is optional: when omitted or None, coverage evaluates an unassigned target, producing the complete missing-art production checklist before artwork generation begins.

## Orthogonal status dimensions

Evaluation preserves six independent status dimensions without collapsing them into a single score:

1. **Structural specification:** `COMPLETE_FOR_FULL_PROFILE`, `COMPLETE_FOR_DECLARED_SCOPE`, or `UNDERSPECIFIED`. Missing frame counts or layer topology remain explicitly underspecified (`UNDERSPECIFIED_FRAME_COUNT`, `UNDERSPECIFIED_LAYER_TOPOLOGY`); they are never defaulted to zero or one layer.
2. **Artwork assignment:** `COMPLETE_FOR_FULL_PROFILE`, `COMPLETE_FOR_DECLARED_SCOPE`, `PARTIAL`, or `UNASSIGNED`. Distinguishes direct source assignments, explicit reuse dependencies, and unassigned occurrences.
3. **Source availability:** `AVAILABLE`, `REUSED`, `MISSING`, `UNVERIFIED`. Unobserved bytes remain `UNVERIFIED`; explicit absence is `MISSING`.
4. **Technical validation:** Source hash validation (`VALID`, `INVALID`, `UNVERIFIED`) applies only to content identity. Image decoding is strictly `NOT_RUN`, and transformation execution is `NOT_RUN`.
5. **Visual review:** `APPROVED`, `REJECTED`, `UNVERIFIED`, `NOT_REQUIRED`. Only caller-supplied operator review records bound to the exact visual composition hash count as approved. Mismatched or evolved composition yields `STALE`. `NOT_REQUIRED` requires explicit unchanged classic reference policy and never establishes authored replacement coverage.
6. **Native evidence & production readiness:** Native evidence is `UNVERIFIED` in M1; `export_ready` is false. Programmatic validity never implies aesthetic approval or native client playback proof.

## Missing-art work-order categories

Each unresolved requirement is classified into an actionable prerequisite category:

- `SUPPLY_ARTWORK`: Required occurrence is unassigned, or classic reference fallback where replacement artwork is required.
- `RESTORE_OR_LOCATE_SOURCE`: Assigned source bytes are missing.
- `CORRECT_INVALID_SOURCE_OR_ASSIGNMENT`: Source hash mismatch, empty source, broken reuse dependency, or rejected review.
- `RESOLVE_REQUIREMENTS`: Action/view slot has underspecified frame count or layer topology.
- `VERIFY_SOURCE_CONTENT`: Source bytes unverified or undeclared SHA-256.
- `VERIFY_TRANSFORMATION`: Transformation recipe declared but unexecuted.
- `REVIEW_ARTWORK`: Visual review is pending/unverified.
- `REVIEW_STALE`: Visual review binding is stale due to composition or source changes.
- `RESOLVE_RUNTIME_SUPPORT`: Action slot mapping is unsupported by pinned runtime profile.

## Bounded limits & determinism

- Maximum 100,000 occurrences, 10,000 sources, 1,000 excluded actions, 1,000 diagnostics.
- Outputs use canonical JSON (`canonical_bytes`) and SHA-256 seals.
- No random identifiers, timestamps, or host filesystem paths in canonical records.
- Outputs use atomic no-overwrite publication (`publish`, `_publish_text`).

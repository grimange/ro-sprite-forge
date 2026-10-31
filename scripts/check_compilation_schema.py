"""Offline conformance checks for compilation manifest and project compilation contracts (RSF-23)."""
import copy
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "src")]
from jsonschema import Draft202012Validator
from ro_sprite_forge.core.canonical import sealed
from ro_sprite_forge.core.compiler import compilation_manifest_schema
from ro_sprite_forge.core.project import project_schema


def main():
    comp_schema = compilation_manifest_schema()
    proj_schema = project_schema()
    Draft202012Validator.check_schema(comp_schema)
    Draft202012Validator.check_schema(proj_schema)
    comp_validator = Draft202012Validator(comp_schema)
    proj_validator = Draft202012Validator(proj_schema)

    h1 = "1" * 64
    h2 = "2" * 64
    h3 = "3" * 64
    h4 = "4" * 64

    valid_manifest = sealed({
        "schema": "rsf.compilation-manifest/v1",
        "id": "compile-novice-walk-south",
        "writer_version": "1.0.0",
        "compilation_mode": "bounded_replacement",
        "replacement_policy": "explicit_rgba",
        "isolation_strategy": "auto",
        "part": "body",
        "target": {"id": "novice-target", "revision": 1, "canonical_sha256": h1},
        "runtime_profile": {"id": "player", "revision": 1, "canonical_sha256": h2},
        "requirements_sha256": h3,
        "ledger": {"id": "novice-ledger", "revision": 2, "canonical_sha256": h4},
        "input_resources": {
            "act": {"format": "ACT 2.4", "bytes": 1024, "sha256": h1},
            "spr": {"format": "SPR 2.1", "bytes": 2048, "sha256": h2, "indexed_count": 10, "rgba_count": 0},
            "head_act": None,
            "head_spr": None,
        },
        "output_resources": {
            "act": {"format": "ACT 2.4", "bytes": 1024, "sha256": h3, "filename": "compiled.act"},
            "spr": {"format": "SPR 2.1", "bytes": 3072, "sha256": h4, "indexed_count": 10, "rgba_count": 1, "filename": "compiled.spr"},
            "head_act": None,
            "head_spr": None,
        },
        "replacements": [
            {
                "requirement_id": "body:Walk/view0/frame0/layer0",
                "assignment_id": "assignment-" + h1,
                "assignment_revision": 1,
                "slot": 8,
                "action": "Walk",
                "view": 0,
                "frame": 0,
                "layer_ordinal": 0,
                "clip_ordinal": 0,
                "source_id": "blob-" + h2,
                "source_sha256": h2,
                "source_origin": "AUTHORED",
                "derived_processing": {
                    "recipe_id": "crop-walk",
                    "recipe_sha256": h3,
                    "source_sha256": h1,
                    "reapplied_in_compiler": False,
                },
                "executed_ledger_ops": [],
                "review_state": "APPROVED",
                "composition_sha256": h4,
                "original_image": {
                    "pool": 0,
                    "index": 3,
                    "width": 32,
                    "height": 64,
                    "decoded_rgba_sha256": h1,
                },
                "output_image": {
                    "pool": 1,
                    "index": 0,
                    "width": 32,
                    "height": 64,
                    "decoded_rgba_sha256": h2,
                },
                "resolution_mode": "COPY_ON_WRITE_APPEND",
                "shared_consumers_count": 2,
                "unaffected_consumers_count": 1,
                "representational_notes": [
                    "INDEXED_CLIP_REMAPPED_TO_RGBA_POOL",
                    "ENCODED_TRUECOLOR_RGBA",
                ],
            }
        ],
        "preservation_summary": {
            "total_action_slots": 104,
            "modified_action_slots": [8],
            "untouched_action_slots": 103,
            "total_frames": 456,
            "modified_frames": 1,
            "untouched_frames": 455,
            "total_visible_clips": 456,
            "modified_clips": 1,
            "unaffected_visible_clips": 455,
            "hidden_clips_preserved": 0,
            "anchors_preserved": 456,
            "events_preserved": 2,
            "delays_preserved": 104,
            "head_resources_preserved_unchanged": True,
            "classic_retained_outside_completeness": True,
        },
        "verification": {
            "decode_after_write": "PASS",
            "metadata_preservation": "PASS",
            "targeted_pixel_verification": "PASS",
            "unaffected_reference_preservation": "PASS",
            "shared_reference_isolation": "PASS",
            "noop_byte_equal": False,
            "rust_oracle": "PASS",
            "rust_oracle_report_sha256": h3,
            "native_korangar": "UNVERIFIED",
        },
        "status": {
            "result": "COMPILED",
            "production_authorized": False,
            "export_ready": False,
            "experimental_bounded_output": True,
            "visual_approval_authority": "OPERATOR_ONLY",
            "diagnostics": ["BOUNDED_REPLACEMENT_ONLY"],
        },
    })

    # 2. Preserve mode valid manifest
    preserve_manifest = copy.deepcopy(valid_manifest)
    preserve_manifest.pop("canonical_sha256")
    preserve_manifest["compilation_mode"] = "preserve"
    preserve_manifest["target"] = None
    preserve_manifest["runtime_profile"] = None
    preserve_manifest["requirements_sha256"] = None
    preserve_manifest["ledger"] = None
    preserve_manifest["replacements"] = []
    preserve_manifest["verification"]["noop_byte_equal"] = True
    preserve_manifest["verification"]["rust_oracle"] = "NOT_RUN"
    preserve_manifest["verification"]["rust_oracle_report_sha256"] = None
    preserve_manifest = sealed(preserve_manifest)

    valid_manifests = [valid_manifest, preserve_manifest]
    for m in valid_manifests:
        comp_validator.validate(m)

    # Project with compilations array
    proj = sealed({
        "schema": "rsf.project/v1",
        "project_id": "test-compile-proj",
        "name": "Test Compilation Project",
        "revision": 1,
        "created_at": "2026-10-30T12:00:00Z",
        "updated_at": "2026-10-30T12:00:00Z",
        "actor": "novice",
        "profile": "player",
        "sources": {},
        "reviews": {},
        "compilations": [valid_manifest],
    })
    proj_validator.validate(proj)

    # Invalid manifests
    invalid_manifests = []

    # 1. Bad schema
    b1 = copy.deepcopy(valid_manifest)
    b1["schema"] = "rsf.compilation-manifest/v2"
    invalid_manifests.append(b1)

    # 2. Invalid compilation_mode
    b2 = copy.deepcopy(valid_manifest)
    b2["compilation_mode"] = "auto_generate"
    invalid_manifests.append(b2)

    # 3. Invalid native_korangar claim (must be UNVERIFIED in RSF-23)
    b3 = copy.deepcopy(valid_manifest)
    b3["verification"]["native_korangar"] = "PASS"
    invalid_manifests.append(b3)

    # 4. Reapplied derived transformation in compiler (must be const False)
    b4 = copy.deepcopy(valid_manifest)
    b4["replacements"][0]["derived_processing"]["reapplied_in_compiler"] = True
    invalid_manifests.append(b4)

    # 5. Unapproved review_state in replacement
    b5 = copy.deepcopy(valid_manifest)
    b5["replacements"][0]["review_state"] = "UNVERIFIED"
    invalid_manifests.append(b5)

    # 6. Invalid resolution_mode
    b6 = copy.deepcopy(valid_manifest)
    b6["replacements"][0]["resolution_mode"] = "MUTATE_SHARED_IN_PLACE"
    invalid_manifests.append(b6)

    for bad in invalid_manifests:
        errs = list(comp_validator.iter_errors(bad))
        assert len(errs) > 0, f"Expected validation error for {bad}"

    print(f"COMPILATION_SCHEMA_PASS schemas=2 valid={len(valid_manifests) + 1} invalid={len(invalid_manifests)}")


if __name__ == "__main__":
    main()

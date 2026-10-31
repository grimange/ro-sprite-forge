"""Offline conformance checks for image recipes and transformation schema contracts (RSF-21)."""
import copy
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "src")]
from jsonschema import Draft202012Validator
from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed
from ro_sprite_forge.core.project import project_schema


def main():
    schema = project_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    source_hash = "1" * 64
    derived_hash = "2" * 64
    recipe_hash = "3" * 64

    recipe_manifest = {
        "schema": "rsf.image-recipe/v1",
        "id": "recipe-crop-flip",
        "name": "Crop and Flip Recipe",
        "source_sha256": source_hash,
        "source_filename": "frame.png",
        "operations": [
            {"op": "crop", "x": 0, "y": 0, "width": 32, "height": 32},
            {"op": "flip", "direction": "horizontal"},
        ],
        "semantics": "1.0.0",
    }
    recipe_manifest = sealed(recipe_manifest)

    base_project = {
        "schema": "rsf.project/v1",
        "project_id": "test-transform-proj",
        "name": "Test Transformation Project",
        "revision": 1,
        "created_at": "2026-10-30T12:00:00Z",
        "updated_at": "2026-10-30T12:00:00Z",
        "actor": "test-actor",
        "profile": "player",
        "sources": {
            source_hash: {
                "sha256": source_hash,
                "filename": "frame.png",
                "size": 4096,
                "blob_path": "blobs/" + source_hash,
                "origin": "AUTHORED",
                "kind": "IMAGE",
                "width": 64,
                "height": 64,
                "mode": "RGBA",
                "transparency_kind": "PARTIALLY_TRANSPARENT",
                "has_transparency": True,
            },
            derived_hash: {
                "sha256": derived_hash,
                "filename": "recipe-crop-flip.png",
                "size": 1024,
                "blob_path": "blobs/" + derived_hash,
                "origin": "AUTHORED",
                "kind": "IMAGE",
                "width": 32,
                "height": 32,
                "mode": "RGBA",
                "transparency_kind": "PARTIALLY_TRANSPARENT",
                "has_transparency": True,
                "recipe_id": "recipe-crop-flip",
                "recipe_sha256": recipe_hash,
                "source_sha256": source_hash,
                "loss_report": ["CROPPED_DISCARDED_PIXELS"],
            },
        },
        "reviews": {},
        "recipes": [recipe_manifest],
    }
    sealed_base = sealed(base_project)

    # Valid instances
    valid = [sealed_base]

    # Additional valid recipes with other operations
    multi_op_project = copy.deepcopy(base_project)
    multi_op_project["recipes"][0]["operations"] = [
        {"op": "crop", "x": 4, "y": 4, "width": 24, "height": 24},
        {"op": "scale", "width": 48, "height": 48, "filter": "nearest"},
        {"op": "offset", "offset_x": 2, "offset_y": -2, "overflow": "clip"},
        {"op": "matte_key", "color": [255, 0, 255], "tolerance": 5, "replacement_alpha": 0},
        {"op": "color_mode", "target_mode": "RGBA", "dither": False},
    ]
    multi_op_project["recipes"][0] = sealed(multi_op_project["recipes"][0])
    valid.append(sealed(multi_op_project))

    # Empty recipes array
    empty_recipes = copy.deepcopy(base_project)
    empty_recipes["recipes"] = []
    valid.append(sealed(empty_recipes))

    # Optional recipes omitted
    no_recipes = copy.deepcopy(base_project)
    no_recipes.pop("recipes")
    valid.append(sealed(no_recipes))

    for doc in valid:
        validator.validate(doc)

    # Invalid instances
    invalid = []

    # 1. Invalid recipe schema
    bad1 = copy.deepcopy(sealed_base)
    bad1["recipes"][0]["schema"] = "rsf.image-recipe/v2"
    invalid.append(bad1)

    # 2. Invalid source_sha256 in recipe
    bad2 = copy.deepcopy(sealed_base)
    bad2["recipes"][0]["source_sha256"] = "invalid_hash"
    invalid.append(bad2)

    # 3. Unknown operation name in recipe
    bad3 = copy.deepcopy(sealed_base)
    bad3["recipes"][0]["operations"].append({"op": "ai_hallucinate_background"})
    invalid.append(bad3)

    # 4. Crop with zero width
    bad4 = copy.deepcopy(sealed_base)
    bad4["recipes"][0]["operations"][0]["width"] = 0
    invalid.append(bad4)

    # 5. Flip with invalid direction
    bad5 = copy.deepcopy(sealed_base)
    bad5["recipes"][0]["operations"][1]["direction"] = "diagonal"
    invalid.append(bad5)

    # 6. Matte key with invalid channel value > 255
    bad6 = copy.deepcopy(sealed_base)
    bad6["recipes"][0]["operations"].append({"op": "matte_key", "color": [300, 0, 0]})
    invalid.append(bad6)

    # 7. Unauthorized extra field on recipe
    bad7 = copy.deepcopy(sealed_base)
    bad7["recipes"][0]["unauthorized_field"] = "bad"
    invalid.append(bad7)

    # 8. Invalid loss_report element (must be string)
    bad8 = copy.deepcopy(sealed_base)
    bad8["sources"][derived_hash]["loss_report"] = [123]
    invalid.append(bad8)

    for doc in invalid:
        errors = list(validator.iter_errors(doc))
        assert len(errors) > 0, f"Expected validation failure for invalid doc: {doc}"

    print(f"TRANSFORMATION_SCHEMA_PASS schemas=1 valid={len(valid)} invalid={len(invalid)}")


if __name__ == "__main__":
    main()

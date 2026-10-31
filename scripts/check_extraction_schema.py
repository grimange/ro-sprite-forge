"""Offline conformance checks for spritesheet extraction and sources schema contracts (RSF-20)."""
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

    sheet_hash = "1" * 64
    extracted_hash = "2" * 64
    recipe_hash = "3" * 64
    collection_hash = "4" * 64

    extraction_manifest = {
        "schema": "rsf.spritesheet-extraction/v1",
        "id": "ext-1",
        "name": "Orc Walk Sheet Extraction",
        "source_sha256": sheet_hash,
        "source_filename": "sheet.png",
        "item_count": 1,
        "collection_sha256": collection_hash,
        "items": [
            {
                "ordinal": 0,
                "id": "cell-0",
                "x": 0,
                "y": 0,
                "width": 32,
                "height": 32,
                "extracted_sha256": extracted_hash,
                "recipe_sha256": recipe_hash,
                "filename": "ext-1_000_cell-0.png",
                "mode": "RGBA",
                "transparency_kind": "PARTIALLY_TRANSPARENT",
                "has_transparency": True,
            }
        ],
    }
    extraction_manifest = sealed(extraction_manifest)

    base_project = {
        "schema": "rsf.project/v1",
        "project_id": "test-extraction-proj",
        "name": "Test Extraction Project",
        "revision": 1,
        "created_at": "2026-10-30T12:00:00Z",
        "updated_at": "2026-10-30T12:00:00Z",
        "actor": "test-actor",
        "profile": "player",
        "sources": {
            sheet_hash: {
                "sha256": sheet_hash,
                "filename": "sheet.png",
                "size": 4096,
                "blob_path": "blobs/" + sheet_hash,
                "origin": "AUTHORED",
                "kind": "IMAGE",
                "width": 128,
                "height": 128,
                "mode": "RGBA",
                "transparency_kind": "PARTIALLY_TRANSPARENT",
                "has_transparency": True,
            },
            extracted_hash: {
                "sha256": extracted_hash,
                "filename": "cell_0.png",
                "size": 512,
                "blob_path": "blobs/" + extracted_hash,
                "origin": "AUTHORED",
                "kind": "IMAGE",
                "width": 32,
                "height": 32,
                "mode": "RGBA",
                "transparency_kind": "PARTIALLY_TRANSPARENT",
                "has_transparency": True,
                "extraction_id": "ext-1",
                "recipe_sha256": recipe_hash,
                "source_sheet_sha256": sheet_hash,
                "rect_id": "cell-0",
                "crop_rect": [0, 0, 32, 32],
            },
        },
        "reviews": {},
        "extractions": [extraction_manifest],
    }
    sealed_base = sealed(base_project)

    # Valid instances
    valid = [sealed_base]

    # Empty extractions array
    empty_ext = copy.deepcopy(base_project)
    empty_ext["extractions"] = []
    valid.append(sealed(empty_ext))

    # Optional extractions field omitted
    no_ext = copy.deepcopy(base_project)
    no_ext.pop("extractions")
    valid.append(sealed(no_ext))

    for doc in valid:
        validator.validate(doc)

    # Invalid instances
    invalid = []

    # 1. Extraction with invalid schema identifier
    bad1 = copy.deepcopy(sealed_base)
    bad1["extractions"][0]["schema"] = "rsf.spritesheet-extraction/v2"
    invalid.append(bad1)

    # 2. Extraction with invalid source_sha256 (not 64 hex)
    bad2 = copy.deepcopy(sealed_base)
    bad2["extractions"][0]["source_sha256"] = "badhash"
    invalid.append(bad2)

    # 3. Item with negative coordinate
    bad3 = copy.deepcopy(sealed_base)
    bad3["extractions"][0]["items"][0]["x"] = -1
    invalid.append(bad3)

    # 4. Item missing required extracted_sha256
    bad4 = copy.deepcopy(sealed_base)
    bad4["extractions"][0]["items"][0].pop("extracted_sha256")
    invalid.append(bad4)

    # 5. Extraction with unauthorized extra property
    bad5 = copy.deepcopy(sealed_base)
    bad5["extractions"][0]["unauthorized_prop"] = True
    invalid.append(bad5)

    # 6. Extraction item with zero width (minimum: 1)
    bad6 = copy.deepcopy(sealed_base)
    bad6["extractions"][0]["items"][0]["width"] = 0
    invalid.append(bad6)

    # 7. Source crop_rect having wrong type
    bad7 = copy.deepcopy(sealed_base)
    bad7["sources"][extracted_hash]["crop_rect"] = "0,0,32,32"
    invalid.append(bad7)

    # 8. Source extraction_id not string
    bad8 = copy.deepcopy(sealed_base)
    bad8["sources"][extracted_hash]["extraction_id"] = 12345
    invalid.append(bad8)

    for doc in invalid:
        errors = list(validator.iter_errors(doc))
        assert len(errors) > 0, f"Expected validation failure for invalid doc: {doc}"

    print(f"EXTRACTION_SCHEMA_PASS schemas=1 valid={len(valid)} invalid={len(invalid)}")


if __name__ == "__main__":
    main()

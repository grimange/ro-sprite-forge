"""Offline conformance checks for project sequences and sources schema contracts (RSF-19)."""
import copy
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "src")]
from jsonschema import Draft202012Validator
from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.core.ingestion import validate_sequence
from ro_sprite_forge.core.project import project_schema


def main():
    schema = project_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    base_project = {
        "schema": "rsf.project/v1",
        "project_id": "test-proj",
        "name": "Test Project",
        "revision": 1,
        "created_at": "2026-10-30T12:00:00Z",
        "updated_at": "2026-10-30T12:00:00Z",
        "actor": "test-actor",
        "profile": "player",
        "sources": {
            "a" * 64: {
                "sha256": "a" * 64,
                "filename": "walk_0.png",
                "size": 1024,
                "blob_path": "blobs/" + "a" * 64,
                "origin": "AUTHORED",
                "kind": "IMAGE",
                "width": 32,
                "height": 32,
                "mode": "RGBA",
                "transparency_kind": "PARTIALLY_TRANSPARENT",
                "has_transparency": True,
                "sequence_id": "seq-1",
                "ordinal": 0,
            }
        },
        "reviews": {},
        "sequences": [
            validate_sequence(
                "seq-1",
                "Seq 1",
                [{"ordinal": 0, "sha256": "a" * 64, "filename": "walk_0.png", "width": 32, "height": 32}],
            )
        ],
    }
    sealed_base = sealed(base_project)

    # Valid instances
    valid = [sealed_base]

    # Another valid with empty sequences
    empty_seq = copy.deepcopy(base_project)
    empty_seq["sequences"] = []
    valid.append(sealed(empty_seq))

    # Without sequences field (optional)
    no_seq = copy.deepcopy(base_project)
    no_seq.pop("sequences")
    valid.append(sealed(no_seq))

    for doc in valid:
        validator.validate(doc)

    # Invalid instances
    invalid = []
    # 1. sequence with negative ordinal
    bad1 = copy.deepcopy(sealed_base)
    bad1["sequences"][0]["frames"][0]["ordinal"] = -1
    invalid.append(bad1)

    # 2. sequence with invalid sha256
    bad2 = copy.deepcopy(sealed_base)
    bad2["sequences"][0]["frames"][0]["sha256"] = "invalid"
    invalid.append(bad2)

    # 3. sequence with missing required name
    bad3 = copy.deepcopy(sealed_base)
    bad3["sequences"][0].pop("name")
    invalid.append(bad3)

    # 4. sequence with invalid schema
    bad4 = copy.deepcopy(sealed_base)
    bad4["sequences"][0]["schema"] = "rsf.sequence/v2"
    invalid.append(bad4)

    # 5. sources with invalid origin
    bad5 = copy.deepcopy(sealed_base)
    bad5["sources"]["a" * 64]["origin"] = "UNKNOWN_ORIGIN"
    invalid.append(bad5)

    # 6. sources with extra unauthorized property
    bad6 = copy.deepcopy(sealed_base)
    bad6["sources"]["a" * 64]["unauthorized"] = True
    invalid.append(bad6)

    for doc in invalid:
        errors = list(validator.iter_errors(doc))
        assert len(errors) > 0, f"Expected validation failure for invalid doc: {doc}"

    print(f"INGESTION_SCHEMA_PASS schemas=1 valid={len(valid)} invalid={len(invalid)}")


if __name__ == "__main__":
    main()

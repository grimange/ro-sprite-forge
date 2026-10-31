"""Create a private loader map through existing audited optional fixture hooks."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests/private_fixture_hooks"))
    from test_audited_fixtures import AUDITED_HASHES, find_fixture
    files = {}
    for name in ("novice_body", "novice_head", "orc_skeleton"):
        for extension in ("act", "spr"):
            key = name + "_" + extension
            path = find_fixture(key)
            if path is None:
                raise SystemExit("NATIVE_UNVERIFIED: fixture unavailable: " + key)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != AUDITED_HASHES[key]:
                raise SystemExit("RESOURCE_MISMATCH: audited fixture: " + key)
            files[f"data\\sprite\\{name}.{extension}"] = dict(path=str(path.resolve()), sha256=digest)
    with args.output.open("x") as stream:
        json.dump(dict(files=files), stream, sort_keys=True, indent=2)
    print("Audited all six input hashes; private loader map created.")


if __name__ == "__main__":
    main()

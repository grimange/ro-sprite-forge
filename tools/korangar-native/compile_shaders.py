"""Compile original pinned entity/WBOIT shaders with upstream build flags."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    parser.add_argument("--slangc", default="slangc")
    parser.add_argument("--builder-image")
    args = parser.parse_args()
    stage = args.stage.resolve()
    output = stage / "shaders"
    output.mkdir(exist_ok=True)
    results = {}
    for group, name in (("forward", "entity"), ("postprocessing", "wboit_resolve")):
        if args.builder_image:
            command = ["docker", "run", "--rm", "--network", "none", "-v", f"{stage}:/work",
                       "--entrypoint", "/home/builder/slangc/bin/slangc", args.builder_image]
            root = Path("/work")
        else:
            command = [args.slangc]
            root = stage
        command += ["-target", "spirv", "-profile", "spirv_1_3", "-I", str(root / "korangar/shaders/modules"),
                    "-matrix-layout-column-major", "-fvk-use-gl-layout", "-default-image-format-unknown", "-O3",
                    "-o", str(root / f"shaders/{name}.spv"), str(root / f"korangar/shaders/passes/{group}/{name}.slang")]
        subprocess.run(command, check=True)
        results[name] = hashlib.sha256((output / f"{name}.spv").read_bytes()).hexdigest()
    (stage / "shader-manifest.json").write_text(json.dumps(results, sort_keys=True, indent=2) + "\n")
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()

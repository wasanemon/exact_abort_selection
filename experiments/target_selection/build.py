#!/usr/bin/env python3
"""Build the standalone reproduction and save the exact command/source identity."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--sanitize", action="store_true")
    args = p.parse_args()
    binary = args.output.resolve()
    binary.parent.mkdir(parents=True, exist_ok=True)
    sources = ["experiments/target_selection/validator.cpp", "eas/Selector.cpp", "eas/Oracle.cpp"]
    flags = ["-std=c++14", "-Wall", "-Wextra", "-O1", "-g", "-fno-omit-frame-pointer", "-fsanitize=address,undefined"] if args.sanitize else ["-std=c++14", "-Wall", "-Wextra", "-O3", "-DNDEBUG"]
    command = ["g++", *flags, "-I.", *sources, "-o", str(binary)]
    run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    info = dict(command=command, cwd=str(ROOT), returncode=run.returncode, stdout=run.stdout, stderr=run.stderr,
                compiler=subprocess.check_output(["g++", "--version"], text=True),
                git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                git_status=subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
                source_sha256={s: hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources+["eas/Selector.h"]})
    if run.returncode == 0:
        info["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    binary.with_suffix(".build.json").write_text(json.dumps(info, indent=2, sort_keys=True)+"\n")
    print(json.dumps(dict(binary=str(binary), returncode=run.returncode, metadata=str(binary.with_suffix('.build.json')))))
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())

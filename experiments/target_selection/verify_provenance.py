#!/usr/bin/env python3
"""Offline check of saved measurement provenance against its measured Git commit.

The checkout's current HEAD may contain later reports. Only the recorded measured
commit is used to validate measurement sources. This checks provenance consistency;
raw observations, traces, decisions, and archive bytes are checked by analyze.py.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "experiments/target_selection/"
SOURCES = (PREFIX + "validator.cpp", "eas/Selector.cpp", "eas/Oracle.cpp", "eas/Selector.h")
RUNNERS = {"runner_sha256": PREFIX + "run.py", "shared_runner_sha256": "experiments/eas/run.py"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


class Audit:
    def __init__(self):
        self.checks = 0
        self.errors = []
        self.git_files = []

    def check(self, condition, message):
        self.checks += 1
        if not condition:
            self.errors.append(message)

    def sha(self, value, label):
        self.check(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
                   label + ": missing/invalid SHA-256")

    def git_bytes(self, commit, name):
        result = subprocess.run(["git", "show", commit + ":" + name], cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False, timeout=15)
        if result.returncode:
            raise ValueError("measured Git object unavailable: " + commit + ":" + name
                             + "; the recorded commit and its objects must exist locally")
        self.git_files.append(name)
        return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="saved measurement directory")
    parser.add_argument("--binary", type=Path, help="optionally verify the actual measured binary bytes")
    args = parser.parse_args()
    audit = Audit()
    commit = None
    binary_checked = False
    try:
        root = args.input.resolve()
        build = read_json(root / "build.json")
        env = read_json(root / "environment.json")
        manifest = read_json(root / "manifest.json")
        audit.check(type(build.get("returncode")) is int and build["returncode"] == 0,
                    "build did not record a successful compiler exit")
        audit.check(build.get("git_status") == "", "build checkout was not recorded clean")
        commit = build.get("git_head")
        if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            raise ValueError("build.git_head must be the full measured commit SHA")
        for field in ("git_head", "git_status"):
            command = env["commands"][field]
            audit.check(type(command.get("returncode")) is int and command["returncode"] == 0,
                        "environment " + field + " command did not succeed")
            expected = commit if field == "git_head" else ""
            output = command.get("output")
            audit.check(isinstance(output, str) and output.strip() == expected,
                        "environment " + field + " differs from clean measured build")
        built_sources = build["source_sha256"]
        env_sources = env["source_sha256"]
        if not isinstance(built_sources, dict) or not isinstance(env_sources, dict):
            raise ValueError("source_sha256 must be an object in build and environment")
        audit.check(set(built_sources) == set(SOURCES), "build source inventory differs from the four measurement sources")
        audit.check(env_sources == built_sources, "environment source hashes differ from build source hashes")
        for name in SOURCES:
            recorded = built_sources.get(name)
            audit.sha(recorded, "build source " + name)
            audit.check(recorded == digest(audit.git_bytes(commit, name)),
                        "build source hash differs from measured Git object: " + name)
        binary_sha = build.get("binary_sha256")
        audit.sha(binary_sha, "build binary")
        for label, record in (("environment", env), ("manifest", manifest)):
            audit.sha(record.get("binary_sha256"), label + " binary")
            audit.check(record.get("binary_sha256") == binary_sha,
                        label + " binary hash differs from build")
        for field, name in RUNNERS.items():
            recorded = manifest.get(field)
            audit.sha(recorded, "manifest " + field)
            audit.check(recorded == digest(audit.git_bytes(commit, name)),
                        field + " differs from measured Git object: " + name)
        for label in ("plan", "gate"):
            name = PREFIX + label + ".json"
            source = audit.git_bytes(commit, name)
            saved = (root / (label + ".json")).read_bytes()
            audit.check(canonical(json.loads(saved)) == canonical(json.loads(source)),
                        "saved " + label + " differs semantically from measured Git object")
            field = "saved_" + label + "_sha256"
            audit.sha(manifest.get(field), "manifest " + field)
            audit.check(manifest.get(field) == digest(saved), "saved " + label + " bytes/hash mismatch")
            if label == "plan":
                audit.sha(manifest.get("plan_sha256"), "manifest source plan")
                audit.check(manifest.get("plan_sha256") == digest(source),
                            "plan source hash differs from measured Git object")
        if args.binary is not None:
            audit.check(file_digest(args.binary) == binary_sha, "actual binary bytes differ from recorded build")
            binary_checked = True
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        audit.errors.append(str(exc))
    result = dict(status="ok" if not audit.errors else "failed", measured_commit=commit,
                  checks=audit.checks, git_source_files_checked=len(audit.git_files),
                  git_source_files=audit.git_files, actual_binary_checked=binary_checked,
                  errors=audit.errors,
                  scope="saved metadata consistency against measured Git objects; observations require analyze.py")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not audit.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

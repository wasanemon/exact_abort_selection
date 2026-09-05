#!/usr/bin/env python3
"""Offline evidence integrity check; --write-manifest is explicit bootstrapping.

The unified manifest covers every regular file below sources except itself,
including extracted text and retrieval logs. It also anchors the two mandatory
Issue #3 inputs to the requested Git commit. No network or source rewrite occurs
in the default verification mode. Original download manifests are checked too.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

BASE = "d150211968ef6d61efda82f9f44f63e3bac28b44"
SOURCE_PATH = Path("experiments/target_selection/sources")
BASE_INPUTS = ("REPORT_policy_comparison_ja.md", "next_stage.json")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def safe_path(root, name):
    name = Path(name)
    if name.is_absolute() or ".." in name.parts or not name.parts:
        raise ValueError("invalid manifest path: " + str(name))
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("manifest path escapes root: " + str(name))
    return path


def files_in_sources(root):
    result = set()
    for path in (root / SOURCE_PATH).rglob("*"):
        if path.is_symlink():
            raise ValueError("source symlinks are not supported: " + str(path))
        if path.is_file() and path != root / SOURCE_PATH / "checksums.json":
            result.add(path.relative_to(root).as_posix())
    return result


def git_source(root, name):
    try:
        p = subprocess.run(["git", "show", BASE + ":" + name], cwd=root,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           check=False, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout if p.returncode == 0 else None


class Audit:
    def __init__(self, root):
        self.root = root
        self.verified = set()
        self.assertions = 0
        self.missing = set()
        self.mismatch = []
        self.errors = []
        self.skipped_download_errors = 0

    def check(self, name, sha, size=None, origin="checksums.json"):
        self.assertions += 1
        path = safe_path(self.root, name)
        if not path.is_file():
            self.missing.add(str(name))
            return
        if path.is_symlink() or digest(path) != sha or (size is not None and path.stat().st_size != size):
            self.mismatch.append({"path": str(name), "origin": origin})
        else:
            self.verified.add(str(name))

    def downloads(self):
        schemas = (("lantern_downloads.json", ("downloads",), "local_path", True),
                   ("representation_download_manifest.json", ("files", "local_files"), "path", False),
                   ("fabric_sources_manifest.json", ("sources",), "path", True))
        for filename, keys, path_key, repo_relative in schemas:
            path = self.root / SOURCE_PATH / filename
            if not path.is_file():
                self.missing.add(str(SOURCE_PATH / filename))
                continue
            data = read_json(path)
            for key in keys:
                for row in data[key]:
                    if row.get("status") == "error":
                        self.skipped_download_errors += 1
                        continue
                    if "sha256" not in row:
                        self.errors.append(filename + ": successful entry lacks sha256")
                        continue
                    name = Path(row[path_key])
                    if not repo_relative:
                        name = SOURCE_PATH / name
                    self.check(name.as_posix(), row["sha256"], row.get("bytes"), filename)
        ding_audit = self.root / SOURCE_PATH / "ding_audit.json"
        if ding_audit.is_file():
            self.check((SOURCE_PATH / "ding.pdf").as_posix(),
                       read_json(ding_audit)["paper"]["sha256"], origin="ding_audit.json")
        else:
            self.missing.add(str(SOURCE_PATH / "ding_audit.json"))

    def failed(self):
        return bool(self.missing or self.mismatch or self.errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="repository root (default: locate from this script)")
    parser.add_argument("--write-manifest", action="store_true",
                        help="explicitly create/refresh checksums.json after checking original source hashes")
    args = parser.parse_args()
    root = args.root.resolve()
    audit = Audit(root)
    manifest_path = root / SOURCE_PATH / "checksums.json"
    unlisted = []
    git_checked = 0
    git_unavailable = []
    try:
        audit.downloads()
        actual = files_in_sources(root)
        if args.write_manifest:
            base_inputs = []
            for name in BASE_INPUTS:
                content = git_source(root, name)
                if content is None:
                    audit.errors.append("bootstrap requires git show " + BASE + ":" + name)
                    continue
                row = {"path": name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
                base_inputs.append(row)
                audit.check(name, row["sha256"], row["bytes"], "git show " + BASE)
            if not audit.failed():
                data = {"schema_version": 1, "base_commit": BASE,
                        "scope": "all files under sources except checksums.json itself; Issue #3 source inputs",
                        "files": [{"path": name, "sha256": digest(root / name),
                                   "bytes": (root / name).stat().st_size} for name in sorted(actual)],
                        "base_inputs": base_inputs}
                manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not manifest_path.is_file():
            audit.missing.add(str(SOURCE_PATH / "checksums.json"))
        else:
            data = read_json(manifest_path)
            if data.get("schema_version") != 1 or data.get("base_commit") != BASE:
                raise ValueError("unsupported checksum schema or unexpected base commit")
            expected = set()
            for row in data["files"]:
                name = row["path"]
                if name in expected or not Path(name).is_relative_to(SOURCE_PATH) or name == str(SOURCE_PATH / "checksums.json"):
                    raise ValueError("duplicate/out-of-scope/self-referential checksum entry: " + name)
                expected.add(name)
                audit.check(name, row["sha256"], row["bytes"])
            unlisted = sorted(actual - expected)
            audit.missing.update(expected - actual)
            names = [row["path"] for row in data["base_inputs"]]
            if sorted(names) != sorted(BASE_INPUTS):
                raise ValueError("checksum manifest must anchor exactly both mandatory Issue #3 inputs")
            for row in data["base_inputs"]:
                audit.check(row["path"], row["sha256"], row["bytes"], "Issue #3 checksum")
                content = git_source(root, row["path"])
                if content is None:
                    git_unavailable.append(row["path"])
                else:
                    git_checked += 1
                    if hashlib.sha256(content).hexdigest() != row["sha256"] or len(content) != row["bytes"]:
                        audit.mismatch.append({"path": row["path"], "origin": "git show " + BASE})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        audit.errors.append(str(exc))
    ok = not audit.failed() and not unlisted
    result = {"status": "ok" if ok else "failed", "verified_files": len(audit.verified),
              "hash_assertions": audit.assertions, "missing": sorted(audit.missing),
              "mismatch": audit.mismatch, "unlisted": unlisted, "errors": audit.errors,
              "recorded_failed_downloads_skipped": audit.skipped_download_errors,
              "issue_3_git_crosschecks": git_checked, "issue_3_git_unavailable": git_unavailable,
              "manifest_written": bool(args.write_manifest and ok)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Audit saved EAS artifacts only; never launch benchmarks or generate plots.

Old absolute artifact paths are relocated into each supplied dataset directory.
Missing/unsuccessful observations are reported as unavailable, not as mismatches.
This checks saved artifacts and exact decisions; it does not replace the engine's
direct snapshot/private-write/full-database verification.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

EAS_MODES = ("graph", "lazy", "profile", "adaptive")
DECISION_FIELDS = ("abort_rounds", "commit", "certificate")
CONDITION_FIELDS = ("arity", "n", "distribution", "workers", "policy_k",
                    "key_count", "zipf", "selector_only")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def equal_bytes(left, right):
    """Compare file contents directly, independently of recorded hashes."""
    with left.open("rb") as a, right.open("rb") as b:
        while True:
            x, y = a.read(1 << 20), b.read(1 << 20)
            if x != y:
                return False
            if not x:
                return True


def stem(spec):
    return f"{spec['condition']}-s{spec['seed']}-{spec['phase']}-{spec['mode']}"


def semantic_key(spec, omit_workers=False):
    fields = [field for field in CONDITION_FIELDS if not (omit_workers and field == "workers")]
    return tuple(spec.get(field) for field in fields) + (spec["phase"], spec["seed"], spec["mode"])


def load_json(path, violations, context):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        violations.append(dict(kind="invalid_json", context=context, path=str(path), error=str(error)))
        return None


class Dataset:
    def __init__(self, name, directory, violations):
        self.name = name
        self.directory = Path(directory).resolve()
        self.violations = violations
        self.specs = []
        self.nodes = {}
        self.digest_cache = {}
        self.unavailable = []
        self.modes = []
        self.summary = {"directory": str(self.directory), "manifest": "manifest.json",
                        "mode_source": "plan.json:modes", "missing_records": [],
                        "unexpected_records": [], "record_checks": []}
        manifest = load_json(self.directory / "manifest.json", violations, name + ":manifest")
        plan = load_json(self.directory / "plan.json", violations, name + ":plan")
        for value, label in ((manifest, "manifest"), (plan, "plan")):
            if not isinstance(value, dict):
                self.unavailable.append(label + "_unavailable")
        if self.unavailable:
            self.summary.update(status="unavailable", reasons=self.unavailable, expected_records=None,
                                present_records=0, file_integrity={}, record_statuses={})
            return
        try:
            self.modes = list(plan["modes"])
            seeds = list(manifest["identity"]["seeds"])
            conditions = manifest["conditions"]
            warmup_match = re.search(r"seed=(\d+)", manifest["warmup"])
            if not warmup_match:
                raise ValueError("manifest must specify warmup seed explicitly")
            phases = [("warmup", int(warmup_match.group(1)))] + [("measure", seed) for seed in seeds]
            for condition in conditions:
                for phase, seed in phases:
                    for mode in self.modes:
                        if mode != "native" or not condition.get("selector_only", False):
                            self.specs.append(dict(condition, phase=phase, seed=seed, mode=mode))
            if not manifest["identity"].get("smoke", False):
                probes = [c for c in conditions if c["suite"] == "constant" and c["arity"] == 8]
                if probes:
                    self.specs.extend(dict(probes[0], phase="capacity_probe", seed=seeds[0], mode=mode)
                                      for mode in EAS_MODES)
        except (KeyError, TypeError, ValueError, IndexError) as error:
            violations.append(dict(kind="invalid_manifest_schema", dataset=name, error=str(error)))
            self.unavailable.append("invalid_manifest_schema")
            self.summary.update(status="unavailable", reasons=self.unavailable, expected_records=None,
                                present_records=0, file_integrity={}, record_statuses={})
            self.specs = []
            return
        expected_names = {stem(spec) + ".json" for spec in self.specs}
        actual_files = {path.name: path for path in (self.directory / "records").glob("*.json")}
        self.summary["unexpected_records"] = sorted(set(actual_files) - expected_names)
        # Unexpected records are also checked; their exclusion from planned
        # comparison groups is explicit rather than silently discarding them.
        for spec in self.specs:
            name = stem(spec)
            record = load_json(self.directory / "records" / (name + ".json"), violations,
                               self.name + ":record:" + name)
            if not isinstance(record, dict):
                if record is not None:
                    violations.append(dict(kind="invalid_record_schema", dataset=self.name, record=name))
                self.summary["missing_records"].append(name)
                node = {"label": self.name + "/" + name, "spec": spec,
                        "reason": "missing_record", "record_status": "missing"}
            else:
                node = self.check_record(name, record, spec)
            self.nodes[name] = node
        for filename in self.summary["unexpected_records"]:
            record = load_json(actual_files[filename], violations, self.name + ":extra:" + filename)
            if isinstance(record, dict):
                self.check_record(filename[:-5], record, None)
        status_counts = Counter(node["record_status"] for node in self.nodes.values())
        integrity = Counter(check["status"] for record in self.summary["record_checks"]
                            for check in record["files"].values())
        self.summary.update(expected_records=len(self.specs), present_records=len(actual_files),
                            expected_present_records=len(self.specs) - len(self.summary["missing_records"]),
                            record_statuses=dict(status_counts), file_integrity=dict(integrity),
                            status="partial" if self.summary["missing_records"] or integrity["unavailable"]
                            else "available")

    def local_path(self, record, field, subdirectory):
        original = record.get(field)
        if not isinstance(original, str) or not original:
            return None
        # Never fall back to an original absolute path, even if it still exists.
        local = self.directory / subdirectory / Path(original).name
        try:
            local.resolve().relative_to(self.directory)
        except ValueError:
            self.violations.append(dict(kind="artifact_outside_dataset", dataset=self.name,
                                        field=field, path=str(local)))
            return None
        return local

    def check_record(self, name, record, spec):
        label = self.name + "/" + name
        report = {"record": name, "files": {}}
        self.summary["record_checks"].append(report)
        node = {"label": label, "spec": spec, "record_status": record.get("status", "unknown"),
                "reason": None, "trace": None, "raw": None}
        if spec is not None:
            mismatches = {field: {"expected": value, "actual": record.get(field)}
                          for field, value in spec.items() if record.get(field) != value}
            if mismatches:
                self.violations.append(dict(kind="record_manifest_mismatch", record=label, fields=mismatches))
        for kind in ("trace", "raw"):
            path = self.local_path(record, kind + "_path", "traces" if kind == "trace" else "raw")
            check = {"path": str(path.relative_to(self.directory)) if path else None}
            report["files"][kind] = check
            if path is None or not path.is_file():
                check.update(status="unavailable", reason="missing_path" if path is None else "missing_file")
                continue
            node[kind] = path
            expected = record.get(kind + "_sha256")
            if not expected:
                check.update(status="unavailable", reason="missing_recorded_sha256")
                continue
            if path not in self.digest_cache:
                self.digest_cache[path] = sha256(path)
            actual = self.digest_cache[path]
            check.update(status="matched" if actual == expected else "mismatch",
                         recorded_sha256=expected, actual_sha256=actual)
            if actual != expected:
                self.violations.append(dict(kind="sha256_mismatch", record=label, artifact=kind,
                                            recorded=expected, actual=actual))
        if node["record_status"] != "ok":
            node["reason"] = "record_status:" + node["record_status"]
        elif node["raw"] is None:
            node["reason"] = "missing_raw_file"
        else:
            raw = load_json(node["raw"], self.violations, label + ":raw")
            decisions = raw.get("decisions") if isinstance(raw, dict) else None
            if not isinstance(decisions, dict) or any(not isinstance(decisions.get(k), list) for k in DECISION_FIELDS):
                node["reason"] = "missing_decision_arrays"
            elif raw.get("status") != "ok" or raw.get("verification") != "passed":
                node["reason"] = "raw_not_verified_ok"
                self.violations.append(dict(kind="record_raw_status_mismatch", record=label,
                                            raw_status=raw.get("status"), verification=raw.get("verification")))
            else:
                for field in ("mode", "seed", "n", "workers", "policy_k", "batch_id", "key_count", "selector_only"):
                    if raw.get(field) != record.get(field):
                        self.violations.append(dict(kind="raw_record_metadata_mismatch", record=label,
                                                    field=field, raw=raw.get(field), record_value=record.get(field)))
        report.update(record_status=node["record_status"],
                      decisions="available" if node["reason"] is None else "unavailable",
                      unavailable_reason=node["reason"])
        return node


def compare_group(label, expected, violations):
    """expected maps each required participant label to its node or None."""
    available = [(name, node) for name, node in expected.items() if node and not node.get("reason")]
    unavailable = {name: node.get("reason") if node else "not_in_manifest"
                   for name, node in expected.items() if not node or node.get("reason")}
    traces = [(name, node) for name, node in expected.items() if node and node.get("trace") is not None]
    result = {"group": label, "expected": list(expected), "available": [name for name, _ in available],
              "unavailable": unavailable, "decision_comparisons": 0, "trace_byte_comparisons": 0,
              "trace_available": [name for name, _ in traces],
              "trace_unavailable": {name: "missing_trace_or_record" for name, node in expected.items()
                                    if not node or node.get("trace") is None}, "mismatches": []}
    if available:
        reference_name, reference_node = available[0]
        reference = json.loads(reference_node["raw"].read_text())["decisions"]
        # Compare every field's complete nested array, never just a hash.
        for name, node in available[1:]:
            actual = json.loads(node["raw"].read_text())["decisions"]
            result["decision_comparisons"] += 1
            different = [field for field in DECISION_FIELDS if actual[field] != reference[field]]
            if different:
                item = dict(kind="decision_mismatch", group=label, reference=reference_name,
                            actual=name, differing_arrays=different)
                result["mismatches"].append(item)
                violations.append(item)
    # Input equality remains checkable even when a process timed out and did
    # not produce decision arrays. Availability of these two checks is separate.
    if traces:
        reference_name, reference_node = traces[0]
        for name, node in traces[1:]:
            result["trace_byte_comparisons"] += 1
            if not equal_bytes(reference_node["trace"], node["trace"]):
                item = dict(kind="trace_bytes_mismatch", group=label,
                            reference=reference_name, actual=name)
                result["mismatches"].append(item)
                violations.append(item)
    result["status"] = ("failed" if result["mismatches"] else "unavailable" if len(available) < 2 else
                        "partial" if unavailable or result["trace_unavailable"] else "passed")
    return result


def summarize_groups(groups):
    counts = Counter(g["status"] for g in groups)
    status = ("unavailable" if not groups else "failed" if counts["failed"] else
              "partial" if counts["partial"] or counts["unavailable"] else "passed")
    return {"status": status, "group_count": len(groups), "statuses": dict(counts),
            "decision_comparisons": sum(g["decision_comparisons"] for g in groups),
            "trace_byte_comparisons": sum(g["trace_byte_comparisons"] for g in groups),
            "unavailable_participants": sum(len(g["unavailable"]) for g in groups), "groups": groups}


def policy_groups(dataset, violations):
    groups = defaultdict(dict)
    for spec in dataset.specs:
        if spec["mode"] in EAS_MODES and spec["phase"] in ("warmup", "measure"):
            key = (spec["condition"], spec["phase"], spec["seed"])
            groups[key][spec["mode"]] = dataset.nodes[stem(spec)]
    return summarize_groups([compare_group(f"{dataset.name}/{condition}/{phase}/seed={seed}",
                            {mode: nodes.get(mode) for mode in EAS_MODES}, violations)
                            for (condition, phase, seed), nodes in sorted(groups.items())])


def worker_groups(dataset, violations):
    groups = defaultdict(dict)
    for spec in dataset.specs:
        if (spec["arity"] == 2 and spec["n"] == 8192 and spec["distribution"] == "zipf" and
                spec["phase"] in ("warmup", "measure") and
                (spec["suite"] == "main" and spec["workers"] == 1 or
                 spec["suite"] == "scale" and spec["workers"] in (2, 4))):
            groups[semantic_key(spec, omit_workers=True)][spec["workers"]] = dataset.nodes[stem(spec)]
    output = []
    for nodes in groups.values():
        exemplar = next(iter(nodes.values()))["spec"]
        label = f"{dataset.name}/workers/{exemplar['phase']}/seed={exemplar['seed']}/mode={exemplar['mode']}"
        check = compare_group(label, {str(w): nodes.get(w) for w in (1, 2, 4)}, violations)
        check.update(mode=exemplar["mode"], seed=exemplar["seed"], phase=exemplar["phase"],
                     expected_workers=[1, 2, 4], manifest_workers=sorted(nodes))
        output.append(check)
    return summarize_groups(sorted(output, key=lambda g: g["group"]))


def overlap_groups(full, smoke, violations):
    indices = []
    for dataset in (full, smoke):
        index = defaultdict(list)
        for spec in dataset.specs:
            if spec["phase"] in ("warmup", "measure"):
                index[semantic_key(spec)].append(dataset.nodes[stem(spec)])
        indices.append(index)
    common = set(indices[0]) & set(indices[1])
    output = []
    for key in sorted(common, key=repr):
        nodes = indices[0][key] + indices[1][key]
        exemplar = nodes[0]["spec"]
        label = f"full-smoke/{exemplar['condition']}/{exemplar['phase']}/seed={exemplar['seed']}/mode={exemplar['mode']}"
        output.append(compare_group(label, {node["label"]: node for node in nodes}, violations))
    result = summarize_groups(output)
    result.update(overlapping_semantic_keys=len(common),
                  full_nonoverlapping_keys=len(set(indices[0]) - common),
                  smoke_nonoverlapping_keys=len(set(indices[1]) - common))
    return result


def audit(full_directory, smoke_directory=None):
    violations = []
    full = Dataset("full", full_directory, violations)
    datasets = {"full": full.summary}
    checks = {"same_policy_full": policy_groups(full, violations),
              "workers_full": worker_groups(full, violations)}
    if smoke_directory is not None:
        smoke = Dataset("smoke", smoke_directory, violations)
        datasets["smoke"] = smoke.summary
        checks["same_policy_smoke"] = policy_groups(smoke, violations)
        checks["full_smoke_overlap"] = overlap_groups(full, smoke, violations)
    partial = any(d["status"] != "available" for d in datasets.values()) or any(
        check["status"] in ("partial", "unavailable") for check in checks.values())
    return {"schema_version": 1, "status": "failed" if violations else "partial" if partial else "passed",
            "scope": "saved artifact integrity and direct full-array decisions; native excluded from EAS policy comparison; native included only in own-mode worker/overlap comparisons",
            "verification_limit": "Does not replace engine-side direct snapshot, private-write, and full database-state comparisons. No benchmark is rerun.",
            "missing_policy": "Missing files/records/hashes, timeout, OOM, unsupported, and budget exhaustion are unavailable, not mismatches; expected runs come from manifest conditions/seeds and saved plan modes.",
            "relocation": "Resolve recorded basenames only inside each supplied dataset's raw/ and traces/ directories; never read original external paths.",
            "datasets": datasets, "checks": checks, "violation_count": len(violations), "violations": violations}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("full_dir", type=Path)
    parser.add_argument("--smoke", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = audit(args.full_dir, args.smoke)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temporary.replace(args.output)
    print(json.dumps({"status": result["status"], "violation_count": result["violation_count"],
                      "output": str(args.output), "checks": {name: {k: v for k, v in check.items() if k != "groups"}
                                                           for name, check in result["checks"].items()}}, sort_keys=True))
    return 1 if result["violation_count"] else 0


if __name__ == "__main__":
    sys.exit(main())

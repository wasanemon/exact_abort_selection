#!/usr/bin/env python3
"""Audit and aggregate the Issue #4 standalone validator measurements.

Reads raw/ and traces/ in place or directly from raw_data.tar.gz. Never extracts
an archive. A partial or corrupt experiment is reported and returns exit code 1.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import statistics
import tarfile


EXACT = {"paper", "graph", "lazy", "profile", "adaptive"}
MAIN_ARRAYS = ("abort_rounds", "commit", "certificate")
PAIRS = (("paper", "adaptive"), ("graph", "adaptive"),
         ("adaptive", "accept_static_degree"), ("adaptive", "accept_id"))
METRICS = ("total_ms", "commit_count", "fvs_size", "peak_rss_kib",
           "validator_commits_per_second")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                               allow_nan=False) + "\n")


def median(values):
    values = [x for x in values if x is not None]
    return statistics.median(values) if values else None


def summary(values):
    values = [x for x in values if x is not None]
    return {"median": median(values), "minimum": min(values) if values else None,
            "maximum": max(values) if values else None, "count": len(values)}


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def divide(a, b):
    return a / b if a is not None and b is not None and b > 0 else None


def csv_write(path, rows, first=()):
    fields = list(first) + sorted(set().union(*(set(r) for r in rows)) - set(first))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class Storage:
    """Relative, regular source files only; tar members never touch the filesystem."""
    def __init__(self, root):
        self.root, self.archive, self.members = root, None, {}
        self.checked_archive_members = 0
        path = root / "raw_data.tar.gz"
        if path.exists():
            self.archive = tarfile.open(path, "r:gz")
            for member in self.archive.getmembers():
                name = member.name
                while name.startswith("./"):
                    name = name[2:]
                pure = PurePosixPath(name)
                if pure.is_absolute() or ".." in pure.parts or "\\" in name:
                    raise ValueError("unsafe archive member: " + member.name)
                if member.isdir():
                    continue
                if not member.isfile() or not pure.parts or pure.parts[0] not in ("raw", "traces", "logs"):
                    raise ValueError("non-regular or unexpected archive member: " + member.name)
                if name in self.members:
                    raise ValueError("duplicate archive member: " + name)
                self.members[name] = member
            manifest_path = root / "archive_manifest.json"
            if manifest_path.exists():
                manifest = load_json(manifest_path)
                if manifest.get("archive") != path.name or digest(path.read_bytes()) != manifest.get("sha256"):
                    raise ValueError("archive digest/name mismatch")
                expected = manifest["members"]
                names = [m["path"] for m in expected]
                if len(names) != len(set(names)) or set(names) != set(self.members):
                    raise ValueError("archive manifest membership mismatch")
                for item in sorted(expected, key=lambda x: self.members[x["path"]].offset):
                    member = self.members[item["path"]]
                    with self.archive.extractfile(member) as stream:
                        data = stream.read()
                    if len(data) != item["bytes"] or digest(data) != item["sha256"]:
                        raise ValueError("archive member digest/size mismatch: " + item["path"])
                    self.checked_archive_members += 1

    def read(self, name):
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or "\\" in name or not pure.parts:
            raise ValueError("unsafe source path: " + name)
        path = self.root / name
        local = None
        if path.exists():
            if path.is_symlink() or not path.is_file() or self.root.resolve() not in path.resolve().parents:
                raise ValueError("source is not a regular contained file: " + name)
            local = path.read_bytes()
        archived = None
        if name in self.members:
            with self.archive.extractfile(self.members[name]) as stream:
                archived = stream.read()
        if local is not None and archived is not None and local != archived:
            raise ValueError("local/archive disagreement: " + name)
        if local is None and archived is None:
            raise ValueError("missing source file: " + name)
        return local if local is not None else archived

    def close(self):
        if self.archive:
            self.archive.close()


def expected_conditions(plan, smoke=False):
    result = []
    for suite in ("main", "scale", "paper_k", "dense"):
        config = plan[suite]
        for arity, n, distribution, k in itertools.product(
                config["arity"], config["n"], config["distribution"], config["k"]):
            if smoke and not (suite in ("main", "paper_k") and n == 40):
                continue
            item = dict(suite=suite, arity=arity, n=n, distribution=distribution,
                        k=k, key_count=plan["key_count"], zipf=plan["zipf"])
            identity = {key: item[key] for key in ("arity", "n", "distribution", "key_count", "zipf")}
            item["batch_id"] = int(digest(json.dumps(identity, sort_keys=True).encode())[:8], 16)
            item["condition"] = f"{suite}-l{arity}-n{n}-{distribution}-k{k}"
            result.append(item)
    return result


def planned_jobs(plan, configs):
    jobs = {}
    for c, seed, rep, mode in itertools.product(
            configs, plan["seeds"], range(1, plan["repetitions_per_seed"] + 1), plan["variants"]):
        identity = f"{c['condition']}-s{seed}-r{rep}-{mode}"
        jobs[identity] = dict(c, seed=seed, repetition=rep, mode=mode, id=identity,
                              trace=f"l{c['arity']}-n{c['n']}-{c['distribution']}-s{seed}.tsv")
    return jobs


def load_json(path):
    return json.loads(path.read_text())


def flatten_numeric(prefix, value, row):
    if isinstance(value, dict):
        for key, item in value.items():
            flatten_numeric(prefix + "." + key, item, row)
    elif type(value) in (int, float) and math.isfinite(value):
        row[prefix] = value


def analyze(root, output, plots=True):
    output.mkdir(parents=True, exist_ok=True)
    errors, rows, references, policy_checks = [], [], {}, 0
    statuses = Counter()
    storage = None
    plan = load_json(root / "plan.json")
    manifest = load_json(root / "manifest.json")
    trace_manifest = load_json(root / "trace_manifest.json")
    scope = manifest.get("scope")
    if scope is None:
        scope = "full" if manifest["conditions"] == expected_conditions(plan) else "smoke"
    if scope not in ("full", "smoke"):
        raise ValueError("manifest scope must be full or smoke")
    configs = expected_conditions(plan, scope == "smoke")
    if manifest["conditions"] != configs:
        errors.append("manifest conditions disagree with plan/scope")
    for label in ("plan", "gate"):
        expected_hash = manifest.get("saved_" + label + "_sha256")
        if expected_hash and digest((root / (label + ".json")).read_bytes()) != expected_hash:
            errors.append(label + " saved hash mismatch")
    jobs = planned_jobs(plan, configs)
    if manifest.get("expected_jobs") != len(jobs):
        errors.append("manifest expected_jobs disagrees with complete plan grid")
    listed = manifest["jobs"]
    listed_ids = [job["id"] for job in listed]
    if len(set(listed_ids)) != len(listed_ids) or set(listed_ids) != set(jobs):
        errors.append("manifest job IDs are duplicated/missing/unexpected")
    for job in listed:
        expected = jobs.get(job["id"])
        if expected and any(job.get(key) != value for key, value in expected.items()):
            errors.append("manifest job metadata mismatch: " + job["id"])
        if expected and job.get("trace_sha256") != trace_manifest.get(expected["trace"], {}).get("sha256"):
            errors.append("manifest job trace hash mismatch: " + job["id"])
    records = {}
    for line_no, line in enumerate((root / "runs.jsonl").read_text().splitlines(), 1):
        try:
            record = json.loads(line)
            identity = record["id"]
            if identity in records:
                raise ValueError("duplicate record: " + identity)
            records[identity] = record
            if identity not in jobs:
                errors.append("unexpected record: " + identity)
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(f"runs.jsonl line {line_no}: {exc}")
    expected_traces = {job["trace"] for job in jobs.values()}
    if set(trace_manifest) != expected_traces:
        errors.append("trace manifest does not exactly cover planned traces")
    checked_traces, checked_raw, trace_ids = 0, 0, {}
    try:
        storage = Storage(root)
        for name, trace in sorted(trace_manifest.items()):
            try:
                if trace["path"] != "traces/" + name:
                    raise ValueError("unexpected trace path")
                data = storage.read(trace["path"])
                if digest(data) != trace["sha256"]:
                    raise ValueError("trace hash mismatch")
                lines = data.decode("utf-8").splitlines()
                header = lines[0].split()
                trace_jobs = [job for job in jobs.values() if job["trace"] == name]
                sample = trace_jobs[0]
                if (len(header) != 4 or header[0] != "EAS_TRACE_V1"
                        or list(map(int, header[1:])) != [sample["key_count"], sample["seed"], sample["batch_id"]]
                        or trace.get("batch_id") != sample["batch_id"]):
                    raise ValueError("trace header/batch provenance mismatch")
                ids = [int(line.split("\t", 1)[0]) for line in lines[1:] if line.strip()]
                if len(ids) != sample["n"] or len(set(ids)) != len(ids):
                    raise ValueError("trace transaction count/ID uniqueness mismatch")
                trace_ids[name] = ids
                checked_traces += 1
            except (ValueError, OSError, KeyError, IndexError, tarfile.TarError) as exc:
                errors.append(f"trace {name}: {exc}")
    except (ValueError, OSError, tarfile.TarError) as exc:
        errors.append("archive/source storage: " + str(exc))
    try:
        # The deterministic archive is lexicographically ordered. Reading in
        # that order avoids repeatedly inflating the entire gzip prefix.
        for identity, expected in sorted(jobs.items()):
            row = dict(expected)
            record = records.get(identity)
            if record is None:
                row["status"] = "missing"
                statuses["missing"] += 1
                rows.append(row)
                continue
            status = record.get("status", "missing_status")
            row["record_status"] = status
            row["status"] = status
            if any(record.get(key) != value for key, value in expected.items()):
                errors.append("record job metadata mismatch: " + identity)
                row["status"] = "integrity_error"
            trace = trace_manifest.get(expected["trace"], {})
            if record.get("trace_sha256") != trace.get("sha256") or not trace.get("sha256"):
                errors.append("record trace provenance mismatch: " + identity)
                row["status"] = "integrity_error"
            raw = None
            if "raw_path" in record:
                try:
                    if record["raw_path"] != "raw/" + identity + ".json":
                        raise ValueError("unexpected raw path")
                    if storage is None:
                        raise ValueError("source storage unavailable")
                    data = storage.read(record["raw_path"])
                    if digest(data) != record.get("raw_sha256"):
                        raise ValueError("raw hash mismatch")
                    checked_raw += 1
                    if status == "ok":
                        raw = json.loads(data)
                except (ValueError, OSError, KeyError, tarfile.TarError) as exc:
                    errors.append(f"raw {identity}: {exc}")
                    row["status"] = "integrity_error"
            elif status == "ok":
                errors.append("successful record lacks raw_path: " + identity)
                row["status"] = "integrity_error"
            if status == "ok" and raw is not None:
                try:
                    if raw.get("status") != "ok" or raw.get("verification") != "passed":
                        raise ValueError("raw status/verification is not successful")
                    if any(raw.get(key) != expected[key] for key in ("n", "mode", "k")):
                        raise ValueError("raw n/mode/k mismatch")
                    for key in ("total_ms", "commit_count", "fvs_size", "peak_rss_kib"):
                        if not finite_number(raw.get(key)):
                            raise ValueError("missing/invalid metric " + key)
                    if (type(raw["commit_count"]) is not int or type(raw["fvs_size"]) is not int
                            or raw["commit_count"] + raw["fvs_size"] != expected["n"]):
                        raise ValueError("commit_count/fvs_size do not partition input")
                    decisions = raw["decisions"]
                    if not isinstance(decisions, dict) or any(not isinstance(decisions.get(k), list) for k in MAIN_ARRAYS):
                        raise ValueError("missing decision arrays")
                    commit, aborts, certificate = (decisions[key] for key in ("commit", "abort_rounds", "certificate"))
                    ids = trace_ids.get(expected["trace"])
                    if ids is None:
                        raise ValueError("cannot validate decisions without verified trace")
                    if (len(commit) != expected["n"] or any(type(x) is not int or x not in (0, 1) for x in commit)
                            or sum(commit) != raw["commit_count"]):
                        raise ValueError("invalid commit mask/count")
                    if certificate != sorted(i for i, bit in zip(ids, commit) if bit):
                        raise ValueError("certificate does not identify commit mask")
                    if any(not isinstance(r, list) or not r for r in aborts):
                        raise ValueError("invalid abort rounds")
                    if expected["mode"] in EXACT:
                        aborted = [i for r in aborts for i in r]
                        if sorted(aborted) != sorted(i for i, bit in zip(ids, commit) if not bit):
                            raise ValueError("abort rounds do not partition rejected transactions")
                    else:
                        if any(not isinstance(decisions.get(key), list) for key in
                               ("consideration_order", "rejected_ids", "initial_degrees")):
                            raise ValueError("missing acceptance decision arrays")
                        if (aborts or sorted(decisions["rejected_ids"]) != sorted(i for i, bit in zip(ids, commit) if not bit)
                                or sorted(decisions["consideration_order"]) != sorted(ids)):
                            raise ValueError("acceptance decisions do not partition the trace")
                    signature = {key: decisions[key] for key in MAIN_ARRAYS} if expected["mode"] in EXACT else decisions
                    policy = "exact" if expected["mode"] in EXACT else expected["mode"]
                    group = (expected["condition"], expected["seed"], policy)
                    if group in references:
                        if signature != references[group]:
                            raise ValueError("full decision arrays disagree across modes/repetitions")
                        policy_checks += 1
                    else:
                        references[group] = signature
                    for key in METRICS[:-1]:
                        row[key] = raw[key]
                    row["validator_commits_per_second"] = divide(1000 * raw["commit_count"], raw["total_ms"])
                    flatten_numeric("stats", raw.get("stats", {}), row)
                    if "runner_peak_rss_kib" in record:
                        row["runner_peak_rss_kib"] = record["runner_peak_rss_kib"]
                except (ValueError, KeyError, TypeError) as exc:
                    errors.append(f"verification {identity}: {exc}")
                    row["status"] = "verification_error"
            statuses[row["status"]] += 1
            rows.append(row)
    finally:
        if storage:
            storage.close()

    successful = [row for row in rows if row["status"] == "ok"]
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["condition"], row["seed"], row["mode"])].append(row)
    seed_rows = []
    for (condition, seed, mode), samples in sorted(grouped.items()):
        valid = [row for row in samples if row["status"] == "ok"]
        item = dict(condition=condition, seed=seed, mode=mode, successful=len(valid),
                    expected=plan["repetitions_per_seed"], complete=len(valid) == plan["repetitions_per_seed"])
        for metric in METRICS:
            item[metric] = median([row.get(metric) for row in valid])
        seed_rows.append(item)
    condition_rows = []
    by_condition = defaultdict(list)
    for row in seed_rows:
        by_condition[(row["condition"], row["mode"])].append(row)
    for (condition, mode), seeds in sorted(by_condition.items()):
        item = dict(condition=condition, mode=mode, complete=all(s["complete"] for s in seeds),
                    complete_seeds=sum(s["complete"] for s in seeds), expected_seeds=len(plan["seeds"]))
        for metric in METRICS:
            # Partial-seed medians remain in seed_metrics.csv but never enter condition estimates.
            for key, value in summary([s[metric] for s in seeds if s["complete"]]).items():
                item[metric + "_" + key] = value
        condition_rows.append(item)

    lookup = {(r["condition"], r["seed"], r["repetition"], r["mode"]): r for r in successful}
    pair_rows = []
    pair_metrics = ("total_ms_ratio", "total_ms_delta", "commit_delta", "validator_rate_ratio")
    for c, seed, rep, pair in itertools.product(configs, plan["seeds"],
            range(1, plan["repetitions_per_seed"] + 1), PAIRS):
        numerator, denominator = pair
        if numerator not in plan["variants"] or denominator not in plan["variants"]:
            continue
        item = dict(condition=c["condition"], seed=seed, repetition=rep,
                    numerator=numerator, denominator=denominator)
        a = lookup.get((c["condition"], seed, rep, numerator))
        b = lookup.get((c["condition"], seed, rep, denominator))
        item["status"] = "ok" if a is not None and b is not None else "incomplete_pair"
        if a is not None and b is not None:
            item.update(total_ms_ratio=divide(a["total_ms"], b["total_ms"]),
                        total_ms_delta=a["total_ms"] - b["total_ms"],
                        commit_delta=a["commit_count"] - b["commit_count"],
                        validator_rate_ratio=divide(a["validator_commits_per_second"], b["validator_commits_per_second"]))
            item["undefined_time_ratio"] = item["total_ms_ratio"] is None
            item["undefined_rate_ratio"] = item["validator_rate_ratio"] is None
        pair_rows.append(item)
    pair_groups = defaultdict(list)
    for row in pair_rows:
        pair_groups[(row["condition"], row["seed"], row["numerator"], row["denominator"])].append(row)
    pair_seeds = []
    for (condition, seed, numerator, denominator), samples in sorted(pair_groups.items()):
        valid = [r for r in samples if r["status"] == "ok"]
        item = dict(condition=condition, seed=seed, numerator=numerator, denominator=denominator,
                    successful=len(valid), complete=len(valid) == plan["repetitions_per_seed"])
        for metric in pair_metrics:
            values = [r.get(metric) for r in valid]
            item[metric] = median(values)
            item[metric + "_defined"] = sum(x is not None for x in values)
        pair_seeds.append(item)
    pair_conditions = []
    pair_grouped = defaultdict(list)
    for row in pair_seeds:
        pair_grouped[(row["condition"], row["numerator"], row["denominator"])].append(row)
    for (condition, numerator, denominator), seeds in sorted(pair_grouped.items()):
        item = dict(condition=condition, numerator=numerator, denominator=denominator,
                    complete=all(s["complete"] for s in seeds), complete_seeds=sum(s["complete"] for s in seeds),
                    expected_seeds=len(plan["seeds"]))
        for metric in pair_metrics:
            for key, value in summary([r[metric] for r in seeds if r["complete"]]).items():
                item[metric + "_" + key] = value
        pair_conditions.append(item)

    complete = not errors and len(records) == len(jobs) and statuses == {"ok": len(jobs)}
    facts = dict(schema_version=1, scope=scope, complete=complete, expected_jobs=len(jobs),
                 observed_records=len(records), statuses=dict(statuses), errors=errors,
                 checked_trace_files=checked_traces, checked_raw_files=checked_raw,
                 checked_archive_members=storage.checked_archive_members if storage else 0,
                 exact_and_repeat_decision_groups=len(references), direct_array_comparisons=policy_checks,
                 zero_commit_observations=sum(r["commit_count"] == 0 for r in successful),
                 measurement="standalone validator; validator_commits_per_second is not DBMS throughput",
                 aggregation="per-observation paired ratios/differences -> repetition median per seed -> median/min/max across complete seeds",
                 caveat="partial seeds excluded from condition estimates; null ratios have zero or undefined denominator; errors invalidate complete",
                 conditions=configs, condition_metrics=condition_rows, paired_condition_metrics=pair_conditions)
    csv_write(output / "observations.csv", rows, ("id", "condition", "seed", "repetition", "mode", "status"))
    csv_write(output / "seed_metrics.csv", seed_rows, ("condition", "seed", "mode"))
    csv_write(output / "condition_metrics.csv", condition_rows, ("condition", "mode"))
    csv_write(output / "paired_observations.csv", pair_rows, ("condition", "seed", "repetition", "numerator", "denominator"))
    csv_write(output / "paired_seed.csv", pair_seeds, ("condition", "seed", "numerator", "denominator"))
    csv_write(output / "paired_conditions.csv", pair_conditions, ("condition", "numerator", "denominator"))
    save(output / "facts.json", facts)
    make_tables(output, facts)
    if plots and condition_rows:
        make_plot(output, facts)
    return facts


def fmt(value):
    return "—" if value is None else f"{value:.5g}"


def make_tables(output, facts):
    lines = ["# Standalone validator 集計", "", f"完全成功: {facts['complete']}。予定 {facts['expected_jobs']}、観測 {facts['observed_records']}。",
             "", "数値は反復→seed の二段階中央値。範囲は seed 間 min/max で信頼区間ではない。",
             "validator rate は commit_count / validator 秒であり DBMS throughput ではない。RSS は process 高水位。",
             "不完全 seed を条件推定に混ぜず、全観測・失敗は CSV に保持する。", "",
             "|条件|方式|確定|FVS|全体 ms|RSS KiB|validator commits/s|完全 seed|",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in facts["condition_metrics"]:
        values = [row["condition"], row["mode"]] + [fmt(row[x + "_median"]) for x in ("commit_count", "fvs_size", "total_ms", "peak_rss_kib", "validator_commits_per_second")]
        values.append(f"{row['complete_seeds']}/{row['expected_seeds']}")
        lines.append("|" + "|".join(values) + "|")
    lines += ["", "## 同一 trace・同一反復の paired 比較", "", "時間比と rate 比は分子/分母、差は分子−分母。各比を反復内で計算してから中央値を取る。",
              "", "|条件|分子/分母|時間比 [min,max]|確定差 [min,max]|rate 比 [min,max]|完全 seed|", "|---|---|---:|---:|---:|---:|"]
    for row in facts["paired_condition_metrics"]:
        values = [row["condition"], row["numerator"] + "/" + row["denominator"]]
        for metric in ("total_ms_ratio", "commit_delta", "validator_rate_ratio"):
            values.append(fmt(row[metric + "_median"]) + " [" + fmt(row[metric + "_minimum"]) + "," + fmt(row[metric + "_maximum"]) + "]")
        values.append(f"{row['complete_seeds']}/{row['expected_seeds']}")
        lines.append("|" + "|".join(values) + "|")
    if facts["errors"]:
        lines += ["", "## 検証エラー", ""] + ["- " + error for error in facts["errors"]]
    (output / "tables_ja.md").write_text("\n".join(lines) + "\n")


def make_plot(output, facts):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    configs = {c["condition"]: c for c in facts["conditions"] if c["arity"] == 2 and c["k"] == 1
               and c["suite"] in ("main", "scale") and c["distribution"] in ("uniform", "zipf")}
    if not configs:
        return
    fig, axes = plt.subplots(2, 3, figsize=(14, 7), squeeze=False)
    modes = [m for m in ("paper", "graph", "lazy", "profile", "adaptive", "accept_id", "accept_static_degree")
             if any(r["mode"] == m for r in facts["condition_metrics"])]
    for di, distribution in enumerate(("uniform", "zipf")):
        for mi, (metric, label) in enumerate((("total_ms", "Validator total (ms)"), ("commit_count", "Commit count"), ("peak_rss_kib", "Process peak RSS (KiB)"))):
            ax = axes[di][mi]
            for mode in modes:
                samples = [r for r in facts["condition_metrics"] if r["condition"] in configs and r["mode"] == mode
                           and configs[r["condition"]]["distribution"] == distribution and r[metric + "_median"] is not None]
                samples.sort(key=lambda r: configs[r["condition"]]["n"])
                if not samples:
                    continue
                xs = [configs[r["condition"]]["n"] for r in samples]
                ax.plot(xs, [r[metric + "_median"] for r in samples], marker="o", markersize=3, label=mode)
                ax.fill_between(xs, [r[metric + "_minimum"] for r in samples], [r[metric + "_maximum"] for r in samples], alpha=.08)
            ax.set_xscale("log", base=2)
            if metric == "total_ms":
                ax.set_yscale("log")
            ax.set_title(distribution + ": " + label)
            ax.set_xlabel("Transactions per batch")
            ax.grid(alpha=.25)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False)
    fig.suptitle("Synthetic complete 2-key RMW / k=1 / standalone validator\nMedians across input seeds; bands are min/max, not confidence intervals")
    fig.tight_layout(rect=(0, .09, 1, .92))
    fig.savefig(output / "main.png", dpi=170)
    fig.savefig(output / "main.svg")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()
    output = args.output or args.input / "summary"
    try:
        facts = analyze(args.input.resolve(), output.resolve(), not args.no_plots)
    except (ValueError, KeyError, TypeError, OSError, tarfile.TarError) as exc:
        output.mkdir(parents=True, exist_ok=True)
        facts = dict(complete=False, errors=["aggregation setup failure: " + str(exc)])
        save(output / "facts.json", facts)
    print(json.dumps({key: facts[key] for key in ("complete", "expected_jobs", "observed_records", "statuses", "errors") if key in facts}, ensure_ascii=False))
    return 0 if facts["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

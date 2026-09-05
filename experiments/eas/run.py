#!/usr/bin/env python3
"""Saved-trace, fresh-process, paired EAS experiments (Python standard library)."""
import argparse
import bisect
import datetime as dt
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import shlex
import shutil
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SUITES = ("main", "arity", "worst", "constant", "scale", "zero_commit")


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            digest.update(part)
    return digest.hexdigest()


def command_output(command, cwd=ROOT):
    try:
        result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=15)
        return {"command": command, "returncode": result.returncode,
                "output": result.stdout}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"command": command, "error": str(error)}


def parse_cpus(spec):
    result = set()
    for piece in spec.split(","):
        if "-" in piece:
            left, right = map(int, piece.split("-", 1))
            result.update(range(left, right + 1))
        else:
            result.add(int(piece))
    allowed = set(os.sched_getaffinity(0))
    if not result or not result <= allowed:
        raise argparse.ArgumentTypeError("CPUs must be a nonempty subset of process affinity")
    return sorted(result)


def configurations(plan, smoke=False, suites=None):
    result = []
    for suite in SUITES:
        if suites and suite not in suites:
            continue
        entry = plan[suite]
        for arity, n, distribution, workers in itertools.product(
                entry["arity"], entry["n"], entry["distribution"], entry.get("workers", [1])):
            if smoke and not (
                suite == "main" and n == 128 or
                suite == "worst" and arity == 2 and n == 256 or
                suite == "zero_commit"):
                continue
            item = dict(suite=suite, arity=arity, n=n, distribution=distribution,
                        workers=workers, policy_k=entry["k"], key_count=plan["key_count"],
                        zipf=entry.get("zipf", 0.99),
                        selector_only=entry.get("selector_only", False))
            item["condition"] = (f"{suite}-l{arity}-n{n}-{distribution}"
                                 f"-w{workers}-k{entry['k']}")
            # Configuration-dependent batch identity, independent of mode/worker scheduling.
            identity = {key: item[key] for key in ("arity", "n", "distribution", "key_count", "zipf")}
            item["batch_id"] = int(hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:8], 16)
            result.append(item)
    return result


def generate_trace(path, condition, seed):
    """Per-ID RNG. Redraw duplicate keys until exactly arity distinct keys exist."""
    arity, key_count = condition["arity"], condition["key_count"]
    if not 0 <= arity <= key_count:
        raise ValueError("arity must be between zero and key_count")
    distribution = condition["distribution"]
    cumulative = []
    if distribution == "zipf":
        total = 0.0
        for rank in range(1, key_count + 1):
            total += rank ** (-condition["zipf"])
            cumulative.append(total)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as stream:
        stream.write(f"EAS_TRACE_V1 {key_count} {seed} {condition['batch_id']}\n")
        for transaction_id in range(1, condition["n"] + 1):
            if distribution == "identical":
                keys = list(range(arity))
            else:
                rng = random.Random(f"EAS-v1:{seed}:{condition['batch_id']}:{transaction_id}")
                unique = set()
                while len(unique) < arity:
                    key = (rng.randrange(key_count) if distribution == "uniform" else
                           bisect.bisect_left(cumulative, rng.random() * cumulative[-1]))
                    unique.add(key)
                keys = sorted(unique)
            stream.write(f"{transaction_id}\t{','.join(map(str, keys))}\n")


def benchmark_command(args, condition, mode, trace, output, incidence=None):
    command = [str(args.binary), "--mode", mode, "--trace", str(trace),
               "--k", str(condition["policy_k"]), "--workers", str(condition["workers"]),
               "--max-incidence", str(args.max_incidence if incidence is None else incidence),
               "--max-graph-bytes", str(args.max_graph_bytes), "--output", str(output)]
    if condition["selector_only"]:
        command.append("--selector-only")
    return command


def execute(command, prefix, timeout, memory_mib, cpus):
    """One new process per invocation. RLIMIT_AS is an address-space cap, not an RSS cap."""
    stdout_path = prefix.with_suffix(".stdout.log")
    stderr_path = prefix.with_suffix(".stderr.log")
    rss_path = prefix.with_suffix(".rss.txt")
    wrapped = command
    if Path("/usr/bin/time").exists():
        wrapped = ["/usr/bin/time", "-f", "%M", "-o", str(rss_path)] + command

    def child_limits():
        limit = memory_mib * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        os.sched_setaffinity(0, cpus)

    result = {"command": command, "wrapper_command": wrapped, "timeout_seconds": timeout,
              "memory_mib": memory_mib, "memory_limit_kind": "RLIMIT_AS",
              "affinity": cpus, "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "stdout": str(stdout_path), "stderr": str(stderr_path), "rss_file": str(rss_path)}
    started = time.monotonic()
    with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
        try:
            process = subprocess.Popen(wrapped, cwd=ROOT, stdout=stdout, stderr=stderr,
                                       preexec_fn=child_limits, start_new_session=True)
            result["wrapper_pid"] = process.pid
            try:
                result["returncode"] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                result["returncode"] = process.returncode
                result["status"] = "timeout"
            except KeyboardInterrupt:
                # The benchmark has its own session; stop it explicitly before allowing resume.
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                result["returncode"] = process.returncode
                result["status"] = "interrupted"
        except (OSError, subprocess.SubprocessError) as error:
            result.update(status="error", error=str(error))
    result["process_wall_seconds"] = time.monotonic() - started
    result["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    if rss_path.exists():
        for line in reversed(rss_path.read_text().splitlines()):
            if line.isdigit():
                result["runner_peak_rss_kib"] = int(line)
                break
    if "status" not in result:
        result["status"] = "ok" if result.get("returncode") == 0 else "error"
        error_text = stderr_path.read_text(errors="replace")
        if any(term in error_text for term in ("std::bad_alloc", "Cannot allocate memory", "out of memory")):
            result["status"] = "oom"
        elif result.get("returncode") in (-signal.SIGKILL, 128 + signal.SIGKILL):
            result["status"] = "killed_unknown"  # Do not infer OOM from SIGKILL alone.
    return result


def inspect_benchmark(record, raw_path):
    if not raw_path.exists():
        if record["status"] == "ok":
            record.update(status="error", error="benchmark produced no JSON")
        return
    try:
        raw = json.loads(raw_path.read_text())
    except (ValueError, OSError) as error:
        record.update(status="error", error=f"invalid benchmark JSON: {error}")
        return
    record["raw_sha256"] = sha256(raw_path)
    # A timed-out process must never be converted to a completed observation.
    if record["status"] not in ("timeout", "oom", "killed_unknown", "interrupted"):
        record["status"] = raw.get("status", record["status"])
        if record["status"] == "ok" and record.get("returncode") != 0:
            record.update(status="error", error="nonzero exit code with ok JSON")
        if record["status"] == "ok" and raw.get("verification") != "passed":
            record.update(status="verification_failed", error="benchmark verification did not pass")
    for key in ("verification", "error", "actual_arity", "arity_min", "arity_max"):
        if key in raw:
            record[key] = raw[key]
    decisions = raw.get("decisions")
    if record["status"] == "ok":
        if not isinstance(decisions, dict) or not all(key in decisions for key in ("abort_rounds", "commit", "certificate")):
            record.update(status="verification_failed", error="missing exact decision arrays")
        else:
            record["decision_sha256"] = hashlib.sha256(
                json.dumps(decisions, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def check_pairs(records, destination):
    def decisions(record):
        original = Path(record["raw_path"])
        local = Path(destination).parent / "raw" / original.name
        return json.loads((local if local.exists() else original).read_text())["decisions"]

    groups = {}
    for record in records:
        if record["phase"] == "measure" and record["mode"] != "native":
            groups.setdefault((record["condition"], record["seed"]), []).append(record)
    checks = []
    for (condition, seed), values in sorted(groups.items()):
        valid = [value for value in values if value["status"] == "ok"]
        expected_modes = ["graph", "lazy", "profile", "adaptive"]
        unavailable = {mode: "not_run" for mode in expected_modes if mode not in {v["mode"] for v in values}}
        unavailable.update({v["mode"]: v["status"] for v in values if v["status"] != "ok"})
        comparison = {"condition": condition, "seed": seed, "expected_modes": expected_modes,
                      "successful_modes": [v["mode"] for v in valid],
                      "unavailable": unavailable}
        if valid:
            reference = decisions(valid[0])
            mismatch = []
            # Compare complete arrays, not merely their checksums.
            for value in valid[1:]:
                actual = decisions(value)
                if actual != reference:
                    mismatch.append(value["mode"])
            comparison.update(reference_mode=valid[0]["mode"], mismatch_modes=mismatch)
            comparison["status"] = ("failed" if mismatch else "passed" if len(valid) == len(expected_modes)
                                    else "partial" if len(valid) > 1 else "insufficient")
        else:
            comparison["status"] = "unavailable"
        checks.append(comparison)
    save_json(destination, {"comparison": "exact abort rounds, commit mask, certificate; native policy excluded",
                            "checks": checks, "failed": sum(x["status"] == "failed" for x in checks)})
    return checks


def main(argv=None):
    def terminate_handler(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate_handler)
    parser = argparse.ArgumentParser(description=__doc__)
    extent = parser.add_mutually_exclusive_group(required=True)
    extent.add_argument("--smoke", action="store_true")
    extent.add_argument("--full", action="store_true")
    parser.add_argument("--plan", type=Path, default=HERE / "plan.json")
    parser.add_argument("--binary", type=Path, default=ROOT / "build" / "bench_eas")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--suite", action="append", choices=SUITES)
    parser.add_argument("--seeds", help="comma-separated override; default is all five prespecified seeds")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--memory-mib", type=int)
    parser.add_argument("--total-seconds", type=float)
    parser.add_argument("--max-incidence", type=int)
    parser.add_argument("--max-graph-bytes", type=int)
    parser.add_argument("--cpus", type=parse_cpus, default=sorted(os.sched_getaffinity(0)))
    parser.add_argument("--resume", action="store_true", help="continue missing records; never rerun saved failures")
    parser.add_argument("--dry-run", action="store_true", help="save manifest and environment without generating traces/running")
    args = parser.parse_args(argv)
    plan = json.loads(args.plan.read_text())
    budgets = plan["budgets"]
    for field, key in (("timeout", "process_timeout_seconds"), ("memory_mib", "memory_mib"),
                       ("total_seconds", "total_seconds"), ("max_incidence", "max_subset_incidence"),
                       ("max_graph_bytes", "max_graph_bytes")):
        if getattr(args, field) is None:
            setattr(args, field, budgets[key])
        if getattr(args, field) <= 0:
            parser.error(f"--{field.replace('_', '-')} must be positive")
    args.binary = args.binary.resolve()
    args.output = args.output.resolve()
    if not args.dry_run and not args.binary.is_file():
        parser.error(f"benchmark binary does not exist: {args.binary}")
    seeds = list(map(int, args.seeds.split(","))) if args.seeds else plan["seeds"]
    if len(set(seeds)) != len(seeds) or not seeds or any(seed < 0 or seed >= 2**64 for seed in seeds):
        parser.error("seeds must be distinct uint64 values and nonempty")
    conditions = configurations(plan, args.smoke, args.suite)
    if not conditions:
        parser.error("no configurations selected")
    args.output.mkdir(parents=True, exist_ok=True)
    for name in ("raw", "records", "traces", "logs"):
        (args.output / name).mkdir(exist_ok=True)
    identity = dict(binary_sha256=sha256(args.binary) if args.binary.exists() else None,
                    plan_sha256=sha256(args.plan), runner_sha256=sha256(Path(__file__)), smoke=args.smoke, suites=args.suite,
                    seeds=seeds, timeout=args.timeout, memory_mib=args.memory_mib,
                    max_incidence=args.max_incidence, max_graph_bytes=args.max_graph_bytes,
                    total_seconds=args.total_seconds, cpus=args.cpus)
    manifest_path = args.output / "manifest.json"
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        if not args.resume:
            parser.error("output manifest already exists; choose a fresh directory or use --resume")
        if old["identity"] != identity:
            parser.error("resume identity differs (binary/plan/arguments); use a fresh output directory")
    elif args.resume:
        parser.error("--resume requires an existing manifest")
    else:
        environment = {"captured_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                       "python": sys.version, "platform": platform.platform(),
                       "uname": list(platform.uname()), "affinity_available": sorted(os.sched_getaffinity(0)),
                       "affinity_used": args.cpus, "logical_cpu_count": os.cpu_count(),
                       "memory_limit_kind": "RLIMIT_AS; measured peak RSS is process-wide",
                       "argv": sys.argv, "command": shlex.join([sys.executable] + sys.argv),
                       "commands": {name: command_output(command) for name, command in (
                           ("git_head", ["git", "rev-parse", "HEAD"]),
                           ("git_status", ["git", "status", "--short"]),
                           ("git_diff", ["git", "diff", "--stat"]),
                           ("cpu", ["lscpu"]), ("compiler", ["c++", "--version"]),
                           ("cmake", ["cmake", "--version"]))}}
        for filename in ("/proc/meminfo", "/proc/version", "/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/cpu.max"):
            path = Path(filename)
            if path.exists():
                environment[filename] = path.read_text()
        for filename in ("CMakeCache.txt", "CMakeFiles/bench_eas.dir/flags.make", "CMakeFiles/bench_eas.dir/link.txt"):
            path = args.binary.parent / filename
            if path.exists():
                environment[filename] = path.read_text()
        save_json(args.output / "environment.json", environment)
        shutil.copyfile(args.plan, args.output / "plan.json")
        save_json(manifest_path, {"identity": identity, "conditions": conditions,
                  "order_seed": plan["order_seed"], "trace_generator": "Python Random version 2, per (seed,batch,id), duplicate redraw",
                  "warmup": "seed=7; one separate unmeasured process per condition/mode, before its five measurements",
                  "scope": "single batch one attempt; no retry; no simultaneous benchmark processes",
                  "capacity_probes": "full only: constant arity 8 trace, max incidence 1, all EAS modes; expected unsupported",
                  "timing": "benchmark intervals exclude generation, DB init, verification; process_wall_seconds is orchestration only"})
    if args.dry_run:
        print(json.dumps({"conditions": len(conditions), "output": str(args.output), "status": "dry_run"}))
        return 0

    order_rng = random.Random(plan["order_seed"])
    jobs = []
    for condition in conditions:
        modes = [mode for mode in plan["modes"] if mode != "native" or not condition["selector_only"]]
        for phase, seed in [("warmup", 7)] + [("measure", seed) for seed in seeds]:
            order = modes[:]
            order_rng.shuffle(order)
            for mode in order:
                jobs.append((condition, phase, seed, mode, args.max_incidence))
    # A required safety control, kept out of every performance summary/ratio.
    if args.full and (not args.suite or "constant" in args.suite):
        probe = next(c for c in conditions if c["suite"] == "constant" and c["arity"] == 8)
        for mode in ("graph", "lazy", "profile", "adaptive"):
            jobs.append((probe, "capacity_probe", seeds[0], mode, 1))
    commands_path = args.output / "commands.json"
    all_commands = []
    for condition, phase, seed, mode, incidence in jobs:
        stem = f"{condition['condition']}-s{seed}-{phase}-{mode}"
        trace = args.output / "traces" / f"{condition['condition']}-s{seed}.tsv"
        raw = args.output / "raw" / f"{stem}.json"
        command = benchmark_command(args, condition, mode, trace, raw, incidence)
        all_commands.append({"id": stem, "command": command, "shell": shlex.join(command)})
    save_json(commands_path, all_commands)
    records = []
    started = time.monotonic()
    # Preserve time consumed before an interruption; a resume receives only the remaining budget.
    progress_path = args.output / "progress.json"
    consumed = (json.loads(progress_path.read_text())["elapsed_seconds_total"]
                if args.resume and progress_path.exists() else
                sum(json.loads(path.read_text()).get("process_wall_seconds", 0)
                    for path in (args.output / "records").glob("*.json")) if args.resume else 0.0)
    trace_hashes = {}
    for index, (condition, phase, seed, mode, incidence) in enumerate(jobs):
        spec = all_commands[index]
        stem = spec["id"]
        record_path = args.output / "records" / f"{stem}.json"
        if args.resume and record_path.exists():
            record = json.loads(record_path.read_text())
            records.append(record)
            continue
        trace = args.output / "traces" / f"{condition['condition']}-s{seed}.tsv"
        raw_path = args.output / "raw" / f"{stem}.json"
        record = dict(condition, phase=phase, seed=seed, mode=mode, sequence=index,
                      trace_path=str(trace), raw_path=str(raw_path), command=spec["command"],
                      max_incidence=incidence, max_graph_bytes=args.max_graph_bytes,
                      expected_status="unsupported" if phase == "capacity_probe" else "ok")
        remaining = args.total_seconds - consumed - (time.monotonic() - started)
        if remaining <= 0:
            record.update(status="budget_exhausted", reason="runner total wall-time budget exhausted")
        elif condition["workers"] > len(args.cpus):
            record.update(status="unsupported", reason="requested workers exceed selected available CPUs")
        else:
            if str(trace) not in trace_hashes:
                if not trace.exists():
                    generate_trace(trace, condition, seed)
                trace_hashes[str(trace)] = sha256(trace)
            record["trace_sha256"] = trace_hashes[str(trace)]
            remaining = args.total_seconds - consumed - (time.monotonic() - started)
            if remaining <= 0:
                record.update(status="budget_exhausted", reason="total budget exhausted during trace generation")
            else:
                record.update(execute(spec["command"], args.output / "logs" / stem,
                                      min(args.timeout, remaining), args.memory_mib, args.cpus))
                inspect_benchmark(record, raw_path)
        if phase == "capacity_probe":
            record["control_passed"] = record["status"] == "unsupported"
        save_json(record_path, record)
        records.append(record)
        save_json(progress_path, {"elapsed_seconds_total": consumed + time.monotonic() - started,
                                  "last_sequence": index, "last_status": record["status"]})
        print(f"[{index + 1}/{len(jobs)}] {stem}: {record['status']}", flush=True)
        if record["status"] == "interrupted":
            break
    # Rebuild the append-free aggregate from the authoritative one-file-per-run records.
    with (args.output / "runs.jsonl").open("w") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    checks = check_pairs(records, args.output / "decision_checks.json")
    counts = {}
    for record in records:
        phase = record["phase"]
        counts.setdefault(phase, {})[record["status"]] = counts.setdefault(phase, {}).get(record["status"], 0) + 1
    result = {"counts": counts, "pair_checks": {status: sum(c["status"] == status for c in checks)
              for status in sorted({c["status"] for c in checks})},
              "wall_seconds_this_invocation": time.monotonic() - started,
              "prior_elapsed_seconds": consumed, "total_budget_seconds": args.total_seconds,
              "expected_jobs": len(jobs), "saved_jobs": len(records),
              "successful_capacity_probes": sum(r.get("control_passed", False) for r in records),
              "completed_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    save_json(args.output / "run_summary.json", result)
    save_json(progress_path, {"elapsed_seconds_total": consumed + time.monotonic() - started,
                              "saved_jobs": len(records), "expected_jobs": len(jobs)})
    print(json.dumps(result, sort_keys=True))
    failed = any(c["status"] == "failed" for c in checks) or any(
        r["status"] in ("error", "verification_failed") or r.get("control_passed") is False for r in records)
    if any(record["status"] == "interrupted" for record in records):
        return 130
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

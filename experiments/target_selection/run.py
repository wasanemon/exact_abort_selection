#!/usr/bin/env python3
"""Issue #4: preregistered standalone validator experiment, sequential processes."""
import argparse
import collections
import datetime as dt
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import platform
import random
import shutil
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
spec = importlib.util.spec_from_file_location("old_eas_runner", ROOT / "experiments/eas/run.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
save, sha256 = old.save_json, old.sha256


def conditions(plan, smoke=False):
    result = []
    for suite in ("main", "scale", "paper_k", "dense"):
        entry = plan[suite]
        for a, n, d, k in itertools.product(entry["arity"], entry["n"], entry["distribution"], entry["k"]):
            if smoke and not (suite == "main" and n == 40 or suite == "paper_k" and n == 40):
                continue
            c = dict(suite=suite, arity=a, n=n, distribution=d, k=k,
                     key_count=plan["key_count"], zipf=plan["zipf"])
            identity = {key: c[key] for key in ("arity", "n", "distribution", "key_count", "zipf")}
            c["batch_id"] = int(hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:8], 16)
            c["condition"] = f"{suite}-l{a}-n{n}-{d}-k{k}"
            result.append(c)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--cpus", type=old.parse_cpus, default=[min(os.sched_getaffinity(0))])
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()
    output, binary = args.output.resolve(), args.binary.resolve()
    if output.exists():
        p.error("use a new output directory; saved observations are immutable")
    if not binary.is_file():
        p.error("binary not found")
    build_path = binary.with_suffix(".build.json")
    if not build_path.is_file():
        p.error("build provenance missing; use build.py")
    build = json.loads(build_path.read_text())
    if build.get("returncode") != 0 or build.get("binary_sha256") != sha256(binary):
        p.error("binary does not match successful build provenance")
    if build.get("git_status"):
        p.error("benchmark requires a build from a clean source checkout")
    if any(sha256(ROOT / source) != digest for source, digest in build["source_sha256"].items()):
        p.error("measured binary sources differ from this checkout")
    plan = json.loads((HERE / "plan.json").read_text())
    gate = json.loads((HERE / "gate.json").read_text())
    if gate["minimal_reproduction"] != "GO_LIMITED":
        p.error("minimal reproduction gate is not open")
    output.mkdir(parents=True)
    for sub in ("traces", "raw", "logs"):
        (output / sub).mkdir()
    save(output / "plan.json", plan)
    save(output / "gate.json", gate)
    save(output / "build.json", build)
    configs = conditions(plan, args.smoke)
    rng, jobs, traces = random.Random(plan["order_seed"]), [], {}
    for c in configs:
        for seed in plan["seeds"]:
            name = f"l{c['arity']}-n{c['n']}-{c['distribution']}-s{seed}.tsv"
            trace = output / "traces" / name
            if name not in traces:
                old.generate_trace(trace, c, seed)
                traces[name] = dict(path=str(trace.relative_to(output)), sha256=sha256(trace), batch_id=c["batch_id"])
            for rep in range(1, plan["repetitions_per_seed"] + 1):
                modes = plan["variants"][:]
                rng.shuffle(modes)
                for mode in modes:
                    jobs.append(dict(c, seed=seed, repetition=rep, mode=mode, trace=name,
                                     trace_sha256=traces[name]["sha256"],
                                     id=f"{c['condition']}-s{seed}-r{rep}-{mode}"))
    save(output / "trace_manifest.json", traces)
    save(output / "manifest.json", dict(scope="smoke" if args.smoke else "full", expected_jobs=len(jobs), conditions=configs, jobs=jobs,
                                        binary_sha256=sha256(binary), plan_sha256=sha256(HERE / "plan.json"),
                                        saved_plan_sha256=sha256(output / "plan.json"), saved_gate_sha256=sha256(output / "gate.json"),
                                        runner_sha256=sha256(Path(__file__)), shared_runner_sha256=sha256(Path(old.__file__))))
    env = dict(captured_utc=dt.datetime.now(dt.timezone.utc).isoformat(), argv=sys.argv,
               python=sys.version, platform=platform.platform(), affinity_used=args.cpus,
               affinity_available=sorted(os.sched_getaffinity(0)),
               binary_sha256=sha256(binary), source_sha256={
                   str(f.relative_to(ROOT)): sha256(f) for f in
                   [HERE / "validator.cpp", ROOT / "eas/Selector.cpp", ROOT / "eas/Oracle.cpp", ROOT / "eas/Selector.h"]},
               commands={name: old.command_output(cmd) for name, cmd in [
                   ("git_head", ["git", "rev-parse", "HEAD"]), ("git_status", ["git", "status", "--short"]),
                   ("compiler", ["g++", "--version"]), ("cpu", ["lscpu"]), ("ram", ["cat", "/proc/meminfo"])]})
    save(output / "environment.json", env)
    budget = plan["budgets"]
    started, statuses = time.monotonic(), collections.Counter()
    with (output / "runs.jsonl").open("w") as stream:
        for number, job in enumerate(jobs, 1):
            command = [str(binary), "--trace", str(output / "traces" / job["trace"]),
                       "--mode", job["mode"], "--k", str(job["k"])]
            if time.monotonic() - started >= budget["total_seconds"]:
                record = dict(job, status="not_run_budget", command=command)
            else:
                run = old.execute(command, output / "logs" / job["id"],
                                  budget["timeout_seconds_per_process"], budget["address_space_mib"], args.cpus)
                record = dict(job, **run)
                raw_path = output / "raw" / (job["id"] + ".json")
                stdout = Path(run["stdout"])
                if stdout.exists():
                    shutil.copyfile(stdout, raw_path)
                    record["raw_path"] = str(raw_path.relative_to(output))
                    record["raw_sha256"] = sha256(raw_path)
                    if record["status"] not in ("timeout", "killed_unknown", "interrupted"):
                        try:
                            raw = json.loads(raw_path.read_text())
                            record["status"] = raw.get("status", "error")
                            if record["status"] == "ok" and (run.get("returncode") != 0 or raw.get("verification") != "passed"):
                                record.update(status="verification_failed")
                        except (ValueError, OSError):
                            record.update(status="error", error="invalid JSON")
            statuses[record["status"]] += 1
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()
            if number % 50 == 0 or number == len(jobs):
                progress = dict(completed=number, expected=len(jobs), statuses=dict(statuses), elapsed_seconds=time.monotonic()-started)
                save(output / "progress.json", progress)
                print(json.dumps(progress), flush=True)
    save(output / "run_summary.json", dict(expected=len(jobs), observed=sum(statuses.values()), statuses=dict(statuses)))
    return 0 if statuses == {"ok": len(jobs)} else 1


if __name__ == "__main__":
    raise SystemExit(main())

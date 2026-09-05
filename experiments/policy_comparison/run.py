#!/usr/bin/env python3
"""Prespecified Issue #3 experiment. Sequential fresh processes, paired 5 seeds x 3 timings."""
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
import shlex
import signal
import sys
import tarfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
spec = importlib.util.spec_from_file_location("eas_runner", ROOT / "experiments/eas/run.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
save_json, sha256 = old.save_json, old.sha256


def configurations(plan, smoke=False):
    result = []
    def add(suite, arity, n, distribution, workers, variants):
        c = dict(suite=suite, arity=arity, n=n, distribution=distribution, workers=workers,
                 key_count=plan["key_count"], zipf=plan["zipf"], selector_only=False)
        identity = {k:c[k] for k in ("arity","n","distribution","key_count","zipf")}
        c["batch_id"] = int(hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:8],16)
        c["condition"] = f"l{arity}-n{n}-{distribution}-w{workers}"
        c["variants"] = variants
        result.append(c)
    primary = ["native","accept_id","accept_static_degree","eas_k1_adaptive","eas_k2_adaptive"]
    if smoke:
        for d in ("uniform","zipf"):
            add("main",2,128,d,1,primary[:])
        for w in (1,2,4):
            add("smoke_parallel",2,32,"zipf",w,primary[:])
        add("zero_commit",1,2,"identical",1,primary[:])
        add("control",2,32,"identical",1,[f"eas_k1_{m}" for m in plan["control_implementations"]])
        return result
    for suite in ("main","arity","scale"):
        e = plan[suite]
        for a,n,d,w in itertools.product(e["arity"],e["n"],e["distribution"],e["workers"]):
            variants = primary[:]
            if suite=="main" and n==8192:
                variants += ["eas_k1_graph","eas_k1_lazy","eas_k1_profile"]
            add(suite,a,n,d,w,variants)
    add("control",2,4096,"identical",1,[f"eas_k1_{m}" for m in plan["control_implementations"]])
    return result


def variant_fields(variant):
    if variant.startswith("eas_"):
        _, k, implementation = variant.split("_")
        return dict(variant=variant, policy="eas", policy_k=int(k[1:]), implementation=implementation, mode=implementation)
    return dict(variant=variant, policy=variant, policy_k=None,
                implementation="native" if variant=="native" else "greedy", mode=variant)


def jobs_for(plan, conditions):
    rng = random.Random(plan["order_seed"])
    jobs = []
    for c in conditions:
        blocks = [("warmup",7,0)] + [("measure",s,r) for s in plan["seeds"] for r in range(1,plan["repetitions_per_seed"]+1)]
        for phase,seed,rep in blocks:
            variants=c["variants"][:];rng.shuffle(variants)
            for v in variants:
                job = dict(c, **variant_fields(v),phase=phase,seed=seed,repetition=rep)
                job["id"]=f"{c['condition']}-s{seed}-r{rep}-{phase}-{v}"
                jobs.append(job)
    return jobs


def prepare_traces(output, jobs):
    archive = ROOT / "experiments/eas/results/full/raw_data.tar.gz"
    old_conditions = json.loads((archive.parent/"manifest.json").read_text())["conditions"]
    metadata = {}
    with tarfile.open(archive,"r:gz") as tar:
        names = set(tar.getnames())
        for job in jobs:
            name=f"l{job['arity']}-n{job['n']}-{job['distribution']}-s{job['seed']}.tsv"
            if name in metadata:continue
            path=output/"traces"/name
            old.generate_trace(path,job,job["seed"])
            regenerated=path.read_bytes()
            item=dict(path=str(path.relative_to(output)),sha256=sha256(path),batch_id=job["batch_id"],source="generated_missing_archive_condition")
            for c in old_conditions:
                if all(c[k]==job[k] for k in ("arity","n","distribution","batch_id")):
                    member=f"traces/{c['condition']}-s{job['seed']}.tsv"
                    if member not in names:continue
                    saved=tar.extractfile(member).read()
                    if saved!=regenerated:raise RuntimeError(f"archived TSV differs from generator: {member}")
                    path.write_bytes(saved)  # archived bytes are the source of benchmark input
                    item.update(source=str(archive.relative_to(ROOT)),member=member,regenerated_bytes_equal=True,
                                archived_sha256=hashlib.sha256(saved).hexdigest())
                    break
            metadata[name]=item
    save_json(output/"trace_manifest.json",dict(archive_sha256=sha256(archive),traces=metadata))
    return metadata


def local_raw(output,record):
    return output/"raw"/Path(record["raw_path"]).name


def check_decisions(output, records):
    """One exact comparison group per trace, worker count, policy AND k; includes repeats."""
    groups=collections.defaultdict(list)
    for r in records:
        if r["phase"]=="measure":
            groups[(r["trace_sha256"],r["workers"],r["policy"],r["policy_k"])].append(r)
    checks=[]
    for key, values in groups.items():
        valid=[r for r in values if r["status"]=="ok"]
        expected=len(values)
        reference=None;mismatch=[]
        for r in valid:
            actual=json.loads(local_raw(output,r).read_text())["decisions"]
            if reference is None:reference=actual
            elif actual!=reference:mismatch.append(r["id"])
        checks.append(dict(trace_sha256=key[0],workers=key[1],policy=key[2],policy_k=key[3],
                           observations=expected,successful=len(valid),implementations=sorted({r["implementation"] for r in valid}),
                           status="failed" if mismatch else "passed" if len(valid)==expected else "incomplete",mismatch=mismatch))
    save_json(output/"decision_checks.json",dict(checks=checks,failed=sum(c["status"]=="failed" for c in checks)))
    return checks


def main():
    p=argparse.ArgumentParser()
    choice=p.add_mutually_exclusive_group(required=True);choice.add_argument("--full",action="store_true");choice.add_argument("--smoke",action="store_true")
    p.add_argument("--output",type=Path,required=True);p.add_argument("--binary",type=Path,default=ROOT/"build/bench_eas")
    p.add_argument("--cpus",type=old.parse_cpus,default=sorted(os.sched_getaffinity(0)))
    p.add_argument("--resume",action="store_true")
    args=p.parse_args();args.output=args.output.resolve();args.binary=args.binary.resolve()
    plan=json.loads((HERE/"plan.json").read_text());budget=plan["budgets"]
    conditions=configurations(plan,args.smoke);jobs=jobs_for(plan,conditions)
    args.output.mkdir(parents=True,exist_ok=True)
    for name in ("traces","raw","records","logs"):(args.output/name).mkdir(exist_ok=True)
    identity=dict(binary_sha256=sha256(args.binary),runner_sha256=sha256(Path(__file__)),shared_runner_sha256=sha256(Path(old.__file__)),
                  plan_sha256=sha256(HERE/"plan.json"),smoke=args.smoke,cpus=args.cpus)
    manifest=args.output/"manifest.json"
    if manifest.exists():
        if not args.resume or json.loads(manifest.read_text())["identity"]!=identity:p.error("existing output or resume identity mismatch; choose fresh output")
        traces=json.loads((args.output/"trace_manifest.json").read_text())["traces"]
        for t in traces.values():
            if sha256(args.output/t["path"])!=t["sha256"]:raise RuntimeError("resume trace hash mismatch")
    else:
        if args.resume:p.error("resume needs a manifest")
        save_json(manifest,dict(identity=identity,conditions=conditions,expected_jobs=len(jobs)))
        save_json(args.output/"plan.json",plan)
        env=dict(captured_utc=dt.datetime.now(dt.timezone.utc).isoformat(),command=shlex.join([sys.executable]+sys.argv),
                 affinity_used=args.cpus,python=sys.version,platform=platform.platform(),
                 commands={n:old.command_output(cmd) for n,cmd in (
                     ("git_head",["git","rev-parse","HEAD"]),("git_status",["git","status","--short"]),
                     ("cpu",["lscpu"]),("compiler",["c++","--version"]),("cmake",["cmake","--version"]))})
        for f in ("/proc/meminfo","/proc/version","/sys/fs/cgroup/cpu.max","/sys/fs/cgroup/memory.max"):
            if Path(f).exists():env[f]=Path(f).read_text()
        for f in ("CMakeCache.txt","CMakeFiles/bench_eas.dir/flags.make","CMakeFiles/bench_eas.dir/link.txt"):
            if (args.binary.parent/f).exists():env[f]=(args.binary.parent/f).read_text()
        save_json(args.output/"environment.json",env)
        traces=prepare_traces(args.output,jobs)
    commands=[]
    for job in jobs:
        name=f"l{job['arity']}-n{job['n']}-{job['distribution']}-s{job['seed']}.tsv"
        job.update(trace_path=str(args.output/"traces"/name),trace_sha256=traces[name]["sha256"],raw_path=str(args.output/"raw"/(job["id"]+".json")))
        cmd=[str(args.binary),"--trace",job["trace_path"],"--mode",job["mode"],"--k",str(job["policy_k"] or 1),"--workers",str(job["workers"]),
             "--max-incidence",str(budget["max_incidence"]),"--max-graph-bytes",str(budget["max_graph_bytes"]),"--output",job["raw_path"]]
        commands.append(dict(id=job["id"],command=cmd,shell=shlex.join(cmd)))
    save_json(args.output/"commands.json",commands)
    progress=args.output/"progress.json"
    consumed=json.loads(progress.read_text())["elapsed_seconds_total"] if args.resume and progress.exists() else 0
    started=time.monotonic();records=[]
    def stop(signum,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    for seq,(job,spec) in enumerate(zip(jobs,commands)):
        file=args.output/"records"/(job["id"]+".json")
        if args.resume and file.exists():
            r=json.loads(file.read_text());records.append(r)
            if r["status"]=="ok" and sha256(local_raw(args.output,r))!=r["raw_sha256"]:raise RuntimeError("resume raw hash mismatch")
            continue
        record=dict(job,sequence=seq,command=spec["command"])
        remaining=budget["total_seconds"]-consumed-(time.monotonic()-started)
        if remaining<=0:record.update(status="budget_exhausted")
        elif job["workers"]>len(args.cpus):record.update(status="unsupported",reason="workers exceed affinity CPUs")
        else:
            record.update(old.execute(spec["command"],args.output/"logs"/job["id"],min(budget["timeout_seconds"],remaining),budget["memory_mib"],args.cpus))
            old.inspect_benchmark(record,Path(job["raw_path"]))
        save_json(file,record);records.append(record)
        save_json(progress,dict(elapsed_seconds_total=consumed+time.monotonic()-started,saved_jobs=len(records),expected_jobs=len(jobs)))
        print(f"[{seq+1}/{len(jobs)}] {job['id']}: {record['status']}",flush=True)
        if record["status"]=="interrupted":break
    (args.output/"runs.jsonl").write_text("".join(json.dumps(r,sort_keys=True)+"\n" for r in records))
    checks=check_decisions(args.output,records)
    summary=dict(expected_jobs=len(jobs),saved_jobs=len(records),counts={phase:dict(collections.Counter(r["status"] for r in records if r["phase"]==phase)) for phase in ("warmup","measure")},
                 decision_checks=dict(collections.Counter(c["status"] for c in checks)),elapsed_seconds_total=consumed+time.monotonic()-started)
    save_json(args.output/"run_summary.json",summary);print(json.dumps(summary))
    return 0 if len(records)==len(jobs) and all(r["status"]=="ok" for r in records) and all(c["status"]=="passed" for c in checks) else 1

if __name__=="__main__":sys.exit(main())

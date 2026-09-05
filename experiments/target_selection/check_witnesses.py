#!/usr/bin/env python3
"""Replay fixed finite witnesses; recorded timings are not performance evidence."""
import argparse
import datetime as dt
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "experiments/policy_comparison/quality/witnesses.json"
MODES = ("paper", "graph", "lazy", "profile", "adaptive", "accept_id", "accept_static_degree")
EXACT = MODES[:5]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def demand(condition, message):
    if not condition:
        raise AssertionError(message)


def maximum(transactions):
    """Enumerate every transaction subset; compare logical sets pairwise."""
    keys = [set(t["keys"]) for t in transactions]
    best, certificates = 0, []
    for mask in range(1 << len(keys)):
        chosen = [i for i in range(len(keys)) if mask & (1 << i)]
        if any(keys[i] & keys[j] for i, j in itertools.combinations(chosen, 2)):
            continue
        ids = sorted(transactions[i]["id"] for i in chosen)
        if len(chosen) > best:
            best, certificates = len(chosen), [ids]
        elif len(chosen) == best:
            certificates.append(ids)
    return dict(commit_count=best, subsets_checked=1 << len(keys), certificates=certificates)


def cfbs(transactions):
    """Algorithm 4 restricted to exact known account/key sets; no batch cap."""
    occupied, chosen, deferred = set(), [], []
    for t in sorted(transactions, key=lambda t: t["id"]):
        keys = set(t["keys"])
        if occupied & keys:
            deferred.append(t["id"])
        else:
            chosen.append(t["id"])
            occupied.update(keys)
    return dict(certificate=chosen, deferred=deferred)


def execute_case(binary, directory, name, transactions, k):
    trace_text = "".join(f"{t['id']}\t{','.join(map(str, t['keys']))}\n" for t in transactions)
    trace = directory / f"{name}.tsv"
    trace.write_text(trace_text)
    results = {}
    for mode in MODES:
        command = [str(binary), "--trace", str(trace), "--mode", mode, "--k", str(k)]
        proc = subprocess.run(command, text=True, capture_output=True, timeout=30, check=False)
        raw = json.loads(proc.stdout)
        demand(proc.returncode == 0 and raw.get("status") == "ok" and raw.get("verification") == "passed",
               f"{name}/{mode}: unsuccessful validator call: {proc.stderr} {proc.stdout}")
        demand(raw["n"] == len(transactions) and raw["k"] == k and raw["mode"] == mode,
               f"{name}/{mode}: metadata mismatch")
        results[mode] = dict(command=command, returncode=proc.returncode, stderr=proc.stderr, result=raw)
    expected = results["paper"]["result"]["decisions"]
    for mode in EXACT:
        decisions = results[mode]["result"]["decisions"]
        for field in ("abort_rounds", "commit", "certificate"):
            demand(decisions[field] == expected[field], f"{name}/{mode}: exact {field} mismatch")
    optimum, cfbs_result = maximum(transactions), cfbs(transactions)
    accept = results["accept_id"]["result"]["decisions"]
    demand(accept["certificate"] == cfbs_result["certificate"] and accept["rejected_ids"] == cfbs_result["deferred"],
           f"{name}: accept_id differs from CFBS under exact known accounts")
    for mode in MODES:
        result = results[mode]["result"]
        demand(result["commit_count"] <= optimum["commit_count"], f"{name}/{mode}: exceeds independently enumerated optimum")
    return dict(name=name, k=k, transactions=transactions, trace_text=trace_text,
                trace_sha256=digest(trace_text.encode()), optimum=optimum,
                cfbs_exact_account_reference=cfbs_result, raw=results)


def check_stored(case, reference):
    transactions = case["transactions"]
    expected_mask = [int(t["id"] in reference["eas_commit"]) for t in transactions]
    for mode in EXACT:
        decisions = case["raw"][mode]["result"]["decisions"]
        demand(decisions["abort_rounds"] == reference["eas_rounds"], f"{case['name']}/{mode}: #3 abort rounds changed")
        demand(decisions["certificate"] == reference["eas_commit"], f"{case['name']}/{mode}: #3 EAS certificate changed")
        demand(decisions["commit"] == expected_mask, f"{case['name']}/{mode}: #3 EAS commit mask changed")
    static = case["raw"]["accept_static_degree"]["result"]["decisions"]
    for actual, stored in (("consideration_order", "static_order"), ("initial_degrees", "static_degrees"),
                           ("certificate", "static_commit")):
        demand(static[actual] == reference[stored], f"{case['name']}: #3 {stored} changed")
    demand(static["commit"] == [int(t["id"] in reference["static_commit"]) for t in transactions],
           f"{case['name']}: #3 static mask changed")
    demand(case["optimum"]["commit_count"] == reference["maximum"], f"{case['name']}: maximum differs from #3")
    case["stored_reference"] = {key: reference[key] for key in
                                ("direction", "maximum", "static_order", "static_degrees", "static_commit", "eas_commit", "eas_rounds")}
    case["checks"] = "exact EAS arrays, static order/degrees/certificate/mask and maximum matched Issue #3"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    binary, output = args.binary.resolve(), args.output.resolve()
    if not binary.is_file():
        parser.error("binary not found")
    if output.exists():
        parser.error("output exists; use a new path to preserve the prior validation")
    source_bytes = SOURCE.read_bytes()
    references = json.loads(source_bytes)["examples"]
    demand(len(references) == 2, "expected the two fixed Issue #3 examples")
    cases = []
    with tempfile.TemporaryDirectory(prefix="issue4_fixed_witnesses_") as temporary:
        directory = Path(temporary)
        for reference in references:
            demand(reference["found"], "stored witness was not found")
            expected_maximum = {"eas_gt_static": 4, "static_gt_eas": 3}[reference["direction"]]
            demand(reference["maximum"] == expected_maximum, "unexpected fixed witness maximum")
            case = execute_case(binary, directory, reference["direction"], reference["minimal"], 1)
            check_stored(case, reference)
            cases.append(case)
        star = [dict(id=1, keys=[0, 1]), dict(id=2, keys=[0, 2]), dict(id=3, keys=[1, 3])]
        case = execute_case(binary, directory, "lantern_cfbs_eas_star", star, 1)
        demand(case["cfbs_exact_account_reference"]["certificate"] == [1], "CFBS star reference")
        for mode in EXACT + ("accept_static_degree",):
            demand(case["raw"][mode]["result"]["decisions"]["certificate"] == [2, 3], f"star/{mode} expected leaves")
        demand(case["optimum"]["commit_count"] == 2, "star optimum")
        case["checks"] = "CFBS/accept_id commits center 1; paper/EAS/static commit leaves 2,3; policies differ"
        cases.append(case)
        same_key = [dict(id=1, keys=[0]), dict(id=2, keys=[0])]
        for k in (1, 2):
            case = execute_case(binary, directory, f"same_key_k{k}", same_key, k)
            for mode in MODES:
                result = case["raw"][mode]["result"]
                expected_count = 0 if k == 2 and mode in EXACT else 1
                demand(result["commit_count"] == expected_count, f"same key k={k}/{mode}: wrong count")
                if expected_count:
                    demand(result["decisions"]["certificate"] == [1], f"same key k={k}/{mode}: ID tie changed")
                elif mode in EXACT:
                    demand(result["decisions"]["abort_rounds"] == [[2, 1]], f"same key k=2/{mode}: frozen top-k changed")
            demand(case["optimum"]["commit_count"] == 1, "same-key maximum")
            case["checks"] = "k=2 frozen paper/EAS commits zero; k=1 and both cheap policies commit one"
            cases.append(case)
    result = dict(schema_version=1, status="passed", scope="fixed finite witness reproduction; no random search",
                  timing_use="Raw validator timings are retained only as invocation output; not performance evidence and no ratios computed.",
                  captured_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  binary=str(binary), binary_sha256=digest(binary.read_bytes()),
                  script_sha256=digest(Path(__file__).read_bytes()), source=str(SOURCE.relative_to(ROOT)),
                  source_sha256=digest(source_bytes), cases_checked=len(cases), validator_calls=len(cases)*len(MODES),
                  subsets_checked=sum(case["optimum"]["subsets_checked"] for case in cases),
                  trace_reproduction="All modes in a case read one saved temporary trace; exact trace bytes and SHA-256 are embedded below.",
                  cases=cases)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "cases_checked", "validator_calls", "subsets_checked")}))


if __name__ == "__main__":
    main()
